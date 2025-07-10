import os
import sys
import json
import time
import logging
import threading
import subprocess
import shutil
import psutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

def setup_logging():
    """配置日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('video_processor.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

class Config:
    def __init__(self):
        # 默认配置
        self.enable_parallel = True
        self.enable_memory_check = True
        self.enable_backup = True
        self.max_workers = 4
        self.timeout_seconds = 300
        self.model_path = "Lin-Chen/sharegpt4video-8b"
        self.query_text = "Begin by providing a general overview of the person's current action (e.g., walking, sitting, interacting) visible in the video footage. Then proceed with a detailed analysis focusing specifically on the physical movements and body positioning within the video frame. For the upper body, describe the position and movement patterns of the arms, hands, shoulders and torso. For the lower body, detail the positioning and motion of the legs, feet and overall balance dynamics. The description must remain strictly focused on observable physical actions, deliberately excluding any mention of facial expressions, clothing details or environmental elements outside the video frame boundaries."
        self.supported_exts = ('.mp4', '.avi', '.mov')
        self.memory_threshold = 90  # 内存使用阈值(%)

config = Config()
print_lock = threading.Lock()

def verify_environment():
    """验证是否在正确的conda环境中运行"""
    required_env = "share4video"
    current_env = os.environ.get('CONDA_DEFAULT_ENV', '')
    if current_env != required_env:
        raise EnvironmentError(
            f"必须在 {required_env} 环境下运行！当前环境: {current_env}\n"
            f"请先执行: conda activate {required_env}"
        )

def get_user_choice(prompt: str, default: bool = True) -> bool:
    """获取用户是/否选择"""
    choice = input(f"{prompt} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    if not choice:
        return default
    return choice == 'y'

def setup_config():
    """交互式配置"""
    print("\n=== 配置选项 ===")
    config.enable_parallel = get_user_choice("启用并行处理?", True)
    if config.enable_parallel:
        try:
            workers = int(input(f"设置并行线程数 (默认 {config.max_workers}): ") or config.max_workers)
            config.max_workers = max(1, min(workers, os.cpu_count() or 4))
        except ValueError:
            print(f"无效输入，使用默认值 {config.max_workers}")
    
    config.enable_memory_check = get_user_choice("启用内存保护?", True)
    if config.enable_memory_check:
        try:
            threshold = int(input(f"设置内存阈值% (默认 {config.memory_threshold}): ") or config.memory_threshold)
            config.memory_threshold = max(50, min(threshold, 95))
        except ValueError:
            print(f"无效输入，使用默认值 {config.memory_threshold}%")
    
    config.enable_backup = get_user_choice("启用结果备份?", True)
    print("="*30 + "\n")

def realtime_print(msg: str, end="\n"):
    """线程安全的实时打印"""
    with print_lock:
        print(msg, end=end, flush=True)
        logging.info(msg.strip())

def check_system_resources():
    """检查系统资源"""
    if config.enable_memory_check:
        mem = psutil.virtual_memory()
        if mem.percent >= config.memory_threshold:
            raise MemoryError(f"内存使用过高: {mem.percent}% (阈值: {config.memory_threshold}%)")

def process_single_video(video_path: Path) -> dict:
    """处理单个视频（直接调用模式）"""
    result = {
        "video_name": video_path.name,
        "status": "success",
        "processing_time": 0,
        "description": ""
    }
    start_time = time.time()

    try:
        check_system_resources()
        
        # 构建直接运行的命令（不再使用conda run）
        cmd = [
            "python", "run.py",
            "--model-path", config.model_path,
            "--video", str(video_path.resolve()),  # 使用绝对路径
            "--query", config.query_text
        ]

        realtime_print(f"\n{'='*40}")
        realtime_print(f"开始处理: {video_path.name}")

        # 启动子进程（确保在脚本所在目录执行）
        process = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),  # 关键修改：设置工作目录
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            universal_newlines=True
        )

        # 实时输出处理
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line)
                # 直接打印到控制台（保持实时性）
                with print_lock:
                    sys.stdout.write(line)
                    sys.stdout.flush()

        # 结果处理
        output = ''.join(output_lines)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, output)

        if "LM OUTPUT TEXT:" in output:
            result["description"] = output.split("LM OUTPUT TEXT:")[1].strip()

    except Exception as e:
        result.update({
            "status": "failed",
            "description": str(e)
        })
        realtime_print(f"处理失败: {video_path.name} - {str(e)}")
    finally:
        result["processing_time"] = round(time.time() - start_time, 2)
        realtime_print(f"处理完成: {video_path.name} (状态: {result['status']}, 用时: {result['processing_time']}秒)")
        realtime_print(f"{'='*40}\n")

    return result

def main():
    verify_environment()  # 新增环境验证
    setup_logging()
    realtime_print("=== 视频处理程序 ===")
    realtime_print(f"工作目录: {os.getcwd()}")
    setup_config()

    # 获取输入路径
    while True:
        folder_path = input("请输入视频文件夹路径: ").strip()
        if Path(folder_path).is_dir():
            break
        realtime_print("错误: 路径无效，请重新输入")

    video_files = [f for f in Path(folder_path).iterdir() if f.suffix.lower() in config.supported_exts]
    if not video_files:
        realtime_print("错误: 未找到支持的视频文件")
        return

    # 处理视频
    results = []
    if config.enable_parallel:
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = [executor.submit(process_single_video, f) for f in video_files]
            for future in tqdm(futures, desc="整体进度", unit="视频"):
                results.append(future.result())
    else:
        for video in tqdm(video_files, desc="处理进度", unit="视频"):
            results.append(process_single_video(video))

    # 保存结果
    output_file = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    if config.enable_backup:
        backup_dir = Path("backup_results")
        backup_dir.mkdir(exist_ok=True)
        shutil.copy2(output_file, backup_dir / output_file)
        realtime_print(f"备份已保存到: {backup_dir/output_file}")

    realtime_print(f"\n处理完成！主结果文件: {output_file}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        realtime_print("\n用户中断程序")
        sys.exit(1)
    except Exception as e:
        logging.exception("程序崩溃")
        realtime_print(f"致命错误: {str(e)}")
        sys.exit(1)