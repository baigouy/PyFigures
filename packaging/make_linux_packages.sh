#!/usr/bin/env bash
# Packs the PyInstaller folder (dist/PyFigures, or dist/"PyFigures NoAI") for
# Linux, run by the CI:
#   PyFigures-Linux-<arch>.tar.gz   the portable folder (unpack, run PyFigures/PyFigures)
#   PyFigures-Linux-<arch>.AppImage the same folder as one executable file
# (PyFigures-NoAI-Linux-… for the no-AI app)
#
#   bash packaging/make_linux_packages.sh <dist dir> <appimagetool> [<app name>]
#
# appimagetool is itself an AppImage; APPIMAGE_EXTRACT_AND_RUN=1 lets it run
# where FUSE is missing (CI runners, containers).
set -euo pipefail
DIST="${1:-dist}"
TOOL="${2:-appimagetool}"
APP="${3:-PyFigures}"                 # the folder and its executable: "PyFigures", "PyFigures NoAI"
PREFIX="${APP// /-}"                  # file names carry no space
ARCH="$(uname -m)"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"

tar -C "$DIST" -czf "$PREFIX-Linux-$ARCH.tar.gz" "$APP"

APPDIR="$(mktemp -d)/PyFigures.AppDir"
mkdir -p "$APPDIR/usr/lib"
cp -a "$DIST/$APP" "$APPDIR/usr/lib/PyFigures"
if [ "$APP" != "PyFigures" ]; then
  # AppRun starts usr/lib/PyFigures/PyFigures: the same program under that name
  ln -s "$APP" "$APPDIR/usr/lib/PyFigures/PyFigures"
fi
cp "$HERE/linux/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp "$HERE/linux/pyfigures.desktop" "$APPDIR/pyfigures.desktop"
cp "$ROOT/pyfigures/icons/pyfigures.png" "$APPDIR/pyfigures.png"
cp "$ROOT/pyfigures/icons/pyfigures.png" "$APPDIR/.DirIcon"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$PREFIX-Linux-$ARCH.AppImage"
ls -l "$PREFIX-Linux-$ARCH.tar.gz" "$PREFIX-Linux-$ARCH.AppImage"
