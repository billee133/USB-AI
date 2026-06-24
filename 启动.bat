@echo off
title USB-AI
cd /d "%~dp0"

echo ============================================
echo   便携2026 AI 系统 - DeepSeek
echo ============================================
echo.
echo 启动方式说明:
echo.
echo   方式1 [当前] - 浏览器直连模式
echo     双击 index.html 即可使用核心对话
echo     适合: 任何有浏览器的电脑
echo.
echo   方式2 [推荐] - 服务器代理模式
echo     双击 启动服务器模式.bat
echo     自动选择 PowerShell / Python / 便携Python
echo     支持完整功能: 联网搜索, 无CORS限制
echo.
echo ============================================

start "" "%~dp0index.html"

echo.
echo 系统已启动!
echo 如搜索功能异常, 请使用 启动服务器模式.bat
echo.
pause
