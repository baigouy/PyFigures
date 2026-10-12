"""
Tests for the integrity / statistics / journal-preset additions to the
PyFigures MCP server:

  * check_image_integrity  -> pyfigures.gui.integrity_ops.analyze()
  * add_significance_bracket
  * list_journal_presets

The integrity tests build tiny synthetic PNG panels (no external sample files),
so they run anywhere cv2 + numpy are available.
"""
from __future__ import annotations

import json
import os
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

cv2 = pytest.importorskip("cv2")

from pyfigures.gui import integrity_ops  # noqa: E402
import pyfigures.mcp_server as M  # noqa: E402


def _write_pyf(paths, tmp):
    root = ET.Element("list")
    for p in paths:
        img = ET.SubElement(root, "Image2D")
        ET.SubElement(img, "filename").text = p
    pyf = os.path.join(tmp, "fig.pyf")
    ET.ElementTree(root).write(pyf, encoding="unicode")
    return pyf


def test_integrity_detects_exact_and_transformed_reuse():
    tmp = tempfile.mkdtemp()
    rng = np.random.default_rng(0)
    a = (rng.random((180, 180)) * 255).astype(np.uint8)
    pa = os.path.join(tmp, "a.png"); cv2.imwrite(pa, a)
    pb = os.path.join(tmp, "b.png"); cv2.imwrite(pb, a)              # same content
    pc = os.path.join(tmp, "c.png"); cv2.imwrite(pc, np.fliplr(a))  # flipped reuse
    pyf = _write_pyf([pa, pb, pc], tmp)

    rep = integrity_ops.analyze(pyf, max_dim=256)
    assert rep["panels_analyzed"] == 3

    reuse = {(x["a"], x["b"]) for x in rep["exact_file_duplicates"]}
    reuse |= {(x["a"], x["b"]) for x in rep["cross_panel_duplicates"]}
    assert (0, 1) in reuse                       # a/b duplication caught

    cross = {(x["a"], x["b"]): x for x in rep["cross_panel_duplicates"]}
    assert (0, 2) in cross                        # flipped reuse caught
    assert cross[(0, 2)]["transform"] == "fliplr"


def test_integrity_detects_copy_move_clone():
    tmp = tempfile.mkdtemp()
    rng = np.random.default_rng(3)
    d = (rng.random((200, 200)) * 255).astype(np.uint8)
    e = d.copy()
    e[120:160, 130:170] = e[10:50, 10:50]         # copy-move a textured patch
    pd = os.path.join(tmp, "d.png"); cv2.imwrite(pd, d)
    pe = os.path.join(tmp, "e.png"); cv2.imwrite(pe, e)
    pyf = _write_pyf([pd, pe], tmp)

    rep = integrity_ops.analyze(pyf, max_dim=256)
    cloned = {c["panel"] for c in rep["within_panel_clones"]}
    assert 1 in cloned                            # panel e has the clone
    # the untouched panel d should not be flagged as internally cloned
    assert 0 not in cloned


def test_integrity_clean_figure_has_no_flags():
    tmp = tempfile.mkdtemp()
    rng = np.random.default_rng(7)
    paths = []
    for i in range(3):
        img = (rng.random((160, 160)) * 255).astype(np.uint8)
        p = os.path.join(tmp, f"p{i}.png"); cv2.imwrite(p, img); paths.append(p)
    pyf = _write_pyf(paths, tmp)
    rep = integrity_ops.analyze(pyf, max_dim=256)
    assert rep["flag_count"] == 0
    assert "No integrity issues" in rep["summary"]


def test_list_journal_presets():
    data = json.loads(M.list_journal_presets())
    assert "nature" in data["journals"]
    nat = data["journals"]["nature"]["widths_mm"]
    assert nat["single"] == 89 and nat["double"] == 183
    # aliases resolve
    assert any("nature communications" in v["aliases"]
               for v in data["journals"].values())


def test_add_significance_bracket_adds_lines_and_free_label():
    tmp = tempfile.mkdtemp()
    # one real panel so the ROI container exists
    img = (np.random.default_rng(1).random((120, 200)) * 255).astype(np.uint8)
    p = os.path.join(tmp, "bars.png"); cv2.imwrite(p, img)
    pyf = _write_pyf([p], tmp)

    msg = M.add_significance_bracket(pyf, [], 0, x1=20, x2=180, y=30, label="***")
    assert "Significance bracket" in msg

    root = ET.parse(pyf).getroot()
    imgs = [e for e in root.iter("Image2D")]
    annots = imgs[0].find("annotations")
    lines = [e for e in annots if e.tag == "Line2D"]
    texts = [e for e in annots if e.tag == "TAText2D"]
    assert len(lines) == 3                         # bar + 2 whiskers
    assert len(texts) == 1
    assert (texts[0].findtext("placement") or "").strip() == "None"  # free-positioned


def test_add_significance_bracket_escapes_plain_label():
    tmp = tempfile.mkdtemp()
    img = (np.random.default_rng(2).random((120, 200)) * 255).astype(np.uint8)
    p = os.path.join(tmp, "bars.png"); cv2.imwrite(p, img)
    pyf = _write_pyf([p], tmp)

    M.add_significance_bracket(pyf, [], 0, x1=20, x2=180, y=30, label="p<0.001")
    root = ET.parse(pyf).getroot()
    txt = next(t.findtext("text") for t in root.iter("TAText2D")
               if (t.findtext("placement") or "").strip() == "None")
    assert "p&lt;0.001" in txt                     # '<' HTML-escaped


def test_add_significance_bracket_bad_whisker_dir():
    tmp = tempfile.mkdtemp()
    img = (np.random.default_rng(4).random((80, 120)) * 255).astype(np.uint8)
    p = os.path.join(tmp, "x.png"); cv2.imwrite(p, img)
    pyf = _write_pyf([p], tmp)
    out = M.add_significance_bracket(pyf, [], 0, x1=1, x2=2, y=3,
                                     whiskers_point="sideways")
    assert out.startswith("ERROR")


# --- adjustment provenance ledger -------------------------------------------
def _write_pyf_fields(specs, tmp):
    """specs: list of dicts of Image2D child tag -> text (plus optional _lbl)."""
    root = ET.Element("list")
    for i, spec in enumerate(specs):
        e = ET.SubElement(root, "Image2D")
        ET.SubElement(e, "filename").text = '""%s""' % spec.get("_file", f"p{i}.tif")
        lbl = spec.pop("_lbl", "")
        spec.pop("_file", None)
        for k, v in spec.items():
            ET.SubElement(e, k).text = v
        ann = ET.SubElement(e, "annotations"); t = ET.SubElement(ann, "TAText2D")
        ET.SubElement(t, "is_letter").text = "True"
        ET.SubElement(t, "text").text = lbl
    pyf = os.path.join(tmp, "fig.pyf")
    ET.ElementTree(root).write(pyf, encoding="unicode")
    return pyf


def test_adjustment_ledger_detects_types_and_clean_panel():
    tmp = tempfile.mkdtemp()
    pyf = _write_pyf_fields([
        {"_lbl": "a"},                                        # untouched
        {"_lbl": "b", "crop_left": "20", "theta": "90",
         "normalization": "{'min_value': 120, 'max_value': 4000}",
         "LUTs": '""Fire""'},
    ], tmp)
    data = json.loads(M.export_adjustment_ledger(pyf))
    assert data["panels_total"] == 2
    assert data["panels"][0]["adjustments"] == []
    types_b = {a["type"] for a in data["panels"][1]["adjustments"]}
    assert {"crop", "rotation", "brightness_contrast", "lut"} <= types_b
    assert "Panel a: no adjustments" in data["methods_paragraph"]


def test_adjustment_ledger_flags_custom_script_and_inconsistent_ranges():
    tmp = tempfile.mkdtemp()
    pyf = _write_pyf_fields([
        {"_lbl": "b", "LUTs": '""Fire""',
         "normalization": "{'min_value': 120, 'max_value': 4000}"},
        {"_lbl": "c", "custom_loading_script": "arr = arr**0.5  # gamma\nself.img = arr"},
        {"_lbl": "d", "LUTs": '""Fire""',
         "normalization": "{'min_value': 0, 'max_value': 255}"},
    ], tmp)
    data = json.loads(M.export_adjustment_ledger(pyf))
    assert data["panels_with_custom_script"] == 1
    assert data["panels"][1]["all_linear"] is False
    assert any("different display ranges" in f for f in data["flags"])


def test_adjustment_ledger_flip_is_linear_not_custom():
    tmp = tempfile.mkdtemp()
    flip_script = M._make_flip_script(flip_h=True, flip_v=False)
    pyf = _write_pyf_fields([{"_lbl": "a", "custom_loading_script": flip_script}], tmp)
    data = json.loads(M.export_adjustment_ledger(pyf))
    p = data["panels"][0]
    assert p["all_linear"] is True                      # a pure flip is not "custom"
    assert any(a["type"] == "flip" for a in p["adjustments"])


# --- zoom / magnified-detail callout ----------------------------------------
def test_add_zoom_callout_builds_box_inset_and_leaders():
    tmp = tempfile.mkdtemp()
    big = (np.random.default_rng(0).random((400, 600, 3)) * 255).astype(np.uint8)
    p = os.path.join(tmp, "parent.png"); cv2.imwrite(p, big)
    pyf = _write_pyf([p], tmp)

    msg = M.add_zoom_callout(pyf, [], 0, source_x=300, source_y=150,
                             source_w=120, source_h=90,
                             parent_width=600, parent_height=400,
                             inset_corner="bottom left")
    assert "Zoom callout" in msg

    annots = ET.parse(pyf).getroot().find("Image2D").find("annotations")
    assert len([e for e in annots if e.tag == "Rectangle2D"]) == 1     # ROI box
    assert len([e for e in annots if e.tag == "Line2D"]) == 2          # 2 leaders
    insets = [e for e in annots if e.tag == "Image2D"]
    assert len(insets) == 1
    ins = insets[0]
    # inset is the parent's own region cropped to the source rect
    assert ins.findtext("crop_left") == "300" and ins.findtext("crop_top") == "150"
    assert ins.findtext("crop_right") == "180"          # 600 - (300+120)
    assert ins.findtext("crop_bottom") == "160"         # 400 - (150+90)
    assert ins.findtext("placement") == "bottom left"


def test_add_zoom_callout_connectors_count_and_validation():
    tmp = tempfile.mkdtemp()
    big = (np.random.default_rng(1).random((200, 200, 3)) * 255).astype(np.uint8)
    p = os.path.join(tmp, "parent.png"); cv2.imwrite(p, big)
    pyf = _write_pyf([p], tmp)

    M.add_zoom_callout(pyf, [], 0, 40, 40, 30, 30, 200, 200, connectors=0)
    annots = ET.parse(pyf).getroot().find("Image2D").find("annotations")
    assert len([e for e in annots if e.tag == "Line2D"]) == 0          # no leaders

    assert M.add_zoom_callout(pyf, [], 0, 1, 1, 1, 1, 10, 10,
                              inset_corner="middle").startswith("ERROR")
    assert M.add_zoom_callout(pyf, [], 0, 1, 1, 1, 1, 10, 10,
                              connectors=5).startswith("ERROR")
    assert M.add_zoom_callout(pyf, [], 0, 1, 1, 0, 1, 10, 10).startswith("ERROR")


# --- figure caption / legend -------------------------------------------------
def test_figure_caption_roundtrip_and_pyf_untouched():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "x.png"); cv2.imwrite(p, np.zeros((10, 10, 3), np.uint8))
    pyf = _write_pyf([p], tmp)

    before = open(pyf, encoding="utf-8").read()
    M.set_figure_caption(pyf, "Panel (a) wild-type. Scale bar, 10 um.", title="Figure 1")
    after = open(pyf, encoding="utf-8").read()
    assert before == after                                   # caption never touches the .pyf
    assert os.path.isfile(os.path.splitext(pyf)[0] + ".caption.json")

    cap = json.loads(M.get_figure_caption(pyf))
    assert cap["title"] == "Figure 1" and "wild-type" in cap["caption"]

    exp = json.loads(M.export_caption(pyf, fmt="md"))
    body = open(exp["output"], encoding="utf-8").read()
    assert body.startswith("## Figure 1") and "wild-type" in body

    # clearing removes the sidecar
    M.set_figure_caption(pyf, "")
    assert M.get_figure_caption(pyf).startswith("No figure caption")


def test_export_caption_requires_caption():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "x.png"); cv2.imwrite(p, np.zeros((10, 10, 3), np.uint8))
    pyf = _write_pyf([p], tmp)
    assert M.export_caption(pyf).startswith("ERROR")


# --- multi-channel merge -----------------------------------------------------
def _exec_script(script):
    """Run a decoded PyFigures loading-script the way the app does (np/plt/self
    provided as the exec namespace) and return the populated `self`."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    class _Self:
        pass
    ns = {"np": np, "plt": plt, "self": _Self()}
    exec(script, ns, ns)          # raises if the script is broken
    return ns["self"]


def test_add_channel_merge_script_executes():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "x.png"); cv2.imwrite(p, np.zeros((10, 10, 3), np.uint8))
    pyf = _write_pyf([p], tmp)
    g = (np.random.default_rng(0).random((80, 100)) * 255).astype(np.uint8)
    r = (np.random.default_rng(1).random((80, 100)) * 255).astype(np.uint8)
    pg = os.path.join(tmp, "gfp.tif"); cv2.imwrite(pg, g)
    pr = os.path.join(tmp, "rfp.tif"); cv2.imwrite(pr, r)

    msg = M.add_channel_merge(pyf, [], [pg, pr], colors=["green", "magenta"], label="Merge")
    assert "Channel-merge" in msg

    raw = next(e.findtext("custom_loading_script")
               for e in ET.parse(pyf).getroot().iter("Image2D")
               if e.findtext("custom_loading_script"))
    self_obj = _exec_script(M._decode(raw))          # must not raise (no nested-func np bug)
    assert self_obj.img is not None


def test_add_channel_merge_mismatched_shapes_and_validation():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "x.png"); cv2.imwrite(p, np.zeros((10, 10, 3), np.uint8))
    pyf = _write_pyf([p], tmp)
    a = (np.random.default_rng(0).random((80, 100)) * 255).astype(np.uint8)
    b = (np.random.default_rng(2).random((40, 60)) * 255).astype(np.uint8)
    pa = os.path.join(tmp, "a.tif"); cv2.imwrite(pa, a)
    pb = os.path.join(tmp, "b.tif"); cv2.imwrite(pb, b)

    M.add_channel_merge(pyf, [], [pa, pb], colors=["green", "red"])
    raw = next(e.findtext("custom_loading_script")
               for e in ET.parse(pyf).getroot().iter("Image2D")
               if e.findtext("custom_loading_script"))
    _exec_script(M._decode(raw))                     # resize path must not raise

    assert M.add_channel_merge(pyf, [], [pa], mode="avg").startswith("ERROR")
    assert M.add_channel_merge(pyf, [], [pa, pb], colors=["red"]).startswith("ERROR")
    assert M.add_channel_merge(pyf, [], [pa, "/no/such.tif"]).startswith("ERROR")


# --- print-ready CMYK export -------------------------------------------------
def test_export_print_ready_validation():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "x.png"); cv2.imwrite(p, np.zeros((10, 10, 3), np.uint8))
    pyf = _write_pyf([p], tmp)
    assert M.export_print_ready(pyf, os.path.join(tmp, "o.tif"),
                                color_mode="lab").startswith("ERROR")
    assert M.export_print_ready(pyf, os.path.join(tmp, "o.png")).startswith("ERROR")
    assert M.export_print_ready(pyf, os.path.join(tmp, "o.tif"),
                                dpi=50).startswith("ERROR")


# --- portable fonts ----------------------------------------------------------
def test_portable_fonts_register_and_resolve():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from pyfigures.gui import portable_fonts

    reg = portable_fonts.register_portable_fonts(app)
    avail = portable_fonts.available_families()
    # DejaVu Sans is bundled with matplotlib -> always registered as a fallback
    assert "DejaVu Sans" in avail
    assert "DejaVu Sans" in reg
    # Helvetica/Arial always resolve to *some* available family (never dangling)
    assert portable_fonts.resolve_family("Helvetica") in avail
    assert portable_fonts.resolve_family("Arial") in avail
    # idempotent
    assert portable_fonts.register_portable_fonts(app) == reg

    rep = portable_fonts.font_report()
    for k in ("bundled_families", "fonts_dir", "helvetica_resolves_to",
              "portable_clones_available"):
        assert k in rep
