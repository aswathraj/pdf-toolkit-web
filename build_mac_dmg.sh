#!/bin/zsh

set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="PDF Forge.app"
VOL_NAME="PDF Forge"
DMG_NAME="PDFForge-macOS.dmg"
BUILD_ROOT="$PWD/build"
DIST_ROOT="$PWD/dist"
STAGE_ROOT="$BUILD_ROOT/dmg-stage"
RELEASE_ROOT="$PWD/release"
APP_PATH="$DIST_ROOT/$APP_NAME"
DMG_PATH="$RELEASE_ROOT/$DMG_NAME"

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

rm -rf "$BUILD_ROOT" "$DIST_ROOT" "$RELEASE_ROOT"

pyinstaller --noconfirm pdf_forge_mac.spec

if [[ ! -d "$APP_PATH" ]]; then
  echo "Expected app bundle not found at $APP_PATH"
  exit 1
fi

codesign --force --deep --sign - "$APP_PATH" >/dev/null 2>&1 || true

mkdir -p "$STAGE_ROOT" "$RELEASE_ROOT"
cp -R "$APP_PATH" "$STAGE_ROOT/"
ln -s /Applications "$STAGE_ROOT/Applications"

hdiutil create \
  -volname "$VOL_NAME" \
  -srcfolder "$STAGE_ROOT" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

rm -rf "$STAGE_ROOT"

echo
echo "App bundle: $APP_PATH"
echo "DMG file:   $DMG_PATH"
echo
