# -*- coding: utf-8 -*-
"""
用户配置管理器
专门管理cache_config.txt格式的用户配置文件
支持程序内设置和文件直接编辑两种方式
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

class UserConfigManager:
    """用户配置管理器类 - 专门管理cache_config.txt格式的配置"""
    
    def __init__(self, config_filename: str = "cache_config.txt"):
        self.project_root = Path(__file__).parent.parent.parent
        self.config_file = self.project_root / config_filename
        self.config = {}
        self._load_config()
        self._setup_environment()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    for line in f:
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
        """创建默认配置文件 - 使用完整的标准格式"""
        # 使用程序根目录下的huggingface文件夹作为默认缓存路径
        default_cache_path = self.project_root / "huggingface"
        default_config_content = f"""# ==================== 缓存配置 ====================
# 模型文件缓存路径，用于存储下载的模型文件
# 默认为程序目录下的huggingface文件夹，可根据需要修改
cache_path={default_cache_path}
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
            print(f"✅ 已创建默认配置文件: {self.config_file}")
        except Exception as e:
            print(f"警告: 保存默认配置文件失败: {e}")
    
    def _setup_environment(self):
        """设置环境变量"""
        # 使用新的get_cache_path方法，它会自动处理空值情况
        cache_path = self.get_cache_path()
        
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
    
    def get_cache_path(self) -> str:
        """获取缓存路径，如果配置为空则返回默认路径"""
        cache_path = self.config.get('cache_path')
        if not cache_path or cache_path.strip() == '':
            # 如果配置为空，返回程序目录下的huggingface文件夹作为默认路径
            default_path = self.project_root / "huggingface"
            return str(default_path)
        return cache_path
    
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
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()
            
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
    
    def get_mirror_config(self) -> Dict[str, str]:
        """获取镜像配置"""
        return {
            'official_site': self.config.get('official_site', 'https://huggingface.co'),
            'mirror_sites': self.config.get('mirror_sites', 'https://hf-mirror.com'),
            'custom_mirrors': self.config.get('custom_mirrors', ''),
            'auto_mirror_switch': self.config.get('auto_mirror_switch', 'true')
        }
    
    def get_network_config(self) -> Dict[str, str]:
        """获取网络配置"""
        return {
            'connection_timeout': self.config.get('connection_timeout', '10'),
            'download_timeout': self.config.get('download_timeout', '300')
        }
    
    def reload_config(self):
        """重新加载配置文件（用于检测外部文件修改）"""
        self._load_config()
        self._setup_environment()
        print("✅ 配置文件已重新加载")

# 全局用户配置管理器实例
_user_config_manager = None

def get_user_config_manager() -> UserConfigManager:
    """获取全局用户配置管理器实例"""
    global _user_config_manager
    if _user_config_manager is None:
        _user_config_manager = UserConfigManager()
    return _user_config_manager

# 在模块导入时自动初始化
get_user_config_manager()