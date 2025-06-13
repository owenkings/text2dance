请使用pyqt设计一个软件，高内聚低耦合， 结构清晰，便于维护，支持扩展式的插件，具备如下功能：

1. 配置层：包含所有的配置，代理配置，爬虫配置，算法配置，界面配置，插件配置等

2. 爬虫层：爬取bilibili、youtube、抖音等视频网站的数据，支持关键字定制，自动化下载视频（参考 https://github.com/iawia002/lux 与 https://github.com/ytdl-org/youtube-dl ）

3. 视频处理层：可以用于编辑，支持视频预览，轨道，剪切，压缩，拼接，调速等编辑操作，可参考 https://github.com/Zulko/moviepy

4. 视频算法层，包括：

4.1 视频2D骨骼生成：实现视频到2D的姿态转换，包括2D骨骼显示、视频显示、2D骨骼算法（支持加载不同算法，可内置算法，包括OpenPose https://github.com/CMU-Perceptual-Computing-Lab/openpose ，VitPose https://github.com/ViTAE-Transformer/ViTPose ，rtmpose https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose ，justdance https://github.com/open-mmlab/mmpose/tree/main/projects/just_dance , poseanything https://github.com/open-mmlab/mmpose/tree/main/projects/pose_anything ， rtmo https://github.com/open-mmlab/mmpose/tree/main/projects/pose_anything ，yoloxpose https://github.com/open-mmlab/mmpose/tree/main/projects/yolox_pose ）

4.2 视频3D骨骼生成层：实现视频到3D的姿态转换，包括3D骨骼显示、视频显示、3D骨骼生成算法（支持加载不同算法，内置算法包括：rtmpose3d https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose3d , video2pose3d https://github.com/zh-plus/video-to-pose3D , videopose3D https://github.com/facebookresearch/VideoPose3D , rtmpose3d https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose3d , FinePose https://github.com/PKU-ICST-MIPL/FinePOSE_CVPR2024 , AdaptPose https://github.com/mgholamikn/AdaptPose )

4.3 视频描述层：实现由视频到文本的转换，包括：视频预览，文本描述，视频到文本描述算法（支持加载不同算法，内置算法包括：describeanything https://github.com/NVlabs/describe-anything ， Vid2Seq https://github.com/google-research/scenic/tree/main/scenic/projects/vid2seq )

5. 界面层：涉及到上述所有的界面，优雅、简洁

6. 插件层： 可支持自定义插件开发，用于扩展。