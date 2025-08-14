#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FBX文件对比分析工具
对比官方FBX SDK生成的文件与自制生成器的文件
"""

import os
import sys
from pathlib import Path

def analyze_fbx_file(filepath):
    """分析FBX文件的基本信息"""
    if not os.path.exists(filepath):
        return None
    
    file_size = os.path.getsize(filepath)
    
    # 尝试读取文件内容进行基本分析
    try:
        with open(filepath, 'rb') as f:
            content = f.read(1024)  # 读取前1KB
            
        # 检查是否是二进制FBX
        is_binary = content.startswith(b'Kaydara FBX Binary')
        
        # 检查是否是ASCII FBX
        is_ascii = b'FBXHeaderExtension' in content or b'; FBX' in content
        
        file_type = "Unknown"
        if is_binary:
            file_type = "Binary FBX"
        elif is_ascii:
            file_type = "ASCII FBX"
        
        return {
            'size': file_size,
            'type': file_type,
            'readable': True
        }
        
    except Exception as e:
        return {
            'size': file_size,
            'type': "Error reading file",
            'readable': False,
            'error': str(e)
        }

def test_fbx_with_official_sdk(filepath):
    """使用官方FBX SDK测试文件"""
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
            node_count = count_nodes(root_node)
            skeleton_count = count_skeletons(root_node)
            
            analysis = {
                "success": True,
                "nodes": node_count,
                "skeletons": skeleton_count
            }
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

def count_nodes(node, count=0):
    """递归计算节点数量"""
    count += 1
    for i in range(node.GetChildCount()):
        count = count_nodes(node.GetChild(i), count)
    return count

def count_skeletons(node, count=0):
    """递归计算骨骼数量"""
    import fbx
    
    # 检查当前节点是否是骨骼
    attr = node.GetNodeAttribute()
    if attr and attr.GetAttributeType() == fbx.FbxNodeAttribute.eSkeleton:
        count += 1
    
    # 递归检查子节点
    for i in range(node.GetChildCount()):
        count = count_skeletons(node.GetChild(i), count)
    
    return count

def generate_maya_import_guide():
    """生成Maya导入指南"""
    guide = """
📋 Maya导入测试指南
===================

🎯 测试步骤:
1. 打开Maya 2020或更高版本
2. File -> Import -> 选择FBX文件
3. 在Import Options中确保以下设置:
   - Animation: ON (如果需要动画)
   - Deformed Models: ON
   - Skins: ON
   - Blend Shapes: ON
   - Curve Filters: ON
   - Sampling Rate: 30fps

🔍 验证检查:
1. 检查Outliner中的层次结构
2. 选择根骨骼，查看整个骨骼链
3. 在Component Mode下检查骨骼连接
4. 使用Joint Tool验证关节方向
5. 检查是否有错误或警告信息

✅ 成功标准:
- 所有骨骼正确导入
- 层次结构完整
- 没有错误信息
- 骨骼可以正常选择和操作

❌ 常见问题:
- 骨骼层次结构错误
- 关节方向不正确
- 缺少骨骼连接
- 导入时出现警告
"""
    return guide

def main():
    """主函数"""
    print("📊 FBX文件对比分析工具")
    print("=" * 60)
    
    # 要分析的FBX文件列表
    fbx_files = [
        ("official_fbx_test.fbx", "官方FBX SDK生成"),
        ("simple_test.fbx", "自制生成器 - 简单测试"),
        ("test_cube.fbx", "自制生成器 - 立方体测试"),
        ("person_0001_skeleton.fbx", "自制生成器 - 人体骨骼"),
        ("maya_test.fbx", "Maya测试文件")
    ]
    
    results = []
    
    print("\n🔍 文件基本信息分析:")
    print("-" * 60)
    
    for filepath, description in fbx_files:
        print(f"\n📁 {description}: {filepath}")
        
        analysis = analyze_fbx_file(filepath)
        if analysis:
            print(f"   文件大小: {analysis['size']:,} 字节")
            print(f"   文件类型: {analysis['type']}")
            print(f"   可读性: {'✅' if analysis['readable'] else '❌'}")
            
            if not analysis['readable'] and 'error' in analysis:
                print(f"   错误: {analysis['error']}")
        else:
            print("   状态: ❌ 文件不存在")
            analysis = {'exists': False}
        
        results.append((filepath, description, analysis))
    
    print("\n\n🧪 官方FBX SDK兼容性测试:")
    print("-" * 60)
    
    for filepath, description, basic_analysis in results:
        if basic_analysis and basic_analysis.get('readable', False):
            print(f"\n🔬 测试 {description}:")
            sdk_test = test_fbx_with_official_sdk(filepath)
            
            if sdk_test['success']:
                print("   ✅ FBX SDK导入成功")
                print(f"   📊 节点数量: {sdk_test['nodes']}")
                print(f"   🦴 骨骼数量: {sdk_test['skeletons']}")
            else:
                print(f"   ❌ FBX SDK导入失败: {sdk_test['error']}")
    
    print("\n\n📈 总结报告:")
    print("=" * 60)
    
    # 统计成功的文件
    existing_files = [r for r in results if r[2] and r[2].get('readable', False)]
    
    print(f"📊 文件统计:")
    print(f"   总文件数: {len(fbx_files)}")
    print(f"   存在文件: {len(existing_files)}")
    print(f"   可读文件: {len([r for r in existing_files if r[2]['readable']])}")
    
    if existing_files:
        print(f"\n📁 推荐用于Maya测试的文件:")
        for filepath, description, analysis in existing_files:
            if analysis['readable'] and analysis['size'] > 1000:  # 过滤掉太小的文件
                print(f"   ✅ {filepath} ({description})")
    
    print("\n" + generate_maya_import_guide())
    
    print("\n🎯 下一步建议:")
    print("1. 在Maya中测试推荐的FBX文件")
    print("2. 对比官方SDK和自制生成器的效果")
    print("3. 根据测试结果选择最佳的生成方案")
    print("4. 如果需要，可以进一步优化FBX生成器")

if __name__ == "__main__":
    main()