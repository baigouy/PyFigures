"""One call recolours the whole figure ("use magenta and green"): every model
in the 19 October sweep, Codex included, recoloured only part of Figure 3."""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

M = pytest.importorskip("pyfigures.mcp_server")


@pytest.fixture
def fig3(tmp_path, qapp):
    from PIL import Image
    rng = np.random.default_rng(0)
    for name in ("cells.png", "other.png"):
        # fluorescence-like: dark background, bright spots
        Image.fromarray((rng.random((60, 80, 3)) ** 4 * 255).astype(np.uint8)).save(tmp_path / name)
    (tmp_path / "m.csv").write_text("Control,Treated\n1,2\n2,3\n3,4\n", encoding="utf-8")
    return tmp_path


RECIPE = ("output: f.pyf\nletter_panels: false\nrows:\n"
          "  - - {split: cells.png, names: [Lamp1, Mito, DNA], merge: true}\n"
          "  - - other.png\n    - {plot: m.csv, kind: box}\n")


def _panels(pyf):
    root = ET.parse(pyf).getroot()
    return list(root.iter("Image2D"))


def test_set_figure_colors_recolours_images_merges_and_plots(fig3):
    res = M.build_figure_from_recipe(str(fig3 / "r.yaml"), recipe_text=RECIPE)
    assert not res.startswith("ERROR"), res
    pyf = str(fig3 / "f.pyf")
    r = M.set_figure_colors(pyf, ["magenta", "green"])
    assert "2 multi-channel image(s)" in r and "1 data plot(s)" in r, r
    p = _panels(pyf)
    merge, other, plot = p[3], p[4], p[5]
    assert merge.findtext("LUTs") == "['MAGENTA', 'GREEN', 'BLUE']"
    assert other.findtext("LUTs") == "['MAGENTA', 'GREEN', 'BLUE']"    # RGB micrograph
    from pyfigures.mcp_tools.core import _decode
    script = _decode(plot.findtext("custom_loading_script"))
    assert "colors=['#ff40ff', '#40ff40']" in script, script
    # the Lamp1 single follows its merge (tint or legend colour)
    lamp1 = ET.tostring(p[0], encoding="unicode").upper()
    assert "MAGENTA" in lamp1 or "FF40FF" in lamp1
    # what ChatGPT's verifier checks for "use magenta and green"
    for q in (merge, other):
        assert "MAGENTA" in q.findtext("LUTs") and "GREEN" in q.findtext("LUTs")
    # the figure still renders
    assert not isinstance(M.render_preview(pyf), str)


def test_single_channel_gray_photographs_kept_and_plot_palettes(fig3):
    """The author's rules: one channel reads best in gray; magenta/green only
    for two-group plots, else a colour-blind-safe palette; a colour photograph
    is not a set of channels."""
    from PIL import Image
    from pyfigures.mcp_tools.content import OKABE_ITO
    from pyfigures.mcp_tools.core import _decode
    Image.new("L", (40, 30), 90).save(fig3 / "mono.png")
    Image.new("RGB", (40, 30), (230, 200, 190)).save(fig3 / "he_stain.png")    # bright field
    (fig3 / "three.csv").write_text("A,B,C\n1,2,3\n2,3,4\n", encoding="utf-8")
    res = M.build_figure_from_recipe(str(fig3 / "r.yaml"), recipe_text=(
        "output: f.pyf\nletter_panels: false\nrows:\n"
        "  - - {image: mono.png, lut: red}\n    - he_stain.png\n"
        "    - {plot: three.csv, kind: bar}\n    - {plot: m.csv, kind: box}\n"))
    assert not res.startswith("ERROR"), res
    pyf = str(fig3 / "f.pyf")
    r = M.set_figure_colors(pyf, ["magenta", "green"])
    assert "set to gray" in r and "he_stain.png" in r and "Okabe-Ito" in r, r
    mono, he, three, two = _panels(pyf)
    assert mono.findtext("LUTs") == "['GRAY']"
    assert "MAGENTA" not in (he.findtext("LUTs") or "")
    assert f"colors={OKABE_ITO[:3]!r}" in _decode(three.findtext("custom_loading_script"))
    assert "colors=['#ff40ff', '#40ff40']" in _decode(two.findtext("custom_loading_script"))
    # keep: the single channel keeps its LUT
    M.set_lut(pyf, [0], 0, ["RED"])
    M.set_figure_colors(pyf, ["magenta", "green"], single_channel="keep")
    assert _panels(pyf)[0].findtext("LUTs") == "['RED']"
    # "make it colour-blind friendly": Okabe-Ito for every plot, even two groups
    r = M.set_figure_colors(pyf, ["colorblind"])
    assert f"colors={OKABE_ITO[:2]!r}" in _decode(_panels(pyf)[3].findtext("custom_loading_script")), r
    res = M.build_figure_from_recipe(str(fig3 / "c.yaml"), recipe_text=(
        RECIPE.replace("f.pyf", "c.pyf") + "colors: [colour-blind]\n"))
    assert not res.startswith("ERROR"), res


def test_bad_colours_change_nothing(fig3):
    M.build_figure_from_recipe(str(fig3 / "r.yaml"), recipe_text=RECIPE)
    pyf = str(fig3 / "f.pyf")
    before = open(pyf, encoding="utf-8").read()
    r = M.set_figure_colors(pyf, ["mauve"])
    assert r.startswith("ERROR") and "mauve" in r
    assert open(pyf, encoding="utf-8").read() == before


def test_recipe_colors_key_and_plot_colors(fig3):
    res = M.build_figure_from_recipe(str(fig3 / "r.yaml"),
                                     recipe_text=RECIPE + "colors: [magenta, green]\n")
    assert not res.startswith("ERROR"), res
    p = _panels(str(fig3 / "f.pyf"))
    assert p[3].findtext("LUTs") == "['MAGENTA', 'GREEN', 'BLUE']"
    bad = M.build_figure_from_recipe(str(fig3 / "b.yaml"),
                                     recipe_text=RECIPE.replace("f.pyf", "b.pyf")
                                     + "colors: magenta\n")
    assert bad.startswith("ERROR") and "colors: [magenta, green]" in bad
    # one plot's own colours
    res = M.add_data_plot(str(fig3 / "f.pyf"), [1], str(fig3 / "m.csv"), kind="bar",
                          colors=["cyan", "#123456"])
    assert not res.startswith("ERROR"), res
    assert M.add_data_plot(str(fig3 / "f.pyf"), [1], str(fig3 / "m.csv"),
                           colors=["notacolour"]).startswith("ERROR")


def test_old_plot_scripts_without_colors_get_them():
    from pyfigures.mcp_tools.content import _recolour_plot_script
    old = "    fig, _rec = _api.plot(_tbl, kind='box', error='sem',\n"
    assert "colors=['#ff40ff']," in _recolour_plot_script(old, ["#ff40ff"])
    new = "_api.plot(_tbl, kind='box', colors=None, title='')"
    assert _recolour_plot_script(new, ["#ff40ff"]) == \
        "_api.plot(_tbl, kind='box', colors=['#ff40ff'], title='')"


def test_gui_figure_colours_action(fig3, monkeypatch):
    from pyfigures.gui import pfgui
    calls = {}
    offered = []
    # an editable combo of presets (was a bare text field)
    monkeypatch.setattr(pfgui.QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: offered.append((a[3], a[5])) or ("magenta, green", True)))

    class Win:
        def _run_mcp_mutation(self, func, msg, **kw):
            calls.update(func=func.__name__, **kw)

    pfgui.PyFigures.figure_colors_action(Win()) if hasattr(pfgui, "PyFigures") else \
        _main_window_class(pfgui).figure_colors_action(Win())
    assert calls == {"func": "set_figure_colors", "colors": ["magenta", "green"]}
    presets, editable = offered[0]
    assert editable is True and "colorblind" in presets and len(presets) >= 6
    from pyfigures.mcp_tools.stacks import _COLOR_LUTS
    for p in presets:                    # every preset is accepted by set_figure_colors
        assert p == "colorblind" or all(c.strip() in _COLOR_LUTS for c in p.split(",")), p


def _main_window_class(pfgui):
    return next(v for v in vars(pfgui).values()
                if isinstance(v, type) and hasattr(v, "figure_colors_action"))
