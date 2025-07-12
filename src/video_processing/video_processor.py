# -*- coding: utf-8 -*-
"""
视频处理器
基于MoviePy实现视频编辑功能
"""

import os
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

try:
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, CompositeVideoClip, 
        concatenate_videoclips, vfx, afx
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    logger.warning("MoviePy未安装，视频处理功能将受限")
    MOVIEPY_AVAILABLE = False

import cv2
import numpy as np


class ProcessingStatus(Enum):
    """处理状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingTask:
    """处理任务数据类"""
    id: str
    operation: str
    input_files: List[str]
    output_file: str
    parameters: Dict[str, Any]
    status: ProcessingStatus = ProcessingStatus.PENDING
    progress: float = 0.0
    error_message: str = ""


class VideoProcessor:
    """视频处理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.tasks: Dict[str, ProcessingTask] = {}
        self.temp_path = Path(config_manager.get('video_processing.temp_path', './temp'))
        self.output_path = Path(config_manager.get('video_processing.output_path', './output'))
        
        # 创建必要目录
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 回调函数
        self.progress_callbacks: List[Callable[[str, float], None]] = []
        self.status_callbacks: List[Callable[[str, ProcessingStatus], None]] = []
        
        # 当前处理的任务
        self.current_task = None
        self.processing_thread = None
        
        # 获取核心任务管理器实例
        try:
            from ..core.task_manager import CoreTaskManager
            self.core_task_manager = CoreTaskManager()
        except ImportError:
            self.core_task_manager = None
            logger.warning("核心任务管理器不可用")
    
    def get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
        """获取视频信息"""
        try:
            if not Path(video_path).exists():
                logger.error(f"视频文件不存在: {video_path}")
                return None
            
            # 检查文件大小
            file_size = Path(video_path).stat().st_size
            if file_size == 0:
                logger.error(f"视频文件为空: {video_path}")
                return None
            
            # 检查文件格式
            supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm']
            file_ext = Path(video_path).suffix.lower()
            if file_ext not in supported_formats:
                logger.warning(f"可能不支持的视频格式: {file_ext}")
            
            # 使用OpenCV获取基本信息
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                # 尝试使用FFMPEG后端
                cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    logger.error(f"无法打开视频文件: {video_path}")
                    return None
            
            # 验证视频流
            ret, test_frame = cap.read()
            if not ret or test_frame is None:
                cap.release()
                logger.error(f"视频文件无法读取帧数据: {video_path}")
                return None
            
            # 重置到开始位置
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 验证获取的信息
            if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
                cap.release()
                logger.error(f"视频信息无效: fps={fps}, frames={frame_count}, size={width}x{height}")
                return None
            
            duration = frame_count / fps if fps > 0 else 0
            
            cap.release()
            
            info = {
                'path': video_path,
                'duration': duration,
                'fps': fps,
                'frame_count': frame_count,
                'width': width,
                'height': height,
                'file_size': file_size,
                'format': Path(video_path).suffix.lower()
            }
            
            # 如果MoviePy可用，获取更详细信息
            if MOVIEPY_AVAILABLE:
                try:
                    clip = VideoFileClip(video_path)
                    info.update({
                        'has_audio': clip.audio is not None,
                        'audio_fps': clip.audio.fps if clip.audio else None
                    })
                    clip.close()
                except Exception as e:
                    logger.warning(f"MoviePy获取详细信息失败: {e}")
            
            return info
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            return None
    
    def create_preview(self, video_path: str, output_path: str = None, 
                      max_duration: int = 30, quality: str = "480p") -> Optional[str]:
        """创建视频预览"""
        try:
            if not MOVIEPY_AVAILABLE:
                logger.error("MoviePy不可用，无法创建预览")
                return None
            
            if not output_path:
                filename = Path(video_path).stem + "_preview.mp4"
                output_path = str(self.temp_path / filename)
            
            clip = VideoFileClip(video_path)
            
            # 限制预览时长
            if clip.duration > max_duration:
                clip = clip.subclip(0, max_duration)
            
            # 调整质量
            if quality == "480p":
                clip = clip.resize(height=480)
            elif quality == "360p":
                clip = clip.resize(height=360)
            elif quality == "720p":
                clip = clip.resize(height=720)
            
            # 输出预览
            clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            clip.close()
            logger.info(f"预览创建完成: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"创建预览失败: {e}")
            return None
    
    def add_task(self, operation: str, input_files: List[str], 
                output_file: str, parameters: Dict[str, Any] = None) -> str:
        """添加处理任务"""
        task_id = f"{operation}_{len(self.tasks)}_{hash(str(input_files)) % 10000}"
        
        task = ProcessingTask(
            id=task_id,
            operation=operation,
            input_files=input_files,
            output_file=output_file,
            parameters=parameters or {}
        )
        
        self.tasks[task_id] = task
        logger.info(f"添加处理任务: {task_id} - {operation}")
        
        return task_id
    
    def start_task(self, task_id: str) -> bool:
        """开始处理任务"""
        if task_id not in self.tasks:
            logger.error(f"任务不存在: {task_id}")
            return False
        
        if self.current_task:
            logger.warning("已有任务在处理中")
            return False
        
        task = self.tasks[task_id]
        if task.status != ProcessingStatus.PENDING:
            logger.warning(f"任务状态不正确: {task_id} - {task.status}")
            return False
        
        self.current_task = task_id
        self._update_task_status(task_id, ProcessingStatus.PROCESSING)
        
        # 同步到核心任务管理器
        if self.core_task_manager:
            try:
                from ..core.task_manager import Task, TaskStatus
                core_task = Task(
                    id=task_id,
                    name=f"视频处理: {task.operation}",
                    task_type="video_processing",
                    params={
                        'operation': task.operation,
                        'input_files': task.input_files,
                        'output_file': task.output_file,
                        **task.parameters
                    }
                )
                self.core_task_manager.add_task(core_task)
                self.core_task_manager.start_task(task_id)
            except Exception as e:
                logger.warning(f"同步任务到核心管理器失败: {e}")
        
        # 在新线程中处理
        self.processing_thread = threading.Thread(
            target=self._process_task,
            args=(task_id,)
        )
        self.processing_thread.start()
        
        return True
    
    def _process_task(self, task_id: str) -> None:
        """处理任务"""
        task = self.tasks[task_id]
        
        try:
            if task.operation == "cut":
                success = self._cut_video(task)
            elif task.operation == "compress":
                success = self._compress_video(task)
            elif task.operation == "concat":
                success = self._concatenate_videos(task)
            elif task.operation == "speed":
                success = self._change_speed(task)
            elif task.operation == "extract_audio":
                success = self._extract_audio(task)
            elif task.operation == "add_audio":
                success = self._add_audio(task)
            elif task.operation == "resize":
                success = self._resize_video(task)
            elif task.operation == "rotate":
                success = self._rotate_video(task)
            elif task.operation == "add_subtitle":
                success = self._add_subtitle(task)
            else:
                logger.error(f"不支持的操作: {task.operation}")
                success = False
            
            if success:
                self._update_task_status(task_id, ProcessingStatus.COMPLETED)
                # 同步完成状态到核心管理器
                if self.core_task_manager:
                    self.core_task_manager.complete_task(task_id)
                logger.info(f"任务处理完成: {task_id}")
            else:
                self._update_task_status(task_id, ProcessingStatus.FAILED, "处理失败")
                # 同步失败状态到核心管理器
                if self.core_task_manager:
                    self.core_task_manager.fail_task(task_id, "处理失败")
                
        except Exception as e:
            logger.error(f"任务处理异常: {task_id} - {e}")
            self._update_task_status(task_id, ProcessingStatus.FAILED, str(e))
            # 同步失败状态到核心管理器
            if self.core_task_manager:
                self.core_task_manager.fail_task(task_id, str(e))
        
        finally:
            self.current_task = None
    
    def _cut_video(self, task: ProcessingTask) -> bool:
        """剪切视频"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            input_file = task.input_files[0]
            start_time = task.parameters.get('start_time', 0)
            end_time = task.parameters.get('end_time')
            
            clip = VideoFileClip(input_file)
            
            if end_time:
                cut_clip = clip.subclip(start_time, end_time)
            else:
                cut_clip = clip.subclip(start_time)
            
            # 进度回调
            def progress_callback(t):
                if clip.duration > 0:
                    progress = (t / clip.duration) * 100
                    self._notify_progress(task.id, progress)
            
            cut_clip.write_videofile(
                task.output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            cut_clip.close()
            clip.close()
            
            return True
            
        except Exception as e:
            logger.error(f"剪切视频失败: {e}")
            return False
    
    def _compress_video(self, task: ProcessingTask) -> bool:
        """压缩视频"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            input_file = task.input_files[0]
            quality = task.parameters.get('quality', 'medium')
            target_size_mb = task.parameters.get('target_size_mb')
            
            clip = VideoFileClip(input_file)
            
            # 根据质量设置参数
            if quality == 'low':
                bitrate = '500k'
                clip = clip.resize(height=480)
            elif quality == 'medium':
                bitrate = '1000k'
                clip = clip.resize(height=720)
            elif quality == 'high':
                bitrate = '2000k'
            else:
                bitrate = quality  # 自定义比特率
            
            # 如果指定了目标大小，计算比特率
            if target_size_mb:
                target_bitrate = (target_size_mb * 8 * 1024) / clip.duration  # kbps
                bitrate = f'{int(target_bitrate)}k'
            
            clip.write_videofile(
                task.output_file,
                codec='libx264',
                bitrate=bitrate,
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            clip.close()
            return True
            
        except Exception as e:
            logger.error(f"压缩视频失败: {e}")
            return False
    
    def _concatenate_videos(self, task: ProcessingTask) -> bool:
        """拼接视频"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            clips = []
            for input_file in task.input_files:
                clip = VideoFileClip(input_file)
                clips.append(clip)
            
            # 拼接视频
            final_clip = concatenate_videoclips(clips)
            
            final_clip.write_videofile(
                task.output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # 清理
            final_clip.close()
            for clip in clips:
                clip.close()
            
            return True
            
        except Exception as e:
            logger.error(f"拼接视频失败: {e}")
            return False
    
    def _change_speed(self, task: ProcessingTask) -> bool:
        """调整播放速度"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            input_file = task.input_files[0]
            speed_factor = task.parameters.get('speed_factor', 1.0)
            
            clip = VideoFileClip(input_file)
            
            # 调整速度
            if speed_factor != 1.0:
                clip = clip.fx(vfx.speedx, speed_factor)
            
            clip.write_videofile(
                task.output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            clip.close()
            return True
            
        except Exception as e:
            logger.error(f"调整速度失败: {e}")
            return False
    
    def _extract_audio(self, task: ProcessingTask) -> bool:
        """提取音频"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            input_file = task.input_files[0]
            
            clip = VideoFileClip(input_file)
            if clip.audio is None:
                logger.error("视频没有音频轨道")
                clip.close()
                return False
            
            audio = clip.audio
            audio.write_audiofile(
                task.output_file,
                verbose=False,
                logger=None
            )
            
            audio.close()
            clip.close()
            return True
            
        except Exception as e:
            logger.error(f"提取音频失败: {e}")
            return False
    
    def _add_audio(self, task: ProcessingTask) -> bool:
        """添加音频"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            video_file = task.input_files[0]
            audio_file = task.input_files[1]
            
            video_clip = VideoFileClip(video_file)
            audio_clip = AudioFileClip(audio_file)
            
            # 调整音频长度匹配视频
            if audio_clip.duration > video_clip.duration:
                audio_clip = audio_clip.subclip(0, video_clip.duration)
            elif audio_clip.duration < video_clip.duration:
                # 循环音频
                loops = int(video_clip.duration / audio_clip.duration) + 1
                audio_clip = afx.loop(audio_clip, n=loops).subclip(0, video_clip.duration)
            
            # 合成
            final_clip = video_clip.set_audio(audio_clip)
            
            final_clip.write_videofile(
                task.output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            final_clip.close()
            video_clip.close()
            audio_clip.close()
            
            return True
            
        except Exception as e:
            logger.error(f"添加音频失败: {e}")
            return False
    
    def _resize_video(self, task: ProcessingTask) -> bool:
        """调整视频尺寸"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            input_file = task.input_files[0]
            width = task.parameters.get('width')
            height = task.parameters.get('height')
            
            clip = VideoFileClip(input_file)
            
            if width and height:
                clip = clip.resize((width, height))
            elif height:
                clip = clip.resize(height=height)
            elif width:
                clip = clip.resize(width=width)
            
            clip.write_videofile(
                task.output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            clip.close()
            return True
            
        except Exception as e:
            logger.error(f"调整尺寸失败: {e}")
            return False
    
    def _rotate_video(self, task: ProcessingTask) -> bool:
        """旋转视频"""
        try:
            if not MOVIEPY_AVAILABLE:
                return False
            
            input_file = task.input_files[0]
            angle = task.parameters.get('angle', 90)
            
            clip = VideoFileClip(input_file)
            
            # 旋转
            if angle == 90:
                clip = clip.fx(vfx.rotate, 90)
            elif angle == 180:
                clip = clip.fx(vfx.rotate, 180)
            elif angle == 270:
                clip = clip.fx(vfx.rotate, 270)
            else:
                clip = clip.fx(vfx.rotate, angle)
            
            clip.write_videofile(
                task.output_file,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(self.temp_path / 'temp_audio.m4a'),
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            clip.close()
            return True
            
        except Exception as e:
            logger.error(f"旋转视频失败: {e}")
            return False
    
    def _add_subtitle(self, task: ProcessingTask) -> bool:
        """添加字幕"""
        try:
            # 这里可以实现字幕添加功能
            # 需要额外的字幕处理库
            logger.warning("字幕添加功能待实现")
            return False
            
        except Exception as e:
            logger.error(f"添加字幕失败: {e}")
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
            return False
        
        self._update_task_status(task_id, ProcessingStatus.CANCELLED)
        
        # 同步取消状态到核心管理器
        if self.core_task_manager:
            self.core_task_manager.cancel_task(task_id)
        
        if self.current_task == task_id:
            self.current_task = None
        
        return True
    
    def get_task_status(self, task_id: str) -> Optional[ProcessingTask]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[ProcessingTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def add_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """添加进度回调"""
        self.progress_callbacks.append(callback)
    
    def add_status_callback(self, callback: Callable[[str, ProcessingStatus], None]) -> None:
        """添加状态回调"""
        self.status_callbacks.append(callback)
    
    def _update_task_status(self, task_id: str, status: ProcessingStatus, error_message: str = "") -> None:
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            if error_message:
                self.tasks[task_id].error_message = error_message
            self._notify_status(task_id, status)
    
    def _notify_progress(self, task_id: str, progress: float) -> None:
        """通知进度更新"""
        if task_id in self.tasks:
            self.tasks[task_id].progress = progress
        
        # 同步进度到核心管理器
        if self.core_task_manager:
            self.core_task_manager.update_progress(task_id, progress)
        
        for callback in self.progress_callbacks:
            try:
                callback(task_id, progress)
            except Exception as e:
                logger.error(f"进度回调异常: {e}")
    
    def _notify_status(self, task_id: str, status: ProcessingStatus) -> None:
        """通知状态更新"""
        for callback in self.status_callbacks:
            try:
                callback(task_id, status)
            except Exception as e:
                logger.error(f"状态回调异常: {e}")
    
    def cleanup(self) -> None:
        """清理资源"""
        logger.info("清理视频处理器资源")
        
        # 取消所有处理任务
        for task_id in list(self.tasks.keys()):
            if self.tasks[task_id].status == ProcessingStatus.PROCESSING:
                self.cancel_task(task_id)
        
        # 等待处理线程结束
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5)