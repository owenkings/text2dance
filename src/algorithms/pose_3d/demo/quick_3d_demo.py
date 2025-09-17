#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速3D可视化演示脚本

这个脚本展示了如何在不使用OSMesa的情况下进行3D人体姿态可视化。

使用方法:
1. 首先运行PMCE生成pkl文件:
   python ./main/run_demo.py --vid_file demo/sample_video.mp4 --gpu 0 --no_render --save_pkl

2. 然后运行此脚本进行3D可视化:
   python ./demo/quick_3d_demo.py
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

def check_dependencies():
    """检查必要的依赖"""
    missing_deps = []
    
    try:
        import matplotlib
        print(f"✓ matplotlib {matplotlib.__version__} 已安装")
    except ImportError:
        missing_deps.append("matplotlib")
    
    try:
        import joblib
        print(f"✓ joblib 已安装")
    except ImportError:
        missing_deps.append("joblib")
    
    try:
        import numpy as np
        print(f"✓ numpy {np.__version__} 已安装")
    except ImportError:
        missing_deps.append("numpy")
    
    try:
        import open3d as o3d
        print(f"✓ open3d {o3d.__version__} 已安装")
    except ImportError:
        print("⚠ open3d 未安装 (可选，用于高质量3D可视化)")
    
    if missing_deps:
        print(f"\n❌ 缺少依赖: {', '.join(missing_deps)}")
        print(f"请运行: pip install {' '.join(missing_deps)}")
        return False
    
    return True

def find_pkl_files():
    """查找可用的pkl文件"""
    output_dir = Path("./output/demo_output")
    pkl_files = []
    
    if output_dir.exists():
        for pkl_file in output_dir.rglob("*.pkl"):
            pkl_files.append(pkl_file)
    
    return pkl_files

def run_matplotlib_demo(pkl_file):
    """运行matplotlib演示"""
    print("\n=== 使用matplotlib进行3D可视化 ===")
    
    # 导入可视化模块
    from demo.simple_3d_visualizer import visualize_pmce_results
    
    output_dir = "./3d_demo_matplotlib"
    Path(output_dir).mkdir(exist_ok=True)
    
    print(f"正在处理: {pkl_file}")
    print(f"输出目录: {output_dir}")
    
    try:
        visualize_pmce_results(
            str(pkl_file),
            output_dir=output_dir,
            show_plots=False  # 不显示，只保存
        )
        print(f"✓ matplotlib可视化完成，图片保存在: {output_dir}")
        return True
    except Exception as e:
        print(f"❌ matplotlib可视化失败: {e}")
        return False

def run_open3d_demo(pkl_file):
    """运行Open3D演示"""
    print("\n=== 使用Open3D进行3D可视化 ===")
    
    try:
        import open3d as o3d
    except ImportError:
        print("⚠ Open3D未安装，跳过Open3D演示")
        return False
    
    # 导入可视化模块
    from demo.open3d_visualizer import visualize_pmce_results_open3d
    
    output_dir = "./3d_demo_open3d"
    Path(output_dir).mkdir(exist_ok=True)
    
    print(f"正在处理: {pkl_file}")
    print(f"输出目录: {output_dir}")
    
    try:
        visualize_pmce_results_open3d(
            str(pkl_file),
            output_dir=output_dir,
            interactive=False  # 不交互，只保存截图
        )
        print(f"✓ Open3D可视化完成，截图保存在: {output_dir}")
        return True
    except Exception as e:
        print(f"❌ Open3D可视化失败: {e}")
        return False

def create_animation_demo(pkl_file):
    """创建动画演示"""
    print("\n=== 创建3D动画 ===")
    
    from demo.simple_3d_visualizer import create_3d_animation
    
    output_dir = "./3d_demo_animation"
    
    print(f"正在创建动画: {pkl_file}")
    print(f"输出目录: {output_dir}")
    print("注意: 这可能需要一些时间...")
    
    try:
        create_3d_animation(
            str(pkl_file),
            output_dir
        )
        print(f"✓ 动画帧生成完成: {output_dir}")
        print("\n可以使用以下命令生成视频:")
        print(f"ffmpeg -r 30 -i {output_dir}/frame_%06d.png -c:v libx264 -pix_fmt yuv420p 3d_animation.mp4")
        return True
    except Exception as e:
        print(f"❌ 动画生成失败: {e}")
        return False

def main():
    print("🎯 PMCE 3D可视化演示")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 查找pkl文件
    pkl_files = find_pkl_files()
    
    if not pkl_files:
        print("\n❌ 未找到pkl文件")
        print("请先运行PMCE生成数据:")
        print("python ./main/run_demo.py --vid_file demo/sample_video.mp4 --gpu 0 --no_render --save_pkl")
        return
    
    print(f"\n📁 找到 {len(pkl_files)} 个pkl文件:")
    for i, pkl_file in enumerate(pkl_files):
        print(f"  {i+1}. {pkl_file}")
    
    # 使用第一个pkl文件进行演示
    pkl_file = pkl_files[0]
    print(f"\n🎬 使用文件进行演示: {pkl_file}")
    
    # 运行不同的可视化演示
    results = []
    
    # matplotlib演示
    results.append(run_matplotlib_demo(pkl_file))
    
    # Open3D演示
    results.append(run_open3d_demo(pkl_file))
    
    # 询问是否创建动画
    print("\n❓ 是否创建3D动画? (这可能需要较长时间)")
    response = input("输入 'y' 创建动画，其他键跳过: ").lower().strip()
    
    if response == 'y':
        results.append(create_animation_demo(pkl_file))
    
    # 总结
    print("\n" + "=" * 50)
    print("🎉 演示完成!")
    
    successful_demos = sum(results)
    total_demos = len([r for r in results if r is not None])
    
    print(f"✓ 成功完成 {successful_demos}/{total_demos} 个演示")
    
    # 显示输出目录
    output_dirs = ["./3d_demo_matplotlib", "./3d_demo_open3d", "./3d_demo_animation"]
    existing_dirs = [d for d in output_dirs if Path(d).exists()]
    
    if existing_dirs:
        print("\n📂 输出目录:")
        for dir_path in existing_dirs:
            file_count = len(list(Path(dir_path).glob("*")))
            print(f"  {dir_path} ({file_count} 个文件)")
    
    print("\n💡 提示:")
    print("- 查看生成的图片了解3D可视化效果")
    print("- 使用 --interactive 参数进行交互式可视化")
    print("- 参考 demo/3D_VISUALIZATION_GUIDE.md 了解更多选项")

if __name__ == "__main__":
    main()