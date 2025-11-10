import os
import json
import time
from PyQt5.QtCore import QThread, pyqtSignal, QMetaObject, Qt

class RefilterThread(QThread):
    """重新过滤处理线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int)  # 当前进度, 总数
    file_processed = pyqtSignal(str, bool, str)  # 文件路径, 是否成功, 消息
    error_occurred = pyqtSignal(str)  # 错误消息
    log_message = pyqtSignal(str)  # 日志消息（线程安全的日志记录）
    
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
                # 检查线程是否应该停止
                if not self.is_running:
                    self.log_message.emit("🛑 重新过滤处理已被用户停止")
                    break
                
                try:
                    # 更新进度（使用Qt::QueuedConnection确保线程安全）
                    self.progress_updated.emit(i, total_videos)
                    
                    # 处理单个视频
                    success, message = self._process_single_video(video_name)
                    
                    # 发送处理结果（使用Qt::QueuedConnection确保线程安全）
                    self.file_processed.emit(video_name, success, message)
                    
                    # 短暂延迟，避免过快处理并允许GUI响应
                    self.msleep(100)  # 使用QThread的msleep而不是time.sleep
                    
                except Exception as e:
                    # 处理单个视频时的异常
                    error_msg = f"处理视频 {video_name} 时出错: {str(e)}"
                    self.file_processed.emit(video_name, False, error_msg)
                    continue
            
            # 最终进度更新
            if self.is_running:
                self.progress_updated.emit(total_videos, total_videos)
                
        except Exception as e:
            # 整体处理异常
            error_msg = f"重新过滤处理出错: {str(e)}"
            self.error_occurred.emit(error_msg)
    
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
            
            # 首先在缓存目录中查找
            for ext in possible_extensions:
                # 尝试查找带模型后缀的文件（新格式）
                for model_suffix in ['local', 'api']:
                    candidate_file = os.path.join(cache_dir, f"{video_base_name}_{length_text_english}_{model_suffix}{ext}")
                    if os.path.exists(candidate_file):
                        target_file = candidate_file
                        break
                
                # 如果没找到带模型后缀的，尝试查找旧格式（向后兼容）
                if not target_file:
                    candidate_file = os.path.join(cache_dir, f"{video_base_name}_{length_text_english}{ext}")
                    if os.path.exists(candidate_file):
                        target_file = candidate_file
                        break
                
                if target_file:
                    break
            
            # 如果缓存目录中没有找到，尝试在description文件夹中查找本地模型结果
            if not target_file:
                description_dir = os.path.join(video_dir, video_base_name, 'description')
                if os.path.exists(description_dir):
                    self.log_message.emit(f"🔍 在缓存中未找到结果文件，尝试在description文件夹中查找: {description_dir}")
                    
                    # 在description文件夹中查找文件，支持完整的文件命名格式
                    for filename in os.listdir(description_dir):
                        if filename.endswith(('.json', '.txt', '.csv', '.md')):
                            # 检查是否匹配完整的命名格式：{video_base_name}_{length_text_english}_{model_suffix}.ext
                            # 或者包含'description'的文件（向后兼容）
                            matches_format = False
                            
                            # 检查完整命名格式
                            if filename.startswith(f"{video_base_name}_{length_text_english}_"):
                                matches_format = True
                            # 检查是否包含'description'（向后兼容）
                            elif 'description' in filename:
                                matches_format = True
                            
                            if matches_format:
                                candidate_file = os.path.join(description_dir, filename)
                                
                                # 检查文件是否是本地模型结果
                                try:
                                    if filename.endswith('.json'):
                                        with open(candidate_file, 'r', encoding='utf-8') as f:
                                            file_data = json.load(f)
                                        model_type = file_data.get('model_type', '')
                                        if model_type == 'local':
                                            target_file = candidate_file
                                            self.log_message.emit(f"✅ 在description文件夹中找到本地模型结果: {filename}")
                                            break
                                        elif model_type == 'api':
                                            self.log_message.emit(f"⏭️ 跳过API模型结果: {filename}")
                                            continue
                                    else:
                                        # 对于非JSON文件，假设是本地模型结果（向后兼容）
                                        target_file = candidate_file
                                        self.log_message.emit(f"✅ 在description文件夹中找到结果文件: {filename}")
                                        break
                                except Exception as e:
                                    self.log_message.emit(f"⚠️ 检查文件 {filename} 时出错: {str(e)}")
                                    continue
            
            if not target_file:
                return False, f"在 {cache_dir} 和 description文件夹中均未找到本地模型结果文件 {video_base_name}_{length_text_english}.*（支持的格式：json/txt/csv/md）"
            
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
                
                # 检查model_type，仅处理本地模型的结果
                model_type = result_data.get('model_type', '')
                if model_type == 'api':
                    self.log_message.emit(f"⏭️ 跳过API模型结果文件: {os.path.basename(target_file)}")
                    return True, "跳过API模型结果"
                elif model_type != 'local':
                    # 如果没有model_type字段或值不是'local'，也跳过（为了安全起见）
                    self.log_message.emit(f"⏭️ 跳过非本地模型结果文件: {os.path.basename(target_file)} (model_type: {model_type})")
                    return True, "跳过非本地模型结果"
                
                # 检查是否已经有action_description且不为空
                if result_data.get('action_description') and result_data.get('action_filter_applied'):
                    self.log_message.emit(f"⏭️ 跳过文件 {os.path.basename(target_file)}：已有过滤结果")
                    return True, "已有过滤结果，跳过处理"
                
                # 获取原始描述
                original_description = result_data.get('description', '')
                if not original_description:
                    return False, f"文件 {os.path.basename(target_file)} 中描述为空"
                
                # 记录开始过滤
                self.log_message.emit(f"正在对文件 {os.path.basename(target_file)} 进行动作描述过滤...")
                self.log_message.emit(f"原始描述: {original_description[:100]}...")
                
                # 调用动作描述过滤方法
                try:
                    if hasattr(self.parent_widget, '_filter_action_description'):
                        filter_result = self.parent_widget._filter_action_description(original_description)
                        filtered_description = filter_result.get('description', '')
                        # 新增的两个字段（可能为空）
                        action_summary = filter_result.get('action_summary', '')
                        action_explanation = filter_result.get('action_explanation', '')
                        filter_success = filter_result.get('filter_success', False)
                    else:
                        self.log_message.emit("❌ 父组件缺少 _filter_action_description 方法")
                        return False, "父组件缺少 _filter_action_description 方法"
                except Exception as e:
                    self.log_message.emit(f"❌ 调用过滤方法时出错: {str(e)}")
                    return False, f"调用过滤方法时出错: {str(e)}"
                
                # 更新结果文件的action_description字段
                if filter_success:
                    result_data['action_description'] = filtered_description
                    # 写入新增字段
                    result_data['action_summary'] = action_summary
                    result_data['action_explanation'] = action_explanation
                    result_data['action_filter_applied'] = True
                    result_data['filter_updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.log_message.emit(f"✅ 过滤成功")
                    self.log_message.emit(f"过滤后描述: {filtered_description[:100]}...")
                else:
                    result_data['action_description'] = ""
                    result_data['action_summary'] = ""
                    result_data['action_explanation'] = ""
                    result_data['action_filter_applied'] = False
                    result_data['filter_updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.log_message.emit(f"⚠️ 过滤未生效，保持原始描述")
                
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
                        if result_data.get('action_summary'):
                            f.write(f"总结(<=10字): {result_data.get('action_summary', '')}\n")
                        if result_data.get('action_explanation'):
                            f.write(f"解释: {result_data.get('action_explanation', '')}\n")
                else:
                    return False, f"不支持保存到文件格式: {file_ext}"
                
                # 同步更新description文件夹中的过滤文件
                self._sync_description_folder_files(video_base_name, video_dir, result_data, filter_success)
                
                return True, "重新过滤完成"
                
            except Exception as e:
                self.log_message.emit(f"❌ 处理文件 {os.path.basename(target_file)} 失败: {str(e)}")
                return False, f"处理文件失败: {str(e)}"
                
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            self.log_message.emit(f"❌ {error_msg}")
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
    
    def _get_model_suffix_from_result(self, result_data):
        """从结果数据中获取模型后缀"""
        try:
            model_type = result_data.get('model_type', '')
            if model_type == 'api':
                return 'api'
            elif model_type == 'local':
                return 'local'
            else:
                # 默认假设为本地模型（向后兼容）
                return 'local'
        except:
            return 'local'
    
    def _check_action_filter_applied(self, video_base_name, video_dir):
        """检查视频是否已成功应用动作过滤"""
        try:
            # 获取视频名称（不含路径）
            video_name = video_base_name
            
            # 检查父组件的内存存储
            if hasattr(self.parent_widget, '_action_filter_applied_videos'):
                if video_name in self.parent_widget._action_filter_applied_videos:
                    return True
            
            # 检查统一命名格式的描述文件
            description_length = self._get_description_length_setting()
            length_text_english = self._get_length_text_english(description_length)
            
            # 检查统一格式的文件：{video_base_name}_{length_text_english}_{model_suffix}.json
            unified_result_files = [
                os.path.join(video_dir, video_base_name, 'description', f'{video_base_name}_{length_text_english}_local.json'),
                os.path.join(video_dir, video_base_name, 'description', f'{video_base_name}_{length_text_english}_api.json')
            ]
            
            for unified_result_file in unified_result_files:
                if os.path.exists(unified_result_file):
                    try:
                        with open(unified_result_file, 'r', encoding='utf-8') as f:
                            result = json.load(f)
                        # 如果文件中明确标记已过滤，则跳过
                        if result.get('action_filter_applied', False):
                            return True
                    except:
                        pass
            
            # 兼容旧版本文件格式（无模型后缀）
            old_unified_result_file = os.path.join(video_dir, video_base_name, 'description', f'{video_base_name}_{length_text_english}.json')
            if os.path.exists(old_unified_result_file):
                try:
                    with open(old_unified_result_file, 'r', encoding='utf-8') as f:
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
            if not os.path.exists(description_dir):
                return
            
            # 获取描述长度设置
            length_text_english = self._get_length_text_english(self._get_description_length_setting())
            
            # 查找符合统一命名格式的文件
            result_files = []
            for filename in os.listdir(description_dir):
                if filename.endswith('.json'):
                    # 检查是否匹配统一命名格式：{video_base_name}_{length_text_english}_{model_suffix}.json
                    if filename.startswith(f"{video_base_name}_{length_text_english}_") and ('_local.json' in filename or '_api.json' in filename):
                        result_files.append(os.path.join(description_dir, filename))
                    # 向后兼容旧格式
                    elif filename in ['result_api.json', 'result_local.json', 'result.json']:
                        result_files.append(os.path.join(description_dir, filename))
            
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
                        self.log_message.emit(f"更新结果文件失败 {result_file}: {str(e)}")
                        
        except Exception as e:
            self.log_message.emit(f"更新结果文件失败: {str(e)}")
    
    def _mark_action_filter_applied(self, video_base_name, video_dir):
        """标记视频已成功应用动作过滤"""
        try:
            # 获取视频名称（不含路径）
            video_name = video_base_name
            
            # 使用父组件的内存存储
            if not hasattr(self.parent_widget, '_action_filter_applied_videos'):
                self.parent_widget._action_filter_applied_videos = set()
            
            # 检查视频是否已标记
            if video_name not in self.parent_widget._action_filter_applied_videos:
                # 添加到内存集合
                self.parent_widget._action_filter_applied_videos.add(video_name)
                self.log_message.emit(f"已将视频 {video_name} 标记为已应用动作过滤")
            else:
                self.log_message.emit(f"视频 {video_name} 已标记，跳过")
                
        except Exception as e:
            self.log_message.emit(f"标记视频失败: {str(e)}")
    
    def _sync_description_folder_files(self, video_base_name, video_dir, result_data, filter_success):
        """同步更新description文件夹中的过滤文件"""
        try:
            # 构建description文件夹路径
            description_dir = os.path.join(video_dir, video_base_name, 'description')
            
            if not os.path.exists(description_dir):
                self.log_message.emit(f"⚠️ description文件夹不存在: {description_dir}")
                return
            
            # 查找description文件夹中的结果文件
            result_files = []
            for filename in os.listdir(description_dir):
                if filename.endswith(('.json', '.txt', '.csv', '.md')):
                    # 检查是否匹配完整的命名格式或包含'description'
                    matches_format = False
                    
                    # 检查完整命名格式：{video_base_name}_{length_text_english}_{model_suffix}.ext
                    if filename.startswith(f"{video_base_name}_") and ('_local.' in filename or '_api.' in filename):
                        matches_format = True
                    # 检查是否包含'description'（向后兼容）
                    elif 'description' in filename:
                        matches_format = True
                    
                    if matches_format:
                        result_files.append(os.path.join(description_dir, filename))
            
            if not result_files:
                self.log_message.emit(f"⚠️ 在description文件夹中未找到描述文件")
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
                        
                        # 更新字段（包含新增的summary和explanation）
                        existing_data.update({
                            'action_description': result_data.get('action_description', ''),
                            'action_summary': result_data.get('action_summary', ''),
                            'action_explanation': result_data.get('action_explanation', ''),
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
                            if result_data.get('action_summary'):
                                f.write(f"总结(<=10字): {result_data.get('action_summary', '')}\n")
                            if result_data.get('action_explanation'):
                                f.write(f"解释: {result_data.get('action_explanation', '')}\n")
                    
                    updated_count += 1
                    
                except Exception as e:
                    self.log_message.emit(f"❌ 更新description文件失败 {os.path.basename(result_file)}: {str(e)}")
            
            if updated_count > 0:
                self.log_message.emit(f"✅ 已同步更新 {updated_count} 个description文件")
            else:
                self.log_message.emit(f"⚠️ 未能更新任何description文件")
                
        except Exception as e:
            self.log_message.emit(f"❌ 同步description文件夹失败: {str(e)}")

    def stop(self):
        """停止处理"""
        self.is_running = False