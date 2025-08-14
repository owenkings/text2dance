#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从参考FBX文件中提取骨骼比例数据
用于修正improved_pkl_to_fbx_converter.py中的人体比例
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

def extract_bone_positions(fbx_file_path):
    """从FBX文件中提取骨骼位置信息"""
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
        
        def traverse_node(node, parent_transform=None):
            if node.GetNodeAttribute():
                attr_type = node.GetNodeAttribute().GetAttributeType()
                if attr_type == fbx.FbxNodeAttribute.eSkeleton:
                    # 获取全局变换
                    global_transform = node.EvaluateGlobalTransform()
                    translation = global_transform.GetT()
                    
                    bone_name = node.GetName()
                    bone_positions[bone_name] = {
                        'position': (float(translation[0]), float(translation[1]), float(translation[2])),
                        'local_position': (float(node.LclTranslation.Get()[0]), 
                                         float(node.LclTranslation.Get()[1]), 
                                         float(node.LclTranslation.Get()[2]))
                    }
            
            # 递归处理子节点
            for i in range(node.GetChildCount()):
                traverse_node(node.GetChild(i), node)
        
        # 从根节点开始遍历
        root_node = scene.GetRootNode()
        traverse_node(root_node)
        
        manager.Destroy()
        return bone_positions
        
    except Exception as e:
        print(f"提取骨骼位置时出错: {e}")
        return None

def calculate_reference_proportions(bone_positions):
    """计算参考FBX文件的人体比例"""
    proportions = {}
    
    try:
        # 定义关键骨骼映射
        key_bones = {
            'hips': 'Skeleton0Hips',
            'spine': 'Skeleton0Spine',
            'spine1': 'Skeleton0Spine1', 
            'spine2': 'Skeleton0Spine2',
            'neck': 'Skeleton0Neck',
            'head': 'Skeleton0Head',
            'left_shoulder': 'Skeleton0LeftShoulder',
            'left_arm': 'Skeleton0LeftArm',
            'left_forearm': 'Skeleton0LeftForeArm',
            'left_hand': 'Skeleton0LeftHand',
            'right_shoulder': 'Skeleton0RightShoulder',
            'right_arm': 'Skeleton0RightArm',
            'right_forearm': 'Skeleton0RightForeArm',
            'right_hand': 'Skeleton0RightHand',
            'left_upleg': 'Skeleton0LeftUpLeg',
            'left_leg': 'Skeleton0LeftLeg',
            'left_foot': 'Skeleton0LeftFoot',
            'right_upleg': 'Skeleton0RightUpLeg',
            'right_leg': 'Skeleton0RightLeg',
            'right_foot': 'Skeleton0RightFoot'
        }
        
        # 计算骨骼长度
        bone_lengths = {}
        
        # 脊椎长度
        if key_bones['hips'] in bone_positions and key_bones['spine'] in bone_positions:
            hips_pos = bone_positions[key_bones['hips']]['position']
            spine_pos = bone_positions[key_bones['spine']]['position']
            bone_lengths['hips_to_spine'] = calculate_bone_length(hips_pos, spine_pos)
        
        # 上臂长度 (肩膀到肘部)
        if key_bones['left_shoulder'] in bone_positions and key_bones['left_arm'] in bone_positions:
            shoulder_pos = bone_positions[key_bones['left_shoulder']]['position']
            arm_pos = bone_positions[key_bones['left_arm']]['position']
            bone_lengths['left_upper_arm'] = calculate_bone_length(shoulder_pos, arm_pos)
        
        # 前臂长度 (肘部到手腕)
        if key_bones['left_arm'] in bone_positions and key_bones['left_forearm'] in bone_positions:
            arm_pos = bone_positions[key_bones['left_arm']]['position']
            forearm_pos = bone_positions[key_bones['left_forearm']]['position']
            bone_lengths['left_forearm'] = calculate_bone_length(arm_pos, forearm_pos)
        
        # 大腿长度
        if key_bones['left_upleg'] in bone_positions and key_bones['left_leg'] in bone_positions:
            upleg_pos = bone_positions[key_bones['left_upleg']]['position']
            leg_pos = bone_positions[key_bones['left_leg']]['position']
            bone_lengths['left_thigh'] = calculate_bone_length(upleg_pos, leg_pos)
        
        # 小腿长度
        if key_bones['left_leg'] in bone_positions and key_bones['left_foot'] in bone_positions:
            leg_pos = bone_positions[key_bones['left_leg']]['position']
            foot_pos = bone_positions[key_bones['left_foot']]['position']
            bone_lengths['left_calf'] = calculate_bone_length(leg_pos, foot_pos)
        
        # 计算比例
        if 'left_thigh' in bone_lengths and 'left_calf' in bone_lengths:
            proportions['thigh_to_calf_ratio'] = bone_lengths['left_thigh'] / bone_lengths['left_calf']
        
        if 'left_upper_arm' in bone_lengths and 'left_forearm' in bone_lengths:
            proportions['upper_arm_to_forearm_ratio'] = bone_lengths['left_upper_arm'] / bone_lengths['left_forearm']
        
        # 总臂长和总腿长
        if 'left_upper_arm' in bone_lengths and 'left_forearm' in bone_lengths:
            total_arm_length = bone_lengths['left_upper_arm'] + bone_lengths['left_forearm']
            proportions['total_arm_length'] = total_arm_length
        
        if 'left_thigh' in bone_lengths and 'left_calf' in bone_lengths:
            total_leg_length = bone_lengths['left_thigh'] + bone_lengths['left_calf']
            proportions['total_leg_length'] = total_leg_length
        
        if 'total_arm_length' in proportions and 'total_leg_length' in proportions:
            proportions['arm_to_leg_ratio'] = proportions['total_arm_length'] / proportions['total_leg_length']
        
        # 保存骨骼长度信息
        proportions['bone_lengths'] = bone_lengths
        proportions['bone_positions'] = bone_positions
        
        return proportions
        
    except Exception as e:
        print(f"计算比例时出错: {e}")
        return None

def generate_proportion_config(proportions):
    """生成比例配置代码"""
    if not proportions:
        return None
    
    config_code = """
# 参考FBX文件的人体比例配置
REFERENCE_PROPORTIONS = {
    # 骨骼长度比例
    'bone_length_ratios': {
"""
    
    if 'thigh_to_calf_ratio' in proportions:
        config_code += f"        'thigh_to_calf': {proportions['thigh_to_calf_ratio']:.3f},\n"
    
    if 'upper_arm_to_forearm_ratio' in proportions:
        config_code += f"        'upper_arm_to_forearm': {proportions['upper_arm_to_forearm_ratio']:.3f},\n"
    
    if 'arm_to_leg_ratio' in proportions:
        config_code += f"        'arm_to_leg': {proportions['arm_to_leg_ratio']:.3f},\n"
    
    config_code += "    },\n"
    
    # 添加绝对长度信息
    config_code += "    # 参考骨骼长度 (单位: FBX单位)\n"
    config_code += "    'reference_lengths': {\n"
    
    if 'bone_lengths' in proportions:
        for bone_name, length in proportions['bone_lengths'].items():
            config_code += f"        '{bone_name}': {length:.3f},\n"
    
    config_code += "    }\n}\n"
    
    return config_code

def main():
    """主函数"""
    reference_fbx = r"e:\image_3d\text2dance\fbx_test_files\jingang_13_c+_004.fbx"
    
    print("=== 提取参考FBX文件的人体比例 ===")
    print(f"分析文件: {reference_fbx}")
    
    # 提取骨骼位置
    bone_positions = extract_bone_positions(reference_fbx)
    if not bone_positions:
        print("无法提取骨骼位置信息")
        return
    
    print(f"提取到 {len(bone_positions)} 个骨骼的位置信息")
    
    # 计算比例
    proportions = calculate_reference_proportions(bone_positions)
    if not proportions:
        print("无法计算人体比例")
        return
    
    print("\n=== 参考人体比例分析结果 ===")
    if 'thigh_to_calf_ratio' in proportions:
        print(f"大腿/小腿比例: {proportions['thigh_to_calf_ratio']:.3f}")
    
    if 'upper_arm_to_forearm_ratio' in proportions:
        print(f"上臂/前臂比例: {proportions['upper_arm_to_forearm_ratio']:.3f}")
    
    if 'arm_to_leg_ratio' in proportions:
        print(f"手臂/腿部比例: {proportions['arm_to_leg_ratio']:.3f}")
    
    if 'bone_lengths' in proportions:
        print("\n=== 关键骨骼长度 ===")
        for bone_name, length in proportions['bone_lengths'].items():
            print(f"{bone_name}: {length:.3f}")
    
    # 生成配置代码
    config_code = generate_proportion_config(proportions)
    if config_code:
        config_file = r"e:\image_3d\text2dance\fbx_test_files\reference_proportions_config.py"
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_code)
        print(f"\n比例配置已保存到: {config_file}")
    
    print("\n=== 分析完成 ===")

if __name__ == "__main__":
    main()