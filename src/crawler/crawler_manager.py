# -*- coding: utf-8 -*-
"""
爬虫管理器
统一管理各平台的视频爬取功能
"""

import os
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from .base_crawler import BaseCrawler
from .bilibili_crawler import BilibiliCrawler
from .youtube_crawler import YoutubeCrawler
from .douyin_crawler import DouyinCrawler
from ..core.task_manager import TaskManager as CoreTaskManager, Task, TaskStatus
from ..core.task_persistence import TaskPersistenceManager, TaskState


class DownloadStatus(Enum):
    """下载状态枚举"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """下载任务数据类"""
    id: str
    url: str
    title: str
    platform: str
    output_path: str
    quality: str = "720p"
    format: str = "mp4"
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    error_message: str = ""
    file_size: int = 0
    downloaded_size: int = 0
    max_retries: int = 3
    retry_count: int = 0
    last_error: str = ""


class CrawlerManager:
    """爬虫管理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.crawlers: Dict[str, BaseCrawler] = {}
        self.download_tasks: Dict[str, DownloadTask] = {}
        self.executor = None
        self.max_concurrent = config_manager.get('crawler.max_concurrent', 15)  # 默认15个线程
        self.download_path = Path(config_manager.get('crawler.download_path', './downloads'))
        
        # 进度回调函数
        self.progress_callbacks: List[Callable[[str, float], None]] = []
        self.status_callbacks: List[Callable[[str, DownloadStatus], None]] = []
        
        # 集成核心任务管理器
        self.core_task_manager = CoreTaskManager(max_workers=self.max_concurrent)
        
        # 任务持久化管理器
        self.persistence_manager = TaskPersistenceManager()
        
        self._initialize_crawlers()
        self._restore_tasks()
    
    def _initialize_crawlers(self):
        """初始化爬虫"""
        try:
            # 初始化各平台爬虫
            self.crawlers['bilibili'] = BilibiliCrawler(self.config_manager)
            self.crawlers['youtube'] = YoutubeCrawler(self.config_manager)
            self.crawlers['douyin'] = DouyinCrawler(self.config_manager)
            
            # 创建线程池
            self.executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_concurrent
            )
            
            logger.info(f"爬虫管理器初始化完成，支持平台: {list(self.crawlers.keys())}")
            
        except Exception as e:
            logger.error(f"爬虫管理器初始化失败: {e}")
    
    def _restore_tasks(self):
        """恢复未完成的下载任务"""
        try:
            # 清理无效任务
            self.persistence_manager.cleanup_invalid_tasks()
            
            # 恢复活跃任务
            active_tasks = self.persistence_manager.get_all_active_tasks()
            restored_count = 0
            
            for task_state in active_tasks:
                if task_state.status in ['downloading', 'paused', 'failed']:
                    # 重新创建DownloadTask对象
                    download_task = DownloadTask(
                        id=task_state.task_id,
                        url=task_state.url,
                        title=task_state.title,
                        platform=task_state.platform,
                        output_path=task_state.output_path,
                        quality=task_state.quality,
                        format=task_state.format,
                        status=DownloadStatus.PAUSED,  # 恢复为暂停状态
                        progress=task_state.progress,
                        file_size=task_state.file_size,
                        downloaded_size=task_state.downloaded_size,
                        max_retries=task_state.max_retries,
                        retry_count=task_state.retry_count,
                        last_error=task_state.last_error
                    )
                    
                    self.download_tasks[task_state.task_id] = download_task
                    restored_count += 1
                    
                    # 通知状态更新
                    self._notify_status(task_state.task_id, DownloadStatus.PAUSED)
            
            if restored_count > 0:
                logger.info(f"恢复了 {restored_count} 个未完成的下载任务")
            
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
    
    def check_duplicate_download(self, url: str) -> Optional[Dict[str, Any]]:
        """检查是否为重复下载
        
        Returns:
            如果是重复下载，返回已下载的文件信息；否则返回None
        """
        try:
            # 检查已完成的下载
            completed_info = self.persistence_manager.is_url_downloaded(url)
            if completed_info:
                # 验证文件是否仍然存在
                file_path = Path(completed_info['file_path'])
                if file_path.exists():
                    logger.info(f"检测到重复下载: {url} -> {file_path}")
                    return completed_info
                else:
                    logger.warning(f"已下载文件不存在，允许重新下载: {file_path}")
            
            # 检查是否有未完成的下载任务
            partial_task = self.persistence_manager.find_partial_download(url)
            if partial_task:
                logger.info(f"发现未完成的下载任务: {url} (进度: {partial_task.progress:.1f}%)")
                return {
                    'type': 'partial',
                    'task_id': partial_task.task_id,
                    'progress': partial_task.progress,
                    'file_path': partial_task.partial_file_path
                }
            
            return None
            
        except Exception as e:
            logger.error(f"检查重复下载失败: {e}")
            return None
    
    def get_supported_platforms(self) -> List[str]:
        """获取支持的平台列表"""
        return list(self.crawlers.keys())
    
    def detect_platform(self, url: str) -> Optional[str]:
        """检测URL对应的平台"""
        for platform, crawler in self.crawlers.items():
            if crawler.is_supported_url(url):
                return platform
        return None
    
    def search_videos(self, keyword: str, platform: str = None, 
                     limit: int = 20) -> List[Dict[str, Any]]:
        """搜索视频
        
        Args:
            keyword: 搜索关键词
            platform: 指定平台，None表示搜索所有平台
            limit: 结果数量限制
        
        Returns:
            视频信息列表
        """
        results = []
        
        try:
            if platform and platform in self.crawlers:
                # 搜索指定平台
                crawler = self.crawlers[platform]
                platform_results = crawler.search_videos(keyword, limit)
                results.extend(platform_results)
            else:
                # 搜索所有平台
                per_platform_limit = max(1, limit // len(self.crawlers))
                for platform_name, crawler in self.crawlers.items():
                    try:
                        platform_results = crawler.search_videos(keyword, per_platform_limit)
                        results.extend(platform_results)
                    except Exception as e:
                        logger.error(f"平台 {platform_name} 搜索失败: {e}")
            
            logger.info(f"搜索关键词 '{keyword}' 完成，找到 {len(results)} 个结果")
            return results[:limit]
            
        except Exception as e:
            logger.error(f"搜索视频失败: {e}")
            return []
    
    def get_video_info(self, url: str, skip_duplicate_check: bool = False) -> Optional[Dict[str, Any]]:
        """获取视频信息"""
        # 检查重复下载（除非明确跳过）
        if not skip_duplicate_check:
            duplicate_info = self.check_duplicate_download(url)
            if duplicate_info:
                if duplicate_info.get('type') == 'partial':
                    # 恢复未完成的任务
                    task_id = duplicate_info['task_id']
                    if task_id in self.download_tasks:
                        logger.info(f"恢复未完成的下载任务: {task_id}")
                        return task_id
                else:
                    # 已完成的重复下载
                    logger.info(f"跳过重复下载: {url} -> {duplicate_info.get('file_path')}")
                    return "DUPLICATE_COMPLETED"
        
        platform = self.detect_platform(url)
        if not platform:
            logger.error(f"不支持的URL: {url}")
            return None
        
        try:
            crawler = self.crawlers[platform]
            return crawler.get_video_info(url)
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            return None
    
    def batch_search_and_download(self, keyword: str, platform: str = None, 
                                 search_limit: int = 10, download_limit: int = None,
                                 quality: str = "720p", format: str = "mp4",
                                 auto_start: bool = True,
                                 progress_callback: Callable[[int, int], None] = None) -> List[str]:
        """批量搜索并下载视频
        
        Args:
            keyword: 搜索关键词
            platform: 指定平台，None表示搜索所有平台
            search_limit: 搜索结果数量限制
            download_limit: 下载数量限制，None表示下载所有搜索结果
            quality: 视频质量
            format: 视频格式
            progress_callback: 进度回调函数
        
        Returns:
            下载任务ID列表
        """
        try:
            # 搜索视频
            search_results = self.search_videos(keyword, platform, search_limit)
            if not search_results:
                logger.warning(f"搜索关键词 '{keyword}' 没有找到结果")
                return []
            
            # 限制下载数量
            if download_limit:
                search_results = search_results[:download_limit]
            
            # 批量添加下载任务
            task_ids = []
            for i, video_info in enumerate(search_results):
                try:
                    task_id = self.add_download_task(
                        url=video_info['url'],
                        title=video_info.get('title', f'Video_{i+1}'),
                        quality=quality,
                        format=format,
                        auto_start=auto_start,
                        skip_duplicate_check=False
                    )
                    if task_id:
                        task_ids.append(task_id)
                        
                    # 更新进度
                    if progress_callback:
                        current = i + 1
                        total = len(search_results)
                        progress_callback(current, total)
                        
                except Exception as e:
                    logger.error(f"添加下载任务失败: {e}")
            
            logger.info(f"批量搜索下载完成，添加了 {len(task_ids)} 个任务")
            return task_ids
            
        except Exception as e:
            logger.error(f"批量搜索下载失败: {e}")
            return []
    
    def batch_download_urls(self, urls: List[str], quality: str = "720p",
                           format: str = "mp4", max_concurrent: int = None,
                           auto_start: bool = True, max_retries: int = 3,
                           skip_duplicate_check: bool = False,
                           progress_callback: Callable[[int, int], None] = None) -> List[str]:
        """批量下载URL列表
        
        Args:
            urls: URL列表
            quality: 视频质量
            format: 视频格式
            max_concurrent: 最大并发数，None使用默认值
            auto_start: 是否自动开始下载
            max_retries: 最大重试次数
            skip_duplicate_check: 是否跳过重复检测
            progress_callback: 进度回调函数
        
        Returns:
            下载任务ID列表
        """
        try:
            task_ids = []
            
            # 设置并发数
            if max_concurrent:
                old_max_concurrent = self.max_concurrent
                self.max_concurrent = max_concurrent
                # 重新创建线程池
                if self.executor:
                    self.executor.shutdown(wait=False)
                self.executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.max_concurrent
                )
            
            # 批量添加任务
            for i, url in enumerate(urls):
                try:
                    # 获取视频信息作为标题
                    video_info = self.get_video_info(url, skip_duplicate_check)
                    # 检查video_info是否为字典类型
                    if isinstance(video_info, dict):
                        title = video_info.get('title', f'Video_{i+1}')
                    else:
                        title = f'Video_{i+1}'
                    
                    task_id = self.add_download_task(
                        url=url,
                        title=title,
                        quality=quality,
                        format=format,
                        auto_start=auto_start,
                        max_retries=max_retries,
                        skip_duplicate_check=skip_duplicate_check
                    )
                    if task_id:
                        task_ids.append(task_id)
                    
                    # 更新进度
                    if progress_callback:
                        current = i + 1
                        total = len(urls)
                        progress_callback(current, total)
                        
                except Exception as e:
                    logger.error(f"添加URL下载任务失败 {url}: {e}")
            
            # 恢复原始并发数
            if max_concurrent:
                self.max_concurrent = old_max_concurrent
            
            logger.info(f"批量URL下载完成，添加了 {len(task_ids)} 个任务")
            return task_ids
            
        except Exception as e:
            logger.error(f"批量URL下载失败: {e}")
            return []
    
    def pause_all_tasks(self):
        """暂停所有下载任务"""
        try:
            paused_count = 0
            for task_id, task in self.download_tasks.items():
                if task.status == DownloadStatus.DOWNLOADING:
                    task.status = DownloadStatus.PAUSED
                    paused_count += 1
                    # 通知状态回调
                    for callback in self.status_callbacks:
                        callback(task_id, DownloadStatus.PAUSED)
            
            logger.info(f"暂停了 {paused_count} 个下载任务")
            
        except Exception as e:
            logger.error(f"暂停所有任务失败: {e}")
    
    def resume_all_tasks(self):
        """恢复所有暂停的下载任务"""
        try:
            resumed_count = 0
            for task_id, task in self.download_tasks.items():
                if task.status in [DownloadStatus.PENDING, DownloadStatus.PAUSED]:
                    success = self.start_download(task_id)
                    if success:
                        resumed_count += 1
            
            logger.info(f"恢复了 {resumed_count} 个下载任务")
            
        except Exception as e:
            logger.error(f"恢复所有任务失败: {e}")
    
    def cancel_all_tasks(self):
        """取消所有下载任务"""
        try:
            cancelled_count = 0
            for task_id, task in list(self.download_tasks.items()):
                if task.status in [DownloadStatus.PENDING, DownloadStatus.DOWNLOADING]:
                    task.status = DownloadStatus.CANCELLED
                    cancelled_count += 1
                    # 通知状态回调
                    for callback in self.status_callbacks:
                        callback(task_id, DownloadStatus.CANCELLED)
            
            logger.info(f"取消了 {cancelled_count} 个下载任务")
            
        except Exception as e:
            logger.error(f"取消所有任务失败: {e}")
    
    def pause_task(self, task_id: str) -> bool:
        """暂停指定任务"""
        try:
            if task_id in self.download_tasks:
                task = self.download_tasks[task_id]
                if task.status == DownloadStatus.DOWNLOADING:
                    task.status = DownloadStatus.PENDING
                    # 通知状态回调
                    for callback in self.status_callbacks:
                        callback(task_id, DownloadStatus.PENDING)
                    logger.info(f"任务 {task_id} 已暂停")
                    return True
            return False
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False
    
    def resume_task(self, task_id: str) -> bool:
        """恢复指定任务"""
        try:
            if task_id in self.download_tasks:
                task = self.download_tasks[task_id]
                if task.status in [DownloadStatus.PENDING, DownloadStatus.PAUSED]:
                    success = self.start_download(task_id)
                    if success:
                        logger.info(f"任务 {task_id} 已恢复")
                        return True
            return False
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """取消指定任务"""
        try:
            if task_id in self.download_tasks:
                task = self.download_tasks[task_id]
                if task.status in [DownloadStatus.PENDING, DownloadStatus.DOWNLOADING]:
                    task.status = DownloadStatus.CANCELLED
                    # 通知状态回调
                    for callback in self.status_callbacks:
                        callback(task_id, DownloadStatus.CANCELLED)
                    logger.info(f"任务 {task_id} 已取消")
                    return True
            return False
        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[DownloadStatus]:
        """获取任务状态"""
        if task_id in self.download_tasks:
            return self.download_tasks[task_id].status
        return None
    
    def get_all_tasks(self) -> Dict[str, DownloadTask]:
        """获取所有任务"""
        return self.download_tasks.copy()
    
    def get_task_statistics(self) -> Dict[str, int]:
        """获取任务统计信息"""
        stats = {
            'total': len(self.download_tasks),
            'pending': 0,
            'downloading': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        
        for task in self.download_tasks.values():
            if task.status == DownloadStatus.PENDING:
                stats['pending'] += 1
            elif task.status == DownloadStatus.DOWNLOADING:
                stats['downloading'] += 1
            elif task.status == DownloadStatus.COMPLETED:
                stats['completed'] += 1
            elif task.status == DownloadStatus.FAILED:
                stats['failed'] += 1
            elif task.status == DownloadStatus.CANCELLED:
                stats['cancelled'] += 1
        
        return stats
    
    def add_progress_callback(self, callback: Callable[[str, float], None]):
        """添加进度回调函数"""
        self.progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable[[str, DownloadStatus], None]):
        """添加状态回调函数"""
        self.status_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[str, float], None]):
        """移除进度回调函数"""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)
    
    def remove_status_callback(self, callback: Callable[[str, DownloadStatus], None]):
        """移除状态回调函数"""
        if callback in self.status_callbacks:
            self.status_callbacks.remove(callback)
    
    def add_download_task(self, url: str, title: str = None,
                         quality: str = "720p", format: str = "mp4", auto_start: bool = True, max_retries: int = 3,
                         skip_duplicate_check: bool = False) -> Optional[str]:
        """添加下载任务
        
        Args:
            url: 视频URL
            title: 视频标题
            quality: 视频质量
            format: 视频格式
            auto_start: 是否自动启动任务
            max_retries: 最大重试次数
            skip_duplicate_check: 是否跳过重复检测
        
        Returns:
            任务ID，失败返回None；如果是重复下载，返回特殊标识
        """
        # 检查重复下载（除非明确跳过）
        if not skip_duplicate_check:
            duplicate_info = self.check_duplicate_download(url)
            if duplicate_info:
                if duplicate_info.get('type') == 'partial':
                    # 恢复未完成的任务
                    task_id = duplicate_info['task_id']
                    if task_id in self.download_tasks:
                        logger.info(f"恢复未完成的下载任务: {task_id}")
                        return task_id
                else:
                    # 已完成的重复下载
                    logger.info(f"跳过重复下载: {url} -> {duplicate_info.get('file_path')}")
                    return "DUPLICATE_COMPLETED"
        
        platform = self.detect_platform(url)
        if not platform:
            logger.error(f"不支持的URL: {url}")
            return None
        
        # 获取视频信息
        if not title:
            video_info = self.get_video_info(url)
            if video_info:
                title = video_info.get('title', 'Unknown')
            else:
                title = 'Unknown'
        
        # 生成任务ID
        task_id = f"{platform}_{len(self.download_tasks)}_{hash(url) % 10000}"
        
        # 创建下载任务
        output_path = str(self.download_path / platform)
        download_task = DownloadTask(
            id=task_id,
            url=url,
            title=title,
            platform=platform,
            output_path=output_path,
            quality=quality,
            format=format,
            max_retries=max_retries
        )
        
        self.download_tasks[task_id] = download_task
        
        # 保存任务状态到持久化管理器
        self.persistence_manager.save_task_state(
            task_id=task_id,
            url=url,
            title=title,
            platform=platform,
            output_path=output_path,
            quality=quality,
            format=format,
            status=download_task.status.value,
            max_retries=max_retries
        )
        
        # 同时添加到核心任务管理器
        core_task = Task(
            task_id=task_id,
            name=f"[{platform}] {title}",
            task_type="爬虫下载",
            status=TaskStatus.PENDING,
            params={
                "url": url,
                "platform": platform,
                "quality": quality,
                "format": format,
                "output_path": download_task.output_path
            }
        )
        
        # 添加到核心任务管理器
        if self.core_task_manager.add_task(core_task):
            logger.info(f"添加下载任务到核心管理器: {task_id} - {title}")
            
            # 如果设置了自动启动且当前运行任务数未达到最大值，则自动启动
            if auto_start:
                running_count = self.core_task_manager.get_running_task_count()
                if running_count < self.core_task_manager.get_max_workers():
                    self.core_task_manager.start_task(task_id)
                    logger.info(f"自动启动任务: {task_id}")
        
        logger.info(f"添加下载任务: {task_id} - {title}")
        return task_id
    
    def start_download(self, task_id: str) -> bool:
        """开始下载任务"""
        if task_id not in self.download_tasks:
            logger.error(f"任务不存在: {task_id}")
            return False
        
        task = self.download_tasks[task_id]
        if task.status not in [DownloadStatus.PENDING, DownloadStatus.PAUSED]:
            logger.warning(f"任务状态不正确: {task_id} - {task.status}")
            return False
        
        try:
            # 更新任务状态
            self._update_task_status(task_id, DownloadStatus.DOWNLOADING)
            
            # 同步更新核心任务管理器状态
            self.core_task_manager.start_task(task_id)
            
            # 提交下载任务到线程池
            future = self.executor.submit(self._download_worker, task_id)
            
            logger.info(f"开始下载任务: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动下载任务失败: {e}")
            self._update_task_status(task_id, DownloadStatus.FAILED, str(e))
            # 同步更新核心任务管理器状态
            self.core_task_manager.fail_task(task_id, str(e))
            return False
    
    def _download_worker(self, task_id: str) -> None:
        """下载工作线程（支持重试和断点续传）"""
        task = self.download_tasks[task_id]
        crawler = self.crawlers[task.platform]
        
        while task.retry_count <= task.max_retries:
            try:
                # 创建输出目录
                output_dir = Path(task.output_path)
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # 定义进度回调
                def progress_callback(progress: float, downloaded: int = 0, total: int = 0):
                    task.progress = progress
                    task.downloaded_size = downloaded
                    if total > 0:
                        task.file_size = total
                    # 同步更新核心任务管理器进度
                    self.core_task_manager.update_task_progress(task_id, progress)
                    self._notify_progress(task_id, progress)
                    
                    # 保存进度到持久化管理器
                    self.persistence_manager.save_task_state(
                        task_id=task_id,
                        url=task.url,
                        title=task.title,
                        platform=task.platform,
                        output_path=task.output_path,
                        quality=task.quality,
                        format=task.format,
                        status=task.status.value,
                        progress=progress,
                        file_size=total,
                        downloaded_size=downloaded,
                        max_retries=task.max_retries,
                        retry_count=task.retry_count,
                        last_error=task.last_error
                    )
                
                # 如果是重试，记录重试信息
                if task.retry_count > 0:
                    logger.info(f"重试下载任务 {task_id} (第{task.retry_count}次重试，最大{task.max_retries}次)")
                    # 对于断点续传，不重置进度
                    if task.progress == 0.0:
                        task.downloaded_size = 0
                
                # 开始下载
                success = crawler.download_video(
                    task.url,
                    task.output_path,
                    quality=task.quality,
                    format=task.format,
                    progress_callback=progress_callback
                )
                
                if success:
                    self._update_task_status(task_id, DownloadStatus.COMPLETED)
                    
                    # 查找下载的文件路径
                    output_dir = Path(task.output_path)
                    downloaded_files = list(output_dir.glob(f"*{task.title}*"))
                    final_file_path = str(downloaded_files[0]) if downloaded_files else str(output_dir / f"{task.title}.{task.format}")
                    
                    # 标记任务完成并移动到已完成记录
                    self.persistence_manager.mark_task_completed(task_id, final_file_path)
                    
                    logger.info(f"下载完成: {task_id} -> {final_file_path}")
                    return
                else:
                    # 下载失败，准备重试
                    error_msg = f"下载失败 (尝试 {task.retry_count + 1}/{task.max_retries + 1})"
                    task.last_error = error_msg
                    task.retry_count += 1
                    
                    if task.retry_count <= task.max_retries:
                        logger.warning(f"下载失败，准备重试: {task_id} - {error_msg}")
                        # 等待一段时间再重试
                        import time
                        time.sleep(min(task.retry_count * 2, 10))  # 递增等待时间，最多10秒
                        continue
                    else:
                        # 超过最大重试次数
                        final_error = f"下载失败，已达到最大重试次数 ({task.max_retries}次)"
                        self._update_task_status(task_id, DownloadStatus.FAILED, final_error)
                        
                        # 更新持久化状态
                        self.persistence_manager.save_task_state(
                            task_id=task_id,
                            url=task.url,
                            title=task.title,
                            platform=task.platform,
                            output_path=task.output_path,
                            quality=task.quality,
                            format=task.format,
                            status=DownloadStatus.FAILED.value,
                            progress=task.progress,
                            file_size=task.file_size,
                            downloaded_size=task.downloaded_size,
                            max_retries=task.max_retries,
                            retry_count=task.retry_count,
                            last_error=final_error
                        )
                        
                        logger.error(f"任务最终失败: {task_id} - {final_error}")
                        return
                        
            except Exception as e:
                error_msg = f"下载异常: {str(e)} (尝试 {task.retry_count + 1}/{task.max_retries + 1})"
                task.last_error = error_msg
                task.retry_count += 1
                
                if task.retry_count <= task.max_retries:
                    logger.warning(f"下载异常，准备重试: {task_id} - {error_msg}")
                    # 等待一段时间再重试
                    import time
                    time.sleep(min(task.retry_count * 2, 10))  # 递增等待时间，最多10秒
                    continue
                else:
                    # 超过最大重试次数
                    final_error = f"下载异常，已达到最大重试次数 ({task.max_retries}次): {str(e)}"
                    self._update_task_status(task_id, DownloadStatus.FAILED, final_error)
                    logger.error(f"任务最终失败: {task_id} - {final_error}")
                    return
    
    def cancel_download(self, task_id: str) -> bool:
        """取消下载任务"""
        if task_id not in self.download_tasks:
            return False
        
        task = self.download_tasks[task_id]
        if task.status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
            return False
        
        self._update_task_status(task_id, DownloadStatus.CANCELLED)
        logger.info(f"取消下载任务: {task_id}")
        return True
    
    def get_task_status(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务状态"""
        return self.download_tasks.get(task_id)
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        return list(self.download_tasks.values())
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        if task_id in self.download_tasks:
            task = self.download_tasks[task_id]
            
            # 如果任务正在运行，先取消
            if task.status == DownloadStatus.DOWNLOADING:
                self.cancel_download(task_id)
            
            # 从核心任务管理器中移除
            self.core_task_manager.remove_task(task_id)
            
            del self.download_tasks[task_id]
            logger.info(f"移除任务: {task_id}")
            return True
        
        logger.warning(f"任务不存在: {task_id}")
        return False
    
    def add_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """添加进度回调函数"""
        self.progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable[[str, DownloadStatus], None]) -> None:
        """添加状态回调函数"""
        self.status_callbacks.append(callback)
    
    def _update_task_status(self, task_id: str, status: DownloadStatus, error_message: str = "") -> None:
        """更新任务状态"""
        if task_id in self.download_tasks:
            self.download_tasks[task_id].status = status
            if error_message:
                self.download_tasks[task_id].error_message = error_message
            
            # 同步更新核心任务管理器状态
            if status == DownloadStatus.DOWNLOADING:
                # 已在start_download中处理
                pass
            elif status == DownloadStatus.COMPLETED:
                self.core_task_manager.complete_task(task_id)
            elif status == DownloadStatus.FAILED:
                self.core_task_manager.fail_task(task_id, error_message)
            elif status == DownloadStatus.PAUSED:
                self.core_task_manager.pause_task(task_id)
            elif status == DownloadStatus.CANCELLED:
                self.core_task_manager.cancel_task(task_id)
            
            self._notify_status(task_id, status)
    
    def _notify_progress(self, task_id: str, progress: float) -> None:
        """通知进度更新"""
        for callback in self.progress_callbacks:
            try:
                callback(task_id, progress)
            except Exception as e:
                logger.error(f"进度回调异常: {e}")
    
    def _notify_status(self, task_id: str, status: DownloadStatus) -> None:
        """通知状态更新"""
        for callback in self.status_callbacks:
            try:
                callback(task_id, status)
            except Exception as e:
                logger.error(f"状态回调异常: {e}")
    
    def crawl(self, url: str, platform: str = None, output_dir: str = None, 
             progress_callback=None, **options) -> Dict[str, Any]:
        """爬取视频（兼容旧接口）
        
        Args:
            url: 视频URL
            platform: 平台名称（可选，会自动检测）
            output_dir: 输出目录
            progress_callback: 进度回调函数
            **options: 其他选项
        
        Returns:
            爬取结果
        """
        try:
            # 检测平台
            if not platform:
                platform = self.detect_platform(url)
                if not platform:
                    raise ValueError(f"不支持的URL: {url}")
            
            # 获取视频信息
            video_info = self.get_video_info(url)
            if not video_info:
                raise ValueError("无法获取视频信息")
            
            # 设置默认输出目录
            if not output_dir:
                output_dir = str(self.download_path / platform)
            
            # 添加下载任务
            task_id = self.add_download_task(
                url=url,
                title=video_info.get('title', 'Unknown'),
                quality=options.get('quality', '720p'),
                format=options.get('format', 'mp4'),
                auto_start=True,  # 确保自动启动
                skip_duplicate_check=False
            )
            
            if not task_id:
                raise ValueError("创建下载任务失败")
            
            # 如果有进度回调，添加到任务
            if progress_callback:
                def wrapped_callback(tid: str, progress: float):
                    if tid == task_id:
                        progress_callback(progress)
                self.add_progress_callback(wrapped_callback)
            
            # 开始下载
            success = self.start_download(task_id)
            if not success:
                raise ValueError("启动下载失败")
            
            # 等待下载完成（简化版本，实际应该异步处理）
            import time
            while True:
                task = self.get_task_status(task_id)
                if not task:
                    break
                    
                if task.status == DownloadStatus.COMPLETED:
                    return {
                        'success': True,
                        'task_id': task_id,
                        'video_info': video_info,
                        'output_path': task.output_path
                    }
                elif task.status == DownloadStatus.FAILED:
                    raise ValueError(f"下载失败: {task.error_message}")
                elif task.status == DownloadStatus.CANCELLED:
                    raise ValueError("下载被取消")
                
                time.sleep(0.1)  # 短暂等待
                
        except Exception as e:
            logger.error(f"爬取失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def set_max_concurrent(self, max_concurrent: int) -> None:
        """设置最大并发数"""
        try:
            if max_concurrent <= 0:
                raise ValueError("最大并发数必须大于0")
            
            old_max_concurrent = self.max_concurrent
            self.max_concurrent = max_concurrent
            
            # 更新核心任务管理器的最大工作线程数
            if self.core_task_manager:
                self.core_task_manager.max_workers = max_concurrent
            
            # 重新创建线程池（如果需要）
            if self.executor and old_max_concurrent != max_concurrent:
                # 等待当前任务完成
                self.executor.shutdown(wait=False)
                # 创建新的线程池
                self.executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_concurrent
                )
            
            logger.info(f"最大并发数已更新: {old_max_concurrent} -> {max_concurrent}")
            
        except Exception as e:
            logger.error(f"设置最大并发数失败: {e}")
    
    def get_download_history(self) -> Dict[str, Any]:
        """获取下载历史
        
        Returns:
            下载历史信息
        """
        return {
            "total_tasks": len(self.download_tasks),
            "completed_tasks": len([t for t in self.download_tasks.values() 
                                   if t.status == DownloadStatus.COMPLETED]),
            "failed_tasks": len([t for t in self.download_tasks.values() 
                               if t.status == DownloadStatus.FAILED]),
            "tasks": {task_id: {
                "title": task.title,
                "url": task.url,
                "status": task.status.value,
                "progress": task.progress,
                "error": task.error_message
            } for task_id, task in self.download_tasks.items()}
        }
    
    def get_downloaded_files(self) -> List[Dict[str, Any]]:
        """获取已下载文件列表
        
        Returns:
            已下载文件信息列表
        """
        return self.persistence_manager.get_completed_downloads()
    
    def clear_completed_tasks(self) -> int:
        """清理已完成的任务
        
        Returns:
            清理的任务数量
        """
        completed_tasks = [task_id for task_id, task in self.download_tasks.items() 
                          if task.status == DownloadStatus.COMPLETED]
        
        for task_id in completed_tasks:
            del self.download_tasks[task_id]
            # 从核心任务管理器中移除
            if hasattr(self.core_task_manager, 'remove_task'):
                self.core_task_manager.remove_task(task_id)
        
        return len(completed_tasks)
    
    def is_url_downloaded(self, url: str) -> bool:
        """检查URL是否已下载
        
        Args:
            url: 要检查的URL
            
        Returns:
            是否已下载
        """
        return self.persistence_manager.is_url_downloaded(url)
    
    def cleanup(self) -> None:
        """清理资源"""
        logger.info("清理爬虫管理器资源")
        
        # 取消所有下载任务
        for task_id in list(self.download_tasks.keys()):
            if self.download_tasks[task_id].status == DownloadStatus.DOWNLOADING:
                self.cancel_download(task_id)
        
        # 关闭线程池
        if self.executor:
            self.executor.shutdown(wait=True)
        
        # 清理爬虫
        for crawler in self.crawlers.values():
            crawler.cleanup()