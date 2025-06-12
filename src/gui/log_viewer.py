# -*- coding: utf-8 -*-
"""
日志查看器组件
提供日志查看、过滤、搜索和导出功能的用户界面
"""

import os
import re
import json
from datetime import datetime, timedelta
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
    QMenu, QApplication, QStatusBar, QTableView
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QDateTime,
    QFileSystemWatcher, QSortFilterProxyModel, QAbstractTableModel,
    QModelIndex, QVariant
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QIntValidator, QDoubleValidator,
    QTextCursor, QTextCharFormat, QColor, QSyntaxHighlighter,
    QTextDocument, QKeySequence
)

from ..utils.logger import Logger

class LogEntry:
    """日志条目"""
    
    def __init__(self, timestamp: datetime, level: str, logger_name: str, message: str, 
                 filename: str = "", line_number: int = 0, function_name: str = ""):
        self.timestamp = timestamp
        self.level = level
        self.logger_name = logger_name
        self.message = message
        self.filename = filename
        self.line_number = line_number
        self.function_name = function_name
    
    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.level} - {self.logger_name}: {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "logger_name": self.logger_name,
            "message": self.message,
            "filename": self.filename,
            "line_number": self.line_number,
            "function_name": self.function_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        """从字典创建"""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            level=data["level"],
            logger_name=data["logger_name"],
            message=data["message"],
            filename=data.get("filename", ""),
            line_number=data.get("line_number", 0),
            function_name=data.get("function_name", "")
        )

class LogTableModel(QAbstractTableModel):
    """日志表格模型"""
    
    def __init__(self):
        super().__init__()
        self.log_entries: List[LogEntry] = []
        self.headers = ["时间", "级别", "记录器", "消息", "文件", "行号", "函数"]
        
        # 级别颜色映射
        self.level_colors = {
            "DEBUG": QColor(128, 128, 128),
            "INFO": QColor(0, 0, 0),
            "WARNING": QColor(255, 165, 0),
            "ERROR": QColor(255, 0, 0),
            "CRITICAL": QColor(139, 0, 0)
        }
    
    def rowCount(self, parent=QModelIndex()):
        return len(self.log_entries)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.log_entries):
            return QVariant()
        
        entry = self.log_entries[index.row()]
        column = index.column()
        
        if role == Qt.DisplayRole:
            if column == 0:  # 时间
                return entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif column == 1:  # 级别
                return entry.level
            elif column == 2:  # 记录器
                return entry.logger_name
            elif column == 3:  # 消息
                return entry.message
            elif column == 4:  # 文件
                return entry.filename
            elif column == 5:  # 行号
                return str(entry.line_number) if entry.line_number > 0 else ""
            elif column == 6:  # 函数
                return entry.function_name
        
        elif role == Qt.ForegroundRole:
            if column == 1:  # 级别列使用颜色
                return self.level_colors.get(entry.level, QColor(0, 0, 0))
        
        elif role == Qt.ToolTipRole:
            if column == 3:  # 消息列显示完整消息
                return entry.message
        
        return QVariant()
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return QVariant()
    
    def add_entry(self, entry: LogEntry):
        """添加日志条目"""
        self.beginInsertRows(QModelIndex(), len(self.log_entries), len(self.log_entries))
        self.log_entries.append(entry)
        self.endInsertRows()
    
    def add_entries(self, entries: List[LogEntry]):
        """批量添加日志条目"""
        if not entries:
            return
        
        self.beginInsertRows(QModelIndex(), len(self.log_entries), len(self.log_entries) + len(entries) - 1)
        self.log_entries.extend(entries)
        self.endInsertRows()
    
    def clear(self):
        """清空日志"""
        self.beginResetModel()
        self.log_entries.clear()
        self.endResetModel()
    
    def get_entry(self, row: int) -> Optional[LogEntry]:
        """获取指定行的日志条目"""
        if 0 <= row < len(self.log_entries):
            return self.log_entries[row]
        return None

class LogFilterProxyModel(QSortFilterProxyModel):
    """日志过滤代理模型"""
    
    def __init__(self):
        super().__init__()
        self.level_filter = set()
        self.logger_filter = set()
        self.start_time = None
        self.end_time = None
        self.message_filter = ""
        self.use_regex = False
    
    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if not model:
            return True
        
        entry = model.get_entry(source_row)
        if not entry:
            return True
        
        # 级别过滤
        if self.level_filter and entry.level not in self.level_filter:
            return False
        
        # 记录器过滤
        if self.logger_filter and entry.logger_name not in self.logger_filter:
            return False
        
        # 时间过滤
        if self.start_time and entry.timestamp < self.start_time:
            return False
        if self.end_time and entry.timestamp > self.end_time:
            return False
        
        # 消息过滤
        if self.message_filter:
            if self.use_regex:
                try:
                    if not re.search(self.message_filter, entry.message, re.IGNORECASE):
                        return False
                except re.error:
                    # 正则表达式错误，使用普通文本搜索
                    if self.message_filter.lower() not in entry.message.lower():
                        return False
            else:
                if self.message_filter.lower() not in entry.message.lower():
                    return False
        
        return True
    
    def set_level_filter(self, levels: set):
        """设置级别过滤"""
        self.level_filter = levels
        self.invalidateFilter()
    
    def set_logger_filter(self, loggers: set):
        """设置记录器过滤"""
        self.logger_filter = loggers
        self.invalidateFilter()
    
    def set_time_filter(self, start_time: Optional[datetime], end_time: Optional[datetime]):
        """设置时间过滤"""
        self.start_time = start_time
        self.end_time = end_time
        self.invalidateFilter()
    
    def set_message_filter(self, message: str, use_regex: bool = False):
        """设置消息过滤"""
        self.message_filter = message
        self.use_regex = use_regex
        self.invalidateFilter()

class LogSyntaxHighlighter(QSyntaxHighlighter):
    """日志语法高亮器"""
    
    def __init__(self, document: QTextDocument):
        super().__init__(document)
        
        # 定义高亮规则
        self.highlighting_rules = []
        
        # 时间戳格式
        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QColor(0, 0, 255))
        self.highlighting_rules.append((r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', timestamp_format))
        
        # 日志级别
        level_formats = {
            'DEBUG': QColor(128, 128, 128),
            'INFO': QColor(0, 128, 0),
            'WARNING': QColor(255, 165, 0),
            'ERROR': QColor(255, 0, 0),
            'CRITICAL': QColor(139, 0, 0)
        }
        
        for level, color in level_formats.items():
            level_format = QTextCharFormat()
            level_format.setForeground(color)
            level_format.setFontWeight(QFont.Bold)
            self.highlighting_rules.append((f'\b{level}\b', level_format))
        
        # 记录器名称
        logger_format = QTextCharFormat()
        logger_format.setForeground(QColor(128, 0, 128))
        self.highlighting_rules.append((r'\w+\.\w+', logger_format))
        
        # 文件路径
        file_format = QTextCharFormat()
        file_format.setForeground(QColor(0, 128, 128))
        self.highlighting_rules.append((r'[\w/\\]+\.py', file_format))
        
        # 行号
        line_format = QTextCharFormat()
        line_format.setForeground(QColor(255, 0, 255))
        self.highlighting_rules.append((r':\d+', line_format))
    
    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            expression = re.compile(pattern)
            for match in expression.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format)

class LogViewer(QWidget):
    """日志查看器组件"""
    
    # 信号定义
    log_entry_selected = pyqtSignal(LogEntry)  # 日志条目被选中
    
    def __init__(self, log_file_path: Optional[str] = None):
        super().__init__()
        
        self.logger = Logger().get_logger("LogViewer")
        self.log_file_path = log_file_path
        
        # 数据模型
        self.log_model = LogTableModel()
        self.filter_model = LogFilterProxyModel()
        self.filter_model.setSourceModel(self.log_model)
        
        # 文件监控
        self.file_watcher = QFileSystemWatcher()
        if self.log_file_path and os.path.exists(self.log_file_path):
            self.file_watcher.addPath(self.log_file_path)
        
        # 自动刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._auto_refresh)
        
        # 状态
        self.auto_scroll = True
        self.auto_refresh_enabled = True
        self.max_entries = 10000
        
        # 初始化界面
        self._init_ui()
        self._connect_signals()
        
        # 加载日志
        if self.log_file_path:
            self._load_log_file()
        
        self.logger.info("日志查看器组件初始化完成")
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建工具栏
        self._create_toolbar(layout)
        
        # 创建主要内容区域
        self._create_main_content(layout)
        
        # 创建状态栏
        self._create_status_bar(layout)
    
    def _create_toolbar(self, layout):
        """创建工具栏"""
        toolbar_layout = QHBoxLayout()
        
        # 文件操作
        self.open_file_btn = QPushButton("打开文件")
        self.open_file_btn.clicked.connect(self._open_log_file)
        toolbar_layout.addWidget(self.open_file_btn)
        
        self.reload_btn = QPushButton("重新加载")
        self.reload_btn.clicked.connect(self._reload_log_file)
        toolbar_layout.addWidget(self.reload_btn)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear_logs)
        toolbar_layout.addWidget(self.clear_btn)
        
        toolbar_layout.addWidget(QFrame())  # 分隔符
        
        # 过滤控件
        toolbar_layout.addWidget(QLabel("级别:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["全部", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.currentTextChanged.connect(self._apply_filters)
        toolbar_layout.addWidget(self.level_combo)
        
        toolbar_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索消息内容...")
        self.search_input.textChanged.connect(self._apply_filters)
        toolbar_layout.addWidget(self.search_input)
        
        self.regex_check = QCheckBox("正则")
        self.regex_check.toggled.connect(self._apply_filters)
        toolbar_layout.addWidget(self.regex_check)
        
        toolbar_layout.addWidget(QFrame())  # 分隔符
        
        # 视图控件
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(self._toggle_auto_scroll)
        toolbar_layout.addWidget(self.auto_scroll_check)
        
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self._toggle_auto_refresh)
        toolbar_layout.addWidget(self.auto_refresh_check)
        
        toolbar_layout.addStretch()
        
        # 导出按钮
        self.export_btn = QPushButton("导出")
        self.export_btn.clicked.connect(self._export_logs)
        toolbar_layout.addWidget(self.export_btn)
        
        layout.addLayout(toolbar_layout)
    
    def _create_main_content(self, layout):
        """创建主要内容区域"""
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 日志表格
        self.log_table = QTableView()
        self.log_table.setModel(self.filter_model)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSelectionBehavior(QTableView.SelectRows)
        self.log_table.setSortingEnabled(True)
        
        # 设置列宽
        header = self.log_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 150)  # 时间
        header.resizeSection(1, 80)   # 级别
        header.resizeSection(2, 120)  # 记录器
        header.resizeSection(4, 200)  # 文件
        header.resizeSection(5, 60)   # 行号
        header.resizeSection(6, 100)  # 函数
        
        splitter.addWidget(self.log_table)
        
        # 详细信息面板
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(5, 5, 5, 5)
        
        detail_layout.addWidget(QLabel("详细信息:"))
        
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(200)
        
        # 应用语法高亮
        self.highlighter = LogSyntaxHighlighter(self.detail_text.document())
        
        detail_layout.addWidget(self.detail_text)
        
        splitter.addWidget(detail_widget)
        
        # 设置分割器比例
        splitter.setSizes([400, 200])
        
        layout.addWidget(splitter)
    
    def _create_status_bar(self, layout):
        """创建状态栏"""
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.entry_count_label = QLabel("条目: 0")
        status_layout.addWidget(self.entry_count_label)
        
        self.filtered_count_label = QLabel("显示: 0")
        status_layout.addWidget(self.filtered_count_label)
        
        layout.addLayout(status_layout)
    
    def _connect_signals(self):
        """连接信号"""
        # 表格选择变化
        self.log_table.selectionModel().currentRowChanged.connect(self._on_selection_changed)
        
        # 文件监控
        self.file_watcher.fileChanged.connect(self._on_file_changed)
        
        # 模型变化
        self.log_model.rowsInserted.connect(self._on_rows_inserted)
        self.filter_model.rowsInserted.connect(self._update_counts)
        self.filter_model.rowsRemoved.connect(self._update_counts)
        self.filter_model.modelReset.connect(self._update_counts)
    
    def _open_log_file(self):
        """打开日志文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "打开日志文件", "", "日志文件 (*.log *.txt);;所有文件 (*)"
            )
            
            if file_path:
                self.set_log_file(file_path)
                
        except Exception as e:
            self.logger.error(f"打开日志文件失败: {e}")
            QMessageBox.critical(self, "错误", f"打开日志文件失败: {e}")
    
    def _reload_log_file(self):
        """重新加载日志文件"""
        if self.log_file_path:
            self._load_log_file()
    
    def _clear_logs(self):
        """清空日志"""
        self.log_model.clear()
        self.detail_text.clear()
        self._update_status("日志已清空")
    
    def _load_log_file(self):
        """加载日志文件"""
        if not self.log_file_path or not os.path.exists(self.log_file_path):
            return
        
        try:
            self._update_status("正在加载日志文件...")
            
            entries = []
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    entry = self._parse_log_line(line, line_num)
                    if entry:
                        entries.append(entry)
                    
                    # 限制条目数量
                    if len(entries) >= self.max_entries:
                        break
            
            # 清空现有日志并添加新日志
            self.log_model.clear()
            self.log_model.add_entries(entries)
            
            self._update_status(f"已加载 {len(entries)} 条日志")
            
        except Exception as e:
            self.logger.error(f"加载日志文件失败: {e}")
            self._update_status(f"加载失败: {e}")
    
    def _parse_log_line(self, line: str, line_num: int) -> Optional[LogEntry]:
        """解析日志行"""
        try:
            # 尝试解析标准格式: [2024-01-01 12:00:00] LEVEL - logger_name: message
            pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(\w+)\s+-\s+([^:]+):\s*(.*)'
            match = re.match(pattern, line)
            
            if match:
                timestamp_str, level, logger_name, message = match.groups()
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    logger_name=logger_name.strip(),
                    message=message.strip()
                )
            
            # 如果无法解析，创建一个简单的条目
            return LogEntry(
                timestamp=datetime.now(),
                level="INFO",
                logger_name="unknown",
                message=line
            )
            
        except Exception as e:
            self.logger.debug(f"解析日志行失败 (行 {line_num}): {e}")
            return None
    
    def _apply_filters(self):
        """应用过滤器"""
        try:
            # 级别过滤
            level_text = self.level_combo.currentText()
            if level_text == "全部":
                self.filter_model.set_level_filter(set())
            else:
                self.filter_model.set_level_filter({level_text})
            
            # 消息过滤
            search_text = self.search_input.text()
            use_regex = self.regex_check.isChecked()
            self.filter_model.set_message_filter(search_text, use_regex)
            
        except Exception as e:
            self.logger.error(f"应用过滤器失败: {e}")
    
    def _toggle_auto_scroll(self, enabled: bool):
        """切换自动滚动"""
        self.auto_scroll = enabled
    
    def _toggle_auto_refresh(self, enabled: bool):
        """切换自动刷新"""
        self.auto_refresh_enabled = enabled
        if enabled:
            self.refresh_timer.start(1000)  # 每秒刷新
        else:
            self.refresh_timer.stop()
    
    def _auto_refresh(self):
        """自动刷新"""
        if self.log_file_path and os.path.exists(self.log_file_path):
            # TODO: 实现增量加载
            pass
    
    def _export_logs(self):
        """导出日志"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出日志", "logs.txt", "文本文件 (*.txt);;JSON文件 (*.json);;所有文件 (*)"
            )
            
            if file_path:
                self._export_to_file(file_path)
                
        except Exception as e:
            self.logger.error(f"导出日志失败: {e}")
            QMessageBox.critical(self, "错误", f"导出日志失败: {e}")
    
    def _export_to_file(self, file_path: str):
        """导出到文件"""
        try:
            entries = []
            for row in range(self.filter_model.rowCount()):
                source_index = self.filter_model.mapToSource(self.filter_model.index(row, 0))
                entry = self.log_model.get_entry(source_index.row())
                if entry:
                    entries.append(entry)
            
            if file_path.endswith('.json'):
                # 导出为JSON
                data = [entry.to_dict() for entry in entries]
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                # 导出为文本
                with open(file_path, 'w', encoding='utf-8') as f:
                    for entry in entries:
                        f.write(str(entry) + '\n')
            
            self._update_status(f"已导出 {len(entries)} 条日志到 {file_path}")
            
        except Exception as e:
            self.logger.error(f"导出到文件失败: {e}")
            raise
    
    def _on_selection_changed(self, current, previous):
        """选择变化处理"""
        try:
            if current.isValid():
                source_index = self.filter_model.mapToSource(current)
                entry = self.log_model.get_entry(source_index.row())
                
                if entry:
                    # 显示详细信息
                    detail_text = f"时间: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    detail_text += f"级别: {entry.level}\n"
                    detail_text += f"记录器: {entry.logger_name}\n"
                    if entry.filename:
                        detail_text += f"文件: {entry.filename}"
                        if entry.line_number > 0:
                            detail_text += f":{entry.line_number}"
                        detail_text += "\n"
                    if entry.function_name:
                        detail_text += f"函数: {entry.function_name}\n"
                    detail_text += f"\n消息:\n{entry.message}"
                    
                    self.detail_text.setPlainText(detail_text)
                    
                    # 发射信号
                    self.log_entry_selected.emit(entry)
            
        except Exception as e:
            self.logger.error(f"处理选择变化失败: {e}")
    
    def _on_file_changed(self, path: str):
        """文件变化处理"""
        if self.auto_refresh_enabled and path == self.log_file_path:
            # TODO: 实现增量加载
            pass
    
    def _on_rows_inserted(self, parent, first, last):
        """行插入处理"""
        if self.auto_scroll:
            # 滚动到底部
            self.log_table.scrollToBottom()
    
    def _update_counts(self):
        """更新计数显示"""
        total_count = self.log_model.rowCount()
        filtered_count = self.filter_model.rowCount()
        
        self.entry_count_label.setText(f"条目: {total_count}")
        self.filtered_count_label.setText(f"显示: {filtered_count}")
    
    def _update_status(self, message: str):
        """更新状态"""
        self.status_label.setText(message)
        QApplication.processEvents()
    
    # 公共接口
    def set_log_file(self, file_path: str):
        """设置日志文件"""
        try:
            # 移除旧的文件监控
            if self.log_file_path and self.log_file_path in self.file_watcher.files():
                self.file_watcher.removePath(self.log_file_path)
            
            self.log_file_path = file_path
            
            # 添加新的文件监控
            if os.path.exists(file_path):
                self.file_watcher.addPath(file_path)
            
            # 加载日志
            self._load_log_file()
            
        except Exception as e:
            self.logger.error(f"设置日志文件失败: {e}")
    
    def add_log_entry(self, entry: LogEntry):
        """添加日志条目"""
        self.log_model.add_entry(entry)
    
    def add_log_entries(self, entries: List[LogEntry]):
        """批量添加日志条目"""
        self.log_model.add_entries(entries)
    
    def clear_logs(self):
        """清空日志"""
        self._clear_logs()
    
    def set_max_entries(self, max_entries: int):
        """设置最大条目数"""
        self.max_entries = max_entries
    
    def get_selected_entry(self) -> Optional[LogEntry]:
        """获取选中的日志条目"""
        current_index = self.log_table.selectionModel().currentIndex()
        if current_index.isValid():
            source_index = self.filter_model.mapToSource(current_index)
            return self.log_model.get_entry(source_index.row())
        return None
    
    def cleanup(self):
        """清理资源"""
        try:
            self.refresh_timer.stop()
            self.file_watcher.removePaths(self.file_watcher.files())
            self.logger.info("日志查看器组件资源清理完成")
        except Exception as e:
            self.logger.error(f"日志查看器组件资源清理失败: {e}")