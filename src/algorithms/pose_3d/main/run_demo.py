import os
# 注释掉OpenGL相关环境变量，使用稳定3D渲染器
# os.environ['PYOPENGL_PLATFORM'] = 'osmesa'
# os.environ['MESA_GL_VERSION_OVERRIDE'] = '3.3'
# os.environ['MESA_GLSL_VERSION_OVERRIDE'] = '330'

import sys
import os.path as osp
import __init_path
import json
# 导入matplotlib用于3D渲染
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import cv2
import torch
import joblib
import shutil
import colorsys
import argparse
import random
import warnings
import numpy as np
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from tqdm import tqdm
from multi_person_tracker import MPT
from torch.utils.data import DataLoader
from scipy.optimize import minimize

import models
from core.config import cfg
from aug_utils import j2d_processing
from coord_utils import get_bbox, process_bbox
from funcs_utils import load_checkpoint, save_obj

# 导入稳定3D渲染相关模块
try:
    # 尝试导入SMPL面数据
    from smpl import SMPL_FACES
    print("成功导入SMPL面数据")
except ImportError:
    try:
        # 从文件加载
        import pickle
        faces_path = os.path.join(os.path.dirname(__file__), '../data/smpl_faces.pkl')
        with open(faces_path, 'rb') as f:
            SMPL_FACES = pickle.load(f)
        print("从文件加载SMPL面数据")
    except:
        # 动态生成基本面数据
        print("警告: 无法加载SMPL面数据，使用简化面结构")
        SMPL_FACES = np.array([[i, i+1, i+2] for i in range(0, 6887, 3)])

# SMPL关节回归器简化版本
SMPL_JOINT_REGRESSOR_SIMPLIFIED = {
    0: "骨盆", 1: "左髋", 2: "右髋", 4: "左膝", 5: "右膝", 7: "左踝", 8: "右踝",
    12: "颈部", 15: "头部", 16: "左肩", 17: "右肩", 18: "左肘", 19: "右肘", 20: "左腕", 21: "右腕"
}

# 稳定3D渲染函数
def render_stable_3d_overlay(img, verts, cam, color=(1.0, 1.0, 0.9)):
    """使用稳定的3D渲染方法在图像上叠加人体网格"""
    try:
        # 使用完整的稳定3D渲染
        joints_3d = extract_key_joints_from_vertices(verts)
        rendered_img = render_stable_3d_model_overlay(img, verts, joints_3d, cam, color)
        return rendered_img
    except Exception as e:
        print(f"稳定3D渲染失败: {e}，返回原始图像")
        return img

def extract_key_joints_from_vertices(vertices):
    """从SMPL顶点中提取关键关节点"""
    # 简化的关节提取，选择代表性顶点作为关节
    key_vertex_indices = [0, 1000, 2000, 3000, 4000, 5000, 6000, 500, 1500, 2500, 3500, 4500, 5500, 6500, 100]
    joints_3d = []
    
    for idx in key_vertex_indices:
        if idx < len(vertices):
            joints_3d.append(vertices[idx])
        else:
            # 如果索引超出范围，使用最后一个顶点
            joints_3d.append(vertices[-1])
    
    return np.array(joints_3d)

def plot_3d_human_mesh_with_faces(ax, vertices, color='#A1B0DC'):
    """绘制带面片的3D人体网格"""
    try:
        # 使用三角剖分渲染面片
        ax.plot_trisurf(vertices[:, 0], vertices[:, 1], vertices[:, 2], 
                       triangles=SMPL_FACES, color=color, alpha=0.8, shade=True)
    except Exception as e:
        # 如果面片渲染失败，使用点云渲染
        ax.scatter(vertices[:, 0], vertices[:, 1], vertices[:, 2], 
                  c=color, s=1, alpha=0.6)

def get_joint_color_mapping():
    """获取关节颜色映射"""
    return {
        0: {'rgb': [255, 0, 0], 'bgr': [0, 0, 255]},      # 骨盆 - 红色
        1: {'rgb': [0, 255, 0], 'bgr': [0, 255, 0]},      # 左髋 - 绿色
        2: {'rgb': [0, 0, 255], 'bgr': [255, 0, 0]},      # 右髋 - 蓝色
        4: {'rgb': [255, 255, 0], 'bgr': [0, 255, 255]},  # 左膝 - 黄色
        5: {'rgb': [255, 0, 255], 'bgr': [255, 0, 255]},  # 右膝 - 洋红
        7: {'rgb': [0, 255, 255], 'bgr': [255, 255, 0]},  # 左踝 - 青色
        8: {'rgb': [128, 0, 128], 'bgr': [128, 0, 128]},  # 右踝 - 紫色
        12: {'rgb': [255, 165, 0], 'bgr': [0, 165, 255]}, # 颈部 - 橙色
        15: {'rgb': [255, 192, 203], 'bgr': [203, 192, 255]}, # 头部 - 粉色
        16: {'rgb': [0, 128, 0], 'bgr': [0, 128, 0]},     # 左肩 - 深绿
        17: {'rgb': [0, 0, 128], 'bgr': [128, 0, 0]},     # 右肩 - 深蓝
        18: {'rgb': [128, 128, 0], 'bgr': [0, 128, 128]}, # 左肘 - 橄榄
        19: {'rgb': [128, 0, 0], 'bgr': [0, 0, 128]},     # 右肘 - 栗色
        20: {'rgb': [0, 128, 128], 'bgr': [128, 128, 0]}, # 左腕 - 蓝绿
        21: {'rgb': [64, 64, 64], 'bgr': [64, 64, 64]},   # 右腕 - 灰色
    }

def render_stable_3d_model_overlay(img, vertices, joints_3d, cam, color=(1.0, 1.0, 0.9)):
    """渲染稳定的3D模型覆盖层到图像上"""
    height, width = img.shape[:2]
    
    # 创建matplotlib图形
    fig = plt.figure(figsize=(width/100, height/100), dpi=100, facecolor='black')
    ax = fig.add_subplot(111, projection='3d')
    
    # 应用相机变换
    if len(cam) >= 3:
        scale = cam[0]
        tx, ty = cam[1], cam[2]
        tz = 5.0  # 固定Z距离
        
        # 应用变换
        vertices_transformed = vertices * scale + np.array([tx, ty, tz])
        joints_transformed = joints_3d * scale + np.array([tx, ty, tz])
    else:
        vertices_transformed = vertices.copy()
        joints_transformed = joints_3d.copy()
    
    # 坐标系变换
    temp_vertices = vertices_transformed.copy()
    temp_vertices[:, 0] = vertices_transformed[:, 0]
    temp_vertices[:, 1] = vertices_transformed[:, 2]
    temp_vertices[:, 2] = -vertices_transformed[:, 1]
    
    vertices_final = temp_vertices.copy()
    vertices_final[:, 0] = -temp_vertices[:, 1]
    vertices_final[:, 1] = temp_vertices[:, 0]
    vertices_final[:, 2] = temp_vertices[:, 2]
    
    # 对关节应用相同变换
    temp_joints = joints_transformed.copy()
    temp_joints[:, 0] = joints_transformed[:, 0]
    temp_joints[:, 1] = joints_transformed[:, 2]
    temp_joints[:, 2] = -joints_transformed[:, 1]
    
    joints_final = temp_joints.copy()
    joints_final[:, 0] = -temp_joints[:, 1]
    joints_final[:, 1] = temp_joints[:, 0]
    joints_final[:, 2] = temp_joints[:, 2]
    
    # 居中和缩放
    center = np.mean(vertices_final, axis=0)
    vertices_final -= center
    joints_final -= center
    
    # 缩放以适应视图
    scale_factor = 2.0
    vertices_final *= scale_factor
    joints_final *= scale_factor
    
    # Z轴偏移
    vertices_final[:, 2] += 1.5
    joints_final[:, 2] += 1.5
    
    # 渲染3D人体模型
    hex_color = '#A1B0DC'
    plot_3d_human_mesh_with_faces(ax, vertices_final, color=hex_color)
    
    # 获取颜色映射
    color_mapping = get_joint_color_mapping()
    
    # 渲染3D关节点
    for joint_idx in range(len(joints_final)):
        if joint_idx in SMPL_JOINT_REGRESSOR_SIMPLIFIED:
            if joint_idx in color_mapping:
                color_info = color_mapping[joint_idx]
                rgb_color = [c/255.0 for c in color_info['rgb']]
                marker = 'o'
                size = 150
            else:
                rgb_color = [0.5, 0.5, 0.5]
                marker = 's'
                size = 100
            
            x, y, z = joints_final[joint_idx]
            ax.scatter(x, y, z, c=[rgb_color], s=size, alpha=1.0, marker=marker, 
                      edgecolors='white', linewidth=2, zorder=30)
    
    # 连接关节
    joint_connections = [
        (0, 1), (0, 2), (1, 4), (2, 5), (4, 7), (5, 8),
        (0, 12), (12, 15), (12, 16), (12, 17),
        (16, 18), (17, 19), (18, 20), (19, 21)
    ]
    
    for connection in joint_connections:
        if (connection[0] < len(joints_final) and connection[1] < len(joints_final)):
            start_joint = joints_final[connection[0]]
            end_joint = joints_final[connection[1]]
            
            ax.plot([start_joint[0], end_joint[0]], 
                   [start_joint[1], end_joint[1]], 
                   [start_joint[2], end_joint[2]], 
                   color='white', linewidth=3, alpha=0.8, zorder=25)
    
    # 设置视图
    max_range = 2.0
    ax.set_xlim([-max_range, max_range])
    ax.set_ylim([-max_range, max_range])
    ax.set_zlim([0, max_range*1.8])
    ax.view_init(elev=25, azim=-10)
    
    # 设置黑色背景
    ax.set_facecolor('black')
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('none')
    ax.yaxis.pane.set_edgecolor('none')
    ax.zaxis.pane.set_edgecolor('none')
    ax.grid(False)
    ax.set_axis_off()
    
    # 渲染到内存
    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
    buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    
    # 转换为BGR格式
    model_3d = cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)
    
    # 调整大小以匹配原始图像
    if model_3d.shape[:2] != img.shape[:2]:
        model_3d = cv2.resize(model_3d, (img.shape[1], img.shape[0]))
    
    # 关闭图形以释放内存
    plt.close(fig)
    
    # 将3D模型叠加到原始图像上
    # 创建掩码，黑色区域不叠加
    mask = np.all(model_3d == [0, 0, 0], axis=2)
    result = img.copy()
    result[~mask] = cv2.addWeighted(img[~mask], 0.3, model_3d[~mask], 0.7, 0)
    
    return result

# 尝试导入渲染器，如果失败则使用稳定3D渲染方案
try:
    from simple_renderer import SimpleRenderer as Renderer
    print("使用简化渲染器 (SimpleRenderer)")
    USE_STABLE_RENDERER = False
except ImportError:
    try:
        from demo.simple_renderer import SimpleRenderer as Renderer
        print("使用简化渲染器 (demo.SimpleRenderer)")
        USE_STABLE_RENDERER = False
    except ImportError:
        print("警告: 无法导入标准渲染器，将使用稳定3D渲染方案")
        USE_STABLE_RENDERER = True
        
        # 定义稳定3D渲染器类
        class Renderer:
            def __init__(self, faces, resolution=(224,224), orig_img=False, wireframe=False):
                self.resolution = resolution
                self.faces = faces
                self.orig_img = orig_img
                self.wireframe = wireframe
                print("使用稳定3D渲染器 (Stable3DRenderer)")
            
            def render(self, img, verts, cam, angle=None, axis=None, mesh_filename=None, color=(1.0, 1.0, 0.9), rotate=False):
                # 使用稳定3D渲染方法
                return render_stable_3d_overlay(img, verts, cam, color)
from smpl import SMPL
import joblib
from pathlib import Path

from utils._dataset_demo import CropDataset, FeatureDataset
from utils.demo_utils import (
    download_youtube_clip,
    convert_crop_cam_to_orig_img,
    prepare_rendering_results,
    video_to_images,
    images_to_video,
)

# 导入二进制FBX生成器
# 移除了binary_fbx_generator导入



# 获取pose3d目录的绝对路径
POSE3D_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DATA_DIR = os.path.join(POSE3D_DIR, 'data/base_data')
MIN_NUM_FRAMES = 25
random.seed(1)
torch.manual_seed(1)
np.random.seed(1)


def convert_crop_cam_to_orig_img(cam, bbox, img_width, img_height):
    '''
    Convert predicted camera from cropped image coordinates
    to original image coordinates
    :param cam (ndarray, shape=(3,)): weak perspective camera in cropped img coordinates
    :param bbox (ndarray, shape=(4,)): bbox coordinates (c_x, c_y, h)
    :param img_width (int): original image width
    :param img_height (int): original image height
    :return:
    '''
    x, y, w, h = bbox[:,0], bbox[:,1], bbox[:,2], bbox[:, 3]
    cx, cy, h = x + w / 2., y + h / 2., h
    hw, hh = img_width / 2., img_height / 2.
    sx = cam[:,0] * (1. / (img_width / h))
    sy = cam[:,0] * (1. / (img_height / h))
    tx = ((cx - hw) / hw / sx) + cam[:,1]
    ty = ((cy - hh) / hh / sy) + cam[:,2]
    orig_cam = np.stack([sx, sy, tx, ty]).T
    return orig_cam


def render(verts, cam, bbox, orig_height, orig_width, orig_img, mesh_face, color, mesh_filename):
    pred_verts, pred_cam, bbox = verts, cam[None, :], bbox[None, :]

    orig_cam = convert_crop_cam_to_orig_img(
        cam=pred_cam,
        bbox=bbox,
        img_width=orig_width,
        img_height=orig_height
    )

    # Setup renderer for visualization
    renderer = Renderer(mesh_face, resolution=(orig_width, orig_height), orig_img=True, wireframe=False)
    renederd_img = renderer.render(
        orig_img,
        pred_verts,
        cam=orig_cam[0],
        color=color,
        mesh_filename=mesh_filename,
        rotate=False
    )

    return renederd_img


def get_joint_setting(mesh_model, joint_category='coco'):
    joint_regressor, joint_num, skeleton = None, None, None
    if joint_category == 'coco':
        joint_regressor = mesh_model.joint_regressor_coco
        joint_num = 19  # add pelvis and neck
        skeleton = (
            (1, 2), (0, 1), (0, 2), (2, 4), (1, 3), (6, 8), (8, 10), (5, 7), (7, 9), (12, 14), (14, 16), (11, 13),
            (13, 15),  # (5, 6), #(11, 12),
            (17, 11), (17, 12), (17, 18), (18, 5), (18, 6), (18, 0))
        flip_pairs = ((1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16))
        model_chk_path = os.path.join(POSE3D_DIR, 'experiment/pretrained/mesh_vis.pth.tar')

    else:
        raise NotImplementedError(f"{joint_category}: unknown joint set category")

    J_regressor = torch.Tensor(joint_regressor)
    model = models.PMCE.get_model(num_joint=joint_num, embed_dim=256, depth=3) 
    
    # 检查模型文件是否存在
    if not os.path.exists(model_chk_path):
        print(f"警告: 模型文件 {model_chk_path} 不存在，将使用随机初始化的模型")
        print("注意: 这将导致姿态估计结果不准确，仅用于测试目的")
        # 返回随机初始化的模型
        return model, joint_regressor, joint_num, skeleton, model_chk_path
    
    try:
        checkpoint = load_checkpoint(load_dir=model_chk_path)
        model.load_state_dict(checkpoint['model_state_dict'])
        print(f"成功加载模型: {model_chk_path}")
    except Exception as e:
        print(f"加载模型失败: {e}")
        print("将使用随机初始化的模型")

    return model, joint_regressor, joint_num, skeleton, model_chk_path

# 移除了create_simple_fbx_text函数

# 移除了create_bvh_file函数

# 移除了create_json_skeleton函数

def add_pelvis_and_neck(joint_coord):
    lhip_idx = 11 # joints_name.index('L_Hip')
    rhip_idx = 12 # joints_name.index('R_Hip')
    pelvis = (joint_coord[:, lhip_idx, :] + joint_coord[:, rhip_idx, :]) * 0.5
    pelvis = pelvis.reshape((joint_coord.shape[0], 1, -1))

    lshoulder_idx = 5 # joints_name.index('L_Shoulder')
    rshoulder_idx = 6 # joints_name.index('R_Shoulder')
    neck = (joint_coord[:, lshoulder_idx, :] + joint_coord[:, rshoulder_idx, :]) * 0.5
    neck = neck.reshape((joint_coord.shape[0], 1, -1))

    joint_coord = np.concatenate((joint_coord, pelvis, neck), axis=1)
    return joint_coord

def normalize_screen_coordinates(X, w, h):
    assert X.shape[-1] == 2
    return X / w * 2 - [1, h / w]

def optimize_cam_param(project_net, model, joint_input, proj_target_joint_img, img_features, bbox1, joint_regressor):
    joint_img = torch.Tensor(joint_input[None, :, :, :]).cuda()
    target_joint = torch.Tensor(proj_target_joint_img[None, :, :2]).cuda()
    img_feat = torch.Tensor(img_features).cuda()

    # get optimization settings for projection
    criterion = nn.L1Loss()
    optimizer = optim.Adam(project_net.parameters(), lr=0.1)

    # estimate mesh, pose
    model.eval()
    pred_mesh, _, __ = model(joint_img, img_feat)
    pred_3d_joint = torch.matmul(joint_regressor, pred_mesh)


    out = {}
    # assume batch=1
    project_net.train()
    for j in range(0, 300):
        # projection
        pred_2d_joint = project_net(pred_3d_joint.detach())

        loss = criterion(pred_2d_joint, target_joint[:, :17, :])
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if j == 100:
            for param_group in optimizer.param_groups:
                param_group['lr'] = 0.05
        if j == 200:
            for param_group in optimizer.param_groups:
                param_group['lr'] = 0.001

    out['mesh'] = pred_mesh[0].detach().cpu().numpy()
    out['cam_param'] = project_net.cam_param[0].detach().cpu().numpy()
    out['bbox'] = bbox1
    out['joints3d'] = pred_3d_joint[0].detach().cpu().numpy()  # 保存3D关节数据

    out['target'] = proj_target_joint_img

    return out


def main(args):
    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

    """ Prepare input video (images) """
    video_file = args.vid_file
    if video_file.startswith('https://www.youtube.com'):
        print(f"Donwloading YouTube video \'{video_file}\'")
        video_file = download_youtube_clip(video_file, '/tmp')
        if video_file is None:
            exit('Youtube url is not valid!')
        print(f"YouTube Video has been downloaded to {video_file}...")

    if not os.path.isfile(video_file):
        exit(f"Input video \'{video_file}\' does not exist!")

    # 检查环境变量中是否指定了输出目录
    if 'POSE_OUTPUT_DIR' in os.environ:
        output_path = os.environ['POSE_OUTPUT_DIR']
    else:
        output_path = osp.join('./output', os.path.basename(video_file).replace('.mp4', ''))
    Path(output_path).mkdir(parents=True, exist_ok=True)
    # image_folder, num_frames, img_shape = video_to_images(video_file, return_info=True, ffmpeg_path='E:/ffmpeg_install/ffmpeg-7.0.2-essentials_build/bin/ffmpeg.exe')
    image_folder, num_frames, img_shape = video_to_images(video_file, return_info=True)
    print(f"Input video number of frames {num_frames}\n")
    orig_height, orig_width = img_shape[:2]


    """ Run tracking """
    bbox_scale = 1.1    #
    # run multi object tracker
    mot = MPT(
        device=device,
        batch_size=args.tracker_batch_size,
        display=args.display,
        detector_type=args.detector,
        output_format='dict',
        yolo_img_size=args.yolo_img_size,
    )
    tracking_results = mot(image_folder)

    # Print tracking results before filtering
    print(f"Found {len(tracking_results)} person tracklets:")
    for person_id in tracking_results.keys():
        num_frames = tracking_results[person_id]['frames'].shape[0]
        print(f"  Person {person_id}: {num_frames} frames")
    
    # remove tracklets if num_frames is less than MIN_NUM_FRAMES
    original_count = len(tracking_results)
    for person_id in list(tracking_results.keys()):
        if tracking_results[person_id]['frames'].shape[0] < MIN_NUM_FRAMES:
            print(f"Removing person {person_id} (only {tracking_results[person_id]['frames'].shape[0]} frames, need {MIN_NUM_FRAMES})")
            del tracking_results[person_id]
    
    print(f"After filtering: {len(tracking_results)} person tracklets remaining (removed {original_count - len(tracking_results)})")
    
    if len(tracking_results) == 0:
        print(f"Warning: No tracklets with >= {MIN_NUM_FRAMES} frames found. Lowering threshold to 10 frames.")
        # Re-run tracking with lower threshold
        tracking_results = mot(image_folder)
        for person_id in list(tracking_results.keys()):
            if tracking_results[person_id]['frames'].shape[0] < 10:
                del tracking_results[person_id]
        print(f"With lower threshold: {len(tracking_results)} person tracklets found")
           
    """ Prepare ViTPose """ 
    from mmpose.apis import (inference_top_down_pose_model, init_pose_model, vis_pose_result)
    from mmpose.datasets import DatasetInfo
    pose_model = init_pose_model(
    args.pose_config, args.pose_checkpoint, device=device)

    dataset = pose_model.cfg.data['test']['type']
    dataset_info = pose_model.cfg.data['test'].get('dataset_info', None)
    if dataset_info is None:
        warnings.warn(
            'Please set `dataset_info` in the config.'
            'Check https://github.com/open-mmlab/mmpose/pull/663 for details.',
            DeprecationWarning)
    else:
        dataset_info = DatasetInfo(dataset_info)


    """ Get PMCE model """
    seq_len = 16
    virtual_crop_size = 500
    joint_set = args.joint_set
    mesh_model = SMPL()
    model, joint_regressor, joint_num, skeleton, ckt_name = get_joint_setting(mesh_model, joint_category=joint_set)
    joint_regressor = torch.Tensor(joint_regressor).to(device)
    
    model = model.to(device)
    model.eval()
    
    project_net = models.project_net.get_model(crop_size=virtual_crop_size).to(device)
    
    # Get feature_extractor
    from models.spin import hmr
    hmr = hmr().to(device)
    checkpoint = torch.load(osp.join(BASE_DATA_DIR, 'spin_model_checkpoint.pth.tar'))
    hmr.load_state_dict(checkpoint['model'], strict=False)
    hmr.eval()

    """ Run PMCE on each person """
    
    print("\nRunning PMCE on each person tracklet...")
    running_results = {}
    for person_id in tqdm(list(tracking_results.keys())):
        bboxes = joints2d = None
        bboxes = tracking_results[person_id]['bbox']
        frames = tracking_results[person_id]['frames']
        joint2ds = []
        
        for idx, frame_id in enumerate(frames):
            img_path = osp.join(image_folder, str(frame_id + 1).zfill(6) + '.jpg')
            persons = []
            person_info = {}
            person_info['bbox'] = bboxes[idx]
            person_info['bbox'][0] = person_info['bbox'][0] - person_info['bbox'][2] * 0.5
            person_info['bbox'][1] = person_info['bbox'][1] - person_info['bbox'][3] * 0.5
            persons.append(person_info)
            
            pose_results, _ = inference_top_down_pose_model(
                pose_model,
                img_path,
                persons,
                bbox_thr=None,
                format='xywh',
                dataset=dataset,
                dataset_info=dataset_info,
                return_heatmap=False,
                outputs=None)
            
            joint2ds.append(pose_results[0]['keypoints'])
            
        joints2d = joint2ds
            
        # Prepare static image features
        dataset = CropDataset(
            image_folder=image_folder,
            frames=frames,
            bboxes=bboxes,
            joints2d=joints2d,
            scale=bbox_scale,
        )

        bboxes = dataset.bboxes
        frames = dataset.frames
        joints2d = dataset.joints2d
        has_keypoints = True if joints2d is not None else False

        crop_dataloader = DataLoader(dataset, batch_size=256, num_workers=0)

        with torch.no_grad():
            feature_list = []
            norm_joints2d = []
            for i, batch in enumerate(crop_dataloader):
                if has_keypoints:
                    batch, nj2d = batch
                    nj2d = add_pelvis_and_neck(nj2d[:, :, :2])
                    nj2d = torch.Tensor(nj2d)
                    norm_joints2d.append(nj2d.reshape(-1, joint_num, 2))

                batch = batch.to(device)
                feature = hmr.feature_extractor(batch.reshape(-1,3,224,224))
                feature_list.append(feature.cpu())

            del batch
            
            feature_list = torch.cat(feature_list, dim=0)
            norm_joints2d = torch.cat(norm_joints2d, dim=0)

        # Encode temporal features and estimate 3D human mesh
        dataset = FeatureDataset(
            image_folder=image_folder,
            frames=frames,
            seq_len=seq_len,
        )
        dataset.feature_list = feature_list
        dataset.joint2d_list = norm_joints2d

        dataloader = DataLoader(dataset, batch_size=1, num_workers=0)     #32
        
        with torch.no_grad():
            pred_cam, pred_mesh, pred_bbox, pred_joints2d, pred_joints3d = [], [], [], [], []

            for i, batch in enumerate(dataloader):
                img_features, nj2d = batch

                nj2d = nj2d[0]
                bbox = get_bbox(nj2d[seq_len//2])
                bbox1 = process_bbox(bbox, aspect_ratio=1.0, scale=1.25)
                proj_target_joint_img, trans = j2d_processing(nj2d[seq_len//2].numpy(), (virtual_crop_size, virtual_crop_size), bbox1, 0, 0, None)
                norm_joint2d = normalize_screen_coordinates(nj2d.numpy(), orig_width, orig_height)
                
                with torch.enable_grad():
                    out = optimize_cam_param(project_net, model, norm_joint2d, proj_target_joint_img, img_features, bbox1, joint_regressor)
                    
                pred_mesh.append(out['mesh'])
                pred_cam.append(out['cam_param'])
                pred_bbox.append(out['bbox'])
                pred_joints2d.append(nj2d.numpy())  # 保存2D关键点数据
                pred_joints3d.append(out['joints3d'])  # 保存3D关节数据

            del batch

        # ========= Save results to a pickle file ========= #
        pred_mesh = np.array(pred_mesh)
        pred_cam = np.array(pred_cam)
        pred_bbox = np.array(pred_bbox)
        pred_joints2d = np.array(pred_joints2d)  # 转换为numpy数组
        pred_joints3d = np.array(pred_joints3d)  # 转换为numpy数组
        
        output_dict = {
            'pred_cam': pred_cam,
            'mesh': pred_mesh,
            'bboxes': pred_bbox,
            'frame_ids': frames,
            'joints2d': pred_joints2d,  # 添加2D关键点数据
            'joints3d': pred_joints3d,  # 添加3D关节数据
        }

        running_results[person_id] = output_dict

    del model

    if args.save_pkl:
        print(f"Saving output results to \'{os.path.join(output_path, 'pmce_output.pkl')}\'.") 
        joblib.dump(running_results, os.path.join(output_path, "pmce_output.pkl"))


    """ Render results as a single video """
    output_img_folder = f'{image_folder}_output'
    input_img_folder = f'{image_folder}_input'
    os.makedirs(output_img_folder, exist_ok=True)
    os.makedirs(input_img_folder, exist_ok=True)

    print(f"\nRendering output video, writing frames to {output_img_folder}")
    # prepare results for rendering
    frame_results = prepare_rendering_results(running_results, num_frames)
    color = (1.0, 0.6059142480254321, 0.5)

    image_file_names = sorted([
        os.path.join(image_folder, x)
        for x in os.listdir(image_folder)
        if x.endswith('.png') or x.endswith('.jpg')
    ])

    for frame_idx in tqdm(range(len(image_file_names))):
        img_fname = image_file_names[frame_idx]
        img = cv2.imread(img_fname)
        input_img = img.copy()
        if args.render_plain:
            img[:] = 0

        if args.sideview:
            side_img = np.zeros_like(img)

        # Check if frame_idx is within bounds of frame_results
        if frame_idx >= len(frame_results):
            print(f"Warning: frame_idx {frame_idx} exceeds frame_results length {len(frame_results)}, skipping frame")
            continue
            
        # Check if frame_results[frame_idx] is not None
        if frame_results[frame_idx] is None:
            print(f"Warning: frame_results[{frame_idx}] is None, skipping frame")
            continue

        for person_id, person_data in frame_results[frame_idx].items():
            frame_verts = person_data['verts']
            frame_cam = person_data['cam']
            frame_bbox = person_data['bbox']

            mesh_filename = None
            if args.save_obj:
                mesh_folder = os.path.join(output_path, 'meshes', f'{person_id:04d}')
                Path(mesh_folder).mkdir(parents=True, exist_ok=True)
                mesh_filename = os.path.join(mesh_folder, f'{frame_idx:06d}.obj')

            mc = color
            
            if not args.no_render:
                img = render(frame_verts, frame_cam, frame_bbox, orig_height, orig_width, img, mesh_model.face, mc, mesh_filename)
            else:
                print(f"Frame {frame_idx}: Pose estimation completed, rendering skipped")

            if args.sideview:
                if not args.no_render:
                    side_img = render(frame_verts, frame_cam, frame_bbox, orig_height, orig_width, 
                     side_img, mesh_model.face, color=mc, angle=270, axis=[0,1,0])
                else:
                    print(f"Frame {frame_idx}: Side view rendering skipped")

        if args.sideview:
            img = np.concatenate([img, side_img], axis=1)

        # save output frames
        cv2.imwrite(os.path.join(output_img_folder, f'{frame_idx:06d}.jpg'), img)
        cv2.imwrite(os.path.join(input_img_folder, f'{frame_idx:06d}.jpg'), input_img)

        if args.display:
            cv2.imshow('Video', img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    if args.display:
        cv2.destroyAllWindows()

    """ Save rendered video """
    vid_name = os.path.basename(video_file)
    save_name = f'pmce_{vid_name.replace(".mp4", "")}_output.mp4'
    save_path = os.path.join(output_path, save_name)

    images_to_video(img_folder=output_img_folder, output_vid_file=save_path)
    images_to_video(img_folder=input_img_folder, output_vid_file=os.path.join(output_path, vid_name))
    print(f"Saving result video to {os.path.abspath(save_path)}")
    shutil.rmtree(output_img_folder)
    shutil.rmtree(input_img_folder)
    shutil.rmtree(image_folder)    


if __name__ == '__main__':
    """
    python src/algorithms/pose3d/main/run_demo.py --vid_file "data/sample_video.mp4" --save_pkl --no_render --gpu 0
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('--vid_file', type=str, default='sample_video.mp4', help='input video path or youtube link')

    parser.add_argument('--detector', type=str, default='yolo', choices=['yolo', 'maskrcnn'],
                        help='object detector to be used for bbox tracking')
    
    parser.add_argument('--joint_set', type=str, default='coco', help='choose the topology of input 2D pose')

    parser.add_argument('--yolo_img_size', type=int, default=416,
                        help='input image size for yolo detector')

    parser.add_argument('--tracker_batch_size', type=int, default=12,
                        help='batch size of object detector used for bbox tracking')
    
    parser.add_argument('--pose_config', type=str, default=os.path.join(POSE3D_DIR, 'ViTPose/mmpose/.mim/configs/body/2d_kpt_sview_rgb_img/topdown_heatmap/coco/res50_coco_256x192.py'), help='Config file for pose')
    
    parser.add_argument('--pose_checkpoint', type=str, default='https://download.openmmlab.com/mmpose/top_down/resnet/res50_coco_256x192-ec54d7f3_20200709.pth', help='Checkpoint file for pose')

    parser.add_argument('--display', action='store_true',
                        help='visualize the results of each step during demo')

    parser.add_argument('--save_pkl', action='store_true',
                        help='save results to a pkl file')

    parser.add_argument('--save_obj', action='store_true',
                        help='save results as .obj files.')

    parser.add_argument('--gender', type=str, default='neutral',
                        help='set gender of people from (neutral, male, female)')

    parser.add_argument('--sideview', action='store_true',
                        help='render meshes from alternate viewpoint.')

    parser.add_argument('--render_plain', action='store_true',
                        help='render meshes on plain background')

    parser.add_argument('--gpu', type=int, default='0', help='gpu number')
    parser.add_argument('--no_render', action='store_true', help='skip rendering and only output pose estimation results')


    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu)

    main(args)