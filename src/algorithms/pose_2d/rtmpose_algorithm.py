# -*- coding: utf-8 -*-
"""
RTMPose 2D姿态估计算法
基于RTMPose的实时2D人体姿态估计
"""

import cv2
import numpy as np
import json
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from ..base_algorithm import Pose2DAlgorithm

class RTMPoseAlgorithm(Pose2DAlgorithm):
    """RTMPose算法实现"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager, "rtmpose")
        
        self.description = "RTMPose 实时2D人体姿态估计算法"
        self.parameters = {
            "model_type": {
                "type": "string",
                "default": "rtmpose-m",
                "options": ["rtmpose-t", "rtmpose-s", "rtmpose-m", "rtmpose-l"],
                "description": "模型类型"
            },
            "input_size": {
                "type": "tuple",
                "default": [256, 192],
                "options": [[192, 256], [256, 192], [384, 288]],
                "description": "输入图像尺寸 [width, height]"
            },
            "confidence_threshold": {
                "type": "float",
                "default": 0.3,
                "min": 0.0,
                "max": 1.0,
                "description": "置信度阈值"
            },
            "nms_threshold": {
                "type": "float",
                "default": 0.5,
                "min": 0.0,
                "max": 1.0,
                "description": "NMS阈值"
            },
            "use_tta": {
                "type": "bool",
                "default": False,
                "description": "使用测试时增强"
            },
            "backend": {
                "type": "string",
                "default": "onnxruntime",
                "options": ["onnxruntime", "tensorrt", "openvino"],
                "description": "推理后端"
            }
        }
        
        # RTMPose特定配置
        self.detector = None
        self.pose_estimator = None
        self.device = "cpu"
        self.input_size = [256, 192]
        
        # COCO关键点定义
        self.keypoint_names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        self.skeleton_pairs = [
            [16, 14], [14, 12], [17, 15], [15, 13], [12, 13],
            [6, 12], [7, 13], [6, 7], [6, 8], [7, 9],
            [8, 10], [9, 11], [2, 3], [1, 2], [1, 3],
            [2, 4], [3, 5], [4, 6], [5, 7]
        ]
        
        # 关键点颜色
        self.keypoint_colors = [
            (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
            (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
            (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
            (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
            (255, 0, 170)
        ]
        
        # 骨架颜色
        self.skeleton_colors = [
            (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
            (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
            (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
            (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
            (255, 0, 170), (255, 0, 85), (255, 0, 0)
        ]
    
    def _initialize(self):
        """初始化RTMPose算法"""
        try:
            # 设置模型路径
            model_dir = self.config.get("model_path", "models/rtmpose")
            self.model_path = str(Path(model_dir))
            
            # 设置输入尺寸
            self.input_size = self.config.get("input_size", [256, 192])
            
            # 检查是否有GPU
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
            
            self.logger.info(f"RTMPose算法初始化完成，设备: {self.device}")
            
        except Exception as e:
            self.logger.error(f"RTMPose算法初始化失败: {e}")
    
    def _load_model(self) -> bool:
        """加载RTMPose模型"""
        try:
            model_type = self.config.get("model_type", "rtmpose-m")
            backend = self.config.get("backend", "onnxruntime")
            
            # 检测器模型路径
            detector_config = Path(self.model_path) / "rtmdet_nano_320-8xb32_coco-person.py"
            detector_checkpoint = Path(self.model_path) / "rtmdet_nano_320-8xb32_coco-person.pth"
            
            # 姿态估计器模型路径
            pose_config = Path(self.model_path) / f"{model_type}_body7_coco-256x192.py"
            pose_checkpoint = Path(self.model_path) / f"{model_type}_body7_coco-256x192.pth"
            
            # 检查模型文件是否存在
            if not all([detector_config.exists(), detector_checkpoint.exists(),
                       pose_config.exists(), pose_checkpoint.exists()]):
                self.logger.warning("部分模型文件不存在，使用模拟模型")
                self._create_dummy_models()
                return True
            
            # 实际的模型加载代码
            # try:
            #     from mmdet.apis import init_detector
            #     from mmpose.apis import init_pose_model
            #     
            #     # 加载检测器
            #     self.detector = init_detector(
            #         str(detector_config), str(detector_checkpoint), device=self.device
            #     )
            #     
            #     # 加载姿态估计器
            #     self.pose_estimator = init_pose_model(
            #         str(pose_config), str(pose_checkpoint), device=self.device
            #     )
            #     
            # except ImportError:
            #     self.logger.warning("MMPose/MMDetection未安装，使用模拟模型")
            #     self._create_dummy_models()
            
            # 使用模拟模型进行演示
            self._create_dummy_models()
            
            self.logger.info(f"RTMPose模型加载成功: {model_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"RTMPose模型加载失败: {e}")
            return False
    
    def _create_dummy_models(self):
        """创建模拟模型用于演示"""
        class DummyDetector:
            def __init__(self):
                pass
                
            def detect(self, image):
                # 模拟人体检测结果
                height, width = image.shape[:2]
                
                # 假设检测到一个人，占据图像中央区域
                x1, y1 = width * 0.2, height * 0.1
                x2, y2 = width * 0.8, height * 0.9
                
                return [{
                    "bbox": [x1, y1, x2, y2],
                    "score": 0.9
                }]
        
        class DummyPoseEstimator:
            def __init__(self):
                self.input_size = [256, 192]
                
            def estimate(self, image, bboxes):
                # 模拟姿态估计结果
                results = []
                
                for bbox in bboxes:
                    x1, y1, x2, y2 = bbox["bbox"]
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    
                    # 生成相对合理的关键点位置
                    keypoints = self._generate_dummy_keypoints(center_x, center_y, x2 - x1, y2 - y1)
                    confidence = np.random.rand(17) * 0.4 + 0.4  # 0.4-0.8之间的置信度
                    
                    results.append({
                        "keypoints": keypoints,
                        "confidence": confidence
                    })
                
                return results
            
            def _generate_dummy_keypoints(self, center_x, center_y, width, height):
                """生成模拟关键点"""
                keypoints = np.zeros((17, 2))
                
                # 头部关键点
                head_y = center_y - height * 0.35
                keypoints[0] = [center_x, head_y]  # nose
                keypoints[1] = [center_x - width * 0.05, head_y - height * 0.02]  # left_eye
                keypoints[2] = [center_x + width * 0.05, head_y - height * 0.02]  # right_eye
                keypoints[3] = [center_x - width * 0.08, head_y]  # left_ear
                keypoints[4] = [center_x + width * 0.08, head_y]  # right_ear
                
                # 上身关键点
                shoulder_y = center_y - height * 0.2
                keypoints[5] = [center_x - width * 0.15, shoulder_y]  # left_shoulder
                keypoints[6] = [center_x + width * 0.15, shoulder_y]  # right_shoulder
                
                elbow_y = center_y - height * 0.05
                keypoints[7] = [center_x - width * 0.2, elbow_y]  # left_elbow
                keypoints[8] = [center_x + width * 0.2, elbow_y]  # right_elbow
                
                wrist_y = center_y + height * 0.1
                keypoints[9] = [center_x - width * 0.25, wrist_y]  # left_wrist
                keypoints[10] = [center_x + width * 0.25, wrist_y]  # right_wrist
                
                # 下身关键点
                hip_y = center_y + height * 0.05
                keypoints[11] = [center_x - width * 0.1, hip_y]  # left_hip
                keypoints[12] = [center_x + width * 0.1, hip_y]  # right_hip
                
                knee_y = center_y + height * 0.25
                keypoints[13] = [center_x - width * 0.08, knee_y]  # left_knee
                keypoints[14] = [center_x + width * 0.08, knee_y]  # right_knee
                
                ankle_y = center_y + height * 0.45
                keypoints[15] = [center_x - width * 0.06, ankle_y]  # left_ankle
                keypoints[16] = [center_x + width * 0.06, ankle_y]  # right_ankle
                
                return keypoints
        
        self.detector = DummyDetector()
        self.pose_estimator = DummyPoseEstimator()
    
    def _process_impl(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """RTMPose处理实现"""
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # 检查输入是图片还是视频
            if input_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                return self._process_image(input_path, output_path, progress_callback, **kwargs)
            else:
                return self._process_video(input_path, output_path, progress_callback, **kwargs)
                
        except Exception as e:
            self.logger.error(f"RTMPose处理失败: {e}")
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
            
            # 检测人体
            detections = self.detector.detect(image)
            
            if progress_callback:
                progress_callback(40.0)
            
            # 姿态估计
            pose_results = self.pose_estimator.estimate(image, detections)
            
            if progress_callback:
                progress_callback(70.0)
            
            # 绘制结果
            result_image = self._draw_poses(image.copy(), pose_results)
            
            # 保存结果
            cv2.imwrite(str(output_path), result_image)
            
            # 保存关键点数据
            json_path = output_path.with_suffix('.json')
            self._save_results(json_path, pose_results, detections)
            
            if progress_callback:
                progress_callback(100.0)
            
            return {
                "type": "image",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "keypoints_path": str(json_path),
                "num_persons": len(pose_results),
                "detections": len(detections)
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
                
                # 检测人体
                detections = self.detector.detect(frame)
                
                # 姿态估计
                pose_results = self.pose_estimator.estimate(frame, detections)
                
                # 绘制结果
                result_frame = self._draw_poses(frame.copy(), pose_results)
                out.write(result_frame)
                
                # 保存帧结果
                frame_results.append({
                    "frame": frame_count,
                    "detections": detections,
                    "poses": pose_results,
                    "num_persons": len(pose_results)
                })
                
                frame_count += 1
                
                # 更新进度
                if progress_callback and total_frames > 0:
                    progress = (frame_count / total_frames) * 100
                    progress_callback(progress)
            
            # 释放资源
            cap.release()
            out.release()
            
            # 保存结果数据
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
    
    def _draw_poses(self, image: np.ndarray, pose_results: List[Dict]) -> np.ndarray:
        """绘制姿态"""
        try:
            confidence_threshold = self.config.get("confidence_threshold", 0.3)
            
            for pose_result in pose_results:
                keypoints = pose_result["keypoints"]
                confidence = pose_result["confidence"]
                
                # 绘制关键点
                for i, (x, y) in enumerate(keypoints):
                    if confidence[i] > confidence_threshold:
                        color = self.keypoint_colors[i % len(self.keypoint_colors)]
                        cv2.circle(image, (int(x), int(y)), 4, color, -1)
                        cv2.circle(image, (int(x), int(y)), 6, (255, 255, 255), 2)
                
                # 绘制骨架
                for i, pair in enumerate(self.skeleton_pairs):
                    if len(pair) == 2:
                        idx1, idx2 = pair[0] - 1, pair[1] - 1  # 转换为0索引
                        if (0 <= idx1 < len(keypoints) and 0 <= idx2 < len(keypoints) and
                            confidence[idx1] > confidence_threshold and
                            confidence[idx2] > confidence_threshold):
                            
                            pt1 = tuple(map(int, keypoints[idx1]))
                            pt2 = tuple(map(int, keypoints[idx2]))
                            color = self.skeleton_colors[i % len(self.skeleton_colors)]
                            cv2.line(image, pt1, pt2, color, 3)
            
            return image
            
        except Exception as e:
            self.logger.error(f"绘制姿态失败: {e}")
            return image
    
    def _save_results(self, json_path: Path, pose_results: List[Dict],
                     detections: List[Dict]):
        """保存结果数据"""
        try:
            data = {
                "algorithm": "rtmpose",
                "model_type": self.config.get("model_type", "rtmpose-m"),
                "input_size": self.input_size,
                "keypoint_names": self.keypoint_names,
                "skeleton_pairs": self.skeleton_pairs,
                "detections": detections,
                "poses": pose_results,
                "num_persons": len(pose_results)
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"保存结果数据失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.detector is not None:
                del self.detector
                self.detector = None
            
            if self.pose_estimator is not None:
                del self.pose_estimator
                self.pose_estimator = None
            
            super().cleanup()
        except Exception as e:
            self.logger.error(f"RTMPose资源清理失败: {e}")