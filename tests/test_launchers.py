"""The standalone app's launchers: PyFigures opens the figure editor, the
'PyFigures Album' executable (Windows) or `--album` (the macOS launcher app,
the command line) the photo album designer, `--poster` the poster designer.
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


def test_spec_builds_the_album_executable_on_windows():
    spec = _read("pyfigures.spec")
    block = spec[spec.index("extra_exes = []"):spec.index("coll = COLLECT(")]
    assert "if sys.platform == 'win32':" in block and "name='PyFigures Album'" in block
    assert "console=False" in block and "exclude_binaries=True" in block
    assert "*extra_exes," in spec[spec.index("coll = COLLECT("):]
    compile(spec, "pyfigures.spec", "exec")


def test_workflow_ships_the_album_launcher_on_macos():
    wf = _read(".github", "workflows", "build.yml")
    assert "packaging/make_macos_album_app.sh dist" in wf
    dmg = wf[wf.index("Package (macOS — dmg)"):]
    assert '"dist/PyFigures Album.app"' in dmg and "dmg_src" in dmg
    assert "${{ matrix.artifact_path }}" in dmg


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_macos_launcher_app_is_made_next_to_pyfigures_app(tmp_path):
    script = os.path.join(ROOT, "packaging", "make_macos_album_app.sh")
    r = subprocess.run(["bash", script, str(tmp_path), "1.2.3"], capture_output=True, text=True)
    assert r.returncode != 0 and "PyFigures.app" in r.stderr     # needs the built app first
    (tmp_path / "PyFigures.app").mkdir()
    r = subprocess.run(["bash", script, str(tmp_path), "1.2.3"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    app = tmp_path / "PyFigures Album.app" / "Contents"
    with open(app / "Info.plist", "rb") as f:
        info = plistlib.load(f)
    assert info["CFBundleExecutable"] == "PyFigures Album"
    assert info["CFBundleShortVersionString"] == "1.2.3" and info["CFBundlePackageType"] == "APPL"
    launcher = (app / "MacOS" / "PyFigures Album").read_text(encoding="utf-8")
    assert launcher.startswith("#!/bin/bash\n")
    assert 'exec open -n -a "$main" --args --album' in launcher
    assert '/../../..' in launcher and "/Applications/PyFigures.app" in launcher
