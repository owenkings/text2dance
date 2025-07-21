# -*- coding: utf-8 -*-
"""
GUI模块
提供图形用户界面相关的组件和功能
"""

# 导入主要组件
from .app import Application, create_application
from .main_window import MainWindow
from .crawler_widget import CrawlerWidget
from .video_widget import VideoEditWidget
from .config_widget import ConfigWidget
from .log_viewer import LogViewer
from .progress_dialog import ProgressDialog, MultiTaskProgressDialog
from .about_dialog import AboutDialog, UpdateDialog
# from .settings_dialog import SettingsDialog  # 模块不存在，暂时注释
from .plugin_manager import PluginManagerWidget
# from .task_manager import TaskManagerWidget  # task_manager已移除

# 版本信息
__version__ = "3.2.0"
__author__ = "开发团队"

# 导出的组件
__all__ = [
    # 主要组件
    "Application",
    "create_application",
    "MainWindow",
    
    # 功能组件
    "CrawlerWidget",
    "VideoEditWidget",
    "ConfigWidget",
    "LogViewer",
    
    # 对话框
    "ProgressDialog",
    "MultiTaskProgressDialog",
    "AboutDialog",
    "UpdateDialog",
    # "SettingsDialog",  # 模块不存在，暂时注释
    
    # 管理器
    "PluginManagerWidget",
    # "TaskManagerWidget",  # task_manager已移除
]

# 便捷函数
def show_about():
    """显示关于对话框"""
    from .about_dialog import show_about_dialog
    return show_about_dialog()

def show_settings():
    """显示设置对话框"""
    # from .settings_dialog import SettingsDialog  # 模块不存在，暂时注释
    # dialog = SettingsDialog()
    # return dialog.exec_()
    print("设置对话框功能暂未实现")
    return False

def show_plugin_manager():
    """显示插件管理器"""
    from .plugin_manager import show_plugin_manager
    return show_plugin_manager()

def show_task_manager():
    """显示任务管理器"""
    # from .task_manager import show_task_manager  # task_manager已移除
    # return show_task_manager()
    print("任务管理器功能已移除")
    return False

def show_progress_dialog(title="处理中", message="请稍候...", parent=None):
    """显示进度对话框"""
    from .progress_dialog import show_progress_dialog
    return show_progress_dialog(title, message, parent)

def show_multi_task_progress_dialog(title="批量处理", parent=None):
    """显示多任务进度对话框"""
    from .progress_dialog import show_multi_task_progress_dialog
    return show_multi_task_progress_dialog(title, parent)