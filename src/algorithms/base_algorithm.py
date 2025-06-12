# -*- coding: utf-8 -*-
"""
算法基类
为所有算法提供统一接口
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

class BaseAlgorithm(ABC):
    """算法基类"""
    
    def __init__(self, config_manager, algorithm_name: str):
        self.config_manager = config_manager
        self.algorithm_name = algorithm_name
        self.logger = logging.getLogger(f"{__name__}.{algorithm_name}")
        
        # 算法配置
        self.config = self._load_config()
        
        # 模型相关
        self.model = None
        self.model_loaded = False
        
        # 算法信息
        self.description = ""
        self.parameters = {}
        self.supported_formats = []
        self.model_path = ""
        
        # 初始化算法
        self._initialize()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载算法配置"""
        try:
            algorithm_config = self.config_manager.get(f"algorithms.{self.algorithm_name}", {})
            return algorithm_config
        except Exception as e:
            self.logger.warning(f"加载配置失败: {e}")
            return {}
    
    @abstractmethod
    def _initialize(self):
        """初始化算法（子类实现）"""
        pass
    
    @abstractmethod
    def _load_model(self) -> bool:
        """加载模型（子类实现）"""
        pass
    
    @abstractmethod
    def _process_impl(self, input_path: str, output_path: str, 
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Any:
        """算法处理实现（子类实现）"""
        pass
    
    def process(self, input_path: str, output_path: str,
                progress_callback: Optional[Callable[[float], None]] = None,
                **kwargs) -> Any:
        """处理入口"""
        try:
            # 验证输入
            if not self._validate_input(input_path):
                raise ValueError(f"无效的输入文件: {input_path}")
            
            # 确保模型已加载
            if not self.model_loaded:
                if not self._load_model():
                    raise RuntimeError("模型加载失败")
                self.model_loaded = True
            
            # 创建输出目录
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 执行处理
            self.logger.info(f"开始处理: {input_path} -> {output_path}")
            result = self._process_impl(input_path, output_path, progress_callback, **kwargs)
            
            self.logger.info(f"处理完成: {output_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
            raise
    
    def _validate_input(self, input_path: str) -> bool:
        """验证输入文件"""
        try:
            path = Path(input_path)
            if not path.exists():
                self.logger.error(f"输入文件不存在: {input_path}")
                return False
            
            if not path.is_file():
                self.logger.error(f"输入路径不是文件: {input_path}")
                return False
            
            # 检查文件格式
            if self.supported_formats:
                file_ext = path.suffix.lower()
                if file_ext not in self.supported_formats:
                    self.logger.error(f"不支持的文件格式: {file_ext}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"输入验证失败: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "name": self.algorithm_name,
            "description": self.description,
            "model_path": self.model_path,
            "model_loaded": self.model_loaded,
            "supported_formats": self.supported_formats,
            "parameters": self.parameters
        }
    
    def set_model_path(self, model_path: str):
        """设置模型路径"""
        self.model_path = model_path
        self.model_loaded = False  # 重置加载状态
    
    def unload_model(self):
        """卸载模型"""
        try:
            if self.model is not None:
                del self.model
                self.model = None
            self.model_loaded = False
            self.logger.info("模型已卸载")
        except Exception as e:
            self.logger.error(f"卸载模型失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            self.unload_model()
            self.logger.info("算法资源清理完成")
        except Exception as e:
            self.logger.error(f"算法资源清理失败: {e}")

class Pose2DAlgorithm(BaseAlgorithm):
    """2D姿态估计算法基类"""
    
    def __init__(self, config_manager, algorithm_name: str):
        super().__init__(config_manager, algorithm_name)
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.jpg', '.png', '.jpeg']
    
    @abstractmethod
    def _process_impl(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """2D姿态估计处理实现"""
        pass
    
    def get_keypoints_format(self) -> Dict[str, Any]:
        """获取关键点格式说明"""
        return {
            "format": "COCO-17",  # 默认格式
            "keypoints": [
                "nose", "left_eye", "right_eye", "left_ear", "right_ear",
                "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
                "left_wrist", "right_wrist", "left_hip", "right_hip",
                "left_knee", "right_knee", "left_ankle", "right_ankle"
            ],
            "skeleton": [
                [16, 14], [14, 12], [17, 15], [15, 13], [12, 13],
                [6, 12], [7, 13], [6, 7], [6, 8], [7, 9],
                [8, 10], [9, 11], [2, 3], [1, 2], [1, 3],
                [2, 4], [3, 5], [4, 6], [5, 7]
            ]
        }

class Pose3DAlgorithm(BaseAlgorithm):
    """3D姿态估计算法基类"""
    
    def __init__(self, config_manager, algorithm_name: str):
        super().__init__(config_manager, algorithm_name)
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv']
    
    @abstractmethod
    def _process_impl(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """3D姿态估计处理实现"""
        pass
    
    def get_keypoints_format(self) -> Dict[str, Any]:
        """获取3D关键点格式说明"""
        return {
            "format": "Human3.6M",  # 默认格式
            "keypoints": [
                "hip", "right_hip", "right_knee", "right_foot",
                "left_hip", "left_knee", "left_foot", "spine",
                "thorax", "neck", "head", "left_shoulder",
                "left_elbow", "left_wrist", "right_shoulder",
                "right_elbow", "right_wrist"
            ],
            "dimensions": 3  # x, y, z
        }

class VideoDescriptionAlgorithm(BaseAlgorithm):
    """视频描述算法基类"""
    
    def __init__(self, config_manager, algorithm_name: str):
        super().__init__(config_manager, algorithm_name)
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv']
    
    @abstractmethod
    def _process_impl(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """视频描述处理实现"""
        pass
    
    def get_description_format(self) -> Dict[str, Any]:
        """获取描述格式说明"""
        return {
            "format": "text",
            "encoding": "utf-8",
            "fields": [
                "timestamp",
                "description",
                "confidence",
                "objects",
                "actions"
            ]
        }