# 智能3D人体对齐视频生成器

这是一个支持命令行参数的3D人体对齐视频生成工具，具备智能模式检测功能，可以自动判断应该使用单人还是多人处理模式。

## 功能特点

- ✅ **智能模式检测**：自动分析pkl文件，智能选择单人或多人处理模式
- ✅ **命令行参数支持**：通过命令行指定视频和pkl文件路径
- ✅ **单人模式**：自动选择主要人员或指定特定人员ID
- ✅ **多人模式**：同时处理所有检测到的人员
- ✅ **人员信息查看**：列出pkl文件中的所有人员信息
- ✅ **自定义输出**：支持自定义输出文件名
- ✅ **智能数据处理**：自动处理缺失的2D关节数据

## 使用方法

### 1. 查看帮助信息
```bash
python run_flexible_alignment.py --help
```

### 2. 列出人员信息
```bash
python run_flexible_alignment.py -v demo/twodance.mp4 -p output/demo_output/twodance/pmce_output.pkl --list-persons
```

### 3. 自动检测模式（推荐）
```bash
# 脚本会自动分析pkl文件，智能选择最佳处理模式
python run_flexible_alignment.py -v demo/sample_video.mp4 -p output/demo_output/sample_video/pmce_output.pkl
```

### 4. 强制单人模式（指定人员ID）
```bash
python run_flexible_alignment.py -v demo/twodance.mp4 -p output/demo_output/twodance/pmce_output.pkl --person-id 1
```

### 5. 强制多人模式（处理所有人员）
```bash
python run_flexible_alignment.py -v demo/twodance.mp4 -p output/demo_output/twodance/pmce_output.pkl --force-multi-person
```

### 6. 自定义输出文件名
```bash
python run_flexible_alignment.py -v demo/twodance.mp4 -p output/demo_output/twodance/pmce_output.pkl -o my_custom_output.mp4
```

## 参数说明

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--video` | `-v` | ✅ | 输入视频文件路径 |
| `--pkl` | `-p` | ✅ | PMCE输出的pkl文件路径 |
| `--output` | `-o` | ❌ | 输出视频文件名（默认自动生成） |
| `--force-multi-person` | | ❌ | 强制多人模式（覆盖自动检测） |
| `--person-id` | | ❌ | 指定处理的人员ID（单人模式） |
| `--scale-factor` | | ❌ | 3D模型缩放因子（默认4.0） |
| `--list-persons` | | ❌ | 仅列出人员信息，不生成视频 |

## 智能模式检测逻辑

脚本会自动分析pkl文件中的人员数据，并根据以下规则选择最佳处理模式：

### 单人模式触发条件：
- 只检测到1个人员
- 检测到多个人员，但有一个人员的帧数占主导地位（≥80%最大帧数且>50帧）

### 多人模式触发条件：
- 检测到多个人员，且帧数相近（没有明显的主导人员）

### 用户覆盖选项：
- 使用 `--person-id` 强制单人模式并指定特定人员
- 使用 `--force-multi-person` 强制多人模式

## 输出文件命名规则

- **单人模式（只有1个人员）**：`{视频名}_SINGLE_3D_ALIGNMENT.mp4`
- **单人模式（自动选择主导人员）**：`{视频名}_AUTO_SINGLE_3D_ALIGNMENT.mp4`
- **单人模式（指定ID）**：`{视频名}_PERSON_{ID}_3D_ALIGNMENT.mp4`
- **多人模式**：`{视频名}_MULTI_PERSON_3D_ALIGNMENT.mp4`

## 示例输出

### 单人模式示例
```
🎬 灵活的3D人体对齐视频生成器
============================================================
📹 输入视频: demo/sample_video.mp4
📦 PKL文件: output/demo_output/sample_video/pmce_output.pkl
✅ 成功加载PMCE数据

👥 检测到 1 个人员:
   人员 1: 81 帧, joints2d: (81, 16, 19, 2)

🎯 选择处理人员 1 (81 帧)
✅ 使用真实的2D关节数据
📊 网格数据: (81, 6890, 3)
📊 2D关节数据: (81, 19, 2)
📹 视频信息: 81 帧, 30.0 FPS, 1920x1080
🎬 处理 81 帧

处理进度: 81/81 (100.0%) | 平均误差: 108.08 | 平均迭代: 22.0
🎥 创建最终视频: sample_video_SINGLE_3D_ALIGNMENT.mp4
✅ 视频创建成功: sample_video_SINGLE_3D_ALIGNMENT.mp4
📹 输出文件大小: 3.7 MB

🎉 视频生成完成: sample_video_SINGLE_3D_ALIGNMENT.mp4
```

### 多人模式示例
```
🎬 创建多人3D对齐视频
==================================================
🎯 将处理 2 个人员
✅ 人员 1: 使用真实的2D关节数据
✅ 人员 2: 使用真实的2D关节数据
📊 人员 1 - 网格: (578, 6890, 3), 2D关节: (578, 19, 2)
📊 人员 2 - 网格: (578, 6890, 3), 2D关节: (578, 19, 2)
📹 视频信息: 578 帧, 30.0 FPS
🎬 处理 578 帧 (多人模式)

处理进度: 578/578 (100.0%)
🎥 创建最终视频: twodance_MULTI_PERSON_3D_ALIGNMENT.mp4
✅ 视频创建成功: twodance_MULTI_PERSON_3D_ALIGNMENT.mp4

🎉 视频生成完成: twodance_MULTI_PERSON_3D_ALIGNMENT.mp4
```

## 技术特点

### 智能模式检测
- 自动分析pkl文件中的人员数据
- 基于帧数分布智能选择处理模式
- 提供用户覆盖选项以满足特殊需求

### 3D跟踪对齐算法
- 基于3D位置跟踪的智能对齐
- 结合2D投影误差和3D位置一致性
- 帧间3D位置连续性保持
- 无旋转变换，避免转圈问题

### 多人处理
- 为每个人员分配不同颜色标识
- 自动位置偏移避免重叠
- 独立的3D位置跟踪
- 支持不同数量的人员

### 数据兼容性
- 自动检测和处理缺失的2D关节数据
- 支持不同格式的pkl文件
- 智能数据格式转换
- 错误处理和恢复机制

## 故障排除

### 常见问题

1. **文件不存在错误**
   ```
   ❌ 视频文件不存在: demo/video.mp4
   ```
   解决：检查视频文件路径是否正确

2. **pkl文件加载失败**
   ```
   ❌ 加载pkl文件失败: ...
   ```
   解决：确保pkl文件是有效的PMCE输出文件

3. **FFmpeg错误**
   ```
   ❌ FFmpeg执行失败: ...
   ```
   解决：确保系统已安装FFmpeg并在PATH中

4. **人员ID不存在**
   ```
   ❌ 未找到指定的人员ID: 3
   ```
   解决：使用 `--list-persons` 查看可用的人员ID

### 性能优化建议

- 单人模式处理速度更快
- 多人模式需要更多计算资源
- 较大的视频文件需要更多处理时间
- 建议在GPU环境下运行以获得最佳性能

## 依赖要求

- Python 3.8+
- OpenCV
- NumPy
- joblib
- FFmpeg（用于视频生成）
- PMCE相关依赖

## 更新日志

### v1.0.0
- ✅ 初始版本发布
- ✅ 支持命令行参数
- ✅ 单人和多人模式
- ✅ 人员信息查看功能
- ✅ 自定义输出文件名
- ✅ 智能数据处理