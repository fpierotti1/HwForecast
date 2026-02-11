@echo off
setlocal
echo ========================================================
echo   Laptop Forecast App v2.9.1 - Portable Launcher
echo ========================================================

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    goto :NoPython
)

:: 2. Check for Virtual Environment
if exist "venv" (
    echo [INFO] Virtual initialization found. Skipping setup...
    goto :LaunchApp
)

:SetupVenv
echo [INIT] Creating Virtual Environment (First Run Only)...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b
)

echo [INIT] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b
)
echo [INFO] Setup Complete.

:LaunchApp
echo.
echo [START] Launching Dashboard...
echo Close this window to stop the application.
echo.

:: Activate env if not already valid (e.g. from jump)
if not defined VIRTUAL_ENV call venv\Scripts\activate.bat

:: Launch Streamlit
streamlit run app.py --global.developmentMode=false

pause
exit /b

:NoPython
echo [ERROR] Python is not found on this system.
echo Please install Python 3.10+ from python.org and try again.
pause
exit /b
