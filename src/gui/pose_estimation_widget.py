# -*- coding: utf-8 -*-
"""
姿势估计界面组件
提供3D姿势估计功能的用户界面
"""

import os
import json
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
    QScrollArea, QTreeWidget, QTreeWidgetItem,
    QDialog, QAbstractItemView, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QPixmap, QIcon

class PoseEstimationThread(QThread):
    """姿势估计处理线程"""
    
    progress_updated = pyqtSignal(int)  # 进度百分比
    status_updated = pyqtSignal(str)  # 状态信息
    log_updated = pyqtSignal(str)  # 实时日志更新
    video_completed = pyqtSignal(str, bool, str, str, float)  # 视频路径, 是否成功, 输出路径, 错误信息, 总耗时
    all_completed = pyqtSignal()

    def __init__(self, videos, output_dir, pose_model="ViTPose", output_format="fbx", enable_3d=True, enable_mesh=False):
        super().__init__()
        self.videos = videos
        self.output_dir = output_dir
        self.pose_model = pose_model
        self.output_format = output_format
        self.enable_3d = enable_3d
        self.enable_mesh = enable_mesh
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
            self.status_updated.emit(f"开始处理 {total_videos} 个视频的姿势估计...")
            
            for i, video_path in enumerate(self.videos):
                if not self.is_running:
                    break
                
                self.status_updated.emit(f"正在处理: {os.path.basename(video_path)}")
                self.log_updated.emit(f"开始处理视频 {i+1}/{total_videos}: {video_path}")
                
                start_time = time.time()
                
                try:
                    # 调用姿势估计处理
                    success, output_path, error_msg = self._process_single_video(video_path)
                    
                    processing_time = time.time() - start_time
                    
                    if success:
                        self.log_updated.emit(f"✓ 处理完成: {output_path} (耗时: {processing_time:.2f}秒)")
                        self.video_completed.emit(video_path, True, output_path, "", processing_time)
                    else:
                        self.log_updated.emit(f"✗ 处理失败: {error_msg}")
                        self.video_completed.emit(video_path, False, "", error_msg, processing_time)
                    
                    # 更新进度
                    progress = int((i + 1) / total_videos * 100)
                    self.progress_updated.emit(progress)
                    
                except Exception as e:
                    error_msg = f"处理视频时发生错误: {str(e)}"
                    self.log_updated.emit(f"✗ {error_msg}")
                    self.video_completed.emit(video_path, False, "", error_msg, 0)
            
            self.status_updated.emit("所有视频处理完成")
            self.all_completed.emit()
            
        except Exception as e:
            self.status_updated.emit(f"处理过程中发生错误: {str(e)}")
            self.log_updated.emit(f"错误: {str(e)}")
    
    def _process_single_video(self, video_path):
        """处理单个视频"""
        try:
            # 构建输出路径
            video_name = Path(video_path).stem
            if self.output_format == "fbx":
                output_path = os.path.join(self.output_dir, f"{video_name}.fbx")
                script_name = "run_demo_fbx.py"
            else:
                output_path = os.path.join(self.output_dir, f"{video_name}_output")
                script_name = "run_demo.py"
            
            # 构建命令
            pose3d_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pose3d")
            script_path = os.path.join(pose3d_dir, "main", script_name)
            
            cmd = [
                "python", script_path,
                "--video_path", video_path,
                "--output_path", output_path
            ]
            
            if self.enable_3d:
                cmd.extend(["--enable_3d", "true"])
            
            if self.enable_mesh:
                cmd.extend(["--enable_mesh", "true"])
            
            # 执行命令
            self.log_updated.emit(f"执行命令: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=pose3d_dir
            )
            
            if result.returncode == 0:
                return True, output_path, ""
            else:
                error_msg = result.stderr or result.stdout or "未知错误"
                return False, "", error_msg
                
        except Exception as e:
            return False, "", str(e)

class PoseEstimationWidget(QWidget):
    """姿势估计界面组件"""
    
    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.processing_thread = None
        self.video_list = []
        self.results = []
        
        self._init_ui()
        self._connect_signals()
        self._load_config()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 输入选项卡
        self.input_tab = self._create_input_tab()
        self.tab_widget.addTab(self.input_tab, "📁 输入设置")
        
        # 处理选项卡
        self.processing_tab = self._create_processing_tab()
        self.tab_widget.addTab(self.processing_tab, "⚙️ 处理设置")
        
        # 输出选项卡
        self.output_tab = self._create_output_tab()
        self.tab_widget.addTab(self.output_tab, "📤 输出设置")
        
        # 结果选项卡
        self.results_tab = self._create_results_tab()
        self.tab_widget.addTab(self.results_tab, "📊 处理结果")
        
        layout.addWidget(self.tab_widget)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 开始处理")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._start_processing)
        
        self.stop_btn = QPushButton("⏹️ 停止处理")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_processing)
        
        self.clear_btn = QPushButton("🗑️ 清空列表")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.clicked.connect(self._clear_video_list)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
    
    def _create_input_tab(self):
        """创建输入选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 视频文件选择
        file_group = QGroupBox("视频文件")
        file_layout = QVBoxLayout(file_group)
        
        # 添加文件按钮
        btn_layout = QHBoxLayout()
        
        self.add_files_btn = QPushButton("📁 添加视频文件")
        self.add_files_btn.clicked.connect(self._add_video_files)
        
        self.add_folder_btn = QPushButton("📂 添加文件夹")
        self.add_folder_btn.clicked.connect(self._add_video_folder)
        
        btn_layout.addWidget(self.add_files_btn)
        btn_layout.addWidget(self.add_folder_btn)
        btn_layout.addStretch()
        
        file_layout.addLayout(btn_layout)
        
        # 视频列表
        self.video_list_widget = QListWidget()
        self.video_list_widget.setMinimumHeight(200)
        file_layout.addWidget(self.video_list_widget)
        
        layout.addWidget(file_group)
        
        return widget
    
    def _create_processing_tab(self):
        """创建处理选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 模型设置
        model_group = QGroupBox("模型设置")
        model_layout = QGridLayout(model_group)
        
        model_layout.addWidget(QLabel("姿势检测模型:"), 0, 0)
        self.pose_model_combo = QComboBox()
        self.pose_model_combo.addItems(["ViTPose", "HRNet", "SimpleBaseline"])
        model_layout.addWidget(self.pose_model_combo, 0, 1)
        
        layout.addWidget(model_group)
        
        # 处理选项
        options_group = QGroupBox("处理选项")
        options_layout = QVBoxLayout(options_group)
        
        self.enable_3d_cb = QCheckBox("启用3D姿势估计")
        self.enable_3d_cb.setChecked(True)
        options_layout.addWidget(self.enable_3d_cb)
        
        self.enable_mesh_cb = QCheckBox("启用人体网格重建")
        options_layout.addWidget(self.enable_mesh_cb)
        
        layout.addWidget(options_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_output_tab(self):
        """创建输出选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QGridLayout(output_group)
        
        output_layout.addWidget(QLabel("输出目录:"), 0, 0)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("选择输出目录...")
        output_layout.addWidget(self.output_dir_edit, 0, 1)
        
        self.browse_output_btn = QPushButton("浏览")
        self.browse_output_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(self.browse_output_btn, 0, 2)
        
        output_layout.addWidget(QLabel("输出格式:"), 1, 0)
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["fbx", "obj", "pkl", "json"])
        output_layout.addWidget(self.output_format_combo, 1, 1)
        
        layout.addWidget(output_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_results_tab(self):
        """创建结果选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 结果表格
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["视频文件", "状态", "输出路径", "处理时间", "错误信息"])
        
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.results_table)
        
        # 日志输出
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _connect_signals(self):
        """连接信号"""
        pass
    
    def _load_config(self):
        """加载配置"""
        if self.config_manager:
            config = self.config_manager.get_config("pose_estimation", {})
            
            # 设置默认输出目录
            default_output = config.get("output_dir", "./output/pose_estimation")
            self.output_dir_edit.setText(default_output)
            
            # 设置默认模型
            default_model = config.get("pose_model", "ViTPose")
            index = self.pose_model_combo.findText(default_model)
            if index >= 0:
                self.pose_model_combo.setCurrentIndex(index)
            
            # 设置默认选项
            self.enable_3d_cb.setChecked(config.get("enable_3d", True))
            self.enable_mesh_cb.setChecked(config.get("enable_mesh", False))
    
    def _save_config(self):
        """保存配置"""
        if self.config_manager:
            config = {
                "output_dir": self.output_dir_edit.text(),
                "pose_model": self.pose_model_combo.currentText(),
                "enable_3d": self.enable_3d_cb.isChecked(),
                "enable_mesh": self.enable_mesh_cb.isChecked(),
                "output_format": self.output_format_combo.currentText()
            }
            self.config_manager.set_config("pose_estimation", config)
    
    def _add_video_files(self):
        """添加视频文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;所有文件 (*)"
        )
        
        for file_path in files:
            if file_path not in self.video_list:
                self.video_list.append(file_path)
                self.video_list_widget.addItem(os.path.basename(file_path))
    
    def _add_video_folder(self):
        """添加视频文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        if folder:
            video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
            for file_path in Path(folder).rglob('*'):
                if file_path.suffix.lower() in video_extensions:
                    file_str = str(file_path)
                    if file_str not in self.video_list:
                        self.video_list.append(file_str)
                        self.video_list_widget.addItem(file_path.name)
    
    def _browse_output_dir(self):
        """浏览输出目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.output_dir_edit.setText(folder)
    
    def _clear_video_list(self):
        """清空视频列表"""
        self.video_list.clear()
        self.video_list_widget.clear()
        self.results.clear()
        self.results_table.setRowCount(0)
        self.log_text.clear()
    
    def _start_processing(self):
        """开始处理"""
        if not self.video_list:
            QMessageBox.warning(self, "警告", "请先添加要处理的视频文件")
            return
        
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "警告", "请设置输出目录")
            return
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存配置
        self._save_config()
        
        # 清空结果
        self.results.clear()
        self.results_table.setRowCount(0)
        self.log_text.clear()
        
        # 创建处理线程
        self.processing_thread = PoseEstimationThread(
            videos=self.video_list.copy(),
            output_dir=output_dir,
            pose_model=self.pose_model_combo.currentText(),
            output_format=self.output_format_combo.currentText(),
            enable_3d=self.enable_3d_cb.isChecked(),
            enable_mesh=self.enable_mesh_cb.isChecked()
        )
        
        # 连接信号
        self.processing_thread.progress_updated.connect(self.progress_bar.setValue)
        self.processing_thread.status_updated.connect(self.status_label.setText)
        self.processing_thread.log_updated.connect(self._append_log)
        self.processing_thread.video_completed.connect(self._on_video_completed)
        self.processing_thread.all_completed.connect(self._on_all_completed)
        
        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 启动线程
        self.processing_thread.start()
    
    def _stop_processing(self):
        """停止处理"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.status_label.setText("正在停止处理...")
    
    def _append_log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def _on_video_completed(self, video_path, success, output_path, error_msg, processing_time):
        """视频处理完成"""
        # 添加到结果表格
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        self.results_table.setItem(row, 0, QTableWidgetItem(os.path.basename(video_path)))
        self.results_table.setItem(row, 1, QTableWidgetItem("✓ 成功" if success else "✗ 失败"))
        self.results_table.setItem(row, 2, QTableWidgetItem(output_path if success else ""))
        self.results_table.setItem(row, 3, QTableWidgetItem(f"{processing_time:.2f}s"))
        self.results_table.setItem(row, 4, QTableWidgetItem(error_msg))
        
        # 保存结果
        self.results.append({
            'video_path': video_path,
            'success': success,
            'output_path': output_path,
            'error_msg': error_msg,
            'processing_time': processing_time
        })
    
    def _on_all_completed(self):
        """所有处理完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        # 显示完成统计
        total = len(self.results)
        success_count = sum(1 for r in self.results if r['success'])
        
        self.status_label.setText(f"处理完成: {success_count}/{total} 个视频成功")
        
        if success_count < total:
            QMessageBox.information(self, "处理完成", 
                                  f"处理完成!\n成功: {success_count}\n失败: {total - success_count}")
        else:
            QMessageBox.information(self, "处理完成", "所有视频处理成功!")