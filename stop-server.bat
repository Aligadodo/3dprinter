@echo off
chcp 65001 >nul 2>&1

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in PATH!
    pause
    exit /b 1
)

python "%~dp0stop-server.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   Stop failed (exit code: %ERRORLEVEL%)
    pause
)
