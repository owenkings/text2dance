#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试骨骼结构，理解FBX中骨骼的正确定义
"""

import fbx
import math

def calculate_distance(pos1, pos2):
    """计算两点间的距离"""
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

def get_node_world_position(node):
    """获取节点的世界坐标位置"""
    transform = node.EvaluateGlobalTransform()
    translation = transform.GetT()
    return (translation[0], translation[1], translation[2])

def debug_bone_structure(fbx_file_path):
    """调试FBX文件的骨骼结构"""
    # 初始化FBX SDK
    manager = fbx.FbxManager.Create()
    scene = fbx.FbxScene.Create(manager, "Scene")
    
    # 创建导入器
    importer = fbx.FbxImporter.Create(manager, "Importer")
    
    try:
        # 导入FBX文件
        if not importer.Initialize(fbx_file_path, -1, manager.GetIOSettings()):
            print(f"无法初始化导入器: {importer.GetStatus().GetErrorString()}")
            return
        
        if not importer.Import(scene):
            print(f"无法导入FBX文件: {importer.GetStatus().GetErrorString()}")
            return
        
        print(f"\n=== 调试骨骼结构 ===")
        print(f"文件: {fbx_file_path}")
        
        # 获取根节点
        root_node = scene.GetRootNode()
        
        # 存储骨骼节点
        skeleton_nodes = {}
        
        def find_skeleton_nodes(node):
            """递归查找骨骼节点"""
            node_name = node.GetName()
            attribute = node.GetNodeAttribute()
            
            if attribute and attribute.GetAttributeType() == fbx.FbxNodeAttribute.eSkeleton:
                world_pos = get_node_world_position(node)
                skeleton_nodes[node_name] = {
                    'node': node,
                    'position': world_pos
                }
            
            # 递归遍历子节点
            for i in range(node.GetChildCount()):
                find_skeleton_nodes(node.GetChild(i))
        
        # 查找所有骨骼节点
        find_skeleton_nodes(root_node)
        
        print(f"\n找到 {len(skeleton_nodes)} 个骨骼节点")
        
        # 分析手臂骨骼链
        print(f"\n=== 手臂骨骼链分析 ===")
        arm_bones = ['LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand']
        
        for i, bone_name in enumerate(arm_bones):
            if bone_name in skeleton_nodes:
                pos = skeleton_nodes[bone_name]['position']
                print(f"{i+1}. {bone_name}: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
                
                # 计算到下一个骨骼的距离
                if i < len(arm_bones) - 1:
                    next_bone = arm_bones[i + 1]
                    if next_bone in skeleton_nodes:
                        next_pos = skeleton_nodes[next_bone]['position']
                        distance = calculate_distance(pos, next_pos)
                        print(f"   -> 到 {next_bone} 的距离: {distance:.3f}")
        
        # 分析腿部骨骼链
        print(f"\n=== 腿部骨骼链分析 ===")
        leg_bones = ['LeftUpLeg', 'LeftLeg', 'LeftFoot']
        
        for i, bone_name in enumerate(leg_bones):
            if bone_name in skeleton_nodes:
                pos = skeleton_nodes[bone_name]['position']
                print(f"{i+1}. {bone_name}: ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
                
                # 计算到下一个骨骼的距离
                if i < len(leg_bones) - 1:
                    next_bone = leg_bones[i + 1]
                    if next_bone in skeleton_nodes:
                        next_pos = skeleton_nodes[next_bone]['position']
                        distance = calculate_distance(pos, next_pos)
                        print(f"   -> 到 {next_bone} 的距离: {distance:.3f}")
        
        # 计算正确的骨骼长度
        print(f"\n=== 正确的骨骼长度计算 ===")
        
        # 上臂长度：LeftShoulder 到 LeftArm
        if 'LeftShoulder' in skeleton_nodes and 'LeftArm' in skeleton_nodes:
            shoulder_pos = skeleton_nodes['LeftShoulder']['position']
            arm_pos = skeleton_nodes['LeftArm']['position']
            upper_arm_length = calculate_distance(shoulder_pos, arm_pos)
            print(f"上臂长度 (LeftShoulder -> LeftArm): {upper_arm_length:.3f}")
        
        # 前臂长度：LeftArm 到 LeftForeArm
        if 'LeftArm' in skeleton_nodes and 'LeftForeArm' in skeleton_nodes:
            arm_pos = skeleton_nodes['LeftArm']['position']
            forearm_pos = skeleton_nodes['LeftForeArm']['position']
            forearm_length = calculate_distance(arm_pos, forearm_pos)
            print(f"前臂长度 (LeftArm -> LeftForeArm): {forearm_length:.3f}")
        
        # 手部长度：LeftForeArm 到 LeftHand
        if 'LeftForeArm' in skeleton_nodes and 'LeftHand' in skeleton_nodes:
            forearm_pos = skeleton_nodes['LeftForeArm']['position']
            hand_pos = skeleton_nodes['LeftHand']['position']
            hand_length = calculate_distance(forearm_pos, hand_pos)
            print(f"手部长度 (LeftForeArm -> LeftHand): {hand_length:.3f}")
        
        # 大腿长度：LeftUpLeg 到 LeftLeg
        if 'LeftUpLeg' in skeleton_nodes and 'LeftLeg' in skeleton_nodes:
            upleg_pos = skeleton_nodes['LeftUpLeg']['position']
            leg_pos = skeleton_nodes['LeftLeg']['position']
            thigh_length = calculate_distance(upleg_pos, leg_pos)
            print(f"大腿长度 (LeftUpLeg -> LeftLeg): {thigh_length:.3f}")
        
        # 小腿长度：LeftLeg 到 LeftFoot
        if 'LeftLeg' in skeleton_nodes and 'LeftFoot' in skeleton_nodes:
            leg_pos = skeleton_nodes['LeftLeg']['position']
            foot_pos = skeleton_nodes['LeftFoot']['position']
            calf_length = calculate_distance(leg_pos, foot_pos)
            print(f"小腿长度 (LeftLeg -> LeftFoot): {calf_length:.3f}")
        
        # 计算比例
        print(f"\n=== 实际比例计算 ===")
        
        # 重新计算上臂和前臂长度
        if ('LeftShoulder' in skeleton_nodes and 'LeftArm' in skeleton_nodes and 
            'LeftForeArm' in skeleton_nodes and 'LeftUpLeg' in skeleton_nodes and 
            'LeftLeg' in skeleton_nodes and 'LeftFoot' in skeleton_nodes):
            
            # 正确的上臂长度：肩膀到肘部
            shoulder_pos = skeleton_nodes['LeftShoulder']['position']
            elbow_pos = skeleton_nodes['LeftArm']['position']  # LeftArm实际上是肘部位置
            actual_upper_arm = calculate_distance(shoulder_pos, elbow_pos)
            
            # 正确的前臂长度：肘部到手腕
            wrist_pos = skeleton_nodes['LeftForeArm']['position']  # LeftForeArm实际上是手腕位置
            actual_forearm = calculate_distance(elbow_pos, wrist_pos)
            
            # 腿部长度
            upleg_pos = skeleton_nodes['LeftUpLeg']['position']
            knee_pos = skeleton_nodes['LeftLeg']['position']
            foot_pos = skeleton_nodes['LeftFoot']['position']
            actual_thigh = calculate_distance(upleg_pos, knee_pos)
            actual_calf = calculate_distance(knee_pos, foot_pos)
            
            print(f"实际上臂长度: {actual_upper_arm:.3f}")
            print(f"实际前臂长度: {actual_forearm:.3f}")
            print(f"实际大腿长度: {actual_thigh:.3f}")
            print(f"实际小腿长度: {actual_calf:.3f}")
            
            if actual_forearm > 0:
                upper_arm_to_forearm_ratio = actual_upper_arm / actual_forearm
                print(f"上臂/前臂比例: {upper_arm_to_forearm_ratio:.3f}")
            
            if actual_calf > 0:
                thigh_to_calf_ratio = actual_thigh / actual_calf
                print(f"大腿/小腿比例: {thigh_to_calf_ratio:.3f}")
            
            if actual_forearm > 0 and actual_calf > 0:
                arm_total = actual_upper_arm + actual_forearm
                leg_total = actual_thigh + actual_calf
                arm_to_leg_ratio = arm_total / leg_total
                print(f"手臂/腿部比例: {arm_to_leg_ratio:.3f}")
        
    except Exception as e:
        print(f"调试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        importer.Destroy()
        manager.Destroy()

if __name__ == "__main__":
    # 调试当前生成的FBX文件
    fbx_file = r"e:\image_3d\text2dance\fbx_test_files\improved_dance_model_person_1.fbx"
    
    print("开始调试FBX骨骼结构...")
    debug_bone_structure(fbx_file)
    
    print("\n同时调试参考FBX文件...")
    reference_fbx = r"e:\image_3d\text2dance\fbx_test_files\jingang_13_c+_004.fbx"
    debug_bone_structure(reference_fbx)