@echo off
title USB-AI — 本地模型安装
cd /d "%~dp0"

echo ============================================
echo   USB-AI — llama-cpp-python 本地推理安装
echo ============================================
echo.
echo 此脚本安装以下内容：
echo   1. llama-cpp-python（~20MB，CPU推理用）
echo   2. 小模型 Qwen2.5-0.5B-Instruct（~400MB GGUF）
echo.
echo 安装后重启 USB-AI 即可在模型下拉框选择本地模型。
echo.
echo 【卸载方法】
echo   pip uninstall llama-cpp-python -y
echo   手动删除 runtime\models\ 下的 .gguf 文件
echo.
set /p CONFIRM="是否继续? [Y/n]: "
if /i "%CONFIRM%"=="n" goto :skip

echo.
echo [1/3] 安装 llama-cpp-python...
pip install llama-cpp-python --quiet
if errorlevel 1 (
    echo [失败] pip install 失败。
    echo 请确保 Python 已安装并添加到 PATH。
    pause
    exit /b 1
)
echo [OK] llama-cpp-python 安装成功

echo.
echo [2/3] 创建 runtime\models\ 目录...
if not exist "runtime\models" mkdir runtime\models
echo [OK]

echo.
echo [3/3] 下载 Qwen2.5-0.5B-Instruct Q4_K_M GGUF（~400MB）...
set MODEL_URL=https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
set MODEL_FILE=runtime\models\qwen2.5-0.5b-instruct-q4_k_m.gguf

if exist "%MODEL_FILE%" (
    echo [跳过] 模型文件已存在
) else (
    echo 下载中，请耐心等待...
    curl -L -o "%MODEL_FILE%" "%MODEL_URL%" --progress-bar
    if errorlevel 1 (
        echo [失败] 下载失败，请手动下载:
        echo   %MODEL_URL%
        echo   保存到: %MODEL_FILE%
        pause
        exit /b 1
    )
    echo [OK] 模型下载完成
)

echo.
echo ============================================
echo   安装完成！
echo ============================================
echo.
echo 现在重启 USB-AI 服务器后，在设置中选择:
echo   "qwen2.5-0.5b-instruct-q4_k_m.gguf" (本地)
echo.
echo 或运行 python -c "import llama_cpp; print('OK')" 验证安装
echo.
pause
goto :done

:skip
echo 已跳过安装。
:done
echo.