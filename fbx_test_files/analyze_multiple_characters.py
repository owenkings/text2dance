#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析FBX文件中是否包含多个人物角色
检查骨骼结构和网格数量
"""

import fbx
import sys

def analyze_fbx_characters(fbx_file_path):
    """
    分析FBX文件中的角色数量和结构
    """
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
        
        print(f"\n=== 分析FBX文件: {fbx_file_path} ===")
        
        # 获取根节点
        root_node = scene.GetRootNode()
        
        # 统计不同类型的节点
        skeleton_roots = []
        mesh_nodes = []
        all_skeleton_nodes = []
        
        def traverse_node(node, depth=0):
            indent = "  " * depth
            node_name = node.GetName()
            
            # 检查节点属性
            attribute = node.GetNodeAttribute()
            if attribute:
                attr_type = attribute.GetAttributeType()
                
                if attr_type == fbx.FbxNodeAttribute.eSkeleton:
                    all_skeleton_nodes.append(node)
                    # 检查是否是骨骼根节点（通常是Hips或类似名称）
                    if any(keyword in node_name.lower() for keyword in ['hips', 'pelvis', 'root', 'skeleton']):
                        if depth <= 2:  # 只考虑较浅层级的根节点
                            skeleton_roots.append(node)
                    
                    print(f"{indent}骨骼节点: {node_name} (深度: {depth})")
                    
                elif attr_type == fbx.FbxNodeAttribute.eMesh:
                    mesh_nodes.append(node)
                    print(f"{indent}网格节点: {node_name}")
                    
                    # 分析网格的蒙皮信息
                    mesh = attribute
                    deformer_count = mesh.GetDeformerCount()
                    print(f"{indent}  - 变形器数量: {deformer_count}")
                    
                    for i in range(deformer_count):
                        deformer = mesh.GetDeformer(i)
                        if deformer.GetDeformerType() == fbx.FbxDeformer.eSkin:
                            skin = fbx.FbxCast.FbxSkin(deformer)
                            cluster_count = skin.GetClusterCount()
                            print(f"{indent}  - 蒙皮簇数量: {cluster_count}")
            
            # 递归遍历子节点
            for i in range(node.GetChildCount()):
                traverse_node(node.GetChild(i), depth + 1)
        
        # 开始遍历
        traverse_node(root_node)
        
        print(f"\n=== 统计结果 ===")
        print(f"总骨骼节点数量: {len(all_skeleton_nodes)}")
        print(f"可能的骨骼根节点数量: {len(skeleton_roots)}")
        print(f"网格节点数量: {len(mesh_nodes)}")
        
        print(f"\n=== 骨骼根节点详情 ===")
        for i, root in enumerate(skeleton_roots):
            print(f"根节点 {i+1}: {root.GetName()}")
            
            # 统计该根节点下的骨骼数量
            def count_skeleton_children(node):
                count = 0
                if node.GetNodeAttribute() and node.GetNodeAttribute().GetAttributeType() == fbx.FbxNodeAttribute.eSkeleton:
                    count = 1
                for j in range(node.GetChildCount()):
                    count += count_skeleton_children(node.GetChild(j))
                return count
            
            skeleton_count = count_skeleton_children(root)
            print(f"  - 该根节点下骨骼数量: {skeleton_count}")
        
        print(f"\n=== 网格节点详情 ===")
        for i, mesh_node in enumerate(mesh_nodes):
            print(f"网格 {i+1}: {mesh_node.GetName()}")
            
            # 获取网格的顶点数量
            mesh = mesh_node.GetNodeAttribute()
            if mesh:
                vertex_count = mesh.GetControlPointsCount()
                polygon_count = mesh.GetPolygonCount()
                print(f"  - 顶点数量: {vertex_count}")
                print(f"  - 多边形数量: {polygon_count}")
        
        # 判断是否有多个角色
        print(f"\n=== 角色数量分析 ===")
        if len(skeleton_roots) > 1:
            print(f"⚠️  检测到 {len(skeleton_roots)} 个可能的骨骼根节点，可能包含多个角色！")
            print("建议：需要选择特定的角色进行比例分析")
        elif len(skeleton_roots) == 1:
            print("✅ 检测到单一骨骼根节点，应该是单个角色")
        else:
            print("❌ 未检测到明确的骨骼根节点")
        
        if len(mesh_nodes) > 1:
            print(f"⚠️  检测到 {len(mesh_nodes)} 个网格节点，可能包含多个角色的网格！")
        
    except Exception as e:
        print(f"分析过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        importer.Destroy()
        manager.Destroy()

if __name__ == "__main__":
    # 分析参考FBX文件
    reference_fbx = r"e:\image_3d\text2dance\fbx_test_files\jingang_13_c+_004.fbx"
    
    print("开始分析参考FBX文件中的角色数量...")
    analyze_fbx_characters(reference_fbx)