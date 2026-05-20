@echo off
chcp 65001 >nul 2>&1
setlocal

echo ================================================
echo    3D Print Pipeline - Web Management Platform
echo ================================================
echo.

REM Check Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in PATH!
    echo   Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

echo   Python:
python --version 2>&1
echo.

if not exist "%~dp0config\.env" (
    echo   API keys for text-to-image providers:
    echo     Create config\.env with your keys
    echo     (see config\.env.example for template)
    echo.
)

python "%~dp0start-server.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ================================================
    echo   Startup failed (exit code: %ERRORLEVEL%)
    echo ================================================
    echo.
    echo   If dependencies are missing, run:
    echo     pip install fastapi uvicorn python-multipart markdown PyYAML httpx Pillow numpy
    echo.
    pause
    exit /b %ERRORLEVEL%
)
