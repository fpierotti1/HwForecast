@echo off
setlocal

echo ==========================================
echo   Laptop Forecast App - Windows Build
echo   Target: Single File Executable (.exe)
echo ==========================================

:: Check for PyInstaller
where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller not found.
    echo Please run: pip install -r requirements.txt
    pause
    exit /b 1
)

:: Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

:: Build Command
echo [INFO] Building LaptopForecast_v3.exe...
pyinstaller --noconfirm --onefile --windowed --name "LaptopForecast_v3" app.py

:: Check Success
if exist "dist\LaptopForecast_v3.exe" (
    echo.
    echo [SUCCESS] Build Complete!
    echo Executable located at: dist\LaptopForecast_v3.exe
) else (
    echo.
    echo [ERROR] Build Failed.
)

pause
endlocal
