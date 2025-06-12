# -*- coding: utf-8 -*-
"""
插件管理器
实现可扩展的插件系统
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
from abc import ABC, abstractmethod
from loguru import logger


class PluginInterface(ABC):
    """插件接口基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        pass
    
    @abstractmethod
    def initialize(self, config_manager) -> bool:
        """初始化插件"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """清理插件资源"""
        pass
    
    def get_menu_items(self) -> List[Dict[str, Any]]:
        """获取插件菜单项
        
        Returns:
            菜单项列表，格式: [{'name': '菜单名', 'callback': 回调函数}]
        """
        return []
    
    def get_toolbar_items(self) -> List[Dict[str, Any]]:
        """获取插件工具栏项
        
        Returns:
            工具栏项列表，格式: [{'name': '按钮名', 'icon': '图标', 'callback': 回调函数}]
        """
        return []


class CrawlerPlugin(PluginInterface):
    """爬虫插件基类"""
    
    @abstractmethod
    def get_supported_sites(self) -> List[str]:
        """获取支持的网站列表"""
        pass
    
    @abstractmethod
    def download_video(self, url: str, output_path: str, **kwargs) -> bool:
        """下载视频"""
        pass
    
    @abstractmethod
    def search_videos(self, keyword: str, **kwargs) -> List[Dict[str, Any]]:
        """搜索视频"""
        pass


class AlgorithmPlugin(PluginInterface):
    """算法插件基类"""
    
    @property
    @abstractmethod
    def algorithm_type(self) -> str:
        """算法类型: pose_2d, pose_3d, video_description"""
        pass
    
    @abstractmethod
    def load_model(self, model_path: str) -> bool:
        """加载模型"""
        pass
    
    @abstractmethod
    def process(self, input_data: Any, **kwargs) -> Any:
        """处理数据"""
        pass


class VideoProcessingPlugin(PluginInterface):
    """视频处理插件基类"""
    
    @abstractmethod
    def get_supported_operations(self) -> List[str]:
        """获取支持的操作列表"""
        pass
    
    @abstractmethod
    def process_video(self, input_path: str, output_path: str, operation: str, **kwargs) -> bool:
        """处理视频"""
        pass


class PluginManager:
    """插件管理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.plugins: Dict[str, PluginInterface] = {}
        self.plugin_types: Dict[str, List[PluginInterface]] = {
            'crawler': [],
            'algorithm': [],
            'video_processing': [],
            'general': []
        }
        self.plugins_path = Path(config_manager.get('plugins.plugins_path', './plugins'))
        
        if config_manager.get('plugins.auto_load', True):
            self.load_all_plugins()
    
    def load_all_plugins(self) -> None:
        """加载所有插件"""
        if not self.plugins_path.exists():
            logger.warning(f"插件目录不存在: {self.plugins_path}")
            return
        
        logger.info(f"开始加载插件，目录: {self.plugins_path}")
        
        for plugin_file in self.plugins_path.glob("*.py"):
            if plugin_file.name.startswith('_'):
                continue
            
            try:
                self.load_plugin(plugin_file)
            except Exception as e:
                logger.error(f"加载插件失败 {plugin_file}: {e}")
        
        logger.info(f"插件加载完成，共加载 {len(self.plugins)} 个插件")
    
    def load_plugin(self, plugin_path: Path) -> bool:
        """加载单个插件"""
        try:
            # 动态导入插件模块
            spec = importlib.util.spec_from_file_location(
                plugin_path.stem, plugin_path
            )
            if spec is None or spec.loader is None:
                logger.error(f"无法创建插件规范: {plugin_path}")
                return False
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, PluginInterface) and 
                    attr != PluginInterface and
                    not attr.__name__.endswith('Plugin')):
                    plugin_class = attr
                    break
            
            if plugin_class is None:
                logger.warning(f"插件文件中未找到有效的插件类: {plugin_path}")
                return False
            
            # 实例化插件
            plugin_instance = plugin_class()
            
            # 初始化插件
            if not plugin_instance.initialize(self.config_manager):
                logger.error(f"插件初始化失败: {plugin_instance.name}")
                return False
            
            # 注册插件
            self.register_plugin(plugin_instance)
            
            logger.info(f"插件加载成功: {plugin_instance.name} v{plugin_instance.version}")
            return True
            
        except Exception as e:
            logger.error(f"加载插件异常 {plugin_path}: {e}")
            return False
    
    def register_plugin(self, plugin: PluginInterface) -> None:
        """注册插件"""
        self.plugins[plugin.name] = plugin
        
        # 按类型分类
        if isinstance(plugin, CrawlerPlugin):
            self.plugin_types['crawler'].append(plugin)
        elif isinstance(plugin, AlgorithmPlugin):
            self.plugin_types['algorithm'].append(plugin)
        elif isinstance(plugin, VideoProcessingPlugin):
            self.plugin_types['video_processing'].append(plugin)
        else:
            self.plugin_types['general'].append(plugin)
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """注销插件"""
        if plugin_name not in self.plugins:
            return False
        
        plugin = self.plugins[plugin_name]
        
        # 清理插件
        try:
            plugin.cleanup()
        except Exception as e:
            logger.error(f"插件清理失败 {plugin_name}: {e}")
        
        # 从分类中移除
        for plugin_list in self.plugin_types.values():
            if plugin in plugin_list:
                plugin_list.remove(plugin)
        
        # 从主字典中移除
        del self.plugins[plugin_name]
        
        logger.info(f"插件已注销: {plugin_name}")
        return True
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """获取插件实例"""
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: str) -> List[PluginInterface]:
        """按类型获取插件列表"""
        return self.plugin_types.get(plugin_type, [])
    
    def get_all_plugins(self) -> Dict[str, PluginInterface]:
        """获取所有插件"""
        return self.plugins.copy()
    
    def get_crawler_plugins(self) -> List[CrawlerPlugin]:
        """获取爬虫插件"""
        return [p for p in self.plugin_types['crawler'] if isinstance(p, CrawlerPlugin)]
    
    def get_algorithm_plugins(self, algorithm_type: str = None) -> List[AlgorithmPlugin]:
        """获取算法插件"""
        plugins = [p for p in self.plugin_types['algorithm'] if isinstance(p, AlgorithmPlugin)]
        if algorithm_type:
            plugins = [p for p in plugins if p.algorithm_type == algorithm_type]
        return plugins
    
    def get_video_processing_plugins(self) -> List[VideoProcessingPlugin]:
        """获取视频处理插件"""
        return [p for p in self.plugin_types['video_processing'] if isinstance(p, VideoProcessingPlugin)]
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """重新加载插件"""
        if plugin_name not in self.plugins:
            return False
        
        # 获取插件文件路径
        plugin_file = self.plugins_path / f"{plugin_name}.py"
        if not plugin_file.exists():
            logger.error(f"插件文件不存在: {plugin_file}")
            return False
        
        # 注销旧插件
        self.unregister_plugin(plugin_name)
        
        # 重新加载
        return self.load_plugin(plugin_file)
    
    def cleanup(self) -> None:
        """清理所有插件"""
        logger.info("开始清理插件")
        
        for plugin_name in list(self.plugins.keys()):
            self.unregister_plugin(plugin_name)
        
        logger.info("插件清理完成")
    
    def get_plugin_info(self) -> List[Dict[str, Any]]:
        """获取插件信息列表"""
        info_list = []
        for plugin in self.plugins.values():
            info = {
                'name': plugin.name,
                'version': plugin.version,
                'description': plugin.description,
                'type': self._get_plugin_type(plugin)
            }
            info_list.append(info)
        return info_list
    
    def _get_plugin_type(self, plugin: PluginInterface) -> str:
        """获取插件类型"""
        if isinstance(plugin, CrawlerPlugin):
            return 'crawler'
        elif isinstance(plugin, AlgorithmPlugin):
            return 'algorithm'
        elif isinstance(plugin, VideoProcessingPlugin):
            return 'video_processing'
        else:
            return 'general'