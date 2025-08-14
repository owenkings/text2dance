#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FBX文件详细对比分析工具
对比参考FBX文件与用户生成的FBX文件，找出Maya兼容性问题
"""

import os
import sys
from pathlib import Path

def analyze_fbx_binary_header(filepath):
    """分析FBX二进制文件头部信息"""
    try:
        with open(filepath, 'rb') as f:
            # 读取前100字节
            header = f.read(100)
            
        # 检查FBX签名
        if not header.startswith(b'Kaydara FBX Binary'):
            return {"error": "不是有效的FBX二进制文件"}
        
        # 解析版本信息
        version_bytes = header[23:27]
        version = int.from_bytes(version_bytes, byteorder='little')
        
        # 解析文件大小信息
        file_size = os.path.getsize(filepath)
        
        return {
            "signature": header[:21].decode('ascii', errors='ignore'),
            "version": version,
            "file_size": file_size,
            "header_hex": header.hex()[:200]  # 前100字节的十六进制表示
        }
        
    except Exception as e:
        return {"error": f"读取文件失败: {str(e)}"}

def test_fbx_with_official_sdk(filepath):
    """使用官方FBX SDK测试文件兼容性"""
    try:
        import fbx
        
        # 创建管理器
        manager = fbx.FbxManager.Create()
        if not manager:
            return {"success": False, "error": "无法创建FBX管理器"}
        
        # 创建IO设置
        ios = fbx.FbxIOSettings.Create(manager, fbx.IOSROOT)
        manager.SetIOSettings(ios)
        
        # 创建场景
        scene = fbx.FbxScene.Create(manager, "TestScene")
        if not scene:
            manager.Destroy()
            return {"success": False, "error": "无法创建FBX场景"}
        
        # 创建导入器
        importer = fbx.FbxImporter.Create(manager, "")
        
        # 初始化导入器
        if not importer.Initialize(filepath, -1, manager.GetIOSettings()):
            error_msg = importer.GetStatus().GetErrorString()
            importer.Destroy()
            manager.Destroy()
            return {"success": False, "error": f"导入器初始化失败: {error_msg}"}
        
        # 导入场景
        result = importer.Import(scene)
        
        if result:
            # 分析场景内容
            root_node = scene.GetRootNode()
            analysis = analyze_scene_structure(root_node)
            analysis["success"] = True
        else:
            analysis = {"success": False, "error": "导入场景失败"}
        
        # 清理资源
        importer.Destroy()
        manager.Destroy()
        
        return analysis
        
    except ImportError:
        return {"success": False, "error": "FBX SDK未安装"}
    except Exception as e:
        return {"success": False, "error": f"测试出错: {str(e)}"}

def analyze_scene_structure(root_node):
    """分析FBX场景结构"""
    import fbx
    
    structure = {
        "total_nodes": 0,
        "skeleton_nodes": 0,
        "mesh_nodes": 0,
        "material_nodes": 0,
        "node_hierarchy": [],
        "skeleton_info": []
    }
    
    def traverse_node(node, level=0):
        structure["total_nodes"] += 1
        
        # 获取节点信息
        node_name = node.GetName()
        node_info = {
            "name": node_name,
            "level": level,
            "type": "Unknown",
            "transform": get_node_transform(node)
        }
        
        # 检查节点属性
        attr = node.GetNodeAttribute()
        if attr:
            attr_type = attr.GetAttributeType()
            if attr_type == fbx.FbxNodeAttribute.eSkeleton:
                structure["skeleton_nodes"] += 1
                node_info["type"] = "Skeleton"
                
                # 获取骨骼类型
                skeleton = fbx.FbxSkeleton(attr)
                skeleton_type = skeleton.GetSkeletonType()
                if skeleton_type == fbx.FbxSkeleton.eRoot:
                    node_info["skeleton_type"] = "Root"
                elif skeleton_type == fbx.FbxSkeleton.eLimbNode:
                    node_info["skeleton_type"] = "LimbNode"
                else:
                    node_info["skeleton_type"] = "Other"
                    
                structure["skeleton_info"].append(node_info)
                
            elif attr_type == fbx.FbxNodeAttribute.eMesh:
                structure["mesh_nodes"] += 1
                node_info["type"] = "Mesh"
            elif attr_type == fbx.FbxNodeAttribute.eMaterial:
                structure["material_nodes"] += 1
                node_info["type"] = "Material"
        
        structure["node_hierarchy"].append(node_info)
        
        # 递归处理子节点
        for i in range(node.GetChildCount()):
            traverse_node(node.GetChild(i), level + 1)
    
    traverse_node(root_node)
    return structure

def get_node_transform(node):
    """获取节点变换信息"""
    translation = node.LclTranslation.Get()
    rotation = node.LclRotation.Get()
    scaling = node.LclScaling.Get()
    
    return {
        "translation": [translation[0], translation[1], translation[2]],
        "rotation": [rotation[0], rotation[1], rotation[2]],
        "scaling": [scaling[0], scaling[1], scaling[2]]
    }

def compare_fbx_files(reference_file, user_file):
    """对比两个FBX文件"""
    print("🔍 FBX文件详细对比分析")
    print("=" * 60)
    
    files = [
        (reference_file, "参考文件（Maya兼容）"),
        (user_file, "用户生成文件")
    ]
    
    results = {}
    
    print("\n📋 基本信息分析:")
    print("-" * 40)
    
    for filepath, description in files:
        print(f"\n📁 {description}: {filepath}")
        
        if not os.path.exists(filepath):
            print("   ❌ 文件不存在")
            results[description] = {"exists": False}
            continue
        
        # 分析文件头部
        header_info = analyze_fbx_binary_header(filepath)
        if "error" in header_info:
            print(f"   ❌ {header_info['error']}")
            results[description] = {"exists": True, "valid": False, "error": header_info["error"]}
            continue
        
        print(f"   文件大小: {header_info['file_size']:,} 字节")
        print(f"   FBX版本: {header_info['version']}")
        print(f"   签名: {header_info['signature']}")
        
        results[description] = {
            "exists": True,
            "valid": True,
            "header": header_info
        }
    
    print("\n\n🧪 FBX SDK兼容性测试:")
    print("-" * 40)
    
    for filepath, description in files:
        if not results[description].get("valid", False):
            continue
            
        print(f"\n🔬 测试 {description}:")
        sdk_test = test_fbx_with_official_sdk(filepath)
        
        if sdk_test["success"]:
            print("   ✅ FBX SDK导入成功")
            print(f"   📊 总节点数: {sdk_test['total_nodes']}")
            print(f"   🦴 骨骼节点数: {sdk_test['skeleton_nodes']}")
            print(f"   🎭 网格节点数: {sdk_test['mesh_nodes']}")
            
            if sdk_test['skeleton_info']:
                print("   🦴 骨骼层次结构:")
                for skeleton in sdk_test['skeleton_info']:
                    indent = "     " + "  " * skeleton['level']
                    skel_type = skeleton.get('skeleton_type', 'Unknown')
                    print(f"{indent}- {skeleton['name']} ({skel_type})")
        else:
            print(f"   ❌ FBX SDK导入失败: {sdk_test['error']}")
        
        results[description]["sdk_test"] = sdk_test
    
    print("\n\n📊 对比分析结果:")
    print("=" * 60)
    
    # 对比文件版本
    ref_result = results.get("参考文件（Maya兼容）", {})
    user_result = results.get("用户生成文件", {})
    
    if ref_result.get("valid") and user_result.get("valid"):
        ref_version = ref_result["header"]["version"]
        user_version = user_result["header"]["version"]
        
        print(f"\n🔢 FBX版本对比:")
        print(f"   参考文件版本: {ref_version}")
        print(f"   用户文件版本: {user_version}")
        
        if ref_version != user_version:
            print("   ⚠️ 版本不匹配可能导致兼容性问题")
        else:
            print("   ✅ 版本匹配")
        
        # 对比文件大小
        ref_size = ref_result["header"]["file_size"]
        user_size = user_result["header"]["file_size"]
        
        print(f"\n📏 文件大小对比:")
        print(f"   参考文件: {ref_size:,} 字节")
        print(f"   用户文件: {user_size:,} 字节")
        print(f"   大小比例: {user_size/ref_size:.2f}")
        
        # 对比SDK测试结果
        ref_sdk = ref_result.get("sdk_test", {})
        user_sdk = user_result.get("sdk_test", {})
        
        if ref_sdk.get("success") and user_sdk.get("success"):
            print(f"\n🏗️ 结构对比:")
            print(f"   参考文件 - 节点数: {ref_sdk['total_nodes']}, 骨骼数: {ref_sdk['skeleton_nodes']}")
            print(f"   用户文件 - 节点数: {user_sdk['total_nodes']}, 骨骼数: {user_sdk['skeleton_nodes']}")
            
            if ref_sdk['skeleton_nodes'] != user_sdk['skeleton_nodes']:
                print("   ⚠️ 骨骼数量不匹配")
        elif ref_sdk.get("success") and not user_sdk.get("success"):
            print(f"\n❌ 关键问题: 用户文件无法被FBX SDK正确解析")
            print(f"   错误信息: {user_sdk.get('error', '未知错误')}")
    
    print("\n\n💡 问题诊断与建议:")
    print("=" * 60)
    
    if not user_result.get("valid", False):
        print("❌ 用户文件格式错误或损坏")
        print("建议: 检查FBX生成代码，确保正确的文件格式")
    elif not user_result.get("sdk_test", {}).get("success", False):
        error_msg = user_result.get("sdk_test", {}).get("error", "")
        print(f"❌ 用户文件无法被FBX SDK解析: {error_msg}")
        
        if "Unexpected file type" in error_msg:
            print("建议: 文件格式可能不标准，检查FBX生成器的格式输出")
        elif "导入场景失败" in error_msg:
            print("建议: 文件结构可能有问题，检查节点层次和属性设置")
        else:
            print("建议: 使用官方FBX SDK重新生成文件")
    else:
        print("✅ 用户文件格式正确，可能是Maya特定的兼容性问题")
        print("建议: 检查Maya导入设置，或尝试不同的FBX版本")

def main():
    """主函数"""
    reference_file = "e:\\image_3d\\text2dance\\data\\jingang_13_c+_004.fbx"
    user_file = "e:\\image_3d\\text2dance\\output\\sample_video\\fbx_output\\person_0001_skeleton.fbx"
    new_compatible_file = "e:\\image_3d\\text2dance\\maya_compatible_skeleton_v7700.fbx"
    
    compare_fbx_files(reference_file, user_file)
    
    # 测试新生成的Maya兼容文件
    print("\n\n🔬 测试新生成的Maya兼容文件:")
    print("=" * 60)
    compare_fbx_files(reference_file, new_compatible_file)

if __name__ == "__main__":
    main()