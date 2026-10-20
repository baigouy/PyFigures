"""End-to-end canvas right-click menu (marker ``gui_e2e``).

For every kind of selection (nothing, an image in a row, a standalone image,
several images, a row, a label row, an equation, an inset, a template slot,
an RGB image, a Z stack) the menu is opened by a real right-click (mouse
press + release through the canvas handlers), its entries are compared with
what that selection must offer, and EVERY entry is run: its dialog really
executes and is answered by clicking its buttons, then the result is read
back from the saved file (layout rows + panel properties), undo / redo and a
save / reopen are checked, and no exception / Qt warning / logged error may
appear.
"""
from __future__ import annotations

import pytest

import gui_e2e_harness as H
from gui_e2e_harness import e2e_files, e2e_gui, menus, watch  # noqa: F401

pytestmark = pytest.mark.gui_e2e


# ---------------------------------------------------------------------------
# what each selection offers
# ---------------------------------------------------------------------------

COMMON = ["Add Empty Image", "Duplicate Selection", "Convert to template"]
LABELS = ["Add labels ▶ / Above the row", "Add labels ▶ / Below the row",
          "Add labels ▶ / Left / top of row/col", "Add labels ▶ / Right / bottom of row/col"]
REMOVE = ["Remove annotations ▶ / Remove all (ROIs, scale bars, texts, …)", "Remove annotations ▶ / Scale bars",
          "Remove annotations ▶ / Texts", "Remove annotations ▶ / ROIs", "Remove annotations ▶ / Insets"]
CROP = ["Crop & size ▶ / Force same width and height", "Crop & size ▶ / Force same aspect ratio",
        "Crop & size ▶ / Force same crop, rotation and bg", "Crop & size ▶ / Reset crop and rotation",
        "Crop & size ▶ / Reset crop only", "Crop & size ▶ / Reset rotation only"]
LOOK = ["Appearance ▶ / Set LUT(s)", "Appearance ▶ / Reset LUT(s)", "Appearance ▶ / Set background",
        "Appearance ▶ / Reset background"]
TEXT = ["Text & lettering ▶ / Change font (non-Letter text)",
        "Text & lettering ▶ / Change background (non-Letter text)",
        "Text & lettering ▶ / Change lettering parameters"]
TAIL = REMOVE + CROP + LOOK + TEXT + ["Ignore"]
IMAGE = ["Edit Image"] + COMMON + ["Extrude (remove from group)"] + LABELS + TAIL

OFFERED = {
    "nothing": ["Add Empty Image", "Ignore"],
    "image": IMAGE,
    "inset": IMAGE,
    "standalone image": ["Edit Image"] + COMMON + LABELS + TAIL,
    "template slot": ["Edit Image"] + COMMON + LABELS + TAIL,
    "several images": COMMON + ["Extrude (remove from group)", "↔  To row", "↕  To column", "▦  To panel",
                                "Reshape to panel (if possible)", "Change space between elements"] + TAIL,
    "row": ["Edit Group (orientation/space)"] + COMMON + ["Extrude (remove from group)",
                                                          "Reshape to panel (if possible)",
                                                          "Change space between elements"] + LABELS + TAIL,
    "text row": ["Edit text", "Edit text row"],
    "equation": ["Edit Image", "Edit equation…"] + IMAGE[1:],
    "rgb image": IMAGE[:-len(TAIL)] + ["Split ▶ / Channel split (Gray mode)",
                                       "Split ▶ / Channel split (Magenta/Green mode)"] + TAIL,
    "z stack": IMAGE[:-len(TAIL)] + ["Split ▶ / Split by a dimension"] + TAIL,
}


@pytest.fixture(scope="module")
def selection_pyf(qapp, e2e_gui, e2e_files, tmp_path_factory):
    """The selection figure, built once through the GUI's own code:
    row 1 = gray8 | cells (with a label row above), row 2 = rgb | zstack |
    equation, a standalone gray16 and a template slot."""
    d = tmp_path_factory.mktemp("selection")
    H.prepare_selection_figure(qapp, e2e_gui, d, e2e_files)
    pyf = str(d / "selection.pyf")
    e2e_gui._save_state_to_file(pyf)
    return pyf


@pytest.fixture
def fig(qapp, e2e_gui, selection_pyf):
    H.load(qapp, e2e_gui, selection_pyf)
    return e2e_gui


def test_each_selection_offers_its_entries(qapp, fig, menus, watch):
    for kind in H.SELECTION_KINDS:
        shape, pos, select = H.select_kind(qapp, fig, kind)
        assert H.right_click(fig, menus, shape, pos=pos, select=select) == OFFERED[kind], kind
    watch.check("right-click menus")


# ---------------------------------------------------------------------------
# what each entry does
# ---------------------------------------------------------------------------

def _names(st):
    return [p["name"] for p in st["panels"] if not p["text"]]


def _sel_names(ctx):
    return ctx["selected"]


def _accept_custom(fill=None):
    def h(dlg):
        if fill is not None:
            fill(dlg)
        H.accept(dlg)
    return h


def _spin_value(value, index=0):
    def fill(dlg):
        from qtpy.QtWidgets import QSpinBox, QDoubleSpinBox
        spins = dlg.findChildren(QSpinBox) + dlg.findChildren(QDoubleSpinBox)
        spins[index].setValue(value)
    return fill


def _pick_combo(text):
    def fill(dlg):
        from qtpy.QtWidgets import QComboBox
        for c in dlg.findChildren(QComboBox):
            i = c.findText(text)
            if i >= 0:
                c.setCurrentIndex(i)
                return
        raise AssertionError(f"no combo with {text!r}")
    return fill


def _column(dlg):
    from qtpy.QtWidgets import QRadioButton, QComboBox
    for r in dlg.findChildren(QRadioButton):
        if "col" in r.text().lower() or r.text().strip().upper() == "Y":
            r.setChecked(True)
            return
    for c in dlg.findChildren(QComboBox):
        for i in range(c.count()):
            if c.itemText(i).strip().upper() in ("Y", "COLUMN", "VERTICAL"):
                c.setCurrentIndex(i)
                return
    raise AssertionError("no column choice")


def _rgb_colour(dlg):
    """QColorDialog / colour picker: choose pure red, accept."""
    from qtpy.QtGui import QColor
    from qtpy.QtWidgets import QColorDialog
    if isinstance(dlg, QColorDialog):
        dlg.setCurrentColor(QColor(255, 0, 0))
    H.accept(dlg)


def _pick_bg(dlg):
    """Background dialog: click the colour swatch (a QColorDialog opens and
    is answered by the next queued handler), then OK."""
    from qtpy.QtWidgets import QPushButton
    swatch = next(b for b in dlg.findChildren(QPushButton) if not b.text())
    swatch.click()
    H.accept(dlg)


BG = [("Select a background color", _pick_bg), ("QColorDialog", _rgb_colour)]


def _changed(before, after, key, names):
    out = {}
    for b, a in zip(before["panels"], after["panels"]):
        if a["name"] in names and b["name"] == a["name"]:
            out[a["name"]] = (b[key], a[key])
    return out


def chk_unchanged(before, after, ctx):
    assert H.same(before, after), H.diff(before, after)


def chk_empty_added(before, after, ctx):
    assert _names(after).count("(empty)") + sum(1 for n in _names(after) if n is None) == \
        _names(before).count("(empty)") + sum(1 for n in _names(before) if n is None) + 1, H.diff(before, after)
    assert len(after["panels"]) == len(before["panels"]) + 1


def chk_duplicated(before, after, ctx):
    sel = _sel_names(ctx)
    for n in set(sel):
        assert _names(after).count(n) == _names(before).count(n) + sel.count(n), (n, H.diff(before, after))


def chk_templated(before, after, ctx):
    sel = [n for n in _sel_names(ctx) if n != "@template@"]
    for n in set(sel):
        assert _names(after).count(n) < _names(before).count(n), (n, H.diff(before, after))
    assert _names(after).count("@template@") >= _names(before).count("@template@") + len(sel)


def chk_extruded(before, after, ctx):
    sel = _sel_names(ctx)
    tops = [r.split(": ", 1)[1] for r in after["rows"]]
    for n in sel:
        assert n in tops, (n, after["rows"])
    assert sorted(_names(after)) == sorted(_names(before))


def chk_grouped(orientation):
    def chk(before, after, ctx):
        sel = _sel_names(ctx)
        sep = " | " if orientation == "X" else " / "
        assert any(sep.join(sel) in r for r in after["rows"]), (sel, after["rows"])
        assert sorted(_names(after)) == sorted(_names(before))
    return chk


def chk_panel(before, after, ctx):
    assert sorted(_names(after)) == sorted(_names(before)), H.diff(before, after)
    assert after["rows"] != before["rows"]


def chk_same_images(before, after, ctx):
    assert sorted(n for n in _names(after) if n not in (None, "(empty)")) == \
        sorted(n for n in _names(before) if n not in (None, "(empty)")), H.diff(before, after)


def chk_space(before, after, ctx):
    assert any(sp == 11.0 for _o, sp in after["groups"]), after["groups"]


def chk_orientation(before, after, ctx):
    assert ("Y", 3.0) in after["groups"] and after["groups"] != before["groups"], after["groups"]


def chk_label_row(before, after, ctx):
    n_text = lambda st: sum(1 for p in st["panels"] if p["text"])  # noqa: E731
    assert n_text(after) > n_text(before), H.diff(before, after)
    assert sorted(_names(after)) == sorted(_names(before))


def chk_split(n_new):
    def chk(before, after, ctx):
        sel = _sel_names(ctx)[0]
        assert _names(after).count(sel) >= _names(before).count(sel) + n_new - 1, H.diff(before, after)
    return chk


def chk_removed(kind_key, value_empty):
    def chk(before, after, ctx):
        sel = set(_sel_names(ctx))
        for b, a in zip(before["panels"], after["panels"]):
            if a["name"] in sel and not a["text"]:
                assert a[kind_key] == value_empty, (a["name"], kind_key, a[kind_key])
            elif b["name"] == a["name"]:
                assert a[kind_key] == b[kind_key], ("other panel touched", a["name"], kind_key)
    return chk


def chk_remove_all(before, after, ctx):
    sel = set(_sel_names(ctx))
    for a in after["panels"]:
        if a["name"] in sel and not a["text"]:
            assert not a["scale_bars"] and not a["rois"] and not a["insets"] and not a["texts"], a


def chk_crop_reset(crop, rot):
    def chk(before, after, ctx):
        sel = set(_sel_names(ctx))
        for a in after["panels"]:
            if a["name"] in sel:
                if crop:
                    assert a["crop"] == (0.0, 0.0, 0.0, 0.0), a
                if rot:
                    assert a["theta"] in (None, 0, 0.0), a
    return chk


def chk_same_size(before, after, ctx):
    sel = [p for p in after["panels"] if p["name"] in set(_sel_names(ctx))]
    if len(sel) > 1:
        assert len({p["size"] for p in sel}) == 1 or \
            max(abs(p["size"][0] - sel[0]["size"][0]) for p in sel) <= 1, [p["size"] for p in sel]


def chk_same_ar(before, after, ctx):
    sel = [p for p in after["panels"] if p["name"] in set(_sel_names(ctx))]
    ars = [p["size"][0] / max(1, p["size"][1]) for p in sel]
    assert max(ars) - min(ars) < 0.06, ars


def chk_luts_set(before, after, ctx):
    sel = set(_sel_names(ctx))
    assert any(a["luts"] for a in after["panels"] if a["name"] in sel), H.diff(before, after)


def chk_luts_reset(before, after, ctx):
    sel = set(_sel_names(ctx))
    assert all(not a["luts"] for a in after["panels"] if a["name"] in sel), H.diff(before, after)


def chk_bg_set(before, after, ctx):
    sel = set(_sel_names(ctx))
    assert any(a["fill"] not in (None, 0) for a in after["panels"] if a["name"] in sel), H.diff(before, after)


def chk_bg_reset(before, after, ctx):
    sel = set(_sel_names(ctx))
    assert all(a["fill"] in (None, 0) for a in after["panels"] if a["name"] in sel), H.diff(before, after)


def chk_text_bg(before, after, ctx):
    sel = set(_sel_names(ctx))
    for b, a in zip(before["panels"], after["panels"]):
        if a["name"] in sel and a["texts"]:
            assert a["text_fill"] != b["text_fill"] and all(f != "None" for f in a["text_fill"]), a
        else:
            assert a["text_fill"] == b["text_fill"], ("other text touched", a["name"])


def chk_no_error(before, after, ctx):
    """Dialog-only entries whose effect is checked by their own dialog test."""


# entry → (dialogs [(title/class, handler)], check, run undo/redo/reopen?)
ENTRIES = {
    "Ignore": ([], chk_unchanged, False),
    "Add Empty Image": ([("Add empty image", _accept_custom())], chk_empty_added, True),
    "Duplicate Selection": ([], chk_duplicated, True),
    "Convert to template": ([], chk_templated, True),
    "Extrude (remove from group)": ([], chk_extruded, True),
    "↔  To row": ([], chk_grouped("X"), True),
    "↕  To column": ([], chk_grouped("Y"), True),
    "▦  To panel": ([("Panel", _accept_custom())], chk_panel, True),
    "Reshape to panel (if possible)": ([("Reorganize as a panel", _accept_custom())], chk_same_images, True),
    "Change space between elements": ([("Change space", _accept_custom(_spin_value(11)))], chk_space, True),
    "Edit Group (orientation/space)": ([("Row Or Column", _accept_custom(_column))], chk_orientation, True),
    "Add labels ▶ / Above the row": ([], chk_label_row, True),
    "Add labels ▶ / Below the row": ([], chk_label_row, True),
    "Add labels ▶ / Left / top of row/col": ([], chk_label_row, True),
    "Add labels ▶ / Right / bottom of row/col": ([], chk_label_row, True),
    "Split ▶ / Channel split (Gray mode)": ([], chk_split(3), True),
    "Split ▶ / Channel split (Magenta/Green mode)": ([], chk_split(3), True),
    "Split ▶ / Split by a dimension": ([("Split", _accept_custom())], chk_split(4), True),
    "Remove annotations ▶ / Remove all (ROIs, scale bars, texts, …)": ([], chk_remove_all, True),
    "Remove annotations ▶ / Scale bars": ([], chk_removed("scale_bars", []), True),
    "Remove annotations ▶ / Texts": ([], chk_removed("texts", []), True),
    "Remove annotations ▶ / ROIs": ([], chk_removed("rois", []), True),
    "Remove annotations ▶ / Insets": ([], chk_removed("insets", 0), True),
    "Crop & size ▶ / Force same width and height": ([], chk_same_size, True),
    "Crop & size ▶ / Force same aspect ratio": ([], chk_same_ar, True),
    "Crop & size ▶ / Force same crop, rotation and bg": ([], chk_same_images, True),
    "Crop & size ▶ / Reset crop and rotation": ([], chk_crop_reset(True, True), True),
    "Crop & size ▶ / Reset crop only": ([], chk_crop_reset(True, False), True),
    "Crop & size ▶ / Reset rotation only": ([], chk_crop_reset(False, True), True),
    "Appearance ▶ / Set LUT(s)": ([("Edit Look Up Tables (LUTs)", _accept_custom(_pick_combo("GREEN")))],
                                  chk_luts_set, True),
    "Appearance ▶ / Reset LUT(s)": ([], chk_luts_reset, True),
    "Appearance ▶ / Set background": (BG, chk_bg_set, True),
    "Appearance ▶ / Reset background": ([], chk_bg_reset, True),
    "Text & lettering ▶ / Change font (non-Letter text)": ([("Select a Font", _accept_custom())],
                                                           chk_same_images, False),
    "Text & lettering ▶ / Change background (non-Letter text)": (BG, chk_text_bg, True),
    "Text & lettering ▶ / Change lettering parameters": ([("Auto lettering", _accept_custom())],
                                                         chk_same_images, False),
    "Edit Image": ([("Annotate the image", H.reject)], chk_unchanged, False),
    "Edit text": ([("Annotate the image", H.reject)], chk_unchanged, False),
    "Edit text row": ([("Edit labels", H.reject)], chk_unchanged, False),
    "Edit equation…": ([("equation", H.reject)], chk_unchanged, False),
}

CASES = [(kind, entry) for kind, entries in OFFERED.items() for entry in entries]


def _selected_names(g):
    sel = H.panel(g).selected_shape
    sel = sel if isinstance(sel, list) else [sel]
    out = []
    for s in sel:
        if s is None:
            continue
        for i in H.images(s):
            fn = i.filename
            out.append(fn if fn == "@template@" else (H.os.path.basename(str(fn)) if fn else None))
    return out


@pytest.mark.parametrize("kind,entry", CASES, ids=[f"{k}-{e}" for k, e in CASES])
def test_right_click_entry(qapp, fig, tmp_path, menus, watch, kind, entry):
    g = fig
    dlgs, check, invariants = ENTRIES[entry]
    before = H.snapshot(g, tmp_path)
    watch.check("loading")
    shape, pos, select = H.select_kind(qapp, g, kind)
    if select and shape is not None:
        H.panel(g).set_current_selection(shape)
    ctx = {"kind": kind, "selected": _selected_names(g)}
    with H.dialogs() as pilot:
        for match, handler in dlgs:
            pilot.expect(match, handler)
        H.right_click(g, menus, shape, pos=pos, select=False, pick=entry)
        H.settle(qapp, g, lambda: not pilot.queue, timeout=20)
        H.settle(qapp, g)
    if H.RECORD:
        print(f"\n[RECORD] {kind} / {entry}: dialogs {pilot.seen} unexpected {pilot.unexpected}")
    assert not pilot.unexpected, f"unexpected dialog(s): {pilot.unexpected}"
    assert not pilot.queue, f"dialog(s) never shown: {[m for m, _h in pilot.queue]}; seen {pilot.seen}"
    after = H.snapshot(g, tmp_path)
    if H.RECORD:
        print(f"[RECORD]   {H.diff(before, after)}")
    check(before, after, ctx)
    watch.check(f"{kind} / {entry}")
    if invariants:
        H.check_invariants(qapp, g, tmp_path, before, after)
        watch.check(f"{kind} / {entry}: undo / redo / reopen")
