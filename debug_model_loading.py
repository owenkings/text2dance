#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型加载调试脚本
用于诊断ShareGPT4Video模型加载失败的具体原因
"""

import os
import sys
import traceback
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "algorithms" / "video_description" / "ShareGPT4Video"))

def test_basic_imports():
    """测试基础导入"""
    print("=== 测试基础导入 ===")
    try:
        import torch
        print(f"✅ PyTorch版本: {torch.__version__}")
        print(f"✅ CUDA可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✅ CUDA版本: {torch.version.cuda}")
            print(f"✅ GPU数量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"   GPU {i}: {props.name}, 显存: {props.total_memory / 1024**3:.1f}GB")
    except Exception as e:
        print(f"❌ PyTorch导入失败: {e}")
        return False
    
    try:
        from transformers import AutoTokenizer, AutoConfig
        print("✅ Transformers导入成功")
    except Exception as e:
        print(f"❌ Transformers导入失败: {e}")
        return False
    
    return True

def test_cache_config():
    """测试缓存配置"""
    print("\n=== 测试缓存配置 ===")
    cache_config_path = project_root / "cache_config.txt"
    
    if not cache_config_path.exists():
        print(f"❌ 配置文件不存在: {cache_config_path}")
        return None, None
    
    cache_path = None
    model_path = None
    
    try:
        with open(cache_config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key, value = key.strip(), value.strip()
                    if key == 'cache_path':
                        cache_path = value
                    elif key == 'sharegpt4video_model_path':
                        model_path = value
        
        print(f"✅ 缓存路径: {cache_path}")
        print(f"✅ 模型路径: {model_path}")
        
        # 检查缓存路径是否存在
        if cache_path and os.path.exists(cache_path):
            print(f"✅ 缓存目录存在")
            # 检查是否有写入权限
            test_file = os.path.join(cache_path, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                print(f"✅ 缓存目录可写")
            except Exception as e:
                print(f"❌ 缓存目录不可写: {e}")
        else:
            print(f"❌ 缓存目录不存在: {cache_path}")
            
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return None, None
    
    return cache_path, model_path

def test_model_loading(cache_path, model_path):
    """测试模型加载"""
    print("\n=== 测试模型加载 ===")
    
    if not cache_path or not model_path:
        print("❌ 缺少必要的配置信息")
        return False
    
    # 设置环境变量
    os.environ["HF_HOME"] = cache_path
    os.environ["HUGGINGFACE_HUB_CACHE"] = cache_path
    os.environ["TRANSFORMERS_CACHE"] = cache_path
    print(f"✅ 设置缓存环境变量: {cache_path}")
    
    try:
        # 导入ShareGPT4Video相关模块
        from src.algorithms.video_description.ShareGPT4Video.llava.model.builder import load_pretrained_model
        from src.algorithms.video_description.ShareGPT4Video.run import get_model_name_from_path
        print("✅ ShareGPT4Video模块导入成功")
        
        # 获取模型名称
        model_name = get_model_name_from_path(model_path)
        print(f"✅ 模型名称: {model_name}")
        
        # 尝试加载模型（使用CPU模式避免GPU内存问题）
        print("开始加载模型（CPU模式）...")
        tokenizer, model, processor, context_len = load_pretrained_model(
            model_path=model_path,
            model_base=None,
            model_name=model_name,
            device_map="cpu",
            device="cpu"
        )
        
        print("✅ 模型加载成功！")
        print(f"✅ 上下文长度: {context_len}")
        print(f"✅ 分词器类型: {type(tokenizer).__name__}")
        print(f"✅ 模型类型: {type(model).__name__}")
        print(f"✅ 处理器类型: {type(processor).__name__ if processor else 'None'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        print("详细错误信息:")
        traceback.print_exc()
        return False

def test_network_connectivity():
    """测试网络连接"""
    print("\n=== 测试网络连接 ===")
    try:
        import requests
        response = requests.get("https://huggingface.co", timeout=10)
        if response.status_code == 200:
            print("✅ Hugging Face网站可访问")
        else:
            print(f"⚠️ Hugging Face网站返回状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 网络连接测试失败: {e}")
        print("建议检查网络连接或使用代理")

def main():
    """主函数"""
    print("ShareGPT4Video模型加载诊断工具")
    print("=" * 50)
    
    # 测试基础导入
    if not test_basic_imports():
        print("\n❌ 基础环境检查失败，请先安装必要的依赖")
        return
    
    # 测试网络连接
    test_network_connectivity()
    
    # 测试缓存配置
    cache_path, model_path = test_cache_config()
    
    # 测试模型加载
    if test_model_loading(cache_path, model_path):
        print("\n🎉 所有测试通过！模型应该可以正常使用。")
    else:
        print("\n❌ 模型加载测试失败。")
        print("\n可能的解决方案:")
        print("1. 检查网络连接，确保可以访问Hugging Face")
        print("2. 清理缓存目录，重新下载模型")
        print("3. 检查磁盘空间是否充足")
        print("4. 尝试使用代理或镜像站点")
        print("5. 检查防火墙设置")

if __name__ == "__main__":
    main()