#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能镜像管理器
实现网络检测、镜像切换、缓存管理等功能
"""

import os
import sys
import time
import json
import yaml
import shutil
import hashlib
import requests
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 设置标准输出编码为UTF-8
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

class MirrorManager:
    """智能镜像管理器"""
    
    def __init__(self, config_file: str = None):
        # 使用项目根目录的 cache_config.txt 配置文件
        if config_file is None:
            # 从当前文件位置计算到项目根目录: ../../../../../../..
            project_root = Path(__file__).parent.parent.parent.parent.parent.parent.parent
            self.config_file = project_root / "cache_config.txt"
        else:
            self.config_file = config_file
        self.config = self._load_config()
        self.cache_path = self._get_cache_path()
        self.min_free_space = 20 * 1024 * 1024 * 1024  # 20GB
        
    def _load_config(self) -> Dict:
        """从 cache_config.txt 文件加载镜像配置"""
        # 默认配置
        config = {
            # HuggingFace 官方地址
            "huggingface": {
                "name": "HuggingFace官方",
                "base_url": "https://huggingface.co",
                "model_url": "https://huggingface.co/Lin-Chen/ShareGPT4V-7B",
                "priority": 1
            },
            
            # HF-Mirror 镜像
            "hf_mirror": {
                "name": "HF-Mirror镜像",
                "base_url": "https://hf-mirror.com",
                "model_url": "https://hf-mirror.com/Lin-Chen/sharegpt4video-8b/tree/main",
                "priority": 2
            },
            
            # 用户自定义镜像
            "custom_mirrors": [],
            
            # 网络检测配置
            "network_config": {
                "timeout": 10,
                "max_retries": 3,
                "ping_count": 3
            },
            
            # 缓存配置
            "cache_config": {
                "enable_verification": True,
                "enable_resume": True,
                "chunk_size": 8192
            }
        }
        
        # 从 cache_config.txt 文件读取配置
        if os.path.exists(self.config_file):
            try:
                cache_config = self._parse_cache_config()
                
                # 更新网络配置
                if 'connection_timeout' in cache_config:
                    config['network_config']['timeout'] = int(cache_config['connection_timeout'])
                
                # 更新镜像站点配置
                if 'official_site' in cache_config:
                    config['huggingface']['base_url'] = cache_config['official_site']
                
                if 'mirror_sites' in cache_config and cache_config['mirror_sites']:
                    mirror_sites = [site.strip() for site in cache_config['mirror_sites'].split(',') if site.strip()]
                    
                    # 根据镜像站点更新配置
                    for i, site in enumerate(mirror_sites):
                        if 'hf-mirror.com' in site:
                            config['hf_mirror']['base_url'] = site
                            config['hf_mirror']['priority'] = i + 2
                
                # 处理自定义镜像
                if 'custom_mirrors' in cache_config and cache_config['custom_mirrors']:
                    custom_sites = [site.strip() for site in cache_config['custom_mirrors'].split(',') if site.strip()]
                    config['custom_mirrors'] = [{
                        'name': f'自定义镜像{i+1}',
                        'base_url': site,
                        'priority': 10 + i
                    } for i, site in enumerate(custom_sites)]
                
            except Exception as e:
                logger.warning(f"解析 cache_config.txt 失败，使用默认配置: {e}")
        
        return config
    
    def _parse_cache_config(self) -> Dict[str, str]:
        """解析 cache_config.txt 文件"""
        config = {}
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue
                
                # 解析键值对
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
        
        return config
    

    
    def _get_cache_path(self) -> str:
        """获取缓存路径"""
        # 1. 优先使用环境变量
        cache_path = os.environ.get('HF_HOME')
        if not cache_path:
            cache_path = os.environ.get('TRANSFORMERS_CACHE')
        
        # 2. 从 cache_config.txt 文件读取
        if not cache_path:
            try:
                cache_config = self._parse_cache_config()
                cache_path = cache_config.get('cache_path')
            except Exception as e:
                logger.warning(f"读取缓存配置失败: {e}")
        
        # 3. 使用默认路径
        if not cache_path:
            cache_path = os.path.join(os.path.expanduser('~'), '.cache', 'huggingface')
        
        return cache_path
    

    
    def check_network_connectivity(self) -> Dict[str, Dict]:
        """检查网络连接性和延迟"""
        print("\n🌐 开始网络连接检测...")
        results = {}
        
        # 获取所有镜像站点
        mirrors = {
            'huggingface': self.config['huggingface'],
            'hf_mirror': self.config['hf_mirror']
        }
        
        # 添加用户自定义镜像
        for custom in self.config.get('custom_mirrors', []):
            mirrors[custom['name']] = custom
        
        for mirror_name, mirror_info in mirrors.items():
            print(f"\n📡 检测 {mirror_info['name']}...")
            result = self._test_mirror_connectivity(mirror_info)
            results[mirror_name] = result
            
            if result['accessible']:
                print(f"✅ {mirror_info['name']} - 延迟: {result['latency']:.2f}ms")
            else:
                print(f"❌ {mirror_info['name']} - 连接失败: {result['error']}")
        
        return results
    
    def _test_mirror_connectivity(self, mirror_info: Dict) -> Dict:
        """测试单个镜像的连接性"""
        base_url = mirror_info['base_url']
        timeout = self.config['network_config']['timeout']
        
        result = {
            'accessible': False,
            'latency': float('inf'),
            'error': None
        }
        
        try:
            # 使用ping测试延迟
            latency = self._ping_host(base_url)
            if latency is not None:
                result['latency'] = latency
            
            # HTTP连接测试
            start_time = time.time()
            response = requests.get(base_url, timeout=timeout, allow_redirects=True)
            end_time = time.time()
            
            if response.status_code == 200:
                result['accessible'] = True
                if result['latency'] == float('inf'):
                    result['latency'] = (end_time - start_time) * 1000
            else:
                result['error'] = f"HTTP {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            result['error'] = "连接失败，请检查网络或启用代理"
        except requests.exceptions.Timeout:
            result['error'] = "连接超时，请检查网络状况"
        except Exception as e:
            result['error'] = f"未知错误: {str(e)}"
        
        return result
    
    def _ping_host(self, url: str) -> Optional[float]:
        """Ping主机获取延迟"""
        try:
            parsed = urlparse(url)
            host = parsed.netloc
            
            # Windows系统使用ping命令
            if sys.platform.startswith('win'):
                cmd = ['ping', '-n', '3', host]
            else:
                cmd = ['ping', '-c', '3', host]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # 解析ping结果获取平均延迟
                output = result.stdout
                if sys.platform.startswith('win'):
                    # Windows ping输出解析
                    lines = output.split('\n')
                    for line in lines:
                        if 'Average' in line or '平均' in line:
                            # 提取延迟数值
                            import re
                            match = re.search(r'(\d+)ms', line)
                            if match:
                                return float(match.group(1))
                else:
                    # Linux/Mac ping输出解析
                    import re
                    match = re.search(r'avg = ([\d.]+)', output)
                    if match:
                        return float(match.group(1))
            
        except Exception:
            pass
        
        return None
    
    def select_best_mirror(self, connectivity_results: Dict[str, Dict]) -> Optional[str]:
        """选择最佳镜像"""
        print("\n🎯 选择最佳镜像站点...")
        
        # 过滤可访问的镜像
        accessible_mirrors = {
            name: result for name, result in connectivity_results.items()
            if result['accessible']
        }
        
        if not accessible_mirrors:
            print("❌ 所有镜像站点都无法访问，请检查网络连接或启用代理")
            return None
        
        # 按延迟排序选择最佳镜像
        best_mirror = min(accessible_mirrors.items(), key=lambda x: x[1]['latency'])
        mirror_name = best_mirror[0]
        latency = best_mirror[1]['latency']
        
        mirror_info = self._get_mirror_info(mirror_name)
        print(f"🚀 选择最佳镜像: {mirror_info['name']} (延迟: {latency:.2f}ms)")
        
        return mirror_name
    
    def _get_mirror_info(self, mirror_name: str) -> Dict:
        """获取镜像信息"""
        if mirror_name in ['huggingface', 'modelscope', 'hf_mirror']:
            return self.config[mirror_name]
        
        # 查找自定义镜像
        for custom in self.config.get('custom_mirrors', []):
            if custom['name'] == mirror_name:
                return custom
        
        return {}
    
    def check_cache_space(self) -> bool:
        """检查缓存空间是否足够"""
        print(f"\n💾 检查缓存空间: {self.cache_path}")
        
        try:
            # 确保缓存目录存在
            os.makedirs(self.cache_path, exist_ok=True)
            
            # 获取可用空间
            if sys.platform.startswith('win'):
                free_bytes = shutil.disk_usage(self.cache_path).free
            else:
                stat = os.statvfs(self.cache_path)
                free_bytes = stat.f_bavail * stat.f_frsize
            
            free_gb = free_bytes / (1024 ** 3)
            required_gb = self.min_free_space / (1024 ** 3)
            
            print(f"可用空间: {free_gb:.2f}GB")
            print(f"所需空间: {required_gb:.2f}GB")
            
            if free_bytes >= self.min_free_space:
                print("✅ 缓存空间充足")
                return True
            else:
                print(f"❌ 缓存空间不足，需要至少 {required_gb:.2f}GB")
                return False
                
        except Exception as e:
            logger.error(f"检查缓存空间失败: {e}")
            return False
    
    def check_model_cache_integrity(self, model_path: str) -> bool:
        """检查模型缓存完整性"""
        print(f"\n🔍 检查模型缓存完整性: {model_path}")
        
        try:
            # 检查模型目录是否存在
            if not os.path.exists(model_path):
                print("❌ 模型缓存目录不存在")
                return False
            
            # 检查必要的模型文件
            required_files = [
                'config.json',
                'tokenizer.json',
                'tokenizer_config.json'
            ]
            
            # 检查是否有模型权重文件
            model_files = []
            for file in os.listdir(model_path):
                if file.endswith(('.bin', '.safetensors')):
                    model_files.append(file)
            
            if not model_files:
                print("❌ 未找到模型权重文件")
                return False
            
            # 检查必要配置文件
            missing_files = []
            for file in required_files:
                file_path = os.path.join(model_path, file)
                if not os.path.exists(file_path):
                    missing_files.append(file)
            
            if missing_files:
                print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
                return False
            
            print("✅ 模型缓存完整")
            return True
            
        except Exception as e:
            logger.error(f"检查模型缓存完整性失败: {e}")
            return False
    
    def setup_mirror_environment(self, mirror_name: str) -> bool:
        """设置镜像环境变量"""
        print(f"\n⚙️ 配置镜像环境: {mirror_name}")
        
        mirror_info = self._get_mirror_info(mirror_name)
        if not mirror_info:
            print(f"❌ 未找到镜像配置: {mirror_name}")
            return False
        
        try:
            if mirror_name == 'hf_mirror':
                # HF-Mirror配置
                os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
                os.environ['HUGGINGFACE_HUB_CACHE'] = self.cache_path
                print("✅ 已配置HF-Mirror镜像环境")
                
            else:
                # HuggingFace官方或自定义镜像
                if 'HF_ENDPOINT' in os.environ:
                    del os.environ['HF_ENDPOINT']
                os.environ['HUGGINGFACE_HUB_CACHE'] = self.cache_path
                print("✅ 已配置HuggingFace官方环境")
            
            return True
            
        except Exception as e:
            logger.error(f"配置镜像环境失败: {e}")
            return False
    
    def clean_corrupted_cache(self, model_path: str) -> bool:
        """清理损坏的缓存文件"""
        print(f"\n🧹 清理损坏的缓存: {model_path}")
        
        try:
            if os.path.exists(model_path):
                # 备份重要配置文件
                config_files = ['config.json', 'tokenizer_config.json']
                backup_dir = f"{model_path}_backup_{int(time.time())}"
                
                for config_file in config_files:
                    config_path = os.path.join(model_path, config_file)
                    if os.path.exists(config_path):
                        os.makedirs(backup_dir, exist_ok=True)
                        shutil.copy2(config_path, backup_dir)
                
                # 删除损坏的缓存
                shutil.rmtree(model_path)
                print(f"✅ 已清理损坏缓存，配置文件备份至: {backup_dir}")
            
            return True
            
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            return False
    
    def initialize_smart_mirror(self) -> bool:
        """初始化智能镜像系统"""
        print("\n🚀 初始化智能镜像管理系统...")
        
        try:
            # 1. 检查缓存空间
            if not self.check_cache_space():
                return False
            
            # 2. 网络连接检测
            connectivity_results = self.check_network_connectivity()
            
            # 3. 选择最佳镜像
            best_mirror = self.select_best_mirror(connectivity_results)
            if not best_mirror:
                return False
            
            # 4. 配置镜像环境
            if not self.setup_mirror_environment(best_mirror):
                return False
            
            print("\n✅ 智能镜像系统初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化智能镜像系统失败: {e}")
            return False
    
    def get_download_progress_callback(self):
        """获取下载进度回调函数"""
        def progress_callback(downloaded: int, total: int):
            if total > 0:
                percent = (downloaded / total) * 100
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                print(f"\r📥 下载进度: {percent:.1f}% ({downloaded_mb:.1f}MB/{total_mb:.1f}MB)", end="")
            else:
                downloaded_mb = downloaded / (1024 * 1024)
                print(f"\r📥 已下载: {downloaded_mb:.1f}MB", end="")
        
        return progress_callback
    


# 全局镜像管理器实例
_mirror_manager = None

def get_mirror_manager() -> MirrorManager:
    """获取全局镜像管理器实例"""
    global _mirror_manager
    if _mirror_manager is None:
        _mirror_manager = MirrorManager()
    return _mirror_manager

def initialize_mirrors() -> bool:
    """初始化镜像系统（兼容性函数）"""
    manager = get_mirror_manager()
    return manager.initialize_smart_mirror()

def check_model_cache(model_path: str) -> bool:
    """检查模型缓存（兼容性函数）"""
    manager = get_mirror_manager()
    return manager.check_model_cache_integrity(model_path)

if __name__ == "__main__":
    # 测试镜像管理器
    manager = MirrorManager()
    success = manager.initialize_smart_mirror()
    if success:
        print("\n✅ 镜像管理器初始化成功")
        print("💡 提示: 您可以通过编辑项目根目录的 cache_config.txt 文件来修改镜像配置")
    else:
        print("\n❌ 镜像管理器初始化失败")