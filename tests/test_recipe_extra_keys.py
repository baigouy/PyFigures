"""Recipe keys that no test exercised yet, each checked in the built .pyf:
montage stamps (stamps / stamp_format / stamp_placement / stamp_color /
time_zero, and stamps: false), split merge_label, kymograph cmap / mark_line /
line_color, orthogonal time_point / z_scale / crosshair_color, arrow
both_ends, plot xlabel, and the figure-wide label_background.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

RECIPE = """
output: out/fig.pyf
label_background: black
rows:
  - - {montage: movie.tif, axis: t, frames: 3, interval: 2, unit: s,
       stamp_format: "t = {value:g} {unit}", stamp_placement: bottom left,
       stamp_color: yellow, time_zero: 1}
  - - {split: rgb.tif, merge_label: "Overlay"}
  - - {image: movie.tif, kymograph: {line: [5, 5, 40, 30], cmap: magma, mark_line: true, line_color: cyan}}
  - - {image: zstack.tif, orthogonal: {at: [20, 20], time_point: 0, z_scale: 2.5, crosshair_color: magenta}}
  - - {image: a.tif, arrows: [{at: [20, 20], from: left, both_ends: true}]}
    - {plot: counts.csv, kind: box, xlabel: "genotype"}
  - - {montage: movie.tif, axis: t, frames: 2, stamps: false}
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory, qapp):
    import tifffile
    from batoolset.img import Img
    from pyfigures.recipe import build_figure_from_recipe
    d = tmp_path_factory.mktemp("recipe_keys")
    t = np.stack([np.full((40, 50), 30 * i, np.uint8) for i in range(5)])
    tifffile.imwrite(d / "movie.tif", t, imagej=True, metadata={"axes": "TYX"})
    z = np.stack([np.full((40, 50), 40 * i, np.uint8) for i in range(4)])
    tifffile.imwrite(d / "zstack.tif", z, imagej=True, metadata={"axes": "ZYX"})
    c = np.zeros((40, 50, 3), np.uint8)
    c[..., 0] = 200
    Img(c, dimensions="hwc").save(str(d / "rgb.tif"))
    Img(np.full((40, 50), 90, np.uint8), dimensions="hw").save(str(d / "a.tif"))
    (d / "counts.csv").write_text("WT,KO\n10,20\n11,22\n12,21\n")
    (d / "r.yaml").write_text(RECIPE, encoding="utf-8")
    res = build_figure_from_recipe(str(d / "r.yaml"))
    assert res["warnings"] == []
    return res, ET.parse(res["output"]).getroot()


def _texts(root):
    from qtpy.QtGui import QTextDocument
    from pyfigures.mcp_server import _decode
    out = []
    for ta in root.iter("TAText2D"):
        raw = _decode(ta.findtext("text") or "")
        doc = QTextDocument()
        doc.setHtml(raw)
        out.append((doc.toPlainText(), raw.lower(), ta.findtext("placement"), ta.findtext("fill_color")))
    return out


def _scripts(root):
    from pyfigures.mcp_server import _decode
    return [(_decode(i.findtext("custom_loading_script")) or "") for i in root.iter("Image2D")
            if i.findtext("custom_loading_script") not in (None, "None")]


def test_summary(built):
    res, _root = built
    assert (res["rows"], res["images"], res["plots"], res["stack_series"]) == (6, 3, 1, 3)


def test_montage_stamps(built):
    _res, root = built
    stamps = [t for t in _texts(root) if t[0].startswith("t = ")]
    # frames 0, 2, 4 of a 2 s interval, time zero at frame 1
    assert [s[0] for s in stamps] == ["t = -2 s", "t = 2 s", "t = 6 s"]
    assert all(s[2] == "bottom left" for s in stamps)
    assert all("#ffff00" in s[1] for s in stamps)            # stamp_color: yellow
    # the second montage has stamps: false — no more stamps than the first montage's
    assert len(stamps) == 3


def test_split_merge_label(built):
    _res, root = built
    plain = [t[0] for t in _texts(root)]
    assert "Overlay" in plain and {"Ch1", "Ch2", "Ch3"} <= set(plain)


def test_split_merge_option_is_not_a_merge_panel():
    """`merge: true/false` on a split (documented) used to be read as a second
    panel kind ("a panel needs exactly one of ...")."""
    from pyfigures.recipe import _panel_kind, RecipeError
    assert _panel_kind({"split": ["a.tif", "b.tif"], "merge": True}, "p") == "split"
    assert _panel_kind({"split": "rgb.tif", "merge": False}, "p") == "split"
    assert _panel_kind({"merge": ["a.tif", "b.tif"]}, "p") == "merge"
    with pytest.raises(RecipeError, match="exactly one"):
        _panel_kind({"split": "rgb.tif", "merge": ["a.tif", "b.tif"]}, "p")


def test_kymograph_options(built):
    _res, root = built
    kymo = next(s for s in _scripts(root) if s.startswith("# pyfigures:kymograph"))
    assert "_cmap = 'magma'" in kymo
    colors = [int(l.findtext("color")) for l in root.iter("Line2D")]
    assert 0x00FFFF in colors                                    # mark_line drawn in cyan


def test_orthogonal_options(built):
    _res, root = built
    ortho = next(s for s in _scripts(root) if s.startswith("# pyfigures:orthogonal_views"))
    assert "_zs = 2.5" in ortho and "_t = 20, 20, None, 0" in ortho.replace("_x, _y, _z, _t", "_t")
    colors = [int(l.findtext("color")) for l in root.iter("Line2D")]
    assert colors.count(0xFF00FF) >= 2                           # crosshair lines in magenta


def test_arrow_both_ends(built):
    _res, root = built
    arrows = [l for l in root.iter("Line2D") if l.findtext("arrow") == "True"]
    assert arrows and arrows[0].findtext("arrow_at_both_ends") == "True"


def test_plot_xlabel(built):
    _res, root = built
    plot = next(s for s in _scripts(root) if "from staplot import api" in s)
    assert "genotype" in plot


def test_label_background_on_image_labels_not_on_plots(built):
    _res, root = built
    texts = _texts(root)
    letters = [t for t in texts if len(t[0]) == 1 and t[0].isalpha()]
    boxed = [t for t in letters if t[3] == "0"]
    assert len(boxed) >= len(letters) - 1                       # all but the plot panel's letter
    assert all(t[3] == "0" for t in texts if t[0].startswith("t = ") or t[0] in ("Ch1", "Overlay"))
