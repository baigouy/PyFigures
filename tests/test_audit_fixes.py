"""
Regression tests for the 2026-09-27 code-audit fixes:

 1  .pyf values are parsed without eval()          (security)
 2  remap_paths: no eval, keeps the ""…"" wrapper, remaps script paths
 3  layout recompute never runs scripts of already-sized panels
 4  MCP-added images store their TRUE size (no 512x512 placeholder)
 5  a failed layout recompute is reported, not swallowed
 7  GUI QC bridge carries caption/stats sidecars both ways
 8  QC temp folders are cleaned up
 9  stats: real Dunn's test, omnibus gating, small-n test choice
10  library index notices caption edits
12  atomic .pyf writes
13  create_figure(num_groups=N) creates the groups
14  Fiji gateway init is a thread-safe singleton
15  channel-merge normalisation is explicit and disclosed in the ledger

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import threading
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _png(path, h, w, val=120):
    from PIL import Image
    Image.fromarray(np.full((h, w), val, np.uint8)).save(path)
    return path


def _img_sizes(pyf):
    out = {}
    for img in ET.parse(pyf).getroot().iter("Image2D"):
        fn = (img.findtext("filename") or "").strip('"')
        out[os.path.basename(fn)] = (float(img.findtext("width")),
                                     float(img.findtext("height")),
                                     float(img.findtext("scale") or 1))
    return out


# ── 1  no eval() when reading a .pyf ───────────────────────────────────────

def test_safe_literal_eval_accepts_real_values():
    from batoolset.serializations.tools import safe_literal_eval
    assert safe_literal_eval("[1, 2.5, -3]") == [1, 2.5, -3]
    assert safe_literal_eval("['DNA', 'GREEN']") == ["DNA", "GREEN"]
    assert safe_literal_eval("[np.float64(1.5), np.int64(2)]") == [1.5, 2]
    v = safe_literal_eval("[nan, inf]")
    assert np.isnan(v[0]) and v[1] == float("inf")
    assert safe_literal_eval("{'top': True, 'left': False}") == {"top": True, "left": False}


def test_safe_literal_eval_rejects_code(tmp_path):
    from batoolset.serializations.tools import safe_literal_eval
    marker = tmp_path / "pwned.txt"
    for payload in (f"[open(r'{marker}', 'w')]",
                    "[__import__('os').getcwd()]",
                    "[(lambda: 1)()]",
                    "[np.save('x', 1)]"):
        with pytest.raises(ValueError):
            safe_literal_eval(payload)
    assert not marker.exists()


def test_opening_malicious_pyf_does_not_execute(tmp_path):
    """A list-valued field used to be eval()'d on open — without the script
    security prompt, since the file has no custom_loading_script."""
    from batoolset.serializations.tools import deserialize_to_dict
    marker = tmp_path / "pwned.txt"
    xml = ("<?xml version='1.0'?><list><Image2D><filename>\"\"a.png\"\"</filename>"
           f"<LUTs>[open(r'{marker}', 'w')]</LUTs></Image2D></list>")
    with pytest.raises(ValueError):
        deserialize_to_dict(xml)
    assert not marker.exists()


# ── 2  remap_paths ──────────────────────────────────────────────────────────

def test_remap_paths_list_keeps_wrapper_and_no_eval(tmp_path):
    from pyfigures.mcp_server import remap_paths, create_figure
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    root = ET.parse(pyf).getroot()
    img = ET.SubElement(root, "Image2D")
    ET.SubElement(img, "filename").text = '""[\'/old/a.png\', \'/old/b.png\']""'
    ET.ElementTree(root).write(pyf, encoding="unicode")

    out = remap_paths(pyf, "/old/", "C:/new/")
    assert "list remapped" in out
    txt = ET.parse(pyf).getroot().find("Image2D/filename").text
    assert txt == '""[\'C:/new/a.png\', \'C:/new/b.png\']""'

    # malicious list is not executed (skipped as unchanged)
    marker = tmp_path / "pwned.txt"
    root = ET.parse(pyf).getroot()
    root.find("Image2D/filename").text = f'""[open(r\'{marker}\', \'w\')]""'
    ET.ElementTree(root).write(pyf, encoding="unicode")
    remap_paths(pyf, "/old/", "/x/")
    assert not marker.exists()


def test_remap_paths_rewrites_script_paths(tmp_path):
    from pyfigures.mcp_server import (remap_paths, create_figure, add_data_plot,
                                      _decode)
    d = str(tmp_path)
    csv = os.path.join(d, "data.csv")
    with open(csv, "w") as f:
        f.write("A,B\n1,4\n2,5\n3,6\n")
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_data_plot(pyf, [0], csv, annotate_stats=False)
    old_prefix = os.path.abspath(d)
    out = remap_paths(pyf, old_prefix, "Z:/moved")
    assert "script: 1 path literal(s) remapped" in out
    script = next(_decode(i.findtext("custom_loading_script"))
                  for i in ET.parse(pyf).getroot().iter("Image2D"))
    assert "Z:/moved" in script and old_prefix not in script
    compile(script, "<panel>", "exec")  # still valid Python


# ── 3/4/5/12/13  MCP save path ──────────────────────────────────────────────

def test_mcp_images_store_true_size_and_aspect(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image
    d = str(tmp_path)
    wide = _png(os.path.join(d, "wide.png"), 100, 400)
    tall = _png(os.path.join(d, "tall.png"), 400, 100)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], wide)
    add_image(pyf, [0], tall)
    s = _img_sizes(pyf)
    assert s["wide.png"][:2] == (400.0, 100.0)
    assert s["tall.png"][:2] == (100.0, 400.0)
    # same row => same displayed height; displayed widths keep the aspect
    wh = s["wide.png"][1] / s["wide.png"][2]
    th = s["tall.png"][1] / s["tall.png"][2]
    assert abs(wh - th) < 0.5
    ww = s["wide.png"][0] / s["wide.png"][2]
    tw = s["tall.png"][0] / s["tall.png"][2]
    assert abs(ww / tw - 16.0) < 0.2


def test_stale_stored_size_is_resynced(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image, set_spacing
    d = str(tmp_path)
    p = _png(os.path.join(d, "a.png"), 100, 300)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], p)
    _png(p, 200, 200)  # source replaced by a different-sized file
    set_spacing(pyf, [0], 4)
    assert _img_sizes(pyf)["a.png"][:2] == (200.0, 200.0)


def test_recompute_does_not_run_sized_panel_scripts(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image, set_spacing, _encode_str
    d = str(tmp_path)
    p = _png(os.path.join(d, "a.png"), 50, 80)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], p)
    marker = os.path.join(d, "ran.txt")
    tree = ET.parse(pyf)
    img = next(tree.getroot().iter("Image2D"))
    img.find("custom_loading_script").text = _encode_str(
        f"open(r'{marker}', 'a').write('x')\n")
    tree.write(pyf, encoding="unicode")
    set_spacing(pyf, [0], 5)
    assert not os.path.exists(marker)
    # the script itself is preserved
    assert "ran.txt" in ET.parse(pyf).getroot().find(".//custom_loading_script").text


def test_recompute_failure_is_reported(tmp_path, monkeypatch):
    from pyfigures import mcp_server as m
    from pyfigures.mcp_tools import core  # patch where _save looks it up
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    m.create_figure(pyf, num_groups=1)
    monkeypatch.setattr(core, "_auto_recompute", lambda p: "boom")
    out = m.add_image(pyf, [0], _png(os.path.join(d, "a.png"), 20, 20))
    assert "WARNING" in out and "boom" in out
    # the warning does not leak into the next call
    monkeypatch.setattr(core, "_auto_recompute", lambda p: "")
    out2 = m.add_image(pyf, [0], _png(os.path.join(d, "b.png"), 20, 20))
    assert "WARNING" not in out2


def test_atomic_write_leaves_no_temp_files(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], _png(os.path.join(d, "a.png"), 20, 20))
    assert not [f for f in os.listdir(d) if f.startswith(".~pyf_")]
    ET.parse(pyf)  # well-formed


def test_create_figure_num_groups(tmp_path):
    from pyfigures.mcp_server import create_figure
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, num_groups=2)
    assert len(ET.parse(pyf).getroot().findall("Group")) == 2
    assert create_figure(pyf, num_groups=2, mode="canvas").startswith("ERROR")
    create_figure(pyf)
    assert ET.parse(pyf).getroot().findall("Group") == []


# ── 7/8  GUI bridge ─────────────────────────────────────────────────────────

def _gui(monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    return EZFIG_GUI()


def test_gui_review_sees_caption(qapp, monkeypatch, tmp_path):
    from pyfigures.mcp_server import create_figure, add_image, set_figure_caption
    from pyfigures.gui.pfgui import EZFIG_GUI
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], _png(os.path.join(d, "a.png"), 30, 30))
    set_figure_caption(pyf, "Cells at 63x. Scale bar 10 um.")
    g = _gui(monkeypatch)
    g.reload_state(pyf, append=False)
    g.current_file = pyf
    captured = {}
    monkeypatch.setattr(EZFIG_GUI, "_show_report",
                        lambda self, title, text: captured.update(text=text))
    g.figure_review_action()
    assert "Caption: present" in captured["text"]
    g._dirty = False


def test_gui_mutation_brings_stats_back_and_cleans_temp(qapp, monkeypatch, tmp_path):
    pytest.importorskip("staplot.api")
    from pyfigures.mcp_server import create_figure, add_data_plot
    d = str(tmp_path)
    csv = os.path.join(d, "data.csv")
    with open(csv, "w") as f:
        f.write("A,B\n1,10\n2,11\n3,12\n2,10\n")
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    g = _gui(monkeypatch)
    g.reload_state(pyf, append=False)
    g.current_file = pyf
    g._run_mcp_mutation(add_data_plot, "ok", group_path=[], csv_path=csv,
                        annotate_stats=True)
    stats = os.path.splitext(pyf)[0] + ".stats.json"
    assert os.path.isfile(stats), "stats sidecar was lost in the temp folder"
    first_tmp = list(g._qc_temp_dirs)
    g._save_current_to_temp_pyf()
    assert all(not os.path.exists(t) for t in first_tmp), "temp folder leaked"
    g._cleanup_qc_temp_dirs()
    g._dirty = False


def test_unsaved_figure_sidecars_follow_first_save(qapp, monkeypatch, tmp_path):
    g = _gui(monkeypatch)
    g.current_file = None
    base = g._sidecar_base()
    with open(base + ".caption.json", "w", encoding="utf-8") as f:
        json.dump({"title": None, "caption": "hello"}, f)
    target = str(tmp_path / "saved.pyf")
    g.save_pyfigures(file=target)
    assert os.path.isfile(str(tmp_path / "saved.caption.json"))
    g._discard_sidecar_stash()
    g._dirty = False


# ── 9  statistics ───────────────────────────────────────────────────────────

def test_dunn_matches_kruskal_for_two_groups():
    """For two groups Dunn's z^2 equals the tie-corrected Kruskal-Wallis H, so
    the Dunn p must equal the Kruskal p (independent check of the formula)."""
    from scipy import stats
    from staplot.stats.anova import dunn_test
    rng = np.random.default_rng(0)
    a = np.round(rng.normal(0, 1, 9), 1)       # rounding creates ties
    b = np.round(rng.normal(0.8, 1, 11), 1)
    (_, _, p_dunn), = dunn_test([a, b])
    assert p_dunn == pytest.approx(stats.kruskal(a, b).pvalue, rel=1e-9)


def test_auto_test_gates_posthoc_on_omnibus():
    from staplot import api
    rng = np.random.default_rng(1)
    same = {k: rng.normal(5, 1, 8).tolist() for k in ("A", "B", "C")}
    rec = api.auto_test(api.table_from_columns(same), only_significant=False)
    assert rec["omnibus"]["p"] >= 0.05
    assert rec["sig_pairs"] == [] and rec["posthoc_shown"] is False
    assert len(rec["comparisons"]) == 3  # still reported


def test_auto_test_small_n_uses_parametric_with_warning():
    from staplot import api
    rec = api.auto_test(api.table_from_columns({"A": [1.0, 1.2], "B": [5.0, 5.3]}))
    assert rec["test"] == "Welch's t-test"
    assert "assumed" in rec["normality"]
    assert rec.get("warnings")


def test_auto_test_warns_when_mann_whitney_cannot_reach_significance():
    from staplot import api
    rec = api.auto_test(api.table_from_columns({"A": [1.0, 2.0, 3.0],
                                                "B": [7.0, 8.0, 9.0]}),
                        parametric=False)
    assert rec["test"] == "Mann-Whitney U test"
    assert any("cannot reach p<0.05" in w for w in rec.get("warnings", []))


def test_kruskal_branch_reports_dunn():
    from staplot import api
    data = {"A": [1, 1, 1, 1, 50], "B": [5, 6, 5, 6, 5], "C": [9, 9, 10, 9, 90]}
    rec = api.auto_test(api.table_from_columns(data), parametric=False)
    assert rec["test"] == "Kruskal-Wallis + Dunn's test"


# ── 10  library index ───────────────────────────────────────────────────────

def test_index_reindexes_on_caption_edit(tmp_path):
    import time
    from pyfigures.mcp_server import (create_figure, set_figure_caption,
                                      index_figures, search_figures)
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf)
    set_figure_caption(pyf, "zebrafish heart")
    idx = json.loads(index_figures(d))["index"]
    time.sleep(0.05)
    set_figure_caption(pyf, "drosophila wing disc")
    r = json.loads(index_figures(d))
    assert r["updated"] == 1 and r["unchanged"] == 0
    assert json.loads(search_figures("drosophila", idx))["n_results"] == 1


# ── 14  Fiji gateway singleton ──────────────────────────────────────────────

def test_init_ij_is_thread_safe_singleton(monkeypatch):
    ij_reader = pytest.importorskip("batoolset.IJ.ij_reader")
    calls = []
    monkeypatch.setattr(ij_reader, "_ij_gateway", None)

    def fake_init(parent_widget=None):
        calls.append(1)
        import time
        time.sleep(0.05)
        return object()
    monkeypatch.setattr(ij_reader, "_init_ij_unlocked", fake_init)
    results = []
    threads = [threading.Thread(target=lambda: results.append(ij_reader.init_ij()))
               for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert len({id(r) for r in results}) == 1


def test_init_ij_failure_is_remembered(monkeypatch):
    ij_reader = pytest.importorskip("batoolset.IJ.ij_reader")
    monkeypatch.setattr(ij_reader, "_ij_gateway", None)

    def bad(parent_widget=None):
        raise RuntimeError("no java")
    monkeypatch.setattr(ij_reader, "_init_ij_unlocked", bad)
    with pytest.raises(RuntimeError):
        ij_reader.init_ij()
    with pytest.raises(RuntimeError, match="previously failed"):
        ij_reader.init_ij()


# ── found during the in-app check / recipe work ─────────────────────────────

def test_set_lut_resolves_case_and_rejects_unknown(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image, set_lut
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], _png(os.path.join(d, "a.png"), 20, 20))
    assert not set_lut(pyf, [0], 0, ["matplotlib_VIRIDIS"]).startswith("ERROR")
    luts = next(ET.parse(pyf).getroot().iter("Image2D")).findtext("LUTs")
    assert "MATPLOTLIB_viridis" in luts            # real key, not upper-cased
    out = set_lut(pyf, [0], 0, ["GREEEN"])
    assert out.startswith("ERROR") and "GREEN" in out   # suggestion offered


def test_saved_pyf_has_no_memory_addresses(tmp_path):
    """ScaleBar.bar used to be written as 'Rectangle2D-0x…' -> every save differed."""
    import re
    from pyfigures.mcp_server import create_figure, add_image, set_scale_bar
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], _png(os.path.join(d, "a.png"), 40, 40))
    set_scale_bar(pyf, [0], 0, 5, px_to_unit=0.5)
    assert not re.search(r">\w+-0x[0-9a-f]+<", open(pyf, encoding="utf-8").read())


def test_mcp_labels_letter_detection():
    from pyfigures.mcp_server import _looks_like_panel_letter
    for t in ("A", "b", "(c)", "D.", "AA"):
        assert _looks_like_panel_letter(t), t
    for t in ("Merge", "WT", "GFP", "*", "n=12", "AB"):
        assert not _looks_like_panel_letter(t), t


def test_image_panel_figures_keep_aspect(tmp_path):
    """A square image drawn via a script must give a square panel (it used to be
    stretched to matplotlib's default 4:3 figure)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from batoolset.matplolibs.tools import get_fig_rect
    from pyfigures.mcp_server import _make_channel_merge_script
    a = _png(os.path.join(str(tmp_path), "a.png"), 50, 50)

    class _S:
        img = None
    s = _S()
    exec(_make_channel_merge_script([a], [(0.0, 1.0, 0.0)], "sum"),
         {"plt": plt, "np": np, "self": s})
    r = get_fig_rect(s.img)
    assert abs(r.width() / r.height() - 1.0) < 0.02
    plt.close(s.img)


def test_resize_uses_point_canvas_units(tmp_path):
    """Canvas unit = 1/72 in: Nature double (183 mm) = 518.7 pt, not 2161."""
    from pyfigures.mcp_server import create_figure, add_image, resize_figure, check_journal_compliance
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], _png(os.path.join(d, "a.png"), 40, 60))
    out = resize_figure(pyf, journal="nature", column="double", dpi=300)
    assert "183.0mm" in out and "2161px" in out
    size = float(ET.parse(pyf).getroot().find("Group/size").text)
    assert abs(size - 183 / 25.4 * 72) < 0.5
    rep = check_journal_compliance(pyf, journal="nature", column="double")
    assert "183.0mm vs target 183.0mm" in rep


def test_crop_is_not_applied_twice_across_saves(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image, transform_image, set_spacing, resize_figure
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], _png(os.path.join(d, "a.png"), 120, 160))
    transform_image(pyf, [0], 0, crop_left=20, crop_right=20)
    for _ in range(3):
        set_spacing(pyf, [0], 3)
        resize_figure(pyf, width_mm=80)
    img = next(ET.parse(pyf).getroot().iter("Image2D"))
    assert float(img.findtext("width")) == 160.0   # raw size, not 120 / 80 / 40


def test_inset_placed_flush_in_single_pass(qapp, tmp_path):
    """A cropped inset must be sized before it is positioned (export renders once)."""
    from qtpy.QtGui import QImage, QPainter
    from pyfigures.mcp_server import create_figure, add_image, add_zoom_callout
    from pyfigures.mcp_tools.core import _load_objects_lazy
    from batoolset.img import Img
    d = str(tmp_path)
    p = _png(os.path.join(d, "a.png"), 120, 160)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], p)
    add_zoom_callout(pyf, [0], 0, 40, 60, 30, 30, 160, 120, inset_corner="top right")
    objects, Group, Image2D = _load_objects_lazy(pyf)
    parent = objects[0].content[0]
    for im in [parent] + [a for a in parent.annotations if isinstance(a, Image2D)]:
        im.img = Img(p)
        im.update_qimage()
    canvas = QImage(2000, 2000, QImage.Format.Format_ARGB32)
    painter = QPainter(canvas)
    parent.draw(painter)
    painter.end()
    inset = next(a for a in parent.annotations if isinstance(a, Image2D))
    pr, ir = parent.getRect(all=True), inset.getRect(all=True)
    assert abs(ir.width() - 0.4 * pr.width()) < 1.0
    assert abs((ir.x() + ir.width()) - (pr.x() + pr.width())) < 1.0   # flush right
    assert abs(ir.y() - pr.y()) < 1.0                                   # flush top


def test_box_plot_boxes_align_with_points():
    import matplotlib
    matplotlib.use("Agg")
    from staplot import api
    fig, _ = api.plot(api.table_from_columns({"A": [1, 2, 3, 4], "B": [5, 6, 7, 8]}),
                      kind="box", annotate=False)
    ax = fig.axes[0]
    box_x = []
    for p in ax.patches:
        xs = p.get_path().vertices[:, 0]
        box_x.append(round((float(xs.min()) + float(xs.max())) / 2, 2))
    box_x.sort()
    assert box_x == [0.0, 1.0]
    import matplotlib.pyplot as plt
    plt.close(fig)


# ── 15  channel merge disclosure ────────────────────────────────────────────

def _merge_fig(d, normalization="per_channel"):
    from pyfigures.mcp_server import create_figure, add_channel_merge
    a = _png(os.path.join(d, "gfp.png"), 30, 30, 60)
    b = _png(os.path.join(d, "rfp.png"), 30, 30, 200)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    out = add_channel_merge(pyf, [0], [a, b], normalization=normalization)
    assert not out.startswith("ERROR"), out
    return pyf


def test_merge_is_disclosed_in_ledger(tmp_path):
    from pyfigures.mcp_server import export_adjustment_ledger
    pyf = _merge_fig(str(tmp_path))
    led = json.loads(export_adjustment_ledger(pyf))
    merge = [p for p in led["panels"] if p["file"].startswith("merge of")]
    assert merge, "merge panel missing from the ledger"
    types = {a["type"] for a in merge[0]["adjustments"]}
    assert {"channel_merge", "brightness_contrast"} <= types
    assert merge[0]["all_linear"] is True


def test_merge_raw_intensities_not_reported_as_stretch(tmp_path):
    from pyfigures.mcp_server import export_adjustment_ledger
    pyf = _merge_fig(str(tmp_path), normalization="none")
    led = json.loads(export_adjustment_ledger(pyf))
    merge = [p for p in led["panels"] if p["file"].startswith("merge of")][0]
    assert {a["type"] for a in merge["adjustments"]} == {"channel_merge"}


def test_edited_merge_script_is_flagged(tmp_path):
    from pyfigures.mcp_server import export_adjustment_ledger, _decode, _encode_str
    pyf = _merge_fig(str(tmp_path))
    tree = ET.parse(pyf)
    el = next(e for e in tree.getroot().iter("custom_loading_script")
              if e.text and "channel_merge" in e.text)
    el.text = _encode_str(_decode(el.text).replace("comp = np.clip",
                                                   "comp = comp ** 0.5\ncomp = np.clip"))
    tree.write(pyf, encoding="unicode")
    led = json.loads(export_adjustment_ledger(pyf))
    assert any("custom processing script" in f for f in led["flags"])


def test_merge_script_none_normalization_executes(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pyfigures.mcp_server import _make_channel_merge_script
    d = str(tmp_path)
    a = _png(os.path.join(d, "a.png"), 10, 12, 51)
    script = _make_channel_merge_script([a], [(0.0, 1.0, 0.0)], "sum", "none")

    class _S:
        img = None
    s = _S()
    exec(script, {"plt": plt, "np": np, "self": s})
    arr = s.img.axes[0].images[0].get_array()
    assert np.allclose(arr[..., 1], 51 / 255.0)  # raw intensity, not stretched
    plt.close(s.img)
