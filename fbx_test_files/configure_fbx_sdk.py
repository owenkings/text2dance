#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FBX SDK Python绑定配置脚本
帮助用户配置已安装的FBX SDK的Python绑定
"""

import os
import sys
import shutil
import site
import glob

def find_fbx_sdk_installation():
    """查找FBX SDK安装路径"""
    possible_paths = [
        "E:\\fbx_sdk_install",
        "C:\\Program Files\\Autodesk\\FBX\\FBX SDK",
        "C:\\Program Files (x86)\\Autodesk\\FBX\\FBX SDK",
    ]
    
    found_paths = []
    
    for base_path in possible_paths:
        if os.path.exists(base_path):
            print(f"✅ 找到FBX SDK安装目录: {base_path}")
            
            # 查找Python绑定目录
            python_dirs = []
            
            # 递归查找包含Python绑定的目录
            for root, dirs, files in os.walk(base_path):
                # 检查必需的文件是否存在
                required_files = ['fbx.pyd', 'fbxsip.pyd', 'FbxCommon.py']
                if all(f in files for f in required_files):
                    python_dirs.append(root)
            
            if python_dirs:
                found_paths.extend(python_dirs)
                print(f"   找到Python绑定目录: {len(python_dirs)}个")
                for pdir in python_dirs:
                    print(f"   - {pdir}")
            else:
                print(f"   ⚠️ 未找到Python绑定文件")
    
    return found_paths

def get_current_python_info():
    """获取当前Python环境信息"""
    print(f"🐍 当前Python版本: {sys.version}")
    print(f"🐍 Python可执行文件: {sys.executable}")
    
    # 获取site-packages路径
    site_packages_paths = site.getsitepackages()
    print(f"📂 site-packages路径:")
    for path in site_packages_paths:
        print(f"   - {path}")
    
    return site_packages_paths[0] if site_packages_paths else None

def copy_fbx_files(source_path, target_path):
    """复制FBX文件到目标路径"""
    # 必需的文件列表
    required_files = ['fbx.pyd', 'fbxsip.pyd', 'FbxCommon.py']
    optional_files = ['fbx.py']  # 某些版本可能没有这个文件
    
    copied_files = []
    
    print(f"\n📋 开始复制FBX文件...")
    print(f"源路径: {source_path}")
    print(f"目标路径: {target_path}")
    
    try:
        # 复制必需文件
        for file_name in required_files:
            src_file = os.path.join(source_path, file_name)
            dst_file = os.path.join(target_path, file_name)
            
            if os.path.exists(src_file):
                shutil.copy2(src_file, dst_file)
                print(f"✅ 已复制: {file_name}")
                copied_files.append(file_name)
            else:
                print(f"❌ 必需文件不存在: {file_name}")
                return False
        
        # 复制可选文件
        for file_name in optional_files:
            src_file = os.path.join(source_path, file_name)
            dst_file = os.path.join(target_path, file_name)
            
            if os.path.exists(src_file):
                shutil.copy2(src_file, dst_file)
                print(f"✅ 已复制: {file_name}")
                copied_files.append(file_name)
            else:
                print(f"ℹ️ 可选文件不存在: {file_name} (这是正常的)")
        
        return len(copied_files) >= len(required_files)
        
    except PermissionError:
        print("❌ 权限不足，请以管理员身份运行此脚本")
        return False
    except Exception as e:
        print(f"❌ 复制文件时出错: {e}")
        return False

def test_fbx_import():
    """测试FBX SDK导入"""
    print("\n🧪 测试FBX SDK导入...")
    
    try:
        import fbx
        print("✅ FBX SDK导入成功！")
        
        # 尝试获取版本信息
        try:
            version = fbx.FbxManager.GetVersion()
            print(f"📦 FBX SDK版本: {version}")
        except:
            print("⚠️ 无法获取FBX SDK版本")
        
        # 尝试创建基本对象
        try:
            manager = fbx.FbxManager.Create()
            print("✅ FBX管理器创建成功")
            
            scene = fbx.FbxScene.Create(manager, "TestScene")
            print("✅ FBX场景创建成功")
            
            print("🎉 FBX SDK测试通过！")
            return True
            
        except Exception as e:
            print(f"⚠️ FBX对象创建失败: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ FBX SDK导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False

def main():
    print("🚀 FBX SDK Python绑定配置助手")
    print("=" * 50)
    
    # 获取当前Python环境信息
    site_packages_path = get_current_python_info()
    
    if not site_packages_path:
        print("❌ 无法获取site-packages路径")
        return
    
    # 查找FBX SDK安装路径
    print("\n🔍 查找FBX SDK安装路径...")
    fbx_paths = find_fbx_sdk_installation()
    
    if not fbx_paths:
        print("❌ 未找到FBX SDK安装路径")
        print("\n💡 请确保:")
        print("1. FBX SDK已正确安装")
        print("2. 安装路径包含Python绑定文件")
        return
    
    # 选择合适的FBX SDK路径
    selected_path = None
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    
    # 优先选择匹配当前Python版本的路径
    for path in fbx_paths:
        if f"Python{sys.version_info.major}{sys.version_info.minor}" in path:
            selected_path = path
            print(f"\n✅ 选择匹配Python {current_version}的路径: {path}")
            break
    
    # 如果没有找到匹配版本，选择第一个可用路径
    if not selected_path:
        selected_path = fbx_paths[0]
        print(f"\n⚠️ 未找到匹配Python {current_version}的路径，使用: {selected_path}")
        print("   这可能导致兼容性问题")
    
    # 询问用户是否继续
    choice = input("\n是否继续配置Python绑定? (Y/n): ").lower()
    if choice == 'n':
        print("❌ 已取消配置")
        return
    
    # 复制FBX文件
    success = copy_fbx_files(selected_path, site_packages_path)
    
    if success:
        print("\n✅ 文件复制完成")
        
        # 测试安装
        if test_fbx_import():
            print("\n" + "=" * 50)
            print("🎉 FBX SDK Python绑定配置成功！")
            print("\n📋 后续步骤:")
            print("1. 现在可以在Python中使用 import fbx")
            print("2. 开始使用FBX SDK进行开发")
            print("3. 参考官方文档: https://help.autodesk.com/view/FBX/2020/ENU/")
        else:
            print("\n" + "=" * 50)
            print("⚠️ 文件复制成功但测试失败")
            print("\n💡 可能的解决方案:")
            print("1. 检查Python版本兼容性")
            print("2. 尝试重新安装FBX SDK")
            print("3. 使用自制FBX生成器作为替代方案")
    else:
        print("\n❌ 配置失败")
        print("\n💡 手动配置步骤:")
        print(f"1. 复制以下文件从 {selected_path}")
        print(f"   到 {site_packages_path}")
        print("   - fbx.pyd")
        print("   - fbx.py")
        print("   - FbxCommon.py")
        print("2. 确保有足够的权限")
        print("3. 运行 python test_fbx_sdk.py 测试")

if __name__ == "__main__":
    main()