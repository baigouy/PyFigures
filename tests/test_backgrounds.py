"""Figure background (gaps between panels), label background boxes and the
letter staying in its corner above a label sharing it — MCP, recipe and GUI.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _png(path, h=40, w=60):
    from PIL import Image
    ramp = np.tile(np.linspace(0, 255, w).astype(np.uint8), (h, 1))
    Image.fromarray(ramp).save(path)
    return path


def _figure(d, label="WT"):
    from pyfigures.mcp_server import create_figure, add_group, add_image
    from pyfigures.mcp_tools.workflow import _finalize_draft
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf)
    add_group(pyf, orientation="X")
    add_image(pyf, [0], _png(os.path.join(d, "a.png")), label=label)
    add_image(pyf, [0], _png(os.path.join(d, "b.png")))
    _finalize_draft(pyf, True, "top left", None, None, "")
    return pyf


def _texts(pyf, panel=0):
    root = ET.parse(pyf).getroot()
    img = list(root.find("Group").find("content").iter("Image2D"))[panel]
    return img.find("annotations").findall("TAText2D")


def test_letter_goes_first_so_it_keeps_the_corner(tmp_path):
    texts = _texts(_figure(str(tmp_path)))
    assert texts[0].findtext("is_letter") == "True"          # letter, then "WT"
    assert "WT" in texts[1].findtext("text")


def test_set_label_background(tmp_path):
    from pyfigures.mcp_server import set_label_background
    pyf = _figure(str(tmp_path))
    out = set_label_background(pyf, "black")
    assert not out.startswith("ERROR"), out
    assert all(t.findtext("fill_color") == "0" for t in _texts(pyf))
    font_bg = ET.parse(pyf).getroot().find("SerializableQFont").findtext("background")
    assert font_bg == "0"                                    # GUI re-letters with it
    set_label_background(pyf, "none", include_letters=False)
    fills = {t.findtext("is_letter"): t.findtext("fill_color") for t in _texts(pyf)}
    assert fills == {"True": "0", "False": "None"}
    assert set_label_background(pyf, "not-a-colour").startswith("ERROR")


def test_page_background_fills_the_gaps(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import set_figure_properties, export_figure
    pyf = _figure(str(tmp_path))
    png = str(tmp_path / "none.png")
    export_figure(pyf, png, dpi=72)
    a = np.asarray(Image.open(png).convert("RGBA"))
    gap = a[a.shape[0] // 2, :, 3] == 0                      # transparent gap column(s)
    assert gap.any()
    assert not set_figure_properties(pyf, page_background="red").startswith("ERROR")
    gui = ET.parse(pyf).getroot().find("SerializableGUIparameters")
    assert gui.findtext("background") == str(0xFF0000)
    png2 = str(tmp_path / "red.png")
    export_figure(pyf, png2, dpi=72)
    b = np.asarray(Image.open(png2).convert("RGBA"))
    row = b[b.shape[0] // 2]
    assert (row[gap] == [255, 0, 0, 255]).all()              # gaps now red, opaque
    set_figure_properties(pyf, page_background="none")
    assert ET.parse(pyf).getroot().find("SerializableGUIparameters").findtext("background") == "None"


def test_recipe_background_keys(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    d = str(tmp_path)
    _png(os.path.join(d, "a.png"))
    rp = os.path.join(d, "r.yaml")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("output: f.pyf\nbackground: white\nlabel_background: black\n"
                "rows:\n  - - {image: a.png, label: WT}\n    - {image: a.png}\n")
    res = build_figure_from_recipe(rp)
    root = ET.parse(res["output"]).getroot()
    assert root.find("SerializableGUIparameters").findtext("background") == str(0xFFFFFF)
    texts = _texts(res["output"])
    assert texts[0].findtext("is_letter") == "True"
    assert all(t.findtext("fill_color") == "0" for t in texts)
    assert "#ffffff" in texts[1].findtext("text").lower()      # label white like letters
    with open(rp, "w", encoding="utf-8") as f:
        f.write("output: f.pyf\nbackground: nocolour\nrows:\n  - - {image: a.png}\n")
    with pytest.raises(RecipeError, match="background"):
        build_figure_from_recipe(rp)


def test_gui_page_background_round_trip(qapp, monkeypatch, tmp_path):
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import set_figure_properties
    EZFIG_GUI.show_tips = lambda self: None
    pyf = _figure(str(tmp_path))
    set_figure_properties(pyf, page_background="#123456")
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    assert g.paint.EZFIG_panel.page_background == 0x123456
    g._choose_page_background(0xFFFFFF)
    assert g._dirty
    out = str(tmp_path / "saved.pyf")
    g._save_state_to_file(out)
    saved = ET.parse(out).getroot().find("SerializableGUIparameters")
    assert saved.findtext("background") == str(0xFFFFFF)
    g._choose_page_background(None)
    assert g.paint.EZFIG_panel.page_background is None
    g._dirty = False
