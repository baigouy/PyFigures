"""Restyle a family of texts at once (22 Oct report: Panel letters had font
controls, other texts — labels, label rows, scale-bar legends — did not).
MCP restyle_texts, GUI Annotations → Text style…, recipe-free.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def fig(tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import (create_figure, add_image, add_annotation, set_scale_bar,
                                      add_corner_labels)
    p = str(tmp_path / "a.tif")
    Img((np.random.default_rng(0).random((60, 80)) * 255).astype(np.uint8), dimensions="hw").save(p)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], p, label="A")
    add_corner_labels(pyf, [0], 0, top_right=["WT"])
    set_scale_bar(pyf, [0], 0, 10, px_to_unit=0.5)
    return pyf


def _texts(pyf):
    from pyfigures.mcp_tools.core import _load, _decode
    _t, root = _load(pyf)
    out = {"letters": [], "texts": [], "scale_bars": []}
    for ta in root.iter("TAText2D"):
        key = "letters" if ta.findtext("is_letter") == "True" else "texts"
        out[key].append(_decode(ta.findtext("text")) or "")
    for sb in root.iter("ScaleBar"):
        out["scale_bars"].append(_decode(sb.findtext("legend")) or "")
    return out


def test_restyle_labels_only(fig):
    from pyfigures.mcp_server import restyle_texts
    r = restyle_texts(fig, "texts", font_family="Courier New", bold=True)
    assert r.startswith("Restyled 1 text(s)"), r
    t = _texts(fig)
    assert "Courier New" in t["texts"][0] and ("font-weight:700" in t["texts"][0] or "font-weight:600" in t["texts"][0])
    assert "Courier New" not in t["letters"][0] and "Courier New" not in t["scale_bars"][0]
    assert "WT" in t["texts"][0]                                 # its words kept


def test_restyle_scale_bars_and_all(fig):
    from pyfigures.mcp_server import restyle_texts
    restyle_texts(fig, "scale bars", font_size=14, color="yellow")
    t = _texts(fig)
    assert "14pt" in t["scale_bars"][0] and "#ffff00" in t["scale_bars"][0].lower()
    restyle_texts(fig, "all", italic=True)
    t = _texts(fig)
    assert all("italic" in h for h in t["letters"] + t["texts"] + t["scale_bars"])
    assert restyle_texts(fig, "everything else", bold=True).startswith("ERROR")
    assert restyle_texts(fig, "texts").startswith("Nothing changed")


def test_recipe_text_style(tmp_path):
    import json
    from PIL import Image
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    d = str(tmp_path)
    Image.fromarray((np.random.default_rng(1).random((60, 80)) * 255).astype(np.uint8)).save(
        os.path.join(d, "im.png"))
    rp = os.path.join(d, "r.json")
    with open(rp, "w") as f:
        json.dump({"output": "fig.pyf", "rows": [[{"image": "im.png", "label": "WT"}]],
                   "text_style": [{"target": "texts", "font": "Courier New", "size": 9}]}, f)
    out = build_figure_from_recipe(rp)["output"]
    assert any("Courier New" in h for h in _texts(out)["texts"])
    with open(rp, "w") as f:
        json.dump({"output": "fig.pyf", "rows": [[{"image": "im.png"}]],
                   "text_style": {"target": "texts", "weight": "bold"}}, f)
    with pytest.raises(RecipeError):
        build_figure_from_recipe(rp)


def test_gui_text_style_dialog(qapp, fig, monkeypatch):
    from qtpy.QtWidgets import QDialog
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        calls = {}

        class _Dlg:
            def __init__(self, *a, **k):
                pass

            def exec_(self):
                w = g._text_style_widgets
                w["target"].setCurrentIndex(w["target"].findData("scale_bars"))
                w["size"].setValue(11)
                w["bold"].setCurrentIndex(1)
                return QDialog.Accepted
        monkeypatch.setattr(pfgui, "CustomDialog", _Dlg)
        monkeypatch.setattr(g, "_run_mcp_mutation", lambda f, msg, **kw: calls.update(func=f.__name__, **kw))
        g.text_style_action()
        assert calls == {"func": "restyle_texts", "target": "scale_bars", "font_size": 11.0, "bold": True}
    finally:
        g._dirty = False
        g.close()
