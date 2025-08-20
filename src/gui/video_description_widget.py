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

    def __init__(self, videos, description_requirement, model_path, use_action_filter=False, generation_mode="random", description_length=300, num_frames=16, api_config=None, device="Auto", enable_multithread=False, thread_count=2, top_p=0.9, algorithm_type="本地模型"):
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
        self.is_running = True
        self.results = []
    
    def stop(self):
        """停止处理线程"""
        self.is_running = False
        self.quit()
        self.wait()
    
    def run(self):
        try:
            total_videos = len(self.videos)
            
            # 根据算法类型选择处理方式
            if self.algorithm_type == "API调用":
                self.status_updated.emit(f"开始API处理 {total_videos} 个视频...")
                self.log_updated.emit("使用API调用模式进行视频描述")
                
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
                    self.status_updated.emit(f"开始多线程处理 {total_videos} 个视频，使用 {self.thread_count} 个线程...")
                    self.log_updated.emit(f"使用多线程处理模式 ({self.thread_count} 个线程并行处理)")
                else:
                    self.status_updated.emit(f"开始批量处理 {total_videos} 个视频...")
                    self.log_updated.emit("使用优化的批量处理模式 (1次模型加载 + N次推理)")
                
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
                    if is_success and self.use_action_filter and description:
                        description = self._filter_action_description(description)
                    
                    # 记录结果
                    processed_result = {
                        'video_path': video_path,
                        'success': is_success,
                        'description': description,
                        'error_message': error_msg,
                        'start_time': result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'end_time': result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'total_processing_time': round(processing_time, 2),
                        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': self._get_video_duration(video_path)
                    }
                    self.results.append(processed_result)
                    
                    # 发送完成信号，包含实际生成描述的时间戳
                    actual_timestamp = result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    self.video_completed.emit(video_path, is_success, description, error_msg, processing_time, actual_timestamp)
                    
                    # 更新进度
                    progress = int(((i + 1) / total_videos) * 100)
                    self.progress_updated.emit(progress)
                    
                    self.status_updated.emit(f"已完成 {i+1}/{total_videos}: {os.path.basename(video_path)}")
            else:
                self.status_updated.emit("批量处理失败")
                self.log_updated.emit("批量处理脚本执行失败")
            
            # 计算总耗时
            overall_end_time = time.time()
            total_time = overall_end_time - overall_start_time
            
            if self.is_running:
                self.log_updated.emit(f"批量处理完成，总耗时: {total_time:.2f}秒")
                self.log_updated.emit(f"平均每个视频: {total_time/total_videos:.2f}秒")
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
                            
                            # 更新进度
                            progress = int((completed_count / total_videos) * 100)
                            self.progress_updated.emit(progress)
                            
                            self.log_updated.emit(f"线程 {chunk_id} 完成，处理了 {len(chunk)} 个视频")
                            
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
                self.log_updated.emit(f"多线程处理完成，共处理 {len(all_results)} 个视频")
                return True, all_results
            else:
                self.log_updated.emit("多线程处理失败，没有获得任何结果")
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
            
            # 添加这组视频的路径
            cmd.extend(['--videos'] + video_chunk)
            
            # 根据描述长度要求动态设置max_new_tokens和更新提示词
            # 字符数转换为大致的token数（中文约1.5字符/token，英文约4字符/token）
            if self.description_length > 0:
                estimated_tokens = max(100, int(self.description_length * 0.8))  # 保守估计
                cmd.extend(['--max-new-tokens', str(estimated_tokens)])
            else:
                # 无限制生成，不设置max_new_tokens参数
                pass
            
            # 根据描述长度设置token限制和提示词
            if self.description_length > 0:
                # 在提示词中添加长度要求
                enhanced_query = f"{self.description_requirement} The total length of the description should be approximately {self.description_length} characters."
                cmd[cmd.index('--query') + 1] = enhanced_query
            # 如果是无限制模式，保持原始提示词不变
            
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
                            return True, results
                        else:
                            self.log_updated.emit(f"线程 {chunk_id} JSON中未找到results字段")
                            return False, []
                    else:
                        self.log_updated.emit(f"线程 {chunk_id} 未找到JSON输出")
                        return False, []
                        
                except json.JSONDecodeError as e:
                    self.log_updated.emit(f"线程 {chunk_id} JSON解析失败: {str(e)}")
                    # 创建备用结果
                    fallback_results = []
                    for video_path in video_chunk:
                        fallback_results.append({
                            'video_path': video_path,
                            'success': True,
                            'description': '处理完成，但无法获取详细描述内容（JSON解析失败）',
                            'error_message': '',
                            'processing_time': 0,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                    return True, fallback_results
            else:
                self.log_updated.emit(f"线程 {chunk_id} 处理失败，返回码: {process.returncode}")
                self.log_updated.emit(f"线程 {chunk_id} 错误输出: {output}")
                return False, []
                
        except Exception as e:
            self.log_updated.emit(f"线程 {chunk_id} 发生异常: {str(e)}")
            return False, []
    
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
            api_model = self.api_config.get('api_model', 'gpt-3.5-turbo')
            
            if not api_endpoint or not api_key:
                self.log_updated.emit("API配置不完整，请检查端点和密钥设置")
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
                    
                    # 构建消息内容
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
                        "max_tokens": 1000
                    }
                    
                    # 发送API请求
                    self.log_updated.emit(f"{video_name}: 发送API请求...")
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
                            
                            results.append({
                                'video_path': video_path,
                                'success': True,
                                'description': description,
                                'error_message': '',
                                'processing_time': processing_time,
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'token_usage': {
                                    'prompt_tokens': prompt_tokens,
                                    'completion_tokens': completion_tokens,
                                    'total_tokens': total_tokens
                                },
                                'account_balance': remaining_balance
                            })
                        else:
                            error_msg = "API返回空描述"
                            self.log_updated.emit(f"{video_name}: {error_msg}")
                            results.append({
                                'video_path': video_path,
                                'success': False,
                                'description': '',
                                'error_message': error_msg,
                                'processing_time': 0,
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    else:
                        error_msg = f"API请求失败: {response.status_code} - {response.text}"
                        self.log_updated.emit(f"{video_name}: {error_msg}")
                        results.append({
                            'video_path': video_path,
                            'success': False,
                            'description': '',
                            'error_message': error_msg,
                            'processing_time': 0,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                
                except Exception as e:
                    error_msg = f"处理异常: {str(e)}"
                    self.log_updated.emit(f"{video_name}: {error_msg}")
                    results.append({
                        'video_path': video_path,
                        'success': False,
                        'description': '',
                        'error_message': error_msg,
                        'processing_time': 0,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                # 更新进度
                progress = int(((i + 1) / total_videos) * 100)
                self.progress_updated.emit(progress)
            
            self.log_updated.emit(f"API处理完成，共处理 {len(results)} 个视频")
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
            
            # 添加所有视频路径
            cmd.extend(['--videos'] + self.videos)
            
            # 根据描述长度要求动态设置max_new_tokens和更新提示词
            # 字符数转换为大致的token数（中文约1.5字符/token，英文约4字符/token）
            if self.description_length > 0:
                estimated_tokens = max(100, int(self.description_length * 0.8))  # 保守估计
                cmd.extend(['--max-new-tokens', str(estimated_tokens)])
                self.log_updated.emit(f"根据描述长度要求({self.description_length}字符)设置最大生成长度: {estimated_tokens} tokens")
                
                # 在提示词中添加长度要求
                enhanced_query = f"{self.description_requirement} The total length of the description should be approximately {self.description_length} characters."
                cmd[cmd.index('--query') + 1] = enhanced_query
                self.log_updated.emit(f"已在提示词中添加长度要求: {self.description_length}字符")
            else:
                # 无限制生成，不设置max_new_tokens参数，也不在提示词中添加长度限制
                self.log_updated.emit("设置为无限制生成模式，不限制输出长度")
            
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
            
            output_lines = []
            self.log_updated.emit("开始读取批量处理输出...")
            
            # 实时读取输出
            while True:
                if not self.is_running:
                    process.terminate()
                    self.log_updated.emit("用户取消批量处理")
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
            
            # 检查进程返回码
            if process.returncode == 0:
                # 尝试从输出中提取JSON结果
                json_output = None
                json_start = -1
                
                # 查找JSON输出的开始位置
                for i, line in enumerate(output_lines):
                    if line.strip().startswith('{'):
                        json_start = i
                        break
                
                if json_start != -1:
                    # 提取JSON部分
                    json_lines = output_lines[json_start:]
                    json_text = '\n'.join(json_lines)
                    
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
                            self.log_updated.emit(f"原始输出: {json_text[:500]}...")
                            
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
                    return False, []
            else:
                error_msg = '\n'.join(output_lines) if output_lines else "未知错误"
                self.log_updated.emit(f"批量处理命令执行失败: {error_msg}")
                return False, []
                
        except Exception as e:
            error_msg = f"批量处理时发生异常: {str(e)}"
            self.log_updated.emit(error_msg)
            return False, []
    
    def _filter_action_description(self, description):
        """使用API过滤动作描述"""
        try:
            if not self.api_config or not self.api_config.get('api_endpoint') or not self.api_config.get('api_key'):
                self.log_updated.emit("API配置不完整，跳过动作描述过滤")
                return description
            
            import requests
            import json
            
            # 构建API请求
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_config.get("api_key")}'
            }
            
            # 构建请求数据
            prompt = f"帮我处理这段话，只保留动作描述，去除环境、人物衣着相关内容，并且不润色，保证原文：\n\n{description}"
            
            data = {
                'model': self.api_config.get('api_model', 'gpt-3.5-turbo'),
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 1000,
                'temperature': 0.1
            }
            
            self.log_updated.emit("正在调用API进行动作描述过滤...")
            
            # 发送API请求
            response = requests.post(
                self.api_config.get('api_endpoint'),
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    filtered_description = result['choices'][0]['message']['content'].strip()
                    self.log_updated.emit("动作描述过滤完成")
                    return filtered_description
                else:
                    self.log_updated.emit("API响应格式异常，使用原始描述")
                    return description
            else:
                self.log_updated.emit(f"API调用失败 (状态码: {response.status_code})，使用原始描述")
                return description
                
        except Exception as e:
            self.log_updated.emit(f"动作描述过滤失败: {str(e)}，使用原始描述")
            return description
    
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
        self.video_results = {}  # 存储视频处理结果
        self.processing_thread = None
        self.is_all_selected = False  # 全选状态标记
        
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
        
        # 根据配置更新UI状态
        self._update_ui_based_on_algorithm_type()
        
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
        
        # 设置固定宽度，防止布局变化
        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(350)
        center_panel.setMinimumWidth(450)
        center_panel.setMaximumWidth(650)
        right_panel.setMinimumWidth(400)
        
        # 添加到主布局，使用固定比例
        main_layout.addWidget(left_panel, 0)  # 固定宽度
        main_layout.addWidget(center_panel, 0)  # 固定宽度
        main_layout.addWidget(right_panel, 1)  # 可伸缩
    
    def _create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 文件上传区域
        upload_group = QGroupBox("视频上传")
        upload_layout = QVBoxLayout(upload_group)
        
        # 上传按钮
        upload_buttons_layout = QHBoxLayout()
        
        self.upload_file_btn = QPushButton("上传视频文件")
        self.upload_file_btn.clicked.connect(self._upload_video_files)
        upload_buttons_layout.addWidget(self.upload_file_btn)
        
        self.upload_folder_btn = QPushButton("上传文件夹")
        self.upload_folder_btn.clicked.connect(self._upload_video_folder)
        upload_buttons_layout.addWidget(self.upload_folder_btn)
        
        upload_layout.addLayout(upload_buttons_layout)
        
        # 视频列表控制区域
        list_control_layout = QHBoxLayout()
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
                font-size: 12px;
                margin-left: 5px;
            }
        """)
        self.selection_status_label.setAlignment(Qt.AlignVCenter)  # 垂直居中对齐
        list_control_layout.addWidget(self.selection_status_label)
        
        list_control_layout.addStretch()
        upload_layout.addLayout(list_control_layout)
        
        # 视频列表（支持复选框）
        self.video_list = QListWidget()
        self.video_list.setMinimumHeight(240)  # 减小高度为状态标签留出空间
        self.video_list.setMaximumHeight(240)  # 设置最大高度，确保不会过度扩展
        self.video_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)
        self.video_list.itemClicked.connect(self._on_video_selected)
        self.video_list.itemChanged.connect(self._on_video_check_changed)
        upload_layout.addWidget(self.video_list)
        
        # 添加间距
        upload_layout.addSpacing(15)
        
        layout.addWidget(upload_group)
        
        # 描述要求区域
        desc_group = QGroupBox("描述要求")
        desc_layout = QVBoxLayout(desc_group)
        
        self.description_text = QTextEdit()
        self.description_text.setMaximumHeight(150)
        # 设置默认描述要求
        default_desc = "Begin by providing a general overview of the person's current action (e.g., walking, sitting, interacting) visible in the video footage. Then proceed with a detailed analysis focusing specifically on the physical movements and body positioning within the video frame. For the upper body, describe the position and movement patterns of the arms, hands, shoulders and torso. For the lower body, detail the positioning and motion of the legs, feet and overall balance dynamics. The description must remain strictly focused on observable physical actions, deliberately excluding any mention of facial expressions, clothing details or environmental elements outside the video frame boundaries."
        self.description_text.setPlainText(default_desc)
        self.description_text.setStyleSheet("color: #888888;")  # 淡灰色
        desc_layout.addWidget(self.description_text)
        
        layout.addWidget(desc_group)
        
        # 功能选项区域
        options_group = QGroupBox("功能选项")
        options_layout = QVBoxLayout(options_group)
        
        # 算法类型从配置中读取，不再显示选择控件
        
        # 功能选项 - 使用网格布局实现一行两列
        options_grid = QGridLayout()
        
        # 第一行：只保留动作描述 和 自适应播放控制
        self.action_filter_checkbox = QCheckBox("只保留动作描述")
        self.action_filter_checkbox.setToolTip("过滤掉场景、物体等描述，专注于人物动作和行为分析")
        self.action_filter_checkbox.stateChanged.connect(self._sync_action_filter_to_center)
        options_grid.addWidget(self.action_filter_checkbox, 0, 0)
        
        self.adaptive_playback_checkbox = QCheckBox("启用自适应播放控制")
        self.adaptive_playback_checkbox.setToolTip("使用PID控制器动态调整播放帧率，提供更平滑的播放体验")
        self.adaptive_playback_checkbox.setChecked(True)  # 默认启用
        self.adaptive_playback_checkbox.stateChanged.connect(self._toggle_adaptive_playback)
        options_grid.addWidget(self.adaptive_playback_checkbox, 0, 1)
        
        # 第二行：模型选择功能（与计算设备对齐）
        model_label = QLabel("选择模型:")
        options_grid.addWidget(model_label, 1, 0)
        
        self.model_selection_combo = QComboBox()
        self.model_selection_combo.addItems([
            "ShareVideoGPT4（本地模型）",
            "火山大模型①", 
            "添加API模型"
        ])
        self.model_selection_combo.setCurrentText("ShareVideoGPT4（本地模型）")  # 默认选择本地模型
        self.model_selection_combo.setToolTip("选择用于视频描述的AI模型")
        self.model_selection_combo.currentTextChanged.connect(self._on_model_selection_changed)
        options_grid.addWidget(self.model_selection_combo, 1, 1)
        
        # 加载已保存的自定义API模型
        self._load_custom_models()
        
        options_layout.addLayout(options_grid)
        
        # 计算设备选择和采样参数（同一行）
        device_layout = QHBoxLayout()
        device_label = QLabel("计算设备:")
        device_layout.addWidget(device_label)
        
        self.device_combo = QComboBox()
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
        
        # 添加间距
        device_layout.addSpacing(50)
        
        # Top-p参数控制（与计算设备同一行，但在第二列位置）
        top_p_label = QLabel("采样参数:")
        device_layout.addWidget(top_p_label)
        
        self.top_p_spinbox = QDoubleSpinBox()
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
        device_layout.addWidget(self.top_p_spinbox)
        
        device_layout.addStretch()
        options_layout.addLayout(device_layout)
        
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
        self.api_key_edit.setText("fa1f2df2-73f8-44b1-99a0-09834047ab51")
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
        
        # 多线程处理选项
        multithread_layout = QHBoxLayout()
        
        self.multithread_checkbox = QCheckBox("启用多线程处理")
        self.multithread_checkbox.setToolTip(
            "启用多线程处理可以同时处理多个视频，提高处理效率\n"
            "注意：仅在使用CUDA或Auto设备时可用，CPU模式不支持多线程"
        )
        multithread_layout.addWidget(self.multithread_checkbox)
        
        # 线程数量选择
        thread_label = QLabel("线程数量:")
        multithread_layout.addWidget(thread_label)
        
        self.thread_count_spinbox = QSpinBox()
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
        options_layout.addLayout(multithread_layout)
        
        # 初始化多线程选项状态
        self._on_device_changed()
        
        layout.addWidget(options_group)
        
        # 参数说明区域（添加滚动功能）
        info_group = QGroupBox("参数说明")
        info_layout = QVBoxLayout(info_group)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumHeight(120)  # 减小最小高度
        scroll_area.setMaximumHeight(250)  # 减小最大高度
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # 详细参数说明
        mode_info = QLabel(
            "<b>🎯 生成模式类型：</b><br>"
            "• <b>确定性生成</b>：每次运行结果完全一致，输出稳定可重复，适合需要一致性的场景<br>"
            "• <b>随机采样生成</b>：每次运行结果略有不同，输出更有创造性和多样性<br>"
            "• <b>混合策略</b>：结合确定性和随机性，平衡稳定性与创造性<br><br>"
            
            "<b>📊 采样帧数设置：</b><br>"
            "控制从视频中提取的关键帧数量，直接影响描述的详细程度和处理时间：<br>"
            "• <b>自动模式（推荐）</b>：根据视频长度智能选择最佳帧数<br>"
            "  - ≤10秒视频：16帧（快速处理，适合短片段）<br>"
            "  - 10-30秒视频：20帧（平衡质量与速度）<br>"
            "  - 30-60秒视频：25帧（详细分析，适合中长视频）<br>"
            "  - >60秒视频：32帧（全面覆盖，适合长视频）<br>"
            "• <b>手动设置</b>：推荐范围8-32帧，帧数越多描述越详细但处理时间越长<br><br>"
            
            "<b>📝 最大生成长度：</b><br>"
            "控制AI生成描述的详细程度和文本长度：<br>"
            "• <b>无限制（0）</b>：允许生成任意长度的描述，适合需要详尽分析的场景<br>"
            "• <b>限制模式</b>：推荐100-500个token，确保描述简洁精准<br>"
            "• 较短设置（100-200）适合快速概览，较长设置（300-500）适合详细分析<br><br>"
            
            "<b>⚡ 功能选项说明：</b><br>"
            "• <b>启用自动保存</b>：自动保存视频列表的输出内容到文件，支持多种格式<br>"
            "  处理完成后会自动保存结果，无需手动操作<br>"
            "• <b>用户选择格式</b>：允许用户选择保存文件的格式（JSON、TXT、CSV、MD等）<br>"
            "  启用后会在处理结束时弹出格式选择对话框<br>"
            "• <b>启用导出功能</b>：提供手动导出功能，可随时导出处理结果<br>"
            "• <b>自适应播放控制</b>：使用PID控制器动态调整播放帧率，提供更平滑的播放体验<br><br>"
            
            "<b>💡 使用建议：</b><br>"
            "• 首次使用建议开启所有功能选项，熟悉后可根据需要调整<br>"
            "• 对于重要视频建议启用备份功能<br>"
            "• 批量处理时建议使用确定性生成模式以保持一致性<br>"
            "• 处理长视频时可适当增加采样帧数以获得更全面的描述"
        )
        mode_info.setWordWrap(True)
        mode_info.setStyleSheet(
            "QLabel {"
            "    background-color: #f8f9fa;"
            "    border: 1px solid #dee2e6;"
            "    border-radius: 5px;"
            "    padding: 15px;"
            "    font-size: 12px;"
            "    line-height: 1.5;"
            "}"
        )
        scroll_layout.addWidget(mode_info)
        
        # 设置滚动区域内容
        scroll_area.setWidget(scroll_content)
        info_layout.addWidget(scroll_area)
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        return panel
    
    def _create_center_panel(self):
        """创建中间面板（视频播放）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 视频播放区域
        video_group = QGroupBox("视频播放")
        video_layout = QVBoxLayout(video_group)
        
        # 视频显示标签
        self.video_label = QLabel()
        self.video_label.setMinimumHeight(300)
        self.video_label.setMaximumHeight(400)  # 设置最大高度
        self.video_label.setMinimumWidth(400)
        self.video_label.setMaximumWidth(600)   # 设置最大宽度
        self.video_label.setStyleSheet("border: 1px solid gray; background-color: black;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("请选择视频文件")
        self.video_label.setScaledContents(False)  # 关闭自动缩放内容
        # 设置尺寸策略，防止自动调整大小
        self.video_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        video_layout.addWidget(self.video_label)
        
        # 播放控制
        controls_layout = QHBoxLayout()
        
        # 后退按钮
        self.backward_btn = QPushButton("⏪")
        self.backward_btn.setToolTip("后退10秒")
        self.backward_btn.clicked.connect(self._backward_10s)
        controls_layout.addWidget(self.backward_btn)
        
        # 播放/暂停按钮
        self.play_btn = QPushButton("▶")
        self.play_btn.setToolTip("播放/暂停")
        self.play_btn.clicked.connect(self._toggle_playback)
        controls_layout.addWidget(self.play_btn)
        
        # 前进按钮
        self.forward_btn = QPushButton("⏩")
        self.forward_btn.setToolTip("前进10秒")
        self.forward_btn.clicked.connect(self._forward_10s)
        controls_layout.addWidget(self.forward_btn)
        
        # 进度条
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setToolTip("拖动调整播放位置")
        self.position_slider.sliderMoved.connect(self._set_position)
        self.position_slider.sliderPressed.connect(self._slider_pressed)
        self.position_slider.sliderReleased.connect(self._slider_released)
        controls_layout.addWidget(self.position_slider)
        
        # 时间显示
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(100)
        controls_layout.addWidget(self.time_label)
        
        video_layout.addLayout(controls_layout)
        
        # 第二行控制：音量和播放速度
        controls_layout2 = QHBoxLayout()
        
        # 音量控制
        volume_label = QLabel("音量:")
        controls_layout2.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.setToolTip("调整音量")
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
        self.speed_combo.currentTextChanged.connect(self._set_playback_rate)
        controls_layout2.addWidget(self.speed_combo)
        
        # 静音按钮
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setToolTip("静音/取消静音")
        self.mute_btn.clicked.connect(self._toggle_mute)
        controls_layout2.addWidget(self.mute_btn)
        
        video_layout.addLayout(controls_layout)
        video_layout.addLayout(controls_layout2)
        
        layout.addWidget(video_group)
        
        # 添加功能选项区域到视频播放下方
        options_group = QGroupBox("快速设置")
        options_layout = QVBoxLayout(options_group)
        
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
        
        tokens_label = QLabel("描述长度要求:")
        tokens_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.center_description_length_combo = QComboBox()
        self.center_description_length_combo.addItems(["简要描述(150字符)", "标准描述(300字符)", "详细描述(500字符)", "非常详细(800字符)", "无限制生成", "自定义长度"])
        self.center_description_length_combo.setCurrentText("标准描述(300字符)")
        self.center_description_length_combo.setToolTip(
            "选择描述的详细程度:\n"
            "• 简要描述: 约150字符，快速概览\n"
            "• 标准描述: 约300字符，平衡详细度\n"
            "• 详细描述: 约500字符，全面分析\n"
            "• 非常详细: 约800字符，深度描述\n"
            "• 无限制生成: 不限制输出长度，生成完整详细描述\n"
            "• 自定义长度: 手动设置字符数量"
        )
        self.center_description_length_combo.currentTextChanged.connect(self._on_description_length_changed)
        
        # 自定义长度输入框（初始隐藏）
        self.center_custom_length_spinbox = QSpinBox()
        self.center_custom_length_spinbox.setRange(0, 2000)
        self.center_custom_length_spinbox.setValue(300)
        self.center_custom_length_spinbox.setSuffix(" 字符")
        self.center_custom_length_spinbox.setSpecialValueText("无限制")
        self.center_custom_length_spinbox.setVisible(False)
        self.center_custom_length_spinbox.setToolTip("自定义描述长度（字符数）\n0: 无限制生成\n100-2000: 指定字符数限制")
        
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
        grid_layout.addWidget(self.center_custom_length_spinbox, 0, 5)
        
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
        
        # 功能说明
        info_label = QLabel(
            "💡 提示: 在此区域可以快速调整主要参数，详细设置请查看左侧面板。\n"
            "🎯 建议: 短视频使用较少帧数，长视频可适当增加帧数以获得更好效果。"
        )
        info_label.setStyleSheet(
            "QLabel {"
            "    background-color: #ecf0f1;"
            "    border: 1px solid #bdc3c7;"
            "    border-radius: 4px;"
            "    padding: 8px;"
            "    color: #2c3e50;"
            "    font-size: 12px;"
            "}"
        )
        info_label.setWordWrap(True)
        options_layout.addWidget(info_label)
        
        layout.addWidget(options_group)
        
        return panel
    
    def _create_right_panel(self):
        """创建右侧面板（日志和结果）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 处理日志选项卡
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setAcceptRichText(True)  # 启用HTML格式支持
        log_layout.addWidget(self.log_text)
        
        tab_widget.addTab(log_tab, "处理日志")
        
        # 详细结果选项卡
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        
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
            cache_config_path = Path("cache_config.txt")
            if cache_config_path.exists():
                with open(cache_config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'sharegpt4video_model_path':
                                self.model_path = value.strip()
                                break
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
                    
        except Exception as e:
            self._log_message(f"加载配置失败: {str(e)}")
    
    def _connect_signals(self):
        """连接信号"""
        # 注意：播放控制按钮的信号已在_create_center_panel中连接，这里不再重复连接
        # 连接中间面板和左侧面板控件的同步信号
        
        # 自动保存选项同步
        self.auto_save_format_combo.currentTextChanged.connect(self._on_auto_save_format_changed)
        
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
        
        # 只有在CUDA模式下才允许多线程处理
        if device == "CUDA":
            self.multithread_checkbox.setEnabled(True)
            self.thread_count_spinbox.setEnabled(True)
            # 默认不勾选多线程，用户可根据需要手动启用
        else:  # Auto或CPU模式
            self.multithread_checkbox.setEnabled(False)
            self.multithread_checkbox.setChecked(False)
            self.thread_count_spinbox.setEnabled(False)
    
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
                
                # 设置生成模式和采样帧数为灰色状态
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setStyleSheet("QComboBox { color: #888888; background-color: #f0f0f0; }")
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setStyleSheet("QSpinBox { color: #888888; background-color: #f0f0f0; }")
                
                # 取消多线程选择
                self.multithread_checkbox.setChecked(False)
                
                # 记录当前模式
                self._log_message(f"当前使用API模式: {model_preset}")
                
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
                
                # 恢复生成模式和采样帧数正常样式
                if hasattr(self, 'center_generation_mode_combo'):
                    self.center_generation_mode_combo.setStyleSheet("")
                if hasattr(self, 'center_num_frames_spinbox'):
                    self.center_num_frames_spinbox.setStyleSheet("")
                
                # 根据设备设置恢复多线程选项状态
                self._on_device_changed()
                
                # 记录当前模式
                self._log_message(f"当前使用本地模型模式: {model_preset}")
                
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
        except Exception as e:
            self._log_message(f"保存API配置失败: {str(e)}")
    
    def _upload_video_files(self):
        """上传视频文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "", "视频文件 (*.mp4)"
        )
        
        if files:
            for file_path in files:
                if file_path not in self.current_videos:
                    self.current_videos.append(file_path)
                    self._add_video_to_list(file_path)
    
    def _upload_video_folder(self):
        """上传视频文件夹（支持累积式添加）"""
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        
        if folder:
            self._add_videos_from_folder(folder)
            
            # 询问是否继续添加更多文件夹
            reply = QMessageBox.question(
                self, "继续添加", 
                f"已添加文件夹: {folder}\n\n是否继续添加其他文件夹？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            # 如果用户选择继续，递归调用自己
            if reply == QMessageBox.Yes:
                self._upload_video_folder()
    
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
                    self._add_video_to_list(file_str)
                    added_count += 1
                    
                    # 检查是否有已存在的描述文件
                    if self._is_video_processed(file_str):
                        processed_count += 1
        
        # 记录添加结果
        if added_count > 0:
            message = f"从文件夹添加了 {added_count} 个视频文件"
            if processed_count > 0:
                message += f"，其中 {processed_count} 个已有处理结果"
            self._log_message(message)
    
    def _select_all_videos(self):
        """全选所有视频"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            item.setCheckState(Qt.Checked)
        self._update_selection_status()
    
    def _deselect_all_videos(self):
        """取消全选所有视频"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            item.setCheckState(Qt.Unchecked)
        self._update_selection_status()
    
    def _get_selected_videos(self):
        """获取选中的视频列表"""
        selected_videos = []
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.checkState() == Qt.Checked:
                video_path = item.data(Qt.UserRole)
                selected_videos.append(video_path)
        return selected_videos
    
    def _on_video_check_changed(self, item):
        """视频复选框状态改变"""
        self._update_selection_status()
    
    def _on_description_length_changed(self, text):
        """描述长度要求改变时的回调"""
        if text == "自定义长度":
            self.center_custom_length_spinbox.setVisible(True)
        else:
            self.center_custom_length_spinbox.setVisible(False)
    
    def _toggle_select_all(self):
        """切换全选/取消全选"""
        if self.is_all_selected:
            # 当前是全选状态，执行取消全选
            self._deselect_all_videos()
        else:
            # 当前不是全选状态，执行全选
            self._select_all_videos()
    
    def _update_selection_status(self):
        """更新选择状态显示"""
        selected_count = len(self._get_selected_videos())
        total_count = self.video_list.count()
        self.selection_status_label.setText(f"已选择：{selected_count}/{total_count}")
        
        # 更新切换按钮状态
        if total_count == 0:
            self.is_all_selected = False
            self.select_toggle_btn.setText("全选")
        elif selected_count == total_count:
            self.is_all_selected = True
            self.select_toggle_btn.setText("取消全选")
        else:
            self.is_all_selected = False
            self.select_toggle_btn.setText("全选")
    
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
    
    def _get_result_file_path(self, video_path):
        """获取结果文件路径 - 统一使用视频名+description格式"""
        video_dir = Path(video_path).parent
        video_name = Path(video_path).stem
        return video_dir / f"{video_name}_description.json"
    
    def _on_video_selected(self, item):
        """视频选中事件"""
        video_path = item.data(Qt.UserRole)
        
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
    
    def _show_video_result(self, video_path):
        """显示视频结果"""
        result_file = self._get_result_file_path(video_path)
        
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
                else:
                    error_msg = result.get('error_message') or '无'
                    result_text += f"\n错误信息:\n{error_msg}"
                
                self.result_text.setPlainText(result_text)
                
            except Exception as e:
                self.result_text.setPlainText(f"读取结果文件失败: {str(e)}")
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
            
            # 获取固定的显示区域大小
            display_width = 400
            display_height = 300
            
            # 缩放图像以适应固定尺寸，保持宽高比
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
        self.log_text.clear()
        if hasattr(self, 'center_progress_bar'):
            self.center_progress_bar.setValue(0)
        
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
        description_length_text = self.center_description_length_combo.currentText()
        if description_length_text == "简要描述(150字符)":
            description_length = 150
        elif description_length_text == "标准描述(300字符)":
            description_length = 300
        elif description_length_text == "详细描述(500字符)":
            description_length = 500
        elif description_length_text == "非常详细(800字符)":
            description_length = 800
        elif description_length_text == "无限制生成":
            description_length = 0  # 0表示无限制
        elif description_length_text == "自定义长度":
            description_length = self.center_custom_length_spinbox.value()
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
            algorithm_type
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
        
        # 同步中间面板按钮状态
        if hasattr(self, 'center_start_btn'):
            self.center_start_btn.setEnabled(True)
        if hasattr(self, 'center_stop_btn'):
            self.center_stop_btn.setEnabled(False)
    
    def _on_video_completed(self, video_path, success, description, error_msg, total_processing_time, actual_timestamp):
        """视频处理完成"""
        video_name = os.path.basename(video_path)
        
        if success:
            self._log_message(f"✅ {video_name} 处理完成")
            
            # 获取当前使用的模型名称
            current_model = self.model_selection_combo.currentText()
            
            # 保存结果
            self._save_video_result(video_path, {
                'success': True,
                'description': description,
                'error_message': '',
                'processed_at': actual_timestamp,  # 使用实际生成描述的时间
                'total_processing_time': total_processing_time,
                'duration': self._get_video_duration(video_path),
                'model_name': current_model,  # 添加使用的模型名称
                'generated_at': actual_timestamp  # 添加生成时间（与processed_at相同，但语义更明确）
            })
            
            # 更新列表显示
            self._update_video_list_item(video_path, True)
        else:
            self._log_message(f"❌ {video_name} 处理失败: {error_msg}")
            
            # 获取当前使用的模型名称
            current_model = self.model_selection_combo.currentText()
            
            # 保存错误结果
            self._save_video_result(video_path, {
                'success': False,
                'description': '',
                'error_message': error_msg,
                'processed_at': actual_timestamp,  # 使用实际处理的时间
                'total_processing_time': total_processing_time,
                'duration': self._get_video_duration(video_path),
                'model_name': current_model,  # 添加使用的模型名称
                'generated_at': actual_timestamp  # 添加生成时间
            })
            
            # 更新列表显示
            self._update_video_list_item(video_path, False)
        
        # 如果当前选中的是刚处理完的视频，立即更新结果显示
        current_item = self.video_list.currentItem()
        if current_item and current_item.data(Qt.UserRole) == video_path:
            self._show_video_result(video_path)
    
    def _on_all_completed(self):
        """所有视频处理完成"""
        self._log_message("所有视频处理完成！")
        
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
        
        # 检查是否启用自动保存
        if self.auto_save_format_combo.currentText() != "关闭":
            self._handle_auto_save()
    
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
            self._log_message(f"统计token使用量时发生错误: {str(e)}")
    
    def _save_video_result(self, video_path, result):
        """保存视频结果"""
        try:
            result_file = self._get_result_file_path(video_path)
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
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
                if success:
                    item.setText(f"✅ {video_name}")
                else:
                    item.setText(f"❌ {video_name}")
                
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
            
            # 检查是否已处理过
            result_file = self._get_result_file_path(video_path)
            if result_file.exists():
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    
                    # 根据处理结果更新显示
                    if result.get('success', False):
                        item.setText(f"✅ {video_name}")
                    else:
                        item.setText(f"❌ {video_name}")
                except Exception as e:
                    # 如果读取结果文件失败，保持原状态
                    self._log_message(f"读取结果文件失败: {str(e)}")
                    if not item.text().startswith(("✅", "❌")):
                        item.setText(video_name)
            else:
                # 如果没有结果文件，显示未处理状态
                if not item.text().startswith(("✅", "❌")):
                    item.setText(video_name)
            
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
            import os
            cache_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache_config.txt')
            
            config_data = {}
            if os.path.exists(cache_config_path):
                with open(cache_config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            key, value = line.strip().split('=', 1)
                            config_data[key] = value.strip()
            
            # 读取动作过滤API配置，如果用户配置为空则使用内置配置
            user_endpoint = config_data.get('action_filter_api_endpoint', '').strip()
            user_key = config_data.get('action_filter_api_key', '').strip()
            user_model = config_data.get('action_filter_api_model', '').strip()
            
            # 如果用户配置了完整的API信息，则使用用户配置
            if user_endpoint and user_key and user_model:
                return {
                    'api_endpoint': user_endpoint,
                    'api_key': user_key,
                    'api_model': user_model
                }
            else:
                # 否则使用内置配置
                return {
                    'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                    'api_key': 'fa1f2df2-73f8-44b1-99a0-09834047ab51',
                    'api_model': 'doubao-1.5-pro-32k-250115'
                }
        except Exception as e:
            self._log_message(f"获取动作过滤API配置失败: {e}")
            # 发生异常时返回内置配置
            return {
                'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                'api_key': 'fa1f2df2-73f8-44b1-99a0-09834047ab51',
                'api_model': 'doubao-1.5-pro-32k-250115'
            }
    
    def _log_message(self, message):
        """记录日志消息"""
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
                    
                    # 生成导出文件路径（保存到description文件夹中）
                    if format_type == 'json':
                        export_file = description_folder / f"{video_name}_description.json"
                        self._export_single_video_json(result, video_path, export_file)
                    elif format_type == 'txt':
                        export_file = description_folder / f"{video_name}_description.txt"
                        self._export_single_video_txt(result, video_path, export_file)
                    elif format_type == 'csv':
                        export_file = description_folder / f"{video_name}_description.csv"
                        self._export_single_video_csv(result, video_path, export_file)
                    elif format_type == 'md':
                        export_file = description_folder / f"{video_name}_description.md"
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
                    
                    video_saved_count = 0
                    for format_type in formats:
                        try:
                            if format_type == 'json':
                                save_file = description_folder / f"{video_name}_description.json"
                                self._export_single_video_json(result, video_path, save_file)
                            elif format_type == 'txt':
                                save_file = description_folder / f"{video_name}_description.txt"
                                self._export_single_video_txt(result, video_path, save_file)
                            elif format_type == 'csv':
                                save_file = description_folder / f"{video_name}_description.csv"
                                self._export_single_video_csv(result, video_path, save_file)
                            elif format_type == 'md':
                                save_file = description_folder / f"{video_name}_description.md"
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
                    
                    # 生成保存文件路径（保存到description文件夹中）
                    if format_type == 'json':
                        save_file = description_folder / f"{video_name}_description.json"
                        self._export_single_video_json(result, video_path, save_file)
                    elif format_type == 'txt':
                        save_file = description_folder / f"{video_name}_description.txt"
                        self._export_single_video_txt(result, video_path, save_file)
                    elif format_type == 'csv':
                        save_file = description_folder / f"{video_name}_description.csv"
                        self._export_single_video_csv(result, video_path, save_file)
                    elif format_type == 'md':
                        save_file = description_folder / f"{video_name}_description.md"
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
        is_local_model = model_name == "ShareVideoGPT4（本地模型）"
        
        if is_local_model:
            # 本地模型：启用本地相关功能，隐藏API配置
            self.api_config_group.setVisible(False)
            self.device_combo.setEnabled(True)
            self.multithread_checkbox.setEnabled(True)
            self.thread_count_spinbox.setEnabled(True)
            self.top_p_spinbox.setEnabled(True)
            if hasattr(self, 'center_generation_mode_combo'):
                self.center_generation_mode_combo.setEnabled(True)
            if hasattr(self, 'center_num_frames_spinbox'):
                self.center_num_frames_spinbox.setEnabled(True)
            
            # 恢复控件正常样式
            self.device_combo.setStyleSheet("")
            self.multithread_checkbox.setStyleSheet("")
            self.thread_count_spinbox.setStyleSheet("")
            self.top_p_spinbox.setStyleSheet("")
            if hasattr(self, 'center_generation_mode_combo'):
                self.center_generation_mode_combo.setStyleSheet("")
            if hasattr(self, 'center_num_frames_spinbox'):
                self.center_num_frames_spinbox.setStyleSheet("")
        else:
            # API模型：禁用本地功能，隐藏API配置（配置保存在文件中）
            self.api_config_group.setVisible(False)
            self.device_combo.setEnabled(False)
            self.multithread_checkbox.setEnabled(False)
            self.thread_count_spinbox.setEnabled(False)
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
            
            # 将API配置保存到配置文件中
            self._save_api_config_to_file(model_name)
    
    def _save_api_config_to_file(self, model_name):
        """将API配置保存到配置文件中"""
        try:
            if hasattr(self, 'config_manager') and self.config_manager:
                # 根据模型名称设置API配置
                if model_name == "火山大模型①":
                    api_config = {
                        'endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                        'api_key': 'fa1f2df2-73f8-44b1-99a0-09834047ab51',
                        'model': 'doubao-1-5-pro-32k-250115'
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
    
    def _save_api_config_to_cache_file(self, api_config):
        """将API配置保存到cache_config.txt文件"""
        try:
            import os
            cache_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache_config.txt')
            
            # 读取现有配置
            config_data = {}
            if os.path.exists(cache_config_path):
                with open(cache_config_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            # 更新配置数据
            updated_lines = []
            config_keys = {
                'custom_api_endpoint': api_config['endpoint'],
                'custom_api_key': api_config['api_key'],
                'custom_api_model': api_config['model']
            }
            
            # 标记哪些配置已经更新
            updated_keys = set()
            
            # 处理现有行
            for line in lines:
                stripped_line = line.strip()
                if '=' in stripped_line and not stripped_line.startswith('#'):
                    key, _ = stripped_line.split('=', 1)
                    if key in config_keys:
                        # 更新现有配置
                        updated_lines.append(f"{key}={config_keys[key]}\n")
                        updated_keys.add(key)
                    else:
                        # 保留其他配置
                        updated_lines.append(line)
                else:
                    # 保留注释和空行
                    updated_lines.append(line)
            
            # 添加未更新的配置项
            for key, value in config_keys.items():
                if key not in updated_keys:
                    updated_lines.append(f"{key}={value}\n")
            
            # 写回文件
            with open(cache_config_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
            
            self._log_message("已将API配置保存到cache_config.txt文件")
            
        except Exception as e:
            self._log_message(f"保存API配置到cache_config.txt失败: {str(e)}")
    
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