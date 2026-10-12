"""Licence compliance of the standalone apps and the README's licence table.

- packaging/collect_licenses.py packs the corresponding source of every
  bundled component into per-group tars (deduplicated) for the release;
- Help > About states the licence and, in a standalone app, opens the
  third-party licence texts;
- every dependency in setup.py (and the video extra) is listed with its
  licence in the README.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tarfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _collect():
    spec = importlib.util.spec_from_file_location(
        "collect_licenses", os.path.join(ROOT, "packaging", "collect_licenses.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sources_are_packed_per_group_and_deduplicated(tmp_path):
    C = _collect()
    src = tmp_path / "src"
    src.mkdir()
    for n in ("a-1.0.tar.gz", "qt-6.4.3.tar.xz", "x264.tar.bz2"):
        (src / n).write_bytes(n.encode() * 10)
    url = (src / "a-1.0.tar.gz").as_uri()
    m1 = [{"name": "a", "version": "1.0", "license": "MIT", "source": url, "group": "python"},
          {"name": "PyQt6-Qt6", "version": "6.4.3", "license": "LGPL v3",
           "source": (src / "qt-6.4.3.tar.xz").as_uri(), "group": "qt"},
          {"name": "local", "version": "0", "license": "BSD", "source": None, "group": "python"}]
    m2 = [{"name": "a", "version": "1.0", "license": "MIT", "source": url, "group": "python"},
          {"name": "x264", "version": "", "license": "GPL-2.0-or-later",
           "source": (src / "x264.tar.bz2").as_uri(), "group": "ffmpeg"}]
    paths = []
    for i, m in enumerate((m1, m2)):
        p = tmp_path / f"m{i}.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        paths.append(str(p))
    out = tmp_path / "out"
    C.sources(str(out), paths)
    tars = sorted(os.listdir(out))
    assert tars == ["corresponding-source-ffmpeg.tar", "corresponding-source-python.tar",
                    "corresponding-source-qt.tar"]
    with tarfile.open(out / "corresponding-source-python.tar") as t:
        assert t.getnames() == ["python/a-1.0.tar.gz"]          # once, not twice
    with tarfile.open(out / "corresponding-source-ffmpeg.tar") as t:
        assert t.extractfile("ffmpeg/x264.tar.bz2").read() == b"x264.tar.bz2" * 10


def test_a_missing_source_fails_the_release(tmp_path, monkeypatch):
    C = _collect()
    monkeypatch.setattr(C.time, "sleep", lambda s: None)       # no back-off between retries
    p = tmp_path / "m.json"
    gone = (tmp_path / "nope.tar.gz").as_uri()
    p.write_text(json.dumps([{"name": "x", "version": "1", "license": "GPL v3",
                              "source": gone, "group": "python"}]), encoding="utf-8")
    with pytest.raises(SystemExit):
        C.sources(str(tmp_path / "out"), [str(p)])


def test_licence_metadata_and_files_are_found():
    C = _collect()
    import importlib.metadata as md
    pyqt = md.distribution("PyQt6")
    assert "GPL" in C._license_of(pyqt)
    try:
        lif = md.distribution("read-lif")
    except md.PackageNotFoundError:
        lif = None
    if lif is not None:                   # its metadata states no licence
        assert "GPL" in C._license_of(lif)
    av = pytest.importorskip("av")
    texts = C._license_texts(md.distribution("av"))
    assert any(name.upper().startswith("LICENSE") for name, _ in texts)
    assert C.LICENSE_FILE.search("x.dist-info/licenses/COPYING.LGPL")
    assert not C.LICENSE_FILE.search("x.dist-info/RECORD")


def test_about_dialog_states_the_licence(qapp, monkeypatch, tmp_path):
    from pyfigures.gui import about_dialog_pzf as A
    from qtpy.QtWidgets import QLabel, QPushButton
    d = A.AboutDialog()
    texts = " ".join(lbl.text() for lbl in d.findChildren(QLabel))
    assert "BSD-2-Clause" in texts and "GPL v3" in texts and "NO WARRANTY" in texts
    assert d.licenses_path is None
    assert not [b for b in d.findChildren(QPushButton) if "licences" in b.text()]
    d.deleteLater()
    # standalone app: the GPL statement and a button opening the licence texts
    (tmp_path / "third_party").mkdir()
    lic = tmp_path / "third_party" / "THIRD_PARTY_LICENSES.txt"
    lic.write_text("GNU GENERAL PUBLIC LICENSE", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    opened = []
    monkeypatch.setattr(A.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url)))
    d = A.AboutDialog()
    texts = " ".join(lbl.text() for lbl in d.findChildren(QLabel))
    assert "GNU General Public License v3" in texts and "FFmpeg" in texts
    (button,) = [b for b in d.findChildren(QPushButton) if "licences" in b.text()]
    button.click()
    assert opened and os.path.samefile(opened[0].toLocalFile(), str(lic))
    d.deleteLater()


def test_readme_lists_every_dependency_with_its_licence():
    with open(os.path.join(ROOT, "setup.py"), encoding="utf-8") as f:
        setup = f.read()
    block = setup[setup.index("install_requires"):setup.index("extras_require")]
    deps = [re.split(r"[<>=!\[ ]", d)[0] for d in re.findall(r'^\s*f?"([^"]+)"', block, re.M)]
    deps = [d.replace("{__VERSION__}", "") for d in deps]
    deps += ["av", "mcp", "FFmpeg"]
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    table = readme[readme.index("# Third party libraries"):readme.index("# Other Figure-Making")]
    rows = [r for r in table.splitlines() if r.startswith("| **")]
    missing = [d for d in deps
               if not any(re.search(r"\b" + re.escape(d.lower()) + r"\b", r.lower()) for r in rows)]
    assert not missing, missing
    for r in rows:
        assert r.rstrip(" |").split("|")[-1].strip(), r          # every row names a licence
    assert "corresponding source" in table and "GNU GPL v3" in table
