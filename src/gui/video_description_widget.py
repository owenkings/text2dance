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

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QShortcut,
    QDialog, QAbstractItemView, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QMutex
from PyQt5.QtGui import QFont, QPixmap, QKeySequence, QImage, QIcon, QMovie
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl

class VideoDescriptionThread(QThread):
    """视频描述处理线程"""
    
    progress_updated = pyqtSignal(int)  # 进度百分比
    status_updated = pyqtSignal(str)  # 状态信息
    video_completed = pyqtSignal(str, bool, str, str)  # 视频路径, 是否成功, 描述内容, 错误信息
    all_completed = pyqtSignal()
    
    def __init__(self, videos, description_requirement, model_path, use_action_filter=False, api_config=None):
        super().__init__()
        self.videos = videos
        self.description_requirement = description_requirement
        self.model_path = model_path
        self.use_action_filter = use_action_filter
        self.api_config = api_config or {}
        self.is_running = True
        self.results = []
    
    def run(self):
        try:
            total_videos = len(self.videos)
            for i, video_path in enumerate(self.videos):
                if not self.is_running:
                    break
                
                self.status_updated.emit(f"正在处理视频 {i+1}/{total_videos}: {os.path.basename(video_path)}")
                
                # 执行视频描述命令
                success, description, error_msg = self._process_single_video(video_path)
                
                # 如果需要动作过滤
                if success and self.use_action_filter and description:
                    description = self._filter_action_description(description)
                
                # 记录结果
                result = {
                    'video_path': video_path,
                    'success': success,
                    'description': description,
                    'error_message': error_msg,
                    'process_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': self._get_video_duration(video_path)
                }
                self.results.append(result)
                
                # 发送完成信号
                self.video_completed.emit(video_path, success, description, error_msg)
                
                # 更新进度
                progress = int(((i + 1) / total_videos) * 100)
                self.progress_updated.emit(progress)
            
            if self.is_running:
                self.all_completed.emit()
                
        except Exception as e:
            self.status_updated.emit(f"处理过程中发生错误: {str(e)}")
    
    def _process_single_video(self, video_path):
        """处理单个视频"""
        try:
            # 构建命令
            cmd = [
                'python',
                'E:\\Tiany\\text2dance\\src\\algorithms\\video_description\\ShareGPT4Video\\run.py',
                '--model-path', self.model_path,
                '--video', video_path,
                '--query', self.description_requirement
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # 从输出中提取描述内容
                output_lines = result.stdout.strip().split('\n')
                description = ""
                for line in output_lines:
                    if "### LM OUTPUT TEXT:" in line:
                        description = line.replace("### LM OUTPUT TEXT:", "").strip()
                        break
                
                if not description:
                    # 如果没有找到标准输出格式，使用最后一行非空输出
                    for line in reversed(output_lines):
                        if line.strip():
                            description = line.strip()
                            break
                
                return True, description, ""
            else:
                return False, "", result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "", "处理超时"
        except Exception as e:
            return False, "", str(e)
    
    def _filter_action_description(self, description):
        """使用API过滤动作描述"""
        try:
            # 这里可以集成API调用来过滤动作描述
            # 暂时返回原描述
            return description
        except Exception as e:
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
        
        # 媒体播放器
        self.media_player = QMediaPlayer()
        
        self._init_ui()
        self._load_cache_config()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化用户界面"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建三个主要区域
        left_panel = self._create_left_panel()  # 300px
        center_panel = self._create_center_panel()  # 400px
        right_panel = self._create_right_panel()  # 500px
        
        # 添加到主布局
        main_layout.addWidget(left_panel, 300)
        main_layout.addWidget(center_panel, 400)
        main_layout.addWidget(right_panel, 500)
    
    def _create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 文件上传区域
        upload_group = QGroupBox("视频上传")
        upload_layout = QVBoxLayout(upload_group)
        
        # 上传按钮
        self.upload_file_btn = QPushButton("上传视频文件")
        self.upload_file_btn.clicked.connect(self._upload_video_files)
        upload_layout.addWidget(self.upload_file_btn)
        
        self.upload_folder_btn = QPushButton("上传视频文件夹")
        self.upload_folder_btn.clicked.connect(self._upload_video_folder)
        upload_layout.addWidget(self.upload_folder_btn)
        
        # 视频列表
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self._on_video_selected)
        upload_layout.addWidget(QLabel("视频列表:"))
        upload_layout.addWidget(self.video_list)
        
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
        
        self.backup_checkbox = QCheckBox("启用备份功能")
        options_layout.addWidget(self.backup_checkbox)
        
        self.export_checkbox = QCheckBox("启用导出功能")
        options_layout.addWidget(self.export_checkbox)
        
        self.action_filter_checkbox = QCheckBox("只保留动作描述")
        options_layout.addWidget(self.action_filter_checkbox)
        
        layout.addWidget(options_group)
        
        # 处理控制区域
        control_group = QGroupBox("处理控制")
        control_layout = QVBoxLayout(control_group)
        
        self.start_btn = QPushButton("开始描述")
        self.start_btn.clicked.connect(self._start_description)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_description)
        control_layout.addWidget(self.stop_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        control_layout.addWidget(self.progress_bar)
        
        layout.addWidget(control_group)
        
        layout.addStretch()
        return panel
    
    def _create_center_panel(self):
        """创建中间面板（视频播放）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 视频播放区域
        video_group = QGroupBox("视频播放")
        video_layout = QVBoxLayout(video_group)
        
        # 视频播放器
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(300)
        self.media_player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget)
        
        # 播放控制
        controls_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self._toggle_playback)
        controls_layout.addWidget(self.play_btn)
        
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.sliderMoved.connect(self._set_position)
        controls_layout.addWidget(self.position_slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        controls_layout.addWidget(self.time_label)
        
        video_layout.addLayout(controls_layout)
        
        layout.addWidget(video_group)
        
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
        export_layout.addWidget(self.export_json_btn)
        
        self.export_txt_btn = QPushButton("导出TXT")
        self.export_txt_btn.clicked.connect(lambda: self._export_results('txt'))
        export_layout.addWidget(self.export_txt_btn)
        
        self.export_csv_btn = QPushButton("导出CSV")
        self.export_csv_btn.clicked.connect(lambda: self._export_results('csv'))
        export_layout.addWidget(self.export_csv_btn)
        
        self.export_md_btn = QPushButton("导出Markdown")
        self.export_md_btn.clicked.connect(lambda: self._export_results('md'))
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
    
    def _connect_signals(self):
        """连接信号"""
        # 媒体播放器信号
        self.media_player.stateChanged.connect(self._media_state_changed)
        self.media_player.positionChanged.connect(self._position_changed)
        self.media_player.durationChanged.connect(self._duration_changed)
    
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
        """上传视频文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        
        if folder:
            for file_path in Path(folder).glob("*.mp4"):
                file_str = str(file_path)
                if file_str not in self.current_videos:
                    self.current_videos.append(file_str)
                    self._add_video_to_list(file_str)
    
    def _add_video_to_list(self, video_path):
        """添加视频到列表"""
        item = QListWidgetItem()
        
        # 检查是否已处理过
        if self._is_video_processed(video_path):
            item.setText(f"✅ {os.path.basename(video_path)}")
        else:
            item.setText(os.path.basename(video_path))
        
        item.setData(Qt.UserRole, video_path)
        self.video_list.addItem(item)
    
    def _is_video_processed(self, video_path):
        """检查视频是否已处理过"""
        # 检查是否有保存的结果文件
        result_file = self._get_result_file_path(video_path)
        return result_file.exists()
    
    def _get_result_file_path(self, video_path):
        """获取结果文件路径"""
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
        """播放视频"""
        if os.path.exists(video_path):
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
            self.play_btn.setText("播放")
    
    def _show_video_result(self, video_path):
        """显示视频结果"""
        result_file = self._get_result_file_path(video_path)
        
        if result_file.exists():
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                
                result_text = f"视频: {os.path.basename(video_path)}\n"
                result_text += f"处理时间: {result.get('process_time', '未知')}\n"
                result_text += f"视频时长: {result.get('duration', '未知')}\n"
                result_text += f"处理状态: {'成功' if result.get('success', False) else '失败'}\n"
                
                if result.get('success', False):
                    result_text += f"\n描述内容:\n{result.get('description', '无')}"
                else:
                    result_text += f"\n错误信息:\n{result.get('error_message', '无')}"
                
                self.result_text.setPlainText(result_text)
                
            except Exception as e:
                self.result_text.setPlainText(f"读取结果文件失败: {str(e)}")
        else:
            self.result_text.setPlainText("该视频尚未处理")
    
    def _toggle_playback(self):
        """切换播放状态"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
    
    def _media_state_changed(self, state):
        """媒体状态改变"""
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("暂停")
        else:
            self.play_btn.setText("播放")
    
    def _position_changed(self, position):
        """播放位置改变"""
        self.position_slider.setValue(position)
        
        # 更新时间显示
        duration = self.media_player.duration()
        if duration > 0:
            current_time = self._format_time(position)
            total_time = self._format_time(duration)
            self.time_label.setText(f"{current_time} / {total_time}")
    
    def _duration_changed(self, duration):
        """播放时长改变"""
        self.position_slider.setRange(0, duration)
    
    def _set_position(self, position):
        """设置播放位置"""
        self.media_player.setPosition(position)
    
    def _format_time(self, ms):
        """格式化时间"""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def _start_description(self):
        """开始描述处理"""
        if not self.current_videos:
            QMessageBox.warning(self, "警告", "请先上传视频文件")
            return
        
        description_requirement = self.description_text.toPlainText().strip()
        if not description_requirement:
            QMessageBox.warning(self, "警告", "请输入描述要求")
            return
        
        # 禁用开始按钮，启用停止按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # 清空日志
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        # 启动处理线程
        self.processing_thread = VideoDescriptionThread(
            self.current_videos,
            description_requirement,
            self.model_path,
            self.action_filter_checkbox.isChecked()
        )
        
        self.processing_thread.progress_updated.connect(self.progress_bar.setValue)
        self.processing_thread.status_updated.connect(self._log_message)
        self.processing_thread.video_completed.connect(self._on_video_completed)
        self.processing_thread.all_completed.connect(self._on_all_completed)
        
        self.processing_thread.start()
        
        self._log_message("开始处理视频描述...")
    
    def _stop_description(self):
        """停止描述处理"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self._log_message("用户取消处理")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def _on_video_completed(self, video_path, success, description, error_msg):
        """视频处理完成"""
        video_name = os.path.basename(video_path)
        
        if success:
            self._log_message(f"✅ {video_name} 处理完成")
            
            # 保存结果
            self._save_video_result(video_path, {
                'success': True,
                'description': description,
                'error_message': '',
                'process_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'duration': self._get_video_duration(video_path)
            })
            
            # 更新列表显示
            self._update_video_list_item(video_path, True)
        else:
            self._log_message(f"❌ {video_name} 处理失败: {error_msg}")
            
            # 保存错误结果
            self._save_video_result(video_path, {
                'success': False,
                'description': '',
                'error_message': error_msg,
                'process_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'duration': self._get_video_duration(video_path)
            })
            
            # 更新列表显示
            self._update_video_list_item(video_path, False)
    
    def _on_all_completed(self):
        """所有视频处理完成"""
        self._log_message("所有视频处理完成！")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # 如果启用了导出功能，询问是否导出
        if self.export_checkbox.isChecked():
            reply = QMessageBox.question(
                self, "导出结果", "处理完成，是否导出结果？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._export_results('json')
    
    def _save_video_result(self, video_path, result):
        """保存视频结果"""
        try:
            result_file = self._get_result_file_path(video_path)
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log_message(f"保存结果失败: {str(e)}")
    
    def _update_video_list_item(self, video_path, success):
        """更新视频列表项显示"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.data(Qt.UserRole) == video_path:
                video_name = os.path.basename(video_path)
                if success:
                    item.setText(f"✅ {video_name}")
                else:
                    item.setText(f"❌ {video_name}")
                break
    
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
    
    def _log_message(self, message):
        """记录日志消息"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 发送状态信号
        self.status_changed.emit(message)
    
    def _export_results(self, format_type):
        """导出结果"""
        if not self.current_videos:
            QMessageBox.warning(self, "警告", "没有可导出的结果")
            return
        
        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not export_dir:
            return
        
        try:
            # 收集所有结果
            all_results = []
            for video_path in self.current_videos:
                result_file = self._get_result_file_path(video_path)
                if result_file.exists():
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                        result['video_path'] = video_path
                        result['video_name'] = os.path.basename(video_path)
                        all_results.append(result)
            
            if not all_results:
                QMessageBox.warning(self, "警告", "没有找到处理结果")
                return
            
            # 根据格式导出
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type == 'json':
                export_file = os.path.join(export_dir, f"video_description_results_{timestamp}.json")
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)
            
            elif format_type == 'txt':
                export_file = os.path.join(export_dir, f"video_description_results_{timestamp}.txt")
                with open(export_file, 'w', encoding='utf-8') as f:
                    for result in all_results:
                        f.write(f"视频: {result['video_name']}\n")
                        f.write(f"处理时间: {result.get('process_time', '未知')}\n")
                        f.write(f"视频时长: {result.get('duration', '未知')}\n")
                        f.write(f"处理状态: {'成功' if result.get('success', False) else '失败'}\n")
                        if result.get('success', False):
                            f.write(f"描述内容: {result.get('description', '无')}\n")
                        else:
                            f.write(f"错误信息: {result.get('error_message', '无')}\n")
                        f.write("-" * 50 + "\n")
            
            elif format_type == 'csv':
                export_file = os.path.join(export_dir, f"video_description_results_{timestamp}.csv")
                with open(export_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['视频名称', '处理时间', '视频时长', '处理状态', '描述内容', '错误信息'])
                    for result in all_results:
                        writer.writerow([
                            result['video_name'],
                            result.get('process_time', '未知'),
                            result.get('duration', '未知'),
                            '成功' if result.get('success', False) else '失败',
                            result.get('description', '无'),
                            result.get('error_message', '无')
                        ])
            
            elif format_type == 'md':
                export_file = os.path.join(export_dir, f"video_description_results_{timestamp}.md")
                with open(export_file, 'w', encoding='utf-8') as f:
                    f.write("# 视频描述结果\n\n")
                    for result in all_results:
                        f.write(f"## {result['video_name']}\n\n")
                        f.write(f"- **处理时间**: {result.get('process_time', '未知')}\n")
                        f.write(f"- **视频时长**: {result.get('duration', '未知')}\n")
                        f.write(f"- **处理状态**: {'成功' if result.get('success', False) else '失败'}\n\n")
                        if result.get('success', False):
                            f.write(f"**描述内容**:\n\n{result.get('description', '无')}\n\n")
                        else:
                            f.write(f"**错误信息**:\n\n{result.get('error_message', '无')}\n\n")
                        f.write("---\n\n")
            
            QMessageBox.information(self, "成功", f"结果已导出到: {export_file}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")