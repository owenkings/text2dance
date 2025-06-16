#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动脚本 - 自动检测和修复NumPy兼容性问题
"""

import os
import sys
import subprocess

def check_and_fix_numpy():
    """检查并修复NumPy兼容性问题"""
    print("正在检查NumPy版本...")
    
    try:
        # 尝试导入numpy
        import numpy
        version = numpy.__version__
        major_version = int(version.split('.')[0])
        
        print(f"当前NumPy版本: {version}")
        
        if major_version >= 2:
            print("检测到NumPy 2.0+，需要降级以兼容OpenCV")
            return fix_numpy_version()
        else:
            print("NumPy版本兼容")
            return True
            
    except ImportError:
        print("NumPy未安装，正在安装兼容版本...")
        return install_numpy()

def fix_numpy_version():
    """修复NumPy版本"""
    try:
        print("正在降级NumPy...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "numpy<2.0", "--force-reinstall", "--no-deps"
        ])
        
        print("正在重新安装相关包...")
        packages = [
            "opencv-python==4.8.1.78",
            "scipy==1.11.3",
            "matplotlib==3.7.2"
        ]
        
        for package in packages:
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", 
                    package, "--force-reinstall"
                ])
                print(f"✓ {package}")
            except subprocess.CalledProcessError:
                print(f"✗ {package} (可能不影响运行)")
        
        print("修复完成！")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"修复失败: {e}")
        return False

def install_numpy():
    """安装兼容的NumPy版本"""
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "numpy<2.0"
        ])
        print("NumPy安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"NumPy安装失败: {e}")
        return False

def install_missing_packages():
    """安装缺失的包"""
    print("\n检查并安装缺失的依赖包...")
    
    # 检查moviepy
    try:
        import moviepy.editor
        print("✓ moviepy 已安装")
    except ImportError:
        print("✗ moviepy 未安装，正在安装...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "moviepy==1.0.3"
            ])
            print("✓ moviepy 安装完成")
        except subprocess.CalledProcessError:
            print("✗ moviepy 安装失败")
            return False
    
    # 检查其他关键依赖
    packages_to_check = [
        ("PyQt5", "PyQt5==5.15.9"),
        ("requests", "requests==2.31.0"),
        ("beautifulsoup4", "beautifulsoup4==4.12.2")
    ]
    
    for module_name, package_spec in packages_to_check:
        try:
            __import__(module_name)
            print(f"✓ {module_name} 已安装")
        except ImportError:
            print(f"✗ {module_name} 未安装，正在安装...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", 
                    package_spec
                ])
                print(f"✓ {module_name} 安装完成")
            except subprocess.CalledProcessError:
                print(f"✗ {module_name} 安装失败")
    
    return True

def test_imports():
    """测试关键模块导入"""
    print("\n测试模块导入...")
    
    modules = [
        ("numpy", "NumPy"),
        ("cv2", "OpenCV"),
        ("PyQt5", "PyQt5"),
        ("moviepy.editor", "MoviePy")
    ]
    
    success = True
    for module, name in modules:
        try:
            __import__(module)
            print(f"✓ {name}")
        except ImportError as e:
            print(f"✗ {name}: {e}")
            success = False
    
    return success

def main():
    """主函数"""
    print("=" * 50)
    print("视频编辑工具启动器")
    print("=" * 50)
    
    # 设置环境变量
    os.environ['OPENCV_DISABLE_EIGEN_TENSOR_SUPPORT'] = '1'
    os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'
    
    # 检查和修复NumPy
    if not check_and_fix_numpy():
        print("\n修复失败，请手动运行以下命令：")
        print("pip install 'numpy<2.0' --force-reinstall")
        input("按回车键退出...")
        return
    
    # 安装缺失的包
    if not install_missing_packages():
        print("\n依赖包安装失败，请手动安装")
        input("按回车键退出...")
        return
    
    # 测试导入
    if not test_imports():
        print("\n模块导入测试失败，请检查依赖安装")
        print("尝试手动安装所有依赖：pip install -r requirements.txt")
        input("按回车键退出...")
        return
    
    # 启动主程序
    print("\n所有检查通过，启动主程序...")
    try:
        import main
    except Exception as e:
        print(f"启动失败: {e}")
        input("按回车键退出...")

if __name__ == "__main__":
    main()