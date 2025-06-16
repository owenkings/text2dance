@echo off
echo NumPy兼容性修复工具
echo ========================
echo.

echo 检查当前NumPy版本...
python -c "import numpy; print('NumPy版本:', numpy.__version__)"

echo.
echo 选择修复方案:
echo 1. 降级到NumPy 1.x (推荐，稳定)
echo 2. 升级到最新版本 (实验性)
set /p choice=请选择 (1/2): 

if "%choice%"=="2" goto upgrade

:downgrade
echo.
echo 降级NumPy到兼容版本...
pip install "numpy<2.0" --force-reinstall --no-deps

echo.
echo 重新安装相关包...
pip install opencv-python==4.8.1.78 --force-reinstall
pip install scipy==1.11.3 --force-reinstall
pip install matplotlib==3.7.2 --force-reinstall
goto test

:upgrade
echo.
echo 升级到支持NumPy 2.0的最新版本...
echo 注意: 这是实验性方案，可能不稳定
echo.
echo 升级OpenCV到最新版本...
pip install "opencv-python>=4.10.0.84" --upgrade

echo.
echo 确保NumPy 2.0...
pip install "numpy>=2.0" --upgrade

echo.
echo 升级其他相关包...
pip install scipy --upgrade
pip install matplotlib --upgrade
pip install moviepy --upgrade

:test
echo.
echo 测试导入...
python -c "import numpy; import cv2; import PyQt5; print('所有模块导入成功!')"

echo.
echo 修复完成！
pause