import numpy as np
import joblib
import os
from pathlib import Path

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False
    print("Open3D未安装。请运行: pip install open3d")

def create_mesh_from_vertices(vertices, faces=None, color=[0.7, 0.7, 0.9]):
    """
    从顶点创建Open3D网格
    
    Args:
        vertices: 顶点坐标 (N, 3)
        faces: 面片索引 (M, 3)，如果为None则创建点云
        color: 颜色 [R, G, B]
    
    Returns:
        Open3D网格或点云对象
    """
    if not OPEN3D_AVAILABLE:
        raise ImportError("Open3D未安装")
    
    if faces is not None:
        # 创建网格
        mesh = o3d.geometry.TriangleMesh()
        mesh.vertices = o3d.utility.Vector3dVector(vertices)
        mesh.triangles = o3d.utility.Vector3iVector(faces)
        mesh.paint_uniform_color(color)
        mesh.compute_vertex_normals()
        return mesh
    else:
        # 创建点云
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(vertices)
        pcd.paint_uniform_color(color)
        return pcd

def create_skeleton_from_joints(joints_3d, skeleton_connections, color=[1.0, 0.0, 0.0]):
    """
    从3D关节点创建骨架线段
    
    Args:
        joints_3d: 3D关节点坐标 (N, 3)
        skeleton_connections: 骨架连接关系列表
        color: 颜色 [R, G, B]
    
    Returns:
        Open3D线段集合
    """
    if not OPEN3D_AVAILABLE:
        raise ImportError("Open3D未安装")
    
    # 创建关节点
    joint_spheres = []
    for joint in joints_3d:
        sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.02)
        sphere.translate(joint)
        sphere.paint_uniform_color([1.0, 0.0, 0.0])  # 红色关节点
        joint_spheres.append(sphere)
    
    # 创建骨架连接线
    lines = []
    line_colors = []
    
    for connection in skeleton_connections:
        start_idx, end_idx = connection
        if start_idx < len(joints_3d) and end_idx < len(joints_3d):
            lines.append([start_idx, end_idx])
            line_colors.append(color)
    
    line_set = o3d.geometry.LineSet()
    line_set.points = o3d.utility.Vector3dVector(joints_3d)
    line_set.lines = o3d.utility.Vector2iVector(lines)
    line_set.colors = o3d.utility.Vector3dVector(line_colors)
    
    return joint_spheres, line_set

def visualize_single_frame(mesh_vertices, faces=None, joints_3d=None, skeleton_connections=None, 
                          title="3D Human Pose", save_path=None):
    """
    可视化单帧3D数据
    
    Args:
        mesh_vertices: 网格顶点 (N, 3)
        faces: 网格面片 (M, 3)
        joints_3d: 3D关节点 (J, 3)
        skeleton_connections: 骨架连接关系
        title: 窗口标题
        save_path: 保存截图路径
    """
    if not OPEN3D_AVAILABLE:
        print("Open3D未安装，无法进行3D可视化")
        return
    
    # 创建可视化器
    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=title, width=1024, height=768)
    
    # 添加网格
    if faces is not None:
        mesh = create_mesh_from_vertices(mesh_vertices, faces, color=[0.7, 0.7, 0.9])
        vis.add_geometry(mesh)
    else:
        # 如果没有面片信息，显示点云（采样）
        sampled_vertices = mesh_vertices[::20]  # 采样以提高性能
        pcd = create_mesh_from_vertices(sampled_vertices, color=[0.7, 0.7, 0.9])
        vis.add_geometry(pcd)
    
    # 添加骨架（如果提供）
    if joints_3d is not None and skeleton_connections is not None:
        joint_spheres, line_set = create_skeleton_from_joints(joints_3d, skeleton_connections)
        for sphere in joint_spheres:
            vis.add_geometry(sphere)
        vis.add_geometry(line_set)
    
    # 设置渲染选项
    render_option = vis.get_render_option()
    render_option.mesh_show_wireframe = False
    render_option.mesh_show_back_face = True
    render_option.point_size = 2.0
    
    # 设置视角
    view_control = vis.get_view_control()
    view_control.set_front([0, 0, -1])
    view_control.set_up([0, -1, 0])
    view_control.set_lookat([0, 0, 0])
    view_control.set_zoom(0.8)
    
    if save_path:
        # 保存截图
        vis.poll_events()
        vis.update_renderer()
        vis.capture_screen_image(save_path)
        print(f"截图保存至: {save_path}")
        vis.destroy_window()
    else:
        # 交互式显示
        print("按Q键退出可视化")
        vis.run()
        vis.destroy_window()

def visualize_pmce_results_open3d(pkl_file_path, faces_file=None, output_dir=None, interactive=True):
    """
    使用Open3D可视化PMCE结果
    
    Args:
        pkl_file_path: PMCE输出的pkl文件路径
        faces_file: SMPL面片文件路径（.npy格式）
        output_dir: 保存截图的目录
        interactive: 是否交互式显示
    """
    if not OPEN3D_AVAILABLE:
        print("Open3D未安装，请运行: pip install open3d")
        return
    
    # 加载结果
    results = joblib.load(pkl_file_path)
    
    # 加载SMPL面片（如果提供）
    faces = None
    if faces_file and os.path.exists(faces_file):
        faces = np.load(faces_file)
        print(f"加载面片文件: {faces_file}")
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"找到 {len(results)} 个人的结果")
    
    for person_id, person_data in results.items():
        print(f"\n处理人员 ID: {person_id}")
        
        meshes = person_data['mesh']  # (T, 6890, 3)
        frame_ids = person_data['frame_ids']
        
        print(f"帧数: {len(meshes)}")
        
        # 可视化几个关键帧
        key_frames = [0, len(meshes)//4, len(meshes)//2, 3*len(meshes)//4, len(meshes)-1]
        
        for i, frame_idx in enumerate(key_frames):
            if frame_idx >= len(meshes):
                continue
                
            mesh_vertices = meshes[frame_idx]  # (6890, 3)
            title = f"Person {person_id} - Frame {frame_ids[frame_idx]}"
            
            save_path = None
            if output_dir:
                save_path = os.path.join(output_dir, f"person_{person_id}_frame_{frame_idx}.png")
            
            if interactive and not output_dir:
                # 交互式显示
                print(f"显示: {title}")
                visualize_single_frame(
                    mesh_vertices, faces, 
                    title=title
                )
            else:
                # 保存截图
                visualize_single_frame(
                    mesh_vertices, faces,
                    title=title, save_path=save_path
                )

def create_animation_open3d(pkl_file_path, faces_file=None, output_dir="./3d_animation_open3d", person_id=None):
    """
    使用Open3D创建3D动画
    
    Args:
        pkl_file_path: PMCE输出的pkl文件路径
        faces_file: SMPL面片文件路径
        output_dir: 保存动画帧的目录
        person_id: 指定人员ID
    """
    if not OPEN3D_AVAILABLE:
        print("Open3D未安装，请运行: pip install open3d")
        return
    
    results = joblib.load(pkl_file_path)
    
    if person_id is None:
        person_id = list(results.keys())[0]
    
    if person_id not in results:
        print(f"未找到人员ID {person_id}")
        return
    
    # 加载面片
    faces = None
    if faces_file and os.path.exists(faces_file):
        faces = np.load(faces_file)
    
    person_data = results[person_id]
    meshes = person_data['mesh']
    frame_ids = person_data['frame_ids']
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"为人员 {person_id} 创建 {len(meshes)} 帧动画")
    
    for i, mesh_vertices in enumerate(meshes):
        save_path = output_dir / f"frame_{i:06d}.png"
        title = f"Person {person_id} - Frame {frame_ids[i]}"
        
        visualize_single_frame(
            mesh_vertices, faces,
            title=title, save_path=str(save_path)
        )
        
        if i % 10 == 0:
            print(f"已处理 {i+1}/{len(meshes)} 帧")
    
    print(f"动画帧保存在: {output_dir}")
    print("可以使用ffmpeg将这些帧合成为视频:")
    print(f"ffmpeg -r 30 -i {output_dir}/frame_%06d.png -c:v libx264 -pix_fmt yuv420p output_3d_animation.mp4")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Open3D 3D可视化工具")
    parser.add_argument('--pkl_file', type=str, required=True, help='PMCE输出的pkl文件路径')
    parser.add_argument('--faces_file', type=str, help='SMPL面片文件路径（.npy格式）')
    parser.add_argument('--output_dir', type=str, help='保存截图的目录')
    parser.add_argument('--no_interactive', action='store_true', help='不使用交互式显示')
    parser.add_argument('--animation', action='store_true', help='创建动画序列')
    parser.add_argument('--person_id', type=int, help='指定人员ID')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pkl_file):
        print(f"文件不存在: {args.pkl_file}")
        exit(1)
    
    if args.animation:
        if not args.output_dir:
            args.output_dir = "./3d_animation_open3d"
        create_animation_open3d(args.pkl_file, args.faces_file, args.output_dir, args.person_id)
    else:
        visualize_pmce_results_open3d(
            args.pkl_file, 
            args.faces_file,
            args.output_dir, 
            interactive=not args.no_interactive
        )