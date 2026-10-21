"""2026-10-08 audit: recipe rebuild sidecars, series scale bars, strict recipe
values, CLI render status, channel-split frame check, UNC / moved sources,
unit names, and the staplot row-pairing fix as seen from a PyFigures scatter.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def proj(tmp_path):
    from PIL import Image
    import tifffile
    d = str(tmp_path)
    Image.fromarray(np.full((40, 60), 100, np.uint8)).save(os.path.join(d, "wt.png"))
    with open(os.path.join(d, "counts.csv"), "w") as f:
        f.write("WT,KO\n10,20\n11,22\n12,21\n9,23\n")
    with open(os.path.join(d, "xy.csv"), "w") as f:
        f.write("x,y\n1,2\n2,\n3,6\n4,8\n5,10\n")
    tifffile.imwrite(os.path.join(d, "tc.tif"),
                     np.random.default_rng(0).integers(0, 255, (3, 2, 32, 32), dtype=np.uint8),
                     imagej=True, metadata={"axes": "TCYX"})
    return d


def _recipe(d, name, obj):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return p


def _stats(pyf):
    from pyfigures.mcp_tools.core import _stats_sidecar_path
    p = _stats_sidecar_path(pyf)
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else []


def test_rebuild_does_not_accumulate_stats(proj):
    from pyfigures.recipe import build_figure_from_recipe
    rp = _recipe(proj, "r.json", {"output": "f.pyf", "rows": [[
        {"image": "wt.png"}, {"plot": "counts.csv", "kind": "box"}]]})
    for _ in range(3):
        out = build_figure_from_recipe(rp)["output"]
    assert len(_stats(out)) == 1
    _recipe(proj, "r.json", {"output": "f.pyf", "rows": [[{"image": "wt.png"}]]})
    build_figure_from_recipe(rp)
    assert _stats(out) == []                       # the removed plot's test is gone


def test_defaults_scale_bar_reaches_montage_and_split_last_panel(proj):
    from pyfigures.recipe import build_figure_from_recipe
    rp = _recipe(proj, "r.json", {
        "output": "f.pyf", "defaults": {"px_to_unit": 0.1, "scale_bar": {"units": 1}},
        "rows": [[{"image": "wt.png"}],
                 [{"montage": "tc.tif", "frames": 3, "columns": 2}],
                 [{"split": "tc.tif"}]]})
    out = build_figure_from_recipe(rp)["output"]
    root = ET.parse(out).getroot()
    bars = [img.find("annotations/ScaleBar") is not None for img in root.iter("Image2D")]
    # image | montage t0 t1 (row 1) t2 + empty padding panel (row 2) | split ch1 ch2 merge
    assert bars == [True, False, False, True, False, False, False, True]


@pytest.mark.parametrize("bad, msg", [
    ({"letter_panels": "false"}, "true or false"),
    ({"spacing": "wide"}, "spacing"),
    ({"spacing": True}, "spacing"),
    ({"rows": [[{"image": "wt.png", "crop": {"left": True}}]]}, "crop"),
])
def test_strict_recipe_values(proj, bad, msg):
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    obj = {"output": "f.pyf", "rows": [[{"image": "wt.png"}]]}
    obj.update(bad)
    with pytest.raises(RecipeError, match=msg):
        build_figure_from_recipe(_recipe(proj, "r.json", obj))


def test_label_text_is_escaped_unless_html(proj):
    from pyfigures.recipe import _label_html
    assert _label_html("p < 0.05 & more") == "<font color=#ffffff>p &lt; 0.05 &amp; more</font>"
    assert _label_html("<i>unc-5</i>") == "<i>unc-5</i>"


def test_cli_fails_when_render_fails(proj, capsys):
    from pyfigures.recipe import main
    ok = _recipe(proj, "ok.json", {"output": "ok.pyf", "rows": [[{"image": "wt.png"}]]})
    assert main(["build", ok, "--render", "notaformat"]) == 1
    assert "render" in capsys.readouterr().err
    assert main(["build", ok, "--render", "png"]) == 0
    assert os.path.isfile(os.path.join(proj, "ok.png"))


def test_cli_continues_after_unexpected_error(proj, monkeypatch, capsys):
    from pyfigures import recipe
    good = _recipe(proj, "good.json", {"output": "g.pyf", "rows": [[{"image": "wt.png"}]]})
    real = recipe.build_figure_from_recipe
    calls = []

    def flaky(rp):
        calls.append(rp)
        if len(calls) == 1:
            raise KeyError("boom")
        return real(rp)
    monkeypatch.setattr(recipe, "build_figure_from_recipe", flaky)
    assert recipe.main(["build", good, good]) == 1
    assert len(calls) == 2 and "unexpected KeyError" in capsys.readouterr().err


def test_channel_split_frame_out_of_range(proj):
    from pyfigures.mcp_server import create_figure, add_channel_split
    f = os.path.join(proj, "f.pyf")
    create_figure(f)
    res = add_channel_split(f, stack_path=os.path.join(proj, "tc.tif"), frame=99)
    assert res.startswith("ERROR") and "0..2" in res


def test_scatter_panel_statistics_pair_rows(proj):
    from pyfigures.mcp_server import create_figure, add_group, add_data_plot
    f = os.path.join(proj, "s.pyf")
    create_figure(f)
    add_group(f, orientation="X")
    add_data_plot(f, [0], os.path.join(proj, "xy.csv"), kind="scatter")
    rec = _stats(f)[-1]
    assert rec["n"] == 4 and rec["r"] == pytest.approx(1.0)


def test_sources_keep_unc_and_unescape_script_literals(tmp_path):
    from pyfigures.source_snapshot import _script_literal, figure_sources
    assert _script_literal("", "'", r"\\\\server\\share\\a.tif") == r"\\server\share\a.tif"
    assert _script_literal("r", "'", r"C:\data\a.tif") == r"C:\data\a.tif"
    # a filename field is used verbatim (no backslash collapsing)
    real = tmp_path / "a.png"
    real.write_bytes(b"x")
    root = ET.fromstring(f'<list><Image2D><filename>""{real}""</filename></Image2D></list>')
    assert figure_sources(root) == [str(real)]


def test_sources_follow_a_moved_figure(tmp_path):
    from pyfigures.source_snapshot import figure_sources
    new = tmp_path / "exp"
    new.mkdir()
    (new / "a.png").write_bytes(b"x")
    pyf = new / "f.pyf"
    pyf.write_text('<list><Image2D><filename>""/home/me/old/exp/a.png""</filename></Image2D></list>',
                   encoding="utf-8")
    assert [os.path.normcase(p) for p in figure_sources(str(pyf))] == \
        [os.path.normcase(str(new / "a.png"))]


@pytest.mark.parametrize("raw, unit", [("micron", "µm"), ("microns", "µm"), ("um", "µm"),
                                       ("\\u00B5m", "µm"), ("nm", "nm"), ("mm", "mm")])
def test_unit_names(raw, unit):
    from pyfigures.stack_info import _norm_unit
    assert _norm_unit(raw) == unit
