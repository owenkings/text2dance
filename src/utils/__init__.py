"""工具模块

提供各种实用工具函数和类。
"""

__version__ = "4.0.0"
__author__ = "Your Name"

# 导入常用工具
try:
    from .logger import Logger
except ImportError:
    # 如果logger模块不存在，提供一个简单的替代
    import logging
    
    class Logger:
        """简单的日志记录器"""
        
        def __init__(self):
            self._logger = logging.getLogger(__name__)
            
        def get_logger(self, name: str = None):
            """获取日志记录器"""
            if name:
                return logging.getLogger(name)
            return self._logger

# 导出主要组件
__all__ = [
    'Logger',
]