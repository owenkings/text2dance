# 视频处理爬虫工具

一个集成了网络爬虫和视频处理功能的综合性工具，支持视频下载、处理、分析和AI算法应用。

## 功能特性

### 🕷️ 网络爬虫
- 支持多种视频网站的视频爬取和下载
- 智能解析视频链接和元数据
- 批量下载和断点续传
- 代理支持和反爬虫机制
- 自定义下载参数和格式选择

### 🎬 视频处理
- 视频格式转换和编码
- 视频剪辑、合并和分割
- 帧提取和视频预览
- 批量处理和自动化工作流
- GPU加速支持

### 🤖 AI算法集成
- **2D姿态估计**: OpenPose, MediaPipe, PoseNet等
- **3D姿态估计**: VideoPose3D, 3D-PoseNet等
- **视频描述生成**: Vid2Seq, Video-ChatGPT等
- 自定义算法插件支持

### 🔧 系统特性
- 现代化的PyQt5图形界面
- 插件系统和扩展支持
- 任务管理和进度监控
- 配置管理和设置保存
- 多语言支持
- 日志记录和错误处理

## 系统要求

### 最低要求
- **操作系统**: Windows 10/11, macOS 10.14+, Ubuntu 18.04+
- **Python**: 3.7 或更高版本
- **内存**: 4GB RAM (推荐 8GB+)
- **存储**: 2GB 可用空间
- **网络**: 稳定的互联网连接

### 推荐配置
- **CPU**: Intel i5 或 AMD Ryzen 5 以上
- **GPU**: NVIDIA GTX 1060 或更高 (用于GPU加速)
- **内存**: 16GB RAM
- **存储**: SSD 硬盘

## 快速开始

### 方法一：一键启动（推荐）

**Windows用户**：
- 双击 `启动程序.bat` 文件
- 选择操作：启动程序、安装依赖或检查依赖状态
- 程序会自动处理依赖问题

**所有平台**：
```bash
# 智能启动（自动检查依赖）
python start.py

# 或专门安装依赖
python install_dependencies.py
```

### 方法二：手动安装

1. 安装所有依赖：
```bash
pip install -r requirements.txt
```

2. 如果遇到特定问题：
```bash
# NumPy兼容性问题
python fix_numpy.py

# MoviePy缺失问题
pip install moviepy==1.0.3

# 完整依赖修复
python install_dependencies.py
```

3. 运行程序：
```bash
python main.py
```

### 常见问题解决

- **`No module named 'moviepy.editor'`**：运行 `pip install moviepy==1.0.3`
- **`_ARRAY_API not found`**：运行 `pip install "numpy<2.0" --force-reinstall`
- **其他依赖问题**：运行 `python install_dependencies.py`

## 安装指南

### 1. 克隆项目
```bash
git clone https://github.com/your-username/video-crawler-tool.git
cd video-crawler-tool
```

### 2. 创建虚拟环境
```bash
# 使用 venv
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 安装依赖
```bash
# 安装基础依赖
pip install -r requirements.txt

# 如果需要GPU支持 (NVIDIA)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 4. 配置环境
```bash
# 复制配置文件模板
cp config/config.example.yaml config/config.yaml

# 编辑配置文件
nano config/config.yaml
```

### 5. 运行程序
```bash
# GUI模式
python main.py

# 命令行模式
python main.py --no-gui

# 查看帮助
python main.py --help
```

## 使用指南

### GUI模式

1. **启动应用程序**
   ```bash
   python main.py
   ```

2. **爬虫功能**
   - 在"爬虫"选项卡中输入视频URL
   - 选择下载目录和质量
   - 点击"开始下载"按钮

3. **视频处理**
   - 在"视频处理"选项卡中选择视频文件
   - 配置处理参数
   - 选择输出格式和目录
   - 开始处理

4. **AI分析**
   - 选择要分析的视频
   - 选择算法类型（2D姿态、3D姿态、视频描述）
   - 配置算法参数
   - 开始分析

### 命令行模式

```bash
# 爬取视频
python main.py --no-gui --crawl "https://example.com/video" --output ./downloads

# 处理视频
python main.py --no-gui --process "video.mp4" --algorithm pose_2d --output ./results

# 批量处理
python main.py --no-gui --process "*.mp4" --algorithm video_description
```

## 配置说明

### 主配置文件 (config/config.yaml)

```yaml
# 应用程序设置
app:
  name: "视频处理爬虫工具"
  version: "1.0.0"
  language: "zh_CN"
  theme: "dark"
  log_level: "INFO"

# 爬虫设置
crawler:
  download_path: "./downloads"
  max_concurrent: 3
  retry_count: 3
  timeout: 30
  user_agent: "Mozilla/5.0..."
  proxy: ""

# 视频处理设置
video_processing:
  temp_path: "./temp"
  output_path: "./output"
  ffmpeg_path: ""
  gpu_acceleration: false
  max_threads: 4

# AI算法设置
algorithms:
  pose_2d:
    default_algorithm: "openpose"
    models_path: "./models/pose_2d"
    confidence_threshold: 0.5
  
  pose_3d:
    default_algorithm: "videopose3d"
    models_path: "./models/pose_3d"
    confidence_threshold: 0.5
  
  video_description:
    default_algorithm: "vid2seq"
    models_path: "./models/description"
    max_length: 100

# 插件设置
plugins:
  plugins_path: "./plugins"
  auto_load: true
  enabled_plugins: []
```

## 插件开发

### 创建自定义插件

1. **创建插件目录**
   ```
   plugins/
   └── my_plugin/
       ├── __init__.py
       ├── plugin.py
       └── config.yaml
   ```

2. **实现插件接口**
   ```python
   # plugins/my_plugin/plugin.py
   from src.core.plugin_base import PluginBase
   
   class MyPlugin(PluginBase):
       def __init__(self):
           super().__init__()
           self.name = "My Plugin"
           self.version = "1.0.0"
       
       def initialize(self):
           # 插件初始化逻辑
           pass
       
       def process_video(self, video_path):
           # 视频处理逻辑
           pass
   ```

3. **注册插件**
   ```python
   # plugins/my_plugin/__init__.py
   from .plugin import MyPlugin
   
   def get_plugin():
       return MyPlugin()
   ```

## API文档

### 核心模块

- **src.crawler**: 爬虫相关功能
- **src.video**: 视频处理功能
- **src.algorithms**: AI算法集成
- **src.gui**: 图形界面组件
- **src.core**: 核心系统组件
- **src.utils**: 工具和辅助函数

### 主要类

```python
# 爬虫管理器
from src.crawler import CrawlerManager
crawler = CrawlerManager()
result = crawler.download_video(url, output_dir)

# 视频处理器
from src.video import VideoProcessor
processor = VideoProcessor()
processor.convert_format(input_file, output_file, format="mp4")

# 算法管理器
from src.algorithms import AlgorithmManager
algorithm_mgr = AlgorithmManager()
result = algorithm_mgr.run_pose_estimation(video_path, algorithm="openpose")
```

## 故障排除

### 常见问题

1. **导入错误**
   ```
   ImportError: No module named 'PyQt5'
   ```
   **解决方案**: 确保已安装所有依赖包
   ```bash
   pip install -r requirements.txt
   ```

2. **FFmpeg未找到**
   ```
   FileNotFoundError: ffmpeg not found
   ```
   **解决方案**: 安装FFmpeg并添加到PATH，或在配置文件中指定路径

3. **GPU加速失败**
   ```
   CUDA out of memory
   ```
   **解决方案**: 减少批处理大小或使用CPU模式

4. **网络连接问题**
   ```
   ConnectionError: Failed to download
   ```
   **解决方案**: 检查网络连接，配置代理或重试

### 日志文件

日志文件位置: `logs/app.log`

查看详细错误信息:
```bash
tail -f logs/app.log
```

## 贡献指南

### 开发环境设置

1. **Fork项目**
2. **创建开发分支**
   ```bash
   git checkout -b feature/new-feature
   ```

3. **安装开发依赖**
   ```bash
   pip install -r requirements.txt
   pip install pytest black flake8 mypy
   ```

4. **运行测试**
   ```bash
   pytest tests/
   ```

5. **代码格式化**
   ```bash
   black src/
   flake8 src/
   mypy src/
   ```

### 提交规范

- 使用清晰的提交信息
- 遵循代码风格指南
- 添加必要的测试
- 更新文档

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI框架
- [OpenCV](https://opencv.org/) - 计算机视觉库
- [FFmpeg](https://ffmpeg.org/) - 多媒体处理
- [PyTorch](https://pytorch.org/) - 深度学习框架
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载工具

## 联系方式

- **项目主页**: https://github.com/your-username/video-crawler-tool
- **问题反馈**: https://github.com/your-username/video-crawler-tool/issues
- **邮箱**: your-email@example.com

## 更新日志

### v3.0.0 (2025-01-15)
- **🚀 视频描述批量处理重大优化**
  - 实现"N个视频 = 1次模型加载 + N次推理"的高效批量处理模式
  - 创建新的`BatchVideoProcessor`类，支持模型复用和资源管理
  - 显著减少模型加载时间，特别是在处理多个视频时效果明显
  - 优化内存使用，避免重复的模型初始化开销

- **📦 新增批量处理脚本**
  - 新建`batch_run.py`脚本，提供完整的命令行批量处理支持
  - 支持多种输入方式：视频列表、视频文件夹、配置文件
  - 提供JSON格式输出，便于程序间数据交换
  - 包含详细的处理统计信息：总时间、平均时间、成功率等

- **🔧 GUI界面批量处理集成**
  - 重构`VideoDescriptionThread`类，替换单视频处理为批量处理逻辑
  - 实现批量结果解析和状态更新机制
  - 保持原有的所有参数支持和用户体验
  - 添加批量处理进度监控和实时日志输出

- **⚡ 性能优化效果**
  - **模型加载优化**：从每个视频重新加载改为整个批次只加载一次
  - **处理时间优化**：批量处理多个视频时显著减少总处理时间
  - **资源管理优化**：实现proper的资源清理和内存管理
  - **设备配置优化**：支持CUDA和CPU的自动检测和优化配置

- **🛠️ 技术实现改进**
  - 使用`torch.inference_mode()`优化推理性能
  - 实现完善的错误处理和异常恢复机制
  - 添加详细的日志记录和调试信息
  - 修复批量处理脚本中的logger初始化问题

- **📊 批量处理统计功能**
  - 提供详细的批量处理报告：总视频数、成功数、失败数
  - 计算总处理时间和平均每个视频处理时间
  - 支持处理结果的结构化输出和保存
  - 实现处理状态的实时监控和反馈

### v2.2.0 (2024-12-20)
- **🎨 界面布局优化**
  - 重新设计视频描述界面布局，将常用功能选项移至视频播放区域下方
  - 在中间面板新增快捷功能区域，包含生成模式、参数设置和快捷选项
  - 增大开始描述和停止处理按钮尺寸，提升操作便利性
  - 添加功能说明文本和进度条显示，优化用户体验
  - 实现左侧面板和中间面板控件的双向同步机制

- **⏱️ 处理耗时计算与显示**
  - 新增视频处理总耗时统计功能，精确记录每个视频的完整处理时间
  - 在处理结果中显示详细的时间信息，包括开始时间、结束时间和总耗时
  - 优化处理流程的时间记录，提供更准确的性能分析数据
  - 支持批量处理时的总体耗时统计和平均处理时间计算

- **🎛️ 高级参数控制**
  - 在视频描述界面新增"高级参数"设置组
  - 添加"最大生成长度"(max_new_tokens)控制：范围0-2048，默认200，0表示无限制
  - 添加"采样帧数"(num_frames)控制：范围0-64，默认16，0表示自动选择
  - 提供详细的工具提示说明和推荐值指导

- **🤖 智能帧数自动选择**
  - 实现基于视频时长的智能帧数选择算法
  - 短视频(≤10秒)：自动选择16帧，快速处理
  - 中等视频(10-30秒)：自动选择20帧，平衡质量与效率
  - 较长视频(30-60秒)：自动选择25帧，确保信息捕获
  - 长视频(>60秒)：自动选择32帧，最大化信息提取
  - 添加错误处理机制，获取时长失败时使用默认值

- **🎯 生成模式增强**
  - 新增"混合策略"生成模式，提供第三种生成选项
  - 混合策略参数配置：do_sample=True, top_p=0.7, temperature=0.8, num_beams=2
  - 完善生成模式映射逻辑，支持确定性、随机采样和混合三种策略
  - 优化生成参数组合，平衡输出质量和多样性

- **🔧 参数传递机制完善**
  - 修改VideoDescriptionThread类，支持max_new_tokens和num_frames参数
  - 更新_process_single_video方法，正确传递高级参数到ShareGPT4Video算法
  - 修改ShareGPT4Video的run.py文件，添加--num_frames命令行参数支持
  - 实现参数验证和默认值处理机制

- **📝 详细日志记录**
  - 添加参数设置的详细日志记录和状态提示
  - 当设置为0时显示相应的"无限制"或"自动选择"提示
  - 记录自动帧数选择的具体数值和选择原因
  - 提供处理过程的完整参数信息追踪

- **⚠️ 安全性考虑**
  - 文档化max_new_tokens无限制设置的潜在风险：内存消耗、处理时间、质量下降、系统稳定性、成本问题
  - 说明num_frames自动选择的考虑因素：计算负载、处理时间、内存占用、质量平衡
  - 提供最佳实践建议和资源监控指导
  - 建议测试验证流程，确保生产环境稳定性

- **🚀 用户体验优化**
  - 简化参数设置，降低使用门槛
  - 智能化处理，减少手动调整需求
  - 提供清晰的参数说明和推荐值
  - 支持批量处理不同长度视频的自动优化

### v2.1.0 (2024-12-19)
- **🐛 语法错误修复**
  - 修复抖音爬虫(douyin_crawler.py)中第295行的缩进错误
  - 修复YouTube爬虫(youtube_crawler.py)中第162行的缩进错误
  - 解决JSON解析循环中try语句缩进不正确的问题

- **🎬 视频播放功能修复**
  - 修复视频描述模块中的视频播放问题
  - 优化视频播放器的兼容性和稳定性
  - 改进视频文件加载和播放控制机制

- **🛡️ 视频处理错误处理增强**
  - 新增`validate_video_file()`函数，提供全面的视频文件验证
  - 增强视频文件格式支持：mp4, avi, mov, mkv, flv, wmv, m4v, webm, mpg, mpeg
  - 改进`_load_video()`方法，添加多重验证和FFMPEG后端支持
  - 优化`_show_frame()`方法的错误处理和资源管理
  - 增强`get_video_info()`方法，添加文件完整性检查和帧数据验证

- **🎯 用户体验优化**
  - 文件选择时实时验证视频文件有效性
  - 批量添加视频时提供详细的错误汇总
  - 改进错误信息显示，提供更清晰的问题诊断
  - 添加完整的日志记录和用户友好的错误提示

- **🔧 ShareGPT4Video集成**
  - 集成ShareGPT4Video视频描述算法
  - 支持自定义描述要求和模型参数
  - 实现处理日志和结果的分离显示
  - 添加视频描述处理的完整工作流

- **🚀 ShareGPT4Video算法重大优化**
  - **消除重复输出**: 修复视频描述结果多次输出的问题，通过添加`silent_mode`参数和智能输出过滤
  - **改进日志管理**: 重构日志系统，支持可配置的日志级别(DEBUG/INFO/WARNING/ERROR)、静默模式和可选文件日志
  - **增强错误处理**: 新增`ResultFormatter`类，提供统一的JSON和纯文本输出格式，完善异常处理机制
  - **优化输出格式**: 支持结构化JSON输出，包含状态、描述、时间戳和元数据信息
  - **命令行界面改进**: 使用`argparse`重构参数解析，支持`--video`、`--output-format`、`--log-level`等参数
  - **超时控制**: 增加10分钟处理超时机制，提升系统稳定性
  - **备用解析**: 实现JSON解析失败时的自动回退机制，确保兼容性
  - **标准错误内容优化**: 过滤模型加载警告、CUDA/GPU警告等系统信息，专注于核心处理结果

- **✅ 代码质量提升**
  - 通过Python AST语法检查器验证所有修复
  - 确保爬虫模块可以正常导入和使用
  - 改进代码结构和可读性
  - 添加测试脚本验证改进功能
  - ShareGPT4Video算法代码重构，提升可维护性和扩展性

- **🔧 技术改进**
  - 优化爬虫模块的错误处理机制
  - 提升JSON数据解析的稳定性
  - 增强代码的健壮性和维护性
  - 显著减少"媒体资源错误"的发生率
  - ShareGPT4Video处理流程优化，减少冗余输出和提升处理效率

### v2.0.0 (2024-12-10)
- **🎯 新增视频描述功能**
  - 集成ShareGPT4Video模型，支持高质量视频内容描述
  - 添加专用的"📝 视频描述"界面选项卡
  - 支持单个和批量视频描述处理
  - 实现三栏布局：上传/功能选择（左）、视频播放（中）、处理日志/结果（右）

- **🤖 AI动作描述过滤**
  - 新增动作描述提取功能，通过API调用去除环境和衣着描述
  - 支持自定义API端点、密钥和模型配置
  - 智能过滤，只保留动作相关的描述内容

- **⚙️ 配置管理增强**
  - 新增视频描述模型缓存路径配置
  - 添加ShareGPT4Video模型路径设置
  - 创建cache_config.txt文件，与界面配置实时同步
  - 支持API配置管理（端点、密钥、模型）

- **📊 批量处理与导出**
  - 支持多格式导出：JSON、TXT、Markdown、Excel
  - 详细的处理记录：播放时间、执行时间、成功状态、描述内容、错误信息
  - 结果备份和导出功能
  - 可选择保存到视频目录或程序目录

- **🖥️ 界面优化**
  - 添加处理状态显示，包括成功/失败标识
  - 支持.mp4视频格式验证和上传
  - 可配置描述要求，支持默认模板（淡灰色提示）
  - 实时进度监控和详细日志显示

- **🔧 技术改进**
  - 支持CPU/CUDA自动检测，优化处理性能
  - 集成PyTorch和Transformers环境检测
  - 添加完整的测试脚本和示例视频
  - 改进错误处理和用户反馈机制

### v1.0.0 (2024-01-01)
- 初始版本发布
- 基础爬虫功能
- 视频处理功能
- AI算法集成
- GUI界面
- 插件系统

---

**注意**: 请遵守相关法律法规，仅用于学习和研究目的。使用本工具下载的内容应符合版权法和网站服务条款。