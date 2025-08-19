#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的PKL to FBX转换器 - 基于参考FBX文件的真实比例
创建包含网格和完整骨骼结构的人体模型
"""

import pickle
import numpy as np
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

# 参考FBX文件的人体比例配置（直接从jingang_13_c+_004.fbx提取）
REFERENCE_PROPORTIONS = {
    # 骨骼长度比例
    'bone_length_ratios': {
        'thigh_to_calf': 1.093,
        'upper_arm_to_forearm': 0.676,
        'arm_to_leg': 0.526,
    },
    # 参考骨骼长度 (单位: FBX单位)
    'reference_lengths': {
        'hips_to_spine': 8.507,
        'left_upper_arm': 16.137,
        'left_forearm': 23.853,
        'left_thigh': 39.703,
        'left_calf': 36.340,
        'spine_to_spine1': 12.036022,
        'spine1_to_spine2': 12.036022,
        'spine2_to_neck': 21.887209,
        'neck_to_head': 10.131214
    }
}

def load_pkl_data(pkl_file_path):
    """
    加载 pkl 文件并分析其结构
    """
    try:
        # 尝试使用 joblib 加载
        try:
            import joblib
            data = joblib.load(pkl_file_path)
            print(f"成功使用 joblib 加载 PKL 文件: {pkl_file_path}")
        except Exception as e:
            print(f"joblib 加载失败: {e}")
            # 尝试标准 pickle 方法
            methods = [
                lambda f: pickle.load(f),
                lambda f: pickle.load(f, encoding='latin1'),
                lambda f: pickle.load(f, encoding='bytes'),
            ]
            
            for i, method in enumerate(methods):
                try:
                    with open(pkl_file_path, 'rb') as f:
                        data = method(f)
                    print(f"成功加载 PKL 文件 (方法 {i+1}): {pkl_file_path}")
                    break
                except Exception as e:
                    if i == len(methods) - 1:
                        raise e
                    continue
        
        return data
        
    except Exception as e:
        print(f"加载 PKL 文件失败: {e}")
        return None

def calculate_bone_length(pos1, pos2):
    """计算两个位置之间的距离"""
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    dz = pos2[2] - pos1[2]
    return math.sqrt(dx*dx + dy*dy + dz*dz)

def calculate_reference_based_positions(joints_data, joint_index_map, scale_factor):
    """基于参考FBX文件的比例计算骨骼位置 - 精确比例版本"""
    try:
        bone_positions = {}
        
        # 获取关键关节位置
        def get_joint_pos(joint_name):
            if joint_name in joint_index_map:
                idx = joint_index_map[joint_name]
                pos = joints_data[idx]
                # 坐标系转换
                return (
                    float(pos[0]) * scale_factor,
                    float(-pos[2]) * scale_factor,
                    float(pos[1]) * scale_factor
                )
            return None
        
        # 获取基础关节位置
        nose_pos = get_joint_pos('nose')
        left_shoulder_pos = get_joint_pos('left_shoulder')
        right_shoulder_pos = get_joint_pos('right_shoulder')
        left_hip_pos = get_joint_pos('left_hip')
        right_hip_pos = get_joint_pos('right_hip')
        left_elbow_pos = get_joint_pos('left_elbow')
        right_elbow_pos = get_joint_pos('right_elbow')
        left_wrist_pos = get_joint_pos('left_wrist')
        right_wrist_pos = get_joint_pos('right_wrist')
        left_knee_pos = get_joint_pos('left_knee')
        right_knee_pos = get_joint_pos('right_knee')
        left_ankle_pos = get_joint_pos('left_ankle')
        right_ankle_pos = get_joint_pos('right_ankle')
        
        if not all([nose_pos, left_shoulder_pos, right_shoulder_pos, left_hip_pos, right_hip_pos]):
            print("警告: 缺少关键关节数据，使用默认位置")
            return {}
        
        # 计算中心点
        hip_center = (
            (left_hip_pos[0] + right_hip_pos[0]) / 2,
            (left_hip_pos[1] + right_hip_pos[1]) / 2,
            (left_hip_pos[2] + right_hip_pos[2]) / 2
        )
        
        shoulder_center = (
            (left_shoulder_pos[0] + right_shoulder_pos[0]) / 2,
            (left_shoulder_pos[1] + right_shoulder_pos[1]) / 2,
            (left_shoulder_pos[2] + right_shoulder_pos[2]) / 2
        )
        
        # 计算躯干长度作为整体缩放参考
        torso_length = calculate_bone_length(hip_center, shoulder_center)
        
        # 使用参考比例
        ref_lengths = REFERENCE_PROPORTIONS['reference_lengths']
        ref_ratios = REFERENCE_PROPORTIONS['bone_length_ratios']
        
        # 计算全局缩放比例（基于躯干长度）
        reference_torso_length = ref_lengths['hips_to_spine'] * 3  # 估算的躯干长度
        global_scale = torso_length / reference_torso_length if reference_torso_length > 0 else 1.0
        
        # 设置骨骼位置
        bone_positions['Hips'] = hip_center
        
        # 脊椎骨骼
        spine_offset_y = ref_lengths['hips_to_spine'] * global_scale
        bone_positions['Spine'] = (
            hip_center[0],
            hip_center[1] + spine_offset_y * 0.3,
            hip_center[2]
        )
        
        bone_positions['Spine1'] = (
            hip_center[0],
            hip_center[1] + spine_offset_y * 0.6,
            hip_center[2]
        )
        
        bone_positions['Spine2'] = shoulder_center
        
        # 颈部和头部
        neck_offset_y = spine_offset_y * 0.2
        bone_positions['Neck'] = (
            shoulder_center[0],
            shoulder_center[1] + neck_offset_y,
            shoulder_center[2]
        )
        
        bone_positions['Head'] = (
            nose_pos[0] if nose_pos else shoulder_center[0],
            shoulder_center[1] + neck_offset_y * 2,
            nose_pos[2] if nose_pos else shoulder_center[2]
        )
        
        # 手臂骨骼 - 使用固定的参考比例（完全基于参考FBX文件）
        def calculate_arm_positions(shoulder_pos, elbow_pos, wrist_pos, is_left=True):
            """计算手臂骨骼位置，使用固定的参考比例"""
            prefix = 'Left' if is_left else 'Right'
            
            # 计算手臂方向向量
            if elbow_pos and wrist_pos:
                # 从肩膀到手腕的总向量
                total_arm_vector = (
                    wrist_pos[0] - shoulder_pos[0],
                    wrist_pos[1] - shoulder_pos[1],
                    wrist_pos[2] - shoulder_pos[2]
                )
                total_arm_length = math.sqrt(sum(v*v for v in total_arm_vector))
                
                if total_arm_length > 0:
                    # 严格按照参考比例重新分配手臂长度
                    upper_arm_ratio = REFERENCE_PROPORTIONS['bone_length_ratios']['upper_arm_to_forearm']  # 0.676
                    # 如果上臂/前臂 = 0.676，那么前臂/上臂 = 1/0.676 = 1.479
                    # 总长度 = 上臂 + 前臂 = 上臂 + 上臂*1.479 = 上臂*(1 + 1.479) = 上臂*2.479
                    # 所以：上臂 = 总长度 / 2.479，前臂 = 总长度 * 1.479 / 2.479
                    actual_upper_arm = total_arm_length * upper_arm_ratio / (upper_arm_ratio + 1)
                    actual_forearm = total_arm_length / (upper_arm_ratio + 1)
                    
                    # 调试输出
                    print(f"调试 {prefix}手臂: 总长度={total_arm_length:.3f}, 上臂={actual_upper_arm:.3f}, 前臂={actual_forearm:.3f}, 比例={actual_upper_arm/actual_forearm:.3f}")
                    
                    # 单位方向向量
                    unit_vector = (
                        total_arm_vector[0] / total_arm_length,
                        total_arm_vector[1] / total_arm_length,
                        total_arm_vector[2] / total_arm_length
                    )
                    
                    # 计算肘部位置（从肩膀开始，沿着手臂方向，距离为上臂长度）
                    elbow_position = (
                        shoulder_pos[0] + unit_vector[0] * actual_upper_arm,
                        shoulder_pos[1] + unit_vector[1] * actual_upper_arm,
                        shoulder_pos[2] + unit_vector[2] * actual_upper_arm
                    )
                    
                    # 计算手腕位置（从肘部开始，沿着手臂方向，距离为前臂长度）
                    wrist_position = (
                        elbow_position[0] + unit_vector[0] * actual_forearm,
                        elbow_position[1] + unit_vector[1] * actual_forearm,
                        elbow_position[2] + unit_vector[2] * actual_forearm
                    )
                    
                    return {
                        f'{prefix}Shoulder': shoulder_pos,
                        f'{prefix}Arm': elbow_position,      # 上臂终点（肘部）
                        f'{prefix}ForeArm': wrist_position,  # 前臂终点（手腕）
                        f'{prefix}Hand': wrist_position
                    }
            
            # 如果数据不完整，使用原始位置
            positions = {f'{prefix}Shoulder': shoulder_pos}
            if elbow_pos:
                positions[f'{prefix}Arm'] = elbow_pos
                positions[f'{prefix}ForeArm'] = elbow_pos
            if wrist_pos:
                positions[f'{prefix}Hand'] = wrist_pos
            return positions
        
        # 计算左臂和右臂
        left_arm_positions = calculate_arm_positions(left_shoulder_pos, left_elbow_pos, left_wrist_pos, True)
        right_arm_positions = calculate_arm_positions(right_shoulder_pos, right_elbow_pos, right_wrist_pos, False)
        
        bone_positions.update(left_arm_positions)
        bone_positions.update(right_arm_positions)
        
        # 腿部骨骼 - 使用固定的参考比例（完全基于参考FBX文件）
        def calculate_leg_positions(hip_pos, knee_pos, ankle_pos, is_left=True):
            """计算腿部骨骼位置，使用固定的参考比例"""
            prefix = 'Left' if is_left else 'Right'
            
            # 计算腿部方向向量
            if knee_pos and ankle_pos:
                # 从髋部到脚踝的总向量
                total_leg_vector = (
                    ankle_pos[0] - hip_pos[0],
                    ankle_pos[1] - hip_pos[1],
                    ankle_pos[2] - hip_pos[2]
                )
                total_leg_length = math.sqrt(sum(v*v for v in total_leg_vector))
                
                if total_leg_length > 0:
                    # 严格按照参考比例重新分配腿部长度
                    thigh_ratio = REFERENCE_PROPORTIONS['bone_length_ratios']['thigh_to_calf']  # 1.093
                    # 如果大腿/小腿 = 1.093，那么小腿/大腿 = 1/1.093 = 0.915
                    # 总长度 = 大腿 + 小腿 = 大腿 + 大腿*0.915 = 大腿*(1 + 0.915) = 大腿*1.915
                    # 所以：大腿 = 总长度 / 1.915，小腿 = 总长度 * 0.915 / 1.915
                    actual_thigh = total_leg_length * thigh_ratio / (thigh_ratio + 1)
                    actual_calf = total_leg_length / (thigh_ratio + 1)
                    
                    # 调试输出
                    print(f"调试 {prefix}腿部: 总长度={total_leg_length:.3f}, 大腿={actual_thigh:.3f}, 小腿={actual_calf:.3f}, 比例={actual_thigh/actual_calf:.3f}")
                    
                    # 单位方向向量
                    unit_vector = (
                        total_leg_vector[0] / total_leg_length,
                        total_leg_vector[1] / total_leg_length,
                        total_leg_vector[2] / total_leg_length
                    )
                    
                    # 计算膝盖位置（从髋部开始，沿着腿部方向，距离为大腿长度）
                    knee_position = (
                        hip_pos[0] + unit_vector[0] * actual_thigh,
                        hip_pos[1] + unit_vector[1] * actual_thigh,
                        hip_pos[2] + unit_vector[2] * actual_thigh
                    )
                    
                    # 计算脚踝位置（从膝盖开始，沿着腿部方向，距离为小腿长度）
                    ankle_position = (
                        knee_position[0] + unit_vector[0] * actual_calf,
                        knee_position[1] + unit_vector[1] * actual_calf,
                        knee_position[2] + unit_vector[2] * actual_calf
                    )
                    
                    return {
                        f'{prefix}UpLeg': hip_pos,
                        f'{prefix}Leg': knee_position,
                        f'{prefix}Foot': ankle_position
                    }
            
            # 如果数据不完整，使用原始位置
            positions = {f'{prefix}UpLeg': hip_pos}
            if knee_pos:
                positions[f'{prefix}Leg'] = knee_pos
            if ankle_pos:
                positions[f'{prefix}Foot'] = ankle_pos
            return positions
        
        # 计算左腿和右腿
        left_leg_positions = calculate_leg_positions(left_hip_pos, left_knee_pos, left_ankle_pos, True)
        right_leg_positions = calculate_leg_positions(right_hip_pos, right_knee_pos, right_ankle_pos, False)
        
        bone_positions.update(left_leg_positions)
        bone_positions.update(right_leg_positions)
        
        print(f"基于参考比例计算了 {len(bone_positions)} 个骨骼位置")
        return bone_positions
        
    except Exception as e:
        print(f"计算参考比例位置时出错: {e}")
        return {}

def create_human_mesh(scene, vertices_data):
    """
    创建人体网格
    """
    try:
        # 创建网格节点
        mesh_node = fbx.FbxNode.Create(scene, "HumanMesh")
        
        # 创建网格
        mesh = fbx.FbxMesh.Create(scene, "HumanMeshGeometry")
        mesh_node.SetNodeAttribute(mesh)
        
        # 使用第一帧的数据创建基础网格
        if len(vertices_data.shape) == 3:  # (frames, vertices, coords)
            first_frame = vertices_data[0]
        else:
            first_frame = vertices_data
        
        vertices_count = first_frame.shape[0]
        
        # 初始化控制点
        mesh.InitControlPoints(vertices_count)
        control_points = mesh.GetControlPoints()
        
        # 设置顶点位置（缩放到合适大小并应用坐标系转换）
        scale_factor = 10.0  # 缩放因子
        for i in range(vertices_count):
            x, y, z = first_frame[i]
            # 原始坐标系转换为Maya坐标系：绕X轴旋转90度使头朝向上方
            control_points[i] = fbx.FbxVector4(
                float(x) * scale_factor,
                float(-z) * scale_factor,  # 原Z轴变为Y轴，取负值
                float(y) * scale_factor    # 原Y轴变为Z轴
            )
        
        # 创建简单的三角形面（连接相邻顶点）
        if vertices_count >= 3:
            # 创建一些基本的三角形面来形成网格
            face_count = min(vertices_count // 3, 200)  # 限制面数
            for i in range(face_count):
                if i * 3 + 2 < vertices_count:
                    mesh.BeginPolygon()
                    mesh.AddPolygon(i * 3)
                    mesh.AddPolygon(i * 3 + 1)
                    mesh.AddPolygon(i * 3 + 2)
                    mesh.EndPolygon()
        
        return mesh_node
        
    except Exception as e:
        print(f"创建人体网格时出错: {e}")
        return None

def create_human_skeleton(scene, joints3d_data):
    """
    创建完整的人体骨骼结构
    """
    try:
        # 定义完整的人体骨骼层次结构（类似参考文件）
        skeleton_hierarchy = {
            'Hips': {
                'parent': None,
                'coco_joint': 'nose',  # 使用nose作为根部参考
                'children': ['Spine', 'LeftUpLeg', 'RightUpLeg']
            },
            'Spine': {
                'parent': 'Hips',
                'coco_joint': 'nose',
                'children': ['Spine1']
            },
            'Spine1': {
                'parent': 'Spine',
                'coco_joint': 'nose',
                'children': ['Spine2']
            },
            'Spine2': {
                'parent': 'Spine1',
                'coco_joint': 'nose',
                'children': ['Neck', 'LeftShoulder', 'RightShoulder']
            },
            'Neck': {
                'parent': 'Spine2',
                'coco_joint': 'nose',
                'children': ['Head']
            },
            'Head': {
                'parent': 'Neck',
                'coco_joint': 'nose',
                'children': []
            },
            'LeftShoulder': {
                'parent': 'Spine2',
                'coco_joint': 'left_shoulder',
                'children': ['LeftArm']
            },
            'LeftArm': {
                'parent': 'LeftShoulder',
                'coco_joint': 'left_shoulder',
                'children': ['LeftForeArm']
            },
            'LeftForeArm': {
                'parent': 'LeftArm',
                'coco_joint': 'left_elbow',
                'children': ['LeftHand']
            },
            'LeftHand': {
                'parent': 'LeftForeArm',
                'coco_joint': 'left_wrist',
                'children': []
            },
            'RightShoulder': {
                'parent': 'Spine2',
                'coco_joint': 'right_shoulder',
                'children': ['RightArm']
            },
            'RightArm': {
                'parent': 'RightShoulder',
                'coco_joint': 'right_shoulder',
                'children': ['RightForeArm']
            },
            'RightForeArm': {
                'parent': 'RightArm',
                'coco_joint': 'right_elbow',
                'children': ['RightHand']
            },
            'RightHand': {
                'parent': 'RightForeArm',
                'coco_joint': 'right_wrist',
                'children': []
            },
            'LeftUpLeg': {
                'parent': 'Hips',
                'coco_joint': 'left_hip',
                'children': ['LeftLeg']
            },
            'LeftLeg': {
                'parent': 'LeftUpLeg',
                'coco_joint': 'left_knee',
                'children': ['LeftFoot']
            },
            'LeftFoot': {
                'parent': 'LeftLeg',
                'coco_joint': 'left_ankle',
                'children': []
            },
            'RightUpLeg': {
                'parent': 'Hips',
                'coco_joint': 'right_hip',
                'children': ['RightLeg']
            },
            'RightLeg': {
                'parent': 'RightUpLeg',
                'coco_joint': 'right_knee',
                'children': ['RightFoot']
            },
            'RightFoot': {
                'parent': 'RightLeg',
                'coco_joint': 'right_ankle',
                'children': []
            }
        }
        
        # COCO 17关节名称映射
        coco_joint_names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        # 创建关节索引映射
        joint_index_map = {name: i for i, name in enumerate(coco_joint_names)}
        
        # 创建骨骼节点字典
        bone_nodes = {}
        
        # 缩放因子
        scale_factor = 100.0
        
        # 获取第一帧数据用于初始位置
        if len(joints3d_data.shape) == 3:
            first_frame = joints3d_data[0]
        else:
            first_frame = joints3d_data
        
        # 计算基于参考比例的骨骼位置
        bone_positions = calculate_reference_based_positions(first_frame, joint_index_map, scale_factor)
        
        # 创建所有骨骼节点
        for bone_name, bone_info in skeleton_hierarchy.items():
            # 创建骨骼属性
            if bone_info['parent'] is None:
                # 根骨骼
                skeleton_attr = fbx.FbxSkeleton.Create(scene, f"{bone_name}_attr")
                skeleton_attr.SetSkeletonType(fbx.FbxSkeleton.eRoot)
                skeleton_attr.Size.Set(100.0)
            else:
                # 子骨骼
                skeleton_attr = fbx.FbxSkeleton.Create(scene, f"{bone_name}_attr")
                skeleton_attr.SetSkeletonType(fbx.FbxSkeleton.eLimbNode)
                skeleton_attr.Size.Set(100.0)
            
            # 创建节点
            bone_node = fbx.FbxNode.Create(scene, bone_name)
            bone_node.SetNodeAttribute(skeleton_attr)
            
            # 使用计算出的位置
            if bone_name in bone_positions:
                pos_x, pos_y, pos_z = bone_positions[bone_name]
                bone_node.LclTranslation.Set(fbx.FbxDouble3(pos_x, pos_y, pos_z))
            else:
                # 回退到原始方法
                coco_joint = bone_info['coco_joint']
                if coco_joint in joint_index_map:
                    joint_idx = joint_index_map[coco_joint]
                    joint_pos = first_frame[joint_idx]
                    
                    # 应用缩放和坐标系转换
                    pos_x = float(joint_pos[0]) * scale_factor
                    pos_y = float(-joint_pos[2]) * scale_factor
                    pos_z = float(joint_pos[1]) * scale_factor
                    
                    bone_node.LclTranslation.Set(fbx.FbxDouble3(pos_x, pos_y, pos_z))
            
            bone_nodes[bone_name] = bone_node
        
        # 建立骨骼层次结构
        root_bone = None
        for bone_name, bone_info in skeleton_hierarchy.items():
            bone_node = bone_nodes[bone_name]
            
            if bone_info['parent'] is None:
                # 根骨骼
                root_bone = bone_node
            else:
                # 子骨骼
                parent_name = bone_info['parent']
                if parent_name in bone_nodes:
                    parent_node = bone_nodes[parent_name]
                    parent_node.AddChild(bone_node)
        
        return root_bone, bone_nodes
        
    except Exception as e:
        print(f"创建人体骨骼时出错: {e}")
        return None, {}

def create_improved_fbx(joints3d_data, mesh_data, output_path, person_id=0):
    """
    创建改进的FBX文件，包含完整的人体模型
    """
    try:
        # 创建 FBX 管理器和场景
        manager = fbx.FbxManager.Create()
        scene = fbx.FbxScene.Create(manager, "HumanScene")
        
        # 设置场景信息
        try:
            scene_info = scene.GetSceneInfo()
            if scene_info:
                pass
        except Exception as e:
            print(f"设置场景信息时出现警告: {e}")
        
        # 设置全局设置
        global_settings = scene.GetGlobalSettings()
        global_settings.SetSystemUnit(fbx.FbxSystemUnit.cm)
        global_settings.SetOriginalSystemUnit(fbx.FbxSystemUnit.cm)
        global_settings.SetTimeMode(fbx.FbxTime.eFrames30)
        
        # 创建根节点
        root_node = scene.GetRootNode()
        
        # 创建人体骨骼
        skeleton_root, bone_nodes = create_human_skeleton(scene, joints3d_data)
        if skeleton_root:
            root_node.AddChild(skeleton_root)
            print(f"创建了 {len(bone_nodes)} 个骨骼节点")
        
        # 如果有网格数据，创建网格
        if mesh_data is not None:
            mesh_node = create_human_mesh(scene, mesh_data)
            if mesh_node:
                root_node.AddChild(mesh_node)
                print("创建了人体网格")
                
                # 尝试将网格绑定到骨骼（简单绑定）
                try:
                    mesh_attr = mesh_node.GetMesh()
                    if mesh_attr and skeleton_root:
                        # 创建蒙皮变形器
                        skin = fbx.FbxSkin.Create(scene, "HumanSkin")
                        
                        # 为主要骨骼创建簇
                        main_bones = ['Hips', 'Spine2', 'LeftArm', 'RightArm', 'LeftUpLeg', 'RightUpLeg']
                        for bone_name in main_bones:
                            if bone_name in bone_nodes:
                                bone_node = bone_nodes[bone_name]
                                
                                # 创建簇
                                cluster = fbx.FbxCluster.Create(scene, f"{bone_name}_cluster")
                                cluster.SetLink(bone_node)
                                cluster.SetLinkMode(fbx.FbxCluster.eTotalOne)
                                
                                # 设置变换矩阵
                                transform_matrix = fbx.FbxAMatrix()
                                cluster.SetTransformMatrix(transform_matrix)
                                
                                link_matrix = bone_node.EvaluateGlobalTransform()
                                cluster.SetTransformLinkMatrix(link_matrix)
                                
                                # 添加顶点权重（简单平均分配）
                                vertex_count = mesh_attr.GetControlPointsCount()
                                vertices_per_bone = max(1, vertex_count // len(main_bones))
                                start_vertex = main_bones.index(bone_name) * vertices_per_bone
                                end_vertex = min(start_vertex + vertices_per_bone, vertex_count)
                                
                                for v in range(start_vertex, end_vertex):
                                    cluster.AddControlPointIndex(v, 1.0)
                                
                                skin.AddCluster(cluster)
                        
                        # 将蒙皮添加到网格
                        mesh_attr.AddDeformer(skin)
                        print("创建了网格蒙皮绑定")
                        
                except Exception as e:
                    print(f"创建蒙皮绑定时出现警告: {e}")
        
        # 如果有多帧数据，创建动画
        if len(joints3d_data.shape) == 3 and joints3d_data.shape[0] > 1:
            num_frames = joints3d_data.shape[0]
            print(f"创建 {num_frames} 帧的骨骼动画...")
            
            # 创建动画堆栈和层
            anim_stack = fbx.FbxAnimStack.Create(scene, "HumanAnimation")
            anim_layer = fbx.FbxAnimLayer.Create(scene, "BaseLayer")
            anim_stack.AddMember(anim_layer)
            
            # COCO关节映射
            coco_joint_names = [
                'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
                'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
                'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
                'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
            ]
            
            # 为骨骼创建动画
            bone_to_joint_map = {
                'Hips': 'nose',
                'LeftShoulder': 'left_shoulder',
                'RightShoulder': 'right_shoulder',
                'LeftArm': 'left_shoulder',
                'RightArm': 'right_shoulder',
                'LeftForeArm': 'left_elbow',
                'RightForeArm': 'right_elbow',
                'LeftHand': 'left_wrist',
                'RightHand': 'right_wrist',
                'LeftUpLeg': 'left_hip',
                'RightUpLeg': 'right_hip',
                'LeftLeg': 'left_knee',
                'RightLeg': 'right_knee',
                'LeftFoot': 'left_ankle',
                'RightFoot': 'right_ankle'
            }
            
            scale_factor = 100.0
            
            for bone_name, joint_name in bone_to_joint_map.items():
                if bone_name in bone_nodes and joint_name in coco_joint_names:
                    bone_node = bone_nodes[bone_name]
                    joint_idx = coco_joint_names.index(joint_name)
                    
                    # 创建位移动画曲线
                    curve_x = bone_node.LclTranslation.GetCurve(anim_layer, "X", True)
                    curve_y = bone_node.LclTranslation.GetCurve(anim_layer, "Y", True)
                    curve_z = bone_node.LclTranslation.GetCurve(anim_layer, "Z", True)
                    
                    # 添加关键帧
                    for frame_idx in range(0, num_frames, max(1, num_frames // 30)):
                        time = fbx.FbxTime()
                        time.SetFrame(frame_idx, fbx.FbxTime.eFrames30)
                        
                        joint_pos = joints3d_data[frame_idx][joint_idx]
                        
                        # 应用缩放因子和坐标系转换
                        # 原始坐标系转换为Maya坐标系：绕X轴旋转90度使头朝向上方
                        scaled_pos = [
                            float(joint_pos[0]) * scale_factor,
                            float(-joint_pos[2]) * scale_factor,  # 原Z轴变为Y轴，取负值
                            float(joint_pos[1]) * scale_factor    # 原Y轴变为Z轴
                        ]
                        
                        # 为不同骨骼添加偏移
                        if 'Spine' in bone_name:
                            scaled_pos[1] += 20.0
                        elif 'Neck' in bone_name:
                            scaled_pos[1] += 40.0
                        elif 'Head' in bone_name:
                            scaled_pos[1] += 60.0
                        
                        if curve_x:
                            key_index = curve_x.KeyAdd(time)[0]
                            curve_x.KeySetValue(key_index, scaled_pos[0])
                            curve_x.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
                        
                        if curve_y:
                            key_index = curve_y.KeyAdd(time)[0]
                            curve_y.KeySetValue(key_index, scaled_pos[1])
                            curve_y.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
                        
                        if curve_z:
                            key_index = curve_z.KeyAdd(time)[0]
                            curve_z.KeySetValue(key_index, scaled_pos[2])
                            curve_z.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
        
        # 导出 FBX 文件
        exporter = fbx.FbxExporter.Create(scene, "")
        
        if not exporter.Initialize(output_path, -1, manager.GetIOSettings()):
            print(f"无法初始化 FBX 导出器: {output_path}")
            return False
        
        # 设置导出格式
        try:
            if hasattr(fbx.FbxIO, 'eFBX_20203_2'):
                exporter.SetFileExportVersion(fbx.FbxIO.eFBX_20203_2)
            elif hasattr(fbx.FbxIO, 'eFBX_2020'):
                exporter.SetFileExportVersion(fbx.FbxIO.eFBX_2020)
        except Exception as e:
            print(f"设置导出格式时出现警告: {e}")
        
        # 导出场景
        result = exporter.Export(scene)
        exporter.Destroy()
        
        if result:
            print(f"成功创建改进的 FBX 文件: {output_path}")
            file_size = os.path.getsize(output_path)
            print(f"文件大小: {file_size:,} 字节")
            return True
        else:
            print(f"导出 FBX 文件失败: {output_path}")
            return False
            
    except Exception as e:
        print(f"创建改进的 FBX 文件时出错: {e}")
        return False
    finally:
        if 'manager' in locals():
            manager.Destroy()

def main():
    """
    主函数
    """
    # 输入和输出文件路径
    # 输入和输出文件路径
    pkl_file = r"e:\image_3d\text2dance\output\sample_video\pmce_output.pkl"
    output_fbx = r"e:\image_3d\text2dance\output\sample_video\improved_human_model.fbx"

    # pkl_file = r"e:\image_3d\text2dance\output\twodance\pmce_output.pkl"
    # output_fbx = r"e:\image_3d\text2dance\output\twodance\improved_twohuman_model.fbx"

    # pkl_file = r"e:\image_3d\text2dance\output\【20分钟 BASI普拉提 全身训练｜增强灵活性与力量 垫上普拉提跟练】Mira普拉提 初学者课程.f30016_split_171_281\pmce_output.pkl"
    # output_fbx = r"e:\image_3d\text2dance\output\【20分钟 BASI普拉提 全身训练｜增强灵活性与力量 垫上普拉提跟练】Mira普拉提 初学者课程.f30016_split_171_281\improved_dance_model.fbx"
    
    
    print("=== 改进的 PKL to FBX 转换器 ===")
    print(f"输入文件: {pkl_file}")
    print(f"输出文件: {output_fbx}")
    
    # 检查输入文件是否存在
    if not os.path.exists(pkl_file):
        print(f"错误: 输入文件不存在: {pkl_file}")
        return
    
    # 加载 PKL 数据
    data = load_pkl_data(pkl_file)
    if data is None:
        return
    
    # 处理数据
    if isinstance(data, dict):
        success_count = 0
        
        for person_id, person_data in data.items():
            print(f"\n=== 处理人物 {person_id} ===")
            
            if not isinstance(person_data, dict):
                print(f"跳过人物 {person_id}: 数据格式不正确")
                continue
            
            # 获取关节和网格数据
            joints3d_data = person_data.get('joints3d')
            mesh_data = person_data.get('mesh')
            
            if joints3d_data is not None:
                print(f"找到 joints3d 数据，形状: {joints3d_data.shape}")
                
                if mesh_data is not None:
                    print(f"找到 mesh 数据，形状: {mesh_data.shape}")
                else:
                    print("未找到 mesh 数据，将只创建骨骼")
                
                # 为每个人物创建单独的 FBX 文件
                person_output_fbx = output_fbx.replace('.fbx', f'_person_{person_id}.fbx')
                
                # 创建改进的 FBX 文件
                if create_improved_fbx(joints3d_data, mesh_data, person_output_fbx, person_id):
                    print(f"✅ 人物 {person_id} 的改进 FBX 文件创建成功: {person_output_fbx}")
                    success_count += 1
                else:
                    print(f"❌ 人物 {person_id} 的改进 FBX 文件创建失败")
            else:
                print(f"跳过人物 {person_id}: 未找到 joints3d 数据")
        
        print(f"\n=== 转换完成 ===")
        print(f"成功转换: {success_count} 个人物")
        
    else:
        print(f"不支持的数据格式: {type(data)}")

if __name__ == "__main__":
    main()