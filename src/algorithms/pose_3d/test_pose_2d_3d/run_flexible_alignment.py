#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵活的3D人体对齐视频生成器
支持命令行参数指定视频和pkl文件路径
支持单人和多人处理模式
"""

import argparse
import os
import sys
import cv2
import numpy as np
import joblib
import subprocess
from create_stable_3d_alignment import (
    StableAligner, render_stable_3d_model, draw_stable_2d_joints,
    create_stable_alignment_frame
)

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='3D人体对齐视频生成器 - 自动检测单人/多人模式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 自动检测模式（推荐）
  python run_flexible_alignment.py -v demo/sample_video.mp4 -p output/demo_output/sample_video/pmce_output.pkl
  
  # 强制单人模式，指定人员ID
  python run_flexible_alignment.py -v demo/twodance.mp4 -p output/demo_output/twodance/pmce_output.pkl --person-id 2
  
  # 强制多人模式
  python run_flexible_alignment.py -v demo/twodance.mp4 -p output/demo_output/twodance/pmce_output.pkl --force-multi-person
  
  # 自定义输出文件名
  python run_flexible_alignment.py -v demo/twodance.mp4 -p output/demo_output/twodance/pmce_output.pkl -o my_output.mp4
        """
    )
    
    parser.add_argument('-v', '--video', required=True,
                       help='输入视频文件路径')
    parser.add_argument('-p', '--pkl', required=True,
                       help='PMCE输出的pkl文件路径')
    parser.add_argument('-o', '--output', default=None,
                       help='输出视频文件名（默认自动生成）')
    parser.add_argument('--force-multi-person', action='store_true',
                       help='强制多人模式：同时处理所有人员（覆盖自动检测）')
    parser.add_argument('--person-id', type=int, default=None,
                       help='指定处理的人员ID（强制单人模式）')
    parser.add_argument('--scale-factor', type=float, default=4.0,
                       help='3D模型缩放因子（默认4.0）')
    parser.add_argument('--list-persons', action='store_true',
                       help='仅列出pkl文件中的人员信息，不生成视频')
    
    return parser.parse_args()

def validate_files(video_path, pkl_path):
    """验证输入文件是否存在"""
    if not os.path.exists(video_path):
        print(f"[ERROR] 视频文件不存在: {video_path}")
        return False
    
    if not os.path.exists(pkl_path):
        print(f"[ERROR] PKL文件不存在: {pkl_path}")
        return False
    
    return True

def analyze_pkl_data(pkl_path):
    """分析pkl文件中的人员数据"""
    try:
        data = joblib.load(pkl_path)
        print(f"[OK] 成功加载PMCE数据: {pkl_path}")
        
        person_infos = []
        print(f"\n[PERSONS] 检测到 {len(data)} 个人员:")
        
        for pid in sorted(data.keys()):
            person_info = data[pid]
            has_joints2d = 'joints2d' in person_info
            mesh_frames = len(person_info['mesh']) if 'mesh' in person_info else 0
            joints2d_shape = person_info['joints2d'].shape if has_joints2d else "无"
            
            print(f"   人员 {pid}: {mesh_frames} 帧, joints2d: {joints2d_shape}")
            
            if mesh_frames > 0:
                person_infos.append({
                    'id': pid,
                    'data': person_info,
                    'frames': mesh_frames,
                    'has_joints2d': has_joints2d
                })
        
        return data, person_infos
        
    except Exception as e:
        print(f"[ERROR] 加载pkl文件失败: {e}")
        return None, None

def auto_detect_mode(person_infos):
    """自动检测应该使用单人还是多人模式"""
    num_persons = len(person_infos)
    
    if num_persons == 0:
        print("[WARNING] 未检测到有效的人员数据，将输出原视频")
        return 'original', None
    elif num_persons == 1:
        print(f"[AUTO] 自动检测: 单人模式 (检测到 {num_persons} 个人员)")
        return 'single', person_infos[0]['id']
    else:
        # 检查是否有一个主要人员（帧数明显更多）
        max_frames = max(p['frames'] for p in person_infos)
        main_persons = [p for p in person_infos if p['frames'] >= max_frames * 0.8]
        
        if len(main_persons) == 1 and max_frames > 50:
            # 如果只有一个人员的帧数占主导地位，且帧数足够多，建议单人模式
            main_person = main_persons[0]
            print(f"[AUTO] 自动检测: 单人模式 (人员 {main_person['id']} 有 {main_person['frames']} 帧，占主导地位)")
            print(f"   [TIP] 提示: 如需处理所有人员，请使用 --force-multi-person 参数")
            return 'single', main_person['id']
        else:
            # 多个人员都有相当数量的帧，建议多人模式
            print(f"[AUTO] 自动检测: 多人模式 (检测到 {num_persons} 个人员，帧数相近)")
            frame_info = ", ".join([f"人员{p['id']}:{p['frames']}帧" for p in person_infos])
            print(f"   [INFO] 帧数分布: {frame_info}")
            print(f"   [TIP] 提示: 如需只处理特定人员，请使用 --person-id 参数")
            return 'multi', None

def create_single_person_video(video_path, pkl_data, person_infos, person_id, output_path, scale_factor):
    """创建单人3D对齐视频"""
    print(f"\n[VIDEO] 创建单人3D对齐视频")
    print("=" * 50)
    
    # 选择人员
    selected_person = None
    if person_id is not None:
        # 用户指定人员ID
        for person_info in person_infos:
            if person_info['id'] == person_id:
                selected_person = person_info
                break
        if selected_person is None:
            print(f"[ERROR] 未找到指定的人员ID: {person_id}")
            return False
    else:
        # 自动选择帧数最多的人员
        selected_person = max(person_infos, key=lambda x: x['frames'])
    
    print(f"[TARGET] 选择处理人员 {selected_person['id']} ({selected_person['frames']} 帧)")
    
    # 准备数据
    person_data = selected_person['data']
    
    # 处理2D关节数据
    if selected_person['has_joints2d']:
        joints_2d = person_data['joints2d']
        if len(joints_2d.shape) == 4:
            joints_2d = joints_2d[:, 0, :, :]  # 取第一个检测结果
        print(f"[OK] 使用真实的2D关节数据")
    else:
        num_frames = len(person_data['mesh'])
        joints_2d = np.zeros((num_frames, 17, 2))
        print(f"[WARNING] 生成虚拟的2D关节数据")
    
    meshes = person_data['mesh']
    print(f"[DATA] 网格数据: {meshes.shape}")
    print(f"[DATA] 2D关节数据: {joints_2d.shape}")
    
    # 处理视频
    return process_video(video_path, meshes, joints_2d, output_path, scale_factor, single_person=True)

def create_multi_person_video(video_path, pkl_data, person_infos, output_path, scale_factor):
    """创建多人3D对齐视频"""
    print(f"\n[VIDEO] 创建多人3D对齐视频")
    print("=" * 50)
    
    print(f"[TARGET] 将处理 {len(person_infos)} 个人员")
    
    # 准备每个人员的数据
    persons_data = []
    min_frames = float('inf')
    
    for person_info in person_infos:
        pid = person_info['id']
        person_data = person_info['data']
        
        # 处理2D关节数据
        if person_info['has_joints2d']:
            joints_2d = person_data['joints2d']
            if len(joints_2d.shape) == 4:
                joints_2d = joints_2d[:, 0, :, :]
            print(f"[OK] 人员 {pid}: 使用真实的2D关节数据")
        else:
            num_frames = len(person_data['mesh'])
            joints_2d = np.zeros((num_frames, 17, 2))
            print(f"[WARNING] 人员 {pid}: 生成虚拟的2D关节数据")
        
        meshes = person_data['mesh']
        min_frames = min(min_frames, len(meshes), len(joints_2d))
        
        persons_data.append({
            'id': pid,
            'meshes': meshes,
            'joints_2d': joints_2d,
            'previous_3d_position': None,
            'aligner': StableAligner()
        })
        
        print(f"📊 人员 {pid} - 网格: {meshes.shape}, 2D关节: {joints_2d.shape}")
    
    # 处理视频
    return process_multi_person_video(video_path, persons_data, output_path, scale_factor, min_frames)

def process_video(video_path, meshes, joints_2d, output_path, scale_factor, single_person=True):
    """处理单人视频"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] 无法打开视频: {video_path}")
        return False
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"[VIDEO] 视频信息: {total_frames} 帧, {fps:.1f} FPS, {width}x{height}")
    
    # 创建临时目录
    temp_dir = "temp_flexible_frames"
    os.makedirs(temp_dir, exist_ok=True)
    
    min_frames = min(total_frames, len(meshes), len(joints_2d))
    print(f"[VIDEO] 处理 {min_frames} 帧")
    
    # 统计信息
    alignment_results = []
    previous_3d_position = None
    aligner = StableAligner()
    
    # 处理每一帧
    for frame_idx in range(min_frames):
        ret, frame = cap.read()
        if not ret:
            break
        
        vertices = meshes[frame_idx]
        frame_joints_2d = joints_2d[frame_idx]
        
        # 确保joints_2d格式正确
        if len(frame_joints_2d.shape) == 1:
            frame_joints_2d = frame_joints_2d.reshape(1, -1, 2)
        elif len(frame_joints_2d.shape) == 2:
            frame_joints_2d = frame_joints_2d.reshape(1, frame_joints_2d.shape[0], frame_joints_2d.shape[1])
        
        # 生成置信度分数（基于2D关节位置的有效性）
        confidence_scores = None
        if len(frame_joints_2d) > 0:
            joints_2d_flat = frame_joints_2d[0]  # 取第一个人的关节
            confidence_scores = np.ones(len(joints_2d_flat))  # 默认置信度为1.0
            
            # 根据关节位置的有效性调整置信度
            for i, joint in enumerate(joints_2d_flat):
                x, y = joint[0], joint[1]
                if x <= 0 or y <= 0:  # 无效关节
                    confidence_scores[i] = 0.0
                elif x < 50 or y < 50 or x > frame.shape[1] - 50 or y > frame.shape[0] - 50:  # 边缘关节
                    confidence_scores[i] = 0.5
                else:  # 有效关节
                    confidence_scores[i] = 1.0
        
        # 创建稳定对齐帧
        stable_frame, alignment_result = create_stable_alignment_frame(
            frame, vertices, frame_joints_2d, scale_factor=scale_factor, 
            previous_3d_position=previous_3d_position, confidence_scores=confidence_scores
        )
        
        alignment_results.append(alignment_result)
        
        # 更新3D位置跟踪
        if 'joints_3d' in alignment_result:
            previous_3d_position = alignment_result['joints_3d'].copy()
        
        # 保存帧
        frame_path = os.path.join(temp_dir, f"frame_{frame_idx:06d}.png")
        cv2.imwrite(frame_path, stable_frame)
        
        # 进度更新
        if (frame_idx + 1) % 10 == 0 or frame_idx == min_frames - 1:
            avg_error = np.mean([r['final_error'] for r in alignment_results])
            avg_iterations = np.mean([r['iterations'] for r in alignment_results])
            print(f"处理进度: {frame_idx + 1}/{min_frames} ({(frame_idx+1)/min_frames*100:.1f}%) | "
                  f"平均误差: {avg_error:.2f} | 平均迭代: {avg_iterations:.1f}")
    
    cap.release()
    
    # 生成视频
    success = create_final_video(temp_dir, output_path, fps)
    
    # 清理临时文件（只有在成功时才清理）
    import shutil
    if success and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            print(f"[OK] 临时文件已清理: {temp_dir}")
        except Exception as e:
            print(f"[WARNING] 清理临时文件失败: {e}")
    elif not success:
        print(f"[INFO] 保留临时文件用于调试: {temp_dir}")
    
    return success

def process_multi_person_video(video_path, persons_data, output_path, scale_factor, min_frames):
    """处理多人视频"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] 无法打开视频: {video_path}")
        return False
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"[VIDEO] 视频信息: {total_frames} 帧, {fps:.1f} FPS")
    
    # 创建临时目录
    temp_dir = "temp_multi_flexible_frames"
    os.makedirs(temp_dir, exist_ok=True)
    
    min_frames = min(min_frames, total_frames)
    print(f"[VIDEO] 处理 {min_frames} 帧 (多人模式)")
    
    # 处理每一帧
    for frame_idx in range(min_frames):
        ret, frame = cap.read()
        if not ret:
            break
        
        # 创建多人合成帧
        multi_person_frame = create_multi_person_frame_flexible(
            frame, persons_data, frame_idx, scale_factor
        )
        
        # 保存帧
        frame_path = os.path.join(temp_dir, f"multi_frame_{frame_idx:06d}.png")
        cv2.imwrite(frame_path, multi_person_frame)
        
        # 进度更新
        if (frame_idx + 1) % 10 == 0 or frame_idx == min_frames - 1:
            print(f"处理进度: {frame_idx + 1}/{min_frames} ({(frame_idx+1)/min_frames*100:.1f}%)")
    
    cap.release()
    
    # 生成视频
    success = create_final_video(temp_dir, output_path, fps, "multi_frame_%06d.png")
    
    # 只在成功时清理临时文件
    if success:
        import shutil
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"[CLEANUP] 已清理临时目录: {temp_dir}")
            except Exception as e:
                print(f"[WARNING] 清理临时目录失败: {e}")
    else:
        print(f"[DEBUG] 视频生成失败，保留临时目录用于调试: {temp_dir}")
    
    return success

def create_multi_person_frame_flexible(original_frame, persons_data, frame_idx, scale_factor):
    """创建多人3D对齐帧（灵活版本）"""
    result_frame = original_frame.copy()
    
    # 为每个人分配不同的颜色和位置偏移
    colors = [(0, 255, 255), (255, 0, 255), (255, 255, 0), (0, 255, 0)]  # 青色、洋红、黄色、绿色
    position_offsets = [(0, 0), (100, 0), (-100, 0), (0, 100)]  # 不同的位置偏移
    
    for person_idx, person_data in enumerate(persons_data):
        if frame_idx >= len(person_data['meshes']) or frame_idx >= len(person_data['joints_2d']):
            continue
            
        pid = person_data['id']
        vertices = person_data['meshes'][frame_idx]
        frame_joints_2d = person_data['joints_2d'][frame_idx]
        
        # 确保joints_2d格式正确
        if len(frame_joints_2d.shape) == 1:
            frame_joints_2d = frame_joints_2d.reshape(1, -1, 2)
        elif len(frame_joints_2d.shape) == 2:
            frame_joints_2d = frame_joints_2d.reshape(1, frame_joints_2d.shape[0], frame_joints_2d.shape[1])
        
        # 执行3D对齐
        aligner = person_data['aligner']
        if len(frame_joints_2d) > 0:
            target_joints_2d = frame_joints_2d[0]
        else:
            target_joints_2d = np.zeros((19, 2))
        
        # 生成置信度分数
        confidence_scores = np.ones(len(target_joints_2d))
        for i, joint in enumerate(target_joints_2d):
            x, y = joint[0], joint[1]
            if x <= 0 or y <= 0:
                confidence_scores[i] = 0.0
            elif x < 50 or y < 50 or x > original_frame.shape[1] - 50 or y > original_frame.shape[0] - 50:
                confidence_scores[i] = 0.5
            else:
                confidence_scores[i] = 1.0
        
        alignment_result = aligner.optimize_stable_alignment(
            vertices, target_joints_2d, person_data['previous_3d_position'], confidence_scores
        )
        
        # 更新3D位置跟踪
        if 'joints_3d' in alignment_result:
            person_data['previous_3d_position'] = alignment_result['joints_3d'].copy()
        
        # 应用位置偏移（为了避免多人重叠）
        offset_x, offset_y = position_offsets[person_idx % len(position_offsets)]
        transform_params = alignment_result['transform_params'].copy()
        transform_params[0] += offset_x  # x偏移
        transform_params[1] += offset_y  # y偏移
        
        # 绘制当前人员的2D关节
        if len(frame_joints_2d) > 0:
            result_frame = draw_stable_2d_joints(result_frame, [frame_joints_2d[0]])
        
        # 渲染3D模型
        model_image = render_stable_3d_model(
            alignment_result['vertices'], 
            alignment_result['joints_3d'],
            original_frame.shape, 
            transform_params,
            scale_factor
        )
        
        # 转换和混合
        model_bgr = cv2.cvtColor(model_image, cv2.COLOR_RGB2BGR)
        model_gray = cv2.cvtColor(model_image, cv2.COLOR_RGB2GRAY)
        _, mask = cv2.threshold(model_gray, 15, 255, cv2.THRESH_BINARY)
        
        # 形态学操作
        kernel = np.ones((3,3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        mask_area = cv2.countNonZero(mask)
        total_area = mask.shape[0] * mask.shape[1]
        mask_ratio = mask_area / total_area
        
        # 只有当mask足够大时才进行混合
        if mask_area > total_area * 0.0001:
            result_frame = result_frame.astype(np.float32)
            model_bgr = model_bgr.astype(np.float32)
            mask_3channel = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
            
            # 应用人员特定的颜色调制
            person_color = np.array(colors[person_idx % len(colors)], dtype=np.float32) / 255.0
            for c in range(3):
                model_bgr[:, :, c] = model_bgr[:, :, c] * 0.7 + model_bgr[:, :, c] * person_color[c] * 0.3
            
            for c in range(3):
                result_frame[:, :, c] = (1 - mask_3channel[:, :, c]) * result_frame[:, :, c] + \
                                       mask_3channel[:, :, c] * model_bgr[:, :, c]
            
            result_frame = result_frame.astype(np.uint8)
        
        # 添加人员标识
        person_color_bgr = colors[person_idx % len(colors)]
        cv2.putText(result_frame, f"Person {pid}", 
                   (10 + person_idx * 120, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, person_color_bgr, 2)
    
    # 添加总体信息
    cv2.putText(result_frame, f"Multi-Person 3D Tracking - Frame {frame_idx}", 
               (10, result_frame.shape[0] - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return result_frame

def create_final_video(temp_dir, output_path, fps, pattern="frame_%06d.png"):
    """使用FFmpeg创建最终视频"""
    print(f"[CREATE] 创建最终视频: {output_path}")
    
    # 检查临时目录是否存在
    if not os.path.exists(temp_dir):
        print(f"[ERROR] 临时目录不存在: {temp_dir}")
        return False
    
    # 检查是否有帧文件 - 根据pattern确定文件前缀
    pattern_prefix = pattern.split('_')[0] + '_'  # 从pattern中提取前缀，如'multi_frame_'或'frame_'
    frame_files = [f for f in os.listdir(temp_dir) if f.startswith(pattern_prefix) and f.endswith('.png')]
    if not frame_files:
        print(f"[ERROR] 临时目录中没有找到帧文件: {temp_dir}")
        print(f"[DEBUG] 查找模式: {pattern_prefix}*.png")
        print(f"[DEBUG] 目录内容: {os.listdir(temp_dir)[:10]}...")  # 显示前10个文件
        return False
    
    print(f"[INFO] 找到 {len(frame_files)} 个帧文件")
    frame_pattern = os.path.join(temp_dir, pattern)
    
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", frame_pattern,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode == 0:
        print(f"[OK] 视频创建成功: {output_path}")
        
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[OUTPUT] 输出文件大小: {file_size:.1f} MB")
        
        return True
    else:
        print(f"[ERROR] FFmpeg执行失败: {result.stderr}")
        return False

def copy_original_video(video_path, output_path):
    """复制原视频到输出路径"""
    print(f"[COPY] 复制原视频: {video_path} -> {output_path}")
    
    try:
        import shutil
        shutil.copy2(video_path, output_path)
        print(f"[SUCCESS] 原视频复制完成: {output_path}")
        return True
    except Exception as e:
        print(f"[ERROR] 复制原视频失败: {e}")
        return False

def generate_output_filename(video_path, mode, person_id=None, num_persons=1):
    """生成输出文件名"""
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    if mode == 'original':
        return f"{video_name}_ORIGINAL_COPY.mp4"
    elif mode == 'multi':
        return f"{video_name}_MULTI_PERSON_3D_ALIGNMENT.mp4"
    elif person_id is not None:
        return f"{video_name}_PERSON_{person_id}_3D_ALIGNMENT.mp4"
    elif num_persons == 1:
        return f"{video_name}_SINGLE_3D_ALIGNMENT.mp4"
    else:
        return f"{video_name}_AUTO_SINGLE_3D_ALIGNMENT.mp4"

def main():
    """主函数"""
    args = parse_arguments()
    
    print("[VIDEO] 智能3D人体对齐视频生成器")
    print("=" * 60)
    print(f"[INPUT] 输入视频: {args.video}")
    print(f"[PKL] PKL文件: {args.pkl}")
    
    # 验证文件
    if not validate_files(args.video, args.pkl):
        return False
    
    # 分析pkl数据
    pkl_data, person_infos = analyze_pkl_data(args.pkl)
    if pkl_data is None:
        return False
    
    # 如果没有检测到人员数据，但pkl文件加载成功，继续处理
    if not person_infos:
        print("[INFO] 未检测到有效的人员数据，将输出原视频")
    
    # 如果只是列出人员信息
    if args.list_persons:
        print("\n📋 人员信息列表完成")
        return True
    
    # 确定处理模式
    if args.person_id is not None:
        # 用户指定了人员ID，强制单人模式
        mode = 'single'
        selected_person_id = args.person_id
        print(f"\n[TARGET] 用户指定: 单人模式 (人员 {args.person_id})")
    elif args.force_multi_person:
        # 用户强制多人模式
        mode = 'multi'
        selected_person_id = None
        print(f"\n[TARGET] 用户指定: 多人模式 (强制)")
    else:
        # 自动检测模式
        print(f"\n[AUTO] 正在自动检测最佳处理模式...")
        mode, selected_person_id = auto_detect_mode(person_infos)
        if mode is None:
            return False
    
    # 生成输出路径
    if args.output is None:
        output_filename = generate_output_filename(
            args.video, mode, selected_person_id, len(person_infos)
        )
        # 获取PKL文件所在的目录作为输出目录
        pkl_dir = os.path.dirname(args.pkl)
        output_path = os.path.join(pkl_dir, output_filename)
    else:
        output_path = args.output
    
    print(f"\n[OUTPUT] 输出视频: {output_path}")
    print(f"[CONFIG] 缩放因子: {args.scale_factor}")
    print(f"[INFO] 处理模式: {'多人模式' if mode == 'multi' else '单人模式'}")
    
    # 选择处理模式
    if mode == 'original':
        # 输出原视频
        success = copy_original_video(args.video, output_path)
    elif mode == 'multi':
        success = create_multi_person_video(
            args.video, pkl_data, person_infos, output_path, args.scale_factor
        )
    else:
        success = create_single_person_video(
            args.video, pkl_data, person_infos, selected_person_id, output_path, args.scale_factor
        )
    
    if success:
        print(f"\n[SUCCESS] 视频生成完成: {output_path}")
        return True
    else:
        print("\n[ERROR] 视频生成失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)