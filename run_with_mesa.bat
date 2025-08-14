@echo off
echo 设置Mesa3D环境变量...
set PYOPENGL_PLATFORM=win32
set PYRENDER_PLATFORM=pyglet
set MESA_GL_VERSION_OVERRIDE=3.3
set MESA_GLSL_VERSION_OVERRIDE=330
set LIBGL_ALWAYS_SOFTWARE=1
set GALLIUM_DRIVER=llvmpipe

echo 运行FBX生成程序...
python src\algorithms\pose3d\main\run_demo_fbx.py --vid_file data/sample_video.mp4 --gpu 0 --save_fbx --skeleton_only

echo 程序执行完成！
pause
