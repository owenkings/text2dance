#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试yt-dlp下载B站视频
"""

import os
import subprocess
import tempfile
import shutil

def test_ytdlp_bilibili_download():
    """测试yt-dlp下载B站视频"""
    print("="*50)
    print("yt-dlp B站下载测试")
    print("="*50)
    
    test_url = "https://www.bilibili.com/video/BV1xx411c7mu"
    
    # 创建临时下载目录
    temp_dir = tempfile.mkdtemp()
    print(f"临时下载目录: {temp_dir}")
    
    try:
        # 构建yt-dlp命令
        cmd = [
            'yt-dlp',
            '--no-playlist',
            '--write-info-json',
            '--output', os.path.join(temp_dir, '%(title)s.%(ext)s'),
            '--format', 'best[ext=mp4]/best',  # 优先选择mp4格式
            '--max-filesize', '50M',  # 限制文件大小
            test_url
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        print("开始下载...")
        
        # 执行下载
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        print(f"返回码: {result.returncode}")
        
        if result.stdout:
            print("标准输出:")
            print(result.stdout)
        
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        # 检查下载的文件
        files = os.listdir(temp_dir)
        print(f"\n下载的文件: {files}")
        
        if result.returncode == 0 and files:
            print("✓ yt-dlp下载成功!")
            
            # 显示文件信息
            for file in files:
                file_path = os.path.join(temp_dir, file)
                size = os.path.getsize(file_path)
                print(f"  {file}: {size} 字节")
            
            return True
        else:
            print("✗ yt-dlp下载失败")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ 下载超时")
        return False
    except Exception as e:
        print(f"✗ 下载异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
            print(f"\n已清理临时目录: {temp_dir}")
        except Exception as e:
            print(f"清理临时目录失败: {e}")

def test_ytdlp_info_only():
    """测试yt-dlp仅获取视频信息"""
    print("\n" + "="*50)
    print("yt-dlp 信息获取测试")
    print("="*50)
    
    test_url = "https://www.bilibili.com/video/BV1xx411c7mu"
    
    try:
        # 构建yt-dlp命令（仅获取信息）
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--no-playlist',
            test_url
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ 成功获取视频信息")
            
            # 解析JSON信息
            import json
            try:
                info = json.loads(result.stdout)
                print(f"标题: {info.get('title', '未知')}")
                print(f"时长: {info.get('duration', 0)}秒")
                print(f"上传者: {info.get('uploader', '未知')}")
                print(f"观看次数: {info.get('view_count', 0)}")
                
                formats = info.get('formats', [])
                print(f"可用格式数量: {len(formats)}")
                
                return True
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                return False
        else:
            print("✗ 获取视频信息失败")
            print(f"错误: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ 信息获取超时")
        return False
    except Exception as e:
        print(f"✗ 信息获取异常: {e}")
        return False

def main():
    """主测试函数"""
    print("yt-dlp B站功能测试")
    print("="*50)
    
    # 测试信息获取
    info_test = test_ytdlp_info_only()
    
    # 测试下载（如果信息获取成功）
    download_test = False
    if info_test:
        download_test = test_ytdlp_bilibili_download()
    
    print("\n" + "="*50)
    print("测试总结")
    print("="*50)
    print(f"信息获取: {'✓ 成功' if info_test else '✗ 失败'}")
    print(f"视频下载: {'✓ 成功' if download_test else '✗ 失败'}")
    
    if info_test and download_test:
        print("\n✓ yt-dlp可以正常下载B站视频!")
        print("建议在应用中使用yt-dlp作为备用下载方案")
    elif info_test:
        print("\n⚠ yt-dlp可以获取视频信息，但下载可能有问题")
    else:
        print("\n✗ yt-dlp无法处理B站视频")

if __name__ == "__main__":
    main()