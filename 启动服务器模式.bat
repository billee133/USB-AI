@echo off

chcp 65001 >nul 2>&1

title AI Server

cd /d "%~dp0"



echo ============================================

rem (original: echo   USB-AI - ????????)
echo ============================================

echo.



set "FOUND="



REM Option 1: System Python

python --version >nul 2>&1

if not errorlevel 1 (

rem (original: echo [????1] ?? Python)
    python --version 2>&1

    set FOUND=py

    goto :launch

)



REM Option 2: Portable Python

if exist "runtime\python\python.exe" (

rem (original: echo [????2] ??? Python (U?????))
    set FOUND=portable

    goto :launch

)



REM Option 3: Auto-deploy portable Python (one-time, ~30MB)

echo.

echo ============================================

rem (original: echo   ???? Python???????????...)
rem (original: echo   ?????????????????? 1-2 ????)
echo ============================================

echo.

mkdir runtime 2>nul

rem (original: echo ????? python.org ???? Python ?????? (~8MB)...)
powershell -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip' -OutFile 'runtime\python-embed-amd64.zip' -UseBasicParsing" 2>nul

if not exist "runtime\python-embed-amd64.zip" (

rem (original: echo [X] ????????????????????)
rem (original: echo ????????? setup_runtime.bat)
    pause

    exit /b 1

)

rem (original: echo ??????...)
powershell -Command "Expand-Archive -Force 'runtime\python-embed-amd64.zip' 'runtime\python'" 2>nul

if exist "runtime\python\python.exe" (

    (echo python312.zip&& echo .&& echo import site) > "runtime\python\python312._pth"

    del "runtime\python-embed-amd64.zip" 2>nul

rem (original: echo [OK] ??? Python ???????!)
    set FOUND=portable

    goto :launch

)

rem (original: echo [X] ???????????????????? setup_runtime.bat)
pause

exit /b 1



:launch

echo.

echo ============================================

rem (original: echo   ??????????...)
rem (original: echo   ??????????? http://localhost:8082)
rem (original: echo   ?? Ctrl+C ????????)
echo ============================================

echo.



REM Delayed browser launch (wait for server to start)

start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8082"



REM Start server in foreground

if "%FOUND%"=="py" (

    python server.py

) else (

    runtime\python\python.exe server.py

)



echo.

echo Server stopped.
pause

