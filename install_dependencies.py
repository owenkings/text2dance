#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依赖安装脚本 - 自动安装所有必需的依赖包
"""

import os
import sys
import subprocess

def install_package(package_spec, description=None):
    """安装单个包"""
    desc = description or package_spec
    print(f"正在安装 {desc}...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            package_spec, "--upgrade"
        ])
        print(f"✓ {desc} 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {desc} 安装失败: {e}")
        return False

def install_from_requirements():
    """从requirements.txt安装依赖"""
    print("正在从requirements.txt安装依赖...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "-r", "requirements.txt"
        ])
        print("✓ requirements.txt 安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ requirements.txt 安装失败: {e}")
        return False

def fix_numpy_compatibility():
    """修复NumPy兼容性"""
    print("\n修复NumPy兼容性...")
    
    try:
        import numpy
        version = numpy.__version__
        major_version = int(version.split('.')[0])
        
        if major_version >= 2:
            print(f"检测到NumPy {version}，需要降级")
            return install_package("numpy<2.0", "NumPy (兼容版本)")
        else:
            print(f"✓ NumPy {version} 版本兼容")
            return True
    except ImportError:
        print("NumPy未安装")
        return install_package("numpy<2.0", "NumPy")

def install_critical_packages():
    """安装关键包"""
    print("\n安装关键依赖包...")
    
    critical_packages = [
        ("moviepy==1.0.3", "MoviePy (视频处理)"),
        ("opencv-python==4.8.1.78", "OpenCV (计算机视觉)"),
        ("PyQt5==5.15.9", "PyQt5 (GUI框架)"),
        ("requests==2.31.0", "Requests (HTTP库)"),
        ("beautifulsoup4==4.12.2", "BeautifulSoup4 (HTML解析)")
    ]
    
    success_count = 0
    for package_spec, description in critical_packages:
        if install_package(package_spec, description):
            success_count += 1
    
    print(f"\n关键包安装完成: {success_count}/{len(critical_packages)}")
    return success_count == len(critical_packages)

def test_imports():
    """测试关键模块导入"""
    print("\n测试模块导入...")
    
    test_modules = [
        ("numpy", "NumPy"),
        ("cv2", "OpenCV"),
        ("PyQt5", "PyQt5"),
        ("moviepy.editor", "MoviePy"),
        ("requests", "Requests"),
        ("bs4", "BeautifulSoup4")
    ]
    
    success_count = 0
    for module_name, display_name in test_modules:
        try:
            __import__(module_name)
            print(f"✓ {display_name}")
            success_count += 1
        except ImportError as e:
            print(f"✗ {display_name}: {e}")
    
    print(f"\n导入测试完成: {success_count}/{len(test_modules)}")
    return success_count == len(test_modules)

def main():
    """主函数"""
    print("=" * 60)
    print("           视频编辑工具 - 依赖安装脚本")
    print("=" * 60)
    
    # 设置环境变量
    os.environ['OPENCV_DISABLE_EIGEN_TENSOR_SUPPORT'] = '1'
    os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'
    
    print("\n选择安装方式:")
    print("1. 完整安装 (推荐)")
    print("2. 仅安装关键包")
    print("3. 仅修复NumPy兼容性")
    
    choice = input("\n请选择 (1/2/3): ").strip()
    
    if choice == "1":
        # 完整安装
        print("\n开始完整安装...")
        
        # 先修复NumPy
        if not fix_numpy_compatibility():
            print("NumPy修复失败")
            return
        
        # 安装所有依赖
        if not install_from_requirements():
            print("\n完整安装失败，尝试安装关键包...")
            install_critical_packages()
        
    elif choice == "2":
        # 仅安装关键包
        print("\n开始安装关键包...")
        fix_numpy_compatibility()
        install_critical_packages()
        
    elif choice == "3":
        # 仅修复NumPy
        print("\n开始修复NumPy...")
        fix_numpy_compatibility()
        
    else:
        print("无效选择，执行完整安装...")
        fix_numpy_compatibility()
        install_from_requirements()
    
    # 测试导入
    if test_imports():
        print("\n🎉 所有依赖安装成功！")
        print("现在可以运行主程序了：python main.py")
    else:
        print("\n⚠️  部分依赖安装失败")
        print("请检查错误信息并手动安装失败的包")
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()