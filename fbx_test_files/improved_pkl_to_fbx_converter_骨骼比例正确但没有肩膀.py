#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的PKL to FBX转换器
创建包含网格和完整骨骼结构的人体模型
"""

import pickle
import numpy as np
import os
import sys

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

def transform_coordinates(x, y, z, coordinate_system='maya'):
    """
    坐标系转换函数 - 参考 save_obj 函数的坐标变换逻辑
    将原始坐标系转换为目标坐标系
    
    Args:
        x, y, z: 原始坐标
        coordinate_system: 坐标系类型 ('maya', 'blender', 'matplotlib')
    
    Returns:
        转换后的坐标 (x', y', z')
    """
    import numpy as np
    
    # 将单个坐标点转换为数组格式以便矩阵运算
    v = np.array([[float(x), float(y), float(z)]])
    
    # 应用与 StableAligner 一致的基础旋转变换
    rx, ry, rz = 0.1, 0.0, 0.0
    
    # 计算旋转矩阵的三角函数值
    cos_rx, sin_rx = np.cos(rx), np.sin(rx)
    cos_ry, sin_ry = np.cos(ry), np.sin(ry)
    cos_rz, sin_rz = np.cos(rz), np.sin(rz)
    
    # 构建XYZ轴旋转矩阵
    R_x = np.array([[1, 0, 0], [0, cos_rx, -sin_rx], [0, sin_rx, cos_rx]])
    R_y = np.array([[cos_ry, 0, sin_ry], [0, 1, 0], [-sin_ry, 0, cos_ry]])
    R_z = np.array([[cos_rz, -sin_rz, 0], [sin_rz, cos_rz, 0], [0, 0, 1]])
    
    # 按照 Z-Y-X 顺序组合旋转矩阵
    R = R_z @ R_y @ R_x
    
    # 应用基础旋转变换
    transformed_vertices = (R @ v.T).T
    
    # 根据目标坐标系应用不同的变换
    if coordinate_system == 'maya':
        # Maya坐标系：Y轴向上，Z轴向前，X轴向右
        # 进行Y轴和Z轴翻转，然后绕Y轴逆时针旋转45度
        vertices_final = transformed_vertices.copy()
        vertices_final[:, 1] = -vertices_final[:, 1]  # Y轴翻转，解决倒立问题
        vertices_final[:, 2] = -vertices_final[:, 2]  # Z轴翻转，解决面向屏幕后方的问题
        
        # 绕Y轴逆时针旋转45度：x' = √2/2 * x + √2/2 * z, y' = y, z' = -√2/2 * x + √2/2 * z
        temp_vertices = vertices_final.copy()
        sqrt2_half = np.sqrt(2) / 2
        vertices_final[:, 0] = sqrt2_half * temp_vertices[:, 0] + sqrt2_half * temp_vertices[:, 2]   # x' = √2/2 * x + √2/2 * z
        vertices_final[:, 1] = temp_vertices[:, 1]   # y' = y (保持不变)
        vertices_final[:, 2] = -sqrt2_half * temp_vertices[:, 0] + sqrt2_half * temp_vertices[:, 2]  # z' = -√2/2 * x + √2/2 * z
        
    elif coordinate_system == 'blender':
        # Blender坐标系：Z轴向上，Y轴向前，X轴向右
        vertices_final = transformed_vertices.copy()
        vertices_final[:, 0] = transformed_vertices[:, 0]   # X保持不变
        vertices_final[:, 1] = -transformed_vertices[:, 1]  # Y = -原Y（向前）
        vertices_final[:, 2] = transformed_vertices[:, 2]   # Z = 原Z（向上）
        
    elif coordinate_system == 'matplotlib':
        # 应用与 render_stable_3d_model 完全相同的坐标系变换序列
        # 第一步坐标变换：x->x, y->z, z->-y
        temp_vertices = transformed_vertices.copy()
        temp_vertices[:, 0] = transformed_vertices[:, 0]
        temp_vertices[:, 1] = transformed_vertices[:, 2]
        temp_vertices[:, 2] = -transformed_vertices[:, 1]
        
        # 第二步坐标变换：x->-y, y->x, z->z
        vertices_final = temp_vertices.copy()
        vertices_final[:, 0] = -temp_vertices[:, 1]
        vertices_final[:, 1] = temp_vertices[:, 0]
        vertices_final[:, 2] = temp_vertices[:, 2]
        
    else:
        # 默认：不进行额外坐标变换
        vertices_final = transformed_vertices
    
    # 返回转换后的单个坐标点
    result = vertices_final[0]
    return float(result[0]), float(result[1]), float(result[2])

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
        
        # 设置顶点位置（缩放到合适大小）
        scale_factor = 100.0  # 放大100倍
        for i in range(vertices_count):
            x, y, z = first_frame[i]
            # 应用坐标系转换
            transformed_x, transformed_y, transformed_z = transform_coordinates(x, y, z, coordinate_system='maya')
            control_points[i] = fbx.FbxVector4(
                transformed_x * scale_factor,
                transformed_y * scale_factor,
                transformed_z * scale_factor
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
        
        # 根据实际COCO关节数据动态计算骨骼长度的函数
        def calculate_bone_length_from_joints(joint1_pos, joint2_pos, scale_factor=100.0):
            """根据两个关节位置计算骨骼长度"""
            distance = np.linalg.norm(np.array(joint1_pos) - np.array(joint2_pos))
            return distance * scale_factor
        
        # 动态计算骨骼长度（基于第一帧数据）
        def get_dynamic_bone_lengths(frame_data, joint_index_map, scale_factor=100.0):
            """基于实际关节数据计算骨骼长度"""
            bone_lengths = {}
            
            # 计算主要骨骼长度
            try:
                # 脊椎相关长度（使用鼻子到臀部中心的距离作为参考）
                nose_pos = frame_data[joint_index_map['nose']]
                left_hip_pos = frame_data[joint_index_map['left_hip']]
                right_hip_pos = frame_data[joint_index_map['right_hip']]
                hip_center = (left_hip_pos + right_hip_pos) / 2
                
                spine_total_length = calculate_bone_length_from_joints(nose_pos, hip_center, scale_factor)
                bone_lengths['Spine'] = spine_total_length * 0.2  # 脊椎第一段
                bone_lengths['Spine1'] = spine_total_length * 0.3  # 脊椎第二段
                bone_lengths['Spine2'] = spine_total_length * 0.3  # 脊椎第三段
                bone_lengths['Neck'] = spine_total_length * 0.15   # 颈部
                bone_lengths['Head'] = spine_total_length * 0.05   # 头部
                
                # 左臂长度
                left_shoulder_pos = frame_data[joint_index_map['left_shoulder']]
                left_elbow_pos = frame_data[joint_index_map['left_elbow']]
                left_wrist_pos = frame_data[joint_index_map['left_wrist']]
                
                bone_lengths['LeftShoulder'] = spine_total_length * 0.1  # 肩膀连接
                bone_lengths['LeftArm'] = calculate_bone_length_from_joints(left_shoulder_pos, left_elbow_pos, scale_factor)
                bone_lengths['LeftForeArm'] = calculate_bone_length_from_joints(left_elbow_pos, left_wrist_pos, scale_factor)
                bone_lengths['LeftHand'] = bone_lengths['LeftForeArm'] * 0.3  # 手部长度
                
                # 右臂长度（对称）
                right_shoulder_pos = frame_data[joint_index_map['right_shoulder']]
                right_elbow_pos = frame_data[joint_index_map['right_elbow']]
                right_wrist_pos = frame_data[joint_index_map['right_wrist']]
                
                bone_lengths['RightShoulder'] = spine_total_length * 0.1  # 肩膀连接
                bone_lengths['RightArm'] = calculate_bone_length_from_joints(right_shoulder_pos, right_elbow_pos, scale_factor)
                bone_lengths['RightForeArm'] = calculate_bone_length_from_joints(right_elbow_pos, right_wrist_pos, scale_factor)
                bone_lengths['RightHand'] = bone_lengths['RightForeArm'] * 0.3  # 手部长度
                
                # 左腿长度
                left_knee_pos = frame_data[joint_index_map['left_knee']]
                left_ankle_pos = frame_data[joint_index_map['left_ankle']]
                
                bone_lengths['LeftUpLeg'] = calculate_bone_length_from_joints(left_hip_pos, left_knee_pos, scale_factor)
                bone_lengths['LeftLeg'] = calculate_bone_length_from_joints(left_knee_pos, left_ankle_pos, scale_factor)
                bone_lengths['LeftFoot'] = bone_lengths['LeftLeg'] * 0.3  # 脚部长度
                
                # 右腿长度（对称）
                right_knee_pos = frame_data[joint_index_map['right_knee']]
                right_ankle_pos = frame_data[joint_index_map['right_ankle']]
                
                bone_lengths['RightUpLeg'] = calculate_bone_length_from_joints(right_hip_pos, right_knee_pos, scale_factor)
                bone_lengths['RightLeg'] = calculate_bone_length_from_joints(right_knee_pos, right_ankle_pos, scale_factor)
                bone_lengths['RightFoot'] = bone_lengths['RightLeg'] * 0.3  # 脚部长度
                
            except Exception as e:
                print(f"计算动态骨骼长度时出错: {e}")
                # 如果计算失败，使用默认值
                bone_lengths = {
                    'Spine': 20.0, 'Spine1': 25.0, 'Spine2': 25.0, 'Neck': 15.0, 'Head': 10.0,
                    'LeftShoulder': 15.0, 'LeftArm': 30.0, 'LeftForeArm': 25.0, 'LeftHand': 8.0,
                    'RightShoulder': 15.0, 'RightArm': 30.0, 'RightForeArm': 25.0, 'RightHand': 8.0,
                    'LeftUpLeg': 40.0, 'LeftLeg': 35.0, 'LeftFoot': 12.0,
                    'RightUpLeg': 40.0, 'RightLeg': 35.0, 'RightFoot': 12.0,
                }
            
            return bone_lengths
        
        # 获取动态骨骼长度
        reference_bone_lengths = get_dynamic_bone_lengths(first_frame, joint_index_map, scale_factor)
        
        # 计算骨骼位置的辅助函数（基于实际关节位置）
        def calculate_bone_position(bone_name):
            """根据实际COCO关节位置计算骨骼位置"""
            bone_info = skeleton_hierarchy[bone_name]
            coco_joint = bone_info['coco_joint']
            
            if coco_joint in joint_index_map:
                joint_idx = joint_index_map[coco_joint]
                joint_pos = first_frame[joint_idx]
                
                # 应用坐标系转换和缩放
                transformed_x, transformed_y, transformed_z = transform_coordinates(
                    joint_pos[0], joint_pos[1], joint_pos[2], coordinate_system='maya'
                )
                
                base_pos = [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                
                # 为特定骨骼添加基于动态长度的偏移
                if bone_name == 'Hips':
                    # 臀部作为根骨骼，使用臀部中心位置
                    left_hip_pos = first_frame[joint_index_map['left_hip']]
                    right_hip_pos = first_frame[joint_index_map['right_hip']]
                    hip_center = (left_hip_pos + right_hip_pos) / 2
                    
                    transformed_x, transformed_y, transformed_z = transform_coordinates(
                        hip_center[0], hip_center[1], hip_center[2], coordinate_system='maya'
                    )
                    return [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                
                elif 'Spine' in bone_name:
                    # 脊椎骨骼基于鼻子和臀部之间的插值
                    nose_pos = first_frame[joint_index_map['nose']]
                    left_hip_pos = first_frame[joint_index_map['left_hip']]
                    right_hip_pos = first_frame[joint_index_map['right_hip']]
                    hip_center = (left_hip_pos + right_hip_pos) / 2
                    
                    if bone_name == 'Spine':
                        # 第一段脊椎，20%位置
                        interp_pos = hip_center + 0.2 * (nose_pos - hip_center)
                    elif bone_name == 'Spine1':
                        # 第二段脊椎，50%位置
                        interp_pos = hip_center + 0.5 * (nose_pos - hip_center)
                    elif bone_name == 'Spine2':
                        # 第三段脊椎，80%位置
                        interp_pos = hip_center + 0.8 * (nose_pos - hip_center)
                    
                    transformed_x, transformed_y, transformed_z = transform_coordinates(
                        interp_pos[0], interp_pos[1], interp_pos[2], coordinate_system='maya'
                    )
                    return [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                
                elif bone_name == 'Neck':
                    # 颈部位于鼻子和肩膀中心之间
                    nose_pos = first_frame[joint_index_map['nose']]
                    left_shoulder_pos = first_frame[joint_index_map['left_shoulder']]
                    right_shoulder_pos = first_frame[joint_index_map['right_shoulder']]
                    shoulder_center = (left_shoulder_pos + right_shoulder_pos) / 2
                    
                    neck_pos = shoulder_center + 0.7 * (nose_pos - shoulder_center)
                    transformed_x, transformed_y, transformed_z = transform_coordinates(
                        neck_pos[0], neck_pos[1], neck_pos[2], coordinate_system='maya'
                    )
                    return [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                
                elif bone_name == 'Head':
                    # 头部稍微高于鼻子位置
                    nose_pos = first_frame[joint_index_map['nose']]
                    head_offset = reference_bone_lengths.get('Head', 10.0) / scale_factor
                    head_pos = nose_pos + np.array([0, head_offset, 0])
                    
                    transformed_x, transformed_y, transformed_z = transform_coordinates(
                        head_pos[0], head_pos[1], head_pos[2], coordinate_system='maya'
                    )
                    return [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                
                else:
                    # 其他骨骼直接使用对应关节位置
                    return base_pos
            
            else:
                return [0, 0, 0]
        
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
            
            # 使用改进的位置计算函数
            bone_position = calculate_bone_position(bone_name)
            bone_node.LclTranslation.Set(fbx.FbxDouble3(bone_position[0], bone_position[1], bone_position[2]))
            
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
        
        # 获取骨骼层次结构定义
        skeleton_hierarchy = {
            'Hips': {
                'parent': None,
                'coco_joint': 'nose',
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
            
            # 为每一帧计算所有骨骼的位置（基于实际关节数据）
            for frame_idx in range(0, num_frames, max(1, num_frames // 30)):
                time = fbx.FbxTime()
                time.SetFrame(frame_idx, fbx.FbxTime.eFrames30)
                
                frame_data = joints3d_data[frame_idx]
                frame_bone_positions = {}
                
                # 为每个骨骼计算当前帧的位置
                for bone_name, bone_info in skeleton_hierarchy.items():
                    coco_joint = bone_info['coco_joint']
                    
                    if bone_name == 'Hips':
                        # 臀部使用臀部中心位置
                        left_hip_idx = coco_joint_names.index('left_hip')
                        right_hip_idx = coco_joint_names.index('right_hip')
                        left_hip_pos = frame_data[left_hip_idx]
                        right_hip_pos = frame_data[right_hip_idx]
                        hip_center = (left_hip_pos + right_hip_pos) / 2
                        
                        transformed_x, transformed_y, transformed_z = transform_coordinates(
                            hip_center[0], hip_center[1], hip_center[2], coordinate_system='maya'
                        )
                        bone_pos = [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                    
                    elif 'Spine' in bone_name:
                        # 脊椎骨骼基于鼻子和臀部之间的插值
                        nose_idx = coco_joint_names.index('nose')
                        left_hip_idx = coco_joint_names.index('left_hip')
                        right_hip_idx = coco_joint_names.index('right_hip')
                        
                        nose_pos = frame_data[nose_idx]
                        left_hip_pos = frame_data[left_hip_idx]
                        right_hip_pos = frame_data[right_hip_idx]
                        hip_center = (left_hip_pos + right_hip_pos) / 2
                        
                        if bone_name == 'Spine':
                            interp_pos = hip_center + 0.2 * (nose_pos - hip_center)
                        elif bone_name == 'Spine1':
                            interp_pos = hip_center + 0.5 * (nose_pos - hip_center)
                        elif bone_name == 'Spine2':
                            interp_pos = hip_center + 0.8 * (nose_pos - hip_center)
                        
                        transformed_x, transformed_y, transformed_z = transform_coordinates(
                            interp_pos[0], interp_pos[1], interp_pos[2], coordinate_system='maya'
                        )
                        bone_pos = [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                    
                    elif bone_name == 'Neck':
                        # 颈部位于鼻子和肩膀中心之间
                        nose_idx = coco_joint_names.index('nose')
                        left_shoulder_idx = coco_joint_names.index('left_shoulder')
                        right_shoulder_idx = coco_joint_names.index('right_shoulder')
                        
                        nose_pos = frame_data[nose_idx]
                        left_shoulder_pos = frame_data[left_shoulder_idx]
                        right_shoulder_pos = frame_data[right_shoulder_idx]
                        shoulder_center = (left_shoulder_pos + right_shoulder_pos) / 2
                        
                        neck_pos = shoulder_center + 0.7 * (nose_pos - shoulder_center)
                        transformed_x, transformed_y, transformed_z = transform_coordinates(
                            neck_pos[0], neck_pos[1], neck_pos[2], coordinate_system='maya'
                        )
                        bone_pos = [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                    
                    elif bone_name == 'Head':
                        # 头部稍微高于鼻子位置
                        nose_idx = coco_joint_names.index('nose')
                        nose_pos = frame_data[nose_idx]
                        # 使用默认头部长度
                        head_offset = 10.0 / scale_factor
                        head_pos = nose_pos + np.array([0, head_offset, 0])
                        
                        transformed_x, transformed_y, transformed_z = transform_coordinates(
                            head_pos[0], head_pos[1], head_pos[2], coordinate_system='maya'
                        )
                        bone_pos = [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                    
                    else:
                        # 其他骨骼直接使用对应的COCO关节位置
                        if coco_joint in coco_joint_names:
                            joint_idx = coco_joint_names.index(coco_joint)
                            joint_pos = frame_data[joint_idx]
                            transformed_x, transformed_y, transformed_z = transform_coordinates(
                                joint_pos[0], joint_pos[1], joint_pos[2], coordinate_system='maya'
                            )
                            bone_pos = [transformed_x * scale_factor, transformed_y * scale_factor, transformed_z * scale_factor]
                        else:
                            bone_pos = [0, 0, 0]
                    
                    frame_bone_positions[bone_name] = bone_pos
                
                # 为每个骨骼设置动画关键帧
                for bone_name, bone_pos in frame_bone_positions.items():
                    if bone_name in bone_nodes:
                        bone_node = bone_nodes[bone_name]
                        
                        # 创建位移动画曲线
                        curve_x = bone_node.LclTranslation.GetCurve(anim_layer, "X", True)
                        curve_y = bone_node.LclTranslation.GetCurve(anim_layer, "Y", True)
                        curve_z = bone_node.LclTranslation.GetCurve(anim_layer, "Z", True)
                        
                        if curve_x:
                            key_index = curve_x.KeyAdd(time)[0]
                            curve_x.KeySetValue(key_index, bone_pos[0])
                            curve_x.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
                        
                        if curve_y:
                            key_index = curve_y.KeyAdd(time)[0]
                            curve_y.KeySetValue(key_index, bone_pos[1])
                            curve_y.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
                        
                        if curve_z:
                            key_index = curve_z.KeyAdd(time)[0]
                            curve_z.KeySetValue(key_index, bone_pos[2])
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
    # pkl_file = r"e:\image_3d\text2dance\output\sample_video\pmce_output.pkl"
    # output_fbx = r"e:\image_3d\text2dance\output\sample_video\improved_human_model.fbx"

    pkl_file = r"e:\image_3d\text2dance\output\twodance\pmce_output.pkl"
    output_fbx = r"e:\image_3d\text2dance\output\twodance\improved_twohuman_model.fbx"

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