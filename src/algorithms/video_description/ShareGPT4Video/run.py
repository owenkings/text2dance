import argparse
import os
import warnings
import logging
import sys
import traceback
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

import numpy as np
import torch
from decord import VideoReader, cpu
from PIL import Image

# 抑制常见警告
warnings.filterwarnings("ignore", message=".*copying from a non-meta parameter.*")
warnings.filterwarnings("ignore", message=".*Did you mean to pass `assign=True`.*")
warnings.filterwarnings("ignore", message=".*resume_download.*deprecated.*")
warnings.filterwarnings("ignore", message=".*Special tokens have been added.*")
warnings.filterwarnings("ignore", message=".*cache-system uses symlinks.*")
warnings.filterwarnings("ignore", message=".*To support symlinks on Windows.*")
warnings.filterwarnings("ignore", message=".*Xet Storage is enabled.*")
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

# 设置详细日志记录
def setup_comprehensive_logging():
    """设置全面的日志记录"""
    # 创建logs目录
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建详细的日志文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f"run_detailed_{timestamp}.log")
    
    # 设置日志格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 添加文件处理器（记录所有级别）
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 添加控制台处理器（只显示重要信息）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger('ShareGPT4Video')

# 自定义输出捕获类
class LoggingCapture:
    """捕获并记录所有输出"""
    
    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        self.buffer = StringIO()
        
    def write(self, text):
        if text.strip():  # 只记录非空内容
            self.logger.log(self.level, f"OUTPUT: {text.strip()}")
        self.buffer.write(text)
        
    def flush(self):
        pass
        
    def getvalue(self):
        return self.buffer.getvalue()

from llava.constants import DEFAULT_IMAGE_TOKEN, IMAGE_TOKEN_INDEX
from llava.conversation import conv_templates
from llava.mm_utils import (get_model_name_from_path, process_images,
                            tokenizer_image_token)
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init


def create_frame_grid(img_array, interval_width=50):
    n, h, w, c = img_array.shape
    grid_size = int(np.ceil(np.sqrt(n)))

    horizontal_band = np.ones((h, interval_width, c),
                              dtype=img_array.dtype) * 255
    vertical_band = np.ones((interval_width, w + (grid_size - 1)
                            * (w + interval_width), c), dtype=img_array.dtype) * 255

    rows = []
    for i in range(grid_size):
        row_frames = []
        for j in range(grid_size):
            idx = i * grid_size + j
            if idx < n:
                frame = img_array[idx]
            else:
                frame = np.ones_like(img_array[0]) * 255
            if j > 0:
                row_frames.append(horizontal_band)
            row_frames.append(frame)
        combined_row = np.concatenate(row_frames, axis=1)
        if i > 0:
            rows.append(vertical_band)
        rows.append(combined_row)

    final_grid = np.concatenate(rows, axis=0)
    return final_grid


def resize_image_grid(image, max_length=1920):
    width, height = image.size
    if max(width, height) > max_length:
        if width > height:
            scale = max_length / width
        else:
            scale = max_length / height

        new_width = int(width * scale)
        new_height = int(height * scale)

        img_resized = image.resize((new_width, new_height), Image.BILINEAR)
    else:
        img_resized = image
    return img_resized


def video_answer(prompt, model, processor, tokenizer, img_grid, do_sample=True,
                 max_new_tokens=200, num_beams=1, top_p=0.9,
                 temperature=1.0, print_res=False, **kwargs):
    # 获取日志记录器
    logger = logging.getLogger('ShareGPT4Video.video_answer')
    
    logger.info("开始视频回答生成...")
    logger.info(f"参数设置: do_sample={do_sample}, max_new_tokens={max_new_tokens}, num_beams={num_beams}")
    logger.info(f"参数设置: top_p={top_p}, temperature={temperature}")
    
    if not isinstance(img_grid, (list, tuple)):
        img_grid = [img_grid]
    
    image_size = img_grid[0].size
    logger.info(f"图像网格大小: {image_size}")
    logger.info(f"图像数量: {len(img_grid)}")
    
    logger.info("处理图像...")
    image_tensor = process_images(img_grid, processor, model.config)[0]
    logger.info(f"图像张量形状: {image_tensor.shape}")
    
    logger.info("处理输入文本...")
    input_ids = tokenizer_image_token(
        prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt')
    input_ids = input_ids.unsqueeze(0).to(
        device=model.device, non_blocking=True)
    logger.info(f"输入ID形状: {input_ids.shape}")
    logger.info(f"模型设备: {model.device}")
    
    pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token is not None else tokenizer.eos_token_id
    logger.info(f"填充token ID: {pad_token_id}")

    with torch.inference_mode():
        logger.info("开始推理模式...")
        # 确保图像张量在正确的设备上
        if model.device.type == 'cuda':
            image_tensor = image_tensor.to(dtype=torch.float16, device=model.device, non_blocking=True)
            logger.info("使用CUDA设备，图像张量转换为float16")
        else:
            image_tensor = image_tensor.to(dtype=torch.float32, device=model.device)
            logger.info("使用CPU设备，图像张量转换为float32")
        
        logger.info(f"最终图像张量形状: {image_tensor.shape}, 数据类型: {image_tensor.dtype}")
        
        logger.info("开始模型生成...")
        output_ids = model.generate(
            input_ids,
            images=image_tensor,
            image_sizes=[image_size],
            do_sample=do_sample,
            temperature=temperature,
            top_p=top_p,
            num_beams=num_beams,
            max_new_tokens=max_new_tokens,
            pad_token_id=pad_token_id,
            use_cache=True,
            **kwargs)
        
        logger.info(f"生成的输出ID形状: {output_ids.shape}")
        
        logger.info("解码输出...")
        outputs = tokenizer.batch_decode(
            output_ids, skip_special_tokens=True)[0].strip()
        
        logger.info(f"解码后输出长度: {len(outputs)} 字符")
    
    if print_res:  # debug usage
        print('### PROMPTING LM WITH: ', prompt)
        print('### LM OUTPUT TEXT:  ', outputs)
        logger.info(f"提示内容: {prompt}")
        logger.info(f"LM输出文本: {outputs}")
    
    logger.info("视频回答生成完成")
    return outputs


def single_test(model, processor, tokenizer, vid_path, qs, pre_query_prompt=None,  num_frames=16, conv_mode="plain"):
    # 获取日志记录器
    logger = logging.getLogger('ShareGPT4Video.single_test')
    
    logger.info("开始单个视频测试...")
    logger.info(f"视频路径: {vid_path}")
    logger.info(f"查询内容: {qs}")
    logger.info(f"帧数: {num_frames}")
    logger.info(f"对话模式: {conv_mode}")
    logger.info(f"预查询提示: {pre_query_prompt}")
    def get_index(num_frames, num_segments):
        seg_size = float(num_frames - 1) / num_segments
        start = int(seg_size / 2)
        offsets = np.array([
            start + int(np.round(seg_size * idx)) for idx in range(num_segments)
        ])
        return offsets

    def load_video(video_path, num_segments=8, return_msg=False, num_frames=4):
        # 获取日志记录器
        logger = logging.getLogger('ShareGPT4Video.load_video')
        
        logger.info(f"开始加载视频: {video_path}")
        logger.info(f"参数: num_segments={num_segments}, return_msg={return_msg}, num_frames={num_frames}")
        
        # 处理视频路径，确保能正确读取包含特殊字符的文件
        try:
            # 标准化路径
            import os
            normalized_path = os.path.normpath(video_path)
            logger.info(f"标准化后的路径: {normalized_path}")
            
            # 检查文件是否存在
            if not os.path.exists(normalized_path):
                logger.error(f"视频文件不存在: {normalized_path}")
                raise FileNotFoundError(f"视频文件不存在: {normalized_path}")
            
            # 获取文件信息
            file_size = os.path.getsize(normalized_path)
            logger.info(f"视频文件大小: {file_size / (1024*1024):.2f} MB")
            
            print(f"正在加载视频: {normalized_path}")
            logger.info(f"正在加载视频: {normalized_path}")
            
            # 尝试加载视频
            vr = VideoReader(normalized_path, ctx=cpu(0), num_threads=1)
            logger.info("视频加载成功")
            
        except Exception as e:
            logger.error(f"视频加载失败: {e}")
            print(f"视频加载失败: {e}")
            print(f"尝试的路径: {video_path}")
            
            # 尝试使用短路径名（Windows系统）
            try:
                import platform
                if platform.system() == 'Windows':
                    try:
                        logger.info("尝试使用Windows短路径名...")
                        import win32api
                        short_path = win32api.GetShortPathName(normalized_path)
                        logger.info(f"短路径名: {short_path}")
                        print(f"尝试使用短路径: {short_path}")
                        vr = VideoReader(short_path, ctx=cpu(0), num_threads=1)
                        logger.info("使用短路径成功加载视频")
                        print("使用短路径成功加载视频")
                    except ImportError:
                        logger.error("win32api不可用，无法使用短路径")
                        print("win32api不可用，无法使用短路径")
                        raise e
                    except Exception as short_path_error:
                        logger.error(f"短路径也失败: {short_path_error}")
                        print(f"短路径也失败: {short_path_error}")
                        raise e
                else:
                    logger.error("非Windows系统，无法使用短路径名解决方案")
                    raise e
            except Exception as final_error:
                logger.error(f"所有尝试都失败了: {final_error}")
                logger.error(f"原始路径: {video_path}")
                logger.error(f"标准化路径: {normalized_path}")
                print(f"所有尝试都失败了: {final_error}")
                print(f"原始路径: {video_path}")
                print(f"标准化路径: {normalized_path}")
                print("建议解决方案:")
                print("1. 确保文件路径正确")
                print("2. 尝试将文件移动到纯英文路径下")
                print("3. 或者将文件重命名为纯英文名称")
                raise
        
        num_frames_total = len(vr)
        logger.info(f"视频总帧数: {num_frames_total}")
        logger.info(f"视频FPS: {vr.get_avg_fps()}")
        print(f"视频总帧数: {num_frames_total}")
        
        logger.info("计算帧索引...")
        frame_indices = get_index(num_frames_total, num_segments)
        logger.info(f"选择的帧索引: {frame_indices}")
        
        logger.info("提取视频帧...")
        img_array = vr.get_batch(frame_indices).asnumpy()
        logger.info(f"提取的帧数组形状: {img_array.shape}")
        logger.info(f"帧数据类型: {img_array.dtype}")
        
        logger.info("创建帧网格...")
        img_grid = create_frame_grid(img_array, 50)
        logger.info(f"帧网格形状: {img_grid.shape}")
        
        logger.info("转换为PIL图像...")
        img_grid = Image.fromarray(img_grid).convert("RGB")
        logger.info(f"PIL图像大小: {img_grid.size}")
        
        logger.info("调整图像网格大小...")
        img_grid = resize_image_grid(img_grid)
        logger.info(f"调整后图像大小: {img_grid.size}")
        
        if return_msg:
            fps = float(vr.get_avg_fps())
            sec = ", ".join([str(round(f / fps, 1)) for f in frame_indices])
            # " " should be added in the start and end
            msg = f"The video contains {len(frame_indices)} frames sampled at {sec} seconds."
            logger.info(f"返回消息: {msg}")
            logger.info("视频加载完成（带消息）")
            return img_grid, msg
        else:
            logger.info("视频加载完成（无消息）")
            return img_grid
    
    if num_frames != 0:
        logger.info("开始加载视频...")
        vid, msg = load_video(
            vid_path, num_segments=num_frames, return_msg=True)
        logger.info(f"视频加载消息: {msg}")
    else:
        logger.warning("帧数为0，不输入图像")
        vid, msg = None, 'num_frames is 0, not inputing image'
    
    img_grid = vid
    logger.info("设置对话模板...")
    conv = conv_templates[conv_mode].copy()
    
    if pre_query_prompt is not None:
        logger.info("使用预查询提示")
        qs = DEFAULT_IMAGE_TOKEN + '\n' + pre_query_prompt + qs
    else:
        logger.info("不使用预查询提示")
        qs = DEFAULT_IMAGE_TOKEN + '\n' + qs
    
    logger.info("构建对话...")
    conv.append_message(conv.roles[0], qs)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()
    logger.info(f"最终提示长度: {len(prompt)} 字符")
    
    logger.info("开始生成回答...")
    llm_response = video_answer(prompt, model=model, processor=processor, tokenizer=tokenizer,
                                do_sample=False, img_grid=img_grid, max_new_tokens=512, print_res=True)
    
    logger.info(f"生成的回答长度: {len(llm_response) if llm_response else 0} 字符")
    logger.info("单个视频测试完成")
    
    return llm_response


if __name__ == "__main__":
    # 设置全面的日志记录
    logger = setup_comprehensive_logging()
    
    # 记录程序开始
    logger.info("="*80)
    logger.info("ShareGPT4Video 视频描述程序开始运行")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    logger.info(f"命令行参数: {sys.argv}")
    logger.info("="*80)
    
    # 设置输出捕获
    stdout_capture = LoggingCapture(logger, logging.INFO)
    stderr_capture = LoggingCapture(logger, logging.ERROR)
    
    # 自定义参数解析函数，处理包含空格和特殊字符的文件路径
    def parse_custom_args():
        # 获取原始命令行参数
        raw_args = sys.argv[1:]
        
        # 初始化参数字典
        parsed_args = {
            'model_path': 'Lin-Chen/sharegpt4video-8b',
            'video': 'examples/yoga.mp4',
            'conv_mode': 'llava_llama_3',
            'query': 'Describe this video in detail.',
            'device': 'cuda'
        }
        
        i = 0
        while i < len(raw_args):
            arg = raw_args[i]
            
            if arg == '--model-path' and i + 1 < len(raw_args):
                parsed_args['model_path'] = raw_args[i + 1]
                i += 2
            elif arg == '--video' and i + 1 < len(raw_args):
                # 处理视频路径，可能包含空格和特殊字符
                video_path = raw_args[i + 1]
                
                # 如果路径被引号包围，移除引号
                if (video_path.startswith('"') and video_path.endswith('"')) or \
                   (video_path.startswith("'") and video_path.endswith("'")):
                    video_path = video_path[1:-1]
                else:
                    # 如果没有引号，尝试重建完整路径
                    # 查找下一个以--开头的参数或到达末尾
                    j = i + 2
                    while j < len(raw_args) and not raw_args[j].startswith('--'):
                        video_path += ' ' + raw_args[j]
                        j += 1
                    i = j - 1  # 调整索引
                
                parsed_args['video'] = video_path.strip()
                i += 2
            elif arg == '--conv-mode' and i + 1 < len(raw_args):
                parsed_args['conv_mode'] = raw_args[i + 1]
                i += 2
            elif arg == '--query' and i + 1 < len(raw_args):
                # 处理查询字符串，可能包含空格
                query = raw_args[i + 1]
                if (query.startswith('"') and query.endswith('"')) or \
                   (query.startswith("'") and query.endswith("'")):
                    query = query[1:-1]
                else:
                    # 重建完整查询字符串
                    j = i + 2
                    while j < len(raw_args) and not raw_args[j].startswith('--'):
                        query += ' ' + raw_args[j]
                        j += 1
                    i = j - 1
                
                parsed_args['query'] = query.strip()
                i += 2
            elif arg == '--device' and i + 1 < len(raw_args):
                parsed_args['device'] = raw_args[i + 1]
                i += 2
            else:
                i += 1
        
        # 创建类似argparse.Namespace的对象
        class Args:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        return Args(
            model_path=parsed_args['model_path'],
            video=parsed_args['video'],
            conv_mode=parsed_args['conv_mode'],
            query=parsed_args['query'],
            device=parsed_args['device']
        )
    
    try:
        # 捕获所有输出
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            # 使用自定义参数解析
            logger.info("开始解析命令行参数...")
            args = parse_custom_args()
            
            # 记录解析结果
            logger.info("参数解析完成:")
            logger.info(f"  模型路径: {args.model_path}")
            logger.info(f"  视频路径: {args.video}")
            logger.info(f"  对话模式: {args.conv_mode}")
            logger.info(f"  查询内容: {args.query}")
            logger.info(f"  设备: {args.device}")
            
            # 输出解析结果用于调试
            print(f"解析的参数:")
            print(f"  模型路径: {args.model_path}")
            print(f"  视频路径: {args.video}")
            print(f"  对话模式: {args.conv_mode}")
            print(f"  查询内容: {args.query}")
            print(f"  设备: {args.device}")
            print()
            
            num_frames = 16
            pre_query_prompt = "The provided image arranges keyframes from a video in a grid view, keyframes are separated with white bands. Answer concisely with overall content and context of the video, highlighting any significant events, characters, or objects that appear throughout the frames."
            
            logger.info(f"设置帧数: {num_frames}")
            logger.info(f"预查询提示: {pre_query_prompt}")
            
            # 检查视频文件是否存在
            logger.info(f"检查视频文件: {args.video}")
            if not os.path.exists(args.video):
                logger.error(f"视频文件不存在: {args.video}")
                raise FileNotFoundError(f"视频文件不存在: {args.video}")
            else:
                logger.info("视频文件存在，继续处理")
            
            logger.info("初始化PyTorch...")
            disable_torch_init()
            
            model_path = os.path.expanduser(args.model_path)
            model_name = get_model_name_from_path(model_path)
            logger.info(f"展开后的模型路径: {model_path}")
            logger.info(f"模型名称: {model_name}")
            
            # 根据device参数设置设备
            logger.info("配置计算设备...")
            if args.device.lower() == 'cuda' and torch.cuda.is_available():
                device_map = 'auto'
                logger.info(f"使用GPU加速，CUDA可用: {torch.cuda.is_available()}")
                logger.info(f"CUDA设备数量: {torch.cuda.device_count()}")
                if torch.cuda.is_available():
                    logger.info(f"当前CUDA设备: {torch.cuda.current_device()}")
                    logger.info(f"CUDA设备名称: {torch.cuda.get_device_name()}")
                print(f"使用GPU加速，CUDA可用: {torch.cuda.is_available()}")
            else:
                device_map = 'cpu'
                logger.info("使用CPU模式")
                print("使用CPU模式")
            
            logger.info("开始加载预训练模型...")
            tokenizer, model, processor, context_len = load_pretrained_model(
                model_path, None, model_name, device_map=device_map)
            logger.info("模型加载完成")
            logger.info(f"上下文长度: {context_len}")
            
            # 当使用device_map='auto'时，模型已经自动分配到合适的设备，无需再次移动
            # 只有在使用CPU模式时才需要显式设置eval模式
            logger.info("设置模型为评估模式...")
            if device_map == 'cpu':
                model = model.eval()
                logger.info("CPU模式：模型设置为评估模式")
            else:
                # GPU模式下，模型已经通过device_map自动配置，只需设置eval模式
                model = model.eval()
                logger.info("GPU模式：模型设置为评估模式")
            
            logger.info("开始视频处理...")
            print("\n开始处理视频...")
            
            outputs = single_test(model,
                                  processor,
                                  tokenizer,
                                  args.video,
                                  qs=args.query,
                                  pre_query_prompt=pre_query_prompt,
                                  num_frames=num_frames,
                                  conv_mode=args.conv_mode)
            
            logger.info("视频处理完成")
            logger.info(f"生成的描述长度: {len(outputs) if outputs else 0} 字符")
            logger.info(f"生成的描述内容: {outputs}")
            
            print("\n=== 视频描述结果 ===")
            print(outputs)
            print("===================\n")
            
    except Exception as e:
        logger.error("程序执行过程中发生错误:")
        logger.error(f"错误类型: {type(e).__name__}")
        logger.error(f"错误信息: {str(e)}")
        logger.error("详细错误堆栈:")
        logger.error(traceback.format_exc())
        
        # 也输出到控制台
        print(f"\n错误: {e}")
        print("详细错误信息请查看日志文件")
        
        # 重新抛出异常
        raise
    
    finally:
        # 记录程序结束
        logger.info("="*80)
        logger.info("ShareGPT4Video 视频描述程序运行结束")
        logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        # 输出捕获的内容摘要
        try:
            stdout_content = stdout_capture.getvalue()
            stderr_content = stderr_capture.getvalue()
            
            if stdout_content:
                logger.info(f"标准输出内容长度: {len(stdout_content)} 字符")
            if stderr_content:
                logger.info(f"标准错误内容长度: {len(stderr_content)} 字符")
        except Exception as capture_error:
            logger.warning(f"获取捕获内容时出错: {capture_error}")
