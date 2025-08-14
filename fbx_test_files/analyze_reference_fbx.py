#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析参考FBX文件结构
"""

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
    sys.exit(1)

def analyze_fbx_file(fbx_path):
    """
    分析FBX文件结构
    """
    if not os.path.exists(fbx_path):
        print(f"文件不存在: {fbx_path}")
        return
    
    try:
        # 创建FBX管理器
        manager = fbx.FbxManager.Create()
        
        # 创建导入器
        importer = fbx.FbxImporter.Create(manager, "")
        
        # 初始化导入器
        if not importer.Initialize(fbx_path, -1, manager.GetIOSettings()):
            print(f"无法初始化导入器: {fbx_path}")
            return
        
        # 创建场景
        scene = fbx.FbxScene.Create(manager, "ImportedScene")
        
        # 导入场景
        importer.Import(scene)
        importer.Destroy()
        
        print(f"=== 分析FBX文件: {fbx_path} ===")
        
        # 分析场景信息
        print(f"\n场景名称: {scene.GetName()}")
        
        # 分析根节点
        root_node = scene.GetRootNode()
        print(f"根节点: {root_node.GetName()}")
        print(f"子节点数量: {root_node.GetChildCount()}")
        
        # 递归分析节点结构
        def analyze_node(node, depth=0):
            indent = "  " * depth
            print(f"{indent}节点: {node.GetName()}")
            
            # 分析节点属性
            attr = node.GetNodeAttribute()
            if attr:
                attr_type = attr.GetAttributeType()
                type_names = {
                    fbx.FbxNodeAttribute.eUnknown: "Unknown",
                    fbx.FbxNodeAttribute.eNull: "Null",
                    fbx.FbxNodeAttribute.eMarker: "Marker",
                    fbx.FbxNodeAttribute.eSkeleton: "Skeleton",
                    fbx.FbxNodeAttribute.eMesh: "Mesh",
                    fbx.FbxNodeAttribute.eNurbs: "Nurbs",
                    fbx.FbxNodeAttribute.ePatch: "Patch",
                    fbx.FbxNodeAttribute.eCamera: "Camera",
                    fbx.FbxNodeAttribute.eCameraStereo: "CameraStereo",
                    fbx.FbxNodeAttribute.eCameraSwitcher: "CameraSwitcher",
                    fbx.FbxNodeAttribute.eLight: "Light",
                    fbx.FbxNodeAttribute.eOpticalReference: "OpticalReference",
                    fbx.FbxNodeAttribute.eOpticalMarker: "OpticalMarker",
                    fbx.FbxNodeAttribute.eNurbsCurve: "NurbsCurve",
                    fbx.FbxNodeAttribute.eTrimNurbsSurface: "TrimNurbsSurface",
                    fbx.FbxNodeAttribute.eBoundary: "Boundary",
                    fbx.FbxNodeAttribute.eNurbsSurface: "NurbsSurface",
                    fbx.FbxNodeAttribute.eShape: "Shape",
                    fbx.FbxNodeAttribute.eLODGroup: "LODGroup",
                    fbx.FbxNodeAttribute.eSubDiv: "SubDiv"
                }
                type_name = type_names.get(attr_type, f"Unknown({attr_type})")
                print(f"{indent}  属性类型: {type_name}")
                
                # 如果是网格，分析网格信息
                if attr_type == fbx.FbxNodeAttribute.eMesh:
                    mesh = node.GetMesh()
                    if mesh:
                        print(f"{indent}  顶点数: {mesh.GetControlPointsCount()}")
                        print(f"{indent}  多边形数: {mesh.GetPolygonCount()}")
                        
                        # 检查是否有蒙皮
                        deformer_count = mesh.GetDeformerCount()
                        print(f"{indent}  变形器数量: {deformer_count}")
                        
                        for i in range(deformer_count):
                            deformer = mesh.GetDeformer(i)
                            if deformer:
                                deformer_type = deformer.GetDeformerType()
                                if deformer_type == fbx.FbxDeformer.eSkin:
                                    try:
                                        skin = deformer
                                        cluster_count = skin.GetClusterCount()
                                        print(f"{indent}    蒙皮变形器，簇数量: {cluster_count}")
                                    except:
                                        print(f"{indent}    蒙皮变形器（无法获取详细信息）")
                
                # 如果是骨骼，分析骨骼信息
                elif attr_type == fbx.FbxNodeAttribute.eSkeleton:
                    try:
                        skeleton = attr
                        skel_type = skeleton.GetSkeletonType()
                        type_names = {
                            fbx.FbxSkeleton.eRoot: "Root",
                            fbx.FbxSkeleton.eLimb: "Limb",
                            fbx.FbxSkeleton.eLimbNode: "LimbNode",
                            fbx.FbxSkeleton.eEffector: "Effector"
                        }
                        skel_type_name = type_names.get(skel_type, f"Unknown({skel_type})")
                        print(f"{indent}  骨骼类型: {skel_type_name}")
                        print(f"{indent}  大小: {skeleton.Size.Get()}")
                    except Exception as e:
                        print(f"{indent}  骨骼信息获取失败: {e}")
            
            # 分析变换
            translation = node.LclTranslation.Get()
            rotation = node.LclRotation.Get()
            scaling = node.LclScaling.Get()
            print(f"{indent}  位置: ({translation[0]:.3f}, {translation[1]:.3f}, {translation[2]:.3f})")
            print(f"{indent}  旋转: ({rotation[0]:.3f}, {rotation[1]:.3f}, {rotation[2]:.3f})")
            print(f"{indent}  缩放: ({scaling[0]:.3f}, {scaling[1]:.3f}, {scaling[2]:.3f})")
            
            # 递归分析子节点
            for i in range(node.GetChildCount()):
                child = node.GetChild(i)
                analyze_node(child, depth + 1)
        
        # 分析所有子节点
        for i in range(root_node.GetChildCount()):
            child = root_node.GetChild(i)
            analyze_node(child)
        
        # 分析动画
        anim_stack_count = scene.GetSrcObjectCount(fbx.FbxAnimStack.ClassId)
        print(f"\n动画堆栈数量: {anim_stack_count}")
        
        for i in range(anim_stack_count):
            anim_stack = scene.GetSrcObject(fbx.FbxAnimStack.ClassId, i)
            if anim_stack:
                print(f"  动画堆栈 {i}: {anim_stack.GetName()}")
                
                # 分析动画层
                layer_count = anim_stack.GetMemberCount(fbx.FbxAnimLayer.ClassId)
                print(f"    动画层数量: {layer_count}")
        
        manager.Destroy()
        
    except Exception as e:
        print(f"分析FBX文件时出错: {e}")
        if 'manager' in locals():
            manager.Destroy()

def main():
    reference_fbx = r"e:\image_3d\text2dance\fbx_test_files\jingang_13_c+_004.fbx"
    current_fbx = r"e:\image_3d\text2dance\fbx_test_files\mesh_animation_from_pkl_person_1.fbx"
    
    print("=== 分析参考FBX文件 ===")
    analyze_fbx_file(reference_fbx)
    
    print("\n" + "="*50 + "\n")
    
    print("=== 分析当前生成的FBX文件 ===")
    analyze_fbx_file(current_fbx)

if __name__ == "__main__":
    main()