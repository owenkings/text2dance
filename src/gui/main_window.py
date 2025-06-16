# -*- coding: utf-8 -*-
"""
主窗口
应用程序的主界面，包含所有功能模块的入口
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QMenuBar, QStatusBar, QToolBar, QAction, QSplitter,
    QDockWidget, QTextEdit, QLabel, QPushButton, QMessageBox,
    QProgressBar, QSystemTrayIcon, QMenu, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings
from PyQt5.QtGui import QIcon, QPixmap, QFont

from ..core.config_manager import ConfigManager
from .crawler_widget import CrawlerWidget
from .video_widget import VideoEditWidget
from .config_widget import ConfigWidget
from .log_viewer import LogViewer

class MainWindow(QMainWindow):
    """主窗口类"""
    
    # 信号定义
    status_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        
        # 初始化配置
        self.config_manager = ConfigManager()
        
        # 设置
        self.settings = QSettings("VideoProcessingSystem", "MainApp")
        
        # 子组件
        self.crawler_widget = None
        self.video_processing_widget = None
        self.algorithm_widget = None
        self.config_widget = None
        self.plugin_widget = None
        self.log_widget = None
        
        # 状态
        self.is_processing = False
        self.current_tasks = []
        
        # 系统托盘
        self.tray_icon = None
        
        # 初始化界面
        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_statusbar()
        self._init_dock_widgets()
        self._init_system_tray()
        self._connect_signals()
        self._load_settings()
        
        print("主窗口初始化完成")
    
    def set_config_manager(self, config_manager):
        """设置配置管理器"""
        self.config_manager = config_manager
        # 更新子组件的配置管理器
        if hasattr(self, 'crawler_widget') and self.crawler_widget:
            self.crawler_widget.config_manager = config_manager
        if hasattr(self, 'video_edit_widget') and self.video_edit_widget:
            self.video_edit_widget.config_manager = config_manager
        if hasattr(self, 'config_widget') and self.config_widget:
            self.config_widget.config_manager = config_manager
        if hasattr(self, 'log_widget') and self.log_widget:
            self.log_widget.config_manager = config_manager
    
    def set_plugin_manager(self, plugin_manager):
        """设置插件管理器"""
        self.plugin_manager = plugin_manager
        # 更新子组件的插件管理器
        if hasattr(self, 'crawler_widget') and self.crawler_widget:
            self.crawler_widget.plugin_manager = plugin_manager
        if hasattr(self, 'video_edit_widget') and self.video_edit_widget:
            self.video_edit_widget.plugin_manager = plugin_manager
    
    def _init_ui(self):
        """初始化用户界面"""
        # 设置窗口属性
        self.setWindowTitle("视频处理系统 - Video Processing System")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # 设置窗口图标
        self.setWindowIcon(self._create_app_icon())
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建选项卡控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabsClosable(False)
        
        # 创建各个功能模块
        self._create_modules()
        
        # 添加选项卡
        self.tab_widget.addTab(self.crawler_widget, "🕷️ 爬虫")
        self.tab_widget.addTab(self.video_edit_widget, "🎬 视频编辑")
        self.tab_widget.addTab(self.config_widget, "⚙️ 配置")
        
        # 任务管理器
        try:
            from .task_manager import TaskManagerWidget
            self.task_manager = TaskManagerWidget(self)
            self.tab_widget.addTab(self.task_manager, "📋 任务管理")
            print("任务管理器已加载")
        except ImportError as e:
            print(f"任务管理器模块导入失败: {e}")
            self.task_manager = None
        
        main_layout.addWidget(self.tab_widget)
        
        # 设置样式
        self._apply_styles()
    
    def _create_modules(self):
        """创建功能模块"""
        try:
            # 爬虫模块
            self.crawler_widget = CrawlerWidget(self.config_manager)
            
            # 视频编辑模块
            from .video_widget import VideoEditWidget
            self.video_edit_widget = VideoEditWidget(self.config_manager)
            
            # 配置模块
            self.config_widget = ConfigWidget(self.config_manager)
            
            # 日志模块
            self.log_viewer = LogViewer()
            
        except Exception as e:
            print(f"创建功能模块失败: {e}")
            QMessageBox.critical(self, "错误", f"创建功能模块失败: {e}")
    
    def _init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        # 新建项目
        new_action = QAction("新建项目(&N)", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)
        
        # 打开项目
        open_action = QAction("打开项目(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)
        
        # 保存项目
        save_action = QAction("保存项目(&S)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        # 导入配置
        import_config_action = QAction("导入配置(&I)", self)
        import_config_action.triggered.connect(self._import_config)
        file_menu.addAction(import_config_action)
        
        # 导出配置
        export_config_action = QAction("导出配置(&E)", self)
        export_config_action.triggered.connect(self._export_config)
        file_menu.addAction(export_config_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        
        # 偏好设置
        preferences_action = QAction("偏好设置(&P)", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self._show_preferences)
        edit_menu.addAction(preferences_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        
        # 全屏
        fullscreen_action = QAction("全屏(&F)", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setCheckable(True)
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具(&T)")
        
        # 清理缓存
        clear_cache_action = QAction("清理缓存(&C)", self)
        clear_cache_action.triggered.connect(self._clear_cache)
        tools_menu.addAction(clear_cache_action)
        
        # 检查更新
        check_update_action = QAction("检查更新(&U)", self)
        check_update_action.triggered.connect(self._check_updates)
        tools_menu.addAction(check_update_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        # 用户手册
        manual_action = QAction("用户手册(&M)", self)
        manual_action.triggered.connect(self._show_manual)
        help_menu.addAction(manual_action)
        
        # 关于
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _init_toolbar(self):
        """初始化工具栏"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)
        
        # 新建项目
        new_action = QAction("新建", self)
        new_action.setIcon(self._create_icon("new"))
        new_action.triggered.connect(self._new_project)
        toolbar.addAction(new_action)
        
        # 打开项目
        open_action = QAction("打开", self)
        open_action.setIcon(self._create_icon("open"))
        open_action.triggered.connect(self._open_project)
        toolbar.addAction(open_action)
        
        # 保存项目
        save_action = QAction("保存", self)
        save_action.setIcon(self._create_icon("save"))
        save_action.triggered.connect(self._save_project)
        toolbar.addAction(save_action)
        
        toolbar.addSeparator()
        
        # 开始处理
        self.start_action = QAction("开始", self)
        self.start_action.setIcon(self._create_icon("play"))
        self.start_action.triggered.connect(self._start_processing)
        toolbar.addAction(self.start_action)
        
        # 停止处理
        self.stop_action = QAction("停止", self)
        self.stop_action.setIcon(self._create_icon("stop"))
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self._stop_processing)
        toolbar.addAction(self.stop_action)
        
        toolbar.addSeparator()
        
        # 设置
        settings_action = QAction("设置", self)
        settings_action.setIcon(self._create_icon("settings"))
        settings_action.triggered.connect(self._show_preferences)
        toolbar.addAction(settings_action)
    
    def _init_statusbar(self):
        """初始化状态栏"""
        statusbar = self.statusBar()
        
        # 状态标签
        self.status_label = QLabel("就绪")
        statusbar.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        statusbar.addPermanentWidget(self.progress_bar)
        
        # 任务计数
        self.task_label = QLabel("任务: 0")
        statusbar.addPermanentWidget(self.task_label)
        
        # 内存使用
        self.memory_label = QLabel("内存: 0 MB")
        statusbar.addPermanentWidget(self.memory_label)
        
        # 定时更新状态
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(2000)  # 每2秒更新一次
    
    def _init_dock_widgets(self):
        """初始化停靠窗口"""
        # 日志停靠窗口
        log_dock = QDockWidget("日志", self)
        log_dock.setWidget(self.log_widget)
        log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)
        
        # 默认隐藏日志窗口
        log_dock.setVisible(False)
        
        # 在视图菜单中添加停靠窗口控制
        view_menu = self.menuBar().children()[2]  # 视图菜单
        if hasattr(view_menu, 'addSeparator'):
            view_menu.addSeparator()
            log_action = log_dock.toggleViewAction()
            log_action.setText("显示日志(&L)")
            view_menu.addAction(log_action)
    
    def _init_system_tray(self):
        """初始化系统托盘"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(self._create_app_icon())
            
            # 创建托盘菜单
            tray_menu = QMenu()
            
            show_action = QAction("显示主窗口", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            tray_menu.addSeparator()
            
            quit_action = QAction("退出", self)
            quit_action.triggered.connect(QApplication.quit)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._tray_icon_activated)
            
            # 显示托盘图标
            self.tray_icon.show()
    
    def _connect_signals(self):
        """连接信号"""
        try:
            # 连接状态信号
            self.status_changed.connect(self.status_label.setText)
            self.progress_changed.connect(self.progress_bar.setValue)
            
            # 连接子组件信号
            if self.crawler_widget:
                self.crawler_widget.status_changed.connect(self._on_module_status_changed)
                self.crawler_widget.progress_changed.connect(self._on_module_progress_changed)
            
            if self.video_processing_widget:
                self.video_processing_widget.status_changed.connect(self._on_module_status_changed)
                self.video_processing_widget.progress_changed.connect(self._on_module_progress_changed)
            
            if self.algorithm_widget:
                self.algorithm_widget.status_changed.connect(self._on_module_status_changed)
                self.algorithm_widget.progress_changed.connect(self._on_module_progress_changed)
            
            # 连接选项卡切换信号
            self.tab_widget.currentChanged.connect(self._on_tab_changed)
            
        except Exception as e:
            print(f"连接信号失败: {e}")
    
    def _apply_styles(self):
        """应用样式"""
        try:
            # 设置应用程序样式
            style = """
            QMainWindow {
                background-color: #f5f5f5;
            }
            
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #e1e1e1;
                border: 1px solid #c0c0c0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            
            QTabBar::tab:hover {
                background-color: #f0f0f0;
            }
            
            QStatusBar {
                background-color: #e1e1e1;
                border-top: 1px solid #c0c0c0;
            }
            
            QToolBar {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                spacing: 3px;
            }
            
            QToolBar QToolButton {
                padding: 5px;
                border: 1px solid transparent;
                border-radius: 3px;
            }
            
            QToolBar QToolButton:hover {
                background-color: #e0e0e0;
                border: 1px solid #c0c0c0;
            }
            
            QToolBar QToolButton:pressed {
                background-color: #d0d0d0;
            }
            
            QDockWidget {
                titlebar-close-icon: url(close.png);
                titlebar-normal-icon: url(float.png);
            }
            
            QDockWidget::title {
                background-color: #e1e1e1;
                padding: 5px;
                border: 1px solid #c0c0c0;
            }
            """
            
            self.setStyleSheet(style)
            
        except Exception as e:
            print(f"应用样式失败: {e}")
    
    def _create_app_icon(self) -> QIcon:
        """创建应用程序图标"""
        # 创建爬虫主题的应用程序图标
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        from PyQt5.QtGui import QPainter, QPen, QBrush, QRadialGradient
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建渐变背景
        gradient = QRadialGradient(16, 16, 16)
        gradient.setColorAt(0, Qt.cyan)
        gradient.setColorAt(0.7, Qt.blue)
        gradient.setColorAt(1, Qt.darkBlue)
        
        # 绘制圆形背景
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(Qt.darkBlue, 2))
        painter.drawEllipse(2, 2, 28, 28)
        
        # 绘制爬虫图案（蜘蛛网状）
        painter.setPen(QPen(Qt.white, 1.5))
        # 中心点
        center_x, center_y = 16, 16
        
        # 绘制放射线
        for angle in range(0, 360, 45):
            import math
            end_x = center_x + 10 * math.cos(math.radians(angle))
            end_y = center_y + 10 * math.sin(math.radians(angle))
            painter.drawLine(center_x, center_y, int(end_x), int(end_y))
        
        # 绘制同心圆
        painter.setPen(QPen(Qt.white, 1))
        for radius in [4, 8, 12]:
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # 绘制中心点
        painter.setBrush(QBrush(Qt.yellow))
        painter.setPen(QPen(Qt.white, 1))
        painter.drawEllipse(center_x - 2, center_y - 2, 4, 4)
        
        painter.end()
        return QIcon(pixmap)
    
    def _create_icon(self, name: str) -> QIcon:
        """创建图标"""
        # 创建SVG图标
        from PyQt5.QtSvg import QSvgRenderer
        from PyQt5.QtGui import QPainter
        from math import cos, sin, radians
        
        # SVG图标数据
        svg_icons = {
            "new": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2V22M2 12H22" stroke="#4CAF50" stroke-width="2" stroke-linecap="round"/>
            </svg>''',
            "open": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 7V5C3 3.89543 3.89543 3 5 3H9L11 5H19C20.1046 5 21 5.89543 21 7V19C21 20.1046 20.1046 21 19 21H5C3.89543 21 3 20.1046 3 19V7Z" stroke="#2196F3" stroke-width="2"/>
            </svg>''',
            "save": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M19 21H5C3.89543 21 3 20.1046 3 19V5C3 3.89543 3.89543 3 5 3H16L21 8V19C21 20.1046 20.1046 21 19 21Z" stroke="#FF9800" stroke-width="2"/>
                <path d="M7 3V8H15" stroke="#FF9800" stroke-width="2"/>
                <path d="M7 13V21" stroke="#FF9800" stroke-width="2"/>
            </svg>''',
            "play": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M8 5V19L19 12L8 5Z" fill="#4CAF50" stroke="#4CAF50" stroke-width="2"/>
            </svg>''',
            "stop": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="6" y="6" width="12" height="12" fill="#F44336" stroke="#F44336" stroke-width="2"/>
            </svg>''',
            "settings": '''<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="#757575" stroke-width="2"/>
                <path d="M19.4 15C19.2669 15.3016 19.2272 15.6362 19.286 15.9606C19.3448 16.285 19.4995 16.5843 19.73 16.82L19.79 16.88C19.976 17.0657 20.1235 17.2863 20.2241 17.5291C20.3248 17.7719 20.3766 18.0322 20.3766 18.295C20.3766 18.5578 20.3248 18.8181 20.2241 19.0609C20.1235 19.3037 19.976 19.5243 19.79 19.71C19.6043 19.896 19.3837 20.0435 19.1409 20.1441C18.8981 20.2448 18.6378 20.2966 18.375 20.2966C18.1122 20.2966 17.8519 20.2448 17.6091 20.1441C17.3663 20.0435 17.1457 19.896 16.96 19.71L16.9 19.65C16.6643 19.4195 16.365 19.2648 16.0406 19.206C15.7162 19.1472 15.3816 19.1869 15.08 19.32C14.7842 19.4468 14.532 19.6572 14.3543 19.9255C14.1766 20.1938 14.0813 20.5082 14.08 20.83V21C14.08 21.5304 13.8693 22.0391 13.4942 22.4142C13.1191 22.7893 12.6104 23 12.08 23C11.5496 23 11.0409 22.7893 10.6658 22.4142C10.2907 22.0391 10.08 21.5304 10.08 21V20.91C10.0723 20.579 9.96512 20.2579 9.77251 19.9887C9.5799 19.7194 9.31074 19.5143 9 19.4C8.69838 19.2669 8.36381 19.2272 8.03941 19.286C7.71502 19.3448 7.41568 19.4995 7.18 19.73L7.12 19.79C6.93425 19.976 6.71368 20.1235 6.47088 20.2241C6.22808 20.3248 5.96783 20.3766 5.705 20.3766C5.44217 20.3766 5.18192 20.3248 4.93912 20.2241C4.69632 20.1235 4.47575 19.976 4.29 19.79C4.10405 19.6043 3.95653 19.3837 3.85588 19.1409C3.75523 18.8981 3.70343 18.6378 3.70343 18.375C3.70343 18.1122 3.75523 17.8519 3.85588 17.6091C3.95653 17.3663 4.10405 17.1457 4.29 16.96L4.35 16.9C4.58054 16.6643 4.73519 16.365 4.794 16.0406C4.85282 15.7162 4.81312 15.3816 4.68 15.08C4.55324 14.7842 4.34276 14.532 4.07447 14.3543C3.80618 14.1766 3.49179 14.0813 3.17 14.08H3C2.46957 14.08 1.96086 13.8693 1.58579 13.4942C1.21071 13.1191 1 12.6104 1 12.08C1 11.5496 1.21071 11.0409 1.58579 10.6658C1.96086 10.2907 2.46957 10.08 3 10.08H3.09C3.42099 10.0723 3.742 9.96512 4.01127 9.77251C4.28054 9.5799 4.48571 9.31074 4.6 9C4.73312 8.69838 4.77282 8.36381 4.714 8.03941C4.65519 7.71502 4.50054 7.41568 4.27 7.18L4.21 7.12C4.02405 6.93425 3.87653 6.71368 3.77588 6.47088C3.67523 6.22808 3.62343 5.96783 3.62343 5.705C3.62343 5.44217 3.67523 5.18192 3.77588 4.93912C3.87653 4.69632 4.02405 4.47575 4.21 4.29C4.39575 4.10405 4.61632 3.95653 4.85912 3.85588C5.10192 3.75523 5.36217 3.70343 5.625 3.70343C5.88783 3.70343 6.14808 3.75523 6.39088 3.85588C6.63368 3.95653 6.85425 4.10405 7.04 4.29L7.1 4.35C7.33568 4.58054 7.63502 4.73519 7.95941 4.794C8.28381 4.85282 8.61838 4.81312 8.92 4.68H9C9.29577 4.55324 9.54802 4.34276 9.72569 4.07447C9.90337 3.80618 9.99872 3.49179 10 3.17V3C10 2.46957 10.2107 1.96086 10.5858 1.58579C10.9609 1.21071 11.4696 1 12 1C12.5304 1 13.0391 1.21071 13.4142 1.58579C13.7893 1.96086 14 2.46957 14 3V3.09C14.0013 3.41179 14.0966 3.72618 14.2743 3.99447C14.452 4.26276 14.7042 4.47324 15 4.6C15.3016 4.73312 15.6362 4.77282 15.9606 4.714C16.285 4.65519 16.5843 4.50054 16.82 4.27L16.88 4.21C17.0657 4.02405 17.2863 3.87653 17.5291 3.77588C17.7719 3.67523 18.0322 3.62343 18.295 3.62343C18.5578 3.62343 18.8181 3.67523 19.0609 3.77588C19.3037 3.87653 19.5243 4.02405 19.71 4.21C19.896 4.39575 20.0435 4.61632 20.1441 4.85912C20.2448 5.10192 20.2966 5.36217 20.2966 5.625C20.2966 5.88783 20.2448 6.14808 20.1441 6.39088C20.0435 6.63368 19.896 6.85425 19.71 7.04L19.65 7.1C19.4195 7.33568 19.2648 7.63502 19.206 7.95941C19.1472 8.28381 19.1869 8.61838 19.32 8.92V9C19.4468 9.29577 19.6572 9.54802 19.9255 9.72569C20.1938 9.90337 20.5082 9.99872 20.83 10H21C21.5304 10 22.0391 10.2107 22.4142 10.5858C22.7893 10.9609 23 11.4696 23 12C23 12.5304 22.7893 13.0391 22.4142 13.4142C22.0391 13.7893 21.5304 14 21 14H20.91C20.5882 14.0013 20.2738 14.0966 20.0055 14.2743C19.7372 14.452 19.5268 14.7042 19.4 15Z" stroke="#757575" stroke-width="2"/>
            </svg>'''
        }
        
        try:
            # 尝试使用SVG图标
            if name in svg_icons:
                svg_data = svg_icons[name].encode('utf-8')
                renderer = QSvgRenderer(svg_data)
                
                pixmap = QPixmap(24, 24)
                pixmap.fill(Qt.transparent)
                
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                
                return QIcon(pixmap)
        except ImportError:
            # 如果没有SVG支持，使用改进的像素图标
            pass
        
        # 备用方案：创建改进的像素图标
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if name == "new":
            painter.setPen(QPen(QColor(76, 175, 80), 3))
            painter.drawLine(12, 4, 12, 20)
            painter.drawLine(4, 12, 20, 12)
        elif name == "open":
            painter.setPen(QPen(QColor(33, 150, 243), 2))
            painter.setBrush(QColor(33, 150, 243, 50))
            painter.drawRect(4, 8, 16, 12)
            painter.drawLine(4, 8, 8, 4)
            painter.drawLine(8, 4, 16, 4)
        elif name == "save":
            painter.setPen(QPen(QColor(255, 152, 0), 2))
            painter.setBrush(QColor(255, 152, 0, 50))
            painter.drawRect(4, 4, 16, 16)
            painter.drawRect(6, 4, 8, 6)
        elif name == "play":
            painter.setPen(QPen(QColor(76, 175, 80), 2))
            painter.setBrush(QColor(76, 175, 80))
            points = [QPoint(8, 6), QPoint(8, 18), QPoint(18, 12)]
            painter.drawPolygon(points)
        elif name == "stop":
            painter.setPen(QPen(QColor(244, 67, 54), 2))
            painter.setBrush(QColor(244, 67, 54))
            painter.drawRect(6, 6, 12, 12)
        elif name == "settings":
            painter.setPen(QPen(QColor(117, 117, 117), 2))
            painter.drawEllipse(8, 8, 8, 8)
            # 绘制齿轮齿
            for i in range(8):
                angle = i * 45
                x1 = 12 + 6 * cos(radians(angle))
                y1 = 12 + 6 * sin(radians(angle))
                x2 = 12 + 8 * cos(radians(angle))
                y2 = 12 + 8 * sin(radians(angle))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        else:
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawRect(4, 4, 16, 16)
        
        painter.end()
        return QIcon(pixmap)
    
    def _load_settings(self):
        """加载设置"""
        try:
            # 恢复窗口几何
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
            
            # 恢复窗口状态
            state = self.settings.value("windowState")
            if state:
                self.restoreState(state)
            
            # 恢复当前选项卡
            current_tab = self.settings.value("currentTab", 0, type=int)
            self.tab_widget.setCurrentIndex(current_tab)
            
        except Exception as e:
            print(f"加载设置失败: {e}")
    
    def _save_settings(self):
        """保存设置"""
        try:
            # 保存窗口几何
            self.settings.setValue("geometry", self.saveGeometry())
            
            # 保存窗口状态
            self.settings.setValue("windowState", self.saveState())
            
            # 保存当前选项卡
            self.settings.setValue("currentTab", self.tab_widget.currentIndex())
            
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    # 槽函数
    def _new_project(self):
        """新建项目"""
        try:
            # TODO: 实现新建项目功能
            self.status_changed.emit("新建项目")
            QMessageBox.information(self, "信息", "新建项目功能待实现")
        except Exception as e:
            print(f"新建项目失败: {e}")
            QMessageBox.critical(self, "错误", f"新建项目失败: {e}")
    
    def _open_project(self):
        """打开项目"""
        try:
            # TODO: 实现打开项目功能
            self.status_changed.emit("打开项目")
            QMessageBox.information(self, "信息", "打开项目功能待实现")
        except Exception as e:
            print(f"打开项目失败: {e}")
            QMessageBox.critical(self, "错误", f"打开项目失败: {e}")
    
    def _save_project(self):
        """保存项目"""
        try:
            # TODO: 实现保存项目功能
            self.status_changed.emit("保存项目")
            QMessageBox.information(self, "信息", "保存项目功能待实现")
        except Exception as e:
            print(f"保存项目失败: {e}")
            QMessageBox.critical(self, "错误", f"保存项目失败: {e}")
    
    def _import_config(self):
        """导入配置"""
        try:
            # TODO: 实现导入配置功能
            self.status_changed.emit("导入配置")
            QMessageBox.information(self, "信息", "导入配置功能待实现")
        except Exception as e:
            print(f"导入配置失败: {e}")
            QMessageBox.critical(self, "错误", f"导入配置失败: {e}")
    
    def _export_config(self):
        """导出配置"""
        try:
            # TODO: 实现导出配置功能
            self.status_changed.emit("导出配置")
            QMessageBox.information(self, "信息", "导出配置功能待实现")
        except Exception as e:
            print(f"导出配置失败: {e}")
            QMessageBox.critical(self, "错误", f"导出配置失败: {e}")
    
    def _show_preferences(self):
        """显示偏好设置"""
        try:
            # 切换到配置选项卡
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i).endswith("配置"):
                    self.tab_widget.setCurrentIndex(i)
                    break
        except Exception as e:
            print(f"显示偏好设置失败: {e}")
    
    def _toggle_fullscreen(self, checked: bool):
        """切换全屏模式"""
        try:
            if checked:
                self.showFullScreen()
            else:
                self.showNormal()
        except Exception as e:
            print(f"切换全屏模式失败: {e}")
    
    def _clear_cache(self):
        """清理缓存"""
        try:
            # TODO: 实现清理缓存功能
            self.status_changed.emit("清理缓存")
            QMessageBox.information(self, "信息", "清理缓存功能待实现")
        except Exception as e:
            print(f"清理缓存失败: {e}")
            QMessageBox.critical(self, "错误", f"清理缓存失败: {e}")
    
    def _check_updates(self):
        """检查更新"""
        try:
            # TODO: 实现检查更新功能
            self.status_changed.emit("检查更新")
            QMessageBox.information(self, "信息", "检查更新功能待实现")
        except Exception as e:
            print(f"检查更新失败: {e}")
            QMessageBox.critical(self, "错误", f"检查更新失败: {e}")
    
    def _show_manual(self):
        """显示用户手册"""
        try:
            # TODO: 实现显示用户手册功能
            QMessageBox.information(self, "用户手册", "用户手册功能待实现")
        except Exception as e:
            print(f"显示用户手册失败: {e}")
    
    def _show_about(self):
        """显示关于对话框"""
        try:
            about_text = """
            <h2>视频处理系统</h2>
            <p>版本: 1.0.0</p>
            <p>一个集成了爬虫、视频处理和算法分析的综合性视频处理平台</p>
            <p>功能特性:</p>
            <ul>
                <li>🕷️ 多平台视频爬取 (B站、YouTube、抖音)</li>
                <li>🎬 专业视频编辑处理</li>
                <li>🤖 AI算法分析 (2D/3D姿态估计、视频描述)</li>
                <li>⚙️ 灵活的配置管理</li>
                <li>🔌 可扩展的插件系统</li>
            </ul>
            <p>© 2024 Video Processing System. All rights reserved.</p>
            """
            
            QMessageBox.about(self, "关于", about_text)
        except Exception as e:
            print(f"显示关于对话框失败: {e}")
    
    def _start_processing(self):
        """开始处理"""
        try:
            current_widget = self.tab_widget.currentWidget()
            if hasattr(current_widget, 'start_processing'):
                current_widget.start_processing()
                self.is_processing = True
                self.start_action.setEnabled(False)
                self.stop_action.setEnabled(True)
                self.progress_bar.setVisible(True)
                self.status_changed.emit("处理中...")
        except Exception as e:
            print(f"开始处理失败: {e}")
            QMessageBox.critical(self, "错误", f"开始处理失败: {e}")
    
    def _stop_processing(self):
        """停止处理"""
        try:
            current_widget = self.tab_widget.currentWidget()
            if hasattr(current_widget, 'stop_processing'):
                current_widget.stop_processing()
                self.is_processing = False
                self.start_action.setEnabled(True)
                self.stop_action.setEnabled(False)
                self.progress_bar.setVisible(False)
                self.status_changed.emit("已停止")
        except Exception as e:
            print(f"停止处理失败: {e}")
            QMessageBox.critical(self, "错误", f"停止处理失败: {e}")
    
    def _update_status(self):
        """更新状态信息"""
        try:
            # 更新任务计数
            task_count = len(self.current_tasks)
            self.task_label.setText(f"任务: {task_count}")
            
            # 更新内存使用
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.memory_label.setText(f"内存: {memory_mb:.1f} MB")
            except ImportError:
                self.memory_label.setText("内存: N/A")
            
        except Exception as e:
            print(f"更新状态失败: {e}")
    
    def _on_module_status_changed(self, status: str):
        """模块状态改变"""
        self.status_changed.emit(status)
    
    def _on_module_progress_changed(self, progress: int):
        """模块进度改变"""
        self.progress_changed.emit(progress)
    
    def _on_tab_changed(self, index: int):
        """选项卡改变"""
        try:
            tab_text = self.tab_widget.tabText(index)
            self.status_changed.emit(f"切换到: {tab_text}")
        except Exception as e:
            print(f"处理选项卡改变失败: {e}")
    
    def _tray_icon_activated(self, reason):
        """系统托盘图标激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
    
    # 重写事件处理
    def closeEvent(self, event):
        """关闭事件"""
        try:
            # 如果有正在进行的任务，询问是否确认退出
            if self.is_processing:
                reply = QMessageBox.question(
                    self, "确认退出",
                    "有任务正在进行中，确定要退出吗？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    event.ignore()
                    return
            
            # 保存设置
            self._save_settings()
            
            # 清理资源
            self._cleanup()
            
            # 隐藏到系统托盘而不是退出
            if self.tray_icon and self.tray_icon.isVisible():
                self.hide()
                event.ignore()
                if not hasattr(self, '_tray_message_shown'):
                    self.tray_icon.showMessage(
                        "视频处理系统",
                        "应用程序已最小化到系统托盘",
                        QSystemTrayIcon.Information,
                        2000
                    )
                    self._tray_message_shown = True
            else:
                event.accept()
                
        except Exception as e:
            print(f"关闭事件处理失败: {e}")
            event.accept()
    
    def _cleanup(self):
        """清理资源"""
        try:
            # 停止定时器
            if hasattr(self, 'status_timer'):
                self.status_timer.stop()
            
            # 清理子组件
            if self.crawler_widget:
                self.crawler_widget.cleanup()
            
            if self.video_processing_widget:
                self.video_processing_widget.cleanup()
            
            if self.algorithm_widget:
                self.algorithm_widget.cleanup()
            
            print("主窗口资源清理完成")
            
        except Exception as e:
            print(f"资源清理失败: {e}")
    
    def add_task(self, task_info: Dict[str, Any]):
        """添加任务"""
        try:
            self.current_tasks.append(task_info)
            
            # 如果有任务管理器，同步任务
            if hasattr(self, 'task_manager') and self.task_manager:
                try:
                    from ..core.task_manager import Task
                    task = Task(
                        name=task_info.get('name', 'Unknown'),
                        task_type=task_info.get('type', 'unknown'),
                        params=task_info
                    )
                    self.task_manager.add_task(task)
                except Exception as e:
                    print(f"同步任务到任务管理器失败: {e}")
            
            print(f"添加任务: {task_info.get('name', 'Unknown')}")
        except Exception as e:
            print(f"添加任务失败: {e}")
    
    def remove_task(self, task_id: str):
        """移除任务"""
        try:
            self.current_tasks = [task for task in self.current_tasks if task.get('id') != task_id]
            
            # 如果有任务管理器，同步移除任务
            if hasattr(self, 'task_manager') and self.task_manager:
                try:
                    task_manager_core = self.task_manager.get_task_manager()
                    task_manager_core.remove_task(task_id)
                except Exception as e:
                    print(f"从任务管理器移除任务失败: {e}")
            
            print(f"移除任务: {task_id}")
        except Exception as e:
            print(f"移除任务失败: {e}")
    
    def show_notification(self, title: str, message: str, icon_type=QSystemTrayIcon.Information):
        """显示通知"""
        try:
            if self.tray_icon and self.tray_icon.isVisible():
                self.tray_icon.showMessage(title, message, icon_type, 3000)
            else:
                # 如果没有系统托盘，使用消息框
                if icon_type == QSystemTrayIcon.Critical:
                    QMessageBox.critical(self, title, message)
                elif icon_type == QSystemTrayIcon.Warning:
                    QMessageBox.warning(self, title, message)
                else:
                    QMessageBox.information(self, title, message)
        except Exception as e:
            print(f"显示通知失败: {e}")