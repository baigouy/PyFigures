#!/bin/bash
# Makes "PyFigures Album.app" next to PyFigures.app (macOS build, see
# .github/workflows/build.yml): a tiny launcher that opens PyFigures.app with
# --album (the photo album designer), so the whole app isn't shipped twice.
# Usage: make_macos_album_app.sh <dist_dir> <version>
set -euo pipefail
DIST="${1:-dist}"
VERSION="${2:-0.0.0}"
APP="$DIST/PyFigures Album.app"
test -d "$DIST/PyFigures.app" || { echo "no $DIST/PyFigures.app: run pyinstaller first" >&2; exit 1; }

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"

printf '%s\n' \
  '#!/bin/bash' \
  '# PyFigures.app next to this app (same folder: Applications, the dmg), else /Applications' \
  'here="$(cd "$(dirname "$0")/../../.." && pwd)"' \
  'main="$here/PyFigures.app"' \
  'if [ ! -d "$main" ]; then main="/Applications/PyFigures.app"; fi' \
  'if [ ! -d "$main" ]; then' \
  '  osascript -e "display alert \"PyFigures.app not found\" message \"Keep PyFigures Album next to PyFigures.app.\""' \
  '  exit 1' \
  'fi' \
  'exec open -n -a "$main" --args --album' \
  > "$APP/Contents/MacOS/PyFigures Album"
chmod +x "$APP/Contents/MacOS/PyFigures Album"

printf '%s\n' \
  '<?xml version="1.0" encoding="UTF-8"?>' \
  '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
  '<plist version="1.0">' \
  '<dict>' \
  '  <key>CFBundleExecutable</key><string>PyFigures Album</string>' \
  '  <key>CFBundleIdentifier</key><string>com.aigouy.pyfigures.album</string>' \
  '  <key>CFBundleName</key><string>PyFigures Album</string>' \
  '  <key>CFBundleDisplayName</key><string>PyFigures Album</string>' \
  '  <key>CFBundlePackageType</key><string>APPL</string>' \
  "  <key>CFBundleShortVersionString</key><string>$VERSION</string>" \
  '  <key>NSHighResolutionCapable</key><true/>' \
  '</dict>' \
  '</plist>' \
  > "$APP/Contents/Info.plist"

echo "made $APP"
