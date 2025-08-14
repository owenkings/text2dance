#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证基于单角色比例改进的FBX文件效果
使用Skeleton0的准确比例数据进行验证
"""

import fbx
import math
import os
from datetime import datetime

# 导入参考比例配置
from reference_proportions_config import REFERENCE_PROPORTIONS

def calculate_distance(pos1, pos2):
    """计算两点间的距离"""
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)

def get_node_world_position(node):
    """获取节点的世界坐标位置"""
    transform = node.EvaluateGlobalTransform()
    translation = transform.GetT()
    return (translation[0], translation[1], translation[2])

def verify_fbx_proportions(fbx_file_path):
    """
    验证FBX文件的人体比例是否符合单角色参考标准
    """
    if not os.path.exists(fbx_file_path):
        print(f"文件不存在: {fbx_file_path}")
        return False
    
    # 初始化FBX SDK
    manager = fbx.FbxManager.Create()
    scene = fbx.FbxScene.Create(manager, "Scene")
    
    # 创建导入器
    importer = fbx.FbxImporter.Create(manager, "Importer")
    
    try:
        # 导入FBX文件
        if not importer.Initialize(fbx_file_path, -1, manager.GetIOSettings()):
            print(f"无法初始化导入器: {importer.GetStatus().GetErrorString()}")
            return False
        
        if not importer.Import(scene):
            print(f"无法导入FBX文件: {importer.GetStatus().GetErrorString()}")
            return False
        
        print(f"\n=== 验证基于单角色比例改进的FBX文件 ===")
        print(f"文件: {os.path.basename(fbx_file_path)}")
        
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
        
        print(f"\n=== 骨骼结构分析 ===")
        print(f"总骨骼数量: {len(skeleton_nodes)}")
        
        # 定义关键骨骼映射
        key_bones = {
            'hips': 'Hips',
            'spine': 'Spine',
            'spine2': 'Spine2',
            'neck': 'Neck',
            'head': 'Head',
            'left_shoulder': 'LeftShoulder',
            'left_arm': 'LeftArm',
            'left_forearm': 'LeftForeArm',
            'left_hand': 'LeftHand',
            'right_shoulder': 'RightShoulder',
            'right_arm': 'RightArm',
            'right_forearm': 'RightForeArm',
            'right_hand': 'RightHand',
            'left_upleg': 'LeftUpLeg',
            'left_leg': 'LeftLeg',
            'left_foot': 'LeftFoot',
            'right_upleg': 'RightUpLeg',
            'right_leg': 'RightLeg',
            'right_foot': 'RightFoot'
        }
        
        # 验证关键骨骼是否存在
        found_bones = 0
        missing_bones = []
        
        print(f"\n=== 关键骨骼位置 ===")
        for key, bone_name in key_bones.items():
            if bone_name in skeleton_nodes:
                pos = skeleton_nodes[bone_name]['position']
                node_type = skeleton_nodes[bone_name]['node'].GetNodeAttribute().GetName()
                print(f"{bone_name}: {pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f} ({node_type})")
                found_bones += 1
            else:
                missing_bones.append(bone_name)
        
        if missing_bones:
            print(f"\n⚠️  缺少关键骨骼: {missing_bones}")
        
        print(f"\n找到关键骨骼: {found_bones}/{len(key_bones)}")
        
        # 计算实际骨骼长度和比例
        def calculate_bone_length_safe(start_bone, end_bone, length_name):
            if start_bone in skeleton_nodes and end_bone in skeleton_nodes:
                start_pos = skeleton_nodes[start_bone]['position']
                end_pos = skeleton_nodes[end_bone]['position']
                length = calculate_distance(start_pos, end_pos)
                print(f"{length_name}: {length:.3f}")
                return length
            else:
                print(f"无法计算 {length_name}，缺少骨骼: {start_bone} 或 {end_bone}")
                return None
        
        print(f"\n=== 实际骨骼长度 ===")
        
        # 计算主要骨骼长度
        left_upper_arm = calculate_bone_length_safe('LeftShoulder', 'LeftArm', '左上臂长度')
        left_forearm = calculate_bone_length_safe('LeftArm', 'LeftForeArm', '左前臂长度')
        left_thigh = calculate_bone_length_safe('LeftUpLeg', 'LeftLeg', '左大腿长度')
        left_calf = calculate_bone_length_safe('LeftLeg', 'LeftFoot', '左小腿长度')
        
        right_upper_arm = calculate_bone_length_safe('RightShoulder', 'RightArm', '右上臂长度')
        right_forearm = calculate_bone_length_safe('RightArm', 'RightForeArm', '右前臂长度')
        right_thigh = calculate_bone_length_safe('RightUpLeg', 'RightLeg', '右大腿长度')
        right_calf = calculate_bone_length_safe('RightLeg', 'RightFoot', '右小腿长度')
        
        # 计算比例并与参考标准对比
        print(f"\n=== 人体比例验证（基于Skeleton0单角色数据） ===")
        
        # 参考比例
        ref_thigh_to_calf = REFERENCE_PROPORTIONS['bone_length_ratios']['thigh_to_calf']
        ref_upper_arm_to_forearm = REFERENCE_PROPORTIONS['bone_length_ratios']['upper_arm_to_forearm']
        ref_arm_to_leg = REFERENCE_PROPORTIONS['bone_length_ratios']['arm_to_leg']
        
        success_count = 0
        total_checks = 0
        
        # 上臂/前臂比例
        if left_upper_arm and left_forearm:
            actual_upper_arm_to_forearm = left_upper_arm / left_forearm
            diff = abs(actual_upper_arm_to_forearm - ref_upper_arm_to_forearm)
            total_checks += 1
            
            print(f"上臂/前臂比例: {actual_upper_arm_to_forearm:.3f}")
            print(f"  参考标准: {ref_upper_arm_to_forearm:.3f}")
            print(f"  差异: {diff:.3f}", end="")
            
            if diff < 0.05:
                print(" ✅ 优秀")
                success_count += 1
            elif diff < 0.15:
                print(" ⚠️ 可接受")
                success_count += 1
            else:
                print(" ❌ 需改进")
        
        # 大腿/小腿比例
        if left_thigh and left_calf:
            actual_thigh_to_calf = left_thigh / left_calf
            diff = abs(actual_thigh_to_calf - ref_thigh_to_calf)
            total_checks += 1
            
            print(f"\n大腿/小腿比例: {actual_thigh_to_calf:.3f}")
            print(f"  参考标准: {ref_thigh_to_calf:.3f}")
            print(f"  差异: {diff:.3f}", end="")
            
            if diff < 0.05:
                print(" ✅ 优秀")
                success_count += 1
            elif diff < 0.15:
                print(" ⚠️ 可接受")
                success_count += 1
            else:
                print(" ❌ 需改进")
        
        # 手臂/腿部比例
        if left_upper_arm and left_forearm and left_thigh and left_calf:
            arm_total = left_upper_arm + left_forearm
            leg_total = left_thigh + left_calf
            actual_arm_to_leg = arm_total / leg_total
            diff = abs(actual_arm_to_leg - ref_arm_to_leg)
            total_checks += 1
            
            print(f"\n手臂/腿部比例: {actual_arm_to_leg:.3f}")
            print(f"  参考标准: {ref_arm_to_leg:.3f}")
            print(f"  差异: {diff:.3f}", end="")
            print(f"\n总手臂长度: {arm_total:.3f}")
            print(f"总腿部长度: {leg_total:.3f}")
            
            if diff < 0.05:
                print(" ✅ 优秀")
                success_count += 1
            elif diff < 0.15:
                print(" ⚠️ 可接受")
                success_count += 1
            else:
                print(" ❌ 需改进")
        
        # 文件信息
        print(f"\n=== 改进状态验证 ===")
        file_size = os.path.getsize(fbx_file_path)
        print(f"文件大小: {file_size:,} 字节")
        
        mod_time = os.path.getmtime(fbx_file_path)
        mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"最后修改时间: {mod_time_str}")
        
        # 验证结论
        print(f"\n=== 验证结论 ===")
        
        if found_bones >= len(key_bones) * 0.8:
            print("✅ FBX文件结构完整，包含完整的人体骨骼")
        else:
            print("❌ FBX文件结构不完整，缺少关键骨骼")
        
        if success_count >= total_checks * 0.7:
            print("✅ 基于单角色比例的改进已成功应用")
            print("✅ 人体比例符合Skeleton0参考标准")
        else:
            print("⚠️ 人体比例仍需进一步调整")
        
        print(f"\n比例验证通过率: {success_count}/{total_checks} ({success_count/total_checks*100:.1f}%)")
        
        return success_count >= total_checks * 0.7
        
    except Exception as e:
        print(f"验证过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理资源
        importer.Destroy()
        manager.Destroy()

if __name__ == "__main__":
    # 验证当前生成的FBX文件
    fbx_file = r"e:\image_3d\text2dance\fbx_test_files\improved_dance_model_person_1.fbx"
    
    print("开始验证基于单角色比例改进的FBX文件...")
    success = verify_fbx_proportions(fbx_file)
    
    if success:
        print("\n🎉 验证成功！FBX文件的人体比例已成功改进")
    else:
        print("\n⚠️ 验证发现问题，可能需要进一步调整")