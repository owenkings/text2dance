#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试停止功能的脚本
"""

import sys
import os
import time
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from src.gui.video_description_widget import VideoDescriptionThread
    print("✅ VideoDescriptionThread 导入成功")
except ImportError as e:
    print(f"❌ VideoDescriptionThread 导入失败: {e}")
    sys.exit(1)

class TestStopWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("停止功能测试")
        self.setGeometry(100, 100, 600, 400)
        
        # 创建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建按钮
        self.start_btn = QPushButton("开始测试处理")
        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.setEnabled(False)
        
        # 创建日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        # 添加到布局
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.log_text)
        
        # 连接信号
        self.start_btn.clicked.connect(self.start_test)
        self.stop_btn.clicked.connect(self.stop_test)
        
        self.processing_thread = None
        
    def log_message(self, message):
        """添加日志消息"""
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        
    def start_test(self):
        """开始测试"""
        self.log_message("开始停止功能测试...")
        
        # 创建测试视频列表（使用不存在的文件进行测试）
        test_videos = [
            "test_video_1.mp4",
            "test_video_2.mp4", 
            "test_video_3.mp4"
        ]
        
        # 创建处理线程
        self.processing_thread = VideoDescriptionThread(
            videos=test_videos,
            description_requirement="测试描述",
            model_path="test_model",
            algorithm_type="本地模型"
        )
        
        # 连接信号
        self.processing_thread.log_updated.connect(self.log_message)
        self.processing_thread.status_updated.connect(self.log_message)
        self.processing_thread.all_completed.connect(self.on_completed)
        
        # 启动线程
        self.processing_thread.start()
        
        # 更新按钮状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.log_message("处理线程已启动")
        
    def stop_test(self):
        """停止测试"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.log_message("正在停止处理线程...")
            
            # 记录停止开始时间
            stop_start_time = time.time()
            
            # 停止线程
            self.processing_thread.stop()
            
            # 计算停止耗时
            stop_time = time.time() - stop_start_time
            self.log_message(f"停止操作完成，耗时: {stop_time:.2f}秒")
            
            # 更新按钮状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        else:
            self.log_message("没有正在运行的处理线程")
            
    def on_completed(self):
        """处理完成"""
        self.log_message("处理完成")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
    def closeEvent(self, event):
        """关闭事件"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.log_message("关闭窗口时停止处理线程...")
            self.processing_thread.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # 创建测试窗口
    window = TestStopWindow()
    window.show()
    
    print("停止功能测试窗口已启动")
    print("请在窗口中点击'开始测试处理'，然后点击'停止处理'来测试停止功能")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()