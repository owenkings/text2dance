#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心任务管理器
提供统一的任务管理功能
"""

import uuid
import time
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from PyQt5.QtCore import QObject, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..utils.logger import Logger


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务数据类"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    task_type: str = "unknown"
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    priority: int = 5
    params: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_time: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.name:
            self.name = f"Task_{self.task_id[:8]}"


class TaskManager(QObject):
    """核心任务管理器"""
    
    # 信号定义
    task_added = pyqtSignal(Task)
    task_updated = pyqtSignal(Task)
    task_removed = pyqtSignal(str)  # task_id
    task_started = pyqtSignal(str)  # task_id
    task_completed = pyqtSignal(str)  # task_id
    task_failed = pyqtSignal(str, str)  # task_id, error
    batch_progress_updated = pyqtSignal(int, int)  # current, total
    
    def __init__(self, max_workers: int = 15):
        super().__init__()
        
        self.logger = Logger().get_logger("TaskManager")
        self.tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, Task] = {}
        
        # 线程池配置
        self.max_workers = max_workers
        self.thread_pool: Optional[ThreadPoolExecutor] = None
        self.is_batch_running = False
        self._lock = threading.Lock()
        
        self.logger.info(f"任务管理器初始化完成，最大线程数: {max_workers}")
    
    def add_task(self, task: Task) -> bool:
        """添加任务"""
        try:
            if task.task_id in self.tasks:
                self.logger.warning(f"任务已存在: {task.task_id}")
                return False
            
            self.tasks[task.task_id] = task
            self.task_added.emit(task)
            
            self.logger.info(f"添加任务: {task.task_id} - {task.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加任务失败: {e}")
            return False
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        try:
            if task_id not in self.tasks:
                self.logger.warning(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            
            # 如果任务正在运行，先取消
            if task.status == TaskStatus.RUNNING:
                self.cancel_task(task_id)
            
            del self.tasks[task_id]
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self.task_removed.emit(task_id)
            
            self.logger.info(f"移除任务: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"移除任务失败: {e}")
            return False
    
    def start_task(self, task_id: str) -> bool:
        """开始任务"""
        try:
            if task_id not in self.tasks:
                self.logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            
            if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
                self.logger.warning(f"任务状态不允许启动: {task_id} - {task.status}")
                return False
            
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.start_time = datetime.now()
            
            self.running_tasks[task_id] = task
            
            self.task_updated.emit(task)
            self.task_started.emit(task_id)
            
            self.logger.info(f"启动任务: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动任务失败: {e}")
            return False
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        try:
            if task_id not in self.tasks:
                self.logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            
            if task.status != TaskStatus.RUNNING:
                self.logger.warning(f"任务未在运行: {task_id} - {task.status}")
                return False
            
            # 更新任务状态
            task.status = TaskStatus.PAUSED
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self.task_updated.emit(task)
            
            self.logger.info(f"暂停任务: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"暂停任务失败: {e}")
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            if task_id not in self.tasks:
                self.logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                self.logger.warning(f"任务已结束: {task_id} - {task.status}")
                return False
            
            # 更新任务状态
            task.status = TaskStatus.CANCELLED
            task.end_time = datetime.now()
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self.task_updated.emit(task)
            
            self.logger.info(f"取消任务: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"取消任务失败: {e}")
            return False
    
    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """完成任务"""
        try:
            if task_id not in self.tasks:
                self.logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            
            # 更新任务状态
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            task.end_time = datetime.now()
            task.result = result
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self.task_updated.emit(task)
            self.task_completed.emit(task_id)
            
            self.logger.info(f"完成任务: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"完成任务失败: {e}")
            return False
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """任务失败"""
        try:
            if task_id not in self.tasks:
                self.logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            
            # 更新任务状态
            task.status = TaskStatus.FAILED
            task.end_time = datetime.now()
            task.error = error
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self.task_updated.emit(task)
            self.task_failed.emit(task_id, error)
            
            self.logger.error(f"任务失败: {task_id} - {error}")
            return True
            
        except Exception as e:
            self.logger.error(f"设置任务失败状态失败: {e}")
            return False
    
    def update_task_progress(self, task_id: str, progress: float) -> bool:
        """更新任务进度"""
        try:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.progress = max(0.0, min(100.0, progress))
            
            self.task_updated.emit(task)
            return True
            
        except Exception as e:
            self.logger.error(f"更新任务进度失败: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """根据状态获取任务"""
        return [task for task in self.tasks.values() if task.status == status]
    
    def get_running_tasks(self) -> List[Task]:
        """获取运行中的任务"""
        return list(self.running_tasks.values())
    
    def get_task_count(self) -> int:
        """获取任务总数"""
        return len(self.tasks)
    
    def get_running_task_count(self) -> int:
        """获取运行中任务数"""
        return len(self.running_tasks)
    
    def clear_completed_tasks(self) -> int:
        """清理已完成的任务"""
        try:
            completed_statuses = [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            completed_tasks = [task for task in self.tasks.values() if task.status in completed_statuses]
            
            count = 0
            for task in completed_tasks:
                if self.remove_task(task.task_id):
                    count += 1
            
            self.logger.info(f"清理了 {count} 个已完成任务")
            return count
            
        except Exception as e:
            self.logger.error(f"清理已完成任务失败: {e}")
            return 0
    
    def get_task_statistics(self) -> Dict[str, int]:
        """获取任务统计信息"""
        stats = {
            "total": len(self.tasks),
            "pending": 0,
            "running": 0,
            "paused": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                stats["pending"] += 1
            elif task.status == TaskStatus.RUNNING:
                stats["running"] += 1
            elif task.status == TaskStatus.PAUSED:
                stats["paused"] += 1
            elif task.status == TaskStatus.COMPLETED:
                stats["completed"] += 1
            elif task.status == TaskStatus.FAILED:
                stats["failed"] += 1
            elif task.status == TaskStatus.CANCELLED:
                stats["cancelled"] += 1
        
        return stats
    
    def set_max_workers(self, max_workers: int) -> bool:
        """设置最大工作线程数"""
        try:
            if max_workers <= 0:
                self.logger.error("最大工作线程数必须大于0")
                return False
            
            old_max_workers = self.max_workers
            self.max_workers = max_workers
            
            # 如果线程池正在运行，需要重新创建
            if self.thread_pool and not self.thread_pool._shutdown:
                self._stop_thread_pool()
                self._start_thread_pool()
            
            self.logger.info(f"更新最大工作线程数: {old_max_workers} -> {max_workers}")
            return True
            
        except Exception as e:
            self.logger.error(f"设置最大工作线程数失败: {e}")
            return False
    
    def _start_thread_pool(self):
        """启动线程池"""
        if not self.thread_pool or self.thread_pool._shutdown:
            self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
            self.logger.info(f"线程池已启动，最大线程数: {self.max_workers}")
    
    def _stop_thread_pool(self):
        """停止线程池"""
        if self.thread_pool and not self.thread_pool._shutdown:
            self.thread_pool.shutdown(wait=False)
            self.logger.info("线程池已停止")
    
    def start_all_pending_tasks(self) -> int:
        """批量启动所有等待中的任务"""
        try:
            with self._lock:
                pending_tasks = self.get_tasks_by_status(TaskStatus.PENDING)
                
                if not pending_tasks:
                    self.logger.info("没有等待中的任务")
                    return 0
                
                # 启动线程池
                self._start_thread_pool()
                self.is_batch_running = True
                
                started_count = 0
                total_tasks = len(pending_tasks)
                
                # 按优先级排序
                pending_tasks.sort(key=lambda t: t.priority, reverse=True)
                
                for i, task in enumerate(pending_tasks):
                    if self.start_task(task.task_id):
                        started_count += 1
                    
                    # 发送批量进度信号
                    self.batch_progress_updated.emit(i + 1, total_tasks)
                
                self.logger.info(f"批量启动任务完成: {started_count}/{total_tasks}")
                return started_count
                
        except Exception as e:
            self.logger.error(f"批量启动任务失败: {e}")
            return 0
    
    def pause_all_running_tasks(self) -> int:
        """批量暂停所有运行中的任务"""
        try:
            with self._lock:
                running_tasks = list(self.running_tasks.values())
                
                if not running_tasks:
                    self.logger.info("没有运行中的任务")
                    return 0
                
                paused_count = 0
                total_tasks = len(running_tasks)
                
                for i, task in enumerate(running_tasks):
                    if self.pause_task(task.task_id):
                        paused_count += 1
                    
                    # 发送批量进度信号
                    self.batch_progress_updated.emit(i + 1, total_tasks)
                
                self.is_batch_running = False
                self.logger.info(f"批量暂停任务完成: {paused_count}/{total_tasks}")
                return paused_count
                
        except Exception as e:
            self.logger.error(f"批量暂停任务失败: {e}")
            return 0
    
    def start_selected_tasks(self, task_ids: List[str]) -> int:
        """批量启动选中的任务"""
        try:
            if not task_ids:
                return 0
            
            with self._lock:
                # 启动线程池
                self._start_thread_pool()
                
                started_count = 0
                total_tasks = len(task_ids)
                
                for i, task_id in enumerate(task_ids):
                    task = self.get_task(task_id)
                    if task and task.status in [TaskStatus.PENDING, TaskStatus.PAUSED]:
                        if self.start_task(task_id):
                            started_count += 1
                    
                    # 发送批量进度信号
                    self.batch_progress_updated.emit(i + 1, total_tasks)
                
                self.logger.info(f"批量启动选中任务完成: {started_count}/{total_tasks}")
                return started_count
                
        except Exception as e:
            self.logger.error(f"批量启动选中任务失败: {e}")
            return 0
    
    def pause_selected_tasks(self, task_ids: List[str]) -> int:
        """批量暂停选中的任务"""
        try:
            if not task_ids:
                return 0
            
            with self._lock:
                paused_count = 0
                total_tasks = len(task_ids)
                
                for i, task_id in enumerate(task_ids):
                    task = self.get_task(task_id)
                    if task and task.status == TaskStatus.RUNNING:
                        if self.pause_task(task_id):
                            paused_count += 1
                    
                    # 发送批量进度信号
                    self.batch_progress_updated.emit(i + 1, total_tasks)
                
                self.logger.info(f"批量暂停选中任务完成: {paused_count}/{total_tasks}")
                return paused_count
                
        except Exception as e:
            self.logger.error(f"批量暂停选中任务失败: {e}")
            return 0
    
    def get_max_workers(self) -> int:
        """获取最大工作线程数"""
        return self.max_workers
    
    def is_thread_pool_running(self) -> bool:
        """检查线程池是否正在运行"""
        return self.thread_pool is not None and not self.thread_pool._shutdown
    
    def shutdown(self):
        """关闭任务管理器"""
        try:
            self.is_batch_running = False
            self._stop_thread_pool()
            self.logger.info("任务管理器已关闭")
        except Exception as e:
            self.logger.error(f"关闭任务管理器失败: {e}")