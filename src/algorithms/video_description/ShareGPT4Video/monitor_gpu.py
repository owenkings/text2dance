#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU实时监控脚本
在运行video_processor_GPU.py时监控GPU使用情况
"""

import time
import os
import sys
from datetime import datetime

try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    print("错误: 需要安装pynvml库")
    print("安装命令: pip install pynvml")
    sys.exit(1)

class GPUMonitor:
    def __init__(self, device_id=0, interval=2):
        self.device_id = device_id
        self.interval = interval
        self.running = True
        
        try:
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            # 兼容不同版本的pynvml库
            gpu_name = pynvml.nvmlDeviceGetName(self.handle)
            if isinstance(gpu_name, bytes):
                self.gpu_name = gpu_name.decode('utf-8')
            else:
                self.gpu_name = str(gpu_name)
        except Exception as e:
            print(f"GPU初始化失败: {e}")
            sys.exit(1)
    
    def get_gpu_info(self):
        """获取GPU信息"""
        try:
            # 内存信息
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            
            # 利用率信息
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            
            # 温度信息
            try:
                temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                temp = "N/A"
            
            # 功耗信息
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(self.handle) / 1000.0  # 转换为瓦特
            except:
                power = "N/A"
            
            return {
                'memory_used': mem_info.used // 1024**2,  # MB
                'memory_total': mem_info.total // 1024**2,  # MB
                'memory_free': mem_info.free // 1024**2,  # MB
                'memory_percent': (mem_info.used / mem_info.total) * 100,
                'gpu_util': util.gpu,
                'memory_util': util.memory,
                'temperature': temp,
                'power': power
            }
        except Exception as e:
            print(f"获取GPU信息失败: {e}")
            return None
    
    def print_header(self):
        """打印表头"""
        print(f"\n监控GPU {self.device_id}: {self.gpu_name}")
        print("=" * 80)
        print(f"{'时间':<12} {'GPU利用率':<10} {'显存使用':<15} {'显存利用率':<12} {'温度':<8} {'功耗':<8}")
        print("-" * 80)
    
    def print_status(self, info):
        """打印状态信息"""
        if info is None:
            return
        
        current_time = datetime.now().strftime("%H:%M:%S")
        memory_usage = f"{info['memory_used']}/{info['memory_total']}MB"
        
        # 根据使用率设置颜色标识
        gpu_status = "🔥" if info['gpu_util'] > 80 else "⚡" if info['gpu_util'] > 50 else "💤"
        memory_status = "🔥" if info['memory_percent'] > 80 else "⚡" if info['memory_percent'] > 50 else "💤"
        
        print(f"{current_time:<12} {gpu_status}{info['gpu_util']:>3}%{'':<5} {memory_status}{memory_usage:<14} {info['memory_util']:>3}%{'':<8} {info['temperature']}{'':<4}°C {info['power']}{'':<4}W")
    
    def check_video_processor_running(self):
        """检查video_processor_GPU.py是否在运行"""
        try:
            # 检查是否有Python进程运行video_processor_GPU.py
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        if 'video_processor_GPU.py' in cmdline:
                            return True
                except:
                    continue
            return False
        except ImportError:
            # 如果没有psutil，跳过检查
            return None
    
    def monitor(self):
        """开始监控"""
        self.print_header()
        
        try:
            while self.running:
                info = self.get_gpu_info()
                self.print_status(info)
                
                # 检查video_processor_GPU.py是否在运行
                is_running = self.check_video_processor_running()
                if is_running is True:
                    print("  📹 检测到video_processor_GPU.py正在运行")
                elif is_running is False:
                    print("  ⏸️  未检测到video_processor_GPU.py运行")
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n监控已停止")
            self.running = False

def main():
    print("GPU实时监控工具")
    print("按 Ctrl+C 停止监控")
    
    # 检查命令行参数
    device_id = 0
    interval = 2
    
    if len(sys.argv) > 1:
        try:
            device_id = int(sys.argv[1])
        except ValueError:
            print("错误: GPU设备ID必须是数字")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        try:
            interval = float(sys.argv[2])
        except ValueError:
            print("错误: 监控间隔必须是数字")
            sys.exit(1)
    
    print(f"监控GPU设备: {device_id}")
    print(f"监控间隔: {interval}秒")
    
    monitor = GPUMonitor(device_id, interval)
    monitor.monitor()

if __name__ == "__main__":
    main()