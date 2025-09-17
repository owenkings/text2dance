# -*- coding: utf-8 -*-
"""
姿势估计界面组件
提供姿势估计功能的用户界面
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
from collections import deque
import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem, QShortcut,
    QDialog, QAbstractItemView, QSizePolicy, QApplication,
    QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QMutex, QUrl
from PyQt5.QtGui import QFont, QPixmap, QKeySequence, QImage, QIcon, QMovie

class PoseEstimationThread(QThread):
    """姿势估计处理线程"""
    
    progress_updated = pyqtSignal(int)  # 进度百分比
    status_updated = pyqtSignal(str)  # 状态信息
    log_updated = pyqtSignal(str)  # 实时日志更新
    video_completed = pyqtSignal(str, bool, str, str, float)  # 视频路径, 是否成功, 输出路径, 错误信息, 总耗时
    all_completed = pyqtSignal()

    def __init__(self, videos, output_dir, pose_model, output_format, enable_3d):
        super().__init__()
        self.videos = videos
        self.output_dir = output_dir
        self.pose_model = pose_model
        self.output_format = output_format
        self.enable_3d = enable_3d
        self.enable_mesh = False  # 可以根据需要设置
        self.is_running = True
        self.results = []
    
    def stop(self):
        """停止处理线程"""
        self.is_running = False
        self.quit()
        self.wait()
    
    def run(self):
        try:
            total_videos = len(self.videos)
            self.status_updated.emit(f"开始处理 {total_videos} 个视频的姿势估计...")
            
            for i, video_path in enumerate(self.videos):
                if not self.is_running:
                    break
                
                self.status_updated.emit(f"正在处理: {os.path.basename(video_path)}")
                self.log_updated.emit(f"开始处理视频 {i+1}/{total_videos}: {video_path}")
                
                start_time = time.time()
                
                try:
                    # 调用姿势估计处理
                    success, output_path, error_msg = self._process_single_video(video_path)
                    
                    processing_time = time.time() - start_time
                    
                    if success:
                        self.log_updated.emit(f"[SUCCESS] 处理完成: {output_path} (耗时: {processing_time:.2f}秒)")
                        self.video_completed.emit(video_path, True, output_path, "", processing_time)
                    else:
                        self.log_updated.emit(f"[ERROR] 处理失败: {error_msg}")
                        self.video_completed.emit(video_path, False, "", error_msg, processing_time)
                    
                    # 更新进度
                    progress = int((i + 1) / total_videos * 100)
                    self.progress_updated.emit(progress)
                    
                except Exception as e:
                    error_msg = f"处理视频时发生错误: {str(e)}"
                    self.log_updated.emit(f"[ERROR] {error_msg}")
                    self.video_completed.emit(video_path, False, "", error_msg, 0)
            
            self.status_updated.emit("所有视频处理完成")
            self.all_completed.emit()
            
        except Exception as e:
            self.status_updated.emit(f"处理过程中发生错误: {str(e)}")
            self.log_updated.emit(f"错误: {str(e)}")
    
    def _get_current_python_path(self):
        """获取当前Python环境的路径"""
        # 使用sys.executable获取当前运行的Python解释器路径
        return sys.executable
    
    def _process_single_video(self, video_path):
        """处理单个视频"""
        try:
            video_name = Path(video_path).stem
            pose3d_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "algorithms", "pose_3d")
            
            # 第一步：运行 run_demo.py 生成 PKL 文件
            self.log_updated.emit(f"步骤1: 运行姿势估计生成PKL文件...")
            
            # 构建输出目录 - 使用输入视频的同级目录下的pose文件夹
            video_dir = os.path.dirname(video_path)
            output_dir = os.path.join(video_dir, video_name, "pose")
            os.makedirs(output_dir, exist_ok=True)
            
            # 项目根目录仍需要用于脚本路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
            # 获取当前Python环境路径
            python_path = self._get_current_python_path()
            self.log_updated.emit(f"使用Python环境: {python_path}")
            
            # 运行 run_demo.py
            run_demo_script = os.path.join(pose3d_dir, "main", "run_demo.py")
            demo_cmd = [
                python_path, run_demo_script,
                "--vid_file", video_path,
                "--save_pkl",
                "--no_render",
                "--gpu", "0"
            ]
            
            self.log_updated.emit(f"执行命令: {' '.join(demo_cmd)}")
            
            # 设置工作目录为项目根目录，确保输出保存到正确位置
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
            # 设置环境变量以确保UTF-8编码和正确的输出路径
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
            env['POSE_OUTPUT_DIR'] = output_dir  # 设置PKL文件输出目录
            env['KMP_DUPLICATE_LIB_OK'] = 'TRUE'  # 解决OpenMP运行时冲突问题
            
            result = subprocess.run(
                demo_cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=project_root
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "run_demo.py执行失败"
                return False, "", f"步骤1失败: {error_msg}"
            
            self.log_updated.emit("[SUCCESS] PKL文件生成成功")
            
            # 第二步：根据输出格式选择相应的处理脚本
            output_paths = []
            
            if self.output_format == "FBX文件" or self.output_format == "两者都有":
                # FBX模式：运行 improved_pkl_to_fbx_converter.py
                self.log_updated.emit(f"步骤2a: 转换PKL文件为FBX格式...")
                
                converter_script = os.path.join(pose3d_dir, "main", "animated_smpl_fbx_converter.py")
                
                # 注意：FBX转换可能需要特定的Python环境，这里保留原来的FBX专用环境
                # 如果FBX转换也可以使用当前环境，可以替换为self._get_current_python_path()
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                fbx_python = os.path.join(project_root, "fbx_env_py37", "Scripts", "python.exe")
                
                pkl_file = os.path.join(output_dir, "pmce_output.pkl")
                output_fbx_path = os.path.join(output_dir, f"{video_name}_animated.fbx")
                
                converter_cmd = [
                    fbx_python, converter_script,
                    "--pkl", pkl_file,
                    "--output_path", output_fbx_path
                ]
                
                self.log_updated.emit(f"执行命令: {' '.join(converter_cmd)}")
                
                # 设置环境变量以确保UTF-8编码
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
                env['KMP_DUPLICATE_LIB_OK'] = 'TRUE'  # 解决OpenMP运行时冲突问题


                
                result = subprocess.run(
                    converter_cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=project_root
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or "FBX转换失败"
                    return False, "", f"步骤2a失败: {error_msg}"
                
                output_paths.append(output_fbx_path)
                self.log_updated.emit(f"[SUCCESS] FBX文件生成成功: {output_fbx_path}")
            
            if self.output_format == "2D和3D对齐视频" or self.output_format == "两者都有":
                # 视频模式：运行 run_flexible_alignment.py
                step_name = "步骤2b" if self.output_format == "两者都有" else "步骤2"
                self.log_updated.emit(f"{step_name}: 生成2D和3D人体对齐视频...")
                
                alignment_script = os.path.join(pose3d_dir, "test_pose_2d_3d", "run_flexible_alignment.py")
                pkl_file = os.path.join(output_dir, "pmce_output.pkl")
                
                # 获取当前Python环境路径
                python_path = self._get_current_python_path()
                
                alignment_cmd = [
                    python_path, alignment_script,
                    "-v", video_path,
                    "-p", pkl_file
                ]
                
                self.log_updated.emit(f"执行命令: {' '.join(alignment_cmd)}")
                
                # 设置环境变量以确保UTF-8编码
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                env['PYTHONLEGACYWINDOWSSTDIO'] = '1'
                
                result = subprocess.run(
                    alignment_cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=project_root
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or "视频生成失败"
                    return False, "", f"{step_name}失败: {error_msg}"
                
                # 直接使用固定的输出文件名，不进行模式匹配
                video_output_path = os.path.join(output_dir, f"{video_name}_alignment_output.mp4")
                
                # 检查文件是否存在
                if os.path.exists(video_output_path):
                    self.log_updated.emit(f"[SUCCESS] 2D和3D人体对齐视频生成成功: {video_output_path}")
                else:
                    self.log_updated.emit(f"[WARNING] 未找到生成的视频文件: {video_output_path}")
                
                output_paths.append(video_output_path)
            
            # 返回主要输出路径（如果有多个文件，返回输出目录）
            if len(output_paths) > 1:
                output_path = output_dir  # 返回输出目录路径
                self.log_updated.emit(f"[SUCCESS] 所有文件已生成到目录: {output_dir}")
            else:
                output_path = output_paths[0] if output_paths else output_dir
            
            return True, output_path, ""
                
        except Exception as e:
            return False, "", str(e)

class PoseEstimationWidget(QWidget):
    """姿势估计界面组件"""
    
    status_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(int)
    
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.current_videos = []
        self.processing_thread = None
        
        # 视频播放相关
        self.video_capture = None
        self.current_video_path = None
        self.total_frames = 0
        self.fps = 30
        self.current_frame = 0
        self.is_playing = False
        self.playback_speed = 1.0
        
        # 播放控制状态
        self.is_slider_pressed = False
        self.is_muted = False
        self.previous_volume = 50
        
        # 播放定时器
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self._update_frame)
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化用户界面"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建三个主要区域
        left_panel = self._create_left_panel()  # 左侧面板
        center_panel = self._create_center_panel()  # 中间面板（视频预览）
        right_panel = self._create_right_panel()  # 右侧面板
        
        # 设置固定宽度，防止布局变化
        left_panel.setMinimumWidth(300)
        left_panel.setMaximumWidth(350)
        center_panel.setMinimumWidth(450)
        center_panel.setMaximumWidth(650)
        right_panel.setMinimumWidth(400)
        
        # 添加到主布局，使用固定比例
        main_layout.addWidget(left_panel, 0)  # 固定宽度
        main_layout.addWidget(center_panel, 0)  # 固定宽度
        main_layout.addWidget(right_panel, 1)  # 可伸缩
    
    def _create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 文件上传区域
        upload_group = QGroupBox("视频上传")
        upload_layout = QVBoxLayout(upload_group)
        
        # 上传按钮
        upload_buttons_layout = QHBoxLayout()
        
        self.upload_file_btn = QPushButton("上传视频文件")
        upload_buttons_layout.addWidget(self.upload_file_btn)
        
        self.upload_folder_btn = QPushButton("上传文件夹")
        upload_buttons_layout.addWidget(self.upload_folder_btn)
        
        upload_layout.addLayout(upload_buttons_layout)
        
        # 视频列表控制区域
        list_control_layout = QHBoxLayout()
        list_control_layout.addWidget(QLabel("视频列表:"))
        
        # 添加全选/取消全选切换按钮
        self.select_toggle_btn = QPushButton("全选")
        self.select_toggle_btn.setMaximumWidth(70)
        self.is_all_selected = False
        list_control_layout.addWidget(self.select_toggle_btn)
        
        # 添加删除选中视频按钮
        self.delete_selected_btn = QPushButton("删除选中")
        self.delete_selected_btn.setMaximumWidth(70)
        self.delete_selected_btn.setStyleSheet("QPushButton { color: #d32f2f; }")
        list_control_layout.addWidget(self.delete_selected_btn)
        
        # 选择状态显示
        self.selection_status_label = QLabel("已选择：0/0")
        self.selection_status_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                margin-left: 5px;
            }
        """)
        self.selection_status_label.setAlignment(Qt.AlignVCenter)
        list_control_layout.addWidget(self.selection_status_label)
        
        list_control_layout.addStretch()
        upload_layout.addLayout(list_control_layout)
        
        # 视频列表（支持复选框）
        self.video_list = QListWidget()
        self.video_list.setMinimumHeight(200)
        self.video_list.setMaximumHeight(200)
        self.video_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)
        upload_layout.addWidget(self.video_list)
        
        layout.addWidget(upload_group)
        
        # 输出格式选择区域
        output_group = QGroupBox("输出格式")
        output_layout = QVBoxLayout(output_group)
        
        # 单选按钮组
        self.output_format_group = QButtonGroup()
        
        # FBX文件选项
        self.fbx_radio = QRadioButton("FBX文件")
        self.fbx_radio.setToolTip("生成标准3D动画格式文件，兼容Maya、Blender等3D软件")
        self.fbx_radio.setChecked(True)  # 默认选中
        self.output_format_group.addButton(self.fbx_radio, 0)
        output_layout.addWidget(self.fbx_radio)
        
        # 2D和3D对齐视频选项
        self.alignment_radio = QRadioButton("2D和3D对齐视频")
        self.alignment_radio.setToolTip("生成带姿势标注的对齐视频文件")
        self.output_format_group.addButton(self.alignment_radio, 1)
        output_layout.addWidget(self.alignment_radio)
        
        # 两者都有选项
        self.both_radio = QRadioButton("两者都有")
        self.both_radio.setToolTip("同时生成FBX文件和2D和3D对齐视频")
        self.output_format_group.addButton(self.both_radio, 2)
        output_layout.addWidget(self.both_radio)
        
        layout.addWidget(output_group)
        
        # 参数说明区域
        info_group = QGroupBox("输出格式说明")
        info_layout = QVBoxLayout(info_group)
        
        info_text = QLabel(
            "<b>📋 输出格式说明：</b><br>"
            "• <b>FBX文件</b>：标准3D动画格式，兼容Maya、Blender等3D软件<br>"
            "• <b>2D和3D对齐视频</b>：生成带姿势标注的对齐视频文件<br>"
            "• <b>两者都有</b>：同时生成FBX文件和2D和3D对齐视频<br><br>"
            
            "<b>💡 使用建议：</b><br>"
            "• FBX文件适合导入3D软件进行动画制作和后期处理<br>"
            "• 2D和3D对齐视频适合直接查看姿势估计和跟踪效果<br>"
            "• 两者都有可以满足不同用途的需求，但处理时间会更长"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(
            "QLabel {"
            "    background-color: #f8f9fa;"
            "    border: 1px solid #dee2e6;"
            "    border-radius: 5px;"
            "    padding: 15px;"
            "    font-size: 12px;"
            "    line-height: 1.5;"
            "}"
        )
        info_layout.addWidget(info_text)
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        return panel
    
    def _create_center_panel(self):
        """创建中间面板（视频预览）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 视频播放区域
        video_group = QGroupBox("视频预览")
        video_layout = QVBoxLayout(video_group)
        
        # 视频显示标签
        self.video_label = QLabel()
        self.video_label.setMinimumHeight(300)
        self.video_label.setMaximumHeight(400)
        self.video_label.setMinimumWidth(400)
        self.video_label.setMaximumWidth(600)
        self.video_label.setStyleSheet("border: 1px solid gray; background-color: black;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("请选择视频文件")
        self.video_label.setScaledContents(False)
        self.video_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        video_layout.addWidget(self.video_label)
        
        # 播放控制
        controls_layout = QHBoxLayout()
        
        # 后退按钮
        self.backward_btn = QPushButton("⏪")
        self.backward_btn.setToolTip("后退10秒")
        controls_layout.addWidget(self.backward_btn)
        
        # 播放/暂停按钮
        self.play_btn = QPushButton("▶")
        self.play_btn.setToolTip("播放/暂停")
        controls_layout.addWidget(self.play_btn)
        
        # 前进按钮
        self.forward_btn = QPushButton("⏩")
        self.forward_btn.setToolTip("前进10秒")
        controls_layout.addWidget(self.forward_btn)
        
        # 进度条
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setToolTip("拖动调整播放位置")
        self.position_slider.sliderMoved.connect(self._set_position)
        self.position_slider.sliderPressed.connect(self._slider_pressed)
        self.position_slider.sliderReleased.connect(self._slider_released)
        controls_layout.addWidget(self.position_slider)
        
        # 时间显示
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(100)
        controls_layout.addWidget(self.time_label)
        
        video_layout.addLayout(controls_layout)
        
        # 第二行控制：音量和播放速度
        controls_layout2 = QHBoxLayout()
        
        # 音量控制
        volume_label = QLabel("音量:")
        controls_layout2.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.setToolTip("调整音量")
        self.volume_slider.valueChanged.connect(self._set_volume)
        controls_layout2.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("50%")
        self.volume_label.setMinimumWidth(30)
        controls_layout2.addWidget(self.volume_label)
        
        controls_layout2.addStretch()
        
        # 播放速度控制
        speed_label = QLabel("速度:")
        controls_layout2.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.setToolTip("调整播放速度")
        self.speed_combo.currentTextChanged.connect(self._set_playback_rate)
        controls_layout2.addWidget(self.speed_combo)
        
        # 静音按钮
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setToolTip("静音/取消静音")
        controls_layout2.addWidget(self.mute_btn)
        
        video_layout.addLayout(controls_layout2)
        
        layout.addWidget(video_group)
        
        # 快速设置区域
        quick_settings_group = QGroupBox("快速设置")
        quick_layout = QVBoxLayout(quick_settings_group)
        
        # 处理控制按钮
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 开始姿势估计")
        self.start_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #3498db;"
            "    color: white;"
            "    border: none;"
            "    padding: 12px 24px;"
            "    font-size: 14px;"
            "    font-weight: bold;"
            "    border-radius: 6px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #2980b9;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #21618c;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #bdc3c7;"
            "    color: #7f8c8d;"
            "}"
        )
        
        self.stop_btn = QPushButton("⏹ 停止处理")
        self.stop_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #e74c3c;"
            "    color: white;"
            "    border: none;"
            "    padding: 12px 24px;"
            "    font-size: 14px;"
            "    font-weight: bold;"
            "    border-radius: 6px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #c0392b;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #a93226;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #bdc3c7;"
            "    color: #7f8c8d;"
            "}"
        )
        self.stop_btn.setEnabled(False)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        
        quick_layout.addLayout(control_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "    border: 2px solid #bdc3c7;"
            "    border-radius: 5px;"
            "    text-align: center;"
            "    font-weight: bold;"
            "}"
            "QProgressBar::chunk {"
            "    background-color: #27ae60;"
            "    border-radius: 3px;"
            "}"
        )
        quick_layout.addWidget(self.progress_bar)
        
        # 状态显示
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(
            "QLabel {"
            "    background-color: #ecf0f1;"
            "    border: 1px solid #bdc3c7;"
            "    border-radius: 4px;"
            "    padding: 8px;"
            "    color: #2c3e50;"
            "    font-size: 12px;"
            "}"
        )
        quick_layout.addWidget(self.status_label)
        
        layout.addWidget(quick_settings_group)
        
        return panel
    
    def _create_right_panel(self):
        """创建右侧面板（日志和结果）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 处理日志选项卡
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        tab_widget.addTab(log_tab, "处理日志")
        
        # 结果展示选项卡
        result_tab = QWidget()
        result_layout = QVBoxLayout(result_tab)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        
        self.export_fbx_btn = QPushButton("导出FBX")
        self.export_fbx_btn.setToolTip("导出姿势估计结果为FBX格式")
        export_layout.addWidget(self.export_fbx_btn)
        
        self.export_json_btn = QPushButton("导出JSON")
        self.export_json_btn.setToolTip("导出姿势估计结果为JSON格式")
        export_layout.addWidget(self.export_json_btn)
        
        self.export_csv_btn = QPushButton("导出CSV")
        self.export_csv_btn.setToolTip("导出姿势估计结果为CSV格式")
        export_layout.addWidget(self.export_csv_btn)
        
        result_layout.addLayout(export_layout)
        
        tab_widget.addTab(result_tab, "处理结果")
        
        layout.addWidget(tab_widget)
        
        return panel
    

    
    def _upload_video_files(self):
        """上传视频文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "", "视频文件 (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm)"
        )
        
        if files:
            for file_path in files:
                if file_path not in self.current_videos:
                    self.current_videos.append(file_path)
                    self._add_video_to_list(file_path)
    
    def _upload_video_folder(self):
        """上传视频文件夹（支持累积式添加）"""
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
        
        if folder:
            self._add_videos_from_folder(folder)
            
            # 询问是否继续添加更多文件夹
            reply = QMessageBox.question(
                self, "继续添加", 
                f"已添加文件夹: {folder}\n\n是否继续添加其他文件夹？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            # 如果用户选择继续，递归调用自己
            if reply == QMessageBox.Yes:
                self._upload_video_folder()
    
    def _add_videos_from_folder(self, folder):
        """从文件夹添加视频文件"""
        video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.wmv', '*.flv', '*.webm']
        
        added_count = 0
        
        for extension in video_extensions:
            for file_path in Path(folder).glob(extension):
                file_str = str(file_path)
                if file_str not in self.current_videos:
                    self.current_videos.append(file_str)
                    self._add_video_to_list(file_str)
                    added_count += 1
        
        if added_count > 0:
            self._log_message(f"从文件夹添加了 {added_count} 个视频文件")
    
    def _add_video_to_list(self, video_path):
        """添加视频到列表"""
        item = QListWidgetItem()
        item.setText(os.path.basename(video_path))
        item.setData(Qt.UserRole, video_path)
        item.setCheckState(Qt.Checked)
        item.setToolTip(video_path)
        self.video_list.addItem(item)
        self._update_selection_status()
    
    def _on_video_selected(self, item):
        """视频选中事件"""
        video_path = item.data(Qt.UserRole)
        if video_path:
            self._load_video(video_path)
    
    def _on_video_check_changed(self, item):
        """视频复选框状态改变"""
        self._update_selection_status()
    
    def _toggle_select_all(self):
        """切换全选/取消全选"""
        if self.is_all_selected:
            self._deselect_all_videos()
        else:
            self._select_all_videos()
    
    def _select_all_videos(self):
        """全选所有视频"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            item.setCheckState(Qt.Checked)
        self._update_selection_status()
    
    def _deselect_all_videos(self):
        """取消全选所有视频"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            item.setCheckState(Qt.Unchecked)
        self._update_selection_status()
    
    def _delete_selected_videos(self):
        """删除选中的视频"""
        selected_videos = self._get_selected_videos()
        
        if not selected_videos:
            QMessageBox.warning(self, "警告", "请先选择要删除的视频")
            return
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除选中的 {len(selected_videos)} 个视频吗？\n\n注意：这只会从列表中移除，不会删除实际文件。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for i in range(self.video_list.count() - 1, -1, -1):
                item = self.video_list.item(i)
                if item.checkState() == Qt.Checked:
                    video_path = item.data(Qt.UserRole)
                    if video_path in self.current_videos:
                        self.current_videos.remove(video_path)
                    self.video_list.takeItem(i)
            
            self._update_selection_status()
    
    def _get_selected_videos(self):
        """获取选中的视频列表"""
        selected_videos = []
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.checkState() == Qt.Checked:
                video_path = item.data(Qt.UserRole)
                selected_videos.append(video_path)
        return selected_videos
    
    def _update_selection_status(self):
        """更新选择状态显示"""
        selected_count = len(self._get_selected_videos())
        total_count = self.video_list.count()
        self.selection_status_label.setText(f"已选择：{selected_count}/{total_count}")
        
        if total_count == 0:
            self.is_all_selected = False
            self.select_toggle_btn.setText("全选")
        elif selected_count == total_count:
            self.is_all_selected = True
            self.select_toggle_btn.setText("取消全选")
        else:
            self.is_all_selected = False
            self.select_toggle_btn.setText("全选")
    
    def _load_video(self, video_path):
        """加载视频"""
        try:
            if self.video_capture:
                self.video_capture.release()
            
            self.video_capture = cv2.VideoCapture(video_path)
            if not self.video_capture.isOpened():
                QMessageBox.warning(self, "错误", f"无法打开视频文件：{video_path}")
                return
            
            self.current_video_path = video_path
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            self.current_frame = 0
            
            # 设置进度条范围
            self.position_slider.setRange(0, self.total_frames - 1)
            self.position_slider.setValue(0)
            
            # 显示第一帧
            self._show_frame(0)
            
            # 更新时间显示
            duration = self.total_frames / self.fps if self.fps > 0 else 0
            self._update_time_display(0, duration)
            
            self._log_message(f"已加载视频：{os.path.basename(video_path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载视频失败：{str(e)}")
    
    def _show_frame(self, frame_number):
        """显示指定帧"""
        if not self.video_capture:
            return
        
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.video_capture.read()
        
        if ret:
            # 转换颜色格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # 创建QImage
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 使用固定的显示区域大小，避免获取标签大小时的问题
            display_width = 400
            display_height = 300
            
            # 缩放图像以适应固定尺寸，保持宽高比
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                display_width, display_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
            self.video_label.setPixmap(scaled_pixmap)
            self.current_frame = frame_number
    
    def _toggle_playback(self):
        """切换播放/暂停"""
        if not self.video_capture:
            return
        
        if self.is_playing:
            self._pause_video()
        else:
            self._play_video()
    
    def _play_video(self):
        """播放视频"""
        if not self.video_capture:
            return
        
        self.is_playing = True
        self.play_btn.setText("⏸")
        
        # 计算播放间隔
        interval = int(1000 / (self.fps * self.playback_speed)) if self.fps > 0 else 33
        self.play_timer.start(interval)
    
    def _pause_video(self):
        """暂停视频"""
        self.is_playing = False
        self.play_btn.setText("▶")
        self.play_timer.stop()
    
    def _update_frame(self):
        """更新帧（定时器回调）"""
        if not self.is_playing or not self.video_capture:
            return
        
        next_frame = self.current_frame + 1
        if next_frame >= self.total_frames:
            self._pause_video()
            return
        
        self._show_frame(next_frame)
        
        if not self.is_slider_pressed:
            self.position_slider.setValue(next_frame)
        
        # 更新时间显示
        current_time = next_frame / self.fps if self.fps > 0 else 0
        duration = self.total_frames / self.fps if self.fps > 0 else 0
        self._update_time_display(current_time, duration)
    
    def _set_position(self, position):
        """设置播放位置"""
        if not self.video_capture:
            return
        
        self._show_frame(position)
        
        # 更新时间显示
        current_time = position / self.fps if self.fps > 0 else 0
        duration = self.total_frames / self.fps if self.fps > 0 else 0
        self._update_time_display(current_time, duration)
    
    def _slider_pressed(self):
        """进度条按下"""
        self.is_slider_pressed = True
    
    def _slider_released(self):
        """进度条释放"""
        self.is_slider_pressed = False
    
    def _backward_10s(self):
        """后退10秒"""
        if not self.video_capture:
            return
        
        target_frame = max(0, self.current_frame - int(10 * self.fps))
        self._show_frame(target_frame)
        self.position_slider.setValue(target_frame)
    
    def _forward_10s(self):
        """前进10秒"""
        if not self.video_capture:
            return
        
        target_frame = min(self.total_frames - 1, self.current_frame + int(10 * self.fps))
        self._show_frame(target_frame)
        self.position_slider.setValue(target_frame)
    
    def _set_volume(self, volume):
        """设置音量"""
        self.volume_label.setText(f"{volume}%")
        if volume == 0:
            self.mute_btn.setText("🔇")
        else:
            self.mute_btn.setText("🔊")
    
    def _toggle_mute(self):
        """切换静音"""
        if self.is_muted:
            self.volume_slider.setValue(self.previous_volume)
            self.is_muted = False
        else:
            self.previous_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
            self.is_muted = True
    
    def _set_playback_rate(self, rate_text):
        """设置播放速度"""
        try:
            self.playback_speed = float(rate_text.replace('x', ''))
            if self.is_playing:
                # 重新启动定时器以应用新的播放速度
                interval = int(1000 / (self.fps * self.playback_speed)) if self.fps > 0 else 33
                self.play_timer.start(interval)
        except ValueError:
            pass
    
    def _update_time_display(self, current_time, duration):
        """更新时间显示"""
        current_str = self._format_time(current_time)
        duration_str = self._format_time(duration)
        self.time_label.setText(f"{current_str} / {duration_str}")
    
    def _format_time(self, seconds):
        """格式化时间显示"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def _start_pose_estimation(self):
        """开始姿势估计"""
        selected_videos = self._get_selected_videos()
        
        if not selected_videos:
            QMessageBox.warning(self, "警告", "请先选择要处理的视频")
            return
        
        # 获取参数
        # 根据单选按钮获取输出格式
        if self.fbx_radio.isChecked():
            output_format = "FBX文件"
        elif self.alignment_radio.isChecked():
            output_format = "2D和3D对齐视频"
        elif self.both_radio.isChecked():
            output_format = "两者都有"
        else:
            output_format = "FBX文件"  # 默认值
        # 使用默认参数
        processing_mode = "人体网格重建"
        quality = "标准"
        enable_smoothing = True
        enable_optimization = True
        save_intermediate = False
        
        # 确定输出目录 - 使用项目根目录的绝对路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        output_dir = os.path.join(project_root, "output", "pose_estimation_results")
        # 注意：不在这里创建目录，而是在实际需要时创建
        
        # 创建处理线程
        self.processing_thread = PoseEstimationThread(
            videos=selected_videos,
            output_dir=output_dir,
            pose_model=processing_mode,
            output_format=output_format,
            enable_3d=(processing_mode == "人体网格重建")
        )
        
        # 连接信号
        self.processing_thread.progress_updated.connect(self.progress_bar.setValue)
        self.processing_thread.status_updated.connect(self.status_label.setText)
        self.processing_thread.log_updated.connect(self._log_message)
        self.processing_thread.video_completed.connect(self._on_video_completed)
        self.processing_thread.all_completed.connect(self._on_processing_finished)
        
        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # 启动线程
        self.processing_thread.start()
        self._log_message(f"开始处理 {len(selected_videos)} 个视频")
    
    def _stop_pose_estimation(self):
        """停止姿势估计"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self._log_message("正在停止处理...")
    
    def _on_video_completed(self, video_path, success, output_path, error_msg, processing_time):
        """单个视频处理完成回调"""
        video_name = os.path.basename(video_path)
        if success:
            self._log_message(f"[SUCCESS] {video_name} 处理成功 - 输出: {output_path} - 耗时: {processing_time:.1f}秒")
        else:
            self._log_message(f"[ERROR] {video_name} 处理失败 - 错误: {error_msg} - 耗时: {processing_time:.1f}秒")
    
    def _on_processing_finished(self):
        """处理完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("处理完成")
        self._log_message("所有视频处理完成")
    
    def _export_results(self, format_type):
        """导出结果"""
        if not hasattr(self, 'processing_results') or not self.processing_results:
            QMessageBox.warning(self, "警告", "没有可导出的结果")
            return
        
        file_filter = {
            'fbx': "FBX文件 (*.fbx)",
            'json': "JSON文件 (*.json)",
            'csv': "CSV文件 (*.csv)"
        }.get(format_type, "所有文件 (*.*)")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"导出{format_type.upper()}文件", "", file_filter
        )
        
        if file_path:
            try:
                # 这里应该实现具体的导出逻辑
                self._log_message(f"结果已导出到：{file_path}")
                QMessageBox.information(self, "成功", f"结果已成功导出到：{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败：{str(e)}")
    
    def _log_message(self, message):
        """记录日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止视频播放
        if self.is_playing:
            self._pause_video()
        
        # 释放视频资源
        if self.video_capture:
            self.video_capture.release()
        
        # 停止处理线程
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait()
        
        event.accept()
    
    def _connect_signals(self):
        """连接信号"""
        # 视频上传相关
        self.upload_file_btn.clicked.connect(self._upload_video_files)
        self.upload_folder_btn.clicked.connect(self._upload_video_folder)
        self.select_toggle_btn.clicked.connect(self._toggle_select_all)
        self.delete_selected_btn.clicked.connect(self._delete_selected_videos)
        
        # 视频列表相关
        self.video_list.itemClicked.connect(self._on_video_selected)
        self.video_list.itemChanged.connect(self._on_video_check_changed)
        
        # 播放控制相关
        self.backward_btn.clicked.connect(self._backward_10s)
        self.play_btn.clicked.connect(self._toggle_playback)
        self.forward_btn.clicked.connect(self._forward_10s)
        
        # 进度条相关
        self.position_slider.valueChanged.connect(self._set_position)
        self.position_slider.sliderPressed.connect(self._slider_pressed)
        self.position_slider.sliderReleased.connect(self._slider_released)
        
        # 音量和速度控制
        self.volume_slider.valueChanged.connect(self._set_volume)
        self.mute_btn.clicked.connect(self._toggle_mute)
        self.speed_combo.currentTextChanged.connect(self._set_playback_rate)
        
        # 处理控制
        self.start_btn.clicked.connect(self._start_pose_estimation)
        self.stop_btn.clicked.connect(self._stop_pose_estimation)
        
        # 导出功能
        self.export_fbx_btn.clicked.connect(lambda: self._export_results('fbx'))
        self.export_json_btn.clicked.connect(lambda: self._export_results('json'))
        self.export_csv_btn.clicked.connect(lambda: self._export_results('csv'))
        
        # 播放定时器
        self.play_timer.timeout.connect(self._update_frame)