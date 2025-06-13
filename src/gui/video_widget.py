# -*- coding: utf-8 -*-
"""
视频处理界面组件
提供视频处理和算法应用功能的用户界面
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QShortcut
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QPixmap, QIcon, QMovie, QKeySequence

from ..algorithms.algorithm_manager import AlgorithmManager, AlgorithmType
from ..video_processing.video_processor import VideoProcessor
from ..utils.logger import Logger

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
        
        # 播放状态
        self.is_playing = False
        self.is_paused = False
        
        # 定时器
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self._update_playback)
        
        # 初始化界面
        self._init_ui()
        self._connect_signals()
        self._load_settings()
        
        self.logger.info("视频编辑界面组件初始化完成")
    
    def _init_ui(self):
        """初始化界面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 左侧：视频列表面板
        left_panel = self._create_video_list_panel()
        layout.addWidget(left_panel)
        
        # 中间：视频预览面板
        center_panel = self._create_video_preview_panel()
        layout.addWidget(center_panel)
        
        # 右侧：编辑操作面板
        right_panel = self._create_edit_operations_panel()
        layout.addWidget(right_panel)
        
        # 设置布局比例 (1:2:1)
        layout.setStretchFactor(left_panel, 1)
        layout.setStretchFactor(center_panel, 2)
        layout.setStretchFactor(right_panel, 1)
    
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
        
        # 预览区域
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("QLabel { background-color: #000; color: #fff; border: 1px solid #ccc; }")
        self.preview_label.setText("无视频预览")
        layout.addWidget(self.preview_label)
        
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
        self.position_slider = QSlider(Qt.Horizontal)
        layout.addWidget(self.position_slider)
        
        # 时间信息
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.total_time_label = QLabel("00:00")
        
        time_layout.addWidget(self.current_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.total_time_label)
        layout.addLayout(time_layout)
        
        return panel
    
    def _create_edit_operations_panel(self) -> QWidget:
        """创建编辑操作面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("编辑操作")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 基本编辑操作
        basic_group = QGroupBox("基本操作")
        basic_layout = QVBoxLayout(basic_group)
        
        self.cut_btn = QPushButton("剪切")
        self.copy_btn = QPushButton("复制")
        self.paste_btn = QPushButton("粘贴")
        self.delete_btn = QPushButton("删除")
        
        basic_layout.addWidget(self.cut_btn)
        basic_layout.addWidget(self.copy_btn)
        basic_layout.addWidget(self.paste_btn)
        basic_layout.addWidget(self.delete_btn)
        
        layout.addWidget(basic_group)
        
        # 时间轴操作
        timeline_group = QGroupBox("时间轴")
        timeline_layout = QVBoxLayout(timeline_group)
        
        self.split_btn = QPushButton("分割")
        self.merge_btn = QPushButton("合并")
        self.trim_btn = QPushButton("修剪")
        
        timeline_layout.addWidget(self.split_btn)
        timeline_layout.addWidget(self.merge_btn)
        timeline_layout.addWidget(self.trim_btn)
        
        layout.addWidget(timeline_group)
        
        # 效果操作
        effects_group = QGroupBox("效果")
        effects_layout = QVBoxLayout(effects_group)
        
        self.fade_in_btn = QPushButton("淡入")
        self.fade_out_btn = QPushButton("淡出")
        self.speed_btn = QPushButton("变速")
        
        effects_layout.addWidget(self.fade_in_btn)
        effects_layout.addWidget(self.fade_out_btn)
        effects_layout.addWidget(self.speed_btn)
        
        layout.addWidget(effects_group)
        
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
        
        # 编辑操作信号
        self.cut_btn.clicked.connect(self._cut_video)
        self.copy_btn.clicked.connect(self._copy_video)
        self.paste_btn.clicked.connect(self._paste_video)
        self.delete_btn.clicked.connect(self._delete_video)
        self.split_btn.clicked.connect(self._split_video)
        self.merge_btn.clicked.connect(self._merge_video)
        self.trim_btn.clicked.connect(self._trim_video)
        self.fade_in_btn.clicked.connect(self._fade_in)
        self.fade_out_btn.clicked.connect(self._fade_out)
        self.speed_btn.clicked.connect(self._change_speed)
        
        # 快捷键
        self._setup_shortcuts()
        
        # 视频路径变化
        self.video_path_input.textChanged.connect(self._on_video_path_changed)
        
        # 多线程选项变化
        self.multithread_check.toggled.connect(self._on_multithread_toggled)
    
    def _setup_shortcuts(self):
        """设置快捷键"""
        
        # 播放控制快捷键
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key_Left), self, self._seek_backward)
        QShortcut(QKeySequence(Qt.Key_Right), self, self._seek_forward)
        QShortcut(QKeySequence(Qt.Key_Home), self, self._seek_to_start)
        QShortcut(QKeySequence(Qt.Key_End), self, self._seek_to_end)
        
        # 编辑快捷键
        QShortcut(QKeySequence.Cut, self, self._cut_video)
        QShortcut(QKeySequence.Copy, self, self._copy_video)
        QShortcut(QKeySequence.Paste, self, self._paste_video)
        QShortcut(QKeySequence.Delete, self, self._delete_video)
    
    def _toggle_play_pause(self):
        """切换播放/暂停"""
        if self.is_playing:
            self._pause_video()
        else:
            self._play_video()
    
    def _seek_backward(self):
        """向后跳转"""
        if self.current_video_info:
            current_pos = self.position_slider.value()
            new_pos = max(0, current_pos - 30)  # 向后30帧
            self.position_slider.setValue(new_pos)
    
    def _seek_forward(self):
        """向前跳转"""
        if self.current_video_info:
            current_pos = self.position_slider.value()
            max_pos = self.position_slider.maximum()
            new_pos = min(max_pos, current_pos + 30)  # 向前30帧
            self.position_slider.setValue(new_pos)
    
    def _seek_to_start(self):
        """跳转到开始"""
        self.position_slider.setValue(0)
    
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
            
            # 加载输出目录设置
            self.output_dir = self.config_manager.get('video_edit.output_dir', './output')
            
        except Exception as e:
            self.logger.error(f"加载设置失败: {e}")
    
    def _add_video(self):
        """添加视频文件"""
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.wmv *.flv);;所有文件 (*)"
        )
        
        for file_path in file_paths:
            self._add_video_to_list(file_path)
    
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
    
    def _load_video_preview(self, item):
        """加载视频预览"""
        video_path = item.data(Qt.UserRole)
        self._load_video(video_path)
    
    def _load_video(self, video_path: str):
        """加载视频"""
        try:
            self.current_video_path = video_path
            self.current_video_info = self.video_processor.get_video_info(video_path)
            
            if self.current_video_info:
                # 更新预览标签
                filename = Path(video_path).name
                self.preview_label.setText(f"预览: {filename}")
                
                # 设置进度条
                duration = self.current_video_info.get('duration', 0)
                fps = self.current_video_info.get('fps', 30)
                total_frames = int(duration * fps)
                
                self.position_slider.setMaximum(total_frames)
                self.position_slider.setValue(0)
                
                # 更新时间标签
                self.current_time_label.setText("00:00")
                self.total_time_label.setText(self._format_time(duration))
                
                # 重置播放状态
                self.current_position = 0.0
                self.is_playing = False
                self.is_paused = False
                
                self.logger.info(f"加载视频: {filename}")
                
        except Exception as e:
            self.logger.error(f"加载视频失败: {e}")
            self._clear_preview()
    
    def _clear_preview(self):
        """清空预览"""
        self.current_video_path = None
        self.current_video_info = None
        self.preview_label.setText("无视频预览")
        self.position_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
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
        
        fps = self.current_video_info.get('fps', 30)
        current_frame = self.position_slider.value()
        
        # 模拟播放进度
        if current_frame < self.position_slider.maximum():
            self.position_slider.setValue(current_frame + 1)
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
            self.current_position = time_seconds
    
    def _format_time(self, seconds):
        """格式化时间显示"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def _cut_video(self):
        """剪切视频"""
        # TODO: 实现视频剪切功能
        self.logger.info("执行视频剪切操作")
    
    def _copy_video(self):
        """复制视频"""
        # TODO: 实现视频复制功能
        self.logger.info("执行视频复制操作")
    
    def _paste_video(self):
        """粘贴视频"""
        # TODO: 实现视频粘贴功能
        self.logger.info("执行视频粘贴操作")
    
    def _delete_video(self):
        """删除视频片段"""
        # TODO: 实现视频删除功能
        self.logger.info("执行视频删除操作")
    
    def _split_video(self):
        """分割视频"""
        # TODO: 实现视频分割功能
        self.logger.info("执行视频分割操作")
    
    def _merge_video(self):
        """合并视频"""
        # TODO: 实现视频合并功能
        self.logger.info("执行视频合并操作")
    
    def _trim_video(self):
        """修剪视频"""
        # TODO: 实现视频修剪功能
        self.logger.info("执行视频修剪操作")
    
    def _fade_in(self):
        """淡入效果"""
        # TODO: 实现淡入效果
        self.logger.info("添加淡入效果")
    
    def _fade_out(self):
        """淡出效果"""
        # TODO: 实现淡出效果
        self.logger.info("添加淡出效果")
    
    def _change_speed(self):
        """变速效果"""
        # TODO: 实现变速效果
        self.logger.info("添加变速效果")
    
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
                "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;所有文件 (*)"
            )
            
            if file_path:
                self.video_path_input.setText(file_path)
                
        except Exception as e:
            self.logger.error(f"浏览视频文件失败: {e}")
    
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
                info_text += f"分辨率: {video_info.get('width', 'Unknown')}x{video_info.get('height', 'Unknown')}\n"
                info_text += f"帧率: {video_info.get('fps', 'Unknown')} fps\n"
                info_text += f"时长: {video_info.get('duration', 'Unknown')} 秒\n"
                info_text += f"总帧数: {video_info.get('frame_count', 'Unknown')}"
                
                self.video_info_label.setText(info_text)
                
                # 更新预览滑块
                frame_count = video_info.get('frame_count', 0)
                self.preview_frame_slider.setMaximum(max(0, frame_count - 1))
                self.frame_info_label.setText(f"帧: 0/{frame_count}")
                
            else:
                self.current_video_path = None
                self.current_video_info = None
                self.video_info_label.setText("未选择视频")
                self.preview_frame_slider.setMaximum(0)
                self.frame_info_label.setText("帧: 0/0")
                
        except Exception as e:
            self.logger.error(f"处理视频路径变化失败: {e}")
    
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
            # TODO: 实现结果树更新
            pass
        except Exception as e:
            self.logger.error(f"更新结果树失败: {e}")
    
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
            if self.processing_thread and self.processing_thread.isRunning():
                self.processing_thread.stop()
            
            self.logger.info("视频处理界面组件资源清理完成")
            
        except Exception as e:
            self.logger.error(f"视频处理界面组件资源清理失败: {e}")