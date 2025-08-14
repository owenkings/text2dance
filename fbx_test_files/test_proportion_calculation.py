#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 测试比例计算的正确性

def test_arm_proportion():
    """测试手臂比例计算"""
    target_ratio = 0.676  # 上臂/前臂应该是0.676
    total_length = 100.0  # 假设总长度为100
    
    print(f"目标比例: 上臂/前臂 = {target_ratio}")
    print(f"总长度: {total_length}")
    
    # 方法1: 我当前使用的公式
    upper_arm_1 = total_length * target_ratio / (target_ratio + 1)
    forearm_1 = total_length / (target_ratio + 1)
    ratio_1 = upper_arm_1 / forearm_1
    
    print(f"\n方法1 (当前公式):")
    print(f"上臂长度: {upper_arm_1:.3f}")
    print(f"前臂长度: {forearm_1:.3f}")
    print(f"实际比例: {ratio_1:.3f}")
    print(f"总长度验证: {upper_arm_1 + forearm_1:.3f}")
    
    # 方法2: 正确的公式
    # 如果上臂/前臂 = 0.676，设上臂=x，前臂=y
    # 那么 x/y = 0.676，即 x = 0.676*y
    # 总长度 = x + y = 0.676*y + y = y*(0.676 + 1) = y*1.676
    # 所以 y = 总长度/1.676，x = 0.676*总长度/1.676
    
    forearm_2 = total_length / (target_ratio + 1)
    upper_arm_2 = target_ratio * total_length / (target_ratio + 1)
    ratio_2 = upper_arm_2 / forearm_2
    
    print(f"\n方法2 (修正公式):")
    print(f"上臂长度: {upper_arm_2:.3f}")
    print(f"前臂长度: {forearm_2:.3f}")
    print(f"实际比例: {ratio_2:.3f}")
    print(f"总长度验证: {upper_arm_2 + forearm_2:.3f}")

def test_leg_proportion():
    """测试腿部比例计算"""
    target_ratio = 1.093  # 大腿/小腿应该是1.093
    total_length = 100.0  # 假设总长度为100
    
    print(f"\n\n目标比例: 大腿/小腿 = {target_ratio}")
    print(f"总长度: {total_length}")
    
    # 正确的公式
    # 如果大腿/小腿 = 1.093，设大腿=x，小腿=y
    # 那么 x/y = 1.093，即 x = 1.093*y
    # 总长度 = x + y = 1.093*y + y = y*(1.093 + 1) = y*2.093
    # 所以 y = 总长度/2.093，x = 1.093*总长度/2.093
    
    calf = total_length / (target_ratio + 1)
    thigh = target_ratio * total_length / (target_ratio + 1)
    ratio = thigh / calf
    
    print(f"\n正确公式:")
    print(f"大腿长度: {thigh:.3f}")
    print(f"小腿长度: {calf:.3f}")
    print(f"实际比例: {ratio:.3f}")
    print(f"总长度验证: {thigh + calf:.3f}")

if __name__ == "__main__":
    test_arm_proportion()
    test_leg_proportion()