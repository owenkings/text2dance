#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存配置测试和管理工具
用于验证缓存路径设置是否正确，并提供缓存清理功能
"""

import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_cache_configuration():
    """测试缓存配置"""
    print("🔍 测试缓存配置...")
    print("=" * 50)
    
    # 导入缓存管理器
    try:
        from src.core.cache_manager import get_cache_manager
        cache_manager = get_cache_manager()
        print("✅ 缓存管理器导入成功")
    except Exception as e:
        print(f"❌ 缓存管理器导入失败: {e}")
        return False
    
    # 检查环境变量
    print("\n📋 环境变量设置:")
    env_vars = [
        'HF_HOME',
        'HUGGINGFACE_HUB_CACHE', 
        'TRANSFORMERS_CACHE',
        'TORCH_HOME',
        'TORCH_HUB'
    ]
    
    for var in env_vars:
        value = os.environ.get(var, 'Not set')
        status = "✅" if value != 'Not set' else "❌"
        print(f"  {status} {var}: {value}")
    
    # 检查缓存目录信息
    print("\n📁 缓存目录信息:")
    cache_info = cache_manager.get_cache_info()
    print(f"  📍 路径: {cache_info['cache_path']}")
    print(f"  📂 存在: {'✅' if cache_info['exists'] else '❌'}")
    print(f"  ✏️  可写: {'✅' if cache_info['writable'] else '❌'}")
    print(f"  📊 大小: {cache_info['size'] / (1024*1024):.2f} MB")
    print(f"  📁 子目录: {', '.join(cache_info['subdirs']) if cache_info['subdirs'] else '无'}")
    
    return True

def check_old_cache():
    """检查旧的缓存目录"""
    print("\n🔍 检查旧缓存目录...")
    print("=" * 50)
    
    old_cache_paths = [
        Path.home() / ".cache" / "huggingface",
        Path.home() / ".cache" / "torch",
        Path.home() / ".cache" / "pip",
        Path.home() / ".cache" / "matplotlib"
    ]
    
    total_size = 0
    found_caches = []
    
    for cache_path in old_cache_paths:
        if cache_path.exists():
            try:
                size = sum(f.stat().st_size for f in cache_path.rglob('*') if f.is_file())
                size_mb = size / (1024 * 1024)
                total_size += size_mb
                found_caches.append((cache_path, size_mb))
                print(f"  📁 {cache_path}: {size_mb:.2f} MB")
            except Exception as e:
                print(f"  ⚠️ {cache_path}: 无法计算大小 ({e})")
        else:
            print(f"  ✅ {cache_path}: 不存在")
    
    if found_caches:
        print(f"\n📊 旧缓存总大小: {total_size:.2f} MB")
        print("\n💡 建议: 可以安全删除这些旧缓存目录以释放磁盘空间")
        print("   新的缓存将保存到配置的E盘路径中")
    else:
        print("\n✅ 未发现旧缓存目录")
    
    return found_caches

def clean_old_cache():
    """清理旧缓存"""
    print("\n🧹 清理旧缓存...")
    print("=" * 50)
    
    old_caches = check_old_cache()
    if not old_caches:
        print("✅ 没有需要清理的旧缓存")
        return
    
    print("\n⚠️ 警告: 此操作将删除以下缓存目录:")
    for cache_path, size_mb in old_caches:
        print(f"  - {cache_path} ({size_mb:.2f} MB)")
    
    response = input("\n确认删除? (y/N): ").strip().lower()
    if response in ['y', 'yes']:
        import shutil
        for cache_path, _ in old_caches:
            try:
                shutil.rmtree(cache_path)
                print(f"✅ 已删除: {cache_path}")
            except Exception as e:
                print(f"❌ 删除失败 {cache_path}: {e}")
        print("\n🎉 旧缓存清理完成！")
    else:
        print("\n❌ 取消清理操作")

def test_model_loading():
    """测试模型加载是否使用新缓存路径"""
    print("\n🤖 测试模型加载...")
    print("=" * 50)
    
    try:
        # 导入缓存管理器确保环境变量已设置
        from src.core.cache_manager import get_cache_manager
        cache_manager = get_cache_manager()
        
        print("正在测试HuggingFace模型加载...")
        
        # 测试transformers库
        try:
            from transformers import AutoTokenizer
            print("✅ transformers库导入成功")
            
            # 检查缓存路径
            import transformers
            cache_dir = getattr(transformers, 'TRANSFORMERS_CACHE', None)
            print(f"📁 Transformers缓存路径: {cache_dir}")
            
        except ImportError:
            print("⚠️ transformers库未安装")
        
        # 测试torch库
        try:
            import torch
            print("✅ PyTorch库导入成功")
            print(f"📁 Torch Hub缓存路径: {torch.hub.get_dir()}")
        except ImportError:
            print("⚠️ PyTorch库未安装")
            
    except Exception as e:
        print(f"❌ 模型加载测试失败: {e}")
        return False
    
    return True

def main():
    """主函数"""
    print("🎯 缓存配置测试和管理工具")
    print("=" * 60)
    
    while True:
        print("\n请选择操作:")
        print("1. 测试缓存配置")
        print("2. 检查旧缓存")
        print("3. 清理旧缓存")
        print("4. 测试模型加载")
        print("5. 全部测试")
        print("0. 退出")
        
        choice = input("\n请输入选择 (0-5): ").strip()
        
        if choice == '1':
            test_cache_configuration()
        elif choice == '2':
            check_old_cache()
        elif choice == '3':
            clean_old_cache()
        elif choice == '4':
            test_model_loading()
        elif choice == '5':
            test_cache_configuration()
            check_old_cache()
            test_model_loading()
        elif choice == '0':
            print("\n👋 再见！")
            break
        else:
            print("\n❌ 无效选择，请重试")
        
        input("\n按回车键继续...")

if __name__ == "__main__":
    main()