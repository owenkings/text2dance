# -*- coding: utf-8 -*-
"""
B站视频爬虫

支持B站视频信息获取和下载
"""

import requests
import json
import re
import os
import subprocess
import sys
from typing import Dict, List, Optional, Any, Callable
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from .base_crawler import BaseCrawler
from ..utils.logger import get_logger


class BilibiliCrawler(BaseCrawler):
    """B站爬虫"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    def platform_name(self) -> str:
        return "bilibili"
    
    def is_supported_url(self, url: str) -> bool:
        """检查是否为B站URL"""
        patterns = [
            r'https?://www\.bilibili\.com/video/[Bb][Vv][0-9A-Za-z]+',
            r'https?://b23\.tv/[0-9A-Za-z]+',
            r'https?://m\.bilibili\.com/video/[Bb][Vv][0-9A-Za-z]+',
            r'https?://www\.bilibili\.com/cheese/play/ss\d+',  # 课程链接
            r'https?://www\.bilibili\.com/bangumi/play/ss\d+',  # 番剧链接
            r'https?://www\.bilibili\.com/bangumi/play/ep\d+',  # 番剧分集链接
            r'https?://live\.bilibili\.com/\d+',  # 直播链接
            r'https?://space\.bilibili\.com/\d+'  # 用户空间链接
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """提取B站视频ID（BV号、课程ID、番剧ID等）"""
        # 处理短链接
        if 'b23.tv' in url:
            try:
                response = self.get_with_retry(url, allow_redirects=True)
                if response:
                    url = response.url
            except Exception as e:
                self.logger.error(f"解析短链接失败: {e}")
                return None
        
        # 提取BV号
        match = re.search(r'[Bb][Vv]([0-9A-Za-z]+)', url)
        if match:
            return f"BV{match.group(1)}"
        
        # 提取课程ID (cheese/play/ss开头)
        match = re.search(r'/cheese/play/ss(\d+)', url)
        if match:
            return f"ss{match.group(1)}"
        
        # 提取番剧ID (bangumi/play/ss开头)
        match = re.search(r'/bangumi/play/ss(\d+)', url)
        if match:
            return f"ss{match.group(1)}"
        
        # 提取番剧分集ID (bangumi/play/ep开头)
        match = re.search(r'/bangumi/play/ep(\d+)', url)
        if match:
            return f"ep{match.group(1)}"
        
        return None
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """获取B站视频信息"""
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                self.logger.error(f"无法提取视频ID: {url}")
                return None
            
            # 对于课程、番剧等特殊链接，直接使用yt-dlp获取信息
            if video_id.startswith(('ss', 'ep')):
                self.logger.info(f"检测到特殊链接类型: {video_id}，使用yt-dlp获取信息")
                return self._get_video_info_with_ytdlp(url, video_id)
            
            # 对于普通视频，先尝试传统方法
            response = self.get_with_retry(url)
            if not response:
                # 如果页面获取失败，尝试yt-dlp
                self.logger.warning("页面获取失败，尝试使用yt-dlp")
                return self._get_video_info_with_ytdlp(url, video_id)
            
            html_content = response.text
            
            # 提取视频信息
            info = self._extract_video_info_from_html(html_content)
            if info:
                info['url'] = url
                info['video_id'] = video_id
                info['platform'] = self.platform_name
                # 保持向后兼容
                if video_id.startswith('BV'):
                    info['bv_id'] = video_id
                return info
            else:
                # 如果传统方法失败，尝试yt-dlp
                self.logger.warning("传统方法获取信息失败，尝试使用yt-dlp")
                return self._get_video_info_with_ytdlp(url, video_id)
            
        except Exception as e:
            self.logger.error(f"获取B站视频信息失败: {e}")
            # 最后尝试yt-dlp
            video_id = self.extract_video_id(url)
            if video_id:
                return self._get_video_info_with_ytdlp(url, video_id)
            return None
    
    def _get_video_info_with_ytdlp(self, url: str, video_id: str) -> Optional[Dict[str, Any]]:
        """使用yt-dlp获取视频信息"""
        try:
            self.logger.info(f"使用yt-dlp获取视频信息: {video_id}")
            
            # 检查yt-dlp是否可用
            cmd_name = None
            try:
                subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, check=True, text=True)
                cmd_name = 'yt-dlp'
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    subprocess.run(['youtube-dl', '--version'], 
                                  capture_output=True, check=True, text=True)
                    cmd_name = 'youtube-dl'
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self.logger.error("yt-dlp和youtube-dl都未安装")
                    return None
            
            # 获取视频信息
            info_cmd = [
                cmd_name,
                '--dump-json',
                '--no-playlist',
                url
            ]
            
            # 添加cookies（如果需要）
            cookies_file = self.config_manager.get('crawler.bilibili.cookies_file')
            if cookies_file and Path(cookies_file).exists():
                info_cmd.extend(['--cookies', cookies_file])
            
            result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                self.logger.error(f"yt-dlp获取信息失败: {result.stderr}")
                return None
            
            # 解析JSON信息
            try:
                video_data = json.loads(result.stdout)
                
                # 转换为标准格式
                info = {
                    'title': video_data.get('title', ''),
                    'description': video_data.get('description', ''),
                    'duration': video_data.get('duration', 0),
                    'thumbnail': video_data.get('thumbnail', ''),
                    'uploader': video_data.get('uploader', ''),
                    'upload_date': video_data.get('upload_date', ''),
                    'view_count': video_data.get('view_count', 0),
                    'like_count': video_data.get('like_count', 0),
                    'url': url,
                    'video_id': video_id,
                    'platform': self.platform_name,
                    'formats': video_data.get('formats', [])
                }
                
                # 保持向后兼容
                if video_id.startswith('BV'):
                    info['bv_id'] = video_id
                
                self.logger.info(f"成功获取视频信息: {info['title']}")
                return info
                
            except json.JSONDecodeError as e:
                self.logger.error(f"解析yt-dlp输出失败: {e}")
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.error("yt-dlp获取信息超时")
            return None
        except Exception as e:
            self.logger.error(f"yt-dlp获取信息异常: {e}")
            return None
    
    def _extract_video_info_from_html(self, html: str) -> Optional[Dict[str, Any]]:
        """从HTML中提取视频信息"""
        try:
            # 尝试多种数据源
            playinfo = None
            initial_state = None
            
            # 方法1: 查找window.__playinfo__
            playinfo_match = re.search(r'window\.__playinfo__\s*=\s*({[^;]+});', html)
            if playinfo_match:
                playinfo_json = playinfo_match.group(1)
                try:
                    playinfo = json.loads(playinfo_json)
                    self.logger.info("使用window.__playinfo__获取播放信息")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"playinfo JSON解析失败: {e}")
                    playinfo = self._parse_json_safely(playinfo_json)
            
            # 方法2: 查找window.__NEPTUNE_IS_MY_WAIFU__（新的B站数据结构）
            if not playinfo:
                neptune_match = re.search(r'window\.__NEPTUNE_IS_MY_WAIFU__\s*=\s*({.+?});', html)
                if neptune_match:
                    try:
                        neptune_data = json.loads(neptune_match.group(1))
                        # 从NEPTUNE数据中提取播放信息
                        if 'videoData' in neptune_data and 'dash' in neptune_data.get('videoData', {}):
                            playinfo = {'data': {'dash': neptune_data['videoData']['dash']}}
                            self.logger.info("使用window.__NEPTUNE_IS_MY_WAIFU__获取播放信息")
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"NEPTUNE JSON解析失败: {e}")
            
            # 查找window.__INITIAL_STATE__
            initial_state_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({[^;]+});', html)
            if initial_state_match:
                initial_state_json = initial_state_match.group(1)
                try:
                    initial_state = json.loads(initial_state_json)
                except json.JSONDecodeError as e:
                    self.logger.warning(f"初始状态JSON解析失败: {e}")
                    initial_state = self._parse_json_safely(initial_state_json)
            
            # 如果都没找到，尝试从页面中直接提取视频信息
            if not playinfo and not initial_state:
                self.logger.warning("未找到标准的播放信息，尝试从页面直接提取")
                return self._extract_video_info_from_page_content(html)
            
            # 如果没有播放信息但有初始状态，尝试构造基本信息
            if not playinfo and initial_state:
                self.logger.warning("未找到播放信息，仅使用基本视频信息")
                return self._extract_basic_video_info(initial_state)
            
            # 如果所有方法都失败，尝试从页面内容提取基本信息
            if not playinfo:
                self.logger.warning("未找到播放信息，尝试提取基本视频信息")
                
                # 尝试从页面内容提取基本信息
                basic_info = self._extract_video_info_from_page_content(html)
                if basic_info:
                    self.logger.info("成功提取基本视频信息，但无法获取下载链接")
                    return basic_info
                
                self.logger.error("完全无法提取视频信息")
                return None
            
            # 提取视频基本信息
            video_data = initial_state.get('videoData', {})
            
            # 提取可用格式
            formats = []
            if 'data' in playinfo and 'dash' in playinfo['data']:
                dash_data = playinfo['data']['dash']
                
                # 视频流
                for video in dash_data.get('video', []):
                    formats.append({
                        'quality': self._get_quality_name(video.get('id', 0)),
                        'format': 'mp4',
                        'url': video.get('baseUrl', ''),
                        'width': video.get('width', 0),
                        'height': video.get('height', 0),
                        'filesize': video.get('bandwidth', 0)
                    })
            
            return {
                'title': video_data.get('title', ''),
                'description': video_data.get('desc', ''),
                'duration': video_data.get('duration', 0),
                'thumbnail': video_data.get('pic', ''),
                'uploader': video_data.get('owner', {}).get('name', ''),
                'upload_date': video_data.get('pubdate', 0),
                'view_count': video_data.get('stat', {}).get('view', 0),
                'like_count': video_data.get('stat', {}).get('like', 0),
                'formats': formats
            }
            
        except Exception as e:
            self.logger.error(f"解析视频信息失败: {e}")
            return None
    
    def _parse_json_safely(self, json_str: str) -> Optional[Dict[str, Any]]:
        """安全地解析JSON字符串，处理可能的额外数据"""
        try:
            # 尝试直接解析
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # 尝试找到第一个完整的JSON对象
                # 使用递归下降解析器来找到完整的JSON
                decoder = json.JSONDecoder()
                obj, idx = decoder.raw_decode(json_str)
                return obj
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.error(f"JSON解析完全失败: {e}")
                return None
    
    def _extract_video_info_from_page_content(self, html: str) -> Optional[Dict[str, Any]]:
        """从页面内容直接提取视频信息"""
        try:
            # 提取基本信息
            title_match = re.search(r'<title>([^<]+)</title>', html)
            title = title_match.group(1) if title_match else ''
            
            # 提取BVID
            bvid_match = re.search(r'"bvid"\s*:\s*"([^"]+)"', html)
            bvid = bvid_match.group(1) if bvid_match else ''
            
            # 提取时长
            duration_match = re.search(r'"duration"\s*:\s*(\d+)', html)
            duration = int(duration_match.group(1)) if duration_match else 0
            
            # 提取上传者
            uploader_match = re.search(r'"name"\s*:\s*"([^"]+)"', html)
            uploader = uploader_match.group(1) if uploader_match else ''
            
            self.logger.info(f"从页面内容提取到基本信息: {title}")
            
            return {
                'title': title.replace(' - 哔哩哔哩', ''),
                'description': '',
                'duration': duration,
                'thumbnail': '',
                'uploader': uploader,
                'upload_date': 0,
                'view_count': 0,
                'like_count': 0,
                'formats': []  # 无法获取下载链接
            }
            
        except Exception as e:
            self.logger.error(f"从页面内容提取信息失败: {e}")
            return None
    
    def _extract_basic_video_info(self, initial_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从初始状态提取基本视频信息"""
        try:
            video_data = initial_state.get('videoData', {})
            
            return {
                'title': video_data.get('title', ''),
                'description': video_data.get('desc', ''),
                'duration': video_data.get('duration', 0),
                'thumbnail': video_data.get('pic', ''),
                'uploader': video_data.get('owner', {}).get('name', ''),
                'upload_date': video_data.get('pubdate', 0),
                'view_count': video_data.get('stat', {}).get('view', 0),
                'like_count': video_data.get('stat', {}).get('like', 0),
                'formats': []  # 无播放信息时无法获取下载链接
            }
            
        except Exception as e:
            self.logger.error(f"提取基本视频信息失败: {e}")
            return None
    
    def _download_with_youtube_dl(self, url: str, output_path: str) -> bool:
        """使用yt-dlp作为备用下载方案，增强地址解析功能"""
        try:
            self.logger.info("尝试使用yt-dlp下载视频")
            
            # 检查yt-dlp是否可用
            cmd_name = None
            try:
                result = subprocess.run(['yt-dlp', '--version'], 
                                      capture_output=True, check=True, text=True)
                cmd_name = 'yt-dlp'
                self.logger.info(f"使用yt-dlp版本: {result.stdout.strip()}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                # 如果yt-dlp不可用，尝试youtube-dl
                try:
                    result = subprocess.run(['youtube-dl', '--version'], 
                                          capture_output=True, check=True, text=True)
                    cmd_name = 'youtube-dl'
                    self.logger.info(f"使用youtube-dl版本: {result.stdout.strip()}")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self.logger.error("yt-dlp和youtube-dl都未安装或不可用")
                    return False
            
            # 首先尝试解析URL以验证其有效性
            self.logger.info("验证URL有效性...")
            info_cmd = [
                cmd_name,
                '--dump-json',
                '--no-playlist',
                url
            ]
            
            try:
                info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=60)
                if info_result.returncode != 0:
                    self.logger.error(f"URL解析失败: {info_result.stderr}")
                    return False
                
                # 解析视频信息
                import json
                video_info = json.loads(info_result.stdout)
                title = video_info.get('title', 'unknown')
                duration = video_info.get('duration', 0)
                self.logger.info(f"解析成功 - 标题: {title}, 时长: {duration}秒")
                
            except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
                self.logger.warning(f"URL预解析失败，继续尝试下载: {e}")
            
            # 确保输出目录存在
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 构建下载命令
            output_template = str(output_dir / '%(title)s.%(ext)s')
            cmd = [
                cmd_name,
                '--no-playlist',
                '--write-info-json',
                '--format', '30016+30216/30016/30216',  # 使用B站特定的格式ID
                '--output', output_template,
                '--retries', '3',  # 重试3次
                '--fragment-retries', '3',  # 片段重试3次
                url
            ]
            
            # 添加cookies支持（如果配置了）
            cookies_file = self.config_manager.get('crawler.bilibili.cookies_file')
            if cookies_file and Path(cookies_file).exists():
                cmd.extend(['--cookies', cookies_file])
                self.logger.info("使用cookies文件")
            
            self.logger.info(f"执行下载命令: {' '.join(cmd)}")
            
            # 执行下载
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                self.logger.info(f"{cmd_name}下载成功")
                if result.stdout:
                    self.logger.info(f"输出: {result.stdout[-500:]}")
                return True
            else:
                self.logger.error(f"{cmd_name}下载失败 (返回码: {result.returncode})")
                if result.stderr:
                    self.logger.error(f"错误信息: {result.stderr}")
                if result.stdout:
                    self.logger.error(f"输出信息: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("下载超时（10分钟）")
            return False
        except Exception as e:
            self.logger.error(f"备用下载异常: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _get_quality_name(self, quality_id: int) -> str:
        """根据质量ID获取质量名称"""
        quality_map = {
            16: '360p',
            32: '480p',
            64: '720p',
            74: '720p60',
            80: '1080p',
            112: '1080p+',
            116: '1080p60',
            120: '4K',
            125: 'HDR',
            126: 'Dolby'
        }
        return quality_map.get(quality_id, f'{quality_id}p')
    
    def search_videos(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """搜索B站视频"""
        try:
            search_url = "https://api.bilibili.com/x/web-interface/search/type"
            
            # 更新请求头，模拟浏览器行为
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/v/channel',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Origin': 'https://www.bilibili.com',
                'Cookie': 'buvid3=randomstring; innersign=0; b_lsid=randomstring',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site'
            }
            
            results = []
            page = 1
            per_page = 50  # B站API每页最多返回50条结果
            
            while len(results) < limit:
                # 更新请求参数，确保符合B站API要求
                params = {
                    'search_type': 'video',
                    'keyword': keyword,
                    'page': page,
                    'order': 'totalrank',  # 默认排序方式
                    'duration': 0,         # 所有时长
                    'tids': 0,             # 所有分区
                    '__refresh__': 'true',
                    'platform': 'pc',
                    'highlight': 1,
                    'single_column': 0,
                    'order_sort': 0,
                    'preload': '',
                    'com2co': 'true'
                }
                
                response = self.get_with_retry(search_url, params=params, headers=headers)
                if not response:
                    break
                
                data = response.json()
                if data.get('code') != 0:
                    self.logger.error(f"搜索API返回错误: {data.get('message')}")
                    break
                
                search_data = data.get('data', {})
                video_results = search_data.get('result', [])
                
                # 如果当前页没有结果，说明已经到底了
                if not video_results:
                    break
                
                # 处理当前页的结果
                for item in video_results:
                    try:
                        # 构建完整的视频URL
                        bvid = item.get('bvid', '')
                        video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else item.get('arcurl', '')
                        
                        # 处理缩略图URL
                        pic_url = item.get('pic', '')
                        if pic_url and not pic_url.startswith('http'):
                            pic_url = f"https:{pic_url}"
                        
                        video_info = {
                            'title': self._clean_html_tags(item.get('title', '')),
                            'description': self._clean_html_tags(item.get('description', '')),
                            'url': video_url,
                            'thumbnail': pic_url,
                            'uploader': item.get('author', ''),
                            'duration': self._parse_duration(item.get('duration', '')),
                            'view_count': item.get('play', 0),
                            'upload_date': item.get('pubdate', 0),
                            'platform': self.platform_name,
                            'bvid': bvid
                        }
                        results.append(video_info)
                        
                        # 如果已经达到限制数量，停止处理
                        if len(results) >= limit:
                            break
                    except Exception as e:
                        self.logger.warning(f"解析视频信息失败: {e}, item: {item}")
                        continue
                
                # 如果已经达到限制数量，退出分页循环
                if len(results) >= limit:
                    break
                    
                # 准备下一页
                page += 1
                
                # 添加延迟避免请求过快
                import time
                time.sleep(0.5)
            
            self.logger.info(f"B站搜索 '{keyword}' 完成，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"B站搜索失败: {e}")
            return []
    
    def _clean_html_tags(self, text: str) -> str:
        """清理HTML标签"""
        return re.sub(r'<[^>]+>', '', text)
    
    def _parse_duration(self, duration_str: str) -> int:
        """解析时长字符串为秒数"""
        try:
            if ':' in duration_str:
                parts = duration_str.split(':')
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0
        except:
            return 0
    
    def download_video(self, url: str, output_path: str, 
                      quality: str = "720p", format: str = "mp4",
                      progress_callback: Callable[[float, int, int], None] = None) -> bool:
        """下载B站视频，优化yt-dlp集成"""
        try:
            self.logger.info(f"开始下载B站视频，URL: {url}")
            
            # 确保输出目录存在
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 首先尝试直接使用yt-dlp下载（更可靠）
            if self._download_with_youtube_dl(url, str(output_dir)):
                return True
            
            # 如果yt-dlp失败，尝试获取视频信息进行传统下载
            self.logger.warning("yt-dlp下载失败，尝试传统方法")
            video_info = self.get_video_info(url)
            if not video_info:
                self.logger.error("无法获取视频信息，下载失败")
                return False
            
            # 检查是否有可用格式
            if not video_info.get('formats'):
                self.logger.error("无可用下载格式")
                return False
            
            title = self.sanitize_filename(video_info['title'])
            output_file = output_dir / f"{title}.{format}"
            
            # 构建yt-dlp命令（备用方案）
            cmd = [
                'yt-dlp',
                '--format', '30016+30216/30016/30216',  # 使用B站特定的格式ID
                '--output', str(output_file),
                '--no-playlist',
                '--retries', '3',
                '--fragment-retries', '3',
                url
            ]
            
            # 添加cookies（如果需要）
            cookies_file = self.config_manager.get('crawler.bilibili.cookies_file')
            if cookies_file and Path(cookies_file).exists():
                cmd.extend(['--cookies', cookies_file])
                self.logger.info("使用cookies文件")
            
            self.logger.info(f"执行备用下载: {title}")
            
            # 执行下载
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            # 监控进度
            stdout_lines = []
            stderr_lines = []
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                
                if output:
                    stdout_lines.append(output.strip())
                    if progress_callback:
                        # 解析进度信息
                        progress_match = re.search(r'(\d+\.\d+)%', output)
                        if progress_match:
                            progress = float(progress_match.group(1))
                            progress_callback(progress, 0, 0)
            
            # 获取剩余的stderr输出
            stderr_output = process.stderr.read()
            if stderr_output:
                stderr_lines.extend(stderr_output.strip().split('\n'))
            
            return_code = process.poll()
            if return_code == 0:
                self.logger.info(f"B站视频下载完成: {output_file}")
                return True
            else:
                self.logger.error(f"B站视频下载失败 (返回码: {return_code})")
                if stderr_lines:
                    self.logger.error(f"错误信息: {' '.join(stderr_lines[-3:])}")
                if stdout_lines:
                    self.logger.error(f"输出信息: {' '.join(stdout_lines[-3:])}")
                return False
                
        except Exception as e:
            self.logger.error(f"B站视频下载异常: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def get_user_videos(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户视频列表"""
        try:
            api_url = "https://api.bilibili.com/x/space/arc/search"
            params = {
                'mid': user_id,
                'ps': min(limit, 50),
                'pn': 1
            }
            
            response = self.get_with_retry(api_url, params=params)
            if not response:
                return []
            
            data = response.json()
            if data.get('code') != 0:
                self.logger.error(f"获取用户视频API错误: {data.get('message')}")
                return []
            
            results = []
            for item in data.get('data', {}).get('list', {}).get('vlist', []):
                video_info = {
                    'title': item.get('title', ''),
                    'description': item.get('description', ''),
                    'url': f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                    'thumbnail': item.get('pic', ''),
                    'duration': item.get('length', 0),
                    'view_count': item.get('play', 0),
                    'upload_date': item.get('created', 0),
                    'platform': self.platform_name
                }
                results.append(video_info)
            
            return results
            
        except Exception as e:
            self.logger.error(f"获取用户视频失败: {e}")
            return []