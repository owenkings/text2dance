# -*- coding: utf-8 -*-
"""
OpenPose 2D姿态估计算法
基于OpenPose的2D人体姿态估计
"""

import cv2
import numpy as np
import json
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from ..base_algorithm import Pose2DAlgorithm

class OpenPoseAlgorithm(Pose2DAlgorithm):
    """OpenPose算法实现"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager, "openpose")
        
        self.description = "OpenPose 2D人体姿态估计算法"
        self.parameters = {
            "model_type": {
                "type": "string",
                "default": "COCO",
                "options": ["COCO", "MPI"],
                "description": "模型类型"
            },
            "net_resolution": {
                "type": "string",
                "default": "368x368",
                "options": ["320x240", "368x368", "432x368", "656x368"],
                "description": "网络输入分辨率"
            },
            "confidence_threshold": {
                "type": "float",
                "default": 0.1,
                "min": 0.0,
                "max": 1.0,
                "description": "置信度阈值"
            },
            "scale_number": {
                "type": "int",
                "default": 1,
                "min": 1,
                "max": 4,
                "description": "尺度数量"
            },
            "scale_gap": {
                "type": "float",
                "default": 0.3,
                "min": 0.1,
                "max": 1.0,
                "description": "尺度间隔"
            }
        }
        
        # OpenPose特定配置
        self.net = None
        self.output_layers = []
        self.keypoint_names = []
        self.skeleton_pairs = []
    
    def _initialize(self):
        """初始化OpenPose算法"""
        try:
            # 设置模型路径
            model_dir = self.config.get("model_path", "models/openpose")
            self.model_path = str(Path(model_dir))
            
            # 设置关键点信息
            model_type = self.config.get("model_type", "COCO")
            if model_type == "COCO":
                self._setup_coco_model()
            else:
                self._setup_mpi_model()
            
            self.logger.info("OpenPose算法初始化完成")
            
        except Exception as e:
            self.logger.error(f"OpenPose算法初始化失败: {e}")
    
    def _setup_coco_model(self):
        """设置COCO模型"""
        self.keypoint_names = [
            "Nose", "Neck", "RShoulder", "RElbow", "RWrist",
            "LShoulder", "LElbow", "LWrist", "RHip", "RKnee",
            "RAnkle", "LHip", "LKnee", "LAnkle", "REye",
            "LEye", "REar", "LEar"
        ]
        
        self.skeleton_pairs = [
            [1, 2], [1, 5], [2, 3], [3, 4], [5, 6], [6, 7],
            [1, 8], [8, 9], [9, 10], [1, 11], [11, 12], [12, 13],
            [1, 0], [0, 14], [14, 16], [0, 15], [15, 17],
            [2, 16], [5, 17]
        ]
    
    def _setup_mpi_model(self):
        """设置MPI模型"""
        self.keypoint_names = [
            "Head", "Neck", "RShoulder", "RElbow", "RWrist",
            "LShoulder", "LElbow", "LWrist", "RHip", "RKnee",
            "RAnkle", "LHip", "LKnee", "LAnkle", "Chest"
        ]
        
        self.skeleton_pairs = [
            [0, 1], [1, 2], [2, 3], [3, 4], [1, 5], [5, 6],
            [6, 7], [1, 14], [14, 8], [8, 9], [9, 10],
            [14, 11], [11, 12], [12, 13]
        ]
    
    def _load_model(self) -> bool:
        """加载OpenPose模型"""
        try:
            model_type = self.config.get("model_type", "COCO")
            
            if model_type == "COCO":
                proto_file = Path(self.model_path) / "pose_deploy_linevec.prototxt"
                weights_file = Path(self.model_path) / "pose_iter_440000.caffemodel"
            else:  # MPI
                proto_file = Path(self.model_path) / "pose_deploy_linevec_faster_4_stages.prototxt"
                weights_file = Path(self.model_path) / "pose_iter_160000.caffemodel"
            
            if not proto_file.exists() or not weights_file.exists():
                self.logger.error(f"模型文件不存在: {proto_file} 或 {weights_file}")
                return False
            
            # 加载网络
            self.net = cv2.dnn.readNetFromCaffe(str(proto_file), str(weights_file))
            
            # 设置输出层
            if model_type == "COCO":
                self.output_layers = ["conv2d_transpose", "conv2d_transpose_1"]
            else:
                self.output_layers = ["conv2d_transpose", "conv2d_transpose_1"]
            
            self.logger.info(f"OpenPose模型加载成功: {model_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"OpenPose模型加载失败: {e}")
            return False
    
    def _process_impl(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """OpenPose处理实现"""
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # 检查输入是图片还是视频
            if input_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                return self._process_image(input_path, output_path, progress_callback, **kwargs)
            else:
                return self._process_video(input_path, output_path, progress_callback, **kwargs)
                
        except Exception as e:
            self.logger.error(f"OpenPose处理失败: {e}")
            raise
    
    def _process_image(self, input_path: Path, output_path: Path,
                      progress_callback: Optional[Callable[[float], None]] = None,
                      **kwargs) -> Dict[str, Any]:
        """处理单张图片"""
        try:
            # 读取图片
            image = cv2.imread(str(input_path))
            if image is None:
                raise ValueError(f"无法读取图片: {input_path}")
            
            if progress_callback:
                progress_callback(10.0)
            
            # 检测姿态
            keypoints, confidence = self._detect_pose(image)
            
            if progress_callback:
                progress_callback(70.0)
            
            # 绘制结果
            result_image = self._draw_pose(image.copy(), keypoints, confidence)
            
            # 保存结果
            cv2.imwrite(str(output_path), result_image)
            
            # 保存关键点数据
            json_path = output_path.with_suffix('.json')
            self._save_keypoints(json_path, keypoints, confidence)
            
            if progress_callback:
                progress_callback(100.0)
            
            return {
                "type": "image",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "keypoints_path": str(json_path),
                "keypoints": keypoints.tolist() if keypoints is not None else [],
                "confidence": confidence.tolist() if confidence is not None else [],
                "num_persons": len(keypoints) if keypoints is not None else 0
            }
            
        except Exception as e:
            self.logger.error(f"图片处理失败: {e}")
            raise
    
    def _process_video(self, input_path: Path, output_path: Path,
                      progress_callback: Optional[Callable[[float], None]] = None,
                      **kwargs) -> Dict[str, Any]:
        """处理视频"""
        try:
            # 打开视频
            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                raise ValueError(f"无法打开视频: {input_path}")
            
            # 获取视频信息
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            
            # 处理每一帧
            frame_results = []
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 检测姿态
                keypoints, confidence = self._detect_pose(frame)
                
                # 绘制结果
                result_frame = self._draw_pose(frame.copy(), keypoints, confidence)
                out.write(result_frame)
                
                # 保存帧结果
                frame_results.append({
                    "frame": frame_count,
                    "keypoints": keypoints.tolist() if keypoints is not None else [],
                    "confidence": confidence.tolist() if confidence is not None else [],
                    "num_persons": len(keypoints) if keypoints is not None else 0
                })
                
                frame_count += 1
                
                # 更新进度
                if progress_callback and total_frames > 0:
                    progress = (frame_count / total_frames) * 100
                    progress_callback(progress)
            
            # 释放资源
            cap.release()
            out.release()
            
            # 保存关键点数据
            json_path = output_path.with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "video_info": {
                        "fps": fps,
                        "width": width,
                        "height": height,
                        "total_frames": total_frames
                    },
                    "frames": frame_results
                }, f, indent=2, ensure_ascii=False)
            
            return {
                "type": "video",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "keypoints_path": str(json_path),
                "total_frames": total_frames,
                "fps": fps,
                "resolution": [width, height]
            }
            
        except Exception as e:
            self.logger.error(f"视频处理失败: {e}")
            raise
    
    def _detect_pose(self, image: np.ndarray) -> tuple:
        """检测姿态"""
        try:
            # 获取参数
            net_resolution = self.config.get("net_resolution", "368x368")
            confidence_threshold = self.config.get("confidence_threshold", 0.1)
            
            # 解析网络分辨率
            net_width, net_height = map(int, net_resolution.split('x'))
            
            # 预处理
            blob = cv2.dnn.blobFromImage(
                image, 1.0 / 255, (net_width, net_height),
                (0, 0, 0), swapRB=False, crop=False
            )
            
            # 前向传播
            self.net.setInput(blob)
            outputs = self.net.forward()
            
            # 解析输出
            keypoints, confidence = self._parse_pose_output(
                outputs, image.shape, confidence_threshold
            )
            
            return keypoints, confidence
            
        except Exception as e:
            self.logger.error(f"姿态检测失败: {e}")
            return None, None
    
    def _parse_pose_output(self, outputs: np.ndarray, image_shape: tuple,
                          confidence_threshold: float) -> tuple:
        """解析姿态输出"""
        try:
            # 这里是简化的解析逻辑
            # 实际的OpenPose输出解析会更复杂
            height, width = image_shape[:2]
            
            # 假设检测到一个人
            num_keypoints = len(self.keypoint_names)
            keypoints = np.zeros((1, num_keypoints, 2))
            confidence = np.zeros((1, num_keypoints))
            
            # 这里应该实现真正的关键点解析逻辑
            # 由于OpenPose的输出解析比较复杂，这里只是示例
            
            return keypoints, confidence
            
        except Exception as e:
            self.logger.error(f"输出解析失败: {e}")
            return None, None
    
    def _draw_pose(self, image: np.ndarray, keypoints: np.ndarray,
                   confidence: np.ndarray) -> np.ndarray:
        """绘制姿态"""
        try:
            if keypoints is None or confidence is None:
                return image
            
            confidence_threshold = self.config.get("confidence_threshold", 0.1)
            
            # 绘制每个人的姿态
            for person_idx in range(len(keypoints)):
                person_keypoints = keypoints[person_idx]
                person_confidence = confidence[person_idx]
                
                # 绘制关键点
                for i, (x, y) in enumerate(person_keypoints):
                    if person_confidence[i] > confidence_threshold:
                        cv2.circle(image, (int(x), int(y)), 3, (0, 255, 0), -1)
                
                # 绘制骨架
                for pair in self.skeleton_pairs:
                    if len(pair) == 2:
                        idx1, idx2 = pair
                        if (idx1 < len(person_keypoints) and idx2 < len(person_keypoints) and
                            person_confidence[idx1] > confidence_threshold and
                            person_confidence[idx2] > confidence_threshold):
                            
                            pt1 = tuple(map(int, person_keypoints[idx1]))
                            pt2 = tuple(map(int, person_keypoints[idx2]))
                            cv2.line(image, pt1, pt2, (0, 0, 255), 2)
            
            return image
            
        except Exception as e:
            self.logger.error(f"绘制姿态失败: {e}")
            return image
    
    def _save_keypoints(self, json_path: Path, keypoints: np.ndarray,
                       confidence: np.ndarray):
        """保存关键点数据"""
        try:
            data = {
                "algorithm": "openpose",
                "model_type": self.config.get("model_type", "COCO"),
                "keypoint_names": self.keypoint_names,
                "skeleton_pairs": self.skeleton_pairs,
                "keypoints": keypoints.tolist() if keypoints is not None else [],
                "confidence": confidence.tolist() if confidence is not None else [],
                "num_persons": len(keypoints) if keypoints is not None else 0
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"保存关键点数据失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.net is not None:
                del self.net
                self.net = None
            super().cleanup()
        except Exception as e:
            self.logger.error(f"OpenPose资源清理失败: {e}")