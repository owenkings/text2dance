# -*- coding: utf-8 -*-
"""
算法管理器
统一管理2D/3D姿态估计和视频描述算法
"""

import logging
import threading
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

class AlgorithmType(Enum):
    """算法类型"""
    POSE_2D = "pose_2d"
    POSE_3D = "pose_3d"
    VIDEO_DESCRIPTION = "video_description"

class ProcessingStatus(Enum):
    """处理状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AlgorithmTask:
    """算法任务"""
    task_id: str
    algorithm_type: AlgorithmType
    algorithm_name: str
    input_path: str
    output_path: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    progress: float = 0.0
    error_message: str = ""
    result: Optional[Any] = None
    params: Dict[str, Any] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}

class AlgorithmManager:
    """算法管理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # 算法注册表
        self.algorithms = {
            AlgorithmType.POSE_2D: {},
            AlgorithmType.POSE_3D: {},
            AlgorithmType.VIDEO_DESCRIPTION: {}
        }
        
        # 任务管理
        self.tasks: Dict[str, AlgorithmTask] = {}
        self.task_threads: Dict[str, threading.Thread] = {}
        self.task_lock = threading.Lock()
        
        # 回调函数
        self.progress_callbacks: List[Callable[[str, float], None]] = []
        self.status_callbacks: List[Callable[[str, ProcessingStatus], None]] = []
        
        # 获取核心任务管理器实例
        try:
            from ..core.task_manager import CoreTaskManager
            self.core_task_manager = CoreTaskManager()
        except ImportError:
            self.core_task_manager = None
            self.logger.warning("核心任务管理器不可用")
        
        # 初始化算法
        self._initialize_algorithms()
    
    def _initialize_algorithms(self):
        """初始化算法"""
        try:
            # 导入并注册2D姿态估计算法
            self._register_pose_2d_algorithms()
            
            # 导入并注册3D姿态估计算法
            self._register_pose_3d_algorithms()
            
            # 导入并注册视频描述算法
            self._register_video_description_algorithms()
            
            self.logger.info("算法初始化完成")
            
        except Exception as e:
            self.logger.error(f"算法初始化失败: {e}")
    
    def _register_pose_2d_algorithms(self):
        """注册2D姿态估计算法"""
        try:
            from .pose_2d.openpose_algorithm import OpenPoseAlgorithm
            from .pose_2d.vitpose_algorithm import VitPoseAlgorithm
            from .pose_2d.rtmpose_algorithm import RTMPoseAlgorithm
            
            self.algorithms[AlgorithmType.POSE_2D] = {
                "openpose": OpenPoseAlgorithm(self.config_manager),
                "vitpose": VitPoseAlgorithm(self.config_manager),
                "rtmpose": RTMPoseAlgorithm(self.config_manager)
            }
            
        except ImportError as e:
            self.logger.warning(f"部分2D姿态估计算法导入失败: {e}")
    
    def _register_pose_3d_algorithms(self):
        """注册3D姿态估计算法"""
        try:
            # 只导入videopose3d算法，因为rtmpose3d算法文件不存在
            from .pose_3d.videopose3d_algorithm import VideoPose3DAlgorithm
            
            self.algorithms[AlgorithmType.POSE_3D] = {
                "videopose3d": VideoPose3DAlgorithm(self.config_manager)
            }
            
        except ImportError as e:
            self.logger.warning(f"部分3D姿态估计算法导入失败: {e}")
    
    def _register_video_description_algorithms(self):
        """注册视频描述算法"""
        try:
            from .video_description.describeanything_algorithm import DescribeAnythingAlgorithm
            from .video_description.vid2seq_algorithm import Vid2SeqAlgorithm
            from .video_description.sharegpt4video_algorithm import ShareGPT4VideoAlgorithm
            
            self.algorithms[AlgorithmType.VIDEO_DESCRIPTION] = {
                "describeanything": DescribeAnythingAlgorithm(self.config_manager),
                "vid2seq": Vid2SeqAlgorithm(self.config_manager),
                "sharegpt4video": ShareGPT4VideoAlgorithm(self.config_manager)
            }
            
        except ImportError as e:
            self.logger.warning(f"部分视频描述算法导入失败: {e}")
    
    def get_available_algorithms(self, algorithm_type: AlgorithmType) -> List[str]:
        """获取可用算法列表"""
        return list(self.algorithms[algorithm_type].keys())
    
    def get_algorithm_info(self, algorithm_type: AlgorithmType, algorithm_name: str) -> Dict[str, Any]:
        """获取算法信息"""
        if algorithm_name in self.algorithms[algorithm_type]:
            algorithm = self.algorithms[algorithm_type][algorithm_name]
            return {
                "name": algorithm_name,
                "type": algorithm_type.value,
                "description": getattr(algorithm, 'description', ''),
                "parameters": getattr(algorithm, 'parameters', {}),
                "supported_formats": getattr(algorithm, 'supported_formats', []),
                "model_path": getattr(algorithm, 'model_path', '')
            }
        return {}
    
    def add_task(self, task_id: str, algorithm_type: AlgorithmType, algorithm_name: str,
                 input_path: str, output_path: str, params: Dict[str, Any] = None) -> bool:
        """添加算法任务"""
        try:
            with self.task_lock:
                if task_id in self.tasks:
                    self.logger.warning(f"任务ID {task_id} 已存在")
                    return False
                
                if algorithm_name not in self.algorithms[algorithm_type]:
                    self.logger.error(f"算法 {algorithm_name} 不存在")
                    return False
                
                task = AlgorithmTask(
                    task_id=task_id,
                    algorithm_type=algorithm_type,
                    algorithm_name=algorithm_name,
                    input_path=input_path,
                    output_path=output_path,
                    params=params or {}
                )
                
                self.tasks[task_id] = task
                self.logger.info(f"添加算法任务: {task_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"添加任务失败: {e}")
            return False
    
    def start_task(self, task_id: str) -> bool:
        """启动算法任务"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    self.logger.error(f"任务 {task_id} 不存在")
                    return False
                
                task = self.tasks[task_id]
                if task.status != ProcessingStatus.PENDING:
                    self.logger.warning(f"任务 {task_id} 状态不是待处理")
                    return False
                
                # 创建处理线程
                thread = threading.Thread(
                    target=self._process_task,
                    args=(task_id,),
                    daemon=True
                )
                
                self.task_threads[task_id] = thread
                task.status = ProcessingStatus.RUNNING
                
                # 通知状态变化
                self._notify_status_change(task_id, ProcessingStatus.RUNNING)
                
                thread.start()
                self.logger.info(f"启动算法任务: {task_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"启动任务失败: {e}")
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """取消算法任务"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    return False
                
                task = self.tasks[task_id]
                if task.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
                    return False
                
                task.status = ProcessingStatus.CANCELLED
                self._notify_status_change(task_id, ProcessingStatus.CANCELLED)
                
                # 如果有线程在运行，等待其结束
                if task_id in self.task_threads:
                    thread = self.task_threads[task_id]
                    if thread.is_alive():
                        # 注意：这里只是标记取消，具体的取消逻辑需要在算法实现中处理
                        pass
                
                self.logger.info(f"取消算法任务: {task_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"取消任务失败: {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[AlgorithmTask]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[AlgorithmTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        try:
            with self.task_lock:
                if task_id not in self.tasks:
                    return False
                
                task = self.tasks[task_id]
                if task.status == ProcessingStatus.RUNNING:
                    self.cancel_task(task_id)
                
                del self.tasks[task_id]
                if task_id in self.task_threads:
                    del self.task_threads[task_id]
                
                self.logger.info(f"移除算法任务: {task_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"移除任务失败: {e}")
            return False
    
    def _process_task(self, task_id: str):
        """处理算法任务"""
        try:
            task = self.tasks[task_id]
            algorithm = self.algorithms[task.algorithm_type][task.algorithm_name]
            
            # 设置进度回调
            def progress_callback(progress: float):
                task.progress = progress
                self._notify_progress_change(task_id, progress)
            
            # 执行算法
            result = algorithm.process(
                input_path=task.input_path,
                output_path=task.output_path,
                progress_callback=progress_callback,
                **task.params
            )
            
            # 检查是否被取消
            if task.status == ProcessingStatus.CANCELLED:
                return
            
            # 更新任务状态
            task.result = result
            task.status = ProcessingStatus.COMPLETED
            task.progress = 100.0
            
            self._notify_progress_change(task_id, 100.0)
            self._notify_status_change(task_id, ProcessingStatus.COMPLETED)
            
            self.logger.info(f"算法任务完成: {task_id}")
            
        except Exception as e:
            self.logger.error(f"算法任务失败 {task_id}: {e}")
            
            task = self.tasks.get(task_id)
            if task:
                task.status = ProcessingStatus.FAILED
                task.error_message = str(e)
                self._notify_status_change(task_id, ProcessingStatus.FAILED)
    
    def add_progress_callback(self, callback: Callable[[str, float], None]):
        """添加进度回调"""
        self.progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable[[str, ProcessingStatus], None]):
        """添加状态回调"""
        self.status_callbacks.append(callback)
    
    def _notify_progress_change(self, task_id: str, progress: float):
        """通知进度变化"""
        for callback in self.progress_callbacks:
            try:
                callback(task_id, progress)
            except Exception as e:
                self.logger.error(f"进度回调失败: {e}")
    
    def _notify_status_change(self, task_id: str, status: ProcessingStatus):
        """通知状态变化"""
        for callback in self.status_callbacks:
            try:
                callback(task_id, status)
            except Exception as e:
                self.logger.error(f"状态回调失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            # 取消所有运行中的任务
            for task_id, task in self.tasks.items():
                if task.status == ProcessingStatus.RUNNING:
                    self.cancel_task(task_id)
            
            # 等待所有线程结束
            for thread in self.task_threads.values():
                if thread.is_alive():
                    thread.join(timeout=5.0)
            
            # 清理算法资源
            for algorithm_type in self.algorithms:
                for algorithm in self.algorithms[algorithm_type].values():
                    if hasattr(algorithm, 'cleanup'):
                        algorithm.cleanup()
            
            self.logger.info("算法管理器清理完成")
            
        except Exception as e:
            self.logger.error(f"算法管理器清理失败: {e}")