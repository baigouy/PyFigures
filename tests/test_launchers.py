"""The standalone app's launchers: PyFigures opens the figure editor, the
'PyFigures Album' / 'PyFigures Poster' executables (Windows) or `--album` /
`--poster` (the macOS launcher apps, the command line) the photo album and
poster designers.
The build itself runs on CI; here the spec, the workflow and the macOS
launcher script are checked.
"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("argv, exe, tool", [
    ([], "", None),
    ([], r"C:\Apps\PyFigures\PyFigures.exe", None),
    ([], r"C:\Apps\PyFigures\PyFigures Album.exe", "album"),
    ([], r"C:\Apps\PyFigures\PyFigures Poster.exe", "poster"),
    (["--album"], "/Applications/PyFigures.app/Contents/MacOS/PyFigures", "album"),
    (["-psn_0_1234", "--album"], "", "album"),            # macOS may add a process id
    (["--poster"], "", "poster"),
    (["figure.pyf"], "", None),
])
def test_requested_tool(argv, exe, tool):
    from pyfigures.__main__ import requested_tool
    assert requested_tool(argv, exe) == tool


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_spec_builds_the_album_and_poster_executables_on_windows():
    spec = _read("pyfigures.spec")
    block = spec[spec.index("extra_exes = []"):spec.index("coll = COLLECT(")]
    assert "for _launcher in ('PyFigures Album', 'PyFigures Poster'):" in block
    assert "if sys.platform != 'win32':" in block and "name=_launcher" in block
    assert "console=False" in block and "exclude_binaries=True" in block
    assert "*extra_exes," in spec[spec.index("coll = COLLECT("):]
    compile(spec, "pyfigures.spec", "exec")


@pytest.mark.parametrize("name", ["pyfigures", "pyfigures_album", "pyfigures_poster"])
def test_every_executable_has_its_icon(name):
    from PIL import Image
    icons = os.path.join(ROOT, "images", "icons")
    with Image.open(os.path.join(icons, name + ".ico")) as ico:
        assert (16, 16) in ico.info["sizes"] and (256, 256) in ico.info["sizes"]
    with Image.open(os.path.join(icons, name + ".icns")) as icns:
        assert icns.format == "ICNS"
    with Image.open(os.path.join(ROOT, "pyfigures", "icons", name + ".png")) as png:
        assert png.size == (1024, 1024)
    spec = _read("pyfigures.spec")
    assert "icon=_icon('pyfigures')" in spec                      # main exe + macOS bundle
    assert "icon=_icon(_launcher.lower().replace(' ', '_'))" in spec


def test_window_icons(qapp, monkeypatch):
    from qtpy.QtWidgets import QApplication, QMessageBox
    from pyfigures import icons
    from pyfigures.poster.poster_window import PosterWindow
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Discard))

    def same(qicon, name):
        a = qicon.pixmap(32, 32).toImage()
        b = icons.app_icon(name).pixmap(32, 32).toImage()
        return not a.isNull() and a == b

    for album, name in ((True, "pyfigures_album"), (False, "pyfigures_poster")):
        w = PosterWindow(album=album)
        assert same(w.windowIcon(), name)
        w.close()
    assert not same(icons.app_icon("pyfigures_album"), "pyfigures_poster")   # really different
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        assert same(g.windowIcon(), "pyfigures")
    finally:
        g._dirty = False
        g.close()
    old = QApplication.windowIcon()
    try:
        icons.set_app_identity("pyfigures_album")
        assert same(QApplication.windowIcon(), "pyfigures_album")
    finally:
        QApplication.setWindowIcon(old)


def test_icons_ship_in_the_package():
    setup = _read("setup.py")
    assert "'pyfigures': ['icons/*.png']" in setup


def test_workflow_ships_the_launchers_on_macos():
    wf = _read(".github", "workflows", "build.yml")
    assert "packaging/make_macos_launcher_apps.sh dist" in wf
    dmg = wf[wf.index("Package (macOS — dmg)"):]
    assert '"dist/PyFigures Album.app" "dist/PyFigures Poster.app"' in dmg and "dmg_src" in dmg
    assert '--icon "PyFigures Poster.app"' in dmg
    assert "${{ matrix.artifact_path }}" in dmg


_LAUNCHER_SCRIPT = os.path.join(ROOT, "packaging", "make_macos_launcher_apps.sh")


def _posix(path):
    return str(path).replace("\\", "/")


def _bash_that_sees_windows_paths():
    """A bash that can open this checkout's files by path. On Windows the
    `bash` on PATH is often WSL's (System32), which cannot read C:\\ paths:
    prefer Git Bash, and give up (skip) rather than test the wrong thing."""
    candidates = [shutil.which("bash")]
    if os.name == "nt":
        for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            candidates.insert(0, os.path.join(root, "Git", "bin", "bash.exe"))
    for bash in candidates:
        if not bash or not os.path.isfile(bash):
            continue
        try:
            r = subprocess.run([bash, "-c", 'test -f "$1"', "_", _posix(_LAUNCHER_SCRIPT)],
                               capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0:
            return bash
    return None


_BASH = _bash_that_sees_windows_paths()


@pytest.mark.skipif(_BASH is None, reason="needs a bash that can read this checkout (Git Bash on Windows)")
@pytest.mark.parametrize("name, flag, bundle_id", [
    ("PyFigures Album", "--album", "com.aigouy.pyfigures.album"),
    ("PyFigures Poster", "--poster", "com.aigouy.pyfigures.poster"),
])
def test_macos_launcher_apps_are_made_next_to_pyfigures_app(tmp_path, name, flag, bundle_id):
    script = _posix(_LAUNCHER_SCRIPT)
    r = subprocess.run([_BASH, script, _posix(tmp_path), "1.2.3"], capture_output=True, text=True)
    assert r.returncode != 0 and "PyFigures.app" in r.stderr     # needs the built app first
    (tmp_path / "PyFigures.app").mkdir()
    r = subprocess.run([_BASH, script, _posix(tmp_path), "1.2.3"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    app = tmp_path / f"{name}.app" / "Contents"
    with open(app / "Info.plist", "rb") as f:
        info = plistlib.load(f)
    assert info["CFBundleExecutable"] == name and info["CFBundleIdentifier"] == bundle_id
    assert info["CFBundleShortVersionString"] == "1.2.3" and info["CFBundlePackageType"] == "APPL"
    icon = app / "Resources" / info["CFBundleIconFile"]
    assert icon.read_bytes()[:4] == b"icns"
    launcher = (app / "MacOS" / name).read_text(encoding="utf-8")
    assert launcher.startswith("#!/bin/bash\n")
    assert f'exec open -n -a "$main" --args {flag}' in launcher
    assert f"Keep {name} next to PyFigures.app" in launcher
    assert '/../../..' in launcher and "/Applications/PyFigures.app" in launcher
