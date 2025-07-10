#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
警告抑制工具
用于抑制PyTorch模型加载时的常见警告信息
"""

import warnings
import os

def suppress_pytorch_warnings():
    """
    抑制PyTorch相关的常见警告
    """
    # 抑制PyTorch模型加载警告
    warnings.filterwarnings("ignore", message=".*copying from a non-meta parameter.*")
    warnings.filterwarnings("ignore", message=".*Did you mean to pass `assign=True`.*")
    
    # 抑制HuggingFace相关警告
    warnings.filterwarnings("ignore", message=".*resume_download.*deprecated.*")
    warnings.filterwarnings("ignore", message=".*Special tokens have been added.*")
    warnings.filterwarnings("ignore", message=".*cache-system uses symlinks.*")
    warnings.filterwarnings("ignore", message=".*To support symlinks on Windows.*")
    warnings.filterwarnings("ignore", message=".*Xet Storage is enabled.*")
    
    # 设置环境变量抑制特定警告
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    print("已启用警告抑制模式")

def setup_clean_environment():
    """
    设置干净的运行环境
    """
    # 抑制警告
    suppress_pytorch_warnings()
    
    # 设置日志级别
    import logging
    logging.getLogger('transformers').setLevel(logging.ERROR)
    logging.getLogger('torch').setLevel(logging.ERROR)
    
if __name__ == "__main__":
    setup_clean_environment()
    print("警告抑制设置完成")