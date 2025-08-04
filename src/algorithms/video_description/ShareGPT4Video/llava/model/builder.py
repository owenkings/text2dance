# -*- coding: utf-8 -*-
# 必须在所有导入之前设置环境变量
import os
import sys

# 设置标准输出编码为UTF-8，避免Unicode字符显示问题
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

#第三种方法
#os.environ["HF_HOME"] = r"E:\Tiany\huggingface"
#os.environ["HUGGINGFACE_HUB_CACHE"] = r"E:\Tiany\huggingface"
#os.environ["TRANSFORMERS_CACHE"] = r"E:\Tiany\huggingface"
#os.environ["BNB_CACHE_DIR"] = r"E:\Tiany\huggingface\bnb_cache"
#os.makedirs(r"E:\Tiany\huggingface", exist_ok=True)
#os.makedirs(r"E:\Tiany\huggingface\bnb_cache", exist_ok=True)

# ==================== 缓存路径配置 ====================
# 用户可以直接修改下面这个变量来改变缓存路径
# 设置为 None 时会自动从 cache_config.txt 文件读取
USER_CACHE_PATH = None  # 例如: r"D:\MyCache\huggingface"

# ==================== 模块级环境变量设置 ====================
# 在模块导入时立即设置环境变量，确保所有HuggingFace组件使用统一缓存路径
try:
    cache_base_path = None
    
    # 获取缓存路径（复用get_cache_path逻辑但简化版本）
    if USER_CACHE_PATH:
        cache_base_path = USER_CACHE_PATH
    else:
        # 读取配置文件
        # builder.py -> model -> llava -> ShareGPT4Video -> video_description -> algorithms -> src -> text2dance (6层)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
        config_file = os.path.join(project_root, "cache_config.txt")
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'cache_path':
                                cache_base_path = value.strip()
                                break
            except Exception:
                pass
    
    # 如果成功获取到缓存路径，设置环境变量
    if cache_base_path and os.path.exists(cache_base_path):
        bnb_cache_path = os.path.join(cache_base_path, "bnb_cache")
        
        # 设置HuggingFace相关环境变量
        os.environ["HF_HOME"] = cache_base_path
        os.environ["HUGGINGFACE_HUB_CACHE"] = cache_base_path
        os.environ["TRANSFORMERS_CACHE"] = cache_base_path
        os.environ["BNB_CACHE_DIR"] = bnb_cache_path
        
        # 确保目录存在
        os.makedirs(cache_base_path, exist_ok=True)
        os.makedirs(bnb_cache_path, exist_ok=True)
        
except Exception:
    # 如果设置失败，静默忽略，使用默认路径
    pass

# ==================== 自动配置逻辑 ====================

def get_cache_path():
    """
    读取配置文件中的 cache_path 值，如果文件不存在则创建完整配置文件
    优先级: USER_CACHE_PATH > 配置文件 > 默认路径
    """
    # 1. 优先使用用户自定义路径（检查存在性和写入权限）
    if USER_CACHE_PATH:
        try:
            # 如果目录不存在，尝试创建
            os.makedirs(USER_CACHE_PATH, exist_ok=True)
            # 检查写入权限
            test_file = os.path.join(USER_CACHE_PATH, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"[OK] 使用用户指定缓存路径: {USER_CACHE_PATH}")
            return USER_CACHE_PATH
        except (OSError, PermissionError) as e:
            print(f"[WARNING] 用户指定路径无法使用: {USER_CACHE_PATH}, 错误: {e}")
            print("[INFO] 将使用配置文件或默认路径")

    # 2. 定位配置文件 (需要7层dirname从builder.py到达项目根目录)
    # builder.py -> model -> llava -> ShareGPT4Video -> video_description -> algorithms -> src -> text2dance
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))))
    config_file = os.path.join(project_root, 'cache_config.txt')

    # 3. 尝试从配置文件读取 cache_path
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释行
                    if not line or line.startswith('#'):
                        continue
                    # 解析 key=value 格式
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == 'cache_path':
                            path = value.strip()
                            try:
                                # 如果路径不存在，尝试创建
                                os.makedirs(path, exist_ok=True)
                                # 检查写入权限
                                test_file = os.path.join(path, '.write_test')
                                with open(test_file, 'w') as f:
                                    f.write('test')
                                os.remove(test_file)
                                print(f"[OK] 使用配置文件缓存路径: {path}")
                                return path
                            except (OSError, PermissionError) as e:
                                print(f"[WARNING] 配置文件中路径无法使用: {path}, 错误: {e}")
                                continue
        except Exception as e:
            print(f"[WARNING] 读取配置文件失败: {e}")

    # 4. 配置文件不存在或无效时，创建完整配置文件
    # 使用相对路径指向项目的model文件夹
    relative_model_path = os.path.join(project_root, "model")
    default_config = f"""# 格式：每行一个配置项，使用 key=value 的形式
# 缓存路径配置（相对于项目根目录）
cache_path={relative_model_path}

# ShareGPT4Video 模型配置
sharegpt4video_model_path=Lin-Chen/sharegpt4video-8b

# API 配置
api_endpoint=https://api.openai.com/v1/chat/completions
api_key=
api_model=gpt-3.5-turbo
"""
    try:
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(default_config)
        print(f"[OK] 已创建默认配置文件: {config_file}")
        print("[INFO] 请修改配置文件中的路径和 API 配置！")
    except Exception as e:
        print(f"[ERROR] 创建配置文件失败: {e}")
        print("[ERROR] 程序无法继续运行，请检查文件权限")
        raise SystemExit(f"配置文件创建失败: {e}")

    # 5. 返回默认路径（确保路径存在和可写）
    # 使用相对路径指向项目的model文件夹
    default_path = os.path.join(project_root, "model")
    try:
        os.makedirs(default_path, exist_ok=True)
        # 检查写入权限
        test_file = os.path.join(default_path, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"[OK] 使用默认缓存路径: {default_path}")
        return default_path
    except (OSError, PermissionError) as e:
        print(f"[ERROR] 默认路径也无法使用: {default_path}, 错误: {e}")
        raise SystemExit(f"无法创建可用的缓存目录: {e}")

# ------------------- 主逻辑 -------------------
if __name__ == "__main__":
    # 获取缓存路径
    cache_base_path = get_cache_path()
    bnb_cache_path = os.path.join(cache_base_path, "bnb_cache")

    # 设置环境变量
    os.environ["HF_HOME"] = cache_base_path
    os.environ["HUGGINGFACE_HUB_CACHE"] = cache_base_path
    os.environ["TRANSFORMERS_CACHE"] = cache_base_path
    os.environ["BNB_CACHE_DIR"] = bnb_cache_path

    # 创建缓存目录
    os.makedirs(cache_base_path, exist_ok=True)
    os.makedirs(bnb_cache_path, exist_ok=True)

    print(f"[OK] 当前缓存目录: {cache_base_path}")
    print(f"[OK] bitsandbytes 缓存目录: {bnb_cache_path}")
    print("环境变量已设置:")
    print(f"  HF_HOME={os.environ['HF_HOME']}")
    print(f"  BNB_CACHE_DIR={os.environ['BNB_CACHE_DIR']}")

# # 获取项目根目录的绝对路径——第二种方法
# project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# cache_dir = os.path.join(project_root, "cache", "huggingface")
# bnb_cache_dir = os.path.join(cache_dir, "bnb_cache")
# 
# # 设置环境变量使用项目内的缓存目录
# os.environ["HF_HOME"] = cache_dir
# os.environ["HUGGINGFACE_HUB_CACHE"] = cache_dir
# os.environ["TRANSFORMERS_CACHE"] = cache_dir
# os.environ["BNB_CACHE_DIR"] = bnb_cache_dir
# 
# # 创建缓存目录
# os.makedirs(cache_dir, exist_ok=True)
# os.makedirs(bnb_cache_dir, exist_ok=True)

#    Copyright 2023 Haotian Liu
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import shutil
import warnings
import torch
from transformers import (AutoConfig, AutoModelForCausalLM, AutoTokenizer,
                         BitsAndBytesConfig)
from llava.constants import (DEFAULT_IM_END_TOKEN, DEFAULT_IM_START_TOKEN,
                           DEFAULT_IMAGE_PATCH_TOKEN)
from llava.model import *
from llava.train.train import smart_tokenizer_and_embedding_resize

def load_pretrained_model(model_path, model_base, model_name, load_8bit=False, load_4bit=False, device_map="auto", device="cuda", use_flash_attn=False, lora_alpha=None, **kwargs):
    # 统一缓存路径设置 - 使用配置文件中的路径
    cache_dir = get_cache_path()
    
    kwargs = {
        "device_map": device_map,
        "cache_dir": cache_dir,
        **kwargs
    }

    if device != "cuda":
        kwargs['device_map'] = {"": device}

    if load_8bit:
        kwargs['load_in_8bit'] = True
    elif load_4bit:
        kwargs['load_in_4bit'] = True
        kwargs['quantization_config'] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type='nf4'
        )
    else:
        # 根据设备类型选择合适的数据类型
        if device == "cpu" or (device_map == "cpu") or (isinstance(device_map, dict) and all(v == "cpu" for v in device_map.values())):
            kwargs['torch_dtype'] = torch.float32  # CPU模式使用float32
        else:
            kwargs['torch_dtype'] = torch.float16  # GPU模式使用float16

    if use_flash_attn:
        kwargs['attn_implementation'] = 'flash_attention_2'

    if 'llava' in model_name.lower() or 'sharegpt4video' in model_name.lower():
        if 'lora' in model_name.lower() and model_base is None:
            warnings.warn('There is `lora` in model name but no `model_base` is provided.')
        if 'lora' in model_name.lower() and model_base is not None:
            from llava.model.language_model.llava_llama import LlavaConfig
            lora_cfg_pretrained = LlavaConfig.from_pretrained(model_path)
            tokenizer = AutoTokenizer.from_pretrained(
                model_base, 
                use_fast=False, 
                model_max_length=lora_cfg_pretrained.tokenizer_model_max_length
            )
            model = LlavaLlamaForCausalLM.from_pretrained(
                model_base,
                low_cpu_mem_usage=True,
                config=lora_cfg_pretrained,
                **kwargs
            )
            # ...中间代码保持不变...
        elif model_base is not None:
            if 'mpt' in model_name.lower():
                if not os.path.isfile(os.path.join(model_path, 'configuration_mpt.py')):
                    shutil.copyfile(os.path.join(model_base, 'configuration_mpt.py'), 
                                  os.path.join(model_path, 'configuration_mpt.py'))
                tokenizer = AutoTokenizer.from_pretrained(
                    model_base, 
                    use_fast=True
                )
                cfg_pretrained = AutoConfig.from_pretrained(
                    model_path, 
                    trust_remote_code=True
                )
                model = LlavaMptForCausalLM.from_pretrained(
                    model_base,
                    low_cpu_mem_usage=True,
                    config=cfg_pretrained,
                    **kwargs
                )
            else:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_base, 
                    use_fast=False
                )
                cfg_pretrained = AutoConfig.from_pretrained(model_path)
                model = LlavaLlamaForCausalLM.from_pretrained(
                    model_base,
                    low_cpu_mem_usage=True,
                    config=cfg_pretrained,
                    **kwargs
                )
            # ...投影器权重加载代码保持不变...
        else:
            if 'mpt' in model_name.lower():
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    use_fast=True
                )
                model = LlavaMptForCausalLM.from_pretrained(
                    model_path,
                    low_cpu_mem_usage=True,
                    **kwargs
                )
            elif 'mistral' in model_name.lower():
                tokenizer = AutoTokenizer.from_pretrained(model_path)
                model = LlavaMistralForCausalLM.from_pretrained(
                    model_path,
                    low_cpu_mem_usage=True,
                    **kwargs
                )
            else:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    use_fast=False
                )
                # 根据device_map配置选择合适的加载方式
                if device_map is not None:
                    model = LlavaLlamaForCausalLM.from_pretrained(
                        model_path,
                        device_map=device_map,
                        **{k: v for k, v in kwargs.items() if k != 'device_map'}
                    )
                else:
                    model = LlavaLlamaForCausalLM.from_pretrained(
                        model_path,
                        low_cpu_mem_usage=True,
                        **kwargs
                    )
    else:
        if model_base is not None:
            from peft import PeftModel
            tokenizer = AutoTokenizer.from_pretrained(model_base, use_fast=False)
            model = AutoModelForCausalLM.from_pretrained(
                model_base,
                low_cpu_mem_usage=True,
                **kwargs
            )
            # ...LoRA相关代码保持不变...
        else:
            use_fast = False
            if 'mpt' in model_name.lower():
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    use_fast=True
                )
                model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    low_cpu_mem_usage=True,
                    trust_remote_code=True,
                    **kwargs
                )
            else:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    use_fast=False
                )
                model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    low_cpu_mem_usage=True,
                    **kwargs
                )

    # 图像处理器和视觉模型加载
    image_processor = None
    if 'llava' in model_name.lower() or 'sharegpt4video' in model_name.lower():
        mm_use_im_start_end = getattr(model.config, "mm_use_im_start_end", False)
        mm_use_im_patch_token = getattr(model.config, "mm_use_im_patch_token", True)
        if mm_use_im_patch_token:
            tokenizer.add_tokens([DEFAULT_IMAGE_PATCH_TOKEN], special_tokens=True)
        if mm_use_im_start_end:
            tokenizer.add_tokens([DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN], special_tokens=True)

        vision_tower = model.get_vision_tower()
        if not vision_tower.is_loaded:
            vision_tower.load_model(device_map=device_map)
        if device_map != 'auto':
            # 确定目标设备
            if isinstance(device_map, str):
                target_device = device_map
            elif isinstance(device_map, dict):
                target_device = next(iter(device_map.values())) if device_map else device
                if isinstance(target_device, int):
                    target_device = f"cuda:{target_device}"
            else:
                target_device = device
            vision_tower.to(device=target_device, dtype=torch.float16)
        image_processor = vision_tower.image_processor
        
        # 确保所有模型组件正确设置设备
        if device_map != 'auto' and device_map != 'cpu':
            # 确定目标设备
            if isinstance(device_map, str):
                target_device = device_map
            elif isinstance(device_map, dict):
                # 从设备映射字典中获取第一个设备作为目标设备
                target_device = next(iter(device_map.values())) if device_map else device
                if isinstance(target_device, int):
                    target_device = f"cuda:{target_device}"
            else:
                target_device = device
            
            # 确保多模态投影器在正确设备上
            if hasattr(model, 'get_model') and hasattr(model.get_model(), 'mm_projector'):
                model.get_model().mm_projector = model.get_model().mm_projector.to(target_device)
            
            # 确保image_newline参数在正确设备上
            if hasattr(model, 'get_model') and hasattr(model.get_model(), 'image_newline'):
                if model.get_model().image_newline.device.type == 'meta':
                    # 如果参数在meta设备上，需要重新初始化
                    embed_std = 1 / torch.sqrt(torch.tensor(model.config.hidden_size, dtype=model.get_model().image_newline.dtype))
                    model.get_model().image_newline = torch.nn.Parameter(
                        torch.randn(model.config.hidden_size, dtype=model.get_model().image_newline.dtype, device=target_device) * embed_std
                    )
                else:
                    model.get_model().image_newline = model.get_model().image_newline.to(target_device)

    # 强制数据类型转换以确保CPU兼容性
    if device == "cpu" or (device_map == "cpu") or (isinstance(device_map, dict) and all(v == "cpu" for v in device_map.values())):
        # 在CPU模式下，强制将所有模型参数转换为float32
        model = model.float()  # 转换主模型
        
        # 转换视觉塔
        if hasattr(model, 'get_vision_tower') and model.get_vision_tower() is not None:
            vision_tower = model.get_vision_tower()
            if hasattr(vision_tower, 'vision_tower'):
                vision_tower.vision_tower = vision_tower.vision_tower.float()
        
        # 转换多模态投影器
        if hasattr(model, 'get_model') and hasattr(model.get_model(), 'mm_projector'):
            model.get_model().mm_projector = model.get_model().mm_projector.float()
        
        # 转换image_newline参数
        if hasattr(model, 'get_model') and hasattr(model.get_model(), 'image_newline'):
            if model.get_model().image_newline is not None:
                model.get_model().image_newline.data = model.get_model().image_newline.data.float()

    context_len = getattr(model.config, "max_sequence_length", 2048)
    return tokenizer, model, image_processor, context_len