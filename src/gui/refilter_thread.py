import os
import json
import time
from PyQt5.QtCore import QThread, pyqtSignal


class RefilterThread(QThread):
    """重新过滤处理线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int)  # 当前进度, 总数
    file_processed = pyqtSignal(str, bool, str)  # 文件路径, 是否成功, 消息
    error_occurred = pyqtSignal(str)  # 错误消息
    
    def __init__(self, selected_videos, parent_widget):
        super().__init__()
        self.selected_videos = selected_videos
        self.parent_widget = parent_widget
        self.is_running = True
    
    def run(self):
        """运行重新过滤处理"""
        try:
            total_videos = len(self.selected_videos)
            
            for i, video_name in enumerate(self.selected_videos):
                if not self.is_running:
                    break
                
                # 更新进度
                self.progress_updated.emit(i, total_videos)
                
                # 处理单个视频
                success, message = self._process_single_video(video_name)
                self.file_processed.emit(video_name, success, message)
                
                # 短暂延迟，避免过快处理
                time.sleep(0.1)
            
            # 最终进度更新
            if self.is_running:
                self.progress_updated.emit(total_videos, total_videos)
                
        except Exception as e:
            self.error_occurred.emit(f"重新过滤处理出错: {str(e)}")
    
    def _process_single_video(self, video_path):
        """处理单个视频的重新过滤"""
        try:
            # 获取视频文件名（不含路径）
            video_name = os.path.basename(video_path)
            # 获取视频文件的基本名称（不含扩展名）
            video_base_name = os.path.splitext(video_name)[0]
            # 获取视频文件所在目录
            video_dir = os.path.dirname(video_path)
            
            # 查找现有的结果文件 - 使用与详细结果显示功能一致的缓存目录
            cache_dir = os.path.join(video_dir, '.text2dance_cache', 'video_description_results')
            
            if not os.path.exists(cache_dir):
                return False, f"缓存目录不存在: {cache_dir}"
            
            # 根据当前选中的描述长度查找特定的结果文件
            description_length = self._get_description_length_setting()
            length_text_english = self._get_length_text_english(description_length)
            
            # 支持多种文件后缀
            possible_extensions = ['.json', '.txt', '.csv', '.md']
            target_file = None
            
            for ext in possible_extensions:
                candidate_file = os.path.join(cache_dir, f"{video_base_name}_{length_text_english}{ext}")
                if os.path.exists(candidate_file):
                    target_file = candidate_file
                    break
            
            if not target_file:
                return False, f"在 {cache_dir} 中未找到结果文件 {video_base_name}_{length_text_english}.*（支持的格式：json/txt/csv/md）"
            
            # 处理目标结果文件
            try:
                # 根据文件扩展名选择读取方式
                file_ext = os.path.splitext(target_file)[1].lower()
                
                if file_ext == '.json':
                    # JSON格式
                    with open(target_file, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                elif file_ext in ['.txt', '.md']:
                    # 文本格式，尝试解析为JSON，如果失败则创建基本结构
                    with open(target_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    try:
                        result_data = json.loads(content)
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，将内容作为描述
                        result_data = {'description': content}
                elif file_ext == '.csv':
                    # CSV格式，简单处理（假设第一行是描述）
                    with open(target_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    if lines:
                        # 假设CSV的第一行包含描述信息
                        description = lines[0].strip()
                        result_data = {'description': description}
                    else:
                        result_data = {'description': ''}
                else:
                    return False, f"不支持的文件格式: {file_ext}"
                
                # 检查是否已经有action_description且不为空
                if result_data.get('action_description') and result_data.get('action_filter_applied'):
                    self.parent_widget._log_message(f"⏭️ 跳过文件 {os.path.basename(target_file)}：已有过滤结果")
                    return True, "已有过滤结果，跳过处理"
                
                # 获取原始描述
                original_description = result_data.get('description', '')
                if not original_description:
                    return False, f"文件 {os.path.basename(target_file)} 中描述为空"
                
                # 记录开始过滤
                self.parent_widget._log_message(f"正在对文件 {os.path.basename(target_file)} 进行动作描述过滤...")
                self.parent_widget._log_message(f"原始描述: {original_description[:100]}...")
                
                # 调用动作描述过滤方法
                try:
                    if hasattr(self.parent_widget, '_filter_action_description'):
                        filter_result = self.parent_widget._filter_action_description(original_description)
                        filtered_description = filter_result['description']
                        filter_success = filter_result['filter_success']
                    else:
                        self.parent_widget._log_message("❌ 父组件缺少 _filter_action_description 方法")
                        return False, "父组件缺少 _filter_action_description 方法"
                except Exception as e:
                    self.parent_widget._log_message(f"❌ 调用过滤方法时出错: {str(e)}")
                    return False, f"调用过滤方法时出错: {str(e)}"
                
                # 更新结果文件的action_description字段
                if filter_success:
                    result_data['action_description'] = filtered_description
                    result_data['action_filter_applied'] = True
                    result_data['filter_updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.parent_widget._log_message(f"✅ 过滤成功")
                    self.parent_widget._log_message(f"过滤后描述: {filtered_description[:100]}...")
                else:
                    result_data['action_description'] = ""
                    result_data['action_filter_applied'] = False
                    result_data['filter_updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.parent_widget._log_message(f"⚠️ 过滤未生效，保持原始描述")
                
                # 根据文件扩展名选择保存方式
                if file_ext == '.json':
                    # JSON格式
                    with open(target_file, 'w', encoding='utf-8') as f:
                        json.dump(result_data, f, ensure_ascii=False, indent=2)
                elif file_ext in ['.txt', '.md']:
                    # 文本格式，保存为JSON
                    with open(target_file, 'w', encoding='utf-8') as f:
                        json.dump(result_data, f, ensure_ascii=False, indent=2)
                elif file_ext == '.csv':
                    # CSV格式，简单保存（保持原有格式但更新描述）
                    with open(target_file, 'w', encoding='utf-8', newline='') as f:
                        # 简单的CSV格式，将描述和动作描述写入
                        f.write(f"{result_data.get('description', '')}\n")
                        if result_data.get('action_description'):
                            f.write(f"{result_data.get('action_description', '')}\n")
                else:
                    return False, f"不支持保存到文件格式: {file_ext}"
                
                # 同步更新description文件夹中的过滤文件
                self._sync_description_folder_files(video_base_name, video_dir, result_data, filter_success)
                
                return True, "重新过滤完成"
                
            except Exception as e:
                self.parent_widget._log_message(f"❌ 处理文件 {os.path.basename(target_file)} 失败: {str(e)}")
                return False, f"处理文件失败: {str(e)}"
                
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            self.parent_widget._log_message(f"❌ {error_msg}")
            return False, error_msg
    
    def _get_description_length_setting(self):
        """获取当前描述长度设置"""
        try:
            # 从父组件的描述长度下拉框获取设置
            if hasattr(self.parent_widget, 'center_description_length_combo'):
                description_length_text = self.parent_widget.center_description_length_combo.currentText()
                if description_length_text:
                    return description_length_text
            
            # 默认返回中等长度
            return '中'
        except:
            return '中'
    
    def _get_length_text_english(self, chinese_text):
        """将中文描述长度转换为英文"""
        length_mapping = {
            "极短": "Extra Short",
            "短": "Short", 
            "中": "Medium",
            "长": "Long",
            "极长": "Extra Long"
        }
        return length_mapping.get(chinese_text, "Medium")
    
    def _check_action_filter_applied(self, video_base_name, video_dir):
        """检查视频是否已成功应用动作过滤"""
        try:
            # 获取视频名称（不含路径）
            video_name = video_base_name
            
            # 优先检查标记文件
            marker_file = os.path.join(video_dir, video_base_name, 'description', '.action_filter_applied')
            if os.path.exists(marker_file):
                try:
                    with open(marker_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 检查标记文件中是否包含该视频名称
                    if video_name in content:
                        return True
                except:
                    pass
            
            # 如果标记文件不存在或没有记录该视频，则检查统一的描述文件
            description_length = self._get_description_length_setting()
            length_text_english = self._get_length_text_english(description_length)
            unified_result_file = os.path.join(video_dir, video_base_name, 'description', f'{video_base_name}_{length_text_english}.json')
            
            if os.path.exists(unified_result_file):
                try:
                    with open(unified_result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    # 如果文件中明确标记已过滤，则跳过
                    if result.get('action_filter_applied', False):
                        return True
                except:
                    pass
            
            # 兼容旧版本文件格式
            old_result_files = [
                os.path.join(video_dir, video_base_name, 'description', 'result_api.json'),
                os.path.join(video_dir, video_base_name, 'description', 'result_local.json'),
                os.path.join(video_dir, video_base_name, 'description', 'result.json')
            ]
            
            for result_file in old_result_files:
                if os.path.exists(result_file):
                    try:
                        with open(result_file, 'r', encoding='utf-8') as f:
                            result = json.load(f)
                        # 如果文件中明确标记已过滤，则跳过
                        if result.get('action_filter_applied', False):
                            return True
                    except:
                        continue
            
            return False
        except:
            return False
    
    def _update_result_files(self, video_base_name, video_dir, original_description, action_description, filter_success):
        """更新结果文件，添加action_description字段"""
        try:
            description_dir = os.path.join(video_dir, video_base_name, 'description')
            result_files = [
                os.path.join(description_dir, 'result_api.json'),
                os.path.join(description_dir, 'result_local.json'),
                os.path.join(description_dir, 'result.json')
            ]
            
            for result_file in result_files:
                if os.path.exists(result_file):
                    try:
                        # 读取现有结果
                        with open(result_file, 'r', encoding='utf-8') as f:
                            result = json.load(f)
                        
                        # 更新字段
                        result['description'] = original_description  # 保持原始描述
                        result['action_description'] = action_description  # 添加动作描述
                        result['action_filter_applied'] = filter_success  # 更新过滤状态
                        result['filter_updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')  # 添加更新时间
                        
                        # 保存更新后的结果
                        with open(result_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                            
                    except Exception as e:
                        self.parent_widget._log_message(f"更新结果文件失败 {result_file}: {str(e)}")
                        
        except Exception as e:
            self.parent_widget._log_message(f"更新结果文件失败: {str(e)}")
    
    def _mark_action_filter_applied(self, video_base_name, video_dir):
        """标记视频已成功应用动作过滤"""
        try:
            # 获取视频名称（不含路径）
            video_name = video_base_name
            
            description_dir = os.path.join(video_dir, video_base_name, 'description')
            if not os.path.exists(description_dir):
                os.makedirs(description_dir, exist_ok=True)
            
            # 创建或更新标记文件
            marker_file = os.path.join(description_dir, '.action_filter_applied')
            
            # 读取现有内容（如果文件存在）
            existing_videos = set()
            if os.path.exists(marker_file):
                try:
                    with open(marker_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 解析已有的视频名称
                    for line in content.split('\n'):
                        if line.strip() and 'Video:' in line:
                            existing_video = line.split('Video:')[1].split(',')[0].strip()
                            existing_videos.add(existing_video)
                except:
                    pass
            
            # 检查视频是否已在标记文件中
            if video_name not in existing_videos:
                # 添加新的视频记录
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                new_entry = f"Video: {video_name}, Action filter applied at: {timestamp}\n"
                
                with open(marker_file, 'a', encoding='utf-8') as f:
                    f.write(new_entry)
                    
                self.parent_widget._log_message(f"已将视频 {video_name} 添加到标记文件")
            else:
                self.parent_widget._log_message(f"视频 {video_name} 已在标记文件中，跳过添加")
                
        except Exception as e:
            self.parent_widget._log_message(f"创建标记文件失败: {str(e)}")
    
    def _sync_description_folder_files(self, video_base_name, video_dir, result_data, filter_success):
        """同步更新description文件夹中的过滤文件"""
        try:
            # 构建description文件夹路径
            description_dir = os.path.join(video_dir, video_base_name, 'description')
            
            if not os.path.exists(description_dir):
                self.parent_widget._log_message(f"⚠️ description文件夹不存在: {description_dir}")
                return
            
            # 查找description文件夹中的结果文件
            result_files = []
            for filename in os.listdir(description_dir):
                if filename.endswith(('.json', '.txt', '.csv', '.md')) and 'description' in filename:
                    result_files.append(os.path.join(description_dir, filename))
            
            if not result_files:
                self.parent_widget._log_message(f"⚠️ 在description文件夹中未找到描述文件")
                return
            
            # 更新每个找到的结果文件
            updated_count = 0
            for result_file in result_files:
                try:
                    file_ext = os.path.splitext(result_file)[1].lower()
                    
                    if file_ext == '.json':
                        # JSON格式 - 读取现有数据并更新
                        try:
                            with open(result_file, 'r', encoding='utf-8') as f:
                                existing_data = json.load(f)
                        except:
                            existing_data = {}
                        
                        # 更新字段
                        existing_data.update({
                            'action_description': result_data.get('action_description', ''),
                            'action_filter_applied': result_data.get('action_filter_applied', False),
                            'filter_updated_at': result_data.get('filter_updated_at', '')
                        })
                        
                        # 保存更新后的数据
                        with open(result_file, 'w', encoding='utf-8') as f:
                            json.dump(existing_data, f, ensure_ascii=False, indent=2)
                            
                    elif file_ext in ['.txt', '.md']:
                        # 文本格式 - 保存为JSON格式
                        with open(result_file, 'w', encoding='utf-8') as f:
                            json.dump(result_data, f, ensure_ascii=False, indent=2)
                            
                    elif file_ext == '.csv':
                        # CSV格式 - 简单保存
                        with open(result_file, 'w', encoding='utf-8', newline='') as f:
                            f.write(f"{result_data.get('description', '')}\n")
                            if result_data.get('action_description'):
                                f.write(f"{result_data.get('action_description', '')}\n")
                    
                    updated_count += 1
                    
                except Exception as e:
                    self.parent_widget._log_message(f"❌ 更新description文件失败 {os.path.basename(result_file)}: {str(e)}")
            
            if updated_count > 0:
                self.parent_widget._log_message(f"✅ 已同步更新 {updated_count} 个description文件")
            else:
                self.parent_widget._log_message(f"⚠️ 未能更新任何description文件")
                
        except Exception as e:
            self.parent_widget._log_message(f"❌ 同步description文件夹失败: {str(e)}")

    def stop(self):
        """停止处理"""
        self.is_running = False