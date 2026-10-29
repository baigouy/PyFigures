"""The figure canvas's right-click menu — the main way the editor is driven.

A synthetic right-click (press + release, real mouse handlers) is sent to the
canvas over a shape; the menu that would pop up is captured instead of shown,
its structure is checked for that kind of selection (nothing selected, an
image in a row, a whole row, several rows, an RGB image, a z-stack), and each
entry is run, with its effect on the figure checked.

Dialogs (CustomDialog, colour pickers, ...) are accepted with their defaults or
a value the test sets on the dialog's own widget. Nothing is shown on screen.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import Qt, QPointF, QEvent
from qtpy.QtGui import QMouseEvent, QColor
from qtpy.QtWidgets import QMenu, QMessageBox, QColorDialog, QInputDialog, QDialog


# ---------------------------------------------------------------------------
# figure + window
# ---------------------------------------------------------------------------

def _img(path, arr, dims):
    from batoolset.img import Img
    Img(arr, dimensions=dims).save(path)
    return str(path)


def _figure(d):
    from pyfigures import mcp_server as M
    pyf = os.path.join(d, "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    g1 = _img(os.path.join(d, "g1.tif"), np.full((40, 60), 60, np.uint8), "hw")
    g2 = _img(os.path.join(d, "g2.tif"), np.full((60, 40), 180, np.uint8), "hw")
    rgb = np.zeros((40, 40, 3), np.uint8)
    rgb[..., 0] = 200
    rgb[..., 1] = 90
    c = _img(os.path.join(d, "rgb.tif"), rgb, "hwc")
    z = _img(os.path.join(d, "z.tif"), np.stack([np.full((30, 30), v, np.uint8) for v in (20, 120, 220)]), "dhw")
    M.add_image(pyf, [0], g1, label="A")
    M.add_image(pyf, [0], g2, label="B")
    M.add_image(pyf, [1], c, label="C")
    M.add_image(pyf, [1], z, label="D")
    # the stack as a stack (split by Z offered): a new Z stack otherwise
    # shows its max projection, as in the GUI
    M.configure_image(pyf, [1], 1, projection="none")
    M.set_scale_bar(pyf, [0], 0, 10)
    M.add_annotation(pyf, [0], 0, "note")
    M.add_roi_rect(pyf, [0], 0, 5, 5, 10, 10)
    return pyf


@pytest.fixture
def ui(monkeypatch):
    """Answers for every dialog a menu entry may open; tests tweak them."""
    from batoolset.GUI.customdialog import CustomDialog
    st = {"custom": [], "configure": None, "accept": True, "color": QColor(255, 0, 0), "msg": []}

    def custom_exec(self, *a, **k):
        st["custom"].append(self.windowTitle())
        if st["configure"] is not None:
            st["configure"](self)
        return QDialog.Accepted if st["accept"] else QDialog.Rejected
    monkeypatch.setattr(CustomDialog, "exec_", custom_exec, raising=False)
    monkeypatch.setattr(CustomDialog, "exec", custom_exec)
    monkeypatch.setattr(QDialog, "exec", lambda self, *a, **k: 0)
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: st["color"]))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    for kind in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, kind,
                            staticmethod(lambda *a, _k=kind, **kw: st["msg"].append((_k, a[1] if len(a) > 1 else ""))
                                         or QMessageBox.Yes))
    return st


@pytest.fixture
def gui(qapp, tmp_path, ui):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.resize(1300, 900)
    g.show()
    qapp.processEvents()
    g._start_pyf_loader([_figure(str(tmp_path))], append=False, reset_undo=True)
    _settle(qapp, g)
    yield g
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def _settle(qapp, g, timeout=60):
    """Until the figure is on the canvas AND every image has its pixels."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        th = getattr(g, "_pyf_loader_thread", None)
        try:
            running = th is not None and th.isRunning()
        except RuntimeError:
            running = False
        shapes = g.paint.EZFIG_panel.shapes_to_draw
        loaded = shapes and all(i.img is not None for s in shapes for i in images(s)
                                if i.filename and i.filename != "@template@")
        if not running and loaded and not getattr(g, "_lazy_img_queue", None) \
                and not getattr(g, "_active_img_loaders", None):
            break
        time.sleep(0.005)
    for _ in range(5):
        qapp.processEvents()


# ---------------------------------------------------------------------------
# right-click machinery
# ---------------------------------------------------------------------------

class MenuCapture:
    """Replaces QMenu.exec: records the menu tree and returns the action at
    *pick* (a list of labels through submenus), or None (= dismissed)."""

    def __init__(self, monkeypatch):
        self.trees = []
        self.pick = None
        cap = self

        def fake_exec(menu, *a, **k):
            cap.trees.append(_tree(menu))
            if cap.pick is None:
                return None
            act = _find(menu, cap.pick)
            act.trigger()             # what a real click does before exec() returns
            return act
        monkeypatch.setattr(QMenu, "exec", fake_exec)
        monkeypatch.setattr(QMenu, "exec_", fake_exec, raising=False)

    @property
    def last(self):
        return self.trees[-1] if self.trees else None


def _tree(menu):
    out = []
    for a in menu.actions():
        if a.isSeparator() and not a.text():
            continue
        if a.menu() is not None:
            out.append((a.text(), _tree(a.menu())))
        else:
            out.append(a.text())
    return out


def _labels(tree):
    flat = []
    for e in tree:
        if isinstance(e, tuple):
            flat.append(e[0])
            flat += [f"{e[0]} / {x}" for x in _labels(e[1])]
        else:
            flat.append(e)
    return flat


def _find(menu, path):
    acts = menu.actions()
    for i, name in enumerate(path):
        match = [a for a in acts if a.text() == name]
        assert match, f"{name!r} not in {[a.text() for a in acts]}"
        if i == len(path) - 1:
            return match[0]
        acts = match[0].menu().actions()


def _center(panel, shape):
    r = shape.boundingRect()
    return QPointF((r.x() + r.width() / 2) * panel.scale, (r.y() + r.height() / 2) * panel.scale)


def _click(panel, pos, button, kind):
    t = {"press": QEvent.Type.MouseButtonPress, "release": QEvent.Type.MouseButtonRelease}[kind]
    ev = QMouseEvent(t, pos, panel.mapToGlobal(pos), button,
                     button if kind == "press" else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    (panel.mousePressEvent if kind == "press" else panel.mouseReleaseEvent)(ev)


def right_click(gui, cap, shape=None, pos=None, select=True, pick=None):
    """Select *shape* (as a left click would) then right-click on it."""
    panel = gui.paint.EZFIG_panel
    if shape is not None and select:
        panel.set_current_selection(shape)
    if pos is None:
        pos = _center(panel, shape)
    cap.pick = pick
    n = len(cap.trees)
    _click(panel, pos, Qt.MouseButton.RightButton, "press")
    _click(panel, pos, Qt.MouseButton.RightButton, "release")
    from qtpy.QtWidgets import QApplication
    for _ in range(5):
        QApplication.processEvents()
    assert len(cap.trees) == n + 1, "no menu popped up"
    return cap.last


@pytest.fixture
def cap(monkeypatch):
    return MenuCapture(monkeypatch)


def rows(gui):
    return [s for s in gui.paint.EZFIG_panel.shapes_to_draw if type(s).__name__ == "Group"]


def images(shape):
    from batoolset.drawings.shapes.image2d import Image2D
    if isinstance(shape, Image2D):
        return [shape]
    return [i for c in getattr(shape, "content", []) for i in images(c)]


def annots(img):
    return sorted(type(a).__name__ for a in (img.annotations or []))


# ---------------------------------------------------------------------------
# menu structure per selection
# ---------------------------------------------------------------------------

def test_empty_canvas_menu(gui, cap):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(None)
    b = panel.updateBounds()
    far = QPointF((b.right() + 40) * panel.scale, (b.bottom() + 40) * panel.scale)
    tree = right_click(gui, cap, pos=far, select=False)
    assert _labels(tree) == ["Canvas", "Add Empty Image", "Ignore"]


def test_image_in_row_menu(gui, cap):
    img = images(rows(gui)[0])[0]
    labels = _labels(right_click(gui, cap, img))
    for expected in ("Edit", "Edit Image", "Selection", "Add Empty Image", "Duplicate Selection",
                     "Convert to template", "Extrude (remove from group)", "Arrange",
                     "Add labels ▶", "Add labels ▶ / Above the row",
                     "Add labels ▶ / Left / top of row/col", "Remove annotations ▶",
                     "Remove annotations ▶ / Scale bars", "Crop & size ▶",
                     "Crop & size ▶ / Reset crop only", "Appearance ▶", "Appearance ▶ / Set LUT(s)",
                     "Text & lettering ▶", "Ignore"):
        assert expected in labels, (expected, labels)
    assert "Split ▶" not in labels                      # plain grey image: nothing to split
    assert "Reshape to panel (if possible)" not in labels   # one image: nothing to reshape
    assert "Change space between elements" not in labels


def test_row_menu(gui, cap):
    labels = _labels(right_click(gui, cap, rows(gui)[0]))
    assert "Edit Group (orientation/space)" in labels and "Change space between elements" in labels
    assert "Edit Image" not in labels


def test_multi_selection_menu(gui, cap):
    sel = rows(gui)
    gui.paint.EZFIG_panel.set_current_selection(list(sel))
    labels = _labels(right_click(gui, cap, sel[0], select=False))
    for expected in ("↔  To row", "↕  To column", "▦  To panel"):
        assert expected in labels


def test_rgb_and_stack_images_offer_split(gui, cap):
    rgb, z = images(rows(gui)[1])
    labels = _labels(right_click(gui, cap, rgb))
    assert "Split ▶ / Channel split (Gray mode)" in labels
    assert "Split ▶ / Channel split (Magenta/Green mode)" in labels
    labels = _labels(right_click(gui, cap, z))
    assert "Split ▶ / Split by a dimension" in labels


def test_dismissing_the_menu_changes_nothing(gui, cap):
    before = gui.paint.EZFIG_panel.shapes_to_draw[:]
    n_imgs = sum(len(images(r)) for r in rows(gui))
    right_click(gui, cap, images(rows(gui)[0])[0], pick=None)
    right_click(gui, cap, images(rows(gui)[0])[0], pick=["Ignore"])
    assert gui.paint.EZFIG_panel.shapes_to_draw == before
    assert sum(len(images(r)) for r in rows(gui)) == n_imgs


# ---------------------------------------------------------------------------
# each entry does what it says
# ---------------------------------------------------------------------------

def test_duplicate_selection(gui, cap):
    panel = gui.paint.EZFIG_panel
    n = len(panel.shapes_to_draw)
    right_click(gui, cap, rows(gui)[0], pick=["Duplicate Selection"])
    assert len(panel.shapes_to_draw) == n + 1


def test_convert_to_template(gui, cap):
    img = images(rows(gui)[0])[1]
    right_click(gui, cap, img, pick=["Convert to template"])
    assert img.filename == "@template@"


def test_extrude_image_out_of_row(gui, cap):
    row = rows(gui)[0]
    img = images(row)[1]
    n = len(gui.paint.EZFIG_panel.shapes_to_draw)
    right_click(gui, cap, img, pick=["Extrude (remove from group)"])
    assert img not in images(row)
    assert len(gui.paint.EZFIG_panel.shapes_to_draw) == n + 1


@pytest.mark.parametrize("label,orientation", [("↔  To row", "X"), ("↕  To column", "Y")])
def test_multi_selection_to_row_or_column(gui, cap, label, orientation):
    panel = gui.paint.EZFIG_panel
    imgs = images(rows(gui)[0])
    panel.set_current_selection(list(imgs))
    right_click(gui, cap, imgs[0], select=False, pick=[label])
    groups = [s for s in panel.shapes_to_draw if type(s).__name__ == "Group"]
    new = [g for g in groups if set(map(id, images(g))) == set(map(id, imgs))]
    assert new and new[0].orientation == orientation


def test_add_empty_image(gui, cap, ui):
    panel = gui.paint.EZFIG_panel
    n = sum(len(images(s)) for s in panel.shapes_to_draw)
    panel.set_current_selection(None)
    b = panel.updateBounds()
    right_click(gui, cap, pos=QPointF((b.right() + 40) * panel.scale, (b.bottom() + 40) * panel.scale),
                select=False, pick=["Add Empty Image"])
    assert ui["custom"][-1] == "Add empty image"
    assert sum(len(images(s)) for s in panel.shapes_to_draw) == n + 1


@pytest.mark.parametrize("entry,gone", [
    (["Remove annotations ▶", "Scale bars"], "ScaleBar"),
    (["Remove annotations ▶", "ROIs"], "Rectangle2D"),
])
def test_remove_annotations_on_selection_only(gui, cap, entry, gone):
    a, b = images(rows(gui)[0])
    c = images(rows(gui)[1])[0]
    other_before = annots(c)
    assert gone in annots(a)
    right_click(gui, cap, a, pick=entry)
    assert gone not in annots(a)
    assert annots(c) == other_before                    # other rows untouched


def test_remove_texts_keeps_letter(gui, cap):
    a = images(rows(gui)[0])[0]
    right_click(gui, cap, a, pick=["Remove annotations ▶", "Texts"])
    texts = [x for x in a.annotations if type(x).__name__ == "TAText2D"]
    assert texts and all(t.is_letter for t in texts)


def test_remove_all_annotations_on_selection(gui, cap):
    a = images(rows(gui)[0])[0]
    right_click(gui, cap, a, pick=["Remove annotations ▶", "Remove all (ROIs, scale bars, texts, …)"])
    assert all(getattr(x, "is_letter", False) for x in a.annotations)


def test_force_same_width_and_height(gui, cap):
    row = rows(gui)[0]
    gui.paint.EZFIG_panel.set_current_selection(row)
    right_click(gui, cap, row, select=False, pick=["Crop & size ▶", "Force same width and height"])
    a, b = images(row)
    assert abs(a.boundingRect().width() - b.boundingRect().width()) < 1
    assert abs(a.boundingRect().height() - b.boundingRect().height()) < 1


def test_force_same_aspect_ratio(gui, cap):
    row = rows(gui)[0]
    right_click(gui, cap, row, pick=["Crop & size ▶", "Force same aspect ratio"])
    a, b = images(row)
    ar = lambda s: s.boundingRect().width() / s.boundingRect().height()  # noqa: E731
    assert abs(ar(a) - ar(b)) < 0.05          # crops are whole pixels: 1 px of a 26 px side


@pytest.mark.parametrize("entry,crop_reset,rot_reset", [
    ("Reset crop and rotation", True, True), ("Reset crop only", True, False),
    ("Reset rotation only", False, True)])
def test_reset_crop_and_rotation(gui, cap, entry, crop_reset, rot_reset):
    img = images(rows(gui)[0])[0]
    img.crop_left, img.crop_top = 5, 3
    img.theta = 30
    right_click(gui, cap, img, pick=["Crop & size ▶", entry])
    assert ((img.crop_left or 0) == 0) == crop_reset
    assert ((img.theta or 0) == 0) == rot_reset


def test_force_same_crop_rotation_as_first(gui, cap):
    row = rows(gui)[0]
    a, b = images(row)
    a.theta = 15
    right_click(gui, cap, row, pick=["Crop & size ▶", "Force same crop, rotation and bg"])
    assert b.theta == 15


def test_background_set_and_reset(gui, cap, ui):
    img = images(rows(gui)[0])[0]
    ui["configure"] = None
    right_click(gui, cap, img, pick=["Appearance ▶", "Set background"])
    assert ui["custom"][-1] == "Select a background color"
    right_click(gui, cap, img, pick=["Appearance ▶", "Reset background"])
    assert getattr(img, "fill_color", None) in (None, 0, "")


def test_set_and_reset_luts(gui, cap, ui):
    img = images(rows(gui)[1])[0]                       # RGB: has channels
    right_click(gui, cap, img, pick=["Appearance ▶", "Set LUT(s)"])
    sel = gui.paint.EZFIG_panel.get_images_from_sel()
    assert ui["custom"] and ui["custom"][-1] == "Edit Look Up Tables (LUTs)", \
        (img.img is None, img.get_nb_channels(), sel, gui.paint.EZFIG_panel.selected_shape)
    img.LUTs = ["RED", "GREEN", "BLUE"]
    right_click(gui, cap, img, pick=["Appearance ▶", "Reset LUT(s)"])
    assert not img.LUTs or img.LUTs != ["RED", "GREEN", "BLUE"]


@pytest.mark.parametrize("entry", ["Channel split (Gray mode)", "Channel split (Magenta/Green mode)"])
def test_channel_split(gui, cap, entry):
    rgb = images(rows(gui)[1])[0]
    n = sum(len(images(s)) for s in gui.paint.EZFIG_panel.shapes_to_draw)
    right_click(gui, cap, rgb, pick=["Split ▶", entry])
    after = sum(len(images(s)) for s in gui.paint.EZFIG_panel.shapes_to_draw)
    assert after >= n + 2                               # 3 channels (+ merge) instead of 1


def test_split_by_dimension_dialog_cancel_is_harmless(gui, cap, ui):
    z = images(rows(gui)[1])[1]
    ui["accept"] = False
    n = sum(len(images(s)) for s in gui.paint.EZFIG_panel.shapes_to_draw)
    right_click(gui, cap, z, pick=["Split ▶", "Split by a dimension"])
    assert sum(len(images(s)) for s in gui.paint.EZFIG_panel.shapes_to_draw) == n


@pytest.mark.parametrize("entry", ["Above the row", "Below the row"])
def test_add_text_row(gui, cap, entry):
    panel = gui.paint.EZFIG_panel
    row = rows(gui)[0]
    n = len(panel.shapes_to_draw)
    right_click(gui, cap, images(row)[0], pick=["Add labels ▶", entry])
    assert len(panel.shapes_to_draw) == n + 1
    new = [s for s in panel.shapes_to_draw if getattr(s, "isText", False)]
    assert new
    i_row, i_txt = panel.shapes_to_draw.index(row), panel.shapes_to_draw.index(new[0])
    assert (i_txt < i_row) if entry == "Above the row" else (i_txt > i_row)


@pytest.mark.parametrize("entry", ["Left / top of row/col", "Right / bottom of row/col"])
def test_add_side_label(gui, cap, entry):
    row = rows(gui)[0]
    n = len(row.content)
    right_click(gui, cap, images(row)[0], pick=["Add labels ▶", entry])
    assert len(row.content) == n + 1
    side = row.content[0] if entry.startswith("Left") else row.content[-1]
    assert getattr(side, "isText", False)


def test_change_space(gui, cap, ui):
    row = rows(gui)[0]

    def set_space(dlg):
        spin = dlg.main_widget.findChild(type(gui.main_space_spinner))
        if spin is not None:
            spin.setValue(12)
    ui["configure"] = set_space
    right_click(gui, cap, row, pick=["Change space between elements"])
    assert ui["custom"][-1] == "Change space"
    assert row.space == 12


def test_edit_group_dialog(gui, cap, ui):
    right_click(gui, cap, rows(gui)[0], pick=["Edit Group (orientation/space)"])
    assert ui["custom"][-1] == "Row Or Column"


def test_reshape_to_panel(gui, cap, ui):
    right_click(gui, cap, rows(gui)[0], pick=["Reshape to panel (if possible)"])
    # either reorganised (dialog accepted) or explained — never an exception


@pytest.mark.parametrize("entry,title", [
    ("Change font (non-Letter text)", "Select a Font"),
    ("Change background (non-Letter text)", "Select a background color"),
])
def test_text_menu_dialogs(gui, cap, ui, entry, title):
    ui["accept"] = False
    right_click(gui, cap, images(rows(gui)[0])[0], pick=["Text & lettering ▶", entry])
    assert ui["custom"][-1] == title


def test_change_lettering_parameters_opens_dialog(gui, cap, ui):
    ui["accept"] = False
    right_click(gui, cap, images(rows(gui)[0])[0], pick=["Text & lettering ▶", "Change lettering parameters"])
    assert ui["custom"][-1] == "Auto lettering"


def test_edit_image_opens_editor(gui, cap, ui):
    ui["accept"] = False
    right_click(gui, cap, images(rows(gui)[0])[0], pick=["Edit Image"])
    assert ui["custom"][-1] == "Annotate the image"


def test_every_entry_runs_without_error(gui, cap, ui, qapp, monkeypatch):
    """Belt and braces: every leaf of the image and row menus, dialogs
    cancelled, on a fresh selection each time — no exception anywhere."""
    import sys
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda t, v, tb: errors.append(f"{t.__name__}: {v}"))
    ui["accept"] = False

    def first_photo():                     # side labels inserted by earlier entries are images too
        return next(i for r in rows(gui) for i in images(r) if not i.isText)

    def first_row():
        return next(r for r in rows(gui) if not r.isText)
    for target_fn in (first_photo, first_row):
        tree = right_click(gui, cap, target_fn())

        def leaves(t, prefix=()):
            for e in t:
                if isinstance(e, tuple):
                    yield from leaves(e[1], prefix + (e[0],))
                elif e and e not in ("Edit", "Selection", "Arrange", "Canvas", "Match first image",
                                     "Reset", "Look-up tables", "Background"):
                    yield list(prefix + (e,))
        for path in leaves(tree):
            target = target_fn()
            right_click(gui, cap, target, pick=path)
            qapp.processEvents()
            assert not errors, (path, errors)


def test_equation_panel_offers_edit_equation(qapp, tmp_path, cap, ui):
    """Only an equation panel gets 'Edit equation…', and it opens the editor
    on that panel."""
    from pyfigures import mcp_server as M
    from pyfigures.gui.pfgui import EZFIG_GUI
    pyf = os.path.join(str(tmp_path), "eq.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_equation(pyf, [0], r"\alpha + \beta")
    M.add_image(pyf, [0], _img(os.path.join(str(tmp_path), "g.tif"), np.full((40, 60), 60, np.uint8), "hw"))
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.resize(1300, 900)
    g.show()
    try:
        g._start_pyf_loader([pyf], append=False, reset_undo=True)
        _settle(qapp, g)
        eq, plain = images(rows(g)[0])
        edited = []
        g.edit_equation = lambda shape: edited.append(shape)
        assert "Edit equation…" not in _labels(right_click(g, cap, plain))
        right_click(g, cap, eq, pick=["Edit equation…"])
        assert edited == [eq]
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()
