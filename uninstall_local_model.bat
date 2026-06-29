@echo off
title USB-AI — 本地模型卸载
cd /d "%~dp0"

echo ============================================
echo   USB-AI — llama-cpp-python 卸载
echo ============================================
echo.
echo 此脚本:
echo   1. 卸载 llama-cpp-python（无残留，项目零影响）
echo   2. 自动回退到 Ollama 本地 / DeepSeek API
echo.
set /p CONFIRM="确认卸载? [y/N]: "
if /i not "%CONFIRM%"=="y" goto :skip

echo.
echo [1/2] 卸载 llama-cpp-python...
pip uninstall llama-cpp-python -y
if errorlevel 1 (
    echo [警告] 卸载失败，尝试忽略
) else (
    echo [OK] 已卸载
)

echo.
echo [2/2] 验证...
python -c "import llama_cpp" 2>nul
if errorlevel 1 (
    echo [OK] llama-cpp-python 已移除，无残留
) else (
    echo [注意] 仍有残留，请手动检查: pip list ^| findstr llama
)

echo.
echo ============================================
echo   卸载完成
echo ============================================
echo.
echo 模型文件仍在 runtime\models\ 中（可手动删除）
echo USB-AI 将自动使用 Ollama 或 DeepSeek API
echo.
pause
goto :done

:skip
echo 已取消。
:done
echo.