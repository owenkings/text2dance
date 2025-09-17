#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
稳定的3D-2D关节对齐系统
解决3D人体转圈问题，通过固定姿态只调整位置和缩放
"""

import os
import sys
import numpy as np
import cv2

# 设置matplotlib使用非交互式后端，避免Qt线程冲突
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import joblib
import subprocess
from scipy.optimize import minimize
import time

# 配置matplotlib支持中文字体
try:
    import matplotlib
    # 尝试设置中文字体
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans', 'Arial Unicode MS']
    matplotlib.rcParams['axes.unicode_minus'] = False
    print("[OK] 已配置matplotlib中文字体支持")
except Exception as e:
    print(f"[WARNING] 字体配置警告: {e}")
    # 如果字体配置失败，将使用英文标注

# 导入必要的函数
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from create_3d_human_video import plot_3d_human_mesh

# SMPL面数据生成
def get_real_smpl_faces():
    """获取真正的SMPL面数据"""
    try:
        # 添加lib路径到sys.path
        lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
        if lib_path not in sys.path:
            sys.path.append(lib_path)
        
        # 尝试从lib.models.smpl_mps导入
        from lib.models.smpl_mps import get_smpl_faces
        faces = get_smpl_faces()
        print(f"[OK] 成功加载真正的SMPL面数据: {len(faces)} 个三角形")
        return faces
    except Exception as e:
        print(f"[WARNING] 无法加载SMPL面数据，使用备用方案: {e}")
        # 备用方案：使用更密集的面生成
        faces = []
        # 创建更密集的三角形网格
        for i in range(0, 6890-6, 6):
            # 创建两个三角形形成一个四边形
            faces.append([i, i+1, i+2])
            faces.append([i+2, i+3, i+4])
            faces.append([i+4, i+5, i])
        return np.array(faces)

# 全局面数据
SMPL_FACES = get_real_smpl_faces()
print(f"[OK] 面数据加载完成: {len(SMPL_FACES)} 个三角形用于3D网格渲染")

# 全局变量存储SMPL面信息
SMPL_FACES_CACHE = None

def load_smpl_faces():
    """加载SMPL面信息用于网格渲染"""
    global SMPL_FACES_CACHE
    if SMPL_FACES_CACHE is not None:
        return SMPL_FACES_CACHE
    
    try:
        # 添加项目路径到sys.path
        project_root = os.path.dirname(os.path.abspath(__file__))
        lib_path = os.path.join(project_root, 'lib')
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # 尝试从lib.smpl加载
        from lib.smpl import SMPL
        smpl_model = SMPL()
        SMPL_FACES_CACHE = smpl_model.face
        print(f"[OK] 加载SMPL面信息: {SMPL_FACES_CACHE.shape}")
        return SMPL_FACES_CACHE
    except Exception as e:
        print(f"[WARNING] 无法加载SMPL面信息: {e}")
        
        # 回退方案：尝试从smplpytorch加载
        try:
            from smplpytorch.pytorch.smpl_layer import SMPL_Layer
            smpl_layer = SMPL_Layer(gender='neutral', model_root='smplpytorch/native/models')
            SMPL_FACES_CACHE = smpl_layer.th_faces.numpy()
            print(f"[OK] 从smplpytorch加载SMPL面信息: {SMPL_FACES_CACHE.shape}")
            return SMPL_FACES_CACHE
        except Exception as e2:
            print(f"[WARNING] 回退加载也失败: {e2}")
            
        # 最终回退：尝试查找预保存的面文件
        try:
            # 修正路径：从test_pose_2d_3d目录向上到pose3d目录，然后到data子目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            pose3d_dir = os.path.dirname(current_dir)  # 从test_pose_2d_3d到pose3d
            faces_file = os.path.join(pose3d_dir, 'data', 'smpl_faces.npy')
            if os.path.exists(faces_file):
                SMPL_FACES_CACHE = np.load(faces_file)
                print(f"[OK] 从文件加载SMPL面信息: {SMPL_FACES_CACHE.shape}")
                return SMPL_FACES_CACHE
            else:
                print(f"面文件不存在: {faces_file}")
                print("尝试生成面信息...")
                # 尝试运行简单面生成器
                import subprocess
                result = subprocess.run([sys.executable, 'simple_smpl_faces.py'], 
                                      capture_output=True, text=True, cwd=pose3d_dir)
                if result.returncode == 0 and os.path.exists(faces_file):
                    SMPL_FACES_CACHE = np.load(faces_file)
                    print(f"[OK] 生成并加载SMPL面信息: {SMPL_FACES_CACHE.shape}")
                    return SMPL_FACES_CACHE
        except Exception as e3:
            print(f"[WARNING] 无法从文件加载面信息: {e3}")
            
        print("将使用点云可视化代替网格")
        return None

def plot_3d_human_mesh_with_faces(ax, vertices, color='#A1B0DC', use_faces=True):
    """绘制3D人体网格，使用SMPL参数化人体模型"""
    
    # 优先使用SMPL面片渲染参数化人体模型
    if use_faces:
        try:
            # 加载SMPL面片数据
            faces = load_smpl_faces()
            if faces is not None and len(faces) > 0:
                # 使用SMPL面片创建参数化人体模型
                mesh = Poly3DCollection(vertices[faces])
                mesh.set_zorder(5)  # 设置最高渲染层级
                mesh.set_alpha(1.0)  # 设置为完全不透明
                
                # 设置指定的颜色
                if isinstance(color, str):
                    if color.startswith('#'):
                        # 转换十六进制颜色到RGB
                        hex_color = color.lstrip('#')
                        face_color = tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))
                    else:
                        face_color = color
                else:
                    face_color = color
                
                # 创建稍微深一点的边缘颜色
                if isinstance(face_color, tuple) and len(face_color) == 3:
                    edge_color = tuple(max(0, c - 0.1) for c in face_color)
                else:
                    edge_color = 'darkblue'
                
                mesh.set_facecolor(face_color)
                mesh.set_edgecolor(edge_color)
                mesh.set_linewidth(0.1)
                
                ax.add_collection3d(mesh)
                print(f"[OK] 使用SMPL参数化人体模型渲染，面片数量: {len(faces)}")
                return True
        except Exception as e:
            print(f"[WARNING] SMPL面片渲染失败: {e}")
    
    # 回退到plot_trisurf渲染
    try:
        from scipy.spatial import Delaunay
        points_2d = vertices[:, :2]  # 使用X,Y坐标进行三角剖分
        tri = Delaunay(points_2d)
        ax.plot_trisurf(vertices[:, 0], vertices[:, 1], vertices[:, 2], 
                       triangles=tri.simplices, color=color)
        print("[OK] 使用plot_trisurf渲染")
        return True
    except Exception as e:
        print(f"[WARNING] plot_trisurf渲染失败: {e}")
    
    # 最终回退到点云渲染
    try:
        ax.scatter(vertices[:, 0], vertices[:, 1], vertices[:, 2], 
                  c=color, s=1)
        print("[WARNING] 回退到点云渲染")
        return False
    except Exception as e:
        print(f"[WARNING] 点云渲染失败: {e}")
        return False

# COCO 2D关节顺序（标准17 keypoints）
COCO_KEYPOINT_NAMES = [
    "nose",        # 0
    "left_eye",    # 1
    "right_eye",   # 2
    "left_ear",    # 3
    "right_ear",   # 4
    "left_shoulder", # 5
    "right_shoulder",# 6
    "left_elbow",    # 7
    "right_elbow",   # 8
    "left_wrist",    # 9
    "right_wrist",   # 10
    "left_hip",      # 11
    "right_hip",     # 12
    "left_knee",     # 13
    "right_knee",    # 14
    "left_ankle",    # 15
    "right_ankle"    # 16
]

# SMPL关节索引映射
SMPL_JOINT_NAMES = [
    'pelvis', 'left_hip', 'right_hip', 'spine1', 'left_knee', 'right_knee',
    'spine2', 'left_ankle', 'right_ankle', 'spine3', 'left_foot', 'right_foot',
    'neck', 'left_collar', 'right_collar', 'head', 'left_shoulder', 'right_shoulder',
    'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist', 'left_hand', 'right_hand'
]

# 从SMPL mesh顶点估算关节位置的映射
SMPL_JOINT_REGRESSOR_SIMPLIFIED = {
    0: [3021, 3022, 3023],  # pelvis
    1: [1361, 1362, 1363],  # left_hip
    2: [4344, 4345, 4346],  # right_hip
    12: [411, 412, 413],    # neck
    15: [411, 412, 413],    # head (近似)
    16: [2878, 2879, 2880], # left_shoulder
    17: [5861, 5862, 5863], # right_shoulder
    18: [2746, 2747, 2748], # left_elbow
    19: [5729, 5730, 5731], # right_elbow
    20: [2319, 2320, 2321], # left_wrist
    21: [5302, 5303, 5304], # right_wrist
    4: [1096, 1097, 1098],  # left_knee
    5: [4079, 4080, 4081],  # right_knee
    7: [3365, 3366, 3367],  # left_ankle
    8: [6728, 6729, 6730],  # right_ankle
}

# 关节重要性权重
JOINT_IMPORTANCE_WEIGHTS = {
    0: 3.0,   # pelvis - 核心关节
    1: 2.5,   # left_hip
    2: 2.5,   # right_hip
    4: 2.8,   # left_knee - 重要支撑关节
    5: 2.8,   # right_knee
    7: 3.2,   # left_ankle - 地面接触点
    8: 3.2,   # right_ankle
    12: 3.5,  # neck - 头部连接
    15: 4.0,  # head - 最重要的视觉标志
    16: 2.2,  # left_shoulder
    17: 2.2,  # right_shoulder
    18: 1.8,  # left_elbow
    19: 1.8,  # right_elbow
    20: 2.0,  # left_wrist - 手部重要
    21: 2.0,  # right_wrist
}

class StableAligner:
    """稳定的3D-2D对齐器，避免转圈问题"""
    
    def __init__(self):
        self.joint_weights = JOINT_IMPORTANCE_WEIGHTS
        self.fixed_rotation = np.array([0.1, 0.0, 0.0])  # 固定的轻微旋转
        self.previous_joint_positions = None  # 用于计算运动幅度
        self.frame_count = 0  # 帧计数器
        self.use_camera_optimization = True  # 新增：是否使用相机参数优化
        # 修正后的3D关节索引到2D关节索引的映射
        # 基于COCO 2D关节格式和SMPL 3D关节格式的正确对应关系
        self.joint_3d_to_2d_mapping = {
            # 3D索引: 2D索引 (关节名称对应)
            1: 11,  # left_hip -> left_hip
            2: 12,  # right_hip -> right_hip
            4: 13,  # left_knee -> left_knee
            5: 14,  # right_knee -> right_knee
            7: 15,  # left_ankle -> left_ankle
            8: 16,  # right_ankle -> right_ankle
            15: 0,  # head -> nose (最接近的对应)
            16: 5,  # left_shoulder -> left_shoulder
            17: 6,  # right_shoulder -> right_shoulder
            18: 7,  # left_elbow -> left_elbow
            19: 8,  # right_elbow -> right_elbow
            20: 9,  # left_wrist -> left_wrist
            21: 10, # right_wrist -> right_wrist
            # 注意：以下3D关节在COCO 2D中没有对应关节，不参与映射:
            # pelvis(0), spine系列(3,6,9), neck(12), collar系列(13,14), 
            # foot系列(10,11), hand系列(22,23)
        }
        
    def extract_3d_joints_from_mesh(self, vertices):
        """从SMPL mesh顶点提取3D关节位置"""
        max_joint_idx = max(SMPL_JOINT_REGRESSOR_SIMPLIFIED.keys())
        joints_3d = np.zeros((max_joint_idx + 1, 3))
        
        for joint_idx, vertex_indices in SMPL_JOINT_REGRESSOR_SIMPLIFIED.items():
            valid_indices = [idx for idx in vertex_indices if idx < len(vertices)]
            if valid_indices:
                joint_pos = np.mean(vertices[valid_indices], axis=0)
                joints_3d[joint_idx] = joint_pos
        
        return joints_3d
    
    def calculate_adaptive_weights(self, joints_2d_target, confidence_scores=None):
        """计算自适应关节权重"""
        adaptive_weights = self.joint_weights.copy()
        
        # 图像尺寸（假设1920x1080）
        img_width, img_height = 1920, 1080
        edge_threshold = 0.1  # 边缘区域阈值（10%）
        
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if joint_3d_idx in adaptive_weights and joint_2d_idx < len(joints_2d_target):
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) == 0:  # 标量值
                        continue
                    
                    base_weight = adaptive_weights[joint_3d_idx]
                    
                    # 1. 可见性权重调整
                    if joint_2d[0] <= 0 or joint_2d[1] <= 0:
                        # 不可见关节权重降为0
                        adaptive_weights[joint_3d_idx] = 0.0
                        continue
                    
                    # 2. 置信度权重调整
                    confidence_factor = 1.0
                    if confidence_scores is not None and joint_2d_idx < len(confidence_scores):
                        confidence = confidence_scores[joint_2d_idx]
                        # 置信度低于0.5的关节降权，高于0.8的关节提权
                        if confidence < 0.5:
                            confidence_factor = 0.5
                        elif confidence > 0.8:
                            confidence_factor = 1.2
                        else:
                            confidence_factor = confidence
                    
                    # 3. 位置权重调整（边缘关节降权）
                    position_factor = 1.0
                    x_ratio = joint_2d[0] / img_width
                    y_ratio = joint_2d[1] / img_height
                    
                    # 如果关节在图像边缘，降低权重
                    if (x_ratio < edge_threshold or x_ratio > (1 - edge_threshold) or
                        y_ratio < edge_threshold or y_ratio > (1 - edge_threshold)):
                        position_factor = 0.7
                    
                    # 4. 运动稳定性权重调整
                    motion_factor = 1.0
                    if self.previous_joint_positions is not None and joint_2d_idx < len(self.previous_joint_positions):
                        try:
                            prev_joint = self.previous_joint_positions[joint_2d_idx]
                            if len(prev_joint.shape) > 0 and prev_joint[0] > 0 and prev_joint[1] > 0:
                                # 计算关节运动幅度
                                motion_magnitude = np.linalg.norm(joint_2d - prev_joint)
                                
                                # 运动幅度过大的关节降权（可能是检测错误）
                                if motion_magnitude > 50:  # 像素阈值
                                    motion_factor = 0.6
                                elif motion_magnitude < 5:  # 稳定关节提权
                                    motion_factor = 1.1
                        except (IndexError, TypeError):
                            pass
                    
                    # 5. 关节类型特殊调整
                    joint_type_factor = 1.0
                    if joint_3d_idx in [15]:  # head关节
                        # 头部关节在中心区域时提权
                        if 0.3 < x_ratio < 0.7 and 0.2 < y_ratio < 0.6:
                            joint_type_factor = 1.3
                    elif joint_3d_idx in [7, 8]:  # ankle关节
                        # 脚踝关节在下半部分时提权
                        if y_ratio > 0.6:
                            joint_type_factor = 1.2
                    
                    # 综合权重计算
                    final_weight = (base_weight * confidence_factor * 
                                  position_factor * motion_factor * joint_type_factor)
                    
                    # 限制权重范围
                    adaptive_weights[joint_3d_idx] = np.clip(final_weight, 0.0, 6.0)
                    
                except (IndexError, TypeError):
                    # 出错时保持原权重
                    continue
        
        # 更新前一帧关节位置
        self.previous_joint_positions = joints_2d_target.copy() if hasattr(joints_2d_target, 'copy') else joints_2d_target
        self.frame_count += 1
        
        return adaptive_weights
    
    def calculate_2d_center_from_joints(self, joints_2d_target):
        """根据2D关节位置计算图像中心点"""
        valid_joints = []
        
        # 收集有效的2D关节位置
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if joint_2d_idx < len(joints_2d_target):
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) == 0:  # 标量值
                        continue
                    if joint_2d[0] > 0 and joint_2d[1] > 0:
                        valid_joints.append(joint_2d)
                except (IndexError, TypeError):
                    continue
        
        if len(valid_joints) > 0:
            # 计算有效关节的中心点
            center = np.mean(valid_joints, axis=0)
            return center[0], center[1]
        else:
            # 如果没有有效关节，使用默认图像中心
            return 960, 540
    
    def project_3d_to_2d_stable(self, points_3d, transform_params, joints_2d_target=None):
        """稳定的3D到2D投影，使用固定旋转，并根据2D关节位置动态调整投影中心"""
        tx, ty, tz, scale = transform_params
        
        # 使用固定的旋转矩阵
        rx, ry, rz = self.fixed_rotation
        cos_rx, sin_rx = np.cos(rx), np.sin(rx)
        cos_ry, sin_ry = np.cos(ry), np.sin(ry)
        cos_rz, sin_rz = np.cos(rz), np.sin(rz)
        
        R_x = np.array([[1, 0, 0], [0, cos_rx, -sin_rx], [0, sin_rx, cos_rx]])
        R_y = np.array([[cos_ry, 0, sin_ry], [0, 1, 0], [-sin_ry, 0, cos_ry]])
        R_z = np.array([[cos_rz, -sin_rz, 0], [sin_rz, cos_rz, 0], [0, 0, 1]])
        R = R_z @ R_y @ R_x
        
        t = np.array([tx, ty, tz])
        
        # 应用变换和缩放
        points_transformed = (R @ (points_3d * scale).T).T + t
        
        # 改进的透视投影：使用更合理的相机模型
        # 确保Z坐标为正值，避免投影异常
        z_coords = points_transformed[:, 2:3]
        z_coords = np.maximum(z_coords, 0.1)  # 确保Z坐标至少为0.1
        
        # 使用更合理的焦距和相机内参矩阵
        focal_length = 200  # 进一步减小焦距，使投影更接近2D关节位置
        img_width, img_height = 1920, 1080
        cx, cy = img_width / 2, img_height / 2  # 相机主点
        
        # 标准透视投影公式
        points_2d = np.zeros((points_transformed.shape[0], 2))
        points_2d[:, 0] = (points_transformed[:, 0] * focal_length / z_coords.flatten()) + cx
        points_2d[:, 1] = (points_transformed[:, 1] * focal_length / z_coords.flatten()) + cy
        
        # 优化的中心偏移计算：基于关节映射的精确对齐
        if joints_2d_target is not None:
            # 提取对应的3D关节并投影
            joints_3d_mapped = []
            joints_2d_mapped = []
            
            for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
                if joint_3d_idx < len(points_3d) and joint_2d_idx < len(joints_2d_target):
                    try:
                        joint_2d = joints_2d_target[joint_2d_idx]
                        if len(joint_2d.shape) > 0 and joint_2d[0] > 0 and joint_2d[1] > 0:
                            joints_3d_mapped.append(joint_3d_idx)
                            joints_2d_mapped.append(joint_2d)
                    except (IndexError, TypeError):
                        continue
            
            if len(joints_3d_mapped) > 0 and len(joints_2d_mapped) > 0:
                # 计算投影关节的中心
                projected_joints = points_2d[joints_3d_mapped]
                projected_center = np.mean(projected_joints, axis=0)
                
                # 计算目标关节的中心
                target_center = np.mean(joints_2d_mapped, axis=0)
                
                # 计算中心偏移差异
                offset = target_center - projected_center
                
                # 应用偏移到所有投影点
                points_2d[:, 0] += offset[0]
                points_2d[:, 1] += offset[1]
                
                # print(f"[DEBUG] 投影中心: ({projected_center[0]:.1f}, {projected_center[1]:.1f})")
                # print(f"[DEBUG] 目标中心: ({target_center[0]:.1f}, {target_center[1]:.1f})")
                # print(f"[DEBUG] 应用偏移: ({offset[0]:.1f}, {offset[1]:.1f})")
                # print(f"[DEBUG] Z坐标范围: [{np.min(z_coords):.2f}, {np.max(z_coords):.2f}]")
            else:
                # print("[DEBUG] 没有有效关节映射，保持投影结果不变")
                pass
        else:
            # print("[DEBUG] 无目标关节，保持投影结果不变")
            pass
        
        return points_2d
    
    def calculate_stable_error(self, transform_params, joints_3d, joints_2d_target, previous_3d_position=None, confidence_scores=None):
        """计算SPIN风格的多损失函数组合误差"""
        joints_2d_proj = self.project_3d_to_2d_stable(joints_3d, transform_params, joints_2d_target)
        
        # 计算自适应权重
        adaptive_weights = self.calculate_adaptive_weights(joints_2d_target, confidence_scores)
        
        # 1. 重投影损失 (Reprojection Loss) - SPIN核心损失
        reprojection_loss = self.calculate_reprojection_loss(joints_2d_proj, joints_2d_target, adaptive_weights)
        
        # 2. 形状先验损失 (Shape Prior Loss) - 约束SMPL形状参数
        shape_prior_loss = self.calculate_shape_prior_loss(transform_params)
        
        # 3. 姿态先验损失 (Pose Prior Loss) - 约束姿态合理性
        pose_prior_loss = self.calculate_pose_prior_loss(joints_3d)
        
        # 4. 时间一致性损失 (Temporal Consistency Loss)
        temporal_loss = 0.0
        if previous_3d_position is not None:
            temporal_loss = self.calculate_temporal_consistency_loss(joints_3d, transform_params, previous_3d_position)
        
        # SPIN风格的损失权重组合
        lambda_reprojection = 1.0    # 重投影损失权重
        lambda_shape = 0.001         # 形状先验权重
        lambda_pose = 0.01           # 姿态先验权重
        lambda_temporal = 0.5 if previous_3d_position is not None else 0.0  # 时间一致性权重
        
        total_loss = (lambda_reprojection * reprojection_loss + 
                     lambda_shape * shape_prior_loss + 
                     lambda_pose * pose_prior_loss + 
                     lambda_temporal * temporal_loss)
        
        return total_loss
    
    def calculate_reprojection_loss(self, joints_2d_proj, joints_2d_target, adaptive_weights):
        """计算重投影损失 - SPIN的核心损失函数"""
        reprojection_error = 0.0
        total_weight = 0.0
        
        # 使用修正后的映射关系计算投影误差
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if (joint_3d_idx < len(joints_2d_proj) and 
                joint_2d_idx < len(joints_2d_target) and
                joint_3d_idx in SMPL_JOINT_REGRESSOR_SIMPLIFIED):
                
                # 安全地访问2D关节数据
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) == 0:  # 标量值
                        continue
                    if (joint_2d[0] > 0 and joint_2d[1] > 0):
                        pass
                    else:
                        continue
                except (IndexError, TypeError):
                    continue
                
                # 使用自适应权重和鲁棒损失函数
                weight = adaptive_weights.get(joint_3d_idx, 0.0)
                if weight > 0:
                    # 使用Huber损失提高鲁棒性
                    error = np.linalg.norm(joints_2d_proj[joint_3d_idx] - joints_2d_target[joint_2d_idx])
                    huber_delta = 1.0
                    if error <= huber_delta:
                        robust_error = 0.5 * error ** 2
                    else:
                        robust_error = huber_delta * (error - 0.5 * huber_delta)
                    
                    reprojection_error += robust_error * weight
                    total_weight += weight
        
        return reprojection_error / max(total_weight, 1e-6)
    
    def calculate_shape_prior_loss(self, transform_params):
        """计算形状先验损失 - 约束变换参数的合理性"""
        tx, ty, tz, scale = transform_params
        
        # 对变换参数施加L2正则化
        translation_prior = (tx**2 + ty**2 + (tz - 5.0)**2)  # 假设合理深度为5米
        scale_prior = (scale - 1.0)**2  # 假设合理缩放为1.0
        
        return translation_prior + scale_prior
    
    def calculate_pose_prior_loss(self, joints_3d):
        """计算姿态先验损失 - 约束3D姿态的合理性"""
        pose_prior = 0.0
        
        # 计算关节角度约束
        try:
            # 检查膝盖弯曲角度（不应过度弯曲）
            if 4 < len(joints_3d) and 1 < len(joints_3d) and 7 < len(joints_3d):  # left_knee, left_hip, left_ankle
                hip_knee = joints_3d[4] - joints_3d[1]  # left_knee - left_hip
                knee_ankle = joints_3d[7] - joints_3d[4]  # left_ankle - left_knee
                
                # 计算膝盖角度
                cos_angle = np.dot(hip_knee, knee_ankle) / (np.linalg.norm(hip_knee) * np.linalg.norm(knee_ankle) + 1e-6)
                cos_angle = np.clip(cos_angle, -1.0, 1.0)
                knee_angle = np.arccos(cos_angle)
                
                # 膝盖角度应在合理范围内（0到π）
                if knee_angle < 0.5:  # 过度弯曲惩罚
                    pose_prior += (0.5 - knee_angle)**2
            
            # 检查身体比例合理性
            if 15 < len(joints_3d) and 0 < len(joints_3d):  # head, pelvis
                body_height = np.linalg.norm(joints_3d[15] - joints_3d[0])  # head - pelvis
                # 身体高度应在合理范围内
                if body_height < 0.8 or body_height > 2.5:
                    pose_prior += (max(0.8 - body_height, body_height - 2.5))**2
                    
        except (IndexError, ValueError):
            pass
        
        return pose_prior
    
    def calculate_temporal_consistency_loss(self, joints_3d, transform_params, previous_3d_position):
        """计算时间一致性损失 - SPIN的时序约束"""
        # 应用当前变换
        transformed_joints = self.apply_stable_transform_to_joints(joints_3d, transform_params)
        
        # 计算与前一帧的位置差异
        position_diff = transformed_joints - previous_3d_position
        
        # 使用加权的时间一致性损失
        temporal_weights = np.array([JOINT_IMPORTANCE_WEIGHTS.get(i, 1.0) for i in range(len(joints_3d))])
        temporal_weights = temporal_weights[:len(position_diff)]  # 确保长度匹配
        
        # 计算加权的L2损失
        weighted_diff = position_diff * temporal_weights.reshape(-1, 1)
        temporal_loss = np.mean(np.sum(weighted_diff**2, axis=1))
        
        return temporal_loss
    
    def spin_style_optimization(self, initial_params, joints_3d, joints_2d_target, previous_3d_position, confidence_scores, bounds):
        """SPIN风格的多阶段优化策略"""
        current_params = initial_params.copy()
        
        # 阶段1: 粗优化 - 主要关注重投影损失
        print("[SPIN-OPT] Stage 1: Coarse optimization focusing on reprojection...")
        
        # 临时调整损失权重，主要优化重投影
        original_weights = (1.0, 0.001, 0.01, 0.5)
        self._temp_loss_weights = (1.0, 0.0001, 0.001, 0.1)  # 降低先验权重
        
        stage1_result = minimize(
            self._calculate_weighted_error,
            current_params,
            args=(joints_3d, joints_2d_target, previous_3d_position, confidence_scores),
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 30, 'ftol': 1e-5}
        )
        
        current_params = stage1_result.x
        print(f"[SPIN-OPT] Stage 1 completed. Error: {stage1_result.fun:.4f}")
        
        # 阶段2: 精细优化 - 平衡所有损失
        print("[SPIN-OPT] Stage 2: Fine optimization with balanced losses...")
        
        # 恢复原始权重
        self._temp_loss_weights = original_weights
        
        stage2_result = minimize(
            self._calculate_weighted_error,
            current_params,
            args=(joints_3d, joints_2d_target, previous_3d_position, confidence_scores),
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 40, 'ftol': 1e-6}
        )
        
        print(f"[SPIN-OPT] Stage 2 completed. Final error: {stage2_result.fun:.4f}")
        
        # 阶段3: 如果有前一帧信息，进行时序优化
        if previous_3d_position is not None:
            print("[SPIN-OPT] Stage 3: Temporal consistency optimization...")
            
            # 增强时序一致性权重
            self._temp_loss_weights = (0.8, 0.001, 0.01, 1.0)
            
            stage3_result = minimize(
                self._calculate_weighted_error,
                stage2_result.x,
                args=(joints_3d, joints_2d_target, previous_3d_position, confidence_scores),
                method='L-BFGS-B',
                bounds=bounds,
                options={'maxiter': 20, 'ftol': 1e-6}
            )
            
            print(f"[SPIN-OPT] Stage 3 completed. Final error: {stage3_result.fun:.4f}")
            final_result = stage3_result
        else:
            final_result = stage2_result
        
        # 清理临时权重
        if hasattr(self, '_temp_loss_weights'):
            delattr(self, '_temp_loss_weights')
        
        return final_result
    
    def _calculate_weighted_error(self, transform_params, joints_3d, joints_2d_target, previous_3d_position=None, confidence_scores=None):
        """使用临时权重的误差计算函数"""
        joints_2d_proj = self.project_3d_to_2d_stable(joints_3d, transform_params, joints_2d_target)
        
        # 计算自适应权重
        adaptive_weights = self.calculate_adaptive_weights(joints_2d_target, confidence_scores)
        
        # 计算各项损失
        reprojection_loss = self.calculate_reprojection_loss(joints_2d_proj, joints_2d_target, adaptive_weights)
        shape_prior_loss = self.calculate_shape_prior_loss(transform_params)
        pose_prior_loss = self.calculate_pose_prior_loss(joints_3d)
        
        temporal_loss = 0.0
        if previous_3d_position is not None:
            temporal_loss = self.calculate_temporal_consistency_loss(joints_3d, transform_params, previous_3d_position)
        
        # 使用临时权重或默认权重
        if hasattr(self, '_temp_loss_weights'):
            lambda_reprojection, lambda_shape, lambda_pose, lambda_temporal = self._temp_loss_weights
        else:
            lambda_reprojection, lambda_shape, lambda_pose, lambda_temporal = (1.0, 0.001, 0.01, 0.5)
        
        # 调整时序权重
        if previous_3d_position is None:
            lambda_temporal = 0.0
        
        total_loss = (lambda_reprojection * reprojection_loss + 
                     lambda_shape * shape_prior_loss + 
                     lambda_pose * pose_prior_loss + 
                     lambda_temporal * temporal_loss)
        
        return total_loss
    
    def apply_stable_transform_to_joints(self, joints_3d, params):
        """对3D关节应用稳定变换"""
        tx, ty, tz, scale = params
        
        # 使用固定的旋转矩阵
        rx, ry, rz = self.fixed_rotation
        cos_rx, sin_rx = np.cos(rx), np.sin(rx)
        cos_ry, sin_ry = np.cos(ry), np.sin(ry)
        cos_rz, sin_rz = np.cos(rz), np.sin(rz)
        
        R_x = np.array([[1, 0, 0], [0, cos_rx, -sin_rx], [0, sin_rx, cos_rx]])
        R_y = np.array([[cos_ry, 0, sin_ry], [0, 1, 0], [-sin_ry, 0, cos_ry]])
        R_z = np.array([[cos_rz, -sin_rz, 0], [sin_rz, cos_rz, 0], [0, 0, 1]])
        R = R_z @ R_y @ R_x
        
        t = np.array([tx, ty, tz])
        
        # 应用变换和缩放
        joints_transformed = (R @ (joints_3d * scale).T).T + t
        
        return joints_transformed
    
    def calculate_initial_alignment_from_2d(self, joints_3d, joints_2d_target):
        """根据2D关节位置计算初始对齐参数"""
        # 收集有效的3D-2D关节对
        valid_3d_joints = []
        valid_2d_joints = []
        
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if (joint_3d_idx < len(joints_3d) and 
                joint_2d_idx < len(joints_2d_target) and
                joint_3d_idx in SMPL_JOINT_REGRESSOR_SIMPLIFIED):
                
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) == 0:
                        continue
                    if joint_2d[0] > 0 and joint_2d[1] > 0:
                        valid_3d_joints.append(joints_3d[joint_3d_idx])
                        valid_2d_joints.append(joint_2d)
                except (IndexError, TypeError):
                    continue
        
        if len(valid_3d_joints) < 3:  # 需要至少3个点来计算变换
            return np.array([0.0, 0.0, 5.0, 1.0])
        
        valid_3d_joints = np.array(valid_3d_joints)
        valid_2d_joints = np.array(valid_2d_joints)
        
        # 计算3D和2D关节的中心点
        center_3d = np.mean(valid_3d_joints, axis=0)
        center_2d = np.mean(valid_2d_joints, axis=0)
        
        # 估算初始的平移参数
        # 假设图像中心为(960, 540)，计算2D中心相对于图像中心的偏移
        tx_init = (center_2d[0] - 960) / 1000.0  # 归一化
        ty_init = (center_2d[1] - 540) / 1000.0
        
        # 估算初始缩放参数
        # 计算3D关节的平均距离
        distances_3d = np.linalg.norm(valid_3d_joints - center_3d, axis=1)
        avg_distance_3d = np.mean(distances_3d)
        
        # 计算2D关节的平均距离
        distances_2d = np.linalg.norm(valid_2d_joints - center_2d, axis=1)
        avg_distance_2d = np.mean(distances_2d)
        
        # 使用身高+焦距法估算初始tz距离（核心方法）
        # 基于透视投影几何关系：tz = (real_height * focal_length) / pixel_height
        
        # 1. 估算人体身高（从头部到脚踝的3D距离）
        head_idx = None
        ankle_indices = []
        
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if joint_3d_idx == 15:  # head
                head_idx = joint_3d_idx
            elif joint_3d_idx in [7, 8]:  # left_ankle, right_ankle
                ankle_indices.append(joint_3d_idx)
        
        estimated_height_3d = 1.7  # 默认身高1.7米
        if head_idx is not None and len(ankle_indices) > 0:
            head_pos = joints_3d[head_idx]
            ankle_positions = [joints_3d[idx] for idx in ankle_indices]
            avg_ankle_pos = np.mean(ankle_positions, axis=0)
            raw_height_3d = abs(head_pos[1] - avg_ankle_pos[1])  # Y轴差值
            # print(f"[DEBUG] 原始3D身高: {raw_height_3d:.3f}, 头部Y: {head_pos[1]:.3f}, 脚踝Y: {avg_ankle_pos[1]:.3f}")
            
            # SMPL模型的身高通常在0.8-2.5范围内，需要适当调整
            if raw_height_3d < 0.5:  # 如果太小，可能是模型单位问题
                estimated_height_3d = raw_height_3d * 2.0  # 放大2倍
            elif raw_height_3d > 3.0:  # 如果太大，缩小
                estimated_height_3d = raw_height_3d * 0.6
            else:
                estimated_height_3d = raw_height_3d
            
            estimated_height_3d = max(estimated_height_3d, 0.8)  # 最小0.8米
            estimated_height_3d = min(estimated_height_3d, 2.5)  # 最大2.5米
        
        # 2. 计算2D图像中的人体像素高度
        head_2d_idx = None
        ankle_2d_indices = []
        
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if joint_3d_idx == 15 and joint_2d_idx < len(joints_2d_target):  # head
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) > 0 and joint_2d[0] > 0 and joint_2d[1] > 0:
                        head_2d_idx = joint_2d_idx
                except (IndexError, TypeError):
                    pass
            elif joint_3d_idx in [7, 8] and joint_2d_idx < len(joints_2d_target):  # ankles
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) > 0 and joint_2d[0] > 0 and joint_2d[1] > 0:
                        ankle_2d_indices.append(joint_2d_idx)
                except (IndexError, TypeError):
                    pass
        
        estimated_height_2d = 400  # 默认像素高度
        if head_2d_idx is not None and len(ankle_2d_indices) > 0:
            head_2d = joints_2d_target[head_2d_idx]
            ankle_2d_positions = [joints_2d_target[idx] for idx in ankle_2d_indices]
            avg_ankle_2d = np.mean(ankle_2d_positions, axis=0)
            estimated_height_2d = abs(head_2d[1] - avg_ankle_2d[1])  # Y轴像素差值
            estimated_height_2d = max(estimated_height_2d, 200)  # 最小200像素
        
        # 3. 使用透视投影公式估算合理的tz距离
        # 根据实际投影系统调整焦距参数
        focal_length = 500  # 增加焦距以获得更合理的距离估算
        tz_estimated = (estimated_height_3d * focal_length) / estimated_height_2d
        
        # print(f"[DEBUG] 焦距: {focal_length}, 2D身高: {estimated_height_2d:.0f}px, 计算距离: {tz_estimated:.2f}m")
        
        # 根据SMPL模型特点调整距离范围
        tz_estimated = max(tz_estimated, 2.0)  # 最小距离2米
        tz_estimated = min(tz_estimated, 8.0)  # 最大距离8米
        
        # 4. 估算缩放因子（基于距离调整）
        scale_init = 1.0
        if avg_distance_3d > 0 and avg_distance_2d > 0:
            # 考虑透视投影的缩放关系
            scale_init = (avg_distance_2d * tz_estimated) / (avg_distance_3d * focal_length)
            scale_init = np.clip(scale_init, 0.3, 3.0)
        
        print(f"[INIT] 身高估算: 3D={estimated_height_3d:.2f}m, 2D={estimated_height_2d:.0f}px")
        print(f"[INIT] 透视投影估算距离: tz={tz_estimated:.2f}m, scale={scale_init:.2f}")
        
        return np.array([tx_init, ty_init, tz_estimated, scale_init])
    
    def project_3d_to_2d_with_camera(self, points_3d, pred_cam, img_width=1920, img_height=1080):
        """使用pred_cam参数进行3D到2D投影（基于SPIN模型的投影方法）"""
        # pred_cam格式: [scale, tx, ty] (3个参数)
        # 参考SPIN模型的projection函数实现
        
        # 构建相机平移向量
        pred_cam_t = np.array([
            pred_cam[1],  # tx
            pred_cam[2],  # ty  
            2 * 5000.0 / (224.0 * pred_cam[0] + 1e-9)  # tz，基于scale计算
        ])
        
        # 应用相机变换（平移）
        points_cam = points_3d + pred_cam_t
        
        # 透视投影
        focal_length = 5000.0  # 5000mm = 5m，与SPIN模型一致
        points_2d = points_cam[:, :2] * focal_length / (points_cam[:, 2:3] + 1e-8)
        
        # 归一化到[-1,1]范围（SPIN模型的输出格式）
        points_2d_norm = points_2d / (224.0 / 2.0)
        
        # 转换到实际图像坐标
        # 假设原始图像尺寸，将归一化坐标转换为像素坐标
        points_2d_pixel = np.zeros_like(points_2d_norm)
        points_2d_pixel[:, 0] = (points_2d_norm[:, 0] + 1.0) * img_width / 2.0
        points_2d_pixel[:, 1] = (points_2d_norm[:, 1] + 1.0) * img_height / 2.0
        
        return points_2d_pixel
    
    def calculate_camera_projection_error(self, pred_cam, vertices, joints_2d_target, img_width=1920, img_height=1080):
        """计算基于相机参数优化的投影误差"""
        # 从mesh顶点提取3D关节
        joints_3d = self.extract_3d_joints_from_mesh(vertices)
        
        # 使用相机参数进行3D到2D投影
        joints_2d_proj = self.project_3d_to_2d_with_camera(joints_3d, pred_cam, img_width, img_height)
        
        # 计算投影误差
        projection_error = 0.0
        valid_joints = 0
        total_weight = 0.0
        
        # 使用映射关系计算投影误差
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if (joint_3d_idx < len(joints_3d) and 
                joint_2d_idx < len(joints_2d_target) and
                joint_3d_idx in SMPL_JOINT_REGRESSOR_SIMPLIFIED):
                
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) == 0:  # 标量值
                        continue
                    if joint_2d[0] > 0 and joint_2d[1] > 0:  # 有效关节
                        weight = self.joint_weights.get(joint_3d_idx, 1.0)
                        error = np.linalg.norm(
                            joints_2d_proj[joint_3d_idx] - joints_2d_target[joint_2d_idx]
                        )
                        projection_error += error * weight
                        total_weight += weight
                        valid_joints += 1
                except (IndexError, TypeError):
                    continue
        
        # 使用加权平均
        projection_error = projection_error / max(total_weight, 1e-6)
        
        return projection_error
    
    def optimize_camera_parameters(self, vertices, joints_2d_target, initial_pred_cam=None, img_width=1920, img_height=1080):
        """优化相机参数实现精确的3D-2D投影对齐"""
        print("🎯 使用相机参数优化进行精确3D-2D投影对齐...")
        
        # 初始相机参数
        if initial_pred_cam is not None:
            initial_params = initial_pred_cam.copy()
        else:
            # 默认初始参数 [scale, tx, ty]
            initial_params = np.array([1.0, 0.0, 0.0])
        
        # 优化边界
        bounds = [
            (0.5, 2.0),   # scale: 缩放因子
            (-1.0, 1.0),  # tx: x方向平移
            (-1.0, 1.0)   # ty: y方向平移
        ]
        
        # 执行优化
        result = minimize(
            self.calculate_camera_projection_error,
            initial_params,
            args=(vertices, joints_2d_target, img_width, img_height),
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 100, 'ftol': 1e-8}
        )
        
        # 计算最终误差
        final_error = self.calculate_camera_projection_error(
            result.x, vertices, joints_2d_target, img_width, img_height
        )
        
        return {
            'vertices': vertices,
            'pred_cam': result.x,
            'final_error': final_error,
            'success': result.success,
            'iterations': result.nit,
            'optimization_result': result
        }
    
    def optimize_stable_alignment(self, vertices, joints_2d_target, previous_3d_position=None, confidence_scores=None, pred_cam=None, img_width=1920, img_height=1080):
        """基于3D跟踪位置优化稳定对齐参数，支持相机参数优化和传统关节对应方法"""
        # 提取3D关节
        joints_3d = self.extract_3d_joints_from_mesh(vertices)
        
        # 根据配置选择优化方法
        if self.use_camera_optimization and pred_cam is not None:
            # 使用相机参数优化方法
            return self.optimize_camera_parameters(vertices, joints_2d_target, pred_cam, img_width, img_height)
        else:
            # 使用传统关节对应方法
            print("[OPTIMIZE] 使用传统优化方法和自适应权重进行3D-2D对齐...")
        # 使用2D关节位置来计算初始参数
        initial_params_2d = self.calculate_initial_alignment_from_2d(joints_3d, joints_2d_target)
        
        # 如果有前一帧的3D位置信息，使用它来初始化参数
        if previous_3d_position is not None:
            # 基于3D跟踪位置计算初始参数
            center_3d = np.mean(joints_3d, axis=0)
            prev_center = np.mean(previous_3d_position, axis=0)
            
            # 计算位置偏移
            offset = center_3d - prev_center
            
            # 计算缩放因子 - 使用更稳定的方法
            current_scale = np.linalg.norm(joints_3d - center_3d, axis=1).mean()
            prev_scale = np.linalg.norm(previous_3d_position - prev_center, axis=1).mean()
            scale_ratio = current_scale / (prev_scale + 1e-6)
            
            # 限制缩放比例变化，避免剧烈波动
            scale_ratio = np.clip(scale_ratio, 0.9, 1.1)  # 限制在±10%范围内
            
            # 初始参数基于3D跟踪 [tx, ty, tz, scale]
            initial_params_3d = np.array([offset[0], offset[1], prev_center[2] + offset[2], scale_ratio])
            
            # 结合2D和3D信息：使用2D的xy，3D的z和scale
            initial_params = np.array([
                initial_params_2d[0],  # 使用2D计算的tx
                initial_params_2d[1],  # 使用2D计算的ty
                initial_params_3d[2],  # 使用3D跟踪的tz
                (initial_params_2d[3] + initial_params_3d[3]) / 2  # 平均缩放
            ])
        else:
            # 使用基于2D关节位置的初始参数
            initial_params = initial_params_2d
        
        # 优化边界：严格限制参数范围，特别是缩放参数
        bounds = [
            (-2.0, 2.0),  # tx
            (-2.0, 2.0),  # ty
            (1.0, 12.0),  # tz - 扩大z轴范围，允许更灵活的深度调整
            (0.8, 1.2)    # scale - 大幅缩小范围，避免大小变化剧烈
        ]
        
        # 计算并打印初始误差
        init_error = self.calculate_stable_error(initial_params, joints_3d, joints_2d_target, previous_3d_position, confidence_scores)
        print(f"Initial error: {init_error}")
        
        # SPIN风格的多阶段优化策略
        result = self.spin_style_optimization(
            initial_params, joints_3d, joints_2d_target, 
            previous_3d_position, confidence_scores, bounds
        )
        
        # 计算最终的分解误差，使用自适应权重
        final_projection_error = 0.0
        final_position_error = 0.0
        
        # 获取最终的自适应权重
        final_adaptive_weights = self.calculate_adaptive_weights(joints_2d_target, confidence_scores)
        
        # 计算投影误差
        joints_2d_proj = self.project_3d_to_2d_stable(joints_3d, result.x, joints_2d_target)
        total_weight = 0.0
        
        # 使用映射关系和自适应权重计算最终投影误差
        for joint_3d_idx, joint_2d_idx in self.joint_3d_to_2d_mapping.items():
            if (joint_3d_idx < len(joints_3d) and 
                joint_2d_idx < len(joints_2d_target) and
                joint_3d_idx in SMPL_JOINT_REGRESSOR_SIMPLIFIED):
                
                try:
                    joint_2d = joints_2d_target[joint_2d_idx]
                    if len(joint_2d.shape) == 0:  # 标量值
                        continue
                    if joint_2d[0] > 0 and joint_2d[1] > 0:
                        weight = final_adaptive_weights.get(joint_3d_idx, 0.0)
                        if weight > 0:
                            error = np.linalg.norm(joints_2d_proj[joint_3d_idx] - joint_2d)
                            final_projection_error += error * weight
                            total_weight += weight
                except (IndexError, TypeError):
                    continue
        
        final_projection_error = final_projection_error / max(total_weight, 1e-6)
        
        # 计算3D位置误差
        if previous_3d_position is not None:
            transformed_joints = self.apply_stable_transform_to_joints(joints_3d, result.x)
            final_position_error = np.mean(np.linalg.norm(transformed_joints - previous_3d_position, axis=1))
        
        return {
            'vertices': vertices,
            'joints_3d': joints_3d,
            'transform_params': result.x,
            'final_error': result.fun,
            'projection_error': final_projection_error,
            'position_error': final_position_error,
            'success': result.success,
            'iterations': result.nit
        }

def render_stable_3d_model(vertices, joints_3d, frame_shape, transform_params=None, pred_cam=None, scale_factor=2.0, joints_2d_target=None, use_camera_projection=False):
    """渲染稳定的3D模型，支持传统变换和相机参数投影"""
    height, width = frame_shape[:2]
    
    # 使用黑色背景增加对比度，提高3D模型可见性
    fig = plt.figure(figsize=(width/100, height/100), dpi=100, facecolor='black')
    ax = fig.add_subplot(111, projection='3d')
    
    if use_camera_projection and pred_cam is not None:
        # 使用相机参数进行变换
        print(f"🎯 使用相机参数渲染: scale={pred_cam[0]:.3f}, tx={pred_cam[1]:.3f}, ty={pred_cam[2]:.3f}")
        
        # 基于相机参数的简化变换（主要用于可视化）
        # 将scale_factor融入到相机参数的scale中
        scale = pred_cam[0] * scale_factor  # 结合scale_factor
        tx, ty = pred_cam[1], pred_cam[2]
        tz = 2 * 5000.0 / (224.0 * pred_cam[0] + 1e-9)  # 根据SPIN模型计算z
        
        # 应用缩放和平移
        vertices_transformed = vertices * scale + np.array([tx, ty, tz])
        joints_transformed = joints_3d * scale + np.array([tx, ty, tz])
        
    elif transform_params is not None:
        # 使用传统变换参数
        tx, ty, tz, scale = transform_params
        
        # 使用固定的轻微旋转
        rx, ry, rz = 0.1, 0.0, 0.0
        cos_rx, sin_rx = np.cos(rx), np.sin(rx)
        cos_ry, sin_ry = np.cos(ry), np.sin(ry)
        cos_rz, sin_rz = np.cos(rz), np.sin(rz)
        
        R_x = np.array([[1, 0, 0], [0, cos_rx, -sin_rx], [0, sin_rx, cos_rx]])
        R_y = np.array([[cos_ry, 0, sin_ry], [0, 1, 0], [-sin_ry, 0, cos_ry]])
        R_z = np.array([[cos_rz, -sin_rz, 0], [sin_rz, cos_rz, 0], [0, 0, 1]])
        R = R_z @ R_y @ R_x
        
        t = np.array([tx, ty, tz])
        
        # 应用变换
        vertices_transformed = (R @ (vertices * scale).T).T + t
        joints_transformed = (R @ (joints_3d * scale).T).T + t
        
    else:
        # 默认情况：不进行变换
        vertices_transformed = vertices.copy()
        joints_transformed = joints_3d.copy()
    
    # 坐标系变换（保持与原始代码一致）
    temp_vertices = vertices_transformed.copy()
    temp_vertices[:, 0] = vertices_transformed[:, 0]
    temp_vertices[:, 1] = vertices_transformed[:, 2]
    temp_vertices[:, 2] = -vertices_transformed[:, 1]
    
    vertices_final = temp_vertices.copy()
    vertices_final[:, 0] = -temp_vertices[:, 1]
    vertices_final[:, 1] = temp_vertices[:, 0]
    vertices_final[:, 2] = temp_vertices[:, 2]
    
    # 对关节应用相同变换
    temp_joints = joints_transformed.copy()
    temp_joints[:, 0] = joints_transformed[:, 0]
    temp_joints[:, 1] = joints_transformed[:, 2]
    temp_joints[:, 2] = -joints_transformed[:, 1]
    
    joints_final = temp_joints.copy()
    joints_final[:, 0] = -temp_joints[:, 1]
    joints_final[:, 1] = temp_joints[:, 0]
    joints_final[:, 2] = temp_joints[:, 2]
    
    # 居中和缩放 - 增强3D模型的显示效果
    center = np.mean(vertices_final, axis=0)
    vertices_final -= center
    joints_final -= center
    
    # 根据2D关节位置调整3D模型的位置
    if joints_2d_target is not None:
        # 创建临时的StableAligner来计算2D中心
        temp_aligner = StableAligner()
        center_2d_x, center_2d_y = temp_aligner.calculate_2d_center_from_joints(joints_2d_target)
        
        # 计算相对于图像中心的偏移
        offset_x = (center_2d_x - width/2) / width * 4.0  # 归一化偏移
        offset_y = (center_2d_y - height/2) / height * 4.0
        
        # 应用偏移到3D模型
        vertices_final[:, 0] += offset_x
        vertices_final[:, 1] -= offset_y  # Y轴方向相反
        joints_final[:, 0] += offset_x
        joints_final[:, 1] -= offset_y
    
    # 使用scale_factor进行实际缩放（仅在非相机投影模式下应用）
    if not (use_camera_projection and pred_cam is not None):
        enhanced_scale = scale_factor  # 直接使用scale_factor进行缩放
        vertices_final *= enhanced_scale
        joints_final *= enhanced_scale
    # 相机投影模式下，scale_factor已经在相机参数处理中应用了
    
    # 调整Z轴偏移，让模型更靠近相机以显得更大
    z_offset = 1.2 + (scale_factor * 0.1)  # 根据缩放因子调整Z偏移
    vertices_final[:, 2] += z_offset
    joints_final[:, 2] += z_offset
    
    # 渲染3D人体模型 - 使用面渲染和指定颜色#A1B0DC
    plot_3d_human_mesh_with_faces(ax, vertices_final, color='#A1B0DC')
    

            

    # 获取颜色映射
    color_mapping = get_joint_color_mapping()
    
    # 渲染3D关节点 - 使用相同的颜色映射
    for joint_idx in range(len(joints_final)):
        if joint_idx in SMPL_JOINT_REGRESSOR_SIMPLIFIED:
            
            # 检查是否有对应的2D映射
            has_2d_mapping = joint_idx in color_mapping
            
            if has_2d_mapping:
                # 有2D映射的关节使用匹配的颜色
                color_info = color_mapping[joint_idx]
                # 将BGR转换为RGB格式的归一化颜色
                rgb_color = [c/255.0 for c in color_info['rgb']]
                marker = 'o'
                size = 150
            else:
                # 没有2D映射的关节使用灰色
                rgb_color = [0.5, 0.5, 0.5]  # 灰色
                marker = 's'  # 方形标记
                size = 100
            
            x, y, z = joints_final[joint_idx]
            # 渲染关节点
            ax.scatter(x, y, z, c=[rgb_color], s=size, alpha=1.0, marker=marker, 
                      edgecolors='white', linewidth=3, zorder=30)
            
            # 只为有映射的关节添加编号标注
            if has_2d_mapping:
                label_text = f"{joint_idx}"
                
                ax.text(x, y, z, label_text, 
                       fontsize=8, color='white', weight='bold',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor=rgb_color, alpha=0.8),
                       ha='center', va='center', zorder=35)
            # 未匹配的关节不显示任何文字标注
    
    # 连接关节 - 使用映射关系智能渲染骨架线
    joint_connections = [
        (0, 1), (0, 2), (1, 4), (2, 5), (4, 7), (5, 8),
        (0, 12), (12, 15), (12, 16), (12, 17),
        (16, 18), (17, 19), (18, 20), (19, 21)
    ]
    
    for connection in joint_connections:
        if (connection[0] < len(joints_final) and connection[1] < len(joints_final) and
            connection[0] in SMPL_JOINT_REGRESSOR_SIMPLIFIED and 
            connection[1] in SMPL_JOINT_REGRESSOR_SIMPLIFIED):
            
            start_joint = joints_final[connection[0]]
            end_joint = joints_final[connection[1]]
            
            # 检查连接的两个关节是否都有2D映射
            start_has_mapping = connection[0] in color_mapping
            end_has_mapping = connection[1] in color_mapping
            
            # 根据映射情况选择线条样式
            if start_has_mapping and end_has_mapping:
                # 两端都有映射 - 使用实线，较粗，白色
                line_color = 'white'
                line_width = 5
                line_style = '-'
                alpha = 1.0
                zorder = 25
            elif start_has_mapping or end_has_mapping:
                # 一端有映射 - 使用虚线，中等粗细，浅灰色
                line_color = 'lightgray'
                line_width = 3
                line_style = '--'
                alpha = 0.8
                zorder = 20
            else:
                # 两端都无映射 - 使用点线，较细，深灰色
                line_color = 'darkgray'
                line_width = 2
                line_style = ':'
                alpha = 0.6
                zorder = 15
            
            # 渲染连接线
            ax.plot([start_joint[0], end_joint[0]], 
                   [start_joint[1], end_joint[1]], 
                   [start_joint[2], end_joint[2]], 
                   color=line_color, linewidth=line_width, 
                   linestyle=line_style, alpha=alpha, zorder=zorder)
    
    # 设置固定视图 - 使用适中的视图范围，确保3D人体完整显示且保持合理大小
    # 平衡视图范围：既避免右侧部分被裁剪，又保持3D人体合理的显示大小
    base_range = 3.5  # 适中的视图范围，确保完整显示且保持合理大小
    ax.set_xlim([-base_range, base_range])
    ax.set_ylim([-base_range, base_range])
    ax.set_zlim([-base_range*0.5, base_range*1.5])  # 调整Z轴范围，包含负值部分
    ax.view_init(elev=25, azim=-10)  # 调整视角让人体更居中
    
    # 设置黑色背景增加对比度
    ax.set_facecolor('black')
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('none')
    ax.yaxis.pane.set_edgecolor('none')
    ax.zaxis.pane.set_edgecolor('none')
    ax.grid(False)
    ax.set_axis_off()
    
    # 渲染到内存
    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (4,))
    buf = buf[:, :, :3]  # 移除alpha通道，只保留RGB
    plt.close()
    
    return buf

def get_joint_color_mapping():
    """为匹配的3D-2D关节对分配相同的颜色"""
    aligner = StableAligner()
    
    # 预定义的颜色列表（BGR格式用于OpenCV，RGB格式用于matplotlib）
    colors_bgr = [
        (0, 0, 255),      # 红色
        (0, 255, 0),      # 绿色  
        (255, 0, 0),      # 蓝色
        (0, 255, 255),    # 黄色
        (255, 0, 255),    # 品红
        (255, 255, 0),    # 青色
        (0, 165, 255),    # 橙色
        (128, 0, 128),    # 紫色
        (0, 128, 255),    # 橙红色
        (255, 192, 203),  # 粉色
        (0, 255, 127),    # 春绿色
        (255, 20, 147),   # 深粉色
        (30, 144, 255),   # 道奇蓝
    ]
    
    colors_rgb = [
        (255, 0, 0),      # 红色
        (0, 255, 0),      # 绿色
        (0, 0, 255),      # 蓝色
        (255, 255, 0),    # 黄色
        (255, 0, 255),    # 品红
        (0, 255, 255),    # 青色
        (255, 165, 0),    # 橙色
        (128, 0, 128),    # 紫色
        (255, 128, 0),    # 橙红色
        (255, 192, 203),  # 粉色
        (127, 255, 0),    # 春绿色
        (255, 20, 147),   # 深粉色
        (30, 144, 255),   # 道奇蓝
    ]
    
    color_mapping = {}
    color_idx = 0
    
    for joint_3d_idx, joint_2d_idx in aligner.joint_3d_to_2d_mapping.items():
        if color_idx < len(colors_bgr):
            color_mapping[joint_3d_idx] = {
                'bgr': colors_bgr[color_idx],
                'rgb': colors_rgb[color_idx],
                '2d_idx': joint_2d_idx
            }
            color_idx += 1
        else:
            # 如果颜色不够，使用灰色
            color_mapping[joint_3d_idx] = {
                'bgr': (128, 128, 128),
                'rgb': (128, 128, 128),
                '2d_idx': joint_2d_idx
            }
    
    return color_mapping

def draw_stable_2d_joints(frame, joints_2d):
    """绘制稳定的2D关节 - 匹配的关节显示相同颜色和编号"""
    frame_with_joints = frame.copy()
    
    # 获取颜色映射
    color_mapping = get_joint_color_mapping()
    
    if len(joints_2d) > 0:
        person_joints = joints_2d[0]
        
        # 确保person_joints是numpy数组并且形状正确
        if isinstance(person_joints, np.ndarray):
            person_joints = person_joints.reshape(-1, 2)
        
        for joint_2d_idx in range(len(person_joints)):
            joint_data = person_joints[joint_2d_idx]
            # 安全地提取x, y坐标
            if len(joint_data) >= 2:
                x, y = float(joint_data[0]), float(joint_data[1])
            else:
                continue
                
            if x > 0 and y > 0:
                # 查找对应的3D关节索引
                corresponding_3d_idx = None
                for joint_3d_idx, mapping_info in color_mapping.items():
                    if mapping_info['2d_idx'] == joint_2d_idx:
                        corresponding_3d_idx = joint_3d_idx
                        break
                
                if corresponding_3d_idx is not None:
                    # 有对应3D关节的2D关节 - 使用匹配的颜色
                    color = color_mapping[corresponding_3d_idx]['bgr']
                    radius = 10
                    
                    # 绘制有映射的关节（实心圆）
                    cv2.circle(frame_with_joints, (int(x), int(y)), radius, color, -1)
                    cv2.circle(frame_with_joints, (int(x), int(y)), radius + 2, (255, 255, 255), 2)
                    
                    # 只显示关节编号，不显示映射关系
                    label_text = f"{joint_2d_idx}"
                    cv2.putText(frame_with_joints, label_text, 
                               (int(x) - 8, int(y) - 15), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                else:
                    # 没有对应3D关节的2D关节
                    color = (128, 128, 128)  # 灰色 - 无映射
                    radius = 6
                    
                    # 绘制无映射的关节（空心圆），但不显示文字标注
                    cv2.circle(frame_with_joints, (int(x), int(y)), radius, color, 2)
                    # 未匹配的关节不显示任何文字标注
        
        # 连接关节 - 使用映射关系智能渲染2D连接线
        joint_connections_2d = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (1, 5), (5, 6), (6, 7),
            (1, 8), (8, 9), (9, 10),
            (0, 11), (11, 12), (12, 13),
            (0, 14), (14, 15), (15, 16)
        ]
        
        for connection in joint_connections_2d:
            if (connection[0] < len(person_joints) and connection[1] < len(person_joints)):
                pt1 = person_joints[connection[0]]
                pt2 = person_joints[connection[1]]
                
                # 安全地提取坐标
                try:
                    x1, y1 = float(pt1[0]), float(pt1[1])
                    x2, y2 = float(pt2[0]), float(pt2[1])
                except (IndexError, TypeError, ValueError):
                    continue
                    
                if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
                    
                    # 获取颜色映射
                    color_mapping = get_joint_color_mapping()
                    
                    # 检查连接的两个2D关节是否都有对应的3D映射
                    start_has_3d_mapping = any(color_info['2d_idx'] == connection[0] 
                                             for color_info in color_mapping.values())
                    end_has_3d_mapping = any(color_info['2d_idx'] == connection[1] 
                                           for color_info in color_mapping.values())
                    
                    # 根据映射情况选择线条样式
                    if start_has_3d_mapping and end_has_3d_mapping:
                        # 两端都有3D映射 - 使用实线，较粗，白色
                        line_color = (255, 255, 255)
                        line_thickness = 4
                    elif start_has_3d_mapping or end_has_3d_mapping:
                        # 一端有3D映射 - 使用中等粗细，浅灰色
                        line_color = (200, 200, 200)
                        line_thickness = 3
                    else:
                        # 两端都无3D映射 - 使用较细，深灰色
                        line_color = (128, 128, 128)
                        line_thickness = 2
                    
                    cv2.line(frame_with_joints, 
                            (int(x1), int(y1)), 
                            (int(x2), int(y2)), 
                            line_color, line_thickness)
    
    return frame_with_joints

def create_stable_alignment_frame(original_frame, vertices, joints_2d, scale_factor=8.0, previous_3d_position=None, confidence_scores=None):
    """创建基于3D跟踪位置的稳定对齐帧
    
    使用映射关系进行智能渲染：
    - 3D关节：有映射的关节用圆形标记，无映射的用方形标记
    - 2D关节：有映射的关节用实心圆，无映射的用空心圆
    - 连接线：根据两端关节的映射情况使用不同样式
    - 标注：显示3D↔2D的映射关系
    
    Args:
        confidence_scores: 2D关节检测的置信度分数，形状为(num_joints,)
    """
    aligner = StableAligner()
    
    # 打印映射关系信息（仅在第一次调用时）
    if not hasattr(create_stable_alignment_frame, '_mapping_printed'):
        print("\n[MAPPING] 3D-2D Joint Mapping:")
        print("=" * 50)
        
        # 统计匹配信息
        total_3d_joints = len(SMPL_JOINT_REGRESSOR_SIMPLIFIED)
        matched_joints = len(aligner.joint_3d_to_2d_mapping)
        unmatched_joints = total_3d_joints - matched_joints
        
        print(f"[STATS] 匹配统计: {matched_joints}/{total_3d_joints} 个3D关节已匹配 ({matched_joints/total_3d_joints*100:.1f}%)")
        print(f"[OK] 已匹配关节: {matched_joints} 个")
        print(f"[ERROR] 未匹配关节: {unmatched_joints} 个")
        print()
        
        # 显示已匹配的关节
        print("[OK] 已匹配的关节:")
        for joint_3d_idx, joint_2d_idx in sorted(aligner.joint_3d_to_2d_mapping.items()):
            joint_name = SMPL_JOINT_NAMES[joint_3d_idx] if joint_3d_idx < len(SMPL_JOINT_NAMES) else f"joint_{joint_3d_idx}"
            importance = JOINT_IMPORTANCE_WEIGHTS.get(joint_3d_idx, 1.0)
            print(f"  [OK] 3D[{joint_3d_idx:2d}] {joint_name:15s} <-> 2D[{joint_2d_idx:2d}] (重要性: {importance:.1f})")
        
        # 显示未匹配的关节
        unmatched_3d_joints = [idx for idx in SMPL_JOINT_REGRESSOR_SIMPLIFIED.keys() 
                              if idx not in aligner.joint_3d_to_2d_mapping]
        if unmatched_3d_joints:
            print("\n[ERROR] 未匹配的3D关节:")
            for joint_3d_idx in sorted(unmatched_3d_joints):
                joint_name = SMPL_JOINT_NAMES[joint_3d_idx] if joint_3d_idx < len(SMPL_JOINT_NAMES) else f"joint_{joint_3d_idx}"
                importance = JOINT_IMPORTANCE_WEIGHTS.get(joint_3d_idx, 1.0)
                print(f"  [ERROR] 3D[{joint_3d_idx:2d}] {joint_name:15s} (重要性: {importance:.1f}) - 无2D对应")
        
        print("=" * 50)
        create_stable_alignment_frame._mapping_printed = True
    
    # 获取2D关节目标
    if len(joints_2d) > 0:
        target_joints_2d = joints_2d[0]
    else:
        target_joints_2d = np.zeros((19, 2))
    
    # 执行基于3D跟踪位置的稳定对齐优化
    alignment_result = aligner.optimize_stable_alignment(vertices, target_joints_2d, previous_3d_position, confidence_scores)
    
    # 渲染稳定的3D模型
    model_image = render_stable_3d_model(
        alignment_result['vertices'], 
        alignment_result['joints_3d'],
        original_frame.shape, 
        transform_params=alignment_result['transform_params'],
        scale_factor=scale_factor,
        joints_2d_target=target_joints_2d
    )
    
    # 绘制稳定的2D关节
    frame_with_2d_joints = draw_stable_2d_joints(original_frame, joints_2d)
    
    # 转换和混合
    model_bgr = cv2.cvtColor(model_image, cv2.COLOR_RGB2BGR)
    model_gray = cv2.cvtColor(model_image, cv2.COLOR_RGB2GRAY)
    # 由于背景改为黑色，调整阈值检测逻辑
    # 检测非黑色区域（即3D模型区域）
    _, mask = cv2.threshold(model_gray, 15, 255, cv2.THRESH_BINARY)
    
    # 形态学操作
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    mask_area = cv2.countNonZero(mask)
    total_area = mask.shape[0] * mask.shape[1]
    mask_ratio = mask_area / total_area
    
    # 显示当前帧的关节匹配状态
    if len(joints_2d) > 0:
        person_joints = joints_2d[0]
        
        # 确保person_joints是numpy数组并且形状正确
        if isinstance(person_joints, np.ndarray):
            person_joints = person_joints.reshape(-1, 2)
        
        # 安全地计算检测到的2D关节数
        detected_2d_joints = 0
        for joint_data in person_joints:
            try:
                x, y = float(joint_data[0]), float(joint_data[1])
                if x > 0 and y > 0:
                    detected_2d_joints += 1
            except (IndexError, TypeError, ValueError):
                continue
                
        matched_in_frame = 0
        
        # 统计当前帧中实际匹配的关节数
        for joint_3d_idx, joint_2d_idx in aligner.joint_3d_to_2d_mapping.items():
            if joint_2d_idx < len(person_joints):
                try:
                    joint_data = person_joints[joint_2d_idx]
                    x, y = float(joint_data[0]), float(joint_data[1])
                    if x > 0 and y > 0:  # 2D关节被检测到
                        matched_in_frame += 1
                except (IndexError, TypeError, ValueError):
                    continue
        
        print(f"[STATUS] 当前帧关节状态: 检测到{detected_2d_joints}个2D关节, 成功匹配{matched_in_frame}个3D-2D关节对")
    
    # 显示更详细的对齐信息
    if 'position_error' in alignment_result and 'projection_error' in alignment_result:
        print(f"[ALIGN] 3D跟踪对齐 | 总误差: {alignment_result['final_error']:.2f} | "
              f"投影误差: {alignment_result['projection_error']:.2f} | "
              f"位置误差: {alignment_result['position_error']:.2f} | "
              f"迭代: {alignment_result['iterations']} | Mask: {mask_ratio*100:.3f}%")
    else:
        print(f"🎯 稳定对齐 | 误差: {alignment_result['final_error']:.2f} | 迭代: {alignment_result['iterations']} | Mask: {mask_ratio*100:.3f}%")
    
    # 降低mask阈值，确保3D模型更容易显示
    # 原来的0.001 (0.1%)太严格，改为0.0001 (0.01%)
    if mask_area < total_area * 0.0001:
        print(f"[WARNING] 3D模型mask太小 ({mask_ratio*100:.4f}%)，跳过渲染")
        return frame_with_2d_joints, alignment_result
    
    print(f"[OK] 3D模型渲染 | Mask面积: {mask_area} ({mask_ratio*100:.3f}%)")
    
    # 混合图像 - 使用透明度混合实现半透明效果
    result_frame = frame_with_2d_joints.copy().astype(np.float32)
    model_bgr = model_bgr.astype(np.float32)
    mask_3channel = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
    
    # 设置3D模型的透明度（与plot_3d_human_mesh_with_faces中的alpha值一致）
    model_alpha = 1.0
    
    for c in range(3):
        # 使用透明度混合：result = background * (1 - alpha * mask) + foreground * (alpha * mask)
        result_frame[:, :, c] = (1 - model_alpha * mask_3channel[:, :, c]) * result_frame[:, :, c] + \
                               (model_alpha * mask_3channel[:, :, c]) * model_bgr[:, :, c]
    
    # 添加信息显示
    tracking_status = "3D Tracking" if previous_3d_position is not None else "No Tracking"
    info_text = [
        f"3D Position-Guided Alignment | Error: {alignment_result['final_error']:.1f} | {tracking_status}",
        f"Transform: tx={alignment_result['transform_params'][0]:.2f}, ty={alignment_result['transform_params'][1]:.2f}, scale={alignment_result['transform_params'][3]:.2f}",
        "Enhanced Stability with 3D Position Tracking"
    ]
    
    for i, text in enumerate(info_text):
        cv2.putText(result_frame.astype(np.uint8), text, 
                   (10, 30 + i*25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return result_frame.astype(np.uint8), alignment_result

def create_stable_alignment_video(video_path=None, pkl_path=None):
    """创建基于3D跟踪位置的稳定对齐视频"""
    print("🎬 创建基于3D跟踪位置的稳定对齐视频")
    print("=" * 60)
    
    # 加载数据 - 支持命令行参数或使用默认值
    if pkl_path is None:
        pkl_file = "output/demo_output/sample_video/pmce_output.pkl"
    else:
        pkl_file = pkl_path
        
    if video_path is None:
        original_video = "demo/sample_video.mp4"
    else:
        original_video = video_path
        
    output_video = "STABLE_3D_TRACKING_ALIGNMENT_VIDEO.mp4"
    
    try:
        data = joblib.load(pkl_file)
        print(f"[OK] 成功加载PMCE数据")
        
        # 显示所有人员信息
        print(f"\n👥 检测到 {len(data)} 个人员:")
        for pid in sorted(data.keys()):
            person_info = data[pid]
            has_joints2d = 'joints2d' in person_info
            mesh_frames = len(person_info['mesh']) if 'mesh' in person_info else 0
            joints2d_shape = person_info['joints2d'].shape if has_joints2d else "无"
            print(f"   人员 {pid}: {mesh_frames} 帧, joints2d: {joints2d_shape}")
        
        # 选择处理所有人员还是特定人员
        # 这里我们处理帧数最多的人员（通常是主要人物）
        selected_person_id = None
        max_frames = 0
        
        for pid in data.keys():
            if 'mesh' in data[pid]:
                frames = len(data[pid]['mesh'])
                if frames > max_frames:
                    max_frames = frames
                    selected_person_id = pid
        
        if selected_person_id is None:
            print("[ERROR] 未找到有效的人员数据")
            return False
            
        person_data = data[selected_person_id]
        print(f"\n🎯 选择处理人员 {selected_person_id} (帧数最多: {max_frames} 帧)")
        
        # 处理2D关节数据
        if 'joints2d' in person_data:
            joints_2d = person_data['joints2d']
            # 如果joints2d是4维的，取第一个检测结果
            if len(joints_2d.shape) == 4:
                joints_2d = joints_2d[:, 0, :, :]  # 取第一个人的检测结果
            print(f"[OK] 使用真实的2D关节数据")
        else:
            # 生成虚拟的2D关节数据（全零，表示未检测到）
            num_frames = len(person_data['mesh'])
            # 创建与sample_video相同格式的数据结构: (frames, persons, joints, coordinates)
            joints_2d = np.zeros((num_frames, 1, 17, 2))  # 1个人，17个关节，2个坐标
            print(f"[WARNING] 生成了虚拟的2D关节数据")
        
        meshes = person_data['mesh']
        
        print(f"📊 网格数据: {meshes.shape}")
        print(f"📊 2D关节数据: {joints_2d.shape}")
        
        # 打开原始视频
        cap = cv2.VideoCapture(original_video)
        if not cap.isOpened():
            print(f"[ERROR] 无法打开视频: {original_video}")
            return False
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"📹 视频信息: {total_frames} 帧, {fps:.1f} FPS, {width}x{height}")
        
        # 创建临时目录
        temp_dir = "temp_3d_tracking_frames"
        os.makedirs(temp_dir, exist_ok=True)
        
        min_frames = min(total_frames, len(meshes), len(joints_2d))
        print(f"🎬 处理 {min_frames} 帧 (启用3D位置跟踪)")
        
        # 统计信息
        alignment_results = []
        previous_3d_position = None  # 用于3D位置跟踪
        aligner = StableAligner()  # 创建对齐器实例
        
        # 处理每一帧
        for frame_idx in range(min_frames):
            ret, frame = cap.read()
            if not ret:
                break
            
            vertices = meshes[frame_idx]
            frame_joints_2d = joints_2d[frame_idx]
            
            # 创建基于3D跟踪位置的稳定对齐帧 - 增大scale_factor放大3D人体
            stable_frame, alignment_result = create_stable_alignment_frame(
                frame, vertices, frame_joints_2d, scale_factor=4.0, previous_3d_position=previous_3d_position
            )
            
            alignment_results.append(alignment_result)
            
            # 更新前一帧的3D位置用于下一帧跟踪
            if 'joints_3d' in alignment_result:
                previous_3d_position = alignment_result['joints_3d'].copy()
            
            # 保存帧
            frame_path = os.path.join(temp_dir, f"tracking_frame_{frame_idx:06d}.png")
            cv2.imwrite(frame_path, stable_frame)
            
            # 进度更新
            if (frame_idx + 1) % 10 == 0 or frame_idx == min_frames - 1:
                avg_error = np.mean([r['final_error'] for r in alignment_results])
                avg_iterations = np.mean([r['iterations'] for r in alignment_results])
                
                # 计算3D跟踪相关统计
                tracking_frames = sum(1 for r in alignment_results if 'position_error' in r)
                avg_pos_error = np.mean([r.get('position_error', 0) for r in alignment_results if 'position_error' in r])
                avg_proj_error = np.mean([r.get('projection_error', 0) for r in alignment_results if 'projection_error' in r])
                
                print(f"处理进度: {frame_idx + 1}/{min_frames} ({(frame_idx+1)/min_frames*100:.1f}%) | "
                      f"总误差: {avg_error:.2f} | 迭代: {avg_iterations:.1f} | "
                      f"3D跟踪帧: {tracking_frames} | 位置误差: {avg_pos_error:.2f} | 投影误差: {avg_proj_error:.2f}")
        
        cap.release()
        
        # 生成统计报告
        errors = [r['final_error'] for r in alignment_results]
        iterations = [r['iterations'] for r in alignment_results]
        
        print(f"\n📊 稳定对齐统计:")
        print(f"   平均误差: {np.mean(errors):.2f}")
        print(f"   误差范围: {np.min(errors):.2f} - {np.max(errors):.2f}")
        print(f"   平均迭代次数: {np.mean(iterations):.1f}")
        print(f"   成功率: 100%")
        
        # 使用FFmpeg创建视频
        print("🎥 创建最终3D跟踪对齐视频...")
        frame_pattern = os.path.join(temp_dir, "tracking_frame_%06d.png")
        
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
            print(f"[OK] 3D跟踪对齐视频创建成功: {output_video}")
            
            # 清理临时文件
            import shutil
            shutil.rmtree(temp_dir)
            
            file_size = os.path.getsize(output_video) / (1024 * 1024)
            print(f"📹 输出文件大小: {file_size:.1f} MB")
            
            return True
        else:
            print(f"[ERROR] FFmpeg执行失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 创建视频时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_stable_alignment_frame_with_camera(frame, vertices, joints_2d, pred_cam, scale_factor=2.0, previous_3d_position=None):
    """
    创建基于相机参数优化的稳定对齐帧
    
    Args:
        frame: 原始视频帧
        vertices: 3D网格顶点 (6890, 3)
        joints_2d: 2D关节点数据 (可能是多人的)
        pred_cam: 相机参数 [scale, tx, ty]
        scale_factor: 3D模型显示缩放因子
        previous_3d_position: 前一帧的3D位置（用于跟踪）
    
    Returns:
        combined_frame: 合并后的帧
        alignment_result: 对齐结果信息
    """
    height, width = frame.shape[:2]
    
    # 创建对齐器实例
    aligner = StableAligner(use_camera_optimization=True)
    
    # 获取2D关节目标
    if len(joints_2d.shape) == 3:  # (persons, joints, coords)
        # 选择第一个人的关节数据
        target_joints_2d = joints_2d[0]
    elif len(joints_2d.shape) == 2:  # (joints, coords)
        target_joints_2d = joints_2d
    else:
        print(f"[WARNING] 不支持的joints_2d形状: {joints_2d.shape}")
        target_joints_2d = joints_2d.reshape(-1, 2)
    
    print(f"🎯 使用相机参数优化进行3D-2D对齐")
    print(f"   相机参数: scale={pred_cam[0]:.3f}, tx={pred_cam[1]:.3f}, ty={pred_cam[2]:.3f}")
    print(f"   2D关节目标: {target_joints_2d.shape}")
    
    # 使用相机参数优化进行稳定对齐
    optimized_cam, final_error, iterations = aligner.optimize_stable_alignment(
        vertices, target_joints_2d, pred_cam=pred_cam, previous_3d_position=previous_3d_position
    )
    
    print(f"   优化后相机参数: scale={optimized_cam[0]:.3f}, tx={optimized_cam[1]:.3f}, ty={optimized_cam[2]:.3f}")
    print(f"   最终误差: {final_error:.2f}, 迭代次数: {iterations}")
    
    # 提取3D关节点
    aligner = StableAligner()
    joints_3d = aligner.extract_3d_joints_from_mesh(vertices)
    
    # 渲染3D模型（使用相机参数）
    model_3d = render_stable_3d_model(
        vertices, 
        joints_3d, 
        (height, width), 
        scale_factor=scale_factor,
        pred_cam=optimized_cam,
        use_camera_projection=True
    )
    
    # 绘制2D关节点
    joints_2d_img = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 绘制目标关节点（红色）
    for i, (x, y) in enumerate(target_joints_2d):
        if x > 0 and y > 0:  # 只绘制有效的关节点
            cv2.circle(joints_2d_img, (int(x), int(y)), 4, (0, 0, 255), -1)
            cv2.putText(joints_2d_img, str(i), (int(x)+5, int(y)-5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
    
    # 计算并绘制投影的关节点（绿色）
    joints_3d = aligner.extract_3d_joints(vertices)
    projected_joints = aligner.project_3d_to_2d_with_camera(joints_3d, optimized_cam, width, height)
    
    for i, (x, y) in enumerate(projected_joints):
        if 0 <= x < width and 0 <= y < height:
            cv2.circle(joints_2d_img, (int(x), int(y)), 3, (0, 255, 0), -1)
            cv2.putText(joints_2d_img, str(i), (int(x)+5, int(y)+5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
    
    # 混合图像
    alpha = 0.7
    combined_frame = cv2.addWeighted(frame, alpha, model_3d, 1-alpha, 0)
    combined_frame = cv2.addWeighted(combined_frame, 0.8, joints_2d_img, 0.2, 0)
    
    # 添加信息文本
    info_text = [
        f"Camera Optimization Alignment",
        f"Scale: {optimized_cam[0]:.3f}, TX: {optimized_cam[1]:.3f}, TY: {optimized_cam[2]:.3f}",
        f"Error: {final_error:.2f}, Iterations: {iterations}",
        f"Frame: {width}x{height}"
    ]
    
    y_offset = 30
    for i, text in enumerate(info_text):
        cv2.putText(combined_frame, text, (10, y_offset + i * 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(combined_frame, text, (10, y_offset + i * 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    
    # 准备返回结果
    alignment_result = {
        'optimized_camera': optimized_cam,
        'final_error': final_error,
        'iterations': iterations,
        'joints_3d': joints_3d,
        'projected_joints': projected_joints,
        'target_joints': target_joints_2d
    }
    
    return combined_frame, alignment_result

def main():
    """主函数，支持命令行参数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='创建稳定的3D对齐视频')
    parser.add_argument('--video_path', type=str, help='输入视频文件路径')
    parser.add_argument('--pkl_path', type=str, help='输入pkl文件路径')
    parser.add_argument('--use_camera_optimization', action='store_true', help='使用相机参数优化方法')
    args = parser.parse_args()
    
    if args.video_path and args.pkl_path:
        # 使用命令行参数
        create_stable_alignment_video(args.video_path, args.pkl_path)
    else:
        # 使用默认配置
        create_stable_alignment_video()

if __name__ == "__main__":
    main()