# -*- coding: utf-8 -*-
"""
任务管理器组件
提供任务的创建、监控、控制和管理功能的用户界面
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from enum import Enum
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
    QTextBrowser, QDialog, QAbstractItemView, QTableView
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime,
    QUrl, QPropertyAnimation, QEasingCurve, QObject,
    QAbstractTableModel, QModelIndex, QVariant
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QIntValidator, QDoubleValidator,
    QTextCursor, QTextCharFormat, QColor, QSyntaxHighlighter,
    QTextDocument, QKeySequence, QPainter, QPen, QBrush
)

from ..utils.logger import Logger
from ..core.task_manager import TaskManager as CoreTaskManager, Task, TaskStatus

class TaskTableModel(QAbstractTableModel):
    """任务表格模型"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.tasks = []
        self.headers = [
            "ID", "名称", "类型", "状态", "进度", 
            "开始时间", "结束时间", "耗时", "优先级"
        ]
    
    def rowCount(self, parent=QModelIndex()):
        return len(self.tasks)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.tasks):
            return QVariant()
        
        task = self.tasks[index.row()]
        column = index.column()
        
        if role == Qt.DisplayRole:
            if column == 0:  # ID
                return task.task_id
            elif column == 1:  # 名称
                return task.name
            elif column == 2:  # 类型
                return task.task_type
            elif column == 3:  # 状态
                return task.status.value
            elif column == 4:  # 进度
                return f"{task.progress:.1f}%"
            elif column == 5:  # 开始时间
                return task.start_time.strftime("%Y-%m-%d %H:%M:%S") if task.start_time else "-"
            elif column == 6:  # 结束时间
                return task.end_time.strftime("%Y-%m-%d %H:%M:%S") if task.end_time else "-"
            elif column == 7:  # 耗时
                if task.start_time:
                    end_time = task.end_time or datetime.now()
                    duration = end_time - task.start_time
                    return str(duration).split('.')[0]  # 去掉微秒
                return "-"
            elif column == 8:  # 优先级
                return task.priority
        
        elif role == Qt.TextAlignmentRole:
            if column in [0, 4, 8]:  # ID, 进度, 优先级
                return Qt.AlignCenter
            elif column in [5, 6, 7]:  # 时间相关
                return Qt.AlignCenter
        
        elif role == Qt.BackgroundRole:
            if task.status == TaskStatus.RUNNING:
                return QColor(173, 216, 230)  # 浅蓝色
            elif task.status == TaskStatus.COMPLETED:
                return QColor(144, 238, 144)  # 浅绿色
            elif task.status == TaskStatus.FAILED:
                return QColor(255, 182, 193)  # 浅红色
            elif task.status == TaskStatus.CANCELLED:
                return QColor(211, 211, 211)  # 浅灰色
        
        elif role == Qt.UserRole:
            return task
        
        return QVariant()
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return QVariant()
    
    def add_task(self, task: Task):
        """添加任务"""
        self.beginInsertRows(QModelIndex(), len(self.tasks), len(self.tasks))
        self.tasks.append(task)
        self.endInsertRows()
    
    def update_task(self, task: Task):
        """更新任务"""
        for i, t in enumerate(self.tasks):
            if t.task_id == task.task_id:
                self.tasks[i] = task
                # 发出数据变化信号
                top_left = self.index(i, 0)
                bottom_right = self.index(i, len(self.headers) - 1)
                self.dataChanged.emit(top_left, bottom_right)
                break
    
    def remove_task(self, task_id: str):
        """移除任务"""
        for i, task in enumerate(self.tasks):
            if task.task_id == task_id:
                self.beginRemoveRows(QModelIndex(), i, i)
                del self.tasks[i]
                self.endRemoveRows()
                break
    
    def clear(self):
        """清空任务"""
        self.beginResetModel()
        self.tasks.clear()
        self.endResetModel()
    
    def get_task(self, index: QModelIndex) -> Optional[Task]:
        """获取任务"""
        if index.isValid() and index.row() < len(self.tasks):
            return self.tasks[index.row()]
        return None

class TaskDetailWidget(QWidget):
    """任务详情控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_task = None
        self._init_ui()
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QFormLayout(info_group)
        
        self.id_label = QLabel("-")
        info_layout.addRow("任务ID:", self.id_label)
        
        self.name_label = QLabel("-")
        self.name_label.setFont(QFont("Arial", 10, QFont.Bold))
        info_layout.addRow("任务名称:", self.name_label)
        
        self.type_label = QLabel("-")
        info_layout.addRow("任务类型:", self.type_label)
        
        self.status_label = QLabel("-")
        info_layout.addRow("状态:", self.status_label)
        
        self.priority_label = QLabel("-")
        info_layout.addRow("优先级:", self.priority_label)
        
        layout.addWidget(info_group)
        
        # 进度信息
        progress_group = QGroupBox("进度信息")
        progress_layout = QVBoxLayout(progress_group)
        
        # 进度条
        progress_info_layout = QHBoxLayout()
        progress_info_layout.addWidget(QLabel("进度:"))
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_info_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("0%")
        progress_info_layout.addWidget(self.progress_label)
        
        progress_layout.addLayout(progress_info_layout)
        
        # 时间信息
        time_layout = QFormLayout()
        
        self.start_time_label = QLabel("-")
        time_layout.addRow("开始时间:", self.start_time_label)
        
        self.end_time_label = QLabel("-")
        time_layout.addRow("结束时间:", self.end_time_label)
        
        self.duration_label = QLabel("-")
        time_layout.addRow("耗时:", self.duration_label)
        
        self.eta_label = QLabel("-")
        time_layout.addRow("预计完成:", self.eta_label)
        
        progress_layout.addLayout(time_layout)
        
        layout.addWidget(progress_group)
        
        # 任务参数
        params_group = QGroupBox("任务参数")
        params_layout = QVBoxLayout(params_group)
        
        self.params_text = QTextBrowser()
        self.params_text.setMaximumHeight(100)
        params_layout.addWidget(self.params_text)
        
        layout.addWidget(params_group)
        
        # 任务结果
        result_group = QGroupBox("任务结果")
        result_layout = QVBoxLayout(result_group)
        
        self.result_text = QTextBrowser()
        self.result_text.setMaximumHeight(100)
        result_layout.addWidget(self.result_text)
        
        layout.addWidget(result_group)
        
        # 错误信息
        error_group = QGroupBox("错误信息")
        error_layout = QVBoxLayout(error_group)
        
        self.error_text = QTextBrowser()
        self.error_text.setMaximumHeight(80)
        error_layout.addWidget(self.error_text)
        
        layout.addWidget(error_group)
        
        layout.addStretch()
    
    def set_task(self, task: Task):
        """设置任务信息"""
        self.current_task = task
        
        # 更新基本信息
        self.id_label.setText(task.task_id)
        self.name_label.setText(task.name)
        self.type_label.setText(task.task_type)
        self.status_label.setText(task.status.value)
        self.priority_label.setText(str(task.priority))
        
        # 更新进度
        self.progress_bar.setValue(int(task.progress))
        self.progress_label.setText(f"{task.progress:.1f}%")
        
        # 更新时间信息
        if task.start_time:
            self.start_time_label.setText(task.start_time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.start_time_label.setText("-")
        
        if task.end_time:
            self.end_time_label.setText(task.end_time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self.end_time_label.setText("-")
        
        # 计算耗时
        if task.start_time:
            end_time = task.end_time or datetime.now()
            duration = end_time - task.start_time
            self.duration_label.setText(str(duration).split('.')[0])
            
            # 计算预计完成时间
            if task.status == TaskStatus.RUNNING and task.progress > 0:
                elapsed = (datetime.now() - task.start_time).total_seconds()
                total_estimated = elapsed * 100 / task.progress
                remaining = total_estimated - elapsed
                eta = datetime.now() + timedelta(seconds=remaining)
                self.eta_label.setText(eta.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                self.eta_label.setText("-")
        else:
            self.duration_label.setText("-")
            self.eta_label.setText("-")
        
        # 更新参数
        if task.params:
            params_text = json.dumps(task.params, indent=2, ensure_ascii=False)
            self.params_text.setPlainText(params_text)
        else:
            self.params_text.clear()
        
        # 更新结果
        if task.result:
            if isinstance(task.result, dict):
                result_text = json.dumps(task.result, indent=2, ensure_ascii=False)
            else:
                result_text = str(task.result)
            self.result_text.setPlainText(result_text)
        else:
            self.result_text.clear()
        
        # 更新错误信息
        if task.error:
            self.error_text.setPlainText(task.error)
            self.error_text.setStyleSheet("color: red;")
        else:
            self.error_text.clear()
            self.error_text.setStyleSheet("")
        
        # 设置状态颜色
        if task.status == TaskStatus.RUNNING:
            self.status_label.setStyleSheet("color: blue;")
        elif task.status == TaskStatus.COMPLETED:
            self.status_label.setStyleSheet("color: green;")
        elif task.status == TaskStatus.FAILED:
            self.status_label.setStyleSheet("color: red;")
        elif task.status == TaskStatus.CANCELLED:
            self.status_label.setStyleSheet("color: orange;")
        else:
            self.status_label.setStyleSheet("")
    
    def clear(self):
        """清空显示"""
        self.current_task = None
        
        self.id_label.setText("-")
        self.name_label.setText("-")
        self.type_label.setText("-")
        self.status_label.setText("-")
        self.priority_label.setText("-")
        
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        
        self.start_time_label.setText("-")
        self.end_time_label.setText("-")
        self.duration_label.setText("-")
        self.eta_label.setText("-")
        
        self.params_text.clear()
        self.result_text.clear()
        self.error_text.clear()
        
        self.status_label.setStyleSheet("")
        self.error_text.setStyleSheet("")

class TaskManagerWidget(QWidget):
    """任务管理器主控件"""
    
    task_selected = pyqtSignal(Task)
    task_started = pyqtSignal(str)  # 任务ID
    task_paused = pyqtSignal(str)   # 任务ID
    task_cancelled = pyqtSignal(str)  # 任务ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = Logger().get_logger("TaskManagerWidget")
        self.task_manager = CoreTaskManager()
        
        self._init_ui()
        self._connect_signals()
        self._setup_timer()
        
        self.logger.info("任务管理器界面初始化完成")
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 单个任务操作
        self.refresh_btn = QPushButton("🔄 刷新")
        self.start_btn = QPushButton("▶️ 开始")
        self.pause_btn = QPushButton("⏸️ 暂停")
        self.cancel_btn = QPushButton("⏹️ 取消")
        self.remove_btn = QPushButton("🗑️ 移除")
        
        # 批量操作
        self.start_all_btn = QPushButton("▶️ 全部开始")
        self.pause_all_btn = QPushButton("⏸️ 全部暂停")
        self.start_selected_btn = QPushButton("▶️ 选中开始")
        self.pause_selected_btn = QPushButton("⏸️ 选中暂停")
        
        # 线程配置
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("线程数:"))
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 50)
        self.thread_spinbox.setValue(15)
        self.thread_spinbox.valueChanged.connect(self._on_thread_count_changed)
        thread_layout.addWidget(self.thread_spinbox)
        
        # 连接信号
        self.refresh_btn.clicked.connect(self._refresh_tasks)
        self.start_btn.clicked.connect(self._start_task)
        self.pause_btn.clicked.connect(self._pause_task)
        self.cancel_btn.clicked.connect(self._cancel_task)
        self.remove_btn.clicked.connect(self._remove_task)
        
        self.start_all_btn.clicked.connect(self._on_start_all_tasks)
        self.pause_all_btn.clicked.connect(self._on_pause_all_tasks)
        self.start_selected_btn.clicked.connect(self._on_start_selected_tasks)
        self.pause_selected_btn.clicked.connect(self._on_pause_selected_tasks)
        
        # 添加到工具栏
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(QLabel("|"))  # 分隔符
        toolbar_layout.addWidget(self.start_btn)
        toolbar_layout.addWidget(self.pause_btn)
        toolbar_layout.addWidget(self.cancel_btn)
        toolbar_layout.addWidget(self.remove_btn)
        toolbar_layout.addWidget(QLabel("|"))  # 分隔符
        toolbar_layout.addWidget(self.start_all_btn)
        toolbar_layout.addWidget(self.pause_all_btn)
        toolbar_layout.addWidget(self.start_selected_btn)
        toolbar_layout.addWidget(self.pause_selected_btn)
        toolbar_layout.addWidget(QLabel("|"))  # 分隔符
        toolbar_layout.addLayout(thread_layout)
        toolbar_layout.addStretch()
        
        # 过滤器
        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部", "等待中", "运行中", "已完成", "失败", "已取消"])
        self.status_filter.currentTextChanged.connect(self._filter_tasks)
        toolbar_layout.addWidget(QLabel("状态:"))
        toolbar_layout.addWidget(self.status_filter)
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["全部", "爬虫", "视频处理", "AI算法", "其他"])
        self.type_filter.currentTextChanged.connect(self._filter_tasks)
        toolbar_layout.addWidget(QLabel("类型:"))
        toolbar_layout.addWidget(self.type_filter)
        
        layout.addLayout(toolbar_layout)
        
        # 主要内容区域
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：任务列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 任务表格
        self.task_model = TaskTableModel()
        self.task_table = QTableView()
        self.task_table.setModel(self.task_model)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.horizontalHeader().setStretchLastSection(True)
        self.task_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        left_layout.addWidget(self.task_table)
        
        splitter.addWidget(left_widget)
        
        # 右侧：任务详情
        self.task_detail = TaskDetailWidget()
        splitter.addWidget(self.task_detail)
        
        # 设置分割比例
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        
        # 状态栏
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.task_count_label = QLabel("任务: 0")
        status_layout.addWidget(self.task_count_label)
        
        self.running_count_label = QLabel("运行中: 0")
        status_layout.addWidget(self.running_count_label)
        
        layout.addLayout(status_layout)
    
    def _connect_signals(self):
        """连接信号"""
        # 连接任务管理器信号
        self.task_manager.task_added.connect(self._on_task_added)
        self.task_manager.task_updated.connect(self._on_task_updated)
        self.task_manager.task_removed.connect(self._on_task_removed)
        if hasattr(self.task_manager, 'batch_progress_updated'):
            self.task_manager.batch_progress_updated.connect(self._on_batch_progress_updated)
    
    def _setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_running_tasks)
        self.update_timer.start(1000)  # 每秒更新一次
    
    def _refresh_tasks(self):
        """刷新任务列表"""
        try:
            self.status_label.setText("正在刷新任务...")
            
            # 清空当前任务
            self.task_model.clear()
            
            # 获取所有任务
            tasks = self.task_manager.get_all_tasks()
            
            for task in tasks:
                self.task_model.add_task(task)
            
            self._update_task_counts()
            self._update_buttons()
            self.status_label.setText("任务刷新完成")
            
        except Exception as e:
            self.logger.error(f"刷新任务失败: {e}")
            self.status_label.setText(f"刷新失败: {e}")
            QMessageBox.critical(self, "错误", f"刷新任务失败: {e}")
    
    def _start_task(self):
        """开始任务"""
        try:
            task = self._get_selected_task()
            if not task:
                QMessageBox.warning(self, "警告", "请先选择任务")
                return
            
            if task.status not in [TaskStatus.PENDING, TaskStatus.PAUSED]:
                QMessageBox.warning(self, "警告", "只能开始等待中或已暂停的任务")
                return
            
            success = self.task_manager.start_task(task.task_id)
            
            if success:
                self.status_label.setText(f"任务 '{task.name}' 已开始")
                self.task_started.emit(task.task_id)
            else:
                QMessageBox.warning(self, "警告", "开始任务失败")
                
        except Exception as e:
            self.logger.error(f"开始任务失败: {e}")
            QMessageBox.critical(self, "错误", f"开始任务失败: {e}")
    
    def _pause_task(self):
        """暂停任务"""
        try:
            task = self._get_selected_task()
            if not task:
                QMessageBox.warning(self, "警告", "请先选择任务")
                return
            
            if task.status != TaskStatus.RUNNING:
                QMessageBox.warning(self, "警告", "只能暂停运行中的任务")
                return
            
            success = self.task_manager.pause_task(task.task_id)
            
            if success:
                self.status_label.setText(f"任务 '{task.name}' 已暂停")
                self.task_paused.emit(task.task_id)
            else:
                QMessageBox.warning(self, "警告", "暂停任务失败")
                
        except Exception as e:
            self.logger.error(f"暂停任务失败: {e}")
            QMessageBox.critical(self, "错误", f"暂停任务失败: {e}")
    
    def _cancel_task(self):
        """取消任务"""
        try:
            task = self._get_selected_task()
            if not task:
                QMessageBox.warning(self, "警告", "请先选择任务")
                return
            
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                QMessageBox.warning(self, "警告", "无法取消已完成的任务")
                return
            
            reply = QMessageBox.question(
                self, "确认取消", 
                f"确定要取消任务 '{task.name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success = self.task_manager.cancel_task(task.task_id)
                
                if success:
                    self.status_label.setText(f"任务 '{task.name}' 已取消")
                    self.task_cancelled.emit(task.task_id)
                else:
                    QMessageBox.warning(self, "警告", "取消任务失败")
                    
        except Exception as e:
            self.logger.error(f"取消任务失败: {e}")
            QMessageBox.critical(self, "错误", f"取消任务失败: {e}")
    
    def _remove_task(self):
        """移除任务"""
        try:
            task = self._get_selected_task()
            if not task:
                QMessageBox.warning(self, "警告", "请先选择任务")
                return
            
            if task.status == TaskStatus.RUNNING:
                QMessageBox.warning(self, "警告", "无法移除运行中的任务，请先取消")
                return
            
            reply = QMessageBox.question(
                self, "确认移除", 
                f"确定要移除任务 '{task.name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success = self.task_manager.remove_task(task.task_id)
                
                if success:
                    self.status_label.setText(f"任务 '{task.name}' 已移除")
                else:
                    QMessageBox.warning(self, "警告", "移除任务失败")
                    
        except Exception as e:
            self.logger.error(f"移除任务失败: {e}")
            QMessageBox.critical(self, "错误", f"移除任务失败: {e}")
    
    def _filter_tasks(self):
        """过滤任务"""
        try:
            status_filter = self.status_filter.currentText()
            type_filter = self.type_filter.currentText()
            
            # TODO: 实现任务过滤逻辑
            # 这里需要实现表格的过滤功能
            
        except Exception as e:
            self.logger.error(f"过滤任务失败: {e}")
    
    def _on_selection_changed(self):
        """处理选择变化"""
        task = self._get_selected_task()
        if task:
            self.task_detail.set_task(task)
            self.task_selected.emit(task)
        else:
            self.task_detail.clear()
        
        self._update_buttons()
    
    def _get_selected_task(self) -> Optional[Task]:
        """获取选中的任务"""
        selection = self.task_table.selectionModel().selectedRows()
        if selection:
            index = selection[0]
            return self.task_model.get_task(index)
        return None
    
    def _update_buttons(self):
        """更新按钮状态"""
        task = self._get_selected_task()
        
        if task:
            self.start_btn.setEnabled(task.status in [TaskStatus.PENDING, TaskStatus.PAUSED])
            self.pause_btn.setEnabled(task.status == TaskStatus.RUNNING)
            self.cancel_btn.setEnabled(task.status in [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED])
            self.remove_btn.setEnabled(task.status != TaskStatus.RUNNING)
        else:
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)
    
    def _update_task_counts(self):
        """更新任务计数"""
        total_count = len(self.task_model.tasks)
        running_count = sum(1 for task in self.task_model.tasks if task.status == TaskStatus.RUNNING)
        
        self.task_count_label.setText(f"任务: {total_count}")
        self.running_count_label.setText(f"运行中: {running_count}")
    
    def _update_running_tasks(self):
        """更新运行中的任务"""
        try:
            # 检查必要的对象是否存在
            if not hasattr(self, 'task_model') or self.task_model is None:
                self.logger.warning("task_model未初始化，跳过任务更新")
                return
                
            if not hasattr(self, 'task_manager') or self.task_manager is None:
                self.logger.warning("task_manager未初始化，跳过任务更新")
                return
            
            # 获取运行中的任务并更新进度
            tasks_to_update = []
            try:
                tasks_to_update = list(self.task_model.tasks)
            except (AttributeError, TypeError) as e:
                import traceback
                self.logger.warning(f"获取任务列表失败: {e}")
                self.logger.debug(f"获取任务列表失败详细信息: {traceback.format_exc()}")
                return
            
            for task in tasks_to_update:
                try:
                    if hasattr(task, 'status') and task.status == TaskStatus.RUNNING:
                        # 从任务管理器获取最新状态
                        updated_task = None
                        try:
                            updated_task = self.task_manager.get_task(task.task_id)
                        except Exception as e:
                            import traceback
                            self.logger.warning(f"获取任务状态失败 {task.task_id}: {e}")
                            self.logger.debug(f"获取任务状态失败详细信息 {task.task_id}: {traceback.format_exc()}")
                            continue
                            
                        if updated_task:
                            try:
                                self.task_model.update_task(updated_task)
                            except Exception as e:
                                import traceback
                                self.logger.warning(f"更新任务模型失败 {task.task_id}: {e}")
                                self.logger.debug(f"更新任务模型失败详细信息 {task.task_id}: {traceback.format_exc()}")
                                continue
                            
                            # 如果当前选中的是这个任务，更新详情
                            try:
                                selected_task = self._get_selected_task()
                                if (selected_task and hasattr(selected_task, 'task_id') and 
                                    hasattr(updated_task, 'task_id') and 
                                    selected_task.task_id == updated_task.task_id):
                                    if hasattr(self, 'task_detail') and self.task_detail is not None:
                                        self.task_detail.set_task(updated_task)
                            except Exception as e:
                                import traceback
                                self.logger.warning(f"更新任务详情失败 {task.task_id}: {e}")
                                self.logger.debug(f"更新任务详情失败详细信息 {task.task_id}: {traceback.format_exc()}")
                                
                except Exception as e:
                    import traceback
                    self.logger.warning(f"处理单个任务时出错: {e}")
                    self.logger.debug(f"处理单个任务时出错详细信息: {traceback.format_exc()}")
                    continue
            
            # 更新任务计数
            try:
                self._update_task_counts()
            except Exception as e:
                import traceback
                self.logger.warning(f"更新任务计数失败: {e}")
                self.logger.debug(f"更新任务计数失败详细信息: {traceback.format_exc()}")
            
        except Exception as e:
            import traceback
            self.logger.error(f"更新运行中任务失败: {e}")
            self.logger.debug(f"更新运行中任务失败详细信息: {traceback.format_exc()}")
    
    def _on_task_added(self, task: Task):
        """处理任务添加"""
        self.task_model.add_task(task)
        self._update_task_counts()
        self.status_label.setText(f"新任务 '{task.name}' 已添加")
    
    def _on_task_updated(self, task: Task):
        """处理任务更新"""
        self.task_model.update_task(task)
        
        # 如果当前选中的是这个任务，更新详情
        selected_task = self._get_selected_task()
        if selected_task and selected_task.task_id == task.task_id:
            self.task_detail.set_task(task)
        
        self._update_task_counts()
    
    def _on_task_removed(self, task_id: str):
        """处理任务移除"""
        self.task_model.remove_task(task_id)
        self._update_task_counts()
        
        # 如果移除的是当前选中的任务，清空详情
        selected_task = self._get_selected_task()
        if not selected_task:
            self.task_detail.clear()
    
    # 公共接口
    def get_task_manager(self) -> CoreTaskManager:
        """获取任务管理器"""
        return self.task_manager
    
    def refresh(self):
        """刷新界面"""
        self._refresh_tasks()
    
    def add_task(self, task: Task):
        """添加任务"""
        return self.task_manager.add_task(task)
    
    def _on_thread_count_changed(self, value):
        """线程数量变化"""
        try:
            if hasattr(self.task_manager, 'set_max_workers'):
                self.task_manager.set_max_workers(value)
                self.logger.info(f"线程数量已更新为: {value}")
        except Exception as e:
            self.logger.error(f"更新线程数量失败: {e}")
    
    def _on_start_all_tasks(self):
        """开始所有等待中的任务"""
        try:
            # 直接调用核心任务管理器的批量启动方法
            count = self.task_manager.start_all_pending_tasks()
            if count > 0:
                self.logger.info(f"已启动 {count} 个任务")
                self._update_buttons()
            else:
                self.logger.info("没有可启动的任务")
        except Exception as e:
            self.logger.error(f"批量启动任务失败: {e}")
    
    def _on_pause_all_tasks(self):
        """暂停所有运行中的任务"""
        try:
            # 直接调用核心任务管理器的批量暂停方法
            count = self.task_manager.pause_all_running_tasks()
            if count > 0:
                self.logger.info(f"已暂停 {count} 个任务")
                self._update_buttons()
            else:
                self.logger.info("没有可暂停的任务")
        except Exception as e:
            self.logger.error(f"批量暂停任务失败: {e}")
    
    def _on_start_selected_tasks(self):
        """开始选中的任务"""
        try:
            selected_tasks = self._get_selected_tasks()
            if not selected_tasks:
                QMessageBox.warning(self, "警告", "请先选择要启动的任务")
                return
            
            # 获取选中任务的ID列表
            task_ids = [task.task_id for task in selected_tasks 
                       if task.status in [TaskStatus.PENDING, TaskStatus.PAUSED]]
            
            if task_ids:
                count = self.task_manager.start_selected_tasks(task_ids)
                if count > 0:
                    self.logger.info(f"已启动 {count} 个选中任务")
                    self._update_buttons()
                else:
                    self.logger.info("没有可启动的选中任务")
            else:
                self.logger.info("没有可启动的选中任务")
        except Exception as e:
            self.logger.error(f"批量启动选中任务失败: {e}")
    
    def _on_pause_selected_tasks(self):
        """暂停选中的任务"""
        try:
            selected_tasks = self._get_selected_tasks()
            if not selected_tasks:
                QMessageBox.warning(self, "警告", "请先选择要暂停的任务")
                return
            
            # 获取选中任务的ID列表
            task_ids = [task.task_id for task in selected_tasks 
                       if task.status == TaskStatus.RUNNING]
            
            if task_ids:
                count = self.task_manager.pause_selected_tasks(task_ids)
                if count > 0:
                    self.logger.info(f"已暂停 {count} 个选中任务")
                    self._update_buttons()
                else:
                    self.logger.info("没有可暂停的选中任务")
            else:
                self.logger.info("没有可暂停的选中任务")
        except Exception as e:
            self.logger.error(f"批量暂停选中任务失败: {e}")
    
    def _on_batch_progress_updated(self, current, total):
        """批量操作进度更新"""
        try:
            progress = (current / total) * 100 if total > 0 else 0
            self.status_label.setText(f"批量操作进度: {current}/{total} ({progress:.1f}%)")
        except Exception as e:
            self.logger.error(f"更新批量进度失败: {e}")
    
    def _get_selected_tasks(self):
        """获取选中的任务"""
        try:
            selected_indexes = self.task_table.selectionModel().selectedRows()
            selected_tasks = []
            
            for index in selected_indexes:
                task = self.task_model.get_task(index)
                if task:
                    selected_tasks.append(task)
            
            return selected_tasks
        except Exception as e:
            self.logger.error(f"获取选中任务失败: {e}")
            return []
    
    def get_running_tasks(self) -> List[Task]:
        """获取运行中的任务"""
        return [task for task in self.task_model.tasks if task.status == TaskStatus.RUNNING]
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        return self.task_manager.get_task(task_id)
    
    def clear_completed_tasks(self):
        """清理已完成的任务"""
        try:
            completed_tasks = [
                task for task in self.task_model.tasks 
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            ]
            
            if not completed_tasks:
                QMessageBox.information(self, "信息", "没有已完成的任务需要清理")
                return
            
            reply = QMessageBox.question(
                self, "确认清理", 
                f"确定要清理 {len(completed_tasks)} 个已完成的任务吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                for task in completed_tasks:
                    self.task_manager.remove_task(task.task_id)
                
                self.status_label.setText(f"已清理 {len(completed_tasks)} 个任务")
                
        except Exception as e:
            self.logger.error(f"清理任务失败: {e}")
            QMessageBox.critical(self, "错误", f"清理任务失败: {e}")

class CreateTaskDialog(QDialog):
    """创建任务对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = Logger().get_logger("CreateTaskDialog")
        
        self.setWindowTitle("创建新任务")
        self.setModal(True)
        self.setFixedSize(500, 400)
        self._init_ui()
        
        self.logger.info("创建任务对话框初始化完成")
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入任务名称")
        basic_layout.addRow("任务名称:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["爬虫", "视频处理", "AI算法", "其他"])
        basic_layout.addRow("任务类型:", self.type_combo)
        
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 10)
        self.priority_spin.setValue(5)
        basic_layout.addRow("优先级:", self.priority_spin)
        
        layout.addWidget(basic_group)
        
        # 任务参数
        params_group = QGroupBox("任务参数")
        params_layout = QVBoxLayout(params_group)
        
        self.params_text = QTextEdit()
        self.params_text.setPlaceholderText("输入JSON格式的任务参数")
        params_layout.addWidget(self.params_text)
        
        layout.addWidget(params_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.create_btn = QPushButton("创建")
        self.create_btn.clicked.connect(self._create_task)
        button_layout.addWidget(self.create_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _create_task(self):
        """创建任务"""
        try:
            name = self.name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "警告", "请输入任务名称")
                return
            
            task_type = self.type_combo.currentText()
            priority = self.priority_spin.value()
            
            # 解析参数
            params_text = self.params_text.toPlainText().strip()
            if params_text:
                try:
                    params = json.loads(params_text)
                except json.JSONDecodeError as e:
                    QMessageBox.critical(self, "错误", f"参数格式错误: {e}")
                    return
            else:
                params = {}
            
            # 创建任务
            task = Task(
                name=name,
                task_type=task_type,
                params=params,
                priority=priority
            )
            
            self.task = task
            self.accept()
            
        except Exception as e:
            self.logger.error(f"创建任务失败: {e}")
            QMessageBox.critical(self, "错误", f"创建任务失败: {e}")
    
    def get_task(self) -> Optional[Task]:
        """获取创建的任务"""
        return getattr(self, 'task', None)

# 便捷函数
def show_task_manager(parent=None) -> TaskManagerWidget:
    """显示任务管理器"""
    widget = TaskManagerWidget(parent)
    return widget

def show_create_task_dialog(parent=None) -> Optional[Task]:
    """显示创建任务对话框"""
    dialog = CreateTaskDialog(parent)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_task()
    return None