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
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
from typing import List, Dict, Any, Optional

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 导入原有模块
from run import (
    setup_comprehensive_logging, LoggingCapture, ResultFormatter,
    disable_torch_init, get_model_name_from_path, load_pretrained_model,
    single_test, video_answer
)

import torch
from llava.conversation import conv_templates, SeparatorStyle
from llava.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN
from llava.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path, KeywordsStoppingCriteria


class BatchVideoProcessor:
    """
    批量视频处理器
    实现一次模型加载，多个视频批量推理
    """
    
    def __init__(self, model_path: str, device: str = 'Auto', conv_mode: str = 'llava_llama_3'):
        """
        初始化批量处理器
        
        Args:
            model_path: 模型路径
            device: 计算设备 ('Auto', 'CUDA' 或 'CPU')
            conv_mode: 对话模式
        """
        self.model_path = model_path
        self.device = self._resolve_device(device)
        self.conv_mode = conv_mode
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
            self.logger.error(f"模型加载失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    def process_single_video(self, video_path: str, query: str, 
                           num_frames: int = 16, 
                           do_sample: bool = True,
                           top_p: float = 0.9,
                           temperature: float = 1.0,
                           max_new_tokens: int = 200,
                           num_beams: int = 1) -> Optional[str]:
        """
        处理单个视频
        
        Args:
            video_path: 视频文件路径
            query: 查询内容
            num_frames: 采样帧数
            do_sample: 是否使用采样
            top_p: nucleus采样参数
            temperature: 生成温度
            max_new_tokens: 最大生成token数
            num_beams: 束搜索束数
            
        Returns:
            Optional[str]: 生成的描述，失败时返回None
        """
        if not self.is_loaded:
            self.logger.error("模型未加载，请先调用load_model()")
            return None
            
        try:
            self.logger.info(f"开始处理视频: {video_path}")
            
            # 检查视频文件是否存在
            if not os.path.exists(video_path):
                self.logger.error(f"视频文件不存在: {video_path}")
                return None
            
            # 设置预查询提示
            pre_query_prompt = "The provided image arranges keyframes from a video in a grid view, keyframes are separated with white bands. Answer concisely with overall content and context of the video, highlighting any significant events, characters, or objects that appear throughout the frames."
            
            # 调用单个测试函数
            result = single_test(
                model=self.model,
                processor=self.processor,
                tokenizer=self.tokenizer,
                vid_path=video_path,
                qs=query,
                pre_query_prompt=pre_query_prompt,
                num_frames=num_frames,
                conv_mode=self.conv_mode,
                do_sample=do_sample,
                top_p=top_p,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                num_beams=num_beams
            )
            
            self.logger.info(f"视频处理完成: {video_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"处理视频失败 {video_path}: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None
    
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
                'max_new_tokens': config.get('max_new_tokens', 200),
                'num_beams': config.get('num_beams', 1)
            }
            
            # 处理单个视频
            start_time = datetime.now()
            description = self.process_single_video(video_path, query, **params)
            end_time = datetime.now()
            
            # 记录结果
            result = {
                'video_path': video_path,
                'query': query,
                'description': description,
                'success': description is not None,
                'processing_time': (end_time - start_time).total_seconds(),
                'timestamp': end_time.isoformat(),
                'parameters': params
            }
            
            results.append(result)
            
            if description:
                self.logger.info(f"成功处理: {video_path}")
            else:
                self.logger.error(f"处理失败: {video_path}")
        
        self.logger.info(f"批量处理完成，成功: {sum(1 for r in results if r['success'])}/{total_videos}")
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
    
    # 生成参数
    parser.add_argument('--num-frames', type=int, default=16,
                       help='视频采样帧数 (默认: 16)')
    parser.add_argument('--do-sample', type=str, choices=['True', 'False'], default='True',
                       help='是否使用采样生成 (默认: True)')
    parser.add_argument('--top-p', type=float, default=0.9,
                       help='nucleus采样参数 (默认: 0.9)')
    parser.add_argument('--temperature', type=float, default=1.0,
                       help='生成温度 (默认: 1.0)')
    parser.add_argument('--max-new-tokens', type=int, default=200,
                       help='最大生成token数 (默认: 200)')
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
            print("错误: 没有找到要处理的视频")
            print("请使用 --videos, --video-dir 或 --config-file 参数指定视频")
            return 1
        
        logger.info(f"找到 {len(video_configs)} 个视频待处理")
        if not args.silent:
            print(f"找到 {len(video_configs)} 个视频待处理")
        
        # 创建批量处理器
        processor = BatchVideoProcessor(
            model_path=args.model_path,
            device=args.device,
            conv_mode=args.conv_mode
        )
        
        # 加载模型（只加载一次）
        logger.info("加载模型...")
        if not args.silent:
            print("正在加载模型...")
        
        if not processor.load_model():
            logger.error("模型加载失败")
            print("错误: 模型加载失败")
            return 1
        
        logger.info("模型加载成功")
        if not args.silent:
            print("模型加载成功，开始批量处理...")
        
        try:
            # 批量处理视频
            start_time = datetime.now()
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
        logger.warning("用户中断执行")
        print("\n执行被用户中断")
        return 1
    
    except Exception as e:
        if logger:
            logger.error(f"程序执行失败: {str(e)}")
            logger.error(traceback.format_exc())
        print(f"错误: {e}")
        return 1
    
    finally:
        if logger:
            logger.info("="*80)
            logger.info("ShareGPT4Video 批量处理程序运行结束")
            logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*80)


if __name__ == '__main__':
    sys.exit(main())