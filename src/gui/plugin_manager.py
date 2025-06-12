# -*- coding: utf-8 -*-
"""
插件管理器组件
提供插件的加载、卸载、配置和管理功能的用户界面
"""

import os
import sys
import json
import importlib
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QFormLayout,
    QPlainTextEdit, QDateTimeEdit, QToolBar, QAction,
    QMenu, QApplication, QStatusBar, QDialogButtonBox,
    QTextBrowser, QDialog
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime,
    QUrl, QPropertyAnimation, QEasingCurve, QObject
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QIntValidator, QDoubleValidator,
    QTextCursor, QTextCharFormat, QColor, QSyntaxHighlighter,
    QTextDocument, QKeySequence, QPainter, QPen, QBrush
)

from ..utils.logger import Logger
from ..core.plugin_manager import PluginManager as CorePluginManager

class PluginInfo:
    """插件信息类"""
    
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", "未知插件")
        self.version = data.get("version", "1.0.0")
        self.description = data.get("description", "")
        self.author = data.get("author", "未知作者")
        self.email = data.get("email", "")
        self.website = data.get("website", "")
        self.license = data.get("license", "")
        self.dependencies = data.get("dependencies", [])
        self.category = data.get("category", "其他")
        self.tags = data.get("tags", [])
        self.enabled = data.get("enabled", False)
        self.path = data.get("path", "")
        self.module = data.get("module", None)
        self.config = data.get("config", {})
        self.status = data.get("status", "未加载")
        self.error = data.get("error", "")

class PluginListWidget(QListWidget):
    """插件列表控件"""
    
    plugin_selected = pyqtSignal(PluginInfo)
    plugin_toggled = pyqtSignal(PluginInfo, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.plugins = {}
        self.setAlternatingRowColors(True)
        self.itemClicked.connect(self._on_item_clicked)
    
    def add_plugin(self, plugin_info: PluginInfo):
        """添加插件"""
        item = QListWidgetItem()
        item.setText(f"{plugin_info.name} v{plugin_info.version}")
        item.setData(Qt.UserRole, plugin_info.name)
        
        # 设置图标和状态
        if plugin_info.enabled:
            item.setIcon(QIcon(":/icons/plugin_enabled.png"))
        else:
            item.setIcon(QIcon(":/icons/plugin_disabled.png"))
        
        # 设置工具提示
        tooltip = f"名称: {plugin_info.name}\n"
        tooltip += f"版本: {plugin_info.version}\n"
        tooltip += f"作者: {plugin_info.author}\n"
        tooltip += f"状态: {plugin_info.status}\n"
        if plugin_info.description:
            tooltip += f"描述: {plugin_info.description}"
        item.setToolTip(tooltip)
        
        self.addItem(item)
        self.plugins[plugin_info.name] = plugin_info
    
    def update_plugin(self, plugin_info: PluginInfo):
        """更新插件信息"""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.UserRole) == plugin_info.name:
                item.setText(f"{plugin_info.name} v{plugin_info.version}")
                
                if plugin_info.enabled:
                    item.setIcon(QIcon(":/icons/plugin_enabled.png"))
                else:
                    item.setIcon(QIcon(":/icons/plugin_disabled.png"))
                
                # 更新工具提示
                tooltip = f"名称: {plugin_info.name}\n"
                tooltip += f"版本: {plugin_info.version}\n"
                tooltip += f"作者: {plugin_info.author}\n"
                tooltip += f"状态: {plugin_info.status}\n"
                if plugin_info.description:
                    tooltip += f"描述: {plugin_info.description}"
                item.setToolTip(tooltip)
                
                break
        
        self.plugins[plugin_info.name] = plugin_info
    
    def remove_plugin(self, plugin_name: str):
        """移除插件"""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.UserRole) == plugin_name:
                self.takeItem(i)
                break
        
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
    
    def get_selected_plugin(self) -> Optional[PluginInfo]:
        """获取选中的插件"""
        current_item = self.currentItem()
        if current_item:
            plugin_name = current_item.data(Qt.UserRole)
            return self.plugins.get(plugin_name)
        return None
    
    def _on_item_clicked(self, item):
        """处理项目点击"""
        plugin_name = item.data(Qt.UserRole)
        plugin_info = self.plugins.get(plugin_name)
        if plugin_info:
            self.plugin_selected.emit(plugin_info)

class PluginDetailWidget(QWidget):
    """插件详情控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_plugin = None
        self._init_ui()
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 插件信息
        info_group = QGroupBox("插件信息")
        info_layout = QFormLayout(info_group)
        
        self.name_label = QLabel("未选择插件")
        self.name_label.setFont(QFont("Arial", 12, QFont.Bold))
        info_layout.addRow("名称:", self.name_label)
        
        self.version_label = QLabel("-")
        info_layout.addRow("版本:", self.version_label)
        
        self.author_label = QLabel("-")
        info_layout.addRow("作者:", self.author_label)
        
        self.status_label = QLabel("-")
        info_layout.addRow("状态:", self.status_label)
        
        self.category_label = QLabel("-")
        info_layout.addRow("分类:", self.category_label)
        
        layout.addWidget(info_group)
        
        # 插件描述
        desc_group = QGroupBox("描述")
        desc_layout = QVBoxLayout(desc_group)
        
        self.description_text = QTextBrowser()
        self.description_text.setMaximumHeight(100)
        desc_layout.addWidget(self.description_text)
        
        layout.addWidget(desc_group)
        
        # 依赖项
        deps_group = QGroupBox("依赖项")
        deps_layout = QVBoxLayout(deps_group)
        
        self.dependencies_list = QListWidget()
        self.dependencies_list.setMaximumHeight(80)
        deps_layout.addWidget(self.dependencies_list)
        
        layout.addWidget(deps_group)
        
        # 配置
        config_group = QGroupBox("配置")
        config_layout = QVBoxLayout(config_group)
        
        self.config_text = QTextEdit()
        self.config_text.setMaximumHeight(120)
        config_layout.addWidget(self.config_text)
        
        # 配置按钮
        config_btn_layout = QHBoxLayout()
        
        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.clicked.connect(self._save_config)
        config_btn_layout.addWidget(self.save_config_btn)
        
        self.reset_config_btn = QPushButton("重置配置")
        self.reset_config_btn.clicked.connect(self._reset_config)
        config_btn_layout.addWidget(self.reset_config_btn)
        
        config_btn_layout.addStretch()
        config_layout.addLayout(config_btn_layout)
        
        layout.addWidget(config_group)
        
        layout.addStretch()
    
    def set_plugin(self, plugin_info: PluginInfo):
        """设置插件信息"""
        self.current_plugin = plugin_info
        
        # 更新基本信息
        self.name_label.setText(plugin_info.name)
        self.version_label.setText(plugin_info.version)
        self.author_label.setText(plugin_info.author)
        self.status_label.setText(plugin_info.status)
        self.category_label.setText(plugin_info.category)
        
        # 更新描述
        self.description_text.setPlainText(plugin_info.description)
        
        # 更新依赖项
        self.dependencies_list.clear()
        for dep in plugin_info.dependencies:
            self.dependencies_list.addItem(dep)
        
        # 更新配置
        config_text = json.dumps(plugin_info.config, indent=2, ensure_ascii=False)
        self.config_text.setPlainText(config_text)
        
        # 设置状态颜色
        if plugin_info.status == "已加载":
            self.status_label.setStyleSheet("color: green;")
        elif plugin_info.status == "错误":
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setStyleSheet("color: orange;")
    
    def clear(self):
        """清空显示"""
        self.current_plugin = None
        self.name_label.setText("未选择插件")
        self.version_label.setText("-")
        self.author_label.setText("-")
        self.status_label.setText("-")
        self.category_label.setText("-")
        self.description_text.clear()
        self.dependencies_list.clear()
        self.config_text.clear()
        self.status_label.setStyleSheet("")
    
    def _save_config(self):
        """保存配置"""
        if not self.current_plugin:
            return
        
        try:
            config_text = self.config_text.toPlainText()
            config = json.loads(config_text)
            
            # TODO: 保存配置到插件管理器
            QMessageBox.information(self, "信息", "配置已保存")
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "错误", f"配置格式错误: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")
    
    def _reset_config(self):
        """重置配置"""
        if not self.current_plugin:
            return
        
        reply = QMessageBox.question(
            self, "确认", "确定要重置配置吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # TODO: 重置配置
            self.config_text.setPlainText("{}")

class PluginManagerWidget(QWidget):
    """插件管理器主控件"""
    
    plugin_loaded = pyqtSignal(str)  # 插件名称
    plugin_unloaded = pyqtSignal(str)  # 插件名称
    plugin_enabled = pyqtSignal(str, bool)  # 插件名称, 启用状态
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = Logger().get_logger("PluginManagerWidget")
        self.plugin_manager = CorePluginManager()
        
        self._init_ui()
        self._connect_signals()
        self._load_plugins()
        
        self.logger.info("插件管理器界面初始化完成")
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_plugins)
        toolbar_layout.addWidget(self.refresh_btn)
        
        self.install_btn = QPushButton("安装插件")
        self.install_btn.clicked.connect(self._install_plugin)
        toolbar_layout.addWidget(self.install_btn)
        
        self.uninstall_btn = QPushButton("卸载插件")
        self.uninstall_btn.clicked.connect(self._uninstall_plugin)
        toolbar_layout.addWidget(self.uninstall_btn)
        
        toolbar_layout.addStretch()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索插件...")
        self.search_edit.textChanged.connect(self._filter_plugins)
        toolbar_layout.addWidget(self.search_edit)
        
        layout.addLayout(toolbar_layout)
        
        # 主要内容区域
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：插件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 分类过滤
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("分类:"))
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "爬虫", "视频处理", "AI算法", "工具", "其他"])
        self.category_combo.currentTextChanged.connect(self._filter_plugins)
        category_layout.addWidget(self.category_combo)
        
        category_layout.addStretch()
        left_layout.addLayout(category_layout)
        
        # 插件列表
        self.plugin_list = PluginListWidget()
        left_layout.addWidget(self.plugin_list)
        
        # 插件控制按钮
        control_layout = QHBoxLayout()
        
        self.enable_btn = QPushButton("启用")
        self.enable_btn.clicked.connect(self._toggle_plugin)
        control_layout.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("禁用")
        self.disable_btn.clicked.connect(self._toggle_plugin)
        control_layout.addWidget(self.disable_btn)
        
        self.reload_btn = QPushButton("重新加载")
        self.reload_btn.clicked.connect(self._reload_plugin)
        control_layout.addWidget(self.reload_btn)
        
        left_layout.addLayout(control_layout)
        
        splitter.addWidget(left_widget)
        
        # 右侧：插件详情
        self.plugin_detail = PluginDetailWidget()
        splitter.addWidget(self.plugin_detail)
        
        # 设置分割比例
        splitter.setSizes([300, 400])
        
        layout.addWidget(splitter)
        
        # 状态栏
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.plugin_count_label = QLabel("插件: 0")
        status_layout.addWidget(self.plugin_count_label)
        
        layout.addLayout(status_layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.plugin_list.plugin_selected.connect(self.plugin_detail.set_plugin)
        self.plugin_list.plugin_selected.connect(self._update_buttons)
    
    def _load_plugins(self):
        """加载插件"""
        try:
            self.status_label.setText("正在加载插件...")
            
            # 获取插件信息
            plugins = self.plugin_manager.get_all_plugins()
            
            self.plugin_list.clear()
            
            for plugin_name, plugin_data in plugins.items():
                plugin_info = PluginInfo(plugin_data)
                self.plugin_list.add_plugin(plugin_info)
            
            self._update_plugin_count()
            self.status_label.setText("插件加载完成")
            
        except Exception as e:
            self.logger.error(f"加载插件失败: {e}")
            self.status_label.setText(f"加载失败: {e}")
            QMessageBox.critical(self, "错误", f"加载插件失败: {e}")
    
    def _refresh_plugins(self):
        """刷新插件列表"""
        self._load_plugins()
    
    def _install_plugin(self):
        """安装插件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择插件文件", "", 
                "插件文件 (*.py *.zip);;Python文件 (*.py);;压缩文件 (*.zip)"
            )
            
            if file_path:
                # TODO: 实现插件安装
                QMessageBox.information(self, "信息", "插件安装功能待实现")
                
        except Exception as e:
            self.logger.error(f"安装插件失败: {e}")
            QMessageBox.critical(self, "错误", f"安装插件失败: {e}")
    
    def _uninstall_plugin(self):
        """卸载插件"""
        try:
            plugin_info = self.plugin_list.get_selected_plugin()
            if not plugin_info:
                QMessageBox.warning(self, "警告", "请先选择要卸载的插件")
                return
            
            reply = QMessageBox.question(
                self, "确认卸载", 
                f"确定要卸载插件 '{plugin_info.name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # TODO: 实现插件卸载
                QMessageBox.information(self, "信息", "插件卸载功能待实现")
                
        except Exception as e:
            self.logger.error(f"卸载插件失败: {e}")
            QMessageBox.critical(self, "错误", f"卸载插件失败: {e}")
    
    def _toggle_plugin(self):
        """切换插件状态"""
        try:
            plugin_info = self.plugin_list.get_selected_plugin()
            if not plugin_info:
                QMessageBox.warning(self, "警告", "请先选择插件")
                return
            
            sender = self.sender()
            enable = sender == self.enable_btn
            
            if enable:
                success = self.plugin_manager.enable_plugin(plugin_info.name)
                action = "启用"
            else:
                success = self.plugin_manager.disable_plugin(plugin_info.name)
                action = "禁用"
            
            if success:
                plugin_info.enabled = enable
                plugin_info.status = "已加载" if enable else "已禁用"
                self.plugin_list.update_plugin(plugin_info)
                self.plugin_detail.set_plugin(plugin_info)
                self._update_buttons()
                
                self.status_label.setText(f"插件 '{plugin_info.name}' {action}成功")
                self.plugin_enabled.emit(plugin_info.name, enable)
            else:
                QMessageBox.warning(self, "警告", f"{action}插件失败")
                
        except Exception as e:
            self.logger.error(f"切换插件状态失败: {e}")
            QMessageBox.critical(self, "错误", f"操作失败: {e}")
    
    def _reload_plugin(self):
        """重新加载插件"""
        try:
            plugin_info = self.plugin_list.get_selected_plugin()
            if not plugin_info:
                QMessageBox.warning(self, "警告", "请先选择插件")
                return
            
            success = self.plugin_manager.reload_plugin(plugin_info.name)
            
            if success:
                # 更新插件信息
                updated_data = self.plugin_manager.get_plugin_info(plugin_info.name)
                if updated_data:
                    updated_info = PluginInfo(updated_data)
                    self.plugin_list.update_plugin(updated_info)
                    self.plugin_detail.set_plugin(updated_info)
                
                self.status_label.setText(f"插件 '{plugin_info.name}' 重新加载成功")
            else:
                QMessageBox.warning(self, "警告", "重新加载插件失败")
                
        except Exception as e:
            self.logger.error(f"重新加载插件失败: {e}")
            QMessageBox.critical(self, "错误", f"重新加载失败: {e}")
    
    def _filter_plugins(self):
        """过滤插件"""
        try:
            search_text = self.search_edit.text().lower()
            category = self.category_combo.currentText()
            
            for i in range(self.plugin_list.count()):
                item = self.plugin_list.item(i)
                plugin_name = item.data(Qt.UserRole)
                plugin_info = self.plugin_list.plugins.get(plugin_name)
                
                if plugin_info:
                    # 文本过滤
                    text_match = (
                        search_text in plugin_info.name.lower() or
                        search_text in plugin_info.description.lower() or
                        search_text in plugin_info.author.lower()
                    )
                    
                    # 分类过滤
                    category_match = (
                        category == "全部" or
                        plugin_info.category == category
                    )
                    
                    item.setHidden(not (text_match and category_match))
                    
        except Exception as e:
            self.logger.error(f"过滤插件失败: {e}")
    
    def _update_buttons(self):
        """更新按钮状态"""
        plugin_info = self.plugin_list.get_selected_plugin()
        
        if plugin_info:
            self.enable_btn.setEnabled(not plugin_info.enabled)
            self.disable_btn.setEnabled(plugin_info.enabled)
            self.reload_btn.setEnabled(True)
            self.uninstall_btn.setEnabled(True)
        else:
            self.enable_btn.setEnabled(False)
            self.disable_btn.setEnabled(False)
            self.reload_btn.setEnabled(False)
            self.uninstall_btn.setEnabled(False)
    
    def _update_plugin_count(self):
        """更新插件计数"""
        total_count = len(self.plugin_list.plugins)
        enabled_count = sum(1 for p in self.plugin_list.plugins.values() if p.enabled)
        
        self.plugin_count_label.setText(f"插件: {total_count} (已启用: {enabled_count})")
    
    # 公共接口
    def get_plugin_manager(self) -> CorePluginManager:
        """获取插件管理器"""
        return self.plugin_manager
    
    def refresh(self):
        """刷新界面"""
        self._refresh_plugins()
    
    def get_enabled_plugins(self) -> List[str]:
        """获取已启用的插件列表"""
        return [name for name, info in self.plugin_list.plugins.items() if info.enabled]
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """启用插件"""
        try:
            success = self.plugin_manager.enable_plugin(plugin_name)
            if success:
                self._refresh_plugins()
            return success
        except Exception as e:
            self.logger.error(f"启用插件失败: {e}")
            return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """禁用插件"""
        try:
            success = self.plugin_manager.disable_plugin(plugin_name)
            if success:
                self._refresh_plugins()
            return success
        except Exception as e:
            self.logger.error(f"禁用插件失败: {e}")
            return False

class PluginInstallDialog(QDialog):
    """插件安装对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = Logger().get_logger("PluginInstallDialog")
        
        self.setWindowTitle("安装插件")
        self.setModal(True)
        self.setFixedSize(500, 400)
        self._init_ui()
        
        self.logger.info("插件安装对话框初始化完成")
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 安装方式选择
        method_group = QGroupBox("安装方式")
        method_layout = QVBoxLayout(method_group)
        
        self.file_radio = QCheckBox("从文件安装")
        self.file_radio.setChecked(True)
        method_layout.addWidget(self.file_radio)
        
        self.url_radio = QCheckBox("从URL安装")
        method_layout.addWidget(self.url_radio)
        
        self.repo_radio = QCheckBox("从仓库安装")
        method_layout.addWidget(self.repo_radio)
        
        layout.addWidget(method_group)
        
        # 文件选择
        file_group = QGroupBox("文件路径")
        file_layout = QHBoxLayout(file_group)
        
        self.file_edit = QLineEdit()
        file_layout.addWidget(self.file_edit)
        
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)
        
        layout.addWidget(file_group)
        
        # URL输入
        url_group = QGroupBox("下载URL")
        url_layout = QVBoxLayout(url_group)
        
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/plugin.zip")
        url_layout.addWidget(self.url_edit)
        
        layout.addWidget(url_group)
        
        # 仓库搜索
        repo_group = QGroupBox("插件仓库")
        repo_layout = QVBoxLayout(repo_group)
        
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索插件...")
        search_layout.addWidget(self.search_edit)
        
        self.search_btn = QPushButton("搜索")
        search_layout.addWidget(self.search_btn)
        
        repo_layout.addLayout(search_layout)
        
        self.repo_list = QListWidget()
        repo_layout.addWidget(self.repo_list)
        
        layout.addWidget(repo_group)
        
        # 安装选项
        options_group = QGroupBox("安装选项")
        options_layout = QVBoxLayout(options_group)
        
        self.auto_enable_check = QCheckBox("安装后自动启用")
        self.auto_enable_check.setChecked(True)
        options_layout.addWidget(self.auto_enable_check)
        
        self.install_deps_check = QCheckBox("自动安装依赖")
        self.install_deps_check.setChecked(True)
        options_layout.addWidget(self.install_deps_check)
        
        layout.addWidget(options_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.install_btn = QPushButton("安装")
        self.install_btn.clicked.connect(self._install_plugin)
        button_layout.addWidget(self.install_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择插件文件", "",
            "插件文件 (*.py *.zip);;Python文件 (*.py);;压缩文件 (*.zip)"
        )
        
        if file_path:
            self.file_edit.setText(file_path)
    
    def _install_plugin(self):
        """安装插件"""
        try:
            # TODO: 实现插件安装逻辑
            QMessageBox.information(self, "信息", "插件安装功能待实现")
            self.accept()
            
        except Exception as e:
            self.logger.error(f"安装插件失败: {e}")
            QMessageBox.critical(self, "错误", f"安装插件失败: {e}")

# 便捷函数
def show_plugin_manager(parent=None) -> PluginManagerWidget:
    """显示插件管理器"""
    widget = PluginManagerWidget(parent)
    return widget

def show_plugin_install_dialog(parent=None) -> PluginInstallDialog:
    """显示插件安装对话框"""
    dialog = PluginInstallDialog(parent)
    dialog.exec_()
    return dialog