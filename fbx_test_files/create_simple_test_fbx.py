#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建简单的测试FBX文件
只包含3个关节，用于测试Maya导入功能
"""

import struct
import os

def write_property(f, prop_type, value):
    """写入属性"""
    f.write(struct.pack('<c', prop_type.encode('ascii')))
    
    if prop_type == 'S':  # 字符串
        encoded = value.encode('utf-8')
        f.write(struct.pack('<I', len(encoded)))
        f.write(encoded)
    elif prop_type == 'I':  # 整数
        f.write(struct.pack('<i', value))
    elif prop_type == 'F':  # 浮点数
        f.write(struct.pack('<f', value))
    elif prop_type == 'd':  # 双精度数组
        f.write(struct.pack('<I', len(value)))
        f.write(struct.pack('<I', 0))  # encoding
        f.write(struct.pack('<I', len(value) * 8))  # compressed length
        for v in value:
            f.write(struct.pack('<d', v))

def write_node_record(f, name, properties, children):
    """写入节点记录"""
    # 计算节点大小（占位符）
    size_pos = f.tell()
    f.write(struct.pack('<Q', 0))  # end_offset 占位符
    f.write(struct.pack('<Q', len(properties)))  # num_properties
    f.write(struct.pack('<Q', 0))  # property_list_len 占位符
    
    # 写入节点名称
    name_bytes = name.encode('utf-8')
    f.write(struct.pack('<B', len(name_bytes)))
    f.write(name_bytes)
    
    # 记录属性开始位置
    prop_start = f.tell()
    
    # 写入属性
    for prop_type, value in properties:
        write_property(f, prop_type, value)
    
    # 记录属性结束位置
    prop_end = f.tell()
    
    # 写入子节点
    for child_name, child_props, child_children in children:
        write_node_record(f, child_name, child_props, child_children)
    
    # 写入空记录标记子节点结束
    if children:
        f.write(struct.pack('<QQQB', 0, 0, 0, 0))
    
    # 更新节点大小信息
    end_pos = f.tell()
    f.seek(size_pos)
    f.write(struct.pack('<Q', end_pos))  # end_offset
    f.seek(size_pos + 16)
    f.write(struct.pack('<Q', prop_end - prop_start))  # property_list_len
    f.seek(end_pos)

def create_simple_fbx():
    """创建简单的FBX文件"""
    filename = "simple_test.fbx"
    
    with open(filename, 'wb') as f:
        # 写入FBX文件头
        f.write(b'Kaydara FBX Binary  \x00')
        f.write(struct.pack('<I', 7400))  # 版本号
        
        # 创建根节点
        write_node_record(f, "FBXHeaderExtension", [], [
            ("FBXHeaderVersion", [('I', 1003)], []),
            ("FBXVersion", [('I', 7400)], []),
            ("Creator", [('S', "Simple FBX Test Generator")], [])
        ])
        
        # 创建定义节点
        write_node_record(f, "Definitions", [], [
            ("Version", [('I', 100)], []),
            ("Count", [('I', 3)], []),
            ("ObjectType", [('S', "Model")], [
                ("Count", [('I', 3)], [])
            ])
        ])
        
        # 创建对象节点
        joints = [
            ("nose", [0.0, 10.0, 0.0]),
            ("left_shoulder", [-5.0, 5.0, 0.0]),
            ("right_shoulder", [5.0, 5.0, 0.0])
        ]
        
        objects = []
        for i, (joint_name, pos) in enumerate(joints):
            joint_id = 1000 + i
            objects.append(("Model", [
                ('I', joint_id),
                ('S', f"{joint_name}\x00\x01Model"),
                ('S', "Joint")
            ], [
                ("Version", [('I', 232)], []),
                ("Properties70", [], [
                    ("P", [('S', "Lcl Translation"), ('S', "Lcl Translation"), ('S', ""), ('S', "A"), ('d', pos)], [])
                ])
            ]))
        
        write_node_record(f, "Objects", [], objects)
        
        # 创建连接节点
        write_node_record(f, "Connections", [], [])
        
        # 创建Takes节点
        write_node_record(f, "Takes", [], [
            ("Current", [('S', "")], [])
        ])
        
        # 写入文件结尾
        f.write(b'\x00' * 13)
        f.write(b'\xf8\x5a\x8c\x6a\xde\xf5\xd9\x7e\xec\xe9\x0c\xe3\x75\x8f\x29\x0b')
    
    print(f"✅ 简单测试FBX文件已创建: {filename}")
    print("📝 包含3个关节: nose, left_shoulder, right_shoulder")
    print("💡 请尝试将此文件导入Maya进行测试")
    
    return filename

if __name__ == "__main__":
    create_simple_fbx()