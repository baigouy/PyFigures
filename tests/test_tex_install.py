"""On-demand LaTeX (TinyTeX) install: batoolset.tex_install, the GUI offer,
the MCP tool and the CLI. Nothing is downloaded here: the bundle is a fake
archive and tlmgr is mocked.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tarfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from batoolset import latex_tools as LT
from batoolset import tex_install as TI

EXE = ".exe" if sys.platform.startswith("win") else ""
PLAT = "windows" if sys.platform.startswith("win") else "x86_64-linux"


def test_bundle_names_per_platform():
    assert TI.asset_name("win32") == "TinyTeX-1-windows.exe"
    assert TI.asset_name("darwin", "arm64") == "TinyTeX-1-darwin.tar.xz"
    assert TI.asset_name("linux", "x86_64") == "TinyTeX-1-linux-x86_64.tar.xz"
    assert TI.asset_name("linux", "aarch64") == "TinyTeX-1-linux-arm64.tar.xz"
    with pytest.raises(ValueError):
        TI.asset_name("linux", "ppc64le")


def test_missing_files_from_a_latex_log():
    log = ("! LaTeX Error: File `physics.sty' not found.\n"
           "! LaTeX Error: File `revtex4-2.cls' not found.\n"
           "! LaTeX Error: File `physics.sty' not found.\n")
    assert TI.missing_files(log) == ["physics.sty", "revtex4-2.cls"]
    assert TI.missing_files("all fine") == []


def _fake_bundle(path, top=".TinyTeX"):
    """A tar.xz laid out like TinyTeX (bin/<platform>/latex …)."""
    with tarfile.open(path, "w:xz") as tf:
        for tool in ("latex", "pdflatex", "xelatex", "dvisvgm", "tlmgr"):
            data = b"#!/bin/sh\n"
            info = tarfile.TarInfo(f"{top}/bin/{PLAT}/{tool}{EXE if tool != 'tlmgr' else ''}")
            if tool == "tlmgr" and EXE:
                info.name = f"{top}/bin/{PLAT}/tlmgr.bat"
            info.size = len(data)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(data))


def test_install_downloads_unpacks_and_adds_packages(tmp_path, monkeypatch):
    root = tmp_path / "home" / "TinyTeX"
    monkeypatch.setenv("PYFIGURES_TINYTEX_DIR", str(root))
    monkeypatch.setattr(TI, "asset_name", lambda *a: "TinyTeX-1-linux-x86_64.tar.xz")
    fetched = []

    def download(url, dest, progress=None, cancelled=None):
        fetched.append(url)
        _fake_bundle(dest)
    monkeypatch.setattr(TI, "_download", download)
    commands = []

    def run(cmd, timeout=0):
        commands.append(cmd)
        if cmd[1] == "info":                         # what tlmgr reports as installed
            return 0, "\n".join(TI.PACKAGES)
        return 0, "ok"
    monkeypatch.setattr(TI, "_run", run)
    steps = []
    assert not TI.is_installed(str(root))
    # an incomplete earlier attempt is kept aside, not deleted
    (root / "leftover").mkdir(parents=True)
    out = TI.install(progress=lambda f, m: steps.append((f, m)))
    assert out == str(root) and TI.is_installed(str(root))
    assert fetched == [TI.DOWNLOAD_BASE + "TinyTeX-1-linux-x86_64.tar.xz"]
    assert any(os.path.basename(p).startswith("TinyTeX-incomplete-") for p in os.listdir(tmp_path / "home"))
    install_cmd = [c for c in commands if c[1] == "install"][0]
    assert "dvisvgm" in install_cmd and "unicode-math" in install_cmd and "siunitx" in install_cmd
    assert steps[-1][0] == 1.0
    # LaTeX tools are now found there
    monkeypatch.setattr(LT.shutil, "which", lambda name: None)
    assert LT.find_tex_tool("xelatex").startswith(str(root))
    # a second install only updates the packages
    fetched.clear()
    TI.install()
    assert fetched == []
    # a package tlmgr did not install is reported
    with pytest.raises(RuntimeError, match="nosuchpkg"):
        TI.install(packages=["siunitx", "nosuchpkg"])


def test_install_missing_packages_from_a_log(monkeypatch):
    monkeypatch.setattr(LT, "find_tex_tool", lambda name: "/tl/tlmgr" if name == "tlmgr" else None)
    calls = []

    def run(cmd, timeout=0):
        calls.append(cmd)
        if cmd[1] == "search":
            return 0, "tlpdb: searching\nphysics:\n\ttexmf-dist/tex/latex/physics/physics.sty\n"
        return 0, ""
    monkeypatch.setattr(TI, "_run", run)
    assert TI.install_missing("! LaTeX Error: File `physics.sty' not found.") == ["physics"]
    assert calls[-1] == ["/tl/tlmgr", "install", "physics"]
    assert TI.install_missing("no error") == []


def test_gui_offer_and_progress(qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import latex_support as LS
    monkeypatch.setattr(LS, "latex_ready", lambda: False)
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: (asked.append(a[2]),
                                                      QMessageBox.StandardButton.No)[1]))
    LS._declined.clear()
    assert LS.offer_latex_install(None, "Full LaTeX") is False
    assert LS.offer_latex_install(None, "Full LaTeX") is False and len(asked) == 1   # asked once
    assert "TinyTeX" in asked[0]

    seen = []

    def fake_install(progress=None, cancelled=None):
        progress(0.5, "Downloading TinyTeX… 30 / 60 MB")
        seen.append(cancelled())
    ready = iter([True])
    monkeypatch.setattr(LS, "latex_ready", lambda: next(ready, True))
    assert LS.run_install(None, installer=fake_install) is True and seen == [False]

    def failing(progress=None, cancelled=None):
        raise RuntimeError("no network")
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a[2])))
    assert LS.run_install(None, installer=failing) is False
    assert "no network" in warned[0]


def test_equation_dialog_install_button(qapp, monkeypatch):
    from pyfigures import equations as E
    from pyfigures.gui import latex_support as LS
    from pyfigures.gui.equation_dialog import EquationDialog
    monkeypatch.setattr(E, "latex_available", lambda: False)
    d = EquationDialog()
    assert not d.engine_check.isEnabled() and d.install_latex_button is not None
    monkeypatch.setattr(LS, "offer_latex_install", lambda parent, why: True)
    monkeypatch.setattr(EquationDialog, "update_preview", lambda self: None)
    d._install_latex()
    assert d.engine_check.isEnabled() and d.engine_check.isChecked()
    assert d.install_latex_button.isHidden()
    d.deleteLater()


def test_gui_menu_and_tex_drop_offer(qapp, monkeypatch, tmp_path):
    from pyfigures import equations as E
    from pyfigures.gui import latex_support as LS
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        names = [a.text() for m in g.menuBar.actions() if m.menu() for a in m.menu().actions()]
        assert "Install LaTeX for PyFigures…" in names
        called = []
        monkeypatch.setattr(LS, "install_latex_action", lambda parent: called.append(parent) or True)
        assert g.install_latex_action(False) and called == [g]
        # a dropped .tex document without LaTeX: installing is offered first
        doc = tmp_path / "d.tex"
        doc.write_text("\\documentclass{article}\\begin{document}\\begin{tikzpicture}"
                       "\\end{tikzpicture}\\end{document}", encoding="utf-8")
        monkeypatch.setattr(E, "find_tex_tool", lambda name: None)
        offers = []
        monkeypatch.setattr(LS, "offer_latex_install", lambda parent, why: offers.append(why) and False)
        assert g._equation_from_tex(str(doc)) is None and offers
    finally:
        g._dirty = False
        g.close()


def test_mcp_and_cli(monkeypatch, capsys):
    import pyfigures.mcp_server as M
    from pyfigures.gui import headless_ops
    monkeypatch.setattr(TI, "install", lambda progress=None, **k: (progress(1.0, "done"), "/x/TinyTeX")[1])
    res = json.loads(M.install_latex())
    assert res["installed_in"] == "/x/TinyTeX" and "latex_available" in res
    status = json.loads(M.install_latex(check_only=True))
    assert "tools" in status and "latex" in status["tools"]
    assert headless_ops._main(["install-latex"]) == 0
    assert "/x/TinyTeX" in capsys.readouterr().out
