"""Recipe keys for checking, bundling and templates: `checks` (integrity,
scale, scale_bars, labels, resolution, journal; a failing check stops the
build before the exports), the `ledger` / `colorblind` exports,
`consolidate`, `template` + `fill`, and the per-panel `properties`.

Also the bugs these found: check_image_integrity could not read any panel
file (quoted filenames), and consolidate_figure left the bundled figure
pointing at the original files.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _noise(path, seed, flip=False):
    from batoolset.img import Img
    a = (np.random.default_rng(seed).random((64, 80)) * 255).astype(np.uint8)
    Img(a[:, ::-1].copy() if flip else a, dimensions="hw").save(str(path))


def _build(d, recipe):
    from pyfigures.recipe import build_figure_from_recipe
    (d / "r.json").write_text(json.dumps(recipe), encoding="utf-8")
    return build_figure_from_recipe(str(d / "r.json"))


def _paths(pyf):
    from pyfigures import mcp_server as M
    return [i["path"] for i in json.loads(M.list_images(pyf))]


_SB = {"px_to_unit": 0.1, "scale_bar": {"units": 2}}


@pytest.fixture
def data(tmp_path, qapp):
    _noise(tmp_path / "a.tif", 1)
    _noise(tmp_path / "b.tif", 2)
    _noise(tmp_path / "a_flipped.tif", 1, flip=True)
    _noise(tmp_path / "c.tif", 3)
    _noise(tmp_path / "d1.tif", 4)
    _noise(tmp_path / "d2.tif", 5)
    return tmp_path


def test_checks_pass_and_ledger_colorblind_exports(data):
    res = _build(data, {
        "output": "out/fig.pyf",
        "rows": [[dict(image="a.tif", display_range=[10, 200], **_SB), dict(image="b.tif", **_SB)]],
        "checks": ["integrity", "scale", "scale_bars", "labels"],
        "exports": ["ledger", {"format": "colorblind", "cvd_type": "protanopia"}],
    })
    assert set(res["checks"]) == {"integrity", "scale", "scale_bars", "labels"}
    assert all(v.startswith("ok: ") for v in res["checks"].values()), res["checks"]
    assert "2 check" not in res["summary"] and "4 check(s) passed" in res["summary"]
    ledger, cb = res["exports"]
    assert ledger.endswith("fig_ledger.json") and cb.endswith("fig_colorblind.png")
    led = json.loads(open(ledger, encoding="utf-8").read())
    assert led["panels_total"] == 2 and led["panels_adjusted"] >= 1
    assert "methods_paragraph" in led
    from PIL import Image
    assert Image.open(cb).size[0] > 50


def test_failing_check_stops_before_the_exports(data):
    from pyfigures.recipe import RecipeError
    recipe = {"output": "out/fig.pyf",
              "rows": [[dict(image="a.tif", **_SB), dict(image="a_flipped.tif", **_SB)]],
              "checks": ["integrity"], "exports": ["png"]}
    with pytest.raises(RecipeError, match=r"(?s)1 check\(s\) failed.*not exported.*integrity: .*duplicate"):
        _build(data, recipe)
    assert os.path.isfile(data / "out" / "fig.pyf")          # saved, to look at
    assert not os.path.exists(data / "out" / "fig.png")       # but not exported
    # fail: false -> only a warning, and the build goes on
    recipe["checks"] = [{"check": "integrity", "fail": False, "hamming_threshold": 6}]
    res = _build(data, recipe)
    assert res["checks"]["integrity"].startswith("FAILED: ")
    assert any(w.startswith("check integrity:") for w in res["warnings"])
    assert os.path.isfile(data / "out" / "fig.png")
    assert "1 check(s) run" in res["summary"]


def test_scale_bar_and_label_checks_name_the_panel(data):
    from pyfigures.recipe import RecipeError
    recipe = {"output": "fig.pyf", "letter_panels": False,
              "rows": [[dict(image="a.tif", **_SB), "b.tif"]],
              "checks": ["scale_bars", "labels"]}
    with pytest.raises(RecipeError) as e:
        _build(data, recipe)
    msg = str(e.value)
    assert "2 check(s) failed" in msg
    assert "1 panel(s) without a scale bar" in msg and "b.tif" in msg
    assert "2 panel(s) without a label" in msg


def test_resolution_and_journal_checks(data):
    from pyfigures.recipe import RecipeError
    base = {"output": "fig.pyf", "rows": [["a.tif", "b.tif"]], "width_mm": 89}
    with pytest.raises(RecipeError, match=r"resolution: .*BELOW 300 DPI"):
        _build(data, dict(base, checks=["resolution"]))
    res = _build(data, dict(base, checks=[{"check": "resolution", "min_dpi": 20}]))
    assert res["checks"]["resolution"].startswith("ok: ")
    with pytest.raises(RecipeError, match=r"journal: \[FAIL\] resolution"):
        _build(data, dict(base, checks=["journal"]))
    res = _build(data, dict(base, checks=[{"check": "journal", "min_dpi": 20}]))
    assert res["checks"]["journal"].startswith("ok: "), res["checks"]


def test_consolidate_in_place_and_to_another_file(data):
    res = _build(data, {"output": "out/fig.pyf", "rows": [["a.tif", "b.tif"]],
                        "consolidate": True})
    files = str(data / "out" / "fig.files")
    assert res["consolidated"] == files and "files bundled" in res["summary"]
    for p in _paths(res["output"]):
        assert os.path.normcase(p).startswith(os.path.normcase(files)) and os.path.isfile(p)

    res = _build(data, {"output": "out/fig.pyf", "rows": [["a.tif", "b.tif"]],
                        "consolidate": "share/fig_share.pyf"})
    assert os.path.isfile(data / "share" / "fig_share.pyf")
    for p in _paths(str(data / "share" / "fig_share.pyf")):
        assert "fig_share.files" in p and os.path.isfile(p)
    assert [os.path.basename(p) for p in _paths(res["output"])] == ["a.tif", "b.tif"]
    assert all(os.path.dirname(p) == str(data) for p in _paths(res["output"]))


def test_template_fill(data):
    from pyfigures import mcp_server as M
    from pyfigures.recipe import RecipeError
    first = _build(data, {"output": "tpl/source.pyf",
                          "rows": [[dict(image="a.tif", **_SB), "b.tif", "c.tif"]]})
    template = str(data / "tpl" / "template.pyf")
    import shutil
    shutil.copyfile(first["output"], template)
    M.templatify_figure(template)

    res = _build(data, {"output": "fig.pyf", "template": "tpl/template.pyf",
                        "fill": ["c.tif", "d*.tif"], "exports": ["png"]})
    assert [os.path.basename(p) for p in _paths(res["output"])] == ["c.tif", "d1.tif", "d2.tif"]
    assert res["images"] == 3 and res["template"] == template and res["warnings"] == []
    # the template's letters and scale bar are kept, not added twice
    annots = json.loads(M.get_annotations(res["output"]))
    letters = sorted(a["text"] for a in annots if a["type"] == "TAText2D")
    assert letters == ["A", "B", "C"], letters
    assert sum(a["type"].startswith("scale_bar") for a in annots) == 1
    assert os.path.isfile(data / "fig.png")

    res = _build(data, {"output": "fig.pyf", "template": "tpl/template.pyf", "fill": ["c.tif"]})
    assert res["warnings"] == ["2 template slot(s) left empty"]
    with pytest.raises(RecipeError, match=r"fill: 4 file\(s\) for 3 template slot\(s\)"):
        _build(data, {"output": "fig.pyf", "template": "tpl/template.pyf",
                      "fill": ["a.tif", "b.tif", "c.tif", "d1.tif"]})


def test_properties_escape_hatch(data):
    from pyfigures import mcp_server as M
    from pyfigures.recipe import RecipeError
    res = _build(data, {"output": "fig.pyf", "rows": [[
        {"image": "a.tif", "properties": {"border_size": 3, "border_color": "0xFF0000",
                                          "opacity": 0.5}}]]})
    p = json.loads(M.list_image_properties(res["output"], [0], 0))
    assert p["border_size"] == 3 and p["opacity"] == 0.5, p
    with pytest.raises(RecipeError, match="property 'bordr_size' can't be set"):
        _build(data, {"output": "fig.pyf",
                      "rows": [[{"image": "a.tif", "properties": {"bordr_size": 3}}]]})


@pytest.mark.parametrize("patch,msg", [
    ({"checks": "integrity"}, "'checks' must be a list"),
    ({"checks": ["spelling"]}, "check 'spelling': must be one of"),
    ({"checks": [{"check": "scale", "tolerence": 1}]}, r"unknown option\(s\) \['tolerence'\]"),
    ({"checks": ["journal"]}, "check journal needs the figure's print size"),
    ({"checks": ["resolution"], "width_px": 800}, "check resolution needs the figure's print size"),
    ({"consolidate": "bundle.zip"}, "'consolidate' must be true or the .pyf"),
    ({"fill": ["a.tif"]}, "'fill' only goes with 'template'"),
    ({"exports": [{"format": "ledger", "colour": 1}]}, "allowed keys are"),
])
def test_top_key_validation(data, patch, msg):
    from pyfigures.recipe import _plan, RecipeError
    recipe = {"output": "f.pyf", "rows": [["a.tif"]]}
    recipe.update(patch)
    with pytest.raises(RecipeError, match=msg):
        _plan(recipe, str(data / "r.yaml"))


@pytest.mark.parametrize("patch,msg", [
    ({"template": "nope.pyf", "fill": ["a.tif"]}, "template: .pyf not found"),
    ({"template": "t.pyf"}, "'template' needs 'fill'"),
    ({"template": "t.pyf", "fill": ["a.tif"], "rows": [["a.tif"]]}, "give 'fill', not 'rows'"),
    ({"template": "t.pyf", "fill": ["zz*.tif"]}, "fill 1: glob 'zz\\*.tif' matched no files"),
    ({"template": "t.pyf", "fill": ["nope.tif"]}, "fill 1: file not found"),
])
def test_template_validation(data, patch, msg):
    from pyfigures.recipe import _plan, RecipeError
    (data / "t.pyf").write_text("<x/>", encoding="utf-8")
    recipe = {"output": "f.pyf"}
    recipe.update(patch)
    with pytest.raises(RecipeError, match=msg):
        _plan(recipe, str(data / "r.yaml"))


@pytest.mark.parametrize("props,msg", [
    ({}, "properties must map"),
    ({"custom_loading_script": "import os"}, "custom_loading_script can't be set"),
    ({"filename": "x.tif"}, "filename can't be set"),
    ({"bad name": 1}, "is not valid"),
    ({"opacity": {"a": 1}}, "must be a text, number"),
])
def test_properties_validation(data, props, msg):
    from pyfigures.recipe import _plan, RecipeError
    with pytest.raises(RecipeError, match=msg):
        _plan({"output": "f.pyf", "rows": [[{"image": "a.tif", "properties": props}]]},
              str(data / "r.yaml"))


_FAILING = {"output": "out/fig.pyf", "letter_panels": False,
            "rows": [["a.tif", "b.tif"]], "checks": ["scale_bars"], "exports": ["png"]}


def test_failed_checks_in_mcp_and_cli(data, capsys):
    from pyfigures import mcp_server as M
    from pyfigures.recipe import main, RecipeChecksFailed
    (data / "r.json").write_text(json.dumps(_FAILING), encoding="utf-8")
    r = M.build_figure_from_recipe(str(data / "r.json"))
    assert r.startswith("ERROR: 1 check(s) failed") and "scale_bars:" in r
    assert main(["build", str(data / "r.json")]) == 1
    assert "2 panel(s) without a scale bar" in capsys.readouterr().err
    with pytest.raises(RecipeChecksFailed) as e:
        _build(data, _FAILING)
    assert e.value.output == str(data / "out" / "fig.pyf")
    assert e.value.checks["scale_bars"].startswith("FAILED: ")


def test_gui_opens_the_figure_when_checks_fail(data, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    shown = {}
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: shown.update(title=a[1], err=a[2])))
    (data / "r.json").write_text(json.dumps(_FAILING), encoding="utf-8")
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda **k: str(data / "r.json"))
    g = EZFIG_GUI()
    g.build_from_recipe_action()
    assert shown["title"] == "Recipe checks failed" and "scale bar" in shown["err"]
    assert g.current_file == str(data / "out" / "fig.pyf")
    assert len(g.paint.EZFIG_panel.shapes_to_draw) >= 1
    g._dirty = False


def test_integrity_check_reads_the_panel_files(data):
    """It used to join the quoted stored name to the figure folder, so every
    panel was a 'load error' and the check always reported no issues."""
    from pyfigures import mcp_server as M
    res = _build(data, {"output": "out/fig.pyf", "rows": [["a.tif", "a_flipped.tif"]]})
    r = json.loads(M.check_image_integrity(res["output"]))
    assert r["load_errors"] == [] and r["panels_analyzed"] == 2
    assert r["cross_panel_duplicates"], r
