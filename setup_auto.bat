@echo off
title USB-AI — 安装自动化依赖
cd /d "%~dp0"

echo ============================================
echo   USB-AI — 桌面自动化依赖安装
echo ============================================
echo.
echo 此脚本安装以下 Python 包:
echo   - pyautogui  (鼠标/键盘控制)
echo   - pillow     (截图处理)
echo.
echo 如果您只需要文件操作和 AI 对话功能，
echo 可以跳过此安装。
echo.
set /p CONFIRM="是否继续安装? [Y/n]: "
if /i "%CONFIRM%"=="n" goto :skip

REM Use portable Python if available, fallback to system Python
set PY=%~dp0runtime\python-win\python.exe
if not exist "%PY%" set PY=python

echo.
echo [安装] pyautogui + pillow...

REM 优先本地 whl 包
set WHEEL_DIR=%~dp0runtime\auto-deps
if exist "%WHEEL_DIR%\*.whl" (
    echo [检测] 发现本地 whl 包，离线安装...
    "%PY%" -m pip install "%WHEEL_DIR%\*.whl" --quiet --no-index
) else (
    "%PY%" -m pip install pyautogui pillow --quiet
)

if not errorlevel 1 (
    echo [OK] 安装成功！
    echo      在 USB-AI 设置中开启"桌面自动化"即可使用
) else (
    echo [错误] 安装失败，请检查 Python 是否可用
    echo        或手动执行: pip install pyautogui pillow
    echo        也可将 whl 文件放入 runtime\auto-deps\ 离线安装
)
goto :done

:skip
echo 已跳过安装。
:done
echo.
pause
