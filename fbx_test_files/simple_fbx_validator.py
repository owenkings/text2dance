#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的FBX文件验证器
验证FBX文件的基本结构和Maya兼容性
"""

import fbx
import FbxCommon
import os
import sys

def validate_fbx_file(fbx_file):
    """验证FBX文件"""
    print(f"🔍 验证FBX文件: {os.path.basename(fbx_file)}")
    print("-" * 60)
    
    if not os.path.exists(fbx_file):
        print("❌ 文件不存在")
        return False
    
    # 文件基本信息
    file_size = os.path.getsize(fbx_file)
    print(f"📊 文件大小: {file_size:,} 字节")
    
    # 检查文件头
    try:
        with open(fbx_file, 'rb') as f:
            header = f.read(32)
            if b'Kaydara FBX Binary' in header:
                print("✅ FBX二进制格式正确")
                
                # 提取版本信息
                f.seek(23)
                version_bytes = f.read(4)
                if len(version_bytes) == 4:
                    version = int.from_bytes(version_bytes, byteorder='little')
                    print(f"📋 FBX版本: {version}")
                    
                    if version == 7700:
                        print("✅ 版本兼容Maya 2020+")
                    elif version == 7400:
                        print("⚠️ 版本较旧，可能存在兼容性问题")
                    else:
                        print(f"❓ 未知版本: {version}")
            else:
                print("❌ 不是有效的FBX二进制文件")
                return False
    except Exception as e:
        print(f"❌ 文件头读取失败: {e}")
        return False
    
    # 尝试使用FBX SDK加载（简化版本）
    try:
        print("\n🧪 FBX SDK基本加载测试:")
        
        # 创建管理器
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
            print("❌ 无法创建场景")
            manager.Destroy()
            return False
        
        # 创建导入器
        importer = fbx.FbxImporter.Create(manager, "")
        
        # 初始化导入器
        if not importer.Initialize(fbx_file, -1, manager.GetIOSettings()):
            print(f"❌ 导入器初始化失败: {importer.GetStatus().GetErrorString()}")
            importer.Destroy()
            manager.Destroy()
            return False
        
        print("✅ 导入器初始化成功")
        
        # 导入场景
        if not importer.Import(scene):
            print(f"❌ 场景导入失败: {importer.GetStatus().GetErrorString()}")
            importer.Destroy()
            manager.Destroy()
            return False
        
        print("✅ 场景导入成功")
        
        # 分析场景内容
        root_node = scene.GetRootNode()
        if root_node:
            node_count = count_nodes_recursive(root_node)
            print(f"📊 场景节点总数: {node_count}")
            
            # 统计不同类型的节点
            skeleton_count = 0
            mesh_count = 0
            null_count = 0
            
            def analyze_node(node):
                nonlocal skeleton_count, mesh_count, null_count
                
                attr = node.GetNodeAttribute()
                if attr:
                    attr_type = attr.GetAttributeType()
                    if attr_type == fbx.FbxNodeAttribute.eSkeleton:
                        skeleton_count += 1
                    elif attr_type == fbx.FbxNodeAttribute.eMesh:
                        mesh_count += 1
                    elif attr_type == fbx.FbxNodeAttribute.eNull:
                        null_count += 1
                
                for i in range(node.GetChildCount()):
                    analyze_node(node.GetChild(i))
            
            analyze_node(root_node)
            
            print(f"🦴 骨骼节点: {skeleton_count}")
            print(f"🔺 网格节点: {mesh_count}")
            print(f"⚪ 空节点: {null_count}")
            
            if skeleton_count > 0:
                print("✅ 包含骨骼结构")
            else:
                print("⚠️ 未检测到骨骼结构")
        
        # 清理资源
        importer.Destroy()
        manager.Destroy()
        
        print("✅ FBX文件验证通过")
        return True
        
    except Exception as e:
        print(f"❌ FBX SDK测试失败: {e}")
        return False

def count_nodes_recursive(node):
    """递归计算节点数量"""
    count = 1  # 当前节点
    for i in range(node.GetChildCount()):
        count += count_nodes_recursive(node.GetChild(i))
    return count

def main():
    """主函数"""
    print("🧪 FBX文件验证器")
    print("=" * 70)
    
    # 要验证的文件列表
    files_to_validate = [
        "fbx_test_files\\maya_compatible_skeleton_v7700.fbx",
        "fbx_test_files\\official_fbx_test.fbx",
        "fbx_test_files\\maya_test.fbx\\fbx_output\\person_0001_skeleton.fbx"
    ]
    
    results = {}
    
    for fbx_file in files_to_validate:
        if os.path.exists(fbx_file):
            print(f"\n{'='*70}")
            success = validate_fbx_file(fbx_file)
            results[fbx_file] = success
        else:
            print(f"\n⚠️ 文件不存在: {fbx_file}")
            results[fbx_file] = False
    
    # 总结报告
    print(f"\n{'='*70}")
    print("📋 验证结果总结:")
    print("-" * 70)
    
    for fbx_file, success in results.items():
        filename = os.path.basename(fbx_file)
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {filename:<40} {status}")
    
    # Maya导入建议
    successful_files = [f for f, success in results.items() if success]
    if successful_files:
        print("\n🎯 Maya导入测试建议:")
        print("-" * 70)
        for fbx_file in successful_files:
            filename = os.path.basename(fbx_file)
            print(f"✅ 推荐测试: {filename}")
        
        print("\n📋 Maya导入步骤:")
        print("1. 打开Maya 2020或更高版本")
        print("2. File -> Import -> 选择上述推荐文件")
        print("3. 在Outliner中检查骨骼层次结构")
        print("4. 在Viewport中查看骨骼显示")
        print("5. 测试骨骼选择和操作")
    else:
        print("\n❌ 没有文件通过验证，建议检查FBX生成过程")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())