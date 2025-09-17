#!/usr/bin/env python3
"""
3D Human Video Generator for PMCE Results
Generates videos showing realistic 3D human body from PMCE output
"""

import os
import sys
import pickle
import argparse
import numpy as np
import subprocess
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
except ImportError:
    print("Error: matplotlib not installed. Please install it with: pip install matplotlib")
    sys.exit(1)

# GPU support
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
    if GPU_AVAILABLE:
        print(f"GPU detected: {torch.cuda.get_device_name(0)}")
    else:
        print("Using CPU mode")
except ImportError:
    GPU_AVAILABLE = False
    print("PyTorch not found, using CPU mode")

# SMPL body model connections for skeleton visualization
SMPL_SKELETON_CONNECTIONS = [
    # Torso
    [0, 1], [0, 2], [0, 3],  # pelvis connections
    [1, 4], [2, 5], [3, 6],  # legs
    [4, 7], [5, 8], [6, 9],  # knees to ankles
    [7, 10], [8, 11],        # feet
    [0, 12], [12, 15],       # spine
    [15, 17], [15, 18], [15, 19],  # shoulders
    [17, 19], [18, 20],      # arms
    [19, 21], [20, 22],      # elbows to wrists
    [21, 23], [22, 24],      # hands
    # Head
    [15, 12], [12, 13], [13, 14], [14, 16]  # neck and head
]

# SMPL faces for mesh rendering - will be loaded from SMPL model
SMPL_FACES = None

def load_smpl_faces():
    """Load SMPL faces for mesh rendering"""
    global SMPL_FACES
    if SMPL_FACES is not None:
        return SMPL_FACES
    
    try:
        # Add project paths to sys.path
        project_root = os.path.dirname(os.path.abspath(__file__))
        lib_path = os.path.join(project_root, 'lib')
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # Try to load from lib.smpl
        from lib.smpl import SMPL
        smpl_model = SMPL()
        SMPL_FACES = smpl_model.face
        print(f"Loaded SMPL faces: {SMPL_FACES.shape}")
        return SMPL_FACES
    except Exception as e:
        print(f"Warning: Could not load SMPL faces: {e}")
        
        # Fallback: try to load faces directly from smplpytorch
        try:
            from smplpytorch.pytorch.smpl_layer import SMPL_Layer
            smpl_layer = SMPL_Layer(gender='neutral', model_root='smplpytorch/native/models')
            SMPL_FACES = smpl_layer.th_faces.numpy()
            print(f"Loaded SMPL faces from smplpytorch: {SMPL_FACES.shape}")
            return SMPL_FACES
        except Exception as e2:
            print(f"Warning: Fallback SMPL loading also failed: {e2}")
            
        # Final fallback: try to find pre-saved faces
        try:
            # 修正路径：从test_pose_2d_3d目录向上到pose3d目录，然后到data子目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            pose3d_dir = os.path.dirname(current_dir)  # 从test_pose_2d_3d到pose3d
            faces_file = os.path.join(pose3d_dir, 'data', 'smpl_faces.npy')
            if os.path.exists(faces_file):
                SMPL_FACES = np.load(faces_file)
                print(f"Loaded SMPL faces from file: {SMPL_FACES.shape}")
                return SMPL_FACES
            else:
                print(f"Face file not found at: {faces_file}")
                print("Trying to generate faces using simple_smpl_faces.py...")
                # Try to run the simple face generator
                import subprocess
                result = subprocess.run([sys.executable, 'simple_smpl_faces.py'], 
                                      capture_output=True, text=True, cwd=pose3d_dir)
                if result.returncode == 0 and os.path.exists(faces_file):
                    SMPL_FACES = np.load(faces_file)
                    print(f"Generated and loaded SMPL faces: {SMPL_FACES.shape}")
                    return SMPL_FACES
        except Exception as e3:
            print(f"Warning: Could not load faces from file: {e3}")
            
        print("Will use point cloud visualization instead of mesh")
        return None

# Key body joints for SMPL model (simplified)
SMPL_JOINT_INDICES = {
    'pelvis': 0, 'left_hip': 1, 'right_hip': 2, 'spine1': 3,
    'left_knee': 4, 'right_knee': 5, 'spine2': 6,
    'left_ankle': 7, 'right_ankle': 8, 'spine3': 9,
    'left_foot': 10, 'right_foot': 11, 'neck': 12,
    'left_collar': 13, 'right_collar': 14, 'head': 15,
    'left_shoulder': 16, 'right_shoulder': 17,
    'left_elbow': 18, 'right_elbow': 19,
    'left_wrist': 20, 'right_wrist': 21,
    'left_hand': 22, 'right_hand': 23
}

def load_pmce_results(pkl_file):
    """Load PMCE results from PKL file"""
    try:
        # Try joblib first (common for PMCE outputs)
        try:
            import joblib
            with open(pkl_file, 'rb') as f:
                data = joblib.load(f)
            print(f"Loaded PKL file with joblib: {pkl_file}")
        except:
            # Fallback to pickle with different encodings
            with open(pkl_file, 'rb') as f:
                try:
                    data = pickle.load(f)
                except:
                    data = pickle.load(f, encoding='latin1')
            print(f"Loaded PKL file with pickle: {pkl_file}")
        
        print(f"Data type: {type(data)}")
        if isinstance(data, dict):
            print(f"Data keys: {list(data.keys())}")
        return data
    except Exception as e:
        print(f"Error loading PKL file: {e}")
        return None

def extract_motion_data_from_pmce(data):
    """Extract motion data from PMCE results with correct structure"""
    motion_frames = []
    
    if isinstance(data, dict):
        # PMCE structure: {person_id: {data_type: frames_data}}
        for person_id, person_data in data.items():
            if isinstance(person_data, dict):
                # Get mesh data (vertices)
                mesh_data = person_data.get('mesh', None)
                pred_cam = person_data.get('pred_cam', None)
                bboxes = person_data.get('bboxes', None)
                frame_ids = person_data.get('frame_ids', None)
                
                if mesh_data is not None and len(mesh_data.shape) == 3:
                    # mesh_data shape: (num_frames, num_vertices, 3)
                    num_frames = mesh_data.shape[0]
                    print(f"Person {person_id}: {num_frames} frames, {mesh_data.shape[1]} vertices")
                    
                    for frame_idx in range(num_frames):
                        # Create frame info
                        frame_info = {
                            'frame_idx': frame_idx,
                            'persons': [{
                                'person_id': person_id,
                                'vertices': mesh_data[frame_idx],  # Shape: (6890, 3)
                                'pred_cam': pred_cam[frame_idx] if pred_cam is not None else None,
                                'bbox': bboxes[frame_idx] if bboxes is not None else None,
                                'frame_id': frame_ids[frame_idx] if frame_ids is not None else frame_idx
                            }]
                        }
                        motion_frames.append(frame_info)
    
    print(f"Extracted {len(motion_frames)} frames")
    return motion_frames

def extract_key_joints_from_mesh(vertices, joint_indices=None, use_gpu=False):
    """Extract key joints from mesh vertices for skeleton visualization with GPU acceleration"""
    if vertices is None or len(vertices) == 0:
        return None
    
    # Convert to GPU tensor if requested and available
    if use_gpu and GPU_AVAILABLE:
        device = torch.device('cuda')
        if isinstance(vertices, np.ndarray):
            vertices_tensor = torch.from_numpy(vertices).float().to(device)
        else:
            vertices_tensor = vertices.to(device)
    else:
        vertices_tensor = vertices if not isinstance(vertices, np.ndarray) else torch.from_numpy(vertices).float()
    
    # Use predefined joint indices or estimate from mesh
    if joint_indices is None:
        # Estimate key joint positions from mesh vertices using GPU acceleration
        joints = []
        
        if use_gpu and GPU_AVAILABLE:
            # GPU-accelerated percentile calculations
            z_coords = vertices_tensor[:, 2]
            z_percentiles = torch.quantile(z_coords, torch.tensor([0.10, 0.20, 0.35, 0.40, 0.80, 0.85, 0.95]).to(device))
            
            # Head (top vertices)
            head_mask = z_coords > z_percentiles[6]  # 95th percentile
            if head_mask.sum() > 0:
                joints.append(vertices_tensor[head_mask].mean(dim=0))
            
            # Neck
            neck_mask = (z_coords > z_percentiles[5]) & (z_coords < z_percentiles[6])  # 85-95th percentile
            if neck_mask.sum() > 0:
                joints.append(vertices_tensor[neck_mask].mean(dim=0))
            
            # Shoulders
            shoulder_level = z_percentiles[4]  # 80th percentile
            shoulder_mask = torch.abs(z_coords - shoulder_level) < 0.1
            if shoulder_mask.sum() > 0:
                shoulder_verts = vertices_tensor[shoulder_mask]
                x_coords = shoulder_verts[:, 0]
                left_shoulder_mask = x_coords == x_coords.min()
                right_shoulder_mask = x_coords == x_coords.max()
                if left_shoulder_mask.sum() > 0:
                    joints.append(shoulder_verts[left_shoulder_mask].mean(dim=0))
                if right_shoulder_mask.sum() > 0:
                    joints.append(shoulder_verts[right_shoulder_mask].mean(dim=0))
            
            # Torso center
            torso_mask = (z_coords > z_percentiles[3]) & (z_coords < z_percentiles[4])  # 40-80th percentile
            if torso_mask.sum() > 0:
                joints.append(vertices_tensor[torso_mask].mean(dim=0))
            
            # Hips
            hip_level = z_percentiles[2]  # 35th percentile
            hip_mask = torch.abs(z_coords - hip_level) < 0.1
            if hip_mask.sum() > 0:
                joints.append(vertices_tensor[hip_mask].mean(dim=0))
            
            # Knees
            knee_level = z_percentiles[1]  # 20th percentile
            knee_mask = torch.abs(z_coords - knee_level) < 0.1
            if knee_mask.sum() > 0:
                knee_verts = vertices_tensor[knee_mask]
                x_coords = knee_verts[:, 0]
                left_knee_mask = x_coords == x_coords.min()
                right_knee_mask = x_coords == x_coords.max()
                if left_knee_mask.sum() > 0:
                    joints.append(knee_verts[left_knee_mask].mean(dim=0))
                if right_knee_mask.sum() > 0:
                    joints.append(knee_verts[right_knee_mask].mean(dim=0))
            
            # Feet
            feet_mask = z_coords < z_percentiles[0]  # 10th percentile
            if feet_mask.sum() > 0:
                feet_verts = vertices_tensor[feet_mask]
                x_coords = feet_verts[:, 0]
                left_foot_mask = x_coords == x_coords.min()
                right_foot_mask = x_coords == x_coords.max()
                if left_foot_mask.sum() > 0:
                    joints.append(feet_verts[left_foot_mask].mean(dim=0))
                if right_foot_mask.sum() > 0:
                    joints.append(feet_verts[right_foot_mask].mean(dim=0))
            
            # Convert back to CPU numpy array
            if joints:
                joints_tensor = torch.stack(joints)
                return joints_tensor.cpu().numpy()
            else:
                return None
        else:
            # CPU fallback (original numpy implementation)
            vertices = vertices_tensor.numpy() if hasattr(vertices_tensor, 'numpy') else vertices_tensor
            
            # Head (top vertices)
            head_candidates = vertices[vertices[:, 2] > np.percentile(vertices[:, 2], 95)]
            if len(head_candidates) > 0:
                joints.append(np.mean(head_candidates, axis=0))
            
            # Neck (slightly below head)
            neck_candidates = vertices[(vertices[:, 2] > np.percentile(vertices[:, 2], 85)) & 
                                     (vertices[:, 2] < np.percentile(vertices[:, 2], 95))]
            if len(neck_candidates) > 0:
                joints.append(np.mean(neck_candidates, axis=0))
            
            # Shoulders (wide points at shoulder level)
            shoulder_level = np.percentile(vertices[:, 2], 80)
            shoulder_candidates = vertices[np.abs(vertices[:, 2] - shoulder_level) < 0.1]
            if len(shoulder_candidates) > 0:
                # Left and right shoulders
                left_shoulder = shoulder_candidates[shoulder_candidates[:, 0] == np.min(shoulder_candidates[:, 0])]
                right_shoulder = shoulder_candidates[shoulder_candidates[:, 0] == np.max(shoulder_candidates[:, 0])]
                if len(left_shoulder) > 0:
                    joints.append(np.mean(left_shoulder, axis=0))
                if len(right_shoulder) > 0:
                    joints.append(np.mean(right_shoulder, axis=0))
            
            # Torso center
            torso_candidates = vertices[(vertices[:, 2] > np.percentile(vertices[:, 2], 40)) & 
                                      (vertices[:, 2] < np.percentile(vertices[:, 2], 80))]
            if len(torso_candidates) > 0:
                joints.append(np.mean(torso_candidates, axis=0))
            
            # Hips
            hip_level = np.percentile(vertices[:, 2], 35)
            hip_candidates = vertices[np.abs(vertices[:, 2] - hip_level) < 0.1]
            if len(hip_candidates) > 0:
                joints.append(np.mean(hip_candidates, axis=0))
            
            # Knees (middle leg level)
            knee_level = np.percentile(vertices[:, 2], 20)
            knee_candidates = vertices[np.abs(vertices[:, 2] - knee_level) < 0.1]
            if len(knee_candidates) > 0:
                # Left and right knees
                left_knee = knee_candidates[knee_candidates[:, 0] == np.min(knee_candidates[:, 0])]
                right_knee = knee_candidates[knee_candidates[:, 0] == np.max(knee_candidates[:, 0])]
                if len(left_knee) > 0:
                    joints.append(np.mean(left_knee, axis=0))
                if len(right_knee) > 0:
                    joints.append(np.mean(right_knee, axis=0))
            
            # Feet (bottom vertices)
            feet_candidates = vertices[vertices[:, 2] < np.percentile(vertices[:, 2], 10)]
            if len(feet_candidates) > 0:
                # Left and right feet
                left_foot = feet_candidates[feet_candidates[:, 0] == np.min(feet_candidates[:, 0])]
                right_foot = feet_candidates[feet_candidates[:, 0] == np.max(feet_candidates[:, 0])]
                if len(left_foot) > 0:
                    joints.append(np.mean(left_foot, axis=0))
                if len(right_foot) > 0:
                    joints.append(np.mean(right_foot, axis=0))
            
            return np.array(joints) if joints else None
    else:
        # Use provided joint indices
        if use_gpu and GPU_AVAILABLE:
            result = vertices_tensor[joint_indices]
            return result.cpu().numpy() if hasattr(result, 'cpu') else result
        else:
            vertices = vertices_tensor.numpy() if hasattr(vertices_tensor, 'numpy') else vertices_tensor
            return vertices[joint_indices]

def plot_3d_human_mesh(ax, vertices, faces=None, color='lightblue', alpha=0.6, use_faces=True):
    """Plot 3D human mesh with face-based rendering or point cloud fallback"""
    
    if use_faces and faces is not None:
        # Render as 3D mesh with faces (solid surface)
        try:
            # Create mesh using faces
            mesh = Poly3DCollection(vertices[faces], alpha=alpha)
            
            # Set blue color (user preferred color)
            face_color = (0.3, 0.6, 0.9)  # Light blue tone
            edge_color = (0.2, 0.4, 0.7)  # Darker blue edge color
            
            mesh.set_facecolor(face_color)
            mesh.set_edgecolor(edge_color)
            mesh.set_linewidth(0.1)
            
            ax.add_collection3d(mesh)
            print("Rendered 3D human mesh with faces")
            return True
        except Exception as e:
            print(f"Warning: Face rendering failed: {e}")
            print("Falling back to point cloud visualization")
    
    # Fallback: render as enhanced point cloud to mimic solid appearance
    # Use less sampling to get denser point cloud for better visual effect
    sample_rate = 2 if len(vertices) > 3000 else 1
    if sample_rate > 1:
        sampled_indices = np.arange(0, len(vertices), sample_rate)
        sampled_vertices = vertices[sampled_indices]
    else:
        sampled_vertices = vertices
    
    # Plot as scatter points with larger size and better density for solid-like appearance
    z_values = sampled_vertices[:, 2]
    z_normalized = (z_values - z_values.min()) / (z_values.max() - z_values.min() + 1e-8)
    
    # Use consistent blue color (matching face rendering color)
    face_color = (0.3, 0.6, 0.9)  # Same as face rendering
    colors = [face_color] * len(sampled_vertices)  # Uniform color for consistency
    
    # Use larger points and higher alpha for more solid appearance
    ax.scatter(sampled_vertices[:, 0], 
              sampled_vertices[:, 1], 
              sampled_vertices[:, 2], 
              c=colors, s=8, alpha=min(alpha + 0.2, 1.0), edgecolors='none')
    
    return False

def plot_3d_skeleton(ax, joints, color='red', linewidth=2):
    """Plot 3D skeleton from joint positions"""
    if joints is None:
        return
    
    # Plot joints
    ax.scatter(joints[:, 0], joints[:, 1], joints[:, 2], 
              c=color, s=30, alpha=0.8, edgecolors='darkred')
    
    # Plot skeleton connections
    for connection in SMPL_SKELETON_CONNECTIONS:
        if len(connection) == 2:
            start_idx, end_idx = connection
            if start_idx < len(joints) and end_idx < len(joints):
                start_point = joints[start_idx]
                end_point = joints[end_idx]
                
                # Only draw if both points are valid
                if not (np.allclose(start_point, 0) or np.allclose(end_point, 0)):
                    ax.plot([start_point[0], end_point[0]],
                           [start_point[1], end_point[1]],
                           [start_point[2], end_point[2]],
                           color=color, linewidth=linewidth, alpha=0.8)

def setup_3d_plot(ax, title="3D Human Motion", frame_idx=None, total_frames=None):
    """Setup 3D plot with proper labels and limits"""
    ax.set_xlabel('X (meters)', fontsize=10)
    ax.set_ylabel('Y (meters)', fontsize=10)
    ax.set_zlabel('Z (meters)', fontsize=10)
    
    if frame_idx is not None:
        if total_frames is not None:
            ax.set_title(f"{title} - Frame {frame_idx+1}/{total_frames}", fontsize=12, fontweight='bold')
        else:
            ax.set_title(f"{title} - Frame {frame_idx+1}", fontsize=12, fontweight='bold')
    else:
        ax.set_title(title, fontsize=12, fontweight='bold')
    
    # Set equal aspect ratio and reasonable limits
    max_range = 1.2
    ax.set_xlim([-max_range, max_range])
    ax.set_ylim([-max_range, max_range])
    ax.set_zlim([0, max_range*1.8])
    
    # Set viewing angle for better human visualization (fixed angle, no rotation)
    # Use front view with proper elevation to see standing human
    ax.view_init(elev=20, azim=45)  # Front-angled view to show standing human properly
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    # Set background
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('gray')
    ax.yaxis.pane.set_edgecolor('gray')
    ax.zaxis.pane.set_edgecolor('gray')
    ax.xaxis.pane.set_alpha(0.1)
    ax.yaxis.pane.set_alpha(0.1)
    ax.zaxis.pane.set_alpha(0.1)

def create_video_frames(motion_frames, output_dir, visualization_type='mesh_skeleton',
                       image_size=(1280, 720), dpi=100, use_gpu=False):
    """Create video frames from motion data with human-like visualization and GPU acceleration"""
    os.makedirs(output_dir, exist_ok=True)
    print(f"Creating video frames in: {output_dir}")
    
    if use_gpu and GPU_AVAILABLE:
        print(f"Using GPU acceleration for data processing")
    else:
        print(f"Using CPU for data processing")
    
    # Load SMPL faces for mesh rendering
    smpl_faces = load_smpl_faces()
    use_face_rendering = smpl_faces is not None
    
    if use_face_rendering:
        print(f"SMPL faces loaded successfully - will render solid 3D mesh")
    else:
        print(f"SMPL faces not available - will use point cloud visualization")
    
    total_frames = len(motion_frames)
    print(f"Total frames to process: {total_frames}")
    
    for i, frame_info in enumerate(motion_frames):
        # Create figure with high quality for better human visualization
        fig = plt.figure(figsize=(image_size[0]/dpi, image_size[1]/dpi), dpi=dpi)
        ax = fig.add_subplot(111, projection='3d')
        
        frame_idx = frame_info['frame_idx']
        
        # Process each person in the frame
        for person_idx, person_info in enumerate(frame_info['persons']):
            person_id = person_info['person_id']
            
            # Plot mesh if available
            if 'vertices' in person_info:
                vertices = person_info['vertices']
                if vertices is not None and len(vertices) > 0:
                    # Apply coordinate transformation to fix orientation
                    # Exchange y,z-axis, and then reverse the direction of x,z-axis
                    vertices = vertices[:, [0, 2, 1]]  # swap y and z
                    vertices[:, 0] = -vertices[:, 0]   # reverse x
                    vertices[:, 2] = -vertices[:, 2]   # reverse z
                    
                    if visualization_type in ['mesh', 'mesh_skeleton', 'solid_mesh']:
                        # For solid_mesh, force face rendering; for others, use available method
                        force_faces = visualization_type == 'solid_mesh'
                        if force_faces:
                            # For solid_mesh, always use face rendering if available
                            mesh_rendered = plot_3d_human_mesh(ax, vertices, faces=smpl_faces, 
                                                              alpha=0.8, use_faces=use_face_rendering)
                            if mesh_rendered:
                                print(f"Frame {frame_idx+1}: Rendered with solid mesh faces")
                            else:
                                print(f"Frame {frame_idx+1}: Face rendering failed, using point cloud")
                        else:
                            # For other modes, use available method
                            mesh_rendered = plot_3d_human_mesh(ax, vertices, faces=smpl_faces, 
                                                              alpha=0.7, use_faces=use_face_rendering)
                    
                    if visualization_type in ['skeleton', 'mesh_skeleton']:
                        # Extract and plot skeleton with GPU acceleration
                        # Use original vertices for joint extraction, then transform joints
                        original_vertices = person_info['vertices']
                        joints = extract_key_joints_from_mesh(original_vertices, use_gpu=use_gpu)
                        if joints is not None:
                            # Apply same coordinate transformation to joints
                            joints = joints[:, [0, 2, 1]]  # swap y and z
                            joints[:, 0] = -joints[:, 0]   # reverse x
                            joints[:, 2] = -joints[:, 2]   # reverse z
                            plot_3d_skeleton(ax, joints, color='red', linewidth=3)
        
        # Setup plot (no frame_idx to avoid rotation)
        setup_3d_plot(ax, "PMCE 3D Human Motion", None, total_frames)
        
        # Add frame information
        gpu_status = "GPU" if use_gpu and GPU_AVAILABLE else "CPU"
        fig.suptitle(f"3D Human Body Reconstruction ({gpu_status})\nFrame {frame_idx+1} / {total_frames}", 
                    fontsize=14, fontweight='bold')
        
        # Save frame
        output_path = os.path.join(output_dir, f"frame_{i:06d}.png")
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        # Progress update
        if (i + 1) % 10 == 0 or i == total_frames - 1:
            print(f"Processed {i + 1}/{total_frames} frames ({(i+1)/total_frames*100:.1f}%)")
    
    print(f"All frames saved to: {output_dir}")
    return total_frames

def create_video_from_frames(frames_dir, output_video, fps=24, quality='high'):
    """Create video from frame images using ffmpeg"""
    frame_pattern = os.path.join(frames_dir, "frame_%06d.png")
    
    # Quality settings for human motion
    if quality == 'high':
        codec_settings = ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    elif quality == 'medium':
        codec_settings = ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
    else:  # low
        codec_settings = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28"]
    
    # FFmpeg command optimized for human motion
    cmd = [
        "ffmpeg", "-y",  # -y to overwrite output file
        "-framerate", str(fps),  # input framerate
        "-i", frame_pattern,  # input pattern
        "-vf", "scale=1920:1080",  # scale to HD resolution
    ] + codec_settings + [
        "-pix_fmt", "yuv420p",  # pixel format for compatibility
        "-movflags", "+faststart",  # optimize for web playback
        output_video
    ]
    
    print(f"Creating video with command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print(f"Video created successfully: {output_video}")
            return True
        else:
            print(f"FFmpeg failed with error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error running FFmpeg: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Create 3D Human Video from PMCE Results")
    parser.add_argument("--pkl_file", 
                       default="output/demo_output/sample_video/pmce_output.pkl",
                       help="Path to PMCE output PKL file")
    parser.add_argument("--output_dir", 
                       default="3d_human_frames",
                       help="Output directory for video frames")
    parser.add_argument("--output_video", 
                       default="pmce_3d_human_motion.mp4",
                       help="Output video file name")
    parser.add_argument("--fps", type=int, default=30, 
                       help="Video frame rate (default: 30)")
    parser.add_argument("--quality", choices=['low', 'medium', 'high'], 
                       default='high', help="Video quality")
    parser.add_argument("--visualization", choices=['mesh', 'skeleton', 'mesh_skeleton', 'solid_mesh'], 
                       default='solid_mesh', help="Visualization type (solid_mesh for face-based rendering)")
    parser.add_argument("--image_size", nargs=2, type=int, default=[1920, 1080],
                       help="Frame image size (width height)")
    parser.add_argument("--dpi", type=int, default=100,
                       help="Image DPI for frame generation")
    parser.add_argument("--use_gpu", action='store_true',
                       help="Use GPU acceleration for data processing (requires PyTorch with CUDA)")
    
    args = parser.parse_args()
    
    # Check if PKL file exists
    if not os.path.exists(args.pkl_file):
        print(f"Error: PKL file not found: {args.pkl_file}")
        print("Please run PMCE demo first to generate the PKL file.")
        return
    
    # Check GPU availability if requested
    if args.use_gpu:
        if not GPU_AVAILABLE:
            print("GPU requested but not available. Please install PyTorch with CUDA support.")
            print("Falling back to CPU mode...")
            args.use_gpu = False
        else:
            print(f"GPU acceleration enabled: {torch.cuda.get_device_name(0)}")
    
    print("Starting 3D Human Video Generation")
    print(f"Input PKL: {args.pkl_file}")
    print(f"Output frames: {args.output_dir}")
    print(f"Output video: {args.output_video}")
    print(f"Visualization: {args.visualization}")
    print(f"Processing mode: {'GPU' if args.use_gpu and GPU_AVAILABLE else 'CPU'}")
    
    # Load PMCE results
    print("\nLoading PMCE results...")
    data = load_pmce_results(args.pkl_file)
    if data is None:
        return
    
    # Extract motion data
    print("\nExtracting motion data...")
    motion_frames = extract_motion_data_from_pmce(data)
    if not motion_frames:
        print("No motion data found in PKL file.")
        return
    
    print(f"Found {len(motion_frames)} frames with motion data")
    
    # Create video frames
    print("\nCreating human video frames...")
    total_frames = create_video_frames(
        motion_frames, 
        args.output_dir,
        visualization_type=args.visualization,
        image_size=tuple(args.image_size),
        dpi=args.dpi,
        use_gpu=args.use_gpu
    )
    
    # Create video from frames
    print("\nCreating video...")
    success = create_video_from_frames(
        args.output_dir,
        args.output_video,
        fps=args.fps,
        quality=args.quality
    )
    
    if success:
        # Get video file size
        if os.path.exists(args.output_video):
            size_mb = os.path.getsize(args.output_video) / (1024 * 1024)
            processing_mode = "GPU" if args.use_gpu and GPU_AVAILABLE else "CPU"
            print(f"\n3D Human Video generation complete!")
            print(f"Video file: {args.output_video} ({size_mb:.1f} MB)")
            print(f"Frames: {total_frames}, FPS: {args.fps}, Quality: {args.quality}")
            print(f"Visualization: {args.visualization}")
            print(f"Processing mode: {processing_mode}")
            print(f"\nThe video now shows realistic 3D human body with mesh and skeleton!")
            if args.use_gpu and GPU_AVAILABLE:
                print(f"GPU acceleration was used for faster data processing!")
        else:
            print("\nVideo file not found after creation.")
    else:
        print("\nVideo creation failed, but frames are available.")
        print(f"Frames directory: {args.output_dir}")

if __name__ == "__main__":
    main()