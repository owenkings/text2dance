#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
豆包API测试脚本
用于测试API密钥是否正常工作，以及验证token消耗
"""

import requests
import json
import time

def test_doubao_api():
    """测试豆包API调用"""
    
    # 测试多个可能的模型
    models_to_test = [
        'doubao-pro-4k',
        'doubao-lite-4k', 
        'doubao-pro-32k',
        'doubao-lite-32k',
        'doubao-1.5-pro-32k-250115'
    ]
    
    # API配置
    api_config = {
        'endpoint': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
        'key': 'c01779ea-7f03-49c9-be26-1d93dd3a1f24',
        'model': 'doubao-seed-1-6-250615'  # 使用已激活的模型
    }
    
    # 构建请求头
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_config["key"]}'
    }
    
    # 构建请求数据（模拟动作过滤的请求）
    test_description = "一个人在跳舞，动作很优美，包含了转圈、跳跃等动作。"
    
    request_data = {
        'model': api_config['model'],
        'messages': [
            {
                'role': 'system',
                'content': '你是一个专业的动作描述过滤助手。请对用户提供的动作描述进行优化和过滤，使其更加准确和专业。'
            },
            {
                'role': 'user',
                'content': f'请对以下动作描述进行过滤和优化：\n\n{test_description}\n\n要求：\n1. 保持描述的准确性\n2. 使用更专业的舞蹈术语\n3. 去除冗余信息\n4. 保持简洁明了'
            }
        ],
        'temperature': 0.7,
        'max_tokens': 500,
        'top_p': 0.9
    }
    
    print("=" * 60)
    print("豆包API测试开始")
    print("=" * 60)
    print(f"API端点: {api_config['endpoint']}")
    print(f"API模型: {api_config['model']}")
    print(f"API密钥: {api_config['key'][:20]}...")
    print(f"测试描述: {test_description}")
    print("-" * 60)
    
    try:
        print("正在发送API请求...")
        start_time = time.time()
        
        # 发送请求
        response = requests.post(
            api_config['endpoint'],
            headers=headers,
            json=request_data,
            timeout=30
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"请求耗时: {response_time:.2f}秒")
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API调用成功！")
            print("-" * 60)
            
            # 提取响应内容
            if 'choices' in result and len(result['choices']) > 0:
                filtered_content = result['choices'][0]['message']['content']
                print("过滤后的描述:")
                print(filtered_content)
                print("-" * 60)
            
            # 显示token使用情况
            if 'usage' in result:
                usage = result['usage']
                print("Token使用情况:")
                print(f"  输入Token: {usage.get('prompt_tokens', 'N/A')}")
                print(f"  输出Token: {usage.get('completion_tokens', 'N/A')}")
                print(f"  总Token: {usage.get('total_tokens', 'N/A')}")
            else:
                print("⚠️ 响应中未包含token使用信息")
            
            print("-" * 60)
            print("完整响应数据:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        else:
            print(f"❌ API调用失败！HTTP状态码: {response.status_code}")
            print("错误响应:")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2, ensure_ascii=False))
            except:
                print(response.text)
                
    except requests.exceptions.Timeout:
        print("❌ 请求超时！")
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误！请检查网络连接。")
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_doubao_api()