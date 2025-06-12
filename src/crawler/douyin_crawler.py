# -*- coding: utf-8 -*-
"""
抖音爬虫实现
"""

import re
import json
import subprocess
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from loguru import logger

from .base_crawler import BaseCrawler
from ..utils.logger import get_logger


class DouyinCrawler(BaseCrawler):
    """抖音爬虫"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    def platform_name(self) -> str:
        return "douyin"
    
    def is_supported_url(self, url: str) -> bool:
        """检查是否为抖音URL"""
        patterns = [
            r'https?://(?:www\.)?douyin\.com/video/\d+',
            r'https?://v\.douyin\.com/[\w\d]+',
            r'https?://(?:www\.)?iesdouyin\.com/share/video/\d+'
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """提取抖音视频ID"""
        # 处理短链接
        if 'v.douyin.com' in url:
            try:
                response = self.get_with_retry(url, allow_redirects=True)
                if response:
                    url = response.url
            except Exception as e:
                logger.error(f"解析抖音短链接失败: {e}")
                return None
        
        # 提取视频ID
        patterns = [
            r'video/(\d+)',
            r'share/video/(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """获取抖音视频信息"""
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                logger.error(f"无法提取抖音视频ID: {url}")
                return None
            
            # 使用yt-dlp获取视频信息
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-playlist',
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"获取抖音视频信息失败: {result.stderr}")
                # 尝试备用方法
                return self._get_video_info_fallback(url)
            
            video_data = json.loads(result.stdout)
            
            # 提取格式信息
            formats = []
            for fmt in video_data.get('formats', []):
                formats.append({
                    'quality': self._get_quality_from_height(fmt.get('height', 0)),
                    'format': fmt.get('ext', 'mp4'),
                    'url': fmt.get('url', ''),
                    'width': fmt.get('width', 0),
                    'height': fmt.get('height', 0),
                    'filesize': fmt.get('filesize', 0) or fmt.get('filesize_approx', 0)
                })
            
            return {
                'title': video_data.get('title', ''),
                'description': video_data.get('description', ''),
                'duration': video_data.get('duration', 0),
                'thumbnail': video_data.get('thumbnail', ''),
                'uploader': video_data.get('uploader', ''),
                'upload_date': video_data.get('upload_date', ''),
                'view_count': video_data.get('view_count', 0),
                'like_count': video_data.get('like_count', 0),
                'formats': formats,
                'url': url,
                'video_id': video_id,
                'platform': self.platform_name
            }
            
        except Exception as e:
            logger.error(f"获取抖音视频信息失败: {e}")
            return self._get_video_info_fallback(url)
    
    def _get_video_info_fallback(self, url: str) -> Optional[Dict[str, Any]]:
        """备用方法获取视频信息"""
        try:
            # 直接访问页面获取信息
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            }
            
            response = self.get_with_retry(url, headers=headers)
            if not response:
                return None
            
            html_content = response.text
            
            # 尝试从HTML中提取信息
            title_match = re.search(r'<title>([^<]+)</title>', html_content)
            title = title_match.group(1) if title_match else 'Unknown'
            
            # 清理标题
            title = re.sub(r'\s*-\s*抖音.*$', '', title)
            
            return {
                'title': title,
                'description': '',
                'duration': 0,
                'thumbnail': '',
                'uploader': '',
                'upload_date': '',
                'view_count': 0,
                'like_count': 0,
                'formats': [],
                'url': url,
                'video_id': self.extract_video_id(url),
                'platform': self.platform_name
            }
            
        except Exception as e:
            logger.error(f"备用方法获取抖音视频信息失败: {e}")
            return None
    
    def _get_quality_from_height(self, height: int) -> str:
        """根据高度获取质量标识"""
        if height >= 1080:
            return '1080p'
        elif height >= 720:
            return '720p'
        elif height >= 480:
            return '480p'
        elif height >= 360:
            return '360p'
        else:
            return f'{height}p'
    
    def search_videos(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """搜索抖音视频"""
        try:
            # 抖音搜索比较复杂，这里提供一个基础实现
            # 实际使用中可能需要更复杂的API调用
            
            search_url = "https://www.douyin.com/search/" + keyword
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.get_with_retry(search_url, headers=headers)
            if not response:
                logger.warning("抖音搜索功能暂时不可用，建议使用直接URL下载")
                return []
            
            # 这里需要解析搜索结果页面
            # 由于抖音的反爬机制，实际实现可能需要更复杂的处理
            
            logger.warning(f"抖音搜索 '{keyword}' 功能正在开发中")
            return []
            
        except Exception as e:
            logger.error(f"抖音搜索失败: {e}")
            return []
    
    def download_video(self, url: str, output_path: str, 
                      quality: str = "720p", format: str = "mp4",
                      progress_callback: Callable[[float, int, int], None] = None) -> bool:
        """下载抖音视频"""
        try:
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取视频信息用于文件名
            video_info = self.get_video_info(url)
            if not video_info:
                logger.error("无法获取抖音视频信息")
                return False
            
            title = self.sanitize_filename(video_info['title'])
            if not title or title == 'Unknown':
                title = f"douyin_{video_info.get('video_id', 'unknown')}"
            
            output_template = str(output_dir / f"{title}.%(ext)s")
            
            # 构建yt-dlp命令
            cmd = [
                'yt-dlp',
                '--format', 'best',
                '--output', output_template,
                '--no-playlist',
                url
            ]
            
            # 添加User-Agent
            cmd.extend([
                '--user-agent', 
                'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
            ])
            
            # 添加代理设置
            if self.config_manager.get('proxy.enabled', False):
                proxy = self.config_manager.get('proxy.http_proxy')
                if proxy:
                    cmd.extend(['--proxy', proxy])
            
            logger.info(f"开始下载抖音视频: {title}")
            
            # 执行下载
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            # 监控进度
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                
                if output and progress_callback:
                    # 解析进度信息
                    progress_match = re.search(r'(\d+\.\d+)%', output)
                    if progress_match:
                        progress = float(progress_match.group(1))
                        progress_callback(progress, 0, 0)
            
            return_code = process.poll()
            if return_code == 0:
                logger.info(f"抖音视频下载完成: {output_template}")
                return True
            else:
                stderr = process.stderr.read()
                logger.error(f"抖音视频下载失败: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"抖音视频下载异常: {e}")
            return False
    
    def get_user_videos(self, user_url: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户视频列表"""
        try:
            # 抖音用户视频获取比较复杂
            # 这里提供基础框架
            
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--flat-playlist',
                '--playlist-end', str(limit),
                user_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"获取抖音用户视频失败: {result.stderr}")
                return []
            
            results = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        video_data = json.loads(line)
                        if video_data.get('_type') == 'video':
                            video_info = {
                                'title': video_data.get('title', ''),
                                'url': video_data.get('webpage_url', ''),
                                'duration': video_data.get('duration', 0),
                                'uploader': video_data.get('uploader', ''),
                                'platform': self.platform_name
                            }
                            results.append(video_info)
                    except json.JSONDecodeError:
                        continue
            
            logger.info(f"获取抖音用户视频完成，共 {len(results)} 个视频")
            return results
            
        except Exception as e:
            logger.error(f"获取抖音用户视频失败: {e}")
            return []
    
    def download_with_watermark_removal(self, url: str, output_path: str,
                                       progress_callback: Callable[[float, int, int], None] = None) -> bool:
        """下载抖音视频并尝试去除水印"""
        try:
            # 首先正常下载
            if not self.download_video(url, output_path, progress_callback=progress_callback):
                return False
            
            # 这里可以添加去水印的后处理逻辑
            # 例如使用FFmpeg进行视频处理
            
            logger.info("抖音视频下载完成（去水印功能待实现）")
            return True
            
        except Exception as e:
            logger.error(f"抖音视频去水印下载失败: {e}")
            return False