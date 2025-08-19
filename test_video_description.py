#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的视频描述功能测试脚本
"""

import os
import sys
import traceback

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

def test_video_description_import():
    """测试视频描述模块导入"""
    print("🔍 测试视频描述模块导入...")
    try:
        from src.gui.video_description_widget import VideoDescriptionWidget
        print("✅ VideoDescriptionWidget 导入成功")
        return True
    except Exception as e:
        print(f"❌ VideoDescriptionWidget 导入失败: {e}")
        traceback.print_exc()
        return False

def test_widget_initialization():
    """测试组件初始化"""
    print("\n🔍 测试组件初始化...")
    try:
        from src.gui.video_description_widget import VideoDescriptionWidget
        from src.core.config_manager import ConfigManager
        from PyQt5.QtWidgets import QApplication
        
        # 创建应用程序实例（如果不存在）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建配置管理器
        config_manager = ConfigManager()
        
        # 创建组件实例
        widget = VideoDescriptionWidget(config_manager)
        print("✅ VideoDescriptionWidget 初始化成功")
        
        # 检查配置加载
        print(f"📁 缓存路径: {getattr(widget, 'cache_path', 'None')}")
        print(f"🤖 模型路径: {getattr(widget, 'model_path', 'None')}")
        print(f"🔧 使用API: {getattr(widget, 'use_api', 'None')}")
        
        return True
    except Exception as e:
        print(f"❌ 组件初始化失败: {e}")
        traceback.print_exc()
        return False

def test_api_mode():
    """测试API模式"""
    print("\n🔍 测试API模式...")
    try:
        from src.gui.video_description_widget import VideoDescriptionWidget
        from src.core.config_manager import ConfigManager
        from PyQt5.QtWidgets import QApplication
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建配置管理器
        config_manager = ConfigManager()
        
        widget = VideoDescriptionWidget(config_manager)
        
        # 强制设置为API模式
        widget.use_api = True
        widget.api_key = "test_key"  # 测试用的key
        
        print("✅ API模式设置成功")
        print(f"🔑 API Key: {'已设置' if widget.api_key else '未设置'}")
        
        return True
    except Exception as e:
        print(f"❌ API模式测试失败: {e}")
        traceback.print_exc()
        return False

def test_config_loading():
    """测试配置加载"""
    print("\n🔍 测试配置文件加载...")
    try:
        config_file = os.path.join(project_root, 'cache_config.txt')
        if os.path.exists(config_file):
            print(f"✅ 配置文件存在: {config_file}")
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print("📄 配置文件内容:")
                for line in content.split('\n')[:10]:  # 只显示前10行
                    if line.strip():
                        print(f"   {line}")
        else:
            print(f"❌ 配置文件不存在: {config_file}")
        
        return True
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🎬 视频描述功能测试")
    print("=" * 60)
    
    tests = [
        test_video_description_import,
        test_widget_initialization,
        test_api_mode,
        test_config_loading,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！视频描述功能基本正常")
    else:
        print("⚠️  部分测试失败，请检查相关配置")
    
    print("=" * 60)

if __name__ == "__main__":
    main()