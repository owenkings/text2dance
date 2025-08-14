# FBX SDK 安装指南

## ⚠️ 重要提醒

根据之前的研究，FBX SDK在Python 3.11环境下存在兼容性问题。建议您先阅读本指南的兼容性说明，然后决定是否继续安装。

## 🐍 创建新的虚拟环境

### 方法1：使用conda创建环境（推荐）

```bash
# 创建Python 3.7环境（FBX SDK官方支持的最高版本）
conda create -n fbx_env python=3.7

# 激活环境
conda activate fbx_env

# 或者尝试Python 3.9（部分用户报告可用）
conda create -n fbx_env_39 python=3.9
conda activate fbx_env_39
```

### 方法2：使用venv创建环境

```bash
# 如果您有Python 3.7安装
python3.7 -m venv fbx_env

# Windows激活
fbx_env\Scripts\activate

# Linux/Mac激活
source fbx_env/bin/activate
```

## 📦 FBX SDK 安装步骤

### 步骤1：下载FBX SDK

1. 访问Autodesk官网：https://www.autodesk.com/developer-network/platform-technologies/fbx-sdk-2020-3-4
2. 注册Autodesk开发者账户（免费）
3. 下载适合您操作系统的FBX SDK

### 步骤2：安装FBX SDK

#### Windows安装
```bash
# 下载Windows版本的FBX SDK安装程序
# 运行安装程序，默认安装到：
# C:\Program Files\Autodesk\FBX\FBX SDK\2020.3.4
```

#### Linux安装
```bash
# 解压下载的tar.gz文件
tar -xzf fbx_sdk_linux.tar.gz

# 运行安装脚本
./fbx_sdk_linux
```

### 步骤3：安装Python绑定

```bash
# 激活您的虚拟环境
conda activate fbx_env  # 或 source fbx_env/bin/activate

# 尝试通过pip安装（可能不可用）
pip install fbx

# 如果pip安装失败，需要手动配置Python绑定
```

### 步骤4：手动配置Python绑定（如果需要）

```bash
# 找到FBX SDK安装目录中的Python绑定文件
# Windows: C:\Program Files\Autodesk\FBX\FBX SDK\2020.3.4\lib\Python37_x64
# Linux: /usr/local/fbx_sdk/lib/python3.7

# 将FBX Python模块添加到Python路径
export PYTHONPATH="$PYTHONPATH:/usr/local/fbx_sdk/lib/python3.7"

# 或在Python代码中添加
import sys
sys.path.append('/path/to/fbx/python/bindings')
```

## 🧪 测试安装

创建测试脚本 `test_fbx_sdk.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

try:
    import fbx
    print("✅ FBX SDK导入成功！")
    print(f"FBX SDK版本: {fbx.FbxManager.GetVersion()}")
    
    # 创建基本的FBX管理器
    manager = fbx.FbxManager.Create()
    print("✅ FBX管理器创建成功！")
    
    # 创建场景
    scene = fbx.FbxScene.Create(manager, "TestScene")
    print("✅ FBX场景创建成功！")
    
    print("🎉 FBX SDK安装和配置完成！")
    
except ImportError as e:
    print(f"❌ FBX SDK导入失败: {e}")
    print("请检查安装和Python路径配置")
    
except Exception as e:
    print(f"❌ FBX SDK测试失败: {e}")
```

## ⚠️ 已知兼容性问题

### Python版本兼容性
- **官方支持**: Python 3.7及以下
- **部分支持**: Python 3.9（需要手动编译或特殊配置）
- **不支持**: Python 3.10, 3.11（存在严重兼容性问题）

### 常见错误及解决方案

#### 错误1：`FbxAxisSystem`对象创建失败
```python
# 可能的解决方案
try:
    axis_system = fbx.FbxAxisSystem.MayaYUp
except:
    # 使用替代方法
    axis_system = fbx.FbxAxisSystem(fbx.FbxAxisSystem.eYAxis, fbx.FbxAxisSystem.eParityOdd, fbx.FbxAxisSystem.eRightHanded)
```

#### 错误2：模块找不到
```bash
# 确保Python路径正确
export PYTHONPATH="$PYTHONPATH:/path/to/fbx/python/bindings"

# 或在代码中添加
import sys
sys.path.insert(0, '/path/to/fbx/python/bindings')
```

## 🔄 替代方案

如果FBX SDK安装遇到困难，建议考虑以下替代方案：

1. **继续使用当前的自制FBX生成器**（推荐）
   - 无依赖问题
   - 已验证可在Maya中正常工作
   - 支持完整的COCO骨骼结构

2. **使用Blender作为中间转换工具**
   ```bash
   # 通过Blender Python API处理FBX
   blender --background --python fbx_converter.py
   ```

3. **使用其他FBX库**
   ```bash
   pip install pyfbx  # 第三方FBX库
   ```

## 📝 安装验证清单

- [ ] 创建了合适版本的Python虚拟环境
- [ ] 下载并安装了FBX SDK
- [ ] 配置了Python绑定路径
- [ ] 运行测试脚本成功
- [ ] 能够创建FBX管理器和场景
- [ ] 能够导入和导出FBX文件

## 🆘 如果安装失败

如果按照本指南安装仍然失败，建议：

1. **回到原方案**：使用已经验证可工作的自制FBX生成器
2. **报告问题**：记录具体的错误信息，以便进一步分析
3. **考虑降级Python版本**：创建Python 3.7环境专门用于FBX SDK

---

**注意**：FBX SDK的安装和配置相对复杂，特别是在较新的Python版本上。如果您的主要目标是生成Maya可用的FBX文件，当前的自制生成器已经能够很好地满足需求。