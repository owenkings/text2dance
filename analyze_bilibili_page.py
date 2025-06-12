#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析B站页面结构
"""

import requests
import re
import json
from typing import List, Dict, Any

def analyze_bilibili_page(url: str):
    """分析B站页面结构"""
    print(f"正在分析页面: {url}")
    
    try:
        # 设置请求头，模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        html = response.text
        
        print(f"页面大小: {len(html)} 字符")
        
        # 查找所有window变量
        window_vars = re.findall(r'window\.__[A-Z_]+__', html)
        print(f"找到的window变量: {set(window_vars)}")
        
        # 检查特定变量
        checks = [
            ('window.__playinfo__', r'window\.__playinfo__'),
            ('window.__INITIAL_STATE__', r'window\.__INITIAL_STATE__'),
            ('window.__NEPTUNE_IS_MY_WAIFU__', r'window\.__NEPTUNE_IS_MY_WAIFU__'),
            ('window.player', r'window\.player'),
            ('__NEXT_DATA__', r'__NEXT_DATA__'),
        ]
        
        for name, pattern in checks:
            if re.search(pattern, html):
                print(f"✓ 找到 {name}")
                # 尝试提取内容
                if name == 'window.__playinfo__':
                    match = re.search(r'window\.__playinfo__\s*=\s*({.+?});', html)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            print(f"  playinfo 数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        except:
                            print(f"  playinfo JSON解析失败，长度: {len(match.group(1))}")
                elif name == 'window.__INITIAL_STATE__':
                    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', html)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            print(f"  INITIAL_STATE 数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        except:
                            print(f"  INITIAL_STATE JSON解析失败，长度: {len(match.group(1))}")
            else:
                print(f"✗ 未找到 {name}")
        
        # 查找视频相关的其他模式
        video_patterns = [
            (r'"bvid"\s*:\s*"([^"]+)"', 'BVID'),
            (r'"title"\s*:\s*"([^"]+)"', '标题'),
            (r'"duration"\s*:\s*(\d+)', '时长'),
            (r'"dash"\s*:', 'DASH流'),
            (r'"durl"\s*:', 'DURL流'),
        ]
        
        print("\n视频信息检查:")
        for pattern, desc in video_patterns:
            matches = re.findall(pattern, html)
            if matches:
                print(f"✓ 找到 {desc}: {matches[:3]}{'...' if len(matches) > 3 else ''}")
            else:
                print(f"✗ 未找到 {desc}")
        
        return True
        
    except Exception as e:
        print(f"分析失败: {e}")
        return False

if __name__ == "__main__":
    url = "https://www.bilibili.com/video/BV1uw7Bz7Ehr"
    print("=" * 60)
    print("B站页面结构分析")
    print("=" * 60)
    
    success = analyze_bilibili_page(url)
    
    print("\n" + "=" * 60)
    if success:
        print("分析完成")
    else:
        print("分析失败")
    print("=" * 60)