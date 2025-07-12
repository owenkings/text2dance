#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断终端命令与程序命令的差异
帮助找出为什么终端可以运行但程序界面不能运行的原因
"""

import os
import sys
import subprocess

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def compare_environments():
    """比较终端环境和程序环境"""
    print("=== 终端命令与程序命令差异诊断 ===")
    
    # 1. 检查当前工作目录
    print(f"\n1. 当前工作目录:")
    print(f"   程序运行目录: {os.getcwd()}")
    print(f"   项目根目录: {project_root}")
    
    # 2. 检查Python环境
    print(f"\n2. Python环境:")
    print(f"   Python版本: {sys.version}")
    print(f"   Python路径: {sys.executable}")
    
    # 3. 检查环境变量
    print(f"\n3. 关键环境变量:")
    env_vars = ['PATH', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES', 'HF_HOME']
    for var in env_vars:
        value = os.environ.get(var, '未设置')
        if len(str(value)) > 100:
            value = str(value)[:100] + '...'
        print(f"   {var}: {value}")
    
    # 4. 检查run.py文件和参数
    print(f"\n4. run.py文件检查:")
    run_py_path = "src/algorithms/video_description/ShareGPT4Video/run.py"
    run_py_absolute = os.path.join(project_root, run_py_path)
    print(f"   相对路径: {run_py_path}")
    print(f"   绝对路径: {run_py_absolute}")
    print(f"   文件存在: {os.path.exists(run_py_absolute)}")
    
    # 5. 模拟程序中的命令构建
    print(f"\n5. 程序中的命令构建:")
    test_video = "test_video.mp4"
    test_query = "Describe this video in detail."
    model_path = "Lin-Chen/ShareGPT4Video-8B"
    
    # 程序中使用的命令
    program_cmd = [
        'python',
        'src/algorithms/video_description/ShareGPT4Video/run.py',
        '--model-path', model_path,
        '--video', test_video,  # 注意：程序使用 --video
        '--query', test_query,
        '--device', 'cuda'
    ]
    
    print(f"   程序命令: {' '.join(program_cmd)}")
    
    # 6. 用户在终端使用的命令格式
    print(f"\n6. 用户终端命令格式:")
    terminal_cmd_example = [
        'python', 'run.py',
        '--model-path', model_path,
        '--video-file', test_video,  # 用户可能使用了错误的参数名
        '--query', test_query,
        '--device', 'cuda'
    ]
    
    print(f"   终端命令示例: {' '.join(terminal_cmd_example)}")
    
    # 7. 检查参数差异
    print(f"\n7. 参数差异分析:")
    print(f"   程序使用: --video")
    print(f"   用户可能使用: --video-file")
    print(f"   正确参数: --video (根据run.py源码确认)")
    
    # 8. 工作目录差异
    print(f"\n8. 工作目录差异:")
    print(f"   终端工作目录: E:\\Tiany\\text2dance\\src\\algorithms\\video_description\\ShareGPT4Video")
    print(f"   程序工作目录: {project_root}")
    print(f"   程序中run.py路径: {run_py_path}")
    
    # 9. 可能的问题原因
    print(f"\n9. 可能的问题原因:")
    print(f"   a) 模型路径问题：程序可能无法访问模型文件")
    print(f"   b) 视频文件路径问题：相对路径解析不同")
    print(f"   c) 环境变量差异：CUDA、HuggingFace等配置")
    print(f"   d) Python包导入问题：工作目录影响模块导入")
    print(f"   e) 权限问题：程序运行权限与终端不同")
    
    # 10. 建议的调试步骤
    print(f"\n10. 建议的调试步骤:")
    print(f"   1. 在程序中添加详细的日志输出")
    print(f"   2. 检查模型文件是否可访问")
    print(f"   3. 验证CUDA环境是否正确配置")
    print(f"   4. 比较终端和程序的环境变量")
    print(f"   5. 测试简化版本的命令")
    
    print(f"\n=== 诊断完成 ===")

def test_simple_command():
    """测试简化的命令"""
    print(f"\n=== 测试简化命令 ===")
    
    # 切换到项目根目录
    os.chdir(project_root)
    
    # 测试run.py是否可以正常导入和运行帮助
    try:
        result = subprocess.run(
            ['python', 'src/algorithms/video_description/ShareGPT4Video/run.py', '--help'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"命令执行成功: {result.returncode == 0}")
        if result.returncode == 0:
            print(f"帮助信息前100字符: {result.stdout[:100]}...")
        else:
            print(f"错误信息: {result.stderr}")
            
    except Exception as e:
        print(f"命令执行失败: {e}")

if __name__ == "__main__":
    compare_environments()
    test_simple_command()