import os
import json
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, 
                             QCheckBox, QMessageBox, QProgressBar, QTextEdit,
                             QSplitter, QGroupBox, QGridLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont


class RefilterDialog(QDialog):
    """重新过滤对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.result_files = []
        self.selected_files = []
        self._init_ui()
        self._load_result_files()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("重新过滤 - 选择本地模型结果文件")
        self.setModal(True)
        self.resize(800, 600)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 说明文本
        info_label = QLabel("选择需要重新应用动作描述过滤的结果文件：")
        info_label.setFont(QFont("Microsoft YaHei", 10))
        main_layout.addWidget(info_label)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧：文件列表
        left_widget = QGroupBox("结果文件列表")
        left_layout = QVBoxLayout(left_widget)
        
        # 全选/取消全选按钮
        select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        select_layout.addWidget(self.select_all_btn)
        select_layout.addWidget(self.deselect_all_btn)
        select_layout.addStretch()
        left_layout.addLayout(select_layout)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.itemChanged.connect(self._on_item_changed)
        left_layout.addWidget(self.file_list)
        
        # 统计信息
        self.stats_label = QLabel("总计: 0 个文件，已选择: 0 个")
        left_layout.addWidget(self.stats_label)
        
        splitter.addWidget(left_widget)
        
        # 右侧：文件详情
        right_widget = QGroupBox("文件详情")
        right_layout = QVBoxLayout(right_widget)
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlainText("请选择一个文件查看详情")
        right_layout.addWidget(self.detail_text)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 400])
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("开始重新过滤（仅本地模型）")
        self.ok_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #27ae60;"
            "    color: white;"
            "    border: none;"
            "    padding: 10px 20px;"
            "    font-size: 12px;"
            "    font-weight: bold;"
            "    border-radius: 5px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #2ecc71;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #bdc3c7;"
            "}"
        )
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #95a5a6;"
            "    color: white;"
            "    border: none;"
            "    padding: 10px 20px;"
            "    font-size: 12px;"
            "    font-weight: bold;"
            "    border-radius: 5px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #7f8c8d;"
            "}"
        )
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # 连接信号
        self.file_list.currentItemChanged.connect(self._on_selection_changed)
    
    def _load_result_files(self):
        """加载结果文件"""
        try:
            # 获取结果目录
            if hasattr(self.parent_widget, 'config_manager'):
                config = self.parent_widget.config_manager.get_config()
                results_dir = config.get('paths', {}).get('results_dir', 'results')
            else:
                results_dir = 'results'
            
            # 确保路径是绝对路径
            if not os.path.isabs(results_dir):
                results_dir = os.path.join(os.getcwd(), results_dir)
            
            video_results_dir = os.path.join(results_dir, 'video_description')
            
            if not os.path.exists(video_results_dir):
                self._show_no_files_message()
                return
            
            # 扫描结果文件
            self.result_files = []
            for root, dirs, files in os.walk(video_results_dir):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        if self._is_refilter_candidate(file_path):
                            self.result_files.append(file_path)
            
            if not self.result_files:
                self._show_no_files_message()
                return
            
            # 填充列表
            self._populate_file_list()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载结果文件失败: {str(e)}")
    
    def _is_refilter_candidate(self, file_path):
        """判断文件是否适合重新过滤"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 首先检查是否为本地模型的结果
            model_type = data.get('model_type', '')
            if model_type != 'local':
                return False  # 仅处理本地模型的结果
            
            # 检查是否有描述内容
            if not data.get('description'):
                return False
            
            # 检查是否使用了原始描述（没有应用过滤或过滤失败）
            # 1. 没有 filter_applied 字段
            # 2. filter_applied 为 False
            # 3. 有 original_description 字段但描述与原始描述相同
            filter_applied = data.get('filter_applied', False)
            if not filter_applied:
                return True
            
            # 检查是否有原始描述且当前描述等于原始描述（说明过滤失败）
            original_desc = data.get('original_description')
            current_desc = data.get('description')
            if original_desc and current_desc == original_desc:
                return True
            
            return False
            
        except Exception:
            return False
    
    def _populate_file_list(self):
        """填充文件列表"""
        self.file_list.clear()
        
        for file_path in self.result_files:
            try:
                # 读取文件信息
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 获取视频名称
                video_path = data.get('video_path', '')
                video_name = os.path.basename(video_path) if video_path else os.path.basename(file_path)
                
                # 创建列表项
                item = QListWidgetItem()
                item.setText(video_name)
                item.setData(Qt.UserRole, file_path)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                
                self.file_list.addItem(item)
                
            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {e}")
        
        self._update_stats()
    
    def _show_no_files_message(self):
        """显示无文件消息"""
        self.file_list.clear()
        item = QListWidgetItem("未找到可重新过滤的本地模型结果文件")
        item.setFlags(Qt.NoItemFlags)
        self.file_list.addItem(item)
        self.stats_label.setText("未找到适合重新过滤的本地模型文件")
    
    def _select_all(self):
        """全选"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Checked)
    
    def _deselect_all(self):
        """取消全选"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(Qt.Unchecked)
    
    def _on_item_changed(self, item):
        """列表项状态改变"""
        self._update_stats()
        self._update_ok_button()
    
    def _on_selection_changed(self, current, previous):
        """选择改变时显示文件详情"""
        if current and current.data(Qt.UserRole):
            file_path = current.data(Qt.UserRole)
            self._show_file_details(file_path)
    
    def _show_file_details(self, file_path):
        """显示文件详情"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            details = []
            details.append(f"文件路径: {file_path}")
            details.append(f"视频路径: {data.get('video_path', '未知')}")
            details.append(f"处理状态: {'成功' if data.get('success') else '失败'}")
            details.append(f"处理时间: {data.get('timestamp', '未知')}")
            details.append(f"过滤状态: {'已应用' if data.get('filter_applied') else '未应用'}")
            
            if data.get('original_description'):
                details.append(f"\n原始描述:\n{data['original_description']}")
            
            if data.get('description'):
                details.append(f"\n当前描述:\n{data['description']}")
            
            if data.get('error_message'):
                details.append(f"\n错误信息: {data['error_message']}")
            
            self.detail_text.setPlainText('\n'.join(details))
            
        except Exception as e:
            self.detail_text.setPlainText(f"读取文件详情失败: {str(e)}")
    
    def _update_stats(self):
        """更新统计信息"""
        total = len(self.result_files)
        selected = 0
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable and item.checkState() == Qt.Checked:
                selected += 1
        
        self.stats_label.setText(f"总计: {total} 个文件，已选择: {selected} 个")
    
    def _update_ok_button(self):
        """更新确定按钮状态"""
        selected_count = 0
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable and item.checkState() == Qt.Checked:
                selected_count += 1
        
        self.ok_btn.setEnabled(selected_count > 0)
    
    def get_selected_files(self):
        """获取选中的文件列表"""
        selected_files = []
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if (item.flags() & Qt.ItemIsUserCheckable and 
                item.checkState() == Qt.Checked and 
                item.data(Qt.UserRole)):
                selected_files.append(item.data(Qt.UserRole))
        
        return selected_files