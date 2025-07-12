# -*- coding: utf-8 -*-
"""
视频处理爬虫工具 - 主程序入口

这是一个集成了网络爬虫和视频处理功能的工具，支持：
- 网络视频爬取和下载
- 视频处理和分析
- 2D/3D姿态估计
- 视频描述生成
- 插件系统
- 任务管理

使用方法:
    python main.py [选项]

选项:
    --help, -h          显示帮助信息
    --version, -v       显示版本信息
    --config, -c FILE   指定配置文件路径
    --log-level LEVEL   设置日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    --no-gui            以命令行模式运行（不启动GUI）
    --debug             启用调试模式
    --profile           启用性能分析
"""

import os
import sys
import argparse
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# NumPy兼容性检查和修复
# NumPy兼容性检查和修复
import os
import sys
import subprocess

# 设置OpenCV兼容性环境变量
os.environ['OPENCV_DISABLE_EIGEN_TENSOR_SUPPORT'] = '1'
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'

try:
    import numpy
    numpy_version = numpy.__version__
    major_version = int(numpy_version.split('.')[0])
    
    if major_version >= 2:
        print(f"检测到NumPy {numpy_version}，与当前OpenCV版本不兼容")
        print("正在尝试自动修复...")
        
        # 尝试自动降级NumPy
        try:
            print("正在降级NumPy到兼容版本...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "numpy<2.0", "--force-reinstall", "--no-deps", "--quiet"
            ])
            print("NumPy降级完成，请重新启动程序")
            input("按回车键退出...")
            sys.exit(0)
        except subprocess.CalledProcessError:
            print("自动修复失败，请手动运行以下命令：")
            print("pip install 'numpy<2.0' --force-reinstall")
            print("或者运行修复脚本：python fix_numpy.py")
            input("按回车键退出...")
            sys.exit(1)
            
except ImportError:
    print("NumPy未安装，正在安装兼容版本...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "numpy<2.0", "--quiet"
        ])
        print("NumPy安装完成，请重新启动程序")
        input("按回车键退出...")
        sys.exit(0)
    except subprocess.CalledProcessError:
        print("NumPy安装失败，请手动安装：pip install 'numpy<2.0'")
        input("按回车键退出...")
        sys.exit(1)

# 导入项目模块
try:
    from src.gui import create_application
    from src.core.config_manager import ConfigManager
    # from src.core.cli import CLIApplication  # 待实现
except ImportError as e:
    error_msg = str(e)
    print(f"导入模块失败: {error_msg}")
    print("请确保所有依赖已正确安装")
    
    if "moviepy" in error_msg:
        print("MoviePy未安装，正在尝试安装...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "moviepy==1.0.3"
            ])
            print("MoviePy安装完成，请重新启动程序")
        except subprocess.CalledProcessError:
            print("MoviePy安装失败，请手动安装：pip install moviepy==1.0.3")
    elif "numpy" in error_msg:
        print("如果是NumPy相关错误，请运行：pip install 'numpy<2.0' --force-reinstall")
    else:
        print("建议运行：pip install -r requirements.txt")
    
    input("按回车键退出...")
    sys.exit(1)

# 应用程序信息
APP_NAME = "视频处理爬虫工具"
APP_VERSION = "2.2.0"
APP_AUTHOR = "开发团队"
APP_DESCRIPTION = "集成网络爬虫和视频处理功能的工具"


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog="VideoTools",
        description=APP_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py                    # 启动GUI模式
    python main.py --no-gui           # 启动命令行模式
    python main.py --debug            # 启动调试模式
    python main.py --log-level DEBUG  # 设置日志级别
        """
    )
    
    # 基本选项
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{APP_NAME} v{APP_VERSION}"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        metavar="FILE",
        help="指定配置文件路径"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="设置日志级别 (默认: INFO)"
    )
    
    # 运行模式
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="以命令行模式运行（不启动GUI）"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )
    
    parser.add_argument(
        "--profile",
        action="store_true",
        help="启用性能分析"
    )
    
    # CLI模式专用选项
    cli_group = parser.add_argument_group("CLI模式选项")
    
    cli_group.add_argument(
        "--crawl",
        type=str,
        metavar="URL",
        help="爬取指定URL的视频"
    )
    
    cli_group.add_argument(
        "--process",
        type=str,
        metavar="FILE",
        help="处理指定的视频文件"
    )
    
    cli_group.add_argument(
        "--algorithm",
        type=str,
        choices=["pose_2d", "pose_3d", "video_description"],
        help="指定处理算法"
    )
    
    cli_group.add_argument(
        "--output",
        type=str,
        metavar="DIR",
        help="指定输出目录"
    )
    
    return parser.parse_args()

def setup_environment(args):
    """设置运行环境"""
    # 设置环境变量
    if args.debug:
        os.environ["DEBUG"] = "1"
        os.environ["PYTHONPATH"] = str(project_root)
    
    # 设置日志级别
    os.environ["LOG_LEVEL"] = args.log_level
    
    # 设置配置文件路径
    if args.config:
        os.environ["CONFIG_FILE"] = args.config

def run_gui_mode(args):
    """运行GUI模式"""
    try:
        print(f"启动 {APP_NAME} v{APP_VERSION} (GUI模式)")
        
        # 创建应用程序
        app = create_application(sys.argv)
        
        # 运行应用程序
        exit_code = app.run()
        
        return exit_code
        
    except Exception as e:
        print(f"GUI模式启动失败: {e}")
        if args.debug:
            traceback.print_exc()
        return 1

def run_cli_mode(args):
    """运行CLI模式"""
    try:
        print(f"启动 {APP_NAME} v{APP_VERSION} (CLI模式)")
        print("CLI模式暂未实现，请使用GUI模式")
        return 1
        
        # TODO: 实现CLI模式
        # # 创建CLI应用程序
        # cli_app = CLIApplication()
        # 
        # # 处理命令行参数
        # if args.crawl:
        #     return cli_app.crawl_url(args.crawl, args.output)
        # elif args.process:
        #     return cli_app.process_video(args.process, args.algorithm, args.output)
        # else:
        #     # 交互式模式
        #     return cli_app.run_interactive()
        
    except Exception as e:
        print(f"CLI模式运行失败: {e}")
        if args.debug:
            traceback.print_exc()
        return 1

def run_with_profiling(func, args):
    """使用性能分析运行函数"""
    try:
        import cProfile
        import pstats
        from io import StringIO
        
        # 创建性能分析器
        profiler = cProfile.Profile()
        
        # 开始分析
        profiler.enable()
        
        # 运行函数
        result = func(args)
        
        # 停止分析
        profiler.disable()
        
        # 输出分析结果
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s)
        ps.sort_stats('cumulative')
        ps.print_stats(20)  # 显示前20个函数
        
        print("\n=== 性能分析结果 ===")
        print(s.getvalue())
        
        return result
        
    except ImportError:
        print("警告: 无法导入cProfile模块，跳过性能分析")
        return func(args)
    except Exception as e:
        print(f"性能分析失败: {e}")
        return func(args)

def check_dependencies():
    """检查依赖项"""
    # 包名到导入名的映射
    package_mapping = {
        "PyQt5": "PyQt5",
        "requests": "requests",
        "opencv-python": "cv2",
        "numpy": "numpy",
        "pillow": "PIL",
        "beautifulsoup4": "bs4",
        "lxml": "lxml",
        "selenium": "selenium",
        "ffmpeg-python": "ffmpeg"
    }
    
    missing_packages = []
    
    for package_name, import_name in package_mapping.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print("错误: 缺少以下依赖包:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n请使用以下命令安装:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_system_requirements():
    """检查系统要求"""
    # 检查Python版本
    if sys.version_info < (3, 7):
        print(f"错误: 需要Python 3.7或更高版本，当前版本: {sys.version}")
        return False
    
    # 检查操作系统
    if sys.platform not in ["win32", "linux", "darwin"]:
        print(f"警告: 未测试的操作系统: {sys.platform}")
    
    # 检查内存
    try:
        import psutil
        memory = psutil.virtual_memory()
        if memory.total < 2 * 1024 * 1024 * 1024:  # 2GB
            print("警告: 系统内存不足2GB，可能影响性能")
    except ImportError:
        pass
    
    return True


def main():
    """主函数"""
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 检查系统要求
        if not check_system_requirements():
            return 1
        
        # 检查依赖项
        if not check_dependencies():
            return 1
        
        # 设置运行环境
        setup_environment(args)
        
        # 选择运行模式
        if args.no_gui:
            run_func = run_cli_mode
        else:
            run_func = run_gui_mode
        
        # 是否启用性能分析
        if args.profile:
            return run_with_profiling(run_func, args)
        else:
            return run_func(args)
        
    except KeyboardInterrupt:
        print("\n用户中断操作")
        return 130
    except Exception as e:
        print(f"程序运行失败: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    # 设置工作目录
    os.chdir(project_root)
    
    # 运行主程序
    exit_code = main()
    
    # 退出
    sys.exit(exit_code)