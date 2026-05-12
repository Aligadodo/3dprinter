@echo off
setlocal

echo ================================================
echo    3D Print Pipeline - Web Management Platform
echo ================================================
echo.
echo   API keys for text-to-image providers:
echo     Create config\.env with your keys
echo     (see config\.env.example for template^)
echo.

python "%~dp0start-server.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo If dependencies are missing, run:
    echo   pip install fastapi uvicorn python-multipart
    pause
)
