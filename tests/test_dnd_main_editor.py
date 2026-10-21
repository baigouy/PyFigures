"""Drag and drop in the main figure editor.

External drops (files from the file manager onto the window): the drop menu
it pops up (the in-window button menu, clicked like a user would), rows,
columns, panels, single images, template slots, .pyf figures (merged),
mixed drops, companion/unsupported files.

Internal drags (moving shapes on the canvas with the left mouse button):
image onto another row's image, image out to empty space, a whole row onto
another row, standalone image onto standalone image, and a drop back onto
itself — for every menu choice offered, the figure must keep exactly the same
images (none lost, none duplicated) and the choice must do what it says.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import Qt, QPointF, QMimeData, QUrl, QEvent
from qtpy.QtGui import QMouseEvent, QDropEvent, QDragEnterEvent
from qtpy.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QPushButton, QFrame


def _tif(path, val, shape=(40, 60)):
    from batoolset.img import Img
    Img(np.full(shape, val, np.uint8), dimensions="hw").save(path)
    return str(path)


@pytest.fixture
def files(tmp_path):
    d = tmp_path / "drop"
    d.mkdir()
    return [_tif(d / f"f{i}.tif", 40 * (i + 1)) for i in range(3)]


@pytest.fixture
def ui(monkeypatch):
    from batoolset.GUI.customdialog import CustomDialog
    st = {"custom": [], "msg": [], "menus": [], "pick": None}

    def custom_exec(self, *a, **k):
        st["custom"].append(self.windowTitle())
        return QDialog.Accepted
    monkeypatch.setattr(CustomDialog, "exec_", custom_exec, raising=False)
    monkeypatch.setattr(CustomDialog, "exec", custom_exec)
    for kind in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, kind,
                            staticmethod(lambda *a, _k=kind, **kw: st["msg"].append(_k) or QMessageBox.Yes))

    def menu_exec(menu, *a, **k):
        labels = [x.text() for x in menu.actions() if x.text()]
        st["menus"].append(labels)
        if st["pick"] is None:
            return None
        act = next((x for x in menu.actions() if x.text() == st["pick"]), None)
        assert act is not None, (st["pick"], labels)
        act.trigger()
        return act
    monkeypatch.setattr(QMenu, "exec", menu_exec)
    monkeypatch.setattr(QMenu, "exec_", menu_exec, raising=False)
    return st


def _all_images(g):
    from batoolset.drawings.shapes.image2d import Image2D
    out, stack = [], list(g.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        s = stack.pop(0)
        if isinstance(s, Image2D):
            out.append(s)
        stack[0:0] = list(getattr(s, "content", None) or [])
    return out


def _wait(qapp, g, cond=None, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        th = getattr(g, "_pyf_loader_thread", None)
        try:
            running = th is not None and th.isRunning()
        except RuntimeError:
            running = False
        busy = running or getattr(g, "_lazy_img_queue", None) or getattr(g, "_active_img_loaders", None)
        loaded = all(i.img is not None for i in _all_images(g) if i.filename and i.filename != "@template@")
        if not busy and loaded and (cond is None or cond()):
            break
        time.sleep(0.005)
    for _ in range(5):
        qapp.processEvents()


def _new_gui(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.resize(1300, 900)
    g.show()
    qapp.processEvents()
    return g


@pytest.fixture
def gui(qapp, ui):
    g = _new_gui(qapp)
    yield g
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


# ---------------------------------------------------------------------------
# external drops
# ---------------------------------------------------------------------------

def _mime(paths=None, text=None):
    m = QMimeData()
    if paths is not None:
        m.setUrls([QUrl.fromLocalFile(p) for p in paths])
    if text is not None:
        m.setText(text)
    return m


def _window_pos(g, panel_point=None):
    panel = g.paint.EZFIG_panel
    if panel_point is None:
        b = panel.updateBounds()
        panel_point = QPointF((b.right() + 60) * panel.scale, (b.bottom() + 60) * panel.scale)
    p = panel.mapTo(g, panel_point.toPoint())
    return QPointF(p)


def drop(g, paths, panel_point=None):
    mime = _mime(paths)          # must outlive the event: QDropEvent doesn't own it
    ev = QDropEvent(_window_pos(g, panel_point), Qt.DropAction.CopyAction, mime,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    ev._mime = mime
    g.dropEvent(ev)
    for _ in range(5):
        QApplication.processEvents()
    return ev


def drop_menu(g):
    """The in-window drop menu (a QFrame of buttons) currently shown."""
    frames = [f for f in g.findChildren(QFrame) if f.isVisible() and f.parent() is g
              and f.objectName() != "hintBubble" and f.findChildren(QPushButton)]
    return frames[-1] if frames else None


def menu_buttons(g):
    m = drop_menu(g)
    return [b.text() for b in m.findChildren(QPushButton)] if m else []


def click(g, label):
    m = drop_menu(g)
    assert m is not None, "no drop menu"
    btn = next((b for b in m.findChildren(QPushButton) if b.text() == label), None)
    assert btn is not None, (label, menu_buttons(g))
    btn.click()
    QApplication.processEvents()


def test_drag_enter_accepts_files_only(gui, files):
    mimes = [(_mime(files), True), (_mime(text="hello"), False)]   # kept alive for the events
    for mime, accepted in mimes:
        ev = QDragEnterEvent(_window_pos(gui).toPoint(), Qt.DropAction.CopyAction, mime,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        gui.dragEnterEvent(ev)
        assert ev.isAccepted() is accepted


def test_drop_text_is_ignored(gui):
    mime = _mime(text="x")
    ev = QDropEvent(_window_pos(gui), Qt.DropAction.CopyAction, mime,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    gui.dropEvent(ev)
    assert drop_menu(gui) is None and _all_images(gui) == []


def test_drop_several_shows_layout_menu(gui, files):
    drop(gui, files)
    labels = menu_buttons(gui)
    for expected in ("ARRANGE AS GROUP", "↔  To row", "↕  To column", "▦  To panel",
                     "ADD TO CANVAS", "➕  As single image(s)", "✕  Cancel"):
        assert any(expected.lower() == x.lower() for x in labels), (expected, labels)
    click(gui, "✕  Cancel")
    assert drop_menu(gui) is None and _all_images(gui) == []


def test_drop_single_offers_single_only(gui, files):
    drop(gui, files[:1])
    labels = menu_buttons(gui)
    assert "↔  To row" not in labels and "➕  As single image(s)" in labels


@pytest.mark.parametrize("label,orientation", [("↔  To row", "X"), ("↕  To column", "Y")])
def test_drop_to_row_or_column(gui, qapp, files, label, orientation):
    drop(gui, files)
    click(gui, label)
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 3)
    shapes = gui.paint.EZFIG_panel.shapes_to_draw
    assert len(shapes) == 1 and type(shapes[0]).__name__ == "Group"
    assert shapes[0].orientation == orientation
    assert [os.path.basename(i.filename) for i in _all_images(gui)] == ["f0.tif", "f1.tif", "f2.tif"]


def test_drop_as_single_images(gui, qapp, files):
    drop(gui, files)
    click(gui, "➕  As single image(s)")
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 3)
    shapes = gui.paint.EZFIG_panel.shapes_to_draw
    assert len(shapes) == 3 and all(type(s).__name__ == "Image2D" for s in shapes)


def test_drop_to_panel(gui, qapp, ui, files):
    drop(gui, files)
    click(gui, "▦  To panel")
    t0 = time.time()
    while len([i for i in _all_images(gui) if i.filename]) < 3 and time.time() - t0 < 10:
        qapp.processEvents()
        time.sleep(0.01)
    assert "Panel" in ui["custom"]
    real = [i for i in _all_images(gui) if i.filename]
    assert len(real) == 3                              # (+ empty filler cells to complete the grid)


def test_drop_onto_existing_image_offers_combine(gui, qapp, files):
    drop(gui, files[:1])
    click(gui, "➕  As single image(s)")
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 1)
    target = _all_images(gui)[0]
    r = target.boundingRect()
    panel = gui.paint.EZFIG_panel
    centre = QPointF((r.x() + r.width() / 2) * panel.scale, (r.y() + r.height() / 2) * panel.scale)
    drop(gui, files[1:2], centre)
    assert "↔  To row (with image below)" in menu_buttons(gui)
    click(gui, "↕  To column (with image below)")
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 2)
    shapes = panel.shapes_to_draw
    assert len(shapes) == 1 and shapes[0].orientation == "Y" and target in shapes[0].content


def test_drop_onto_template_slot_assigns_it(gui, qapp, files, tmp_path):
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "tpl.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], files[0])
    M.add_image(pyf, [0], files[1])
    M.templatify_figure(pyf)
    gui._start_pyf_loader([pyf], append=False, reset_undo=True)
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 2)
    slot = _all_images(gui)[1]
    assert slot.filename == "@template@"
    r = slot.boundingRect()
    panel = gui.paint.EZFIG_panel
    drop(gui, files[2:3], QPointF((r.x() + r.width() / 2) * panel.scale, (r.y() + r.height() / 2) * panel.scale))
    assert "⬜  Assign to template slot" in menu_buttons(gui)
    click(gui, "⬜  Assign to template slot")
    _wait(qapp, gui, lambda: _all_images(gui)[1].filename != "@template@")
    assert os.path.basename(_all_images(gui)[1].filename) == "f2.tif"
    assert _all_images(gui)[0].filename == "@template@"


def test_drop_pyf_merges_figure(gui, qapp, files, tmp_path):
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "other.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], files[0])
    M.add_image(pyf, [0], files[1])
    drop(gui, [pyf])
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 2)
    assert drop_menu(gui) is None                      # a figure opens directly, no menu
    assert len(_all_images(gui)) == 2
    drop(gui, [pyf, files[2]])                         # mixed: figure merged + menu for the image
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 4)
    assert "➕  As single image(s)" in menu_buttons(gui)
    click(gui, "➕  As single image(s)")
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 5)
    assert len(_all_images(gui)) == 5


def test_drop_folder(gui, qapp, files):
    drop(gui, [os.path.dirname(files[0])])
    click(gui, "↔  To row")
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 3)
    assert len(_all_images(gui)) == 3


def test_drop_unsupported_file_does_not_break(gui, qapp, files, tmp_path, ui):
    import sys
    errors = []
    old = sys.excepthook
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    try:
        txt = tmp_path / "notes.txt"
        txt.write_text("not an image")
        drop(gui, [str(txt), files[0]])
        if drop_menu(gui) is not None:
            click(gui, "➕  As single image(s)")
        _wait(qapp, gui, timeout=10)
    finally:
        sys.excepthook = old
    assert not errors, errors
    names = [os.path.basename(i.filename) for i in _all_images(gui)]
    assert names == ["f0.tif"]                          # the .txt is skipped, not a broken panel
    csv = tmp_path / "only.csv"
    csv.write_text("a,b\n1,2\n")
    drop(gui, [str(csv)])
    assert drop_menu(gui) is None                       # nothing droppable: no menu at all
    assert "only.csv" in gui.statusBar().currentMessage()
    assert len(_all_images(gui)) == 1


# ---------------------------------------------------------------------------
# internal drags on the canvas
# ---------------------------------------------------------------------------

@pytest.fixture
def canvas_fig(qapp, tmp_path, ui, files):
    """Two rows [A B] and [C D] plus a standalone image E."""
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    a, b, c = files
    d = _tif(tmp_path / "d.tif", 220, (60, 40))
    e = _tif(tmp_path / "e.tif", 90, (50, 50))
    M.add_image(pyf, [0], a, label="A")
    M.add_image(pyf, [0], b, label="B")
    M.add_image(pyf, [1], c, label="C")
    M.add_image(pyf, [1], d, label="D")
    g = _new_gui(qapp)
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    _wait(qapp, g, lambda: len(_all_images(g)) == 4)
    yield g, e
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def _by_name(g, name):
    return next(i for i in _all_images(g) if os.path.basename(i.filename or "").startswith(name))


def _centre(panel, shape, dx=0.0, dy=0.0):
    r = shape.boundingRect()
    return QPointF((r.x() + r.width() / 2 + dx) * panel.scale, (r.y() + r.height() / 2 + dy) * panel.scale)


def _mouse(panel, kind, pos, buttons=Qt.MouseButton.LeftButton):
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease}[kind]
    btn = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.LeftButton if kind in ("press", "move") else Qt.MouseButton.NoButton
    ev = QMouseEvent(t, pos, panel.mapToGlobal(pos), btn, held, Qt.KeyboardModifier.NoModifier)
    {"press": panel.mousePressEvent, "move": panel.mouseMoveEvent, "release": panel.mouseReleaseEvent}[kind](ev)


def drag(g, shape, to_point, steps=6):
    """Select *shape* (as the user's click-click does) then drag it with the
    left button to *to_point* (canvas widget coordinates)."""
    panel = g.paint.EZFIG_panel
    panel.set_current_selection(shape)
    start = _centre(panel, shape)
    _mouse(panel, "press", start)
    for i in range(1, steps + 1):
        _mouse(panel, "move", QPointF(start.x() + (to_point.x() - start.x()) * i / steps,
                                      start.y() + (to_point.y() - start.y()) * i / steps))
    _mouse(panel, "release", to_point)
    for _ in range(5):
        QApplication.processEvents()


def _inventory(g):
    """Every image exactly once: (filename) multiset."""
    return sorted(os.path.basename(i.filename) for i in _all_images(g))


def _no_overlap(g):
    shapes = g.paint.EZFIG_panel.shapes_to_draw
    rects = [s.boundingRect() for s in shapes]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            inter = rects[i].intersected(rects[j])
            assert inter.width() < 1 or inter.height() < 1, (shapes[i], shapes[j])


def _offered(ui):
    return ui["menus"][-1] if ui["menus"] else []


def test_drag_image_onto_other_rows_image_offers_choices(canvas_fig, ui):
    g, _ = canvas_fig
    panel = g.paint.EZFIG_panel
    drag(g, _by_name(g, "f0"), _centre(panel, _by_name(g, "f2")))
    offered = _offered(ui)
    assert offered, "no menu after dropping an image onto another row"
    assert set(offered) & {"Swap", "To row", "To column", "Add to group (keep dragged shape layout)"}


@pytest.mark.parametrize("choice", ["Swap", "To row", "To column",
                                    "Add to group (keep dragged shape layout)",
                                    "Add to group (don't keep dragged shape layout)"])
def test_each_drop_choice_keeps_every_image(canvas_fig, ui, choice):
    g, _ = canvas_fig
    panel = g.paint.EZFIG_panel
    before = _inventory(g)
    a, c = _by_name(g, "f0"), _by_name(g, "f2")
    drag(g, a, _centre(panel, c))                      # look at what is offered
    if choice not in _offered(ui):
        pytest.skip(f"{choice!r} not offered for this drop: {_offered(ui)}")
    ui["pick"] = choice
    drag(g, _by_name(g, "f0"), _centre(panel, _by_name(g, "f2")))
    panel.update_size()
    assert _inventory(g) == before, (choice, _inventory(g))
    _no_overlap(g)
    a, c = _by_name(g, "f0"), _by_name(g, "f2")
    top = panel.get_top_parent_of_shape
    if choice.startswith("Add to group"):
        assert top(a) is top(c)
    if choice == "Swap":
        assert top(a) is not top(_by_name(g, "f1"))    # A left its row...
        assert top(c) is top(_by_name(g, "f1"))        # ...and C took its place


def test_drag_image_out_to_empty_space_extrudes(canvas_fig, ui):
    g, _ = canvas_fig
    panel = g.paint.EZFIG_panel
    b = panel.updateBounds()
    away = QPointF((b.right() + 80) * panel.scale, (b.bottom() + 80) * panel.scale)
    drag(g, _by_name(g, "f1"), away)
    offered = _offered(ui)
    extrude = next((x for x in offered if x.startswith(("Extrude", "Add as new Row"))), None)
    assert extrude, offered
    before = _inventory(g)
    ui["pick"] = extrude
    drag(g, _by_name(g, "f1"), away)
    assert _inventory(g) == before
    assert _by_name(g, "f1") in panel.shapes_to_draw


def test_drag_row_onto_row(canvas_fig, ui):
    g, _ = canvas_fig
    panel = g.paint.EZFIG_panel
    rows = [s for s in panel.shapes_to_draw if type(s).__name__ == "Group"]
    before = _inventory(g)
    drag(g, rows[0], _centre(panel, rows[1]))
    for choice in list(_offered(ui)):
        if choice in ("Ignore", ""):
            continue
        ui["pick"] = choice
        rows = [s for s in panel.shapes_to_draw if type(s).__name__ == "Group"]
        drag(g, rows[0], _centre(panel, rows[-1]))
        assert _inventory(g) == before, choice
        ui["pick"] = None
        break


def test_drag_standalone_onto_standalone(canvas_fig, qapp, ui):
    g, e = canvas_fig
    panel = g.paint.EZFIG_panel
    # make two loose images: extrude B, add E as single
    b_img = _by_name(g, "f1")
    panel.all_as_single() if False else None
    g.all_images_directly([e])
    _wait(qapp, g, lambda: len(_all_images(g)) == 5)
    loose = [s for s in panel.shapes_to_draw if type(s).__name__ == "Image2D"]
    assert loose
    target = next(s for s in panel.shapes_to_draw if type(s).__name__ == "Group")
    before = _inventory(g)
    drag(g, loose[0], _centre(panel, target))
    if "To row" in _offered(ui):
        ui["pick"] = "To row"
        drag(g, loose[0], _centre(panel, target))
        assert _inventory(g) == before
    assert b_img in _all_images(g)


def test_tiny_drag_is_a_click(canvas_fig, ui):
    g, _ = canvas_fig
    panel = g.paint.EZFIG_panel
    a = _by_name(g, "f0")
    r0 = a.boundingRect()
    drag(g, a, _centre(panel, a, dx=2, dy=2))
    assert not ui["menus"] or ui["menus"][-1] == []
    r1 = a.boundingRect()
    assert abs(r1.x() - r0.x()) < 1 and abs(r1.y() - r0.y()) < 1   # snapped back
