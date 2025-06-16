@echo off
chcp 65001 >nul
echo ================================================
echo           视频编辑工具启动器
echo ================================================
echo.

echo 正在检查Python环境...
python --version
if errorlevel 1 (
    echo Python未安装或未添加到PATH
    echo 请先安装Python 3.7+
    pause
    exit /b 1
)

echo.
echo 选择操作:
echo 1. 启动程序
echo 2. 安装/修复依赖
echo 3. 检查依赖状态
set /p action=请选择 (1/2/3): 

if "%action%"=="2" goto install_deps
if "%action%"=="3" goto check_deps

:start_program
echo.
echo 正在启动程序...
python start.py

if errorlevel 1 (
    echo.
    echo 启动失败，可能是依赖问题
    echo 是否要安装依赖? (y/n)
    set /p install_choice=
    if /i "%install_choice%"=="y" goto install_deps
    
    echo 尝试直接运行主程序...
    python main.py
)
goto end

:install_deps
echo.
echo 正在安装依赖...
python install_dependencies.py
goto end

:check_deps
echo.
echo 检查依赖状态...
python -c "import numpy, cv2, PyQt5; import moviepy.editor; print('所有关键依赖已安装')"
if errorlevel 1 (
    echo 依赖检查失败，建议运行依赖安装
)
goto end

:end
echo.
echo 程序已退出
pause