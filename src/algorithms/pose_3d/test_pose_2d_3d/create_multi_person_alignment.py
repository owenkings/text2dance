import cv2
import numpy as np
import joblib
import os
import subprocess
from create_stable_3d_alignment import (
    StableAligner, render_stable_3d_model, draw_stable_2d_joints,
    create_stable_alignment_frame
)

def create_multi_person_alignment_video():
    """创建多人3D跟踪对齐视频"""
    print("🎬 创建多人3D跟踪对齐视频")
    print("=" * 60)
    
    # 加载数据
    pkl_file = "output/demo_output/twodance/pmce_output.pkl"
    original_video = "demo/twodance.mp4"
    output_video = "MULTI_PERSON_3D_ALIGNMENT_VIDEO.mp4"
    
    try:
        data = joblib.load(pkl_file)
        print(f"✅ 成功加载PMCE数据")
        
        # 显示所有人员信息
        print(f"\n👥 检测到 {len(data)} 个人员:")
        person_infos = []
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
        
        if len(person_infos) == 0:
            print("❌ 未找到有效的人员数据")
            return False
        
        # 按帧数排序，处理所有人员
        person_infos.sort(key=lambda x: x['frames'], reverse=True)
        print(f"\n🎯 将处理 {len(person_infos)} 个人员")
        
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
                    joints_2d = joints_2d[:, 0, :, :]  # 取第一个检测结果
                print(f"✅ 人员 {pid}: 使用真实的2D关节数据")
            else:
                num_frames = len(person_data['mesh'])
                joints_2d = np.zeros((num_frames, 17, 2))
                print(f"⚠️ 人员 {pid}: 生成虚拟的2D关节数据")
            
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
        
        # 打开原始视频
        cap = cv2.VideoCapture(original_video)
        if not cap.isOpened():
            print(f"❌ 无法打开视频: {original_video}")
            return False
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"📹 视频信息: {total_frames} 帧, {fps:.1f} FPS, {width}x{height}")
        
        # 创建临时目录
        temp_dir = "temp_multi_person_frames"
        os.makedirs(temp_dir, exist_ok=True)
        
        min_frames = min(min_frames, total_frames)
        print(f"🎬 处理 {min_frames} 帧 (多人3D跟踪)")
        
        # 统计信息
        all_alignment_results = []
        
        # 处理每一帧
        for frame_idx in range(min_frames):
            ret, frame = cap.read()
            if not ret:
                break
            
            # 创建多人合成帧
            multi_person_frame = create_multi_person_frame(
                frame, persons_data, frame_idx, scale_factor=8.0
            )
            
            # 保存帧
            frame_path = os.path.join(temp_dir, f"multi_frame_{frame_idx:06d}.png")
            cv2.imwrite(frame_path, multi_person_frame)
            
            # 进度更新
            if (frame_idx + 1) % 10 == 0 or frame_idx == min_frames - 1:
                print(f"处理进度: {frame_idx + 1}/{min_frames} ({(frame_idx+1)/min_frames*100:.1f}%)")
        
        cap.release()
        
        # 使用FFmpeg创建视频
        print("🎥 创建最终多人3D对齐视频...")
        frame_pattern = os.path.join(temp_dir, "multi_frame_%06d.png")
        
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", f'"{frame_pattern}"',
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            f'"{output_video}"'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode == 0:
            print(f"✅ 多人3D对齐视频创建成功: {output_video}")
            
            # 清理临时文件
            import shutil
            shutil.rmtree(temp_dir)
            
            file_size = os.path.getsize(output_video) / (1024 * 1024)
            print(f"📹 输出文件大小: {file_size:.1f} MB")
            
            return True
        else:
            print(f"❌ FFmpeg执行失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 创建视频时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_multi_person_frame(original_frame, persons_data, frame_idx, scale_factor=8.0):
    """创建多人3D对齐帧"""
    result_frame = original_frame.copy()
    
    # 为每个人分配不同的颜色和位置偏移
    colors = [(0, 255, 255), (255, 0, 255), (255, 255, 0), (0, 255, 0)]  # 青色、洋红、黄色、绿色
    # 增大位置偏移，确保多人不重叠
    position_offsets = [(0, 0), (400, 0), (-400, 0), (0, 300)]  # 更大的位置偏移
    
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
        
        alignment_result = aligner.optimize_stable_alignment(
            vertices, target_joints_2d, person_data['previous_3d_position']
        )
        
        # 更新3D位置跟踪
        if 'joints_3d' in alignment_result:
            person_data['previous_3d_position'] = alignment_result['joints_3d'].copy()
        
        # 应用位置偏移（为了避免多人重叠）
        # 不直接修改transform_params，而是在渲染后的3D坐标上应用偏移
        offset_x, offset_y = position_offsets[person_idx % len(position_offsets)]
        transform_params = alignment_result['transform_params'].copy()
        
        # 将像素偏移转换为3D空间的合理偏移
        # 根据视图范围和图像尺寸计算合理的3D偏移
        view_range = 2.5  # 对应render_stable_3d_model中的base_range
        x_offset_3d = (offset_x / original_frame.shape[1]) * view_range * 2  # 归一化到3D空间
        y_offset_3d = (offset_y / original_frame.shape[0]) * view_range * 2
        
        # 限制偏移在合理范围内，避免超出优化边界
        x_offset_3d = np.clip(x_offset_3d, -1.5, 1.5)
        y_offset_3d = np.clip(y_offset_3d, -1.5, 1.5)
        
        transform_params[0] += x_offset_3d  # x偏移
        transform_params[1] += y_offset_3d  # y偏移
        
        # 渲染3D模型
        model_image = render_stable_3d_model(
            alignment_result['vertices'], 
            alignment_result['joints_3d'],
            original_frame.shape, 
            transform_params,
            pred_cam=None,
            scale_factor=scale_factor,
            joints_2d_target=target_joints_2d,
            use_camera_projection=False
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
        
        print(f"🎯 帧 {frame_idx} - 人员 {pid}: 误差 {alignment_result['final_error']:.2f}, Mask {mask_ratio*100:.3f}%")
    
    # 添加总体信息
    cv2.putText(result_frame, f"Multi-Person 3D Tracking - Frame {frame_idx}", 
               (10, result_frame.shape[0] - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return result_frame

if __name__ == "__main__":
    if create_multi_person_alignment_video():
        print("\n🎉 多人3D跟踪对齐视频创建完成!")
        print("📹 文件名: MULTI_PERSON_3D_ALIGNMENT_VIDEO.mp4")
        print("🎨 特点:")
        print("   - 同时处理多个人员的3D模型")
        print("   - 每个人员使用不同颜色标识")
        print("   - 自动位置偏移避免重叠")
        print("   - 独立的3D位置跟踪")
        print("   - 帧数最多的人员优先处理")
    else:
        print("\n❌ 多人视频创建失败")