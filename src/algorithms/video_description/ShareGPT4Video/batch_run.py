#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ShareGPT4Video 批量处理脚本
实现一次模型加载，多个视频批量推理的优化版本
"""

import os
import sys
import json
import argparse
import logging
import traceback
import warnings
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
from typing import List, Dict, Any, Optional

# 过滤各种警告信息，防止在日志中出现干扰信息
warnings.filterwarnings("ignore", message=".*copying from a non-meta parameter.*")
warnings.filterwarnings("ignore", message=".*Did you mean to pass `assign=True`.*")
warnings.filterwarnings("ignore", message=".*resume_download.*deprecated.*")
warnings.filterwarnings("ignore", message=".*Special tokens have been added.*")
warnings.filterwarnings("ignore", message=".*word embeddings are fine-tuned.*")
warnings.filterwarnings("ignore", message=".*cache-system uses symlinks.*")
warnings.filterwarnings("ignore", message=".*To support symlinks on Windows.*")
warnings.filterwarnings("ignore", message=".*Xet Storage is enabled.*")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'  # 减少transformers库的详细输出

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 导入原有模块
from run import (
    setup_comprehensive_logging, LoggingCapture, ResultFormatter,
    disable_torch_init, get_model_name_from_path, single_test, video_answer
)

# 导入智能模型加载功能
try:
    from llava.model.builder import load_model_with_smart_retry
    smart_loading_available = True
    print("✅ 智能模型加载功能已启用")
except ImportError:
    from run import load_pretrained_model
    smart_loading_available = False
    print("⚠️ 智能模型加载功能不可用，使用传统加载方式")

import torch
import numpy as np
from llava.conversation import conv_templates, SeparatorStyle
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN
from llava.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path, KeywordsStoppingCriteria
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
import gc


class BatchVideoProcessor:
    """
    批量视频处理器
    实现一次模型加载，多个视频批量推理
    """
    
    def __init__(self, model_path: str, device: str = 'Auto', conv_mode: str = 'llava_llama_3', enable_smart_loading: bool = True):
        """
        初始化批量视频处理器
        
        Args:
            model_path: 模型路径
            device: 设备类型 ('Auto', 'CUDA', 'CPU')
            conv_mode: 对话模式
            enable_smart_loading: 是否启用智能加载功能（False时可获得更快的预加载速度）
        """
        self.model_path = model_path
        self.device = self._resolve_device(device)
        self.conv_mode = conv_mode
        self.enable_smart_loading = enable_smart_loading
        self.logger = logging.getLogger('BatchVideoProcessor')
        
        # 模型组件
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.context_len = None
        self.target_device = None
        
        # 加载状态
        self.is_loaded = False
    
    def _resolve_device(self, device: str) -> str:
        """
        解析设备配置，实现Auto模式的自动检测逻辑
        
        Args:
            device: 用户指定的设备 ('Auto', 'CUDA', 'CPU')
            
        Returns:
            str: 实际使用的设备 ('cuda' 或 'cpu')
        """
        if device.upper() == 'CPU':
            return 'cpu'
        elif device.upper() == 'CUDA':
            if torch.cuda.is_available():
                return 'cuda'
            else:
                print("警告: CUDA不可用，自动切换到CPU模式")
                return 'cpu'
        elif device.upper() == 'AUTO':
            # Auto模式：按照用户提供的逻辑图实现
            if not torch.cuda.is_available():
                print("检测到无GPU，使用CPU模式")
                return 'cpu'
            else:
                # 检查GPU内存是否大于8GB
                try:
                    gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    print(f"检测到GPU，显存: {gpu_memory_gb:.1f}GB")
                    
                    if gpu_memory_gb > 8:
                        print("显存大于8GB，使用标准混合模式")
                        return 'cuda'
                    else:
                        print("显存小于等于8GB，使用低显存混合模式")
                        return 'cuda'  # 仍然使用CUDA，但会在load_model中进行优化
                except Exception as e:
                    print(f"GPU内存检测失败: {e}，使用CPU模式")
                    return 'cpu'
        else:
            # 默认情况，尝试使用CUDA
            return 'cuda' if torch.cuda.is_available() else 'cpu'
        
    def load_model(self) -> bool:
        """
        加载模型（只执行一次）
        
        Returns:
            bool: 加载是否成功
        """
        if self.is_loaded:
            self.logger.info("模型已加载，跳过重复加载")
            return True
            
        try:
            self.logger.info("开始加载模型...")
            
            # 初始化PyTorch
            disable_torch_init()
            
            model_path = os.path.expanduser(self.model_path)
            model_name = get_model_name_from_path(model_path)
            self.logger.info(f"模型路径: {model_path}")
            self.logger.info(f"模型名称: {model_name}")
            
            # 配置设备映射
            if self.device.lower() == 'cuda' and torch.cuda.is_available():
                device_map = {
                    "model.embed_tokens": 0,
                    "model.layers": 0,
                    "model.norm": 0,
                    "lm_head": 0,
                    "model.mm_projector": 0,
                    "model.vision_tower": 0,
                    "model.image_newline": 0
                }
                self.target_device = "cuda:0"
                self.logger.info("使用GPU加速")
            else:
                device_map = 'cpu'
                self.target_device = "cpu"
                self.logger.info("使用CPU模式")
            
            # 加载预训练模型
            if smart_loading_available and self.enable_smart_loading:
                self.logger.info("使用智能模型加载功能（支持镜像切换和错误重试）")
                self.tokenizer, self.model, self.processor, self.context_len = load_model_with_smart_retry(
                    model_path, None, model_name, device_map=device_map, enable_smart_loading=True
                )
            elif smart_loading_available and not self.enable_smart_loading:
                self.logger.info("智能加载已禁用，使用传统加载方式（更快的预加载速度）")
                self.tokenizer, self.model, self.processor, self.context_len = load_model_with_smart_retry(
                    model_path, None, model_name, device_map=device_map, enable_smart_loading=False
                )
            else:
                self.logger.info("智能加载功能不可用，使用传统模型加载方式")
                from run import load_pretrained_model
                self.tokenizer, self.model, self.processor, self.context_len = load_pretrained_model(
                    model_path, None, model_name, device_map=device_map
                )
            
            # 确保模型组件在正确设备上
            if self.target_device != "cpu":
                # 移动视觉塔
                if hasattr(self.model, 'get_vision_tower') and self.model.get_vision_tower() is not None:
                    vision_tower = self.model.get_vision_tower()
                    vision_tower = vision_tower.to(self.target_device)
                    self.logger.info(f"视觉塔已移动到设备: {self.target_device}")
                
                # 移动多模态投影器
                if hasattr(self.model, 'get_model') and hasattr(self.model.get_model(), 'mm_projector'):
                    self.model.get_model().mm_projector = self.model.get_model().mm_projector.to(self.target_device)
                    self.logger.info(f"多模态投影器已移动到设备: {self.target_device}")
                
                # 移动image_newline参数
                if hasattr(self.model, 'get_model') and hasattr(self.model.get_model(), 'image_newline'):
                    self.model.get_model().image_newline = self.model.get_model().image_newline.to(self.target_device)
                    self.logger.info(f"image_newline参数已移动到设备: {self.target_device}")
                
                # 确保整个模型在正确设备上
                self.model = self.model.to(self.target_device)
                self.logger.info(f"整个模型已移动到设备: {self.target_device}")
            
            # 设置为评估模式
            self.model = self.model.eval()
            
            self.is_loaded = True
            self.logger.info("模型加载完成")
            return True
            
        except Exception as e:
            # 检查是否为网络连接问题
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['connecttimeouterror', 'localentrynotfounderror', 'connection to huggingface.co timed out', 'max retries exceeded', 'cannot find the requested files in the local cache']):
                self.logger.error("网络连接问题：无法连接到 `https://huggingface.co` 下载模型文件。请检查网络连接或配置离线模式。")
                self.logger.error(f"详细错误信息: {str(e)}")
            else:
                self.logger.error(f"模型加载失败: {str(e)}")
                self.logger.error(traceback.format_exc())
            return False
    
    def process_single_video(self, video_path: str, query: str, 
                           num_frames: int = 16, 
                           do_sample: bool = True,
                           top_p: float = 0.9,
                           temperature: float = 1.0,
                           max_new_tokens: Optional[int] = None,
                           num_beams: int = 1) -> tuple[Optional[str], Optional[str]]:
        """
        处理单个视频
        
        Args:
            video_path: 视频文件路径
            query: 查询内容
            num_frames: 采样帧数（为0时自动选择）
            do_sample: 是否使用采样
            top_p: nucleus采样参数
            temperature: 生成温度
            max_new_tokens: 最大生成token数
            num_beams: 束搜索束数
            
        Returns:
            tuple[Optional[str], Optional[str]]: (生成的描述, 错误信息)，成功时返回(描述, None)，失败时返回(None, 错误信息)
        """
        if not self.is_loaded:
            error_msg = "模型未加载，请先调用load_model()"
            self.logger.error(error_msg)
            return None, error_msg
            
        try:
            self.logger.info(f"开始处理视频: {video_path}")
            
            # 检查视频文件是否存在
            if not os.path.exists(video_path):
                error_msg = f"视频文件不存在: {video_path}"
                self.logger.error(error_msg)
                return None, error_msg
            
            # 如果num_frames为0，根据视频时长自动选择帧数
            if num_frames == 0:
                try:
                    from decord import VideoReader, cpu
                    
                    # 标准化路径
                    normalized_path = os.path.normpath(video_path)
                    
                    # 加载视频获取时长信息
                    vr = VideoReader(normalized_path, ctx=cpu(0), num_threads=1)
                    total_frames = len(vr)
                    fps = vr.get_avg_fps()
                    duration = total_frames / fps  # 视频时长（秒）
                    
                    # 根据视频时长自动选择帧数
                    if duration <= 10:  # 10秒以内
                        num_frames = 8
                    elif duration <= 30:  # 30秒以内
                        num_frames = 12
                    elif duration <= 60:  # 1分钟以内
                        num_frames = 16
                    elif duration <= 180:  # 3分钟以内
                        num_frames = 20
                    elif duration <= 300:  # 5分钟以内
                        num_frames = 24
                    else:  # 超过5分钟
                        num_frames = 32
                    
                    self.logger.info(f"视频 {video_path} 时长: {duration:.1f}秒，自动选择帧数: {num_frames}")
                    
                except Exception as e:
                    self.logger.error(f"自动帧数选择失败: {e}，使用默认16帧")
                    num_frames = 16
            
            # 设置预查询提示
            pre_query_prompt = "The provided image arranges keyframes from a video in a grid view, keyframes are separated with white bands. Answer concisely with overall content and context of the video, highlighting any significant events, characters, or objects that appear throughout the frames."
            
            # 构建single_test参数
            test_params = {
                'model': self.model,
                'processor': self.processor,
                'tokenizer': self.tokenizer,
                'vid_path': video_path,
                'qs': query,
                'pre_query_prompt': pre_query_prompt,
                'num_frames': num_frames,
                'conv_mode': self.conv_mode,
                'do_sample': do_sample,
                'top_p': top_p,
                'temperature': temperature,
                'num_beams': num_beams
            }
            
            # 只有当max_new_tokens被明确设置时才添加该参数
            if max_new_tokens is not None:
                test_params['max_new_tokens'] = max_new_tokens
            
            # 调用单个测试函数
            result = single_test(**test_params)
            
            self.logger.info(f"视频处理完成: {video_path}")
            return result, None
            
        except Exception as e:
            error_msg = f"处理视频失败 {video_path}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            return None, error_msg
    
    def process_videos_batch(self, video_configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理多个视频
        
        Args:
            video_configs: 视频配置列表，每个配置包含视频路径和处理参数
            
        Returns:
            List[Dict[str, Any]]: 处理结果列表
        """
        if not self.is_loaded:
            self.logger.error("模型未加载，请先调用load_model()")
            return []
        
        results = []
        total_videos = len(video_configs)
        
        self.logger.info(f"开始批量处理 {total_videos} 个视频")
        
        for i, config in enumerate(video_configs, 1):
            video_path = config.get('video_path')
            query = config.get('query', 'Describe this video in detail.')
            
            self.logger.info(f"处理进度: {i}/{total_videos} - {video_path}")
            
            # 提取处理参数
            params = {
                'num_frames': config.get('num_frames', 16),
                'do_sample': config.get('do_sample', True),
                'top_p': config.get('top_p', 0.9),
                'temperature': config.get('temperature', 1.0),
                'num_beams': config.get('num_beams', 1)
            }
            
            # 只有当max_new_tokens被明确设置且大于0时才添加该参数
            max_new_tokens = config.get('max_new_tokens')
            if max_new_tokens is not None and max_new_tokens > 0:
                params['max_new_tokens'] = max_new_tokens
            
            # 处理单个视频
            start_time = datetime.now()
            description, error_message = self.process_single_video(video_path, query, **params)
            end_time = datetime.now()
            
            # 记录结果
            result = {
                'video_path': video_path,
                'query': query,
                'description': description,
                'success': description is not None,
                'error_message': error_message or '',
                'processing_time': (end_time - start_time).total_seconds(),
                'timestamp': end_time.isoformat(),
                'parameters': params
            }
            
            results.append(result)
            
            if description:
                self.logger.info(f"成功处理: {video_path}")
            else:
                self.logger.error(f"处理失败: {video_path} - {error_message}")
        
        self.logger.info(f"批量处理完成，成功: {sum(1 for r in results if r['success'])}/{total_videos}")
        return results
    
    def process_videos_batch_gpu_optimized(self, video_configs: List[Dict[str, Any]], 
                                          batch_size: int = 2, 
                                          max_workers: int = 4) -> List[Dict[str, Any]]:
        """
        GPU优化的批量视频处理方法
        实现真正的批量推理，而不是逐个处理
        
        Args:
            video_configs: 视频配置列表
            batch_size: GPU批处理大小（同时处理的视频数量）
            max_workers: 预处理线程数
            
        Returns:
            List[Dict[str, Any]]: 处理结果列表
        """
        if not self.is_loaded:
            self.logger.error("模型未加载，请先调用load_model()")
            return []
        
        total_videos = len(video_configs)
        self.logger.info(f"开始GPU优化批量处理 {total_videos} 个视频")
        self.logger.info(f"用户设置 - 批处理大小: {batch_size}, 预处理线程数: {max_workers}")
        self.logger.info(f"将按照 {batch_size} 个视频为一组进行批量处理")
        
        # 动态调整批处理大小（保留用户设置的优先级）
        original_batch_size = batch_size
        if self.device == 'cuda' and torch.cuda.is_available():
            gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            if gpu_memory_gb <= 8:
                # 低显存GPU建议限制，但不强制覆盖用户设置
                recommended_batch_size = 1
                if batch_size > recommended_batch_size:
                    self.logger.warning(f"检测到低显存GPU ({gpu_memory_gb:.1f}GB)，建议批处理大小不超过{recommended_batch_size}，当前设置: {batch_size}")
                    self.logger.warning(f"如果遇到显存不足错误，请降低批处理大小到{recommended_batch_size}")
                else:
                    self.logger.info(f"检测到低显存GPU ({gpu_memory_gb:.1f}GB)，当前批处理大小: {batch_size} (适合)")
            elif gpu_memory_gb <= 16:
                # 中等显存GPU建议限制
                recommended_batch_size = 2
                if batch_size > recommended_batch_size:
                    self.logger.warning(f"检测到中等显存GPU ({gpu_memory_gb:.1f}GB)，建议批处理大小不超过{recommended_batch_size}，当前设置: {batch_size}")
                    self.logger.warning(f"如果遇到显存不足错误，请降低批处理大小到{recommended_batch_size}")
                else:
                    self.logger.info(f"检测到中等显存GPU ({gpu_memory_gb:.1f}GB)，当前批处理大小: {batch_size} (适合)")
            else:
                self.logger.info(f"检测到高显存GPU ({gpu_memory_gb:.1f}GB)，使用用户设置的批处理大小: {batch_size}")
        else:
            self.logger.info(f"使用用户设置的批处理大小: {batch_size}")
        
        results = []
        
        # 分批处理视频
        for batch_start in range(0, total_videos, batch_size):
            batch_end = min(batch_start + batch_size, total_videos)
            batch_configs = video_configs[batch_start:batch_end]
            
            self.logger.info(f"处理批次 {batch_start//batch_size + 1}/{(total_videos + batch_size - 1)//batch_size}")
            self.logger.info(f"批次范围: {batch_start+1}-{batch_end}/{total_videos}")
            
            # 并行预处理视频帧
            t_pre_start = datetime.now()
            batch_data = self._preprocess_video_batch(batch_configs, max_workers)
            t_pre_end = datetime.now()
            self.logger.info(f"批次预处理耗时: {(t_pre_end - t_pre_start).total_seconds():.3f}s")
            
            # GPU批量推理
            t_inf_start = datetime.now()
            batch_results = self._gpu_batch_inference(batch_data)
            t_inf_end = datetime.now()
            self.logger.info(f"批次推理耗时: {(t_inf_end - t_inf_start).total_seconds():.3f}s")
            
            results.extend(batch_results)
            
            # 清理GPU内存
            if self.device == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
                gc.collect()
        
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(f"GPU优化批量处理完成，成功: {success_count}/{total_videos}")
        return results
    
    def _preprocess_video_batch(self, batch_configs: List[Dict[str, Any]], 
                               max_workers: int) -> List[Dict[str, Any]]:
        """
        并行预处理视频批次
        
        Args:
            batch_configs: 批次视频配置
            max_workers: 最大工作线程数
            
        Returns:
            List[Dict[str, Any]]: 预处理后的批次数据
        """
        self.logger.info(f"开始并行预处理 {len(batch_configs)} 个视频")
        
        t_batch_pre_start = datetime.now()  # 添加缺失的时间戳变量
        batch_data = []
        
        def preprocess_single_video(config):
            """预处理单个视频"""
            _t0 = datetime.now()
            try:
                video_path = config.get('video_path')
                query = config.get('query', 'Describe this video in detail.')
                num_frames = config.get('num_frames', 16)
                _auto_selected = (num_frames == 0)
                _duration_sec = None
                
                # 加载视频帧
                from run import single_test
                
                # 使用与single_test相同的视频加载逻辑
                def get_index(num_frames_total, num_segments):
                    seg_size = float(num_frames_total - 1) / num_segments
                    start = int(seg_size / 2)
                    offsets = np.array([
                        start + int(np.round(seg_size * idx)) for idx in range(num_segments)
                    ])
                    return offsets
                
                def load_video_frames(video_path, num_segments=8):
                    """加载视频帧"""
                    import os
                    from decord import VideoReader, cpu
                    from run import create_frame_grid, resize_image_grid
                    from PIL import Image
                    
                    normalized_path = os.path.normpath(video_path)
                    if not os.path.exists(normalized_path):
                        raise FileNotFoundError(f"视频文件不存在: {normalized_path}")
                    
                    vr = VideoReader(normalized_path, ctx=cpu(0), num_threads=1)
                    num_frames_total = len(vr)
                    
                    frame_indices = get_index(num_frames_total, num_segments)
                    img_array = vr.get_batch(frame_indices).asnumpy()
                    
                    img_grid = create_frame_grid(img_array, 50)
                    img_grid = Image.fromarray(img_grid).convert("RGB")
                    img_grid = resize_image_grid(img_grid)
                    
                    return img_grid
                
                # 自动帧数选择逻辑
                if num_frames == 0:
                    try:
                        import os
                        from decord import VideoReader, cpu
                        
                        normalized_path = os.path.normpath(video_path)
                        vr = VideoReader(normalized_path, ctx=cpu(0), num_threads=1)
                        total_frames = len(vr)
                        fps = vr.get_avg_fps()
                        duration = total_frames / fps
                        _duration_sec = float(duration)
                        
                        if duration <= 10:
                            num_frames = 8
                        elif duration <= 30:
                            num_frames = 12
                        elif duration <= 60:
                            num_frames = 16
                        elif duration <= 180:
                            num_frames = 20
                        elif duration <= 300:
                            num_frames = 24
                        else:
                            num_frames = 32
                    except Exception:
                        num_frames = 16
                
                # 加载视频帧
                img_grid = load_video_frames(video_path, num_frames)
                
                # 构建对话
                conv = conv_templates[self.conv_mode].copy()
                pre_query_prompt = "The provided image arranges keyframes from a video in a grid view, keyframes are separated with white bands. Answer concisely with overall content and context of the video, highlighting any significant events, characters, or objects that appear throughout the frames."
                qs = DEFAULT_IMAGE_TOKEN + '\n' + pre_query_prompt + query
                
                conv.append_message(conv.roles[0], qs)
                conv.append_message(conv.roles[1], None)
                prompt = conv.get_prompt()
                
                _t1 = datetime.now()
                return {
                    'config': config,
                    'img_grid': img_grid,
                    'prompt': prompt,
                    'success': True,
                    'error': None,
                    'stage_times': {
                        'preprocess': (_t1 - _t0).total_seconds()
                    },
                    'selected_num_frames': int(num_frames),
                    'auto_selected_frames': bool(_auto_selected),
                    'video_duration_sec': _duration_sec
                }
                
            except Exception as e:
                _t1 = datetime.now()
                self.logger.error(f"预处理视频失败 {config.get('video_path')}: {str(e)}")
                return {
                    'config': config,
                    'img_grid': None,
                    'prompt': None,
                    'success': False,
                    'error': str(e),
                    'stage_times': {
                        'preprocess': (_t1 - _t0).total_seconds()
                    }
                }
        
        # 并行预处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_config = {executor.submit(preprocess_single_video, config): config 
                              for config in batch_configs}
            
            for future in as_completed(future_to_config):
                result = future.result()
                batch_data.append(result)
        
        success_count = sum(1 for data in batch_data if data['success'])
        t_batch_pre_end = datetime.now()
        self.logger.info(f"预处理完成，成功: {success_count}/{len(batch_configs)}，总耗时: {(t_batch_pre_end - t_batch_pre_start).total_seconds():.3f}s")
        
        return batch_data
    
    def _gpu_batch_inference(self, batch_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        GPU批量推理
        
        Args:
            batch_data: 预处理后的批次数据
            
        Returns:
            List[Dict[str, Any]]: 推理结果
        """
        self.logger.info(f"开始GPU批量推理 {len(batch_data)} 个视频")
        
        results = []
        
        # 分离成功和失败的数据
        successful_data = [data for data in batch_data if data['success']]
        failed_data = [data for data in batch_data if not data['success']]
        
        # 处理失败的数据
        for data in failed_data:
            config = data['config']
            result = {
                'video_path': config.get('video_path'),
                'query': config.get('query', ''),
                'description': None,
                'success': False,
                'error_message': data['error'],
                'processing_time': 0,
                'timestamp': datetime.now().isoformat(),
                'parameters': {},
                'stage_times': data.get('stage_times', {})
            }
            results.append(result)
        
        if not successful_data:
            self.logger.warning("没有成功预处理的视频数据")
            return results
        
        # 批量处理成功的数据
        try:
            # 准备批量输入
            img_grids = [data['img_grid'] for data in successful_data]
            prompts = [data['prompt'] for data in successful_data]
            configs = [data['config'] for data in successful_data]
            
            # 处理图像
            self.logger.info("处理批量图像...")
            image_tensors = []
            image_sizes = []
            image_proc_times = []
            
            for img_grid in img_grids:
                _img_start = datetime.now()
                if not isinstance(img_grid, (list, tuple)):
                    img_grid = [img_grid]
                
                image_size = img_grid[0].size
                image_sizes.append(image_size)
                
                image_tensor = process_images(img_grid, self.processor, self.model.config)[0]
                image_tensors.append(image_tensor)
                _img_end = datetime.now()
                image_proc_times.append((_img_end - _img_start).total_seconds())
            
            # 处理文本输入
            self.logger.info("处理批量文本输入...")
            input_ids_list = []
            tokenize_times = []
            for prompt in prompts:
                _tt0 = datetime.now()
                input_ids = tokenizer_image_token(
                    prompt, self.tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt')
                input_ids = input_ids.unsqueeze(0)
                input_ids_list.append(input_ids)
                _tt1 = datetime.now()
                tokenize_times.append((_tt1 - _tt0).total_seconds())
            
            # 批量推理
            self.logger.info("开始批量推理...")
            pad_token_id = self.tokenizer.pad_token_id if self.tokenizer.pad_token is not None else self.tokenizer.eos_token_id
            
            with torch.inference_mode():
                batch_outputs = []
                
                # 逐个推理（因为不同视频的输入长度可能不同）
                for i, (input_ids, image_tensor, image_size, config, data_item) in enumerate(
                    zip(input_ids_list, image_tensors, image_sizes, configs, successful_data)):
                    
                    start_time = datetime.now()
                    
                    # 移动到设备
                    input_ids = input_ids.to(device=self.model.device, non_blocking=True)
                    
                    if self.model.device.type == 'cuda':
                        image_tensor = image_tensor.to(dtype=torch.float16, device=self.model.device, non_blocking=True)
                    else:
                        image_tensor = image_tensor.to(dtype=torch.float32, device=self.model.device)
                    
                    # 提取生成参数
                    params = {
                        'do_sample': config.get('do_sample', True),
                        'top_p': config.get('top_p', 0.9),
                        'temperature': config.get('temperature', 1.0),
                        'num_beams': config.get('num_beams', 1)
                    }
                    
                    max_new_tokens = config.get('max_new_tokens')
                    if max_new_tokens is not None and max_new_tokens > 0:
                        params['max_new_tokens'] = max_new_tokens
                    
                    # 生成
                    try:
                        t_gen_start = datetime.now()
                        output_ids = self.model.generate(
                            input_ids,
                            images=image_tensor,
                            image_sizes=[image_size],
                            pad_token_id=pad_token_id,
                            use_cache=True,
                            **params
                        )
                        t_gen_end = datetime.now()
                        
                        # 解码
                        t_dec_start = datetime.now()
                        output_text = self.tokenizer.batch_decode(
                            output_ids, skip_special_tokens=True)[0].strip()
                        t_dec_end = datetime.now()
                        
                        end_time = datetime.now()
                        processing_time = (end_time - start_time).total_seconds()
                        
                        # token统计
                        try:
                            in_tok = int(input_ids.shape[-1])
                        except Exception:
                            in_tok = None
                        try:
                            out_tok = int(output_ids.shape[-1]) if hasattr(output_ids, 'shape') else None
                        except Exception:
                            out_tok = None
                        
                        stage_times = data_item.get('stage_times', {}).copy()
                        stage_times.update({
                            'image_process': image_proc_times[i],
                            'tokenize': tokenize_times[i],
                            'generate': (t_gen_end - t_gen_start).total_seconds(),
                            'decode': (t_dec_end - t_dec_start).total_seconds(),
                            'total': processing_time
                        })
                        
                        result = {
                            'video_path': config.get('video_path'),
                            'query': config.get('query', ''),
                            'description': output_text,
                            'success': True,
                            'error_message': '',
                            'processing_time': processing_time,
                            'timestamp': end_time.isoformat(),
                            'parameters': params,
                            'stage_times': stage_times,
                            'token_counts': {
                                'input_tokens': in_tok,
                                'output_tokens': out_tok
                            },
                            'selected_num_frames': data_item.get('selected_num_frames'),
                            'auto_selected_frames': data_item.get('auto_selected_frames'),
                            'video_duration_sec': data_item.get('video_duration_sec')
                        }
                        
                        self.logger.info(
                            f"成功处理视频 {i+1}/{len(successful_data)}: {config.get('video_path')} | 生成: {stage_times['generate']:.3f}s, 解码: {stage_times['decode']:.3f}s, 输入tok: {in_tok}, 输出tok: {out_tok}")
                        
                    except Exception as e:
                        end_time = datetime.now()
                        error_msg = f"推理失败: {str(e)}"
                        self.logger.error(f"视频 {config.get('video_path')} 推理失败: {error_msg}")
                        
                        result = {
                            'video_path': config.get('video_path'),
                            'query': config.get('query', ''),
                            'description': None,
                            'success': False,
                            'error_message': error_msg,
                            'processing_time': 0,
                            'timestamp': end_time.isoformat(),
                            'parameters': params,
                            'stage_times': data_item.get('stage_times', {})
                        }
                    
                    results.append(result)
        
        except Exception as e:
            self.logger.error(f"批量推理过程中发生异常: {str(e)}")
            # 为所有成功预处理的数据创建失败结果
            for data in successful_data:
                config = data['config']
                result = {
                    'video_path': config.get('video_path'),
                    'query': config.get('query', ''),
                    'description': None,
                    'success': False,
                    'error_message': f"批量推理异常: {str(e)}",
                    'processing_time': 0,
                    'timestamp': datetime.now().isoformat(),
                    'parameters': {},
                    'stage_times': data.get('stage_times', {})
                }
                results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        self.logger.info(f"GPU批量推理完成，成功: {success_count}/{len(batch_data)}")
        
        return results
    
    def cleanup(self):
        """
        清理资源
        """
        if self.is_loaded:
            self.logger.info("清理模型资源...")
            
            # 清理CUDA缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                self.logger.info("CUDA缓存已清理")
            
            # 强制垃圾回收
            gc.collect()
            
            # 重置状态
            self.model = None
            self.tokenizer = None
            self.processor = None
            self.is_loaded = False
            
            self.logger.info("资源清理完成")


def parse_batch_arguments():
    """
    解析批量处理命令行参数
    """
    parser = argparse.ArgumentParser(description='ShareGPT4Video 批量视频描述生成工具')
    
    # 模型参数
    parser.add_argument('--model-path', default='Lin-Chen/sharegpt4video-8b',
                       help='模型路径 (默认: Lin-Chen/sharegpt4video-8b)')
    parser.add_argument('--device', default='Auto', choices=['Auto', 'CUDA', 'CPU'],
                       help='计算设备 (默认: Auto)')
    parser.add_argument('--conv-mode', default='llava_llama_3',
                       help='对话模式 (默认: llava_llama_3)')
    parser.add_argument('--disable-smart-loading', action='store_true',
                       help='禁用智能加载功能，获得更快的预加载速度（适用于模型已缓存的情况）')
    
    # 输入参数
    parser.add_argument('--videos', nargs='+', help='视频文件路径列表')
    parser.add_argument('--video-dir', help='视频文件夹路径')
    parser.add_argument('--config-file', help='批量配置JSON文件路径')
    parser.add_argument('--query', default='Describe this video in detail.',
                       help='默认查询内容')
    
    # 输出参数
    parser.add_argument('--output-file', help='输出结果JSON文件路径')
    parser.add_argument('--output-format', choices=['json', 'plain'], default='json',
                       help='输出格式 (默认: json)')
    
    # GPU优化参数
    parser.add_argument('--gpu-optimized', action='store_true',
                       help='启用GPU优化批处理模式，提升大量视频处理性能')
    parser.add_argument('--batch-size', type=int, default=2,
                       help='GPU批处理大小，同时处理的视频数量 (默认: 2)')
    parser.add_argument('--max-workers', type=int, default=4,
                       help='预处理线程数 (默认: 4)')
    
    # 生成参数
    parser.add_argument('--num-frames', type=int, default=16,
                       help='视频采样帧数 (默认: 16)')
    parser.add_argument('--do-sample', type=str, choices=['True', 'False'], default='True',
                       help='是否使用采样生成 (默认: True)')
    parser.add_argument('--top-p', type=float, default=0.9,
                       help='nucleus采样参数 (默认: 0.9)')
    parser.add_argument('--temperature', type=float, default=1.0,
                       help='生成温度 (默认: 1.0)')
    parser.add_argument('--max-new-tokens', type=int, default=None,
                       help='最大生成token数 (默认: None，无限制生成)')
    parser.add_argument('--num-beams', type=int, default=1,
                       help='束搜索束数 (默认: 1)')
    
    # 日志参数
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='日志级别 (默认: INFO)')
    parser.add_argument('--silent', action='store_true',
                       help='静默模式，不输出到控制台')
    parser.add_argument('--no-file-log', action='store_true',
                       help='禁用文件日志')
    
    return parser.parse_args()


def collect_video_configs(args) -> List[Dict[str, Any]]:
    """
    收集视频配置
    
    Args:
        args: 命令行参数
        
    Returns:
        List[Dict[str, Any]]: 视频配置列表
    """
    configs = []
    
    # 从配置文件读取
    if args.config_file:
        try:
            with open(args.config_file, 'r', encoding='utf-8') as f:
                file_configs = json.load(f)
                if isinstance(file_configs, list):
                    configs.extend(file_configs)
                else:
                    configs.append(file_configs)
        except Exception as e:
            logging.error(f"读取配置文件失败: {e}")
    
    # 从视频列表添加
    if args.videos:
        for video_path in args.videos:
            config = {
                'video_path': video_path,
                'query': args.query,
                'num_frames': args.num_frames,
                'do_sample': args.do_sample.lower() == 'true',
                'top_p': args.top_p,
                'temperature': args.temperature,
                'max_new_tokens': args.max_new_tokens,
                'num_beams': args.num_beams
            }
            configs.append(config)
    
    # 从视频文件夹添加
    if args.video_dir:
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
        try:
            for filename in os.listdir(args.video_dir):
                if any(filename.lower().endswith(ext) for ext in video_extensions):
                    video_path = os.path.join(args.video_dir, filename)
                    config = {
                        'video_path': video_path,
                        'query': args.query,
                        'num_frames': args.num_frames,
                        'do_sample': args.do_sample.lower() == 'true',
                        'top_p': args.top_p,
                        'temperature': args.temperature,
                        'max_new_tokens': args.max_new_tokens,
                        'num_beams': args.num_beams
                    }
                    configs.append(config)
        except Exception as e:
            logging.error(f"读取视频文件夹失败: {e}")
    
    return configs


def main():
    """
    批量处理主函数
    """
    logger = None
    try:
        # 解析参数
        args = parse_batch_arguments()
        
        # 设置日志
        logger = setup_comprehensive_logging(
            log_level=args.log_level,
            silent_mode=args.silent,
            enable_file_log=not args.no_file_log
        )
        
        logger.info("="*80)
        logger.info("ShareGPT4Video 批量处理程序开始运行")
        logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        # 收集视频配置
        video_configs = collect_video_configs(args)
        
        if not video_configs:
            logger.error("没有找到要处理的视频")
            if args.output_format == 'json' and not args.output_file:
                error_output = {
                    'summary': {
                        'total_videos': 0,
                        'successful_videos': 0,
                        'failed_videos': 0,
                        'total_time_seconds': 0,
                        'average_time_per_video': 0,
                        'timestamp': datetime.now().isoformat(),
                        'error': '没有找到要处理的视频'
                    },
                    'results': []
                }
                print(json.dumps(error_output, ensure_ascii=False, indent=2))
            elif not args.silent:
                print("错误: 没有找到要处理的视频")
                print("请使用 --videos, --video-dir 或 --config-file 参数指定视频")
            return 1
        
        logger.info(f"找到 {len(video_configs)} 个视频待处理")
        if not args.silent:
            print(f"找到 {len(video_configs)} 个视频待处理")
        
        # 创建批量处理器
        enable_smart_loading = not args.disable_smart_loading
        if args.disable_smart_loading:
            logger.info("智能加载已禁用，将使用传统加载方式获得更快的预加载速度")
        
        processor = BatchVideoProcessor(
            model_path=args.model_path,
            device=args.device,
            conv_mode=args.conv_mode,
            enable_smart_loading=enable_smart_loading
        )
        
        # 加载模型（只加载一次）
        logger.info("加载模型...")
        if not args.silent:
            print("正在加载模型...")
        
        if not processor.load_model():
            # 在处理结果前再次记录网络连接错误信息，方便用户查看
            logger.error("批量处理失败")
            logger.error("批量处理脚本执行失败")
            logger.error("网络连接问题：无法连接到 https://huggingface.co 下载模型文件。请检查网络连接或配置离线模式")
            
            if args.output_format == 'json' and not args.output_file:
                error_output = {
                    'summary': {
                        'total_videos': len(video_configs),
                        'successful_videos': 0,
                        'failed_videos': len(video_configs),
                        'total_time_seconds': 0,
                        'average_time_per_video': 0,
                        'timestamp': datetime.now().isoformat(),
                        'error': '网络连接问题：无法连接到 https://huggingface.co 下载模型文件'
                    },
                    'results': []
                }
                print(json.dumps(error_output, ensure_ascii=False, indent=2))
            elif not args.silent:
                print("错误: 网络连接问题，无法连接到 https://huggingface.co 下载模型文件")
            return 1
        
        logger.info("模型加载成功")
        if not args.silent:
            print("模型加载成功，开始批量处理...")
        
        try:
            # 批量处理视频
            start_time = datetime.now()
            
            # 根据用户选择使用不同的处理方法
            if args.gpu_optimized:
                logger.info(f"使用GPU优化批处理模式 (批处理大小: {args.batch_size}, 预处理线程: {args.max_workers})")
                if not args.silent:
                    print(f"使用GPU优化批处理模式 (批处理大小: {args.batch_size}, 预处理线程: {args.max_workers})")
                results = processor.process_videos_batch_gpu_optimized(
                    video_configs, 
                    batch_size=args.batch_size, 
                    max_workers=args.max_workers
                )
            else:
                logger.info("使用标准批处理模式")
                if not args.silent:
                    print("使用标准批处理模式")
                results = processor.process_videos_batch(video_configs)
            
            end_time = datetime.now()
            
            total_time = (end_time - start_time).total_seconds()
            successful_count = sum(1 for r in results if r['success'])
            
            logger.info(f"批量处理完成，总耗时: {total_time:.2f}秒")
            logger.info(f"成功处理: {successful_count}/{len(video_configs)} 个视频")
            
            if not args.silent:
                print(f"\n批量处理完成！")
                print(f"总耗时: {total_time:.2f}秒")
                print(f"成功处理: {successful_count}/{len(video_configs)} 个视频")
            
            # 输出结果
            if args.output_format == 'json':
                output_data = {
                    'summary': {
                        'total_videos': len(video_configs),
                        'successful_videos': successful_count,
                        'failed_videos': len(video_configs) - successful_count,
                        'total_time_seconds': total_time,
                        'average_time_per_video': total_time / len(video_configs) if video_configs else 0,
                        'timestamp': end_time.isoformat()
                    },
                    'results': results
                }
                
                output_json = json.dumps(output_data, ensure_ascii=False, indent=2)
                
                if args.output_file:
                    with open(args.output_file, 'w', encoding='utf-8') as f:
                        f.write(output_json)
                    logger.info(f"结果已保存到: {args.output_file}")
                    if not args.silent:
                        print(f"结果已保存到: {args.output_file}")
                else:
                    print(output_json)
            
            else:  # plain format
                for i, result in enumerate(results, 1):
                    print(f"\n=== 视频 {i}/{len(results)} ===")
                    print(f"路径: {result['video_path']}")
                    print(f"查询: {result['query']}")
                    print(f"成功: {'是' if result['success'] else '否'}")
                    print(f"处理时间: {result['processing_time']:.2f}秒")
                    if result['description']:
                        print(f"描述: {result['description']}")
                    else:
                        print("描述: 处理失败")
            
            return 0
            
        finally:
            # 清理资源
            processor.cleanup()
    
    except KeyboardInterrupt:
        if logger:
            logger.warning("用户中断执行")
        if not args.silent:
            print("\n执行被用户中断")
        return 1
    
    except Exception as e:
        if logger:
            logger.error(f"程序执行失败: {str(e)}")
            logger.error(traceback.format_exc())
        
        # 如果是JSON输出模式且没有指定输出文件，输出错误的JSON格式
        if args.output_format == 'json' and not args.output_file:
            error_output = {
                'summary': {
                    'total_videos': 0,
                    'successful_videos': 0,
                    'failed_videos': 0,
                    'total_time_seconds': 0,
                    'average_time_per_video': 0,
                    'timestamp': datetime.now().isoformat(),
                    'error': str(e)
                },
                'results': []
            }
            print(json.dumps(error_output, ensure_ascii=False, indent=2))
        elif not args.silent:
            print(f"错误: {e}")
        return 1
    
    finally:
        if logger:
            # 计算总耗时
            try:
                if 'start_time' in locals():
                    total_time = (datetime.now() - start_time).total_seconds()
                    logger.info(f"批量处理完成，总耗时: {total_time:.2f}秒")
                    logger.info(f"平均每个视频: {total_time:.2f}秒")
                else:
                    logger.info("批量处理完成，总耗时: 0.00秒")
                    logger.info("平均每个视频: 0.00秒")
            except:
                logger.info("批量处理完成")
            
            logger.info("所有视频处理完成！")
            logger.info("="*80)
            logger.info("ShareGPT4Video 批量处理程序运行结束")
            logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*80)


if __name__ == '__main__':
    sys.exit(main())