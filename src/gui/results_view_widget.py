# -*- coding: utf-8 -*-
"""
查看结果板块
1. 选择文件夹并读取其中视频，显示为列表
2. 点击列表中的视频，支持播放/暂停
3. 读取视频同名文件夹下 description 内容，支持本地/API结果切换
4. 读取视频同名文件夹下 pose3d 结果（.mp4 / .fbx）
"""

import os
from pathlib import Path
from typing import List, Optional

import cv2
from PyQt5.QtCore import Qt, QTimer, QUrl, QElapsedTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QLineEdit, QComboBox, QPlainTextEdit,
    QMessageBox, QGroupBox, QSplitter
)
from PyQt5.QtGui import QDesktopServices


class ResultsViewWidget(QWidget):
    """查看结果板块"""

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager

        # 播放相关
        self.video_capture = None
        self.current_video_path: Optional[str] = None
        self.fps = 25.0
        self.video_frame_count = 0
        # 统一时间轴：使用一个主定时器驱动两侧播放
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.is_playing = False
        self.elapsed_timer = QElapsedTimer()
        self.accumulated_ms = 0  # 暂停前累计的播放毫秒数

        # pose3d 播放相关（右上半部分）
        self.pose_video_capture = None
        self.pose_fps = 25.0
        self.pose_frame_count = 0
        self.pose_timer = QTimer(self)
        self.pose_timer.timeout.connect(self._update_pose_frame)
        self.pose_is_playing = False

        self._init_ui()

    # UI
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 主分割：左1/3（列表与选择），右2/3（预览/姿态 + 描述）
        main_splitter = QSplitter(Qt.Horizontal)

        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # 选择视频文件
        file_bar = QHBoxLayout()
        file_btn = QPushButton("选择视频文件")
        file_btn.clicked.connect(self._select_video_file)
        file_bar.addWidget(file_btn)
        left_layout.addLayout(file_bar)

        # 选择文件夹（递归遍历）
        folder_bar = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("请选择包含视频的文件夹…(递归遍历)")
        select_btn = QPushButton("选择文件夹")
        refresh_btn = QPushButton("刷新")
        select_btn.clicked.connect(self._select_folder)
        refresh_btn.clicked.connect(self._refresh_folder)
        folder_bar.addWidget(self.folder_edit)
        folder_bar.addWidget(select_btn)
        folder_bar.addWidget(refresh_btn)
        left_layout.addLayout(folder_bar)

        # 视频列表
        self.video_list = QListWidget()
        self.video_list.itemSelectionChanged.connect(self._on_video_selected)
        left_layout.addWidget(self.video_list)

        main_splitter.addWidget(left_panel)

        # 右侧面板：垂直分割（上2/3：左右分割，视频预览/姿态播放；下1/3：描述内容）
        right_splitter = QSplitter(Qt.Vertical)

        # 顶部区域：水平分割为左右各一半
        top_splitter = QSplitter(Qt.Horizontal)

        # 左：视频预览
        preview_group = QGroupBox("视频预览")
        pg_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(240)
        controls = QHBoxLayout()
        play_btn = QPushButton("播放")
        pause_btn = QPushButton("暂停")
        stop_btn = QPushButton("停止")
        play_btn.clicked.connect(self._play)
        pause_btn.clicked.connect(self._pause)
        stop_btn.clicked.connect(self._stop)
        controls.addWidget(play_btn)
        controls.addWidget(pause_btn)
        controls.addWidget(stop_btn)
        pg_layout.addWidget(self.preview_label)
        pg_layout.addLayout(controls)

        # 右：姿态结果播放
        pose_group = QGroupBox("动作姿态结果 (pose3d) 播放")
        pg2_layout = QVBoxLayout(pose_group)
        self.pose_preview_label = QLabel()
        self.pose_preview_label.setAlignment(Qt.AlignCenter)
        self.pose_preview_label.setMinimumHeight(240)

        self.pose_mp4_label = QLabel("MP4: 无")
        self.pose_fbx_label = QLabel("FBX: 无")

        pose_controls = QHBoxLayout()
        pose_play_btn = QPushButton("播放")
        pose_pause_btn = QPushButton("暂停")
        pose_stop_btn = QPushButton("停止")
        # 统一控制：右侧姿态播放按钮也联动左侧的主播放控制
        pose_play_btn.clicked.connect(self._play)
        pose_pause_btn.clicked.connect(self._pause)
        pose_stop_btn.clicked.connect(self._stop)
        pose_controls.addWidget(pose_play_btn)
        pose_controls.addWidget(pose_pause_btn)
        pose_controls.addWidget(pose_stop_btn)

        open_row = QHBoxLayout()
        open_mp4_btn = QPushButton("外部预览MP4")
        open_fbx_btn = QPushButton("外部打开FBX")
        open_mp4_btn.clicked.connect(self._open_pose_mp4)
        open_fbx_btn.clicked.connect(self._open_pose_fbx)
        open_row.addWidget(open_mp4_btn)
        open_row.addWidget(open_fbx_btn)

        pg2_layout.addWidget(self.pose_preview_label)
        pg2_layout.addWidget(self.pose_mp4_label)
        pg2_layout.addWidget(self.pose_fbx_label)
        pg2_layout.addLayout(pose_controls)
        pg2_layout.addLayout(open_row)

        top_splitter.addWidget(preview_group)
        top_splitter.addWidget(pose_group)

        # 底部区域：描述内容
        desc_group = QGroupBox("描述内容")
        dg_layout = QVBoxLayout(desc_group)
        model_bar = QHBoxLayout()
        self.model_combo = QComboBox()
        # 初始给出一个占位项，选择视频后会动态填充可用模型
        self.model_combo.addItems(["本地模型"])
        self.model_combo.currentIndexChanged.connect(self._load_description_for_current)
        self.model_combo.currentTextChanged.connect(self._load_description_for_current)
        model_bar.addWidget(QLabel("模型选择:"))
        model_bar.addWidget(self.model_combo)
        dg_layout.addLayout(model_bar)
        self.description_view = QPlainTextEdit()
        self.description_view.setReadOnly(True)
        dg_layout.addWidget(self.description_view)

        right_splitter.addWidget(top_splitter)
        right_splitter.addWidget(desc_group)

        main_splitter.addWidget(right_splitter)

        # 设置初始大小比例与拉伸因子：左(1) : 右(2)，顶部(2) : 底部(1)
        # sizes 提供初始大小，setStretchFactor 保持相对比例在窗口缩放时更稳定
        main_splitter.setSizes([300, 600])
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        right_splitter.setSizes([400, 200])
        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 1)

        # 顶部左右保持均分（未强制要求比例，可视需要再调整）
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)

        layout.addWidget(main_splitter)

    # 目录选择/刷新
    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择视频所在文件夹")
        if folder:
            self.folder_edit.setText(folder)
            self._refresh_folder()

    def _select_video_file(self):
        filters = "视频文件 (*.mp4 *.avi *.mov *.mkv *.wmv *.mpeg)"
        file_path, _ = QFileDialog.getOpenFileName(self, "选择视频文件", "", filters)
        if file_path:
            # 防止重复添加
            exists = False
            for i in range(self.video_list.count()):
                if self.video_list.item(i).data(Qt.UserRole) == file_path:
                    exists = True
                    break
            if not exists:
                vp = Path(file_path)
                item = QListWidgetItem(vp.name)
                item.setData(Qt.UserRole, file_path)
                self.video_list.addItem(item)

    def _refresh_folder(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "提示", "请先选择文件夹")
            return
        self._load_videos_recursive(Path(folder))

    # 加载视频列表
    def _load_videos_recursive(self, folder: Path):
        self.video_list.clear()
        if not folder.exists() or not folder.is_dir():
            QMessageBox.warning(self, "提示", "文件夹不存在或不可用")
            return
        exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".mpeg"}
        # 排除生成结果目录（避免将 pose/pose3d 内的结果视频列入左侧列表）
        exclude_dirs = {"pose", "pose3d"}
        videos: List[Path] = []
        try:
            for p in folder.rglob("*"):
                if p.is_file() and p.suffix.lower() in exts:
                    # 如果路径中包含被排除的目录名，则跳过
                    try:
                        if any(parent.name.lower() in exclude_dirs for parent in p.parents):
                            continue
                    except Exception:
                        pass
                    videos.append(p)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"遍历文件夹失败: {e}")
            return
        for vp in sorted(videos):
            item = QListWidgetItem(vp.name)
            item.setData(Qt.UserRole, str(vp))
            self.video_list.addItem(item)

    # 选择视频
    def _on_video_selected(self):
        items = self.video_list.selectedItems()
        if not items:
            return
        video_path = items[0].data(Qt.UserRole)
        self.current_video_path = video_path
        # 重置预览
        self._open_capture(video_path)
        self._pause()
        self._show_first_frame()
        # 加载描述与姿态结果
        self._populate_models_for_current()
        self._load_description_for_current()
        self._load_pose3d_for_current()
        # 如果有pose mp4，打开并展示第一帧
        if getattr(self, 'pose_mp4_path', None):
            self._open_pose_capture(str(self.pose_mp4_path))
            self._pose_pause()
            
            self._pose_show_first_frame()

    # 播放控制
    def _open_capture(self, video_path: str):
        try:
            if self.video_capture:
                self.video_capture.release()
            self.video_capture = cv2.VideoCapture(video_path)
            fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            if fps and fps > 0:
                self.fps = fps
            count = self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT)
            try:
                self.video_frame_count = int(count) if count and count > 0 else 0
            except Exception:
                self.video_frame_count = 0
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开视频失败: {e}")

    def _show_first_frame(self):
        if not self.video_capture:
            return
        ok, frame = self.video_capture.read()
        if ok:
            self._display_frame(frame)
            # 回退到起始位置
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def _play(self):
        if not self.video_capture:
            return
        self.is_playing = True
        self.pose_is_playing = bool(self.pose_video_capture)
        # 使用统一时间轴：启动高精度计时器
        self.elapsed_timer.start()
        base_fps = max(int(self.fps if self.fps and self.fps > 0 else 25),
                       int(self.pose_fps if self.pose_video_capture and self.pose_fps and self.pose_fps > 0 else 0),
                       30)
        interval = max(10, int(1000 / base_fps))
        self.timer.start(interval)

    def _pause(self):
        if self.is_playing:
            self.accumulated_ms += self.elapsed_timer.elapsed()
        self.is_playing = False
        self.pose_is_playing = False
        self.timer.stop()

    def _stop(self):
        self._pause()
        self.accumulated_ms = 0
        if self.video_capture:
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._show_first_frame()
        # 同步停止姿态播放并回到首帧
        if self.pose_video_capture:
            self.pose_video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._pose_show_first_frame()

    def _update_frame(self):
        # 使用统一时间轴驱动两侧画面更新
        if not self.is_playing or not self.video_capture:
            return
        # 当前播放位置（毫秒）
        pos_ms = self.accumulated_ms + self.elapsed_timer.elapsed()

        # 左侧视频按时间映射到帧索引
        try:
            vid_index = int((pos_ms * self.fps) / 1000)
        except Exception:
            vid_index = 0
        if self.video_frame_count and vid_index >= self.video_frame_count:
            self._stop()
            return
        # 跳转并读取该帧
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, vid_index))
        ok, frame = self.video_capture.read()
        if ok:
            self._display_frame(frame)

        # 右侧姿态视频按同一时间轴映射
        if self.pose_video_capture:
            try:
                pose_index = int((pos_ms * self.pose_fps) / 1000)
            except Exception:
                pose_index = 0
            if self.pose_frame_count and pose_index >= self.pose_frame_count:
                # 若姿态视频结束，也同步停止
                self._stop()
                return
            self.pose_video_capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, pose_index))
            ok2, frame2 = self.pose_video_capture.read()
            if ok2:
                self._display_pose_frame(frame2)

    def _display_frame(self, frame):
        # BGR -> RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(self.preview_label.width(), self.preview_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(pix)

    # pose3d 播放控制
    def _open_pose_capture(self, video_path: str):
        try:
            if self.pose_video_capture:
                self.pose_video_capture.release()
            self.pose_video_capture = cv2.VideoCapture(video_path)
            fps = self.pose_video_capture.get(cv2.CAP_PROP_FPS)
            if fps and fps > 0:
                self.pose_fps = fps
            count = self.pose_video_capture.get(cv2.CAP_PROP_FRAME_COUNT)
            try:
                self.pose_frame_count = int(count) if count and count > 0 else 0
            except Exception:
                self.pose_frame_count = 0
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开姿态视频失败: {e}")

    def _pose_show_first_frame(self):
        if not self.pose_video_capture:
            return
        ok, frame = self.pose_video_capture.read()
        if ok:
            self._display_pose_frame(frame)
            # 回退到起始位置
            self.pose_video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def _pose_play(self):
        # 统一由主控制处理，此方法保留以兼容旧逻辑
        self._play()

    def _pose_pause(self):
        self._pause()

    def _pose_stop(self):
        self._stop()

    def _update_pose_frame(self):
        if not self.pose_is_playing or not self.pose_video_capture:
            return
        ok, frame = self.pose_video_capture.read()
        if not ok:
            self._pose_stop()
            return
        self._display_pose_frame(frame)

    def _display_pose_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(self.pose_preview_label.width(), self.pose_preview_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.pose_preview_label.setPixmap(pix)

    # 根据当前视频动态填充可用模型列表（本地 + 不同API模型）
    def _populate_models_for_current(self):
        try:
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItem("本地模型")
            if not self.current_video_path:
                self.model_combo.blockSignals(False)
                return
            vp = Path(self.current_video_path)
            description_folder = (vp.parent / vp.stem / 'description')
            if not description_folder.exists():
                self.model_combo.blockSignals(False)
                return
            # 扫描所有JSON，收集 model_name
            api_models = []
            for jf in description_folder.glob(f"{vp.stem}_*.json"):
                try:
                    import json
                    with open(jf, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    model_name = data.get('model_name') or data.get('api_model') or ''
                    model_suffix = data.get('model_suffix') or ''
                    # 认为非local即属于API模型
                    if (model_name and model_name not in api_models) and (model_suffix != 'local'):
                        api_models.append(model_name)
                except Exception:
                    continue
            for m in api_models:
                self.model_combo.addItem(f"API: {m}")
        finally:
            self.model_combo.blockSignals(False)

    # 描述内容加载
    def _load_description_for_current(self):
        if not self.current_video_path:
            return
        current_text = self.model_combo.currentText().strip()
        is_local = (current_text == '本地模型')
        vp = Path(self.current_video_path)
        video_folder = vp.parent / vp.stem
        description_folder = video_folder / 'description'
        if not description_folder.exists():
            self.description_view.setPlainText("未找到 description 文件夹")
            return

        import json
        chosen_file: Optional[Path] = None
        chosen_data = None
        try:
            if is_local:
                # 优先带local后缀的文件
                candidates = list(description_folder.glob(f"{vp.stem}_*_{'local'}.json"))
                if not candidates:
                    candidates = list(description_folder.glob(f"{vp.stem}_*.json"))
                if candidates:
                    chosen_file = max(candidates, key=lambda p: p.stat().st_mtime)
                    with open(chosen_file, 'r', encoding='utf-8') as f:
                        chosen_data = json.load(f)
            else:
                # API模型：匹配当前选择的模型名称
                api_model = current_text.replace('API: ', '')
                match_files = []
                for jf in description_folder.glob(f"{vp.stem}_*.json"):
                    try:
                        with open(jf, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        model_name = data.get('model_name') or data.get('api_model') or ''
                        model_suffix = data.get('model_suffix') or ''
                        if model_name == api_model and model_suffix != 'local':
                            match_files.append((jf, data))
                    except Exception:
                        continue
                if match_files:
                    chosen_file, chosen_data = max(match_files, key=lambda x: x[0].stat().st_mtime)

            if chosen_data:
                desc = chosen_data.get('description') or chosen_data.get('summary') or ''
                action_desc = chosen_data.get('action_description', '')
                model_name = chosen_data.get('model_name') or chosen_data.get('api_model') or ('本地模型' if is_local else '')
                status = '成功' if chosen_data.get('success', True) else '失败'
                header = f"文件: {chosen_file.name if chosen_file else ''}\n状态: {status}\n模型: {model_name}"
                # 本地模型严格要求展示 description + action_description
                if is_local:
                    content_text = header + ("\n\n" + desc if desc else "")
                    if action_desc:
                        content_text += f"\n\n动作描述:\n{action_desc}"
                else:
                    # API模型优先展示 description，若有动作描述也一起展示
                    content_text = header + ("\n\n" + desc if desc else "")
                    if action_desc:
                        content_text += f"\n\n动作描述:\n{action_desc}"
            else:
                # 兜底：txt/md/csv
                fallback = None
                for ext in ('.txt', '.md', '.csv'):
                    files = list(description_folder.glob(f"{vp.stem}_*{ext}"))
                    if files:
                        fallback = max(files, key=lambda p: p.stat().st_mtime)
                        break
                if fallback:
                    try:
                        with open(fallback, 'r', encoding='utf-8') as f:
                            content_text = f.read()
                    except Exception:
                        content_text = f"无法读取文件: {fallback.name}"
                else:
                    content_text = "未找到描述结果文件"
            self.description_view.setPlainText(content_text)
        except Exception as e:
            self.description_view.setPlainText(f"加载描述结果失败: {e}")

    # 姿态结果加载
    def _load_pose3d_for_current(self):
        self.pose_mp4_path = None
        self.pose_fbx_path = None
        if not self.current_video_path:
            self.pose_mp4_label.setText("MP4: 无")
            self.pose_fbx_label.setText("FBX: 无")
            return
        vp = Path(self.current_video_path)
        pose_folder = vp.parent / vp.stem / 'pose3d'
        if not pose_folder.exists():
            self.pose_mp4_label.setText("MP4: 未找到 pose3d 文件夹")
            self.pose_fbx_label.setText("FBX: 未找到 pose3d 文件夹")
            return
        mp4s = list(pose_folder.glob("*.mp4"))
        fbxs = list(pose_folder.glob("*.fbx"))
        if mp4s:
            self.pose_mp4_path = max(mp4s, key=lambda p: p.stat().st_mtime)
            self.pose_mp4_label.setText(f"MP4: {self.pose_mp4_path.name}")
        else:
            self.pose_mp4_label.setText("MP4: 无")
        if fbxs:
            self.pose_fbx_path = max(fbxs, key=lambda p: p.stat().st_mtime)
            self.pose_fbx_label.setText(f"FBX: {self.pose_fbx_path.name}")
        else:
            self.pose_fbx_label.setText("FBX: 无")

    def _open_pose_mp4(self):
        if not getattr(self, 'pose_mp4_path', None):
            QMessageBox.information(self, "提示", "未找到MP4结果文件")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pose_mp4_path)))

    def _open_pose_fbx(self):
        if not getattr(self, 'pose_fbx_path', None):
            QMessageBox.information(self, "提示", "未找到FBX结果文件")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pose_fbx_path)))