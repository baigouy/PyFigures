"""`PyFigures --self-test report.json` (run by the CI on each built app).

Run with PYTEST_QT_API=pyqt6.
"""
import json
import os
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def test_self_test_passes_without_pymupdf(qapp, tmp_path, monkeypatch):
    pytest.importorskip("pypdfium2")
    pytest.importorskip("av")
    pytest.importorskip("zarr")
    from pyfigures import self_test
    monkeypatch.setitem(sys.modules, "fitz", None)          # as in the apps
    out = tmp_path / "r.json"
    assert self_test.run(str(out)) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] and set(report["checks"]) == {"qt_svg", "pdf_panels", "video", "zarr"}
    assert "pypdfium2" in report["checks"]["pdf_panels"]


def test_self_test_fails_if_pymupdf_is_bundled(qapp, tmp_path):
    pytest.importorskip("fitz")
    from pyfigures import self_test
    out = tmp_path / "r.json"
    assert self_test.run(str(out)) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "PyMuPDF (AGPL) is bundled" in report["checks"]["pdf_panels"]


def test_command_line_flag(tmp_path):
    out = tmp_path / "r.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_API="pyqt6")
    p = subprocess.run([sys.executable, "-m", "pyfigures", "--self-test", str(out)],
                       env=env, capture_output=True, text=True, timeout=300)
    report = json.loads(out.read_text(encoding="utf-8"))
    assert p.returncode == (0 if report["ok"] else 1)
    assert set(report["checks"]) == {"qt_svg", "pdf_panels", "video", "zarr"}
