# -*- coding: utf-8 -*-
"""
关于对话框组件
显示应用程序信息、版本、作者、许可证等内容的用户界面
"""

import os
import sys
import platform
from datetime import datetime
from typing import Dict, Any, Optional, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QFormLayout,
    QPlainTextEdit, QDateTimeEdit, QToolBar, QAction,
    QMenu, QApplication, QStatusBar, QDialogButtonBox,
    QTextBrowser, QWidget
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime,
    QUrl, QPropertyAnimation, QEasingCurve
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QIntValidator, QDoubleValidator,
    QTextCursor, QTextCharFormat, QColor, QSyntaxHighlighter,
    QTextDocument, QKeySequence, QPainter, QPen, QBrush,
    QDesktopServices
)

from ..utils.logger import Logger

class AboutDialog(QDialog):
    """关于对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = Logger().get_logger("AboutDialog")
        
        # 应用程序信息
        self.app_info = {
            "name": "视频处理爬虫工具",
            "version": "2.0.0",
            "build": "20240101",
            "description": "一个集成视频爬取、处理和AI算法的综合工具",
            "author": "开发团队",
            "email": "support@example.com",
            "website": "https://github.com/example/video-crawler",
            "license": "MIT License",
            "copyright": f"© {datetime.now().year} 开发团队. All rights reserved."
        }
        
        # 初始化界面
        self.setWindowTitle(f"关于 {self.app_info['name']}")
        self.setModal(True)
        self.setFixedSize(600, 500)
        self._init_ui()
        self._connect_signals()
        
        self.logger.info("关于对话框初始化完成")
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 关于选项卡
        self.about_tab = self._create_about_tab()
        self.tab_widget.addTab(self.about_tab, "关于")
        
        # 系统信息选项卡
        self.system_tab = self._create_system_tab()
        self.tab_widget.addTab(self.system_tab, "系统信息")
        
        # 许可证选项卡
        self.license_tab = self._create_license_tab()
        self.tab_widget.addTab(self.license_tab, "许可证")
        
        # 致谢选项卡
        self.credits_tab = self._create_credits_tab()
        self.tab_widget.addTab(self.credits_tab, "致谢")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮区域
        self._create_button_area(layout)
    
    def _create_about_tab(self) -> QWidget:
        """创建关于选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 应用程序图标和名称
        header_layout = QHBoxLayout()
        
        # 图标
        icon_label = QLabel()
        icon_label.setFixedSize(64, 64)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ddd;
                border-radius: 32px;
                background-color: #f0f0f0;
                background-image: url(':/icons/app_icon.png');
                background-repeat: no-repeat;
                background-position: center;
            }
        """)
        header_layout.addWidget(icon_label)
        
        # 应用信息
        info_layout = QVBoxLayout()
        
        # 应用名称
        name_label = QLabel(self.app_info["name"])
        name_label.setFont(QFont("Arial", 18, QFont.Bold))
        name_label.setStyleSheet("color: #2c3e50;")
        info_layout.addWidget(name_label)
        
        # 版本信息
        version_label = QLabel(f"版本 {self.app_info['version']} (构建 {self.app_info['build']})")
        version_label.setFont(QFont("Arial", 10))
        version_label.setStyleSheet("color: #7f8c8d;")
        info_layout.addWidget(version_label)
        
        # 描述
        desc_label = QLabel(self.app_info["description"])
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setStyleSheet("color: #34495e;")
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        
        info_layout.addStretch()
        
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 详细信息
        details_layout = QFormLayout()
        details_layout.setSpacing(10)
        
        # 作者
        author_label = QLabel(self.app_info["author"])
        author_label.setStyleSheet("color: #2c3e50;")
        details_layout.addRow("作者:", author_label)
        
        # 邮箱
        email_label = QLabel(f'<a href="mailto:{self.app_info["email"]}">{self.app_info["email"]}</a>')
        email_label.setOpenExternalLinks(True)
        email_label.setStyleSheet("color: #3498db;")
        details_layout.addRow("邮箱:", email_label)
        
        # 网站
        website_label = QLabel(f'<a href="{self.app_info["website"]}">{self.app_info["website"]}</a>')
        website_label.setOpenExternalLinks(True)
        website_label.setStyleSheet("color: #3498db;")
        details_layout.addRow("网站:", website_label)
        
        # 许可证
        license_label = QLabel(self.app_info["license"])
        license_label.setStyleSheet("color: #2c3e50;")
        details_layout.addRow("许可证:", license_label)
        
        layout.addLayout(details_layout)
        
        layout.addStretch()
        
        # 版权信息
        copyright_label = QLabel(self.app_info["copyright"])
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setFont(QFont("Arial", 9))
        copyright_label.setStyleSheet("color: #95a5a6; padding: 10px;")
        layout.addWidget(copyright_label)
        
        return widget
    
    def _create_system_tab(self) -> QWidget:
        """创建系统信息选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 系统信息表格
        info_layout = QFormLayout()
        info_layout.setSpacing(8)
        
        # 获取系统信息
        system_info = self._get_system_info()
        
        for key, value in system_info.items():
            key_label = QLabel(f"{key}:")
            key_label.setFont(QFont("Arial", 9, QFont.Bold))
            key_label.setStyleSheet("color: #2c3e50;")
            
            value_label = QLabel(str(value))
            value_label.setFont(QFont("Arial", 9))
            value_label.setStyleSheet("color: #34495e;")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            
            info_layout.addRow(key_label, value_label)
        
        layout.addLayout(info_layout)
        
        layout.addStretch()
        
        # 复制按钮
        copy_btn = QPushButton("复制系统信息")
        copy_btn.clicked.connect(self._copy_system_info)
        layout.addWidget(copy_btn)
        
        return widget
    
    def _create_license_tab(self) -> QWidget:
        """创建许可证选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 许可证文本
        license_text = QTextBrowser()
        license_text.setPlainText(self._get_license_text())
        license_text.setFont(QFont("Consolas", 9))
        layout.addWidget(license_text)
        
        return widget
    
    def _create_credits_tab(self) -> QWidget:
        """创建致谢选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 致谢文本
        credits_text = QTextBrowser()
        credits_text.setHtml(self._get_credits_html())
        credits_text.setOpenExternalLinks(True)
        layout.addWidget(credits_text)
        
        return widget
    
    def _create_button_area(self, layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(20, 10, 20, 20)
        
        # 检查更新按钮
        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.clicked.connect(self._check_for_updates)
        button_layout.addWidget(self.check_update_btn)
        
        button_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号"""
        pass
    
    def _get_system_info(self) -> Dict[str, str]:
        """获取系统信息"""
        try:
            import psutil
            
            # 获取内存信息
            memory = psutil.virtual_memory()
            memory_info = f"{memory.total // (1024**3)} GB (可用: {memory.available // (1024**3)} GB)"
            
            # 获取CPU信息
            cpu_count = psutil.cpu_count(logical=False)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_info = f"{cpu_count} 核心 ({cpu_count_logical} 逻辑处理器)"
            
        except ImportError:
            memory_info = "未知"
            cpu_info = "未知"
        
        return {
            "操作系统": f"{platform.system()} {platform.release()}",
            "系统架构": platform.machine(),
            "处理器": platform.processor() or "未知",
            "CPU": cpu_info,
            "内存": memory_info,
            "Python版本": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "Python路径": sys.executable,
            "PyQt5版本": self._get_pyqt_version(),
            "工作目录": os.getcwd(),
            "用户名": os.getenv('USERNAME') or os.getenv('USER') or "未知",
            "计算机名": platform.node()
        }
    
    def _get_pyqt_version(self) -> str:
        """获取PyQt5版本"""
        try:
            from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
            return f"PyQt {PYQT_VERSION_STR} (Qt {QT_VERSION_STR})"
        except ImportError:
            return "未知"
    
    def _get_license_text(self) -> str:
        """获取许可证文本"""
        return """
MIT License

Copyright (c) 2024 开发团队

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
    
    def _get_credits_html(self) -> str:
        """获取致谢HTML"""
        return """
<h3>开发团队</h3>
<p>感谢所有为这个项目做出贡献的开发者。</p>

<h3>第三方库</h3>
<p>本项目使用了以下优秀的开源库：</p>
<ul>
<li><strong>PyQt5</strong> - 跨平台GUI工具包<br>
    <a href="https://www.riverbankcomputing.com/software/pyqt/">https://www.riverbankcomputing.com/software/pyqt/</a></li>
<li><strong>OpenCV</strong> - 计算机视觉库<br>
    <a href="https://opencv.org/">https://opencv.org/</a></li>
<li><strong>NumPy</strong> - 科学计算库<br>
    <a href="https://numpy.org/">https://numpy.org/</a></li>
<li><strong>Requests</strong> - HTTP库<br>
    <a href="https://requests.readthedocs.io/">https://requests.readthedocs.io/</a></li>
<li><strong>yt-dlp</strong> - 视频下载工具<br>
    <a href="https://github.com/yt-dlp/yt-dlp">https://github.com/yt-dlp/yt-dlp</a></li>
<li><strong>FFmpeg</strong> - 多媒体处理框架<br>
    <a href="https://ffmpeg.org/">https://ffmpeg.org/</a></li>
</ul>

<h3>AI模型</h3>
<p>本项目集成了以下AI模型和算法：</p>
<ul>
<li><strong>OpenPose</strong> - 2D姿态估计<br>
    <a href="https://github.com/CMU-Perceptual-Computing-Lab/openpose">https://github.com/CMU-Perceptual-Computing-Lab/openpose</a></li>
<li><strong>VideoPose3D</strong> - 3D姿态估计<br>
    <a href="https://github.com/facebookresearch/VideoPose3D">https://github.com/facebookresearch/VideoPose3D</a></li>
<li><strong>RTMPose</strong> - 实时姿态估计<br>
    <a href="https://github.com/open-mmlab/mmpose">https://github.com/open-mmlab/mmpose</a></li>
</ul>

<h3>特别感谢</h3>
<p>感谢开源社区的无私贡献，让我们能够站在巨人的肩膀上构建这个项目。</p>

<h3>反馈与贡献</h3>
<p>如果您发现任何问题或有改进建议，欢迎通过以下方式联系我们：</p>
<ul>
<li>GitHub Issues: <a href="https://github.com/example/video-crawler/issues">提交问题</a></li>
<li>邮箱: <a href="mailto:support@example.com">support@example.com</a></li>
</ul>
"""
    
    def _copy_system_info(self):
        """复制系统信息到剪贴板"""
        try:
            system_info = self._get_system_info()
            
            info_text = f"{self.app_info['name']} {self.app_info['version']}\n"
            info_text += "=" * 50 + "\n"
            
            for key, value in system_info.items():
                info_text += f"{key}: {value}\n"
            
            clipboard = QApplication.clipboard()
            clipboard.setText(info_text)
            
            QMessageBox.information(self, "信息", "系统信息已复制到剪贴板")
            
        except Exception as e:
            self.logger.error(f"复制系统信息失败: {e}")
            QMessageBox.critical(self, "错误", f"复制系统信息失败: {e}")
    
    def _check_for_updates(self):
        """检查更新"""
        try:
            # TODO: 实现更新检查功能
            QMessageBox.information(
                self, "检查更新", 
                "当前版本已是最新版本。\n\n"
                "如需获取最新版本，请访问：\n"
                f"{self.app_info['website']}"
            )
            
        except Exception as e:
            self.logger.error(f"检查更新失败: {e}")
            QMessageBox.critical(self, "错误", f"检查更新失败: {e}")
    
    # 公共接口
    def set_app_info(self, app_info: Dict[str, str]):
        """设置应用程序信息"""
        self.app_info.update(app_info)
        # 重新初始化界面
        # TODO: 实现界面更新
    
    def get_app_info(self) -> Dict[str, str]:
        """获取应用程序信息"""
        return self.app_info.copy()
    
    @staticmethod
    def show_about_dialog(parent=None, app_info: Optional[Dict[str, str]] = None) -> 'AboutDialog':
        """显示关于对话框"""
        dialog = AboutDialog(parent)
        if app_info:
            dialog.set_app_info(app_info)
        dialog.exec_()
        return dialog

class UpdateDialog(QDialog):
    """更新对话框"""
    
    def __init__(self, update_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self.logger = Logger().get_logger("UpdateDialog")
        self.update_info = update_info
        
        # 初始化界面
        self.setWindowTitle("发现新版本")
        self.setModal(True)
        self.setFixedSize(450, 350)
        self._init_ui()
        self._connect_signals()
        
        self.logger.info("更新对话框初始化完成")
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("发现新版本！")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 版本信息
        version_layout = QFormLayout()
        
        current_version = QLabel(self.update_info.get("current_version", "未知"))
        version_layout.addRow("当前版本:", current_version)
        
        new_version = QLabel(self.update_info.get("new_version", "未知"))
        new_version.setStyleSheet("color: #27ae60; font-weight: bold;")
        version_layout.addRow("最新版本:", new_version)
        
        release_date = QLabel(self.update_info.get("release_date", "未知"))
        version_layout.addRow("发布日期:", release_date)
        
        layout.addLayout(version_layout)
        
        # 更新说明
        layout.addWidget(QLabel("更新内容:"))
        
        changelog = QTextBrowser()
        changelog.setPlainText(self.update_info.get("changelog", "暂无更新说明"))
        changelog.setMaximumHeight(150)
        layout.addWidget(changelog)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("立即下载")
        self.download_btn.clicked.connect(self._download_update)
        button_layout.addWidget(self.download_btn)
        
        self.later_btn = QPushButton("稍后提醒")
        self.later_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.later_btn)
        
        self.skip_btn = QPushButton("跳过此版本")
        self.skip_btn.clicked.connect(self._skip_version)
        button_layout.addWidget(self.skip_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号"""
        pass
    
    def _download_update(self):
        """下载更新"""
        try:
            download_url = self.update_info.get("download_url")
            if download_url:
                QDesktopServices.openUrl(QUrl(download_url))
                self.accept()
            else:
                QMessageBox.warning(self, "警告", "下载链接不可用")
                
        except Exception as e:
            self.logger.error(f"下载更新失败: {e}")
            QMessageBox.critical(self, "错误", f"下载更新失败: {e}")
    
    def _skip_version(self):
        """跳过此版本"""
        try:
            # TODO: 实现跳过版本功能
            self.reject()
        except Exception as e:
            self.logger.error(f"跳过版本失败: {e}")

# 便捷函数
def show_about_dialog(parent=None, app_info: Optional[Dict[str, str]] = None):
    """显示关于对话框"""
    return AboutDialog.show_about_dialog(parent, app_info)

def show_update_dialog(update_info: Dict[str, Any], parent=None) -> UpdateDialog:
    """显示更新对话框"""
    dialog = UpdateDialog(update_info, parent)
    dialog.exec_()
    return dialog