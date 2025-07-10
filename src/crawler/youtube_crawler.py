# -*- coding: utf-8 -*-
"""
YouTube爬虫实现
"""

import re
import json
import subprocess
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from loguru import logger

from .base_crawler import BaseCrawler
from ..utils.logger import get_logger


class YoutubeCrawler(BaseCrawler):
    """YouTube爬虫"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    def platform_name(self) -> str:
        return "youtube"
    
    def is_supported_url(self, url: str) -> bool:
        """检查是否为YouTube URL"""
        patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/v/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+'
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """提取YouTube视频ID"""
        patterns = [
            r'(?:v=|/)([\w-]{11})',
            r'youtu\.be/([\w-]{11})',
            r'embed/([\w-]{11})',
            r'shorts/([\w-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """获取YouTube视频信息"""
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                logger.error(f"无法提取视频ID: {url}")
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
                logger.error(f"获取YouTube视频信息失败: {result.stderr}")
                return None
            
            video_data = json.loads(result.stdout)
            
            # 提取格式信息
            formats = []
            for fmt in video_data.get('formats', []):
                if fmt.get('vcodec') != 'none':  # 只要视频格式
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
            logger.error(f"获取YouTube视频信息失败: {e}")
            return None
    
    def _get_quality_from_height(self, height: int) -> str:
        """根据高度获取质量标识"""
        if height >= 2160:
            return '4K'
        elif height >= 1440:
            return '1440p'
        elif height >= 1080:
            return '1080p'
        elif height >= 720:
            return '720p'
        elif height >= 480:
            return '480p'
        elif height >= 360:
            return '360p'
        elif height >= 240:
            return '240p'
        else:
            return f'{height}p'
    
    def search_videos(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """搜索YouTube视频"""
        try:
            # 使用yt-dlp搜索
            search_query = f"ytsearch{limit}:{keyword}"
            
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--flat-playlist',
                search_query
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"YouTube搜索失败: {result.stderr}")
                return []
            
            results = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            video_data = json.loads(line)
                            video_info = {
                                'title': video_data.get('title', ''),
                                'description': video_data.get('description', ''),
                                'url': video_data.get('webpage_url', f"https://www.youtube.com/watch?v={video_data.get('id', '')}"),
                                'thumbnail': video_data.get('thumbnail', ''),
                                'uploader': video_data.get('uploader', ''),
                                'duration': video_data.get('duration', 0),
                                'view_count': video_data.get('view_count', 0),
                                'upload_date': video_data.get('upload_date', ''),
                                'platform': self.platform_name
                            }
                            results.append(video_info)
                        except json.JSONDecodeError:
                            continue
            
            logger.info(f"YouTube搜索 '{keyword}' 完成，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"YouTube搜索失败: {e}")
            return []
    
    def download_video(self, url: str, output_path: str, 
                      quality: str = "720p", format: str = "mp4",
                      progress_callback: Callable[[float, int, int], None] = None) -> bool:
        """下载YouTube视频"""
        try:
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取视频信息用于文件名
            video_info = self.get_video_info(url)
            if not video_info:
                logger.error("无法获取视频信息")
                return False
            
            title = self.sanitize_filename(video_info['title'])
            output_template = str(output_dir / f"{title}.%(ext)s")
            
            # 构建yt-dlp命令
            cmd = [
                'yt-dlp',
                '--format', self._get_format_selector(quality, format),
                '--output', output_template,
                '--no-playlist',
                url
            ]
            
            # 添加代理设置
            if self.config_manager.get('proxy.enabled', False):
                proxy = self.config_manager.get('proxy.http_proxy')
                if proxy:
                    cmd.extend(['--proxy', proxy])
            
            logger.info(f"开始下载YouTube视频: {title}")
            
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
                    
                    # 解析下载速度和大小
                    size_match = re.search(r'(\d+\.\d+\w+)\s+at\s+(\d+\.\d+\w+/s)', output)
                    if size_match:
                        # 可以进一步解析文件大小信息
                        pass
            
            return_code = process.poll()
            if return_code == 0:
                logger.info(f"YouTube视频下载完成: {output_template}")
                return True
            else:
                stderr = process.stderr.read()
                logger.error(f"YouTube视频下载失败: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"YouTube视频下载异常: {e}")
            return False
    
    def _get_format_selector(self, quality: str, format: str) -> str:
        """获取格式选择器"""
        # 提取质量数字
        quality_num = re.search(r'(\d+)', quality)
        if quality_num:
            height = int(quality_num.group(1))
            return f'best[height<={height}][ext={format}]/best[height<={height}]/best'
        else:
            return f'best[ext={format}]/best'
    
    def get_playlist_videos(self, playlist_url: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取播放列表视频"""
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--flat-playlist',
                '--playlist-end', str(limit),
                playlist_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"获取播放列表失败: {result.stderr}")
                return []
            
            results = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            video_data = json.loads(line)
                            if video_data.get('_type') == 'video':
                                video_info = {
                                    'title': video_data.get('title', ''),
                                    'url': video_data.get('webpage_url', f"https://www.youtube.com/watch?v={video_data.get('id', '')}"),
                                    'duration': video_data.get('duration', 0),
                                    'uploader': video_data.get('uploader', ''),
                                    'platform': self.platform_name
                                }
                                results.append(video_info)
                        except json.JSONDecodeError:
                            continue
            
            logger.info(f"获取播放列表完成，共 {len(results)} 个视频")
            return results
            
        except Exception as e:
            logger.error(f"获取播放列表失败: {e}")
            return []
    
    def get_channel_videos(self, channel_url: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取频道视频"""
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--flat-playlist',
                '--playlist-end', str(limit),
                f"{channel_url}/videos"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"获取频道视频失败: {result.stderr}")
                return []
            
            results = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            video_data = json.loads(line)
                            if video_data.get('_type') == 'video':
                                video_info = {
                                    'title': video_data.get('title', ''),
                                    'url': video_data.get('webpage_url', f"https://www.youtube.com/watch?v={video_data.get('id', '')}"),
                                    'duration': video_data.get('duration', 0),
                                    'uploader': video_data.get('uploader', ''),
                                    'upload_date': video_data.get('upload_date', ''),
                                    'platform': self.platform_name
                                }
                                results.append(video_info)
                        except json.JSONDecodeError:
                            continue
            
            logger.info(f"获取频道视频完成，共 {len(results)} 个视频")
            return results
            
        except Exception as e:
            logger.error(f"获取频道视频失败: {e}")
            return []