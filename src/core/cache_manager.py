# -*- coding: utf-8 -*-
"""
缓存管理器
负责统一管理各种AI库的缓存路径配置
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

class CacheManager:
    """缓存管理器类"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.config_file = self.project_root / "cache_config.txt"
        self.cache_config = {}
        self._load_config()
        self._setup_environment()
    
    def _load_config(self):
        """加载缓存配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self.cache_config[key.strip()] = value.strip()
            else:
                # 创建默认配置
                self._create_default_config()
        except Exception as e:
            print(f"警告: 加载缓存配置失败: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认缓存配置"""
        default_cache_path = self.project_root / "model"
        self.cache_config = {
            'cache_path': str(default_cache_path),
            'sharegpt4video_model_path': 'Lin-Chen/sharegpt4video-8b',
            'api_endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
            'api_key': 'fa1f2df2-73f8-44b1-99a0-09834047ab51',
            'api_model': 'doubao-1.5-vision-pro-250328'
        }
        
        # 保存默认配置到文件
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write("# 格式：每行一个配置项，使用 key=value 的形式\n")
                for key, value in self.cache_config.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            print(f"警告: 保存默认缓存配置失败: {e}")
    
    def _setup_environment(self):
        """设置环境变量"""
        cache_path = self.cache_config.get('cache_path')
        if cache_path:
            # 确保缓存目录存在
            cache_dir = Path(cache_path)
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                # 测试目录是否可写
                test_file = cache_dir / ".test_write"
                test_file.write_text("test")
                test_file.unlink()
                
                # 设置HuggingFace相关环境变量
                os.environ['HF_HOME'] = str(cache_dir)
                os.environ['HUGGINGFACE_HUB_CACHE'] = str(cache_dir / 'hub')
                os.environ['TRANSFORMERS_CACHE'] = str(cache_dir / 'transformers')
                
                # 设置其他常用AI库的缓存路径
                os.environ['TORCH_HOME'] = str(cache_dir / 'torch')
                os.environ['TORCH_HUB'] = str(cache_dir / 'torch' / 'hub')
                
                print(f"✅ 缓存路径已设置为: {cache_path}")
                
            except Exception as e:
                print(f"⚠️ 缓存目录设置失败: {e}")
                print(f"将使用系统默认缓存路径")
    
    def get_cache_path(self) -> Optional[str]:
        """获取缓存路径"""
        return self.cache_config.get('cache_path')
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.cache_config.get(key, default)
    
    def set_config(self, key: str, value: str):
        """设置配置项"""
        self.cache_config[key] = value
        self._save_config()
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write("# 格式：每行一个配置项，使用 key=value 的形式\n")
                for key, value in self.cache_config.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            print(f"警告: 保存缓存配置失败: {e}")
    
    def clear_cache(self, cache_type: str = 'all'):
        """清理缓存"""
        cache_path = Path(self.get_cache_path() or '')
        if not cache_path.exists():
            print("缓存目录不存在")
            return
        
        try:
            if cache_type == 'all' or cache_type == 'huggingface':
                hf_cache = cache_path / 'hub'
                if hf_cache.exists():
                    import shutil
                    shutil.rmtree(hf_cache)
                    print("✅ HuggingFace缓存已清理")
            
            if cache_type == 'all' or cache_type == 'torch':
                torch_cache = cache_path / 'torch'
                if torch_cache.exists():
                    import shutil
                    shutil.rmtree(torch_cache)
                    print("✅ PyTorch缓存已清理")
                    
        except Exception as e:
            print(f"清理缓存失败: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        cache_path = Path(self.get_cache_path() or '')
        info = {
            'cache_path': str(cache_path),
            'exists': cache_path.exists(),
            'writable': False,
            'size': 0,
            'subdirs': []
        }
        
        if cache_path.exists():
            try:
                # 测试可写性
                test_file = cache_path / ".test_write"
                test_file.write_text("test")
                test_file.unlink()
                info['writable'] = True
                
                # 计算大小
                total_size = 0
                for item in cache_path.rglob('*'):
                    if item.is_file():
                        total_size += item.stat().st_size
                info['size'] = total_size
                
                # 获取子目录
                info['subdirs'] = [d.name for d in cache_path.iterdir() if d.is_dir()]
                
            except Exception as e:
                print(f"获取缓存信息失败: {e}")
        
        return info

# 全局缓存管理器实例
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

# 在模块导入时自动初始化
get_cache_manager()