# -*- coding: utf-8 -*-
"""
配置界面组件
提供系统配置和设置管理功能的用户界面
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QFormLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QPixmap, QIcon, QIntValidator, QDoubleValidator

from ..utils.logger import Logger

class ConfigWidget(QWidget):
    """配置界面组件"""
    
    # 信号定义
    config_changed = pyqtSignal(str, dict)  # 配置类别, 配置数据
    
    def __init__(self, config_manager):
        super().__init__()
        
        self.config_manager = config_manager
        self.logger = Logger().get_logger("ConfigWidget")
        
        # 配置数据
        self.config_data = {}
        self.modified_configs = set()
        
        # 初始化界面
        self._init_ui()
        self._connect_signals()
        self._load_configs()
        
        self.logger.info("配置界面组件初始化完成")
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 通用设置选项卡
        self.general_tab = self._create_general_tab()
        self.tab_widget.addTab(self.general_tab, "通用设置")
        
        # 爬虫设置选项卡
        self.crawler_tab = self._create_crawler_tab()
        self.tab_widget.addTab(self.crawler_tab, "爬虫设置")
        
        # 视频处理设置选项卡
        self.video_tab = self._create_video_tab()
        self.tab_widget.addTab(self.video_tab, "视频处理")
        
        # 算法设置选项卡
        self.algorithm_tab = self._create_algorithm_tab()
        self.tab_widget.addTab(self.algorithm_tab, "算法设置")
        
        # 界面设置选项卡
        self.ui_tab = self._create_ui_tab()
        self.tab_widget.addTab(self.ui_tab, "界面设置")
        
        # 高级设置选项卡
        self.advanced_tab = self._create_advanced_tab()
        self.tab_widget.addTab(self.advanced_tab, "高级设置")
        
        layout.addWidget(self.tab_widget)
        
        # 控制按钮
        self._create_control_buttons(layout)
    
    def _create_general_tab(self) -> QWidget:
        """创建通用设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 基本设置组
        basic_group = QGroupBox("基本设置")
        basic_layout = QFormLayout(basic_group)
        
        # 语言设置
        self.language_combo = QComboBox()
        self.language_combo.addItems(["简体中文", "English", "日本語"])
        basic_layout.addRow("界面语言:", self.language_combo)
        
        # 主题设置
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["默认主题", "深色主题", "浅色主题", "高对比度"])
        basic_layout.addRow("界面主题:", self.theme_combo)
        
        # 自动保存
        self.auto_save_check = QCheckBox("启用自动保存")
        basic_layout.addRow(self.auto_save_check)
        
        # 自动保存间隔
        self.auto_save_interval_spin = QSpinBox()
        self.auto_save_interval_spin.setRange(1, 60)
        self.auto_save_interval_spin.setValue(5)
        self.auto_save_interval_spin.setSuffix(" 分钟")
        basic_layout.addRow("自动保存间隔:", self.auto_save_interval_spin)
        
        layout.addWidget(basic_group)
        
        # 路径设置组
        path_group = QGroupBox("路径设置")
        path_layout = QFormLayout(path_group)
        
        # 默认下载目录
        download_layout = QHBoxLayout()
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setText("./downloads")
        download_layout.addWidget(self.download_dir_input)
        
        self.browse_download_btn = QPushButton("浏览")
        self.browse_download_btn.clicked.connect(lambda: self._browse_directory(self.download_dir_input))
        download_layout.addWidget(self.browse_download_btn)
        
        path_layout.addRow("默认下载目录:", download_layout)
        
        # 默认输出目录
        output_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText("./output")
        output_layout.addWidget(self.output_dir_input)
        
        self.browse_output_btn = QPushButton("浏览")
        self.browse_output_btn.clicked.connect(lambda: self._browse_directory(self.output_dir_input))
        output_layout.addWidget(self.browse_output_btn)
        
        path_layout.addRow("默认输出目录:", output_layout)
        
        # 临时目录
        temp_layout = QHBoxLayout()
        self.temp_dir_input = QLineEdit()
        self.temp_dir_input.setText("./temp")
        temp_layout.addWidget(self.temp_dir_input)
        
        self.browse_temp_btn = QPushButton("浏览")
        self.browse_temp_btn.clicked.connect(lambda: self._browse_directory(self.temp_dir_input))
        temp_layout.addWidget(self.browse_temp_btn)
        
        path_layout.addRow("临时目录:", temp_layout)
        
        layout.addWidget(path_group)
        
        # 日志设置组
        log_group = QGroupBox("日志设置")
        log_layout = QFormLayout(log_group)
        
        # 日志级别
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText("INFO")
        log_layout.addRow("日志级别:", self.log_level_combo)
        
        # 日志文件大小限制
        self.log_size_spin = QSpinBox()
        self.log_size_spin.setRange(1, 1000)
        self.log_size_spin.setValue(10)
        self.log_size_spin.setSuffix(" MB")
        log_layout.addRow("日志文件大小限制:", self.log_size_spin)
        
        # 日志文件数量
        self.log_count_spin = QSpinBox()
        self.log_count_spin.setRange(1, 100)
        self.log_count_spin.setValue(5)
        log_layout.addRow("保留日志文件数量:", self.log_count_spin)
        
        layout.addWidget(log_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_crawler_tab(self) -> QWidget:
        """创建爬虫设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 网络设置组
        network_group = QGroupBox("网络设置")
        network_layout = QFormLayout(network_group)
        
        # 请求超时
        self.request_timeout_spin = QSpinBox()
        self.request_timeout_spin.setRange(5, 300)
        self.request_timeout_spin.setValue(30)
        self.request_timeout_spin.setSuffix(" 秒")
        network_layout.addRow("请求超时:", self.request_timeout_spin)
        
        # 重试次数
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 10)
        self.retry_count_spin.setValue(3)
        network_layout.addRow("重试次数:", self.retry_count_spin)
        
        # 请求间隔
        self.request_delay_spin = QDoubleSpinBox()
        self.request_delay_spin.setRange(0, 10)
        self.request_delay_spin.setValue(1.0)
        self.request_delay_spin.setSuffix(" 秒")
        network_layout.addRow("请求间隔:", self.request_delay_spin)
        
        # 并发数
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 20)
        self.concurrent_spin.setValue(3)
        network_layout.addRow("最大并发数:", self.concurrent_spin)
        
        layout.addWidget(network_group)
        
        # 代理设置组
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QFormLayout(proxy_group)
        
        # 启用代理
        self.enable_proxy_check = QCheckBox("启用代理")
        proxy_layout.addRow(self.enable_proxy_check)
        
        # 代理类型
        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["HTTP", "HTTPS", "SOCKS5"])
        proxy_layout.addRow("代理类型:", self.proxy_type_combo)
        
        # 代理地址
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("代理服务器地址")
        proxy_layout.addRow("代理地址:", self.proxy_host_input)
        
        # 代理端口
        self.proxy_port_spin = QSpinBox()
        self.proxy_port_spin.setRange(1, 65535)
        self.proxy_port_spin.setValue(8080)
        proxy_layout.addRow("代理端口:", self.proxy_port_spin)
        
        # 代理用户名
        self.proxy_username_input = QLineEdit()
        self.proxy_username_input.setPlaceholderText("用户名（可选）")
        proxy_layout.addRow("用户名:", self.proxy_username_input)
        
        # 代理密码
        self.proxy_password_input = QLineEdit()
        self.proxy_password_input.setEchoMode(QLineEdit.Password)
        self.proxy_password_input.setPlaceholderText("密码（可选）")
        proxy_layout.addRow("密码:", self.proxy_password_input)
        
        layout.addWidget(proxy_group)
        
        # 下载设置组
        download_group = QGroupBox("下载设置")
        download_layout = QFormLayout(download_group)
        
        # 默认视频质量
        self.default_quality_combo = QComboBox()
        self.default_quality_combo.addItems(["最高质量", "1080p", "720p", "480p", "360p"])
        download_layout.addRow("默认视频质量:", self.default_quality_combo)
        
        # 默认下载类型
        self.default_type_combo = QComboBox()
        self.default_type_combo.addItems(["视频+音频", "仅视频", "仅音频"])
        download_layout.addRow("默认下载类型:", self.default_type_combo)
        
        # 自动下载字幕
        self.auto_subtitle_check = QCheckBox("自动下载字幕")
        download_layout.addRow(self.auto_subtitle_check)
        
        # 自动下载缩略图
        self.auto_thumbnail_check = QCheckBox("自动下载缩略图")
        download_layout.addRow(self.auto_thumbnail_check)
        
        layout.addWidget(download_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_video_tab(self) -> QWidget:
        """创建视频处理设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 处理设置组
        process_group = QGroupBox("处理设置")
        process_layout = QFormLayout(process_group)
        
        # 默认帧率
        self.default_fps_spin = QSpinBox()
        self.default_fps_spin.setRange(1, 120)
        self.default_fps_spin.setValue(30)
        self.default_fps_spin.setSuffix(" fps")
        process_layout.addRow("默认帧率:", self.default_fps_spin)
        
        # 默认分辨率
        self.default_resolution_combo = QComboBox()
        self.default_resolution_combo.addItems(["原始分辨率", "1920x1080", "1280x720", "854x480", "640x360"])
        process_layout.addRow("默认分辨率:", self.default_resolution_combo)
        
        # 默认质量
        self.default_video_quality_spin = QSpinBox()
        self.default_video_quality_spin.setRange(1, 100)
        self.default_video_quality_spin.setValue(80)
        self.default_video_quality_spin.setSuffix("%")
        process_layout.addRow("默认质量:", self.default_video_quality_spin)
        
        # 默认编码器
        self.default_encoder_combo = QComboBox()
        self.default_encoder_combo.addItems(["H.264", "H.265", "VP9", "AV1"])
        process_layout.addRow("默认编码器:", self.default_encoder_combo)
        
        layout.addWidget(process_group)
        
        # 性能设置组
        performance_group = QGroupBox("性能设置")
        performance_layout = QFormLayout(performance_group)
        
        # 启用GPU加速
        self.enable_gpu_check = QCheckBox("启用GPU加速")
        performance_layout.addRow(self.enable_gpu_check)
        
        # 启用多线程
        self.enable_multithread_check = QCheckBox("启用多线程处理")
        performance_layout.addRow(self.enable_multithread_check)
        
        # 默认线程数
        self.default_threads_spin = QSpinBox()
        self.default_threads_spin.setRange(1, 32)
        self.default_threads_spin.setValue(4)
        performance_layout.addRow("默认线程数:", self.default_threads_spin)
        
        # 内存限制
        self.memory_limit_spin = QDoubleSpinBox()
        self.memory_limit_spin.setRange(0.5, 64.0)
        self.memory_limit_spin.setValue(4.0)
        self.memory_limit_spin.setSuffix(" GB")
        performance_layout.addRow("内存限制:", self.memory_limit_spin)
        
        layout.addWidget(performance_group)
        
        # 缓存设置组
        cache_group = QGroupBox("缓存设置")
        cache_layout = QFormLayout(cache_group)
        
        # 启用缓存
        self.enable_cache_check = QCheckBox("启用处理缓存")
        cache_layout.addRow(self.enable_cache_check)
        
        # 缓存大小限制
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(100, 10000)
        self.cache_size_spin.setValue(1000)
        self.cache_size_spin.setSuffix(" MB")
        cache_layout.addRow("缓存大小限制:", self.cache_size_spin)
        
        # 缓存过期时间
        self.cache_expire_spin = QSpinBox()
        self.cache_expire_spin.setRange(1, 30)
        self.cache_expire_spin.setValue(7)
        self.cache_expire_spin.setSuffix(" 天")
        cache_layout.addRow("缓存过期时间:", self.cache_expire_spin)
        
        layout.addWidget(cache_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_algorithm_tab(self) -> QWidget:
        """创建算法设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 2D姿态估计设置组
        pose2d_group = QGroupBox("2D姿态估计")
        pose2d_layout = QFormLayout(pose2d_group)
        
        # 默认算法
        self.default_pose2d_combo = QComboBox()
        self.default_pose2d_combo.addItems(["OpenPose", "VitPose", "RTMPose"])
        pose2d_layout.addRow("默认算法:", self.default_pose2d_combo)
        
        # 置信度阈值
        self.pose2d_confidence_spin = QDoubleSpinBox()
        self.pose2d_confidence_spin.setRange(0.0, 1.0)
        self.pose2d_confidence_spin.setValue(0.5)
        self.pose2d_confidence_spin.setSingleStep(0.1)
        pose2d_layout.addRow("置信度阈值:", self.pose2d_confidence_spin)
        
        # 输入尺寸
        self.pose2d_input_size_combo = QComboBox()
        self.pose2d_input_size_combo.addItems(["256x192", "384x288", "512x384", "640x480"])
        pose2d_layout.addRow("输入尺寸:", self.pose2d_input_size_combo)
        
        layout.addWidget(pose2d_group)
        
        # 3D姿态估计设置组
        pose3d_group = QGroupBox("3D姿态估计")
        pose3d_layout = QFormLayout(pose3d_group)
        
        # 默认算法
        self.default_pose3d_combo = QComboBox()
        self.default_pose3d_combo.addItems(["RTMPose3D", "VideoPose3D", "Video2Pose3D"])
        pose3d_layout.addRow("默认算法:", self.default_pose3d_combo)
        
        # 时序窗口大小
        self.pose3d_window_spin = QSpinBox()
        self.pose3d_window_spin.setRange(1, 100)
        self.pose3d_window_spin.setValue(27)
        pose3d_layout.addRow("时序窗口大小:", self.pose3d_window_spin)
        
        # 深度阈值
        self.pose3d_depth_spin = QDoubleSpinBox()
        self.pose3d_depth_spin.setRange(0.0, 10.0)
        self.pose3d_depth_spin.setValue(1.0)
        self.pose3d_depth_spin.setSingleStep(0.1)
        pose3d_layout.addRow("深度阈值:", self.pose3d_depth_spin)
        
        layout.addWidget(pose3d_group)
        
        # 视频描述设置组
        video_desc_group = QGroupBox("视频描述")
        video_desc_layout = QFormLayout(video_desc_group)
        
        # 默认算法
        self.default_video_desc_combo = QComboBox()
        self.default_video_desc_combo.addItems(["ShareGPT4Video", "DescribeAnything", "Vid2Seq"])
        video_desc_layout.addRow("默认算法:", self.default_video_desc_combo)
        
        # 模型缓存路径
        cache_path_layout = QHBoxLayout()
        self.video_desc_cache_input = QLineEdit()
        self.video_desc_cache_input.setText("./models/video_description")
        self.video_desc_cache_input.textChanged.connect(self._on_cache_path_changed)
        cache_path_layout.addWidget(self.video_desc_cache_input)
        
        self.browse_cache_btn = QPushButton("浏览")
        self.browse_cache_btn.clicked.connect(lambda: self._browse_directory(self.video_desc_cache_input))
        cache_path_layout.addWidget(self.browse_cache_btn)
        
        video_desc_layout.addRow("模型缓存路径:", cache_path_layout)
        
        # ShareGPT4Video模型路径
        self.sharegpt4video_model_input = QLineEdit()
        self.sharegpt4video_model_input.setText("Lin-Chen/sharegpt4video-8b")
        self.sharegpt4video_model_input.textChanged.connect(self._on_cache_path_changed)
        video_desc_layout.addRow("ShareGPT4Video模型:", self.sharegpt4video_model_input)
        
        # 描述语言
        self.desc_language_combo = QComboBox()
        self.desc_language_combo.addItems(["中文", "English", "日本語"])
        video_desc_layout.addRow("描述语言:", self.desc_language_combo)
        
        # 描述长度
        self.desc_length_combo = QComboBox()
        self.desc_length_combo.addItems(["简短", "中等", "详细"])
        video_desc_layout.addRow("描述长度:", self.desc_length_combo)
        
        # 最大文本长度
        self.max_text_length_spin = QSpinBox()
        self.max_text_length_spin.setRange(50, 1000)
        self.max_text_length_spin.setValue(200)
        video_desc_layout.addRow("最大文本长度:", self.max_text_length_spin)
        
        layout.addWidget(video_desc_group)
        
        # API配置设置组（用于动作描述过滤）
        api_group = QGroupBox("API配置（动作描述过滤）")
        api_layout = QFormLayout(api_group)
        
        # API端点
        self.api_endpoint_input = QLineEdit()
        self.api_endpoint_input.setPlaceholderText("https://ark.cn-beijing.volces.com/api/v3/chat/completions")
        self.api_endpoint_input.textChanged.connect(self._on_cache_path_changed)
        api_layout.addRow("API端点:", self.api_endpoint_input)
        
        # API密钥
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入API密钥")
        self.api_key_input.textChanged.connect(self._on_cache_path_changed)
        api_layout.addRow("API密钥:", self.api_key_input)
        
        # API模型
        self.api_model_input = QLineEdit()
        self.api_model_input.setText("doubao-1-5-pro-32k-250115")
        self.api_model_input.textChanged.connect(self._on_cache_path_changed)
        api_layout.addRow("API模型:", self.api_model_input)
        
        layout.addWidget(api_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_ui_tab(self) -> QWidget:
        """创建界面设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 外观设置组
        appearance_group = QGroupBox("外观设置")
        appearance_layout = QFormLayout(appearance_group)
        
        # 字体大小
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(10)
        self.font_size_spin.setSuffix(" pt")
        appearance_layout.addRow("字体大小:", self.font_size_spin)
        
        # 字体族
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["系统默认", "微软雅黑", "宋体", "Arial", "Consolas"])
        appearance_layout.addRow("字体族:", self.font_family_combo)
        
        # 窗口透明度
        self.window_opacity_spin = QSpinBox()
        self.window_opacity_spin.setRange(50, 100)
        self.window_opacity_spin.setValue(100)
        self.window_opacity_spin.setSuffix("%")
        appearance_layout.addRow("窗口透明度:", self.window_opacity_spin)
        
        # 启用动画
        self.enable_animation_check = QCheckBox("启用界面动画")
        appearance_layout.addRow(self.enable_animation_check)
        
        layout.addWidget(appearance_group)
        
        # 行为设置组
        behavior_group = QGroupBox("行为设置")
        behavior_layout = QFormLayout(behavior_group)
        
        # 启动时恢复窗口状态
        self.restore_window_check = QCheckBox("启动时恢复窗口状态")
        behavior_layout.addRow(self.restore_window_check)
        
        # 最小化到系统托盘
        self.minimize_to_tray_check = QCheckBox("最小化到系统托盘")
        behavior_layout.addRow(self.minimize_to_tray_check)
        
        # 关闭时确认
        self.confirm_exit_check = QCheckBox("退出时显示确认对话框")
        behavior_layout.addRow(self.confirm_exit_check)
        
        # 自动检查更新
        self.auto_update_check = QCheckBox("启动时自动检查更新")
        behavior_layout.addRow(self.auto_update_check)
        
        layout.addWidget(behavior_group)
        
        # 通知设置组
        notification_group = QGroupBox("通知设置")
        notification_layout = QFormLayout(notification_group)
        
        # 启用桌面通知
        self.desktop_notification_check = QCheckBox("启用桌面通知")
        notification_layout.addRow(self.desktop_notification_check)
        
        # 启用声音通知
        self.sound_notification_check = QCheckBox("启用声音通知")
        notification_layout.addRow(self.sound_notification_check)
        
        # 通知持续时间
        self.notification_duration_spin = QSpinBox()
        self.notification_duration_spin.setRange(1, 30)
        self.notification_duration_spin.setValue(5)
        self.notification_duration_spin.setSuffix(" 秒")
        notification_layout.addRow("通知持续时间:", self.notification_duration_spin)
        
        layout.addWidget(notification_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """创建高级设置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 调试设置组
        debug_group = QGroupBox("调试设置")
        debug_layout = QFormLayout(debug_group)
        
        # 启用调试模式
        self.debug_mode_check = QCheckBox("启用调试模式")
        debug_layout.addRow(self.debug_mode_check)
        
        # 详细日志
        self.verbose_logging_check = QCheckBox("启用详细日志")
        debug_layout.addRow(self.verbose_logging_check)
        
        # 性能监控
        self.performance_monitor_check = QCheckBox("启用性能监控")
        debug_layout.addRow(self.performance_monitor_check)
        
        # 错误报告
        self.error_reporting_check = QCheckBox("启用错误报告")
        debug_layout.addRow(self.error_reporting_check)
        
        layout.addWidget(debug_group)
        
        # 实验性功能组
        experimental_group = QGroupBox("实验性功能")
        experimental_layout = QFormLayout(experimental_group)
        
        # 启用实验性功能
        self.experimental_features_check = QCheckBox("启用实验性功能")
        experimental_layout.addRow(self.experimental_features_check)
        
        # 新算法支持
        self.new_algorithms_check = QCheckBox("启用新算法支持")
        experimental_layout.addRow(self.new_algorithms_check)
        
        # 云端处理
        self.cloud_processing_check = QCheckBox("启用云端处理")
        experimental_layout.addRow(self.cloud_processing_check)
        
        layout.addWidget(experimental_group)
        
        # 插件设置组
        plugin_group = QGroupBox("插件设置")
        plugin_layout = QVBoxLayout(plugin_group)
        
        # 插件列表
        self.plugin_list = QListWidget()
        plugin_layout.addWidget(self.plugin_list)
        
        # 插件控制按钮
        plugin_button_layout = QHBoxLayout()
        
        self.install_plugin_btn = QPushButton("安装插件")
        self.install_plugin_btn.clicked.connect(self._install_plugin)
        plugin_button_layout.addWidget(self.install_plugin_btn)
        
        self.remove_plugin_btn = QPushButton("移除插件")
        self.remove_plugin_btn.clicked.connect(self._remove_plugin)
        plugin_button_layout.addWidget(self.remove_plugin_btn)
        
        self.refresh_plugins_btn = QPushButton("刷新插件")
        self.refresh_plugins_btn.clicked.connect(self._refresh_plugins)
        plugin_button_layout.addWidget(self.refresh_plugins_btn)
        
        plugin_button_layout.addStretch()
        
        plugin_layout.addLayout(plugin_button_layout)
        
        layout.addWidget(plugin_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_control_buttons(self, layout):
        """创建控制按钮"""
        button_layout = QHBoxLayout()
        
        # 重置按钮
        self.reset_btn = QPushButton("重置默认")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self.reset_btn)
        
        # 导入配置按钮
        self.import_btn = QPushButton("导入配置")
        self.import_btn.clicked.connect(self._import_config)
        button_layout.addWidget(self.import_btn)
        
        # 导出配置按钮
        self.export_btn = QPushButton("导出配置")
        self.export_btn.clicked.connect(self._export_config)
        button_layout.addWidget(self.export_btn)
        
        button_layout.addStretch()
        
        # 应用按钮
        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self._apply_config)
        button_layout.addWidget(self.apply_btn)
        
        # 确定按钮
        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self._ok_config)
        button_layout.addWidget(self.ok_btn)
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._cancel_config)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号"""
        # 监听配置变化
        self._connect_config_signals()
    
    def _connect_config_signals(self):
        """连接配置变化信号"""
        # 通用设置
        self.language_combo.currentTextChanged.connect(lambda: self._mark_modified("general"))
        self.theme_combo.currentTextChanged.connect(lambda: self._mark_modified("general"))
        self.auto_save_check.toggled.connect(lambda: self._mark_modified("general"))
        
        # 爬虫设置
        self.request_timeout_spin.valueChanged.connect(lambda: self._mark_modified("crawler"))
        self.retry_count_spin.valueChanged.connect(lambda: self._mark_modified("crawler"))
        
        # 视频处理设置
        self.default_fps_spin.valueChanged.connect(lambda: self._mark_modified("video_processing"))
        self.default_resolution_combo.currentTextChanged.connect(lambda: self._mark_modified("video_processing"))
        
        # 算法设置
        self.default_pose2d_combo.currentTextChanged.connect(lambda: self._mark_modified("algorithms"))
        self.default_pose3d_combo.currentTextChanged.connect(lambda: self._mark_modified("algorithms"))
        self.default_video_desc_combo.currentTextChanged.connect(lambda: self._mark_modified("algorithms"))
        
        # 界面设置
        self.font_size_spin.valueChanged.connect(lambda: self._mark_modified("ui"))
        self.theme_combo.currentTextChanged.connect(lambda: self._mark_modified("ui"))
    
    def _mark_modified(self, config_type: str):
        """标记配置已修改"""
        self.modified_configs.add(config_type)
        self.apply_btn.setEnabled(True)
    
    def _load_configs(self):
        """加载配置"""
        try:
            # 加载通用设置
            general_config = self.config_manager.get_config("general", {})
            self._load_general_config(general_config)
            
            # 加载爬虫设置
            crawler_config = self.config_manager.get_config("crawler", {})
            self._load_crawler_config(crawler_config)
            
            # 加载视频处理设置
            video_config = self.config_manager.get_config("video_processing", {})
            self._load_video_config(video_config)
            
            # 加载算法设置
            algorithm_config = self.config_manager.get_config("algorithms", {})
            self._load_algorithm_config(algorithm_config)
            
            # 加载界面设置
            ui_config = self.config_manager.get_config("ui", {})
            self._load_ui_config(ui_config)
            
            # 加载高级设置
            advanced_config = self.config_manager.get_config("advanced", {})
            self._load_advanced_config(advanced_config)
            
            # 清除修改标记
            self.modified_configs.clear()
            self.apply_btn.setEnabled(False)
            
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            QMessageBox.critical(self, "错误", f"加载配置失败: {e}")
    
    def _load_general_config(self, config: dict):
        """加载通用配置"""
        self.language_combo.setCurrentText(config.get("language", "简体中文"))
        self.theme_combo.setCurrentText(config.get("theme", "默认主题"))
        self.auto_save_check.setChecked(config.get("auto_save", True))
        self.auto_save_interval_spin.setValue(config.get("auto_save_interval", 5))
        
        self.download_dir_input.setText(config.get("download_dir", "./downloads"))
        self.output_dir_input.setText(config.get("output_dir", "./output"))
        self.temp_dir_input.setText(config.get("temp_dir", "./temp"))
        
        self.log_level_combo.setCurrentText(config.get("log_level", "INFO"))
        self.log_size_spin.setValue(config.get("log_size_mb", 10))
        self.log_count_spin.setValue(config.get("log_count", 5))
    
    def _load_crawler_config(self, config: dict):
        """加载爬虫配置"""
        self.request_timeout_spin.setValue(config.get("request_timeout", 30))
        self.retry_count_spin.setValue(config.get("retry_count", 3))
        self.request_delay_spin.setValue(config.get("request_delay", 1.0))
        self.concurrent_spin.setValue(config.get("max_concurrent", 3))
        
        proxy_config = config.get("proxy", {})
        self.enable_proxy_check.setChecked(proxy_config.get("enabled", False))
        self.proxy_type_combo.setCurrentText(proxy_config.get("type", "HTTP"))
        self.proxy_host_input.setText(proxy_config.get("host", ""))
        self.proxy_port_spin.setValue(proxy_config.get("port", 8080))
        self.proxy_username_input.setText(proxy_config.get("username", ""))
        self.proxy_password_input.setText(proxy_config.get("password", ""))
        
        self.default_quality_combo.setCurrentText(config.get("default_quality", "最高质量"))
        self.default_type_combo.setCurrentText(config.get("default_type", "视频+音频"))
        self.auto_subtitle_check.setChecked(config.get("auto_subtitle", False))
        self.auto_thumbnail_check.setChecked(config.get("auto_thumbnail", False))
    
    def _load_video_config(self, config: dict):
        """加载视频处理配置"""
        self.default_fps_spin.setValue(config.get("default_fps", 30))
        self.default_resolution_combo.setCurrentText(config.get("default_resolution", "原始分辨率"))
        self.default_video_quality_spin.setValue(config.get("default_quality", 80))
        self.default_encoder_combo.setCurrentText(config.get("default_encoder", "H.264"))
        
        self.enable_gpu_check.setChecked(config.get("enable_gpu", False))
        self.enable_multithread_check.setChecked(config.get("enable_multithread", True))
        self.default_threads_spin.setValue(config.get("default_threads", 4))
        self.memory_limit_spin.setValue(config.get("memory_limit_gb", 4.0))
        
        cache_config = config.get("cache", {})
        self.enable_cache_check.setChecked(cache_config.get("enabled", True))
        self.cache_size_spin.setValue(cache_config.get("size_mb", 1000))
        self.cache_expire_spin.setValue(cache_config.get("expire_days", 7))
    
    def _load_algorithm_config(self, config: dict):
        """加载算法配置"""
        pose2d_config = config.get("pose_2d", {})
        self.default_pose2d_combo.setCurrentText(pose2d_config.get("default_algorithm", "OpenPose"))
        self.pose2d_confidence_spin.setValue(pose2d_config.get("confidence_threshold", 0.5))
        self.pose2d_input_size_combo.setCurrentText(pose2d_config.get("input_size", "256x192"))
        
        pose3d_config = config.get("pose_3d", {})
        self.default_pose3d_combo.setCurrentText(pose3d_config.get("default_algorithm", "RTMPose3D"))
        self.pose3d_window_spin.setValue(pose3d_config.get("temporal_window", 27))
        self.pose3d_depth_spin.setValue(pose3d_config.get("depth_threshold", 1.0))
        
        video_desc_config = config.get("video_description", {})
        self.default_video_desc_combo.setCurrentText(video_desc_config.get("default_algorithm", "ShareGPT4Video"))
        
        # 从cache_config.txt文件读取配置
        cache_config = self._load_cache_config()
        self.video_desc_cache_input.setText(cache_config.get("cache_path", video_desc_config.get("cache_path", "./models/video_description")))
        self.sharegpt4video_model_input.setText(cache_config.get("sharegpt4video_model_path", video_desc_config.get("sharegpt4video_model_path", "Lin-Chen/sharegpt4video-8b")))
        
        self.desc_language_combo.setCurrentText(video_desc_config.get("language", "中文"))
        self.desc_length_combo.setCurrentText(video_desc_config.get("length", "中等"))
        self.max_text_length_spin.setValue(video_desc_config.get("max_text_length", 200))
        
        api_config = config.get("api", {})
        self.api_endpoint_input.setText(cache_config.get("api_endpoint", api_config.get("endpoint", "")))
        self.api_key_input.setText(cache_config.get("api_key", api_config.get("key", "")))
        self.api_model_input.setText(cache_config.get("api_model", api_config.get("model", "gpt-3.5-turbo")))
    
    def _load_ui_config(self, config: dict):
        """加载界面配置"""
        self.font_size_spin.setValue(config.get("font_size", 10))
        self.font_family_combo.setCurrentText(config.get("font_family", "系统默认"))
        self.window_opacity_spin.setValue(config.get("window_opacity", 100))
        self.enable_animation_check.setChecked(config.get("enable_animation", True))
        
        self.restore_window_check.setChecked(config.get("restore_window", True))
        self.minimize_to_tray_check.setChecked(config.get("minimize_to_tray", False))
        self.confirm_exit_check.setChecked(config.get("confirm_exit", True))
        self.auto_update_check.setChecked(config.get("auto_update", True))
        
        notification_config = config.get("notification", {})
        self.desktop_notification_check.setChecked(notification_config.get("desktop", True))
        self.sound_notification_check.setChecked(notification_config.get("sound", False))
        self.notification_duration_spin.setValue(notification_config.get("duration", 5))
    
    def _load_advanced_config(self, config: dict):
        """加载高级配置"""
        debug_config = config.get("debug", {})
        self.debug_mode_check.setChecked(debug_config.get("enabled", False))
        self.verbose_logging_check.setChecked(debug_config.get("verbose_logging", False))
        self.performance_monitor_check.setChecked(debug_config.get("performance_monitor", False))
        self.error_reporting_check.setChecked(debug_config.get("error_reporting", True))
        
        experimental_config = config.get("experimental", {})
        self.experimental_features_check.setChecked(experimental_config.get("enabled", False))
        self.new_algorithms_check.setChecked(experimental_config.get("new_algorithms", False))
        self.cloud_processing_check.setChecked(experimental_config.get("cloud_processing", False))
        
        # 加载插件列表
        self._refresh_plugins()
    
    def _on_cache_path_changed(self):
        """缓存路径变更时同步到cache_config.txt文件"""
        try:
            import os
            cache_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache_config.txt')
            
            # 读取现有配置
            config_data = {}
            if os.path.exists(cache_config_path):
                with open(cache_config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            config_data[key] = value
            
            # 更新配置
            config_data['cache_path'] = self.video_desc_cache_input.text()
            config_data['sharegpt4video_model_path'] = self.sharegpt4video_model_input.text()
            config_data['api_endpoint'] = self.api_endpoint_input.text()
            config_data['api_key'] = self.api_key_input.text()
            config_data['api_model'] = self.api_model_input.text()
            
            # 写入文件
            with open(cache_config_path, 'w', encoding='utf-8') as f:
                for key, value in config_data.items():
                    f.write(f"{key}={value}\n")
                    
        except Exception as e:
            print(f"更新cache_config.txt失败: {e}")
        
        self._mark_modified("algorithms")
    
    def _load_cache_config(self):
        """从cache_config.txt文件加载配置"""
        try:
            import os
            cache_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache_config.txt')
            
            config_data = {}
            if os.path.exists(cache_config_path):
                with open(cache_config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            config_data[key] = value
            
            return config_data
        except Exception as e:
            print(f"读取cache_config.txt失败: {e}")
            return {}
    
    # 槽函数实现
    def _browse_directory(self, line_edit: QLineEdit):
        """浏览目录"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self, "选择目录", line_edit.text()
            )
            if dir_path:
                line_edit.setText(dir_path)
                self._mark_modified("general")
        except Exception as e:
            self.logger.error(f"浏览目录失败: {e}")
    
    def _install_plugin(self):
        """安装插件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择插件文件", "", "插件文件 (*.py *.zip);;所有文件 (*)"
            )
            
            if file_path:
                # TODO: 实现插件安装功能
                QMessageBox.information(self, "信息", "插件安装功能待实现")
                
        except Exception as e:
            self.logger.error(f"安装插件失败: {e}")
            QMessageBox.critical(self, "错误", f"安装插件失败: {e}")
    
    def _remove_plugin(self):
        """移除插件"""
        try:
            current_item = self.plugin_list.currentItem()
            if current_item:
                # TODO: 实现插件移除功能
                QMessageBox.information(self, "信息", "插件移除功能待实现")
        except Exception as e:
            self.logger.error(f"移除插件失败: {e}")
    
    def _refresh_plugins(self):
        """刷新插件列表"""
        try:
            self.plugin_list.clear()
            # TODO: 实现插件列表刷新
            # 这里应该从插件管理器获取插件列表
            pass
        except Exception as e:
            self.logger.error(f"刷新插件列表失败: {e}")
    
    def _reset_to_defaults(self):
        """重置为默认设置"""
        try:
            reply = QMessageBox.question(
                self, "确认重置", "确定要重置所有设置为默认值吗？\n此操作不可撤销。",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # TODO: 实现重置默认设置功能
                QMessageBox.information(self, "信息", "重置默认设置功能待实现")
                
        except Exception as e:
            self.logger.error(f"重置默认设置失败: {e}")
    
    def _import_config(self):
        """导入配置"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入配置文件", "", "配置文件 (*.json *.yaml *.yml);;所有文件 (*)"
            )
            
            if file_path:
                # TODO: 实现配置导入功能
                QMessageBox.information(self, "信息", "配置导入功能待实现")
                
        except Exception as e:
            self.logger.error(f"导入配置失败: {e}")
            QMessageBox.critical(self, "错误", f"导入配置失败: {e}")
    
    def _export_config(self):
        """导出配置"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出配置文件", "config.json", "配置文件 (*.json *.yaml *.yml);;所有文件 (*)"
            )
            
            if file_path:
                # TODO: 实现配置导出功能
                QMessageBox.information(self, "信息", "配置导出功能待实现")
                
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            QMessageBox.critical(self, "错误", f"导出配置失败: {e}")
    
    def _apply_config(self):
        """应用配置"""
        try:
            # 收集所有配置
            configs = self._collect_all_configs()
            
            # 保存配置
            for config_type, config_data in configs.items():
                if config_type in self.modified_configs:
                    self.config_manager.set_config(config_type, config_data)
                    self.config_changed.emit(config_type, config_data)
            
            # 清除修改标记
            self.modified_configs.clear()
            self.apply_btn.setEnabled(False)
            
            QMessageBox.information(self, "信息", "配置已应用")
            
        except Exception as e:
            self.logger.error(f"应用配置失败: {e}")
            QMessageBox.critical(self, "错误", f"应用配置失败: {e}")
    
    def _ok_config(self):
        """确定配置"""
        try:
            if self.modified_configs:
                self._apply_config()
            self.close()
        except Exception as e:
            self.logger.error(f"确定配置失败: {e}")
    
    def _cancel_config(self):
        """取消配置"""
        try:
            if self.modified_configs:
                reply = QMessageBox.question(
                    self, "确认取消", "有未保存的配置更改，确定要取消吗？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    return
            
            self.close()
            
        except Exception as e:
            self.logger.error(f"取消配置失败: {e}")
    
    def _collect_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """收集所有配置"""
        configs = {}
        
        # 通用配置
        configs["general"] = {
            "language": self.language_combo.currentText(),
            "theme": self.theme_combo.currentText(),
            "auto_save": self.auto_save_check.isChecked(),
            "auto_save_interval": self.auto_save_interval_spin.value(),
            "download_dir": self.download_dir_input.text(),
            "output_dir": self.output_dir_input.text(),
            "temp_dir": self.temp_dir_input.text(),
            "log_level": self.log_level_combo.currentText(),
            "log_size_mb": self.log_size_spin.value(),
            "log_count": self.log_count_spin.value()
        }
        
        # 爬虫配置
        configs["crawler"] = {
            "request_timeout": self.request_timeout_spin.value(),
            "retry_count": self.retry_count_spin.value(),
            "request_delay": self.request_delay_spin.value(),
            "max_concurrent": self.concurrent_spin.value(),
            "proxy": {
                "enabled": self.enable_proxy_check.isChecked(),
                "type": self.proxy_type_combo.currentText(),
                "host": self.proxy_host_input.text(),
                "port": self.proxy_port_spin.value(),
                "username": self.proxy_username_input.text(),
                "password": self.proxy_password_input.text()
            },
            "default_quality": self.default_quality_combo.currentText(),
            "default_type": self.default_type_combo.currentText(),
            "auto_subtitle": self.auto_subtitle_check.isChecked(),
            "auto_thumbnail": self.auto_thumbnail_check.isChecked()
        }
        
        # 视频处理配置
        configs["video_processing"] = {
            "default_fps": self.default_fps_spin.value(),
            "default_resolution": self.default_resolution_combo.currentText(),
            "default_quality": self.default_video_quality_spin.value(),
            "default_encoder": self.default_encoder_combo.currentText(),
            "enable_gpu": self.enable_gpu_check.isChecked(),
            "enable_multithread": self.enable_multithread_check.isChecked(),
            "default_threads": self.default_threads_spin.value(),
            "memory_limit_gb": self.memory_limit_spin.value(),
            "cache": {
                "enabled": self.enable_cache_check.isChecked(),
                "size_mb": self.cache_size_spin.value(),
                "expire_days": self.cache_expire_spin.value()
            }
        }
        
        # 算法配置
        configs["algorithms"] = {
            "pose_2d": {
                "default_algorithm": self.default_pose2d_combo.currentText(),
                "confidence_threshold": self.pose2d_confidence_spin.value(),
                "input_size": self.pose2d_input_size_combo.currentText()
            },
            "pose_3d": {
                "default_algorithm": self.default_pose3d_combo.currentText(),
                "temporal_window": self.pose3d_window_spin.value(),
                "depth_threshold": self.pose3d_depth_spin.value()
            },
            "video_description": {
                "default_algorithm": self.default_video_desc_combo.currentText(),
                "cache_path": self.video_desc_cache_input.text(),
                "sharegpt4video_model_path": self.sharegpt4video_model_input.text(),
                "language": self.desc_language_combo.currentText(),
                "length": self.desc_length_combo.currentText(),
                "max_text_length": self.max_text_length_spin.value()
            },
            "api": {
                "endpoint": self.api_endpoint_input.text(),
                "key": self.api_key_input.text(),
                "model": self.api_model_input.text()
            }
        }
        
        # 界面配置
        configs["ui"] = {
            "font_size": self.font_size_spin.value(),
            "font_family": self.font_family_combo.currentText(),
            "window_opacity": self.window_opacity_spin.value(),
            "enable_animation": self.enable_animation_check.isChecked(),
            "restore_window": self.restore_window_check.isChecked(),
            "minimize_to_tray": self.minimize_to_tray_check.isChecked(),
            "confirm_exit": self.confirm_exit_check.isChecked(),
            "auto_update": self.auto_update_check.isChecked(),
            "notification": {
                "desktop": self.desktop_notification_check.isChecked(),
                "sound": self.sound_notification_check.isChecked(),
                "duration": self.notification_duration_spin.value()
            }
        }
        
        # 高级配置
        configs["advanced"] = {
            "debug": {
                "enabled": self.debug_mode_check.isChecked(),
                "verbose_logging": self.verbose_logging_check.isChecked(),
                "performance_monitor": self.performance_monitor_check.isChecked(),
                "error_reporting": self.error_reporting_check.isChecked()
            },
            "experimental": {
                "enabled": self.experimental_features_check.isChecked(),
                "new_algorithms": self.new_algorithms_check.isChecked(),
                "cloud_processing": self.cloud_processing_check.isChecked()
            }
        }
        
        return configs
    
    # 公共接口
    def get_config(self, config_type: str) -> Dict[str, Any]:
        """获取指定类型的配置"""
        configs = self._collect_all_configs()
        return configs.get(config_type, {})
    
    def set_config(self, config_type: str, config_data: Dict[str, Any]):
        """设置指定类型的配置"""
        try:
            if config_type == "general":
                self._load_general_config(config_data)
            elif config_type == "crawler":
                self._load_crawler_config(config_data)
            elif config_type == "video_processing":
                self._load_video_config(config_data)
            elif config_type == "algorithms":
                self._load_algorithm_config(config_data)
            elif config_type == "ui":
                self._load_ui_config(config_data)
            elif config_type == "advanced":
                self._load_advanced_config(config_data)
                
        except Exception as e:
            self.logger.error(f"设置配置失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            self.logger.info("配置界面组件资源清理完成")
        except Exception as e:
            self.logger.error(f"配置界面组件资源清理失败: {e}")