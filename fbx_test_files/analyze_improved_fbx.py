#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析改进后的FBX文件，验证基于参考比例的改进效果
"""

import os
import sys
import math

# 添加 FBX SDK 路径
fbx_sdk_path = r"C:\Program Files\Autodesk\FBX\FBX SDK\2020.3.2\lib\vs2017\x64\release"
if os.path.exists(fbx_sdk_path):
    sys.path.append(fbx_sdk_path)

try:
    import fbx
except ImportError:
    print("错误: 无法导入 FBX SDK")
    print("请确保已正确安装 Autodesk FBX SDK 2020.3.2")
    sys.exit(1)

def calculate_bone_length(pos1, pos2):
    """计算两个位置之间的距离"""
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    dz = pos2[2] - pos1[2]
    return math.sqrt(dx*dx + dy*dy + dz*dz)

def analyze_fbx_proportions(fbx_file_path):
    """分析FBX文件的人体比例"""
    try:
        # 创建 FBX 管理器和场景
        manager = fbx.FbxManager.Create()
        scene = fbx.FbxScene.Create(manager, "Scene")
        
        # 创建导入器
        importer = fbx.FbxImporter.Create(manager, "")
        
        if not importer.Initialize(fbx_file_path, -1, manager.GetIOSettings()):
            print(f"无法初始化导入器: {fbx_file_path}")
            return None
        
        # 导入场景
        if not importer.Import(scene):
            print(f"无法导入场景: {fbx_file_path}")
            return None
        
        importer.Destroy()
        
        # 提取骨骼位置
        bone_positions = {}
        
        def traverse_node(node):
            if node.GetNodeAttribute():
                attr_type = node.GetNodeAttribute().GetAttributeType()
                if attr_type == fbx.FbxNodeAttribute.eSkeleton:
                    # 获取全局变换
                    global_transform = node.EvaluateGlobalTransform()
                    translation = global_transform.GetT()
                    
                    bone_name = node.GetName()
                    bone_positions[bone_name] = (
                        float(translation[0]), 
                        float(translation[1]), 
                        float(translation[2])
                    )
            
            # 递归处理子节点
            for i in range(node.GetChildCount()):
                traverse_node(node.GetChild(i))
        
        # 从根节点开始遍历
        root_node = scene.GetRootNode()
        traverse_node(root_node)
        
        manager.Destroy()
        
        # 计算关键比例
        proportions = {}
        
        # 计算手臂比例
        if all(bone in bone_positions for bone in ['LeftShoulder', 'LeftArm', 'LeftForeArm']):
            shoulder_pos = bone_positions['LeftShoulder']
            elbow_pos = bone_positions['LeftArm']
            wrist_pos = bone_positions['LeftForeArm']
            
            upper_arm_length = calculate_bone_length(shoulder_pos, elbow_pos)
            forearm_length = calculate_bone_length(elbow_pos, wrist_pos)
            
            if forearm_length > 0:
                proportions['left_upper_arm_to_forearm'] = upper_arm_length / forearm_length
            proportions['left_upper_arm_length'] = upper_arm_length
            proportions['left_forearm_length'] = forearm_length
            proportions['left_total_arm_length'] = upper_arm_length + forearm_length
        
        # 计算腿部比例
        if all(bone in bone_positions for bone in ['LeftUpLeg', 'LeftLeg', 'LeftFoot']):
            hip_pos = bone_positions['LeftUpLeg']
            knee_pos = bone_positions['LeftLeg']
            ankle_pos = bone_positions['LeftFoot']
            
            thigh_length = calculate_bone_length(hip_pos, knee_pos)
            calf_length = calculate_bone_length(knee_pos, ankle_pos)
            
            if calf_length > 0:
                proportions['left_thigh_to_calf'] = thigh_length / calf_length
            proportions['left_thigh_length'] = thigh_length
            proportions['left_calf_length'] = calf_length
            proportions['left_total_leg_length'] = thigh_length + calf_length
        
        # 计算手臂/腿部比例
        if 'left_total_arm_length' in proportions and 'left_total_leg_length' in proportions:
            proportions['arm_to_leg_ratio'] = proportions['left_total_arm_length'] / proportions['left_total_leg_length']
        
        return proportions
        
    except Exception as e:
        print(f"分析FBX文件时出错: {e}")
        return None

def compare_with_reference():
    """与参考FBX文件进行对比"""
    # 参考比例
    reference_proportions = {
        'thigh_to_calf': 1.093,
        'upper_arm_to_forearm': 0.676,
        'arm_to_leg': 0.526,
    }
    
    # 分析文件
    files_to_analyze = {
        '参考FBX文件': r'e:\image_3d\text2dance\fbx_test_files\jingang_13_c+_004.fbx',
        '改进后的FBX文件': r'e:\image_3d\text2dance\fbx_test_files\improved_dance_model_person_1.fbx'
    }
    
    print("=== FBX文件人体比例对比分析 ===")
    print(f"参考标准比例:")
    print(f"  大腿/小腿比例: {reference_proportions['thigh_to_calf']:.3f}")
    print(f"  上臂/前臂比例: {reference_proportions['upper_arm_to_forearm']:.3f}")
    print(f"  手臂/腿部比例: {reference_proportions['arm_to_leg']:.3f}")
    print()
    
    results = {}
    
    for file_name, file_path in files_to_analyze.items():
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            continue
        
        print(f"=== 分析 {file_name} ===")
        proportions = analyze_fbx_proportions(file_path)
        
        if proportions:
            results[file_name] = proportions
            
            print(f"骨骼长度:")
            if 'left_upper_arm_length' in proportions:
                print(f"  左上臂长度: {proportions['left_upper_arm_length']:.3f}")
            if 'left_forearm_length' in proportions:
                print(f"  左前臂长度: {proportions['left_forearm_length']:.3f}")
            if 'left_thigh_length' in proportions:
                print(f"  左大腿长度: {proportions['left_thigh_length']:.3f}")
            if 'left_calf_length' in proportions:
                print(f"  左小腿长度: {proportions['left_calf_length']:.3f}")
            
            print(f"人体比例:")
            if 'left_thigh_to_calf' in proportions:
                ratio = proportions['left_thigh_to_calf']
                diff = abs(ratio - reference_proportions['thigh_to_calf'])
                print(f"  大腿/小腿比例: {ratio:.3f} (与参考差异: {diff:.3f})")
            
            if 'left_upper_arm_to_forearm' in proportions:
                ratio = proportions['left_upper_arm_to_forearm']
                diff = abs(ratio - reference_proportions['upper_arm_to_forearm'])
                print(f"  上臂/前臂比例: {ratio:.3f} (与参考差异: {diff:.3f})")
            
            if 'arm_to_leg_ratio' in proportions:
                ratio = proportions['arm_to_leg_ratio']
                diff = abs(ratio - reference_proportions['arm_to_leg'])
                print(f"  手臂/腿部比例: {ratio:.3f} (与参考差异: {diff:.3f})")
            
            print()
        else:
            print(f"无法分析文件: {file_path}")
            print()
    
    # 对比分析
    if len(results) >= 2:
        print("=== 改进效果评估 ===")
        ref_key = '参考FBX文件'
        improved_key = '改进后的FBX文件'
        
        if ref_key in results and improved_key in results:
            ref_data = results[ref_key]
            improved_data = results[improved_key]
            
            # 比较各项比例的改进程度
            comparisons = [
                ('大腿/小腿比例', 'left_thigh_to_calf', reference_proportions['thigh_to_calf']),
                ('上臂/前臂比例', 'left_upper_arm_to_forearm', reference_proportions['upper_arm_to_forearm']),
                ('手臂/腿部比例', 'arm_to_leg_ratio', reference_proportions['arm_to_leg'])
            ]
            
            for name, key, target in comparisons:
                if key in ref_data and key in improved_data:
                    ref_diff = abs(ref_data[key] - target)
                    improved_diff = abs(improved_data[key] - target)
                    
                    if ref_diff > 0:
                        improvement = ((ref_diff - improved_diff) / ref_diff) * 100
                        print(f"{name}:")
                        print(f"  参考文件与标准差异: {ref_diff:.3f}")
                        print(f"  改进文件与标准差异: {improved_diff:.3f}")
                        if improvement > 0:
                            print(f"  改进程度: +{improvement:.1f}% (更接近标准)")
                        else:
                            print(f"  改进程度: {improvement:.1f}% (偏离标准)")
                        print()

def main():
    """主函数"""
    compare_with_reference()

if __name__ == "__main__":
    main()