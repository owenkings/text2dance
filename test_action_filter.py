#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动作描述过滤功能
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from src.gui.video_description_widget import VideoDescriptionThread

def test_action_filter():
    """测试动作描述过滤功能"""
    
    # 模拟API配置
    api_config = {
        'api_endpoint': 'https://api.openai.com/v1/chat/completions',
        'api_key': 'your-api-key-here',  # 需要替换为真实的API密钥
        'api_model': 'gpt-3.5-turbo'
    }
    
    # 创建测试线程实例
    thread = VideoDescriptionThread(
        videos=[],
        description_requirement="",
        model_path="",
        use_action_filter=True,
        api_config=api_config
    )
    
    # 测试描述文本
    test_description = """
    在这个视频中，一个穿着蓝色T恤和黑色牛仔裤的年轻男子站在明亮的客厅里。
    他正在做一系列的舞蹈动作：首先他举起双臂过头顶，然后向左转身，
    接着做了一个跳跃动作，落地时双脚分开。随后他弯腰触地，
    然后快速起身并向右摆动手臂。整个过程中，背景可以看到沙发和电视。
    """
    
    print("原始描述:")
    print(test_description)
    print("\n" + "="*50 + "\n")
    
    # 测试过滤功能
    filtered_description = thread._filter_action_description(test_description)
    
    print("过滤后的描述:")
    print(filtered_description)
    
    # 检查配置
    print("\n" + "="*50 + "\n")
    print("API配置检查:")
    if not api_config.get('api_endpoint'):
        print("❌ API端点未配置")
    else:
        print(f"✅ API端点: {api_config.get('api_endpoint')}")
    
    if not api_config.get('api_key') or api_config.get('api_key') == 'your-api-key-here':
        print("❌ API密钥未配置或为默认值")
    else:
        print("✅ API密钥已配置")
    
    if not api_config.get('api_model'):
        print("❌ API模型未配置")
    else:
        print(f"✅ API模型: {api_config.get('api_model')}")

def check_cache_config():
    """检查cache_config.txt文件中的API配置"""
    
    cache_config_path = os.path.join(os.path.dirname(__file__), 'cache_config.txt')
    
    print("检查cache_config.txt文件:")
    print(f"文件路径: {cache_config_path}")
    
    if not os.path.exists(cache_config_path):
        print("❌ cache_config.txt文件不存在")
        return
    
    print("✅ cache_config.txt文件存在")
    
    try:
        config_data = {}
        with open(cache_config_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config_data[key] = value
        
        print("\n配置内容:")
        for key, value in config_data.items():
            if 'api' in key.lower():
                if key == 'api_key' and value:
                    print(f"  {key}: {'*' * len(value)}")
                else:
                    print(f"  {key}: {value}")
        
        # 检查必要的API配置
        required_keys = ['api_endpoint', 'api_key', 'api_model']
        missing_keys = []
        
        for key in required_keys:
            if key not in config_data or not config_data[key]:
                missing_keys.append(key)
        
        if missing_keys:
            print(f"\n❌ 缺少必要的API配置: {', '.join(missing_keys)}")
        else:
            print("\n✅ API配置完整")
            
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")

if __name__ == "__main__":
    print("动作描述过滤功能测试")
    print("="*50)
    
    # 检查配置文件
    check_cache_config()
    
    print("\n" + "="*50 + "\n")
    
    # 测试过滤功能
    test_action_filter()
    
    print("\n" + "="*50)
    print("测试完成")
    print("\n注意事项:")
    print("1. 请确保在cache_config.txt中配置了正确的API信息")
    print("2. 需要有效的API密钥才能进行实际的过滤测试")
    print("3. 在GUI中勾选'只保留动作描述'选项后，处理视频时会自动调用此功能")