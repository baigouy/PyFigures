"""End-to-end menu bar and toolbar of the figure editor (marker ``gui_e2e``).

Every entry is triggered as a click would (QAction.trigger on the action the
menu really shows); its dialogs really execute and are answered by filling
their widgets and clicking their buttons (file pickers, which are native OS
windows, answer with prepared paths). The RESULT is checked: the figure read
back from a saved file, the files an export wrote, the text of a report, the
window it opened. Figure-changing actions must also survive undo / redo and
a save / reopen, and nothing may raise, warn in Qt or log an error.
"""
from __future__ import annotations

import json
import os
import zipfile

import pytest

import gui_e2e_harness as H
from gui_e2e_harness import e2e_files, e2e_gui, no_file_dialogs, watch  # noqa: F401

pytestmark = pytest.mark.gui_e2e

BASE = ["row 1: gray8.tif | cells.png", "row 2: rgb.tif | zstack.tif"]


# ---------------------------------------------------------------------------
# dialog answers
# ---------------------------------------------------------------------------

def ok(dlg):
    H.accept(dlg)


def _red(dlg):
    from qtpy.QtGui import QColor
    dlg.setCurrentColor(QColor(255, 0, 0))
    H.accept(dlg)


def report(store):
    """A read-only report (CustomDialog + QTextBrowser): keep its text, Ok."""
    def h(dlg):
        from qtpy.QtWidgets import QTextBrowser, QTextEdit, QPlainTextEdit
        views = dlg.findChildren(QTextBrowser) + dlg.findChildren(QTextEdit) + dlg.findChildren(QPlainTextEdit)
        store.setdefault("reports", []).append("\n".join(v.toPlainText() for v in views))
        store.setdefault("titles", []).append(dlg.windowTitle())
        H.accept(dlg)
    return h


def message(store):
    """A QMessageBox: keep its text, accept it."""
    def h(dlg):
        store.setdefault("messages", []).append(dlg.windowTitle() + ": " + dlg.text())
        H.accept(dlg)
    return h


def text_input(value):
    def h(dlg):
        dlg.setTextValue(value)
        H.accept(dlg)
    return h


def number_input(value):
    def h(dlg):
        from qtpy.QtWidgets import QInputDialog
        if dlg.inputMode() == QInputDialog.InputMode.IntInput:
            dlg.setIntValue(int(value))
        elif dlg.inputMode() == QInputDialog.InputMode.DoubleInput:
            dlg.setDoubleValue(float(value))
        else:
            dlg.setTextValue(str(value))
        H.accept(dlg)
    return h


def combo(text, then=None):
    def h(dlg):
        from qtpy.QtWidgets import QComboBox
        for c in dlg.findChildren(QComboBox):
            i = c.findText(text)
            if i >= 0:
                c.setCurrentIndex(i)
                break
        else:
            raise AssertionError(f"no {text!r} in the combos of {dlg.windowTitle()}")
        (then or H.accept)(dlg)
    return h


def line_edit(label, value, then=None):
    def h(dlg):
        from qtpy.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit
        try:
            H.widget_by(dlg, QLineEdit, label=label).setText(value)
        except AssertionError:
            w = (dlg.findChildren(QPlainTextEdit) + dlg.findChildren(QTextEdit))[0]
            w.setPlainText(value)
        (then or H.accept)(dlg)
    return h


def grid_rows(n):
    """The grid-panel dialog: 'Specify Rows' = n."""
    def h(dlg):
        from qtpy.QtWidgets import QRadioButton, QSpinBox
        H.widget_by(dlg, QRadioButton, label="Specify Rows").setChecked(True)
        dlg.findChildren(QSpinBox)[0].setValue(n)
        H.accept(dlg)
    return h


def equation(latex):
    def h(dlg):
        dlg.latex_edit.setPlainText(latex)
        H.accept(dlg)
    return h


# ---------------------------------------------------------------------------
# start figures and selections
# ---------------------------------------------------------------------------

def _start(qapp, g, d, files, start):
    """'base' (2 rows), 'stacks' (base + a loose movie), 'empty', 'texts'
    (base whose 'note' text needs typographic tidying)."""
    from pyfigures import mcp_server as M
    if start == "empty":
        g.new_fig()
        H.settle(qapp, g)
        return None
    pyf = H.base_figure(d, files)
    if start == "stacks":
        M.add_image(pyf, [], files["tstack"])
    if start == "texts":
        M.add_annotation(pyf, [0], 1, "10-20 µm at 37 degrees C")
    H.load(qapp, g, pyf)
    return pyf


def _select(g, what):
    p = H.panel(g)
    if what is None:
        p.set_current_selection(None)
    elif what == "all rows":
        p.set_current_selection(list(H.rows(g)))
    else:
        p.set_current_selection(H.by_name(g, what))


# ---------------------------------------------------------------------------
# checks: (g, before, after, run) -> None; run = {"out": dir, "ans": file
# answers, "reports": [...], "messages": [...], "status": str}
# ---------------------------------------------------------------------------

def rows_are(expected):
    def chk(g, b, a, run):
        H.expect_rows(a, expected)
    return chk


def wrote(ext, *, magic=None, raster=False, mode=None):
    def chk(g, b, a, run):
        files = [f for f in os.listdir(run["out"]) if f.lower().endswith(ext)]
        assert files, f"no {ext} written: {os.listdir(run['out'])}"
        path = os.path.join(run["out"], files[0])
        assert os.path.getsize(path) > 200, path
        if magic is not None:
            with open(path, "rb") as fh:
                head = fh.read(4096)
            assert magic in head, (ext, head[:60])
        if raster:
            from PIL import Image
            with Image.open(path) as im:
                assert im.size[0] > 100 and im.size[1] > 50, im.size
                if mode is not None:
                    assert im.mode == mode, im.mode
        assert H.same(b, a), "exporting changed the figure"
    return chk


def report_says(*words):
    def chk(g, b, a, run):
        text = "\n".join(run.get("reports", []))
        for w in words:
            assert w.lower() in text.lower(), (w, text[:600])
        assert H.same(b, a), "a report changed the figure"
    return chk


def panels_added(n, *, name=None, script=False):
    def chk(g, b, a, run):
        if n is None:                      # a new figure: anything but empty
            assert len([p for p in a["panels"] if not p["text"]]) >= 2, H.diff(b, a)
            return
        assert len(a["panels"]) == len(b["panels"]) + n, (H.diff(b, a), run.get("messages"), run.get("status"))
        new = [p for p in a["panels"] if p not in b["panels"]]
        if name is not None:
            assert any(p["name"] and name in str(p["name"]) for p in new), new
        if script:
            assert any(p["script"] for p in new), new
    return chk


def all_panels(pred, what):
    def chk(g, b, a, run):
        bad = [p["name"] for p in a["panels"] if not p["text"] and not pred(p)]
        assert not bad, f"{what}: {bad}"
    return chk


def unchanged(g, b, a, run):
    assert H.same(b, a), H.diff(b, a)


def both(*checks):
    def chk(g, b, a, run):
        for c in checks:
            c(g, b, a, run)
    return chk


# ---------------------------------------------------------------------------
# the table: key -> spec
#   start: start figure; sel: selection; files: file-picker answers
#   (names of e2e_files, or 'out:<name>' in the output folder);
#   dialogs: [(title/class, handler)]; check; inv: undo/redo/reopen checked
# ---------------------------------------------------------------------------

def spec(check, dialogs=(), start="base", sel="gray8", files=None, inv=True, before=None, after=None):
    return {"check": check, "dialogs": list(dialogs), "start": start, "sel": sel,
            "files": files or {}, "inv": inv, "before": before, "after": after}


def _make_dirty(g):
    H.panel(g).set_current_selection(H.by_name(g, "cells"))
    H.panel(g).duplicate()


def chk_saved_back(g, b, a, run):
    st = H.read_state(g.current_file)       # b already holds the duplicate made before
    assert len(st["panels"]) == len(b["panels"]) == 5, "Save did not write the change back"
    assert not g._dirty


def chk_save_as(g, b, a, run):
    target = os.path.join(run["out"], "saved.pyf")
    assert os.path.isfile(target)
    assert H.same(H.read_state(target), b)
    assert os.path.abspath(g.current_file) == os.path.abspath(target)
    assert "saved" in g.windowTitle()


def chk_consolidated(g, b, a, run):
    found = []
    for root, _dirs, fs in os.walk(run["out"]):
        found += fs
    assert any(f.endswith(".pyf") for f in found), found
    for n in ("gray8.tif", "cells.png", "rgb.tif", "zstack.tif"):
        assert n in found, (n, found)


def chk_template(g, b, a, run):
    names = [p["name"] for p in a["panels"] if not p["text"]]
    assert names and all(n == "@template@" for n in names), names


def chk_new(g, b, a, run):
    assert a["panels"] == [] and a["rows"] == []


def chk_selection(expected):
    def chk(g, b, a, run):
        sel = H.panel(g).selected_shape
        if expected is None:
            assert not sel, sel
        else:
            sel = sel if isinstance(sel, list) else [sel]
            assert len(sel) == expected, sel
    return chk


def _fill_caption(dlg):
    # the rich-text caption dialog (one dialog: title + formatted caption)
    dlg.title_edit.setText("Figure 7")
    dlg.doc.setPlainText("e2e caption")
    H.accept(dlg)


def chk_caption(g, b, a, run):
    from pyfigures.mcp_server import get_figure_caption
    d = json.loads(get_figure_caption(g.current_file))
    assert d["title"] == "Figure 7" and "e2e caption" in d["caption"], d


def chk_alt_text(g, b, a, run):
    from pyfigures.mcp_tools.upkeep import read_alt_text
    stored = read_alt_text(g.current_file)
    assert stored and "e2e alt text" in json.dumps(stored), stored


def chk_pptx(g, b, a, run):
    wrote(".pptx")(g, b, a, run)
    path = os.path.join(run["out"], "saved.pptx")
    with zipfile.ZipFile(path) as z:
        assert any(n.startswith("ppt/slides/slide1") for n in z.namelist())


def chk_latex(g, b, a, run):
    names = os.listdir(run["out"])
    assert any(n.endswith(".pdf") for n in names) and any(n.endswith(".pdf_tex") for n in names), names


def chk_jsx(g, b, a, run):
    wrote(".jsx")(g, b, a, run)
    assert any(n.endswith("_assets") for n in os.listdir(run["out"])), os.listdir(run["out"])


def chk_source_data(g, b, a, run):
    found = []
    for root, _dirs, fs in os.walk(run["out"]):
        found += fs
    assert any(f.lower().endswith((".png", ".tif", ".tiff", ".pdf", ".svg")) for f in found), found
    assert any("method" in f.lower() or f.lower().endswith((".md", ".txt", ".json")) for f in found), found


def chk_video(g, b, a, run):
    names = [n for n in os.listdir(run["out"]) if n.lower().endswith((".mp4", ".avi", ".gif", ".webm"))]
    assert names, os.listdir(run["out"])
    import cv2
    cap = cv2.VideoCapture(os.path.join(run["out"], names[0]))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert n >= 5, n


def chk_scale_bars_everywhere(g, b, a, run):
    imgs = [p for p in a["panels"] if not p["text"] and p["name"] not in (None, "@template@")]
    assert all(p["scale_bars"] for p in imgs), [(p["name"], p["scale_bars"]) for p in imgs]


def chk_annotation_added(cls):
    def chk(g, b, a, run):
        pa = next(p for p in a["panels"] if p["name"] == "gray8.tif")
        pb = next(p for p in b["panels"] if p["name"] == "gray8.tif")
        if cls == "inset":
            assert pa["insets"] > pb["insets"], (pb["insets"], pa["insets"])
        else:
            assert len(pa["rois"]) > len(pb["rois"]), (pb["rois"], pa["rois"])
    return chk


def _bold_texts(dlg):
    w = dlg.parent()._text_style_widgets
    w["target"].setCurrentIndex(w["target"].findData("texts"))
    w["bold"].setCurrentIndex(1)
    H.accept(dlg)


def chk_texts_bold(g, b, a, run):
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _decode
    path = os.path.join(run["out"], "restyled.pyf")
    g._save_state_to_file(path)
    texts = [_decode(t.findtext("text")) or "" for t in ET.parse(path).getroot().iter("TAText2D")
             if t.findtext("is_letter") != "True"]
    assert texts and all("font-weight:700" in t or "font-weight:600" in t for t in texts), texts
    assert a["panels"][0]["texts"] == b["panels"][0]["texts"]          # words kept


def chk_tidied(g, b, a, run):
    texts = [t for p in a["panels"] for t in p["texts"]]
    assert any("10–20" in t and "37 °C" in t for t in texts), texts


def chk_removed(key, empty):
    def chk(g, b, a, run):
        assert all(p[key] == empty for p in a["panels"] if not p["text"]), [(p["name"], p[key]) for p in a["panels"]]
        assert any(p[key] != empty for p in b["panels"]), f"nothing to remove ({key})"
    return chk


def chk_window(attr, cls_name=None):
    def chk(g, b, a, run):
        w = getattr(g, attr, None)
        assert w is not None and w.isVisible(), attr
        if cls_name:
            assert type(w).__name__ == cls_name, type(w).__name__
        w.close()
    return chk


def chk_width_changed(g, b, a, run):
    # the drawn figure (panel sizes in the file are their source sizes)
    wa = H.panel(g).updateBounds().width()
    wb = run["width0"]
    assert abs(wa - wb) > 5, (wb, wa)


def chk_background(value):
    def chk(g, b, a, run):
        assert str(a["background"]) == str(value), a["background"]
    return chk


def status_says(text):
    def chk(g, b, a, run):
        assert text in run["status"], run["status"]
    return chk


def _spaced(g, space):
    for r in H.rows(g):
        r.space = space
        r.update()
    H.panel(g).finalize_and_update()


def _all_spaces(st, value):
    assert all(sp == value for _o, sp in st["groups"]), st["groups"]


def chk_rgb_luts(expected):
    def chk(g, b, a, run):
        import ast
        luts = next(p["luts"] for p in a["panels"] if p["name"] == "rgb.tif")
        if isinstance(luts, str):
            luts = ast.literal_eval(luts)
        assert [str(x).upper() for x in (luts or [])] == expected, luts
    return chk


def chk_undo(g, b, a, run):
    # 'before' = after the duplicate made by spec.before; undo removed it
    assert len(a["panels"]) == len(b["panels"]) - 1, H.diff(b, a)


def chk_redo(g, b, a, run):
    assert len(a["panels"]) == len(b["panels"]) + 1, H.diff(b, a)


def _duplicate_then_undo(g):
    _make_dirty(g)
    g._flush_pending_checkpoints()
    g.undo()


def _recipe(run, files):
    path = os.path.join(run["out"], "recipe.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"output: {json.dumps(os.path.join(run['out'], 'from_recipe.pyf'))}\n"
                 f"rows:\n  - [{json.dumps(files['png'])}, {json.dumps(files['png2'])}]\n")
    return path


ACTIONS = {
    # ── File ──
    "menu: File > Open…": spec(rows_are(["row 1: gray8.tif | cells2.png"]), files={"open": "pyf"}, inv=False),
    "menu: File > Merge into current figure…": spec(rows_are(BASE + ["row 3: gray8.tif | cells2.png"]),
                                                    files={"open": "pyf"}),
    "menu: File > New": spec(chk_new, inv=False),
    "menu: File > Draft figure from folder…": spec(panels_added(None), [("Draft figure from folder", ok)],
                                                   files={"dir": "folder_copy"}, inv=False),
    "menu: File > Build figure from recipe…": spec(rows_are(["row 1: cells.png | cells2.png"]),
                                                   files={"open": "recipe"}, inv=False),
    "menu: File > Search figure library…": spec(rows_are(["row 1: gray8.tif | cells2.png"]),
                                                [("Search figure library", text_input("cells2")),
                                                 ("Figure library search", ok)], files={"dir": "library"},
                                                inv=False),
    "menu: File > Save": spec(chk_saved_back, before=_make_dirty, inv=False),
    "menu: File > Save As...": spec(chk_save_as, files={"save": "out:saved.pyf"}, inv=False),
    "menu: File > Save And Consolidate...": spec(chk_consolidated, files={"dir": "out:", "save": "out:cons.pyf"},
                                                 inv=False),
    "menu: File > Compare with another version…": spec(unchanged, files={"open": "pyf", "save": "out:diff.html"},
                                                       inv=False),
    "menu: File > Convert figure to template": spec(chk_template),
    "menu: File > Review comments > Export for review…": spec(
        wrote(".html", magic=b"<html"), [("Export for review", text_input("me@lab.org")),
                                         ("Exported for review", H.reject)],
        files={"save": "out:saved.html"}, inv=False),
    "menu: File > Review comments > Import review comments…": spec(unchanged, files={"open": "review"}, inv=False),
    "menu: File > Review comments > View review comments": spec(unchanged, inv=False),
    "menu: File > Figure caption / legend…": spec(chk_caption, [("Figure caption / legend", _fill_caption)],
                                                  inv=False),
    "menu: File > Alt text (accessibility)…": spec(chk_alt_text, [("Alt text", line_edit("", "e2e alt text"))],
                                                   inv=False),
    "menu: File > Copy style from another figure…": spec(both(status_says("Style copied from other.pyf"),
                                                              lambda g, b, a, run: _all_spaces(a, 3.0)),
                                                         [("Copy style", ok)], files={"open": "pyf"},
                                                         before=lambda g: _spaced(g, 9)),
    # exports
    "menu: File > Export As > SVG": spec(wrote(".svg", magic=b"<svg"), files={"save": "out:saved.svg"}, inv=False),
    "menu: File > Export As > PDF": spec(wrote(".pdf", magic=b"%PDF"), files={"save": "out:saved.pdf"}, inv=False),
    "menu: File > Export As > PDF + LaTeX (text as LaTeX)…": spec(chk_latex, files={"save": "out:saved.pdf"},
                                                                  inv=False),
    "menu: File > Export As > PowerPoint (editable)…": spec(chk_pptx, files={"save": "out:saved.pptx"}, inv=False),
    "menu: File > Export As > Adobe Illustrator script (.jsx)…": spec(chk_jsx, files={"save": "out:saved.jsx"},
                                                                     inv=False),
    "menu: File > Export As > VectorCraft (editable)…": spec(wrote(".vectorcraft"),
                                                            files={"save": "out:saved.vectorcraft"}, inv=False),
    "menu: File > Export As > DeckCraft slide (editable)…": spec(wrote(".deckcraft", magic=b"PK"),
                                                                files={"save": "out:saved.deckcraft"}, inv=False),
    "menu: File > Export As > PNG": spec(wrote(".png", raster=True), [("QInputDialog", number_input("150"))],
                                         files={"save": "out:saved.png"}, inv=False),
    "menu: File > Export As > TIF": spec(wrote(".tif", raster=True), [("QInputDialog", number_input("150"))],
                                         files={"save": "out:saved.tif"}, inv=False),
    "menu: File > Export As > JPEG": spec(wrote(".jpg", raster=True), [("QInputDialog", number_input("150"))],
                                          files={"save": "out:saved.jpg"}, inv=False),
    "menu: File > Export As > Print-ready TIFF (CMYK)…": spec(
        wrote(".tif", raster=True, mode="CMYK"),
        [("Print-ready", combo("cmyk")), ("Print-ready", number_input(150)), ("exported", ok)],
        files={"save": "out:saved.tif"}, inv=False),
    "menu: File > Export As > Video (animate time-stacks)…": spec(chk_video, start="stacks",
                                                                  files={"save": "out:saved.mp4"}, inv=False),
    "menu: File > Export As > Source data bundle…": spec(chk_source_data, files={"dir": "out:"}, inv=False),
    # ── Edit ──
    "menu: Edit > Undo": spec(chk_undo, before=_make_dirty, inv=False),
    "menu: Edit > Redo": spec(chk_redo, before=_duplicate_then_undo, inv=False),
    "menu: Edit > Select all": spec(chk_selection(2), sel=None, inv=False),
    "menu: Edit > Reset Selection": spec(chk_selection(None), inv=False),
    "menu: Edit > Duplicate Selection": spec(panels_added(1, name="gray8")),
    # ── Insert ──
    "menu: Insert > Images from files > To a new row…": spec(rows_are(BASE + ["row 3: cells2.png | gray16.tif"]),
                                                             files={"open_many": ["png2", "tif16"]}),
    "menu: Insert > Images from files > To a new column…": spec(
        rows_are(BASE + ["row 3: cells2.png / gray16.tif"]), files={"open_many": ["png2", "tif16"]}),
    "menu: Insert > Images from files > To a grid panel…": spec(
        rows_are(BASE + ["row 3: cells2.png | gray16.tif"]), [("Panel", grid_rows(1))],
        files={"open_many": ["png2", "tif16"]}),
    "menu: Insert > Images from files > As single images…": spec(
        rows_are(BASE + ["row 3: cells2.png", "row 4: gray16.tif"]), files={"open_many": ["png2", "tif16"]}),
    "menu: Insert > Images from files > To a row with the selected panel…": spec(
        rows_are(["row 1: (gray8.tif | cells.png) | cells2.png", BASE[1]]), files={"open_many": ["png2"]}),
    "menu: Insert > Images from files > To a column with the selected panel…": spec(
        rows_are(["row 1: (gray8.tif | cells.png) / cells2.png", BASE[1]]), files={"open_many": ["png2"]}),
    "menu: Insert > Images from files > Stack as a montage of frames…": spec(
        rows_are(BASE + ["row 3: [movie.tif x5]"]), [("Stack montage", line_edit("Which frames", "all"))],
        files={"open": "tstack"}),
    "menu: Insert > Add image from URL / OME-Zarr / OMERO…": spec(
        rows_are(BASE + ["row 3: cells2.png"]), [("URL", text_input("@png2"))]),
    "menu: Insert > Empty panel grid…": spec(panels_added(4, name="@template@"), [("Empty panel grid", ok)]),
    "menu: Insert > Data plot from CSV…": spec(panels_added(1, script=True), [("plot", ok)],
                                               files={"open_many": ["csv"], "open": "csv"}),
    "menu: Insert > Multi-channel merge…": spec(panels_added(1, script=True), [("merge", ok)],
                                                files={"open_many": ["tif8", "tif16"]}),
    "menu: Insert > Stack views > Montage of frames (time / Z)…": spec(
        rows_are(BASE + ["row 3: [zstack.tif x4]"]), [("Stack montage", line_edit("Which frames", "all"))],
        sel="zstack"),
    "menu: Insert > Stack views > Channel split (each channel + merge)…": spec(panels_added(4), [("split", ok)],
                                                                             sel="rgb"),
    "menu: Insert > Stack views > Channel split (Magenta/Green mode)…": spec(panels_added(3), sel="rgb"),
    "menu: Insert > Stack views > Kymograph along a line…": spec(panels_added(1), [("Kymograph", ok)],
                                                                start="stacks", sel="movie"),
    "menu: Insert > Stack views > Orthogonal views (XZ / YZ)…": spec(panels_added(1, script=True), [("Orthogonal", ok)],
                                                                    sel="zstack"),
    "menu: Insert > LUT colour bar…": spec(panels_added(1, script=True), [("colour bar", ok)]),
    "menu: Insert > Add equation (LaTeX)…": spec(panels_added(1, name="eq"), [("Equation (LaTeX)", equation(r"E=mc^2"))]),
    "menu: Insert > Add LaTeX code panel…": spec(panels_added(1), [("LaTeX", ok)]),
    # ── Annotations ──
    "menu: Annotations > Add scale bar to all panels…": spec(chk_scale_bars_everywhere, [("scale bar", ok)]),
    "menu: Annotations > Add zoom callout to selected panel…": spec(chk_annotation_added("inset"),
                                                                    [("zoom callout", ok)]),
    "menu: Annotations > Add arrow pointing at a feature…": spec(chk_annotation_added("roi"), [("arrow", ok)]),
    "menu: Annotations > Text style (letters, labels, scale bars…)…": spec(chk_texts_bold, [("Text style", _bold_texts)]),
    "menu: Annotations > Draw ROIs, text, crop or rotate (double-click a panel)…": spec(
        unchanged, [("Annotate the image", H.reject)], inv=False),
    "menu: Annotations > Figure colours…": spec(chk_rgb_luts(["MAGENTA", "GREEN", "BLUE"]),
                                                [("Figure colours", text_input("magenta, green, blue"))]),
    "menu: Annotations > Panel letters (A, B, C…)…": spec(all_panels(lambda p: True, ""), [("letter", ok)],
                                                          inv=False),
    "menu: Annotations > Tidy text typography (×, °, units, ranges…)": spec(chk_tidied, start="texts"),
    "menu: Annotations > Remove > Remove all annotations (ROIs, scale bars, texts, ...)": spec(
        both(chk_removed("rois", []), chk_removed("scale_bars", []), chk_removed("texts", []))),
    "menu: Annotations > Remove > Remove all scale bars": spec(chk_removed("scale_bars", [])),
    "menu: Annotations > Remove > Remove all texts": spec(chk_removed("texts", [])),
    "menu: Annotations > Remove > Remove all ROIs": spec(chk_removed("rois", [])),
    "menu: Annotations > Remove > Remove all insets": spec(chk_removed("insets", 0)),
    # ── QC ──
    "menu: QC > Audit figure (missing scale bars / labels)": spec(report_says("scale"), [("Figure audit", "report")],
                                                                 inv=False),
    "menu: QC > Check journal compliance…": spec(report_says("width"), [("Check journal compliance", ok),
                                                                       ("Journal compliance", "report")], inv=False),
    "menu: QC > Check print resolution…": spec(report_says("dpi"), [("Check print resolution", ok),
                                                                   ("Print resolution", "report")], inv=False),
    "menu: QC > Apply journal guidelines…": spec(chk_width_changed, [("guidelines", ok)]),
    "menu: QC > Enforce minimum font size…": spec(all_panels(lambda p: True, ""),
                                                  [("minimum font", number_input(9))]),
    "menu: QC > Preview figure under colour-blindness…": spec(unchanged, [("Colour-blindness preview", ok), ("deuteranopia preview", ok)],
                                                              inv=False),
    "menu: QC > Show color-blind assistant": spec(chk_window("color_assistant"), inv=False),
    "menu: QC > Check image integrity (duplicates / clones)…": spec(report_says("panel"),
                                                                   [("Image integrity", "report")], inv=False),
    "menu: QC > Check scale-bar consistency…": spec(report_says("no pixel size set", "panel D"),
                                                    [("Scale-bar consistency", "report")],
                                                    inv=False),
    "menu: QC > Pre-submission review (all checks)…": spec(report_says("Mechanical checks", "Reviewer questions"),
                                                           [("Pre-submission review", "report")], inv=False),
    "menu: QC > Adjustment provenance ledger (Methods)…": spec(report_says("panel"),
                                                              [("Adjustment provenance ledger", "report")],
                                                              inv=False),
    "menu: QC > Fonts (portable / Helvetica)…": spec(report_says("helvetica"), [("Fonts", "report")], inv=False),
    "menu: QC > Check for changed source files…": spec(unchanged, inv=False),
    "menu: QC > Remap image paths…": spec(all_panels(lambda p: True, ""), [("Remap", ok)]),
    # ── Tools ──
    "menu: Tools > Poster / collage designer…": spec(chk_window("_poster_window"), inv=False),
    "menu: Tools > Photo album designer…": spec(chk_window("_album_window"), inv=False),
    # ── View ──
    "menu: View > Show the 'double-click to edit' hint": spec(unchanged, inv=False),
    "menu: View > Show new Z stacks as max projection": spec(unchanged, inv=False),
    "menu: View > Theme > System (auto)": spec(unchanged, inv=False),
    "menu: View > Theme > Light": spec(unchanged, inv=False),
    "menu: View > Theme > Dark": spec(unchanged, inv=False),
    # ── Help ──
    "menu: Help > About": spec(unchanged, [("PyFigures:", ok)], inv=False),
    # a window beside the figure, not modal (a drop while it was open was lost)
    "menu: Help > Show Tips": spec(both(unchanged, chk_window("_tip_dialog", "TipDialog")), inv=False,
                                   before=H.real_show_tips),
    "menu: Help > List shortcuts": spec(unchanged, [("hortcut", ok)], inv=False),
    "menu: Help > User Guide": spec(unchanged, inv=False),
    # ── toolbar ──
    "toolbar: Open": spec(rows_are(["row 1: gray8.tif | cells2.png"]), files={"open": "pyf"}, inv=False),
    "toolbar: New figure": spec(chk_new, inv=False),
    "toolbar: Save": spec(chk_saved_back, before=_make_dirty, inv=False),
    "toolbar: Export as raster image": spec(wrote(".tif", raster=True), [("QInputDialog", number_input("150"))],
                            files={"save": "out:saved.tif"}, inv=False),
    "toolbar: Update selection size": spec(chk_width_changed, sel=None, before=lambda g: g.size_spinbox.setValue(300)),
    "toolbar: Undo": spec(chk_undo, before=_make_dirty, inv=False),
    "toolbar: Redo": spec(chk_redo, before=_duplicate_then_undo, inv=False),
    "toolbar: Background > None (transparent)": spec(chk_background(None), before=lambda g: g._choose_page_background(0)),
    "toolbar: Background > White": spec(chk_background(0xFFFFFF)),
    "toolbar: Background > Black": spec(chk_background(0)),
    "toolbar: Background > Other colour…": spec(chk_background(0xFF0000), [("QColorDialog", "red")]),
}

# entries whose result is checked by a dedicated test of this file
ELSEWHERE = {
    "menu: View > Show the 'double-click to edit' hint": [
        "test_gui_e2e_menus.py::test_view_toggles_change_what_they_say"],
    "menu: View > Show new Z stacks as max projection": [
        "test_gui_e2e_menus.py::test_view_toggles_change_what_they_say"],
    "menu: View > Theme > System (auto)": ["test_gui_e2e_menus.py::test_theme_entries_switch_the_palette"],
    "menu: View > Theme > Light": ["test_gui_e2e_menus.py::test_theme_entries_switch_the_palette"],
    "menu: View > Theme > Dark": ["test_gui_e2e_menus.py::test_theme_entries_switch_the_palette"],
    "menu: Help > User Guide": ["test_gui_e2e_menus.py::test_user_guide_opens_the_bundled_guide"],
    "menu: QC > Check for changed source files…": ["test_gui_e2e_menus.py::test_changed_sources_are_listed"],
    "menu: Tools > Vector PDF panels (PyMuPDF)…": [
        "test_gui_e2e_menus.py::test_vector_pdf_entry_offers_pymupdf_and_installs_nothing_on_not_now"],
    "menu: File > Review comments > Import review comments…": [
        "test_gui_e2e_menus.py::test_review_round_trip_through_the_menus"],
    "menu: File > Review comments > View review comments": [
        "test_gui_e2e_menus.py::test_review_round_trip_through_the_menus"],
}

WIDGETS = ["toolbar-widget: size_spinbox", "toolbar-widget: unit_combobox", "toolbar-widget: main_space_spinner",
           "toolbar-widget: auto_lettering_checkbox", "toolbar-widget: letter_line_edit",
           "toolbar-widget: page_bounds_checkbox"]


def _answers(spec_files, files, out, run):
    ans = {}
    for k, v in spec_files.items():
        def one(name):
            if name.startswith("out:"):
                return os.path.join(out, name[4:]) if name[4:] else out
            if name == "recipe":
                return _recipe(run, files)
            if name in ("folder_copy", "library"):
                # actions that write into the chosen folder get a copy of it
                import shutil
                dst = os.path.join(out, name)
                if name == "folder_copy":
                    shutil.copytree(files["folder"], dst)
                else:
                    os.makedirs(dst)
                    shutil.copy(files["pyf"], dst)
                return dst
            if name == "review":
                return run.get("review_html")
            return files[name]
        ans[k] = [one(x) for x in v] if isinstance(v, list) else one(v)
    return ans


def perform(qapp, g, files, file_answers, out, key, run=None):
    """Trigger menu entry *key* with the dialogs / file answers of its spec
    (also used by the tutorial tests to do what a step asks). Returns
    (pilot, run)."""
    s = ACTIONS[key]
    run = run if run is not None else {"out": str(out)}
    file_answers.update(_answers(s["files"], files, str(out), run))
    dialogs = []
    for match, handler in s["dialogs"]:
        if handler == "red":
            handler = _red
        if handler == "report":
            handler = report(run)
        if match == "URL":
            handler = text_input(files["png2"])
        dialogs.append((match, handler))
    act = H.action(g, key)
    with H.dialogs() as pilot:
        for match, handler in dialogs:
            pilot.expect(match, handler)
        pilot.expect("QMessageBox", message(run))      # optional: an info box at the end
        act.trigger()
        H.settle(qapp, g, lambda: len(pilot.queue) <= 1, timeout=40)
        H.settle(qapp, g)
    run["status"] = g.statusBar().currentMessage()
    return pilot, run


KEYS = list(ACTIONS)


@pytest.mark.parametrize("key", KEYS)
def test_menu_action(qapp, e2e_gui, e2e_files, no_file_dialogs, tmp_path, watch, key):
    s = ACTIONS[key]
    g = e2e_gui
    if H.resolve_key([k for k, _a in H.menu_actions(g)], key) is None:
        pytest.skip(f"{key!r} is no longer in the GUI (renamed beyond recognition or removed)")
    if "LaTeX code panel" in key:
        from batoolset.latex_tools import latex_available
        if not latex_available():           # it would offer to download TinyTeX
            pytest.skip("no LaTeX installation on this computer")
    out = tmp_path / "out"
    out.mkdir()
    run = {"out": str(out)}
    _start(qapp, g, tmp_path, e2e_files, s["start"])
    current = os.path.join(str(tmp_path), "current.pyf")
    g._save_state_to_file(current)
    H.load(qapp, g, current)
    if s["sel"] is not None and s["start"] != "empty":
        _select(g, s["sel"])
    if s["before"] is not None:
        s["before"](g)
        H.settle(qapp, g)
    before = H.snapshot(g, tmp_path)
    run["width0"] = H.panel(g).updateBounds().width()
    watch.check("start figure")
    pilot, run = perform(qapp, g, e2e_files, no_file_dialogs, out, key, run)
    after = H.snapshot(g, tmp_path)
    if H.RECORD:
        print(f"\n[RECORD] {key}: dialogs {pilot.seen} unexpected {pilot.unexpected} status {run['status']!r}"
              f"\n[RECORD]   out {os.listdir(str(out))} messages {run.get('messages')}"
              f"\n[RECORD]   {H.diff(before, after)}")
    assert not pilot.unexpected, f"unexpected dialog(s): {pilot.unexpected} (seen {pilot.seen})"
    missing = [m for m, _h in pilot.queue if m != "QMessageBox"]
    assert not missing, f"dialog(s) never shown: {missing}; seen {pilot.seen}"
    s["check"](g, before, after, run)
    watch.check(key)
    if s["inv"]:
        H.check_invariants(qapp, g, tmp_path, before, after)
        watch.check(f"{key}: undo / redo / reopen")


# ---------------------------------------------------------------------------
# toolbar widgets: typed / clicked like a user does
# ---------------------------------------------------------------------------

def _key(widget, key):
    from qtpy.QtCore import QEvent, Qt
    from qtpy.QtGui import QKeyEvent
    from qtpy.QtWidgets import QApplication
    for t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(t, key, Qt.KeyboardModifier.NoModifier))


def _wait_timer(qapp, g, timer):
    import time
    t0 = time.time()
    while timer.isActive() and time.time() - t0 < 5:
        qapp.processEvents()
        time.sleep(0.01)
    H.settle(qapp, g)


def _figure_width(st):
    return max(p["size"][0] for p in st["panels"][:2]) if st["panels"] else 0


@pytest.mark.parametrize("key", WIDGETS)
def test_toolbar_widget(qapp, e2e_gui, e2e_files, tmp_path, watch, key):
    from qtpy.QtCore import Qt
    g = e2e_gui
    _start(qapp, g, tmp_path, e2e_files, "base")
    before = H.snapshot(g, tmp_path)
    name = key.split(": ", 1)[1]
    w = getattr(g, name)
    check_inv = True
    if name == "size_spinbox":
        # nothing selected: the whole figure gets the typed width (Enter applies it)
        H.panel(g).set_current_selection(None)
        w.setValue(260)
        _key(w, Qt.Key.Key_Return)
        _wait_timer(qapp, g, g.value_changed_timer)
        after = H.snapshot(g, tmp_path)
        rows_w = [r.boundingRect().width() for r in H.rows(g)]
        assert all(abs(x - 260) <= 3 for x in rows_w), rows_w
        assert not H.same(before, after), "the new width is not in the saved figure"
    elif name == "unit_combobox":
        texts = {}
        for unit in ("Cm", "Inches", "mm"):
            w.setCurrentText(unit)
            texts[unit] = g.value_label.text()
        cm, inch, mm = (float(texts[u].split(chr(8776))[1]) for u in ("Cm", "Inches", "mm"))
        # (each shown with one decimal: cm is rounded before ×10)
        assert abs(mm - cm * 10) < 0.6 and abs(inch - cm / 2.54) < 0.1, texts
        after = H.snapshot(g, tmp_path)
        assert H.same(before, after)
        check_inv = False
    elif name == "main_space_spinner":
        w.setValue(12)
        _wait_timer(qapp, g, g.main_space_spinner_changed_timer)
        after = H.snapshot(g, tmp_path)
        assert str(after["space"]) in ("12", "12.0"), after["space"]
    elif name == "auto_lettering_checkbox":
        w.setChecked(False)
        H.settle(qapp, g)
        after = H.snapshot(g, tmp_path)
        assert not any(p["letters"] for p in after["panels"]), [p["letters"] for p in after["panels"]]
        w.setChecked(True)
        H.settle(qapp, g)
        back = H.snapshot(g, tmp_path)
        assert [p["letters"] for p in back["panels"]] == [p["letters"] for p in before["panels"]]
        check_inv = False
    elif name == "letter_line_edit":
        old = w.text()
        try:
            w.setText("A" if old != "A" else "a")
            H.settle(qapp, g)
            after = H.snapshot(g, tmp_path)
            letters = [x for p in after["panels"] for x in p["letters"]]
            assert letters and all(x == x.upper() for x in letters) == (w.text() == "A"), letters
        finally:
            w.setText(old)
            H.settle(qapp, g)
        check_inv = False
    elif name == "page_bounds_checkbox":
        def a4(dlg):
            H.click_button(dlg, "Done") or H.accept(dlg)
        with H.dialogs() as pilot:
            pilot.expect("Page Bounds", a4)
            w.click()
            H.settle(qapp, g, lambda: not pilot.queue, timeout=10)
        assert not pilot.queue and w.isChecked()
        b = H.panel(g).bounds
        assert b is not None and b.width() > 100 and b.height() > 100, b
        w.click()
        H.settle(qapp, g)
        assert not w.isChecked()
        after = H.snapshot(g, tmp_path)
        assert H.same(before, after)
        check_inv = False
    else:
        raise AssertionError(f"no test for {key}")
    watch.check(key)
    if check_inv:
        H.check_invariants(qapp, g, tmp_path, before, after)
        watch.check(f"{key}: undo / redo / reopen")


# ---------------------------------------------------------------------------
# entries a single table row cannot check
# ---------------------------------------------------------------------------

def _trigger(qapp, g, key, expect=(), accept_rest=False):
    act = H.action(g, key)
    with H.dialogs(accept_all=accept_rest) as pilot:
        for match, handler in expect:
            pilot.expect(match, handler)
        act.trigger()
        H.settle(qapp, g, lambda: not pilot.queue, timeout=30)
        H.settle(qapp, g)
    assert not pilot.queue, f"{key}: dialog(s) never shown {pilot.queue}; seen {pilot.seen}"
    return pilot


def test_review_round_trip_through_the_menus(qapp, e2e_gui, e2e_files, no_file_dialogs, tmp_path, watch):
    """Export for review → a reviewer pins a comment → Import review comments
    shows it → View review comments shows it again."""
    import pyfigures.gui.review as review
    g = e2e_gui
    _start(qapp, g, tmp_path, e2e_files, "base")
    g.current_file = str(tmp_path / "fig.pyf")
    g._save_state_to_file(g.current_file)
    html = str(tmp_path / "for_review.html")
    no_file_dialogs["save"] = html
    _trigger(qapp, g, "menu: File > Review comments > Export for review…",
             [("Export for review", text_input("me@lab.org")), ("Exported for review", H.reject)])
    assert os.path.isfile(html)
    payload = json.dumps({"comments": [{"x": 0.25, "y": 0.5, "text": "Panel B too dark", "author": "rev1",
                                        "ts": "2026-10-08T10:00"}], "author": "rev1", "owner_email": "me@lab.org"})
    with open(html, encoding="utf-8") as fh:
        text = fh.read()
    text = review.html_export._COMMENT_BLOCK_RE.sub(lambda m: m.group(0).replace(m.group(1), payload), text)
    reviewed = str(tmp_path / "reviewed.html")
    with open(reviewed, "w", encoding="utf-8") as fh:
        fh.write(text)
    no_file_dialogs["open"] = reviewed
    shown = []

    def look(dlg):
        from qtpy.QtWidgets import QAbstractItemView, QLabel
        words = [w.text() for w in dlg.findChildren(QLabel)]
        for view in dlg.findChildren(QAbstractItemView):
            m = view.model()
            words += [str(m.data(m.index(r, 0))) for r in range(m.rowCount())]
        shown.append((dlg.windowTitle(), " ".join(words)))
        H.reject(dlg)
    _trigger(qapp, g, "menu: File > Review comments > Import review comments…", [("Review comments (1)", look)])
    _trigger(qapp, g, "menu: File > Review comments > View review comments", [("Review comments (1)", look)])
    assert len(shown) == 2 and all("Panel B too dark" in w for _t, w in shown), shown
    assert len(review.load_sidecar_comments(g.current_file)) == 1
    watch.check("review comments")


def test_view_toggles_change_what_they_say(qapp, e2e_gui, e2e_files, tmp_path, watch):
    """'Show new Z stacks as max projection' off: a new Z stack shows its
    first slice; the hint toggle is remembered in the preferences."""
    from pyfigures.gui import user_prefs
    g = e2e_gui
    _start(qapp, g, tmp_path, e2e_files, "base")
    hint = H.action(g, "menu: View > Show the 'double-click to edit' hint")
    was = hint.isChecked()
    hint.trigger()
    assert user_prefs.load_show_edit_hint() is (not was)
    hint.trigger()
    assert user_prefs.load_show_edit_hint() is was
    proj = H.action(g, "menu: View > Show new Z stacks as max projection")
    try:
        if proj.isChecked():
            proj.trigger()
        assert user_prefs.load_max_project_z_stacks() is False
        g.all_images_directly([e2e_files["zstack"]])
        H.settle(qapp, g, lambda: len(H.images(g)) == 5)
        st = H.snapshot(g, tmp_path)
        assert st["panels"][-1]["name"] == "zstack.tif" and st["panels"][-1]["projection"] is None
        proj.trigger()
        assert user_prefs.load_max_project_z_stacks() is True
        g.all_images_directly([e2e_files["zstack"]])
        H.settle(qapp, g, lambda: len(H.images(g)) == 6)
        assert H.snapshot(g, tmp_path)["panels"][-1]["projection"] == "max"
    finally:
        if not proj.isChecked():
            proj.trigger()
    watch.check("view toggles")


def test_theme_entries_switch_the_palette(qapp, e2e_gui, watch):
    from qtpy.QtGui import QPalette
    from pyfigures.gui.theme import load_saved_theme
    g = e2e_gui
    acts = H.actions(g)
    window = QPalette.ColorRole.Window
    try:
        acts["menu: View > Theme > Dark"].trigger()
        assert qapp.palette().color(window).lightness() < 100 and load_saved_theme() == "dark"
        assert acts["menu: View > Theme > Dark"].isChecked() and not acts["menu: View > Theme > Light"].isChecked()
        acts["menu: View > Theme > Light"].trigger()
        assert qapp.palette().color(window).lightness() > 150 and load_saved_theme() == "light"
        acts["menu: View > Theme > System (auto)"].trigger()
        assert load_saved_theme() == "system" and acts["menu: View > Theme > System (auto)"].isChecked()
    finally:
        acts["menu: View > Theme > Light"].trigger()
    watch.check("themes")


def test_user_guide_opens_the_bundled_guide(qapp, e2e_gui, no_file_dialogs, watch):
    g = e2e_gui
    _trigger(qapp, g, "menu: Help > User Guide")
    urls = no_file_dialogs["browser"]
    assert urls and urls[-1].startswith("file://") and urls[-1].endswith("pyfigures_user_guide.html")
    assert os.path.isfile(urls[-1][len("file://"):])
    watch.check("user guide")


def test_vector_pdf_entry_offers_pymupdf_and_installs_nothing_on_not_now(qapp, e2e_gui, e2e_files, tmp_path,
                                                                         monkeypatch, watch):
    """Tools > Vector PDF panels (PyMuPDF)…: with PyMuPDF it says PDF panels
    are already vectors; without it, it offers the install (licence named,
    download only on Install) and 'Not now' installs nothing."""
    from pyfigures.gui import pdf_support
    g = e2e_gui
    _start(qapp, g, tmp_path, e2e_files, "base")
    key = "menu: Tools > Vector PDF panels (PyMuPDF)…"
    monkeypatch.setattr(pdf_support, "ASK_OFFSCREEN", True)     # (silent on offscreen otherwise)
    said = []

    def note(dlg):
        said.append(dlg.windowTitle() + ": " + dlg.text() + " " + dlg.informativeText())
        H.reject(dlg)
    monkeypatch.setattr(pdf_support, "has_pymupdf", lambda: True)
    _trigger(qapp, g, key, [("Vector PDF panels", note)])
    assert "already vectors" in said[-1]
    installs = []
    monkeypatch.setattr(pdf_support, "has_pymupdf", lambda: False)
    monkeypatch.setattr(pdf_support, "install_pymupdf", lambda *a, **k: installs.append(1) or (True, ""))

    def not_now(dlg):
        said.append(dlg.windowTitle() + ": " + dlg.text() + " " + dlg.informativeText())
        assert H.click_button(dlg, "Not now")
    _trigger(qapp, g, key, [("Keep PDF panels as vectors?", not_now)])
    assert "PyMuPDF" in said[-1] and "only if you click Install" in said[-1]
    assert installs == []
    watch.check(key)


def test_changed_sources_are_listed(qapp, e2e_gui, e2e_files, no_file_dialogs, tmp_path, watch):
    """Save, change a source image on disk, QC > Check for changed source
    files names it and Yes re-reads it."""
    import shutil
    import numpy as np
    from batoolset.img import Img
    from pyfigures import mcp_server as M
    g = e2e_gui
    src = tmp_path / "src"
    src.mkdir()
    a = shutil.copy(e2e_files["tif8"], src / "a.tif")
    b = shutil.copy(e2e_files["png"], src / "b.png")
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], str(a))
    M.add_image(pyf, [0], str(b))
    H.load(qapp, g, pyf)
    _trigger(qapp, g, "menu: File > Save")          # writes the sources snapshot
    said = []

    def note(dlg):
        said.append(dlg.text())
        H.accept(dlg)
    _trigger(qapp, g, "menu: QC > Check for changed source files…", [("Changed source files", note)])
    assert "unchanged" in said[-1]
    Img(np.full((40, 60), 7, np.uint8), dimensions="hw").save(str(a))
    os.utime(str(a), (1e9, 1e9))
    _trigger(qapp, g, "menu: QC > Check for changed source files…", [("Changed source files", note)])
    assert "a.tif" in said[-1] and "b.png" not in said[-1]
    H.settle(qapp, g)
    assert "re-read" in g.statusBar().currentMessage()
    watch.check("changed sources")
