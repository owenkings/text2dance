
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("🧪 测试FBX SDK安装...")

try:
    import fbx
    print("✅ FBX SDK导入成功！")
    
    # 获取版本信息
    try:
        version = fbx.FbxManager.GetVersion()
        print(f"📦 FBX SDK版本: {version}")
    except:
        print("⚠️ 无法获取FBX SDK版本")
    
    # 创建基本对象
    try:
        manager = fbx.FbxManager.Create()
        print("✅ FBX管理器创建成功")
        
        scene = fbx.FbxScene.Create(manager, "TestScene")
        print("✅ FBX场景创建成功")
        
        # 测试轴系统创建
        try:
            axis_system = fbx.FbxAxisSystem.MayaYUp
            print("✅ FBX轴系统创建成功")
        except Exception as e:
            print(f"⚠️ FBX轴系统创建失败: {e}")
        
        print("🎉 FBX SDK基本功能测试通过！")
        
    except Exception as e:
        print(f"❌ FBX对象创建失败: {e}")
        
except ImportError as e:
    print(f"❌ FBX SDK导入失败: {e}")
    print("
💡 可能的解决方案:")
    print("1. 确保已安装FBX SDK")
    print("2. 检查Python版本兼容性（推荐Python 3.7）")
    print("3. 配置正确的PYTHONPATH")
    print("4. 考虑使用自制FBX生成器作为替代方案")
    
except Exception as e:
    print(f"❌ 未知错误: {e}")
