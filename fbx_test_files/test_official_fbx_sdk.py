#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试官方FBX SDK功能
使用官方FBX SDK创建一个简单的骨骼动画文件
"""

import fbx
import FbxCommon
import os
import sys

def create_fbx_with_official_sdk():
    """使用官方FBX SDK创建FBX文件"""
    print("🚀 开始使用官方FBX SDK创建FBX文件...")
    
    # 创建FBX管理器
    manager = fbx.FbxManager.Create()
    if not manager:
        print("❌ 无法创建FBX管理器")
        return False
    
    # 创建IO设置
    ios = fbx.FbxIOSettings.Create(manager, fbx.IOSROOT)
    manager.SetIOSettings(ios)
    
    # 创建场景
    scene = fbx.FbxScene.Create(manager, "TestScene")
    if not scene:
        print("❌ 无法创建FBX场景")
        return False
    
    print("✅ FBX管理器和场景创建成功")
    
    # 创建根节点
    root_node = scene.GetRootNode()
    
    # 创建骨骼层次结构
    joints = create_skeleton_hierarchy(scene, root_node)
    
    # 保存文件
    output_file = "official_fbx_test.fbx"
    success = save_fbx_file(manager, scene, output_file)
    
    # 清理资源
    manager.Destroy()
    
    if success:
        print(f"🎉 FBX文件创建成功: {output_file}")
        # 检查文件大小
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"📊 文件大小: {file_size} 字节")
        return True
    else:
        print("❌ FBX文件创建失败")
        return False

def create_skeleton_hierarchy(scene, root_node):
    """创建骨骼层次结构"""
    print("🦴 创建骨骼层次结构...")
    
    joints = {}
    
    # 定义COCO关键点的子集（简化版本）
    joint_hierarchy = {
        'root': {'parent': None, 'position': (0, 0, 0)},
        'spine': {'parent': 'root', 'position': (0, 50, 0)},
        'neck': {'parent': 'spine', 'position': (0, 100, 0)},
        'head': {'parent': 'neck', 'position': (0, 120, 0)},
        'left_shoulder': {'parent': 'spine', 'position': (-20, 90, 0)},
        'left_elbow': {'parent': 'left_shoulder', 'position': (-40, 70, 0)},
        'left_wrist': {'parent': 'left_elbow', 'position': (-60, 50, 0)},
        'right_shoulder': {'parent': 'spine', 'position': (20, 90, 0)},
        'right_elbow': {'parent': 'right_shoulder', 'position': (40, 70, 0)},
        'right_wrist': {'parent': 'right_elbow', 'position': (60, 50, 0)},
        'left_hip': {'parent': 'root', 'position': (-10, 0, 0)},
        'left_knee': {'parent': 'left_hip', 'position': (-10, -40, 0)},
        'left_ankle': {'parent': 'left_knee', 'position': (-10, -80, 0)},
        'right_hip': {'parent': 'root', 'position': (10, 0, 0)},
        'right_knee': {'parent': 'right_hip', 'position': (10, -40, 0)},
        'right_ankle': {'parent': 'right_knee', 'position': (10, -80, 0)}
    }
    
    # 创建骨骼节点
    for joint_name, joint_info in joint_hierarchy.items():
        # 创建骨骼属性
        skeleton_attr = fbx.FbxSkeleton.Create(scene, f"{joint_name}_skeleton")
        
        if joint_info['parent'] is None:
            # 根骨骼
            skeleton_attr.SetSkeletonType(fbx.FbxSkeleton.eRoot)
        else:
            # 肢体骨骼
            skeleton_attr.SetSkeletonType(fbx.FbxSkeleton.eLimbNode)
        
        # 创建节点
        joint_node = fbx.FbxNode.Create(scene, joint_name)
        joint_node.SetNodeAttribute(skeleton_attr)
        
        # 设置位置
        pos = joint_info['position']
        joint_node.LclTranslation.Set(fbx.FbxDouble3(pos[0], pos[1], pos[2]))
        
        joints[joint_name] = joint_node
        
        # 建立父子关系
        if joint_info['parent'] is None:
            root_node.AddChild(joint_node)
        else:
            parent_joint = joints[joint_info['parent']]
            parent_joint.AddChild(joint_node)
        
        print(f"  ✅ 创建关节: {joint_name}")
    
    print(f"🎯 骨骼层次结构创建完成，共 {len(joints)} 个关节")
    return joints

def save_fbx_file(manager, scene, filename):
    """保存FBX文件"""
    print(f"💾 保存FBX文件: {filename}")
    
    # 创建导出器
    exporter = fbx.FbxExporter.Create(manager, "")
    
    # 初始化导出器
    if not exporter.Initialize(filename, -1, manager.GetIOSettings()):
        print(f"❌ 无法初始化导出器: {exporter.GetStatus().GetErrorString()}")
        return False
    
    # 导出场景
    result = exporter.Export(scene)
    
    # 清理导出器
    exporter.Destroy()
    
    if result:
        print("✅ FBX文件保存成功")
        return True
    else:
        print("❌ FBX文件保存失败")
        return False

def compare_with_custom_generator():
    """与自制FBX生成器进行对比"""
    print("\n📊 对比分析:")
    print("=" * 50)
    
    files_to_check = [
        ("official_fbx_test.fbx", "官方FBX SDK生成"),
        ("person_0001_skeleton.fbx", "自制FBX生成器")
    ]
    
    for filename, description in files_to_check:
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"📁 {description}: {filename}")
            print(f"   文件大小: {file_size:,} 字节")
        else:
            print(f"❌ {description}: {filename} (文件不存在)")
    
    print("\n💡 建议:")
    print("1. 在Maya中测试两个文件的导入效果")
    print("2. 检查骨骼层次结构是否正确")
    print("3. 验证动画兼容性")

def main():
    """主函数"""
    print("🧪 官方FBX SDK测试程序")
    print("=" * 50)
    
    try:
        # 测试FBX SDK版本信息
        try:
            version = fbx.FbxManager.GetVersion()
            print(f"📋 FBX SDK版本: {version}")
        except AttributeError:
            print("📋 FBX SDK版本: 无法获取版本信息")
        
        # 创建FBX文件
        success = create_fbx_with_official_sdk()
        
        if success:
            # 对比分析
            compare_with_custom_generator()
            
            print("\n🎉 测试完成！")
            print("\n📋 Maya导入测试步骤:")
            print("1. 打开Maya")
            print("2. File -> Import -> 选择 official_fbx_test.fbx")
            print("3. 检查Outliner中的骨骼层次结构")
            print("4. 与之前的 person_0001_skeleton.fbx 进行对比")
        else:
            print("❌ 测试失败")
            return 1
            
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())