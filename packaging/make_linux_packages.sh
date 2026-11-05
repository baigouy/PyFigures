#!/usr/bin/env bash
# Packs the PyInstaller folder (dist/PyFigures) for Linux, run by the CI:
#   PyFigures-Linux-<arch>.tar.gz   the portable folder (unpack, run PyFigures/PyFigures)
#   PyFigures-Linux-<arch>.AppImage the same folder as one executable file
#
#   bash packaging/make_linux_packages.sh <dist dir> <appimagetool>
#
# appimagetool is itself an AppImage; APPIMAGE_EXTRACT_AND_RUN=1 lets it run
# where FUSE is missing (CI runners, containers).
set -euo pipefail
DIST="${1:-dist}"
TOOL="${2:-appimagetool}"
ARCH="$(uname -m)"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"

tar -C "$DIST" -czf "PyFigures-Linux-$ARCH.tar.gz" PyFigures

APPDIR="$(mktemp -d)/PyFigures.AppDir"
mkdir -p "$APPDIR/usr/lib"
cp -a "$DIST/PyFigures" "$APPDIR/usr/lib/PyFigures"
cp "$HERE/linux/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp "$HERE/linux/pyfigures.desktop" "$APPDIR/pyfigures.desktop"
cp "$ROOT/pyfigures/icons/pyfigures.png" "$APPDIR/pyfigures.png"
cp "$ROOT/pyfigures/icons/pyfigures.png" "$APPDIR/.DirIcon"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "PyFigures-Linux-$ARCH.AppImage"
ls -l "PyFigures-Linux-$ARCH.tar.gz" "PyFigures-Linux-$ARCH.AppImage"
