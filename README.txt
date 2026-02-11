================================================================================
LAPTOP FORECAST APP v3.1 - CROSS-PLATFORM DEPLOYMENT GUIDE
================================================================================

This package contains the source code for the Laptop Forecast App v3.1.
Support is included for both Windows and macOS (Tahoe/Modern).

PREREQUISITES
-------------
1. Python 3.9+ installed.
2. Dependencies installed via:
   pip install -r requirements.txt

================================================================================
WINDOWS BUILD INSTRUCTIONS
================================================================================

1. Open a Command Prompt or PowerShell in this folder.
2. Run the build script:
   > build_windows.bat

   This script will:
   - Verify PyInstaller is installed.
   - Compile a single-file executable.
   - Output the file to: dist\LaptopForecast_v3.exe

3. Deployment:
   - Copy 'dist\LaptopForecast_v3.exe' to any location.
   - Ensure 'forecast_db.json' is accessible if sharing data.

================================================================================
MACOS BUILD INSTRUCTIONS
================================================================================

1. Open Terminal in this folder.
2. Install system dependencies (for DMG creation):
   > brew install create-dmg
   (If you don't use Homebrew, the script falls back to 'hdiutil' for a basic DMG)

3. Make the script executable:
   > chmod +x build_macos.sh

4. Run the build script:
   > ./build_macos.sh

   This script will:
   - Check for PyInstaller.
   - Build 'LaptopForecast_v3.app'.
   - Package it into 'LaptopForecast_v3_3.1.dmg'.

5. Deployment:
   - Share the 'dist/LaptopForecast_v3_3.1.dmg' file.
   - Users can mount the DMG and drag the app to Applications.

================================================================================
TROUBLESHOOTING
================================================================================
- If 'pyinstaller' is not found, ensure it is in your system PATH.
  Try: 'python -m pip install pyinstaller'

- If macOS complains about "Unidentified Developer", go to:
  System Settings > Privacy & Security > Open Anyway.

================================================================================
CONTACT
================================================================================
Created by Fabio Pierotti
