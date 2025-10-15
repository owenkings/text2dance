# -*- coding: utf-8 -*-
"""
ShareGPT4Video视频描述算法
基于ShareGPT4Video模型实现视频内容描述
"""

import os
import json
import logging
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from ..base_algorithm import VideoDescriptionAlgorithm


class ShareGPT4VideoAlgorithm(VideoDescriptionAlgorithm):
    """ShareGPT4Video视频描述算法"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager, "sharegpt4video")
        self.description = "ShareGPT4Video视频内容描述算法"
        
        # 获取模型路径
        self.model_path = config_manager.get(
            'algorithms.video_description.sharegpt4video.model_path',
            'E:/Tiany/huggingface/ShareGPT4Video-8B'
        )
        
        # ShareGPT4Video脚本路径
        self.script_path = Path(__file__).parent / "ShareGPT4Video" / "run.py"
        
        self.logger = logging.getLogger(f"{__name__}.{self.algorithm_name}")
        
    def _initialize(self):
        """初始化算法（实现抽象方法）"""
        self.logger.info("初始化ShareGPT4Video算法")
        # 初始化相关资源
        self.model_path = self.config.get(
            'algorithms.video_description.sharegpt4video.model_path',
            'E:/Tiany/huggingface/ShareGPT4Video-8B'
        )
        
    def _load_model(self) -> bool:
        """加载模型（实现抽象方法）"""
        try:
            # 检查模型是否存在
            model_path = Path(self.model_path)
            if not model_path.exists():
                self.logger.warning(f"模型路径不存在: {self.model_path}")
                return False
                
            self.logger.info(f"ShareGPT4Video模型路径: {self.model_path}")
            return True
        except Exception as e:
            self.logger.error(f"加载ShareGPT4Video模型失败: {e}")
            return False
    
    def _process_impl(self, input_path: str, output_path: str, 
                     progress_callback: Optional[Callable[[float], None]] = None,
                     **kwargs) -> Dict[str, Any]:
        """实现视频描述处理"""
        try:
            self.logger.info(f"开始处理视频: {input_path}")
            
            # 检查模型是否存在，如果不存在则初始化镜像管理器
            mirror_log = self._check_and_initialize_model()
            
            if progress_callback:
                progress_callback(10.0)
            
            # 准备命令参数
            query = kwargs.get('query', '请详细描述这个视频的内容，包括场景、人物、动作和情节。')
            device = kwargs.get('device', 'cuda')
            conv_mode = kwargs.get('conv_mode', 'llava_v1')
            
            # 构建命令 - 使用新的参数格式
            cmd = [
                sys.executable,
                str(self.script_path),
                '--model-path', self.model_path,
                '--video', input_path,
                '--conv-mode', conv_mode,
                '--query', query,
                '--device', device,
                '--output-format', 'json',
                '--log-level', 'INFO'
            ]
            
            self.logger.info(f"执行命令: {' '.join(cmd)}")
            
            if progress_callback:
                progress_callback(20.0)
            
            # 执行命令并捕获输出
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if progress_callback:
                progress_callback(60.0)
            
            # 记录所有输出
            if result.stdout:
                self.logger.info(f"标准输出: {result.stdout}")
            if result.stderr:
                self.logger.warning(f"标准错误: {result.stderr}")
            
            # 检查返回码
            if result.returncode != 0:
                error_msg = f"ShareGPT4Video执行失败，返回码: {result.returncode}"
                if result.stderr:
                    error_msg += f"\n错误信息: {result.stderr}"
                raise RuntimeError(error_msg)
            
            if progress_callback:
                progress_callback(80.0)
            
            # 解析JSON输出
            try:
                # 提取JSON部分（可能包含其他输出）
                output_lines = result.stdout.strip().split('\n')
                json_output = None
                
                # 查找JSON输出
                for i, line in enumerate(output_lines):
                    if line.strip().startswith('{'):
                        # 尝试解析从这一行开始的JSON
                        json_text = '\n'.join(output_lines[i:])
                        try:
                            json_output = json.loads(json_text)
                            break
                        except json.JSONDecodeError:
                            continue
                
                if json_output and json_output.get('status') == 'success':
                    description = json_output.get('description', '')
                    metadata = json_output.get('metadata', {})
                    
                    # 合并镜像管理器日志和处理日志
                    combined_log = ""
                    if mirror_log:
                        combined_log += "=== 镜像管理器初始化日志 ===\n" + mirror_log + "\n\n"
                    combined_log += "=== 模型处理日志 ===\n"
                    combined_log += result.stdout + "\n" + result.stderr if result.stderr else result.stdout
                    
                    final_result = {
                        'algorithm': self.algorithm_name,
                        'input_path': input_path,
                        'output_path': output_path,
                        'description': description,
                        'processing_log': combined_log,
                        'parameters': {
                            'query': query,
                            'device': device,
                            'conv_mode': conv_mode,
                            'model_path': self.model_path
                        },
                        'metadata': metadata,
                        'status': 'completed'
                    }
                elif json_output and json_output.get('status') == 'error':
                    error_msg = json_output.get('error_message', '未知错误')
                    raise RuntimeError(f"ShareGPT4Video处理失败: {error_msg}")
                else:
                    # 回退到旧的解析方法
                    description = self._extract_description_fallback(result.stdout)
                    # 合并镜像管理器日志和处理日志
                    combined_log = ""
                    if mirror_log:
                        combined_log += "=== 镜像管理器初始化日志 ===\n" + mirror_log + "\n\n"
                    combined_log += "=== 模型处理日志 ===\n"
                    combined_log += result.stdout + "\n" + result.stderr if result.stderr else result.stdout
                    
                    final_result = {
                        'algorithm': self.algorithm_name,
                        'input_path': input_path,
                        'output_path': output_path,
                        'description': description,
                        'processing_log': combined_log,
                        'parameters': {
                            'query': query,
                            'device': device,
                            'conv_mode': conv_mode,
                            'model_path': self.model_path
                        },
                        'status': 'completed'
                    }
                    
            except Exception as parse_error:
                self.logger.warning(f"JSON解析失败，使用备用方法: {parse_error}")
                # 回退到旧的解析方法
                description = self._extract_description_fallback(result.stdout)
                # 合并镜像管理器日志和处理日志
                combined_log = ""
                if mirror_log:
                    combined_log += "=== 镜像管理器初始化日志 ===\n" + mirror_log + "\n\n"
                combined_log += "=== 模型处理日志 ===\n"
                combined_log += result.stdout + "\n" + result.stderr if result.stderr else result.stdout
                
                final_result = {
                    'algorithm': self.algorithm_name,
                    'input_path': input_path,
                    'output_path': output_path,
                    'description': description,
                    'processing_log': combined_log,
                    'parameters': {
                        'query': query,
                        'device': device,
                        'conv_mode': conv_mode,
                        'model_path': self.model_path
                    },
                    'status': 'completed'
                }
            
            if progress_callback:
                progress_callback(90.0)
            
            # 保存结果到JSON文件
            if output_path:
                output_file = Path(output_path) / f"{Path(input_path).stem}_sharegpt4video_result.json"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(final_result, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"结果已保存到: {output_file}")
            
            if progress_callback:
                progress_callback(100.0)
            
            return final_result
            

        except Exception as e:
            self.logger.error(f"处理视频时发生错误: {e}")
            raise e
    
    def _extract_description_fallback(self, output: str) -> str:
        """备用的描述提取方法"""
        lines = output.strip().split('\n')
        description_lines = []
        
        for line in lines:
            line = line.strip()
            # 检查是否是描述内容
            if line and not any(keyword in line.lower() for keyword in 
                              ['loading', 'warning', 'error', 'info', 'debug', 
                               'model', 'device', 'cuda', 'torch', 'accelerate']):
                description_lines.append(line)
        
        if description_lines:
            # 返回完整的描述内容，不进行截断
            return '\n'.join(description_lines)  # 返回所有描述行
        
        # 如果没有找到明确的描述，尝试从完整输出中提取
        for line in reversed(lines):
            if line and len(line) > 20 and not any(keyword in line.lower() for keyword in 
                                                  ['loading', 'warning', 'error', 'model', 'device']):
                return line
        
        return "视频描述生成完成，但未能提取到具体描述内容。"
    
    def _check_and_initialize_model(self) -> str:
        """检查模型是否存在，如果不存在则初始化镜像管理器"""
        import io
        import contextlib
        
        # 检查模型路径是否存在
        model_exists = os.path.exists(self.model_path) and os.path.isdir(self.model_path)
        
        if model_exists:
            # 检查模型文件是否完整
            required_files = ['config.json', 'pytorch_model.bin', 'tokenizer.json']
            model_complete = all(os.path.exists(os.path.join(self.model_path, f)) for f in required_files)
            
            if model_complete:
                return ""  # 模型存在且完整，无需初始化镜像管理器
        
        # 模型不存在或不完整，需要初始化镜像管理器
        self.logger.info("检测到模型文件缺失，正在初始化镜像管理器...")
        
        try:
            # 导入镜像管理器
            from .ShareGPT4Video.llava.model.mirror_manager import get_mirror_manager
            
            # 捕获镜像管理器的输出
            output_buffer = io.StringIO()
            
            with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
                mirror_manager = get_mirror_manager()
                success = mirror_manager.initialize_smart_mirror()
            
            mirror_output = output_buffer.getvalue()
            
            if success:
                self.logger.info("镜像管理器初始化成功")
                return mirror_output
            else:
                self.logger.warning("镜像管理器初始化失败，但将继续尝试处理")
                return mirror_output + "\n⚠️ 镜像管理器初始化失败，可能影响模型下载"
                
        except Exception as e:
            error_msg = f"镜像管理器初始化异常: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
    
    def get_supported_formats(self) -> list:
        """获取支持的视频格式"""
        return ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    
    def get_algorithm_info(self) -> Dict[str, Any]:
        """获取算法信息"""
        return {
            'name': self.algorithm_name,
            'description': 'ShareGPT4Video视频内容描述算法',
            'model_path': self.model_path,
            'supported_formats': self.get_supported_formats(),
            'parameters': {
                'query': {
                    'type': 'string',
                    'description': '视频描述查询要求',
                    'default': '请详细描述这个视频的内容，包括场景、人物、动作和情节。'
                },
                'device': {
                    'type': 'string',
                    'description': '计算设备',
                    'default': 'cuda',
                    'options': ['cuda', 'cpu']
                },
                'conv_mode': {
                    'type': 'string',
                    'description': '对话模式',
                    'default': 'llava_v1',
                    'options': ['llava_v1', 'llava_llama_2']
                }
            }
        }