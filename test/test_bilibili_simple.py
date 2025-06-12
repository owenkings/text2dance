#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的B站下载测试脚本
"""

import sys
import os
import requests
import json
import re
from typing import Dict, List, Optional, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_bilibili_page_analysis():
    """测试B站页面分析"""
    print("="*50)
    print("B站页面分析测试")
    print("="*50)
    
    test_url = "https://www.bilibili.com/video/BV1xx411c7mu"
    
    try:
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        print(f"正在获取页面: {test_url}")
        response = requests.get(test_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html = response.text
        print(f"页面大小: {len(html)} 字符")
        
        # 检查各种数据源
        data_sources = {
            '__playinfo__': r'window\.__playinfo__\s*=\s*({.+?});',
            '__INITIAL_STATE__': r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
            '__NEPTUNE_IS_MY_WAIFU__': r'window\.__NEPTUNE_IS_MY_WAIFU__\s*=\s*({.+?});'
        }
        
        found_data = {}
        
        for name, pattern in data_sources.items():
            match = re.search(pattern, html)
            if match:
                try:
                    data = json.loads(match.group(1))
                    found_data[name] = data
                    print(f"✓ 找到 {name}: {len(str(data))} 字符")
                except json.JSONDecodeError as e:
                    print(f"✗ {name} JSON解析失败: {e}")
            else:
                print(f"✗ 未找到 {name}")
        
        # 尝试提取基本信息
        title_match = re.search(r'<title>([^<]+)</title>', html)
        title = title_match.group(1) if title_match else '未找到标题'
        print(f"页面标题: {title}")
        
        # 检查是否有播放信息
        if '__playinfo__' in found_data:
            playinfo = found_data['__playinfo__']
            if 'data' in playinfo and 'dash' in playinfo['data']:
                print("✓ 找到DASH播放信息")
            elif 'data' in playinfo and 'durl' in playinfo['data']:
                print("✓ 找到DURL播放信息")
            else:
                print("✗ 播放信息格式不明")
        
        # 检查初始状态
        if '__INITIAL_STATE__' in found_data:
            initial_state = found_data['__INITIAL_STATE__']
            if 'videoData' in initial_state:
                video_data = initial_state['videoData']
                print(f"视频标题: {video_data.get('title', '未知')}")
                print(f"视频时长: {video_data.get('duration', 0)}秒")
                print(f"上传者: {video_data.get('owner', {}).get('name', '未知')}")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_youtube_dl_availability():
    """测试yt-dlp/youtube-dl可用性"""
    print("\n" + "="*50)
    print("下载工具可用性测试")
    print("="*50)
    
    import subprocess
    
    # 测试yt-dlp
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ yt-dlp可用: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        print("✗ yt-dlp未安装")
    except Exception as e:
        print(f"✗ yt-dlp测试失败: {e}")
    
    # 测试youtube-dl
    try:
        result = subprocess.run(['youtube-dl', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ youtube-dl可用: {result.stdout.strip()}")
            return True
        else:
            print(f"✗ youtube-dl不可用: {result.stderr}")
            return False
    except FileNotFoundError:
        print("✗ youtube-dl未安装")
        return False
    except Exception as e:
        print(f"✗ youtube-dl测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("B站下载功能简单测试")
    print("="*50)
    
    # 测试页面分析
    page_test = test_bilibili_page_analysis()
    
    # 测试youtube-dl
    ytdl_test = test_youtube_dl_availability()
    
    print("\n" + "="*50)
    print("测试总结")
    print("="*50)
    print(f"页面分析: {'✓ 成功' if page_test else '✗ 失败'}")
    print(f"youtube-dl: {'✓ 可用' if ytdl_test else '✗ 不可用'}")
    
    if not page_test:
        print("\n建议:")
        print("1. 检查网络连接")
        print("2. 检查B站是否可访问")
        print("3. 可能需要更新User-Agent")
    
    if not ytdl_test:
        print("\n安装youtube-dl:")
        print("pip install youtube-dl")
        print("或者使用yt-dlp (更新的版本):")
        print("pip install yt-dlp")

if __name__ == "__main__":
    main()