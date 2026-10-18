"""The generic property setters never report success for a change they did not make.

set_inset_property(..., "size_fraction", "0.4") wrote an unused XML field and
replied success, while the inset kept its 0.25 width (list_insets itself names
the field "size_fraction"). Unknown names are now rejected without touching the
file, friendly names map to the stored field, out-of-range values are refused,
and the reply gives the value read back from the saved file.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")
FRACTION = "fraction_of_parent_image_width_if_image_is_inset"


@pytest.fixture
def fig(tmp_path, qapp):
    from PIL import Image
    img = tmp_path / "cells.png"
    Image.new("L", (80, 60), 128).save(img)
    pyf = tmp_path / "inset.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(img))
    M.add_inset(str(pyf), [0], 0, str(img), size_fraction=0.25)
    return pyf


def _fractions(pyf):
    return [float(e.text) for e in ET.parse(pyf).getroot().iter(FRACTION) if e.text not in (None, "None")]


def test_size_fraction_alias_changes_the_real_fraction(fig):
    res = M.set_inset_property(str(fig), [0], 0, 0, "size_fraction", "0.4")
    assert not res.startswith("ERROR"), res
    assert 0.4 in _fractions(fig)
    assert "0.4" in res and FRACTION in res
    listed = M.list_insets(str(fig), [0], 0)
    assert '"size_fraction": 0.4' in listed


def test_unknown_property_is_rejected_and_file_unchanged(fig):
    before = fig.read_bytes()
    res = M.set_inset_property(str(fig), [0], 0, 0, "size_fractoin", "0.4")
    assert res.startswith("ERROR") and "size_fraction" in res
    assert fig.read_bytes() == before
    res = M.set_image_property(str(fig), [0], 0, "brightness", "2")
    assert res.startswith("ERROR")
    assert fig.read_bytes() == before


def test_out_of_range_fraction_is_rejected(fig):
    before = fig.read_bytes()
    assert M.set_inset_property(str(fig), [0], 0, 0, "size_fraction", "1.5").startswith("ERROR")
    assert M.set_image_property(str(fig), [0], 0, "opacity", "3").startswith("ERROR")
    assert fig.read_bytes() == before


def test_image_setter_reports_stored_value_and_accepts_aliases(fig):
    res = M.set_image_property(str(fig), [0], 0, "rotation", "45")
    assert not res.startswith("ERROR"), res
    assert "theta = 45" in res
    assert M.get_image_property(str(fig), [0], 0, "theta").strip().startswith("45")
