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

### v1.0.0 (2024-01-01)
- 初始版本发布
- 基础爬虫功能
- 视频处理功能
- AI算法集成
- GUI界面
- 插件系统

---

**注意**: 请遵守相关法律法规，仅用于学习和研究目的。使用本工具下载的内容应符合版权法和网站服务条款。