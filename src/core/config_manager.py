# -*- coding: utf-8 -*-
"""
配置管理器
负责整个应用程序的配置管理
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger
from PyQt5.QtCore import QObject, pyqtSignal


class ConfigManager(QObject):
    """配置管理器类"""
    
    # 配置变更信号
    config_changed = pyqtSignal(dict)
    
    def __init__(self, config_file: str = "config.yaml"):
        super().__init__()
        self.config_file = Path(config_file)
        self.config_data: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
                logger.info(f"配置文件加载成功: {self.config_file}")
            else:
                logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
                self._create_default_config()
            return True
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            self._create_default_config()
            return False
    
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
            logger.info(f"配置文件保存成功: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"配置文件保存失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键，支持点分隔的嵌套键，如 'app.name'
            default: 默认值
        
        Returns:
            配置值
        """
        try:
            keys = key.split('.')
            value = self.config_data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
        except Exception:
            return default
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值
        
        Args:
            key: 配置键，支持点分隔的嵌套键
            value: 配置值
        """
        try:
            keys = key.split('.')
            config = self.config_data
            
            # 创建嵌套字典结构
            for k in keys[:-1]:
                if k not in config or not isinstance(config[k], dict):
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
            logger.debug(f"设置配置: {key} = {value}")
            
            # 发射配置变更信号
            self.config_changed.emit(self.config_data)
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
    
    def has(self, key: str) -> bool:
        """检查配置键是否存在"""
        return self.get(key) is not None
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置段"""
        return self.get(section, {})
    
    def get_config(self, section: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取配置段（兼容方法）"""
        if default is None:
            default = {}
        result = self.get(section, default)
        # 确保返回的是字典类型
        if not isinstance(result, dict):
            return default
        return result
    
    def update_section(self, section: str, data: Dict[str, Any]) -> None:
        """更新配置段"""
        current = self.get_section(section)
        current.update(data)
        self.set(section, current)
    
    def _create_default_config(self) -> None:
        """创建默认配置"""
        self.config_data = {
            'app': {
                'name': 'VideoProcessor',
                'version': '4.1.1',
                'debug': True,
                'log_level': 'INFO'
            },
            'ui': {
                'theme': 'dark',
                'language': 'zh_CN',
                'window': {
                    'width': 1200,
                    'height': 800,
                    'resizable': True
                }
            },
            'crawler': {
                'download_path': './downloads',
                'max_concurrent': 3,
                'timeout': 30
            },
            'video_processing': {
                'temp_path': './temp',
                'output_path': './output'
            },
            'algorithms': {
                'pose_2d': {
                    'default': 'openpose',
                    'models_path': './models/pose_2d'
                },
                'pose_3d': {
                    'default': 'rtmpose3d',
                    'models_path': './models/pose_3d'
                },
                'video_description': {
                    'device': 'CUDA',  # 默认使用CUDA
                    'models_path': './models/video_description'
                }
            },
            'plugins': {
                'enabled': True,
                'plugins_path': './plugins'
            }
        }
        logger.info("创建默认配置")
    
    def reload(self) -> bool:
        """重新加载配置"""
        return self.load_config()
    
    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self._create_default_config()
        self.save_config()
        logger.info("配置已重置为默认值")