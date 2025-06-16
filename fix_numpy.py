#!/usr/bin/env python3
"""
NumPy兼容性修复脚本

这个脚本用于修复NumPy 2.0与OpenCV的兼容性问题
"""

import subprocess
import sys
import os

def check_numpy_version():
    """检查当前NumPy版本"""
    try:
        import numpy as np
        version = np.__version__
        major_version = int(version.split('.')[0])
        print(f"当前NumPy版本: {version}")
        return major_version, version
    except ImportError:
        print("NumPy未安装")
        return None, None

def fix_numpy_compatibility():
    """修复NumPy兼容性问题"""
    print("开始修复NumPy兼容性问题...")
    print("\n选择修复方案:")
    print("1. 降级到NumPy 1.x (推荐，稳定)")
    print("2. 升级到最新版本 (实验性)")
    
    choice = input("请选择 (1/2): ").strip()
    
    major_version, current_version = check_numpy_version()
    
    if choice == "2":
        return fix_with_latest_versions()
    else:
        return fix_with_downgrade(major_version, current_version)

def fix_with_downgrade(major_version, current_version):
    """使用降级方案修复"""
    if major_version is None:
        print("正在安装NumPy...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy<2.0"])
            print("NumPy安装完成")
        except subprocess.CalledProcessError as e:
            print(f"安装NumPy失败: {e}")
            return False
    
    elif major_version >= 2:
        print(f"检测到NumPy {current_version}，降级到1.x版本")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "numpy<2.0", "--force-reinstall", "--no-deps"
            ])
            print("NumPy降级完成")
            
            packages_to_reinstall = [
                "opencv-python==4.8.1.78",
                "scipy==1.11.3",
                "matplotlib==3.7.2"
            ]
            
            for package in packages_to_reinstall:
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", 
                        package, "--force-reinstall"
                    ])
                    print(f"重新安装 {package} 完成")
                except subprocess.CalledProcessError:
                    print(f"重新安装 {package} 失败，但可能不影响运行")
                    
        except subprocess.CalledProcessError as e:
            print(f"降级NumPy失败: {e}")
            return False
    
    else:
        print(f"NumPy版本 {current_version} 兼容，无需修复")
    
    return True

def fix_with_latest_versions():
    """使用最新版本修复"""
    print("尝试升级到支持NumPy 2.0的最新版本...")
    print("注意: 这是实验性方案，可能不稳定")
    
    try:
        # 升级到最新的OpenCV版本
        print("升级OpenCV到最新版本...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "opencv-python>=4.10.0.84", "--upgrade"
        ])
        
        # 确保NumPy 2.0
        print("确保NumPy 2.0...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "numpy>=2.0", "--upgrade"
        ])
        
        # 升级其他相关包
        packages_to_upgrade = [
            "scipy",
            "matplotlib",
            "moviepy"
        ]
        
        for package in packages_to_upgrade:
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", 
                    package, "--upgrade"
                ])
                print(f"升级 {package} 完成")
            except subprocess.CalledProcessError:
                print(f"升级 {package} 失败")
        
        print("最新版本升级完成")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"升级失败: {e}")
        print("回退到降级方案...")
        major_version, current_version = check_numpy_version()
        return fix_with_downgrade(major_version, current_version)

def test_imports():
    """测试关键模块导入"""
    print("\n测试模块导入...")
    
    modules_to_test = [
        ("numpy", "np"),
        ("cv2", None),
        ("PyQt5.QtWidgets", "QApplication"),
        ("moviepy.editor", "VideoFileClip")
    ]
    
    success_count = 0
    
    for module_name, import_as in modules_to_test:
        try:
            if import_as:
                exec(f"import {module_name} as {import_as}")
            else:
                exec(f"import {module_name}")
            print(f"✓ {module_name} 导入成功")
            success_count += 1
        except ImportError as e:
            print(f"✗ {module_name} 导入失败: {e}")
    
    print(f"\n导入测试完成: {success_count}/{len(modules_to_test)} 个模块成功")
    return success_count == len(modules_to_test)

if __name__ == "__main__":
    print("NumPy兼容性修复工具")
    print("=" * 50)
    
    if fix_numpy_compatibility():
        print("\n修复完成！")
        if test_imports():
            print("\n所有模块导入正常，可以运行主程序了")
            print("运行命令: python main.py")
        else:
            print("\n部分模块仍有问题，请检查错误信息")
    else:
        print("\n修复失败，请手动执行以下命令:")
        print("pip install 'numpy<2.0' --force-reinstall")
        print("pip install opencv-python==4.8.1.78 --force-reinstall")