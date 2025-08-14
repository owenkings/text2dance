#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 调试骨骼长度计算

def debug_arm_calculation():
    """调试手臂长度计算"""
    print("=== 调试手臂长度计算 ===")
    
    # 模拟实际数据
    total_arm_length = 66.937  # 从验证结果中获取的总手臂长度
    target_ratio = 0.676  # 上臂/前臂应该是0.676
    
    print(f"总手臂长度: {total_arm_length}")
    print(f"目标比例 (上臂/前臂): {target_ratio}")
    
    # 当前使用的公式
    upper_arm_current = total_arm_length * target_ratio / (target_ratio + 1)
    forearm_current = total_arm_length / (target_ratio + 1)
    ratio_current = upper_arm_current / forearm_current
    
    print(f"\n当前公式结果:")
    print(f"上臂长度: {upper_arm_current:.3f}")
    print(f"前臂长度: {forearm_current:.3f}")
    print(f"实际比例: {ratio_current:.3f}")
    print(f"总长度验证: {upper_arm_current + forearm_current:.3f}")
    
    # 验证实际测量值
    measured_upper_arm = 32.225
    measured_forearm = 34.712
    measured_ratio = measured_upper_arm / measured_forearm
    measured_total = measured_upper_arm + measured_forearm
    
    print(f"\n实际测量值:")
    print(f"上臂长度: {measured_upper_arm:.3f}")
    print(f"前臂长度: {measured_forearm:.3f}")
    print(f"实际比例: {measured_ratio:.3f}")
    print(f"总长度: {measured_total:.3f}")
    
    # 分析差异
    print(f"\n差异分析:")
    print(f"上臂长度差异: {abs(upper_arm_current - measured_upper_arm):.3f}")
    print(f"前臂长度差异: {abs(forearm_current - measured_forearm):.3f}")
    print(f"比例差异: {abs(ratio_current - measured_ratio):.3f}")
    
    # 如果要达到目标比例，应该如何分配
    print(f"\n要达到目标比例 {target_ratio}，应该分配:")
    # 设上臂=x，前臂=y，x/y=0.676，x+y=measured_total
    # x = 0.676*y，0.676*y + y = measured_total
    # y*(0.676+1) = measured_total，y = measured_total/1.676
    correct_forearm = measured_total / (target_ratio + 1)
    correct_upper_arm = target_ratio * measured_total / (target_ratio + 1)
    correct_ratio = correct_upper_arm / correct_forearm
    
    print(f"正确上臂长度: {correct_upper_arm:.3f}")
    print(f"正确前臂长度: {correct_forearm:.3f}")
    print(f"正确比例: {correct_ratio:.3f}")
    print(f"总长度验证: {correct_upper_arm + correct_forearm:.3f}")

def debug_leg_calculation():
    """调试腿部长度计算"""
    print(f"\n=== 调试腿部长度计算 ===")
    
    # 模拟实际数据
    total_leg_length = 104.124  # 从验证结果中获取的总腿部长度
    target_ratio = 1.093  # 大腿/小腿应该是1.093
    
    print(f"总腿部长度: {total_leg_length}")
    print(f"目标比例 (大腿/小腿): {target_ratio}")
    
    # 验证实际测量值
    measured_thigh = 39.462
    measured_calf = 64.663
    measured_ratio = measured_thigh / measured_calf
    measured_total = measured_thigh + measured_calf
    
    print(f"\n实际测量值:")
    print(f"大腿长度: {measured_thigh:.3f}")
    print(f"小腿长度: {measured_calf:.3f}")
    print(f"实际比例: {measured_ratio:.3f}")
    print(f"总长度: {measured_total:.3f}")
    
    # 如果要达到目标比例，应该如何分配
    print(f"\n要达到目标比例 {target_ratio}，应该分配:")
    correct_calf = measured_total / (target_ratio + 1)
    correct_thigh = target_ratio * measured_total / (target_ratio + 1)
    correct_ratio = correct_thigh / correct_calf
    
    print(f"正确大腿长度: {correct_thigh:.3f}")
    print(f"正确小腿长度: {correct_calf:.3f}")
    print(f"正确比例: {correct_ratio:.3f}")
    print(f"总长度验证: {correct_thigh + correct_calf:.3f}")

if __name__ == "__main__":
    debug_arm_calculation()
    debug_leg_calculation()