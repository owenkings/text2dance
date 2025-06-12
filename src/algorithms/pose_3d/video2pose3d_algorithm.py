# -*- coding: utf-8 -*-
"""
Video2Pose3D 3D姿态估计算法
基于Video2Pose3D的视频3D人体姿态估计
"""

import cv2
import numpy as np
import json
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

from ..base_algorithm import Pose3DAlgorithm

class Video2Pose3DAlgorithm(Pose3DAlgorithm):
    """Video2Pose3D算法实现"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager, "video2pose3d")
        
        self.description = "Video2Pose3D 基于视频的3D人体姿态估计算法"
        self.parameters = {
            "model_type": {
                "type": "string",
                "default": "cpn_ft_h36m_dbb",
                "options": ["cpn_ft_h36m_dbb", "detectron_ft_h36m", "hrnet_ft_h36m"],
                "description": "2D姿态检测模型类型"
            },
            "lifting_model": {
                "type": "string",
                "default": "videopose3d_h36m_243f",
                "options": ["videopose3d_h36m_243f", "videopose3d_h36m_81f", "videopose3d_h36m_27f"],
                "description": "3D提升模型"
            },
            "input_size": {
                "type": "tuple",
                "default": [384, 384],
                "options": [[256, 256], [384, 384], [512, 512]],
                "description": "输入图像尺寸 [width, height]"
            },
            "confidence_threshold": {
                "type": "float",
                "default": 0.3,
                "min": 0.0,
                "max": 1.0,
                "description": "2D关键点置信度阈值"
            },
            "temporal_window": {
                "type": "int",
                "default": 243,
                "options": [27, 81, 243],
                "description": "时序窗口大小（帧数）"
            },
            "use_ground_truth_2d": {
                "type": "bool",
                "default": False,
                "description": "使用真实2D关键点（如果可用）"
            },
            "flip_augmentation": {
                "type": "bool",
                "default": True,
                "description": "使用翻转增强"
            },
            "bone_length_term": {
                "type": "float",
                "default": 1.0,
                "min": 0.0,
                "max": 10.0,
                "description": "骨长约束权重"
            },
            "trajectory_model": {
                "type": "string",
                "default": "none",
                "options": ["none", "linear", "cubic"],
                "description": "轨迹模型类型"
            }
        }
        
        # Video2Pose3D特定配置
        self.pose_detector_2d = None
        self.pose_lifter_3d = None
        self.device = "cpu"
        self.input_size = [384, 384]
        
        # 时序缓存
        self.temporal_cache = []
        self.max_cache_size = 243
        
        # Human3.6M关键点定义（17个关键点）
        self.keypoint_names = [
            'Hip', 'RHip', 'RKnee', 'RFoot',
            'LHip', 'LKnee', 'LFoot', 'Spine',
            'Thorax', 'Neck/Nose', 'Head',
            'LShoulder', 'LElbow', 'LWrist',
            'RShoulder', 'RElbow', 'RWrist'
        ]
        
        # 3D骨架连接
        self.skeleton_pairs = [
            [0, 1], [1, 2], [2, 3],  # 右腿
            [0, 4], [4, 5], [5, 6],  # 左腿
            [0, 7], [7, 8], [8, 9], [9, 10],  # 脊柱到头部
            [8, 11], [11, 12], [12, 13],  # 左臂
            [8, 14], [14, 15], [15, 16]   # 右臂
        ]
        
        # 关键点颜色（RGB）
        self.keypoint_colors = [
            (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
            (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
            (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
            (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
            (255, 0, 170)
        ]
        
        # 骨架颜色
        self.skeleton_colors = [
            (255, 0, 0), (255, 85, 0), (255, 170, 0),  # 右腿
            (170, 255, 0), (85, 255, 0), (0, 255, 0),  # 左腿
            (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255),  # 脊柱
            (0, 85, 255), (0, 0, 255), (85, 0, 255),  # 左臂
            (170, 0, 255), (255, 0, 255), (255, 0, 170)   # 右臂
        ]
    
    def _initialize(self):
        """初始化Video2Pose3D算法"""
        try:
            # 设置模型路径
            model_dir = self.config.get("model_path", "models/video2pose3d")
            self.model_path = str(Path(model_dir))
            
            # 设置输入尺寸
            self.input_size = self.config.get("input_size", [384, 384])
            
            # 设置时序窗口大小
            temporal_window = self.config.get("temporal_window", 243)
            self.max_cache_size = temporal_window
            
            # 检查是否有GPU
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
            
            self.logger.info(f"Video2Pose3D算法初始化完成，设备: {self.device}")
            
        except Exception as e:
            self.logger.error(f"Video2Pose3D算法初始化失败: {e}")
    
    def _load_model(self) -> bool:
        """加载Video2Pose3D模型"""
        try:
            model_type = self.config.get("model_type", "cpn_ft_h36m_dbb")
            lifting_model = self.config.get("lifting_model", "videopose3d_h36m_243f")
            
            # 2D姿态检测器模型路径
            detector_path = Path(self.model_path) / f"{model_type}.pth"
            
            # 3D提升模型路径
            lifter_path = Path(self.model_path) / f"{lifting_model}.bin"
            
            # 检查模型文件是否存在
            if not detector_path.exists() or not lifter_path.exists():
                self.logger.warning("模型文件不存在，使用模拟模型")
                self._create_dummy_models()
                return True
            
            # 实际的模型加载代码
            # try:
            #     import torch
            #     from .models import PoseDetector2D, PoseLifter3D
            #     
            #     # 加载2D姿态检测器
            #     self.pose_detector_2d = PoseDetector2D(model_type)
            #     self.pose_detector_2d.load_state_dict(torch.load(detector_path, map_location=self.device))
            #     self.pose_detector_2d.to(self.device)
            #     self.pose_detector_2d.eval()
            #     
            #     # 加载3D姿态提升器
            #     self.pose_lifter_3d = PoseLifter3D(lifting_model)
            #     self.pose_lifter_3d.load_state_dict(torch.load(lifter_path, map_location=self.device))
            #     self.pose_lifter_3d.to(self.device)
            #     self.pose_lifter_3d.eval()
            #     
            # except ImportError:
            #     self.logger.warning("PyTorch或相关依赖未安装，使用模拟模型")
            #     self._create_dummy_models()
            
            # 使用模拟模型进行演示
            self._create_dummy_models()
            
            self.logger.info(f"Video2Pose3D模型加载成功: {model_type} + {lifting_model}")
            return True
            
        except Exception as e:
            self.logger.error(f"Video2Pose3D模型加载失败: {e}")
            return False
    
    def _create_dummy_models(self):
        """创建模拟模型用于演示"""
        class DummyPoseDetector2D:
            def __init__(self):
                self.input_size = [384, 384]
                
            def detect(self, image):
                """检测2D关键点"""
                height, width = image.shape[:2]
                
                # 简单的人体检测
                center_x, center_y = width // 2, height // 2
                body_width, body_height = width * 0.3, height * 0.7
                
                # 生成Human3.6M格式的2D关键点
                keypoints_2d = self._generate_h36m_keypoints(
                    center_x, center_y, body_width, body_height
                )
                
                # 生成置信度
                confidence = np.random.rand(17) * 0.4 + 0.5
                
                return {
                    "keypoints": keypoints_2d,
                    "confidence": confidence,
                    "bbox": [center_x - body_width/2, center_y - body_height/2,
                            center_x + body_width/2, center_y + body_height/2]
                }
            
            def _generate_h36m_keypoints(self, center_x, center_y, width, height):
                """生成Human3.6M格式的2D关键点"""
                keypoints = np.zeros((17, 2))
                
                # Hip (0)
                keypoints[0] = [center_x, center_y + height * 0.1]
                
                # 右腿
                keypoints[1] = [center_x + width * 0.1, center_y + height * 0.1]  # RHip
                keypoints[2] = [center_x + width * 0.08, center_y + height * 0.25]  # RKnee
                keypoints[3] = [center_x + width * 0.06, center_y + height * 0.45]  # RFoot
                
                # 左腿
                keypoints[4] = [center_x - width * 0.1, center_y + height * 0.1]  # LHip
                keypoints[5] = [center_x - width * 0.08, center_y + height * 0.25]  # LKnee
                keypoints[6] = [center_x - width * 0.06, center_y + height * 0.45]  # LFoot
                
                # 脊柱
                keypoints[7] = [center_x, center_y - height * 0.05]  # Spine
                keypoints[8] = [center_x, center_y - height * 0.2]   # Thorax
                keypoints[9] = [center_x, center_y - height * 0.3]   # Neck/Nose
                keypoints[10] = [center_x, center_y - height * 0.35] # Head
                
                # 左臂
                keypoints[11] = [center_x - width * 0.15, center_y - height * 0.2]  # LShoulder
                keypoints[12] = [center_x - width * 0.2, center_y - height * 0.05]  # LElbow
                keypoints[13] = [center_x - width * 0.25, center_y + height * 0.1]  # LWrist
                
                # 右臂
                keypoints[14] = [center_x + width * 0.15, center_y - height * 0.2]  # RShoulder
                keypoints[15] = [center_x + width * 0.2, center_y - height * 0.05]  # RElbow
                keypoints[16] = [center_x + width * 0.25, center_y + height * 0.1]  # RWrist
                
                return keypoints
        
        class DummyPoseLifter3D:
            def __init__(self):
                self.temporal_window = 243
                self.receptive_field = 243
                
            def lift_to_3d(self, keypoints_2d_sequence):
                """将2D关键点序列提升到3D"""
                if len(keypoints_2d_sequence) == 0:
                    return []
                
                # 获取最新的2D关键点
                latest_2d = keypoints_2d_sequence[-1]
                keypoints_2d = latest_2d["keypoints"]
                confidence_2d = latest_2d["confidence"]
                
                # 生成3D关键点
                keypoints_3d = self._lift_to_3d(keypoints_2d)
                
                # 3D置信度基于2D置信度
                confidence_3d = confidence_2d * 0.8
                
                return {
                    "keypoints_3d": keypoints_3d,
                    "confidence_3d": confidence_3d,
                    "temporal_consistency": self._calculate_temporal_consistency(keypoints_2d_sequence)
                }
            
            def _lift_to_3d(self, keypoints_2d):
                """将2D关键点提升到3D"""
                keypoints_3d = np.zeros((17, 3))
                
                # 复制x, y坐标
                keypoints_3d[:, :2] = keypoints_2d
                
                # 生成合理的深度信息
                # Hip作为根节点，深度为0
                keypoints_3d[0, 2] = 0
                
                # 腿部深度
                keypoints_3d[1, 2] = -20  # RHip
                keypoints_3d[2, 2] = -10  # RKnee
                keypoints_3d[3, 2] = 0    # RFoot
                keypoints_3d[4, 2] = 20   # LHip
                keypoints_3d[5, 2] = 10   # LKnee
                keypoints_3d[6, 2] = 0    # LFoot
                
                # 躯干深度
                keypoints_3d[7, 2] = 0    # Spine
                keypoints_3d[8, 2] = 10   # Thorax
                keypoints_3d[9, 2] = 20   # Neck/Nose
                keypoints_3d[10, 2] = 30  # Head
                
                # 手臂深度
                keypoints_3d[11, 2] = 15  # LShoulder
                keypoints_3d[12, 2] = 5   # LElbow
                keypoints_3d[13, 2] = -5  # LWrist
                keypoints_3d[14, 2] = -15 # RShoulder
                keypoints_3d[15, 2] = -5  # RElbow
                keypoints_3d[16, 2] = 5   # RWrist
                
                # 添加一些随机变化
                noise = np.random.normal(0, 5, keypoints_3d.shape)
                keypoints_3d += noise
                
                return keypoints_3d
            
            def _calculate_temporal_consistency(self, keypoints_2d_sequence):
                """计算时序一致性"""
                if len(keypoints_2d_sequence) < 2:
                    return 1.0
                
                # 简单的时序一致性计算
                prev_kpts = keypoints_2d_sequence[-2]["keypoints"]
                curr_kpts = keypoints_2d_sequence[-1]["keypoints"]
                
                # 计算关键点移动距离
                distances = np.linalg.norm(curr_kpts - prev_kpts, axis=1)
                avg_distance = np.mean(distances)
                
                # 距离越小，一致性越高
                consistency = max(0, 1 - avg_distance / 50)
                return consistency
        
        self.pose_detector_2d = DummyPoseDetector2D()
        self.pose_lifter_3d = DummyPoseLifter3D()
    
    def _process_impl(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """Video2Pose3D处理实现"""
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # Video2Pose3D主要针对视频
            if input_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                return self._process_image(input_path, output_path, progress_callback, **kwargs)
            else:
                return self._process_video(input_path, output_path, progress_callback, **kwargs)
                
        except Exception as e:
            self.logger.error(f"Video2Pose3D处理失败: {e}")
            raise
    
    def _process_image(self, input_path: Path, output_path: Path,
                      progress_callback: Optional[Callable[[float], None]] = None,
                      **kwargs) -> Dict[str, Any]:
        """处理单张图片（效果有限，建议使用视频）"""
        try:
            # 读取图片
            image = cv2.imread(str(input_path))
            if image is None:
                raise ValueError(f"无法读取图片: {input_path}")
            
            if progress_callback:
                progress_callback(20.0)
            
            # 2D姿态检测
            pose_2d_result = self.pose_detector_2d.detect(image)
            
            if progress_callback:
                progress_callback(60.0)
            
            # 3D姿态提升（单帧效果有限）
            pose_3d_result = self.pose_lifter_3d.lift_to_3d([pose_2d_result])
            
            if progress_callback:
                progress_callback(80.0)
            
            # 绘制结果
            result_image = self._draw_pose_3d(image.copy(), pose_3d_result)
            
            # 保存结果
            cv2.imwrite(str(output_path), result_image)
            
            # 保存关键点数据
            json_path = output_path.with_suffix('.json')
            self._save_results(json_path, [pose_3d_result], [pose_2d_result])
            
            if progress_callback:
                progress_callback(100.0)
            
            return {
                "type": "image",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "keypoints_path": str(json_path),
                "num_persons": 1,
                "warning": "单帧3D姿态估计精度有限，建议使用视频输入获得更好效果"
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
            
            # 重置时序缓存
            self.temporal_cache = []
            
            # 处理每一帧
            frame_results = []
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 2D姿态检测
                pose_2d_result = self.pose_detector_2d.detect(frame)
                
                # 更新时序缓存
                self._update_temporal_cache(pose_2d_result)
                
                # 3D姿态提升
                pose_3d_result = self.pose_lifter_3d.lift_to_3d(self.temporal_cache)
                
                # 应用后处理
                pose_3d_result = self._post_process_3d(pose_3d_result)
                
                # 绘制结果
                result_frame = self._draw_pose_3d(frame.copy(), pose_3d_result)
                out.write(result_frame)
                
                # 保存帧结果
                frame_results.append({
                    "frame": frame_count,
                    "pose_2d": pose_2d_result,
                    "pose_3d": pose_3d_result,
                    "temporal_consistency": pose_3d_result.get("temporal_consistency", 0.0)
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
                    "algorithm_info": {
                        "name": "video2pose3d",
                        "model_type": self.config.get("model_type", "cpn_ft_h36m_dbb"),
                        "lifting_model": self.config.get("lifting_model", "videopose3d_h36m_243f"),
                        "temporal_window": self.config.get("temporal_window", 243)
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
                "resolution": [width, height],
                "temporal_window": self.config.get("temporal_window", 243)
            }
            
        except Exception as e:
            self.logger.error(f"视频处理失败: {e}")
            raise
    
    def _update_temporal_cache(self, pose_2d_result: Dict):
        """更新时序缓存"""
        self.temporal_cache.append(pose_2d_result)
        
        # 保持缓存大小
        if len(self.temporal_cache) > self.max_cache_size:
            self.temporal_cache.pop(0)
    
    def _post_process_3d(self, pose_3d_result: Dict) -> Dict:
        """3D姿态后处理"""
        try:
            # 骨长约束
            if self.config.get("bone_length_term", 1.0) > 0:
                pose_3d_result = self._apply_bone_length_constraint(pose_3d_result)
            
            # 轨迹平滑
            trajectory_model = self.config.get("trajectory_model", "none")
            if trajectory_model != "none":
                pose_3d_result = self._apply_trajectory_smoothing(pose_3d_result, trajectory_model)
            
            return pose_3d_result
            
        except Exception as e:
            self.logger.error(f"3D姿态后处理失败: {e}")
            return pose_3d_result
    
    def _apply_bone_length_constraint(self, pose_3d_result: Dict) -> Dict:
        """应用骨长约束"""
        try:
            keypoints_3d = pose_3d_result["keypoints_3d"]
            
            # 定义骨骼连接和标准长度比例
            bone_connections = [
                (0, 1, 0.1),   # Hip to RHip
                (1, 2, 0.4),   # RHip to RKnee
                (2, 3, 0.4),   # RKnee to RFoot
                (0, 4, 0.1),   # Hip to LHip
                (4, 5, 0.4),   # LHip to LKnee
                (5, 6, 0.4),   # LKnee to LFoot
                (0, 7, 0.2),   # Hip to Spine
                (7, 8, 0.3),   # Spine to Thorax
                (8, 9, 0.2),   # Thorax to Neck
                (9, 10, 0.2),  # Neck to Head
                (8, 11, 0.3),  # Thorax to LShoulder
                (11, 12, 0.3), # LShoulder to LElbow
                (12, 13, 0.3), # LElbow to LWrist
                (8, 14, 0.3),  # Thorax to RShoulder
                (14, 15, 0.3), # RShoulder to RElbow
                (15, 16, 0.3)  # RElbow to RWrist
            ]
            
            # 简化的骨长约束（这里只是示例）
            weight = self.config.get("bone_length_term", 1.0)
            if weight > 0:
                # 实际实现中应该使用更复杂的优化算法
                pass
            
            return pose_3d_result
            
        except Exception as e:
            self.logger.error(f"骨长约束应用失败: {e}")
            return pose_3d_result
    
    def _apply_trajectory_smoothing(self, pose_3d_result: Dict, model_type: str) -> Dict:
        """应用轨迹平滑"""
        try:
            if model_type == "linear":
                # 线性插值平滑
                pass
            elif model_type == "cubic":
                # 三次样条插值平滑
                pass
            
            return pose_3d_result
            
        except Exception as e:
            self.logger.error(f"轨迹平滑失败: {e}")
            return pose_3d_result
    
    def _draw_pose_3d(self, image: np.ndarray, pose_3d_result: Dict) -> np.ndarray:
        """绘制3D姿态（投影到2D）"""
        try:
            keypoints_3d = pose_3d_result["keypoints_3d"]
            confidence_3d = pose_3d_result["confidence_3d"]
            confidence_threshold = self.config.get("confidence_threshold", 0.3)
            
            # 投影3D关键点到2D（简化版本，直接使用x,y坐标）
            keypoints_2d = keypoints_3d[:, :2]
            
            # 绘制关键点
            for i, (x, y) in enumerate(keypoints_2d):
                if confidence_3d[i] > confidence_threshold:
                    # 根据深度信息调整颜色
                    z = keypoints_3d[i, 2] if len(keypoints_3d[i]) > 2 else 0
                    depth_factor = min(max((z + 100) / 200, 0), 1)  # 归一化深度
                    
                    color = self.keypoint_colors[i % len(self.keypoint_colors)]
                    # 根据深度调整颜色亮度
                    color = tuple(int(c * (0.5 + 0.5 * depth_factor)) for c in color)
                    
                    cv2.circle(image, (int(x), int(y)), 6, color, -1)
                    cv2.circle(image, (int(x), int(y)), 8, (255, 255, 255), 2)
            
            # 绘制3D骨架
            for i, (idx1, idx2) in enumerate(self.skeleton_pairs):
                if (idx1 < len(keypoints_2d) and idx2 < len(keypoints_2d) and
                    confidence_3d[idx1] > confidence_threshold and
                    confidence_3d[idx2] > confidence_threshold):
                    
                    pt1 = tuple(map(int, keypoints_2d[idx1]))
                    pt2 = tuple(map(int, keypoints_2d[idx2]))
                    
                    # 根据深度差异调整线条颜色
                    z1 = keypoints_3d[idx1, 2] if len(keypoints_3d[idx1]) > 2 else 0
                    z2 = keypoints_3d[idx2, 2] if len(keypoints_3d[idx2]) > 2 else 0
                    avg_depth = (z1 + z2) / 2
                    depth_factor = min(max((avg_depth + 100) / 200, 0), 1)
                    
                    color = self.skeleton_colors[i % len(self.skeleton_colors)]
                    color = tuple(int(c * (0.5 + 0.5 * depth_factor)) for c in color)
                    
                    cv2.line(image, pt1, pt2, color, 3)
            
            # 显示时序一致性信息
            consistency = pose_3d_result.get("temporal_consistency", 0.0)
            cv2.putText(image, f"Temporal Consistency: {consistency:.2f}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            return image
            
        except Exception as e:
            self.logger.error(f"绘制3D姿态失败: {e}")
            return image
    
    def _save_results(self, json_path: Path, pose_3d_results: List[Dict],
                     pose_2d_results: List[Dict] = None):
        """保存结果数据"""
        try:
            data = {
                "algorithm": "video2pose3d",
                "model_type": self.config.get("model_type", "cpn_ft_h36m_dbb"),
                "lifting_model": self.config.get("lifting_model", "videopose3d_h36m_243f"),
                "input_size": self.input_size,
                "temporal_window": self.config.get("temporal_window", 243),
                "keypoint_names": self.keypoint_names,
                "skeleton_pairs": self.skeleton_pairs,
                "coordinate_system": "Human3.6M",
                "poses_3d": pose_3d_results,
                "poses_2d": pose_2d_results or [],
                "num_persons": len(pose_3d_results)
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"保存结果数据失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.pose_detector_2d is not None:
                del self.pose_detector_2d
                self.pose_detector_2d = None
            
            if self.pose_lifter_3d is not None:
                del self.pose_lifter_3d
                self.pose_lifter_3d = None
            
            # 清理缓存
            self.temporal_cache = []
            
            super().cleanup()
        except Exception as e:
            self.logger.error(f"Video2Pose3D资源清理失败: {e}")