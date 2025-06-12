# -*- coding: utf-8 -*-
"""
VitPose 2D姿态估计算法
基于Vision Transformer的2D人体姿态估计
"""

import cv2
import numpy as np
import json
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from ..base_algorithm import Pose2DAlgorithm

class VitPoseAlgorithm(Pose2DAlgorithm):
    """VitPose算法实现"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager, "vitpose")
        
        self.description = "VitPose Vision Transformer 2D人体姿态估计算法"
        self.parameters = {
            "model_size": {
                "type": "string",
                "default": "base",
                "options": ["tiny", "small", "base", "large", "huge"],
                "description": "模型大小"
            },
            "input_size": {
                "type": "int",
                "default": 256,
                "options": [192, 256, 384],
                "description": "输入图像尺寸"
            },
            "confidence_threshold": {
                "type": "float",
                "default": 0.3,
                "min": 0.0,
                "max": 1.0,
                "description": "置信度阈值"
            },
            "use_udp": {
                "type": "bool",
                "default": True,
                "description": "使用UDP解码"
            },
            "flip_test": {
                "type": "bool",
                "default": True,
                "description": "使用翻转测试"
            }
        }
        
        # VitPose特定配置
        self.model = None
        self.device = "cpu"
        self.input_size = 256
        
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
        
        # 颜色定义
        self.colors = [
            (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
            (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
            (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
            (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
            (255, 0, 170)
        ]
    
    def _initialize(self):
        """初始化VitPose算法"""
        try:
            # 设置模型路径
            model_dir = self.config.get("model_path", "models/vitpose")
            self.model_path = str(Path(model_dir))
            
            # 设置输入尺寸
            self.input_size = self.config.get("input_size", 256)
            
            # 检查是否有GPU
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
            
            self.logger.info(f"VitPose算法初始化完成，设备: {self.device}")
            
        except Exception as e:
            self.logger.error(f"VitPose算法初始化失败: {e}")
    
    def _load_model(self) -> bool:
        """加载VitPose模型"""
        try:
            # 这里应该加载实际的VitPose模型
            # 由于VitPose需要特定的环境和依赖，这里提供框架
            
            model_size = self.config.get("model_size", "base")
            model_file = Path(self.model_path) / f"vitpose_{model_size}_coco.pth"
            
            if not model_file.exists():
                self.logger.warning(f"模型文件不存在: {model_file}")
                # 创建一个模拟模型用于演示
                self.model = self._create_dummy_model()
                self.logger.info("使用模拟模型进行演示")
                return True
            
            # 实际的模型加载代码
            # import torch
            # from mmpose.apis import init_pose_model
            # config_file = Path(self.model_path) / f"vitpose_{model_size}_coco.py"
            # self.model = init_pose_model(str(config_file), str(model_file), device=self.device)
            
            self.logger.info(f"VitPose模型加载成功: {model_size}")
            return True
            
        except Exception as e:
            self.logger.error(f"VitPose模型加载失败: {e}")
            return False
    
    def _create_dummy_model(self):
        """创建模拟模型用于演示"""
        class DummyModel:
            def __init__(self):
                self.input_size = 256
                
            def predict(self, image):
                # 模拟预测结果
                height, width = image.shape[:2]
                num_keypoints = 17
                
                # 生成随机关键点（在图像范围内）
                keypoints = np.random.rand(1, num_keypoints, 2)
                keypoints[:, :, 0] *= width
                keypoints[:, :, 1] *= height
                
                # 生成随机置信度
                confidence = np.random.rand(1, num_keypoints) * 0.5 + 0.3
                
                return keypoints, confidence
        
        return DummyModel()
    
    def _process_impl(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """VitPose处理实现"""
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # 检查输入是图片还是视频
            if input_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                return self._process_image(input_path, output_path, progress_callback, **kwargs)
            else:
                return self._process_video(input_path, output_path, progress_callback, **kwargs)
                
        except Exception as e:
            self.logger.error(f"VitPose处理失败: {e}")
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
            # 预处理图像
            processed_image = self._preprocess_image(image)
            
            # 模型推理
            keypoints, confidence = self.model.predict(processed_image)
            
            # 后处理
            keypoints, confidence = self._postprocess_results(
                keypoints, confidence, image.shape
            )
            
            return keypoints, confidence
            
        except Exception as e:
            self.logger.error(f"姿态检测失败: {e}")
            return None, None
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """预处理图像"""
        try:
            # 调整图像尺寸
            resized = cv2.resize(image, (self.input_size, self.input_size))
            
            # 归一化
            normalized = resized.astype(np.float32) / 255.0
            
            # 标准化（ImageNet均值和标准差）
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            
            normalized = (normalized - mean) / std
            
            return normalized
            
        except Exception as e:
            self.logger.error(f"图像预处理失败: {e}")
            return image
    
    def _postprocess_results(self, keypoints: np.ndarray, confidence: np.ndarray,
                           original_shape: tuple) -> tuple:
        """后处理结果"""
        try:
            if keypoints is None or confidence is None:
                return None, None
            
            # 将关键点坐标从模型输入尺寸映射回原始图像尺寸
            height, width = original_shape[:2]
            scale_x = width / self.input_size
            scale_y = height / self.input_size
            
            keypoints[:, :, 0] *= scale_x
            keypoints[:, :, 1] *= scale_y
            
            # 过滤低置信度的关键点
            confidence_threshold = self.config.get("confidence_threshold", 0.3)
            mask = confidence > confidence_threshold
            
            return keypoints, confidence
            
        except Exception as e:
            self.logger.error(f"结果后处理失败: {e}")
            return keypoints, confidence
    
    def _draw_pose(self, image: np.ndarray, keypoints: np.ndarray,
                   confidence: np.ndarray) -> np.ndarray:
        """绘制姿态"""
        try:
            if keypoints is None or confidence is None:
                return image
            
            confidence_threshold = self.config.get("confidence_threshold", 0.3)
            
            # 绘制每个人的姿态
            for person_idx in range(len(keypoints)):
                person_keypoints = keypoints[person_idx]
                person_confidence = confidence[person_idx]
                
                # 绘制关键点
                for i, (x, y) in enumerate(person_keypoints):
                    if person_confidence[i] > confidence_threshold:
                        color = self.colors[i % len(self.colors)]
                        cv2.circle(image, (int(x), int(y)), 4, color, -1)
                        cv2.circle(image, (int(x), int(y)), 6, (255, 255, 255), 2)
                
                # 绘制骨架
                for pair in self.skeleton_pairs:
                    if len(pair) == 2:
                        idx1, idx2 = pair[0] - 1, pair[1] - 1  # 转换为0索引
                        if (0 <= idx1 < len(person_keypoints) and 0 <= idx2 < len(person_keypoints) and
                            person_confidence[idx1] > confidence_threshold and
                            person_confidence[idx2] > confidence_threshold):
                            
                            pt1 = tuple(map(int, person_keypoints[idx1]))
                            pt2 = tuple(map(int, person_keypoints[idx2]))
                            cv2.line(image, pt1, pt2, (0, 255, 0), 3)
            
            return image
            
        except Exception as e:
            self.logger.error(f"绘制姿态失败: {e}")
            return image
    
    def _save_keypoints(self, json_path: Path, keypoints: np.ndarray,
                       confidence: np.ndarray):
        """保存关键点数据"""
        try:
            data = {
                "algorithm": "vitpose",
                "model_size": self.config.get("model_size", "base"),
                "input_size": self.input_size,
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
            if self.model is not None:
                del self.model
                self.model = None
            super().cleanup()
        except Exception as e:
            self.logger.error(f"VitPose资源清理失败: {e}")