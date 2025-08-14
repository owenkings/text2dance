#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PKL文件结构分析脚本
分析run_demo.py生成的PKL文件中的坐标系和多人位置信息
"""

import joblib
import numpy as np
import os

def analyze_pkl_file(pkl_path):
    """
    分析PKL文件的结构和内容
    """
    print(f"\n=== 分析PKL文件: {pkl_path} ===")
    
    if not os.path.exists(pkl_path):
        print(f"错误: 文件不存在 {pkl_path}")
        return
    
    try:
        # 加载PKL文件
        data = joblib.load(pkl_path)
        print(f"PKL文件加载成功")
        
        # 分析顶层结构
        print(f"\n--- 顶层数据结构 ---")
        print(f"数据类型: {type(data)}")
        
        if isinstance(data, dict):
            print(f"字典键数量: {len(data.keys())}")
            print(f"字典键: {list(data.keys())}")
            
            # 分析每个人的数据
            for person_id, person_data in data.items():
                print(f"\n--- Person {person_id} 数据分析 ---")
                print(f"Person数据类型: {type(person_data)}")
                
                if isinstance(person_data, dict):
                    print(f"Person数据键: {list(person_data.keys())}")
                    
                    # 分析各个数据字段
                    for key, value in person_data.items():
                        print(f"\n  {key}:")
                        print(f"    类型: {type(value)}")
                        
                        if isinstance(value, np.ndarray):
                            print(f"    形状: {value.shape}")
                            print(f"    数据类型: {value.dtype}")
                            print(f"    数值范围: [{np.min(value):.4f}, {np.max(value):.4f}]")
                            
                            # 特别分析关键字段
                            if key == 'pred_cam':
                                print(f"    相机参数分析:")
                                print(f"      每帧相机参数数量: {value.shape[-1] if len(value.shape) > 1 else 'N/A'}")
                                if len(value.shape) >= 2:
                                    print(f"      第一帧相机参数: {value[0] if len(value) > 0 else 'N/A'}")
                                    
                            elif key == 'joints3d':
                                print(f"    3D关节分析:")
                                if len(value.shape) >= 3:
                                    print(f"      关节数量: {value.shape[-2]}")
                                    print(f"      坐标维度: {value.shape[-1]}")
                                    print(f"      第一帧第一个关节: {value[0, 0] if len(value) > 0 and len(value[0]) > 0 else 'N/A'}")
                                    
                            elif key == 'joints2d':
                                print(f"    2D关节分析:")
                                if len(value.shape) >= 3:
                                    print(f"      关节数量: {value.shape[-2]}")
                                    print(f"      坐标维度: {value.shape[-1]}")
                                    print(f"      第一帧第一个关节: {value[0, 0] if len(value) > 0 and len(value[0]) > 0 else 'N/A'}")
                                    
                            elif key == 'mesh':
                                print(f"    网格顶点分析:")
                                if len(value.shape) >= 3:
                                    print(f"      顶点数量: {value.shape[-2]}")
                                    print(f"      坐标维度: {value.shape[-1]}")
                                    
                            elif key == 'bboxes':
                                print(f"    边界框分析:")
                                if len(value.shape) >= 2:
                                    print(f"      边界框参数数量: {value.shape[-1]}")
                                    print(f"      第一帧边界框: {value[0] if len(value) > 0 else 'N/A'}")
                                    
                        elif isinstance(value, list):
                            print(f"    列表长度: {len(value)}")
                            if len(value) > 0:
                                print(f"    第一个元素类型: {type(value[0])}")
                                if isinstance(value[0], np.ndarray):
                                    print(f"    第一个元素形状: {value[0].shape}")
                        else:
                            print(f"    值: {value}")
                            
        # 分析坐标系特征
        print(f"\n--- 坐标系分析 ---")
        analyze_coordinate_system(data)
        
        # 分析多人位置关系
        print(f"\n--- 多人位置关系分析 ---")
        analyze_multi_person_positions(data)
        
    except Exception as e:
        print(f"分析PKL文件时出错: {e}")
        import traceback
        traceback.print_exc()

def analyze_coordinate_system(data):
    """
    分析坐标系特征
    """
    if not isinstance(data, dict):
        print("数据不是字典格式，无法分析坐标系")
        return
        
    for person_id, person_data in data.items():
        if 'joints3d' in person_data:
            joints3d = person_data['joints3d']
            if isinstance(joints3d, np.ndarray) and len(joints3d.shape) >= 3:
                print(f"Person {person_id} 3D关节坐标系分析:")
                
                # 分析第一帧的关节位置
                if len(joints3d) > 0:
                    first_frame = joints3d[0]
                    print(f"  第一帧关节坐标范围:")
                    print(f"    X轴: [{np.min(first_frame[:, 0]):.4f}, {np.max(first_frame[:, 0]):.4f}]")
                    print(f"    Y轴: [{np.min(first_frame[:, 1]):.4f}, {np.max(first_frame[:, 1]):.4f}]")
                    print(f"    Z轴: [{np.min(first_frame[:, 2]):.4f}, {np.max(first_frame[:, 2]):.4f}]")
                    
                    # 分析根关节位置（通常是骨盆）
                    if len(first_frame) > 17:  # COCO格式通常有17个关节，加上骨盆和颈部
                        pelvis_idx = 17  # 骨盆通常是第18个关节（索引17）
                        if pelvis_idx < len(first_frame):
                            pelvis_pos = first_frame[pelvis_idx]
                            print(f"  骨盆位置 (根关节): [{pelvis_pos[0]:.4f}, {pelvis_pos[1]:.4f}, {pelvis_pos[2]:.4f}]")
                            
                # 分析相机参数
                if 'pred_cam' in person_data:
                    cam_params = person_data['pred_cam']
                    if isinstance(cam_params, np.ndarray) and len(cam_params) > 0:
                        print(f"  相机参数 (第一帧): {cam_params[0]}")
                        print(f"  相机参数说明: [scale, tx, ty] 或 [sx, sy, tx, ty]")

def analyze_multi_person_positions(data):
    """
    分析多人位置关系
    """
    if not isinstance(data, dict):
        print("数据不是字典格式，无法分析多人位置")
        return
        
    person_count = len(data)
    print(f"检测到 {person_count} 个人")
    
    if person_count < 2:
        print("只有一个人，无法分析多人位置关系")
        return
        
    # 收集所有人的根关节位置
    root_positions = {}
    for person_id, person_data in data.items():
        if 'joints3d' in person_data:
            joints3d = person_data['joints3d']
            if isinstance(joints3d, np.ndarray) and len(joints3d.shape) >= 3 and len(joints3d) > 0:
                first_frame = joints3d[0]
                if len(first_frame) > 17:
                    pelvis_idx = 17
                    if pelvis_idx < len(first_frame):
                        root_positions[person_id] = first_frame[pelvis_idx]
                        
    # 分析人与人之间的距离
    if len(root_positions) >= 2:
        print(f"\n多人根关节位置:")
        for person_id, pos in root_positions.items():
            print(f"  Person {person_id}: [{pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}]")
            
        # 计算人与人之间的距离
        person_ids = list(root_positions.keys())
        for i in range(len(person_ids)):
            for j in range(i+1, len(person_ids)):
                pos1 = root_positions[person_ids[i]]
                pos2 = root_positions[person_ids[j]]
                distance = np.linalg.norm(pos1 - pos2)
                print(f"  Person {person_ids[i]} 到 Person {person_ids[j]} 的距离: {distance:.4f}")
                
        # 分析是否包含真实世界位置信息
        print(f"\n真实世界位置信息分析:")
        distances = []
        for i in range(len(person_ids)):
            for j in range(i+1, len(person_ids)):
                pos1 = root_positions[person_ids[i]]
                pos2 = root_positions[person_ids[j]]
                distance = np.linalg.norm(pos1 - pos2)
                distances.append(distance)
                
        if distances:
            avg_distance = np.mean(distances)
            print(f"  平均人际距离: {avg_distance:.4f}")
            if avg_distance > 0.1:  # 如果距离大于0.1米
                print(f"  ✓ 可能包含真实世界位置信息 (人际距离合理)")
            else:
                print(f"  ✗ 可能不包含真实世界位置信息 (人际距离过小)")

def main():
    # 分析多个PKL文件
    pkl_files = [
        "e:/image_3d/text2dance/output/sample_video/pmce_output.pkl",
        "e:/image_3d/text2dance/output/twodance/pmce_output.pkl",
    ]
    
    for pkl_file in pkl_files:
        if os.path.exists(pkl_file):
            analyze_pkl_file(pkl_file)
        else:
            print(f"文件不存在: {pkl_file}")
            
    print("\n=== 分析完成 ===")

if __name__ == "__main__":
    main()