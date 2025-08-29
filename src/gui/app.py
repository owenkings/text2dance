# -*- coding: utf-8 -*-
"""
主应用程序入口
提供应用程序的初始化、配置和启动功能
"""

import os
import sys
import json
import signal
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QSplashScreen, QSystemTrayIcon, QMenu, QAction,
    QStyleFactory, QDesktopWidget
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QTranslator,
    QLocale, QLibraryInfo, QSettings, QStandardPaths
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QPalette, QColor
)

# 导入自定义模块
from .main_window import MainWindow
from ..core.config_manager import ConfigManager
from ..core.plugin_manager import PluginManager

class Application(QApplication):
    """自定义应用程序类"""
    
    # 信号定义
    config_changed = pyqtSignal(dict)
    theme_changed = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    
    def __init__(self, argv):
        super().__init__(argv)
        
        # 基本属性
        self.app_name = "视频处理爬虫工具"
        self.app_version = "4.1.3"
        self.app_author = "开发团队"
        self.app_organization = "VideoTools"
        
        # 设置应用程序信息
        self.setApplicationName(self.app_name)
        self.setApplicationVersion(self.app_version)
        self.setOrganizationName(self.app_organization)
        self.setOrganizationDomain("videotools.com")
        
        # 初始化组件
        self.config_manager = None
        self.plugin_manager = None
        self.main_window = None
        self.splash_screen = None
        self.system_tray = None
        self.translator = None
        
        # 初始化应用程序
        self._init_app()
    
    def _init_app(self):
        """初始化应用程序"""
        try:
            # 设置应用程序图标
            self.setWindowIcon(QIcon(":/icons/app_icon.png"))
            
            # 显示启动画面
            self._show_splash_screen()
            
            # 初始化配置管理器
            self._update_splash_message("正在加载配置...")
            self._init_config()
            
            # 应用配置
            self._update_splash_message("正在应用配置...")
            self._apply_config()
            
            # 初始化核心组件
            self._update_splash_message("正在初始化核心组件...")
            self._init_core_components()
            
            # 初始化主窗口
            self._update_splash_message("正在创建主窗口...")
            self._init_main_window()
            
            # 初始化系统托盘
            self._update_splash_message("正在初始化系统托盘...")
            self._init_system_tray()
            
            # 设置信号处理
            self._update_splash_message("正在设置信号处理...")
            self._setup_signal_handlers()
            
            # 连接信号
            self._update_splash_message("正在连接信号...")
            self._connect_signals()
            
            # 完成初始化
            self._update_splash_message("初始化完成！")
            QApplication.processEvents()
            
            # 短暂延迟以显示完成消息
            import time
            time.sleep(0.5)
            
            print(f"{self.app_name} v{self.app_version} 初始化完成")
            
        except Exception as e:
            self._handle_init_error(e)
    
    def _show_splash_screen(self):
        """显示启动画面"""
        try:
            # 创建启动画面
            splash_pixmap = QPixmap(500, 350)
            splash_pixmap.fill(QColor(25, 25, 35))
            
            # 在启动画面上绘制内容
            from PyQt5.QtGui import QPainter, QLinearGradient, QPen
            from math import cos, sin, radians
            
            painter = QPainter(splash_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 绘制渐变背景
            gradient = QLinearGradient(0, 0, 0, 350)
            gradient.setColorAt(0, QColor(45, 45, 65))
            gradient.setColorAt(1, QColor(25, 25, 35))
            painter.fillRect(splash_pixmap.rect(), gradient)
            
            # 绘制标题
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
            from PyQt5.QtCore import QRect
            title_rect = QRect(0, 80, 500, 60)
            painter.drawText(title_rect, Qt.AlignCenter, "爬虫管理系统")
            
            # 绘制副标题
            painter.setPen(QColor(180, 180, 180))
            painter.setFont(QFont("Microsoft YaHei", 12))
            subtitle_rect = QRect(0, 140, 500, 30)
            painter.drawText(subtitle_rect, Qt.AlignCenter, "Spider Management System")
            
            # 绘制装饰性图标
            painter.setPen(QPen(QColor(64, 128, 255), 3))
            painter.setBrush(QColor(64, 128, 255, 100))
            center_x, center_y = 250, 200
            
            # 绘制蜘蛛网状图案
            for i in range(6):
                angle = i * 60
                x = center_x + 30 * cos(radians(angle))
                y = center_y + 30 * sin(radians(angle))
                painter.drawLine(center_x, center_y, int(x), int(y))
            
            # 绘制同心圆
            for radius in [15, 25, 35]:
                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
            
            # 绘制版本信息
            painter.setPen(QColor(120, 120, 120))
            painter.setFont(QFont("Arial", 10))
            version_rect = QRect(0, 300, 500, 20)
            painter.drawText(version_rect, Qt.AlignCenter, f"Version {self.app_version}")
            
            painter.end()
            
            self.splash_screen = QSplashScreen(splash_pixmap)
            self.splash_screen.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
            
            # 显示启动信息
            self.splash_screen.showMessage(
                f"正在启动 {self.app_name} v{self.app_version}...",
                Qt.AlignBottom | Qt.AlignCenter,
                QColor(255, 255, 255)
            )
            
            self.splash_screen.show()
            self.processEvents()
            
        except Exception as e:
            print(f"显示启动画面失败: {e}")
    
    def _update_splash_message(self, message: str):
        """更新启动画面消息"""
        if hasattr(self, 'splash_screen') and self.splash_screen:
            self.splash_screen.showMessage(
                message, 
                Qt.AlignBottom | Qt.AlignCenter, 
                QColor(255, 255, 255)
            )
            QApplication.processEvents()
    
    def _init_config(self):
        """初始化配置管理器"""
        try:
            self._update_splash_message("正在加载配置...")
            
            self.config_manager = ConfigManager()
            
            # 设置默认配置
            self._set_default_config()
            
            print("配置管理器初始化完成")
            
        except Exception as e:
            print(f"初始化配置管理器失败: {e}")
            raise
    
    def _set_default_config(self):
        """设置默认配置"""
        default_config = {
            "general": {
                "language": "zh_CN",
                "theme": "default",
                "auto_save": True,
                "check_updates": True,
                "log_level": "INFO"
            },
            "ui": {
                "window_state": "",
                "window_geometry": "",
                "splitter_states": {},
                "toolbar_visible": True,
                "statusbar_visible": True
            },
            "crawler": {
                "download_dir": str(Path.home() / "Downloads" / "VideoTools"),
                "max_concurrent": 3,
                "retry_count": 3,
                "timeout": 30,
                "proxy": ""
            },
            "video": {
                "output_dir": str(Path.home() / "Videos" / "VideoTools"),
                "temp_dir": str(Path.home() / "AppData" / "Local" / "VideoTools" / "temp"),
                "ffmpeg_path": "",
                "gpu_acceleration": False,
                "max_threads": 4
            },
            "algorithms": {
                "pose_2d": {
                    "default_algorithm": "openpose",
                    "confidence_threshold": 0.5
                },
                "pose_3d": {
                    "default_algorithm": "videopose3d",
                    "confidence_threshold": 0.5
                },
                "video_description": {
                    "default_algorithm": "ShareGPT4Video",
                    "max_length": 100
                }
            },
            "plugins": {
                "plugin_dir": str(Path.cwd() / "plugins"),
                "auto_load": True,
                "enabled_plugins": []
            }
        }
        
        # 设置默认值（如果不存在）
        for section, values in default_config.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    if not self.config_manager.has(f"{section}.{key}"):
                        self.config_manager.set(f"{section}.{key}", value)
            else:
                if not self.config_manager.has(f"general.{section}"):
                    self.config_manager.set(f"general.{section}", values)
    
    def _apply_config(self):
        """应用配置"""
        try:
            self._update_splash_message("正在应用配置...")
            
            # 应用语言设置
            language = self.config_manager.get("general.language", "zh_CN")
            self._set_language(language)
            
            # 应用主题设置
            theme = self.config_manager.get("general.theme", "default")
            self._set_theme(theme)
            
            # 应用字体设置
            self._set_font()
            
            print("配置应用完成")
            
        except Exception as e:
            print(f"应用配置失败: {e}")
    
    def _set_language(self, language: str):
        """设置语言"""
        try:
            # 移除旧的翻译器
            if self.translator:
                self.removeTranslator(self.translator)
            
            # 创建新的翻译器
            self.translator = QTranslator()
            
            # 加载翻译文件
            if language != "en_US":
                translation_file = f":/translations/{language}.qm"
                if self.translator.load(translation_file):
                    self.installTranslator(self.translator)
                    print(f"语言设置为: {language}")
                else:
                    print(f"无法加载翻译文件: {translation_file}")
            
            self.language_changed.emit(language)
            
        except Exception as e:
            print(f"设置语言失败: {e}")
    
    def _set_theme(self, theme: str):
        """设置主题"""
        try:
            if theme == "dark":
                self._apply_dark_theme()
            elif theme == "light":
                self._apply_light_theme()
            else:
                self._apply_default_theme()
            
            self.theme_changed.emit(theme)
            print(f"主题设置为: {theme}")
            
        except Exception as e:
            print(f"设置主题失败: {e}")
    
    def _apply_dark_theme(self):
        """应用深色主题"""
        dark_palette = QPalette()
        
        # 设置颜色
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
        dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        
        self.setPalette(dark_palette)
    
    def _apply_light_theme(self):
        """应用浅色主题"""
        light_palette = QPalette()
        
        # 设置颜色
        light_palette.setColor(QPalette.Window, QColor(240, 240, 240))
        light_palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Base, QColor(255, 255, 255))
        light_palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
        light_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
        light_palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Text, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Button, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        light_palette.setColor(QPalette.Link, QColor(0, 0, 255))
        light_palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        light_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        
        self.setPalette(light_palette)
    
    def _apply_default_theme(self):
        """应用默认主题"""
        self.setPalette(self.style().standardPalette())
    
    def _init_logging(self):
        """初始化日志系统"""
        try:
            from ..utils.logger import Logger
            # 创建Logger实例，这会自动初始化日志系统
            logger_instance = Logger()
            logger = logger_instance.get_logger("Application")
            logger.info("日志系统初始化完成")
            print("✅ 日志系统初始化完成")
        except Exception as e:
            print(f"⚠️ 日志系统初始化失败: {e}")
    
    def _set_font(self):
        """设置字体"""
        try:
            # 设置默认字体
            font = QFont("Microsoft YaHei", 9)
            if not font.exactMatch():
                font = QFont("Arial", 9)
            
            self.setFont(font)
            
        except Exception as e:
            print(f"设置字体失败: {e}")
    
    def _init_core_components(self):
        """初始化核心组件"""
        try:
            self._update_splash_message("正在初始化核心组件...")
            
            # 初始化日志系统
            self._init_logging()
            
            # 初始化插件管理器
            self.plugin_manager = PluginManager(self.config_manager)
            
            print("核心组件初始化完成")
            
        except Exception as e:
            print(f"初始化核心组件失败: {e}")
            raise
    
    def _init_main_window(self):
        """初始化主窗口"""
        try:
            self._update_splash_message("正在创建主窗口...")
            
            self.main_window = MainWindow()
            
            # 传递组件引用
            self.main_window.set_config_manager(self.config_manager)
            self.main_window.set_plugin_manager(self.plugin_manager)
            
            # 恢复窗口状态
            self._restore_window_state()
            
            print("主窗口初始化完成")
            
        except Exception as e:
            print(f"初始化主窗口失败: {e}")
            raise
    
    def _init_system_tray(self):
        """初始化系统托盘"""
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                print("系统托盘不可用")
                return
            
            self.system_tray = QSystemTrayIcon(self)
            self.system_tray.setIcon(QIcon(":/icons/app_icon.png"))
            self.system_tray.setToolTip(self.app_name)
            
            # 创建托盘菜单
            tray_menu = QMenu()
            
            show_action = QAction("显示主窗口", self)
            show_action.triggered.connect(self._show_main_window)
            tray_menu.addAction(show_action)
            
            tray_menu.addSeparator()
            
            quit_action = QAction("退出", self)
            quit_action.triggered.connect(self.quit)
            tray_menu.addAction(quit_action)
            
            self.system_tray.setContextMenu(tray_menu)
            
            # 连接信号
            self.system_tray.activated.connect(self._on_tray_activated)
            
            self.system_tray.show()
            
            print("系统托盘初始化完成")
            
        except Exception as e:
            print(f"初始化系统托盘失败: {e}")
    
    def _setup_signal_handlers(self):
        """设置信号处理"""
        try:
            # 设置系统信号处理
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # 设置异常处理
            sys.excepthook = self._exception_handler
            
        except Exception as e:
            print(f"设置信号处理失败: {e}")
    
    def _connect_signals(self):
        """连接信号"""
        try:
            # 连接应用程序信号
            self.aboutToQuit.connect(self._on_about_to_quit)
            
            # 连接配置变化信号
            if self.config_manager:
                self.config_manager.config_changed.connect(self._on_config_changed)
            
        except Exception as e:
            print(f"连接信号失败: {e}")
    
    def _update_splash_message(self, message: str):
        """更新启动画面消息"""
        if self.splash_screen:
            self.splash_screen.showMessage(
                message,
                Qt.AlignBottom | Qt.AlignCenter,
                QColor(255, 255, 255)
            )
            self.processEvents()
    
    def _restore_window_state(self):
        """恢复窗口状态"""
        try:
            if not self.main_window:
                return
            
            # 恢复窗口几何
            geometry = self.config_manager.get("ui.window_geometry", "")
            if geometry:
                self.main_window.restoreGeometry(geometry.encode())
            else:
                # 居中显示
                self._center_window()
            
            # 恢复窗口状态
            state = self.config_manager.get("ui.window_state", "")
            if state:
                self.main_window.restoreState(state.encode())
            
        except Exception as e:
            print(f"恢复窗口状态失败: {e}")
    
    def _center_window(self):
        """居中显示窗口"""
        try:
            if not self.main_window:
                return
            
            desktop = QDesktopWidget()
            screen_rect = desktop.screenGeometry()
            window_rect = self.main_window.geometry()
            
            x = (screen_rect.width() - window_rect.width()) // 2
            y = (screen_rect.height() - window_rect.height()) // 2
            
            self.main_window.move(x, y)
            
        except Exception as e:
            print(f"居中窗口失败: {e}")
    
    def _save_window_state(self):
        """保存窗口状态"""
        try:
            if not self.main_window or not self.config_manager:
                return
            
            # 保存窗口几何
            geometry = self.main_window.saveGeometry().data().decode()
            self.config_manager.set("ui.window_geometry", geometry)
            
            # 保存窗口状态
            state = self.main_window.saveState().data().decode()
            self.config_manager.set("ui.window_state", state)
            
            # 保存配置
            self.config_manager.save()
            
        except Exception as e:
            print(f"保存窗口状态失败: {e}")
    
    def _show_main_window(self):
        """显示主窗口"""
        if self.main_window:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
    
    def _on_tray_activated(self, reason):
        """处理托盘激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_main_window()
    
    def _on_config_changed(self, config: Dict[str, Any]):
        """处理配置变化"""
        try:
            self.config_changed.emit(config)
            
            # 应用语言变化
            if "language" in config.get("general", {}):
                language = config["general"]["language"]
                self._set_language(language)
            
            # 应用主题变化
            if "theme" in config.get("general", {}):
                theme = config["general"]["theme"]
                self._set_theme(theme)
            
        except Exception as e:
            print(f"处理配置变化失败: {e}")
    
    def _on_about_to_quit(self):
        """处理退出前事件"""
        try:
            print("应用程序即将退出")
            
            # 保存窗口状态
            self._save_window_state()
            
            # 卸载所有插件
            if self.plugin_manager:
                self.plugin_manager.unload_all_plugins()
            
            # 隐藏系统托盘
            if self.system_tray:
                self.system_tray.hide()
            
        except Exception as e:
            print(f"退出前处理失败: {e}")
    
    def _signal_handler(self, signum, frame):
        """系统信号处理器"""
        try:
            self.logger.info(f"收到系统信号: {signum}")
        except:
            pass  # 避免重入调用
        self.quit()
    
    def _exception_handler(self, exc_type, exc_value, exc_traceback):
        """异常处理器"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        print(f"未处理的异常: {error_msg}")
        
        # 显示错误对话框
        if hasattr(self, 'main_window') and self.main_window:
            QMessageBox.critical(
                self.main_window,
                "严重错误",
                f"应用程序遇到严重错误:\n\n{exc_value}\n\n请查看日志文件获取详细信息。"
            )
    
    def _handle_init_error(self, error: Exception):
        """处理初始化错误"""
        error_msg = f"应用程序初始化失败: {error}"
        
        print(error_msg)
        
        # 隐藏启动画面
        if self.splash_screen:
            self.splash_screen.hide()
        
        # 显示错误对话框
        QMessageBox.critical(
            None,
            "初始化错误",
            f"{error_msg}\n\n应用程序将退出。"
        )
        
        sys.exit(1)
    
    # 公共接口
    def run(self):
        """运行应用程序"""
        try:
            # 隐藏启动画面
            if self.splash_screen:
                self.splash_screen.finish(self.main_window)
            
            # 显示主窗口
            if self.main_window:
                self.main_window.show()
            
            # 启动事件循环
            return self.exec_()
            
        except Exception as e:
            print(f"运行应用程序失败: {e}")
            return 1
    
    def get_config_manager(self) -> Optional[ConfigManager]:
        """获取配置管理器"""
        return self.config_manager
    
    def get_plugin_manager(self) -> Optional[PluginManager]:
        """获取插件管理器"""
        return self.plugin_manager
    
    
    def get_main_window(self) -> Optional[MainWindow]:
        """获取主窗口"""
        return self.main_window

def create_application(argv) -> Application:
    """创建应用程序实例"""
    # 设置高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 创建应用程序
    app = Application(argv)
    
    return app

def main():
    """主函数"""
    try:
        # 创建应用程序
        app = create_application(sys.argv)
        
        # 运行应用程序
        exit_code = app.run()
        
        # 退出
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"启动应用程序失败: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()