# 配置文件迁移指南

## 概述

本项目已从使用 `cache_config.txt` 文件迁移到使用新的 `UserConfigManager` 系统。新系统提供了更好的配置管理、类型安全和错误处理。

## 主要变化

### 1. 配置管理器
- **旧方式**: 直接读写 `cache_config.txt` 文件
- **新方式**: 使用 `UserConfigManager` 类统一管理配置

### 2. 配置文件位置
- **配置文件**: `user_config.json` (替代 `cache_config.txt`)
- **位置**: 项目根目录

### 3. 配置文件格式
从文本格式迁移到 JSON 格式，提供更好的结构化数据支持。

#### 旧格式 (cache_config.txt)
```
cache_path=E:\Tiany\huggingface
sharegpt4video_model_path=Lin-Chen/sharegpt4video-8b
custom_api_endpoint=https://ark.cn-beijing.volces.com/api/v3/chat/completions
custom_api_key=your-api-key
custom_api_model=doubao-1.5-vision-pro-250328
```

#### 新格式 (user_config.json)
```json
{
  "cache_path": "E:\\Tiany\\huggingface",
  "sharegpt4video_model_path": "Lin-Chen/sharegpt4video-8b",
  "custom_api": {
    "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    "key": "your-api-key",
    "model": "doubao-1.5-vision-pro-250328",
    "name": ""
  },
  "action_filter_api": {
    "endpoint": "",
    "key": "",
    "model": ""
  }
}
```

## 使用新的配置管理器

### 获取配置管理器实例
```python
from src.core.user_config_manager import get_user_config_manager

config = get_user_config_manager()
```

### 读取配置
```python
# 获取基本配置
cache_path = config.config.get('cache_path')
model_path = config.config.get('sharegpt4video_model_path')

# 获取API配置
custom_api = config.get_api_config('custom')
action_filter_api = config.get_api_config('action_filter')
```

### 设置配置
```python
# 设置API配置
config.set_api_config('custom', {
    'endpoint': 'https://api.example.com',
    'key': 'your-api-key',
    'model': 'your-model',
    'name': 'Custom API'
})

# 设置基本配置
config.config['cache_path'] = '/path/to/cache'
config.save_config()
```

## 自动迁移

系统会自动检测并迁移旧的 `cache_config.txt` 文件：

1. 如果存在 `cache_config.txt` 但不存在 `user_config.json`，系统会自动迁移
2. 迁移完成后，旧文件会被重命名为 `cache_config.txt.backup`
3. 如果迁移失败，系统会使用默认配置

## 错误处理

新系统提供了更好的错误处理：

- 配置文件损坏时自动使用默认配置
- 缺少配置项时自动补充默认值
- 详细的错误日志记录

## 兼容性

为了确保向后兼容性，以下文件仍然包含对旧配置文件的回退支持：

- `src/algorithms/video_description/ShareGPT4Video/llava/model/mirror_manager.py`
- `src/algorithms/video_description/ShareGPT4Video/llava/model/builder.py`

这些文件会首先尝试使用新的配置管理器，如果失败则回退到直接读取 `cache_config.txt`。

## 测试

可以使用提供的测试脚本验证配置系统：

```bash
python test_config.py
```

测试脚本会验证：
- 配置管理器初始化
- 配置读取和写入
- API配置管理
- 错误处理

## 注意事项

1. **备份**: 迁移前建议备份现有的 `cache_config.txt` 文件
2. **权限**: 确保程序有权限读写配置文件
3. **路径**: 配置文件路径使用绝对路径以避免相对路径问题
4. **编码**: 新配置文件使用 UTF-8 编码，支持中文等多语言字符