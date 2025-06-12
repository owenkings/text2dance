# -*- coding: utf-8 -*-
"""
进度对话框组件
提供任务进度显示、取消操作和详细信息查看功能的用户界面
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QFormLayout,
    QPlainTextEdit, QDateTimeEdit, QToolBar, QAction,
    QMenu, QApplication, QStatusBar, QDialogButtonBox
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime,
    QPropertyAnimation, QEasingCurve, QRect, QPoint
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QIntValidator, QDoubleValidator,
    QTextCursor, QTextCharFormat, QColor, QSyntaxHighlighter,
    QTextDocument, QKeySequence, QPainter, QPen, QBrush,
    QMovie
)

from ..utils.logger import Logger

class TaskProgress:
    """任务进度信息"""
    
    def __init__(self, task_id: str, name: str, total: int = 100):
        self.task_id = task_id
        self.name = name
        self.total = total
        self.current = 0
        self.status = "等待中"
        self.start_time = None
        self.end_time = None
        self.error_message = ""
        self.details = []
        self.sub_tasks = {}
        self.cancelled = False
    
    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100.0)
    
    @property
    def elapsed_time(self) -> timedelta:
        """已用时间"""
        if not self.start_time:
            return timedelta(0)
        end_time = self.end_time or datetime.now()
        return end_time - self.start_time
    
    @property
    def estimated_remaining(self) -> Optional[timedelta]:
        """预计剩余时间"""
        if not self.start_time or self.current <= 0:
            return None
        
        elapsed = self.elapsed_time.total_seconds()
        if elapsed <= 0:
            return None
        
        rate = self.current / elapsed
        if rate <= 0:
            return None
        
        remaining_items = self.total - self.current
        remaining_seconds = remaining_items / rate
        return timedelta(seconds=remaining_seconds)
    
    def start(self):
        """开始任务"""
        self.start_time = datetime.now()
        self.status = "进行中"
    
    def update(self, current: int, status: str = None, detail: str = None):
        """更新进度"""
        self.current = current
        if status:
            self.status = status
        if detail:
            self.details.append(f"[{datetime.now().strftime('%H:%M:%S')}] {detail}")
    
    def complete(self, status: str = "已完成"):
        """完成任务"""
        self.current = self.total
        self.status = status
        self.end_time = datetime.now()
    
    def fail(self, error_message: str):
        """任务失败"""
        self.status = "失败"
        self.error_message = error_message
        self.end_time = datetime.now()
    
    def cancel(self):
        """取消任务"""
        self.cancelled = True
        self.status = "已取消"
        self.end_time = datetime.now()

class ProgressDialog(QDialog):
    """进度对话框"""
    
    # 信号定义
    cancelled = pyqtSignal()  # 用户取消操作
    task_completed = pyqtSignal(str)  # 任务完成，参数为任务ID
    task_failed = pyqtSignal(str, str)  # 任务失败，参数为任务ID和错误信息
    
    def __init__(self, title: str = "进度", parent=None, 
                 cancelable: bool = True, auto_close: bool = True):
        super().__init__(parent)
        
        self.logger = Logger().get_logger("ProgressDialog")
        
        # 配置
        self.cancelable = cancelable
        self.auto_close = auto_close
        
        # 任务管理
        self.tasks: Dict[str, TaskProgress] = {}
        self.current_task_id = None
        
        # 更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(100)  # 100ms更新一次
        
        # 动画
        self.progress_animation = None
        
        # 初始化界面
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(500, 300)
        self._init_ui()
        self._connect_signals()
        
        self.logger.info("进度对话框初始化完成")
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 主要信息区域
        self._create_main_info(layout)
        
        # 进度条区域
        self._create_progress_area(layout)
        
        # 详细信息区域
        self._create_detail_area(layout)
        
        # 按钮区域
        self._create_button_area(layout)
    
    def _create_main_info(self, layout):
        """创建主要信息区域"""
        info_layout = QHBoxLayout()
        
        # 任务图标/动画
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ccc;
                border-radius: 24px;
                background-color: #f0f0f0;
            }
        """)
        info_layout.addWidget(self.icon_label)
        
        # 任务信息
        info_text_layout = QVBoxLayout()
        
        self.task_name_label = QLabel("准备中...")
        self.task_name_label.setFont(QFont("Arial", 12, QFont.Bold))
        info_text_layout.addWidget(self.task_name_label)
        
        self.task_status_label = QLabel("等待开始")
        self.task_status_label.setStyleSheet("color: #666;")
        info_text_layout.addWidget(self.task_status_label)
        
        self.task_time_label = QLabel("")
        self.task_time_label.setStyleSheet("color: #888; font-size: 10px;")
        info_text_layout.addWidget(self.task_time_label)
        
        info_text_layout.addStretch()
        
        info_layout.addLayout(info_text_layout)
        info_layout.addStretch()
        
        layout.addLayout(info_layout)
    
    def _create_progress_area(self, layout):
        """创建进度条区域"""
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout(progress_group)
        
        # 主进度条
        progress_info_layout = QHBoxLayout()
        
        self.progress_label = QLabel("0%")
        self.progress_label.setMinimumWidth(50)
        progress_info_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_info_layout.addWidget(self.progress_bar)
        
        self.progress_count_label = QLabel("0 / 0")
        self.progress_count_label.setMinimumWidth(80)
        self.progress_count_label.setAlignment(Qt.AlignRight)
        progress_info_layout.addWidget(self.progress_count_label)
        
        progress_layout.addLayout(progress_info_layout)
        
        # 时间信息
        time_layout = QHBoxLayout()
        
        self.elapsed_label = QLabel("已用时间: 00:00:00")
        time_layout.addWidget(self.elapsed_label)
        
        time_layout.addStretch()
        
        self.remaining_label = QLabel("预计剩余: --:--:--")
        time_layout.addWidget(self.remaining_label)
        
        progress_layout.addLayout(time_layout)
        
        # 速度信息
        self.speed_label = QLabel("速度: --")
        self.speed_label.setStyleSheet("color: #666; font-size: 10px;")
        progress_layout.addWidget(self.speed_label)
        
        layout.addWidget(progress_group)
    
    def _create_detail_area(self, layout):
        """创建详细信息区域"""
        detail_group = QGroupBox("详细信息")
        detail_layout = QVBoxLayout(detail_group)
        
        # 详细信息文本
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(100)
        self.detail_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                font-family: Consolas, monospace;
                font-size: 9px;
            }
        """)
        detail_layout.addWidget(self.detail_text)
        
        # 显示/隐藏详细信息按钮
        self.toggle_detail_btn = QPushButton("显示详细信息")
        self.toggle_detail_btn.setCheckable(True)
        self.toggle_detail_btn.clicked.connect(self._toggle_detail_visibility)
        detail_layout.addWidget(self.toggle_detail_btn)
        
        # 初始隐藏详细信息
        self.detail_text.hide()
        
        layout.addWidget(detail_group)
    
    def _create_button_area(self, layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        # 暂停/继续按钮
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle_pause)
        button_layout.addWidget(self.pause_btn)
        
        button_layout.addStretch()
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(self.cancelable)
        self.cancel_btn.clicked.connect(self._cancel_task)
        button_layout.addWidget(self.cancel_btn)
        
        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """连接信号"""
        pass
    
    def _update_display(self):
        """更新显示"""
        if not self.current_task_id or self.current_task_id not in self.tasks:
            return
        
        task = self.tasks[self.current_task_id]
        
        # 更新任务名称和状态
        self.task_name_label.setText(task.name)
        self.task_status_label.setText(task.status)
        
        # 更新进度
        progress = int(task.progress_percent)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{progress}%")
        self.progress_count_label.setText(f"{task.current} / {task.total}")
        
        # 更新时间信息
        elapsed = task.elapsed_time
        elapsed_str = self._format_timedelta(elapsed)
        self.elapsed_label.setText(f"已用时间: {elapsed_str}")
        
        remaining = task.estimated_remaining
        if remaining:
            remaining_str = self._format_timedelta(remaining)
            self.remaining_label.setText(f"预计剩余: {remaining_str}")
        else:
            self.remaining_label.setText("预计剩余: --:--:--")
        
        # 更新速度信息
        if task.start_time and task.current > 0:
            elapsed_seconds = task.elapsed_time.total_seconds()
            if elapsed_seconds > 0:
                speed = task.current / elapsed_seconds
                self.speed_label.setText(f"速度: {speed:.1f} 项/秒")
        
        # 更新详细信息
        if task.details:
            detail_text = "\n".join(task.details[-10:])  # 只显示最后10条
            self.detail_text.setPlainText(detail_text)
            # 滚动到底部
            cursor = self.detail_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.detail_text.setTextCursor(cursor)
        
        # 更新按钮状态
        if task.status in ["已完成", "失败", "已取消"]:
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.close_btn.setEnabled(True)
            
            # 自动关闭
            if self.auto_close and task.status == "已完成":
                QTimer.singleShot(2000, self.accept)  # 2秒后自动关闭
        
        # 更新图标
        self._update_icon(task.status)
    
    def _update_icon(self, status: str):
        """更新图标"""
        color_map = {
            "等待中": "#ccc",
            "进行中": "#4CAF50",
            "已完成": "#2196F3",
            "失败": "#F44336",
            "已取消": "#FF9800",
            "暂停": "#FFC107"
        }
        
        color = color_map.get(status, "#ccc")
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                border: 1px solid {color};
                border-radius: 24px;
                background-color: {color};
            }}
        """)
    
    def _format_timedelta(self, td: timedelta) -> str:
        """格式化时间间隔"""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _toggle_detail_visibility(self):
        """切换详细信息可见性"""
        if self.detail_text.isVisible():
            self.detail_text.hide()
            self.toggle_detail_btn.setText("显示详细信息")
            self.resize(self.width(), self.height() - 100)
        else:
            self.detail_text.show()
            self.toggle_detail_btn.setText("隐藏详细信息")
            self.resize(self.width(), self.height() + 100)
    
    def _toggle_pause(self):
        """切换暂停/继续"""
        # TODO: 实现暂停/继续功能
        if self.pause_btn.text() == "暂停":
            self.pause_btn.setText("继续")
        else:
            self.pause_btn.setText("暂停")
    
    def _cancel_task(self):
        """取消任务"""
        if self.current_task_id and self.current_task_id in self.tasks:
            task = self.tasks[self.current_task_id]
            task.cancel()
            self.cancelled.emit()
    
    # 公共接口
    def add_task(self, task_id: str, name: str, total: int = 100) -> TaskProgress:
        """添加任务"""
        task = TaskProgress(task_id, name, total)
        self.tasks[task_id] = task
        
        if not self.current_task_id:
            self.current_task_id = task_id
        
        return task
    
    def start_task(self, task_id: str):
        """开始任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.start()
            self.current_task_id = task_id
            
            # 启用相关按钮
            self.pause_btn.setEnabled(True)
            self.cancel_btn.setEnabled(self.cancelable)
            self.close_btn.setEnabled(False)
    
    def update_task(self, task_id: str, current: int, status: str = None, detail: str = None):
        """更新任务进度"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.update(current, status, detail)
    
    def complete_task(self, task_id: str, status: str = "已完成"):
        """完成任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.complete(status)
            self.task_completed.emit(task_id)
    
    def fail_task(self, task_id: str, error_message: str):
        """任务失败"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.fail(error_message)
            self.task_failed.emit(task_id, error_message)
    
    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def is_cancelled(self, task_id: str = None) -> bool:
        """检查是否已取消"""
        if task_id:
            task = self.tasks.get(task_id)
            return task.cancelled if task else False
        
        # 检查当前任务
        if self.current_task_id:
            task = self.tasks.get(self.current_task_id)
            return task.cancelled if task else False
        
        return False
    
    def set_cancelable(self, cancelable: bool):
        """设置是否可取消"""
        self.cancelable = cancelable
        self.cancel_btn.setEnabled(cancelable)
    
    def set_auto_close(self, auto_close: bool):
        """设置是否自动关闭"""
        self.auto_close = auto_close
    
    def cleanup(self):
        """清理资源"""
        try:
            self.update_timer.stop()
            if self.progress_animation:
                self.progress_animation.stop()
            self.logger.info("进度对话框资源清理完成")
        except Exception as e:
            self.logger.error(f"进度对话框资源清理失败: {e}")

class MultiTaskProgressDialog(ProgressDialog):
    """多任务进度对话框"""
    
    def __init__(self, title: str = "批量任务进度", parent=None, 
                 cancelable: bool = True, auto_close: bool = False):
        super().__init__(title, parent, cancelable, auto_close)
        
        # 任务队列
        self.task_queue = []
        self.completed_tasks = []
        self.failed_tasks = []
        
        # 重新调整界面
        self._init_multi_task_ui()
    
    def _init_multi_task_ui(self):
        """初始化多任务界面"""
        # 在进度区域添加总体进度
        progress_group = self.findChild(QGroupBox, "进度")
        if progress_group:
            layout = progress_group.layout()
            
            # 总体进度
            overall_layout = QHBoxLayout()
            
            overall_layout.addWidget(QLabel("总体进度:"))
            
            self.overall_progress_bar = QProgressBar()
            self.overall_progress_bar.setRange(0, 100)
            self.overall_progress_bar.setValue(0)
            overall_layout.addWidget(self.overall_progress_bar)
            
            self.overall_progress_label = QLabel("0 / 0")
            overall_layout.addWidget(self.overall_progress_label)
            
            layout.insertLayout(0, overall_layout)
    
    def _update_display(self):
        """更新显示"""
        super()._update_display()
        
        # 更新总体进度
        total_tasks = len(self.tasks)
        completed_tasks = len(self.completed_tasks) + len(self.failed_tasks)
        
        if total_tasks > 0:
            overall_progress = int((completed_tasks / total_tasks) * 100)
            self.overall_progress_bar.setValue(overall_progress)
            self.overall_progress_label.setText(f"{completed_tasks} / {total_tasks}")
    
    def add_task_to_queue(self, task_id: str, name: str, total: int = 100):
        """添加任务到队列"""
        task = self.add_task(task_id, name, total)
        self.task_queue.append(task_id)
        return task
    
    def start_next_task(self):
        """开始下一个任务"""
        if self.task_queue:
            next_task_id = self.task_queue.pop(0)
            self.start_task(next_task_id)
            return next_task_id
        return None
    
    def complete_current_and_start_next(self, status: str = "已完成"):
        """完成当前任务并开始下一个"""
        if self.current_task_id:
            self.complete_task(self.current_task_id, status)
            self.completed_tasks.append(self.current_task_id)
        
        next_task_id = self.start_next_task()
        return next_task_id
    
    def fail_current_and_start_next(self, error_message: str):
        """当前任务失败并开始下一个"""
        if self.current_task_id:
            self.fail_task(self.current_task_id, error_message)
            self.failed_tasks.append(self.current_task_id)
        
        next_task_id = self.start_next_task()
        return next_task_id
    
    def get_summary(self) -> Dict[str, Any]:
        """获取任务摘要"""
        return {
            "total": len(self.tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "pending": len(self.task_queue),
            "current": self.current_task_id
        }

# 便捷函数
def show_progress_dialog(title: str = "进度", parent=None, 
                        cancelable: bool = True, auto_close: bool = True) -> ProgressDialog:
    """显示进度对话框"""
    dialog = ProgressDialog(title, parent, cancelable, auto_close)
    dialog.show()
    return dialog

def show_multi_task_progress_dialog(title: str = "批量任务进度", parent=None, 
                                   cancelable: bool = True, auto_close: bool = False) -> MultiTaskProgressDialog:
    """显示多任务进度对话框"""
    dialog = MultiTaskProgressDialog(title, parent, cancelable, auto_close)
    dialog.show()
    return dialog