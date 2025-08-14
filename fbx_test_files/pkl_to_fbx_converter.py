#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PKL to FBX Converter
将 pmce_output.pkl 文件转换为 Maya 兼容的 FBX 文件
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

def load_pkl_data(pkl_file_path):
    """
    加载 pkl 文件并分析其结构
    """
    try:
        # 尝试使用 joblib 加载（pose3d 使用 joblib.dump 保存）
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
        
        print(f"数据类型: {type(data)}")
        
        if isinstance(data, dict):
            print(f"字典键: {list(data.keys())}")
            
            # 分析每个人物的数据结构
            for person_id, person_data in data.items():
                print(f"\n人物 ID '{person_id}':")
                if isinstance(person_data, dict):
                    print(f"  包含的数据键: {list(person_data.keys())}")
                    
                    # 分析关键数据
                    for key, value in person_data.items():
                        print(f"  {key}:")
                        if hasattr(value, 'shape'):
                            print(f"    形状: {value.shape}")
                            print(f"    数据类型: {value.dtype}")
                        elif isinstance(value, (list, tuple)):
                            print(f"    长度: {len(value)}")
                        else:
                            print(f"    类型: {type(value)}")
                else:
                    print(f"  类型: {type(person_data)}")
        
        return data
        
    except Exception as e:
        print(f"加载 PKL 文件失败: {e}")
        return None

def analyze_mesh_data(mesh_data):
    """
    分析网格数据结构
    """
    if mesh_data is None:
        return None
        
    print(f"\n=== 网格数据分析 ===")
    print(f"形状: {mesh_data.shape}")
    print(f"数据类型: {mesh_data.dtype}")
    
    # 假设数据格式为 [frames, vertices, coordinates]
    if len(mesh_data.shape) == 3:
        frames, vertices, coords = mesh_data.shape
        print(f"帧数: {frames}")
        print(f"顶点数: {vertices}")
        print(f"坐标维度: {coords}")
        
        # 检查坐标范围
        print(f"X 坐标范围: [{mesh_data[:,:,0].min():.3f}, {mesh_data[:,:,0].max():.3f}]")
        print(f"Y 坐标范围: [{mesh_data[:,:,1].min():.3f}, {mesh_data[:,:,1].max():.3f}]")
        print(f"Z 坐标范围: [{mesh_data[:,:,2].min():.3f}, {mesh_data[:,:,2].max():.3f}]")
        
        return {
            'frames': frames,
            'vertices': vertices,
            'coords': coords,
            'data': mesh_data
        }
    
    return None

def create_fbx_from_joints3d(joints3d_data, output_path, person_id=0):
    """
    从 joints3d 数据创建 FBX 骨骼动画文件
    """
    if joints3d_data is None:
        print("错误: 无效的关节数据")
        return False
    
    try:
        # COCO 17关节名称（与 pose3d 一致）
        joint_names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        # 骨骼层次结构
        bone_hierarchy = {
            'left_eye': 'nose',
            'right_eye': 'nose',
            'left_ear': 'left_eye',
            'right_ear': 'right_eye',
            'left_shoulder': 'nose',
            'right_shoulder': 'nose',
            'left_elbow': 'left_shoulder',
            'right_elbow': 'right_shoulder',
            'left_wrist': 'left_elbow',
            'right_wrist': 'right_elbow',
            'left_hip': 'nose',
            'right_hip': 'nose',
            'left_knee': 'left_hip',
            'right_knee': 'right_hip',
            'left_ankle': 'left_knee',
            'right_ankle': 'right_knee'
        }
        
        # 创建 FBX 管理器和场景
        manager = fbx.FbxManager.Create()
        scene = fbx.FbxScene.Create(manager, "SkeletonScene")
        
        # 设置场景信息（简化版本）
        try:
            scene_info = scene.GetSceneInfo()
            if scene_info:
                # 尝试设置基本信息，如果失败则跳过
                pass
        except Exception as e:
            print(f"设置场景信息时出现警告: {e}")
            pass
        
        # 设置全局设置
        global_settings = scene.GetGlobalSettings()
        global_settings.SetSystemUnit(fbx.FbxSystemUnit.m)  # 使用米作为单位
        global_settings.SetOriginalSystemUnit(fbx.FbxSystemUnit.m)
        global_settings.SetTimeMode(fbx.FbxTime.eFrames30)
        
        # 创建根节点
        root_node = scene.GetRootNode()
        
        # 创建骨架
        skeleton = fbx.FbxSkeleton.Create(scene, "Skeleton")
        skeleton.SetSkeletonType(fbx.FbxSkeleton.eRoot)
        skeleton.Size.Set(1.0)
        
        # 创建根骨骼节点
        root_bone_node = fbx.FbxNode.Create(scene, "Root")
        root_bone_node.SetNodeAttribute(skeleton)
        root_node.AddChild(root_bone_node)
        
        # 创建关节节点字典
        joint_nodes = {}
        
        # 首先创建所有关节节点
        for i, joint_name in enumerate(joint_names):
            # 创建骨骼属性
            limb_node_attr = fbx.FbxSkeleton.Create(scene, f"{joint_name}_attr")
            limb_node_attr.SetSkeletonType(fbx.FbxSkeleton.eLimbNode)
            limb_node_attr.Size.Set(0.1)
            
            # 创建节点
            joint_node = fbx.FbxNode.Create(scene, joint_name)
            joint_node.SetNodeAttribute(limb_node_attr)
            
            # 设置初始位置（使用第一帧数据）
            if len(joints3d_data.shape) == 3:  # (frames, joints, coords)
                first_frame = joints3d_data[0]
                joint_pos = first_frame[i]
            else:  # 单帧数据
                joint_pos = joints3d_data[i]
            
            # 缩放位置（pose3d 数据通常很小）
            scale_factor = 100.0  # 放大100倍
            joint_node.LclTranslation.Set(fbx.FbxDouble3(
                float(joint_pos[0]) * scale_factor,
                float(joint_pos[1]) * scale_factor,
                float(joint_pos[2]) * scale_factor
            ))
            
            joint_nodes[joint_name] = joint_node
        
        # 建立骨骼层次结构
        for joint_name, joint_node in joint_nodes.items():
            if joint_name in bone_hierarchy:
                parent_name = bone_hierarchy[joint_name]
                if parent_name in joint_nodes:
                    joint_nodes[parent_name].AddChild(joint_node)
                else:
                    root_bone_node.AddChild(joint_node)
            else:
                # 根关节连接到根骨骼
                root_bone_node.AddChild(joint_node)
        
        # 如果有多帧数据，创建动画
        if len(joints3d_data.shape) == 3 and joints3d_data.shape[0] > 1:
            num_frames = joints3d_data.shape[0]
            print(f"创建 {num_frames} 帧的骨骼动画...")
            
            # 创建动画堆栈和层
            anim_stack = fbx.FbxAnimStack.Create(scene, "SkeletonAnimation")
            anim_layer = fbx.FbxAnimLayer.Create(scene, "BaseLayer")
            anim_stack.AddMember(anim_layer)
            
            # 为每个关节创建动画曲线
            for i, joint_name in enumerate(joint_names):
                if joint_name in joint_nodes:
                    joint_node = joint_nodes[joint_name]
                    
                    # 创建位移动画曲线
                    curve_x = joint_node.LclTranslation.GetCurve(anim_layer, "X", True)
                    curve_y = joint_node.LclTranslation.GetCurve(anim_layer, "Y", True)
                    curve_z = joint_node.LclTranslation.GetCurve(anim_layer, "Z", True)
                    
                    # 添加关键帧
                    for frame_idx in range(num_frames):
                        time = fbx.FbxTime()
                        time.SetFrame(frame_idx, fbx.FbxTime.eFrames30)
                        
                        joint_pos = joints3d_data[frame_idx][i]
                        
                        # 应用缩放
                        scaled_pos = [
                            float(joint_pos[0]) * scale_factor,
                            float(joint_pos[1]) * scale_factor,
                            float(joint_pos[2]) * scale_factor
                        ]
                        
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
        
        # 设置导出格式（使用兼容的格式）
        try:
            # 尝试设置为 FBX 2020 格式
            if hasattr(fbx.FbxIO, 'eFBX_20203_2'):
                exporter.SetFileExportVersion(fbx.FbxIO.eFBX_20203_2)
            elif hasattr(fbx.FbxIO, 'eFBX_2020'):
                exporter.SetFileExportVersion(fbx.FbxIO.eFBX_2020)
            else:
                # 使用默认格式
                pass
        except Exception as e:
            print(f"设置导出格式时出现警告: {e}")
            pass
        
        # 导出场景
        result = exporter.Export(scene)
        exporter.Destroy()
        
        if result:
            print(f"成功创建骨骼 FBX 文件: {output_path}")
            file_size = os.path.getsize(output_path)
            print(f"文件大小: {file_size:,} 字节")
            if len(joints3d_data.shape) == 3:
                print(f"包含 {joints3d_data.shape[0]} 帧动画，{len(joint_names)} 个关节")
            return True
        else:
            print(f"导出 FBX 文件失败: {output_path}")
            return False
            
    except Exception as e:
        print(f"创建骨骼 FBX 文件时出错: {e}")
        return False
    finally:
        if 'manager' in locals():
            manager.Destroy()

def create_fbx_from_mesh(mesh_info, output_path):
    """
    从网格数据创建 FBX 文件
    """
    if mesh_info is None:
        print("错误: 无效的网格信息")
        return False
    
    try:
        # 创建 FBX 管理器和场景
        manager = fbx.FbxManager.Create()
        scene = fbx.FbxScene.Create(manager, "MeshScene")
        
        # 设置场景信息（简化版本）
        try:
            scene_info = scene.GetSceneInfo()
            if scene_info:
                # 尝试设置基本信息，如果失败则跳过
                pass
        except Exception as e:
            print(f"设置场景信息时出现警告: {e}")
            pass
        
        # 设置全局设置
        global_settings = scene.GetGlobalSettings()
        global_settings.SetSystemUnit(fbx.FbxSystemUnit.cm)
        global_settings.SetOriginalSystemUnit(fbx.FbxSystemUnit.cm)
        global_settings.SetTimeMode(fbx.FbxTime.eFrames30)
        
        # 创建根节点
        root_node = scene.GetRootNode()
        
        # 创建网格节点
        mesh_node = fbx.FbxNode.Create(scene, "MeshNode")
        root_node.AddChild(mesh_node)
        
        # 创建网格
        mesh = fbx.FbxMesh.Create(scene, "Mesh")
        mesh_node.SetNodeAttribute(mesh)
        
        # 使用第一帧的数据创建基础网格
        first_frame = mesh_info['data'][0]  # 第一帧数据
        vertices_count = mesh_info['vertices']
        
        # 初始化控制点
        mesh.InitControlPoints(vertices_count)
        control_points = mesh.GetControlPoints()
        
        # 设置顶点位置
        for i in range(vertices_count):
            x, y, z = first_frame[i]
            control_points[i] = fbx.FbxVector4(float(x), float(y), float(z))
        
        # 创建简单的三角形面（如果顶点数足够）
        if vertices_count >= 3:
            # 创建一些基本的三角形面
            face_count = min(vertices_count // 3, 100)  # 限制面数
            for i in range(face_count):
                mesh.BeginPolygon()
                mesh.AddPolygon(i * 3)
                mesh.AddPolygon(i * 3 + 1)
                mesh.AddPolygon(i * 3 + 2)
                mesh.EndPolygon()
        
        # 如果有多帧数据，创建动画
        if mesh_info['frames'] > 1:
            print(f"创建 {mesh_info['frames']} 帧的动画...")
            
            # 创建动画堆栈和层
            anim_stack = fbx.FbxAnimStack.Create(scene, "MeshAnimation")
            anim_layer = fbx.FbxAnimLayer.Create(scene, "BaseLayer")
            anim_stack.AddMember(anim_layer)
            
            # 为每个顶点创建动画曲线
            for vertex_idx in range(min(vertices_count, 50)):  # 限制动画顶点数
                # 创建变形器
                if vertex_idx == 0:  # 只为第一个顶点创建示例动画
                    # 创建位移动画曲线
                    curve_x = mesh_node.LclTranslation.GetCurve(anim_layer, "X", True)
                    curve_y = mesh_node.LclTranslation.GetCurve(anim_layer, "Y", True)
                    curve_z = mesh_node.LclTranslation.GetCurve(anim_layer, "Z", True)
                    
                    # 添加关键帧
                    for frame_idx in range(0, mesh_info['frames'], max(1, mesh_info['frames'] // 30)):
                        time = fbx.FbxTime()
                        time.SetFrame(frame_idx, fbx.FbxTime.eFrames30)
                        
                        vertex_pos = mesh_info['data'][frame_idx][vertex_idx]
                        
                        if curve_x:
                            key_index = curve_x.KeyAdd(time)[0]
                            curve_x.KeySetValue(key_index, float(vertex_pos[0]))
                            curve_x.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
                        
                        if curve_y:
                            key_index = curve_y.KeyAdd(time)[0]
                            curve_y.KeySetValue(key_index, float(vertex_pos[1]))
                            curve_y.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
                        
                        if curve_z:
                            key_index = curve_z.KeyAdd(time)[0]
                            curve_z.KeySetValue(key_index, float(vertex_pos[2]))
                            curve_z.KeySetInterpolation(key_index, fbx.FbxAnimCurveDef.eInterpolationLinear)
        
        # 导出 FBX 文件
        exporter = fbx.FbxExporter.Create(scene, "")
        
        if not exporter.Initialize(output_path, -1, manager.GetIOSettings()):
            print(f"错误: 无法初始化 FBX 导出器")
            return False
        
        # 设置导出格式（使用兼容的格式）
        try:
            # 尝试设置为 FBX 2020 格式
            if hasattr(fbx.FbxIO, 'eFBX_20203_2'):
                exporter.SetFileExportVersion(fbx.FbxIO.eFBX_20203_2)
            elif hasattr(fbx.FbxIO, 'eFBX_2020'):
                exporter.SetFileExportVersion(fbx.FbxIO.eFBX_2020)
            else:
                # 使用默认格式
                pass
        except Exception as e:
            print(f"设置导出格式时出现警告: {e}")
            pass
        
        success = exporter.Export(scene)
        exporter.Destroy()
        
        if success:
            print(f"成功创建 FBX 文件: {output_path}")
            file_size = os.path.getsize(output_path)
            print(f"文件大小: {file_size:,} 字节")
            return True
        else:
            print("FBX 导出失败")
            return False
            
    except Exception as e:
        print(f"创建 FBX 文件时出错: {e}")
        return False
    finally:
        if 'manager' in locals():
            manager.Destroy()

def main():
    """
    主函数
    """
    # 输入和输出文件路径
    pkl_file = r"e:\image_3d\text2dance\output\sample_video\pmce_output.pkl"
    output_fbx = r"e:\image_3d\text2dance\fbx_test_files\mesh_animation_from_pkl.fbx"
    
    print("=== PKL to FBX 转换器 ===")
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
    
    # 处理 pose3d 生成的数据结构
    if isinstance(data, dict):
        success_count = 0
        total_persons = len(data)
        
        for person_id, person_data in data.items():
            print(f"\n=== 处理人物 {person_id} ===")
            
            if not isinstance(person_data, dict):
                print(f"跳过人物 {person_id}: 数据格式不正确")
                continue
            
            # 查找 joints3d 数据
            joints3d_data = None
            if 'joints3d' in person_data:
                joints3d_data = person_data['joints3d']
                print(f"找到 joints3d 数据，形状: {joints3d_data.shape}")
                
                # 为每个人物创建单独的 FBX 文件
                person_output_fbx = output_fbx.replace('.fbx', f'_person_{person_id}.fbx')
                
                # 创建骨骼动画 FBX 文件
                if create_fbx_from_joints3d(joints3d_data, person_output_fbx, person_id):
                    print(f"✅ 人物 {person_id} 的骨骼 FBX 文件创建成功: {person_output_fbx}")
                    success_count += 1
                else:
                    print(f"❌ 人物 {person_id} 的骨骼 FBX 文件创建失败")
                    
            elif 'mesh' in person_data:
                # 如果没有 joints3d，尝试使用 mesh 数据创建网格动画
                mesh_data = person_data['mesh']
                print(f"使用 mesh 数据作为网格数据，形状: {mesh_data.shape}")
                
                # 分析网格数据
                mesh_info = analyze_mesh_data(mesh_data)
                if mesh_info is None:
                    print(f"无法分析人物 {person_id} 的网格数据")
                    continue
                
                # 为每个人物创建单独的 FBX 文件
                person_output_fbx = output_fbx.replace('.fbx', f'_person_{person_id}_mesh.fbx')
                
                # 创建网格动画 FBX 文件
                if create_fbx_from_mesh(mesh_info, person_output_fbx):
                    print(f"✅ 人物 {person_id} 的网格 FBX 文件创建成功: {person_output_fbx}")
                    success_count += 1
                else:
                    print(f"❌ 人物 {person_id} 的网格 FBX 文件创建失败")
            else:
                print(f"人物 {person_id} 没有可用的3D数据（joints3d 或 mesh），跳过")
                continue
        
        if success_count > 0:
            print(f"\n=== 转换完成 ===")
            print(f"成功转换 {success_count}/{total_persons} 个人物")
            print("\n建议:")
            print("1. 在 Maya 中导入生成的 FBX 文件进行测试")
            print("2. 检查骨骼结构和动画")
            print("3. 根据需要调整缩放和位置")
            print("4. 如果文件显示过大，可以在 Maya 中缩放模型")
        else:
            print("\n转换失败: 没有成功转换任何人物数据")
    else:
        print("错误: PKL 文件数据格式不正确，期望字典格式")

if __name__ == "__main__":
    main()