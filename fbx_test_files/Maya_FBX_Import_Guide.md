# Maya FBX 骨骼导入指南

## 快速开始

1. **生成FBX文件**：
   ```bash
   python src/algorithms/pose3d/main/run_demo.py --vid_file data/sample_video.mp4 --save_pkl --save_fbx --skeleton_only
   ```
   这将在 `./output/sample_video/fbx_output/` 目录下生成 `person_0001_skeleton.fbx` 文件。
   
   **注意**：新版本的FBX文件已经优化，使用了Maya兼容的格式：
   - 包含Skeleton根节点
   - 使用LimbNode关节类型（而非Joint）
   - 改进的层次结构连接

## 问题描述
如果您在Maya中导入FBX文件后看不到骨骼，请按照以下步骤操作：

## 解决方案

### 1. 检查大纲视图 (Outliner)
- 打开 Window > Outliner
- 查看是否有名为 "nose", "left_shoulder" 等的节点
- 如果看到这些节点，说明骨骼已经导入，只是显示问题

**如果在Outliner中没有看到任何节点：**
- 检查导入是否成功完成（没有错误提示）
- 尝试在Outliner中点击 "Show" 菜单，确保显示所有对象类型
- 检查是否有任何过滤器被激活
- 尝试在Outliner中搜索关节名称（如"nose"或"shoulder"）

### 2. 显示骨骼
在Maya中，按照以下步骤显示骨骼：

#### 方法1：通过显示菜单
1. 在视口中，点击 Show > Objects > Joints
2. 确保 Joints 选项被勾选

#### 方法2：通过视口显示设置
1. 在视口右上角，点击显示设置图标
2. 找到 "Joints" 选项并勾选

#### 方法3：选择并显示
1. 在Outliner中选择所有关节节点
2. 按 Ctrl+H 取消隐藏
3. 或者在Channel Box中将 Visibility 设置为 On

### 3. 调整关节显示大小
如果关节太小看不见：
1. 选择所有关节
2. 在Attribute Editor中找到 "Joint" 选项卡
3. 调整 "Radius" 值（建议设置为 5-10）

### 4. 检查缩放
如果物体太大或太小：
1. 选择所有对象
2. 按 F 键聚焦到选中对象
3. 或者手动调整视口缩放

### 5. 导入设置
导入FBX时，确保以下设置：
- File > Import > Options
- 在FBX Import Options中：
  - 勾选 "Animation"
  - 勾选 "Deformed Models"
  - 勾选 "Skins"
  - 勾选 "Shapes"

## 文件信息
- 生成的FBX文件包含17个COCO关节点
- 每个关节都有一个球体几何体用于可视化
- 文件格式：FBX 7.4 二进制格式
- 关节类型：Joint（Maya标准关节类型）

## 关节列表
生成的FBX文件包含以下关节：
1. nose (鼻子)
2. left_eye (左眼)
3. right_eye (右眼)
4. left_ear (左耳)
5. right_ear (右耳)
6. left_shoulder (左肩)
7. right_shoulder (右肩)
8. left_elbow (左肘)
9. right_elbow (右肘)
10. left_wrist (左腕)
11. right_wrist (右腕)
12. left_hip (左髋)
13. right_hip (右髋)
14. left_knee (左膝)
15. right_knee (右膝)
16. left_ankle (左踝)
17. right_ankle (右踝)

## 故障排除

### 如果Outliner中完全没有节点：
1. **重新导入文件**：
   - File > Import
   - 选择FBX文件
   - 在导入选项中确保勾选所有相关选项

2. **检查导入错误**：
   - 查看Maya的Script Editor（Window > General Editors > Script Editor）
   - 查看是否有错误或警告信息

3. **尝试不同的导入方式**：
   - File > Open（而不是Import）
   - 或者拖拽FBX文件到Maya视口中

4. **文件路径问题**：
   - 检查文件路径中是否包含中文字符
   - 尝试将文件复制到英文路径下再导入
   - 确保文件路径不要太长

### 如果仍然看不到骨骼：
1. 检查Maya版本兼容性（建议Maya 2018或更高版本）
2. 尝试用其他3D软件（如Blender）打开FBX文件验证文件完整性
3. 重新生成FBX文件

## 技术细节
- FBX版本：7.4
- 文件格式：二进制
- 关节半径：5.0单位
- 坐标系：Maya标准坐标系