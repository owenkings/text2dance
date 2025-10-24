# -*- coding: utf-8 -*-
"""
视频描述界面组件
提供视频描述功能的用户界面
"""

import os
import json
import csv
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import deque
import cv2
import numpy as np

# 导入缓存管理器
from ..core.cache_manager import get_cache_manager

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QShortcut,
    QDialog, QAbstractItemView, QSizePolicy, QApplication,
    QButtonGroup, QRadioButton, QFormLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QMutex, QUrl
from PyQt5.QtGui import QFont, QPixmap, QKeySequence, QImage, QIcon, QMovie

class MultiFolderSelectionDialog(QDialog):
    """支持多选的文件夹选择对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择多个文件夹")
        self.setModal(True)
        self.resize(800, 600)
        
        # 存储选中的文件夹
        self.selected_folders = []
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 说明文字
        info_label = QLabel("请选择要处理的文件夹（支持Ctrl+点击多选，Shift+点击范围选择）：")
        info_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # 文件夹树形视图
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabel("文件夹")
        self.folder_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 支持多选
        self.folder_tree.setRootIsDecorated(True)
        layout.addWidget(self.folder_tree)
        
        # 当前路径显示
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("当前路径:"))
        self.current_path_label = QLabel("")
        self.current_path_label.setStyleSheet("color: #666; font-family: monospace;")
        path_layout.addWidget(self.current_path_label)
        path_layout.addStretch()
        layout.addLayout(path_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 浏览按钮
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_root_folder)
        button_layout.addWidget(self.browse_btn)
        
        # 全选/取消全选按钮
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all_folders)
        button_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.clicked.connect(self._deselect_all_folders)
        button_layout.addWidget(self.deselect_all_btn)
        
        button_layout.addStretch()
        
        # 确认和取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QPushButton("确认")
        self.ok_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #3498db;"
            "    color: white;"
            "    border: none;"
            "    padding: 8px 16px;"
            "    border-radius: 4px;"
            "    font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "    background-color: #2980b9;"
            "}"
        )
        self.ok_btn.clicked.connect(self._accept_selection)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
        
        # 初始化显示当前工作目录
        self._load_folder_tree(os.getcwd())
    
    def _browse_root_folder(self):
        """浏览选择根文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择根文件夹")
        if folder:
            self._load_folder_tree(folder)
    
    def _load_folder_tree(self, root_path):
        """加载文件夹树"""
        self.folder_tree.clear()
        self.current_path_label.setText(root_path)
        
        try:
            # 创建根节点
            root_item = QTreeWidgetItem(self.folder_tree)
            root_item.setText(0, os.path.basename(root_path) or root_path)
            root_item.setData(0, Qt.UserRole, root_path)
            root_item.setExpanded(True)
            
            # 递归加载子文件夹
            self._load_subfolders(root_item, root_path, max_depth=3)
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载文件夹失败: {str(e)}")
    
    def _load_subfolders(self, parent_item, folder_path, max_depth=3, current_depth=0):
        """递归加载子文件夹"""
        if current_depth >= max_depth:
            return
        
        try:
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    # 创建子节点
                    child_item = QTreeWidgetItem(parent_item)
                    child_item.setText(0, item)
                    child_item.setData(0, Qt.UserRole, item_path)
                    
                    # 递归加载更深层的文件夹
                    self._load_subfolders(child_item, item_path, max_depth, current_depth + 1)
                    
        except PermissionError:
            # 忽略权限错误
            pass
        except Exception:
            # 忽略其他错误
            pass
    
    def _select_all_folders(self):
        """全选所有文件夹"""
        self.folder_tree.selectAll()
    
    def _deselect_all_folders(self):
        """取消全选所有文件夹"""
        self.folder_tree.clearSelection()
    
    def _accept_selection(self):
        """确认选择"""
        selected_items = self.folder_tree.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "提示", "请至少选择一个文件夹")
            return
        
        # 获取选中的文件夹路径
        self.selected_folders = []
        for item in selected_items:
            folder_path = item.data(0, Qt.UserRole)
            if folder_path and os.path.isdir(folder_path):
                self.selected_folders.append(folder_path)
        
        if not self.selected_folders:
            QMessageBox.warning(self, "提示", "没有找到有效的文件夹")
            return
        
        self.accept()
    
    def get_selected_folders(self):
        """获取选中的文件夹列表"""
        return self.selected_folders

class CustomAPIDialog(QDialog):
    """自定义API模型配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义API模型配置")
        self.setModal(True)
        self.setFixedSize(500, 350)
        
        layout = QVBoxLayout(self)
        
        # 说明文字
        info_label = QLabel("请填写您的API模型配置信息：")
        info_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # API端点
        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.setPlaceholderText("如：https://api.openai.com/v1/chat/completions")
        self.endpoint_edit.setToolTip("API服务的完整端点URL地址")
        form_layout.addRow("API端点 (必填):", self.endpoint_edit)
        
        # API密钥
        api_key_layout = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("输入您的API密钥")
        self.api_key_edit.setToolTip("用于身份验证的API密钥")
        api_key_layout.addWidget(self.api_key_edit)
        
        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.setMaximumWidth(50)
        self.show_key_btn.clicked.connect(self._toggle_key_visibility)
        api_key_layout.addWidget(self.show_key_btn)
        
        form_layout.addRow("API密钥 (必填):", api_key_layout)
        
        # 模型名称
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText("如：gpt-4-vision-preview")
        self.model_name_edit.setToolTip("API服务中的具体模型名称")
        form_layout.addRow("模型名称 (必填):", self.model_name_edit)
        
        # 自定义显示名称
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("如：我的GPT-4模型")
        self.display_name_edit.setToolTip("在界面中显示的自定义名称")
        form_layout.addRow("显示名称 (必填):", self.display_name_edit)
        
        layout.addLayout(form_layout)
        
        # 添加间距
        layout.addSpacing(20)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QPushButton("确认")
        self.ok_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #3498db;"
            "    color: white;"
            "    border: none;"
            "    padding: 8px 16px;"
            "    border-radius: 4px;"
            "    font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "    background-color: #2980b9;"
            "}"
        )
        self.ok_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
    
    def _toggle_key_visibility(self):
        """切换API密钥显示/隐藏"""
        if self.api_key_edit.echoMode() == QLineEdit.Password:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self.show_key_btn.setText("隐藏")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.show_key_btn.setText("显示")
    
    def _validate_and_accept(self):
        """验证输入并接受对话框"""
        # 检查必填字段
        if not self.endpoint_edit.text().strip():
            QMessageBox.warning(self, "输入错误", "请填写API端点")
            self.endpoint_edit.setFocus()
            return
        
        if not self.api_key_edit.text().strip():
            QMessageBox.warning(self, "输入错误", "请填写API密钥")
            self.api_key_edit.setFocus()
            return
        
        if not self.model_name_edit.text().strip():
            QMessageBox.warning(self, "输入错误", "请填写模型名称")
            self.model_name_edit.setFocus()
            return
        
        if not self.display_name_edit.text().strip():
            QMessageBox.warning(self, "输入错误", "请填写显示名称")
            self.display_name_edit.setFocus()
            return
        
        # 验证URL格式
        endpoint = self.endpoint_edit.text().strip()
        if not (endpoint.startswith('http://') or endpoint.startswith('https://')):
            QMessageBox.warning(self, "输入错误", "API端点必须以http://或https://开头")
            self.endpoint_edit.setFocus()
            return
        
        self.accept()

class FrameRateMonitor:
    """帧率监控器"""
    
    def __init__(self, window_size=30):
        self.frame_times = deque(maxlen=window_size)
        self.last_frame_time = time.time()
        self.frame_count = 0
    
    def record_frame(self):
        """记录一帧的时间"""
        current_time = time.time()
        if self.frame_count > 0:  # 跳过第一帧
            frame_interval = current_time - self.last_frame_time
            self.frame_times.append(frame_interval)
        
        self.last_frame_time = current_time
        self.frame_count += 1
    
    def get_measured_fps(self):
        """获取测量的FPS"""
        if len(self.frame_times) < 2:
            return 0
        
        avg_interval = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_interval if avg_interval > 0 else 0
    
    def reset(self):
        """重置监控器"""
        self.frame_times.clear()
        self.frame_count = 0
        self.last_frame_time = time.time()

class AdaptivePIDController:
    """自适应PID控制器"""
    
    def __init__(self, kp=0.1, ki=0.01, kd=0.05, target_fps=30.0):
        self.kp = kp  # 比例增益
        self.ki = ki  # 积分增益
        self.kd = kd  # 微分增益
        self.target_fps = target_fps
        
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = time.time()
    
    def update(self, measured_fps):
        """更新控制器并返回调整值"""
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0:
            return 0
        
        # 计算误差
        error = self.target_fps - measured_fps
        
        # 积分项
        self.integral += error * dt
        # 限制积分项防止积分饱和
        self.integral = max(-10, min(10, self.integral))
        
        # 微分项
        derivative = (error - self.last_error) / dt
        
        # PID输出
        output = (self.kp * error + 
                 self.ki * self.integral + 
                 self.kd * derivative)
        
        self.last_error = error
        self.last_time = current_time
        
        return output
    
    def set_target_fps(self, target_fps):
        """设置目标FPS"""
        self.target_fps = target_fps
    
    def reset(self):
        """重置控制器"""
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = time.time()

class VideoDescriptionThread(QThread):
    """视频描述处理线程 - 使用批量处理优化"""
    
    progress_updated = pyqtSignal(int)  # 进度百分比
    status_updated = pyqtSignal(str)  # 状态信息
    log_updated = pyqtSignal(str)  # 实时日志更新
    video_completed = pyqtSignal(str, bool, str, str, float, str)  # 视频路径, 是否成功, 描述内容, 错误信息, 总耗时, 实际时间戳
    all_completed = pyqtSignal()

    def __init__(self, videos, description_requirement, model_path, use_action_filter=False, generation_mode="random", description_length=300, num_frames=16, api_config=None, device="Auto", enable_multithread=False, thread_count=2, top_p=0.9, algorithm_type="本地模型", enable_gpu_optimization=False, gpu_batch_size=2, gpu_max_workers=4, enable_smart_loading=True, enable_fast_preload=True, gpu_device="自动检测"):
        super().__init__()
        self.videos = videos
        self.description_requirement = description_requirement
        self.model_path = model_path
        self.use_action_filter = use_action_filter
        self.generation_mode = generation_mode  # "deterministic" 或 "random"
        self.description_length = description_length  # 描述长度要求（字符数）
        self.num_frames = num_frames
        self.api_config = api_config or {}
        self.device = device  # 添加设备参数
        self.enable_multithread = enable_multithread  # 是否启用多线程
        self.thread_count = thread_count  # 线程数量
        self.top_p = top_p  # Top-p参数
        self.algorithm_type = algorithm_type  # 算法类型："本地模型" 或 "API调用"
        self.enable_gpu_optimization = enable_gpu_optimization  # 是否启用GPU优化
        self.gpu_batch_size = gpu_batch_size  # GPU批处理大小
        self.gpu_max_workers = gpu_max_workers  # GPU预处理线程数
        self.enable_smart_loading = enable_smart_loading  # 是否启用智能加载
        self.enable_fast_preload = enable_fast_preload  # 是否启用快速预加载
        self.gpu_device = gpu_device  # GPU设备选择
        self.is_running = True
        self.results = []
        self.current_process = None  # 初始化当前进程引用
    
    def stop(self):
        """停止处理线程"""
        self.is_running = False
        
        # 如果有正在运行的子进程，强制终止
        if hasattr(self, 'current_process') and self.current_process:
            try:
                self.current_process.terminate()
                # 等待进程终止，最多等待3秒
                try:
                    self.current_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # 如果3秒后还没终止，强制杀死进程
                    self.current_process.kill()
                    self.current_process.wait()
            except Exception as e:
                import traceback
                print(f"强制终止子进程时出错: {e}")
                # 添加日志记录
                if hasattr(self, 'logger'):
                    self.logger.error(f"强制终止子进程失败: {e}")
                    self.logger.debug(f"强制终止子进程失败详细信息: {traceback.format_exc()}")
        
        self.quit()
        # 设置超时等待，避免无限等待
        if not self.wait(5000):  # 等待5秒
            self.terminate()  # 强制终止线程
    
    def run(self):
        try:
            total_videos = len(self.videos)
            
            # 根据算法类型选择处理方式
            if self.algorithm_type == "API调用":
                self.status_updated.emit(f"🚀 开始API处理 {total_videos} 个视频...")
                self.log_updated.emit("使用API调用模式进行视频描述")
                
                # 初始化进度条
                self.progress_updated.emit(0)
                
                # 输出API信息
                api_info = f"使用API模型: {self.api_config.get('api_model', 'gpt-3.5-turbo')}"
                self.log_updated.emit(api_info)
                
                # 记录整体开始时间
                overall_start_time = time.time()
                
                # API模式处理
                success, results = self._process_videos_api()
                
            else:  # 本地模型模式
                # 检查是否启用多线程处理
                if self.enable_multithread and self.device in ["CUDA", "Auto"] and total_videos > 1:
                    self.status_updated.emit(f"🚀 开始多线程处理 {total_videos} 个视频，使用 {self.thread_count} 个线程...")
                    self.progress_updated.emit(0)
                    self.log_updated.emit(f"使用多线程处理模式 ({self.thread_count} 个线程并行处理)")
                else:
                    self.status_updated.emit(f"🚀 开始批量处理 {total_videos} 个视频...")
                    self.log_updated.emit("使用优化的批量处理模式 (1次模型加载 + N次推理)")
                    self.progress_updated.emit(0)
                
                # 输出设备信息
                device_info = f"此次运行使用的计算设备: {self.device}"
                if self.device == "Auto":
                    device_info += " (将自动检测最佳设备)"
                elif self.device == "CUDA":
                    device_info += " (强制使用GPU加速)"
                elif self.device == "CPU":
                    device_info += " (强制使用CPU处理)"
                self.log_updated.emit(device_info)
                
                # 记录整体开始时间
                overall_start_time = time.time()
                
                # 根据设置选择处理方式
                if self.enable_multithread and self.device in ["CUDA", "Auto"] and total_videos > 1:
                    success, results = self._process_videos_multithread()
                else:
                    success, results = self._process_videos_batch()
            
            if success and results:
                # 处理每个视频的结果
                for i, result in enumerate(results):
                    if not self.is_running:
                        break
                    
                    video_path = result['video_path']
                    is_success = result['success']
                    description = result['description'] or ""
                    error_msg = result.get('error_message', "")
                    processing_time = result.get('processing_time', 0)
                    
                    # 如果需要动作过滤
                    filter_success = False
                    action_description = ""
                    if is_success and hasattr(self, 'use_action_filter') and self.use_action_filter and description:
                        filter_result = self._filter_action_description(description)
                        action_description = filter_result['description']
                        filter_success = filter_result['filter_success']
                    
                    # 记录结果
                    processed_result = {
                        'video_path': video_path,
                        'success': is_success,
                        'description': description,  # 保留原始描述
                        'action_description': action_description,  # 添加过滤后的动作描述
                        'error_message': error_msg,
                        'start_time': result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'end_time': result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'total_processing_time': round(processing_time, 2),
                        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': self._get_video_duration(video_path),
                        'action_filter_applied': filter_success  # 添加动作过滤成功标记
                    }
                    self.results.append(processed_result)
                    
                    # 如果成功应用了动作过滤，创建标记文件
                    if filter_success:
                        self._mark_action_filter_applied(video_path)
                    
                    # 发送完成信号，包含实际生成描述的时间戳
                    actual_timestamp = result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    self.video_completed.emit(video_path, is_success, description, error_msg, processing_time, actual_timestamp)
                    
                    # 不在线程中直接保存结果，而是通过信号传递给主线程处理
                    # API模型结果将由主线程中的_on_video_completed方法保存
                    
                    # 更新进度和状态
                    progress = int(((i + 1) / total_videos) * 100)
                    self.progress_updated.emit(progress)
                    
                    completed_status = f"✅ 已完成 {i+1}/{total_videos}: {os.path.basename(video_path)}"
                    self.status_updated.emit(completed_status)
                    self.log_updated.emit(completed_status)
            else:
                self.status_updated.emit("批量处理失败")
                self.log_updated.emit("批量处理脚本执行失败")
            
            # 计算总耗时
            overall_end_time = time.time()
            total_time = overall_end_time - overall_start_time
            
            if self.is_running:
                # 完成时设置进度条为100%
                self.progress_updated.emit(100)
                self.status_updated.emit("✅ 批量处理完成")
                self.log_updated.emit(f"✅ 批量处理完成，总耗时: {total_time:.2f}秒")
                self.log_updated.emit(f"📊 平均每个视频: {total_time/total_videos:.2f}秒")
                self.all_completed.emit()
                
        except Exception as e:
            self.status_updated.emit(f"处理过程中发生错误: {str(e)}")
            self.log_updated.emit(f"异常详情: {str(e)}")
    
    def _process_videos_multithread(self):
        """多线程处理视频"""
        import threading
        import queue
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        try:
            total_videos = len(self.videos)
            self.log_updated.emit(f"准备启动 {self.thread_count} 个处理线程")
            
            # 将视频分组，每组分配给一个线程
            video_chunks = []
            chunk_size = max(1, total_videos // self.thread_count)
            
            for i in range(0, total_videos, chunk_size):
                chunk = self.videos[i:i + chunk_size]
                if chunk:  # 确保chunk不为空
                    video_chunks.append(chunk)
            
            # 如果分组数量超过线程数，合并最后的小组
            while len(video_chunks) > self.thread_count:
                last_chunk = video_chunks.pop()
                video_chunks[-1].extend(last_chunk)
            
            self.log_updated.emit(f"视频分组完成：{len(video_chunks)} 个组，每组平均 {total_videos/len(video_chunks):.1f} 个视频")
            
            all_results = []
            completed_count = 0
            
            # 使用线程池执行器
            with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
                # 提交所有任务
                future_to_chunk = {}
                for i, chunk in enumerate(video_chunks):
                    future = executor.submit(self._process_video_chunk, chunk, i)
                    future_to_chunk[future] = (chunk, i)
                
                # 处理完成的任务
                for future in as_completed(future_to_chunk):
                    if not self.is_running:
                        self.log_updated.emit("用户取消多线程处理")
                        executor.shutdown(wait=False)
                        return False, []
                    
                    chunk, chunk_id = future_to_chunk[future]
                    try:
                        success, results = future.result()
                        if success and results:
                            all_results.extend(results)
                            completed_count += len(chunk)
                            
                            # 更新进度和状态
                            progress = int((completed_count / total_videos) * 100)
                            self.progress_updated.emit(progress)
                            
                            status_msg = f"🔄 多线程处理中 - 已完成 {completed_count}/{total_videos} 个视频"
                            self.status_updated.emit(status_msg)
                            self.log_updated.emit(f"✅ 线程 {chunk_id} 完成，处理了 {len(chunk)} 个视频")
                            
                            # 发送每个视频的完成信号
                            for result in results:
                                actual_timestamp = result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                                self.video_completed.emit(
                                    result['video_path'],
                                    result['success'],
                                    result['description'] or "",
                                    result.get('error_message', ""),
                                    result.get('processing_time', 0),
                                    actual_timestamp
                                )
                        else:
                            self.log_updated.emit(f"线程 {chunk_id} 处理失败")
                            
                    except Exception as e:
                        self.log_updated.emit(f"线程 {chunk_id} 发生异常: {str(e)}")
            
            if all_results:
                # 多线程处理完成时设置进度条为100%
                self.progress_updated.emit(100)
                self.status_updated.emit("✅ 多线程处理完成")
                self.log_updated.emit(f"✅ 多线程处理完成，共处理 {len(all_results)} 个视频")
                return True, all_results
            else:
                self.status_updated.emit("❌ 多线程处理失败")
                self.log_updated.emit("❌ 多线程处理失败，没有获得任何结果")
                return False, []
                
        except Exception as e:
            error_msg = f"多线程处理时发生异常: {str(e)}"
            self.log_updated.emit(error_msg)
            return False, []
    
    def _process_video_chunk(self, video_chunk, chunk_id):
        """处理一组视频（在单独线程中运行）"""
        try:
            self.log_updated.emit(f"线程 {chunk_id} 开始处理 {len(video_chunk)} 个视频")
            
            # 构建批量处理命令
            cmd = [
                'python',
                'src/algorithms/video_description/ShareGPT4Video/batch_run.py',
                '--model-path', self.model_path,
                '--query', self.description_requirement,
                '--device', self.device,
                '--output-format', 'json'
            ]
            
            # 创建临时配置文件传递视频列表，避免Windows命令行长度限制
            import tempfile
            import json
            import os
            
            # 生成视频配置
            video_configs = []
            for video_path in video_chunk:
                video_config = {
                    "video_path": video_path,
                    "query": self.description_requirement,
                    "num_frames": self.num_frames if self.num_frames > 0 else 16,
                    "do_sample": self.generation_mode != "deterministic",
                    "top_p": self.top_p if self.generation_mode in ["random", "hybrid"] else 0.9,
                    "temperature": 0.8 if self.generation_mode == "hybrid" else 1.0,
                    "num_beams": 2 if self.generation_mode == "hybrid" else 1,
                    "max_new_tokens": None  # 不限制输出长度
                }
                video_configs.append(video_config)
            
            # 创建临时配置文件
            config_fd, config_path = tempfile.mkstemp(suffix='.json', prefix='chunk_config_')
            config_file_created = False
            try:
                with os.fdopen(config_fd, 'w', encoding='utf-8') as f:
                    json.dump(video_configs, f, ensure_ascii=False, indent=2)
                config_file_created = True
                
                self.log_updated.emit(f"线程 {chunk_id} 创建临时配置文件: {config_path}")
                
                # 使用配置文件而不是直接传递视频列表
                cmd.extend(['--config-file', config_path])
            except Exception as e:
                self.log_updated.emit(f"线程 {chunk_id} 创建临时配置文件失败: {str(e)}")
                return False, []
            
            # 根据描述长度要求更新提示词（但不限制max_new_tokens）
            # 注意：描述长度等级现在只用于API模型的动作过滤功能，本地模型不再使用长度建议
            # if self.description_length > 0:
            #     # 在提示词中添加长度建议，但不强制限制输出长度
            #     enhanced_query = f"{self.description_requirement} The total length of the description should be approximately {self.description_length} characters."
            #     cmd[cmd.index('--query') + 1] = enhanced_query
            # # 如果是无限制模式，保持原始提示词不变
            
            # 注意：不再设置max_new_tokens限制，让模型自由生成完整描述
            # 描述长度要求仅作为提示词中的建议，不应强制截断输出
            
            if self.num_frames > 0:
                cmd.extend(['--num-frames', str(self.num_frames)])
            else:
                cmd.extend(['--num-frames', '16'])
            
            # 添加生成控制参数
            if self.generation_mode == "deterministic":
                cmd.extend(['--do-sample', 'False', '--num-beams', '1'])
            elif self.generation_mode == "random":
                cmd.extend(['--do-sample', 'True', '--top-p', str(self.top_p)])
            elif self.generation_mode == "hybrid":
                cmd.extend(['--do-sample', 'True', '--top-p', str(self.top_p), '--temperature', '0.8', '--num-beams', '2'])
            
            # 设置工作目录
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=project_root
            )
            
            output, _ = process.communicate()
            
            if process.returncode == 0:
                # 解析JSON结果
                try:
                    import json
                    # 查找JSON输出
                    lines = output.strip().split('\n')
                    json_start = -1
                    
                    for i, line in enumerate(lines):
                        if line.strip().startswith('{'):
                            json_start = i
                            break
                    
                    if json_start != -1:
                        json_text = '\n'.join(lines[json_start:])
                        json_output = json.loads(json_text)
                        
                        if 'results' in json_output:
                            results = json_output['results']
                            self.log_updated.emit(f"线程 {chunk_id} 成功解析 {len(results)} 个结果")
                            
                            # 为每个结果发送video_completed信号，确保结果被正确保存
                            for result in results:
                                video_path = result.get('video_path', '')
                                success = result.get('success', False)
                                description = result.get('description', '')
                                error_msg = result.get('error_message', '')
                                processing_time = result.get('processing_time', 0)
                                
                                # 获取时间戳，如果不存在则使用当前时间
                                actual_timestamp = result.get('timestamp')
                                if not actual_timestamp:
                                    actual_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                
                                # 发送video_completed信号，触发结果保存
                                self.video_completed.emit(
                                    video_path, 
                                    success, 
                                    description, 
                                    error_msg, 
                                    processing_time, 
                                    actual_timestamp
                                )
                            
                            return True, results
                        else:
                            self.log_updated.emit(f"线程 {chunk_id} JSON中未找到results字段")
                            return False, []
                    else:
                        self.log_updated.emit(f"线程 {chunk_id} 未找到JSON输出")
                        return False, []
                        
                except json.JSONDecodeError as e:
                    self.log_updated.emit(f"线程 {chunk_id} JSON解析失败: {str(e)}")
                    # 创建备用结果并发送video_completed信号
                    fallback_results = []
                    for video_path in video_chunk:
                        actual_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        fallback_result = {
                            'video_path': video_path,
                            'success': True,
                            'description': '处理完成，但无法获取详细描述内容（JSON解析失败）',
                            'error_message': '',
                            'processing_time': 0,
                            'timestamp': actual_timestamp
                        }
                        fallback_results.append(fallback_result)
                        
                        # 发送video_completed信号，确保备用结果也被保存
                        self.video_completed.emit(
                            video_path, 
                            True, 
                            '处理完成，但无法获取详细描述内容（JSON解析失败）', 
                            '', 
                            0, 
                            actual_timestamp
                        )
                    return True, fallback_results
            else:
                self.log_updated.emit(f"线程 {chunk_id} 处理失败，返回码: {process.returncode}")
                self.log_updated.emit(f"线程 {chunk_id} 错误输出: {output}")
                return False, []
        
        except Exception as e:
            self.log_updated.emit(f"线程 {chunk_id} 发生异常: {str(e)}")
            return False, []
        finally:
            # 清理临时配置文件
            try:
                if config_file_created and os.path.exists(config_path):
                    os.unlink(config_path)
                    self.log_updated.emit(f"线程 {chunk_id} 清理临时配置文件: {config_path}")
            except Exception as e:
                self.log_updated.emit(f"线程 {chunk_id} 清理临时配置文件失败: {str(e)}")
    
    def _process_videos_api(self):
        """使用API处理所有视频"""
        try:
            import requests
            import json
            import base64
            import cv2
            import numpy as np
            from datetime import datetime
            
            # 验证API配置
            api_endpoint = self.api_config.get('api_endpoint', '').strip()
            api_key = self.api_config.get('api_key', '').strip()
            # 视频描述API应该使用支持多模态的模型
            api_model = "doubao-1.5-vision-pro-250328"  # 强制使用支持多模态的视频理解模型
            api_key = "fa1f2df2-73f8-44b1-99a0-09834047ab51"  # 视频描述API密钥
            
            if not api_endpoint:
                self.log_updated.emit("API端点配置不完整，请检查设置")
                return False, []
            
            self.log_updated.emit(f"使用API端点: {api_endpoint}")
            self.log_updated.emit(f"使用模型: {api_model}")
            
            results = []
            total_videos = len(self.videos)
            
            for i, video_path in enumerate(self.videos):
                if not self.is_running:
                    self.log_updated.emit("用户取消API处理")
                    break
                
                video_name = os.path.basename(video_path)
                self.status_updated.emit(f"正在处理 {i+1}/{total_videos}: {video_name}")
                self.log_updated.emit(f"开始处理视频: {video_name}")
                
                # 实时更新进度条
                progress = int((i / total_videos) * 100)
                self.progress_updated.emit(progress)
                
                start_time = time.time()
                
                try:
                    # 提取视频帧
                    frames = self._extract_video_frames(video_path)
                    if not frames:
                        error_msg = "无法提取视频帧"
                        self.log_updated.emit(f"{video_name}: {error_msg}")
                        results.append({
                            'video_path': video_path,
                            'success': False,
                            'description': '',
                            'error_message': error_msg,
                            'processing_time': 0,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        continue
                    
                    # 将帧转换为base64编码
                    encoded_frames = []
                    for frame in frames:
                        _, buffer = cv2.imencode('.jpg', frame)
                        frame_base64 = base64.b64encode(buffer).decode('utf-8')
                        encoded_frames.append(frame_base64)
                    
                    # 构建API请求
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}'
                    }
                    
                    # 构建消息内容 - doubao-1.5-vision-pro-250328是支持多模态的视频理解模型
                    content = [{
                        "type": "text",
                        "text": self.description_requirement
                    }]
                    
                    # 添加视频帧
                    for frame_base64 in encoded_frames:
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{frame_base64}"
                            }
                        })
                    
                    payload = {
                        "model": api_model,
                        "messages": [{
                            "role": "user",
                            "content": content
                        }],
                        "max_tokens": 16384
                    }
                    
                    # 发送API请求
                    self.log_updated.emit(f"{video_name}: 发送API请求...")
                    self.status_updated.emit(f"正在调用API处理 {i+1}/{total_videos}: {video_name}")
                    response = requests.post(api_endpoint, headers=headers, json=payload, timeout=60)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        description = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        
                        # 提取token使用量信息
                        usage_info = response_data.get('usage', {})
                        prompt_tokens = usage_info.get('prompt_tokens', 0)
                        completion_tokens = usage_info.get('completion_tokens', 0)
                        total_tokens = usage_info.get('total_tokens', 0)
                        
                        # 提取账户余额信息（如果API提供）
                        account_info = response_data.get('account', {})
                        remaining_balance = account_info.get('remaining_balance', 'N/A')
                        
                        if description:
                            processing_time = time.time() - start_time
                            
                            # 显示token使用量信息
                            token_info = f"Token使用: 输入{prompt_tokens}, 输出{completion_tokens}, 总计{total_tokens}"
                            if remaining_balance != 'N/A':
                                token_info += f", 余额: {remaining_balance}"
                            
                            self.log_updated.emit(f"{video_name}: API处理成功，耗时 {processing_time:.2f}秒")
                            self.log_updated.emit(f"{video_name}: {token_info}")
                            
                            actual_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            results.append({
                                'video_path': video_path,
                                'success': True,
                                'description': description,
                                'error_message': '',
                                'processing_time': processing_time,
                                'timestamp': actual_timestamp,
                                'token_usage': {
                                    'prompt_tokens': prompt_tokens,
                                    'completion_tokens': completion_tokens,
                                    'total_tokens': total_tokens
                                },
                                'account_balance': remaining_balance
                            })
                            
                            # 发送video_completed信号，确保实时更新单个视频结果
                            self.video_completed.emit(
                                video_path, 
                                True, 
                                description, 
                                '', 
                                processing_time, 
                                actual_timestamp
                            )
                        else:
                            error_msg = "API返回空描述"
                            self.log_updated.emit(f"{video_name}: {error_msg}")
                            actual_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            results.append({
                                'video_path': video_path,
                                'success': False,
                                'description': '',
                                'error_message': error_msg,
                                'processing_time': 0,
                                'timestamp': actual_timestamp
                            })
                            
                            # 发送video_completed信号，确保实时更新单个视频结果
                            self.video_completed.emit(
                                video_path, 
                                False, 
                                '', 
                                error_msg, 
                                0, 
                                actual_timestamp
                            )
                    else:
                        error_msg = f"API请求失败: {response.status_code} - {response.text}"
                        self.log_updated.emit(f"{video_name}: {error_msg}")
                        
                        # 检查是否是模型不匹配的错误（llm model received multi-modal messages）
                        if "llm model received multi-modal messages" in response.text:
                            self.log_updated.emit(f"错误原因: 当前模型不支持多模态输入，请确保使用 doubao-1.5-vision-pro-250328 模型进行视频描述")
                            self.log_updated.emit(f"系统已自动修正API配置，请重新运行视频描述功能")
                        
                        actual_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        results.append({
                            'video_path': video_path,
                            'success': False,
                            'description': '',
                            'error_message': error_msg,
                            'processing_time': 0,
                            'timestamp': actual_timestamp
                        })
                        
                        # 发送video_completed信号，确保实时更新单个视频结果
                        self.video_completed.emit(
                            video_path, 
                            False, 
                            '', 
                            error_msg, 
                            0, 
                            actual_timestamp
                        )
                
                except Exception as e:
                    error_msg = f"处理异常: {str(e)}"
                    self.log_updated.emit(f"{video_name}: {error_msg}")
                    actual_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    results.append({
                        'video_path': video_path,
                        'success': False,
                        'description': '',
                        'error_message': error_msg,
                        'processing_time': 0,
                        'timestamp': actual_timestamp
                    })
                    
                    # 发送video_completed信号，确保实时更新单个视频结果
                    self.video_completed.emit(
                        video_path, 
                        False, 
                        '', 
                        error_msg, 
                        0, 
                        actual_timestamp
                    )
                
                # 更新进度
                progress = int(((i + 1) / total_videos) * 100)
                self.progress_updated.emit(progress)
            
            # API处理完成
            self.progress_updated.emit(100)
            self.status_updated.emit("✅ API处理完成")
            self.log_updated.emit(f"✅ API处理完成，共处理 {len(results)} 个视频")
            return True, results
            
        except Exception as e:
            error_msg = f"API处理时发生异常: {str(e)}"
            self.log_updated.emit(error_msg)
            return False, []
    
    def _extract_video_frames(self, video_path):
        """提取视频帧用于API处理"""
        try:
            import cv2
            
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return []
            
            # 获取视频信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # 计算采样帧数
            num_frames = min(self.num_frames if self.num_frames > 0 else 16, total_frames)
            
            # 均匀采样帧
            frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
            
            frames = []
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if ret:
                    # 调整帧大小以减少数据传输量
                    height, width = frame.shape[:2]
                    if width > 512:
                        scale = 512 / width
                        new_width = 512
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    frames.append(frame)
            
            cap.release()
            return frames
            
        except Exception as e:
            self.log_updated.emit(f"提取视频帧时发生异常: {str(e)}")
            return []
    
    def _process_videos_batch(self):
        """批量处理所有视频"""
        try:
            # 使用传入的设备设置
            device_setting = self.device
            
            # 构建批量处理命令
            cmd = [
                'python',
                'src/algorithms/video_description/ShareGPT4Video/batch_run.py',
                '--model-path', self.model_path,
                '--query', self.description_requirement,
                '--device', device_setting,
                '--output-format', 'json'
            ]
            
            # 创建临时配置文件传递视频列表，避免Windows命令行长度限制
            import tempfile
            import json
            import os
            
            # 生成视频配置
            video_configs = []
            for video_path in self.videos:
                video_config = {
                    "video_path": video_path,
                    "query": self.description_requirement,
                    "num_frames": self.num_frames if self.num_frames > 0 else 16,
                    "do_sample": self.generation_mode != "deterministic",
                    "top_p": self.top_p if self.generation_mode in ["random", "hybrid"] else 0.9,
                    "temperature": 0.8 if self.generation_mode == "hybrid" else 1.0,
                    "num_beams": 2 if self.generation_mode == "hybrid" else 1,
                    "max_new_tokens": None  # 不限制输出长度
                }
                video_configs.append(video_config)
            
            # 创建临时配置文件
            config_fd, config_path = tempfile.mkstemp(suffix='.json', prefix='batch_config_')
            config_file_created = False
            try:
                with os.fdopen(config_fd, 'w', encoding='utf-8') as f:
                    json.dump(video_configs, f, ensure_ascii=False, indent=2)
                config_file_created = True
                
                self.log_updated.emit(f"创建临时配置文件: {config_path}")
                
                # 使用配置文件而不是直接传递视频列表
                cmd.extend(['--config-file', config_path])
            except Exception as e:
                self.log_updated.emit(f"创建临时配置文件失败: {str(e)}")
                return False, []
            
            # 根据描述长度要求更新提示词（但不限制max_new_tokens）
            # 注意：描述长度等级现在只用于API模型的动作过滤功能，本地模型不再使用长度建议
            # if self.description_length > 0:
            #     # 在提示词中添加长度建议，但不强制限制输出长度
            #     enhanced_query = f"{self.description_requirement} The total length of the description should be approximately {self.description_length} characters."
            #     cmd[cmd.index('--query') + 1] = enhanced_query
            #     self.log_updated.emit(f"已在提示词中添加长度建议: {self.description_length}字符（不限制实际输出长度）")
            # else:
            #     # 无限制生成模式
            #     self.log_updated.emit("设置为无限制生成模式，不限制输出长度")
            
            # 注意：不再设置max_new_tokens限制，让模型自由生成完整描述
            # 描述长度要求仅作为提示词中的建议，模型可以根据视频内容生成更完整的描述
            
            # 处理帧数设置
            if self.num_frames > 0:
                cmd.extend(['--num-frames', str(self.num_frames)])
                self.log_updated.emit(f"设置采样帧数: {self.num_frames}")
            else:
                cmd.extend(['--num-frames', '16'])  # 默认值
                self.log_updated.emit("使用默认采样帧数: 16")
            
            # 添加生成控制参数
            if self.generation_mode == "deterministic":
                cmd.extend(['--do-sample', 'False', '--num-beams', '1'])
                self.log_updated.emit("使用确定性生成模式 (do_sample=False, num_beams=1)")
            elif self.generation_mode == "random":
                cmd.extend(['--do-sample', 'True', '--top-p', str(self.top_p)])
                self.log_updated.emit(f"使用随机采样生成模式 (do_sample=True, top_p={self.top_p})")
            elif self.generation_mode == "hybrid":
                cmd.extend(['--do-sample', 'True', '--top-p', str(self.top_p), '--temperature', '0.8', '--num-beams', '2'])
                self.log_updated.emit(f"使用混合策略模式 (do_sample=True, top_p={self.top_p}, temperature=0.8, num_beams=2)")
            
            # 添加GPU优化参数
            if self.enable_gpu_optimization:
                cmd.extend(['--gpu-optimized'])
                cmd.extend(['--batch-size', str(self.gpu_batch_size)])
                cmd.extend(['--max-workers', str(self.gpu_max_workers)])
                self.log_updated.emit(f"启用GPU优化批处理 (批处理大小: {self.gpu_batch_size}, 预处理线程: {self.gpu_max_workers})")
            else:
                self.log_updated.emit("使用标准批处理模式")
            
            # 记录执行的命令
            cmd_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd)
            self.log_updated.emit(f"执行批量处理命令: {cmd_str}")
            
            # 设置工作目录为项目根目录
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.log_updated.emit(f"工作目录: {project_root}")
            
            # 执行批量处理命令
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                cwd=project_root
            )
            
            # 保存当前进程引用，以便停止时能够终止
            self.current_process = process
            
            output_lines = []
            self.log_updated.emit("开始读取批量处理输出...")
            
            # 实时读取输出
            while True:
                if not self.is_running:
                    try:
                        process.terminate()
                        # 等待进程终止，最多等待2秒
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            # 如果2秒后还没终止，强制杀死进程
                            process.kill()
                            process.wait()
                        self.log_updated.emit("用户取消批量处理，进程已终止")
                    except Exception as e:
                        self.log_updated.emit(f"终止进程时出错: {e}")
                    finally:
                        self.current_process = None
                    return False, []
                
                line = process.stdout.readline()
                
                if line is not None:
                    line = line.strip()
                    if line:
                        output_lines.append(line)
                        self.log_updated.emit(line)
                
                # 检查进程是否结束
                if process.poll() is not None:
                    # 读取剩余输出
                    remaining_output = process.stdout.read()
                    if remaining_output is not None and remaining_output:
                        remaining_lines = remaining_output.strip().split('\n')
                        for remaining_line in remaining_lines:
                            if remaining_line.strip():
                                output_lines.append(remaining_line.strip())
                                self.log_updated.emit(remaining_line.strip())
                    break
                
                time.sleep(0.01)
            
            self.log_updated.emit(f"批量处理命令执行完成，返回码: {process.returncode}")
            
        except Exception as e:
            self.log_updated.emit(f"批量处理发生异常: {str(e)}")
            return False, []
        finally:
            # 清理进程引用
            self.current_process = None
            
            # 清理临时配置文件
            try:
                if config_file_created and os.path.exists(config_path):
                    os.unlink(config_path)
                    self.log_updated.emit(f"清理临时配置文件: {config_path}")
            except Exception as e:
                self.log_updated.emit(f"清理临时配置文件失败: {str(e)}")
            
            # 检查进程返回码
            if process.returncode == 0:
                # 尝试从输出中提取JSON结果
                json_output = None
                json_start = -1
                json_end = -1
                
                # 改进的JSON查找逻辑：查找包含完整JSON结构的行
                self.log_updated.emit(f"开始解析输出，共 {len(output_lines)} 行")
                
                # 查找包含完整JSON的单行
                json_line = None
                json_line_index = -1
                
                for i, line in enumerate(output_lines):
                    line = line.strip()
                    if (line.startswith('{') and line.endswith('}') and 
                        'summary' in line and 'results' in line):
                        json_line = line
                        json_line_index = i
                        break
                
                if json_line:
                    self.log_updated.emit(f"找到JSON输出，在第 {json_line_index+1} 行")
                    
                    try:
                        import json
                        # 直接解析单行JSON
                        json_output = json.loads(json_line)
                        self.log_updated.emit("成功解析批量处理结果")
                        
                        # 提取结果列表
                        if 'results' in json_output:
                            results = json_output['results']
                            self.log_updated.emit(f"批量处理完成，共处理 {len(results)} 个视频")
                            return True, results
                        else:
                            self.log_updated.emit("JSON输出中未找到results字段")
                            return False, []
                            
                    except json.JSONDecodeError as e:
                        self.log_updated.emit(f"JSON解析失败: {str(e)}")
                        self.log_updated.emit(f"尝试解析的JSON前200字符: {json_line[:200]}")
                        return False, []
                
                # 如果没找到单行JSON，尝试多行JSON解析（向后兼容）
                json_start = -1
                json_end = -1
                
                # 从后往前查找完整的JSON块
                for i in range(len(output_lines) - 1, -1, -1):
                    line = output_lines[i].strip()
                    if line == '}' and json_end == -1:
                        json_end = i
                    elif line.startswith('{') and json_end != -1:
                        json_start = i
                        break
                
                # 如果没找到完整的JSON块，尝试查找包含"summary"和"results"的JSON
                if json_start == -1:
                    for i, line in enumerate(output_lines):
                        if (line.strip().startswith('{') and 
                            ('summary' in line or 'results' in line or 
                             any('summary' in output_lines[j] or 'results' in output_lines[j] 
                                 for j in range(i, min(i+10, len(output_lines)))))):
                            json_start = i
                            break
                
                if json_start != -1:
                    # 提取JSON部分
                    if json_end != -1:
                        json_lines = output_lines[json_start:json_end+1]
                    else:
                        json_lines = output_lines[json_start:]
                    
                    json_text = '\n'.join(json_lines)
                    self.log_updated.emit(f"找到多行JSON输出，从第 {json_start+1} 行开始，共 {len(json_lines)} 行")
                    
                    try:
                        import json
                        # 尝试直接解析完整JSON
                        json_output = json.loads(json_text)
                        self.log_updated.emit("成功解析批量处理结果")
                        
                        # 提取结果列表
                        if 'results' in json_output:
                            results = json_output['results']
                            self.log_updated.emit(f"批量处理完成，共处理 {len(results)} 个视频")
                            return True, results
                        else:
                            self.log_updated.emit("JSON输出中未找到results字段")
                            return False, []
                            
                    except json.JSONDecodeError as e:
                        self.log_updated.emit(f"JSON解析失败: {str(e)}")
                        self.log_updated.emit(f"尝试解析的JSON前200字符: {json_text[:200]}")
                        
                        # 尝试使用递归下降解析器解析截断的JSON
                        try:
                            decoder = json.JSONDecoder()
                            json_output, idx = decoder.raw_decode(json_text)
                            self.log_updated.emit("使用备用解析器成功解析JSON")
                            
                            if 'results' in json_output:
                                results = json_output['results']
                                self.log_updated.emit(f"批量处理完成，共处理 {len(results)} 个视频")
                                return True, results
                            else:
                                self.log_updated.emit("JSON输出中未找到results字段")
                                return False, []
                        except Exception as e2:
                            self.log_updated.emit(f"备用JSON解析也失败: {str(e2)}")
                            
                            # 尝试逐行查找JSON对象
                            self.log_updated.emit("尝试逐行查找JSON对象...")
                            for i, line in enumerate(output_lines):
                                if line.strip().startswith('{') and ('summary' in line or 'results' in line):
                                    try:
                                        single_line_json = json.loads(line.strip())
                                        if 'results' in single_line_json:
                                            results = single_line_json['results']
                                            self.log_updated.emit(f"在第 {i+1} 行找到有效JSON，共处理 {len(results)} 个视频")
                                            return True, results
                                    except:
                                        continue
                            
                            # 如果JSON解析完全失败，但批量处理返回码为0，说明处理成功
                            # 尝试为每个视频创建成功的结果记录
                            self.log_updated.emit("JSON解析失败，但批量处理成功完成，为所有视频创建成功记录")
                            fallback_results = []
                            for video_path in self.videos:
                                fallback_results.append({
                                    'video_path': video_path,
                                    'success': True,
                                    'description': '批量处理已完成，但无法获取详细描述内容（JSON解析失败）',
                                    'error_message': '',
                                    'processing_time': 0,
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                })
                            self.log_updated.emit(f"创建了 {len(fallback_results)} 个备用结果记录")
                            return True, fallback_results
                else:
                    self.log_updated.emit("未找到JSON输出")
                    # 输出最后几行用于调试
                    self.log_updated.emit("输出的最后10行:")
                    for i, line in enumerate(output_lines[-10:], len(output_lines)-9):
                        self.log_updated.emit(f"第{i}行: {line}")
                    return False, []
            else:
                error_msg = '\n'.join(output_lines) if output_lines else "未知错误"
                self.log_updated.emit(f"批量处理命令执行失败: {error_msg}")
                return False, []
    
    def _filter_action_description(self, description):
        """使用API过滤动作描述
        
        返回:
            dict: {
                'description': str,  # 过滤后的描述
                'filter_success': bool  # 是否成功应用了动作过滤
            }
        """
        try:
            # 获取动作过滤API配置
            filter_api_config = self._get_action_filter_api_config()
            if not filter_api_config or not filter_api_config.get('api_endpoint'):
                self.log_updated.emit("API配置不完整，跳过动作描述过滤")
                return {'description': description, 'filter_success': False}
            
            import requests
            import json
            
            # 构建API请求 - 使用配置的API密钥
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {filter_api_config["api_key"]}'
            }
            
            # 获取当前描述长度等级设置
            description_length_level = "中"  # 默认值
            try:
                if hasattr(self, 'center_description_length_combo'):
                    description_length_level = self.center_description_length_combo.currentText()
            except:
                pass
            
            # 根据长度等级设置相应的处理要求
            length_instruction = ""
            if description_length_level == "极短":
                length_instruction = "输出应该非常简洁，只保留最核心的动作描述，去除所有修饰词和细节。"
            elif description_length_level == "短":
                length_instruction = "输出应该简要，保留主要动作信息，适当简化描述。"
            elif description_length_level == "中":
                length_instruction = "输出应该保持适中长度，平衡详细度和简洁性。"
            elif description_length_level == "长":
                length_instruction = "输出应该详细，包含更多动作细节和描述。"
            elif description_length_level == "极长":
                length_instruction = "输出应该非常详细，全面分析所有动作，包含丰富的动作描述。"
            
            # 构建请求数据 - 先翻译再过滤动作描述，根据长度等级调整详细程度
            prompt = f"""请帮我处理这段话，严格按照以下要求：

1. 如果原文是英文，请先将其翻译为中文
2. 只保留与身体动作、姿态、运动相关的描述
3. 去除环境、背景、人物衣着、外貌、物品等与动作描述无关内容
4. 输出必须是完整的句子，包含明确的主语（如"男子"、"女子"、"运动员"、"舞者"等）
5. 保持自然的语言表达，按照{description_length_level}等级对动作描述进行缩写或者扩写，输出相应详细程度的内容
6. 不要添加任何原文中没有出现的动作的相关描述，除非原文中明确提到某个动作
7. 如果某句话包含动作和非动作内容，只需保留动作部分

当前描述长度等级：{description_length_level}

原文：
{description}

请直接输出过滤后的内容，不要添加任何解释或说明。"""
            
            data = {
                'model': filter_api_config['api_model'],
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 16384,
                'temperature': 0.1
            }
            
            self.log_updated.emit("正在调用API进行动作描述过滤...")
            
            # 发送API请求 - 使用配置的API端点，增加超时时间到120秒
            response = requests.post(
                filter_api_config['api_endpoint'],
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    filtered_description = result['choices'][0]['message']['content'].strip()
                    self.log_updated.emit("动作描述过滤完成")
                    return {'description': filtered_description, 'filter_success': True}
                else:
                    self.log_updated.emit("API响应格式异常，使用原始描述")
                    return {'description': description, 'filter_success': False}
            else:
                self.log_updated.emit(f"API调用失败 (状态码: {response.status_code})，使用原始描述")
                return {'description': description, 'filter_success': False}
                
        except Exception as e:
            self.log_updated.emit(f"动作描述过滤失败: {str(e)}，使用原始描述")
            return {'description': description, 'filter_success': False}
    
    def _mark_action_filter_applied(self, video_path):
        """标记视频已成功应用动作过滤"""
        try:
            video_name = os.path.basename(video_path)
            video_base_name = os.path.splitext(video_name)[0]
            
            description_dir = os.path.join(video_base_name, 'description')
            if not os.path.exists(description_dir):
                os.makedirs(description_dir, exist_ok=True)
            
            # 创建或更新标记文件
            marker_file = os.path.join(description_dir, '.action_filter_applied')
            
            # 读取现有内容（如果文件存在）
            existing_videos = set()
            if os.path.exists(marker_file):
                try:
                    with open(marker_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 解析已有的视频名称
                    for line in content.split('\n'):
                        if line.strip() and 'Video:' in line:
                            existing_video = line.split('Video:')[1].split(',')[0].strip()
                            existing_videos.add(existing_video)
                except:
                    pass
            
            # 检查视频是否已在标记文件中
            if video_name not in existing_videos:
                # 添加新的视频记录
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                new_entry = f"Video: {video_name}, Action filter applied at: {timestamp}\n"
                
                with open(marker_file, 'a', encoding='utf-8') as f:
                    f.write(new_entry)
                    
                self._log_message(f"已将视频 {video_name} 添加到标记文件")
            else:
                self._log_message(f"视频 {video_name} 已在标记文件中，跳过添加")
                
        except Exception as e:
            self._log_message(f"创建标记文件失败: {str(e)}")
    
    def _check_action_filter_applied(self, video_path):
        """检查视频是否已成功应用动作过滤"""
        try:
            video_name = os.path.basename(video_path)
            video_base_name = os.path.splitext(video_name)[0]
            video_dir = os.path.dirname(video_path)
            
            # 优先检查标记文件
            marker_file = os.path.join(video_dir, video_base_name, 'description', '.action_filter_applied')
            if os.path.exists(marker_file):
                try:
                    with open(marker_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 检查标记文件中是否包含该视频名称
                    if video_name in content:
                        return True
                except:
                    pass
            
            # 如果标记文件不存在或没有记录该视频，则检查结果文件
            user_result_file = self._get_user_result_file_path(video_path)
            if user_result_file.exists():
                try:
                    with open(user_result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    # 如果文件中明确标记已过滤，则返回True
                    if result.get('action_filter_applied', False):
                        return True
                except:
                    pass
            
            return False
        except:
            return False
    
    def check_action_filter_applied(self, video_path):
        """检查视频是否已成功应用动作过滤（公共方法）"""
        return self._check_action_filter_applied(video_path)
    
    def _get_video_duration(self, video_path):
        """获取视频时长"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            return f"{duration:.2f}秒"
        except:
            return "未知"
    
    def _get_auto_frames(self, video_path):
        """根据视频时长自动选择帧数"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            
            # 根据视频时长自动选择帧数
            if duration <= 10:  # 短视频（≤10秒）
                return 16  # 使用较少帧数
            elif duration <= 30:  # 中等视频（10-30秒）
                return 20  # 中等帧数
            elif duration <= 60:  # 较长视频（30-60秒）
                return 25  # 较多帧数
            else:  # 长视频（>60秒）
                return 32  # 最多帧数
                
        except Exception as e:
            # 如果获取时长失败，返回默认值
            self.log_updated.emit(f"获取视频时长失败，使用默认帧数16: {str(e)}")
            return 16
    
    def _get_action_filter_api_config(self):
        """获取动作过滤API配置"""
        try:
            # 使用绝对导入避免相对导入问题
            import sys
            import os
            
            # 添加项目根目录到路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            from src.core.user_config_manager import get_user_config_manager
            config_manager = get_user_config_manager()
            
            # 获取动作过滤API配置
            action_filter_config = config_manager.get_api_config('action_filter')
            
            # 如果用户配置了完整的API信息，则使用用户配置
            if (action_filter_config.get('endpoint') and 
                action_filter_config.get('key') and 
                action_filter_config.get('model')):
                return {
                    'api_endpoint': action_filter_config['endpoint'],
                    'api_key': action_filter_config['key'],
                    'api_model': action_filter_config['model']
                }
            else:
                # 否则使用内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                    'api_model': 'doubao-seed-1-6-250615'
                }
        except Exception as e:
            self.log_updated.emit(f"使用UserConfigManager加载配置失败，回退到直接文件读取: {e}")
            
            # 回退方案：直接读取配置文件
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                config_file = os.path.join(project_root, 'cache_config.txt')
                
                if os.path.exists(config_file):
                    # cache_config.txt是简单的key=value格式，不是INI格式
                    config_dict = {}
                    with open(config_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                config_dict[key.strip()] = value.strip()
                    
                    # 检查是否有action filter相关配置
                    if ('action_filter_api_endpoint' in config_dict and 
                        'action_filter_api_key' in config_dict and 
                        'action_filter_api_model' in config_dict):
                        return {
                            'api_endpoint': config_dict['action_filter_api_endpoint'],
                            'api_key': config_dict['action_filter_api_key'],
                            'api_model': config_dict['action_filter_api_model']
                        }
                
                # 如果配置文件读取失败或配置不完整，返回内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                    'api_model': 'doubao-seed-1-6-250615'
                }
                
            except Exception as fallback_error:
                self.log_updated.emit(f"配置文件读取也失败，使用默认配置: {fallback_error}")
                # 最终回退：返回内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                    'api_model': 'doubao-seed-1-6-250615'
                }

    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()

class VideoDescriptionWidget(QWidget):
    """视频描述界面组件"""
    
    status_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(int)
    
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.current_videos = []
        self.video_durations = {}  # 缓存各视频的时长（秒），用于排序/分桶
        self.video_results = {}  # 存储视频处理结果
        self.processing_thread = None
        self.is_all_selected = False  # 全选状态标记
        
        # 初始化use_action_filter属性，避免AttributeError
        self.use_action_filter = False
        
        # 日志文件管理
        self.log_file_path = None
        self.log_file_handle = None
        self.log_monitoring_enabled = False
        
        # OpenCV视频播放相关
        self.video_capture = None
        self.current_video_path = None
        self.total_frames = 0
        self.fps = 30
        self.current_frame = 0
        self.is_playing = False
        self.playback_speed = 1.0
        
        # 播放控制状态
        self.is_slider_pressed = False
        self.is_muted = False
        self.previous_volume = 50
        self._last_click_time = 0  # 防抖机制用的时间戳
        
        # 动态帧率调整相关变量
        self.frame_rate_monitor = FrameRateMonitor(window_size=30)
        self.pid_controller = AdaptivePIDController(kp=0.1, ki=0.01, kd=0.05)
        self.adaptive_interval = 33  # 初始间隔（毫秒）
        self.base_interval = 33  # 基础间隔
        self.enable_adaptive_playback = True  # 是否启用自适应播放
        self.adjustment_counter = 0  # 调整计数器
        
        # 播放定时器
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self._update_frame)
        
        # 自适应调整定时器（每秒调整一次）
        self.adaptive_timer = QTimer()
        self.adaptive_timer.timeout.connect(self._adaptive_playback_control)
        self.adaptive_timer.setInterval(1000)  # 1秒间隔
        
        self._init_ui()
        self._load_cache_config()
        self._connect_signals()
        
        # 确保模型选择与配置文件同步
        self._sync_model_selection_with_config()
        
        # 根据配置更新UI状态
        self._update_ui_based_on_algorithm_type()
        
        # 根据当前选择的模型更新UI状态
        if hasattr(self, 'model_selection_combo'):
            current_model = self.model_selection_combo.currentText()
            self._update_model_ui_state(current_model)
        
        # 初始化自适应播放控制状态
        self._toggle_adaptive_playback(Qt.Checked if self.enable_adaptive_playback else Qt.Unchecked)
    
    def _init_ui(self):
        """初始化用户界面"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建三个主要区域
        left_panel = self._create_left_panel()  # 左侧面板
        center_panel = self._create_center_panel()  # 中间面板
        right_panel = self._create_right_panel()  # 右侧面板
        
        # 创建主分割器（水平分割）
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)  # 防止面板被完全折叠
        
        # 添加面板到分割器
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(center_panel)
        self.main_splitter.addWidget(right_panel)
        
        # 设置初始比例和最小宽度
        self._setup_responsive_layout()
        
        # 添加分割器到主布局
        main_layout.addWidget(self.main_splitter)
        
        # 连接窗口大小变化事件
        self._connect_resize_handler()
        
        # 初始化时调整视频列表高度
        QTimer.singleShot(100, self._adjust_video_list_height)  # 延迟调用确保窗口已显示
    
    def _create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)  # 内容顶部居中对齐
        
        # 文件上传区域
        upload_group = QGroupBox("视频上传")
        upload_layout = QVBoxLayout(upload_group)
        upload_layout.setContentsMargins(8, 8, 8, 12)  # 设置合适的内边距，底部稍大
        upload_layout.setAlignment(Qt.AlignCenter)  # 上传区域内容居中
        
        # 上传按钮
        upload_buttons_layout = QHBoxLayout()
        upload_buttons_layout.setAlignment(Qt.AlignCenter)  # 按钮居中对齐
        
        self.upload_file_btn = QPushButton("上传视频文件")
        self.upload_file_btn.setMinimumWidth(140)  # 增加最小宽度使按钮更明显
        self.upload_file_btn.setMinimumHeight(36)  # 增加高度使按钮更明显
        self.upload_file_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.upload_file_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
                border: 2px solid #4CAF50;
                border-radius: 6px;
                background-color: #f8f9fa;
                color: #2e7d32;
            }
            QPushButton:hover {
                background-color: #e8f5e8;
                border-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #c8e6c9;
            }
        """)
        self.upload_file_btn.clicked.connect(self._upload_video_files)
        upload_buttons_layout.addWidget(self.upload_file_btn)
        
        self.upload_folder_btn = QPushButton("上传文件夹")
        self.upload_folder_btn.setMinimumWidth(140)  # 增加最小宽度使按钮更明显
        self.upload_folder_btn.setMinimumHeight(36)  # 增加高度使按钮更明显
        self.upload_folder_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.upload_folder_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
                border: 2px solid #2196F3;
                border-radius: 6px;
                background-color: #f8f9fa;
                color: #1565c0;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
                border-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #bbdefb;
            }
        """)
        self.upload_folder_btn.clicked.connect(self._upload_video_folder)
        upload_buttons_layout.addWidget(self.upload_folder_btn)
        
        upload_layout.addLayout(upload_buttons_layout)
        
        # 视频列表控制区域
        list_control_layout = QHBoxLayout()
        list_control_layout.setAlignment(Qt.AlignCenter)  # 控制按钮居中对齐
        list_control_layout.addWidget(QLabel("视频列表:"))
        
        # 添加全选/取消全选切换按钮
        self.select_toggle_btn = QPushButton("全选")
        self.select_toggle_btn.clicked.connect(self._toggle_select_all)
        self.select_toggle_btn.setMaximumWidth(70)
        self.is_all_selected = False  # 跟踪当前选择状态
        list_control_layout.addWidget(self.select_toggle_btn)
        
        # 添加删除选中视频按钮
        self.delete_selected_btn = QPushButton("删除选中")
        self.delete_selected_btn.clicked.connect(self._delete_selected_videos)
        self.delete_selected_btn.setMaximumWidth(70)
        self.delete_selected_btn.setStyleSheet("QPushButton { color: #d32f2f; }")
        list_control_layout.addWidget(self.delete_selected_btn)
        
        # 选择状态显示（移动到删除按钮后方）
        self.selection_status_label = QLabel("已选择：0/0")
        self.selection_status_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 11px;
                margin-left: 5px;
            }
        """)
        self.selection_status_label.setAlignment(Qt.AlignVCenter)  # 垂直居中对齐
        list_control_layout.addWidget(self.selection_status_label)
        
        list_control_layout.addStretch()
        upload_layout.addLayout(list_control_layout)
        
        # 视频列表（支持复选框）
        self.video_list = QListWidget()
        self.video_list.setMinimumHeight(120)  # 设置最小高度
        self.video_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # 使用Preferred策略便于动态调整
        self.video_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #d0d0d0; /* 加粗边框确保下边框清晰显示 */
                border-radius: 6px;
                background-color: #ffffff;
                margin: 3px 3px 8px 3px; /* 增加底部外边距确保下边框在组边框内 */
                padding: 6px 4px 6px 4px; /* 调整内边距，确保内容不被遮挡 */
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f0f0f0;
                margin: 1px 0px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border: 1px solid #2196f3;
                border-radius: 3px;
                color: #000000; /* 确保选中时文字为黑色，保持可读性 */
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.video_list.itemClicked.connect(self._on_video_selected)
        self.video_list.itemChanged.connect(self._on_video_check_changed)
        upload_layout.addWidget(self.video_list)
        upload_layout.setStretch(upload_layout.indexOf(self.video_list), 1)
        
        # 保存upload_group引用以便后续调整
        self.upload_group = upload_group
        layout.addWidget(upload_group)
        
        # 在视频上传组和描述要求组之间添加额外间距
        layout.addSpacing(10)
        
        # 描述要求区域
        desc_group = QGroupBox("描述要求")
        desc_layout = QVBoxLayout(desc_group)
        desc_layout.setContentsMargins(8, 8, 8, 8)
        desc_layout.setAlignment(Qt.AlignCenter)  # 描述区域内容居中
        
        self.description_text = QTextEdit()
        self.description_text.setMinimumHeight(100)
        # self.description_text.setMaximumHeight(150)
        # 设置默认描述要求
        default_desc = "Begin by providing a general overview of the person's current action (e.g., walking, sitting, interacting) visible in the video footage. Then proceed with a detailed analysis focusing specifically on the physical movements and body positioning within the video frame. For the upper body, describe the position and movement patterns of the arms, hands, shoulders and torso. For the lower body, detail the positioning and motion of the legs, feet and overall balance dynamics. The description must remain strictly focused on observable physical actions, deliberately excluding any mention of facial expressions, clothing details or environmental elements outside the video frame boundaries."
        self.description_text.setPlainText(default_desc)
        self.description_text.setStyleSheet("color: #888888;")  # 淡灰色
        desc_layout.addWidget(self.description_text)
        
        layout.addWidget(desc_group)
        
        # 功能选项区域
        options_group = QGroupBox("功能选项")
        options_layout = QVBoxLayout(options_group)
        options_layout.setContentsMargins(8, 8, 8, 8)
        options_layout.setAlignment(Qt.AlignCenter)  # 功能选项区域内容居中
        # 提高分组最小高度以容纳更大的行高，避免文字裁切
        options_group.setMinimumHeight(260)
        
        # 算法类型从配置中读取，不再显示选择控件
        
        # 功能选项 - 使用网格布局实现6行2列的精确对齐
        options_grid = QGridLayout()
        options_grid.setColumnStretch(0, 1)  # 第一列占50%
        options_grid.setColumnStretch(1, 1)  # 第二列占50%
        options_grid.setHorizontalSpacing(20)  # 列间距
        options_grid.setVerticalSpacing(16)   # 行间距（进一步增大，防止裁切）
        # 为所有可见行设置最小行高，避免中文文本被裁切
        for r in range(0, 9):
            options_grid.setRowMinimumHeight(r, 34)
        
        # 第一行：动作描述 和 自适应播放控制
        self.action_filter_checkbox = QCheckBox("只保留动作描述")
        self.action_filter_checkbox.setToolTip("过滤掉场景、物体等描述，专注于人物动作和行为分析")
        self.action_filter_checkbox.setMinimumHeight(28)
        self.action_filter_checkbox.setStyleSheet("QCheckBox{font-size:13px;}")
        self.action_filter_checkbox.stateChanged.connect(self._sync_action_filter_to_center)
        options_grid.addWidget(self.action_filter_checkbox, 0, 0, Qt.AlignLeft)
        
        self.adaptive_playback_checkbox = QCheckBox("自适应播放控制")
        self.adaptive_playback_checkbox.setToolTip("使用PID控制器动态调整播放帧率，提供更平滑的播放体验")
        self.adaptive_playback_checkbox.setChecked(True)  # 默认启用
        self.adaptive_playback_checkbox.setMinimumHeight(28)
        self.adaptive_playback_checkbox.setStyleSheet("QCheckBox{font-size:13px;}")
        self.adaptive_playback_checkbox.stateChanged.connect(self._toggle_adaptive_playback)
        options_grid.addWidget(self.adaptive_playback_checkbox, 0, 1, Qt.AlignLeft)
        
        # 第二行：选择模型及其选项框
        model_widget = QWidget()
        model_layout = QHBoxLayout(model_widget)
        model_layout.setContentsMargins(0, 0, 0, 0)
        
        model_label = QLabel("选择模型:")
        model_label.setMinimumHeight(26)
        model_label.setStyleSheet("QLabel{font-size:13px;}")
        model_layout.addWidget(model_label)
        
        self.model_selection_combo = QComboBox()
        self.model_selection_combo.setMinimumHeight(26)
        self.model_selection_combo.addItems([
            "ShareVideoGPT4（本地模型）",
            "火山大模型①", 
            "添加API模型"
        ])
        self.model_selection_combo.setCurrentText("ShareVideoGPT4（本地模型）")  # 默认选择本地模型
        self.model_selection_combo.setToolTip("选择用于视频描述的AI模型")
        self.model_selection_combo.currentTextChanged.connect(self._on_model_selection_changed)
        model_layout.addWidget(self.model_selection_combo)
        model_layout.addStretch()
        # 该行较高，明确设置容器高度，避免被压缩
        model_widget.setMinimumHeight(34)
        
        options_grid.addWidget(model_widget, 1, 0, 1, 2)  # 跨两列
        
        # 加载已保存的自定义API模型
        self._load_custom_models()
        
        # 第三行：计算设备（及其选项框）和采样参数（及其选项框）
        # 计算设备选择（第三行第一列）
        device_widget = QWidget()
        device_layout = QHBoxLayout(device_widget)
        device_layout.setContentsMargins(0, 0, 0, 0)
        
        device_label = QLabel("计算设备:")
        device_label.setMinimumHeight(26)
        device_label.setStyleSheet("QLabel{font-size:13px;}")
        device_layout.addWidget(device_label)
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumHeight(26)
        self.device_combo.addItems(["Auto", "CUDA", "CPU"])
        self.device_combo.setCurrentText("CUDA")  # 默认设置为CUDA
        self.device_combo.setToolTip(
            "选择视频描述处理的计算设备:\n"
            "• Auto: 自动检测最佳设备（推荐）\n"
            "• CUDA: 强制使用GPU加速\n"
            "• CPU: 强制使用CPU处理"
        )
        self.device_combo.currentTextChanged.connect(self._on_device_changed)
        device_layout.addWidget(self.device_combo)
        device_layout.addStretch()
        device_widget.setMinimumHeight(34)
        options_grid.addWidget(device_widget, 2, 0)
        
        # 采样参数（第三行第二列）
        sampling_widget = QWidget()
        sampling_layout = QHBoxLayout(sampling_widget)
        sampling_layout.setContentsMargins(0, 0, 0, 0)
        
        top_p_label = QLabel("采样参数:")
        top_p_label.setMinimumHeight(26)
        top_p_label.setStyleSheet("QLabel{font-size:13px;}")
        sampling_layout.addWidget(top_p_label)
        
        self.top_p_spinbox = QDoubleSpinBox()
        self.top_p_spinbox.setMinimumHeight(26)
        self.top_p_spinbox.setRange(0.8, 1.0)
        self.top_p_spinbox.setSingleStep(0.01)
        self.top_p_spinbox.setDecimals(2)
        self.top_p_spinbox.setValue(0.9)  # 默认值0.9
        self.top_p_spinbox.setToolTip(
            "控制生成文本的多样性和详细程度:\n"
            "• 0.8-0.85: 生成简洁、聚焦的描述\n"
            "• 0.9: 平衡的描述详细程度（推荐）\n"
            "• 0.95-1.0: 生成更详细、更丰富的描述"
        )
        sampling_layout.addWidget(self.top_p_spinbox)
        sampling_layout.addStretch()
        sampling_widget.setMinimumHeight(34)
        options_grid.addWidget(sampling_widget, 2, 1)
        
        # API配置区域（初始隐藏）
        self.api_config_group = QGroupBox("API配置")
        api_config_layout = QVBoxLayout(self.api_config_group)
        
        # API端点
        api_endpoint_layout = QHBoxLayout()
        api_endpoint_label = QLabel("API端点:")
        api_endpoint_layout.addWidget(api_endpoint_label)
        
        self.api_endpoint_edit = QLineEdit()
        self.api_endpoint_edit.setText("https://ark.cn-beijing.volces.com/api/v3/chat/completions")
        self.api_endpoint_edit.setPlaceholderText("例如: https://api.openai.com/v1/chat/completions")
        self.api_endpoint_edit.setToolTip("输入API服务的完整端点URL")
        self.api_endpoint_edit.textChanged.connect(self._save_api_config)
        api_endpoint_layout.addWidget(self.api_endpoint_edit)
        api_config_layout.addLayout(api_endpoint_layout)
        
        # API密钥
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API密钥:")
        api_key_layout.addWidget(api_key_label)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setText("fa1f2df2-73f8-44b1-99a0-09834047ab51")  # 视频描述API密钥
        self.api_key_edit.setPlaceholderText("输入您的API密钥")
        self.api_key_edit.setToolTip("输入API服务的认证密钥")
        self.api_key_edit.textChanged.connect(self._save_api_config)
        api_key_layout.addWidget(self.api_key_edit)
        
        # 显示/隐藏密钥按钮
        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.setMaximumWidth(50)
        self.show_key_btn.clicked.connect(self._toggle_api_key_visibility)
        api_key_layout.addWidget(self.show_key_btn)
        api_config_layout.addLayout(api_key_layout)
        
        # API模型
        api_model_layout = QHBoxLayout()
        api_model_label = QLabel("API模型:")
        api_model_layout.addWidget(api_model_label)
        
        self.api_model_combo = QComboBox()
        self.api_model_combo.setEditable(True)
        self.api_model_combo.addItems(["doubao-1.5-vision-pro-250328", "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "claude-3-sonnet", "claude-3-opus"])
        self.api_model_combo.setCurrentText("doubao-1.5-vision-pro-250328")
        self.api_model_combo.setToolTip("选择或输入要使用的API模型名称")
        self.api_model_combo.currentTextChanged.connect(self._save_api_config)
        api_model_layout.addWidget(self.api_model_combo)
        api_model_layout.addStretch()
        api_config_layout.addLayout(api_model_layout)
        
        # 初始隐藏API配置
        self.api_config_group.setVisible(False)
        options_layout.addWidget(self.api_config_group)
        
        # 第四行：启用多线程（及其选项框）和GPU设备（及其选项框）
        # 多线程选项（第四行第一列）
        multithread_widget = QWidget()
        multithread_layout = QHBoxLayout(multithread_widget)
        multithread_layout.setContentsMargins(0, 0, 0, 0)
        
        self.multithread_checkbox = QCheckBox("多线程：")
        self.multithread_checkbox.setToolTip(
            "多线程处理可以同时处理多个视频，提高处理效率\n"
            "注意：仅在使用CUDA或Auto设备时可用，CPU模式不支持多线程"
        )
        self.multithread_checkbox.setMinimumHeight(28)
        self.multithread_checkbox.setStyleSheet("QCheckBox{font-size:13px;}")
        multithread_layout.addWidget(self.multithread_checkbox)
        
        self.thread_count_spinbox = QSpinBox()
        self.thread_count_spinbox.setMinimumHeight(26)
        self.thread_count_spinbox.setMinimum(1)
        self.thread_count_spinbox.setMaximum(8)
        self.thread_count_spinbox.setValue(2)  # 默认2个线程
        self.thread_count_spinbox.setToolTip(
            "设置同时处理的线程数量\n"
            "建议根据GPU显存大小选择：\n"
            "• 8GB以下显存：1-2个线程\n"
            "• 8-16GB显存：2-4个线程\n"
            "• 16GB以上显存：4-8个线程"
        )
        multithread_layout.addWidget(self.thread_count_spinbox)
        multithread_layout.addStretch()
        multithread_widget.setMinimumHeight(34)
        options_grid.addWidget(multithread_widget, 3, 0)
        
        # GPU设备选择（第四行第二列）
        gpu_device_widget = QWidget()
        gpu_device_layout = QHBoxLayout(gpu_device_widget)
        gpu_device_layout.setContentsMargins(0, 0, 0, 0)
        
        gpu_device_label = QLabel("GPU设备:")
        gpu_device_label.setMinimumHeight(26)
        gpu_device_label.setStyleSheet("QLabel{font-size:13px;}")
        gpu_device_layout.addWidget(gpu_device_label)
        
        self.gpu_device_combo = QComboBox()
        self.gpu_device_combo.setMinimumHeight(26)
        # 初始化GPU设备列表
        self._initialize_gpu_devices()
        self.gpu_device_combo.setCurrentText("自动检测")
        self.gpu_device_combo.setToolTip(
            "选择要使用的GPU设备\n"
            "• 自动检测：系统自动选择最佳设备\n"
            "• cuda:0/cuda:1：指定特定GPU\n"
            "• cpu：强制使用CPU处理"
        )
        gpu_device_layout.addWidget(self.gpu_device_combo)
        gpu_device_layout.addStretch()
        gpu_device_widget.setMinimumHeight(34)
        options_grid.addWidget(gpu_device_widget, 3, 1)
        
        # 第五行：启用智能加速和启用快速预加载
        self.smart_loading_checkbox = QCheckBox("智能加速")
        self.smart_loading_checkbox.setChecked(True)  # 默认启用
        self.smart_loading_checkbox.setToolTip(
            "智能加载可以根据系统资源动态调整加载策略\n"
            "自动优化内存使用和加载速度，提升整体性能"
        )
        self.smart_loading_checkbox.setMinimumHeight(28)
        self.smart_loading_checkbox.setStyleSheet("QCheckBox{font-size:13px;}")
        options_grid.addWidget(self.smart_loading_checkbox, 4, 0)
        
        self.fast_preload_checkbox = QCheckBox("快速预加载")
        self.fast_preload_checkbox.setChecked(True)  # 默认启用
        self.fast_preload_checkbox.setToolTip(
            "快速预加载可以提前加载下一批数据\n"
            "减少等待时间，提升处理流畅度"
        )
        self.fast_preload_checkbox.setMinimumHeight(28)
        self.fast_preload_checkbox.setStyleSheet("QCheckBox{font-size:13px;}")
        options_grid.addWidget(self.fast_preload_checkbox, 4, 1)
        
        # 第六行：启用GPU优化及其选项框（单独一行）
        gpu_optimization_widget = QWidget()
        gpu_optimization_layout = QHBoxLayout(gpu_optimization_widget)
        gpu_optimization_layout.setContentsMargins(0, 0, 0, 0)
        
        self.gpu_optimization_checkbox = QCheckBox("GPU优化")
        self.gpu_optimization_checkbox.setToolTip(
            "启用GPU优化批处理可以显著提升大量视频的处理性能\n"
            "通过批量推理和并行预处理减少GPU内存碎片和模型加载开销\n"
            "注意：仅在使用CUDA设备且处理多个视频时推荐启用"
        )
        self.gpu_optimization_checkbox.setMinimumHeight(28)
        self.gpu_optimization_checkbox.setStyleSheet("QCheckBox{font-size:13px;}")
        gpu_optimization_layout.addWidget(self.gpu_optimization_checkbox)
        
        # GPU批处理大小
        batch_size_label = QLabel("批处理大小:")
        batch_size_label.setMinimumHeight(26)
        batch_size_label.setStyleSheet("QLabel{font-size:13px;}")
        gpu_optimization_layout.addWidget(batch_size_label)
        
        self.gpu_batch_size_spinbox = QSpinBox()
        self.gpu_batch_size_spinbox.setMinimumHeight(26)
        self.gpu_batch_size_spinbox.setMinimum(1)
        self.gpu_batch_size_spinbox.setMaximum(8)
        self.gpu_batch_size_spinbox.setValue(2)  # 默认2个视频一批
        self.gpu_batch_size_spinbox.setToolTip(
            "设置同时进行GPU推理的视频数量\n"
            "建议根据GPU显存大小选择：\n"
            "• 8GB以下显存：1-2个视频\n"
            "• 8-16GB显存：2-4个视频\n"
            "• 16GB以上显存：4-8个视频"
        )
        gpu_optimization_layout.addWidget(self.gpu_batch_size_spinbox)
        
        # 预处理线程数
        workers_label = QLabel("预处理线程:")
        workers_label.setMinimumHeight(26)
        workers_label.setStyleSheet("QLabel{font-size:13px;}")
        gpu_optimization_layout.addWidget(workers_label)
        
        self.gpu_max_workers_spinbox = QSpinBox()
        self.gpu_max_workers_spinbox.setMinimumHeight(26)
        self.gpu_max_workers_spinbox.setMinimum(1)
        self.gpu_max_workers_spinbox.setMaximum(16)
        self.gpu_max_workers_spinbox.setValue(4)  # 默认4个预处理线程
        self.gpu_max_workers_spinbox.setToolTip(
            "设置视频预处理的并行线程数\n"
            "用于并行加载和预处理视频帧\n"
            "建议设置为CPU核心数的1-2倍"
        )
        gpu_optimization_layout.addWidget(self.gpu_max_workers_spinbox)
        gpu_optimization_layout.addStretch()
        
        gpu_optimization_widget.setMinimumHeight(36)
        options_grid.addWidget(gpu_optimization_widget, 5, 0, 1, 2)  # 跨两列
        
        # 第七行：视频处理排序（仅影响处理顺序，不影响显示顺序）
        video_sort_widget = QWidget()
        video_sort_layout = QHBoxLayout(video_sort_widget)
        video_sort_layout.setContentsMargins(0, 0, 0, 0)
        
        video_sort_label = QLabel("处理排序:")
        video_sort_label.setMinimumHeight(26)
        video_sort_label.setStyleSheet("QLabel{font-size:13px;}")
        video_sort_layout.addWidget(video_sort_label)
        
        self.duration_sort_mode_combo = QComboBox()
        self.duration_sort_mode_combo.addItems(["默认顺序", "按时长升序", "按时长降序", "按时长分桶"])
        self.duration_sort_mode_combo.setToolTip("选择视频处理的顺序方式（仅影响处理顺序，不改变列表显示）:\n• 默认顺序: 按添加顺序处理\n• 按时长升序: 先处理短视频\n• 按时长降序: 先处理长视频\n• 按时长分桶: 按时长区间分组处理")
        self.duration_sort_mode_combo.setMinimumHeight(26)
        video_sort_layout.addWidget(self.duration_sort_mode_combo)
        video_sort_layout.addStretch()
        
        video_sort_widget.setMinimumHeight(34)
        options_grid.addWidget(video_sort_widget, 6, 0, 1, 2)  # 跨两列
        
        # 将网格布局添加到选项布局中
        options_layout.addLayout(options_grid)
        
        # 初始化多线程和GPU优化选项状态
        self._on_device_changed()
        
        layout.addWidget(options_group)
        
        # 参数说明已迁移至中间面板的无标题滚动区域，左侧不再显示单独的“参数说明”标题和内容
        
        # 调整左侧分组的伸缩比例，确保视频列表获得更多空间
        layout.setStretch(layout.indexOf(upload_group), 5)
        layout.setStretch(layout.indexOf(desc_group), 1)
        layout.setStretch(layout.indexOf(options_group), 2)
        
        layout.addStretch()
        return panel
    
    def _create_center_panel(self):
        """创建中间面板（视频播放）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)  # 中间面板内容居中对齐
        
        # 视频播放区域
        video_group = QGroupBox("视频播放")
        video_layout = QVBoxLayout(video_group)
        video_layout.setSpacing(4)
        video_layout.setContentsMargins(12, 12, 12, 12)
        video_layout.setAlignment(Qt.AlignCenter)  # 视频播放区域内容居中
        
        # 视频显示标签
        self.video_label = QLabel()
        self.video_label.setMinimumHeight(230)
        self.video_label.setMaximumHeight(300)
        # 取消固定的最大宽高，允许随容器自适应
        # self.video_label.setMaximumHeight(400)
        # self.video_label.setMinimumWidth(400)
        # self.video_label.setMaximumWidth(600)
        self.video_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("请选择视频文件")
        self.video_label.setScaledContents(False)  # 保持比例缩放，由代码控制
        # 使用可扩展策略，随父布局伸缩
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        video_layout.addWidget(self.video_label)
        video_layout.addSpacing(4)
        
        # 进度条控制行
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 4, 0, 0)
        controls_layout.setSpacing(6)
        controls_layout.setAlignment(Qt.AlignCenter)  # 进度条控制居中
        
        # 进度条
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setToolTip("拖动调整播放位置")
        self.position_slider.setMinimumHeight(16)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #ddd;
                height: 4px;
                background: #f8f9fa;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #007bff;
                border: 1px solid #007bff;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #0056b3;
                border-color: #0056b3;
            }
            QSlider::sub-page:horizontal {
                background: #007bff;
                border-radius: 2px;
            }
        """)
        self.position_slider.sliderMoved.connect(self._set_position)
        self.position_slider.sliderPressed.connect(self._slider_pressed)
        self.position_slider.sliderReleased.connect(self._slider_released)
        controls_layout.addWidget(self.position_slider)
        
        # 时间显示
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(100)
        controls_layout.addWidget(self.time_label)
        
        # 将进度条和时间显示合并到下方播放控制行中
        
        # 播放控制按钮行（在视频播放窗口下方）
        playback_controls_layout = QHBoxLayout()
        playback_controls_layout.setSpacing(4)  # 紧凑按钮间距
        playback_controls_layout.setContentsMargins(0, 2, 0, 0)
        playback_controls_layout.setAlignment(Qt.AlignCenter)  # 播放控制按钮居中
        
        # 取消居中拉伸，紧凑排列
        
        # 后退按钮
        self.backward_btn = QPushButton("⏪")
        self.backward_btn.setToolTip("后退10秒")
        self.backward_btn.setMinimumSize(32, 24)
        self.backward_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        self.backward_btn.clicked.connect(self._backward_10s)
        playback_controls_layout.addWidget(self.backward_btn)
        
        # 播放/暂停按钮
        self.play_btn = QPushButton("▶")
        self.play_btn.setToolTip("播放/暂停")
        self.play_btn.setMinimumSize(36, 24)
        self.play_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #007bff;
                border-radius: 4px;
                background-color: #007bff;
                color: white;
            }
            QPushButton:hover {
                background-color: #0056b3;
                border-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        self.play_btn.clicked.connect(self._toggle_playback)
        playback_controls_layout.addWidget(self.play_btn)
        
        # 前进按钮
        self.forward_btn = QPushButton("⏩")
        self.forward_btn.setToolTip("前进10秒")
        self.forward_btn.setMinimumSize(32, 24)
        self.forward_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        self.forward_btn.clicked.connect(self._forward_10s)
        playback_controls_layout.addWidget(self.forward_btn)
        
        # 与进度条保持适度间隔
        playback_controls_layout.addSpacing(4)
        
        # 音量和播放速度控制行
        controls_layout2 = QHBoxLayout()
        controls_layout2.setContentsMargins(0, 2, 0, 0)
        controls_layout2.setSpacing(4)
        controls_layout2.setAlignment(Qt.AlignCenter)  # 音量和播放速度控制居中
        
        # 音量控制
        volume_label = QLabel("音量:")
        controls_layout2.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setMaximumWidth(90)
        self.volume_slider.setMinimumHeight(18)
        self.volume_slider.setToolTip("调整音量")
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #ddd;
                height: 4px;
                background: #f8f9fa;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #28a745;
                border: 1px solid #28a745;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #1e7e34;
                border-color: #1e7e34;
            }
            QSlider::sub-page:horizontal {
                background: #28a745;
                border-radius: 2px;
            }
        """)
        self.volume_slider.valueChanged.connect(self._set_volume)
        controls_layout2.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("50%")
        self.volume_label.setMinimumWidth(30)
        controls_layout2.addWidget(self.volume_label)
        
        controls_layout2.addStretch()
        
        # 播放速度控制
        speed_label = QLabel("速度:")
        controls_layout2.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.setToolTip("调整播放速度")
        self.speed_combo.setMinimumHeight(22)
        self.speed_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #f8f9fa;
                font-size: 12px;
            }
            QComboBox:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #6c757d;
                margin-right: 4px;
            }
        """)
        self.speed_combo.currentTextChanged.connect(self._set_playback_rate)
        controls_layout2.addWidget(self.speed_combo)
        
        # 静音按钮
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setToolTip("静音/取消静音")
        self.mute_btn.clicked.connect(self._toggle_mute)
        controls_layout2.addWidget(self.mute_btn)
        
        # 先放置音量/倍速行
        video_layout.addLayout(controls_layout2)
        # 将进度条和时间显示并入播放控制行，并放在音量/倍速行之后
        playback_controls_layout.addLayout(controls_layout)
        video_layout.addLayout(playback_controls_layout)
        
        layout.addWidget(video_group)
        
        # 添加功能选项区域到视频播放下方
        options_group = QGroupBox("快速设置")
        options_layout = QVBoxLayout(options_group)
        options_layout.setAlignment(Qt.AlignCenter)  # 快速设置区域内容居中
        
        # 使用网格布局确保对齐
        from PyQt5.QtWidgets import QGridLayout
        grid_layout = QGridLayout()
        
        # 第一行：生成模式和最大生成长度
        mode_label = QLabel("生成模式:")
        mode_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.center_generation_mode_combo = QComboBox()
        self.center_generation_mode_combo.addItems(["确定性生成", "随机采样生成", "混合策略"])
        self.center_generation_mode_combo.setCurrentText("随机采样生成")
        self.center_generation_mode_combo.setToolTip(
            "确定性生成: 每次运行结果完全一致\n"
            "随机采样生成: 每次运行结果略有不同，更有创造性\n"
            "混合策略: 结合确定性和随机性"
        )
        
        tokens_label = QLabel("描述长度建议:")
        tokens_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.center_description_length_combo = QComboBox()
        self.center_description_length_combo.addItems(["极短", "短", "中", "长", "极长"])
        self.center_description_length_combo.setCurrentText("中")
        self.center_description_length_combo.setToolTip(
            "选择描述的长度等级（用于模型生成和动作过滤）:\n"
            "• 极短: 非常简洁的描述，突出核心动作\n"
            "• 短: 简要描述，包含主要动作信息\n"
            "• 中: 标准长度，平衡详细度和简洁性\n"
            "• 长: 详细描述，包含更多动作细节\n"
            "• 极长: 非常详细的描述，全面分析所有动作\n\n"
            "注意：此设置既用于模型生成时的长度建议，\n"
            "也用于动作过滤时的长度调整。"
        )
        self.center_description_length_combo.currentTextChanged.connect(self._on_description_length_changed)
        
        # 自定义长度输入框（初始隐藏）
        # 自定义长度输入框（已移除，使用新的五等级系统）
        # self.center_custom_length_spinbox = QSpinBox()
        # self.center_custom_length_spinbox.setRange(0, 2000)
        # self.center_custom_length_spinbox.setValue(300)
        # self.center_custom_length_spinbox.setSuffix(" 字符")
        # self.center_custom_length_spinbox.setSpecialValueText("无限制")
        # self.center_custom_length_spinbox.setVisible(False)
        # self.center_custom_length_spinbox.setToolTip("自定义描述建议长度（字符数）\n0: 无限制生成，不给出长度建议\n100-2000: 建议字符数（AI可能生成更多内容）\n\n注意：这只是给AI的建议，不会强制截断输出")
        
        # 第二行：采样帧数和自动保存选项
        frames_label = QLabel("采样帧数:")
        frames_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.center_num_frames_spinbox = QSpinBox()
        self.center_num_frames_spinbox.setRange(0, 64)
        self.center_num_frames_spinbox.setValue(16)
        self.center_num_frames_spinbox.setSpecialValueText("自动")
        self.center_num_frames_spinbox.setToolTip(
            "控制从视频中采样的帧数\n"
            "0: 自动选择（基于视频长度）\n"
            "推荐值: 8-32帧"
        )
        
        auto_save_label = QLabel("启用自动保存:")
        auto_save_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.auto_save_format_combo = QComboBox()
        self.auto_save_format_combo.addItems(["关闭", "JSON格式", "TXT格式", "CSV格式", "MD格式", "全部格式"])
        self.auto_save_format_combo.setToolTip("选择自动保存的文件格式，选择'关闭'则不启用自动保存，选择'全部格式'则同时导出所有类型的文件")
        
        # 添加到网格布局 (行, 列)
        grid_layout.addWidget(mode_label, 0, 0)
        grid_layout.addWidget(self.center_generation_mode_combo, 0, 1)
        grid_layout.addWidget(tokens_label, 0, 3)
        grid_layout.addWidget(self.center_description_length_combo, 0, 4)
        # 自定义长度输入框已移除
        # grid_layout.addWidget(self.center_custom_length_spinbox, 0, 5)
        
        grid_layout.addWidget(frames_label, 1, 0)
        grid_layout.addWidget(self.center_num_frames_spinbox, 1, 1)
        grid_layout.addWidget(auto_save_label, 1, 3)
        grid_layout.addWidget(self.auto_save_format_combo, 1, 4)
        
        # 设置列间距和拉伸
        grid_layout.setColumnMinimumWidth(2, 50)  # 第2列作为间距列，设置最小宽度
        grid_layout.setColumnStretch(5, 1)  # 最后一列拉伸
        grid_layout.setContentsMargins(20, 0, 0, 0)  # 左边距，让整体向右移动
        
        options_layout.addLayout(grid_layout)
        
        # 第三行：处理控制按钮（增大尺寸）
        control_layout = QHBoxLayout()
        
        self.center_start_btn = QPushButton("🚀 开始描述")
        self.center_start_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #3498db;"
            "    color: white;"
            "    border: none;"
            "    padding: 12px 24px;"
            "    font-size: 14px;"
            "    font-weight: bold;"
            "    border-radius: 6px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #2980b9;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #21618c;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #bdc3c7;"
            "    color: #7f8c8d;"
            "}"
        )
        self.center_start_btn.clicked.connect(self._start_description)
        
        self.center_stop_btn = QPushButton("⏹ 停止处理")
        self.center_stop_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #e74c3c;"
            "    color: white;"
            "    border: none;"
            "    padding: 12px 24px;"
            "    font-size: 14px;"
            "    font-weight: bold;"
            "    border-radius: 6px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #c0392b;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #a93226;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #bdc3c7;"
            "    color: #7f8c8d;"
            "}"
        )
        self.center_stop_btn.setEnabled(False)
        self.center_stop_btn.clicked.connect(self._stop_description)
        
        control_layout.addWidget(self.center_start_btn)
        control_layout.addWidget(self.center_stop_btn)
        
        # 添加重新过滤按钮
        self.refilter_btn = QPushButton("🔄 重新过滤")
        self.refilter_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #f39c12;"
            "    color: white;"
            "    border: none;"
            "    padding: 12px 24px;"
            "    font-size: 14px;"
            "    font-weight: bold;"
            "    border-radius: 6px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #e67e22;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #d35400;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #bdc3c7;"
            "    color: #7f8c8d;"
            "}"
        )
        self.refilter_btn.setToolTip("对已生成的结果重新应用动作描述过滤")
        self.refilter_btn.clicked.connect(self._show_refilter_dialog)
        control_layout.addWidget(self.refilter_btn)
        
        options_layout.addLayout(control_layout)
        
        # 进度条
        self.center_progress_bar = QProgressBar()
        self.center_progress_bar.setStyleSheet(
            "QProgressBar {"
            "    border: 2px solid #bdc3c7;"
            "    border-radius: 5px;"
            "    text-align: center;"
            "    font-weight: bold;"
            "}"
            "QProgressBar::chunk {"
            "    background-color: #27ae60;"
            "    border-radius: 3px;"
            "}"
        )
        options_layout.addWidget(self.center_progress_bar)
        
        # 功能说明（改为无标题滚动说明区）
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        center_scroll.setMinimumHeight(180)
        center_scroll.setMaximumHeight(360)
        center_scroll_content = QWidget()
        center_scroll_layout = QVBoxLayout(center_scroll_content)
        
        center_mode_info = QLabel(
            """
            <b>🎯 生成模式：</b><br>
            • 确定性生成：结果稳定一致，适合批量与复现需求<br>
            • 随机采样生成：结果更具多样性与创造性<br>
            • 混合策略：在稳定与丰富之间折中<br><br>
            <b>📝 描述长度建议：</b><br>
            • 选项：简要/标准/详细/非常详细/无限制/自定义<br>
            • 自定义长度：为AI提供建议字符数（不会强制截断）<br>
            • 注意：这是“建议值”，AI可根据视频复杂度适当增减以保证完整性<br><br>
            <b>📊 采样帧数：</b><br>
            • 0 = 自动：按视频时长自适应（≤10秒16帧；10-30秒20帧；30-60秒25帧；>60秒32帧）<br>
            • 手动：推荐范围 8-32 帧；帧数越多覆盖越全面、耗时越长<br><br>
            <b>🎛️ 采样参数（top_p）：</b><br>
            • 0.8-0.85：更聚焦、更简洁；0.9（默认）：平衡；0.95-1.0：更丰富<br><br>
            <b>🖥️ 计算设备：</b><br>
            • Auto（推荐）/CUDA/CPU；GPU设备可指定 cuda:0 等<br><br>
            <b>🧩 并行与批处理：</b><br>
            • 多线程与线程数设置；GPU优化批处理：合理设置批大小与预处理线程数<br>
            • 处理大量视频时更明显；单段短视频收益有限<br><br>
            <b>⚡ 性能与优化说明：</b><br>
            • 智能加速：根据系统负载动态调整加载与缓存，降低峰值占用<br>
            • 快速预加载：提前准备下一批数据，减少空转等待，提升吞吐<br>
            • 批大小建议：8GB显存 1-2；8-16GB 2-4；16GB+ 4-8（需结合分辨率）<br>
            • 预处理线程：与CPU/磁盘有关，建议 2-4/8-16GB；4-8/16GB+；过多会引发上下文切换开销<br>
            • 遇到显存不足（OOM）：降低批大小/分辨率，关闭GPU优化或换用CPU；同时关闭其他占GPU程序<br>
            • I/O 成为瓶颈（机械盘/网盘）：提高预加载、适当降低线程数更稳<br>
            • 日志会输出“设备/显存状态”，据此迭代参数，逐步收敛到稳定高效配置<br><br>
            <b>🧭 内容控制：</b><br>
            • 只保留动作描述、自适应播放控制<br><br>
            <b>💾 自动保存：</b><br>
            • 导出格式：JSON/TXT/CSV/MD/全部/关闭；处理完成自动保存<br><br>
            <b>🔑 API配置：</b><br>
            • 端点/密钥/模型名称按服务方要求填写；密钥可隐藏/显示
            """
        )
        center_mode_info.setWordWrap(True)
        center_mode_info.setStyleSheet(
            "QLabel { background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; padding: 10px; color: #2c3e50; font-size: 12px; line-height: 1.5; }"
        )
        center_scroll_layout.addWidget(center_mode_info)
        
        # 预留2-3行空间用于未来新增选项
        spacer = QWidget()
        spacer.setMinimumHeight(60)
        center_scroll_layout.addWidget(spacer)
        center_scroll_layout.addStretch()
        
        center_scroll.setWidget(center_scroll_content)
        options_layout.addWidget(center_scroll)
        
        layout.addWidget(options_group)
        
        return panel
    
    def _create_right_panel(self):
        """创建右侧面板（日志和结果）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)  # 右侧面板内容居中对齐
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 处理日志选项卡
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setAlignment(Qt.AlignCenter)  # 日志选项卡内容居中
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setAcceptRichText(True)  # 启用HTML格式支持
        
        # 连接文本变化信号到日志文件写入
        self.log_text.textChanged.connect(self._on_log_text_changed)
        
        log_layout.addWidget(self.log_text)
        
        tab_widget.addTab(log_tab, "处理日志")
        
        # 详细结果选项卡
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        result_layout.setAlignment(Qt.AlignCenter)  # 结果选项卡内容居中
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)
        
        # 添加模型结果切换按钮
        model_switch_layout = QHBoxLayout()
        model_switch_layout.setAlignment(Qt.AlignCenter)  # 按钮居中
        
        self.model_switch_label = QLabel("模型结果:")
        model_switch_layout.addWidget(self.model_switch_label)
        
        self.local_model_btn = QPushButton("本地模型")
        self.local_model_btn.clicked.connect(lambda: self._switch_model_result('local'))
        self.local_model_btn.setToolTip("显示本地模型生成的结果")
        model_switch_layout.addWidget(self.local_model_btn)
        
        self.api_model_btn = QPushButton("API模型")
        self.api_model_btn.clicked.connect(lambda: self._switch_model_result('api'))
        self.api_model_btn.setToolTip("显示API模型生成的结果")
        model_switch_layout.addWidget(self.api_model_btn)
        
        result_layout.addLayout(model_switch_layout)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        export_layout.setAlignment(Qt.AlignCenter)  # 导出按钮居中
        
        self.export_json_btn = QPushButton("导出JSON")
        self.export_json_btn.clicked.connect(lambda: self._export_results('json'))
        self.export_json_btn.setToolTip("导出选中视频的详细结果为JSON格式")
        export_layout.addWidget(self.export_json_btn)
        
        self.export_txt_btn = QPushButton("导出TXT")
        self.export_txt_btn.clicked.connect(lambda: self._export_results('txt'))
        self.export_txt_btn.setToolTip("导出选中视频的详细结果为TXT格式")
        export_layout.addWidget(self.export_txt_btn)
        
        self.export_csv_btn = QPushButton("导出CSV")
        self.export_csv_btn.clicked.connect(lambda: self._export_results('csv'))
        self.export_csv_btn.setToolTip("导出选中视频的详细结果为CSV格式")
        export_layout.addWidget(self.export_csv_btn)
        
        self.export_md_btn = QPushButton("导出Markdown")
        self.export_md_btn.clicked.connect(lambda: self._export_results('md'))
        self.export_md_btn.setToolTip("导出选中视频的详细结果为Markdown格式")
        export_layout.addWidget(self.export_md_btn)
        
        result_layout.addLayout(export_layout)
        
        tab_widget.addTab(result_tab, "详细结果")
        
        layout.addWidget(tab_widget)
        
        return panel
    
    def _load_cache_config(self):
        """加载缓存配置"""
        try:
            from ..core.user_config_manager import get_user_config_manager
            config_manager = get_user_config_manager()
            
            # 获取模型路径配置
            model_path = config_manager.config.get('sharegpt4video_model_path', '')
            if model_path:
                self.model_path = model_path
            else:
                self.model_path = "Lin-Chen/sharegpt4video-8b"
        except Exception as e:
            self.model_path = "Lin-Chen/sharegpt4video-8b"
            self._log_message(f"加载缓存配置失败: {str(e)}")
        
        # 从配置管理器加载设备设置
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                device_setting = self.config_manager.get('algorithms.video_description.device', 'CUDA')  # 默认使用CUDA
                if hasattr(self, 'device_combo'):
                    self.device_combo.setCurrentText(device_setting)
                    
                # 加载算法类型设置
                algorithm_type = self.config_manager.get('algorithms.video_description.algorithm_type', '本地模型')
                if hasattr(self, 'algorithm_type_combo'):
                    self.algorithm_type_combo.setCurrentText(algorithm_type)
                    
                # 加载API配置
                api_endpoint = self.config_manager.get('algorithms.video_description.api_endpoint', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
                api_key = self.config_manager.get('algorithms.video_description.api_key', 'fa1f2df2-73f8-44b1-99a0-09834047ab51')
                api_model = self.config_manager.get('algorithms.video_description.api_model', 'doubao-1.5-vision-pro-250328')
                
                if hasattr(self, 'api_endpoint_edit'):
                    self.api_endpoint_edit.setText(api_endpoint)
                if hasattr(self, 'api_key_edit'):
                    self.api_key_edit.setText(api_key)
                if hasattr(self, 'api_model_combo'):
                    self.api_model_combo.setCurrentText(api_model)
                    
                # 加载智能加载配置
                enable_smart_loading = self.config_manager.get('algorithms.video_description.enable_smart_loading', True)
                enable_fast_preload = self.config_manager.get('algorithms.video_description.enable_fast_preload', True)
                gpu_device = self.config_manager.get('algorithms.video_description.gpu_device', '自动检测')
                
                if hasattr(self, 'smart_loading_checkbox'):
                    self.smart_loading_checkbox.setChecked(enable_smart_loading)
                if hasattr(self, 'fast_preload_checkbox'):
                    self.fast_preload_checkbox.setChecked(enable_fast_preload)
                if hasattr(self, 'gpu_device_combo'):
                    self.gpu_device_combo.setCurrentText(gpu_device)
                    
                # 加载多线程和GPU优化配置
                enable_multithread = self.config_manager.get('algorithms.video_description.enable_multithread', False)
                thread_count = self.config_manager.get('algorithms.video_description.thread_count', 2)
                enable_gpu_optimization = self.config_manager.get('algorithms.video_description.enable_gpu_optimization', False)
                gpu_batch_size = self.config_manager.get('algorithms.video_description.gpu_batch_size', 2)
                gpu_max_workers = self.config_manager.get('algorithms.video_description.gpu_max_workers', 4)
                
                if hasattr(self, 'multithread_checkbox'):
                    self.multithread_checkbox.setChecked(enable_multithread)
                if hasattr(self, 'thread_count_spinbox'):
                    self.thread_count_spinbox.setValue(thread_count)
                if hasattr(self, 'gpu_optimization_checkbox'):
                    self.gpu_optimization_checkbox.setChecked(enable_gpu_optimization)
                if hasattr(self, 'gpu_batch_size_spinbox'):
                    self.gpu_batch_size_spinbox.setValue(gpu_batch_size)
                if hasattr(self, 'gpu_max_workers_spinbox'):
                    self.gpu_max_workers_spinbox.setValue(gpu_max_workers)
                    
                # 恢复时长排序/分桶模式
                if hasattr(self, 'duration_sort_mode_combo'):
                    try:
                        saved_mode = self.config_manager.get('algorithms.video_description.duration_sort_mode', '默认顺序') if hasattr(self, 'config_manager') and self.config_manager else '默认顺序'
                        if saved_mode:
                            self.duration_sort_mode_combo.setCurrentText(saved_mode)
                    except Exception as e2:
                        self._log_message(f"加载时长排序模式失败: {str(e2)}")
                    
        except Exception as e:
            self._log_message(f"加载配置失败: {str(e)}")
    
    def _connect_signals(self):
        """连接信号"""
        # 注意：播放控制按钮的信号已在_create_center_panel中连接，这里不再重复连接
        # 连接中间面板和左侧面板控件的同步信号
        
        # 自动保存选项同步
        self.auto_save_format_combo.currentTextChanged.connect(self._on_auto_save_format_changed)
        
        # 排序/分桶模式切换
        if hasattr(self, 'duration_sort_mode_combo'):
            self.duration_sort_mode_combo.currentTextChanged.connect(self._on_duration_sort_mode_changed)
        
        # 连接GPU优化选项信号
        if hasattr(self, 'gpu_optimization_checkbox'):
            self.gpu_optimization_checkbox.toggled.connect(self._on_gpu_optimization_toggled)
            
        # 连接智能加载设置信号
        if hasattr(self, 'smart_loading_checkbox'):
            self.smart_loading_checkbox.toggled.connect(self._save_api_config)
        if hasattr(self, 'fast_preload_checkbox'):
            self.fast_preload_checkbox.toggled.connect(self._save_api_config)
        if hasattr(self, 'gpu_device_combo'):
            self.gpu_device_combo.currentTextChanged.connect(self._on_gpu_device_changed)
            self.gpu_device_combo.currentTextChanged.connect(self._save_api_config)
            
        # 连接多线程和GPU优化设置信号
        if hasattr(self, 'multithread_checkbox'):
            self.multithread_checkbox.toggled.connect(self._save_api_config)
        if hasattr(self, 'thread_count_spinbox'):
            self.thread_count_spinbox.valueChanged.connect(self._save_api_config)
        if hasattr(self, 'gpu_batch_size_spinbox'):
            self.gpu_batch_size_spinbox.valueChanged.connect(self._save_api_config)
        if hasattr(self, 'gpu_max_workers_spinbox'):
            self.gpu_max_workers_spinbox.valueChanged.connect(self._save_api_config)
        
        # 连接配置变化信号
        try:
            # 获取主窗口的app实例
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'app'):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, 'app') and hasattr(main_window.app, 'config_changed'):
                main_window.app.config_changed.connect(self._on_config_changed)
        except Exception as e:
            self._log_message(f"连接配置变化信号失败: {str(e)}")
    
    def _setup_responsive_layout(self):
        """设置响应式布局"""
        # 设置面板最小宽度
        left_panel = self.main_splitter.widget(0)
        center_panel = self.main_splitter.widget(1)
        right_panel = self.main_splitter.widget(2)
        
        left_panel.setMinimumWidth(280)
        center_panel.setMinimumWidth(400)
        right_panel.setMinimumWidth(350)
        
        # 根据当前窗口大小设置初始比例
        self._adjust_layout_for_window_size()
        
        # 连接分割器位置变化信号，保存用户偏好
        self.main_splitter.splitterMoved.connect(self._save_splitter_state)
        
        # 加载保存的分割器状态
        self._load_splitter_state()
    
    def _adjust_layout_for_window_size(self):
        """根据窗口大小调整布局"""
        try:
            # 获取当前窗口宽度
            window_width = self.width()
            if window_width <= 0:
                # 如果还没有显示，使用默认值
                window_width = 1200
            
            # 根据窗口宽度设置不同的比例
            if window_width < 1000:
                # 小屏幕：紧凑布局
                sizes = [280, 400, 350]
            elif window_width < 1400:
                # 中等屏幕：平衡布局
                sizes = [320, 480, 400]
            else:
                # 大屏幕：宽松布局
                sizes = [350, 550, 450]
            
            # 调整比例以适应实际窗口宽度
            total_size = sum(sizes)
            if total_size < window_width:
                # 按比例扩展
                scale = window_width / total_size
                sizes = [int(size * scale) for size in sizes]
            
            self.main_splitter.setSizes(sizes)
            
        except Exception as e:
            self._log_message(f"调整布局失败: {str(e)}")
    
    def _connect_resize_handler(self):
        """连接窗口大小变化处理器"""
        # 使用定时器防止频繁调整
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._on_window_resized)
    
    def resizeEvent(self, event):
        """窗口大小变化事件"""
        super().resizeEvent(event)
        # 延迟调整布局，避免频繁计算
        if hasattr(self, 'resize_timer'):
            self.resize_timer.start(100)  # 100ms延迟
    
    def _on_window_resized(self):
        """窗口大小变化处理"""
        if hasattr(self, 'main_splitter'):
            self._adjust_layout_for_window_size()
        # 调整视频列表高度
        self._adjust_video_list_height()
    
    def _adjust_video_list_height(self):
        """根据窗口高度动态调整视频列表高度"""
        try:
            if not hasattr(self, 'video_list') or not hasattr(self, 'upload_group'):
                return
            
            # 获取当前窗口高度
            window_height = self.height()
            if window_height <= 0:
                window_height = 800  # 默认高度
            
            # 计算上传组的可用高度
            # 考虑主布局边距、面板间距、描述区域等占用的空间
            reserved_height = 400  # 为其他组件预留的高度（描述区域、功能选项区域、边距等）
            available_height = max(200, window_height - reserved_height)
            
            # 计算上传组内部其他组件占用的高度
            upload_buttons_height = 50  # 上传按钮区域高度
            list_control_height = 35   # 列表控制区域高度
            group_margins = 24         # 组边距（上下各12px）
            list_margins = 16          # 列表外边距和内边距
            
            # 计算视频列表可用的最大高度
            max_list_height = available_height - upload_buttons_height - list_control_height - group_margins - list_margins
            
            # 设置视频列表高度约束
            min_height = 120  # 最小高度
            max_height = max(min_height, max_list_height)
            
            # 应用高度约束
            self.video_list.setMinimumHeight(min_height)
            self.video_list.setMaximumHeight(max_height)
            
            # 确保上传组也有合适的高度约束
            upload_group_height = upload_buttons_height + list_control_height + max_height + group_margins + list_margins
            self.upload_group.setMaximumHeight(upload_group_height + 20)  # 额外留一些空间
            
        except Exception as e:
            self._log_message(f"调整视频列表高度失败: {str(e)}")
    
    def _save_splitter_state(self):
        """保存分割器状态"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager and hasattr(self, 'main_splitter'):
                sizes = self.main_splitter.sizes()
                self.config_manager.set('ui.video_description.splitter_sizes', sizes)
        except Exception as e:
            self._log_message(f"保存分割器状态失败: {str(e)}")
    
    def _load_splitter_state(self):
        """加载分割器状态"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager and hasattr(self, 'main_splitter'):
                sizes = self.config_manager.get('ui.video_description.splitter_sizes', None)
                if sizes and len(sizes) == 3:
                    self.main_splitter.setSizes(sizes)
        except Exception as e:
            self._log_message(f"加载分割器状态失败: {str(e)}")
    
    def _on_device_changed(self):
        """设备选择变化处理"""
        # 检查当前是否为API模式
        model_preset = "ShareVideoGPT4（本地模型）"  # 默认值
        if hasattr(self, 'config_manager') and self.config_manager:
            algorithm_config = self.config_manager.get('algorithms', {})
            video_desc_config = algorithm_config.get('video_description', {})
            model_preset = video_desc_config.get('model_preset', 'ShareVideoGPT4（本地模型）')
        
        is_api_mode = model_preset != "ShareVideoGPT4（本地模型）"
        
        # 如果是API模式，不处理设备变化（保持禁用状态）
        if is_api_mode:
            return
            
        device = self.device_combo.currentText()
        
        # 只有在CUDA模式下才允许多线程处理和GPU优化
        if device == "CUDA":
            self.multithread_checkbox.setEnabled(True)
            self.thread_count_spinbox.setEnabled(True)
            # 启用智能加载选项
            if hasattr(self, 'smart_loading_checkbox'):
                self.smart_loading_checkbox.setEnabled(True)
                self.fast_preload_checkbox.setEnabled(True)
                self.gpu_device_combo.setEnabled(True)
            # 启用GPU优化选项
            if hasattr(self, 'gpu_optimization_checkbox'):
                self.gpu_optimization_checkbox.setEnabled(True)
                self.gpu_batch_size_spinbox.setEnabled(self.gpu_optimization_checkbox.isChecked())
                self.gpu_max_workers_spinbox.setEnabled(self.gpu_optimization_checkbox.isChecked())
            # 默认不勾选多线程，用户可根据需要手动启用
        else:  # Auto或CPU模式
            self.multithread_checkbox.setEnabled(False)
            self.multithread_checkbox.setChecked(False)
            self.thread_count_spinbox.setEnabled(False)
            # 智能加载选项在Auto模式下仍可用，CPU模式下禁用
            if hasattr(self, 'smart_loading_checkbox'):
                if device == "Auto":
                    self.smart_loading_checkbox.setEnabled(True)
                    self.fast_preload_checkbox.setEnabled(True)
                    self.gpu_device_combo.setEnabled(True)
                else:  # CPU模式
                    self.smart_loading_checkbox.setEnabled(False)
                    self.fast_preload_checkbox.setEnabled(False)
                    self.gpu_device_combo.setEnabled(False)
            # 禁用GPU优化选项
            if hasattr(self, 'gpu_optimization_checkbox'):
                self.gpu_optimization_checkbox.setEnabled(False)
                self.gpu_optimization_checkbox.setChecked(False)
                self.gpu_batch_size_spinbox.setEnabled(False)
                self.gpu_max_workers_spinbox.setEnabled(False)
    
    def _on_gpu_optimization_toggled(self, checked: bool):
        """GPU优化选项切换处理"""
        if hasattr(self, 'gpu_batch_size_spinbox') and hasattr(self, 'gpu_max_workers_spinbox'):
            self.gpu_batch_size_spinbox.setEnabled(checked)
            self.gpu_max_workers_spinbox.setEnabled(checked)
    
    def _on_gpu_device_changed(self, device_name: str):
        """GPU设备选择变化处理"""
        try:
            if device_name == "自动检测":
                self._log_message("🔄 GPU设备: 已选择自动检测模式")
                self._perform_auto_gpu_detection()
            elif device_name.startswith("cuda:"):
                gpu_id = device_name.split(":")[1]
                self._log_message(f"🎯 GPU设备: 已手动选择 {device_name}")
                self._show_gpu_device_info(int(gpu_id))
            elif device_name == "cpu":
                self._log_message("💻 GPU设备: 已选择CPU模式，将不使用GPU加速")
            else:
                self._log_message(f"⚙️ GPU设备: 已选择 {device_name}")
        except Exception as e:
            self._log_message(f"❌ GPU设备选择处理失败: {str(e)}")
    
    def _perform_auto_gpu_detection(self):
        """执行自动GPU检测并显示详细信息"""
        try:
            import torch
            
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                self._log_message(f"  🔍 自动检测: 发现 {device_count} 个可用GPU设备")
                
                # 选择最佳GPU设备
                best_gpu = 0
                max_memory = 0
                best_device_name = ""
                
                for i in range(device_count):
                    device_name = torch.cuda.get_device_name(i)
                    device_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                    
                    self._log_message(f"    📱 GPU {i}: {device_name} ({device_memory:.1f}GB)")
                    
                    if device_memory > max_memory:
                        max_memory = device_memory
                        best_gpu = i
                        best_device_name = device_name
                
                # 显示自动选择结果
                self._log_message(f"  ✅ 自动选择: cuda:{best_gpu} - {best_device_name} ({max_memory:.1f}GB)")
                
                # 显示GPU状态信息
                try:
                    torch.cuda.set_device(best_gpu)
                    memory_allocated = torch.cuda.memory_allocated(best_gpu) / (1024**3)
                    memory_reserved = torch.cuda.memory_reserved(best_gpu) / (1024**3)
                    self._log_message(f"    📊 显存状态: 已分配 {memory_allocated:.2f}GB / 已保留 {memory_reserved:.2f}GB")
                except Exception as e:
                    self._log_message(f"    ⚠️ 无法获取显存状态: {str(e)}")
                    
            else:
                self._log_message("  ❌ 自动检测: 未发现可用的CUDA设备，将回退到CPU模式")
                
        except ImportError:
            self._log_message("  ❌ 自动检测失败: 无法导入PyTorch")
        except Exception as e:
            self._log_message(f"  ❌ 自动检测失败: {str(e)}")
    
    def _show_gpu_device_info(self, gpu_id: int):
        """显示指定GPU设备的详细信息"""
        try:
            import torch
            
            if torch.cuda.is_available() and gpu_id < torch.cuda.device_count():
                device_name = torch.cuda.get_device_name(gpu_id)
                device_memory = torch.cuda.get_device_properties(gpu_id).total_memory / (1024**3)
                
                self._log_message(f"  📱 设备信息: {device_name} ({device_memory:.1f}GB 显存)")
                
                # 显示计算能力
                try:
                    compute_capability = torch.cuda.get_device_capability(gpu_id)
                    self._log_message(f"  💻 计算能力: {compute_capability[0]}.{compute_capability[1]}")
                except Exception:
                    pass
                
                # 显示当前显存使用情况
                try:
                    torch.cuda.set_device(gpu_id)
                    memory_allocated = torch.cuda.memory_allocated(gpu_id) / (1024**3)
                    memory_reserved = torch.cuda.memory_reserved(gpu_id) / (1024**3)
                    self._log_message(f"  📊 显存状态: 已分配 {memory_allocated:.2f}GB / 已保留 {memory_reserved:.2f}GB")
                except Exception as e:
                    self._log_message(f"  ⚠️ 无法获取显存状态: {str(e)}")
                    
            else:
                self._log_message(f"  ❌ GPU {gpu_id} 不可用或不存在")
                
        except ImportError:
            self._log_message(f"  ❌ 无法获取GPU {gpu_id} 信息: PyTorch未安装")
        except Exception as e:
            self._log_message(f"  ❌ 获取GPU {gpu_id} 信息失败: {str(e)}")
    
    def refresh_ui_state(self):
        """刷新UI状态（供外部调用）"""
        self._update_ui_based_on_algorithm_type()
    
    def _update_ui_based_on_algorithm_type(self):
        """根据配置中的模型预设更新UI状态"""
        try:
            # 从配置中读取模型预设
            model_preset = "ShareVideoGPT4（本地模型）"  # 默认值
            if hasattr(self, 'config_manager') and self.config_manager:
                algorithm_config = self.config_manager.get('algorithms', {})
                video_desc_config = algorithm_config.get('video_description', {})
                model_preset = video_desc_config.get('model_preset', 'ShareVideoGPT4（本地模型）')
            
            # 判断是否为API模式（除了ShareVideoGPT4（本地模型）之外的都是API模式）
            is_api_mode = model_preset != "ShareVideoGPT4（本地模型）"
            
            if is_api_mode:
                # 隐藏API配置（配置保存在文件中），禁用本地模型相关配置
                self.api_config_group.setVisible(False)
                
                # 禁用本地模型相关功能
                self.device_combo.setEnabled(False)
                self.multithread_checkbox.setEnabled(False)
                self.thread_count_spinbox.setEnabled(False)
                self.top_p_spinbox.setEnabled(False)
                
                # 禁用GPU优化选项
                if hasattr(self, 'gpu_optimization_checkbox'):
                    self.gpu_optimization_checkbox.setEnabled(False)
                    self.gpu_optimization_checkbox.setChecked(False)
                    self.gpu_batch_size_spinbox.setEnabled(False)
                    self.gpu_max_workers_spinbox.setEnabled(False)
                
                # 禁用生成模式和采样帧数（API模式下这些参数由API控制）
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setEnabled(False)
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setEnabled(False)
                
                # 设置控件为灰色状态
                self.device_combo.setStyleSheet("QComboBox { color: #888888; background-color: #f0f0f0; }")
                self.multithread_checkbox.setStyleSheet("QCheckBox { color: #888888; }")
                self.thread_count_spinbox.setStyleSheet("QSpinBox { color: #888888; background-color: #f0f0f0; }")
                self.top_p_spinbox.setStyleSheet("QDoubleSpinBox { color: #888888; background-color: #f0f0f0; }")
                
                # 设置GPU优化选项为灰色状态
                if hasattr(self, 'gpu_optimization_checkbox'):
                    self.gpu_optimization_checkbox.setStyleSheet("QCheckBox { color: #888888; }")
                    self.gpu_batch_size_spinbox.setStyleSheet("QSpinBox { color: #888888; background-color: #f0f0f0; }")
                    self.gpu_max_workers_spinbox.setStyleSheet("QSpinBox { color: #888888; background-color: #f0f0f0; }")
                
                # 设置生成模式和采样帧数为灰色状态
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setStyleSheet("QComboBox { color: #888888; background-color: #f0f0f0; }")
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setStyleSheet("QSpinBox { color: #888888; background-color: #f0f0f0; }")
                
                # 取消多线程选择
                self.multithread_checkbox.setChecked(False)
                
                # API模式已在_update_model_ui_state中记录日志，此处不再重复记录
                
            else:  # 本地模型模式 (ShareVideoGPT4（本地模型）)
                # 隐藏API配置，启用本地模型相关配置
                self.api_config_group.setVisible(False)
                
                # 启用本地模型相关功能
                self.device_combo.setEnabled(True)
                self.top_p_spinbox.setEnabled(True)
                
                # 启用生成模式和采样帧数
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setEnabled(True)
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setEnabled(True)
                
                # 恢复控件正常样式
                self.device_combo.setStyleSheet("")
                self.multithread_checkbox.setStyleSheet("")
                self.thread_count_spinbox.setStyleSheet("")
                self.top_p_spinbox.setStyleSheet("")
                
                # 恢复GPU优化选项正常样式
                if hasattr(self, 'gpu_optimization_checkbox'):
                    self.gpu_optimization_checkbox.setStyleSheet("")
                    self.gpu_batch_size_spinbox.setStyleSheet("")
                    self.gpu_max_workers_spinbox.setStyleSheet("")
                
                # 恢复生成模式和采样帧数正常样式
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setStyleSheet("")
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setStyleSheet("")
                
                # 根据设备设置恢复多线程选项状态
                self._on_device_changed()
                
                # 本地模型模式已在_update_model_ui_state中记录日志，此处不再重复记录
                
        except Exception as e:
            self._log_message(f"更新UI状态失败: {str(e)}")
    
    def _toggle_api_key_visibility(self):
        """切换API密钥显示/隐藏"""
        if self.api_key_edit.echoMode() == QLineEdit.Password:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self.show_key_btn.setText("隐藏")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.show_key_btn.setText("显示")
    

    
    def _save_api_config(self):
        """保存API配置"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                # 保存API配置
                self.config_manager.set('algorithms.video_description.api_endpoint', self.api_endpoint_edit.text())
                self.config_manager.set('algorithms.video_description.api_key', self.api_key_edit.text())
                self.config_manager.set('algorithms.video_description.api_model', self.api_model_combo.currentText())
                
                # 保存智能加载配置
                if hasattr(self, 'smart_loading_checkbox'):
                    self.config_manager.set('algorithms.video_description.enable_smart_loading', self.smart_loading_checkbox.isChecked())
                if hasattr(self, 'fast_preload_checkbox'):
                    self.config_manager.set('algorithms.video_description.enable_fast_preload', self.fast_preload_checkbox.isChecked())
                if hasattr(self, 'gpu_device_combo'):
                    self.config_manager.set('algorithms.video_description.gpu_device', self.gpu_device_combo.currentText())
                    
                # 保存多线程和GPU优化配置
                if hasattr(self, 'multithread_checkbox'):
                    self.config_manager.set('algorithms.video_description.enable_multithread', self.multithread_checkbox.isChecked())
                if hasattr(self, 'thread_count_spinbox'):
                    self.config_manager.set('algorithms.video_description.thread_count', self.thread_count_spinbox.value())
                if hasattr(self, 'gpu_optimization_checkbox'):
                    self.config_manager.set('algorithms.video_description.enable_gpu_optimization', self.gpu_optimization_checkbox.isChecked())
                if hasattr(self, 'gpu_batch_size_spinbox'):
                    self.config_manager.set('algorithms.video_description.gpu_batch_size', self.gpu_batch_size_spinbox.value())
                if hasattr(self, 'gpu_max_workers_spinbox'):
                    self.config_manager.set('algorithms.video_description.gpu_max_workers', self.gpu_max_workers_spinbox.value())
                    
        except Exception as e:
            self._log_message(f"保存配置失败: {str(e)}")
    
    def _upload_video_files(self):
        """上传视频文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "", "视频文件 (*.mp4)"
        )
        
        if files:
            for file_path in files:
                if file_path not in self.current_videos:
                    self.current_videos.append(file_path)
                    # 读取并缓存视频时长
                    try:
                        cap = cv2.VideoCapture(file_path)
                        if cap.isOpened():
                            fps = cap.get(cv2.CAP_PROP_FPS) or 0
                            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                            duration = frame_count / fps if fps > 0 else 0
                            self.video_durations[file_path] = float(duration)
                        else:
                            self.video_durations[file_path] = None
                        cap.release()
                    except Exception:
                        self.video_durations[file_path] = None
                    self._add_video_to_list(file_path)
            # 上传完成后根据模式应用排序/分桶
            if hasattr(self, 'duration_sort_mode_combo'):
                self._apply_duration_sorting()
    
    def _upload_video_folder(self):
        """上传视频文件夹（支持多选文件夹）"""
        # 使用自定义的多选文件夹对话框
        folders = self._select_multiple_folders()
        
        if folders:
            total_added = 0
            total_processed = 0
            
            # 处理所有选中的文件夹
            for folder in folders:
                added_count, processed_count = self._add_videos_from_folder(folder)
                total_added += added_count
                total_processed += processed_count
            
            # 显示总结信息
            if total_added > 0:
                message = f"从 {len(folders)} 个文件夹中添加了 {total_added} 个视频文件"
                if total_processed > 0:
                    message += f"，其中 {total_processed} 个已有处理结果"
                self._log_message(message)
                
                # 显示成功消息
                QMessageBox.information(
                    self, "添加完成", 
                    f"成功处理了 {len(folders)} 个文件夹\n"
                    f"添加视频: {total_added} 个\n"
                    f"已有结果: {total_processed} 个"
                )
            else:
                QMessageBox.information(self, "提示", "所选文件夹中没有找到新的视频文件")
    
    def _select_multiple_folders(self):
        """显示支持多选的文件夹选择对话框"""
        dialog = MultiFolderSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_selected_folders()
        return []
    
    def _add_videos_from_folder(self, folder):
        """从文件夹添加视频文件并读取已有描述文件"""
        video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.wmv', '*.flv', '*.webm']
        
        added_count = 0
        processed_count = 0
        
        for extension in video_extensions:
            for file_path in Path(folder).glob(extension):
                file_str = str(file_path)
                if file_str not in self.current_videos:
                    self.current_videos.append(file_str)
                    # 缓存时长
                    try:
                        cap = cv2.VideoCapture(file_str)
                        if cap.isOpened():
                            fps = cap.get(cv2.CAP_PROP_FPS) or 0
                            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                            duration = frame_count / fps if fps > 0 else 0
                            self.video_durations[file_str] = float(duration)
                        else:
                            self.video_durations[file_str] = None
                        cap.release()
                    except Exception:
                        self.video_durations[file_str] = None
                    self._add_video_to_list(file_str)
                    added_count += 1
                    
                    # 检查是否有已存在的描述文件
                    if self._is_video_processed(file_str):
                        processed_count += 1
        
        # 应用排序/分桶
        if hasattr(self, 'duration_sort_mode_combo'):
            self._apply_duration_sorting()
        
        # 返回添加和处理的数量
        return added_count, processed_count
    
    def _select_all_videos(self):
        """全选所有视频（忽略分组头）"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Checked)
        self._update_selection_status()
    
    def _deselect_all_videos(self):
        """取消全选所有视频（忽略分组头）"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Unchecked)
        self._update_selection_status()
    
    def _get_selected_videos(self):
        """获取选中的视频列表（忽略分组头等不可勾选项）"""
        selected_videos = []
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if (item.flags() & Qt.ItemIsUserCheckable) and item.checkState() == Qt.Checked:
                video_path = item.data(Qt.UserRole)
                if video_path:
                    selected_videos.append(video_path)
        return selected_videos
    
    def _on_video_check_changed(self, item):
        """视频复选框状态改变"""
        self._update_selection_status()
    
    def _on_description_length_changed(self, text):
        """描述长度要求改变时的回调"""
        # 新的五等级系统不需要自定义长度输入框
        pass
    
    def _toggle_select_all(self):
        """切换全选/取消全选"""
        if self.is_all_selected:
            # 当前是全选状态，执行取消全选
            self._deselect_all_videos()
        else:
            # 当前不是全选状态，执行全选
            self._select_all_videos()
    
    def _update_selection_status(self):
        """更新选择状态显示（忽略分组头）"""
        selected_count = 0
        total_checkable = 0
        for i in range(self.video_list.count()):
            it = self.video_list.item(i)
            if it.flags() & Qt.ItemIsUserCheckable:
                total_checkable += 1
                if it.checkState() == Qt.Checked:
                    selected_count += 1
        self.selection_status_label.setText(f"已选择：{selected_count}/{total_checkable}")
        
        # 更新切换按钮状态
        if total_checkable == 0:
            self.is_all_selected = False
            self.select_toggle_btn.setText("全选")
        elif selected_count == total_checkable:
            self.is_all_selected = True
            self.select_toggle_btn.setText("取消全选")
        else:
            self.is_all_selected = False
            self.select_toggle_btn.setText("全选")
    
    def _on_duration_sort_mode_changed(self, mode_text: str):
        """时长排序/分桶模式变化"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                self.config_manager.set('algorithms.video_description.duration_sort_mode', mode_text)
        except Exception as e:
            self._log_message(f"保存时长排序模式失败: {str(e)}")
        self._apply_duration_sorting()
    
    def _apply_duration_sorting(self):
        """根据下拉框选择对视频列表进行排序或分桶显示"""
        try:
            if not hasattr(self, 'video_list') or not hasattr(self, 'duration_sort_mode_combo'):
                return
            mode = self.duration_sort_mode_combo.currentText()
            # 收集当前所有视频项（忽略分组头）
            items = []
            for i in range(self.video_list.count()):
                item = self.video_list.item(i)
                if item.flags() & Qt.ItemIsUserCheckable:
                    items.append(item)
            if not items:
                return
            
            # 备份原始顺序（只生成一次）
            if not hasattr(self, '_original_video_order'):
                self._original_video_order = [it.data(Qt.UserRole) for it in items]
            
            # 构建 (video_path, item, duration_seconds, checked) 列表
            entries = []
            for it in items:
                vp = it.data(Qt.UserRole)
                checked = (it.checkState() == Qt.Checked)
                dur = self._ensure_video_duration(vp)
                entries.append((vp, it, dur, checked))
            
            def rebuild_from_order(ordered_entries, with_groups=False):
                # 重建列表，同时保持复选框状态
                self.video_list.clear()
                if with_groups:
                    # 定义分桶并收集
                    groups = {
                        '0-10s': [],
                        '10-30s': [],
                        '30-60s': [],
                        '1-2min': [],
                        '2-5min': [],
                        '5min+': []
                    }
                    for vp, _it, dur, checked in ordered_entries:
                        if dur is None or dur < 0:
                            group_key = '0-10s'
                        elif dur <= 10:
                            group_key = '0-10s'
                        elif dur <= 30:
                            group_key = '10-30s'
                        elif dur <= 60:
                            group_key = '30-60s'
                        elif dur <= 120:
                            group_key = '1-2min'
                        elif dur <= 300:
                            group_key = '2-5min'
                        else:
                            group_key = '5min+'
                        groups[group_key].append((vp, dur, checked))
                    
                    bucket_order = ['0-10s', '10-30s', '30-60s', '1-2min', '2-5min', '5min+']
                    for gkey in bucket_order:
                        if not groups[gkey]:
                            continue
                        header = self._create_group_header(gkey)
                        self.video_list.addItem(header)
                        for vp, dur, checked in groups[gkey]:
                            self._recreate_video_item(vp, checked)
                else:
                    for vp, _it, _dur, checked in ordered_entries:
                        self._recreate_video_item(vp, checked)
                # 刷新选择状态
                self._update_selection_status()
            
            if mode == '默认顺序':
                order_map = {vp: idx for idx, vp in enumerate(self._original_video_order)}
                ordered = sorted(entries, key=lambda x: order_map.get(x[0], 1e9))
                rebuild_from_order(ordered, with_groups=False)
            elif mode == '按时长升序':
                ordered = sorted(entries, key=lambda x: (float('inf') if (x[2] is None or x[2] < 0) else x[2], os.path.basename(x[0]).lower()))
                rebuild_from_order(ordered, with_groups=False)
            elif mode == '按时长降序':
                ordered = sorted(entries, key=lambda x: (-(x[2]) if (x[2] is not None and x[2] >= 0) else float('inf'), os.path.basename(x[0]).lower()))
                rebuild_from_order(ordered, with_groups=False)
            elif mode == '按时长分桶':
                ordered = sorted(entries, key=lambda x: (x[2] if x[2] is not None else float('inf')))
                rebuild_from_order(ordered, with_groups=True)
        except Exception as e:
            self._log_message(f"应用时长排序失败: {str(e)}")
    
    def _ensure_video_duration(self, video_path: str):
        """获取视频时长（秒），优先使用缓存，失败返回None"""
        if hasattr(self, 'video_durations') and video_path in self.video_durations:
            return self.video_durations.get(video_path)
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                cap.release()
                return None
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            dur = frame_count / fps if fps > 0 else 0
            cap.release()
            if hasattr(self, 'video_durations'):
                self.video_durations[video_path] = float(dur)
            return float(dur)
        except Exception:
            return None
    
    def _create_group_header(self, text: str) -> QListWidgetItem:
        """创建不可选择且不可勾选的分组头"""
        header = QListWidgetItem(text)
        f = header.font()
        f.setBold(True)
        header.setFont(f)
        header.setFlags(header.flags() & ~Qt.ItemIsUserCheckable & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
        return header
    
    def _recreate_video_item(self, video_path: str, checked: bool):
        """按现有样式重建视频项（保持复选框状态）"""
        item = QListWidgetItem()
        video_name = os.path.basename(video_path)
        if self._is_video_processed(video_path):
            item.setText(f"✅ {video_name}")
        else:
            item.setText(video_name)
        item.setData(Qt.UserRole, video_path)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.video_list.addItem(item)
    
    def _delete_selected_videos(self):
        """删除选中的视频"""
        selected_videos = self._get_selected_videos()
        
        if not selected_videos:
            QMessageBox.warning(self, "警告", "请先选择要删除的视频")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除选中的 {len(selected_videos)} 个视频吗？\n\n注意：这只会从列表中移除，不会删除实际文件。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 从后往前删除，避免索引变化问题
            for i in range(self.video_list.count() - 1, -1, -1):
                item = self.video_list.item(i)
                if item.checkState() == Qt.Checked:
                    video_path = item.data(Qt.UserRole)
                    # 从current_videos列表中移除
                    if video_path in self.current_videos:
                        self.current_videos.remove(video_path)
                    # 从列表控件中移除
                    self.video_list.takeItem(i)
            
            # 更新选择状态显示
            self._update_selection_status()
            
            self._log_message(f"已删除 {len(selected_videos)} 个视频")
            
            # 删除后根据模式应用排序/分桶
            if hasattr(self, 'duration_sort_mode_combo'):
                self._apply_duration_sorting()
    
    def _add_video_to_list(self, video_path):
        """添加视频到列表（带复选框）"""
        item = QListWidgetItem()
        
        # 检查是否已处理过
        if self._is_video_processed(video_path):
            item.setText(f"✅ {os.path.basename(video_path)}")
        else:
            item.setText(os.path.basename(video_path))
        
        item.setData(Qt.UserRole, video_path)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)  # 默认选中
        self.video_list.addItem(item)
        
        # 更新选择状态显示
        self._update_selection_status()
    
    def _is_video_processed(self, video_path):
        """检查视频是否已处理过"""
        # 检查是否有保存的结果文件
        result_file = self._get_result_file_path(video_path)
        return result_file.exists()
    
    def _ensure_cache_dir(self, video_path):
        """确保视频目录下的隐藏缓存目录存在并可写"""
        try:
            # 获取视频所在目录
            video_dir = Path(video_path).parent
            
            # 在视频目录下创建隐藏的缓存文件夹
            # 使用 .text2dance_cache 作为隐藏文件夹名称
            cache_dir = video_dir / ".text2dance_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建视频描述结果缓存目录
            result_cache_dir = cache_dir / "video_description_results"
            result_cache_dir.mkdir(parents=True, exist_ok=True)
            
            # 测试目录是否可写
            test_file = result_cache_dir / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            
            return result_cache_dir
        except Exception as e:
            self._log_message(f"创建视频目录下的隐藏缓存目录失败: {str(e)}")
            # 失败时返回临时目录
            temp_dir = Path(os.environ.get('TEMP', '/tmp')) / "text2dance_cache"
            temp_dir.mkdir(parents=True, exist_ok=True)
            return temp_dir
    
    def _get_length_text_english(self, chinese_text):
        """将中文描述长度转换为英文"""
        length_mapping = {
            "极短": "Extra Short",
            "短": "Short", 
            "中": "Medium",
            "长": "Long",
            "极长": "Extra Long"
        }
        return length_mapping.get(chinese_text, "Medium")
    
    def _get_user_result_file_path(self, video_path, model_type=None):
        """获取用户目录下的结果文件路径 - 保存到视频同名文件夹/description目录
        
        参数:
            video_path: 视频路径
            model_type: 模型类型，'api' 表示API模型，None或其他值表示本地模型
        """
        try:
            # 获取视频所在目录和视频名称
            video_dir = Path(video_path).parent
            video_name = Path(video_path).stem
            
            # 创建视频同名文件夹和description、pose子文件夹
            video_folder = video_dir / video_name
            description_folder = video_folder / "description"
            pose_folder = video_folder / "pose"  # 为未来功能预留
            
            # 确保目录存在
            description_folder.mkdir(parents=True, exist_ok=True)
            pose_folder.mkdir(parents=True, exist_ok=True)
            
            # 获取当前的描述长度等级，用于生成统一的文件名
            description_length_text = getattr(self, 'center_description_length_combo', None)
            if description_length_text and hasattr(description_length_text, 'currentText'):
                length_text = description_length_text.currentText()
            else:
                length_text = "中"  # 默认值
            
            # 转换为英文
            length_text_english = self._get_length_text_english(length_text)
            
            # 新的文件名格式：视频名称_描述长度.json
            return description_folder / f"{video_name}_{length_text_english}.json"
        except Exception as e:
            self._log_message(f"创建用户结果文件路径失败: {str(e)}")
            # 失败时返回缓存路径作为备用
            return self._get_result_file_path(video_path, model_type)

    def _get_result_file_path(self, video_path, model_type=None):
        """获取结果文件路径 - 使用视频目录下的隐藏缓存文件夹保存，避免污染视频目录
        
        参数:
            video_path: 视频路径
            model_type: 模型类型，'api' 表示API模型，None或其他值表示本地模型
        """
        # 确保视频目录下的隐藏缓存目录存在
        cache_dir = self._ensure_cache_dir(video_path)
        
        # 获取视频文件名（不含扩展名）
        video_name = Path(video_path).stem
        
        # 获取当前的描述长度等级，用于生成统一的文件名
        description_length_text = getattr(self, 'center_description_length_combo', None)
        if description_length_text and hasattr(description_length_text, 'currentText'):
            length_text = description_length_text.currentText()
        else:
            length_text = "中"  # 默认值
        
        # 转换为英文
        length_text_english = self._get_length_text_english(length_text)
        
        # 新的文件名格式：视频名称_描述长度.json
        return cache_dir / f"{video_name}_{length_text_english}.json"
    
    def _on_video_selected(self, item):
        """视频选中事件"""
        if item is None:
            return
        # 忽略分组头或不可勾选的项
        try:
            if not (item.flags() & Qt.ItemIsUserCheckable):
                return
        except Exception:
            pass
        
        video_path = item.data(Qt.UserRole)
        if not video_path:
            return
        
        # 播放视频
        self._play_video(video_path)
        
        # 显示结果（如果有）
        self._show_video_result(video_path)
    
    def _play_video(self, video_path):
        """加载视频（不自动播放）"""
        try:
            if not os.path.exists(video_path):
                self._log_message(f"视频文件不存在: {video_path}")
                return
            
            # 检查文件大小
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                self._log_message(f"视频文件为空: {video_path}")
                return
            
            # 停止当前播放
            self._stop_video()
            
            # 打开新视频
            self.video_capture = cv2.VideoCapture(video_path)
            if not self.video_capture.isOpened():
                self._log_message(f"无法打开视频文件: {video_path}")
                return
            
            # 获取视频信息
            self.current_video_path = video_path
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30  # 默认帧率
            
            # 设置进度条范围
            self.position_slider.setRange(0, self.total_frames - 1)
            self.current_frame = 0
            
            # 显示第一帧（不自动播放）
            self._show_frame(0)
            
            # 重置播放状态
            self.is_playing = False
            self.play_btn.setText("▶")
            
            self._log_message(f"成功加载视频: {os.path.basename(video_path)}")
            
        except Exception as e:
            self._log_message(f"播放视频时发生错误: {str(e)}")
            import traceback
            self._log_message(f"详细错误信息: {traceback.format_exc()}")
    
    def _switch_model_result(self, model_type):
        """切换显示不同模型的结果"""
        # 获取当前选中的视频
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择一个视频")
            return
        
        # 获取选中视频的路径
        video_path = selected_items[0].data(Qt.UserRole)
        
        # 检查指定模型类型的结果文件是否存在
        result_file = self._get_result_file_path(video_path, model_type=model_type)
        if not result_file.exists():
            QMessageBox.information(self, "提示", f"该视频没有{model_type}模型的处理结果")
            return
        
        # 显示指定模型类型的结果
        self._show_video_result(video_path, model_type=model_type)
        
        # 根据切换的模型类型更新UI状态
        if model_type == 'api':
            # 如果切换到API模型，获取当前选择的API模型名称并更新UI状态
            current_model = self.model_selection_combo.currentText()
            if "API" in current_model:
                self._update_model_ui_state(current_model)
        else:
            # 如果切换到本地模型，获取当前选择的本地模型名称并更新UI状态
            current_model = self.model_selection_combo.currentText()
            if "API" not in current_model:
                self._update_model_ui_state(current_model)
    
    def _show_video_result(self, video_path, model_type=None):
        """显示视频结果，可以指定显示本地模型或API模型的结果"""
        # 如果未指定模型类型，则尝试先加载本地模型结果，如果不存在则加载API模型结果
        if model_type is None:
            # 先尝试加载本地模型结果
            local_result_file = self._get_result_file_path(video_path, model_type='local')
            api_result_file = self._get_result_file_path(video_path, model_type='api')
            
            if local_result_file.exists():
                result_file = local_result_file
                model_type = 'local'
            elif api_result_file.exists():
                result_file = api_result_file
                model_type = 'api'
            else:
                # 兼容旧版本，尝试加载无模型类型的结果文件
                result_file = self._get_result_file_path(video_path)
        else:
            # 指定了模型类型，直接加载对应的结果文件
            result_file = self._get_result_file_path(video_path, model_type=model_type)
        
        if result_file.exists():
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                
                result_text = f"视频: {os.path.basename(video_path)}\n"
                
                # 显示生成日期时间
                generated_at = result.get('generated_at') or result.get('processed_at')
                if generated_at:
                    try:
                        from datetime import datetime
                        # 尝试解析时间戳
                        if isinstance(generated_at, (int, float)):
                            dt = datetime.fromtimestamp(generated_at)
                        else:
                            dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
                        result_text += f"生成时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    except:
                        result_text += f"生成时间: {generated_at}\n"
                else:
                    result_text += "生成时间: 未知\n"
                
                # 显示使用的模型
                model_name = result.get('model_name', '未知')
                result_text += f"使用模型: {model_name}\n"
                

                
                # 显示总耗时
                total_time = result.get('total_processing_time')
                if total_time is not None:
                    if total_time < 60:
                        time_str = f"{total_time:.1f} 秒"
                    elif total_time < 3600:
                        minutes = int(total_time // 60)
                        seconds = total_time % 60
                        time_str = f"{minutes} 分 {seconds:.1f} 秒"
                    else:
                        hours = int(total_time // 3600)
                        minutes = int((total_time % 3600) // 60)
                        seconds = total_time % 60
                        time_str = f"{hours} 小时 {minutes} 分 {seconds:.1f} 秒"
                    result_text += f"总耗时: {time_str}\n"
                else:
                    # 兼容旧格式
                    result_text += f"处理时间: {result.get('process_time', '未知')}\n"
                
                result_text += f"视频时长: {result.get('duration', '未知')}\n"
                result_text += f"处理状态: {'成功' if result.get('success', False) else '失败'}\n"
                
                if result.get('success', False):
                    result_text += f"\n描述内容:\n{result.get('description', '无')}"
                    
                    # 显示动作描述内容（如果存在）
                    action_description = result.get('action_description', '')
                    if action_description:
                        result_text += f"\n\n动作描述内容:\n{action_description}"
                    
                    # 显示是否过滤字段
                    action_filter_applied = result.get('action_filter_applied', False)
                    result_text += f"\n\n是否过滤处理: {'是' if action_filter_applied else '否'}"
                    
                    # 显示过滤更新时间（如果存在）
                    filter_updated_at = result.get('filter_updated_at', '')
                    if filter_updated_at:
                        result_text += f"\n过滤更新时间: {filter_updated_at}"
                else:
                    error_msg = result.get('error_message') or '无'
                    result_text += f"\n错误信息:\n{error_msg}"
                
                # 显示当前查看的模型类型
                if model_type:
                    result_text += f"\n\n当前显示: {'API模型' if model_type == 'api' else '本地模型'}结果"
                    
                    # 检查是否存在另一个模型的结果
                    other_model_type = 'local' if model_type == 'api' else 'api'
                    other_result_file = self._get_result_file_path(video_path, model_type=other_model_type)
                    
                    if other_result_file.exists():
                        result_text += f"\n提示: 该视频同时存在{'API模型' if other_model_type == 'api' else '本地模型'}的结果，可点击下方按钮切换查看"
            except Exception as e:
                import traceback
                result_text = f"读取结果文件失败: {str(e)}"
                self.logger.error(f"读取结果文件失败: {e}")
                self.logger.debug(f"读取结果文件失败详细信息: {traceback.format_exc()}")
                
            try:
                self.result_text.setPlainText(result_text)
            except Exception as e:
                import traceback
                self.result_text.setPlainText(f"读取结果文件失败: {str(e)}")
                self.logger.error(f"设置结果文本失败: {e}")
                self.logger.debug(f"设置结果文本失败详细信息: {traceback.format_exc()}")
        else:
            self.result_text.setPlainText("该视频尚未处理")
    
    def _toggle_playback(self):
        """切换播放状态"""
        # 防抖机制：检查是否在短时间内重复点击
        current_time = time.time()
        if hasattr(self, '_last_click_time') and (current_time - self._last_click_time) < 0.3:
            self._log_message("按钮点击过快，忽略此次点击")
            return
        self._last_click_time = current_time
        
        self._log_message(f"播放按钮被点击，当前状态: {'播放中' if self.is_playing else '暂停'}")
        
        if self.video_capture is None:
            self._log_message("错误：没有加载视频，请先选择一个视频")
            return
            
        if self.is_playing:
            self._pause_video()
            self._log_message("视频已暂停")
        else:
            self._start_playback()
            if self.is_playing:
                self._log_message("视频开始播放")
            else:
                self._log_message("播放失败")
    
    def _start_playback(self):
        """开始播放（使用动态帧率调整）"""
        if self.video_capture is not None and self.video_capture.isOpened():
            self.is_playing = True
            self.play_btn.setText("⏸")
            
            # 初始化动态帧率调整系统
            target_fps = self.fps * self.playback_speed
            self.pid_controller.set_target_fps(target_fps)
            self.pid_controller.reset()
            self.frame_rate_monitor.reset()
            
            # 计算基础播放间隔
            self.base_interval = int(1000 / self.fps / self.playback_speed)
            self.adaptive_interval = self.base_interval
            self.adjustment_counter = 0
            
            # 启动播放定时器
            self.play_timer.start(self.adaptive_interval)
            
            # 启动自适应调整定时器（如果启用）
            if self.enable_adaptive_playback:
                self.adaptive_timer.start()
            
            self._log_message(f"开始播放，视频FPS: {self.fps}, 目标FPS: {target_fps:.1f}, 播放速度: {self.playback_speed}x, 自适应播放: {'启用' if self.enable_adaptive_playback else '禁用'}")
        else:
            self._log_message("无法开始播放：视频未加载或已关闭")
            # 重置按钮状态
            self.is_playing = False
            self.play_btn.setText("▶")
    
    def _pause_video(self):
        """暂停播放"""
        self.is_playing = False
        self.play_btn.setText("▶")
        self.play_timer.stop()
        self.adaptive_timer.stop()
    
    def _stop_video(self):
        """停止播放"""
        self.is_playing = False
        self.play_btn.setText("▶")
        self.play_timer.stop()
        self.adaptive_timer.stop()
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
        self.current_frame = 0
        self.total_frames = 0
    
    def _update_frame(self):
        """更新帧显示（带帧率监控的顺序播放）"""
        if not self.is_playing or self.video_capture is None:
            return
        
        try:
            # 记录帧时间（用于帧率监控）
            if self.enable_adaptive_playback:
                self.frame_rate_monitor.record_frame()
            
            # 读取下一帧
            ret, frame = self.video_capture.read()
            if ret:
                self.current_frame += 1
                self._display_frame(frame)
                
                # 更新进度条（如果用户没有在拖动）
                if not self.is_slider_pressed:
                    self.position_slider.setValue(self.current_frame)
                
                # 更新时间显示
                self._update_time_display()
            else:
                # 播放完毕
                self._log_message("视频播放完毕")
                self._pause_video()
                self.current_frame = 0
                self._show_frame(0)
                
        except Exception as e:
            self._log_message(f"更新帧时发生错误: {str(e)}")
            self._pause_video()
    
    def _display_frame(self, frame):
        """显示帧"""
        try:
            # 转换颜色格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # 创建QImage
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 使用video_label当前可用尺寸进行缩放，保持宽高比
            label_size = self.video_label.size()
            display_width = max(1, label_size.width())
            display_height = max(1, label_size.height())
            
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                display_width, display_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
            # 显示图像
            self.video_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self._log_message(f"显示帧时发生错误: {str(e)}")
    
    def _show_frame(self, frame_number):
        """显示指定帧"""
        if self.video_capture is None:
            return
        
        try:
            # 设置帧位置
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.video_capture.read()
            
            if ret:
                self.current_frame = frame_number
                self._display_frame(frame)
                self._update_time_display()
            
        except Exception as e:
            self._log_message(f"显示帧时发生错误: {str(e)}")
    
    def _update_time_display(self):
        """更新时间显示"""
        if self.fps > 0:
            current_seconds = self.current_frame / self.fps
            total_seconds = self.total_frames / self.fps
            
            current_time = self._format_time(int(current_seconds * 1000))
            total_time = self._format_time(int(total_seconds * 1000))
            
            self.time_label.setText(f"{current_time} / {total_time}")
    

    
    def _set_position(self, position):
        """设置播放位置"""
        if self.video_capture is not None:
            self.current_frame = position
            self._show_frame(position)
    

    
    def _format_time(self, ms):
        """格式化时间"""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def _backward_10s(self):
        """后退10秒"""
        if self.video_capture is not None and self.fps > 0:
            frames_to_skip = int(10 * self.fps)  # 10秒对应的帧数
            new_frame = max(0, self.current_frame - frames_to_skip)
            self._show_frame(new_frame)
    
    def _forward_10s(self):
        """前进10秒"""
        if self.video_capture is not None and self.fps > 0:
            frames_to_skip = int(10 * self.fps)  # 10秒对应的帧数
            new_frame = min(self.total_frames - 1, self.current_frame + frames_to_skip)
            self._show_frame(new_frame)
    
    def _slider_pressed(self):
        """进度条按下"""
        self.is_slider_pressed = True
    
    def _slider_released(self):
        """进度条释放"""
        self.is_slider_pressed = False
        # 设置新位置
        if self.video_capture is not None:
            new_frame = self.position_slider.value()
            self._show_frame(new_frame)
    
    def _set_volume(self, volume):
        """设置音量"""
        # OpenCV不支持音频，这里只更新UI显示
        self.volume_label.setText(f"{volume}%")
        
        # 更新静音按钮状态
        if volume == 0:
            self.mute_btn.setText("🔇")
            self.is_muted = True
        else:
            self.mute_btn.setText("🔊")
            self.is_muted = False
    
    def _toggle_mute(self):
        """切换静音状态"""
        if self.is_muted:
            # 取消静音
            self.volume_slider.setValue(self.previous_volume)
            self.volume_label.setText(f"{self.previous_volume}%")
            self.mute_btn.setText("🔊")
            self.is_muted = False
        else:
            # 静音
            self.previous_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
            self.volume_label.setText("0%")
            self.mute_btn.setText("🔇")
            self.is_muted = True
    
    def _adaptive_playback_control(self):
        """自适应播放控制（PID控制器核心逻辑）"""
        if not self.is_playing or not self.enable_adaptive_playback:
            return
        
        try:
            # 获取测量的FPS
            measured_fps = self.frame_rate_monitor.get_measured_fps()
            
            if measured_fps <= 0:
                return  # 数据不足，跳过调整
            
            # 使用PID控制器计算调整值
            adjustment = self.pid_controller.update(measured_fps)
            
            # 计算新的播放间隔
            # adjustment为正值表示需要加快播放（减少间隔）
            # adjustment为负值表示需要减慢播放（增加间隔）
            new_interval = self.adaptive_interval - int(adjustment)
            
            # 限制调整范围（防止过度调整）
            min_interval = int(self.base_interval * 0.7)  # 最快不超过基础速度的1.43倍
            max_interval = int(self.base_interval * 1.5)  # 最慢不超过基础速度的0.67倍
            new_interval = max(min_interval, min(max_interval, new_interval))
            
            # 只有当间隔变化超过阈值时才调整（避免频繁微调）
            interval_change = abs(new_interval - self.adaptive_interval)
            if interval_change >= 2:  # 至少2毫秒的变化
                self.adaptive_interval = new_interval
                self.play_timer.setInterval(self.adaptive_interval)
                self.adjustment_counter += 1
                
                # 每10次调整记录一次日志（避免日志过多）
                if self.adjustment_counter % 10 == 0:
                    target_fps = self.pid_controller.target_fps
                    self._log_message(f"自适应调整 #{self.adjustment_counter}: 测量FPS={measured_fps:.1f}, 目标FPS={target_fps:.1f}, 新间隔={self.adaptive_interval}ms")
                    
        except Exception as e:
            self._log_message(f"自适应播放控制错误: {str(e)}")
    
    def _toggle_adaptive_playback(self, state):
        """切换自适应播放控制"""
        self.enable_adaptive_playback = state == Qt.Checked
        
        if self.enable_adaptive_playback:
            self._log_message("自适应播放控制已启用")
            # 如果正在播放，重新初始化自适应控制
            if self.is_playing and self.fps > 0:
                target_fps = self.fps * self.playback_speed
                self.pid_controller.set_target_fps(target_fps)
                self.frame_rate_monitor.reset()
                self.adaptive_timer.start(1000)  # 每秒调整一次
        else:
            self._log_message("自适应播放控制已禁用")
            # 停止自适应调整，回到传统模式
            self.adaptive_timer.stop()
            if self.is_playing and self.fps > 0:
                # 使用基础间隔
                self.play_timer.setInterval(self.base_interval)
    
    def _set_playback_rate(self, rate_text):
        """设置播放速度（支持动态帧率调整）"""
        try:
            rate = float(rate_text.replace('x', ''))
            self.playback_speed = rate
            
            # 如果正在播放，更新播放控制
            if self.is_playing and self.fps > 0:
                # 重新计算基础间隔
                self.base_interval = int(1000 / self.fps / self.playback_speed)
                self.adaptive_interval = self.base_interval
                
                if self.enable_adaptive_playback:
                    # 更新PID控制器的目标FPS
                    target_fps = self.fps * self.playback_speed
                    self.pid_controller.set_target_fps(target_fps)
                    # 重置帧率监控器
                    self.frame_rate_monitor.reset()
                    self._log_message(f"播放速度已设置为 {self.playback_speed}x，目标FPS: {target_fps:.1f}，基础间隔: {self.base_interval}ms")
                else:
                    # 传统模式：直接设置定时器间隔
                    self.play_timer.setInterval(self.base_interval)
                    self._log_message(f"播放速度已调整为 {self.playback_speed}x，定时器间隔: {self.base_interval}ms")
                
        except ValueError:
            pass  # 忽略无效的速度值
    
    def _start_description(self):
        """开始描述处理"""
        if not self.current_videos:
            QMessageBox.warning(self, "警告", "请先上传视频文件")
            return
        
        # 获取选中的视频
        selected_videos = self._get_selected_videos()
        if not selected_videos:
            QMessageBox.warning(self, "警告", "请至少选择一个视频进行处理")
            return
        
        description_requirement = self.description_text.toPlainText().strip()
        if not description_requirement:
            QMessageBox.warning(self, "警告", "请输入描述要求")
            return
        
        # 同步中间面板按钮状态
        if hasattr(self, 'center_start_btn'):
            self.center_start_btn.setEnabled(False)
        if hasattr(self, 'center_stop_btn'):
            self.center_stop_btn.setEnabled(True)
        
        # 清空日志
        if hasattr(self, 'log_text'):
            self.log_text.clear()
        if hasattr(self, 'center_progress_bar'):
            self.center_progress_bar.setValue(0)
        
        # 创建新的日志文件
        self._create_log_file()
        
        # 从中间面板获取参数
        # 获取生成模式
        generation_text = self.center_generation_mode_combo.currentText()
            
        if generation_text == "确定性生成":
            generation_mode = "deterministic"
        elif generation_text == "随机采样生成":
            generation_mode = "random"
        elif generation_text == "混合策略":
            generation_mode = "hybrid"
        else:
            generation_mode = "random"  # 默认值
        
        # 获取描述长度要求并转换为字符数
        # 获取描述长度等级
        description_length_text = self.center_description_length_combo.currentText()
        if description_length_text == "极短":
            description_length = 100
        elif description_length_text == "短":
            description_length = 200
        elif description_length_text == "中":
            description_length = 300
        elif description_length_text == "长":
            description_length = 500
        elif description_length_text == "极长":
            description_length = 800
        else:
            description_length = 300  # 默认值
        
        # 获取其他参数
        num_frames = self.center_num_frames_spinbox.value()
        top_p = self.top_p_spinbox.value()
        
        # 获取API配置
        api_config = self._get_api_config()
        
        # 获取设备设置
        device_setting = self.device_combo.currentText()
        
        # 获取多线程设置
        enable_multithread = self.multithread_checkbox.isChecked() and self.multithread_checkbox.isEnabled()
        thread_count = self.thread_count_spinbox.value()
        
        # 获取智能加载设置
        enable_smart_loading = self.smart_loading_checkbox.isChecked()
        enable_fast_preload = self.fast_preload_checkbox.isChecked()
        gpu_device = self.gpu_device_combo.currentText()
        
        # 获取GPU优化设置
        enable_gpu_optimization = False
        gpu_batch_size = 4
        gpu_max_workers = 2
        if hasattr(self, 'gpu_optimization_checkbox'):
            enable_gpu_optimization = self.gpu_optimization_checkbox.isChecked() and self.gpu_optimization_checkbox.isEnabled()
            gpu_batch_size = self.gpu_batch_size_spinbox.value()
            gpu_max_workers = self.gpu_max_workers_spinbox.value()
        
        # 根据当前选择的模型确定算法类型
        current_model = self.model_selection_combo.currentText()
        if current_model == "ShareVideoGPT4（本地模型）":
            algorithm_type = "本地模型"
        else:
            algorithm_type = "API调用"
        
        # 启动处理线程（只处理选中的视频）
        self.processing_thread = VideoDescriptionThread(
            selected_videos,
            description_requirement,
            self.model_path,
            self.action_filter_checkbox.isChecked(),
            generation_mode,
            description_length,
            num_frames,
            api_config,
            device_setting,
            enable_multithread,
            thread_count,
            top_p,
            algorithm_type,
            enable_gpu_optimization,
            gpu_batch_size,
            gpu_max_workers,
            enable_smart_loading,
            enable_fast_preload,
            gpu_device
        )
        
        if hasattr(self, 'center_progress_bar'):
            self.processing_thread.progress_updated.connect(self.center_progress_bar.setValue)
        self.processing_thread.status_updated.connect(self._log_message)
        self.processing_thread.log_updated.connect(self._log_message)
        self.processing_thread.video_completed.connect(self._on_video_completed)
        self.processing_thread.all_completed.connect(self._on_all_completed)
        
        self.processing_thread.start()
        
        self._log_message("开始处理视频描述...")
    
    def _stop_description(self):
        """停止描述处理"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self._log_message("用户取消处理")
            
            # 等待线程完全停止，最多等待10秒
            if not self.processing_thread.wait(10000):
                self._log_message("警告：线程未能正常停止，强制终止")
                self.processing_thread.terminate()
        
        # 关闭日志文件
        self._close_log_file()
        
        # 同步中间面板按钮状态
        if hasattr(self, 'center_start_btn'):
            self.center_start_btn.setEnabled(True)
        if hasattr(self, 'center_stop_btn'):
            self.center_stop_btn.setEnabled(False)
    
    def _on_video_completed(self, video_path, success, description, error_msg, total_processing_time, actual_timestamp):
        """视频处理完成 - 实时处理和保存"""
        video_name = os.path.basename(video_path)
        
        if success:
            self._log_message(f"✅ {video_name} 处理完成")
            
            # 获取当前使用的模型名称
            current_model = self.model_selection_combo.currentText()
            
            # 确定模型类型（本地或API）
            model_type = 'api' if hasattr(self.processing_thread, 'algorithm_type') and self.processing_thread.algorithm_type == "API调用" else 'local'
            
            # 保存原始结果 - 根据实际模型类型保存
            self._log_message(f"保存{model_type}模型结果")
            original_result = {
                'success': True,
                'description': description,
                'action_description': '',  # 初始化为空，稍后可能会被填充
                'error_message': '',
                'processed_at': actual_timestamp,  # 使用实际生成描述的时间
                'total_processing_time': total_processing_time,
                'duration': self._get_video_duration(video_path),
                'model_name': current_model,  # 添加使用的模型名称
                'generated_at': actual_timestamp,  # 添加生成时间（与processed_at相同，但语义更明确）
                'model_type': model_type,  # 明确标记模型类型
                'action_filter_applied': False  # 初始化为未应用过滤
            }
            self._save_video_result(video_path, original_result, model_type)
            
            # 实时API过滤（如果启用）
            filter_success = False
            if hasattr(self, 'use_action_filter') and self.use_action_filter and description:
                self._log_message(f"开始对 {video_name} 进行实时API过滤...")
                try:
                    filter_result = self._filter_action_description(description)
                    filtered_description = filter_result['description']
                    filter_success = filter_result['filter_success']
                    
                    # 保存过滤后的结果（使用api模型类型标识）
                    filtered_result = {
                        'success': True,
                        'description': description,  # 保留原始描述
                        'action_description': filtered_description,  # 保存过滤后的动作描述
                        'original_description': description,  # 保留原始描述（向后兼容）
                        'error_message': '',
                        'processed_at': actual_timestamp,
                        'total_processing_time': total_processing_time,
                        'duration': self._get_video_duration(video_path),
                        'model_name': current_model,
                        'generated_at': actual_timestamp,
                        'model_type': 'api',  # 标记为API过滤结果
                        'filter_applied': True,  # 标记已应用过滤
                        'action_filter_applied': filter_success  # 添加动作过滤成功标记
                    }
                    self._save_video_result(video_path, filtered_result, 'api')
                    if filter_success:
                        self._log_message(f"✅ {video_name} API过滤完成")
                        # 创建动作过滤成功标记文件
                        self._mark_action_filter_applied(video_path)
                    else:
                        self._log_message(f"⚠️ {video_name} API过滤未成功，使用原始描述")
                except Exception as e:
                    self._log_message(f"❌ {video_name} API过滤失败: {str(e)}")
            
            # 实时自动保存（如果启用）
            if self.auto_save_format_combo.currentText() != "关闭":
                self._log_message(f"开始对 {video_name} 进行实时自动保存...")
                try:
                    self._handle_auto_save_single_video(video_path)
                    self._log_message(f"✅ {video_name} 自动保存完成")
                except Exception as e:
                    self._log_message(f"❌ {video_name} 自动保存失败: {str(e)}")
            
            # 更新列表显示
            self._update_video_list_item(video_path, True)
            
            # 如果当前选中的视频就是刚处理完的视频，立即刷新结果显示
            current_item = self.video_list.currentItem()
            if current_item and current_item.data(Qt.UserRole) == video_path:
                self._show_video_result(video_path)
        else:
            self._log_message(f"❌ {video_name} 处理失败: {error_msg}")
            
            # 获取当前使用的模型名称
            current_model = self.model_selection_combo.currentText()
            
            # 确定模型类型（本地或API）
            model_type = 'api' if hasattr(self.processing_thread, 'algorithm_type') and self.processing_thread.algorithm_type == "API调用" else 'local'
            
            # 保存错误结果 - 根据实际模型类型保存
            self._log_message(f"保存{model_type}模型错误结果")
            self._save_video_result(video_path, {
                'success': False,
                'description': '',
                'error_message': error_msg,
                'processed_at': actual_timestamp,  # 使用实际处理的时间
                'total_processing_time': total_processing_time,
                'duration': self._get_video_duration(video_path),
                'model_name': current_model,  # 添加使用的模型名称
                'generated_at': actual_timestamp,  # 添加生成时间
                'model_type': model_type  # 明确标记模型类型
            }, model_type)
            
            # 更新列表显示
            self._update_video_list_item(video_path, False)
            
            # 如果当前选中的视频就是刚处理完的视频，立即刷新结果显示
            current_item = self.video_list.currentItem()
            if current_item and current_item.data(Qt.UserRole) == video_path:
                self._show_video_result(video_path)
    
    def _on_all_completed(self):
        """所有视频处理完成"""
        self._log_message("所有视频处理完成！")
        
        # 关闭日志文件
        self._close_log_file()
        
        # 统计总token消耗和获取账户余额（仅API调用模式）
        if hasattr(self.processing_thread, 'algorithm_type') and self.processing_thread.algorithm_type == "API调用":
            self._show_total_token_usage_and_balance()
        
        # 刷新视频列表状态显示
        self._refresh_video_list_status()
        
        # 同步中间面板按钮状态
        if hasattr(self, 'center_start_btn'):
            self.center_start_btn.setEnabled(True)
        if hasattr(self, 'center_stop_btn'):
            self.center_stop_btn.setEnabled(False)
        
        # 检查是否启用自动保存（注意：自动保存已在每个视频完成时实时执行，此处不再重复执行）
        # if self.auto_save_format_combo.currentText() != "关闭":
        #     self._handle_auto_save()
    
    def _show_total_token_usage_and_balance(self):
        """显示总token消耗和账户余额（蓝色字体）"""
        try:
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_tokens = 0
            latest_balance = None
            
            # 遍历所有处理结果，统计token使用量
            for result in getattr(self.processing_thread, 'results', []):
                token_usage = result.get('token_usage')
                if token_usage:
                    total_prompt_tokens += token_usage.get('prompt_tokens', 0)
                    total_completion_tokens += token_usage.get('completion_tokens', 0)
                    total_tokens += token_usage.get('total_tokens', 0)
                
                # 获取最新的账户余额
                account_balance = result.get('account_balance')
                if account_balance and account_balance != 'N/A':
                    latest_balance = account_balance
            
            # 如果有token使用量，显示统计信息
            if total_tokens > 0:
                # 使用普通格式显示
                token_msg = f"📊 本次运行总Token消耗: 输入{total_prompt_tokens}, 输出{total_completion_tokens}, 总计{total_tokens}"
                self._log_message(token_msg)
                
                # 显示账户余额
                if latest_balance:
                    balance_msg = f"💰 当前账户余额: {latest_balance}"
                    self._log_message(balance_msg)
                else:
                    balance_msg = f"💰 账户余额信息: 未提供"
                    self._log_message(balance_msg)
            
        except Exception as e:
            import traceback
            self._log_message(f"统计token使用量时发生错误: {str(e)}")
            self.logger.error(f"统计token使用量失败: {e}")
            self.logger.debug(f"统计token使用量失败详细信息: {traceback.format_exc()}")
    
    def _save_video_result(self, video_path, result, model_type=None):
        """保存视频结果 - 双重保存机制：同时保存到缓存目录和用户目录
        
        参数:
            video_path: 视频路径
            result: 结果数据
            model_type: 模型类型，'api' 表示API模型，None或其他值表示本地模型
        """
        try:
            # 处理描述内容中的换行符
            if 'description' in result and isinstance(result['description'], str):
                # 将描述文本中的 \n 转换为实际的换行符
                result['description'] = result['description'].replace('\\n', '\n')
            
            # 添加模型类型信息到结果中
            result['model_type'] = 'api' if model_type == 'api' else 'local'
            
            # 1. 保存到缓存目录（保持原有逻辑）
            cache_result_file = self._get_result_file_path(video_path, model_type)
            with open(cache_result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            # 2. 统一保存到用户目录（视频同名文件夹/description），不再区分模型类型
            user_result_file = self._get_user_result_file_path(video_path)
            
            # 如果文件已存在，合并模型信息到现有文件中
            if user_result_file.exists():
                try:
                    with open(user_result_file, 'r', encoding='utf-8') as f:
                        existing_result = json.load(f)
                    
                    # 合并模型结果，保留所有模型的信息
                    if model_type == 'api':
                        existing_result['api_model_result'] = result
                    else:
                        existing_result['local_model_result'] = result
                    
                    # 更新主要显示内容为当前模型结果
                    existing_result.update(result)
                    
                    with open(user_result_file, 'w', encoding='utf-8') as f:
                        json.dump(existing_result, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    # 如果合并失败，直接覆盖
                    with open(user_result_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
            else:
                # 新文件，直接保存
                with open(user_result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
            self._log_message(f"已保存{'API' if model_type == 'api' else '本地'}模型结果到统一文件")
            self._log_message(f"  缓存位置: {cache_result_file}")
            self._log_message(f"  用户位置: {user_result_file}")
        except Exception as e:
            self._log_message(f"保存结果失败: {str(e)}")
    
    def _update_video_list_item(self, video_path, success):
        """更新视频列表项显示（保持复选框状态）"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.data(Qt.UserRole) == video_path:
                # 保存当前复选框状态
                current_check_state = item.checkState()
                
                video_name = os.path.basename(video_path)
                display_text = ""
                if success:
                    display_text = f"✅ {video_name}"
                else:
                    display_text = f"❌ {video_name}"
                
                # 检查是否已应用动作过滤
                try:
                    if hasattr(self, '_check_action_filter_applied') and self._check_action_filter_applied(video_path):
                        display_text += " 🎯"
                except Exception as e:
                    self.logger.warning(f"检查动作过滤状态时出错: {e}")
                    # 继续执行，不影响主要功能
                
                item.setText(display_text)
                
                # 恢复复选框状态
                item.setCheckState(current_check_state)
                break
    
    def _refresh_video_list_status(self):
        """刷新视频列表状态显示（保持复选框状态）"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            video_path = item.data(Qt.UserRole)
            video_name = os.path.basename(video_path)
            
            # 保存当前复选框状态
            current_check_state = item.checkState()
            
            # 检查是否已处理过（检查本地模型和API模型的结果）
            local_result_file = self._get_result_file_path(video_path, model_type='local')
            api_result_file = self._get_result_file_path(video_path, model_type='api')
            legacy_result_file = self._get_result_file_path(video_path)  # 兼容旧版本
            
            # 初始化状态标记
            local_success = False
            api_success = False
            legacy_success = False
            
            # 检查本地模型结果
            if local_result_file.exists():
                try:
                    with open(local_result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    if result.get('success', False):
                        local_success = True
                except Exception as e:
                    self._log_message(f"读取本地模型结果文件失败: {str(e)}")
            
            # 检查API模型结果
            if api_result_file.exists():
                try:
                    with open(api_result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    if result.get('success', False):
                        api_success = True
                except Exception as e:
                    self._log_message(f"读取API模型结果文件失败: {str(e)}")
            
            # 检查旧版本结果（兼容性）
            if legacy_result_file.exists():
                try:
                    with open(legacy_result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    if result.get('success', False):
                        legacy_success = True
                except Exception as e:
                    self._log_message(f"读取旧版本结果文件失败: {str(e)}")
            
            # 检查是否已应用动作过滤
            action_filter_applied = False
            try:
                if hasattr(self, '_check_action_filter_applied'):
                    action_filter_applied = self._check_action_filter_applied(video_path)
            except Exception as e:
                self.logger.warning(f"检查动作过滤状态时出错: {e}")
                # 继续执行，不影响主要功能
            
            # 根据处理结果更新显示
            if local_success and api_success:
                display_text = f"✅✅ {video_name} [本地+API]"
            elif local_success:
                display_text = f"✅ {video_name} [本地]"
            elif api_success:
                display_text = f"✅ {video_name} [API]"
            elif legacy_success:
                display_text = f"✅ {video_name} [旧版]"
            else:
                # 检查是否有失败的结果
                has_result = local_result_file.exists() or api_result_file.exists() or legacy_result_file.exists()
                if has_result:
                    display_text = f"❌ {video_name}"
                else:
                    # 如果没有结果文件，显示未处理状态
                    if not item.text().startswith(("✅", "❌")):
                        display_text = video_name
                    else:
                        display_text = item.text()
            
            # 如果已应用动作过滤，添加特殊标记
            if action_filter_applied:
                display_text += " 🎯"
            
            item.setText(display_text)
            
            # 恢复复选框状态
            item.setCheckState(current_check_state)
    
    def _get_video_duration(self, video_path):
        """获取视频时长"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            return f"{duration:.2f}秒"
        except:
            return "未知"
    
    def _get_api_config(self):
        """获取动作过滤API配置"""
        try:
            from ..core.user_config_manager import get_user_config_manager
            config_manager = get_user_config_manager()
            
            # 获取动作过滤API配置
            action_filter_config = config_manager.get_api_config('action_filter')
            
            # 如果用户配置了完整的API信息，则使用用户配置
            if (action_filter_config.get('endpoint') and 
                action_filter_config.get('key') and 
                action_filter_config.get('model')):
                return {
                    'api_endpoint': action_filter_config['endpoint'],
                    'api_key': action_filter_config['key'],
                    'api_model': action_filter_config['model']
                }
            else:
                # 否则使用内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                    'api_model': 'doubao-seed-1-6-250615'
                }
        except Exception as e:
            self._log_message(f"获取动作过滤API配置失败: {e}")
            # 发生异常时返回内置配置
            return {
                'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                'api_model': 'doubao-seed-1-6-250615'
            }
    
    def _log_message(self, message):
        """记录日志消息"""
        # 检查log_text是否已初始化
        if not hasattr(self, 'log_text'):
            return
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)
        
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # 发送状态信号
        self.status_changed.emit(message)
    
    def _log_message_html(self, html_message):
        """记录HTML格式的日志消息（支持颜色和样式）"""
        # 检查log_text是否已初始化
        if not hasattr(self, 'log_text'):
            return
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"<span style='color: #666;'>[{timestamp}]</span> {html_message}"
        
        # 使用insertHtml来插入HTML格式的消息
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertHtml(formatted_message + "<br>")
        
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # 发送状态信号（去除HTML标签）
        import re
        plain_text = re.sub(r'<[^>]+>', '', html_message)
        self.status_changed.emit(plain_text)
    
    def _filter_action_description(self, description):
        """使用API过滤动作描述
        
        返回:
            dict: {
                'description': str,  # 过滤后的描述
                'filter_success': bool  # 是否成功应用了动作过滤
            }
        """
        try:
            # 获取动作过滤API配置
            filter_api_config = self._get_action_filter_api_config()
            if not filter_api_config or not filter_api_config.get('api_endpoint'):
                self._log_message("API配置不完整，跳过动作描述过滤")
                return {'description': description, 'filter_success': False}
            
            import requests
            import json
            
            # 构建API请求 - 使用配置的API密钥
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {filter_api_config["api_key"]}'
            }
            
            # 获取当前描述长度等级设置
            description_length_level = "中"  # 默认值
            try:
                if hasattr(self, 'center_description_length_combo'):
                    description_length_level = self.center_description_length_combo.currentText()
            except:
                pass
            
            # 根据长度等级设置相应的处理要求
            length_instruction = ""
            if description_length_level == "极短":
                length_instruction = "输出应该非常简洁，只保留最核心的动作描述，去除所有修饰词和细节。"
            elif description_length_level == "短":
                length_instruction = "输出应该简要，保留主要动作信息，适当简化描述。"
            elif description_length_level == "中":
                length_instruction = "输出应该保持适中长度，平衡详细度和简洁性。"
            elif description_length_level == "长":
                length_instruction = "输出应该详细，包含更多动作细节和描述。"
            elif description_length_level == "极长":
                length_instruction = "输出应该非常详细，全面分析所有动作，包含丰富的动作描述。"
            
            # 构建请求数据 - 先翻译再过滤动作描述，根据长度等级调整详细程度
            prompt = f"""请帮我处理这段话，严格按照以下要求：

1. 如果原文是英文，请先将其翻译为中文
2. 只保留与身体动作、姿态、运动相关的描述
3. 去除环境、背景、人物衣着、外貌、物品等与动作描述无关内容
4. 输出必须是完整的句子，包含明确的主语（如"男子"、"女子"、"运动员"、"舞者"等）
5. 保持自然的语言表达，按照{description_length_level}等级对动作描述进行缩写或者扩写，输出相应详细程度的内容
6. 不要添加任何原文中没有出现的动作的相关描述，除非原文中明确提到某个动作
7. 如果某句话包含动作和非动作内容，只需保留动作部分

当前描述长度等级：{description_length_level}

原文：
{description}

请直接输出过滤后的内容，不要添加任何解释或说明。"""
            
            data = {
                'model': filter_api_config['api_model'],
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 16384,
                'temperature': 0.1
            }
            
            self._log_message("正在调用API进行动作描述过滤...")
            
            # 发送API请求 - 使用配置的API端点，增加超时时间到120秒
            response = requests.post(
                filter_api_config['api_endpoint'],
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    filtered_description = result['choices'][0]['message']['content'].strip()
                    self._log_message("动作描述过滤完成")
                    return {'description': filtered_description, 'filter_success': True}
                else:
                    self._log_message("API响应格式异常，使用原始描述")
                    return {'description': description, 'filter_success': False}
            else:
                self._log_message(f"API调用失败 (状态码: {response.status_code})，使用原始描述")
                return {'description': description, 'filter_success': False}
                
        except Exception as e:
            self._log_message(f"动作描述过滤失败: {str(e)}，使用原始描述")
            return {'description': description, 'filter_success': False}
    
    def _get_action_filter_api_config(self):
        """获取动作过滤API配置"""
        try:
            # 使用绝对导入避免相对导入问题
            import sys
            import os
            
            # 添加项目根目录到路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            from src.core.user_config_manager import get_user_config_manager
            config_manager = get_user_config_manager()
            
            # 获取动作过滤API配置
            action_filter_config = config_manager.get_api_config('action_filter')
            
            # 如果用户配置了完整的API信息，则使用用户配置
            if (action_filter_config.get('endpoint') and 
                action_filter_config.get('key') and 
                action_filter_config.get('model')):
                return {
                    'api_endpoint': action_filter_config['endpoint'],
                    'api_key': action_filter_config['key'],
                    'api_model': action_filter_config['model']
                }
            else:
                # 否则使用内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                    'api_model': 'doubao-seed-1-6-250615'
                }
        except Exception as e:
            self._log_message(f"使用UserConfigManager加载配置失败，回退到直接文件读取: {e}")
            
            # 回退方案：直接读取配置文件
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                config_file = os.path.join(project_root, 'cache_config.txt')
                
                if os.path.exists(config_file):
                    # cache_config.txt是简单的key=value格式，不是INI格式
                    config_dict = {}
                    with open(config_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                config_dict[key.strip()] = value.strip()
                    
                    # 检查是否有action filter相关配置
                    if ('action_filter_api_endpoint' in config_dict and 
                        'action_filter_api_key' in config_dict and 
                        'action_filter_api_model' in config_dict):
                        return {
                            'api_endpoint': config_dict['action_filter_api_endpoint'],
                            'api_key': config_dict['action_filter_api_key'],
                            'api_model': config_dict['action_filter_api_model']
                        }
                
                # 如果配置文件读取失败或配置不完整，返回内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                    'api_model': 'doubao-seed-1-6-250615'
                }
                
            except Exception as fallback_error:
                self._log_message(f"配置文件读取也失败，使用默认配置: {fallback_error}")
                # 最终回退：返回内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
                    'api_model': 'doubao-seed-1-6-250615'
                }
    
    def _create_log_file(self):
        """创建新的日志文件"""
        try:
            # 确保logs文件夹存在
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            # 生成日志文件名（基于当前时间）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = f"video_description_{timestamp}.log"
            self.log_file_path = logs_dir / log_filename
            
            # 创建并打开日志文件
            self.log_file_handle = open(self.log_file_path, 'w', encoding='utf-8')
            
            # 写入文件头信息
            header = f"视频描述处理日志\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}\n"
            self.log_file_handle.write(header)
            self.log_file_handle.flush()
            
            self.log_monitoring_enabled = True
            
            # 记录日志文件创建信息
            self._log_message(f"日志文件已创建: {self.log_file_path}")
            
        except Exception as e:
            self._log_message(f"创建日志文件失败: {str(e)}")
    
    def _close_log_file(self):
        """关闭日志文件"""
        try:
            if self.log_file_handle:
                # 写入文件尾信息
                footer = f"\n{'='*50}\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                self.log_file_handle.write(footer)
                self.log_file_handle.close()
                self.log_file_handle = None
                
            self.log_monitoring_enabled = False
            
            if self.log_file_path:
                self._log_message(f"日志文件已保存: {self.log_file_path}")
                
        except Exception as e:
            print(f"关闭日志文件失败: {str(e)}")
    
    def _on_log_text_changed(self):
        """监听日志文本变化，实时写入文件"""
        if not self.log_monitoring_enabled or not self.log_file_handle:
            return
            
        try:
            # 获取当前日志文本的纯文本内容
            current_text = self.log_text.toPlainText()
            
            # 如果有新内容，写入文件
            if current_text:
                # 获取最后一行（新增的内容）
                lines = current_text.split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if last_line and not hasattr(self, '_last_logged_line'):
                        self._last_logged_line = ""
                    
                    # 只写入新的行
                    if last_line != getattr(self, '_last_logged_line', ''):
                        self.log_file_handle.write(last_line + '\n')
                        self.log_file_handle.flush()  # 立即刷新到磁盘
                        self._last_logged_line = last_line
                        
        except Exception as e:
            # 避免在日志写入过程中产生递归错误
            print(f"写入日志文件失败: {str(e)}")
    
    def _initialize_gpu_devices(self):
        """初始化GPU设备列表并进行自动检测"""
        try:
            # 导入torch来检测GPU
            import torch
            
            # 基础设备列表
            devices = ["自动检测", "cpu"]
            
            # 检测CUDA设备
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                self._log_message(f"🔍 GPU设备检测: 发现 {device_count} 个CUDA设备")
                
                for i in range(device_count):
                    device_name = torch.cuda.get_device_name(i)
                    device_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                    devices.append(f"cuda:{i}")
                    
                    # 记录详细的GPU信息到日志
                    self._log_message(f"  📱 GPU {i}: {device_name} ({device_memory:.1f}GB 显存)")
                    
                    # 检测GPU计算能力
                    try:
                        compute_capability = torch.cuda.get_device_capability(i)
                        self._log_message(f"    💻 计算能力: {compute_capability[0]}.{compute_capability[1]}")
                    except Exception as e:
                        self._log_message(f"    ⚠️ 无法获取计算能力信息: {str(e)}")
                
                # 显示当前CUDA版本信息
                cuda_version = torch.version.cuda
                if cuda_version:
                    self._log_message(f"  🔧 CUDA版本: {cuda_version}")
                
                # 显示推荐的GPU设备
                if device_count > 0:
                    # 选择显存最大的GPU作为推荐
                    best_gpu = 0
                    max_memory = 0
                    for i in range(device_count):
                        memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                        if memory > max_memory:
                            max_memory = memory
                            best_gpu = i
                    
                    self._log_message(f"  ✅ 推荐使用: cuda:{best_gpu} (显存最大: {max_memory:.1f}GB)")
            else:
                self._log_message("🔍 GPU设备检测: 未发现可用的CUDA设备，将使用CPU模式")
                
                # 检查是否安装了CUDA版本的PyTorch
                if hasattr(torch.version, 'cuda') and torch.version.cuda is None:
                    self._log_message("  ⚠️ 检测到CPU版本的PyTorch，如需GPU加速请安装CUDA版本")
            
            # 添加设备到下拉框
            self.gpu_device_combo.addItems(devices)
            
        except ImportError:
            # 如果无法导入torch，使用默认设备列表
            self._log_message("⚠️ 无法导入PyTorch，使用默认GPU设备列表")
            self.gpu_device_combo.addItems(["自动检测", "cuda:0", "cuda:1", "cpu"])
        except Exception as e:
            # 其他异常情况
            self._log_message(f"❌ GPU设备检测失败: {str(e)}")
            self.gpu_device_combo.addItems(["自动检测", "cuda:0", "cuda:1", "cpu"])
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止视频播放并释放资源
        self._stop_video()
        
        # 停止处理线程
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait()
        
        event.accept()
    
    def _export_results(self, format_type):
        """导出结果 - 每个视频单独导出到视频同名文件夹的description子目录"""
        if not self.current_videos:
            QMessageBox.warning(self, "警告", "没有可导出的结果")
            return
        
        # 获取选中的视频
        selected_videos = self._get_selected_videos()
        if not selected_videos:
            QMessageBox.warning(self, "警告", "请先选择要导出的视频")
            return
        
        try:
            exported_count = 0
            failed_count = 0
            
            # 为每个选中的视频单独导出
            for video_path in selected_videos:
                # 获取视频所在目录和视频名称
                video_dir = Path(video_path).parent
                video_name = Path(video_path).stem
                
                # 创建视频同名文件夹和description子文件夹
                video_folder = video_dir / video_name
                description_folder = video_folder / "description"
                pose_folder = video_folder / "pose"  # 为未来功能预留
                
                # 确保目录存在
                description_folder.mkdir(parents=True, exist_ok=True)
                pose_folder.mkdir(parents=True, exist_ok=True)
                
                # 检查处理结果文件（优先查找缓存文件，确保数据完整性）
                cache_result_file = self._get_result_file_path(video_path)
                user_result_file = self._get_user_result_file_path(video_path)
                
                result_file = None
                if cache_result_file.exists():
                    result_file = cache_result_file
                elif user_result_file.exists():
                    result_file = user_result_file
                
                # 导出统一的描述文件
                if result_file and result_file.exists():
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    
                    # 获取描述长度等级用于文件命名（转换为英文格式，与自动保存保持一致）
                    description_length_text = self.center_description_length_combo.currentText()
                    description_length_english = self._get_length_text_english(description_length_text)
                    
                    # 生成导出文件路径（统一格式，与自动保存命名一致）
                    if format_type == 'json':
                        export_file = description_folder / f"{video_name}_{description_length_english}.json"
                        self._export_single_video_json(result, video_path, export_file)
                    elif format_type == 'txt':
                        export_file = description_folder / f"{video_name}_{description_length_english}.txt"
                        self._export_single_video_txt(result, video_path, export_file)
                    elif format_type == 'csv':
                        export_file = description_folder / f"{video_name}_{description_length_english}.csv"
                        self._export_single_video_csv(result, video_path, export_file)
                    elif format_type == 'md':
                        export_file = description_folder / f"{video_name}_{description_length_english}.md"
                        self._export_single_video_md(result, video_path, export_file)
                    
                    exported_count += 1
                else:
                    failed_count += 1
                    self._log_message(f"未找到视频处理结果: {os.path.basename(video_path)}")
            
            # 显示导出结果
            if exported_count > 0:
                message = f"成功导出 {exported_count} 个视频的描述文件到各自的description文件夹"
                if failed_count > 0:
                    message += f"\n{failed_count} 个视频未找到处理结果"
                QMessageBox.information(self, "导出完成", message)
                self._log_message(f"导出完成: {exported_count} 成功, {failed_count} 失败")
            else:
                QMessageBox.warning(self, "导出失败", "没有找到任何处理结果")
            
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误: {str(e)}")
            self._log_message(f"导出失败: {str(e)}")
    
    def _export_single_video_json(self, result, video_path, export_file):
        """导出单个视频的JSON格式描述 - 保持原始格式"""
        # 直接使用原始结果格式，确保与读取逻辑兼容
        export_data = result.copy()  # 复制原始数据
        
        # 确保error_message字段正确处理None值
        if not export_data.get('success', False) and export_data.get('error_message') is None:
            export_data['error_message'] = '无'
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def _export_single_video_txt(self, result, video_path, export_file):
        """导出单个视频的TXT格式描述"""
        with open(export_file, 'w', encoding='utf-8') as f:
            f.write(f"视频名称: {os.path.basename(video_path)}\n")
            f.write(f"视频相对路径: {os.path.relpath(video_path, Path(video_path).parent)}\n")
            
            # 添加生成日期时间
            generated_at = result.get('generated_at') or result.get('processed_at')
            if generated_at:
                try:
                    from datetime import datetime
                    if isinstance(generated_at, (int, float)):
                        dt = datetime.fromtimestamp(generated_at)
                    else:
                        dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
                    f.write(f"生成时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
                except:
                    f.write(f"生成时间: {generated_at}\n")
            else:
                f.write("生成时间: 未知\n")
            
            # 添加使用的模型
            model_name = result.get('model_name', '未知')
            f.write(f"使用模型: {model_name}\n")
            

            
            f.write(f"视频时长: {result.get('duration', '未知')}\n")
            f.write(f"处理时长: {self._format_processing_time(result.get('total_processing_time'))}\n")
            f.write(f"处理状态: {'成功' if result.get('success', False) else '失败'}\n")
            f.write(f"设备信息: {result.get('device_info', '未知')}\n")
            f.write("-" * 50 + "\n")
            
            if result.get('success', False):
                f.write(f"视频描述:\n{result.get('description', '无')}\n")
            else:
                error_msg = result.get('error_message') or '无'
                f.write(f"错误信息:\n{error_msg}\n")
    
    def _export_single_video_csv(self, result, video_path, export_file):
        """导出单个视频的CSV格式描述"""
        import csv
        with open(export_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['字段', '值'])
            writer.writerow(['视频名称', os.path.basename(video_path)])
            writer.writerow(['视频相对路径', os.path.relpath(video_path, Path(video_path).parent)])
            
            # 添加生成日期时间
            generated_at = result.get('generated_at') or result.get('processed_at')
            if generated_at:
                try:
                    from datetime import datetime
                    if isinstance(generated_at, (int, float)):
                        dt = datetime.fromtimestamp(generated_at)
                    else:
                        dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
                    writer.writerow(['生成时间', dt.strftime('%Y-%m-%d %H:%M:%S')])
                except:
                    writer.writerow(['生成时间', generated_at])
            else:
                writer.writerow(['生成时间', '未知'])
            
            # 添加使用的模型
            model_name = result.get('model_name', '未知')
            writer.writerow(['使用模型', model_name])
            

            
            writer.writerow(['视频时长', result.get('duration', '未知')])
            writer.writerow(['处理时长', self._format_processing_time(result.get('total_processing_time'))])
            writer.writerow(['处理状态', '成功' if result.get('success', False) else '失败'])
            writer.writerow(['设备信息', result.get('device_info', '未知')])
            
            if result.get('success', False):
                writer.writerow(['视频描述', result.get('description', '无')])
            else:
                error_msg = result.get('error_message') or '无'
                writer.writerow(['错误信息', error_msg])
    
    def _export_single_video_md(self, result, video_path, export_file):
        """导出单个视频的Markdown格式描述"""
        with open(export_file, 'w', encoding='utf-8') as f:
            f.write(f"# {os.path.basename(video_path)} 视频描述\n\n")
            f.write("## 基本信息\n\n")
            f.write(f"- **视频名称**: {os.path.basename(video_path)}\n")
            f.write(f"- **视频相对路径**: {os.path.relpath(video_path, Path(video_path).parent)}\n")
            
            # 添加生成日期时间
            generated_at = result.get('generated_at') or result.get('processed_at')
            if generated_at:
                try:
                    from datetime import datetime
                    if isinstance(generated_at, (int, float)):
                        dt = datetime.fromtimestamp(generated_at)
                    else:
                        dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
                    f.write(f"- **生成时间**: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
                except:
                    f.write(f"- **生成时间**: {generated_at}\n")
            else:
                f.write("- **生成时间**: 未知\n")
            
            # 添加使用的模型
            model_name = result.get('model_name', '未知')
            f.write(f"- **使用模型**: {model_name}\n")
            

            
            f.write(f"- **视频时长**: {result.get('duration', '未知')}\n")
            f.write(f"- **处理时长**: {self._format_processing_time(result.get('total_processing_time'))}\n")
            f.write(f"- **处理状态**: {'成功' if result.get('success', False) else '失败'}\n")
            f.write(f"- **设备信息**: {result.get('device_info', '未知')}\n\n")
            
            if result.get('success', False):
                f.write("## 视频描述\n\n")
                f.write(f"{result.get('description', '无')}\n")
            else:
                f.write("## 错误信息\n\n")
                error_msg = result.get('error_message') or '无'
                f.write(f"{error_msg}\n")
    
    def _format_processing_time(self, total_time):
        """格式化处理时间"""
        if total_time is not None:
            if total_time < 60:
                return f"{total_time:.1f} 秒"
            elif total_time < 3600:
                minutes = int(total_time // 60)
                seconds = total_time % 60
                return f"{minutes} 分 {seconds:.1f} 秒"
            else:
                hours = int(total_time // 3600)
                minutes = int((total_time % 3600) // 60)
                seconds = total_time % 60
                return f"{hours} 小时 {minutes} 分 {seconds:.1f} 秒"
        return "未知"
            

    
    def _handle_auto_save_single_video(self, video_path):
        """处理单个视频的实时自动保存"""
        # 检查是否有处理结果
        result_file = self._get_result_file_path(video_path)
        if not result_file.exists():
            self._log_message(f"未找到视频处理结果: {os.path.basename(video_path)}")
            return
        
        # 读取处理结果
        with open(result_file, 'r', encoding='utf-8') as f:
            result = json.load(f)
        
        # 获取自动保存格式
        format_text = self.auto_save_format_combo.currentText()
        
        if format_text == "全部格式":
            # 保存所有格式
            formats = ["json", "txt", "csv", "md"]
            self._auto_save_single_video_all_formats(video_path, result, formats)
        else:
            # 保存指定格式
            format_map = {
                "JSON格式": "json",
                "TXT格式": "txt", 
                "CSV格式": "csv",
                "MD格式": "md"
            }
            selected_format = format_map.get(format_text, "json")
            self._auto_save_single_video_format(video_path, result, selected_format)
    
    def _auto_save_single_video_all_formats(self, video_path, result, formats):
        """为单个视频保存所有格式"""
        video_name = Path(video_path).stem
        video_dir = Path(video_path).parent
        
        # 创建视频同名文件夹和description子文件夹
        video_folder = video_dir / video_name
        description_folder = video_folder / "description"
        pose_folder = video_folder / "pose"  # 为未来功能预留
        
        # 确保目录存在
        description_folder.mkdir(parents=True, exist_ok=True)
        pose_folder.mkdir(parents=True, exist_ok=True)
        
        # 获取描述长度等级用于文件命名（转换为英文格式，与手动导出保持一致）
        description_length_text = self.center_description_length_combo.currentText()
        description_length_english = self._get_length_text_english(description_length_text)
        
        saved_count = 0
        format_names = {"json": "JSON", "txt": "TXT", "csv": "CSV", "md": "MD"}
        
        for format_type in formats:
            try:
                if format_type == 'json':
                    save_file = description_folder / f"{video_name}_{description_length_english}.json"
                    self._export_single_video_json(result, video_path, save_file)
                elif format_type == 'txt':
                    save_file = description_folder / f"{video_name}_{description_length_english}.txt"
                    self._export_single_video_txt(result, video_path, save_file)
                elif format_type == 'csv':
                    save_file = description_folder / f"{video_name}_{description_length_english}.csv"
                    self._export_single_video_csv(result, video_path, save_file)
                elif format_type == 'md':
                    save_file = description_folder / f"{video_name}_{description_length_english}.md"
                    self._export_single_video_md(result, video_path, save_file)
                
                saved_count += 1
            except Exception as e:
                self._log_message(f"保存{format_names[format_type]}格式失败 ({os.path.basename(video_path)}): {str(e)}")
        
        if saved_count > 0:
            self._log_message(f"视频 {os.path.basename(video_path)} 成功保存 {saved_count} 种格式到description文件夹")
    
    def _auto_save_single_video_format(self, video_path, result, format_type):
        """为单个视频保存指定格式"""
        video_name = Path(video_path).stem
        video_dir = Path(video_path).parent
        
        # 创建视频同名文件夹和description子文件夹
        video_folder = video_dir / video_name
        description_folder = video_folder / "description"
        pose_folder = video_folder / "pose"  # 为未来功能预留
        
        # 确保目录存在
        description_folder.mkdir(parents=True, exist_ok=True)
        pose_folder.mkdir(parents=True, exist_ok=True)
        
        # 获取描述长度等级用于文件命名（转换为英文格式，与手动导出保持一致）
        description_length_text = self.center_description_length_combo.currentText()
        description_length_english = self._get_length_text_english(description_length_text)
        
        try:
            if format_type == 'json':
                save_file = description_folder / f"{video_name}_{description_length_english}.json"
                self._export_single_video_json(result, video_path, save_file)
            elif format_type == 'txt':
                save_file = description_folder / f"{video_name}_{description_length_english}.txt"
                self._export_single_video_txt(result, video_path, save_file)
            elif format_type == 'csv':
                save_file = description_folder / f"{video_name}_{description_length_english}.csv"
                self._export_single_video_csv(result, video_path, save_file)
            elif format_type == 'md':
                save_file = description_folder / f"{video_name}_{description_length_english}.md"
                self._export_single_video_md(result, video_path, save_file)
            
            self._log_message(f"视频 {os.path.basename(video_path)} 成功保存{format_type.upper()}格式到description文件夹")
        except Exception as e:
            self._log_message(f"保存{format_type.upper()}格式失败 ({os.path.basename(video_path)}): {str(e)}")

    def _handle_auto_save(self):
        """处理自动保存功能 - 每个视频单独保存到视频所在目录"""
        if not self.current_videos:
            QMessageBox.warning(self, "警告", "没有可保存的结果")
            return
        
        # 获取选中的视频
        selected_videos = self._get_selected_videos()
        if not selected_videos:
            QMessageBox.warning(self, "警告", "请先选择要保存的视频")
            return
        
        try:
            # 根据下拉框选择确定格式
            format_text = self.auto_save_format_combo.currentText()
            
            if format_text == "全部格式":
                # 导出所有格式
                formats = ["json", "txt", "csv", "md"]
                self._auto_save_all_formats(formats, selected_videos)
            else:
                format_map = {
                    "JSON格式": "json",
                    "TXT格式": "txt", 
                    "CSV格式": "csv",
                    "MD格式": "md"
                }
                selected_format = format_map.get(format_text, "json")
                
                # 直接执行自动保存到各视频所在目录
                self._auto_save_results(selected_format, selected_videos)
            
        except Exception as e:
            QMessageBox.critical(self, "自动保存失败", f"自动保存过程中发生错误: {str(e)}")
    
    def _auto_save_all_formats(self, formats, selected_videos=None):
        """执行全部格式自动保存 - 每个视频保存所有格式到视频同名文件夹的description子目录"""
        try:
            # 如果没有指定选中视频，则使用所有视频
            videos_to_save = selected_videos if selected_videos is not None else self.current_videos
            
            total_saved_count = 0
            failed_videos = 0
            format_names = {"json": "JSON", "txt": "TXT", "csv": "CSV", "md": "MD"}
            
            for video_path in videos_to_save:
                if video_path in self.video_results:
                    result = self.video_results[video_path]
                    video_name = Path(video_path).stem
                    
                    # 创建description文件夹
                    video_dir = Path(video_path).parent
                    description_folder = video_dir / "description"
                    description_folder.mkdir(exist_ok=True)
                    
                    # 获取描述长度等级用于文件命名
                    description_length_text = self.center_description_length_combo.currentText()
                    length_suffix = f"-{description_length_text}长度描述" if description_length_text else ""
                    
                    video_saved_count = 0
                    for format_type in formats:
                        try:
                            if format_type == 'json':
                                save_file = description_folder / f"{video_name}{length_suffix}_description.json"
                                self._export_single_video_json(result, video_path, save_file)
                            elif format_type == 'txt':
                                save_file = description_folder / f"{video_name}{length_suffix}_description.txt"
                                self._export_single_video_txt(result, video_path, save_file)
                            elif format_type == 'csv':
                                save_file = description_folder / f"{video_name}{length_suffix}_description.csv"
                                self._export_single_video_csv(result, video_path, save_file)
                            elif format_type == 'md':
                                save_file = description_folder / f"{video_name}{length_suffix}_description.md"
                                self._export_single_video_md(result, video_path, save_file)
                            
                            video_saved_count += 1
                            total_saved_count += 1
                        except Exception as e:
                            self._log_message(f"保存{format_names[format_type]}格式失败 ({os.path.basename(video_path)}): {str(e)}")
                    
                    if video_saved_count > 0:
                        self._log_message(f"视频 {os.path.basename(video_path)} 成功保存 {video_saved_count} 种格式")
                    else:
                        failed_videos += 1
                else:
                    failed_videos += 1
                    self._log_message(f"未找到视频处理结果: {os.path.basename(video_path)}")
            
            # 显示保存结果
            if total_saved_count > 0:
                video_count = len(videos_to_save) - failed_videos
                message = f"成功为 {video_count} 个视频导出了全部格式文件（共 {total_saved_count} 个文件）到各自的description文件夹"
                if failed_videos > 0:
                    message += f"\n{failed_videos} 个视频未找到处理结果"
                QMessageBox.information(self, "全部格式自动保存完成", message)
                self._log_message(f"全部格式自动保存完成: {total_saved_count} 个文件成功, {failed_videos} 个视频失败")
            else:
                QMessageBox.warning(self, "自动保存失败", "没有找到任何处理结果")
            
        except Exception as e:
            QMessageBox.critical(self, "自动保存失败", f"自动保存过程中发生错误: {str(e)}")
            self._log_message(f"全部格式自动保存失败: {str(e)}")
    
    def _auto_save_results(self, format_type, selected_videos=None):
        """执行自动保存 - 每个视频单独保存到视频同名文件夹的description子目录"""
        try:
            # 如果没有指定选中视频，则使用所有视频
            videos_to_save = selected_videos if selected_videos is not None else self.current_videos
            
            saved_count = 0
            failed_count = 0
            
            # 为每个视频单独保存
            for video_path in videos_to_save:
                result_file = self._get_result_file_path(video_path)
                if result_file.exists():
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    
                    # 获取视频所在目录和视频名称
                    video_dir = Path(video_path).parent
                    video_name = Path(video_path).stem
                    
                    # 创建视频同名文件夹和description子文件夹
                    video_folder = video_dir / video_name
                    description_folder = video_folder / "description"
                    pose_folder = video_folder / "pose"  # 为未来功能预留
                    
                    # 确保目录存在
                    description_folder.mkdir(parents=True, exist_ok=True)
                    pose_folder.mkdir(parents=True, exist_ok=True)
                    
                    # 获取描述长度等级用于文件命名（转换为英文格式，与手动导出保持一致）
                    description_length_text = self.center_description_length_combo.currentText()
                    description_length_english = self._get_length_text_english(description_length_text)
                    
                    # 生成保存文件路径（保存到description文件夹中）
                    if format_type == 'json':
                        save_file = description_folder / f"{video_name}_{description_length_english}.json"
                        self._export_single_video_json(result, video_path, save_file)
                    elif format_type == 'txt':
                        save_file = description_folder / f"{video_name}_{description_length_english}.txt"
                        self._export_single_video_txt(result, video_path, save_file)
                    elif format_type == 'csv':
                        save_file = description_folder / f"{video_name}_{description_length_english}.csv"
                        self._export_single_video_csv(result, video_path, save_file)
                    elif format_type == 'md':
                        save_file = description_folder / f"{video_name}_{description_length_english}.md"
                        self._export_single_video_md(result, video_path, save_file)
                    
                    saved_count += 1
                else:
                    failed_count += 1
                    self._log_message(f"未找到视频处理结果: {os.path.basename(video_path)}")
            
            # 显示保存结果
            if saved_count > 0:
                message = f"成功自动保存 {saved_count} 个视频的描述文件到各自的description文件夹"
                if failed_count > 0:
                    message += f"\n{failed_count} 个视频未找到处理结果"
                QMessageBox.information(self, "自动保存完成", message)
                self._log_message(f"自动保存完成: {saved_count} 成功, {failed_count} 失败")
            else:
                QMessageBox.warning(self, "自动保存失败", "没有找到任何处理结果")
            
        except Exception as e:
            QMessageBox.critical(self, "自动保存失败", f"自动保存过程中发生错误: {str(e)}")
            self._log_message(f"自动保存失败: {str(e)}")
    
    def _on_auto_save_format_changed(self, text):
        """自动保存格式变化处理"""
        self._log_message(f"自动保存格式已更改为: {text}")
    
    def _sync_action_filter_to_center(self, state):
        """同步动作过滤到中间面板"""
        # 这里可以添加同步逻辑，目前暂时为空
        pass
    
    def _on_model_selection_changed(self, model_name):
        """模型选择变化处理"""
        if model_name == "添加API模型":
            dialog = CustomAPIDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                # 保存自定义模型配置
                custom_config = {
                    'endpoint': dialog.endpoint_edit.text(),
                    'api_key': dialog.api_key_edit.text(),
                    'model': dialog.model_name_edit.text(),
                    'display_name': dialog.display_name_edit.text()
                }
                self._save_custom_api_model(custom_config)
                # 添加到下拉框并选中
                self.model_selection_combo.addItem(custom_config['display_name'])
                self.model_selection_combo.setCurrentText(custom_config['display_name'])
            else:
                # 用户取消，恢复之前的选择
                self.model_selection_combo.setCurrentIndex(0)
                return
        
        # 更新UI状态和日志
        self._update_model_ui_state(model_name)
        self._log_message(f"已切换到模型: {model_name}")
        
        # 保存到配置
        self._save_model_selection(model_name)
    
    def _update_model_ui_state(self, model_name):
        """根据模型选择更新UI状态"""
        # 检查UI组件是否已初始化
        if not hasattr(self, 'api_config_group') or not hasattr(self, 'device_combo'):
            return
        
        # 判断是否为API模型（API模型名称中包含"API"字样）
        is_api_model = "API" in model_name
        is_local_model = not is_api_model
        
        # 记录当前使用的模型模式
        if is_api_model:
            self._log_message(f"当前使用API模型模式: {model_name}")
        else:
            self._log_message(f"当前使用本地模型模式: {model_name}")
        
        if is_local_model:
            # 本地模型：启用本地相关功能，隐藏API配置
            self.api_config_group.setVisible(False)
            self.device_combo.setEnabled(True)
            if hasattr(self, 'multithread_checkbox'):
                self.multithread_checkbox.setEnabled(True)
            if hasattr(self, 'thread_count_spinbox'):
                self.thread_count_spinbox.setEnabled(True)
            if hasattr(self, 'top_p_spinbox'):
                self.top_p_spinbox.setEnabled(True)
            if hasattr(self, 'center_generation_mode_combo'):
                self.center_generation_mode_combo.setEnabled(True)
            if hasattr(self, 'center_num_frames_spinbox'):
                self.center_num_frames_spinbox.setEnabled(True)
            
            # 恢复控件正常样式
            self.device_combo.setStyleSheet("")
            if hasattr(self, 'multithread_checkbox'):
                self.multithread_checkbox.setStyleSheet("")
            if hasattr(self, 'thread_count_spinbox'):
                self.thread_count_spinbox.setStyleSheet("")
            if hasattr(self, 'top_p_spinbox'):
                self.top_p_spinbox.setStyleSheet("")
            if hasattr(self, 'center_generation_mode_combo'):
                self.center_generation_mode_combo.setStyleSheet("")
            if hasattr(self, 'center_num_frames_spinbox'):
                self.center_num_frames_spinbox.setStyleSheet("")
        else:
            # API模型：保持本地功能可选，隐藏API配置（配置保存在文件中）
            self.api_config_group.setVisible(False)
            
            # 检查API是否可用，如果不可用则保持本地功能可选
            api_available = self._check_api_availability(model_name)
            
            if api_available:
                # API可用时禁用本地功能
                self.device_combo.setEnabled(False)
                if hasattr(self, 'multithread_checkbox'):
                    self.multithread_checkbox.setEnabled(False)
                if hasattr(self, 'thread_count_spinbox'):
                    self.thread_count_spinbox.setEnabled(False)
                if hasattr(self, 'top_p_spinbox'):
                    self.top_p_spinbox.setEnabled(False)
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setEnabled(False)
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setEnabled(False)
                
                # 设置禁用样式
                disabled_style = "color: #999; background-color: #f5f5f5;"
                self.device_combo.setStyleSheet(disabled_style)
                self.multithread_checkbox.setStyleSheet(disabled_style)
                self.thread_count_spinbox.setStyleSheet(disabled_style)
                self.top_p_spinbox.setStyleSheet(disabled_style)
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setStyleSheet(disabled_style)
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setStyleSheet(disabled_style)
            else:
                # API不可用时保持本地功能可选
                self._log_message(f"API模型 {model_name} 不可用，保持本地功能可选")
                # 恢复控件正常样式和状态
                self.device_combo.setEnabled(True)
                if hasattr(self, 'multithread_checkbox'):
                    self.multithread_checkbox.setEnabled(True)
                if hasattr(self, 'thread_count_spinbox'):
                    self.thread_count_spinbox.setEnabled(True)
                if hasattr(self, 'top_p_spinbox'):
                    self.top_p_spinbox.setEnabled(True)
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setEnabled(True)
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setEnabled(True)
            
            # 将API配置保存到配置文件中
            self._save_api_config_to_file(model_name)
    
    def _check_api_availability(self, model_name):
        """检查API模型是否可用
        
        Args:
            model_name: API模型名称
            
        Returns:
            bool: API是否可用
        """
        try:
            # 获取API配置
            api_endpoint = ""
            
            # 根据模型名称获取对应的API端点
            if model_name == "火山大模型①":
                api_endpoint = "ark.cn-beijing.volces.com"
            else:
                # 检查是否为自定义API模型
                if hasattr(self, 'config_manager') and self.config_manager:
                    custom_models = self.config_manager.get('algorithms.video_description.custom_api_models', [])
                    for custom_model in custom_models:
                        if custom_model.get('display_name') == model_name:
                            endpoint = custom_model.get('endpoint', '')
                            # 从URL中提取域名
                            import re
                            from urllib.parse import urlparse
                            if endpoint:
                                parsed_url = urlparse(endpoint)
                                api_endpoint = parsed_url.netloc
                            break
            
            # 如果没有找到API端点，默认检查常见的API服务器
            if not api_endpoint:
                api_endpoint = "api.openai.com"
            
            # 检查网络连接
            import socket
            try:
                # 尝试连接到API服务器域名
                self._log_message(f"正在检查API服务器 {api_endpoint} 的连接状态...")
                socket.create_connection((api_endpoint, 443), timeout=5)
                self._log_message(f"API服务器 {api_endpoint} 连接正常，API模型 {model_name} 可用")
                return True
            except (socket.timeout, socket.gaierror, ConnectionRefusedError) as e:
                self._log_message(f"无法连接到API服务器 {api_endpoint}，API模型 {model_name} 不可用: {str(e)}")
                return False
        except Exception as e:
            self._log_message(f"检查API可用性时出错: {str(e)}")
            return False
    
    def _save_api_config_to_file(self, model_name):
        """将API配置保存到配置文件中"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                # 根据模型名称设置API配置
                if model_name == "火山大模型①":
                    # 注意：这里只保存端点配置，视频描述API和动作描述过滤API使用不同的密钥和模型
                    # 视频描述API在请求时会强制使用正确的模型和密钥
                    api_config = {
                        'endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                        'api_key': 'fa1f2df2-73f8-44b1-99a0-09834047ab51',  # 视频描述API密钥
                        'model': 'doubao-1.5-vision-pro-250328'  # 视频描述专用模型
                    }
                else:
                    # 检查是否为自定义API模型
                    custom_models = self.config_manager.get('algorithms.video_description.custom_api_models', [])
                    api_config = None
                    for custom_model in custom_models:
                        if custom_model.get('display_name') == model_name:
                            api_config = {
                                'endpoint': custom_model.get('endpoint', ''),
                                'api_key': custom_model.get('api_key', ''),
                                'model': custom_model.get('model', '')
                            }
                            break
                    
                    if api_config is None:
                        return  # 未找到对应的模型配置
                
                # 保存API配置到配置管理器
                self.config_manager.set('algorithms.video_description.api_endpoint', api_config['endpoint'])
                self.config_manager.set('algorithms.video_description.api_key', api_config['api_key'])
                self.config_manager.set('algorithms.video_description.api_model', api_config['model'])
                self.config_manager.save_config()
                
                # 同时保存到cache_config.txt文件
                self._save_api_config_to_cache_file(api_config)
                
                self._log_message(f"已将{model_name}的API配置保存到配置文件")
                
        except Exception as e:
            self._log_message(f"保存API配置到文件失败: {str(e)}")
    
    def _set_api_config_for_model(self, model_name):
        """根据模型名称设置API配置（已废弃，配置直接保存到文件）"""
        # 此方法已废弃，API配置现在直接保存到配置文件中
        pass
    
    def _save_model_selection(self, model_name):
        """保存模型选择到配置"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                self.config_manager.set('algorithms.video_description.current_model', model_name)
                self.config_manager.save_config()
        except Exception as e:
            self._log_message(f"保存模型选择失败: {str(e)}")
    
    def _save_custom_api_model(self, custom_config):
        """保存自定义API模型配置"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                # 获取现有的自定义模型列表
                custom_models = self.config_manager.get('algorithms.video_description.custom_api_models', [])
                custom_models.append(custom_config)
                self.config_manager.set('algorithms.video_description.custom_api_models', custom_models)
                self.config_manager.save_config()
                self._log_message(f"已保存自定义API模型: {custom_config['display_name']}")
        except Exception as e:
            self._log_message(f"保存自定义API模型失败: {str(e)}")
    
    def _load_custom_models(self):
        """加载已保存的自定义API模型到组合框"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                # 获取已保存的自定义模型列表
                custom_models = self.config_manager.get('algorithms.video_description.custom_api_models', [])
                
                # 在"添加API模型"选项之前插入自定义模型
                insert_index = self.model_selection_combo.count() - 1  # "添加API模型"的索引
                
                for custom_model in custom_models:
                    display_name = custom_model.get('display_name', '未命名模型')
                    # 检查是否已经存在，避免重复添加
                    if self.model_selection_combo.findText(display_name) == -1:
                        self.model_selection_combo.insertItem(insert_index, display_name)
                        insert_index += 1
                        self._log_message(f"已加载自定义API模型: {display_name}")
                
                # 尝试恢复上次选择的模型
                current_model = self.config_manager.get('algorithms.video_description.current_model', 'ShareVideoGPT4（本地模型）')
                if self.model_selection_combo.findText(current_model) != -1:
                    self.model_selection_combo.setCurrentText(current_model)
                    self._log_message(f"已恢复模型选择: {current_model}")
                    
        except Exception as e:
            self._log_message(f"加载自定义API模型失败: {str(e)}")
    
    def _sync_model_selection_with_config(self):
        """确保模型选择组合框与配置文件中的模型预设保持同步"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager and hasattr(self, 'model_selection_combo'):
                # 从配置中读取模型预设
                algorithm_config = self.config_manager.get('algorithms', {})
                video_desc_config = algorithm_config.get('video_description', {})
                config_model = video_desc_config.get('model_preset', 'ShareVideoGPT4（本地模型）')
                
                # 检查配置中的模型是否在组合框中存在
                if self.model_selection_combo.findText(config_model) != -1:
                    # 如果存在且与当前选择不同，则更新组合框选择
                    current_model = self.model_selection_combo.currentText()
                    if current_model != config_model:
                        self.model_selection_combo.blockSignals(True)  # 阻止信号触发
                        self.model_selection_combo.setCurrentText(config_model)
                        self.model_selection_combo.blockSignals(False)  # 恢复信号
                        self._log_message(f"已同步模型选择: {config_model}")
                else:
                    # 如果配置中的模型不存在，则更新配置为当前选择的模型
                    current_model = self.model_selection_combo.currentText()
                    self.config_manager.set('algorithms.video_description.model_preset', current_model)
                    self.config_manager.save_config()
                    self._log_message(f"已更新配置中的模型预设: {current_model}")
                    
        except Exception as e:
            self._log_message(f"同步模型选择失败: {str(e)}")
    
    def _save_api_config_to_cache_file(self, api_config):
        """将API配置保存到配置文件"""
        try:
            from ..core.user_config_manager import get_user_config_manager
            config_manager = get_user_config_manager()
            
            # 保存API配置
            config_manager.set_api_config('custom', {
                'endpoint': api_config['endpoint'],
                'key': api_config['api_key'],
                'model': api_config['model']
            })
            
            self._log_message("已将API配置保存到配置文件")
            
        except Exception as e:
            self._log_message(f"保存API配置到配置文件失败: {str(e)}")
    
    def _on_config_changed(self, config: Dict[str, Any]):
        """处理配置变化"""
        try:
            # 检查是否是算法配置变化
            if 'algorithms' in config and 'video_description' in config['algorithms']:
                self._log_message("检测到视频描述配置变化，正在更新UI...")
                # 刷新UI状态
                self.refresh_ui_state()
        except Exception as e:
            self._log_message(f"处理配置变化失败: {str(e)}")
    
    def _show_refilter_dialog(self):
        """显示重新过滤对话框"""
        try:
            # 检查是否有选中的视频
            selected_videos = self._get_selected_videos()
            
            if not selected_videos:
                QMessageBox.warning(self, "提示", "请先选择要重新过滤的视频文件")
                return
            
            # 检查API配置
            if not self._validate_api_config():
                QMessageBox.warning(self, "配置错误", "请先配置API相关设置")
                return
            
            # 确认重新过滤
            reply = QMessageBox.question(
                self, 
                "确认重新过滤", 
                f"确定要对选中的 {len(selected_videos)} 个视频文件进行重新过滤吗？\n\n"
                f"这将读取视频同名文件夹中的描述文件，应用动作描述过滤，并更新描述文件。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 开始重新过滤处理
                self._start_refilter_process(selected_videos)
            
        except Exception as e:
            self._log_message(f"启动重新过滤失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"启动重新过滤失败: {str(e)}")
    
    def _start_refilter_process(self, selected_videos):
        """开始重新过滤处理"""
        try:
            # 检查API配置
            if not self._validate_api_config():
                QMessageBox.warning(self, "配置错误", "请先配置API相关设置")
                return
            
            # 创建重新过滤线程
            from .refilter_thread import RefilterThread
            self.refilter_thread = RefilterThread(selected_videos, self)
            self.refilter_thread.progress_updated.connect(self._update_refilter_progress)
            self.refilter_thread.file_processed.connect(self._on_refilter_file_processed)
            self.refilter_thread.finished.connect(self._on_refilter_finished)
            self.refilter_thread.error_occurred.connect(self._on_refilter_error)
            
            # 更新UI状态
            self.refilter_btn.setEnabled(False)
            self.center_start_btn.setEnabled(False)
            self.center_progress_bar.setValue(0)
            self.center_progress_bar.setMaximum(len(selected_videos))
            
            # 开始处理
            self.refilter_thread.start()
            self._log_message(f"开始重新过滤 {len(selected_videos)} 个视频的描述")
            
        except Exception as e:
            self._log_message(f"启动重新过滤失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"启动重新过滤失败: {str(e)}")
    
    def _update_refilter_progress(self, current, total):
        """更新重新过滤进度"""
        self.center_progress_bar.setValue(current)
        self.center_progress_bar.setFormat(f"重新过滤进度: {current}/{total}")
    
    def _on_refilter_file_processed(self, file_path, success, message):
        """处理单个文件重新过滤完成"""
        if success:
            self._log_message(f"✅ 重新过滤完成: {file_path}")
        else:
            self._log_message(f"❌ 重新过滤失败: {file_path} - {message}")
    
    def _on_refilter_finished(self):
        """重新过滤全部完成"""
        self.refilter_btn.setEnabled(True)
        self.center_start_btn.setEnabled(True)
        self.center_progress_bar.setValue(0)
        self.center_progress_bar.setFormat("")
        self._log_message("🎉 重新过滤处理完成")
        QMessageBox.information(self, "完成", "重新过滤处理已完成")
    
    def _on_refilter_error(self, error_message):
        """处理重新过滤错误"""
        self.refilter_btn.setEnabled(True)
        self.center_start_btn.setEnabled(True)
        self.center_progress_bar.setValue(0)
        self.center_progress_bar.setFormat("")
        self._log_message(f"❌ 重新过滤出错: {error_message}")
        QMessageBox.critical(self, "错误", f"重新过滤出错: {error_message}")
    
    def _validate_api_config(self):
        """验证API配置"""
        try:
            api_endpoint = self.api_endpoint_edit.text().strip()
            api_key = self.api_key_edit.text().strip()
            
            if not api_endpoint:
                return False
            if not api_key:
                return False
                
            return True
        except:
            return False