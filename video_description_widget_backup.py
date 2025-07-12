# -*- coding: utf-8 -*-
"""
视频描述界面
提供视频描述功能的用户界面
"""

import os
import sys
import json
import time
import threading
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QGroupBox,
    QCheckBox, QSpinBox, QProgressBar, QMessageBox,
    QTabWidget, QScrollArea, QFrame, QComboBox,
    QDialog, QRadioButton
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex
from PyQt5.QtGui import QFont, QTextCursor, QPalette, QColor

# 修复相对导入问题
try:
    from ..core.config_manager import ConfigManager
    from ..utils.logger import get_logger
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    try:
        from src.core.config_manager import ConfigManager
        from src.utils.logger import get_logger
    except ImportError:
        # 如果仍然失败，创建简单的替代实现
        import logging
        
        class ConfigManager:
            def __init__(self):
                self.config = {}
            
            def get_config(self, section):
                return self.config.get(section, {})
            
            def save_config(self, section, config):
                self.config[section] = config
        
        def get_logger(name):
            logging.basicConfig(level=logging.INFO)
            return logging.getLogger(name)

logger = get_logger(__name__)


class VideoDescriptionWorker(QThread):
    """视频描述处理工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int)  # 当前进度, 总数
    video_completed = pyqtSignal(str, dict)  # 视频路径, 结果
    all_completed = pyqtSignal(list)  # 所有结果
    error_occurred = pyqtSignal(str)  # 错误信息
    log_message = pyqtSignal(str)  # 日志消息
    
    def __init__(self, video_files: List[str], config: Dict[str, Any]):
        super().__init__()
        self.video_files = video_files
        self.config = config
        self.is_running = True
        self.results = []
        self.mutex = QMutex()
    
    def stop(self):
        """停止处理"""
        self.is_running = False
    
    def run(self):
        """执行视频描述处理"""
        try:
            if self.config.get('enable_parallel', False) and len(self.video_files) > 1:
                self._process_parallel()
            else:
                self._process_sequential()
            
            if self.is_running:
                self.all_completed.emit(self.results)
        except Exception as e:
            self.error_occurred.emit(f"处理过程中发生错误: {str(e)}")
    
    def _process_sequential(self):
        """顺序处理视频"""
        for i, video_path in enumerate(self.video_files):
            if not self.is_running:
                break
            
            result = self._process_single_video(video_path)
            self.results.append(result)
            self.video_completed.emit(video_path, result)
            self.progress_updated.emit(i + 1, len(self.video_files))
    
    def _process_parallel(self):
        """并行处理视频"""
        max_workers = self.config.get('max_workers', 2)
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._process_single_video, video_path): video_path 
                      for video_path in self.video_files}
            
            for future in futures:
                if not self.is_running:
                    break
                
                try:
                    result = future.result()
                    video_path = futures[future]
                    
                    with self.mutex:
                        self.results.append(result)
                        completed_count += 1
                    
                    self.video_completed.emit(video_path, result)
                    self.progress_updated.emit(completed_count, len(self.video_files))
                except Exception as e:
                    self.log_message.emit(f"处理视频时发生错误: {str(e)}")
    
    def _process_single_video(self, video_path: str) -> Dict[str, Any]:
        """处理单个视频"""
        result = {
            "video_path": video_path,
            "video_name": Path(video_path).name,
            "status": "success",
            "start_time": datetime.now().isoformat(),
            "processing_time": 0,
            "description": "",
            "error_message": ""
        }
        
        start_time = time.time()
        
        try:
            if not self.is_running:
                result["status"] = "cancelled"
                return result
            
            self.log_message.emit(f"开始处理: {Path(video_path).name}")
            
            # 构建命令 - 处理包含特殊字符的路径
            import shlex
            import os
            
            # 规范化视频路径并转换为绝对路径
            normalized_video_path = os.path.abspath(os.path.normpath(video_path))
            
            # 构建命令参数列表
            cmd = [
                "python",
                "E:\\Tiany\\text2dance\\external\\video_description\\alorithms\\run.py",
                "--model-path", self.config.get('model_path', 'Lin-Chen/sharegpt4video-8b'),
                "--video", normalized_video_path,  # 使用规范化的绝对路径
                "--query", self.config.get('query_text', '')
            ]
            
            # 记录执行的命令（用于调试）
            self.log_message.emit(f"执行命令: {' '.join(shlex.quote(arg) for arg in cmd)}")
            
            # 在Windows环境下，使用shell=True可以更好地处理特殊字符
            # 但为了安全性，我们仍然使用参数列表而不是字符串
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='replace',
                cwd=os.path.dirname(cmd[1]),  # 设置工作目录
                shell=False  # 保持False以确保安全性
            )
            
            output, _ = process.communicate()
            
            if process.returncode == 0:
                # 提取描述内容
                if "LM OUTPUT TEXT:" in output:
                    description = output.split("LM OUTPUT TEXT:")[1].strip()
                    result["description"] = description
                else:
                    result["description"] = "未找到描述输出"
                    result["status"] = "warning"
            else:
                result["status"] = "failed"
                result["error_message"] = output
                
        except Exception as e:
            result["status"] = "failed"
            result["error_message"] = str(e)
        finally:
            result["processing_time"] = round(time.time() - start_time, 2)
            result["end_time"] = datetime.now().isoformat()
        
        return result


class VideoDescriptionWidget(QWidget):
    """视频描述界面组件"""
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.video_files = []
        self.results = {}
        self.worker = None
        self.is_processing = False
        
        self._init_ui()
        self._connect_signals()
        self._load_config()
        
        # 检查存储空间
        self._check_storage_space()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 创建主分割器
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # 左侧面板
        left_panel = self._create_left_panel()
        main_splitter.addWidget(left_panel)
        
        # 右侧面板
        right_panel = self._create_right_panel()
        main_splitter.addWidget(right_panel)
        
        # 设置分割器比例
        main_splitter.setSizes([400, 600])
        
        # 底部状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)
        
        layout.addLayout(status_layout)
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 文件上传区域
        upload_group = QGroupBox("视频文件")
        upload_layout = QVBoxLayout(upload_group)
        
        # 上传按钮
        upload_btn_layout = QHBoxLayout()
        self.upload_file_btn = QPushButton("上传视频文件")
        self.upload_folder_btn = QPushButton("上传视频文件夹")
        self.clear_files_btn = QPushButton("清空列表")
        
        upload_btn_layout.addWidget(self.upload_file_btn)
        upload_btn_layout.addWidget(self.upload_folder_btn)
        upload_btn_layout.addWidget(self.clear_files_btn)
        upload_layout.addLayout(upload_btn_layout)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(200)
        upload_layout.addWidget(self.file_list)
        
        layout.addWidget(upload_group)
        
        # 描述要求区域
        query_group = QGroupBox("描述要求")
        query_layout = QVBoxLayout(query_group)
        
        self.query_text = QTextEdit()
        self.query_text.setMinimumHeight(150)
        self.query_text.setMaximumHeight(200)
        
        # 设置默认文本和样式
        default_query = ("Begin by providing a general overview of the person's current action "
                        "(e.g., walking, sitting, interacting) visible in the video footage. "
                        "Then proceed with a detailed analysis focusing specifically on the "
                        "physical movements and body positioning within the video frame. "
                        "For the upper body, describe the position and movement patterns of "
                        "the arms, hands, shoulders and torso. For the lower body, detail "
                        "the positioning and motion of the legs, feet and overall balance "
                        "dynamics. The description must remain strictly focused on observable "
                        "physical actions, deliberately excluding any mention of facial "
                        "expressions, clothing details or environmental elements outside "
                        "the video frame boundaries.")
        
        self.query_text.setPlainText(default_query)
        self._set_placeholder_style()
        
        query_layout.addWidget(self.query_text)
        layout.addWidget(query_group)
        
        # 处理选项区域
        options_group = QGroupBox("处理选项")
        options_layout = QGridLayout(options_group)
        
        # 多线程选项
        self.parallel_cb = QCheckBox("启用多线程处理")
        options_layout.addWidget(self.parallel_cb, 0, 0, 1, 2)
        
        # 线程数设置
        options_layout.addWidget(QLabel("线程数:"), 1, 0)
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 8)
        self.thread_count.setValue(2)
        options_layout.addWidget(self.thread_count, 1, 1)
        
        # 内存阈值
        self.memory_check_cb = QCheckBox("启用内存阈值检查")
        options_layout.addWidget(self.memory_check_cb, 2, 0, 1, 2)
        
        # 备份选项
        self.backup_cb = QCheckBox("启用结果备份")
        options_layout.addWidget(self.backup_cb, 3, 0, 1, 2)
        
        # 导出选项
        self.export_cb = QCheckBox("自动导出结果")
        options_layout.addWidget(self.export_cb, 4, 0, 1, 2)
        
        layout.addWidget(options_group)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始描述")
        self.stop_btn = QPushButton("停止处理")
        self.export_btn = QPushButton("导出结果")
        
        # 设置按钮样式（包含动画和悬停效果）
        self._setup_button_styles()
        self.stop_btn.setEnabled(False)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.export_btn)
        
        layout.addLayout(control_layout)
        layout.addStretch()
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 结果显示区域
        result_group = QGroupBox("处理结果")
        result_layout = QVBoxLayout(result_group)
        
        # 创建选项卡
        self.result_tabs = QTabWidget()
        
        # 日志选项卡
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.result_tabs.addTab(self.log_text, "处理日志")
        
        # 详细结果选项卡
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.result_tabs.addTab(self.detail_text, "详细结果")
        
        result_layout.addWidget(self.result_tabs)
        layout.addWidget(result_group)
        
        return panel
    
    def _set_placeholder_style(self):
        """设置占位符样式（淡灰色）"""
        # 保存默认文本
        self.default_query_text = self.query_text.toPlainText()
        self.is_placeholder_active = True
        
        # 设置淡灰色样式
        self._apply_placeholder_style()
        
        # 连接焦点和文本变化事件
        self.query_text.focusInEvent = self._on_query_focus_in
        self.query_text.focusOutEvent = self._on_query_focus_out
        self.query_text.textChanged.connect(self._on_query_text_changed)
    
    def _apply_placeholder_style(self):
        """应用占位符样式"""
        palette = self.query_text.palette()
        palette.setColor(QPalette.Text, QColor(128, 128, 128))  # 淡灰色
        self.query_text.setPalette(palette)
    
    def _apply_normal_style(self):
        """应用正常文本样式"""
        palette = self.query_text.palette()
        palette.setColor(QPalette.Text, QColor(0, 0, 0))  # 黑色
        self.query_text.setPalette(palette)
    
    def _on_query_focus_in(self, event):
        """文本框获得焦点时的处理"""
        if self.is_placeholder_active:
            self.query_text.clear()
            self._apply_normal_style()
            self.is_placeholder_active = False
        # 调用原始的focusInEvent
        QTextEdit.focusInEvent(self.query_text, event)
    
    def _on_query_focus_out(self, event):
        """文本框失去焦点时的处理"""
        if not self.query_text.toPlainText().strip():
            self.query_text.setPlainText(self.default_query_text)
            self._apply_placeholder_style()
            self.is_placeholder_active = True
        # 调用原始的focusOutEvent
        QTextEdit.focusOutEvent(self.query_text, event)
    
    def _on_query_text_changed(self):
        """文本内容变化时的处理"""
        if not self.is_placeholder_active and not self.query_text.toPlainText().strip():
            # 如果用户清空了所有文本，恢复占位符
            self.query_text.setPlainText(self.default_query_text)
            self._apply_placeholder_style()
            self.is_placeholder_active = True
    
    def _setup_button_styles(self):
        """设置按钮样式（包含悬停和点击效果）"""
        # 开始描述按钮样式
        start_style = """
        QPushButton {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            border: 2px solid #4CAF50;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #45a049;
            border-color: #45a049;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #3d8b40;
            border-color: #3d8b40;
            padding: 9px 15px 7px 17px;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            border-color: #cccccc;
            color: #666666;
        }
        """
        
        # 停止处理按钮样式
        stop_style = """
        QPushButton {
            background-color: #f44336;
            color: white;
            font-weight: bold;
            border: 2px solid #f44336;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #da190b;
            border-color: #da190b;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #c62828;
            border-color: #c62828;
            padding: 9px 15px 7px 17px;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            border-color: #cccccc;
            color: #666666;
        }
        """
        
        # 导出结果按钮样式
        export_style = """
        QPushButton {
            background-color: #2196F3;
            color: white;
            font-weight: bold;
            border: 2px solid #2196F3;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #1976D2;
            border-color: #1976D2;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #1565C0;
            border-color: #1565C0;
            padding: 9px 15px 7px 17px;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            border-color: #cccccc;
            color: #666666;
        }
        """
        
        self.start_btn.setStyleSheet(start_style)
        self.stop_btn.setStyleSheet(stop_style)
        self.export_btn.setStyleSheet(export_style)
    
    def _connect_signals(self):
        """连接信号"""
        self.upload_file_btn.clicked.connect(self._upload_files)
        self.upload_folder_btn.clicked.connect(self._upload_folder)
        self.clear_files_btn.clicked.connect(self._clear_files)
        self.start_btn.clicked.connect(self._start_processing)
        self.stop_btn.clicked.connect(self._stop_processing)
        self.export_btn.clicked.connect(self._export_results)
        self.file_list.itemClicked.connect(self._on_file_selected)
        
        # 多线程选项变化
        self.parallel_cb.toggled.connect(self.thread_count.setEnabled)
    
    def _load_config(self):
        """加载配置"""
        # 加载处理选项
        self.parallel_cb.setChecked(self.config_manager.get('video_description.enable_parallel', False))
        self.thread_count.setValue(self.config_manager.get('video_description.max_workers', 2))
        self.memory_check_cb.setChecked(self.config_manager.get('video_description.enable_memory_check', True))
        self.backup_cb.setChecked(self.config_manager.get('video_description.enable_backup', True))
        self.export_cb.setChecked(self.config_manager.get('video_description.auto_export', False))
        
        # 设置线程数控件状态
        self.thread_count.setEnabled(self.parallel_cb.isChecked())
    
    def _save_config(self):
        """保存配置"""
        self.config_manager.set('video_description.enable_parallel', self.parallel_cb.isChecked())
        self.config_manager.set('video_description.max_workers', self.thread_count.value())
        self.config_manager.set('video_description.enable_memory_check', self.memory_check_cb.isChecked())
        self.config_manager.set('video_description.enable_backup', self.backup_cb.isChecked())
        self.config_manager.set('video_description.auto_export', self.export_cb.isChecked())
        self.config_manager.save_config()
    
    def _validate_file_path(self, file_path: str) -> tuple[bool, str]:
        """验证文件路径并检测潜在问题
        
        Returns:
            tuple: (is_valid, warning_message)
        """
        import re
        
        warnings = []
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        # 检查文件是否可读
        if not os.access(file_path, os.R_OK):
            return False, "文件无法读取，请检查权限"
        
        # 检查路径长度（Windows路径限制）
        if len(file_path) > 260:
            warnings.append("路径过长，可能在某些系统上出现问题")
        
        # 检查特殊字符
        filename = Path(file_path).name
        problematic_chars = re.findall(r'[\[\]【】\(\)（）\s]+', filename)
        if problematic_chars:
            char_list = ', '.join(set(''.join(problematic_chars)))
            warnings.append(f"文件名包含特殊字符: {char_list}")
        
        # 检查中文字符
        if re.search(r'[\u4e00-\u9fff]', filename):
            warnings.append("文件名包含中文字符")
        
        warning_msg = "; ".join(warnings) if warnings else ""
        return True, warning_msg
    
    def _upload_files(self):
        """上传视频文件"""
        # 支持更多视频格式
        video_filter = "视频文件 (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm);;所有文件 (*.*)"
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "", video_filter
        )
        
        added_count = 0
        warning_files = []
        
        for file_path in files:
            if file_path not in self.video_files:
                # 验证文件路径
                is_valid, warning_msg = self._validate_file_path(file_path)
                
                if is_valid:
                    self.video_files.append(file_path)
                    # 显示文件名，处理特殊字符
                    display_name = Path(file_path).name
                    item = QListWidgetItem(display_name)
                    item.setData(Qt.UserRole, file_path)
                    item.setToolTip(file_path)  # 设置完整路径为提示
                    
                    # 如果有警告，在列表项中标记
                    if warning_msg:
                        item.setForeground(QColor(255, 140, 0))  # 橙色文字表示警告
                        item.setToolTip(f"{file_path}\n\n⚠️ 警告: {warning_msg}")
                        warning_files.append((Path(file_path).name, warning_msg))
                    
                    self.file_list.addItem(item)
                    added_count += 1
                else:
                    self._log_message(f"错误: {Path(file_path).name} - {warning_msg}")
        
        if added_count > 0:
            self._log_message(f"已添加 {added_count} 个视频文件")
            
            # 显示警告文件汇总
            if warning_files:
                warning_msg = f"\n⚠️ 发现 {len(warning_files)} 个文件包含特殊字符，可能影响处理:\n"
                for filename, warning in warning_files:
                    warning_msg += f"  • {filename}: {warning}\n"
                warning_msg += "\n建议重命名这些文件以避免潜在问题。"
                self._log_message(warning_msg)
        
        self._update_status()
    
    def _upload_folder(self):
        """上传视频文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        if folder_path:
            # 支持多种视频格式
            video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.wmv', '*.flv', '*.webm']
            video_files = []
            
            # 搜索所有支持的视频格式
            for ext in video_extensions:
                video_files.extend(list(Path(folder_path).glob(ext)))
                # 同时搜索大写扩展名
                video_files.extend(list(Path(folder_path).glob(ext.upper())))
            
            added_count = 0
            warning_files = []
            
            for file_path in video_files:
                file_str = str(file_path)
                if file_str not in self.video_files:
                    # 验证文件路径
                    is_valid, warning_msg = self._validate_file_path(file_str)
                    
                    if is_valid:
                        self.video_files.append(file_str)
                        item = QListWidgetItem(file_path.name)
                        item.setData(Qt.UserRole, file_str)
                        item.setToolTip(file_str)  # 设置完整路径为提示
                        
                        # 如果有警告，在列表项中标记
                        if warning_msg:
                            item.setForeground(QColor(255, 140, 0))  # 橙色文字表示警告
                            item.setToolTip(f"{file_str}\n\n⚠️ 警告: {warning_msg}")
                            warning_files.append((file_path.name, warning_msg))
                        
                        self.file_list.addItem(item)
                        added_count += 1
                    else:
                        self._log_message(f"错误: {file_path.name} - {warning_msg}")
            
            if added_count > 0:
                self._log_message(f"已添加 {added_count} 个视频文件")
                
                # 显示警告文件汇总
                if warning_files:
                    warning_msg = f"\n⚠️ 发现 {len(warning_files)} 个文件包含特殊字符，可能影响处理:\n"
                    for filename, warning in warning_files:
                        warning_msg += f"  • {filename}: {warning}\n"
                    warning_msg += "\n建议重命名这些文件以避免潜在问题。"
                    self._log_message(warning_msg)
            else:
                QMessageBox.information(self, "提示", 
                    f"所选文件夹中没有找到支持的视频文件\n支持格式: {', '.join([ext[2:] for ext in video_extensions])}")
        
        self._update_status()
    
    def _clear_files(self):
        """清空文件列表"""
        self.video_files.clear()
        self.results.clear()
        self.file_list.clear()
        self.detail_text.clear()
        self._update_status()
    
    def _start_processing(self):
        """开始处理"""
        if not self.video_files:
            QMessageBox.warning(self, "警告", "请先上传视频文件")
            return
        
        query_text = self.query_text.toPlainText().strip()
        if not query_text:
            QMessageBox.warning(self, "警告", "请输入描述要求")
            return
        
        # 检查存储空间
        if not self._check_storage_space(show_warning=False):
            reply = QMessageBox.question(
                self, "存储空间不足", 
                "检测到存储空间不足，继续处理可能导致失败。\n\n是否仍要继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # 保存配置
        self._save_config()
        
        # 准备配置
        config = {
            'model_path': 'Lin-Chen/sharegpt4video-8b',
            'query_text': query_text,
            'enable_parallel': self.parallel_cb.isChecked(),
            'max_workers': self.thread_count.value()
            # 移除超时设置 - 现在支持无限制处理时间
        }
        
        # 启动工作线程
        self.worker = VideoDescriptionWorker(self.video_files.copy(), config)
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.video_completed.connect(self._on_video_completed)
        self.worker.all_completed.connect(self._on_all_completed)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.log_message.connect(self._log_message)
        
        self.worker.start()
        
        # 更新UI状态
        self.is_processing = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.video_files))
        self.progress_bar.setValue(0)
        
        self._log_message(f"开始处理 {len(self.video_files)} 个视频文件...")
    
    def _stop_processing(self):
        """停止处理"""
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        
        self._reset_ui_state()
        self._log_message("处理已停止")
    
    def _on_progress_updated(self, current: int, total: int):
        """更新进度"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"处理进度: {current}/{total}")
    
    def _on_video_completed(self, video_path: str, result: Dict[str, Any]):
        """单个视频处理完成"""
        self.results[video_path] = result
        
        # 更新文件列表显示状态
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.UserRole) == video_path:
                status = result['status']
                if status == 'success':
                    item.setText(f"{Path(video_path).name} ✅ 已完成")
                elif status == 'failed':
                    item.setText(f"{Path(video_path).name} ❌ 失败")
                # 移除超时状态显示 - 现在支持无限制处理时间
                break
        
        self._log_message(f"完成: {Path(video_path).name} - {result['status']} (用时: {result['processing_time']}秒)")
    
    def _on_all_completed(self, results: List[Dict[str, Any]]):
        """所有视频处理完成"""
        self._reset_ui_state()
        
        success_count = sum(1 for r in results if r['status'] == 'success')
        total_count = len(results)
        
        self._log_message(f"\n处理完成! 成功: {success_count}/{total_count}")
        
        # 自动导出
        if self.export_cb.isChecked():
            self._export_results()
    
    def _on_error(self, error_msg: str):
        """处理错误"""
        self._reset_ui_state()
        self._log_message(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
    
    def _reset_ui_state(self):
        """重置UI状态"""
        self.is_processing = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("就绪")
    
    def _on_file_selected(self, item: QListWidgetItem):
        """文件选中事件"""
        video_path = item.data(Qt.UserRole)
        if video_path in self.results:
            result = self.results[video_path]
            self._show_video_detail(result)
    
    def _show_video_detail(self, result: Dict[str, Any]):
        """显示视频详细信息"""
        detail_text = f"""视频名称: {result['video_name']}
处理状态: {result['status']}
开始时间: {result.get('start_time', 'N/A')}
结束时间: {result.get('end_time', 'N/A')}
处理时间: {result['processing_time']} 秒

描述内容:
{result.get('description', '无描述内容')}

错误信息:
{result.get('error_message', '无错误')}
"""
        
        self.detail_text.setPlainText(detail_text)
        self.result_tabs.setCurrentIndex(1)  # 切换到详细结果选项卡
    
    def _export_results(self):
        """导出结果"""
        if not self.results:
            QMessageBox.information(self, "提示", "没有可导出的结果")
            return
        
        # 选择导出格式
        format_dialog = QDialog(self)
        format_dialog.setWindowTitle("选择导出格式")
        format_dialog.setFixedSize(300, 200)
        
        layout = QVBoxLayout(format_dialog)
        
        # 格式选择
        format_group = QGroupBox("导出格式")
        format_layout = QVBoxLayout(format_group)
        
        self.json_radio = QRadioButton("JSON格式 (.json)")
        self.csv_radio = QRadioButton("CSV格式 (.csv)")
        self.txt_radio = QRadioButton("文本格式 (.txt)")
        self.xml_radio = QRadioButton("XML格式 (.xml)")
        
        self.json_radio.setChecked(True)  # 默认选择JSON
        
        format_layout.addWidget(self.json_radio)
        format_layout.addWidget(self.csv_radio)
        format_layout.addWidget(self.txt_radio)
        format_layout.addWidget(self.xml_radio)
        
        layout.addWidget(format_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        
        ok_button.clicked.connect(format_dialog.accept)
        cancel_button.clicked.connect(format_dialog.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        if format_dialog.exec_() != QDialog.Accepted:
            return
        
        # 确定导出格式
        if self.json_radio.isChecked():
            export_format = 'json'
        elif self.csv_radio.isChecked():
            export_format = 'csv'
        elif self.txt_radio.isChecked():
            export_format = 'txt'
        elif self.xml_radio.isChecked():
            export_format = 'xml'
        else:
            export_format = 'json'  # 默认
        
        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not export_dir:
            return
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_description_results_{timestamp}.{export_format}"
            filepath = Path(export_dir) / filename
            
            # 准备导出数据
            export_data = {
                "export_time": datetime.now().isoformat(),
                "total_videos": len(self.results),
                "successful_videos": sum(1 for r in self.results.values() if r['status'] == 'success'),
                "results": list(self.results.values())
            }
            
            # 根据格式导出
            if export_format == 'json':
                self._export_json(filepath, export_data)
            elif export_format == 'csv':
                self._export_csv(filepath, export_data)
            elif export_format == 'txt':
                self._export_txt(filepath, export_data)
            elif export_format == 'xml':
                self._export_xml(filepath, export_data)
            
            self._log_message(f"结果已导出到: {filepath}")
            QMessageBox.information(self, "成功", f"结果已导出到:\n{filepath}")
            
        except Exception as e:
            error_msg = f"导出失败: {str(e)}"
            self._log_message(error_msg)
            QMessageBox.critical(self, "错误", error_msg)
    
    def _export_json(self, filepath: Path, export_data: dict):
        """导出JSON格式"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    def _export_csv(self, filepath: Path, export_data: dict):
        """导出CSV格式"""
        import csv
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 写入标题行
            writer.writerow([
                '视频名称', '处理状态', '开始时间', '结束时间', 
                '处理时间(秒)', '描述内容', '错误信息'
            ])
            
            # 写入数据行
            for result in export_data['results']:
                writer.writerow([
                    result.get('video_name', ''),
                    result.get('status', ''),
                    result.get('start_time', ''),
                    result.get('end_time', ''),
                    result.get('processing_time', ''),
                    result.get('description', '').replace('\n', ' '),  # 移除换行符
                    result.get('error_message', '')
                ])
    
    def _export_txt(self, filepath: Path, export_data: dict):
        """导出文本格式"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("视频描述结果导出报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"导出时间: {export_data['export_time']}\n")
            f.write(f"总视频数: {export_data['total_videos']}\n")
            f.write(f"成功处理: {export_data['successful_videos']}\n")
            f.write(f"失败数量: {export_data['total_videos'] - export_data['successful_videos']}\n\n")
            
            f.write("详细结果:\n")
            f.write("-" * 50 + "\n\n")
            
            for i, result in enumerate(export_data['results'], 1):
                f.write(f"{i}. 视频名称: {result.get('video_name', '')}\n")
                f.write(f"   处理状态: {result.get('status', '')}\n")
                f.write(f"   开始时间: {result.get('start_time', '')}\n")
                f.write(f"   结束时间: {result.get('end_time', '')}\n")
                f.write(f"   处理时间: {result.get('processing_time', '')} 秒\n")
                f.write(f"   描述内容:\n   {result.get('description', '').replace(chr(10), chr(10) + '   ')}\n")
                if result.get('error_message'):
                    f.write(f"   错误信息: {result.get('error_message', '')}\n")
                f.write("\n" + "-" * 30 + "\n\n")
    
    def _export_xml(self, filepath: Path, export_data: dict):
        """导出XML格式"""
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        
        # 创建根元素
        root = ET.Element('VideoDescriptionResults')
        
        # 添加元数据
        metadata = ET.SubElement(root, 'Metadata')
        ET.SubElement(metadata, 'ExportTime').text = export_data['export_time']
        ET.SubElement(metadata, 'TotalVideos').text = str(export_data['total_videos'])
        ET.SubElement(metadata, 'SuccessfulVideos').text = str(export_data['successful_videos'])
        
        # 添加结果
        results_elem = ET.SubElement(root, 'Results')
        
        for result in export_data['results']:
            video_elem = ET.SubElement(results_elem, 'Video')
            
            ET.SubElement(video_elem, 'Name').text = result.get('video_name', '')
            ET.SubElement(video_elem, 'Status').text = result.get('status', '')
            ET.SubElement(video_elem, 'StartTime').text = result.get('start_time', '')
            ET.SubElement(video_elem, 'EndTime').text = result.get('end_time', '')
            ET.SubElement(video_elem, 'ProcessingTime').text = str(result.get('processing_time', ''))
            
            # 使用CDATA包装描述内容
            description_elem = ET.SubElement(video_elem, 'Description')
            description_elem.text = result.get('description', '')
            
            if result.get('error_message'):
                ET.SubElement(video_elem, 'ErrorMessage').text = result.get('error_message', '')
        
        # 格式化XML并写入文件
        xml_str = ET.tostring(root, encoding='unicode')
        dom = minidom.parseString(xml_str)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(dom.toprettyxml(indent='  '))
    
    def _log_message(self, message: str):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        self.log_text.append(log_entry)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def _update_status(self):
        """更新状态"""
        count = len(self.video_files)
        if count == 0:
            self.status_label.setText("就绪")
        else:
            self.status_label.setText(f"已加载 {count} 个视频文件")
    
    def _check_storage_space(self, show_warning: bool = True):
        """检查存储空间"""
        try:
            # 检查是否禁用了警告
            if show_warning and self.config_manager.get('video_description.disable_storage_warning', False):
                return True
            
            # 获取模型缓存目录
            cache_path = self.config_manager.get('video_description.cache_path', '')
            if not cache_path:
                cache_path = os.path.join(os.getcwd(), 'cache')
            
            # 检查缓存目录可用空间
            cache_free_space = self._get_free_space(cache_path)
            cache_free_gb = cache_free_space / (1024**3)
            
            # 检查系统盘可用空间
            system_drive = os.path.splitdrive(os.environ.get('SystemRoot', 'C:'))[0]
            system_free_space = self._get_free_space(system_drive)
            system_free_gb = system_free_space / (1024**3)
            
            # 检查是否满足要求
            cache_sufficient = cache_free_gb >= 20.0
            system_sufficient = system_free_gb >= 3.0
            
            if not cache_sufficient or not system_sufficient:
                if show_warning:
                    self._show_storage_warning(cache_free_gb, system_free_gb, cache_sufficient, system_sufficient)
                return False
            else:
                self._log_message(f"存储空间检查通过 - 缓存目录: {cache_free_gb:.1f}GB, 系统盘: {system_free_gb:.1f}GB")
                return True
                
        except Exception as e:
            logger.error(f"存储空间检查失败: {e}")
            self._log_message(f"存储空间检查失败: {str(e)}")
            return True  # 检查失败时允许继续
    
    def _get_free_space(self, path: str) -> int:
        """获取指定路径的可用空间（字节）"""
        try:
            # 确保路径存在
            if not os.path.exists(path):
                # 如果路径不存在，尝试创建或使用父目录
                parent_path = os.path.dirname(path)
                if os.path.exists(parent_path):
                    path = parent_path
                else:
                    path = os.getcwd()
            
            # 使用shutil.disk_usage获取磁盘使用情况
            total, used, free = shutil.disk_usage(path)
            return free
            
        except Exception as e:
            logger.error(f"获取磁盘空间失败 {path}: {e}")
            return 0
    
    def _show_storage_warning(self, cache_free_gb: float, system_free_gb: float, 
                             cache_sufficient: bool, system_sufficient: bool):
        """显示存储空间警告"""
        warning_msg = "⚠️ 存储空间检查警告\n\n"
        
        if not cache_sufficient:
            warning_msg += f"❌ 模型缓存目录可用空间不足:\n"
            warning_msg += f"   当前: {cache_free_gb:.1f}GB，要求: ≥20GB\n\n"
        else:
            warning_msg += f"✅ 模型缓存目录: {cache_free_gb:.1f}GB (充足)\n\n"
        
        if not system_sufficient:
            warning_msg += f"❌ 系统盘可用空间不足:\n"
            warning_msg += f"   当前: {system_free_gb:.1f}GB，要求: ≥3GB\n\n"
        else:
            warning_msg += f"✅ 系统盘: {system_free_gb:.1f}GB (充足)\n\n"
        
        warning_msg += "建议操作:\n"
        if not cache_sufficient:
            warning_msg += "• 清理模型缓存目录或更换到空间更大的位置\n"
            warning_msg += "• 可在配置界面修改模型缓存路径\n"
        if not system_sufficient:
            warning_msg += "• 清理系统盘临时文件和不必要的文件\n"
        
        warning_msg += "\n空间不足可能导致模型下载失败或处理中断。"
        
        # 显示警告对话框
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("存储空间警告")
        msg_box.setText(warning_msg)
        msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Ignore)
        msg_box.setDefaultButton(QMessageBox.Ok)
        
        # 添加"不再显示"选项
        dont_show_again = msg_box.addButton("不再显示此警告", QMessageBox.ActionRole)
        
        result = msg_box.exec_()
        
        if msg_box.clickedButton() == dont_show_again:
            self.config_manager.set('video_description.disable_storage_warning', True)
            self.config_manager.save_config()
            self._log_message("已禁用存储空间警告提示")
        
        # 记录警告信息
        self._log_message(f"存储空间警告 - 缓存: {cache_free_gb:.1f}GB, 系统: {system_free_gb:.1f}GB")


if __name__ == "__main__":
    """独立运行测试"""
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建配置管理器实例
    config_manager = ConfigManager()
    
    # 创建视频描述组件
    widget = VideoDescriptionWidget(config_manager)
    widget.show()
    
    print("视频描述组件已启动，相对导入问题已修复")
    
    sys.exit(app.exec_())