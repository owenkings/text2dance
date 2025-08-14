#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FBX SDK环境自动设置脚本
帮助用户创建虚拟环境并尝试安装FBX SDK
"""

import os
import sys
import subprocess
import platform

def run_command(command, shell=True):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(command, shell=shell, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_conda():
    """检查conda是否可用"""
    success, stdout, stderr = run_command("conda --version")
    return success

def check_python_version(version):
    """检查指定Python版本是否可用"""
    python_cmd = f"python{version}" if platform.system() != "Windows" else f"python"
    success, stdout, stderr = run_command(f"{python_cmd} --version")
    return success and version in stdout

def create_conda_env(env_name, python_version):
    """使用conda创建虚拟环境"""
    print(f"🔧 正在创建conda环境: {env_name} (Python {python_version})")
    
    # 删除已存在的环境
    run_command(f"conda env remove -n {env_name} -y")
    
    # 创建新环境
    success, stdout, stderr = run_command(f"conda create -n {env_name} python={python_version} -y")
    
    if success:
        print(f"✅ conda环境 {env_name} 创建成功")
        return True
    else:
        print(f"❌ conda环境创建失败: {stderr}")
        return False

def create_venv_env(env_name, python_version):
    """使用venv创建虚拟环境"""
    print(f"🔧 正在创建venv环境: {env_name} (Python {python_version})")
    
    python_cmd = f"python{python_version}" if platform.system() != "Windows" else "python"
    
    # 删除已存在的环境
    if os.path.exists(env_name):
        import shutil
        shutil.rmtree(env_name)
    
    # 创建新环境
    success, stdout, stderr = run_command(f"{python_cmd} -m venv {env_name}")
    
    if success:
        print(f"✅ venv环境 {env_name} 创建成功")
        return True
    else:
        print(f"❌ venv环境创建失败: {stderr}")
        return False

def get_activation_command(env_name, use_conda=True):
    """获取环境激活命令"""
    if use_conda:
        return f"conda activate {env_name}"
    else:
        if platform.system() == "Windows":
            return f"{env_name}\\Scripts\\activate"
        else:
            return f"source {env_name}/bin/activate"

def check_existing_fbx_sdk():
    """检查系统中是否已安装FBX SDK"""
    possible_paths = [
        "C:\\Program Files\\Autodesk\\FBX\\FBX SDK\\2020.3.7\\lib\\Python37_x64",
        "C:\\Program Files\\Autodesk\\FBX\\FBX SDK\\2020.3\\lib\\Python37_x64",
        "C:\\Program Files\\Autodesk\\FBX\\FBX SDK\\2020.2\\lib\\Python37_x64",
        "C:\\Program Files (x86)\\Autodesk\\FBX\\FBX SDK\\2020.3.7\\lib\\Python37_x64",
        "C:\\Program Files (x86)\\Autodesk\\FBX\\FBX SDK\\2020.3\\lib\\Python37_x64",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            fbx_files = ['fbx.pyd', 'fbx.py', 'FbxCommon.py']
            if all(os.path.exists(os.path.join(path, f)) for f in fbx_files):
                return path
    
    return None

def auto_install_fbx_sdk(fbx_path):
    """自动安装已存在的FBX SDK"""
    import site
    import shutil
    
    site_packages = site.getsitepackages()[0]
    print(f"📂 找到FBX SDK: {fbx_path}")
    print(f"📂 目标目录: {site_packages}")
    
    try:
        files_to_copy = ['fbx.pyd', 'fbx.py', 'FbxCommon.py']
        
        for file_name in files_to_copy:
            src = os.path.join(fbx_path, file_name)
            dst = os.path.join(site_packages, file_name)
            
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"✅ 已复制: {file_name}")
            else:
                print(f"⚠️ 文件不存在: {file_name}")
        
        # 测试安装
        print("\n🧪 测试安装...")
        if test_fbx_import():
            print("🎉 FBX SDK自动安装成功！")
            return True
        else:
            print("❌ 安装失败，请尝试手动安装")
            return False
            
    except Exception as e:
        print(f"❌ 复制文件时出错: {e}")
        print("💡 请尝试以管理员权限运行此脚本")
        return False

def install_fbx_in_current_env():
    """在当前环境下安装FBX SDK"""
    print("🔧 在当前环境下安装FBX SDK...")
    print(f"🐍 当前Python版本: {sys.version}")
    
    # 检查当前Python版本是否兼容
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if current_version not in ["3.7", "3.9"]:
        print(f"⚠️ 警告: 当前Python版本 {current_version} 可能与FBX SDK不兼容")
        print("   推荐版本: Python 3.7 或 3.9")
        
        choice = input("是否继续安装? (y/N): ").lower()
        if choice != 'y':
            print("❌ 已取消安装")
            return False
    
    # 首先检查是否已安装FBX SDK
    print("\n🔍 检查系统中是否已安装FBX SDK...")
    existing_fbx_path = check_existing_fbx_sdk()
    
    if existing_fbx_path:
        print(f"✅ 找到已安装的FBX SDK: {existing_fbx_path}")
        choice = input("是否自动配置Python绑定? (Y/n): ").lower()
        
        if choice != 'n':
            if auto_install_fbx_sdk(existing_fbx_path):
                return True
            else:
                print("⚠️ 自动安装失败，继续尝试其他方法...")
    else:
        print("❌ 未找到已安装的FBX SDK")
    
    # 尝试多种安装方法
    install_methods = [
        ("pip install fbx", "通过pip安装fbx包"),
        ("pip install fbx-sdk", "通过pip安装fbx-sdk包"),
        ("pip install autodesk-fbx", "通过pip安装autodesk-fbx包"),
    ]
    
    for cmd, desc in install_methods:
        print(f"\n🔧 尝试: {desc}")
        success, stdout, stderr = run_command(cmd)
        
        if success:
            print(f"✅ {desc} 成功！")
            print(stdout)
            
            # 立即测试安装
            print("\n🧪 测试安装...")
            test_success = test_fbx_import()
            if test_success:
                print("🎉 FBX SDK安装并测试成功！")
                return True
            else:
                print("⚠️ 安装成功但测试失败，继续尝试其他方法...")
        else:
            print(f"❌ {desc} 失败: {stderr}")
    
    # 如果所有pip方法都失败，提供手动安装指导
    print("\n❌ 所有pip安装方法都失败了")
    print("\n💡 手动安装FBX SDK的详细步骤:")
    print("\n📥 1. 下载FBX SDK:")
    print("   访问: https://aps.autodesk.com/developer/overview/fbx-sdk")
    print("   下载适合Windows的FBX SDK (推荐版本: 2020.3.7)")
    print("   注意: 确保下载包含Python绑定的版本")
    
    print("\n🔧 2. 安装FBX SDK:")
    print("   运行下载的安装程序")
    print("   默认安装路径通常为: C:\\Program Files\\Autodesk\\FBX\\FBX SDK\\")
    
    print("\n🐍 3. 配置Python绑定:")
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    print(f"   当前Python版本: {current_version}")
    
    if current_version == "3.7":
        print("   ✅ Python 3.7 与FBX SDK兼容性最佳")
        print("   找到安装目录下的: lib\\Python37_x64\\")
    else:
        print(f"   ⚠️ Python {current_version} 可能需要重新编译绑定")
        print("   找到安装目录下最接近的Python版本文件夹")
    
    print("\n📂 4. 复制绑定文件:")
    import site
    site_packages = site.getsitepackages()[0]
    print(f"   目标目录: {site_packages}")
    print("   复制以下文件到site-packages:")
    print("   - fbx.pyd (Windows动态库)")
    print("   - fbx.py (Python接口文件)")
    print("   - FbxCommon.py (通用函数)")
    
    print("\n🧪 5. 测试安装:")
    print("   运行: python test_fbx_sdk.py")
    
    print("\n🔗 参考资源:")
    print("   - 官方文档: https://help.autodesk.com/view/FBX/2020/ENU/")
    print("   - 社区讨论: https://forums.autodesk.com/t5/fbx-forum/bd-p/area-fbx")
    print("   - 详细指南: FBX_SDK_Installation_Guide.md")
    
    # 提供自动复制命令
    print("\n⚡ 快速安装命令 (需要管理员权限):")
    print("   如果FBX SDK已安装到默认路径，可尝试运行:")
    fbx_path = "C:\\Program Files\\Autodesk\\FBX\\FBX SDK\\2020.3.7\\lib\\Python37_x64"
    print(f"   xcopy \"{fbx_path}\\*\" \"{site_packages}\\\" /Y")
    print("   (请根据实际安装路径调整命令)")
    
    return False

def test_fbx_import():
    """测试FBX SDK导入"""
    try:
        import fbx
        print("✅ FBX SDK导入成功！")
        
        # 尝试创建基本对象
        try:
            manager = fbx.FbxManager.Create()
            print("✅ FBX管理器创建成功")
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

def create_test_script():
    """创建FBX SDK测试脚本"""
    test_script = """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("🧪 测试FBX SDK安装...")

try:
    import fbx
    print("✅ FBX SDK导入成功！")
    
    # 获取版本信息
    try:
        version = fbx.FbxManager.GetVersion()
        print(f"📦 FBX SDK版本: {version}")
    except:
        print("⚠️ 无法获取FBX SDK版本")
    
    # 创建基本对象
    try:
        manager = fbx.FbxManager.Create()
        print("✅ FBX管理器创建成功")
        
        scene = fbx.FbxScene.Create(manager, "TestScene")
        print("✅ FBX场景创建成功")
        
        # 测试轴系统创建
        try:
            axis_system = fbx.FbxAxisSystem.MayaYUp
            print("✅ FBX轴系统创建成功")
        except Exception as e:
            print(f"⚠️ FBX轴系统创建失败: {e}")
        
        print("🎉 FBX SDK基本功能测试通过！")
        
    except Exception as e:
        print(f"❌ FBX对象创建失败: {e}")
        
except ImportError as e:
    print(f"❌ FBX SDK导入失败: {e}")
    print("\n💡 可能的解决方案:")
    print("1. 确保已安装FBX SDK")
    print("2. 检查Python版本兼容性（推荐Python 3.7）")
    print("3. 配置正确的PYTHONPATH")
    print("4. 考虑使用自制FBX生成器作为替代方案")
    
except Exception as e:
    print(f"❌ 未知错误: {e}")
"""
    
    with open("test_fbx_sdk.py", "w", encoding="utf-8") as f:
        f.write(test_script)
    
    print("📝 已创建FBX SDK测试脚本: test_fbx_sdk.py")

def main():
    print("🚀 FBX SDK环境设置助手")
    print("=" * 50)
    
    # 检查系统信息
    print(f"💻 操作系统: {platform.system()} {platform.release()}")
    print(f"🐍 当前Python版本: {sys.version}")
    
    # 添加安装模式选择
    print("\n🎯 选择安装模式:")
    print("1. 在当前环境下直接安装FBX SDK")
    print("2. 创建新的虚拟环境并安装FBX SDK")
    
    while True:
        try:
            mode_choice = int(input("\n请选择模式 (1-2): "))
            if mode_choice in [1, 2]:
                break
            else:
                print("❌ 请输入1或2")
        except ValueError:
            print("❌ 请输入数字")
    
    if mode_choice == 1:
        # 在当前环境下安装
        print("\n📌 选择: 在当前环境下安装FBX SDK")
        create_test_script()
        success = install_fbx_in_current_env()
        
        if success:
            print("\n" + "=" * 50)
            print("🎉 FBX SDK安装成功！")
            print("\n📋 后续步骤:")
            print("1. 运行测试: python test_fbx_sdk.py")
            print("2. 开始使用FBX SDK进行开发")
        else:
            print("\n" + "=" * 50)
            print("❌ FBX SDK安装失败")
            print("\n💡 建议:")
            print("1. 参考手动安装指导")
            print("2. 或者继续使用自制FBX生成器")
        return
    
    # 原有的虚拟环境创建逻辑
    print("\n📌 选择: 创建新的虚拟环境")
    
    # 检查conda可用性
    has_conda = check_conda()
    print(f"📦 Conda可用: {'是' if has_conda else '否'}")
    
    # 推荐的Python版本
    recommended_versions = ["3.7", "3.9"]
    available_versions = []
    
    for version in recommended_versions:
        if check_python_version(version):
            available_versions.append(version)
    
    print(f"🔍 可用的推荐Python版本: {available_versions if available_versions else '无'}")
    
    if not available_versions:
        print("⚠️ 警告: 未找到推荐的Python版本（3.7或3.9）")
        print("   FBX SDK可能无法正常工作")
        
        choice = input("\n是否继续使用当前Python版本? (y/N): ").lower()
        if choice != 'y':
            print("❌ 已取消安装")
            return
    
    # 选择环境创建方式
    if has_conda:
        print("\n🎯 推荐使用conda创建环境")
        use_conda = input("使用conda创建环境? (Y/n): ").lower() != 'n'
    else:
        print("\n🎯 将使用venv创建环境")
        use_conda = False
    
    # 选择Python版本
    if available_versions:
        if len(available_versions) == 1:
            python_version = available_versions[0]
            print(f"\n📌 将使用Python {python_version}")
        else:
            print("\n📌 选择Python版本:")
            for i, version in enumerate(available_versions, 1):
                print(f"  {i}. Python {version}")
            
            while True:
                try:
                    choice = int(input("请选择 (1-{}): ".format(len(available_versions))))
                    if 1 <= choice <= len(available_versions):
                        python_version = available_versions[choice - 1]
                        break
                    else:
                        print("❌ 无效选择")
                except ValueError:
                    print("❌ 请输入数字")
    else:
        python_version = "3.7"  # 默认尝试3.7
    
    # 环境名称
    env_name = f"fbx_env_py{python_version.replace('.', '')}"
    print(f"\n🏷️ 环境名称: {env_name}")
    
    # 创建环境
    if use_conda:
        success = create_conda_env(env_name, python_version)
    else:
        success = create_venv_env(env_name, python_version)
    
    if not success:
        print("❌ 环境创建失败")
        return
    
    # 创建测试脚本
    create_test_script()
    
    # 提供后续步骤指导
    print("\n" + "=" * 50)
    print("🎉 环境创建完成！")
    print("\n📋 后续步骤:")
    print(f"1. 激活环境: {get_activation_command(env_name, use_conda)}")
    print("2. 下载并安装FBX SDK (参考 FBX_SDK_Installation_Guide.md)")
    print("3. 配置Python绑定路径")
    print("4. 运行测试: python test_fbx_sdk.py")
    
    print("\n💡 提示:")
    print("- 如果安装遇到困难，建议继续使用当前的自制FBX生成器")
    print("- 详细安装指南请参考: FBX_SDK_Installation_Guide.md")
    
    # 询问是否立即尝试安装
    if input("\n是否现在尝试通过pip安装fbx? (y/N): ").lower() == 'y':
        print("\n🔧 尝试通过pip安装fbx...")
        activate_cmd = get_activation_command(env_name, use_conda)
        
        if use_conda:
            install_cmd = f"conda activate {env_name} && pip install fbx"
        else:
            if platform.system() == "Windows":
                install_cmd = f"{env_name}\\Scripts\\activate && pip install fbx"
            else:
                install_cmd = f"source {env_name}/bin/activate && pip install fbx"
        
        success, stdout, stderr = run_command(install_cmd)
        
        if success:
            print("✅ pip安装成功！请运行测试脚本验证")
        else:
            print(f"❌ pip安装失败: {stderr}")
            print("💡 这是正常的，FBX SDK通常需要手动安装")

if __name__ == "__main__":
    main()