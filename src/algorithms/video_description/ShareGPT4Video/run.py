import argparse
import os
import warnings

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
    if not isinstance(img_grid, (list, tuple)):
        img_grid = [img_grid]
    image_size = img_grid[0].size
    image_tensor = process_images(img_grid, processor, model.config)[0]
    input_ids = tokenizer_image_token(
        prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt')
    input_ids = input_ids.unsqueeze(0).to(
        device=model.device, non_blocking=True)
    pad_token_id = tokenizer.pad_token_id if tokenizer.pad_token is not None else tokenizer.eos_token_id

    with torch.inference_mode():
        # 确保图像张量在正确的设备上
        if model.device.type == 'cuda':
            image_tensor = image_tensor.to(dtype=torch.float16, device=model.device, non_blocking=True)
        else:
            image_tensor = image_tensor.to(dtype=torch.float32, device=model.device)
            
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
        outputs = tokenizer.batch_decode(
            output_ids, skip_special_tokens=True)[0].strip()
    if print_res:  # debug usage
        print('### PROMPTING LM WITH: ', prompt)
        print('### LM OUTPUT TEXT:  ', outputs)

    return outputs


def single_test(model, processor, tokenizer, vid_path, qs, pre_query_prompt=None,  num_frames=16, conv_mode="plain"):
    def get_index(num_frames, num_segments):
        seg_size = float(num_frames - 1) / num_segments
        start = int(seg_size / 2)
        offsets = np.array([
            start + int(np.round(seg_size * idx)) for idx in range(num_segments)
        ])
        return offsets

    def load_video(video_path, num_segments=8, return_msg=False, num_frames=4):
        #vr = VideoReader(video_path, ctx=cpu(0), num_threads=1)
        # 处理视频路径，确保能正确读取包含特殊字符的文件
        try:
            # 标准化路径
            import os
            normalized_path = os.path.normpath(video_path)
            
            # 检查文件是否存在
            if not os.path.exists(normalized_path):
                raise FileNotFoundError(f"视频文件不存在: {normalized_path}")
            
            print(f"正在加载视频: {normalized_path}")
            
            # 尝试加载视频
            vr = VideoReader(normalized_path, ctx=cpu(0), num_threads=1)
            
        except Exception as e:
            print(f"视频加载失败: {e}")
            print(f"尝试的路径: {video_path}")
            
            # 尝试使用短路径名（Windows系统）
            try:
                import platform
                if platform.system() == 'Windows':
                    try:
                        import win32api
                        short_path = win32api.GetShortPathName(normalized_path)
                        print(f"尝试使用短路径: {short_path}")
                        vr = VideoReader(short_path, ctx=cpu(0), num_threads=1)
                        print("使用短路径成功加载视频")
                    except ImportError:
                        print("win32api不可用，无法使用短路径")
                        raise e
                    except Exception as short_path_error:
                        print(f"短路径也失败: {short_path_error}")
                        raise e
                else:
                    raise e
            except Exception as final_error:
                print(f"所有尝试都失败了: {final_error}")
                print(f"原始路径: {video_path}")
                print(f"标准化路径: {normalized_path}")
                print("建议解决方案:")
                print("1. 确保文件路径正确")
                print("2. 尝试将文件移动到纯英文路径下")
                print("3. 或者将文件重命名为纯英文名称")
                raise
        num_frames = len(vr)
        frame_indices = get_index(num_frames, num_segments)
        img_array = vr.get_batch(frame_indices).asnumpy()
        img_grid = create_frame_grid(img_array, 50)
        img_grid = Image.fromarray(img_grid).convert("RGB")
        img_grid = resize_image_grid(img_grid)
        if return_msg:
            fps = float(vr.get_avg_fps())
            sec = ", ".join([str(round(f / fps, 1)) for f in frame_indices])
            # " " should be added in the start and end
            msg = f"The video contains {len(frame_indices)} frames sampled at {sec} seconds."
            return img_grid, msg
        else:
            return img_grid
    if num_frames != 0:
        vid, msg = load_video(
            vid_path, num_segments=num_frames, return_msg=True)
    else:
        vid, msg = None, 'num_frames is 0, not inputing image'
    img_grid = vid
    conv = conv_templates[conv_mode].copy()
    if pre_query_prompt is not None:
        qs = DEFAULT_IMAGE_TOKEN + '\n' + pre_query_prompt + qs
    else:
        qs = DEFAULT_IMAGE_TOKEN + '\n' + qs
    conv.append_message(conv.roles[0], qs)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()
    llm_response = video_answer(prompt, model=model, processor=processor, tokenizer=tokenizer,
                                do_sample=False, img_grid=img_grid, max_new_tokens=512, print_res=True)
    return llm_response


if __name__ == "__main__":
    #parser = argparse.ArgumentParser()
    #parser.add_argument("--model-path", type=str, default="Lin-Chen/sharegpt4video-8b")
    #parser.add_argument("--video", type=str, default="examples/yoga.mp4")
    #parser.add_argument("--conv-mode", type=str, default="llava_llama_3")
    #parser.add_argument("--query", type=str, default="Describe this video in detail.")
    #parser.add_argument("--device", type=str, default="cuda", help="Device to use: 'cuda' for GPU or 'cpu' for CPU")
    #args = parser.parse_args()
    import sys
    
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
    
    # 使用自定义参数解析
    args = parse_custom_args()
    
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

    disable_torch_init()
    model_path = os.path.expanduser(args.model_path)
    model_name = get_model_name_from_path(model_path)
    
    # 根据device参数设置设备
    if args.device.lower() == 'cuda' and torch.cuda.is_available():
        device_map = 'auto'
        print(f"使用GPU加速，CUDA可用: {torch.cuda.is_available()}")
    else:
        device_map = 'cpu'
        print("使用CPU模式")
    
    tokenizer, model, processor, context_len = load_pretrained_model(
        model_path, None, model_name, device_map=device_map)
    
    # 当使用device_map='auto'时，模型已经自动分配到合适的设备，无需再次移动
    # 只有在使用CPU模式时才需要显式设置eval模式
    if device_map == 'cpu':
        model = model.eval()
    else:
        # GPU模式下，模型已经通过device_map自动配置，只需设置eval模式
        model = model.eval()

    outputs = single_test(model,
                          processor,
                          tokenizer,
                          args.video,
                          qs=args.query,
                          pre_query_prompt=pre_query_prompt,
                          num_frames=num_frames,
                          conv_mode=args.conv_mode)
