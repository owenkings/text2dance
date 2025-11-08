# -*- coding: utf-8 -*-
"""
配置管理器
负责统一管理项目的所有配置项，包括缓存路径、API配置、镜像配置等
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

class ConfigManager:
    """配置管理器类 - 统一管理项目配置"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.config_file = self.project_root / "cache_config.txt"
        self.config = {}
        self._load_config()
        self._setup_environment()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self.config_file.exists():
                # 尝试多种编码方式读取文件
                encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin1']
                content = None
                
                for encoding in encodings:
                    try:
                        with open(self.config_file, 'r', encoding=encoding) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
                
                if content is None:
                    print(f"警告: 无法读取配置文件 {self.config_file}，使用默认配置")
                    self._create_default_config()
                    return
                
                # 解析配置内容
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        self.config[key.strip()] = value.strip()
            else:
                # 创建默认配置
                self._create_default_config()
        except Exception as e:
            print(f"警告: 加载配置文件失败: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置文件"""
        # 使用当前配置文件的完整格式作为默认配置
        default_config_content = """# ==================== 缓存配置 ====================
# 模型文件缓存路径，用于存储下载的模型文件
cache_path=E:\\Tiany\\huggingface
# 最小可用空间要求（GB），下载前检查磁盘空间
min_free_space_gb=20

# ==================== 模型配置 ====================
# ShareGPT4Video模型路径标识符
sharegpt4video_model_path=Lin-Chen/sharegpt4video-8b

# ==================== 网络配置 ====================
# 网络连接超时时间（秒）
connection_timeout=10
# 下载超时时间（秒）
download_timeout=300
# 启用自动镜像切换
auto_mirror_switch=true

# ==================== 镜像站点配置 ====================
# HuggingFace官方站点
official_site=https://huggingface.co
# 镜像站点列表（按优先级排序，用逗号分隔）
mirror_sites=https://hf-mirror.com
# 用户自定义镜像站点（可选，用逗号分隔）
custom_mirrors=

# ==================== 用户自定义API配置 ====================
# 自定义视频描述API模型配置（程序内置火山大模型①，用户可添加自定义模型供选择）
# 自定义API模型名称（将在界面中显示，如：我的GPT模型）
custom_api_model_name=
# 自定义API端点
custom_api_endpoint=https://ark.cn-beijing.volces.com/api/v3/chat/completions
# 自定义API密钥
custom_api_key=fa1f2df2-73f8-44b1-99a0-09834047ab51
# 自定义API模型标识
custom_api_model=doubao-1.5-vision-pro-250328

# 动作过滤API配置（程序内置默认配置，用户填写后覆盖内置配置）
# 动作过滤API端点
action_filter_api_endpoint=
# 动作过滤API密钥
action_filter_api_key=
# 动作过滤API模型名称
action_filter_api_model=

# ==================== 扩展API配置 ====================
# 扩展API配置示例（用户可根据需要添加更多自定义视频描述API模型）
# 格式：custom_api_model_name_N=模型显示名称
#       custom_api_endpoint_N=端点URL
#       custom_api_key_N=API密钥
#       custom_api_model_N=模型标识
# 示例：
# custom_api_model_name_2=我的GPT模型
# custom_api_endpoint_2=https://api.openai.com/v1/chat/completions
# custom_api_key_2=your_openai_api_key
# custom_api_model_2=gpt-4-vision-preview
"""
        
        # 保存默认配置到文件
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.write(default_config_content)
            # 重新加载配置
            self._load_config()
        except Exception as e:
            print(f"警告: 保存默认配置文件失败: {e}")
    
    def _setup_environment(self):
        """设置环境变量"""
        cache_path = self.config.get('cache_path')
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
        return self.config.get('cache_path')
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: str):
        """设置配置项"""
        self.config[key] = value
        self._save_config()
    
    def update_config(self, config_dict: Dict[str, str]):
        """批量更新配置项"""
        self.config.update(config_dict)
        self._save_config()
    
    def _save_config(self):
        """保存配置到文件 - 保持原有格式和注释"""
        try:
            # 读取现有文件内容，保持注释和格式
            existing_lines = []
            if self.config_file.exists():
                # 尝试多种编码方式读取文件
                encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin1']
                
                for encoding in encodings:
                    try:
                        with open(self.config_file, 'r', encoding=encoding) as f:
                            existing_lines = f.readlines()
                        break
                    except UnicodeDecodeError:
                        continue
            
            # 更新配置值，保持原有格式
            updated_lines = []
            for line in existing_lines:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#') and '=' in stripped_line:
                    key = stripped_line.split('=', 1)[0].strip()
                    if key in self.config:
                        # 更新配置值，保持原有的缩进和格式
                        indent = len(line) - len(line.lstrip())
                        updated_lines.append(' ' * indent + f"{key}={self.config[key]}\n")
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)
            
            # 写回文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
                
        except Exception as e:
            print(f"警告: 保存配置文件失败: {e}")
    
    def get_api_config(self, api_type: str = 'custom') -> Dict[str, str]:
        """获取API配置"""
        if api_type == 'custom':
            return {
                'endpoint': self.config.get('custom_api_endpoint', ''),
                'key': self.config.get('custom_api_key', ''),
                'model': self.config.get('custom_api_model', ''),
                'name': self.config.get('custom_api_model_name', '')
            }
        elif api_type == 'action_filter':
            return {
                'endpoint': self.config.get('action_filter_api_endpoint', ''),
                'key': self.config.get('action_filter_api_key', ''),
                'model': self.config.get('action_filter_api_model', '')
            }
        return {}
    
    def set_api_config(self, api_type: str, config_dict: Dict[str, str]):
        """设置API配置"""
        if api_type == 'custom':
            if 'endpoint' in config_dict:
                self.config['custom_api_endpoint'] = config_dict['endpoint']
            if 'key' in config_dict:
                self.config['custom_api_key'] = config_dict['key']
            if 'model' in config_dict:
                self.config['custom_api_model'] = config_dict['model']
            if 'name' in config_dict:
                self.config['custom_api_model_name'] = config_dict['name']
        elif api_type == 'action_filter':
            if 'endpoint' in config_dict:
                self.config['action_filter_api_endpoint'] = config_dict['endpoint']
            if 'key' in config_dict:
                self.config['action_filter_api_key'] = config_dict['key']
            if 'model' in config_dict:
                self.config['action_filter_api_model'] = config_dict['model']
        
        self._save_config()
    
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

# 全局配置管理器实例
_config_manager = None

def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

# 保持向后兼容性的别名
def get_cache_manager() -> ConfigManager:
    """获取全局配置管理器实例（向后兼容）"""
    return get_config_manager()

# 在模块导入时自动初始化
get_config_manager()