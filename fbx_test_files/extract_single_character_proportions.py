#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从包含多个角色的FBX文件中提取单个角色的人体比例
专门针对jingang_13_c+_004.fbx文件中的第一个角色（Skeleton0）
"""

import fbx
import math
import sys

def calculate_distance(pos1, pos2):
    """计算两点间的距离"""
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

def get_node_world_position(node):
    """获取节点的世界坐标位置"""
    transform = node.EvaluateGlobalTransform()
    translation = transform.GetT()
    return (translation[0], translation[1], translation[2])

def extract_single_character_proportions(fbx_file_path, character_prefix="Skeleton0"):
    """
    从FBX文件中提取指定角色的人体比例
    """
    # 初始化FBX SDK
    manager = fbx.FbxManager.Create()
    scene = fbx.FbxScene.Create(manager, "Scene")
    
    # 创建导入器
    importer = fbx.FbxImporter.Create(manager, "Importer")
    
    try:
        # 导入FBX文件
        if not importer.Initialize(fbx_file_path, -1, manager.GetIOSettings()):
            print(f"无法初始化导入器: {importer.GetStatus().GetErrorString()}")
            return None
        
        if not importer.Import(scene):
            print(f"无法导入FBX文件: {importer.GetStatus().GetErrorString()}")
            return None
        
        print(f"\n=== 提取角色 {character_prefix} 的人体比例 ===")
        
        # 获取根节点
        root_node = scene.GetRootNode()
        
        # 存储指定角色的骨骼节点
        character_bones = {}
        
        def find_character_bones(node):
            """递归查找指定角色的骨骼节点"""
            node_name = node.GetName()
            
            # 检查是否属于指定角色
            if node_name.startswith(character_prefix):
                attribute = node.GetNodeAttribute()
                if attribute and attribute.GetAttributeType() == fbx.FbxNodeAttribute.eSkeleton:
                    # 获取骨骼的世界坐标位置
                    world_pos = get_node_world_position(node)
                    character_bones[node_name] = {
                        'node': node,
                        'position': world_pos
                    }
                    print(f"找到骨骼: {node_name} 位置: {world_pos}")
            
            # 递归遍历子节点
            for i in range(node.GetChildCount()):
                find_character_bones(node.GetChild(i))
        
        # 查找指定角色的骨骼
        find_character_bones(root_node)
        
        if not character_bones:
            print(f"未找到角色 {character_prefix} 的骨骼节点")
            return None
        
        print(f"\n找到 {len(character_bones)} 个 {character_prefix} 的骨骼节点")
        
        # 定义关键骨骼映射（基于实际找到的骨骼名称）
        key_bones = {
            'hips': f'{character_prefix}Hips',
            'spine': f'{character_prefix}Spine',
            'spine1': f'{character_prefix}Spine1',
            'spine2': f'{character_prefix}Spine2',
            'neck': f'{character_prefix}Neck',
            'head': f'{character_prefix}Head',
            'left_shoulder': f'{character_prefix}LeftShoulder',
            'left_arm': f'{character_prefix}LeftArm',
            'left_forearm': f'{character_prefix}LeftForeArm',
            'left_hand': f'{character_prefix}LeftHand',
            'right_shoulder': f'{character_prefix}RightShoulder',
            'right_arm': f'{character_prefix}RightArm',
            'right_forearm': f'{character_prefix}RightForeArm',
            'right_hand': f'{character_prefix}RightHand',
            'left_upleg': f'{character_prefix}LeftUpLeg',
            'left_leg': f'{character_prefix}LeftLeg',
            'left_foot': f'{character_prefix}LeftFoot',
            'right_upleg': f'{character_prefix}RightUpLeg',
            'right_leg': f'{character_prefix}RightLeg',
            'right_foot': f'{character_prefix}RightFoot'
        }
        
        # 验证关键骨骼是否存在
        missing_bones = []
        for key, bone_name in key_bones.items():
            if bone_name not in character_bones:
                missing_bones.append(bone_name)
        
        if missing_bones:
            print(f"\n⚠️  缺少以下关键骨骼: {missing_bones}")
            print("可用的骨骼列表:")
            for bone_name in sorted(character_bones.keys()):
                print(f"  - {bone_name}")
        
        # 计算骨骼长度
        bone_lengths = {}
        
        def calculate_bone_length(start_bone, end_bone, length_name):
            if start_bone in character_bones and end_bone in character_bones:
                start_pos = character_bones[start_bone]['position']
                end_pos = character_bones[end_bone]['position']
                length = calculate_distance(start_pos, end_pos)
                bone_lengths[length_name] = length
                print(f"{length_name}: {length:.3f}")
                return length
            else:
                print(f"无法计算 {length_name}，缺少骨骼: {start_bone} 或 {end_bone}")
                return None
        
        print(f"\n=== 计算 {character_prefix} 的骨骼长度 ===")
        
        # 计算主要骨骼长度
        hips_to_spine = calculate_bone_length(key_bones['hips'], key_bones['spine'], 'hips_to_spine')
        spine_to_spine1 = calculate_bone_length(key_bones['spine'], key_bones['spine1'], 'spine_to_spine1')
        spine1_to_spine2 = calculate_bone_length(key_bones['spine1'], key_bones['spine2'], 'spine1_to_spine2')
        spine2_to_neck = calculate_bone_length(key_bones['spine2'], key_bones['neck'], 'spine2_to_neck')
        neck_to_head = calculate_bone_length(key_bones['neck'], key_bones['head'], 'neck_to_head')
        
        # 左臂
        left_shoulder_to_arm = calculate_bone_length(key_bones['left_shoulder'], key_bones['left_arm'], 'left_shoulder_to_arm')
        left_upper_arm = calculate_bone_length(key_bones['left_arm'], key_bones['left_forearm'], 'left_upper_arm')
        left_forearm = calculate_bone_length(key_bones['left_forearm'], key_bones['left_hand'], 'left_forearm')
        
        # 右臂
        right_shoulder_to_arm = calculate_bone_length(key_bones['right_shoulder'], key_bones['right_arm'], 'right_shoulder_to_arm')
        right_upper_arm = calculate_bone_length(key_bones['right_arm'], key_bones['right_forearm'], 'right_upper_arm')
        right_forearm = calculate_bone_length(key_bones['right_forearm'], key_bones['right_hand'], 'right_forearm')
        
        # 左腿
        left_thigh = calculate_bone_length(key_bones['left_upleg'], key_bones['left_leg'], 'left_thigh')
        left_calf = calculate_bone_length(key_bones['left_leg'], key_bones['left_foot'], 'left_calf')
        
        # 右腿
        right_thigh = calculate_bone_length(key_bones['right_upleg'], key_bones['right_leg'], 'right_thigh')
        right_calf = calculate_bone_length(key_bones['right_leg'], key_bones['right_foot'], 'right_calf')
        
        # 计算人体比例
        proportions = {}
        
        print(f"\n=== 计算 {character_prefix} 的人体比例 ===")
        
        # 大腿/小腿比例
        if left_thigh and left_calf:
            proportions['thigh_to_calf'] = left_thigh / left_calf
            print(f"大腿/小腿比例: {proportions['thigh_to_calf']:.3f}")
        
        # 上臂/前臂比例
        if left_upper_arm and left_forearm:
            proportions['upper_arm_to_forearm'] = left_upper_arm / left_forearm
            print(f"上臂/前臂比例: {proportions['upper_arm_to_forearm']:.3f}")
        
        # 手臂/腿部比例（总长度）
        if left_upper_arm and left_forearm and left_thigh and left_calf:
            arm_total = left_upper_arm + left_forearm
            leg_total = left_thigh + left_calf
            proportions['arm_to_leg'] = arm_total / leg_total
            print(f"手臂/腿部比例: {proportions['arm_to_leg']:.3f}")
        
        # 生成配置文件
        config_content = f"""# {character_prefix} 角色的人体比例配置
# 从 {fbx_file_path} 提取

# 骨骼长度比例
REFERENCE_PROPORTIONS = {{
    # 主要比例
    'thigh_to_calf': {proportions.get('thigh_to_calf', 1.0):.6f},
    'upper_arm_to_forearm': {proportions.get('upper_arm_to_forearm', 1.0):.6f},
    'arm_to_leg': {proportions.get('arm_to_leg', 1.0):.6f},
    
    # 参考骨骼长度
    'hips_to_spine': {bone_lengths.get('hips_to_spine', 10.0):.6f},
    'left_upper_arm': {bone_lengths.get('left_upper_arm', 30.0):.6f},
    'left_forearm': {bone_lengths.get('left_forearm', 25.0):.6f},
    'left_thigh': {bone_lengths.get('left_thigh', 40.0):.6f},
    'left_calf': {bone_lengths.get('left_calf', 35.0):.6f},
    'right_upper_arm': {bone_lengths.get('right_upper_arm', 30.0):.6f},
    'right_forearm': {bone_lengths.get('right_forearm', 25.0):.6f},
    'right_thigh': {bone_lengths.get('right_thigh', 40.0):.6f},
    'right_calf': {bone_lengths.get('right_calf', 35.0):.6f},
    'spine_to_spine1': {bone_lengths.get('spine_to_spine1', 15.0):.6f},
    'spine1_to_spine2': {bone_lengths.get('spine1_to_spine2', 15.0):.6f},
    'spine2_to_neck': {bone_lengths.get('spine2_to_neck', 10.0):.6f},
    'neck_to_head': {bone_lengths.get('neck_to_head', 8.0):.6f}
}}

# 角色信息
CHARACTER_INFO = {{
    'name': '{character_prefix}',
    'total_bones': {len(character_bones)},
    'source_file': r'{fbx_file_path}'
}}
"""
        
        # 保存配置文件
        config_file = f"single_character_proportions_{character_prefix.lower()}.py"
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print(f"\n✅ {character_prefix} 的比例配置已保存到: {config_file}")
        
        return {
            'proportions': proportions,
            'bone_lengths': bone_lengths,
            'character_bones': list(character_bones.keys())
        }
        
    except Exception as e:
        print(f"提取过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        # 清理资源
        importer.Destroy()
        manager.Destroy()

if __name__ == "__main__":
    # 分析参考FBX文件中的第一个角色
    reference_fbx = r"e:\image_3d\text2dance\fbx_test_files\jingang_13_c+_004.fbx"
    
    print("开始提取第一个角色（Skeleton0）的人体比例...")
    result = extract_single_character_proportions(reference_fbx, "Skeleton0")
    
    if result:
        print("\n=== 提取完成 ===")
        print(f"成功提取了 {len(result['character_bones'])} 个骨骼的信息")
        print(f"计算了 {len(result['proportions'])} 个关键比例")
    else:
        print("\n❌ 提取失败")