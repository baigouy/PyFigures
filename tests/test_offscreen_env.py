"""pyfigures.offscreen: the headless Qt platform must see real fonts on every
OS. Windows needs QT_QPA_FONTDIR (offscreen scans only that folder); Linux
(fontconfig) and macOS (Core Text) must be left untouched."""
import os
import subprocess
import sys

import pytest

from pyfigures import offscreen


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_no_font_dir_forced_on_linux_and_macos(monkeypatch, platform):
    monkeypatch.setattr(offscreen.sys, "platform", platform)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("QT_QPA_FONTDIR", raising=False)
    assert offscreen.system_font_dir() is None
    offscreen.ensure_offscreen_fonts()
    assert "QT_QPA_FONTDIR" not in os.environ


def test_windows_gets_system_fonts(monkeypatch, tmp_path):
    (tmp_path / "Fonts").mkdir()
    monkeypatch.setattr(offscreen.sys, "platform", "win32")
    monkeypatch.setenv("WINDIR", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("QT_QPA_FONTDIR", raising=False)
    offscreen.ensure_offscreen_fonts()
    assert os.environ["QT_QPA_FONTDIR"] == str(tmp_path / "Fonts")


def test_explicit_choices_are_respected(monkeypatch):
    monkeypatch.setattr(offscreen.sys, "platform", "win32")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("QT_QPA_FONTDIR", "/my/fonts")
    offscreen.ensure_offscreen_fonts()
    assert os.environ["QT_QPA_FONTDIR"] == "/my/fonts"
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")      # a real display: untouched
    monkeypatch.delenv("QT_QPA_FONTDIR")
    offscreen.ensure_offscreen_fonts()
    assert "QT_QPA_FONTDIR" not in os.environ


def test_headless_qt_sees_fonts():
    """On this OS, a fresh offscreen QApplication set up by use_offscreen()
    finds system fonts (was 0 families on Windows)."""
    code = ("import os\n"
            "os.environ.pop('QT_QPA_FONTDIR', None)\n"
            "os.environ.pop('QT_QPA_PLATFORM', None)\n"
            "from pyfigures.offscreen import use_offscreen\n"
            "use_offscreen()\n"
            "from PyQt6.QtWidgets import QApplication\n"
            "from PyQt6.QtGui import QFontDatabase\n"
            "app = QApplication([])\n"
            "print(len(QFontDatabase.families()), flush=True)\n"
            "os._exit(0)\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=120, cwd=os.path.dirname(os.path.dirname(__file__)))
    assert int(out.stdout.strip().splitlines()[-1]) > 5, out.stderr
