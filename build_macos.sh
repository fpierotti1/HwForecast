#!/bin/bash

APP_NAME="LaptopForecast_v3"
VERSION="3.1"
DMG_NAME="${APP_NAME}_${VERSION}.dmg"

echo "=========================================="
echo "  Laptop Forecast App - macOS Build"
echo "  Target: .app Bundle & .dmg Image"
echo "=========================================="

# Check for PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "[ERROR] PyInstaller not found."
    echo "Please run: pip install -r requirements.txt"
    exit 1
fi

# Clean previous builds
echo "[INFO] Cleaning previous builds..."
rm -rf build dist *.spec

# Build .app Bundle
echo "[INFO] Building ${APP_NAME}.app..."
pyinstaller --noconfirm --windowed --name "${APP_NAME}" app.py

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "[ERROR] Build of .app failed."
    exit 1
else
    echo "[SUCCESS] Created dist/${APP_NAME}.app"
fi

# Create DMG
echo "[INFO] Packaging into ${DMG_NAME}..."

# Check for create-dmg (brew install create-dmg)
if command -v create-dmg &> /dev/null; then
    create-dmg \
      --volname "${APP_NAME}" \
      --window-pos 200 120 \
      --window-size 800 400 \
      --icon-size 100 \
      --icon "${APP_NAME}.app" 200 190 \
      --hide-extension "${APP_NAME}.app" \
      --app-drop-link 600 185 \
      "dist/${DMG_NAME}" \
      "dist/${APP_NAME}.app"
      
    if [ -f "dist/${DMG_NAME}" ]; then
        echo "[SUCCESS] Created dist/${DMG_NAME}"
    else
        echo "[ERROR] DMG creation failed."
    fi
    
elif command -v hdiutil &> /dev/null; then
    echo "[WARN] 'create-dmg' not found. Fallback to hdiutil (Basic DMG)."
    hdiutil create -volname "${APP_NAME}" -srcfolder "dist/${APP_NAME}.app" -ov -format UDZO "dist/${DMG_NAME}"
    echo "[SUCCESS] Created dist/${DMG_NAME} (via hdiutil)"
else
    echo "[ERROR] No DMG tools found (create-dmg or hdiutil). Skipping DMG creation."
fi

echo "=========================================="
echo "  Build Process Finished."
echo "=========================================="
