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


def test_gnu_texts_fall_back_to_spdx_when_gnu_org_times_out(monkeypatch):
    C = _collect()
    asked = []

    def fake_get(url, tries=3, timeout=120):
        asked.append(url)
        if "gnu.org" in url:
            raise OSError("timed out")
        return b"GNU GENERAL PUBLIC LICENSE Version 3"

    monkeypatch.setattr(C, "_get", fake_get)
    assert C._gnu_text("GNU GENERAL PUBLIC LICENSE, Version 3").startswith("GNU GENERAL")
    assert asked == ["https://www.gnu.org/licenses/gpl-3.0.txt",
                     "https://raw.githubusercontent.com/spdx/license-list-data/main/text/GPL-3.0-only.txt"]
    assert set(C.GNU_SPDX_IDS) == set(C.GNU_TEXTS)


def test_ffmpeg_build_found_in_ffmpeg_latest_json(monkeypatch):
    # PyAV 19 wheels use FFmpeg 9.0, described only in scripts/ffmpeg-latest.json
    import types
    import urllib.error
    C = _collect()
    monkeypatch.setitem(sys.modules, "av", types.SimpleNamespace(__version__="19.0.2", ffmpeg_version_info="9.0.2"))
    asked = []

    def fake_get(url, tries=3, timeout=120):
        asked.append(url)
        if url.endswith("ffmpeg-9.0.json"):
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        if url.endswith("ffmpeg-latest.json"):
            return b'{"url": "https://github.com/PyAV-Org/pyav-ffmpeg/releases/download/9.0.2-1/ffmpeg-{platform}.tar.gz"}'
        assert url == C.PYAV_FFMPEG_PKG.format(tag="9.0.2-1"), url
        return b'name="x264", source_url="https://example.org/x264.tar.bz2"'

    monkeypatch.setattr(C, "_get", fake_get)
    comps = C._ffmpeg_components()
    assert comps[0]["version"] == "9.0.2-1"
    assert [c["name"] for c in comps[1:]] == ["x264"]
    assert asked[0].endswith("/v19.0.2/scripts/ffmpeg-9.0.json")


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
    # bundled in the app instead of PyMuPDF (AGPL): permissive, with PDFium's notices
    pdfium = md.distribution("pypdfium2")
    assert "GPL" not in C._license_of(pdfium)
    names = [name for name, _ in C._license_texts(pdfium)]
    assert any("Apache" in n for n in names) and any("pdfium" in n.lower() for n in names)
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
    assert "Affero" not in texts and "PyMuPDF" not in texts
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


def test_the_wheel_installs_only_the_pyfigures_package():
    # find_packages() without include also picked up the repo's images/ folder
    # and installed a top-level "images" package into site-packages
    with open(os.path.join(ROOT, "setup.py"), encoding="utf-8") as f:
        setup = f.read()
    call = re.search(r"packages=setuptools\.find_packages\(include=(\[[^\]]*\])\)", setup)
    assert call, "packages= must use find_packages(include=[...])"
    import ast
    import fnmatch
    include = ast.literal_eval(call.group(1))
    # what find_packages(include=...) picks (no setuptools in the CI venv):
    # folders with an __init__.py under importable parents, matching a pattern
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        if rel == ".":
            continue
        if "__init__.py" not in filenames:
            dirnames[:] = []     # not a package: nothing below it is importable
            continue
        name = rel.replace(os.sep, ".")
        if any(fnmatch.fnmatchcase(name, pat) for pat in include):
            found.append(name)
    assert "images" not in found
    assert "pyfigures" in found and "pyfigures.gui" in found
    assert all(p == "pyfigures" or p.startswith("pyfigures.") for p in found), found


def test_every_extra_named_in_the_docs_exists():
    with open(os.path.join(ROOT, "setup.py"), encoding="utf-8") as f:
        setup = f.read()
    block = setup[setup.index("extras_require"):]
    extras = set(re.findall(r"^\s*'(\w+)':\s*\[", block, re.M))
    assert {"ai", "video", "fiji", "all"} <= extras
    docs = [os.path.join(ROOT, "README.md")]
    for name in os.listdir(os.path.join(ROOT, "docs")):
        if name.endswith((".md", ".html")):
            docs.append(os.path.join(ROOT, "docs", name))
    named = set()
    for p in docs:
        with open(p, encoding="utf-8") as f:
            named |= set(re.findall(r"pyfigures\[(\w+)\]", f.read()))
    assert named and not named - extras, named - extras
    # 'all' really is all the other extras — except 'omero': omero-py needs
    # zeroc-ice, which has no wheel on PyPI for Windows (and often fails to
    # build elsewhere), so it would break `pip install pyfigures[all]`; and
    # 'test' (pytest & co.), which no user feature needs
    all_block = block[block.index("'all'"):]
    all_block = all_block[:all_block.index("]")]
    assert "omero" in extras and "omero-py" not in all_block
    assert "test" in extras and "pytest" not in all_block
    for extra in extras - {"all", "omero", "test"}:
        sub = block[block.index(f"'{extra}'"):]
        for req in re.findall(r'"([^"]+)"', sub[:sub.index("]")]):
            assert f'"{req}"' in all_block, (extra, req)
