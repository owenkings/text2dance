# -*- coding: utf-8 -*-
"""
任务持久化管理器
提供下载任务的状态保存和恢复功能，支持断点续传
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import asdict, dataclass
from loguru import logger


@dataclass
class TaskState:
    """任务状态数据类"""
    task_id: str
    url: str
    title: str
    platform: str
    output_path: str
    quality: str
    format: str
    status: str
    progress: float
    file_size: int
    downloaded_size: int
    max_retries: int
    retry_count: int
    last_error: str
    created_time: str
    updated_time: str
    partial_file_path: Optional[str] = None  # 部分下载文件路径
    url_hash: Optional[str] = None  # URL哈希，用于重复检测


class TaskPersistenceManager:
    """任务持久化管理器"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 任务状态文件
        self.tasks_file = self.data_dir / "download_tasks.json"
        # 已完成任务记录文件（用于重复检测）
        self.completed_file = self.data_dir / "completed_downloads.json"
        
        # 内存中的任务状态
        self.active_tasks: Dict[str, TaskState] = {}
        self.completed_tasks: Dict[str, Dict[str, Any]] = {}  # url_hash -> task_info
        
        self._load_tasks()
        self._load_completed_tasks()
    
    def _generate_url_hash(self, url: str) -> str:
        """生成URL的哈希值，用于重复检测"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def _load_tasks(self) -> None:
        """加载活跃任务状态"""
        try:
            if self.tasks_file.exists():
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for task_data in data.get('tasks', []):
                        task_state = TaskState(**task_data)
                        self.active_tasks[task_state.task_id] = task_state
                logger.info(f"加载了 {len(self.active_tasks)} 个活跃任务")
        except Exception as e:
            logger.error(f"加载任务状态失败: {e}")
    
    def _load_completed_tasks(self) -> None:
        """加载已完成任务记录"""
        try:
            if self.completed_file.exists():
                with open(self.completed_file, 'r', encoding='utf-8') as f:
                    self.completed_tasks = json.load(f)
                logger.info(f"加载了 {len(self.completed_tasks)} 个已完成任务记录")
        except Exception as e:
            logger.error(f"加载已完成任务记录失败: {e}")
    
    def _save_tasks(self) -> None:
        """保存活跃任务状态"""
        try:
            data = {
                'tasks': [asdict(task) for task in self.active_tasks.values()],
                'last_updated': datetime.now().isoformat()
            }
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存任务状态失败: {e}")
    
    def _save_completed_tasks(self) -> None:
        """保存已完成任务记录"""
        try:
            with open(self.completed_file, 'w', encoding='utf-8') as f:
                json.dump(self.completed_tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存已完成任务记录失败: {e}")
    
    def save_task_state(self, task_id: str, url: str, title: str, platform: str,
                       output_path: str, quality: str, format: str, status: str,
                       progress: float = 0.0, file_size: int = 0, downloaded_size: int = 0,
                       max_retries: int = 3, retry_count: int = 0, last_error: str = "",
                       partial_file_path: Optional[str] = None) -> None:
        """保存任务状态"""
        url_hash = self._generate_url_hash(url)
        current_time = datetime.now().isoformat()
        
        # 创建或更新任务状态
        if task_id in self.active_tasks:
            task_state = self.active_tasks[task_id]
            task_state.status = status
            task_state.progress = progress
            task_state.file_size = file_size
            task_state.downloaded_size = downloaded_size
            task_state.retry_count = retry_count
            task_state.last_error = last_error
            task_state.updated_time = current_time
            if partial_file_path:
                task_state.partial_file_path = partial_file_path
        else:
            task_state = TaskState(
                task_id=task_id,
                url=url,
                title=title,
                platform=platform,
                output_path=output_path,
                quality=quality,
                format=format,
                status=status,
                progress=progress,
                file_size=file_size,
                downloaded_size=downloaded_size,
                max_retries=max_retries,
                retry_count=retry_count,
                last_error=last_error,
                created_time=current_time,
                updated_time=current_time,
                partial_file_path=partial_file_path,
                url_hash=url_hash
            )
            self.active_tasks[task_id] = task_state
        
        self._save_tasks()
    
    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """获取任务状态"""
        return self.active_tasks.get(task_id)
    
    def get_all_active_tasks(self) -> List[TaskState]:
        """获取所有活跃任务"""
        return list(self.active_tasks.values())
    
    def remove_task(self, task_id: str) -> None:
        """移除任务"""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
            self._save_tasks()
    
    def mark_task_completed(self, task_id: str, final_file_path: str) -> None:
        """标记任务完成并移动到已完成记录"""
        if task_id in self.active_tasks:
            task_state = self.active_tasks[task_id]
            
            # 添加到已完成记录
            self.completed_tasks[task_state.url_hash] = {
                'url': task_state.url,
                'title': task_state.title,
                'platform': task_state.platform,
                'file_path': final_file_path,
                'quality': task_state.quality,
                'format': task_state.format,
                'completed_time': datetime.now().isoformat(),
                'file_size': task_state.file_size
            }
            
            # 从活跃任务中移除
            del self.active_tasks[task_id]
            
            self._save_tasks()
            self._save_completed_tasks()
    
    def is_url_downloaded(self, url: str) -> Optional[Dict[str, Any]]:
        """检查URL是否已经下载过
        
        Returns:
            如果已下载，返回下载信息；否则返回None
        """
        url_hash = self._generate_url_hash(url)
        return self.completed_tasks.get(url_hash)
    
    def find_partial_download(self, url: str) -> Optional[TaskState]:
        """查找未完成的下载任务
        
        Returns:
            如果找到未完成的任务，返回任务状态；否则返回None
        """
        url_hash = self._generate_url_hash(url)
        for task_state in self.active_tasks.values():
            if (task_state.url_hash == url_hash and 
                task_state.status in ['downloading', 'paused', 'failed'] and
                task_state.progress > 0):
                return task_state
        return None
    
    def cleanup_invalid_tasks(self) -> None:
        """清理无效的任务（如部分文件不存在等）"""
        invalid_tasks = []
        
        for task_id, task_state in self.active_tasks.items():
            # 检查部分下载文件是否存在
            if (task_state.partial_file_path and 
                not Path(task_state.partial_file_path).exists()):
                logger.warning(f"部分下载文件不存在，重置任务进度: {task_id}")
                task_state.progress = 0.0
                task_state.downloaded_size = 0
                task_state.partial_file_path = None
        
        # 移除无效任务
        for task_id in invalid_tasks:
            del self.active_tasks[task_id]
        
        if invalid_tasks:
            self._save_tasks()
            logger.info(f"清理了 {len(invalid_tasks)} 个无效任务")
    
    def get_download_statistics(self) -> Dict[str, Any]:
        """获取下载统计信息"""
        active_count = len(self.active_tasks)
        completed_count = len(self.completed_tasks)
        
        # 统计各状态的任务数量
        status_counts = {}
        total_size = 0
        for task_state in self.active_tasks.values():
            status = task_state.status
            status_counts[status] = status_counts.get(status, 0) + 1
            total_size += task_state.file_size
        
        return {
            'active_tasks': active_count,
            'completed_tasks': completed_count,
            'status_distribution': status_counts,
            'total_download_size': total_size
        }