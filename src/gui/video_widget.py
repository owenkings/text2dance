# -*- coding: utf-8 -*-
"""
视频处理界面组件
提供视频处理和算法应用功能的用户界面
"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
from moviepy.editor import VideoFileClip, concatenate_videoclips
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QShortcut,
    QDialog, QAbstractItemView, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QMutex
from PyQt5.QtGui import QFont, QPixmap, QKeySequence, QImage, QIcon, QMovie, QColor

from ..algorithms.algorithm_manager import AlgorithmManager, AlgorithmType
from ..video_processing.video_processor import VideoProcessor
from ..utils.logger import Logger


def validate_video_file(video_path: str) -> tuple[bool, str]:
    """验证视频文件的有效性
    
    Args:
        video_path: 视频文件路径
        
    Returns:
        tuple: (是否有效, 错误信息)
    """
    try:
        # 检查文件是否存在
        if not Path(video_path).exists():
            return False, "视频文件不存在"
        
        # 检查文件大小
        file_size = Path(video_path).stat().st_size
        if file_size == 0:
            return False, "视频文件为空"
        
        if file_size < 1024:  # 小于1KB可能是损坏的文件
            return False, "视频文件过小，可能已损坏"
        
        # 检查文件扩展名
        supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm', '.mpg', '.mpeg']
        file_ext = Path(video_path).suffix.lower()
        if file_ext not in supported_formats:
            return False, f"不支持的视频格式: {file_ext}"
        
        # 尝试打开视频文件进行基本验证
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            # 尝试FFMPEG后端
            cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                return False, "无法打开视频文件，可能文件已损坏或格式不兼容"
        
        # 尝试读取第一帧
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            return False, "视频文件无法读取帧数据，可能已损坏"
        
        return True, ""
        
    except Exception as e:
        return False, f"验证视频文件时发生错误: {str(e)}"

class VideoProcessingThread(QThread):
    """视频处理工作线程"""
    
    progress_updated = pyqtSignal(float)
    status_updated = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    frame_processed = pyqtSignal(int, object)  # 帧号, 处理结果
    
    def __init__(self, algorithm_manager, video_processor, task_config):
        super().__init__()
        self.algorithm_manager = algorithm_manager
        self.video_processor = video_processor
        self.task_config = task_config
        self.is_running = True
    
    def run(self):
        try:
            # 执行视频处理任务
            result = self.video_processor.process_video(
                input_path=self.task_config['input_path'],
                algorithm_type=self.task_config['algorithm_type'],
                algorithm_name=self.task_config['algorithm_name'],
                output_path=self.task_config['output_path'],
                progress_callback=self.progress_updated.emit,
                status_callback=self.status_updated.emit,
                frame_callback=self.frame_processed.emit,
                **self.task_config.get('options', {})
            )
            
            if self.is_running:
                self.result_ready.emit(result)
                
        except Exception as e:
            if self.is_running:
                self.error_occurred.emit(str(e))
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()

class CommandExecutionThread(QThread):
    """指令执行工作线程"""
    
    progress_updated = pyqtSignal(int)  # 进度百分比
    status_updated = pyqtSignal(str)  # 状态信息
    operation_status_updated = pyqtSignal(object, str)  # 操作对象, 状态
    execution_completed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, operations, video_path, output_dir, max_workers=4):
        super().__init__()
        self.operations = operations
        self.video_path = video_path
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.is_running = True
        self.mutex = QMutex()
    
    def run(self):
        try:
            self.status_updated.emit("开始执行指令...")
            
            # 使用线程池执行操作
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_operation = {}
                for operation in self.operations:
                    if not self.is_running:
                        break
                    
                    future = executor.submit(self._execute_single_operation, operation)
                    future_to_operation[future] = operation
                
                # 处理完成的任务
                completed_count = 0
                total_count = len(self.operations)
                
                for future in as_completed(future_to_operation):
                    if not self.is_running:
                        break
                    
                    operation = future_to_operation[future]
                    
                    try:
                        result = future.result()
                        if result:
                            self.operation_status_updated.emit(operation, '已完成')
                        else:
                            self.operation_status_updated.emit(operation, '失败')
                    except Exception as e:
                        self.operation_status_updated.emit(operation, '失败')
                        self.error_occurred.emit(f"执行操作失败: {operation.get('description', '未知操作')}, 错误: {str(e)}")
                    
                    completed_count += 1
                    progress = int((completed_count / total_count) * 100)
                    self.progress_updated.emit(progress)
                    
                    self.status_updated.emit(f"已完成 {completed_count}/{total_count} 个操作")
            
            if self.is_running:
                self.execution_completed.emit()
                self.status_updated.emit("所有指令执行完成")
                
        except Exception as e:
            if self.is_running:
                self.error_occurred.emit(f"执行指令时发生错误: {str(e)}")
    
    def _execute_single_operation(self, operation):
        """执行单个操作"""
        try:
            # 更新操作状态为执行中
            self.operation_status_updated.emit(operation, '执行中')
            
            if operation['type'] == 'split':
                return self._execute_split_operation(operation)
            elif operation['type'] == 'delete':
                return self._execute_delete_operation(operation)
            # 可以在这里添加其他类型的操作
            
            return False
            
        except Exception as e:
            self.operation_status_updated.emit(operation, '失败')
            raise e
    
    def _execute_split_operation(self, operation):
        """执行分割操作"""
        try:
            # 获取分割的开始和结束帧
            start_frame = operation.get('start_frame', 0)
            end_frame = operation.get('end_frame')
            
            if end_frame is None:
                return False
            
            # 加载视频
            video_clip = VideoFileClip(self.video_path)
            
            # 将帧号转换为时间
            fps = video_clip.fps
            start_time = start_frame / fps
            end_time = end_frame / fps
            
            # 创建子剪辑
            subclip = video_clip.subclip(start_time, end_time)
            
            # 生成输出文件名
            base_name = os.path.splitext(os.path.basename(self.video_path))[0]
            output_filename = f"{base_name}_split_{start_frame}_{end_frame}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # 写入文件
            subclip.write_videofile(output_path, verbose=False, logger=None)
            subclip.close()
            video_clip.close()
            
            return True
            
        except Exception as e:
            raise e
    
    def _execute_delete_operation(self, operation):
        """执行删除操作（实际上是保留其他部分）"""
        try:
            # 这里可以实现删除操作的逻辑
            # 暂时返回True表示成功
            return True
            
        except Exception as e:
            raise e
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()

class CommandExecutionThread(QThread):
    """指令执行线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int)  # 进度更新
    status_updated = pyqtSignal(str)    # 状态更新
    operation_status_updated = pyqtSignal(dict, str)  # 操作状态更新
    execution_completed = pyqtSignal()  # 执行完成
    error_occurred = pyqtSignal(str)    # 错误发生
    
    def __init__(self, operations, video_path, output_dir, max_workers=4):
        super().__init__()
        self.operations = operations
        self.video_path = video_path
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.is_running = False
        
    def run(self):
        """执行线程主函数"""
        self.is_running = True
        
        try:
            self.status_updated.emit("正在初始化...")
            
            # 使用线程池执行操作
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_operation = {}
                for operation in self.operations:
                    future = executor.submit(self._execute_single_operation, operation)
                    future_to_operation[future] = operation
                
                # 处理完成的任务
                completed_count = 0
                total_count = len(self.operations)
                
                for future in as_completed(future_to_operation):
                    if not self.is_running:
                        break
                    
                    operation = future_to_operation[future]
                    
                    try:
                        result = future.result()
                        if result:
                            self.operation_status_updated.emit(operation, '已完成')
                        else:
                            self.operation_status_updated.emit(operation, '失败')
                    except Exception as e:
                        self.operation_status_updated.emit(operation, '失败')
                        print(f"操作执行失败: {operation.get('description', '未知操作')}, 错误: {str(e)}")
                    
                    completed_count += 1
                    progress = int((completed_count / total_count) * 100)
                    self.progress_updated.emit(progress)
                    
                    self.status_updated.emit(f"已完成 {completed_count}/{total_count} 个操作")
            
            if self.is_running:
                self.status_updated.emit("所有操作执行完成")
                self.execution_completed.emit()
            
        except Exception as e:
            self.error_occurred.emit(f"执行过程中发生错误: {str(e)}")
        
        finally:
            self.is_running = False
    
    def _execute_single_operation(self, operation):
        """执行单个操作"""
        try:
            # 更新操作状态为执行中
            self.operation_status_updated.emit(operation, '执行中')
            
            if operation['type'] == 'split':
                return self._execute_split_operation(operation)
            elif operation['type'] == 'delete':
                return self._execute_delete_operation(operation)
            else:
                print(f"未知操作类型: {operation['type']}")
                return False
                
        except Exception as e:
            print(f"执行操作失败: {operation.get('description', '未知操作')}, 错误: {str(e)}")
            return False
    
    def _execute_split_operation(self, operation):
        """执行分割操作"""
        try:
            from moviepy.editor import VideoFileClip
            
            # 获取分割的开始和结束帧
            start_frame = operation.get('start_frame', 0)
            end_frame = operation.get('end_frame')
            
            if end_frame is None:
                print(f"分割操作缺少结束帧: {operation['description']}")
                return False
            
            # 加载视频
            video_clip = VideoFileClip(self.video_path)
            
            # 将帧号转换为时间
            fps = video_clip.fps
            start_time = start_frame / fps
            end_time = end_frame / fps
            
            # 创建子剪辑
            subclip = video_clip.subclip(start_time, end_time)
            
            # 生成输出文件名
            base_name = os.path.splitext(os.path.basename(self.video_path))[0]
            output_filename = f"{base_name}_split_{start_frame}_{end_frame}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # 写入文件
            subclip.write_videofile(output_path, verbose=False, logger=None)
            
            # 清理资源
            subclip.close()
            video_clip.close()
            
            print(f"分割完成: {output_filename}")
            return True
            
        except Exception as e:
            print(f"分割操作失败: {str(e)}")
            return False
    
    def _execute_delete_operation(self, operation):
        """执行删除操作"""
        try:
            # TODO: 实现删除操作
            print(f"删除操作: {operation.get('description', '未知删除操作')}")
            time.sleep(1)  # 模拟处理时间
            return True
            
        except Exception as e:
            print(f"删除操作失败: {str(e)}")
            return False
    
    def stop(self):
        """停止执行"""
        self.is_running = False


class VideoPreviewDialog(QDialog):
    """视频预览对话框"""
    
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.video_capture = None
        self.is_playing = False
        self.is_paused = False
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 30
        self.play_timer = QTimer()
        
        self._init_ui()
        self._connect_signals()
        self._load_video()
    
    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle(f"预览: {os.path.basename(self.video_path)}")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # 视频预览标签
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(600, 400)
        self.preview_label.setStyleSheet(
            "QLabel { background-color: #000; color: #fff; border: 1px solid #ccc; }"
        )
        self.preview_label.setText("加载中...")
        layout.addWidget(self.preview_label, 1)
        
        # 播放控制
        control_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("播放")
        self.pause_btn = QPushButton("暂停")
        self.stop_btn = QPushButton("停止")
        
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 进度条
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setMinimumHeight(30)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B1B1B1, stop:1 #c4c4c4);
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b4b4b4, stop:1 #8f8f8f);
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d4d4d4, stop:1 #afafaf);
            }
        """)
        layout.addWidget(self.progress_slider)
        
        # 时间信息
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.total_time_label = QLabel("00:00")
        
        time_layout.addWidget(self.current_time_label)
        time_layout.addWidget(QLabel("/"))
        time_layout.addWidget(self.total_time_label)
        time_layout.addStretch()
        
        layout.addLayout(time_layout)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
    
    def _connect_signals(self):
        """连接信号"""
        self.play_btn.clicked.connect(self._play_video)
        self.pause_btn.clicked.connect(self._pause_video)
        self.stop_btn.clicked.connect(self._stop_video)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.valueChanged.connect(self._on_position_changed)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        self.play_timer.timeout.connect(self._update_playback)
    
    def _load_video(self):
        """加载视频"""
        try:
            self.video_capture = cv2.VideoCapture(self.video_path)
            
            if self.video_capture.isOpened():
                self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
                self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
                
                self.progress_slider.setMaximum(max(1, self.total_frames - 1))
                self.progress_slider.setValue(0)
                
                # 更新时间标签
                total_seconds = self.total_frames / self.fps if self.fps > 0 else 0
                self.total_time_label.setText(self._format_time(total_seconds))
                self.current_time_label.setText("00:00")
                
                # 显示第一帧
                self._show_frame(0)
            else:
                self.preview_label.setText("无法加载视频")
                
        except Exception as e:
            self.preview_label.setText(f"加载失败: {str(e)}")
    
    def _show_frame(self, frame_number):
        """显示指定帧"""
        if not self.video_capture or not self.video_capture.isOpened():
            return
        
        try:
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.video_capture.read()
            
            if ret:
                # 转换BGR到RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                
                # 创建QImage
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # 缩放图像以适应标签大小
                label_size = self.preview_label.size()
                if label_size.width() > 0 and label_size.height() > 0:
                    scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                        label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.preview_label.setPixmap(scaled_pixmap)
                else:
                    self.preview_label.setPixmap(QPixmap.fromImage(qt_image))
                
                self.current_frame = frame_number
                
        except Exception as e:
            print(f"显示帧失败: {e}")
    
    def _play_video(self):
        """播放视频"""
        if not self.video_capture:
            return
        
        self.is_playing = True
        self.is_paused = False
        interval = int(1000 / self.fps) if self.fps > 0 else 33
        self.play_timer.start(interval)
    
    def _pause_video(self):
        """暂停视频"""
        self.is_playing = False
        self.is_paused = True
        self.play_timer.stop()
    
    def _stop_video(self):
        """停止视频"""
        self.is_playing = False
        self.is_paused = False
        self.play_timer.stop()
        self.progress_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self._show_frame(0)
    
    def _update_playback(self):
        """更新播放进度"""
        if not self.is_playing:
            return
        
        current_frame = self.progress_slider.value()
        
        if current_frame < self.progress_slider.maximum():
            next_frame = current_frame + 1
            self.progress_slider.setValue(next_frame)
            self._show_frame(next_frame)
        else:
            self._stop_video()
    
    def _on_slider_pressed(self):
        """进度条按下"""
        self.play_timer.stop()
    
    def _on_slider_released(self):
        """进度条释放"""
        if self.is_playing:
            interval = int(1000 / self.fps) if self.fps > 0 else 33
            self.play_timer.start(interval)
    
    def _on_position_changed(self, position):
        """播放位置改变"""
        time_seconds = position / self.fps if self.fps > 0 else 0
        self.current_time_label.setText(self._format_time(time_seconds))
        self._show_frame(position)
    
    def _on_slider_moved(self, position):
        """进度条拖拽时实时跳转"""
        time_seconds = position / self.fps if self.fps > 0 else 0
        self.current_time_label.setText(self._format_time(time_seconds))
        self._show_frame(position)
    
    def _format_time(self, seconds):
        """格式化时间显示"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.video_capture:
            self.video_capture.release()
        self.play_timer.stop()
        event.accept()

class VideoEditWidget(QWidget):
    """视频编辑界面组件"""
    
    # 信号定义
    status_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(int)
    video_selected = pyqtSignal(str)
    
    def __init__(self, config_manager):
        super().__init__()
        
        self.config_manager = config_manager
        self.logger = Logger().get_logger("VideoEditWidget")
        
        # 算法管理器
        self.algorithm_manager = AlgorithmManager(config_manager)
        
        # 视频处理器
        self.video_processor = VideoProcessor(config_manager)
        
        # 当前视频信息
        self.current_video_path = None
        self.current_video_info = None
        self.current_position = 0.0
        
        # 视频列表
        self.video_list = []
        self.current_video_index = -1
        
        # 编辑操作列表
        self.edit_operations = []
        
        # 视频指令映射字典 - 为每个视频路径保存对应的指令列表
        self.video_operations_map = {}
        
        # 播放状态
        self.is_playing = False
        self.is_paused = False
        
        # 定时器
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self._update_playback)
        
        # 处理结果存储
        self.processing_results = []
        
        # 编辑操作列表
        self.edit_operations = []
        
        # 指令执行线程
        self.execution_thread = None
        
        # 初始化界面
        self._init_ui()
        self._connect_signals()
        self._load_settings()
        
        self.logger.info("视频编辑界面组件初始化完成")
    
    def _save_current_video_operations(self):
        """保存当前视频的指令列表"""
        if self.current_video_path and self.edit_operations:
            self.video_operations_map[self.current_video_path] = self.edit_operations.copy()
            self.logger.info(f"保存视频指令列表: {self.current_video_path}, 指令数量: {len(self.edit_operations)}")
    
    def _load_video_operations(self, video_path):
        """加载指定视频的指令列表"""
        if video_path in self.video_operations_map:
            self.edit_operations = self.video_operations_map[video_path].copy()
            self.logger.info(f"加载视频指令列表: {video_path}, 指令数量: {len(self.edit_operations)}")
        else:
            self.edit_operations = []
            self.logger.info(f"新视频，清空指令列表: {video_path}")
        
        # 更新指令表格显示
        self._refresh_command_table()
    
    def _refresh_command_table(self):
        """刷新指令表格显示"""
        try:
            self.command_table_widget.setRowCount(0)
            
            for operation in self.edit_operations:
                self._add_command_to_table(operation)
                
        except Exception as e:
            self.logger.error(f"刷新指令表格失败: {e}")
    
    def _init_ui(self):
        """初始化界面"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 左侧：视频列表面板
        left_panel = self._create_video_list_panel()
        main_layout.addWidget(left_panel)
        
        # 中间：视频预览面板
        center_panel = self._create_video_preview_panel()
        main_layout.addWidget(center_panel)
        
        # 右侧：控制面板（包含算法选择等）
        control_panel = self._create_control_panel()
        main_layout.addWidget(control_panel)
        
        # 底部：指令列表面板
        command_panel = self._create_command_list_panel()
        
        # 使用垂直分割器组合中间和底部面板
        center_splitter = QSplitter(Qt.Vertical)
        center_splitter.addWidget(center_panel)
        center_splitter.addWidget(command_panel)
        center_splitter.setStretchFactor(0, 2)  # 视频预览占更多空间
        center_splitter.setStretchFactor(1, 1)  # 指令列表占较少空间
        
        # 重新布局
        main_layout.takeAt(1)  # 移除center_panel
        main_layout.insertWidget(1, center_splitter)
        
        # 设置布局比例 (1:2:1)
        main_layout.setStretchFactor(left_panel, 1)
        main_layout.setStretchFactor(center_splitter, 2)
        main_layout.setStretchFactor(control_panel, 1)
    
    def _create_video_list_panel(self) -> QWidget:
        """创建视频列表面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("视频列表")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.add_video_btn = QPushButton("添加视频")
        self.remove_video_btn = QPushButton("删除")
        self.remove_video_btn.setEnabled(False)
        
        btn_layout.addWidget(self.add_video_btn)
        btn_layout.addWidget(self.remove_video_btn)
        layout.addLayout(btn_layout)
        
        # 视频列表
        self.video_list_widget = QListWidget()
        self.video_list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.video_list_widget)
        
        return panel
    
    def _create_video_preview_panel(self) -> QWidget:
        """创建视频预览面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("视频预览")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 视频预览标签
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setScaledContents(False)  # 手动控制缩放以保持宽高比
        self.preview_label.setStyleSheet(
            "QLabel { background-color: #000; color: #fff; border: 1px solid #ccc; }"
        )
        self.preview_label.setText("请选择视频文件")
        layout.addWidget(self.preview_label, 1)  # 设置拉伸因子
        
        # 播放控制 - 紧贴视频预览窗口
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 5, 0, 5)  # 减少上下边距
        control_layout.setSpacing(8)  # 减少按钮间距
        
        self.play_btn = QPushButton("播放")
        self.pause_btn = QPushButton("暂停")
        self.stop_btn = QPushButton("停止")
        
        # 设置按钮样式，使其更紧凑
        button_style = """
            QPushButton {
                padding: 6px 12px;
                font-size: 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """
        
        self.play_btn.setStyleSheet(button_style)
        self.pause_btn.setStyleSheet(button_style)
        self.stop_btn.setStyleSheet(button_style)
        
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 进度条和帧控制
        progress_group = QGroupBox("播放进度")
        progress_layout = QVBoxLayout(progress_group)
        
        # 进度条
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(100)
        self.position_slider.setValue(0)
        self.position_slider.setMinimumHeight(30)  # 增加高度
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B1B1B1, stop:1 #c4c4c4);
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b4b4b4, stop:1 #8f8f8f);
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d4d4d4, stop:1 #afafaf);
            }
        """)
        # 添加点击跳转功能
        self.position_slider.mousePressEvent = self._slider_mouse_press_event
        progress_layout.addWidget(self.position_slider)
        
        # 时间和帧信息
        info_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.total_time_label = QLabel("00:00")
        self.current_frame_label = QLabel("帧: 0")
        self.total_frame_label = QLabel("总帧: 0")
        
        info_layout.addWidget(self.current_time_label)
        info_layout.addWidget(QLabel("/"))
        info_layout.addWidget(self.total_time_label)
        info_layout.addStretch()
        info_layout.addWidget(self.current_frame_label)
        info_layout.addWidget(QLabel("/"))
        info_layout.addWidget(self.total_frame_label)
        progress_layout.addLayout(info_layout)
        
        # 帧跳转控制
        frame_control_layout = QHBoxLayout()
        
        self.prev_frame_btn = QPushButton("上一帧")
        self.next_frame_btn = QPushButton("下一帧")
        
        frame_control_layout.addWidget(QLabel("跳转到帧:"))
        self.frame_input = QSpinBox()
        self.frame_input.setMinimum(0)
        self.frame_input.setMaximum(0)
        frame_control_layout.addWidget(self.frame_input)
        
        self.goto_frame_btn = QPushButton("跳转")
        frame_control_layout.addWidget(self.goto_frame_btn)
        
        frame_control_layout.addStretch()
        
        # 批量帧跳转控制
        frame_control_layout.addWidget(QLabel("步长:"))
        self.frame_step_input = QSpinBox()
        self.frame_step_input.setMinimum(1)
        self.frame_step_input.setMaximum(1000)
        self.frame_step_input.setValue(30)  # 默认30帧
        frame_control_layout.addWidget(self.frame_step_input)
        
        self.prev_x_frame_btn = QPushButton("上X帧")
        self.next_x_frame_btn = QPushButton("下X帧")
        frame_control_layout.addWidget(self.prev_x_frame_btn)
        frame_control_layout.addWidget(self.next_x_frame_btn)
        
        frame_control_layout.addStretch()
        frame_control_layout.addWidget(self.prev_frame_btn)
        frame_control_layout.addWidget(self.next_frame_btn)
        
        progress_layout.addLayout(frame_control_layout)
        layout.addWidget(progress_group)
        
        # 编辑操作
        edit_group = QGroupBox("编辑操作")
        edit_layout = QHBoxLayout(edit_group)
        
        self.split_btn = QPushButton("分割开始")
        self.split_state = "start"  # 记录分割状态: start 或 end
        self.delete_btn = QPushButton("删除当前片段")
        
        edit_layout.addWidget(self.split_btn)
        edit_layout.addWidget(self.delete_btn)
        edit_layout.addStretch()
        
        layout.addWidget(edit_group)
        
        return panel
    
    def _create_command_list_panel(self) -> QWidget:
        """创建指令列表面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("编辑指令列表")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 指令列表（表格形式）
        self.command_table_widget = QTableWidget()
        self.command_table_widget.setColumnCount(4)
        self.command_table_widget.setHorizontalHeaderLabels(["操作", "开始位置", "结束位置", "执行状态"])
        self.command_table_widget.setAlternatingRowColors(True)
        self.command_table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 设置列宽
        header = self.command_table_widget.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.command_table_widget)
        
        # 指令操作按钮
        command_btn_layout = QHBoxLayout()
        
        self.clear_commands_btn = QPushButton("清空列表")
        self.remove_command_btn = QPushButton("删除选中")
        self.remove_command_btn.setEnabled(False)
        
        command_btn_layout.addWidget(self.clear_commands_btn)
        command_btn_layout.addWidget(self.remove_command_btn)
        
        layout.addLayout(command_btn_layout)
        
        # 执行控制
        execute_group = QGroupBox("执行控制")
        execute_layout = QVBoxLayout(execute_group)
        
        # 执行按钮
        execute_btn_layout = QHBoxLayout()
        
        self.execute_btn = QPushButton("执行所有指令")
        self.execute_btn.setEnabled(False)
        self.execute_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        execute_btn_layout.addWidget(self.execute_btn)
        
        self.execute_pending_btn = QPushButton("执行未执行命令")
        self.execute_pending_btn.setEnabled(False)
        self.execute_pending_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; }")
        execute_btn_layout.addWidget(self.execute_pending_btn)
        
        execute_layout.addLayout(execute_btn_layout)
        
        # 执行进度
        self.execute_progress = QProgressBar()
        self.execute_progress.setVisible(False)
        execute_layout.addWidget(self.execute_progress)
        
        # 当前执行状态
        self.execute_status_label = QLabel("就绪")
        self.execute_status_label.setAlignment(Qt.AlignCenter)
        execute_layout.addWidget(self.execute_status_label)
        
        layout.addWidget(execute_group)
        
        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QVBoxLayout(output_group)
        
        # 输出目录
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(QLabel("输出目录:"))
        
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText("./output")
        output_dir_layout.addWidget(self.output_dir_input)
        
        self.browse_output_btn = QPushButton("浏览")
        output_dir_layout.addWidget(self.browse_output_btn)
        
        output_layout.addLayout(output_dir_layout)
        
        # 输出文件名
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(QLabel("文件名:"))
        
        self.output_filename_input = QLineEdit()
        self.output_filename_input.setPlaceholderText("自动生成")
        filename_layout.addWidget(self.output_filename_input)
        
        output_layout.addLayout(filename_layout)
        
        layout.addWidget(output_group)
        
        # 输出目录视频列表
        output_videos_group = QGroupBox("输出目录视频")
        output_videos_layout = QVBoxLayout(output_videos_group)
        
        # 刷新按钮
        refresh_output_btn = QPushButton("刷新列表")
        output_videos_layout.addWidget(refresh_output_btn)
        
        # 输出视频列表
        self.output_video_list = QListWidget()
        self.output_video_list.setAlternatingRowColors(True)
        output_videos_layout.addWidget(self.output_video_list)
        
        layout.addWidget(output_videos_group)
        
        # 连接刷新按钮
        refresh_output_btn.clicked.connect(self._refresh_output_videos)
        
        layout.addStretch()
        
        return panel
    
    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 视频输入组
        input_group = QGroupBox("视频输入")
        input_layout = QVBoxLayout(input_group)
        
        # 文件选择
        file_layout = QHBoxLayout()
        
        self.video_path_input = QLineEdit()
        self.video_path_input.setPlaceholderText("选择视频文件")
        file_layout.addWidget(self.video_path_input)
        
        self.browse_video_btn = QPushButton("浏览")
        self.browse_video_btn.clicked.connect(self._browse_video_file)
        file_layout.addWidget(self.browse_video_btn)
        
        input_layout.addLayout(file_layout)
        
        # 视频信息显示
        self.video_info_label = QLabel("未选择视频")
        self.video_info_label.setWordWrap(True)
        self.video_info_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; border: 1px solid #ccc; }")
        input_layout.addWidget(self.video_info_label)
        
        layout.addWidget(input_group)
        
        # 算法选择组
        algorithm_group = QGroupBox("算法选择")
        algorithm_layout = QGridLayout(algorithm_group)
        
        # 算法类型
        algorithm_layout.addWidget(QLabel("算法类型:"), 0, 0)
        self.algorithm_type_combo = QComboBox()
        self.algorithm_type_combo.addItems(["2D姿态估计", "3D姿态估计", "视频描述"])
        self.algorithm_type_combo.currentTextChanged.connect(self._on_algorithm_type_changed)
        algorithm_layout.addWidget(self.algorithm_type_combo, 0, 1)
        
        # 具体算法
        algorithm_layout.addWidget(QLabel("具体算法:"), 1, 0)
        self.algorithm_name_combo = QComboBox()
        algorithm_layout.addWidget(self.algorithm_name_combo, 1, 1)
        
        layout.addWidget(algorithm_group)
        
        # 处理选项组
        options_group = QGroupBox("处理选项")
        options_layout = QGridLayout(options_group)
        
        # 输出目录
        options_layout.addWidget(QLabel("输出目录:"), 0, 0)
        output_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText("./output")
        output_layout.addWidget(self.output_dir_input)
        
        self.browse_output_btn = QPushButton("浏览")
        self.browse_output_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(self.browse_output_btn)
        
        options_layout.addLayout(output_layout, 0, 1)
        
        # 帧率设置
        options_layout.addWidget(QLabel("处理帧率:"), 1, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(30)
        self.fps_spin.setSuffix(" fps")
        options_layout.addWidget(self.fps_spin, 1, 1)
        
        # 分辨率设置
        options_layout.addWidget(QLabel("输出分辨率:"), 2, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["原始分辨率", "1920x1080", "1280x720", "854x480", "640x360"])
        options_layout.addWidget(self.resolution_combo, 2, 1)
        
        # 质量设置
        options_layout.addWidget(QLabel("输出质量:"), 3, 0)
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(80)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        options_layout.addWidget(self.quality_slider, 3, 1)
        
        self.quality_label = QLabel("80%")
        options_layout.addWidget(self.quality_label, 4, 1)
        
        # 批处理选项
        self.batch_process_check = QCheckBox("批量处理模式")
        options_layout.addWidget(self.batch_process_check, 5, 0, 1, 2)
        
        layout.addWidget(options_group)
        
        # 高级选项组
        advanced_group = QGroupBox("高级选项")
        advanced_layout = QGridLayout(advanced_group)
        
        # GPU加速
        self.gpu_check = QCheckBox("启用GPU加速")
        advanced_layout.addWidget(self.gpu_check, 0, 0)
        
        # 多线程处理
        self.multithread_check = QCheckBox("多线程处理")
        advanced_layout.addWidget(self.multithread_check, 0, 1)
        
        # 线程数设置
        advanced_layout.addWidget(QLabel("线程数:"), 1, 0)
        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setRange(1, 16)
        self.thread_count_spin.setValue(4)
        advanced_layout.addWidget(self.thread_count_spin, 1, 1)
        
        # 内存限制
        advanced_layout.addWidget(QLabel("内存限制(GB):"), 2, 0)
        self.memory_limit_spin = QDoubleSpinBox()
        self.memory_limit_spin.setRange(0.5, 32.0)
        self.memory_limit_spin.setValue(4.0)
        self.memory_limit_spin.setSuffix(" GB")
        advanced_layout.addWidget(self.memory_limit_spin, 2, 1)
        
        layout.addWidget(advanced_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始处理")
        self.start_btn.clicked.connect(self._start_processing)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_processing)
        button_layout.addWidget(self.stop_btn)
        
        self.preview_btn = QPushButton("预览设置")
        self.preview_btn.clicked.connect(self._preview_settings)
        button_layout.addWidget(self.preview_btn)
        
        layout.addLayout(button_layout)
        
        # 进度显示
        progress_group = QGroupBox("处理进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("就绪")
        progress_layout.addWidget(self.status_label)
        
        # 时间信息
        time_layout = QHBoxLayout()
        
        self.elapsed_label = QLabel("已用时间: 00:00:00")
        time_layout.addWidget(self.elapsed_label)
        
        self.remaining_label = QLabel("剩余时间: --:--:--")
        time_layout.addWidget(self.remaining_label)
        
        progress_layout.addLayout(time_layout)
        
        layout.addWidget(progress_group)
        
        layout.addStretch()
        
        return panel
    
    def _create_result_panel(self) -> QWidget:
        """创建结果面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建选项卡
        self.result_tabs = QTabWidget()
        
        # 实时预览选项卡
        preview_tab = self._create_preview_tab()
        self.result_tabs.addTab(preview_tab, "实时预览")
        
        # 处理结果选项卡
        result_tab = self._create_result_tab()
        self.result_tabs.addTab(result_tab, "处理结果")
        
        # 统计信息选项卡
        stats_tab = self._create_stats_tab()
        self.result_tabs.addTab(stats_tab, "统计信息")
        
        # 日志选项卡
        log_tab = self._create_log_tab()
        self.result_tabs.addTab(log_tab, "处理日志")
        
        layout.addWidget(self.result_tabs)
        
        return panel
    
    def _create_preview_tab(self) -> QWidget:
        """创建预览选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 预览控制
        control_layout = QHBoxLayout()
        
        self.preview_play_btn = QPushButton("播放")
        self.preview_play_btn.clicked.connect(self._toggle_preview_play)
        control_layout.addWidget(self.preview_play_btn)
        
        self.preview_frame_slider = QSlider(Qt.Horizontal)
        self.preview_frame_slider.valueChanged.connect(self._on_preview_frame_changed)
        control_layout.addWidget(self.preview_frame_slider)
        
        self.frame_info_label = QLabel("帧: 0/0")
        control_layout.addWidget(self.frame_info_label)
        
        layout.addLayout(control_layout)
        
        # 预览显示区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("QLabel { background-color: #000; color: #fff; }")
        self.preview_label.setText("无预览内容")
        
        scroll_area.setWidget(self.preview_label)
        layout.addWidget(scroll_area)
        
        return widget
    
    def _create_result_tab(self) -> QWidget:
        """创建结果选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 结果控制
        control_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self._export_results)
        control_layout.addWidget(self.export_btn)
        
        self.clear_results_btn = QPushButton("清空结果")
        self.clear_results_btn.clicked.connect(self._clear_results)
        control_layout.addWidget(self.clear_results_btn)
        
        control_layout.addStretch()
        
        self.result_format_combo = QComboBox()
        self.result_format_combo.addItems(["JSON", "CSV", "XML", "TXT"])
        control_layout.addWidget(QLabel("导出格式:"))
        control_layout.addWidget(self.result_format_combo)
        
        layout.addLayout(control_layout)
        
        # 结果显示
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["项目", "值", "类型", "时间戳"])
        layout.addWidget(self.result_tree)
        
        return widget
    
    def _create_stats_tab(self) -> QWidget:
        """创建统计信息选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 统计信息表格
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["统计项", "数值"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.stats_table)
        
        return widget
    
    def _create_log_tab(self) -> QWidget:
        """创建日志选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 日志控制
        log_control_layout = QHBoxLayout()
        
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self._clear_log)
        log_control_layout.addWidget(self.clear_log_btn)
        
        self.save_log_btn = QPushButton("保存日志")
        self.save_log_btn.clicked.connect(self._save_log)
        log_control_layout.addWidget(self.save_log_btn)
        
        log_control_layout.addStretch()
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        log_control_layout.addWidget(self.auto_scroll_check)
        
        layout.addLayout(log_control_layout)
        
        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)
        
        return widget
    
    def _connect_signals(self):
        """连接信号"""
        # 视频列表信号
        self.add_video_btn.clicked.connect(self._add_video)
        self.remove_video_btn.clicked.connect(self._remove_video)
        self.video_list_widget.itemDoubleClicked.connect(self._load_video_preview)
        self.video_list_widget.itemSelectionChanged.connect(self._on_video_selection_changed)
        
        # 播放控制信号
        self.play_btn.clicked.connect(self._play_video)
        self.pause_btn.clicked.connect(self._pause_video)
        self.stop_btn.clicked.connect(self._stop_video)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        self.position_slider.valueChanged.connect(self._on_position_changed)
        
        # 帧控制信号
        self.prev_frame_btn.clicked.connect(self._prev_frame)
        self.next_frame_btn.clicked.connect(self._next_frame)
        self.prev_x_frame_btn.clicked.connect(self._prev_x_frames)
        self.next_x_frame_btn.clicked.connect(self._next_x_frames)
        self.goto_frame_btn.clicked.connect(self._goto_frame)
        
        # 编辑操作信号
        self.split_btn.clicked.connect(self._split_video)
        self.delete_btn.clicked.connect(self._delete_segment)
        
        # 指令列表信号
        self.command_table_widget.itemSelectionChanged.connect(self._on_command_selection_changed)
        self.clear_commands_btn.clicked.connect(self._clear_commands)
        self.remove_command_btn.clicked.connect(self._remove_selected_command)
        self.execute_btn.clicked.connect(self._execute_commands)
        self.execute_pending_btn.clicked.connect(self._execute_pending_commands)
        
        # 输出视频列表信号
        self.output_video_list.itemDoubleClicked.connect(self._preview_output_video)
        
        # 输出目录
        self.browse_output_btn.clicked.connect(self._browse_output_dir)
        
        # 快捷键
        self._setup_shortcuts()
        
        # 视频路径变化
        if hasattr(self, 'video_path_input'):
            self.video_path_input.textChanged.connect(self._on_video_path_changed)
        
        # 多线程选项变化
        if hasattr(self, 'multithread_check'):
            self.multithread_check.toggled.connect(self._on_multithread_toggled)
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        
        # 播放控制快捷键
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key_Left), self, self._seek_backward)
        QShortcut(QKeySequence(Qt.Key_Right), self, self._seek_forward)
        
        # 帧控制快捷键
        QShortcut(QKeySequence(Qt.Key_Comma), self, self._prev_frame)
        QShortcut(QKeySequence(Qt.Key_Period), self, self._next_frame)
        
    def _toggle_play_pause(self):
        """切换播放/暂停"""
        if self.is_playing:
            self._pause_video()
        else:
            self._play_video()
            
    def _seek_backward(self):
        """快退"""
        if self.current_video_info:
            current_pos = self.position_slider.value()
            new_pos = max(0, current_pos - 30)  # 快退30帧
            self.position_slider.setValue(new_pos)
            
    def _seek_forward(self):
        """快进"""
        if self.current_video_info:
            current_pos = self.position_slider.value()
            max_pos = self.position_slider.maximum()
            new_pos = min(max_pos, current_pos + 30)  # 快进30帧
            self.position_slider.setValue(new_pos)
            
    def _jump_to_frame(self):
        """跳转到指定帧"""
        if self.current_video_info:
            frame_num = self.frame_input.value()
            self.position_slider.setValue(frame_num)
            self._on_position_changed(frame_num)
             
    def _seek_to_start(self):
        """跳转到开始"""
        if self.current_video_info:
            self.position_slider.setValue(0)
            
    def _seek_to_end(self):
        """跳转到结束"""
        if self.current_video_info:
            self.position_slider.setValue(self.position_slider.maximum())
            
    def _setup_edit_shortcuts(self):
        """设置编辑快捷键"""
        # 分割和删除快捷键
        QShortcut(QKeySequence(Qt.Key_S), self, self._split_video)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self._delete_segment)
    
    def _seek_to_end(self):
        """跳转到结束"""
        self.position_slider.setValue(self.position_slider.maximum())
    
    def _load_settings(self):
        """加载设置"""
        try:
            # 加载上次的视频列表
            last_video_list = self.config_manager.get('video_edit.last_video_list', [])
            for video_path in last_video_list:
                if Path(video_path).exists():
                    self._add_video_to_list(video_path)
            
            # 加载所有视频的指令列表
            operations_data = self.config_manager.get('video_edit.video_operations', {})
            for video_path, operations in operations_data.items():
                if Path(video_path).exists():
                    self.video_operations_map[video_path] = operations
            
            # 加载上次选中的视频
            last_selected_video = self.config_manager.get('video_edit.last_selected_video', '')
            if last_selected_video and Path(last_selected_video).exists():
                # 在视频列表中选中该视频
                for i in range(self.video_list_widget.count()):
                    item = self.video_list_widget.item(i)
                    if item and item.data(Qt.UserRole) == last_selected_video:
                        self.video_list_widget.setCurrentItem(item)
                        break
            
            # 加载输出目录设置
            output_dir = self.config_manager.get('video_edit.output_dir', './output')
            if hasattr(self, 'output_dir_input'):
                self.output_dir_input.setText(output_dir)
            
            # 更新算法列表
            self._update_algorithm_list()
            
        except Exception as e:
            self.logger.error(f"加载设置失败: {e}")
    
    def _save_settings(self):
        """保存设置"""
        try:
            # 保存当前视频列表
            self.config_manager.set('video_edit.last_video_list', self.video_list)
            
            # 保存当前选中的视频
            if self.current_video_path:
                self.config_manager.set('video_edit.last_selected_video', self.current_video_path)
            
            # 保存所有视频的指令列表
            operations_data = {}
            for video_path, operations in self.video_operations_map.items():
                operations_data[video_path] = [
                    {
                        'operation_type': op['operation_type'],
                        'start_time': op['start_time'],
                        'end_time': op['end_time'],
                        'output_name': op['output_name']
                    } for op in operations
                ]
            self.config_manager.set('video_edit.video_operations', operations_data)
            
            # 保存输出目录设置
            if hasattr(self, 'output_dir_input'):
                output_dir = self.output_dir_input.text()
                self.config_manager.set('video_edit.output_dir', output_dir)
            
            self.config_manager.save()
            self.logger.info("设置保存成功")
            
        except Exception as e:
            self.logger.error(f"保存设置失败: {e}")
    
    def _add_video(self):
        """添加视频文件"""
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.m4v *.webm *.mpg *.mpeg);;所有文件 (*)"
        )
        
        valid_files = []
        invalid_files = []
        
        for file_path in file_paths:
            # 验证视频文件
            is_valid, error_msg = validate_video_file(file_path)
            if is_valid:
                valid_files.append(file_path)
                self._add_video_to_list(file_path)
            else:
                invalid_files.append((file_path, error_msg))
                self.logger.warning(f"跳过无效视频文件: {file_path}, 错误: {error_msg}")
        
        # 显示结果
        if valid_files:
            self.logger.info(f"成功添加 {len(valid_files)} 个视频文件")
        
        if invalid_files:
            error_details = "\n".join([f"• {Path(f[0]).name}: {f[1]}" for f in invalid_files[:5]])
            if len(invalid_files) > 5:
                error_details += f"\n... 还有 {len(invalid_files) - 5} 个文件"
            
            QMessageBox.warning(
                self, 
                "部分文件无效", 
                f"以下 {len(invalid_files)} 个文件无法添加:\n\n{error_details}"
            )
    
    def _add_video_to_list(self, video_path: str):
        """添加视频到列表"""
        if video_path not in self.video_list:
            self.video_list.append(video_path)
            
            # 获取视频信息
            video_info = self.video_processor.get_video_info(video_path)
            
            # 创建列表项
            item = QListWidgetItem()
            filename = Path(video_path).name
            
            if video_info:
                duration = video_info.get('duration', 0)
                duration_str = self._format_time(duration)
                item.setText(f"{filename} ({duration_str})")
            else:
                item.setText(filename)
            
            item.setData(Qt.UserRole, video_path)
            self.video_list_widget.addItem(item)
            
            self.logger.info(f"添加视频: {filename}")
    
    def _remove_video(self):
        """删除选中的视频"""
        current_item = self.video_list_widget.currentItem()
        if current_item:
            video_path = current_item.data(Qt.UserRole)
            if video_path in self.video_list:
                self.video_list.remove(video_path)
            
            row = self.video_list_widget.row(current_item)
            self.video_list_widget.takeItem(row)
            
            # 如果删除的是当前预览的视频，清空预览
            if video_path == self.current_video_path:
                self._clear_preview()
            
            self.logger.info(f"删除视频: {Path(video_path).name}")
    
    def _on_video_selection_changed(self):
        """视频选择变化"""
        current_item = self.video_list_widget.currentItem()
        self.remove_video_btn.setEnabled(current_item is not None)
        
        # 如果有当前视频，保存其指令列表
        if self.current_video_path:
            self._save_current_video_operations()
        
        # 如果选择了新视频，加载其指令列表
        if current_item:
            video_path = current_item.data(Qt.UserRole)
            self._load_video_operations(video_path)
    
    def _load_video_preview(self, item):
        """加载视频预览"""
        video_path = item.data(Qt.UserRole)
        self._load_video(video_path)
    
    def _load_video(self, video_path: str):
        """加载视频"""
        try:
            # 保存当前视频的指令列表
            if self.current_video_path:
                self._save_current_video_operations()
            
            # 验证视频文件
            is_valid, error_msg = validate_video_file(video_path)
            if not is_valid:
                raise ValueError(f"视频文件验证失败: {error_msg}")
            
            self.current_video_path = video_path
            self.current_video_info = self.video_processor.get_video_info(video_path)
            
            if not self.current_video_info:
                raise RuntimeError("无法获取视频信息，文件可能已损坏")
            
            # 初始化OpenCV视频捕获对象
            if hasattr(self, 'video_capture') and self.video_capture:
                self.video_capture.release()
            
            # 尝试多种方式打开视频
            self.video_capture = cv2.VideoCapture(video_path)
            if not self.video_capture.isOpened():
                # 尝试使用FFMPEG后端
                self.video_capture = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
                if not self.video_capture.isOpened():
                    raise RuntimeError("无法打开视频文件，可能是编码格式不支持或文件已损坏")
            
            # 验证视频流
            ret, test_frame = self.video_capture.read()
            if not ret or test_frame is None:
                self.video_capture.release()
                raise RuntimeError("视频文件无法读取帧数据，可能已损坏")
            
            # 重置到开始位置
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            if self.current_video_info and self.video_capture.isOpened():
                # 更新预览标签
                filename = Path(video_path).name
                
                # 设置进度条
                duration = self.current_video_info.get('duration', 0)
                fps = self.current_video_info.get('fps', 30)
                total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
                
                self.position_slider.setMaximum(max(1, total_frames - 1))
                self.position_slider.setValue(0)
                
                # 更新时间标签
                self.current_time_label.setText("00:00")
                self.total_time_label.setText(self._format_time(duration))
                
                # 更新帧信息
                self.current_frame_label.setText("帧: 0")
                self.total_frame_label.setText(f"总帧: {total_frames}")
                
                # 设置帧输入范围
                self.frame_input.setMaximum(max(0, total_frames - 1))
                self.frame_input.setValue(0)
                
                # 重置播放状态
                self.current_position = 0.0
                self.is_playing = False
                self.is_paused = False
                
                # 加载该视频的指令列表
                self._load_video_operations(video_path)
                
                # 显示第一帧
                self._show_frame(0)
                    
                self.logger.info(f"加载视频: {filename}")
                    
        except Exception as e:
            self.logger.error(f"加载视频失败: {e}")
            self._clear_preview()
    
    def _show_frame(self, frame_number):
        """显示指定帧"""
        if not hasattr(self, 'video_capture') or not self.video_capture.isOpened():
            self.logger.warning("视频捕获对象未初始化或已关闭")
            return
            
        try:
            # 验证帧号有效性
            if not self.current_video_info:
                self.logger.error("视频信息不可用")
                return
                
            total_frames = self.current_video_info.get('frame_count', 0)
            if frame_number < 0 or frame_number >= total_frames:
                self.logger.error(f"无效的帧号: {frame_number}, 总帧数: {total_frames}")
                return
            
            # 设置视频位置到指定帧
            success = self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            if not success:
                self.logger.error(f"无法设置视频位置到帧 {frame_number}")
                return
                
            ret, frame = self.video_capture.read()
            
            if ret and frame is not None:
                # 检查帧数据有效性
                if frame.size == 0:
                    self.logger.error(f"帧 {frame_number} 数据为空")
                    return
                    
                # 转换BGR到RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                
                if h <= 0 or w <= 0 or ch <= 0:
                    self.logger.error(f"无效的帧尺寸: {w}x{h}x{ch}")
                    return
                    
                bytes_per_line = ch * w
                
                # 创建QImage
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                if qt_image.isNull():
                    self.logger.error("创建QImage失败")
                    return
                
                # 获取预览标签的实际大小
                label_size = self.preview_label.size()
                if label_size.width() > 0 and label_size.height() > 0:
                    # 缩放图像以适应标签大小，保持宽高比
                    scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                        label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    
                    if scaled_pixmap.isNull():
                        self.logger.error("图像缩放失败")
                        return
                    
                    # 显示图像
                    self.preview_label.setPixmap(scaled_pixmap)
                else:
                    # 如果标签尺寸无效，使用原始尺寸
                    original_pixmap = QPixmap.fromImage(qt_image)
                    if not original_pixmap.isNull():
                        self.preview_label.setPixmap(original_pixmap)
                    else:
                        self.logger.error("创建原始尺寸Pixmap失败")
            else:
                self.logger.error(f"无法读取帧 {frame_number}")
                
        except Exception as e:
            self.logger.error(f"显示帧失败: {e}")
            # 显示错误信息给用户
            self.preview_label.clear()
            self.preview_label.setText(f"视频播放错误: {str(e)}")
    
    def _clear_preview(self):
        """清空预览"""
        self.current_video_path = None
        self.current_video_info = None
        
        # 释放视频捕获对象
        if hasattr(self, 'video_capture'):
            self.video_capture.release()
            
        self.preview_label.clear()
        self.preview_label.setText("无视频预览")
        self.position_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        self.current_frame_label.setText("帧: 0")
        self.total_frame_label.setText("总帧: 0")
        self.frame_input.setMaximum(0)
        self.frame_input.setValue(0)
        self.is_playing = False
        self.is_paused = False
        self.play_timer.stop()
    
    def _play_video(self):
        """播放视频"""
        if not self.current_video_path:
            return
        
        self.is_playing = True
        self.is_paused = False
        self.play_timer.start(33)  # 约30fps
        self.logger.info("开始播放视频")
    
    def _pause_video(self):
        """暂停视频"""
        self.is_playing = False
        self.is_paused = True
        self.play_timer.stop()
        self.logger.info("暂停播放视频")
    
    def _stop_video(self):
        """停止视频"""
        self.is_playing = False
        self.is_paused = False
        self.play_timer.stop()
        self.position_slider.setValue(0)
        self.current_position = 0.0
        self.current_time_label.setText("00:00")
        self.logger.info("停止播放视频")
    
    def _update_playback(self):
        """更新播放进度"""
        if not self.is_playing or not self.current_video_info:
            return
        
        current_frame = self.position_slider.value()
        
        # 播放进度
        if current_frame < self.position_slider.maximum():
            next_frame = current_frame + 1
            self.position_slider.setValue(next_frame)
            self._show_frame(next_frame)
        else:
            self._stop_video()
    
    def _on_slider_pressed(self):
        """进度条按下"""
        self.play_timer.stop()
    
    def _on_slider_released(self):
        """进度条释放"""
        if self.is_playing:
            self.play_timer.start(33)
    
    def _on_position_changed(self, position):
        """播放位置改变"""
        if self.current_video_info:
            fps = self.current_video_info.get('fps', 30)
            time_seconds = position / fps if fps > 0 else 0
            self.current_time_label.setText(self._format_time(time_seconds))
            self.current_frame_label.setText(f"帧: {position}")
            self.frame_input.setValue(position)
            self.current_position = time_seconds
            
            # 显示对应帧（拖拽时也更新预览）
            self._show_frame(position)
    
    def _format_time(self, seconds):
        """格式化时间显示"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
        
    def _slider_mouse_press_event(self, event):
        """处理进度条鼠标点击事件，实现点击跳转"""
        if event.button() == Qt.LeftButton:
            # 获取滑块的几何信息
            slider_rect = self.position_slider.rect()
            slider_height = slider_rect.height()
            
            # 检查点击是否在滑块的有效区域内（垂直方向）
            click_y = event.y()
            if click_y < 0 or click_y > slider_height:
                return  # 点击在滑块外部，不处理
            
            # 计算点击位置对应的值
            slider_width = self.position_slider.width()
            click_pos = event.x()
            
            # 确保点击位置在水平范围内
            if click_pos < 0 or click_pos > slider_width:
                return
            
            # 计算目标帧号
            if hasattr(self, 'current_video_info') and self.current_video_info:
                total_frames = self.current_video_info.get('frame_count', 0)
                if total_frames > 0:
                    target_frame = int((click_pos / slider_width) * total_frames)
                    target_frame = max(0, min(target_frame, total_frames - 1))
                    
                    # 设置滑块值和跳转
                    self.position_slider.setValue(target_frame)
                    self.frame_input.setValue(target_frame)
                    self._goto_frame()
        
        # 调用原始的鼠标按下事件
        QSlider.mousePressEvent(self.position_slider, event)
    
    def _prev_frame(self):
        """上一帧"""
        if self.current_video_info:
            current_frame = self.frame_input.value()
            if current_frame > 0:
                new_frame = current_frame - 1
                self.frame_input.setValue(new_frame)
                self.position_slider.setValue(new_frame)
                self._show_frame(new_frame)
                
                # 更新时间显示
                fps = self.current_video_info.get('fps', 30)
                time_seconds = new_frame / fps if fps > 0 else 0
                self.current_time_label.setText(self._format_time(time_seconds))
                self.current_frame_label.setText(f"帧: {new_frame}")
                self.current_position = time_seconds
    
    def _next_frame(self):
        """下一帧"""
        if self.current_video_info:
            current_frame = self.frame_input.value()
            max_frame = self.frame_input.maximum()
            if current_frame < max_frame:
                new_frame = current_frame + 1
                self.frame_input.setValue(new_frame)
                self.position_slider.setValue(new_frame)
                self._show_frame(new_frame)
                
                # 更新时间显示
                fps = self.current_video_info.get('fps', 30)
                time_seconds = new_frame / fps if fps > 0 else 0
                self.current_time_label.setText(self._format_time(time_seconds))
                self.current_frame_label.setText(f"帧: {new_frame}")
                self.current_position = time_seconds
    
    def _prev_x_frames(self):
        """上X帧"""
        if self.current_video_info:
            current_frame = self.frame_input.value()
            step = self.frame_step_input.value()
            new_frame = max(0, current_frame - step)
            
            self.frame_input.setValue(new_frame)
            self.position_slider.setValue(new_frame)
            self._show_frame(new_frame)
            
            # 更新时间显示
            fps = self.current_video_info.get('fps', 30)
            time_seconds = new_frame / fps if fps > 0 else 0
            self.current_time_label.setText(self._format_time(time_seconds))
            self.current_frame_label.setText(f"帧: {new_frame}")
            self.current_position = time_seconds
    
    def _next_x_frames(self):
        """下X帧"""
        if self.current_video_info:
            current_frame = self.frame_input.value()
            step = self.frame_step_input.value()
            max_frame = self.frame_input.maximum()
            new_frame = min(max_frame, current_frame + step)
            
            self.frame_input.setValue(new_frame)
            self.position_slider.setValue(new_frame)
            self._show_frame(new_frame)
            
            # 更新时间显示
            fps = self.current_video_info.get('fps', 30)
            time_seconds = new_frame / fps if fps > 0 else 0
            self.current_time_label.setText(self._format_time(time_seconds))
            self.current_frame_label.setText(f"帧: {new_frame}")
            self.current_position = time_seconds
    
    def _goto_frame(self):
        """跳转到指定帧"""
        if self.current_video_info:
            frame_num = self.frame_input.value()
            self.position_slider.setValue(frame_num)
            
            fps = self.current_video_info.get('fps', 30)
            time_seconds = frame_num / fps if fps > 0 else 0
            self.current_time_label.setText(self._format_time(time_seconds))
            self.current_frame_label.setText(f"帧: {frame_num}")
            self.current_position = time_seconds
            
            # 显示指定帧
            self._show_frame(frame_num)
            self.logger.info(f"跳转到第{frame_num}帧")
    
    def _split_video(self):
        """分割视频"""
        if not self.current_video_path:
            return
        
        current_frame = self.frame_input.value()
        
        if self.split_state == "start":
            # 开始分割操作
            operation = {
                'type': 'split',
                'start_frame': current_frame,
                'description': f'分割开始: 帧{current_frame}'
            }
            
            self.edit_operations.append(operation)
            self._add_command_to_table(operation)
            self.logger.info(f"开始分割操作: {operation['description']}")
            
            # 切换到结束状态
            self.split_state = "end"
            self.split_btn.setText("分割结束")
            
        else:  # split_state == "end"
            # 优先更新选中的条目
            current_row = self.command_table_widget.currentRow()
            target_operation = None
            
            if current_row >= 0:
                # 获取选中的操作
                item = self.command_table_widget.item(current_row, 0)
                if item:
                    selected_op = item.data(Qt.UserRole)
                    if selected_op and selected_op['type'] == 'split' and 'end_frame' not in selected_op:
                        target_operation = selected_op
            
            # 如果没有选中合适的条目，查找最后一个未完成的分割操作
            if not target_operation:
                for op in reversed(self.edit_operations):
                    if op['type'] == 'split' and 'end_frame' not in op:
                        target_operation = op
                        break
            
            # 完成分割操作
            if target_operation:
                target_operation['end_frame'] = current_frame
                target_operation['description'] = f'分割片段 帧{target_operation["start_frame"]} - 帧{current_frame}'
                self._update_command_in_table(target_operation)
                self.logger.info(f"完成分割操作: {target_operation['description']}")
            
            # 切换回开始状态
            self.split_state = "start"
            self.split_btn.setText("分割开始")
    
    def _delete_segment(self):
        """删除当前片段"""
        if not self.current_video_path:
            return
        
        current_time = self.current_position
        
        # 检查是否已有未完成的删除操作
        for op in self.edit_operations:
            if op['type'] == 'delete' and 'end_time' not in op:
                # 完成之前的删除操作
                op['end_time'] = current_time
                op['description'] = f'删除片段 {self._format_time(op["start_time"])} - {self._format_time(current_time)}'
                self._update_command_in_table(op)
                self.logger.info(f"完成删除操作: {op['description']}")
                return
        
        # 开始新的删除操作
        operation = {
            'type': 'delete',
            'start_time': current_time,
            'description': f'删除开始: {self._format_time(current_time)}'
        }
        
        self.edit_operations.append(operation)
        self._add_command_to_table(operation)
        self.logger.info(f"开始删除操作: {operation['description']}")
    
    def _add_command_to_table(self, operation):
        """添加指令到表格"""
        row = self.command_table_widget.rowCount()
        self.command_table_widget.insertRow(row)
        
        # 操作类型
        operation_item = QTableWidgetItem(operation['description'])
        operation_item.setData(Qt.UserRole, operation)
        self.command_table_widget.setItem(row, 0, operation_item)
        
        # 开始帧号/时间
        if 'start_frame' in operation:
            start_item = QTableWidgetItem(f"帧{operation['start_frame']}")
        else:
            start_time = operation.get('start_time', operation.get('time', 0))
            start_item = QTableWidgetItem(self._format_time(start_time))
        self.command_table_widget.setItem(row, 1, start_item)
        
        # 结束帧号/时间
        if 'end_frame' in operation:
            end_item = QTableWidgetItem(f"帧{operation['end_frame']}")
        elif 'end_time' in operation:
            end_item = QTableWidgetItem(self._format_time(operation['end_time']))
        else:
            end_item = QTableWidgetItem('待定')
        self.command_table_widget.setItem(row, 2, end_item)
        
        # 执行状态
        status_item = QTableWidgetItem(operation.get('status', '未执行'))
        self.command_table_widget.setItem(row, 3, status_item)
        
        # 启用执行按钮
        self.execute_btn.setEnabled(True)
        self.execute_pending_btn.setEnabled(True)
        
    def _update_command_in_table(self, operation):
        """更新表格中的指令"""
        # 先尝试通过对象引用匹配
        for row in range(self.command_table_widget.rowCount()):
            item = self.command_table_widget.item(row, 0)
            if item and item.data(Qt.UserRole) is operation:
                self._update_table_row(row, operation)
                return
        
        # 如果对象引用匹配失败，通过操作内容匹配
        for row in range(self.command_table_widget.rowCount()):
            item = self.command_table_widget.item(row, 0)
            if item:
                stored_op = item.data(Qt.UserRole)
                if (stored_op and stored_op['type'] == operation['type'] and 
                    stored_op.get('start_frame') == operation.get('start_frame') and
                    stored_op.get('start_time') == operation.get('start_time')):
                    # 更新存储的操作对象
                    item.setData(Qt.UserRole, operation)
                    self._update_table_row(row, operation)
                    return
    
    def _update_table_row(self, row, operation):
        """更新表格行"""
        # 更新操作描述
        desc_item = self.command_table_widget.item(row, 0)
        if desc_item:
            desc_item.setText(operation['description'])
        
        # 更新结束帧号/时间
        end_item = self.command_table_widget.item(row, 2)
        if end_item:
            if 'end_frame' in operation:
                end_item.setText(f"帧{operation['end_frame']}")
            elif 'end_time' in operation:
                end_item.setText(self._format_time(operation['end_time']))
            else:
                end_item.setText('待定')
        
        # 更新执行状态
        status_item = self.command_table_widget.item(row, 3)
        if status_item:
            status_item.setText(operation.get('status', '未执行'))
    
    def _on_command_selection_changed(self):
        """指令选择变化"""
        current_row = self.command_table_widget.currentRow()
        self.remove_command_btn.setEnabled(current_row >= 0)
     
    def _clear_commands(self):
        """清空指令列表"""
        self.command_table_widget.setRowCount(0)
        self.edit_operations.clear()
        self.execute_btn.setEnabled(False)
        self.execute_pending_btn.setEnabled(False)
        self.remove_command_btn.setEnabled(False)
        self.logger.info("清空指令列表")
     
    def _remove_selected_command(self):
        """删除选中的指令"""
        current_row = self.command_table_widget.currentRow()
        if current_row >= 0:
            item = self.command_table_widget.item(current_row, 0)
            if item:
                operation = item.data(Qt.UserRole)
                if operation in self.edit_operations:
                    self.edit_operations.remove(operation)
            
            self.command_table_widget.removeRow(current_row)
            
            # 检查是否还有指令
            has_commands = self.command_table_widget.rowCount() > 0
            self.execute_btn.setEnabled(has_commands)
            self.execute_pending_btn.setEnabled(has_commands)
            self.logger.info("删除选中的指令")
    
    def _execute_commands(self):
        """执行所有指令"""
        if not self.edit_operations:
            return
        
        self._execute_operations(self.edit_operations)
    
    def _execute_pending_commands(self):
        """执行未执行的指令"""
        pending_operations = [op for op in self.edit_operations if op.get('status', '未执行') == '未执行']
        if not pending_operations:
            QMessageBox.information(self, "提示", "没有未执行的命令")
            return
        
        self._execute_operations(pending_operations)
    
    def _execute_operations(self, operations):
        """执行指定的操作列表（使用多线程）"""
        if not operations:
            return
        
        if not self.current_video_path:
            QMessageBox.warning(self, "错误", "请先选择视频文件")
            return
        
        output_dir = self.output_dir_input.text()
        if not output_dir:
            QMessageBox.warning(self, "错误", "请先设置输出目录")
            return
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 检查是否已有执行线程在运行
        if self.execution_thread and self.execution_thread.isRunning():
            QMessageBox.warning(self, "警告", "已有指令正在执行中")
            return
        
        # 显示进度条和状态
        self.execute_progress.setVisible(True)
        self.execute_progress.setValue(0)
        self.execute_status_label.setText("准备执行...")
        
        # 禁用执行按钮
        self.execute_btn.setEnabled(False)
        self.execute_pending_btn.setEnabled(False)
        
        # 创建并启动执行线程
        max_workers = 4  # 可以根据需要调整线程数
        self.execution_thread = CommandExecutionThread(
            operations, self.current_video_path, output_dir, max_workers
        )
        
        # 连接信号
        self.execution_thread.progress_updated.connect(self._on_execution_progress_updated)
        self.execution_thread.status_updated.connect(self._on_execution_status_updated)
        self.execution_thread.operation_status_updated.connect(self._on_operation_status_updated)
        self.execution_thread.execution_completed.connect(self._on_execution_completed)
        self.execution_thread.error_occurred.connect(self._on_execution_error)
        
        # 启动线程
        self.execution_thread.start()
        
        self.logger.info(f"开始多线程执行 {len(operations)} 个操作")
    
    def _on_execution_progress_updated(self, progress):
        """执行进度更新"""
        self.execute_progress.setValue(progress)
    
    def _on_execution_status_updated(self, status):
        """执行状态更新"""
        self.execute_status_label.setText(status)
        self.logger.info(f"执行状态: {status}")
    
    def _on_operation_status_updated(self, operation, status):
        """操作状态更新"""
        operation['status'] = status
        self._update_operation_status_in_table(operation)
        self.logger.info(f"操作状态更新: {operation.get('description', '未知操作')} -> {status}")
    
    def _on_execution_completed(self):
        """执行完成"""
        self.execute_progress.setVisible(False)
        self.execute_status_label.setText("执行完成")
        
        # 重新启用执行按钮
        self.execute_btn.setEnabled(True)
        self.execute_pending_btn.setEnabled(True)
        
        # 刷新输出目录视频列表
        self._refresh_output_videos()
        
        self.logger.info("所有指令执行完成")
        QMessageBox.information(self, "完成", "所有指令执行完成")
    
    def _on_execution_error(self, error_msg):
        """执行错误"""
        self.execute_progress.setVisible(False)
        self.execute_status_label.setText("执行失败")
        
        # 重新启用执行按钮
        self.execute_btn.setEnabled(True)
        self.execute_pending_btn.setEnabled(True)
        
        self.logger.error(f"执行错误: {error_msg}")
        QMessageBox.critical(self, "执行错误", error_msg)
    
    def _update_operation_status_in_table(self, operation):
        """更新表格中操作的状态"""
        for row in range(self.command_table_widget.rowCount()):
            item = self.command_table_widget.item(row, 0)
            if item and item.data(Qt.UserRole) == operation:
                status_item = self.command_table_widget.item(row, 3)
                if status_item:
                    status_item.setText(operation.get('status', '未执行'))
                break
         
    def _refresh_output_videos(self):
        """刷新输出目录视频列表"""
        self.output_video_list.clear()
        
        output_dir = self.output_dir_input.text()
        if not output_dir or not os.path.exists(output_dir):
            return
            
        try:
            # 支持的视频格式
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
            
            for file_name in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file_name)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file_name)
                    if ext.lower() in video_extensions:
                        item = QListWidgetItem(file_name)
                        item.setData(Qt.UserRole, file_path)
                        self.output_video_list.addItem(item)
                        
            self.logger.info(f"刷新输出目录视频列表，找到 {self.output_video_list.count()} 个视频文件")
            
        except Exception as e:
            self.logger.error(f"刷新输出目录视频列表失败: {e}")
            
    def _preview_output_video(self, item):
        """预览输出目录中的视频"""
        video_path = item.data(Qt.UserRole)
        
        # 使用新的视频预览对话框
        dialog = VideoPreviewDialog(video_path, self)
        dialog.exec_()
    
    def _update_algorithm_list(self):
        """更新算法列表"""
        try:
            current_type = self.algorithm_type_combo.currentText()
            self.algorithm_name_combo.clear()
            
            if current_type == "2D姿态估计":
                algorithms = self.algorithm_manager.get_available_algorithms(AlgorithmType.POSE_2D)
            elif current_type == "3D姿态估计":
                algorithms = self.algorithm_manager.get_available_algorithms(AlgorithmType.POSE_3D)
            elif current_type == "视频描述":
                algorithms = self.algorithm_manager.get_available_algorithms(AlgorithmType.VIDEO_DESCRIPTION)
            else:
                algorithms = []
            
            self.algorithm_name_combo.addItems(algorithms)
            
        except Exception as e:
            self.logger.error(f"更新算法列表失败: {e}")
    
    # 槽函数实现
    def _browse_video_file(self):
        """浏览视频文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择视频文件", "", 
                "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.m4v *.webm *.mpg *.mpeg);;所有文件 (*)"
            )
            
            if file_path:
                # 验证视频文件
                is_valid, error_msg = validate_video_file(file_path)
                if not is_valid:
                    QMessageBox.warning(self, "视频文件错误", f"选择的视频文件无效:\n{error_msg}")
                    self.logger.warning(f"选择的视频文件无效: {file_path}, 错误: {error_msg}")
                    return
                
                self.video_path_input.setText(file_path)
                self.logger.info(f"选择视频文件: {file_path}")
                
        except Exception as e:
            self.logger.error(f"浏览视频文件失败: {e}")
            QMessageBox.critical(self, "错误", f"浏览视频文件时发生错误:\n{str(e)}")
    
    def _browse_output_dir(self):
        """浏览输出目录"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self, "选择输出目录", self.output_dir_input.text()
            )
            if dir_path:
                self.output_dir_input.setText(dir_path)
        except Exception as e:
            self.logger.error(f"浏览输出目录失败: {e}")
    
    def _on_video_path_changed(self, path: str):
        """视频路径变化"""
        try:
            if path and os.path.exists(path):
                # 获取视频信息
                video_info = self.video_processor.get_video_info(path)
                self.current_video_path = path
                self.current_video_info = video_info
                
                # 更新显示
                info_text = f"文件: {os.path.basename(path)}\n"
                
                if video_info:
                    info_text += f"分辨率: {video_info.get('width', 'Unknown')}x{video_info.get('height', 'Unknown')}\n"
                    info_text += f"帧率: {video_info.get('fps', 'Unknown')} fps\n"
                    info_text += f"时长: {video_info.get('duration', 'Unknown')} 秒\n"
                    info_text += f"总帧数: {video_info.get('frame_count', 'Unknown')}"
                    
                    # 更新预览滑块
                    frame_count = video_info.get('frame_count', 0)
                    self.preview_frame_slider.setMaximum(max(0, frame_count - 1))
                    self.frame_info_label.setText(f"帧: 0/{frame_count}")
                else:
                    info_text += "视频信息获取失败\n"
                    info_text += "可能的原因: 文件损坏、格式不支持或编解码器缺失"
                    
                    # 重置预览滑块
                    self.preview_frame_slider.setMaximum(0)
                    self.frame_info_label.setText("帧: 0/0")
                
                self.video_info_label.setText(info_text)
                
            else:
                self.current_video_path = None
                self.current_video_info = None
                self.video_info_label.setText("未选择视频")
                self.preview_frame_slider.setMaximum(0)
                self.frame_info_label.setText("帧: 0/0")
                
        except Exception as e:
            self.logger.error(f"处理视频路径变化失败: {e}")
            # 重置界面状态
            self.current_video_path = None
            self.current_video_info = None
            self.video_info_label.setText(f"视频加载失败: {str(e)}")
            self.preview_frame_slider.setMaximum(0)
            self.frame_info_label.setText("帧: 0/0")
    
    def _on_algorithm_type_changed(self, algorithm_type: str):
        """算法类型变化"""
        self._update_algorithm_list()
    
    def _on_quality_changed(self, value: int):
        """质量设置变化"""
        self.quality_label.setText(f"{value}%")
    
    def _on_multithread_toggled(self, checked: bool):
        """多线程选项切换"""
        self.thread_count_spin.setEnabled(checked)
    
    def _on_preview_frame_changed(self, frame_num: int):
        """预览帧变化"""
        try:
            if self.current_video_info:
                frame_count = self.current_video_info.get('frame_count', 0)
                self.frame_info_label.setText(f"帧: {frame_num}/{frame_count}")
                
                # TODO: 实现帧预览功能
                
        except Exception as e:
            self.logger.error(f"处理预览帧变化失败: {e}")
    
    def _toggle_preview_play(self):
        """切换预览播放"""
        try:
            # TODO: 实现预览播放功能
            current_text = self.preview_play_btn.text()
            if current_text == "播放":
                self.preview_play_btn.setText("暂停")
            else:
                self.preview_play_btn.setText("播放")
        except Exception as e:
            self.logger.error(f"切换预览播放失败: {e}")
    
    def _preview_settings(self):
        """预览设置"""
        try:
            # TODO: 实现设置预览功能
            QMessageBox.information(self, "信息", "设置预览功能待实现")
        except Exception as e:
            self.logger.error(f"预览设置失败: {e}")
    
    def _start_processing(self):
        """开始处理"""
        try:
            if not self.current_video_path:
                QMessageBox.warning(self, "警告", "请选择视频文件")
                return
            
            if not self.algorithm_name_combo.currentText():
                QMessageBox.warning(self, "警告", "请选择处理算法")
                return
            
            # 准备任务配置
            algorithm_type_map = {
                "2D姿态估计": AlgorithmType.POSE_2D,
                "3D姿态估计": AlgorithmType.POSE_3D,
                "视频描述": AlgorithmType.VIDEO_DESCRIPTION
            }
            
            task_config = {
                'input_path': self.current_video_path,
                'algorithm_type': algorithm_type_map[self.algorithm_type_combo.currentText()],
                'algorithm_name': self.algorithm_name_combo.currentText(),
                'output_path': self.output_dir_input.text(),
                'options': {
                    'fps': self.fps_spin.value(),
                    'resolution': self.resolution_combo.currentText(),
                    'quality': self.quality_slider.value(),
                    'batch_mode': self.batch_process_check.isChecked(),
                    'use_gpu': self.gpu_check.isChecked(),
                    'use_multithread': self.multithread_check.isChecked(),
                    'thread_count': self.thread_count_spin.value(),
                    'memory_limit': self.memory_limit_spin.value()
                }
            }
            
            # 启动处理线程
            self.processing_thread = VideoProcessingThread(
                self.algorithm_manager, self.video_processor, task_config
            )
            
            self.processing_thread.progress_updated.connect(self._on_progress_updated)
            self.processing_thread.status_updated.connect(self._on_status_updated)
            self.processing_thread.result_ready.connect(self._on_result_ready)
            self.processing_thread.error_occurred.connect(self._on_error_occurred)
            self.processing_thread.frame_processed.connect(self._on_frame_processed)
            
            self.processing_thread.start()
            
            # 更新界面状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("开始处理...")
            
            self.status_changed.emit("开始视频处理")
            
        except Exception as e:
            self.logger.error(f"开始处理失败: {e}")
            QMessageBox.critical(self, "错误", f"开始处理失败: {e}")
    
    def _stop_processing(self):
        """停止处理"""
        try:
            if self.processing_thread and self.processing_thread.isRunning():
                self.processing_thread.stop()
            
            # 重置界面状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("已停止")
            
            self.status_changed.emit("处理已停止")
            
        except Exception as e:
            self.logger.error(f"停止处理失败: {e}")
    
    def _export_results(self):
        """导出结果"""
        try:
            if not self.processing_results:
                QMessageBox.warning(self, "警告", "没有可导出的结果")
                return
            
            # TODO: 实现结果导出功能
            QMessageBox.information(self, "信息", "结果导出功能待实现")
            
        except Exception as e:
            self.logger.error(f"导出结果失败: {e}")
    
    def _clear_results(self):
        """清空结果"""
        try:
            self.processing_results.clear()
            self.result_tree.clear()
            self.stats_table.setRowCount(0)
        except Exception as e:
            self.logger.error(f"清空结果失败: {e}")
    
    def _clear_log(self):
        """清空日志"""
        try:
            self.log_text.clear()
        except Exception as e:
            self.logger.error(f"清空日志失败: {e}")
    
    def _save_log(self):
        """保存日志"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存日志", "processing_log.txt", "文本文件 (*.txt);;所有文件 (*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                
                QMessageBox.information(self, "信息", "日志保存成功")
                
        except Exception as e:
            self.logger.error(f"保存日志失败: {e}")
            QMessageBox.critical(self, "错误", f"保存日志失败: {e}")
    
    # 线程信号处理
    def _on_progress_updated(self, progress: float):
        """进度更新"""
        self.progress_bar.setValue(int(progress))
        self.progress_changed.emit(int(progress))
    
    def _on_status_updated(self, status: str):
        """状态更新"""
        self.status_label.setText(status)
        self.status_changed.emit(status)
        
        # 添加到日志
        self._add_log(f"[状态] {status}")
    
    def _on_result_ready(self, result: dict):
        """结果就绪"""
        try:
            self.processing_results.append(result)
            
            # 更新结果树
            self._update_result_tree(result)
            
            # 更新统计信息
            self._update_stats()
            
            # 重置界面状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("处理完成")
            
            self.status_changed.emit("处理完成")
            
            self._add_log("[完成] 视频处理完成")
            
        except Exception as e:
            self.logger.error(f"处理结果失败: {e}")
    
    def _on_error_occurred(self, error: str):
        """发生错误"""
        try:
            # 重置界面状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("处理失败")
            
            self.status_changed.emit("处理失败")
            
            self._add_log(f"[错误] {error}")
            
            QMessageBox.critical(self, "处理错误", f"处理失败: {error}")
            
        except Exception as e:
            self.logger.error(f"处理错误失败: {e}")
    
    def _on_frame_processed(self, frame_num: int, result: object):
        """帧处理完成"""
        try:
            # TODO: 更新预览显示
            pass
        except Exception as e:
            self.logger.error(f"处理帧结果失败: {e}")
    
    def _update_result_tree(self, result: dict):
        """更新结果树"""
        try:
            # 创建根节点
            root_item = QTreeWidgetItem(self.result_tree)
            algorithm_name = result.get('algorithm_name', '未知算法')
            input_path = result.get('input_path', '未知路径')
            root_item.setText(0, f"{algorithm_name} - {Path(input_path).name}")
            
            # 根据算法类型处理结果
            algorithm_type = result.get('algorithm_type')
            if algorithm_type == 'VIDEO_DESCRIPTION' and algorithm_name == 'ShareGPT4Video':
                self._add_sharegpt4video_result(root_item, result)
            else:
                self._add_general_result(root_item, result)
                
            # 展开根节点
            root_item.setExpanded(True)
            
        except Exception as e:
            self.logger.error(f"更新结果树失败: {e}")
    
    def _add_sharegpt4video_result(self, parent_item: QTreeWidgetItem, result: dict):
        """添加ShareGPT4Video结果"""
        try:
            # 显示处理日志（包含警告信息）
            processing_log = result.get('processing_log', '')
            if processing_log:
                log_item = QTreeWidgetItem(parent_item)
                log_item.setText(0, "处理日志")
                
                # 按行分割日志并添加子项
                log_lines = processing_log.strip().split('\n')
                for line in log_lines:
                    if line.strip():
                        line_item = QTreeWidgetItem(log_item)
                        line_item.setText(0, line.strip())
                        
                        # 高亮警告信息
                        if 'WARNING' in line or 'warning' in line:
                            line_item.setForeground(0, QColor(255, 165, 0))  # 橙色
                        elif 'ERROR' in line or 'error' in line:
                            line_item.setForeground(0, QColor(255, 0, 0))  # 红色
                
                log_item.setExpanded(True)
            
            # 显示最终描述结果
            description = result.get('description', '')
            if description:
                desc_item = QTreeWidgetItem(parent_item)
                desc_item.setText(0, "视频描述")
                
                # 将描述按句子分割显示
                sentences = description.split('. ')
                for sentence in sentences:
                    if sentence.strip():
                        sentence_item = QTreeWidgetItem(desc_item)
                        sentence_item.setText(0, sentence.strip() + ('.' if not sentence.endswith('.') else ''))
                
                desc_item.setExpanded(True)
                
        except Exception as e:
            self.logger.error(f"添加ShareGPT4Video结果失败: {e}")
    
    def _add_general_result(self, parent_item: QTreeWidgetItem, result: dict):
        """添加通用算法结果"""
        try:
            # 显示基本信息
            for key, value in result.items():
                if key not in ['algorithm_name', 'input_path', 'algorithm_type']:
                    item = QTreeWidgetItem(parent_item)
                    item.setText(0, f"{key}: {value}")
                    
        except Exception as e:
            self.logger.error(f"添加通用结果失败: {e}")
    
    def _update_stats(self):
        """更新统计信息"""
        try:
            # TODO: 实现统计信息更新
            pass
        except Exception as e:
            self.logger.error(f"更新统计信息失败: {e}")
    
    def _add_log(self, message: str):
        """添加日志"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_message = f"[{timestamp}] {message}"
            
            self.log_text.append(log_message)
            
            # 自动滚动
            if self.auto_scroll_check.isChecked():
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.End)
                self.log_text.setTextCursor(cursor)
                
        except Exception as e:
            self.logger.error(f"添加日志失败: {e}")
    
    # 公共接口
    def start_processing(self):
        """开始处理（由主窗口调用）"""
        self._start_processing()
    
    def stop_processing(self):
        """停止处理（由主窗口调用）"""
        self._stop_processing()
    
    def cleanup(self):
        """清理资源"""
        try:
            # 保存当前设置
            self._save_settings()
            
            if self.processing_thread and self.processing_thread.isRunning():
                self.processing_thread.stop()
            
            self.logger.info("视频处理界面组件资源清理完成")
            
        except Exception as e:
            self.logger.error(f"视频处理界面组件资源清理失败: {e}")