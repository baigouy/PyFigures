"""Offer to install PyAV when a video can't be read or written well.

PyAV (``pip install av``) is a wheel that bundles ffmpeg — including the H.264
encoder — on Windows, macOS and Linux, so videos work without installing
ffmpeg on the system. OpenCV can also read videos, but writes only the old
MPEG-4 codec, which QuickTime / Safari / PowerPoint on a Mac can't play.
Neither is a hard dependency of PyFigures (``pip install pyfigures[video]``).
"""
from __future__ import annotations

import importlib
import subprocess
import sys

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMessageBox

_declined = set()          # don't ask twice in one session for the same need


def _satisfied(need):
    from batoolset.img import video_backends
    have = video_backends()
    if need == "read":
        return have["cv2"] or have["av"]
    return have["h264"]


def install_pyav():
    """pip install av into the running Python; returns (ok, message)."""
    if getattr(sys, "frozen", False):
        return False, "This PyFigures build can't install packages; use a version with video support."
    try:
        proc = subprocess.run([sys.executable, "-m", "pip", "install", "av"],
                              capture_output=True, text=True, timeout=900)
    except Exception as e:
        return False, str(e)
    importlib.invalidate_caches()
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "pip failed").strip()[-1500:]
    return True, "PyAV installed."


def offer_video_support(parent, need="read"):
    """True when videos can be read (*need* 'read') or written as H.264 ('h264'),
    after offering to install PyAV if needed. False if the user declined or
    the install failed — callers then go on with what is there (OpenCV) or stop."""
    if _satisfied(need):
        return True
    if need in _declined:
        return False
    why = ("Reading this video" if need == "read" else
           "Writing a video that plays everywhere (H.264 — QuickTime, Safari, PowerPoint, browsers)")
    answer = QMessageBox.question(
        parent, "Video support",
        f"{why} needs PyAV, a free library that includes ffmpeg (no separate "
        "ffmpeg install; Windows, macOS and Linux).\n\n"
        "Install it now? (pip install av — about 30 MB)",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
    if answer != QMessageBox.Yes:
        _declined.add(need)
        return False
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        ok, msg = install_pyav()
    finally:
        QApplication.restoreOverrideCursor()
    if not ok or not _satisfied(need):
        QMessageBox.warning(parent, "Video support",
                            "PyAV could not be installed:\n" + msg
                            + "\n\nYou can install it yourself with:  pip install av")
        _declined.add(need)
        return False
    return True
