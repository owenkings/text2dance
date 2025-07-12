#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
豆包API集成测试脚本
测试动作描述过滤功能是否能正常使用豆包API
"""

import os
import sys
import json
import requests

def test_doubao_api():
    """测试豆包API调用"""
    print("=== 豆包API集成测试 ===")
    
    # 读取配置
    config_file = "cache_config.txt"
    if not os.path.exists(config_file):
        print(f"❌ 配置文件 {config_file} 不存在")
        return False
    
    config = {}
    with open(config_file, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value
    
    # 检查API配置
    api_endpoint = config.get('api_endpoint', '')
    api_key = config.get('api_key', '')
    api_model = config.get('api_model', '')
    
    print(f"API端点: {api_endpoint}")
    print(f"API模型: {api_model}")
    print(f"API密钥: {'已配置' if api_key else '未配置'}")
    
    if not api_endpoint or not api_key or not api_model:
        print("❌ API配置不完整")
        return False
    
    # 测试API调用
    test_description = """
    在这个视频中，一个穿着蓝色T恤和黑色牛仔裤的年轻男子站在明亮的客厅里。
    他正在做一系列的舞蹈动作：首先他举起双臂过头顶，然后向左转身，
    接着做了一个跳跃动作，落地时双脚分开。随后他弯腰触地，
    然后快速起身并向右摆动手臂。整个过程中，背景可以看到沙发和电视。
    """
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        prompt = f"帮我处理这段话，只保留动作描述，去除环境、人物衣着相关内容，并且不润色，保证原文：\n\n{test_description}"
        
        data = {
            'model': api_model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'max_tokens': 1000,
            'temperature': 0.1
        }
        
        print("\n🔄 正在调用豆包API...")
        response = requests.post(
            api_endpoint,
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API调用成功")
            print("\n📝 响应内容:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if 'choices' in result and len(result['choices']) > 0:
                filtered_content = result['choices'][0]['message']['content'].strip()
                print("\n🎯 过滤后的动作描述:")
                print(f"\"{filtered_content}\"")
                
                print("\n📊 过滤效果对比:")
                print("原始描述:")
                print(test_description.strip())
                print("\n过滤后描述:")
                print(filtered_content)
                
                return True
            else:
                print("❌ API响应格式异常")
                return False
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API调用异常: {str(e)}")
        return False

def test_config_loading():
    """测试配置加载"""
    print("\n=== 配置加载测试 ===")
    
    # 模拟VideoDescriptionWidget的配置加载
    try:
        cache_config_path = os.path.join(os.path.dirname(__file__), 'cache_config.txt')
        
        config_data = {}
        if os.path.exists(cache_config_path):
            with open(cache_config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        config_data[key] = value
        
        api_config = {
            'api_endpoint': config_data.get('api_endpoint', ''),
            'api_key': config_data.get('api_key', ''),
            'api_model': config_data.get('api_model', 'doubao-1-5-pro-32k-250115')
        }
        
        print("✅ 配置加载成功")
        print(f"API端点: {api_config['api_endpoint']}")
        print(f"API模型: {api_config['api_model']}")
        print(f"API密钥: {'已配置' if api_config['api_key'] else '未配置'}")
        
        return api_config
        
    except Exception as e:
        print(f"❌ 配置加载失败: {str(e)}")
        return None

def main():
    """主函数"""
    print("豆包API集成测试")
    print("=" * 50)
    
    # 测试配置加载
    config = test_config_loading()
    if not config:
        return
    
    # 测试API调用
    success = test_doubao_api()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 豆包API集成测试通过！")
        print("\n✨ 现在可以在视频描述功能中使用豆包API进行动作描述过滤了")
        print("\n📋 使用步骤:")
        print("1. 打开视频描述功能")
        print("2. 勾选'只保留动作描述'选项")
        print("3. 上传视频并开始处理")
        print("4. 系统会自动调用豆包API过滤描述内容")
    else:
        print("❌ 豆包API集成测试失败")
        print("\n🔧 请检查:")
        print("1. API密钥是否正确")
        print("2. 网络连接是否正常")
        print("3. API端点是否可访问")
        print("4. 账户余额是否充足")

if __name__ == "__main__":
    main()