"""layout_canvas gives free-canvas panels the requested displayed width.

It wrote the scaled size into width/height, but saving re-syncs width/height
from the source file, so every panel came back at its raw size. The displayed
size is now reached through the panel's scale (displayed = raw / scale), and
the geometry is checked with the real PyFigures objects.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def _figure(tmp_path, qapp):
    from PIL import Image
    pyf = tmp_path / "canvas.pyf"
    assert not M.create_figure(str(pyf), mode="canvas").startswith("ERROR")
    for i, shape in enumerate(((100, 50), (50, 100))):
        src = tmp_path / f"panel_{i}.png"
        Image.new("RGB", shape, (30, 90, 150)).save(src)
        M.add_image(str(pyf), group_path=[], filename=str(src))
    return pyf


def _geometry(pyf):
    from batoolset.serializations.tools import deserialize_to_dict, create_object
    from batoolset.drawings.shapes.image2d import Image2D
    objects = create_object(list.__name__, deserialize_to_dict(pyf.read_text(encoding="utf-8")))
    out = []
    for obj in objects:
        if isinstance(obj, Image2D):
            rect = obj.getRect(all=True)
            out.append((round(rect.x(), 3), round(rect.y(), 3), round(rect.width(), 3), round(rect.height(), 3)))
    return out


def test_vertical_layout_has_the_requested_width(tmp_path, qapp):
    pyf = _figure(tmp_path, qapp)
    res = M.layout_canvas(str(pyf), width_px=200, spacing_px=7, direction="Y")
    assert not res.startswith("ERROR"), res
    assert _geometry(pyf) == [(0, 0, 200, 100), (0, 107, 200, 400)]


def test_horizontal_layout_keeps_sources(tmp_path, qapp):
    pyf = _figure(tmp_path, qapp)
    M.layout_canvas(str(pyf), width_px=200, spacing_px=7, direction="X")
    assert _geometry(pyf) == [(0, 0, 200, 100), (207, 0, 200, 400)]
    text = pyf.read_text(encoding="utf-8")
    assert "panel_0.png" in text and "panel_1.png" in text


def test_invalid_direction_does_not_change_the_file(tmp_path, qapp):
    pyf = _figure(tmp_path, qapp)
    before = pyf.read_bytes()
    assert M.layout_canvas(str(pyf), direction="diagonal").startswith("ERROR")
    assert pyf.read_bytes() == before
