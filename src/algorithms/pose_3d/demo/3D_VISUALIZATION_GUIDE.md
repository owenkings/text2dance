# 3D可视化指南 - 无需OSMesa

本指南介绍如何在不解决OSMesa问题的情况下，使用替代方案进行3D人体姿态和网格的可视化。

## 问题背景

PMCE项目默认使用pyrender和OSMesa进行3D渲染，但在Windows系统上可能遇到OSMesa配置问题。为了解决这个问题，我们提供了几种替代的3D可视化方案。

## 解决方案

### 方案1: 使用--no_render参数运行demo

最简单的方法是在运行demo时添加`--no_render`参数，跳过渲染步骤：

```bash
python ./main/run_demo.py --vid_file demo/sample_video.mp4 --gpu 0 --no_render --save_pkl
```

这样可以：
- 成功运行PMCE算法
- 生成3D网格数据（保存在pkl文件中）
- 跳过有问题的渲染步骤
- 输出原始视频和姿态估计结果

### 方案2: 使用matplotlib进行3D可视化

我们提供了`simple_3d_visualizer.py`脚本，使用matplotlib进行3D可视化：

#### 安装依赖
```bash
pip install matplotlib
```

#### 使用方法

1. **可视化关键帧**：
```bash
python ./demo/simple_3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl --output_dir ./3d_visualization
```

2. **创建动画序列**：
```bash
python ./demo/simple_3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl --animation --output_dir ./3d_animation
```

3. **只保存不显示**：
```bash
python ./demo/simple_3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl --output_dir ./3d_visualization --no_show
```

#### 功能特点
- 显示3D网格点云
- 支持多人姿态可视化
- 可以生成动画序列
- 轻量级，无需复杂依赖

### 方案3: 使用Open3D进行高质量3D可视化

我们提供了`open3d_visualizer.py`脚本，使用Open3D进行更高质量的3D可视化：

#### 安装依赖
```bash
pip install open3d
```

#### 使用方法

1. **交互式3D可视化**：
```bash
python ./demo/open3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl
```

2. **使用SMPL面片进行完整网格渲染**：
```bash
python ./demo/open3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl --faces_file ./data/base_data/smpl_faces.npy
```

3. **保存高质量截图**：
```bash
python ./demo/open3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl --output_dir ./open3d_screenshots --no_interactive
```

4. **创建高质量动画**：
```bash
python ./demo/open3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl --animation --output_dir ./open3d_animation
```

#### 功能特点
- 高质量3D渲染
- 交互式3D查看器
- 支持完整网格显示（需要面片数据）
- 可以旋转、缩放、平移视角
- 支持保存高分辨率截图

### 方案4: 修改renderer.py使用其他平台

如果你想继续使用原始的渲染功能，可以修改`demo/renderer.py`文件：

```python
# 在文件开头设置不同的平台
os.environ['PYOPENGL_PLATFORM'] = 'win32'  # 或 'egl'
os.environ['PYRENDER_PLATFORM'] = 'pyglet'
```

然后正常运行demo（不使用--no_render参数）。

## 输出文件说明

运行PMCE后，你会得到以下文件：

1. **pmce_output.pkl**: 包含3D网格顶点、相机参数等数据
2. **pmce_sample_video_output.mp4**: 处理后的视频（如果渲染成功）
3. **sample_video.mp4**: 原始输入视频的副本

## 数据格式说明

`pmce_output.pkl`文件包含：
```python
{
    person_id: {
        'pred_cam': array,      # 相机参数 (T, 3)
        'mesh': array,          # 3D网格顶点 (T, 6890, 3)
        'bboxes': array,        # 边界框 (T, 4)
        'frame_ids': array,     # 帧ID (T,)
    }
}
```

其中：
- T: 时间步数
- 6890: SMPL模型的顶点数
- 3: XYZ坐标

## 创建视频动画

使用可视化脚本生成动画帧后，可以用ffmpeg合成视频：

```bash
# 从matplotlib生成的帧
ffmpeg -r 30 -i ./3d_animation/frame_%06d.png -c:v libx264 -pix_fmt yuv420p 3d_animation.mp4

# 从Open3D生成的帧
ffmpeg -r 30 -i ./open3d_animation/frame_%06d.png -c:v libx264 -pix_fmt yuv420p open3d_animation.mp4
```

## 推荐工作流程

1. **首先运行PMCE获取数据**：
   ```bash
   python ./main/run_demo.py --vid_file demo/sample_video.mp4 --gpu 0 --no_render --save_pkl
   ```

2. **选择可视化方案**：
   - 快速预览：使用matplotlib方案
   - 高质量可视化：使用Open3D方案
   - 需要原始渲染：修改renderer.py

3. **生成可视化结果**：
   ```bash
   # matplotlib方案
   python ./demo/simple_3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl
   
   # 或Open3D方案
   python ./demo/open3d_visualizer.py --pkl_file ./output/demo_output/sample_video/pmce_output.pkl
   ```

## 注意事项

1. **性能考虑**：3D网格包含6890个顶点，可视化时可能需要采样以提高性能
2. **内存使用**：长视频序列可能占用大量内存，建议分批处理
3. **依赖安装**：确保安装了相应的可视化库（matplotlib或Open3D）
4. **文件路径**：确保pkl文件路径正确，且文件存在

## 故障排除

### 常见问题

1. **ImportError: No module named 'open3d'**
   - 解决：`pip install open3d`

2. **matplotlib显示问题**
   - 解决：确保安装了GUI后端，如`pip install PyQt5`

3. **内存不足**
   - 解决：增加采样率，减少显示的顶点数量

4. **pkl文件加载失败**
   - 解决：检查文件路径和文件完整性

通过这些方案，你可以在不解决OSMesa问题的情况下，成功进行3D人体姿态和网格的可视化。