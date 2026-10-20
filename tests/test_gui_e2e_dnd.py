"""End-to-end drag and drop in the figure editor (marker ``gui_e2e``).

External drops: real QDragEnterEvent / QDragMoveEvent / QDropEvent carrying
file URLs at a computed canvas position, then a click on the in-window drop
menu's button, with any dialog that follows really executed and answered.
Internal drags: mouse press / move / release sent through the canvas
handlers, then the drop menu's entry.

Every scenario checks the RESULT on the saved file — the actual arrangement
(``layout_rows``) and the key properties of the new panels — then that undo
gives the starting figure back, redo the result, and a save / reopen keeps
it; no exception, Qt warning or logged error is allowed on the way.
"""
from __future__ import annotations

import os

import pytest

import gui_e2e_harness as H
from gui_e2e_harness import e2e_files, e2e_gui, menus, no_file_dialogs, watch  # noqa: F401

pytestmark = pytest.mark.gui_e2e

BASE = ["row 1: gray8.tif | cells.png", "row 2: rgb.tif | zstack.tif"]
LOOSE = BASE + ["row 3: gray16.tif"]
SLOT = BASE + ["row 3: (template slot)"]


# ---------------------------------------------------------------------------
# start figures
# ---------------------------------------------------------------------------

def start(qapp, g, d, files, kind="base"):
    H.load(qapp, g, H.base_figure(d, files))
    if kind in ("loose", "slot"):
        g.all_images_directly([files["tif16"]])
        H.settle(qapp, g, lambda: len(H.images(g)) == 5)
        if kind == "slot":
            H.panel(g).templatify(H.by_name(g, "gray16"))
        H.panel(g).set_current_selection(None)
        pyf = os.path.join(str(d), f"start_{kind}.pyf")
        g._save_state_to_file(pyf)
        H.load(qapp, g, pyf)              # a clean undo history starting here


# ---------------------------------------------------------------------------
# external drops
# ---------------------------------------------------------------------------

def _montage_all(dlg):
    from qtpy.QtWidgets import QLineEdit
    H.widget_by(dlg, QLineEdit, label="Which frames").setText("all")
    H.accept(dlg)


def _series_2(dlg):
    from qtpy.QtWidgets import QListWidget
    dlg.findChild(QListWidget).setCurrentRow(1)
    H.click_button(dlg, "Open")


def _panel(rows):
    def fill(dlg):
        from qtpy.QtWidgets import QRadioButton, QSpinBox
        H.widget_by(dlg, QRadioButton, label="Specify Rows").setChecked(True)
        dlg.findChildren(QSpinBox)[0].setValue(rows)
        H.accept(dlg)
    return fill


# (situation, files, where, start figure, choice, dialogs, expected rows, check)
#   where: None = empty canvas, or the stem of the panel dropped onto
DROPS = [
    ("one image on empty canvas", ["png2"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: cells2.png"], None),
    ("one image on empty canvas", ["png2"], None, "base", "✕  Cancel", [], BASE, None),
    ("several images on empty canvas", ["png2", "tif16"], None, "base", "↔  To row", [],
     BASE + ["row 3: cells2.png | gray16.tif"], lambda a: a["groups"][-1][0] == "X"),
    ("several images on empty canvas", ["png2", "tif16"], None, "base", "↕  To column", [],
     BASE + ["row 3: cells2.png / gray16.tif"], lambda a: a["groups"][-1][0] == "Y"),
    ("several images on empty canvas", ["png2", "tif16", "tif8"], None, "base", "▦  To panel",
     [("Panel", _panel(2))], BASE + ["row 3: cells2.png | gray16.tif", "row 4: gray8.tif | (empty)"], None),
    ("several images on empty canvas", ["png2", "tif16"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: cells2.png", "row 4: gray16.tif"], None),
    ("several images on empty canvas", ["png2", "tif16"], None, "base", "✕  Cancel", [], BASE, None),
    ("onto an image", ["png2"], "gray16", "loose", "↔  To row (with image below)", [],
     BASE + ["row 3: gray16.tif | cells2.png"], None),
    ("onto an image", ["png2"], "gray16", "loose", "↕  To column (with image below)", [],
     BASE + ["row 3: gray16.tif / cells2.png"], None),
    ("onto an image", ["png2"], "gray16", "loose", "➕  As single image(s)", [],
     LOOSE + ["row 4: cells2.png"], None),
    ("onto a group", ["png2"], "gray8", "base", "↔  To row (with image below)", [],
     ["row 1: (gray8.tif | cells.png) | cells2.png", BASE[1]], None),
    ("onto a group", ["png2"], "gray8", "base", "↕  To column (with image below)", [],
     ["row 1: (gray8.tif | cells.png) / cells2.png", BASE[1]], None),
    ("onto a group", ["png2"], "gray8", "base", "➕  As single image(s)", [],
     BASE + ["row 3: cells2.png"], None),
    ("onto a template slot", ["png2"], "@template@", "slot", "⬜  Assign to template slot", [],
     BASE + ["row 3: cells2.png"], None),
    ("onto a template slot", ["png2"], "@template@", "slot", "➕  As single image(s)", [],
     SLOT + ["row 4: cells2.png"], None),
    ("one time stack", ["tstack"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: movie.tif"], lambda a: a["panels"][-1]["projection"] is None),
    ("one time stack", ["tstack"], None, "base", "🎞  Montage of frames (time / Z)…",
     [("Stack montage", _montage_all)], BASE + ["row 3: [movie.tif x5]"], None),
    ("one z stack", ["zstack"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: zstack.tif"], lambda a: a["panels"][-1]["projection"] == "max"),
    ("one z stack", ["zstack"], None, "base", "🎞  Montage of frames (time / Z)…",
     [("Stack montage", _montage_all)], BASE + ["row 3: [zstack.tif x4]"], None),
    (".tex", ["tex"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: eq_*.svg"], None),
    ("folder", ["folder"], None, "base", "↔  To row", [], BASE + ["row 3: f1.png | f2.png"], None),
    ("folder", ["folder"], None, "base", "↕  To column", [], BASE + ["row 3: f1.png / f2.png"], None),
    ("folder", ["folder"], None, "base", "▦  To panel", [("Panel", _panel(1))],
     BASE + ["row 3: f1.png | f2.png"], None),
    ("folder", ["folder"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: f1.png", "row 4: f2.png"], None),
    ("a stack among several images", ["tstack", "png2"], None, "base", "↔  To row", [],
     BASE + ["row 3: movie.tif | cells2.png"], None),
    ("a stack among several images", ["tstack", "png2"], None, "base", "↕  To column", [],
     BASE + ["row 3: movie.tif / cells2.png"], None),
    ("a stack among several images", ["tstack", "png2"], None, "base", "▦  To panel", [("Panel", _panel(1))],
     BASE + ["row 3: movie.tif | cells2.png"], None),
    ("a stack among several images", ["tstack", "png2"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: movie.tif", "row 4: cells2.png"], None),
    ("unsupported file", ["txt", "png2"], None, "base", "➕  As single image(s)", [],
     BASE + ["row 3: cells2.png"], None),
    ("multi-series file", ["pdf2"], None, "base", "➕  As single image(s)", [("Select Series", _series_2)],
     BASE + ["row 3: two_pages.pdf"], lambda a: a["panels"][-1]["series"] == 1),
    ("video", ["video"], None, "base", "➕  As single image(s)", [], BASE + ["row 3: clip.mp4"], None),
    ("video", ["video"], None, "base", "🎞  Montage of frames (time / Z)…",
     [("Stack montage", _montage_all)], BASE + ["row 3: [clip.mp4 x6]"], None),
]

DROP_IDS = [f"{s[0]}-{s[4].strip('➕↔↕▦⬜🎞✕ ')}" for s in DROPS]


def _where(g, stem):
    if stem is None:
        return None
    if stem == "@template@":
        return H.centre(g, next(i for i in H.images(g) if i.filename == "@template@"))
    return H.centre(g, H.by_name(g, stem))


@pytest.mark.parametrize("situation,names,where,kind,choice,dlgs,rows,check", DROPS, ids=DROP_IDS)
def test_drop(qapp, e2e_gui, e2e_files, tmp_path, watch, situation, names, where, kind, choice, dlgs,
              rows, check):
    g = e2e_gui
    start(qapp, g, tmp_path, e2e_files, kind)
    before = H.snapshot(g, tmp_path)
    watch.check("loading the start figure")
    assert H.drop_files(g, [e2e_files[n] for n in names], _where(g, where))
    live = H.offered_as(H.drop_choices(g), choice)
    if live is None:
        H.dismiss_drop_menu(g)
        pytest.skip(f"{choice!r} is no longer offered ({situation}); "
                    "test_drop_menu_offers_what_each_situation_allows says whether it should be")
    with H.dialogs() as pilot:
        for match, handler in dlgs:
            pilot.expect(match, handler)
        H.click_drop_choice(g, live)
        H.settle(qapp, g, lambda: not pilot.queue, timeout=30)
        H.settle(qapp, g)
    assert not pilot.queue, f"dialog(s) never shown: {pilot.queue}; seen {pilot.seen}"
    assert not pilot.unexpected, f"unexpected dialog(s): {pilot.unexpected}"
    assert H.drop_menu(g) is None
    after = H.snapshot(g, tmp_path)
    H.expect_rows(after, rows, f"{situation} → {choice}")
    if check is not None:
        assert check(after), (after["panels"][-1], H.diff(before, after))
    watch.check(f"{situation} → {choice}")
    H.check_invariants(qapp, g, tmp_path, before, after)
    watch.check(f"{situation} → {choice}: undo / redo / reopen")


def test_drop_without_menu(qapp, e2e_gui, e2e_files, tmp_path, watch):
    """.pyf: merged straight away; CSV / text alone: refused, said in the
    status bar, figure untouched; a plain text drag is not even accepted."""
    from qtpy.QtCore import QMimeData, Qt
    from qtpy.QtGui import QDragEnterEvent
    g = e2e_gui
    start(qapp, g, tmp_path, e2e_files)
    before = H.snapshot(g, tmp_path)
    H.drop_files(g, [e2e_files["pyf"]])
    H.settle(qapp, g, lambda: len(H.images(g)) == 6)
    assert H.drop_menu(g) is None
    after = H.snapshot(g, tmp_path)
    H.expect_rows(after, BASE + ["row 3: gray8.tif | cells2.png"], ".pyf drop")
    H.check_invariants(qapp, g, tmp_path, before, after)
    for name in ("csv", "txt"):
        start(qapp, g, tmp_path, e2e_files)
        H.drop_files(g, [e2e_files[name]])
        assert H.drop_menu(g) is None
        assert os.path.basename(e2e_files[name]) in g.statusBar().currentMessage()
        assert H.same(H.snapshot(g, tmp_path), before)
    mime = QMimeData()
    mime.setText("hello")
    ev = QDragEnterEvent(H.window_pos(g, H.empty_point(g)).toPoint(), Qt.DropAction.CopyAction, mime,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    g.dragEnterEvent(ev)
    assert not ev.isAccepted()
    watch.check("drops without a menu")


_SINGLE = ["➕  As single image(s)", "✕  Cancel"]
_GROUP = ["↔  To row", "↕  To column", "▦  To panel"]
_COMBINE = ["↔  To row (with image below)", "↕  To column (with image below)"]
_MONTAGE = ["➕  As single image(s)", "🎞  Montage of frames (time / Z)…", "✕  Cancel"]

# (situation, start figure, files, where, the drop menu's buttons)
DROP_OFFERS = [
    ("one image on empty canvas", "base", ["png2"], None, _SINGLE),
    ("several images on empty canvas", "base", ["png2", "tif16"], None, _GROUP + _SINGLE),
    ("one time stack", "base", ["tstack"], None, _MONTAGE),
    ("one z stack", "base", ["zstack"], None, _MONTAGE),
    ("video", "base", ["video"], None, _MONTAGE),
    ("a stack among several images", "base", ["tstack", "png2"], None, _GROUP + _SINGLE),  # no montage
    ("multi-series file", "base", ["pdf2"], None, _SINGLE),
    (".tex", "base", ["tex"], None, _SINGLE),
    ("folder", "base", ["folder"], None, _GROUP + _SINGLE),
    ("unsupported file", "base", ["txt", "png2"], None, _SINGLE),
    ("onto an image", "loose", ["png2"], "gray16", _COMBINE + _SINGLE),
    ("onto a group", "base", ["png2"], "gray8", _COMBINE + _SINGLE),
    ("onto a template slot", "slot", ["png2"], "@template@", _SINGLE[:1] + ["⬜  Assign to template slot",
                                                                           "✕  Cancel"]),
]


def test_drop_menu_offers_what_each_situation_allows(qapp, e2e_gui, e2e_files, tmp_path, watch):
    """... and Cancel (how the menu is dismissed here) leaves the figure as it was."""
    g = e2e_gui
    for situation, kind, names, where, expected in DROP_OFFERS:
        start(qapp, g, tmp_path, e2e_files, kind)
        before = H.snapshot(g, tmp_path)
        H.drop_files(g, [e2e_files[n] for n in names], _where(g, where))
        assert not H.missing_entries(expected, H.drop_choices(g)), (situation, H.drop_choices(g))
        H.dismiss_drop_menu(g)
        H.settle(qapp, g)
        assert H.drop_menu(g) is None
        assert H.same(H.snapshot(g, tmp_path), before), (situation, "Cancel changed the figure")
    watch.check("drop menus")


# ---------------------------------------------------------------------------
# internal drags on the canvas
# ---------------------------------------------------------------------------

def _drag_start(qapp, g, d, files):
    """Rows [gray8 cells] [rgb zstack] + two loose images gray16, cells2."""
    H.load(qapp, g, H.base_figure(d, files))
    g.all_images_directly([files["tif16"], files["png2"]])
    H.settle(qapp, g, lambda: len(H.images(g)) == 6)
    H.panel(g).set_current_selection(None)
    pyf = os.path.join(str(d), "start_drag.pyf")
    g._save_state_to_file(pyf)
    H.load(qapp, g, pyf)


def _loose(g):
    return [s for s in H.panel(g).shapes_to_draw if type(s).__name__ == "Image2D"]


DRAG_FROM_TO = {
    "image onto image of another row": lambda g: (H.by_name(g, "gray8"), H.centre(g, H.by_name(g, "rgb"))),
    "row onto row": lambda g: (H.rows(g)[0], H.centre(g, H.rows(g)[1])),
    "loose image onto loose image": lambda g: (_loose(g)[0], H.centre(g, _loose(g)[1])),
    "row onto loose image": lambda g: (H.rows(g)[0], H.centre(g, _loose(g)[0])),
    "image to empty space": lambda g: (H.by_name(g, "cells"), H.empty_point(g)),
    "loose image onto image in row": lambda g: (_loose(g)[0], H.centre(g, H.by_name(g, "rgb"))),
}

R1, R2 = "gray8.tif | cells.png", "rgb.tif | zstack.tif"
DRAGS = [
    ("image onto image of another row", "Swap",
     ["row 1: rgb.tif | cells.png", "row 2: gray8.tif | zstack.tif", "row 3: gray16.tif", "row 4: cells2.png"]),
    ("image onto image of another row", "Add to group (keep dragged shape layout)",
     ["row 1: cells.png", "row 2: rgb.tif | zstack.tif | gray8.tif", "row 3: gray16.tif", "row 4: cells2.png"]),
    ("image onto image of another row", "Add to group (don't keep dragged shape layout)",
     ["row 1: cells.png", "row 2: rgb.tif | zstack.tif | gray8.tif", "row 3: gray16.tif", "row 4: cells2.png"]),
    # a row inside a new row is the same row: "To row" onto a row extends it
    ("image onto image of another row", "To row",
     ["row 1: cells.png", "row 2: rgb.tif | zstack.tif | gray8.tif", "row 3: gray16.tif", "row 4: cells2.png"]),
    ("image onto image of another row", "To column",
     ["row 1: cells.png", "row 2: (rgb.tif | zstack.tif) / gray8.tif", "row 3: gray16.tif", "row 4: cells2.png"]),
    ("row onto row", "Swap",
     [f"row 1: {R2}", f"row 2: {R1}", "row 3: gray16.tif", "row 4: cells2.png"]),
    ("row onto row", "Add to group (keep dragged shape layout)",
     [f"row 1: {R2} | ({R1})", "row 2: gray16.tif", "row 3: cells2.png"]),
    ("row onto row", "Add to group (don't keep dragged shape layout)",
     [f"row 1: {R2} | {R1}", "row 2: gray16.tif", "row 3: cells2.png"]),
    ("row onto row", "To row",
     [f"row 1: {R2} | {R1}", "row 2: gray16.tif", "row 3: cells2.png"]),
    ("row onto row", "To column",
     [f"row 1: ({R2}) / ({R1})", "row 2: gray16.tif", "row 3: cells2.png"]),
    ("loose image onto loose image", "Swap",
     [f"row 1: {R1}", f"row 2: {R2}", "row 3: cells2.png", "row 4: gray16.tif"]),
    ("loose image onto loose image", "To row",
     [f"row 1: {R1}", f"row 2: {R2}", "row 3: cells2.png | gray16.tif"]),
    ("loose image onto loose image", "To column",
     [f"row 1: {R1}", f"row 2: {R2}", "row 3: cells2.png / gray16.tif"]),
    # the dragged row takes the loose image in, where the row is
    ("row onto loose image", "Add to group",
     [f"row 1: {R1} | gray16.tif", f"row 2: {R2}", "row 3: cells2.png"]),
    ("row onto loose image", "To row",
     [f"row 1: {R2}", f"row 2: gray16.tif | {R1}", "row 3: cells2.png"]),
    ("row onto loose image", "To column",
     [f"row 1: {R2}", f"row 2: gray16.tif / ({R1})", "row 3: cells2.png"]),
    ("row onto loose image", "Swap",
     [f"row 1: gray16.tif", f"row 2: {R2}", f"row 3: {R1}", "row 4: cells2.png"]),
    ("image to empty space", "Extrude",
     ["row 1: gray8.tif", f"row 2: {R2}", "row 3: gray16.tif", "row 4: cells2.png", "row 5: cells.png"]),
    ("loose image onto image in row", "Add to group (keep dragged shape layout)",
     [f"row 1: {R1}", f"row 2: {R2} | gray16.tif", "row 3: cells2.png"]),
    ("loose image onto image in row", "Add to group (don't keep dragged shape layout)",
     [f"row 1: {R1}", f"row 2: {R2} | gray16.tif", "row 3: cells2.png"]),
    ("loose image onto image in row", "To row",
     [f"row 1: {R1}", f"row 2: {R2} | gray16.tif", "row 3: cells2.png"]),
    ("loose image onto image in row", "To column",
     [f"row 1: {R1}", f"row 2: ({R2}) / gray16.tif", "row 3: cells2.png"]),
    ("loose image onto image in row", "Swap",
     [f"row 1: {R1}", "row 2: gray16.tif", "row 3: rgb.tif | zstack.tif", "row 4: cells2.png"]),
]


@pytest.mark.parametrize("situation,choice,rows", DRAGS, ids=[f"{s}-{c}" for s, c, _r in DRAGS])
def test_internal_drag(qapp, e2e_gui, e2e_files, tmp_path, menus, watch, situation, choice, rows):
    g = e2e_gui
    _drag_start(qapp, g, tmp_path, e2e_files)
    before = H.snapshot(g, tmp_path)
    shape, to = DRAG_FROM_TO[situation](g)
    menus.pick = None
    H.drag(g, shape, to)                          # look at the menu, dismiss it
    if H.offered_as(menus.last, choice) is None:
        pytest.skip(f"{choice!r} is no longer offered ({situation}); "
                    "test_drag_menus_offer_the_right_choices says whether it should be")
    assert H.same(H.snapshot(g, tmp_path), before), "a dismissed drag menu changed the figure"
    shape, to = DRAG_FROM_TO[situation](g)
    menus.pick = choice
    H.drag(g, shape, to)
    menus.pick = None
    H.settle(qapp, g)
    after = H.snapshot(g, tmp_path)
    assert sorted(p["name"] for p in after["panels"]) == sorted(p["name"] for p in before["panels"]), \
        "an image was lost or duplicated"
    H.expect_rows(after, rows, f"{situation} → {choice}")
    watch.check(f"{situation} → {choice}")
    H.check_invariants(qapp, g, tmp_path, before, after)
    watch.check(f"{situation} → {choice}: undo / redo / reopen")


def test_drag_menus_offer_the_right_choices(qapp, e2e_gui, e2e_files, tmp_path, menus):
    g = e2e_gui
    for situation in H.DRAG_SITUATIONS:
        _drag_start(qapp, g, tmp_path, e2e_files)
        shape, to = DRAG_FROM_TO[situation](g)
        H.drag(g, shape, to)
        expected = sorted({c for s, c, _r in DRAGS if s == situation})
        assert not H.missing_entries(expected, menus.last), (situation, menus.last)


def test_tiny_drag_is_a_click_and_drag_onto_itself_does_nothing(qapp, e2e_gui, e2e_files, tmp_path, menus):
    g = e2e_gui
    _drag_start(qapp, g, tmp_path, e2e_files)
    before = H.snapshot(g, tmp_path)
    n = len(menus.trees)
    a = H.by_name(g, "gray8")
    H.drag(g, a, H.centre(g, a, dx=2, dy=2))
    H.drag(g, H.rows(g)[0], H.centre(g, H.rows(g)[0], dx=3))
    assert all(not t for t in menus.trees[n:])
    assert H.same(H.snapshot(g, tmp_path), before)
