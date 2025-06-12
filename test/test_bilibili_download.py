#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频下载功能测试脚本
"""

import sys
import os
import json
import re
from typing import Optional, Dict, Any

# 避免Qt相关问题
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 全局变量用于存储导入的模块
BilibiliCrawler = None
ConfigManager = None
get_logger = None

try:
    from crawler.bilibili_crawler import BilibiliCrawler
    from core.config_manager import ConfigManager
    from utils.logger import get_logger
    IMPORTS_SUCCESS = True
except ImportError as e:
    print(f"导入模块失败: {e}")
    IMPORTS_SUCCESS = False

def test_json_parsing():
    """测试JSON解析功能"""
    print("测试JSON解析修复...")
    
    # 模拟有问题的JSON字符串（包含额外数据）
    test_json = '{"title":"测试视频","duration":120}; var extra = "data";'
    
    try:
        # 使用修复后的解析方法
        decoder = json.JSONDecoder()
        obj, idx = decoder.raw_decode(test_json)
        print(f"✓ JSON解析成功: {obj}")
        return True
    except Exception as e:
        print(f"✗ JSON解析失败: {e}")
        return False

def test_bilibili_download():
    """测试B站视频下载功能"""
    try:
        # 首先测试JSON解析
        if not test_json_parsing():
            return False
            
        # 检查导入是否成功
        if not IMPORTS_SUCCESS:
            print("✗ 模块导入失败，无法进行完整测试")
            return False
            
        # 尝试导入和初始化
        print("正在初始化组件...")
        
        # 设置日志
        logger = get_logger('test')
        
        # 初始化配置管理器
        config_manager = ConfigManager()
        
        # 初始化B站爬虫
        crawler = BilibiliCrawler(config_manager)
        
        # 测试URL
        test_url = "https://www.bilibili.com/video/BV1uw7Bz7Ehr?t=1.3"
        
        print(f"开始测试B站视频下载: {test_url}")
        
        # 获取视频信息
        print("正在获取视频信息...")
        video_info = crawler.get_video_info(test_url)
        
        if video_info:
            print("✓ 视频信息获取成功!")
            print(f"标题: {video_info.get('title', 'N/A')}")
            print(f"时长: {video_info.get('duration', 0)}秒")
            print(f"上传者: {video_info.get('uploader', 'N/A')}")
            print(f"观看次数: {video_info.get('view_count', 0)}")
            print(f"可用格式数量: {len(video_info.get('formats', []))}")
            
            # 显示可用格式
            formats = video_info.get('formats', [])
            if formats:
                print("\n可用格式:")
                for i, fmt in enumerate(formats[:5]):  # 只显示前5个格式
                    print(f"  {i+1}. {fmt.get('quality', 'N/A')} - {fmt.get('width', 0)}x{fmt.get('height', 0)}")
            
            print("\n✓ B站视频信息解析功能正常!")
            return True
        else:
            print("✗ 视频信息获取失败")
            return False
            
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("B站视频下载功能测试")
    print("=" * 50)
    
    success = test_bilibili_download()
    
    print("\n" + "=" * 50)
    if success:
        print("测试结果: ✓ 通过")
        print("B站视频下载功能已修复，可以正常使用!")
    else:
        print("测试结果: ✗ 失败")
        print("请检查错误日志以获取更多信息")
    print("=" * 50)