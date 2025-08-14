# PKL to FBX 转换使用指南

## 概述

成功将 `pmce_output.pkl` 文件转换为 Maya 兼容的 FBX 骨骼动画文件。

## 生成的文件

### 主要输出文件
- **文件名**: `mesh_animation_from_pkl_person_1.fbx`
- **文件大小**: 148,864 字节 (约 145 KB)
- **动画帧数**: 81 帧
- **骨骼数量**: 17 个关节 (COCO 17 关节格式)
- **格式**: FBX 2020 兼容格式

### 数据来源
- **原始文件**: `e:\image_3d\text2dance\output\sample_video\pmce_output.pkl`
- **生成命令**: `python src/algorithms/pose3d/main/run_demo.py --vid_file data/sample_video.mp4 --save_pkl --save_fbx --skeleton_only`
- **数据结构**: joints3d 数据 (81, 17, 3) - 81帧，17个关节，每个关节3D坐标

## COCO 17 关节结构

转换后的 FBX 文件包含以下骨骼层次结构：

```
Root
├── Nose (0)
├── LeftEye (1)
├── RightEye (2)
├── LeftEar (3)
├── RightEar (4)
├── LeftShoulder (5)
│   └── LeftElbow (7)
│       └── LeftWrist (9)
├── RightShoulder (6)
│   └── RightElbow (8)
│       └── RightWrist (10)
├── LeftHip (11)
│   └── LeftKnee (13)
│       └── LeftAnkle (15)
└── RightHip (12)
    └── RightKnee (14)
        └── RightAnkle (16)
```

## Maya 导入指南

### 1. 导入步骤
```
1. 打开 Maya 2020 或更高版本
2. File → Import → 选择 mesh_animation_from_pkl_person_1.fbx
3. 在导入选项中确保启用 "Animation" 选项
4. 点击 Import
```

### 2. 可能的显示问题及解决方案

**问题**: 模型显示过大
**解决方案**:
```
1. 选择导入的骨骼组
2. 在 Channel Box 中设置 Scale X/Y/Z 为 0.01 或更小值
3. 或者使用 Modify → Transformation Tools → Scale Tool
```

**问题**: 骨骼不可见
**解决方案**:
```
1. 在 Viewport 中启用 Show → Joints
2. 或者选择骨骼后在 Display → Object Display → Joint Size 调整大小
```

### 3. 动画播放
```
1. 确保时间轴设置为 1-81 帧
2. 点击播放按钮查看动画
3. 可以在 Graph Editor 中查看和编辑动画曲线
```

## 技术细节

### 转换过程
1. **数据加载**: 使用 joblib 加载 pkl 文件
2. **数据解析**: 提取 joints3d 数据 (81帧 × 17关节 × 3D坐标)
3. **骨骼创建**: 基于 COCO 17 关节标准创建骨骼层次
4. **动画生成**: 为每个关节的 X/Y/Z 轴创建动画曲线
5. **FBX导出**: 使用 Autodesk FBX SDK 导出为标准 FBX 格式

### 坐标系统
- **单位**: 米 (Meters)
- **坐标系**: 右手坐标系
- **帧率**: 30 FPS
- **时间范围**: 0-81 帧

## 使用建议

1. **预览检查**: 在导入 Maya 前，可以使用 FBX Review 或其他 FBX 查看器预览文件
2. **缩放调整**: 根据场景需要调整模型缩放比例
3. **动画优化**: 可以在 Maya 中进一步优化动画曲线
4. **格式兼容**: 该 FBX 文件兼容 Maya 2020+、Blender 2.8+、Unity 2019+ 等主流软件

## 故障排除

### 常见问题
1. **文件无法导入**: 确保使用 Maya 2020 或更高版本
2. **动画不播放**: 检查时间轴设置和动画层
3. **骨骼位置异常**: 可能需要调整坐标系或缩放

### 技术支持
- 转换工具: `pkl_to_fbx_converter.py`
- 验证工具: `simple_fbx_validator.py`
- 相关文档: 查看 `fbx_test_files` 目录下的其他 Markdown 文档

---

**生成时间**: 2025年8月9日  
**工具版本**: PKL to FBX Converter v1.0  
**FBX SDK**: Autodesk FBX SDK 2020.3.2