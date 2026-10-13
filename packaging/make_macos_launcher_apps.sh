#!/bin/bash
# Makes "PyFigures Album.app" and "PyFigures Poster.app" next to PyFigures.app
# (macOS build, see .github/workflows/build.yml): tiny launchers that open
# PyFigures.app with --album (the photo album designer) or --poster (the
# poster designer), so the whole app isn't shipped three times. On Windows
# the same launchers are executables built by pyfigures.spec.
# Usage: make_macos_launcher_apps.sh <dist_dir> <version>
set -euo pipefail
DIST="${1:-dist}"
VERSION="${2:-0.0.0}"
test -d "$DIST/PyFigures.app" || { echo "no $DIST/PyFigures.app: run pyinstaller first" >&2; exit 1; }

make_launcher() {
  local name="$1" flag="$2" id="$3"
  local app="$DIST/$name.app"
  rm -rf "$app"
  mkdir -p "$app/Contents/MacOS"

  printf '%s\n' \
    '#!/bin/bash' \
    '# PyFigures.app next to this app (same folder: Applications, the dmg), else /Applications' \
    'here="$(cd "$(dirname "$0")/../../.." && pwd)"' \
    'main="$here/PyFigures.app"' \
    'if [ ! -d "$main" ]; then main="/Applications/PyFigures.app"; fi' \
    'if [ ! -d "$main" ]; then' \
    "  osascript -e 'display alert \"PyFigures.app not found\" message \"Keep $name next to PyFigures.app.\"'" \
    '  exit 1' \
    'fi' \
    "exec open -n -a \"\$main\" --args $flag" \
    > "$app/Contents/MacOS/$name"
  chmod +x "$app/Contents/MacOS/$name"

  printf '%s\n' \
    '<?xml version="1.0" encoding="UTF-8"?>' \
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
    '<plist version="1.0">' \
    '<dict>' \
    "  <key>CFBundleExecutable</key><string>$name</string>" \
    "  <key>CFBundleIdentifier</key><string>com.aigouy.pyfigures.$id</string>" \
    "  <key>CFBundleName</key><string>$name</string>" \
    "  <key>CFBundleDisplayName</key><string>$name</string>" \
    '  <key>CFBundlePackageType</key><string>APPL</string>' \
    "  <key>CFBundleShortVersionString</key><string>$VERSION</string>" \
    '  <key>NSHighResolutionCapable</key><true/>' \
    '</dict>' \
    '</plist>' \
    > "$app/Contents/Info.plist"

  echo "made $app"
}

make_launcher "PyFigures Album" --album album
make_launcher "PyFigures Poster" --poster poster
