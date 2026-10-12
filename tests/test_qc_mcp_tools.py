"""MCP QC tools that had no test: check_resolution, enforce_min_font_size,
apply_journal_guidelines and list_fonts (each also reachable from the GUI's QC
menu — tests/test_qc_gui.py — and, for journals, the recipe's ``journal:``).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import mcp_server as M


def _tif(path, shape, val=100):
    from batoolset.img import Img
    Img(np.full(shape, val, np.uint8), dimensions="hw").save(str(path))
    return str(path)


@pytest.fixture
def fig(tmp_path):
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    M.add_image(pyf, [0], _tif(tmp_path / "small.tif", (100, 120)))      # 120 px wide
    M.add_image(pyf, [0], _tif(tmp_path / "big.tif", (1500, 1800)))      # 1800 px wide
    M.add_image(pyf, [1], _tif(tmp_path / "mid.tif", (600, 600)))
    M.add_annotation(pyf, [0], 0, '<span style="font-size:4pt">tiny</span>')
    return pyf


def _dpis(report):
    return {m.group(1): (m.group(2), int(m.group(3))) for m in re.finditer(
        r"\[(?:ok|FAIL)\].*?\((\w+)\.tif\).*?-> \[?(ok|FAIL)?.*?(\d+) DPI", report)} or \
        {m.group(1): int(m.group(2)) for m in re.finditer(r"\((\w+)\.tif\).*?(\d+) DPI", report)}


def test_check_resolution_flags_soft_panels(fig):
    rep = M.check_resolution(fig, min_dpi=300, journal="nature", column="double")
    assert rep.startswith("Resolution check at")
    lines = {re.search(r"\((\w+)\.tif\)", l).group(1): l for l in rep.splitlines() if ".tif)" in l}
    assert set(lines) == {"small", "big", "mid"}
    assert "[FAIL]" in lines["small"] and "[ok]" in lines["big"]
    assert "BELOW 300 DPI" in rep


def test_check_resolution_dpi_scales_with_print_width(fig):
    def dpi(rep, name):
        line = next(l for l in rep.splitlines() if f"({name}.tif)" in l)
        return int(re.search(r"(\d+) DPI", line.split("->")[-1]).group(1))
    wide = M.check_resolution(fig, width_mm=180)
    narrow = M.check_resolution(fig, width_mm=90)
    assert dpi(narrow, "big") == pytest.approx(2 * dpi(wide, "big"), rel=0.02)
    # same width in another unit: same numbers (only the header names the unit)
    assert M.check_resolution(fig, width_cm=9).splitlines()[1:] == narrow.splitlines()[1:]
    assert M.check_resolution(fig, width_in=90 / 25.4).splitlines()[1:] == narrow.splitlines()[1:]


def test_check_resolution_errors(fig, tmp_path):
    assert M.check_resolution(fig, journal="no-such-journal").startswith("ERROR")
    empty = str(tmp_path / "empty.pyf")
    M.create_figure(empty, mode="groups", num_groups=1, orientation="X", spacing=3)
    assert M.check_resolution(empty, width_mm=80).startswith("No raster panels")


def _font_sizes(pyf):
    _tree, root = M._load(pyf)
    fig_size = root.find("SerializableQFont").find("size").text
    html = " ".join(M._decode(t.find("text").text) for t in root.iter("TAText2D")
                    if t.find("text") is not None and t.find("text").text)
    return float(fig_size), [float(x) for x in re.findall(r"font-size:\s*([\d.]+)pt", html)]


def test_enforce_min_font_size(fig):
    out = M.enforce_min_font_size(fig, min_pt=7, font_family="Arial")
    assert out.startswith("Enforced")
    fig_pt, ann = _font_sizes(fig)
    assert fig_pt >= 7 and ann and min(ann) >= 7
    _tree, root = M._load(fig)
    assert "Arial" in M._decode(root.find("SerializableQFont").find("family").text)
    assert M.enforce_min_font_size(fig, min_pt=7).startswith("All fonts already")   # idempotent


def test_apply_journal_guidelines(fig):
    out = M.apply_journal_guidelines(fig, journal="nature", column="single", add_panel_labels=True,
                                     scale_bar_units=10, scale_bar_px_to_unit=0.1, min_font_pt=8)
    assert out.startswith("Applied journal guidelines")
    assert "panel labels: added 2" in out and "scale bars" in out
    fig_pt, ann = _font_sizes(fig)
    assert fig_pt >= 8 and min(ann) >= 8
    _tree, root = M._load(fig)
    assert len(list(root.iter("ScaleBar"))) >= 3
    labels = [M._decode(t.find("text").text) for t in root.iter("TAText2D")
              if t.find("text") is not None and t.find("text").text]
    assert any(">a<" in l for l in labels) and any(">b<" in l for l in labels)
    assert "resize:" in out and "ERROR" not in out.split("\n\n")[0]
    assert M.apply_journal_guidelines(fig, journal="nope").startswith("ERROR")


def test_label_letters_continue_like_a_spreadsheet():
    from pyfigures.mcp_tools.qc import _increment_label_letter as inc
    assert [inc(x) for x in ("a", "y", "z", "az", "zz", "")] == ["b", "z", "aa", "ba", "aaa", "a"]


def test_list_fonts():
    d = json.loads(M.list_fonts())
    for key in ("bundled_families", "fonts_dir", "portable_clones_available"):
        assert key in d, d.keys()
    assert os.path.isdir(d["fonts_dir"])
    assert isinstance(d["bundled_families"], list)
