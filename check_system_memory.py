#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统内存检查工具
检查物理内存和虚拟内存配置，提供优化建议
"""

import psutil
import os
import platform

def check_system_memory():
    """检查系统内存状态"""
    print("=" * 60)
    print("系统内存检查报告")
    print("=" * 60)
    
    # 检查物理内存
    memory = psutil.virtual_memory()
    total_gb = memory.total / (1024**3)
    available_gb = memory.available / (1024**3)
    used_gb = memory.used / (1024**3)
    percent_used = memory.percent
    
    print(f"\n📊 物理内存状态:")
    print(f"   总计: {total_gb:.1f} GB")
    print(f"   已用: {used_gb:.1f} GB ({percent_used:.1f}%)")
    print(f"   可用: {available_gb:.1f} GB")
    
    # 检查虚拟内存
    swap = psutil.swap_memory()
    swap_total_gb = swap.total / (1024**3)
    swap_used_gb = swap.used / (1024**3)
    swap_free_gb = swap.free / (1024**3)
    swap_percent = swap.percent
    
    print(f"\n💾 虚拟内存状态:")
    print(f"   总计: {swap_total_gb:.1f} GB")
    print(f"   已用: {swap_used_gb:.1f} GB ({swap_percent:.1f}%)")
    print(f"   可用: {swap_free_gb:.1f} GB")
    
    # 检查系统信息
    print(f"\n🖥️ 系统信息:")
    print(f"   操作系统: {platform.system()} {platform.release()}")
    print(f"   架构: {platform.architecture()[0]}")
    print(f"   处理器: {platform.processor()}")
    
    # 提供建议
    print(f"\n💡 建议:")
    
    # 物理内存建议
    if available_gb < 8:
        print(f"   ⚠️ 物理内存不足 (可用: {available_gb:.1f}GB)")
        print(f"      - 关闭不必要的程序")
        print(f"      - 重启系统释放内存")
        print(f"      - 考虑增加物理内存")
    elif available_gb < 16:
        print(f"   ⚠️ 物理内存较少 (可用: {available_gb:.1f}GB)")
        print(f"      - 建议关闭其他程序")
        print(f"      - 使用较小的模型")
    else:
        print(f"   ✅ 物理内存充足 (可用: {available_gb:.1f}GB)")
    
    # 虚拟内存建议
    if swap_total_gb < 16:
        print(f"   ⚠️ 虚拟内存配置过小 (总计: {swap_total_gb:.1f}GB)")
        print(f"      - 建议设置为物理内存的1.5-2倍")
        print(f"      - 推荐设置: {total_gb * 1.5:.0f}-{total_gb * 2:.0f}GB")
        print(f"      - Windows设置路径: 控制面板 > 系统 > 高级系统设置 > 性能设置 > 高级 > 虚拟内存")
    elif swap_free_gb < 8:
        print(f"   ⚠️ 虚拟内存可用空间不足 (可用: {swap_free_gb:.1f}GB)")
        print(f"      - 建议增加虚拟内存大小")
        print(f"      - 或清理磁盘空间")
    else:
        print(f"   ✅ 虚拟内存配置合理")
    
    # 模型加载建议
    print(f"\n🤖 模型加载建议:")
    total_memory = available_gb + swap_free_gb
    if total_memory < 20:
        print(f"   ❌ 总可用内存不足 ({total_memory:.1f}GB)")
        print(f"      - 无法加载大型模型")
        print(f"      - 建议增加虚拟内存或物理内存")
        print(f"      - 或使用更小的模型")
    elif total_memory < 32:
        print(f"   ⚠️ 总可用内存有限 ({total_memory:.1f}GB)")
        print(f"      - 可以尝试加载模型，但可能较慢")
        print(f"      - 建议关闭其他程序")
        print(f"      - 使用CPU模式可能更稳定")
    else:
        print(f"   ✅ 总可用内存充足 ({total_memory:.1f}GB)")
        print(f"      - 可以正常加载大型模型")
    
    print(f"\n" + "=" * 60)
    
    return {
        'physical_total': total_gb,
        'physical_available': available_gb,
        'virtual_total': swap_total_gb,
        'virtual_free': swap_free_gb,
        'total_available': total_memory
    }

def get_windows_virtual_memory_instructions():
    """获取Windows虚拟内存设置说明"""
    if platform.system().lower() != 'windows':
        return
    
    print("\n📋 Windows虚拟内存设置步骤:")
    print("1. 右键点击 '此电脑' -> 属性")
    print("2. 点击 '高级系统设置'")
    print("3. 在 '性能' 部分点击 '设置'")
    print("4. 切换到 '高级' 选项卡")
    print("5. 在 '虚拟内存' 部分点击 '更改'")
    print("6. 取消勾选 '自动管理所有驱动器的分页文件大小'")
    print("7. 选择系统驱动器（通常是C:）")
    print("8. 选择 '自定义大小'")
    print("9. 设置初始大小和最大大小（建议相同）")
    print("10. 点击 '设置' -> '确定' -> 重启系统")
    
    memory = psutil.virtual_memory()
    total_gb = memory.total / (1024**3)
    recommended_size = int(total_gb * 1.5 * 1024)  # 转换为MB
    
    print(f"\n💡 推荐设置:")
    print(f"   初始大小: {recommended_size} MB")
    print(f"   最大大小: {recommended_size} MB")
    print(f"   (约 {recommended_size/1024:.1f} GB)")

if __name__ == "__main__":
    try:
        memory_info = check_system_memory()
        
        if platform.system().lower() == 'windows':
            get_windows_virtual_memory_instructions()
        
        # 检查是否需要立即处理
        if memory_info['virtual_total'] < 16 or memory_info['total_available'] < 20:
            print(f"\n🚨 紧急建议:")
            print(f"   当前配置无法支持大型模型加载")
            print(f"   请按照上述说明增加虚拟内存后重试")
            exit(1)
        else:
            print(f"\n✅ 系统配置检查完成")
            exit(0)
            
    except Exception as e:
        print(f"❌ 检查过程中出现错误: {e}")
        exit(1)