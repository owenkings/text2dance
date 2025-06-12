# -*- coding: utf-8 -*-
"""
爬虫基类
定义统一的爬虫接口
"""

import re
import time
import requests
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from loguru import logger


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.session = requests.Session()
        self.timeout = config_manager.get('crawler.timeout', 30)
        self.retry_times = config_manager.get('crawler.retry_times', 3)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(self.headers)
        
        # 设置代理
        self._setup_proxy()
    
    def _setup_proxy(self):
        """设置代理"""
        if self.config_manager.get('proxy.enabled', False):
            proxies = {}
            http_proxy = self.config_manager.get('proxy.http_proxy')
            https_proxy = self.config_manager.get('proxy.https_proxy')
            socks_proxy = self.config_manager.get('proxy.socks_proxy')
            
            if http_proxy:
                proxies['http'] = http_proxy
            if https_proxy:
                proxies['https'] = https_proxy
            if socks_proxy:
                proxies['http'] = socks_proxy
                proxies['https'] = socks_proxy
            
            if proxies:
                self.session.proxies.update(proxies)
                logger.info(f"设置代理: {proxies}")
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称"""
        pass
    
    @abstractmethod
    def is_supported_url(self, url: str) -> bool:
        """检查是否支持该URL"""
        pass
    
    @abstractmethod
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """获取视频信息
        
        Returns:
            {
                'title': '视频标题',
                'description': '视频描述',
                'duration': 视频时长(秒),
                'thumbnail': '缩略图URL',
                'uploader': '上传者',
                'upload_date': '上传日期',
                'view_count': 观看次数,
                'like_count': 点赞数,
                'formats': [可用格式列表]
            }
        """
        pass
    
    @abstractmethod
    def search_videos(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """搜索视频
        
        Args:
            keyword: 搜索关键词
            limit: 结果数量限制
        
        Returns:
            视频信息列表
        """
        pass
    
    @abstractmethod
    def download_video(self, url: str, output_path: str, 
                      quality: str = "720p", format: str = "mp4",
                      progress_callback: Callable[[float, int, int], None] = None) -> bool:
        """下载视频
        
        Args:
            url: 视频URL
            output_path: 输出路径
            quality: 视频质量
            format: 视频格式
            progress_callback: 进度回调函数 (progress, downloaded, total)
        
        Returns:
            是否下载成功
        """
        pass
    
    def get_with_retry(self, url: str, **kwargs) -> Optional[requests.Response]:
        """带重试的GET请求"""
        for attempt in range(self.retry_times):
            try:
                # 如果传入了headers参数，则合并到session的headers中
                if 'headers' in kwargs:
                    temp_headers = self.session.headers.copy()
                    temp_headers.update(kwargs['headers'])
                    kwargs['headers'] = temp_headers
                
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                if response.status_code == 200:
                    return response
                elif response.status_code == 412:
                    logger.warning(f"请求被拒绝 (412)，可能需要更新请求头或参数, URL: {url}")
                    # 对于412错误，增加更长的等待时间
                    if attempt < self.retry_times - 1:
                        time.sleep(2 + attempt)
                else:
                    logger.warning(f"请求失败，状态码: {response.status_code}, URL: {url}")
                    if attempt < self.retry_times - 1:
                        time.sleep(1 + attempt * 0.5)
            except Exception as e:
                logger.warning(f"请求异常 (尝试 {attempt + 1}/{self.retry_times}): {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(1 + attempt * 0.5)
        
        logger.error(f"请求最终失败: {url}")
        return None
    
    def post_with_retry(self, url: str, **kwargs) -> Optional[requests.Response]:
        """带重试的POST请求"""
        for attempt in range(self.retry_times):
            try:
                response = self.session.post(url, timeout=self.timeout, **kwargs)
                if response.status_code == 200:
                    return response
                else:
                    logger.warning(f"POST请求失败，状态码: {response.status_code}, URL: {url}")
            except Exception as e:
                logger.warning(f"POST请求异常 (尝试 {attempt + 1}/{self.retry_times}): {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(1)
        
        logger.error(f"POST请求最终失败: {url}")
        return None
    
    def download_file(self, url: str, output_path: str, 
                     progress_callback: Callable[[float, int, int], None] = None) -> bool:
        """下载文件
        
        Args:
            url: 文件URL
            output_path: 输出路径
            progress_callback: 进度回调函数
        
        Returns:
            是否下载成功
        """
        try:
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            progress_callback(progress, downloaded_size, total_size)
            
            logger.info(f"文件下载完成: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"文件下载失败: {e}")
            return False
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """从URL中提取视频ID"""
        # 子类应该重写此方法
        return None
    
    def format_duration(self, seconds: int) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes}分{seconds}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            return f"{hours}时{minutes}分{seconds}秒"
    
    def format_count(self, count: int) -> str:
        """格式化数量"""
        if count < 1000:
            return str(count)
        elif count < 10000:
            return f"{count / 1000:.1f}K"
        elif count < 100000000:
            return f"{count / 10000:.1f}万"
        else:
            return f"{count / 100000000:.1f}亿"
    
    def sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        # 移除或替换不合法的字符
        illegal_chars = r'[<>:"/\\|?*]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 限制长度
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename.strip()
    
    def cleanup(self):
        """清理资源"""
        if hasattr(self, 'session'):
            self.session.close()
        logger.debug(f"{self.platform_name} 爬虫资源已清理")