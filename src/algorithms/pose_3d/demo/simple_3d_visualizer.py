import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import joblib
import os
import cv2
from pathlib import Path

def plot_3d_skeleton(joints_3d, skeleton_connections, title="3D Human Pose"):
    """
    使用matplotlib绘制3D人体骨架
    
    Args:
        joints_3d: 3D关节点坐标 (N, 3)
        skeleton_connections: 骨架连接关系列表
        title: 图表标题
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # 绘制关节点
    ax.scatter(joints_3d[:, 0], joints_3d[:, 1], joints_3d[:, 2], 
               c='red', s=50, alpha=0.8)
    
    # 绘制骨架连接
    for connection in skeleton_connections:
        start_idx, end_idx = connection
        if start_idx < len(joints_3d) and end_idx < len(joints_3d):
            start_point = joints_3d[start_idx]
            end_point = joints_3d[end_idx]
            ax.plot([start_point[0], end_point[0]], 
                   [start_point[1], end_point[1]], 
                   [start_point[2], end_point[2]], 
                   'b-', linewidth=2)
    
    # 设置坐标轴
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(title)
    
    # 设置相等的坐标轴比例
    max_range = np.array([joints_3d[:, 0].max() - joints_3d[:, 0].min(),
                         joints_3d[:, 1].max() - joints_3d[:, 1].min(),
                         joints_3d[:, 2].max() - joints_3d[:, 2].min()]).max() / 2.0
    
    mid_x = (joints_3d[:, 0].max() + joints_3d[:, 0].min()) * 0.5
    mid_y = (joints_3d[:, 1].max() + joints_3d[:, 1].min()) * 0.5
    mid_z = (joints_3d[:, 2].max() + joints_3d[:, 2].min()) * 0.5
    
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
    
    return fig, ax

def plot_3d_mesh_points(vertices, title="3D Mesh", sample_rate=10):
    """
    使用matplotlib绘制3D网格点云
    
    Args:
        vertices: 3D顶点坐标 (N, 3)
        title: 图表标题
        sample_rate: 采样率，只显示部分点以提高性能
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # 采样顶点以提高性能
    sampled_vertices = vertices[::sample_rate]
    
    # 绘制点云
    ax.scatter(sampled_vertices[:, 0], sampled_vertices[:, 1], sampled_vertices[:, 2], 
               c=sampled_vertices[:, 2], cmap='viridis', s=1, alpha=0.6)
    
    # 设置坐标轴
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(title)
    
    return fig, ax

def visualize_pmce_results(pkl_file_path, output_dir=None, show_plots=True):
    """
    可视化PMCE结果
    
    Args:
        pkl_file_path: PMCE输出的pkl文件路径
        output_dir: 保存图片的目录
        show_plots: 是否显示图片
    """
    # 加载结果
    results = joblib.load(pkl_file_path)
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # COCO骨架连接关系
    skeleton_connections = [
        (1, 2), (0, 1), (0, 2), (2, 4), (1, 3), (6, 8), (8, 10), 
        (5, 7), (7, 9), (12, 14), (14, 16), (11, 13), (13, 15),
        (17, 11), (17, 12), (17, 18), (18, 5), (18, 6), (18, 0)
    ]
    
    print(f"找到 {len(results)} 个人的结果")
    
    for person_id, person_data in results.items():
        print(f"\n处理人员 ID: {person_id}")
        
        meshes = person_data['mesh']  # (T, 6890, 3)
        cams = person_data['pred_cam']  # (T, 3)
        frame_ids = person_data['frame_ids']
        
        print(f"帧数: {len(meshes)}")
        print(f"网格顶点数: {meshes[0].shape[0]}")
        
        # 可视化几个关键帧
        key_frames = [0, len(meshes)//4, len(meshes)//2, 3*len(meshes)//4, len(meshes)-1]
        
        for i, frame_idx in enumerate(key_frames):
            if frame_idx >= len(meshes):
                continue
                
            mesh_vertices = meshes[frame_idx]  # (6890, 3)
            
            # 绘制3D网格点云
            fig, ax = plot_3d_mesh_points(
                mesh_vertices, 
                title=f"Person {person_id} - Frame {frame_ids[frame_idx]} - 3D Mesh",
                sample_rate=20  # 只显示1/20的点
            )
            
            if output_dir:
                save_path = os.path.join(output_dir, f"person_{person_id}_frame_{frame_idx}_mesh.png")
                plt.savefig(save_path, dpi=150, bbox_inches='tight')
                print(f"保存图片: {save_path}")
            
            if show_plots:
                plt.show()
            else:
                plt.close()

def create_3d_animation(pkl_file_path, output_dir, person_id=None):
    """
    创建3D动画序列
    
    Args:
        pkl_file_path: PMCE输出的pkl文件路径
        output_dir: 保存动画帧的目录
        person_id: 指定人员ID，如果为None则处理第一个人
    """
    results = joblib.load(pkl_file_path)
    
    if person_id is None:
        person_id = list(results.keys())[0]
    
    if person_id not in results:
        print(f"未找到人员ID {person_id}")
        return
    
    person_data = results[person_id]
    meshes = person_data['mesh']
    frame_ids = person_data['frame_ids']
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"为人员 {person_id} 创建 {len(meshes)} 帧动画")
    
    for i, mesh_vertices in enumerate(meshes):
        fig, ax = plot_3d_mesh_points(
            mesh_vertices,
            title=f"Person {person_id} - Frame {frame_ids[i]}",
            sample_rate=30
        )
        
        # 设置固定的视角
        ax.view_init(elev=20, azim=45)
        
        save_path = output_dir / f"frame_{i:06d}.png"
        plt.savefig(save_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        if i % 10 == 0:
            print(f"已处理 {i+1}/{len(meshes)} 帧")
    
    print(f"动画帧保存在: {output_dir}")
    print("可以使用ffmpeg将这些帧合成为视频:")
    print(f"ffmpeg -r 30 -i {output_dir}/frame_%06d.png -c:v libx264 -pix_fmt yuv420p output_3d_animation.mp4")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="简单的3D可视化工具")
    parser.add_argument('--pkl_file', type=str, required=True, help='PMCE输出的pkl文件路径')
    parser.add_argument('--output_dir', type=str, help='保存图片的目录')
    parser.add_argument('--no_show', action='store_true', help='不显示图片，只保存')
    parser.add_argument('--animation', action='store_true', help='创建动画序列')
    parser.add_argument('--person_id', type=int, help='指定人员ID')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pkl_file):
        print(f"文件不存在: {args.pkl_file}")
        exit(1)
    
    if args.animation:
        if not args.output_dir:
            args.output_dir = "./3d_animation_frames"
        create_3d_animation(args.pkl_file, args.output_dir, args.person_id)
    else:
        visualize_pmce_results(
            args.pkl_file, 
            args.output_dir, 
            show_plots=not args.no_show
        )