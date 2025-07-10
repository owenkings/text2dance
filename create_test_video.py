#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创建测试视频文件
"""

import cv2
import numpy as np
import os
from pathlib import Path

def create_test_video():
    """创建一个简单的测试视频"""
    # 视频参数
    width, height = 640, 480
    fps = 30
    duration = 3  # 3秒
    total_frames = fps * duration
    
    # 输出路径
    output_path = Path(__file__).parent / 'test_video.mp4'
    
    # 创建视频写入器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    print(f"正在创建测试视频: {output_path}")
    
    for frame_num in range(total_frames):
        # 创建一个简单的动画帧
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 背景颜色渐变
        frame[:, :] = [50, 50, 50]
        
        # 移动的圆形（模拟人物动作）
        center_x = int(width * 0.3 + (width * 0.4) * (frame_num / total_frames))
        center_y = int(height * 0.5 + 50 * np.sin(frame_num * 0.2))
        
        # 绘制"人物"（简单的圆形和线条）
        # 头部
        cv2.circle(frame, (center_x, center_y - 60), 20, (255, 200, 150), -1)
        
        # 身体
        cv2.line(frame, (center_x, center_y - 40), (center_x, center_y + 40), (255, 255, 255), 3)
        
        # 手臂（摆动）
        arm_angle = np.sin(frame_num * 0.3) * 0.5
        arm_x = int(center_x + 30 * np.cos(arm_angle))
        arm_y = int(center_y - 10 + 30 * np.sin(arm_angle))
        cv2.line(frame, (center_x, center_y - 10), (arm_x, arm_y), (255, 255, 255), 3)
        
        arm_x2 = int(center_x - 30 * np.cos(arm_angle))
        arm_y2 = int(center_y - 10 - 30 * np.sin(arm_angle))
        cv2.line(frame, (center_x, center_y - 10), (arm_x2, arm_y2), (255, 255, 255), 3)
        
        # 腿部（走路动作）
        leg_angle = np.sin(frame_num * 0.4) * 0.8
        leg_x = int(center_x + 25 * np.sin(leg_angle))
        leg_y = center_y + 80
        cv2.line(frame, (center_x, center_y + 40), (leg_x, leg_y), (255, 255, 255), 3)
        
        leg_x2 = int(center_x - 25 * np.sin(leg_angle))
        cv2.line(frame, (center_x, center_y + 40), (leg_x2, leg_y), (255, 255, 255), 3)
        
        # 添加文本
        cv2.putText(frame, f"Frame {frame_num + 1}/{total_frames}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Test Video - Walking Motion", 
                   (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # 写入帧
        out.write(frame)
        
        # 显示进度
        if (frame_num + 1) % 10 == 0:
            progress = (frame_num + 1) / total_frames * 100
            print(f"进度: {progress:.1f}%")
    
    # 释放资源
    out.release()
    
    print(f"✓ 测试视频创建完成: {output_path}")
    print(f"视频信息: {width}x{height}, {fps}fps, {duration}秒")
    
    return output_path

if __name__ == "__main__":
    create_test_video()