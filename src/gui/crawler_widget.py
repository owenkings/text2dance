# -*- coding: utf-8 -*-
"""
爬虫界面组件
提供视频爬取功能的用户界面
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
    QListWidget, QListWidgetItem, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon
from ..crawler.crawler_manager import DownloadStatus

from ..crawler.crawler_manager import CrawlerManager
from ..utils.logger import Logger

class CrawlerThread(QThread):
    """爬虫工作线程"""
    
    progress_updated = pyqtSignal(float)
    status_updated = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, crawler_manager, task_config):
        super().__init__()
        self.crawler_manager = crawler_manager
        self.task_config = task_config
        self.is_running = True
    
    def run(self):
        try:
            # 执行爬取任务
            result = self.crawler_manager.crawl(
                url=self.task_config['url'],
                platform=self.task_config['platform'],
                output_dir=self.task_config['output_dir'],
                progress_callback=self.progress_updated.emit,
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

class SearchThread(QThread):
    """搜索工作线程"""
    
    progress_updated = pyqtSignal(int, int)  # current, total
    status_updated = pyqtSignal(str)
    result_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, crawler_manager, keyword, platform, limit):
        super().__init__()
        self.crawler_manager = crawler_manager
        self.keyword = keyword
        self.platform = platform
        self.limit = limit
        self.is_running = True
    
    def run(self):
        try:
            self.status_updated.emit("正在搜索...")
            
            # 如果限制为0，表示无限制，设置为一个较大的数值
            search_limit = self.limit if self.limit > 0 else 10000
            
            # 执行搜索
            results = self.crawler_manager.search_videos(
                keyword=self.keyword,
                platform=self.platform,
                limit=search_limit
            )
            
            if self.is_running:
                self.result_ready.emit(results)
                
        except Exception as e:
            if self.is_running:
                self.error_occurred.emit(str(e))
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()

class DownloadThread(QThread):
    """下载工作线程"""
    
    progress_updated = pyqtSignal(int, int)  # current, total
    status_updated = pyqtSignal(str)
    result_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, crawler_manager, urls, quality, max_retries):
        super().__init__()
        self.crawler_manager = crawler_manager
        self.urls = urls
        self.quality = quality
        self.max_retries = max_retries
        self.is_running = True
    
    def run(self):
        try:
            self.status_updated.emit("正在下载...")
            
            # 执行批量下载
            task_ids = self.crawler_manager.batch_download_urls(
                urls=self.urls,
                quality=self.quality,
                max_retries=self.max_retries,
                skip_duplicate_check=False,
                progress_callback=self._on_progress
            )
            
            if self.is_running:
                self.result_ready.emit(task_ids)
                
        except Exception as e:
            if self.is_running:
                self.error_occurred.emit(str(e))
    
    def _on_progress(self, current, total):
        """进度回调"""
        if self.is_running:
            self.progress_updated.emit(int(current), int(total))
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()

class SearchDownloadThread(QThread):
    """搜索并下载工作线程"""
    
    progress_updated = pyqtSignal(int, int)  # current, total
    status_updated = pyqtSignal(str)
    result_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, crawler_manager, keyword, platform, search_limit, download_limit, quality, output_dir):
        super().__init__()
        self.crawler_manager = crawler_manager
        self.keyword = keyword
        self.platform = platform
        self.search_limit = search_limit
        self.download_limit = download_limit
        self.quality = quality
        self.output_dir = output_dir
        self.is_running = True
    
    def run(self):
        try:
            self.status_updated.emit("正在搜索并下载...")
            
            # 如果搜索限制为0，表示无限制
            search_limit = self.search_limit if self.search_limit > 0 else 10000
            
            # 执行搜索并下载
            task_ids = self.crawler_manager.batch_search_and_download(
                keyword=self.keyword,
                platform=self.platform,
                search_limit=search_limit,
                download_limit=self.download_limit,
                quality=self.quality,
                output_dir=self.output_dir,
                progress_callback=self._on_progress
            )
            
            if self.is_running:
                self.result_ready.emit(task_ids)
                
        except Exception as e:
            if self.is_running:
                self.error_occurred.emit(str(e))
    
    def _on_progress(self, current, total):
        """进度回调"""
        if self.is_running:
            self.progress_updated.emit(int(current), int(total))
    
    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()

class CrawlerWidget(QWidget):
    """爬虫界面组件"""
    
    # 信号定义
    status_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(int)
    
    def __init__(self, config_manager):
        super().__init__()
        
        self.config_manager = config_manager
        self.logger = Logger().get_logger("CrawlerWidget")
        
        # 爬虫管理器
        self.crawler_manager = CrawlerManager(config_manager)
        
        # 获取核心任务管理器实例
        try:
            from ..core.task_manager import CoreTaskManager
            self.core_task_manager = CoreTaskManager()
        except ImportError:
            self.core_task_manager = None
            self.logger.warning("核心任务管理器不可用")
        
        # 工作线程
        self.crawler_thread = None
        self.search_thread = None
        self.download_thread = None
        self.search_download_thread = None
        
        # 任务历史
        self.task_history = []
        
        # 初始化界面
        self._init_ui()
        self._connect_signals()
        self._load_settings()
        
        # 定时刷新任务列表
        self.task_refresh_timer = QTimer()
        self.task_refresh_timer.timeout.connect(self._auto_refresh_tasks)
        self.task_refresh_timer.start(5000)  # 每5秒刷新一次
        
        # 注册进度和状态回调
        self.crawler_manager.add_progress_callback(self._on_task_progress_updated)
        if hasattr(self.crawler_manager, 'add_status_callback'):
            self.crawler_manager.add_status_callback(self._on_task_status_updated)
        
        self.logger.info("爬虫界面组件初始化完成")
    
    def _reset_search_ui(self):
        """重置搜索UI状态"""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("搜索")
        self.search_progress.setVisible(False)
    
    def _reset_download_ui(self):
        """重置下载UI状态"""
        self.download_selected_btn.setEnabled(True)
        self.download_selected_btn.setText("下载选中")
        self.download_progress.setVisible(False)
    
    def _on_search_progress(self, current, total, message):
        """搜索进度更新"""
        if total > 0:
            self.search_progress.setMaximum(total)
            self.search_progress.setValue(current)
        self.search_btn.setText(f"搜索中... {message}")
    
    def _on_search_completed(self, results):
        """搜索完成"""
        self._update_search_results(results)
        self._reset_search_ui()
        
        if results:
            QMessageBox.information(self, "信息", f"找到 {len(results)} 个视频")
        else:
            QMessageBox.warning(self, "警告", "没有找到相关视频")
    
    def _on_search_error(self, error_msg):
        """搜索错误"""
        self.logger.error(f"搜索失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"搜索失败: {error_msg}")
        self._reset_search_ui()
    
    def _on_download_progress(self, current, total):
        """下载进度更新"""
        self.download_progress.setValue(current)
        self.download_selected_btn.setText(f"下载中... ({current}/{total})")
    
    def _on_download_completed(self, task_ids):
        """下载完成"""
        self._reset_download_ui()
        
        if task_ids:
            QMessageBox.information(self, "信息", f"成功添加 {len(task_ids)} 个下载任务")
            # 添加回调监听
            self.crawler_manager.add_progress_callback(self._on_task_progress_updated)
            self.crawler_manager.add_status_callback(self._on_task_status_updated)
        else:
            QMessageBox.warning(self, "警告", "添加下载任务失败")
    
    def _on_download_error(self, error_msg):
        """下载错误"""
        self.logger.error(f"下载失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"下载失败: {error_msg}")
        self._reset_download_ui()
    
    def _reset_search_download_ui(self):
        """重置搜索下载UI状态"""
        self.search_download_btn.setEnabled(True)
        self.search_download_btn.setText("搜索并下载")
    
    def _on_search_download_completed(self, task_ids):
        """搜索下载完成"""
        self._reset_search_download_ui()
        
        if task_ids:
            QMessageBox.information(self, "信息", f"成功添加 {len(task_ids)} 个下载任务")
            # 添加回调监听
            self.crawler_manager.add_progress_callback(self._on_task_progress_updated)
            self.crawler_manager.add_status_callback(self._on_task_status_updated)
        else:
            QMessageBox.warning(self, "警告", "没有找到可下载的视频")
    
    def _on_search_download_error(self, error_msg):
        """搜索下载错误"""
        self.logger.error(f"搜索下载失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"搜索下载失败: {error_msg}")
        self._reset_search_download_ui()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 单个URL爬取选项卡
        self.single_tab = self._create_single_crawl_tab()
        self.tab_widget.addTab(self.single_tab, "单个URL")
        
        # 批量爬取选项卡
        self.batch_tab = self._create_batch_crawl_tab()
        self.tab_widget.addTab(self.batch_tab, "批量爬取")
        
        # 搜索爬取选项卡
        self.search_tab = self._create_search_crawl_tab()
        self.tab_widget.addTab(self.search_tab, "搜索爬取")
        
        # 任务管理选项卡
        self.task_tab = self._create_task_management_tab()
        self.tab_widget.addTab(self.task_tab, "任务管理")
        
        layout.addWidget(self.tab_widget)
        
        # 状态栏
        self._create_status_bar(layout)
    
    def _create_single_crawl_tab(self) -> QWidget:
        """创建单个URL爬取选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # URL输入组
        url_group = QGroupBox("URL设置")
        url_layout = QGridLayout(url_group)
        
        # URL输入
        url_layout.addWidget(QLabel("视频URL:"), 0, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入B站、YouTube或抖音视频URL")
        url_layout.addWidget(self.url_input, 0, 1)
        
        # 平台选择
        url_layout.addWidget(QLabel("平台:"), 1, 0)
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["自动检测", "bilibili", "youtube", "douyin"])
        url_layout.addWidget(self.platform_combo, 1, 1)
        
        # 输出目录
        url_layout.addWidget(QLabel("输出目录:"), 2, 0)
        output_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText("./downloads")
        output_layout.addWidget(self.output_dir_input)
        
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(self.browse_btn)
        
        url_layout.addLayout(output_layout, 2, 1)
        
        layout.addWidget(url_group)
        
        # 下载选项组
        options_group = QGroupBox("下载选项")
        options_layout = QGridLayout(options_group)
        
        # 视频质量
        options_layout.addWidget(QLabel("视频质量:"), 0, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["最高质量", "1080p", "720p", "480p", "360p"])
        options_layout.addWidget(self.quality_combo, 0, 1)
        
        # 下载类型
        options_layout.addWidget(QLabel("下载类型:"), 1, 0)
        self.download_type_combo = QComboBox()
        self.download_type_combo.addItems(["视频+音频", "仅视频", "仅音频"])
        options_layout.addWidget(self.download_type_combo, 1, 1)
        
        # 字幕选项
        self.subtitle_check = QCheckBox("下载字幕")
        options_layout.addWidget(self.subtitle_check, 2, 0)
        
        # 缩略图选项
        self.thumbnail_check = QCheckBox("下载缩略图")
        options_layout.addWidget(self.thumbnail_check, 2, 1)
        
        # 代理设置
        options_layout.addWidget(QLabel("代理:"), 3, 0)
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("http://proxy:port (可选)")
        options_layout.addWidget(self.proxy_input, 3, 1)
        
        layout.addWidget(options_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_single_btn = QPushButton("开始下载")
        self.start_single_btn.clicked.connect(self._start_single_crawl)
        button_layout.addWidget(self.start_single_btn)
        
        self.stop_single_btn = QPushButton("停止下载")
        self.stop_single_btn.setEnabled(False)
        self.stop_single_btn.clicked.connect(self._stop_crawl)
        button_layout.addWidget(self.stop_single_btn)
        
        button_layout.addStretch()
        
        self.preview_btn = QPushButton("预览信息")
        self.preview_btn.clicked.connect(self._preview_video_info)
        button_layout.addWidget(self.preview_btn)
        
        layout.addLayout(button_layout)
        
        # 进度显示
        progress_group = QGroupBox("下载进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.single_progress = QProgressBar()
        progress_layout.addWidget(self.single_progress)
        
        self.single_status = QLabel("就绪")
        progress_layout.addWidget(self.single_status)
        
        layout.addWidget(progress_group)
        
        # 结果显示
        result_group = QGroupBox("下载结果")
        result_layout = QVBoxLayout(result_group)
        
        self.single_result = QTextEdit()
        self.single_result.setMaximumHeight(150)
        self.single_result.setReadOnly(True)
        result_layout.addWidget(self.single_result)
        
        layout.addWidget(result_group)
        
        return widget
    
    def _create_batch_crawl_tab(self) -> QWidget:
        """创建批量爬取选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # URL列表组
        url_list_group = QGroupBox("URL列表")
        url_list_layout = QVBoxLayout(url_list_group)
        
        # URL输入区域
        input_layout = QHBoxLayout()
        
        self.batch_url_input = QLineEdit()
        self.batch_url_input.setPlaceholderText("输入URL后按回车添加")
        input_layout.addWidget(self.batch_url_input)
        
        self.add_url_btn = QPushButton("添加")
        self.add_url_btn.clicked.connect(self._add_batch_url)
        input_layout.addWidget(self.add_url_btn)
        
        self.load_urls_btn = QPushButton("从文件加载")
        self.load_urls_btn.clicked.connect(self._load_urls_from_file)
        input_layout.addWidget(self.load_urls_btn)
        
        url_list_layout.addLayout(input_layout)
        
        # URL列表
        self.url_list = QListWidget()
        self.url_list.setMaximumHeight(150)
        url_list_layout.addWidget(self.url_list)
        
        # 列表控制按钮
        list_control_layout = QHBoxLayout()
        
        self.remove_url_btn = QPushButton("移除选中")
        self.remove_url_btn.clicked.connect(self._remove_selected_url)
        list_control_layout.addWidget(self.remove_url_btn)
        
        self.clear_urls_btn = QPushButton("清空列表")
        self.clear_urls_btn.clicked.connect(self._clear_url_list)
        list_control_layout.addWidget(self.clear_urls_btn)
        
        list_control_layout.addStretch()
        
        url_list_layout.addLayout(list_control_layout)
        
        layout.addWidget(url_list_group)
        
        # 批量选项组
        batch_options_group = QGroupBox("批量选项")
        batch_options_layout = QGridLayout(batch_options_group)
        
        # 并发数
        batch_options_layout.addWidget(QLabel("并发数:"), 0, 0)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(3)
        batch_options_layout.addWidget(self.concurrent_spin, 0, 1)
        
        # 延迟设置
        batch_options_layout.addWidget(QLabel("下载间隔(秒):"), 1, 0)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 60)
        self.delay_spin.setValue(1.0)
        batch_options_layout.addWidget(self.delay_spin, 1, 1)
        
        # 失败重试
        batch_options_layout.addWidget(QLabel("重试次数:"), 2, 0)
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        batch_options_layout.addWidget(self.retry_spin, 2, 1)
        
        # 错误处理
        self.continue_on_error_check = QCheckBox("遇到错误继续")
        self.continue_on_error_check.setChecked(True)
        batch_options_layout.addWidget(self.continue_on_error_check, 3, 0, 1, 2)
        
        # 断点续传
        self.resume_download_check = QCheckBox("启用断点续传")
        self.resume_download_check.setChecked(True)
        self.resume_download_check.setToolTip("程序重启后自动恢复未完成的下载任务")
        batch_options_layout.addWidget(self.resume_download_check, 4, 0, 1, 2)
        
        # 重复检测
        self.skip_duplicate_check = QCheckBox("跳过重复下载")
        self.skip_duplicate_check.setChecked(True)
        self.skip_duplicate_check.setToolTip("检测并跳过已下载的视频")
        batch_options_layout.addWidget(self.skip_duplicate_check, 5, 0, 1, 2)
        
        layout.addWidget(batch_options_group)
        
        # 控制按钮
        batch_button_layout = QHBoxLayout()
        
        self.start_batch_btn = QPushButton("开始批量下载")
        self.start_batch_btn.clicked.connect(self._start_batch_crawl)
        batch_button_layout.addWidget(self.start_batch_btn)
        
        self.pause_all_btn = QPushButton("全部暂停")
        self.pause_all_btn.clicked.connect(self._pause_all_tasks)
        self.pause_all_btn.setEnabled(False)
        batch_button_layout.addWidget(self.pause_all_btn)
        
        self.resume_all_btn = QPushButton("全部恢复")
        self.resume_all_btn.clicked.connect(self._resume_all_tasks)
        self.resume_all_btn.setEnabled(False)
        batch_button_layout.addWidget(self.resume_all_btn)
        
        self.stop_batch_btn = QPushButton("全部取消")
        self.stop_batch_btn.setEnabled(False)
        self.stop_batch_btn.clicked.connect(self._cancel_all_tasks)
        batch_button_layout.addWidget(self.stop_batch_btn)
        
        batch_button_layout.addStretch()
        
        layout.addLayout(batch_button_layout)
        
        # 批量进度
        batch_progress_group = QGroupBox("批量进度")
        batch_progress_layout = QVBoxLayout(batch_progress_group)
        
        self.batch_progress = QProgressBar()
        batch_progress_layout.addWidget(self.batch_progress)
        
        self.batch_status = QLabel("就绪")
        batch_progress_layout.addWidget(self.batch_status)
        
        layout.addWidget(batch_progress_group)
        
        return widget
    
    def _create_search_crawl_tab(self) -> QWidget:
        """创建搜索爬取选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 搜索设置组
        search_group = QGroupBox("搜索设置")
        search_layout = QGridLayout(search_group)
        
        # 搜索关键词
        search_layout.addWidget(QLabel("关键词:"), 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词")
        search_layout.addWidget(self.search_input, 0, 1)
        
        # 搜索平台
        search_layout.addWidget(QLabel("搜索平台:"), 1, 0)
        self.search_platform_combo = QComboBox()
        self.search_platform_combo.addItems(["bilibili", "youtube"])
        search_layout.addWidget(self.search_platform_combo, 1, 1)
        
        # 搜索数量
        search_layout.addWidget(QLabel("搜索数量:"), 2, 0)
        self.search_count_spin = QSpinBox()
        self.search_count_spin.setRange(0, 5000)
        self.search_count_spin.setValue(50)
        self.search_count_spin.setSpecialValueText("无上限")
        search_layout.addWidget(self.search_count_spin, 2, 1)
        
        # 排序方式
        search_layout.addWidget(QLabel("排序方式:"), 3, 0)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["相关度", "时间", "播放量", "评分"])
        search_layout.addWidget(self.sort_combo, 3, 1)
        
        layout.addWidget(search_group)
        
        # 搜索选项
        search_options_group = QGroupBox("搜索选项")
        search_options_layout = QGridLayout(search_options_group)
        
        # 自动下载选项
        self.auto_download_check = QCheckBox("搜索后自动下载")
        search_options_layout.addWidget(self.auto_download_check, 0, 0)
        
        # 下载数量限制
        search_options_layout.addWidget(QLabel("下载数量:"), 0, 1)
        self.download_limit_spin = QSpinBox()
        self.download_limit_spin.setRange(0, 100)
        self.download_limit_spin.setValue(0)  # 0表示不限制
        self.download_limit_spin.setSpecialValueText("不限制")
        search_options_layout.addWidget(self.download_limit_spin, 0, 2)
        
        # 下载文件夹设置
        search_options_layout.addWidget(QLabel("下载文件夹:"), 1, 0)
        self.search_output_dir_input = QLineEdit()
        self.search_output_dir_input.setText("./downloads")  # 默认为工程文件夹下的downloads
        search_options_layout.addWidget(self.search_output_dir_input, 1, 1)
        
        self.search_browse_btn = QPushButton("浏览")
        self.search_browse_btn.clicked.connect(self._browse_search_output_dir)
        search_options_layout.addWidget(self.search_browse_btn, 1, 2)
        
        layout.addWidget(search_options_group)
        
        # 搜索按钮
        search_button_layout = QHBoxLayout()
        
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._search_videos)
        search_button_layout.addWidget(self.search_btn)
        
        self.search_download_btn = QPushButton("搜索并下载")
        self.search_download_btn.clicked.connect(self._search_and_download)
        search_button_layout.addWidget(self.search_download_btn)
        
        search_button_layout.addStretch()
        
        layout.addLayout(search_button_layout)
        
        # 搜索进度条
        self.search_progress = QProgressBar()
        self.search_progress.setVisible(False)
        layout.addWidget(self.search_progress)
        
        # 搜索结果
        result_group = QGroupBox("搜索结果")
        result_layout = QVBoxLayout(result_group)
        
        self.search_result_table = QTableWidget()
        self.search_result_table.setColumnCount(5)
        self.search_result_table.setHorizontalHeaderLabels(["选择", "标题", "作者", "时长", "URL"])
        self.search_result_table.horizontalHeader().setStretchLastSection(True)
        result_layout.addWidget(self.search_result_table)
        
        # 结果控制按钮
        result_button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all_results)
        result_button_layout.addWidget(self.select_all_btn)
        
        self.download_selected_btn = QPushButton("下载选中")
        self.download_selected_btn.clicked.connect(self._download_selected_results)
        result_button_layout.addWidget(self.download_selected_btn)
        
        result_button_layout.addStretch()
        
        result_layout.addLayout(result_button_layout)
        
        # 下载进度条
        self.download_progress = QProgressBar()
        self.download_progress.setVisible(False)
        result_layout.addWidget(self.download_progress)
        
        layout.addWidget(result_group)
        
        return widget
    
    def _create_task_management_tab(self) -> QWidget:
        """创建任务管理选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 如果有核心任务管理器，使用专门的任务管理界面
        if self.core_task_manager:
            try:
                from .task_manager import TaskManagerWidget
                self.task_manager_widget = TaskManagerWidget(self.core_task_manager)
                layout.addWidget(self.task_manager_widget)
                return widget
            except ImportError:
                self.logger.warning("无法导入任务管理器界面，使用简化版本")
        
        # 简化版任务列表（备用）
        task_group = QGroupBox("任务列表")
        task_layout = QVBoxLayout(task_group)
        
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(7)
        self.task_table.setHorizontalHeaderLabels(["选择", "任务ID", "标题", "状态", "进度", "平台", "操作"])
        self.task_table.horizontalHeader().setStretchLastSection(True)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        task_layout.addWidget(self.task_table)
        
        layout.addWidget(task_group)
        
        # 批量操作控制
        batch_control_group = QGroupBox("批量操作")
        batch_control_layout = QHBoxLayout(batch_control_group)
        
        # 选择操作
        self.select_all_tasks_btn = QPushButton("全选")
        self.select_all_tasks_btn.clicked.connect(self._select_all_tasks)
        batch_control_layout.addWidget(self.select_all_tasks_btn)
        
        self.unselect_all_tasks_btn = QPushButton("取消全选")
        self.unselect_all_tasks_btn.clicked.connect(self._unselect_all_tasks)
        batch_control_layout.addWidget(self.unselect_all_tasks_btn)
        
        self.select_unfinished_btn = QPushButton("选择未完成")
        self.select_unfinished_btn.clicked.connect(self._select_unfinished_tasks)
        batch_control_layout.addWidget(self.select_unfinished_btn)
        
        batch_control_layout.addWidget(QLabel("|"))  # 分隔符
        
        self.start_all_btn = QPushButton("全部开始")
        self.start_all_btn.clicked.connect(self._start_all_crawler_tasks)
        batch_control_layout.addWidget(self.start_all_btn)
        
        self.pause_all_btn = QPushButton("全部暂停")
        self.pause_all_btn.clicked.connect(self._pause_all_crawler_tasks)
        batch_control_layout.addWidget(self.pause_all_btn)
        
        batch_control_layout.addWidget(QLabel("|"))  # 分隔符
        
        self.start_selected_btn = QPushButton("开始选中")
        self.start_selected_btn.clicked.connect(self._start_selected_crawler_tasks)
        batch_control_layout.addWidget(self.start_selected_btn)
        
        self.pause_selected_btn = QPushButton("暂停选中")
        self.pause_selected_btn.clicked.connect(self._pause_selected_crawler_tasks)
        batch_control_layout.addWidget(self.pause_selected_btn)
        
        batch_control_layout.addStretch()
        
        layout.addWidget(batch_control_group)
        
        # 线程配置
        thread_config_group = QGroupBox("线程配置")
        thread_config_layout = QHBoxLayout(thread_config_group)
        
        thread_config_layout.addWidget(QLabel("最大并发数:"))
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(1, 20)
        self.max_workers_spin.setValue(self.crawler_manager.max_concurrent)
        self.max_workers_spin.valueChanged.connect(self._on_max_workers_changed)
        thread_config_layout.addWidget(self.max_workers_spin)
        
        thread_config_layout.addWidget(QLabel("当前运行:"))
        self.running_count_label = QLabel("0")
        thread_config_layout.addWidget(self.running_count_label)
        
        thread_config_layout.addStretch()
        
        layout.addWidget(thread_config_group)
        
        # 任务控制
        task_control_layout = QHBoxLayout()
        
        self.refresh_tasks_btn = QPushButton("刷新")
        self.refresh_tasks_btn.clicked.connect(self._refresh_task_list)
        task_control_layout.addWidget(self.refresh_tasks_btn)
        
        self.clear_completed_btn = QPushButton("清除已完成")
        self.clear_completed_btn.clicked.connect(self._clear_completed_tasks)
        task_control_layout.addWidget(self.clear_completed_btn)
        
        task_control_layout.addStretch()
        
        layout.addLayout(task_control_layout)
        
        return widget
    
    def _create_status_bar(self, layout):
        """创建状态栏"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel)
        status_layout = QHBoxLayout(status_frame)
        
        self.overall_status = QLabel("就绪")
        status_layout.addWidget(self.overall_status)
        
        status_layout.addStretch()
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setMaximumWidth(200)
        self.overall_progress.setVisible(False)
        status_layout.addWidget(self.overall_progress)
        
        layout.addWidget(status_frame)
    
    def _connect_signals(self):
        """连接信号"""
        # URL输入回车事件
        self.batch_url_input.returnPressed.connect(self._add_batch_url)
        
        # 平台选择变化
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
    
    def _load_settings(self):
        """加载设置"""
        try:
            # 从配置管理器加载设置
            crawler_config = self.config_manager.get_config("crawler", {})
            
            # 设置默认输出目录
            default_output = crawler_config.get("default_output_dir", "./downloads")
            self.output_dir_input.setText(default_output)
            
            # 设置默认质量
            default_quality = crawler_config.get("default_quality", "最高质量")
            index = self.quality_combo.findText(default_quality)
            if index >= 0:
                self.quality_combo.setCurrentIndex(index)
            
        except Exception as e:
            self.logger.error(f"加载设置失败: {e}")
    
    # 槽函数实现
    def _browse_output_dir(self):
        """浏览输出目录"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self, "选择输出目录", self.output_dir_input.text())
            if dir_path:
                self.output_dir_input.setText(dir_path)
        except Exception as e:
            self.logger.error(f"浏览输出目录失败: {e}")
    
    def _browse_search_output_dir(self):
        """浏览搜索下载输出目录"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self, "选择下载目录", self.search_output_dir_input.text())
            if dir_path:
                self.search_output_dir_input.setText(dir_path)
        except Exception as e:
            self.logger.error(f"浏览搜索下载目录失败: {e}")
    
    def _browse_output_dir_old(self):
        """浏览输出目录（旧版本）"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self, "选择输出目录", self.output_dir_input.text()
            )
            if dir_path:
                self.output_dir_input.setText(dir_path)
        except Exception as e:
            self.logger.error(f"浏览目录失败: {e}")
    
    def _on_platform_changed(self, platform: str):
        """平台选择变化"""
        try:
            # 根据平台调整可用选项
            if platform == "douyin":
                # 抖音特殊设置
                self.subtitle_check.setEnabled(False)
            else:
                self.subtitle_check.setEnabled(True)
        except Exception as e:
            self.logger.error(f"处理平台变化失败: {e}")
    
    def _preview_video_info(self):
        """预览视频信息"""
        try:
            url = self.url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "警告", "请输入视频URL")
                return
            
            # TODO: 实现视频信息预览
            QMessageBox.information(self, "信息", "视频信息预览功能待实现")
            
        except Exception as e:
            self.logger.error(f"预览视频信息失败: {e}")
            QMessageBox.critical(self, "错误", f"预览失败: {e}")
    
    def _start_single_crawl(self):
        """开始单个URL爬取"""
        try:
            url = self.url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "警告", "请输入视频URL")
                return
            
            # 准备任务配置
            task_config = {
                'url': url,
                'platform': self.platform_combo.currentText(),
                'output_dir': self.output_dir_input.text(),
                'options': {
                    'quality': self.quality_combo.currentText(),
                    'download_type': self.download_type_combo.currentText(),
                    'subtitle': self.subtitle_check.isChecked(),
                    'thumbnail': self.thumbnail_check.isChecked(),
                    'proxy': self.proxy_input.text().strip() or None
                }
            }
            
            # 同步到核心任务管理器
            if self.core_task_manager:
                try:
                    from ..core.task_manager import Task, TaskStatus
                    core_task = Task(
                        id=f"single_{len(self.task_history)}",
                        name=f"下载: {url}",
                        task_type="download",
                        params=task_config
                    )
                    self.core_task_manager.add_task(core_task)
                except Exception as e:
                    self.logger.warning(f"同步任务到核心管理器失败: {e}")
            
            # 使用新的下载任务管理器
            skip_duplicate = not getattr(self, 'skip_duplicate_check', None) or not self.skip_duplicate_check.isChecked()
            
            task_id = self.crawler_manager.add_download_task(
                url=url,
                title=None,  # 让系统自动获取标题
                quality=self.quality_combo.currentText(),
                format="mp4",  # 默认格式
                auto_start=True,
                max_retries=3,
                skip_duplicate_check=skip_duplicate
            )
            
            if task_id:
                # 添加回调监听
                self.crawler_manager.add_progress_callback(self._on_task_progress_updated)
                self.crawler_manager.add_status_callback(self._on_task_status_updated)
                
                self.logger.info(f"开始单个下载任务: {task_id}")
            else:
                QMessageBox.warning(self, "警告", "添加下载任务失败")
                return
            
            # 更新界面状态
            self.start_single_btn.setEnabled(False)
            self.stop_single_btn.setEnabled(True)
            self.single_progress.setValue(0)
            self.single_status.setText("开始下载...")
            
            self.status_changed.emit("开始单个视频下载")
            
        except Exception as e:
            self.logger.error(f"开始单个爬取失败: {e}")
            QMessageBox.critical(self, "错误", f"开始下载失败: {e}")
    
    def _stop_crawl(self):
        """停止爬取"""
        try:
            if self.crawler_thread and self.crawler_thread.isRunning():
                self.crawler_thread.stop()
                
            # 重置界面状态
            self.start_single_btn.setEnabled(True)
            self.stop_single_btn.setEnabled(False)
            self.start_batch_btn.setEnabled(True)
            self.stop_batch_btn.setEnabled(False)
            
            self.single_status.setText("已停止")
            self.batch_status.setText("已停止")
            
            self.status_changed.emit("下载已停止")
            
        except Exception as e:
            self.logger.error(f"停止爬取失败: {e}")
    
    def _add_batch_url(self):
        """添加批量URL"""
        try:
            url = self.batch_url_input.text().strip()
            if url:
                item = QListWidgetItem(url)
                self.url_list.addItem(item)
                self.batch_url_input.clear()
        except Exception as e:
            self.logger.error(f"添加URL失败: {e}")
    
    def _load_urls_from_file(self):
        """从文件加载URL"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择URL文件", "", "文本文件 (*.txt);;所有文件 (*)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f if line.strip()]
                
                for url in urls:
                    if url:
                        item = QListWidgetItem(url)
                        self.url_list.addItem(item)
                
                QMessageBox.information(self, "信息", f"成功加载 {len(urls)} 个URL")
                
        except Exception as e:
            self.logger.error(f"从文件加载URL失败: {e}")
            QMessageBox.critical(self, "错误", f"加载失败: {e}")
    
    def _remove_selected_url(self):
        """移除选中的URL"""
        try:
            current_row = self.url_list.currentRow()
            if current_row >= 0:
                self.url_list.takeItem(current_row)
        except Exception as e:
            self.logger.error(f"移除URL失败: {e}")
    
    def _clear_url_list(self):
        """清空URL列表"""
        try:
            self.url_list.clear()
        except Exception as e:
            self.logger.error(f"清空URL列表失败: {e}")
    
    def _start_batch_crawl(self):
        """开始批量爬取"""
        try:
            if self.url_list.count() == 0:
                QMessageBox.warning(self, "警告", "请添加要下载的URL")
                return
            
            # 收集URL列表
            urls = []
            for i in range(self.url_list.count()):
                item = self.url_list.item(i)
                if item:
                    urls.append(item.text())
            
            if not urls:
                QMessageBox.warning(self, "警告", "没有有效的URL")
                return
            
            # 获取下载选项
            quality = self.quality_combo.currentText()
            max_concurrent = self.concurrent_spin.value()
            max_retries = self.retry_spin.value()
            skip_duplicate = not self.skip_duplicate_check.isChecked()  # 注意逻辑反转
            
            # 启动批量下载
            task_ids = self.crawler_manager.batch_download_urls(
                urls=urls,
                quality=quality,
                max_concurrent=max_concurrent,
                max_retries=max_retries,
                skip_duplicate_check=skip_duplicate,
                progress_callback=self._on_batch_progress_updated
            )
            
            if task_ids:
                # 更新界面状态
                self.start_batch_btn.setEnabled(False)
                self.pause_all_btn.setEnabled(True)
                self.resume_all_btn.setEnabled(True)
                self.stop_batch_btn.setEnabled(True)
                
                self.batch_status.setText(f"批量下载中... ({len(task_ids)} 个任务)")
                self.batch_progress.setValue(0)
                
                # 添加回调监听
                self.crawler_manager.add_progress_callback(self._on_task_progress_updated)
                self.crawler_manager.add_status_callback(self._on_task_status_updated)
                
                self.logger.info(f"开始批量下载，共 {len(task_ids)} 个任务")
                QMessageBox.information(self, "信息", f"成功添加 {len(task_ids)} 个下载任务")
            else:
                QMessageBox.warning(self, "警告", "添加下载任务失败")
            
        except Exception as e:
            self.logger.error(f"开始批量爬取失败: {e}")
            QMessageBox.critical(self, "错误", f"批量下载失败: {e}")
    
    def _search_videos(self):
        """搜索视频"""
        try:
            keyword = self.search_input.text().strip()
            if not keyword:
                QMessageBox.warning(self, "警告", "请输入搜索关键词")
                return
            
            # 如果已有搜索线程在运行，先停止
            if self.search_thread and self.search_thread.isRunning():
                self.search_thread.quit()
                self.search_thread.wait()
            
            platform = self.search_platform_combo.currentText()
            search_count = self.search_count_spin.value()
            
            # 处理搜索数量为0的情况（表示无上限）
            if search_count == 0:
                search_count = 10000  # 设置一个较大的数值作为无上限
            
            # 创建搜索线程
            self.search_thread = SearchThread(
                self.crawler_manager,
                keyword,
                platform if platform != "全部" else None,
                search_count
            )
            
            # 连接信号
            self.search_thread.progress_updated.connect(self._on_search_progress)
            self.search_thread.result_ready.connect(self._on_search_completed)
            self.search_thread.error_occurred.connect(self._on_search_error)
            
            # 更新UI状态
            self.search_btn.setEnabled(False)
            self.search_btn.setText("搜索中...")
            self.search_progress.setVisible(True)
            self.search_progress.setValue(0)
            
            # 启动搜索线程
            self.search_thread.start()
            
        except Exception as e:
            self.logger.error(f"启动搜索失败: {e}")
            QMessageBox.critical(self, "错误", f"搜索失败: {e}")
            self._reset_search_ui()
    
    def _select_all_results(self):
        """全选搜索结果"""
        try:
            for row in range(self.search_result_table.rowCount()):
                checkbox = self.search_result_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(True)
        except Exception as e:
            self.logger.error(f"全选结果失败: {e}")
    
    def _select_all_tasks(self):
        """全选任务"""
        try:
            for row in range(self.task_table.rowCount()):
                checkbox = self.task_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(True)
        except Exception as e:
            self.logger.error(f"全选任务失败: {e}")
    
    def _unselect_all_tasks(self):
        """取消全选任务"""
        try:
            for row in range(self.task_table.rowCount()):
                checkbox = self.task_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(False)
        except Exception as e:
            self.logger.error(f"取消全选任务失败: {e}")
    
    def _select_unfinished_tasks(self):
        """选择未完成的任务（未下载、失败、暂停的任务）"""
        try:
            for row in range(self.task_table.rowCount()):
                checkbox = self.task_table.cellWidget(row, 0)
                status_item = self.task_table.item(row, 3)  # 状态列
                if checkbox and status_item:
                    status = status_item.text()
                    # 选择未完成的状态：等待中、失败、已取消、已暂停
                    if status in ['等待中', '失败', '已取消', '已暂停']:
                        checkbox.setChecked(True)
                    else:
                        checkbox.setChecked(False)
        except Exception as e:
            self.logger.error(f"选择未完成任务失败: {e}")
    
    def _search_and_download(self):
        """搜索并下载"""
        try:
            keyword = self.search_input.text().strip()
            if not keyword:
                QMessageBox.warning(self, "警告", "请输入搜索关键词")
                return
            
            # 如果已有搜索下载线程在运行，先停止
            if self.search_download_thread and self.search_download_thread.isRunning():
                self.search_download_thread.quit()
                self.search_download_thread.wait()
            
            platform = self.search_platform_combo.currentText()
            search_count = self.search_count_spin.value()
            download_limit = self.download_limit_spin.value() if self.download_limit_spin.value() > 0 else None
            quality = self.quality_combo.currentText()
            output_dir = self.search_output_dir_input.text().strip() or "./downloads"
            
            # 处理搜索数量为0的情况（表示无上限）
            if search_count == 0:
                search_count = 10000  # 设置一个较大的数值作为无上限
            
            # 创建搜索下载线程
            self.search_download_thread = SearchDownloadThread(
                self.crawler_manager,
                keyword,
                platform if platform != "全部" else None,
                search_count,
                download_limit,
                quality,
                output_dir
            )
            
            # 连接信号
            self.search_download_thread.progress_updated.connect(self._on_search_download_progress)
            self.search_download_thread.result_ready.connect(self._on_search_download_completed)
            self.search_download_thread.error_occurred.connect(self._on_search_download_error)
            
            # 更新UI状态
            self.search_download_btn.setEnabled(False)
            self.search_download_btn.setText("搜索下载中...")
            
            # 启动搜索下载线程
            self.search_download_thread.start()
            
        except Exception as e:
            self.logger.error(f"启动搜索下载失败: {e}")
            QMessageBox.critical(self, "错误", f"搜索下载失败: {e}")
            self._reset_search_download_ui()
    
    def _download_selected_results(self):
        """下载选中的搜索结果"""
        try:
            selected_urls = []
            for row in range(self.search_result_table.rowCount()):
                checkbox = self.search_result_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    url_item = self.search_result_table.item(row, 4)
                    if url_item:
                        selected_urls.append(url_item.text())
            
            if not selected_urls:
                QMessageBox.warning(self, "警告", "请选择要下载的视频")
                return
            
            # 如果已有下载线程在运行，先停止
            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.quit()
                self.download_thread.wait()
            
            quality = self.quality_combo.currentText()
            max_retries = self.retry_spin.value()
            
            # 创建下载线程
            self.download_thread = DownloadThread(
                self.crawler_manager,
                selected_urls,
                quality,
                max_retries
            )
            
            # 连接信号
            self.download_thread.progress_updated.connect(self._on_download_progress)
            self.download_thread.result_ready.connect(self._on_download_completed)
            self.download_thread.error_occurred.connect(self._on_download_error)
            
            # 更新UI状态
            self.download_selected_btn.setEnabled(False)
            self.download_selected_btn.setText("下载中...")
            self.download_progress.setVisible(True)
            self.download_progress.setValue(0)
            self.download_progress.setMaximum(len(selected_urls))
            
            # 启动下载线程
            self.download_thread.start()
                
        except Exception as e:
            self.logger.error(f"启动下载失败: {e}")
            QMessageBox.critical(self, "错误", f"下载失败: {e}")
            self._reset_download_ui()
    
    def _refresh_task_list(self):
        """刷新任务列表"""
        try:
            tasks = self.crawler_manager.get_all_tasks()
            self._update_task_table(tasks)
            self.logger.info(f"任务列表已刷新，共 {len(tasks)} 个任务")
        except Exception as e:
            self.logger.error(f"刷新任务列表失败: {e}")
            QMessageBox.critical(self, "错误", f"刷新失败: {e}")
    
    def _clear_completed_tasks(self):
        """清除已完成任务"""
        try:
            # 获取已完成的任务
            all_tasks = self.crawler_manager.get_all_tasks()
            completed_tasks = [task for task in all_tasks.values() if task.status.value in ['completed', 'failed', 'cancelled']]
            
            if not completed_tasks:
                QMessageBox.information(self, "信息", "没有已完成的任务")
                return
            
            reply = QMessageBox.question(self, "确认", f"确定要清除 {len(completed_tasks)} 个已完成的任务吗？",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                # 清除已完成的任务
                for task in completed_tasks:
                    self.crawler_manager.remove_task(task.id)
                
                self._refresh_task_list()
                QMessageBox.information(self, "信息", f"已清除 {len(completed_tasks)} 个已完成任务")
        except Exception as e:
            self.logger.error(f"清除已完成任务失败: {e}")
            QMessageBox.critical(self, "错误", f"清除失败: {e}")
    
    def _update_search_results(self, results):
        """更新搜索结果表格"""
        self.search_result_table.setRowCount(len(results))
        
        for row, video in enumerate(results):
            # 复选框
            checkbox = QCheckBox()
            self.search_result_table.setCellWidget(row, 0, checkbox)
            
            # 标题
            self.search_result_table.setItem(row, 1, QTableWidgetItem(video.get('title', '')))
            
            # 作者
            self.search_result_table.setItem(row, 2, QTableWidgetItem(video.get('uploader', '')))
            
            # 时长
            duration = video.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "未知"
            self.search_result_table.setItem(row, 3, QTableWidgetItem(duration_str))
            
            # URL
            self.search_result_table.setItem(row, 4, QTableWidgetItem(video.get('url', '')))
    
    def _update_task_table(self, tasks):
        """更新任务表格"""
        # 如果tasks是字典，转换为列表
        if isinstance(tasks, dict):
            task_list = list(tasks.values())
        else:
            task_list = tasks
            
        self.task_table.setRowCount(len(task_list))
        
        for row, task in enumerate(task_list):
            # 选择复选框
            checkbox = QCheckBox()
            self.task_table.setCellWidget(row, 0, checkbox)
            
            # 任务ID
            task_id = getattr(task, 'id', getattr(task, 'task_id', 'Unknown'))
            self.task_table.setItem(row, 1, QTableWidgetItem(str(task_id)))
            
            # 标题
            title = getattr(task, 'title', getattr(task, 'name', '未知'))
            self.task_table.setItem(row, 2, QTableWidgetItem(str(title)))
            
            # 状态
            status_map = {
                'pending': '等待中',
                'downloading': '下载中',
                'running': '运行中',
                'completed': '已完成',
                'failed': '失败',
                'cancelled': '已取消',
                'paused': '已暂停'
            }
            status = getattr(task, 'status', 'unknown')
            if hasattr(status, 'value'):
                status = status.value
            status_text = status_map.get(status, str(status))
            self.task_table.setItem(row, 3, QTableWidgetItem(status_text))
            
            # 进度
            progress = getattr(task, 'progress', 0)
            progress_text = f"{progress:.1f}%" if progress else "0%"
            self.task_table.setItem(row, 4, QTableWidgetItem(progress_text))
            
            # 平台
            platform = getattr(task, 'platform', getattr(task, 'params', {}).get('platform', '未知'))
            self.task_table.setItem(row, 5, QTableWidgetItem(str(platform)))
            
            # 操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            
            # 根据任务状态显示不同的操作按钮
            if status in ['pending', 'paused']:
                start_btn = QPushButton("开始")
                start_btn.setMaximumWidth(50)
                start_btn.clicked.connect(lambda checked, tid=task_id: self._start_single_task(tid))
                action_layout.addWidget(start_btn)
            elif status in ['running', 'downloading']:
                pause_btn = QPushButton("暂停")
                pause_btn.setMaximumWidth(50)
                pause_btn.clicked.connect(lambda checked, tid=task_id: self._pause_single_task(tid))
                action_layout.addWidget(pause_btn)
            
            # 删除按钮
            if status in ['completed', 'failed', 'cancelled']:
                delete_btn = QPushButton("删除")
                delete_btn.setMaximumWidth(50)
                delete_btn.clicked.connect(lambda checked, tid=task_id: self._delete_single_task(tid))
                action_layout.addWidget(delete_btn)
            
            self.task_table.setCellWidget(row, 6, action_widget)
        
        # 更新运行中任务数量
        self._update_running_count()
    
    def _on_search_download_progress(self, current, total):
        """搜索下载进度回调"""
        try:
            # 确保参数是数字类型
            current = float(current) if current is not None else 0
            total = float(total) if total is not None else 0
            progress = (current / total * 100) if total > 0 else 0
            self.search_download_btn.setText(f"搜索下载中... ({int(current)}/{int(total)})")
        except (ValueError, TypeError) as e:
            self.logger.warning(f"进度回调参数类型错误: current={current}, total={total}, error={e}")
            self.search_download_btn.setText("搜索下载中...")
    
    def _on_task_progress_updated(self, task_id, progress):
        """任务进度更新回调"""
        try:
            # 更新任务表格中对应任务的进度
            for row in range(self.task_table.rowCount()):
                task_id_item = self.task_table.item(row, 1)  # 任务ID现在在第1列
                if task_id_item and task_id_item.text() == str(task_id):
                    progress_item = self.task_table.item(row, 4)  # 进度现在在第4列
                    if progress_item:
                        progress_item.setText(f"{progress:.1f}%")
                    # 强制刷新表格显示
                    self.task_table.viewport().update()
                    break
        except Exception as e:
            self.logger.error(f"更新任务进度失败: {e}")
    
    def _on_task_status_updated(self, task_id, status):
        """任务状态更新回调"""
        try:
            status_map = {
                'pending': '等待中',
                'downloading': '下载中',
                'running': '运行中',
                'completed': '已完成',
                'failed': '失败',
                'cancelled': '已取消',
                'paused': '已暂停'
            }
            
            # 处理枚举类型的状态
            if hasattr(status, 'value'):
                status = status.value
            
            status_text = status_map.get(status, str(status))
            
            # 同步状态到核心任务管理器
            if self.core_task_manager:
                try:
                    from ..core.task_manager import TaskStatus
                    # 映射状态
                    status_mapping = {
                        "pending": TaskStatus.PENDING,
                        "downloading": TaskStatus.RUNNING,
                        "running": TaskStatus.RUNNING,
                        "completed": TaskStatus.COMPLETED,
                        "failed": TaskStatus.FAILED,
                        "cancelled": TaskStatus.CANCELLED
                    }
                    
                    core_status = status_mapping.get(str(status).lower(), TaskStatus.PENDING)
                    
                    if core_status == TaskStatus.COMPLETED:
                        self.core_task_manager.complete_task(task_id)
                    elif core_status == TaskStatus.FAILED:
                        self.core_task_manager.fail_task(task_id, "下载失败")
                    elif core_status == TaskStatus.CANCELLED:
                        self.core_task_manager.cancel_task(task_id)
                    elif core_status == TaskStatus.RUNNING:
                        self.core_task_manager.start_task(task_id)
                        
                except Exception as e:
                    self.logger.warning(f"同步任务状态到核心管理器失败: {e}")
            
            # 更新任务表格中对应任务的状态
            for row in range(self.task_table.rowCount()):
                task_id_item = self.task_table.item(row, 1)  # 任务ID现在在第1列
                if task_id_item and task_id_item.text() == str(task_id):
                    status_item = self.task_table.item(row, 3)  # 状态现在在第3列
                    if status_item:
                        status_item.setText(status_text)
                    break
        except Exception as e:
            self.logger.error(f"更新任务状态失败: {e}")
    
    def _on_batch_progress_updated(self, current, total):
        """批量任务进度更新"""
        try:
            progress = (current / total) * 100 if total > 0 else 0
            self.batch_progress.setValue(int(progress))
            self.overall_progress.setValue(int(progress))
            self.progress_changed.emit(int(progress))
            
            # 更新状态文本
            self.batch_status.setText(f"批量下载中... ({current}/{total})")
            
        except Exception as e:
            self.logger.error(f"更新批量进度失败: {e}")
    
    def _pause_all_tasks(self):
        """暂停所有任务"""
        try:
            self.crawler_manager.pause_all_tasks()
            self.batch_status.setText("已暂停")
            self.status_changed.emit("所有任务已暂停")
        except Exception as e:
            self.logger.error(f"暂停所有任务失败: {e}")
    
    def _resume_all_tasks(self):
        """恢复所有任务"""
        try:
            self.crawler_manager.resume_all_tasks()
            self.batch_status.setText("下载中...")
            self.status_changed.emit("所有任务已恢复")
        except Exception as e:
            self.logger.error(f"恢复所有任务失败: {e}")
    
    def _cancel_all_tasks(self):
        """取消所有任务"""
        try:
            self.crawler_manager.cancel_all_tasks()
            self.start_batch_btn.setEnabled(True)
            self.pause_all_btn.setEnabled(False)
            self.resume_all_btn.setEnabled(False)
            self.stop_batch_btn.setEnabled(False)
            self.batch_status.setText("已取消")
            self.status_changed.emit("所有任务已取消")
        except Exception as e:
            self.logger.error(f"取消所有任务失败: {e}")
    
    # 线程信号处理
    def _on_single_progress_updated(self, progress: float):
        """单个任务进度更新"""
        self.single_progress.setValue(int(progress))
        self.overall_progress.setValue(int(progress))
        self.progress_changed.emit(int(progress))
    
    def _on_single_status_updated(self, status: str):
        """单个任务状态更新"""
        self.single_status.setText(status)
        self.overall_status.setText(status)
        self.status_changed.emit(status)
    
    def _on_single_result_ready(self, result: dict):
        """单个任务结果就绪"""
        try:
            # 显示结果
            result_text = f"下载完成\n文件: {result.get('output_path', 'Unknown')}\n"
            result_text += f"大小: {result.get('file_size', 'Unknown')}\n"
            result_text += f"时长: {result.get('duration', 'Unknown')}"
            
            self.single_result.setText(result_text)
            
            # 重置界面状态
            self.start_single_btn.setEnabled(True)
            self.stop_single_btn.setEnabled(False)
            self.single_status.setText("下载完成")
            
            self.status_changed.emit("下载完成")
            
        except Exception as e:
            self.logger.error(f"处理结果失败: {e}")
    
    def _on_single_error_occurred(self, error: str):
        """单个任务发生错误"""
        try:
            self.single_result.setText(f"下载失败: {error}")
            
            # 重置界面状态
            self.start_single_btn.setEnabled(True)
            self.stop_single_btn.setEnabled(False)
            self.single_status.setText("下载失败")
            
            self.status_changed.emit("下载失败")
            
            QMessageBox.critical(self, "下载错误", f"下载失败: {error}")
            
        except Exception as e:
            self.logger.error(f"处理错误失败: {e}")
    
    # 公共接口
    def start_processing(self):
        """开始处理（由主窗口调用）"""
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # 单个URL
            self._start_single_crawl()
        elif current_tab == 1:  # 批量爬取
            self._start_batch_crawl()
        elif current_tab == 2:  # 搜索爬取
            self._search_videos()
    
    def stop_processing(self):
        """停止处理（由主窗口调用）"""
        self._stop_crawl()
    
    def _auto_refresh_tasks(self):
        """自动刷新任务列表"""
        try:
            if self.tab_widget.currentIndex() == 3:  # 任务管理选项卡
                tasks = self.crawler_manager.get_all_tasks()
                self._update_task_table(tasks)
        except Exception as e:
            self.logger.error(f"自动刷新任务列表失败: {e}")
    
    def _start_all_crawler_tasks(self):
        """开始所有爬虫任务"""
        try:
            # 获取所有任务
            tasks = self.crawler_manager.get_all_tasks()
            if not tasks:
                QMessageBox.information(self, "提示", "没有任务")
                return
            
            # 过滤出可启动的任务（等待中、失败的任务）
            pending_tasks = []
            for task in tasks:
                status = getattr(task, 'status', 'pending')
                # 检查实际存在的状态值：PENDING, PAUSED, FAILED, CANCELLED
                if status in ['pending', 'paused', 'failed', 'cancelled', 'PENDING', 'PAUSED', 'FAILED', 'CANCELLED'] or status in [DownloadStatus.PENDING, DownloadStatus.PAUSED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
                    pending_tasks.append(task)
                    print(f"Debug: 找到可启动任务 {getattr(task, 'id', 'unknown')}, 状态: {status}")
            
            if not pending_tasks:
                QMessageBox.information(self, "提示", "没有可启动的任务（所有任务都在运行中或已完成）")
                return
            
            # 启动所有等待中的任务
            success_count = 0
            for task in pending_tasks:
                task_id = getattr(task, 'id', getattr(task, 'task_id', None))
                if task_id:
                    if self.crawler_manager.resume_task(task_id):
                        success_count += 1
            
            self._refresh_task_list()
            self._update_running_count()
            self.status_changed.emit(f"已启动 {success_count} 个任务")
            
        except Exception as e:
            self.logger.error(f"启动所有任务失败: {e}")
            QMessageBox.critical(self, "错误", f"启动所有任务失败: {e}")
    
    def _pause_all_crawler_tasks(self):
        """暂停所有爬虫任务"""
        try:
            # 获取所有任务
            tasks = self.crawler_manager.get_all_tasks()
            if not tasks:
                QMessageBox.information(self, "提示", "没有任务")
                return
            
            # 过滤出可暂停的任务（下载中的任务）
            running_tasks = []
            for task in tasks:
                status = getattr(task, 'status', 'pending')
                # 检查实际存在的状态值：DOWNLOADING
                if status in ['downloading', 'DOWNLOADING'] or status == DownloadStatus.DOWNLOADING:
                    running_tasks.append(task)
                    print(f"Debug: 找到可暂停任务 {getattr(task, 'id', 'unknown')}, 状态: {status}")
            
            if not running_tasks:
                QMessageBox.information(self, "提示", "没有正在运行的任务")
                return
            
            # 暂停所有运行中的任务
            success_count = 0
            for task in running_tasks:
                task_id = getattr(task, 'id', getattr(task, 'task_id', None))
                if task_id:
                    if self.crawler_manager.pause_task(task_id):
                        success_count += 1
            
            self._refresh_task_list()
            self._update_running_count()
            self.status_changed.emit(f"已暂停 {success_count} 个任务")
            
        except Exception as e:
            self.logger.error(f"暂停所有任务失败: {e}")
            QMessageBox.critical(self, "错误", f"暂停所有任务失败: {e}")
    
    def _start_selected_crawler_tasks(self):
        """开始选中的爬虫任务"""
        try:
            selected_tasks = self._get_selected_crawler_tasks()
            if not selected_tasks:
                QMessageBox.information(self, "提示", "请先选择要启动的任务")
                return
            
            # 过滤出可启动的任务
            startable_tasks = []
            for task in selected_tasks:
                status = getattr(task, 'status', 'pending')
                if status in ['pending', 'paused', 'failed', 'cancelled', 'PENDING', 'PAUSED', 'FAILED', 'CANCELLED'] or status in [DownloadStatus.PENDING, DownloadStatus.PAUSED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
                    startable_tasks.append(task)
                    print(f"Debug: 找到可启动的选中任务 {getattr(task, 'id', 'unknown')}, 状态: {status}")
            
            if not startable_tasks:
                QMessageBox.information(self, "提示", "选中的任务中没有可启动的任务")
                return
            
            # 启动选中的任务
            success_count = 0
            for task in startable_tasks:
                task_id = getattr(task, 'id', getattr(task, 'task_id', None))
                if task_id:
                    if self.crawler_manager.resume_task(task_id):
                        success_count += 1
            
            self._refresh_task_list()
            self._update_running_count()
            self.status_changed.emit(f"已启动 {success_count} 个选中任务")
            
        except Exception as e:
            self.logger.error(f"启动选中任务失败: {e}")
            QMessageBox.critical(self, "错误", f"启动选中任务失败: {e}")
    
    def _pause_selected_crawler_tasks(self):
        """暂停选中的爬虫任务"""
        try:
            selected_tasks = self._get_selected_crawler_tasks()
            if not selected_tasks:
                QMessageBox.information(self, "提示", "请先选择要暂停的任务")
                return
            
            # 过滤出可暂停的任务
            pausable_tasks = []
            for task in selected_tasks:
                status = getattr(task, 'status', 'pending')
                if status in ['downloading', 'DOWNLOADING'] or status == DownloadStatus.DOWNLOADING:
                    pausable_tasks.append(task)
                    print(f"Debug: 找到可暂停的选中任务 {getattr(task, 'id', 'unknown')}, 状态: {status}")
            
            if not pausable_tasks:
                QMessageBox.information(self, "提示", "选中的任务中没有正在运行的任务")
                return
            
            # 暂停选中的任务
            success_count = 0
            for task in pausable_tasks:
                task_id = getattr(task, 'id', getattr(task, 'task_id', None))
                if task_id:
                    if self.crawler_manager.pause_task(task_id):
                        success_count += 1
            
            self._refresh_task_list()
            self._update_running_count()
            self.status_changed.emit(f"已暂停 {success_count} 个选中任务")
            
        except Exception as e:
            self.logger.error(f"暂停选中任务失败: {e}")
            QMessageBox.critical(self, "错误", f"暂停选中任务失败: {e}")
    
    def _get_selected_crawler_tasks(self):
        """获取选中的爬虫任务"""
        try:
            selected_tasks = []
            tasks = self.crawler_manager.get_all_tasks()
            
            # 获取选中的行（通过复选框）
            selected_rows = []
            for row in range(self.task_table.rowCount()):
                checkbox = self.task_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    selected_rows.append(row)
            
            # 根据选中的行获取对应的任务
            for row in selected_rows:
                if row < len(tasks):
                    selected_tasks.append(tasks[row])
            
            return selected_tasks
            
        except Exception as e:
            self.logger.error(f"获取选中任务失败: {e}")
            return []
    
    def _on_max_workers_changed(self, value):
        """最大并发数改变"""
        try:
            self.crawler_manager.set_max_concurrent(value)
            self.status_changed.emit(f"最大并发数已设置为 {value}")
            
        except Exception as e:
            self.logger.error(f"设置最大并发数失败: {e}")
    
    def _update_running_count(self):
        """更新运行中任务数量显示"""
        try:
            tasks = self.crawler_manager.get_all_tasks()
            running_count = len([task for task in tasks if getattr(task, 'status', 'pending') in ['downloading', 'DOWNLOADING'] or getattr(task, 'status', 'pending') == DownloadStatus.DOWNLOADING])
            if hasattr(self, 'running_count_label'):
                self.running_count_label.setText(str(running_count))
            
        except Exception as e:
            self.logger.error(f"更新运行数量失败: {e}")
    
    def _start_single_task(self, task_id):
        """开始单个任务"""
        try:
            self.crawler_manager.resume_task(task_id)
            self._refresh_task_list()
            self._update_running_count()
            self.status_changed.emit(f"任务 {task_id} 已启动")
            
        except Exception as e:
            self.logger.error(f"启动任务 {task_id} 失败: {e}")
            QMessageBox.critical(self, "错误", f"启动任务失败: {e}")
    
    def _pause_single_task(self, task_id):
        """暂停单个任务"""
        try:
            self.crawler_manager.pause_task(task_id)
            self._refresh_task_list()
            self._update_running_count()
            self.status_changed.emit(f"任务 {task_id} 已暂停")
            
        except Exception as e:
            self.logger.error(f"暂停任务 {task_id} 失败: {e}")
            QMessageBox.critical(self, "错误", f"暂停任务失败: {e}")
    
    def _delete_single_task(self, task_id):
        """删除单个任务"""
        try:
            reply = QMessageBox.question(self, "确认删除", f"确定要删除任务 {task_id} 吗？", 
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.crawler_manager.remove_task(task_id)
                self._refresh_task_list()
                self._update_running_count()
                self.status_changed.emit(f"任务 {task_id} 已删除")
            
        except Exception as e:
            self.logger.error(f"删除任务 {task_id} 失败: {e}")
            QMessageBox.critical(self, "错误", f"删除任务失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'task_refresh_timer'):
                self.task_refresh_timer.stop()
                
            if self.crawler_thread and self.crawler_thread.isRunning():
                self.crawler_thread.stop()
            
            self.logger.info("爬虫界面组件资源清理完成")
            
        except Exception as e:
            self.logger.error(f"爬虫界面组件资源清理失败: {e}")