@echo off
title USB-AI - 运行环境部署
cd /d "%~dp0"

echo ============================================
echo   USB-AI - 运行环境部署
echo ============================================
echo.
echo   在您的主电脑上运行此脚本，预下载
echo   运行环境到U盘。之后拿到任何电脑
echo   上都可以零依赖启动服务器模式。
echo.
echo ============================================

set RUNTIME_DIR=%~dp0runtime

REM Check existing
echo [检测] 扫描当前电脑环境...
echo.

powershell -Command "exit $PSVersionTable.PSVersion.Major" >nul 2>&1
if errorlevel 1 (
    echo   [OK] PowerShell 已内置 (Win10+ 目标电脑无需部署)
) else (
    echo   [--] PowerShell 不可用 (目标电脑需 Python)
)

python --version >nul 2>&1
if not errorlevel 1 (
    echo   [OK] 系统 Python 已安装
)

if exist "%RUNTIME_DIR%\python\python.exe" (
    echo   [OK] 便携 Python 已部署在 runtime\python\
    echo.
    echo 运行环境已就绪! 可直接使用。
    goto :done
)

echo.
echo --------------------------------------------
echo   选择部署方式:
echo.
echo   1. 在线下载 (推荐)
echo      Python 3.12 嵌入式版 (~8MB)
echo      从 python.org 直接下载
echo.
echo   2. 手动部署
echo      自行下载 python-embed-amd64.zip
echo      放入 runtime\ 目录并解压到 python\
echo.
echo   3. 跳过 (仅使用浏览器直连模式)
echo --------------------------------------------
echo.

set /p CHOICE="请输入选项 [1/2/3]: "

if "%CHOICE%"=="1" goto :download
if "%CHOICE%"=="2" goto :manual
if "%CHOICE%"=="3" goto :skip
goto :done

:download
echo.
echo [下载] 正在从 python.org 下载 Python 3.12 嵌入式版...
echo.

set PYTHON_VERSION=3.12.8
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip
set DOWNLOAD_FILE=%RUNTIME_DIR%\python-embed-amd64.zip

echo   下载地址: %PYTHON_URL%
echo   保存位置: %DOWNLOAD_FILE%
echo.

powershell -Command "& { try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%DOWNLOAD_FILE%' -UseBasicParsing; Write-Host '下载完成!'; exit 0 } catch { Write-Host \"下载失败: $_\"; exit 1 } }"

if not exist "%DOWNLOAD_FILE%" (
    echo.
    echo [失败] 自动下载失败，请尝试手动部署。
    goto :manual
)

echo.
echo [解压] 正在解压 Python 嵌入式版...
powershell -Command "Expand-Archive -Force '%DOWNLOAD_FILE%' '%RUNTIME_DIR%\python'" >nul 2>&1

if not exist "%RUNTIME_DIR%\python\python.exe" (
    echo 备用解压方式...
    powershell -Command "& { $shell = New-Object -ComObject Shell.Application; $zip = $shell.NameSpace('%DOWNLOAD_FILE%'); $dest = $shell.NameSpace('%RUNTIME_DIR%\python'); $dest.CopyHere($zip.Items(), 16) }" >nul 2>&1
)

if exist "%RUNTIME_DIR%\python\python.exe" (
    echo   [OK] 解压完成
) else (
    echo   [X] 解压失败，请手动解压 %DOWNLOAD_FILE% 到 runtime\python\
    goto :manual
)

del "%DOWNLOAD_FILE%" >nul 2>&1

REM Configure embeddable Python
(
    echo python312.zip
    echo .
    echo import site
) > "%RUNTIME_DIR%\python\python312._pth"

echo [测试] 验证便携 Python...
"%RUNTIME_DIR%\python\python.exe" --version >nul 2>&1
if not errorlevel 1 (
    echo   [OK] 便携 Python 部署成功!
) else (
    echo   [X] 便携 Python 验证失败
    goto :manual
)

goto :done

:manual
echo.
echo --------------------------------------------
echo   手动部署说明:
echo.
echo   1. 浏览器访问:
echo      https://www.python.org/downloads/windows/
echo      下载 Windows embeddable package (64-bit)
echo.
echo   2. 将下载的 zip 放入 runtime\ 目录
echo.
echo   3. 解压到 runtime\python\
echo      确认存在: runtime\python\python.exe
echo --------------------------------------------
echo.
pause
exit /b 0

:skip
echo 已跳过。系统将以浏览器直连模式运行。
pause
exit /b 0

:done
echo.
echo ============================================
echo   [OK] 运行环境部署完成!
echo.
echo   现在可以将U盘插到任何Windows电脑:
echo   1. 双击 启动服务器模式.bat
echo      - 自动使用便携 Python 启动服务器
echo   2. 或双击 启动.bat
echo      - 浏览器直连模式
echo.
echo   便携 Python: runtime\python\python.exe
echo ============================================
echo.
pause
