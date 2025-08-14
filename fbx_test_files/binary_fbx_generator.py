import struct
import os
from datetime import datetime
import numpy as np

def create_binary_fbx(joints3d, output_path, person_id, frame_ids=None):
    """
    创建二进制FBX文件
    
    Args:
        joints3d: 3D关节数据 (num_frames, num_joints, 3)
        output_path: 输出路径
        person_id: 人物ID
        frame_ids: 帧ID列表
    """
    try:
        # COCO 17关节名称
        joint_names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        # 骨骼连接关系
        bone_connections = [
            (0, 1), (0, 2),  # nose to eyes
            (1, 3), (2, 4),  # eyes to ears
            (0, 5), (0, 6),  # nose to shoulders
            (5, 7), (6, 8),  # shoulders to elbows
            (7, 9), (8, 10), # elbows to wrists
            (0, 11), (0, 12), # nose to hips
            (11, 13), (12, 14), # hips to knees
            (13, 15), (14, 16)  # knees to ankles
        ]
        
        # 创建输出目录
        fbx_output_dir = os.path.join(output_path, 'fbx_output')
        os.makedirs(fbx_output_dir, exist_ok=True)
        fbx_file_path = os.path.join(fbx_output_dir, f'person_{person_id:04d}_skeleton.fbx')
        
        with open(fbx_file_path, 'wb') as f:
            # 写入FBX二进制文件头
            # Bytes 0-20: "Kaydara FBX Binary  \x00" (21 bytes)
            header_magic = b"Kaydara FBX Binary  \x00"
            f.write(header_magic)
            
            # Bytes 21-22: [0x1A, 0x00] (header size indicator)
            f.write(struct.pack('<H', 0x001A))
            
            # Bytes 23-26: version number (7400 for FBX 7.4)
            f.write(struct.pack('<I', 7400))
            
            # 写入根节点记录
            write_node_record(f, "", [], [
                create_fbx_header_extension(),
                create_definitions(joint_names),
                create_objects(joint_names, joints3d),
                create_connections(joint_names, bone_connections),
                create_takes(len(joints3d))
            ])
            
            # 写入文件尾部
            # 写入空节点记录标记文件结束
            f.write(struct.pack('<I', 0))  # end_offset
            f.write(struct.pack('<I', 0))  # num_properties
            f.write(struct.pack('<I', 0))  # property_list_len
            f.write(b'\x00')  # name_len
            
            # 写入未知的尾部数据
            f.write(b'\x00' * 160)  # 填充160字节的尾部
        
        print(f"二进制FBX文件已保存到: {fbx_file_path}")
        return fbx_file_path
        
    except Exception as e:
        print(f"创建二进制FBX文件时出错: {str(e)}")
        return None

def write_node_record(f, name, properties, children):
    """写入节点记录"""
    # 计算节点大小
    start_pos = f.tell()
    
    # 预留空间给节点头
    f.write(b'\x00' * 13)  # end_offset(4) + num_properties(4) + property_list_len(4) + name_len(1)
    
    # 写入节点名称
    name_bytes = name.encode('utf-8')
    f.write(name_bytes)
    
    # 写入属性
    properties_start = f.tell()
    for prop in properties:
        write_property(f, prop)
    properties_end = f.tell()
    
    # 写入子节点
    for child in children:
        if isinstance(child, tuple) and len(child) == 3:
            child_name, child_props, child_children = child
            write_node_record(f, child_name, child_props, child_children)
    
    # 计算并写入节点头信息
    end_pos = f.tell()
    f.seek(start_pos)
    f.write(struct.pack('<I', end_pos))  # end_offset
    f.write(struct.pack('<I', len(properties)))  # num_properties
    f.write(struct.pack('<I', properties_end - properties_start))  # property_list_len
    f.write(struct.pack('<B', len(name_bytes)))  # name_len
    f.seek(end_pos)

def write_property(f, prop):
    """写入属性"""
    prop_type, value = prop
    f.write(prop_type.encode('ascii'))
    
    if prop_type == 'S':  # String
        value_bytes = value.encode('utf-8')
        f.write(struct.pack('<I', len(value_bytes)))
        f.write(value_bytes)
    elif prop_type == 'I':  # Int32
        f.write(struct.pack('<i', value))
    elif prop_type == 'L':  # Int64
        f.write(struct.pack('<q', value))
    elif prop_type == 'F':  # Float32
        f.write(struct.pack('<f', value))
    elif prop_type == 'D':  # Float64
        f.write(struct.pack('<d', value))
    elif prop_type == 'f':  # Float32 Array
        f.write(struct.pack('<I', len(value)))
        f.write(struct.pack('<I', 0))  # encoding (0 = raw)
        f.write(struct.pack('<I', len(value) * 4))  # compressed_length
        for v in value:
            f.write(struct.pack('<f', v))
    elif prop_type == 'd':  # Float64 Array
        f.write(struct.pack('<I', len(value)))
        f.write(struct.pack('<I', 0))  # encoding (0 = raw)
        f.write(struct.pack('<I', len(value) * 8))  # compressed_length
        for v in value:
            f.write(struct.pack('<d', v))

def create_fbx_header_extension():
    """创建FBX头部扩展节点"""
    now = datetime.now()
    return ("FBXHeaderExtension", [], [
        ("FBXHeaderVersion", [('I', 1003)], []),
        ("FBXVersion", [('I', 7400)], []),
        ("CreationTimeStamp", [], [
            ("Version", [('I', 1000)], []),
            ("Year", [('I', now.year)], []),
            ("Month", [('I', now.month)], []),
            ("Day", [('I', now.day)], []),
            ("Hour", [('I', now.hour)], []),
            ("Minute", [('I', now.minute)], []),
            ("Second", [('I', now.second)], []),
            ("Millisecond", [('I', 0)], [])
        ]),
        ("Creator", [('S', "Binary FBX Converter for Maya")], [])
    ])

def create_definitions(joint_names):
    """创建定义节点"""
    return ("Definitions", [], [
        ("Version", [('I', 100)], []),
        ("Count", [('I', len(joint_names) + 5)], []),
        ("ObjectType", [('S', "Model")], [
            ("Count", [('I', len(joint_names))], [])
        ]),
        ("ObjectType", [('S', "Geometry")], [
            ("Count", [('I', len(joint_names))], [])
        ]),
        ("ObjectType", [('S', "Material")], [
            ("Count", [('I', 1)], [])
        ])
    ])

def create_objects(joint_names, joints3d):
    """创建对象节点"""
    objects = []
    
    # 创建根骨骼节点
    objects.append(("Model", [('L', 999999), ('S', "Model::Skeleton"), ('S', "Skeleton")], [
        ("Version", [('I', 232)], []),
        ("Properties70", [], [
            ("P", [('S', "Lcl Translation"), ('S', "Lcl Translation"), ('S', ""), ('S', "A"), 
                  ('D', 0.0), ('D', 0.0), ('D', 0.0)], []),
            ("P", [('S', "Lcl Rotation"), ('S', "Lcl Rotation"), ('S', ""), ('S', "A"), 
                  ('D', 0.0), ('D', 0.0), ('D', 0.0)], []),
            ("P", [('S', "Lcl Scaling"), ('S', "Lcl Scaling"), ('S', ""), ('S', "A"), 
                  ('D', 1.0), ('D', 1.0), ('D', 1.0)], [])
        ])
    ]))
    
    # 创建材质
    objects.append(("Material", [('L', 2000000), ('S', "Material::BoneMaterial"), ('S', "")], [
        ("Version", [('I', 102)], []),
        ("ShadingModel", [('S', "phong")], []),
        ("MultiLayer", [('I', 0)], []),
        ("Properties70", [], [
            ("P", [('S', "DiffuseColor"), ('S', "Color"), ('S', ""), ('S', "A"), ('D', 1.0), ('D', 0.5), ('D', 0.0)], [])
        ])
    ]))
    
    # 创建几何体和模型
    for i, joint_name in enumerate(joint_names):
        # 创建球体几何体
        vertices, indices = create_sphere_geometry(5.0)  # 半径5.0，更容易看见5cm半径的球体
        
        objects.append(("Geometry", [('L', 3000000 + i), ('S', f"Geometry::{joint_name}_sphere"), ('S', "Mesh")], [
            ("Vertices", [('d', vertices.flatten())], []),
            ("PolygonVertexIndex", [('i', indices.flatten())], []),
            ("GeometryVersion", [('I', 124)], [])
        ]))
        
        # 创建关节节点 (使用LimbNode类型)
        first_frame_pos = joints3d[0][i]  # 使用原始坐标，不放大
        objects.append(("Model", [('L', 1000000 + i), ('S', f"Model::{joint_name}"), ('S', "LimbNode")], [
            ("Version", [('I', 232)], []),
            ("Properties70", [], [
                ("P", [('S', "Lcl Translation"), ('S', "Lcl Translation"), ('S', ""), ('S', "A"), 
                      ('D', float(first_frame_pos[0])), ('D', float(first_frame_pos[1])), ('D', float(first_frame_pos[2]))], []),
                ("P", [('S', "Lcl Rotation"), ('S', "Lcl Rotation"), ('S', ""), ('S', "A"), 
                      ('D', 0.0), ('D', 0.0), ('D', 0.0)], []),
                ("P", [('S', "Lcl Scaling"), ('S', "Lcl Scaling"), ('S', ""), ('S', "A"), 
                      ('D', 1.0), ('D', 1.0), ('D', 1.0)], [])
            ])
        ]))
    
    return ("Objects", [], objects)

def create_sphere_geometry(radius, segments=8):
    """创建球体几何体"""
    vertices = []
    indices = []
    
    # 创建球体顶点
    for i in range(segments + 1):
        lat = np.pi * (-0.5 + float(i) / segments)
        for j in range(segments * 2 + 1):
            lon = 2 * np.pi * float(j) / (segments * 2)
            x = radius * np.cos(lat) * np.cos(lon)
            y = radius * np.cos(lat) * np.sin(lon)
            z = radius * np.sin(lat)
            vertices.extend([x, y, z])
    
    # 创建球体面
    for i in range(segments):
        for j in range(segments * 2):
            first = i * (segments * 2 + 1) + j
            second = first + segments * 2 + 1
            
            # 第一个三角形
            indices.extend([first, second, first + 1])
            # 第二个三角形
            indices.extend([second, second + 1, first + 1])
    
    # 转换为负索引格式（FBX要求）
    fbx_indices = []
    for i in range(0, len(indices), 3):
        fbx_indices.extend([indices[i], indices[i+1], -(indices[i+2]+1)])
    
    return np.array(vertices), np.array(fbx_indices)

def create_connections(joint_names, bone_connections):
    """创建连接节点"""
    connections = []
    
    # 连接几何体到模型
    for i in range(len(joint_names)):
        connections.append(("C", [('S', "OO"), ('L', 3000000 + i), ('L', 1000000 + i)], []))
        connections.append(("C", [('S', "OO"), ('L', 2000000), ('L', 1000000 + i)], []))
    
    # 创建骨骼层次结构
    connected_joints = set()
    
    # 连接有父子关系的骨骼
    for parent_idx, child_idx in bone_connections:
        connections.append(("C", [('S', "OO"), ('L', 1000000 + child_idx), ('L', 1000000 + parent_idx)], []))
        connected_joints.add(child_idx)
        connected_joints.add(parent_idx)
    
    # 将没有父节点的关节连接到根骨骼
    for i in range(len(joint_names)):
        if i not in connected_joints or i not in [child for _, child in bone_connections]:
            connections.append(("C", [('S', "OO"), ('L', 1000000 + i), ('L', 999999)], []))
    
    return ("Connections", [], connections)

def create_takes(num_frames):
    """创建Takes节点"""
    return ("Takes", [], [
        ("Current", [('S', "Take 001")], []),
        ("Take", [('S', "Take 001")], [
            ("FileName", [('S', "Take_001.tak")], []),
            ("LocalTime", [('L', 0), ('L', (num_frames-1) * 1539538600)], []),
            ("ReferenceTime", [('L', 0), ('L', (num_frames-1) * 1539538600)], [])
        ])
    ])

if __name__ == "__main__":
    # 测试代码
    import numpy as np
    
    # 创建测试数据
    num_frames = 10
    num_joints = 17
    joints3d = np.random.rand(num_frames, num_joints, 3) * 2 - 1  # -1到1之间的随机数据
    
    create_binary_fbx(joints3d, "test_output", 1)