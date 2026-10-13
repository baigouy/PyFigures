"""Poster / photo-album designer GUI: every toolbar button and page-dock
control, the unsaved-changes prompt, mouse gestures on the canvas (select,
move, group drag, Shift multi-select, rotate, resize, Ctrl-crop, Ctrl-pan,
background pan and wheel zoom, double-click text) and drag-and-drop from the
file manager (single file, several files, folders, template slots, .pyf
figures, unreadable files).

Mouse and drop events are synthetic Qt events sent to an offscreen widget —
nothing touches the real desktop. Dialogs and menus are answered by patching
their exec()/static getters.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import Qt, QPointF, QPoint, QMimeData, QUrl, QEvent
from qtpy.QtGui import QMouseEvent, QWheelEvent, QDropEvent, QDragEnterEvent
from qtpy.QtWidgets import QMenu, QFileDialog, QInputDialog, QMessageBox


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _png(path, size, rgb):
    from PIL import Image
    Image.new("RGB", size, rgb).save(path)
    return str(path)


@pytest.fixture
def photos(tmp_path):
    d = tmp_path / "photos"
    d.mkdir()
    return {
        "red": _png(d / "red.png", (200, 100), (220, 30, 30)),
        "green": _png(d / "green.png", (100, 200), (30, 200, 60)),
        "blue": _png(d / "blue.png", (150, 150), (30, 60, 220)),
    }


@pytest.fixture
def messages(monkeypatch):
    """Record every QMessageBox instead of blocking on it."""
    seen = []

    def rec(kind, ret=None):
        def f(*a, **k):
            seen.append((kind, a[1] if len(a) > 1 else "", a[2] if len(a) > 2 else ""))
            return ret
        return staticmethod(f)
    for kind in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, kind, rec(kind, QMessageBox.Ok))
    return seen


@pytest.fixture
def win(qapp, monkeypatch, messages):
    from pyfigures.poster.poster_window import PosterWindow
    from pyfigures.poster import poster_text_dialog
    monkeypatch.setattr(poster_text_dialog.PosterTextDialog, "exec", lambda self: 1)
    # never block on the unsaved-changes question; tests that care re-patch it
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Discard))
    w = PosterWindow()
    assert not w.canvas.is_modified()
    w.show()
    qapp.processEvents()
    yield w
    w.canvas.mark_saved()
    w.close()


def _file_dialogs(monkeypatch, open_path=None, save_path=None, folder=None):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (open_path or "", "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (save_path or "", "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: folder or ""))


def _items(monkeypatch, *answers):
    """QInputDialog.getItem answers, in order."""
    queue = list(answers)
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (queue.pop(0), True)))
    return queue


def _menu_picks(monkeypatch, *labels):
    """Each QMenu.exec() call returns the action whose text contains the next
    label (None = dismissed). Records every menu's labels."""
    queue = list(labels)
    shown = []

    def fake_exec(self, *a, **k):
        texts = [act.text() for act in self.actions()]
        shown.append(texts)
        want = queue.pop(0) if queue else None
        if want is None:
            return None
        for act in self.actions():
            if want in act.text():
                return act
        raise AssertionError(f"no menu entry containing {want!r} in {texts}")
    monkeypatch.setattr(QMenu, "exec", fake_exec)
    return shown


def _px(canvas, x_mm, y_mm):
    x, y = canvas._mm_to_px(x_mm, y_mm)
    return QPointF(x, y)


def _mouse(canvas, kind, pos, mods=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease, "dbl": QEvent.Type.MouseButtonDblClick}[kind]
    buttons = button if kind in ("press", "move", "dbl") else Qt.MouseButton.NoButton
    ev = QMouseEvent(t, pos, canvas.mapToGlobal(pos), button, buttons, mods)
    {"press": canvas.mousePressEvent, "move": canvas.mouseMoveEvent,
     "release": canvas.mouseReleaseEvent, "dbl": canvas.mouseDoubleClickEvent}[kind](ev)


def _drag(canvas, a, b, mods=Qt.KeyboardModifier.NoModifier, steps=4):
    _mouse(canvas, "press", a, mods)
    for i in range(1, steps + 1):
        _mouse(canvas, "move", QPointF(a.x() + (b.x() - a.x()) * i / steps,
                                       a.y() + (b.y() - a.y()) * i / steps), mods)
    _mouse(canvas, "release", b, mods)


def _drop(canvas, paths, pos, text_only=False):
    mime = QMimeData()
    if text_only:
        mime.setText("just text")
    else:
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    enter = QDragEnterEvent(pos.toPoint(), Qt.DropAction.CopyAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    canvas.dragEnterEvent(enter)
    ev = QDropEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    canvas.dropEvent(ev)
    return enter


def _geom(s):
    return (round(s.x_mm, 6), round(s.y_mm, 6), round(s.width_mm, 6), round(s.height_mm, 6), round(s.theta, 6))


# ---------------------------------------------------------------------------
# toolbar: every action
# ---------------------------------------------------------------------------

def test_every_toolbar_action_is_wired(win):
    names = [a for a, _icon in win._TOOLBAR_ICON_MAP]
    for attr in names:
        act = getattr(win, attr)
        assert act.text(), attr
    connected = {a for a in names if a not in ("align_action", "distribute_action")}
    for attr in connected:
        assert getattr(win, attr).receivers(getattr(win, attr).triggered) >= 1, attr


def test_add_image_text_delete_raise_lower_undo_redo(win, monkeypatch, photos):
    c = win.canvas
    _file_dialogs(monkeypatch, open_path=photos["red"])
    win.add_image_action.trigger()
    _file_dialogs(monkeypatch, open_path=photos["blue"])
    win.add_image_action.trigger()
    assert [os.path.basename(s.path) for s in c.shapes_to_draw] == ["red.png", "blue.png"]
    assert c.is_modified() and win.windowTitle().startswith("*")
    win.add_text_action.trigger()                       # body text, editor dialog patched
    assert type(c.shapes_to_draw[-1]).__name__ == "PosterText"
    assert c.shapes_to_draw[-1].style == "body"
    c.selected = c.shapes_to_draw[0]
    win.raise_action.trigger()
    assert os.path.basename(c.shapes_to_draw[-1].path) == "red.png"
    win.lower_action.trigger()
    assert os.path.basename(c.shapes_to_draw[0].path) == "red.png"
    c.selected = c.shapes_to_draw[0]
    win.delete_action.trigger()
    assert len(c.shapes_to_draw) == 2
    assert win.undo_action.isEnabled()
    win.undo_action.trigger()
    assert len(c.shapes_to_draw) == 3
    assert win.redo_action.isEnabled()
    win.redo_action.trigger()
    assert len(c.shapes_to_draw) == 2
    while c.can_undo():
        win.undo_action.trigger()
    assert c.shapes_to_draw == [] and not c.is_modified()
    assert not win.undo_action.isEnabled() and not win.windowTitle().startswith("*")


def test_add_text_heading_menu(win):
    from pyfigures.poster.poster_shapes import TEXT_STYLE_PRESETS
    menus = [m for m in win.findChildren(QMenu)
             if [a.text() for a in m.actions()][:1] == [TEXT_STYLE_PRESETS["h1"]["label"]]]
    assert menus, "heading menu missing"
    for act, key in zip(menus[0].actions(), ("h1", "h2", "h3", "body", "caption")):
        act.trigger()
        assert win.canvas.shapes_to_draw[-1].style == key
    heights = [s.height_mm for s in win.canvas.shapes_to_draw]
    assert heights == sorted(heights, reverse=True)


def test_add_image_unreadable_file_warns(win, monkeypatch, tmp_path, messages):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"garbage")
    _file_dialogs(monkeypatch, open_path=str(bad))
    win.add_image_action.trigger()
    assert win.canvas.shapes_to_draw == []
    assert messages and messages[-1][0] == "warning" and "cannot read" in messages[-1][2]


def test_background_buttons(win, monkeypatch, photos, tmp_path, messages):
    c = win.canvas
    _file_dialogs(monkeypatch, open_path=photos["blue"])
    win.bg_action.trigger()
    assert c.background is not None and c.background.path == photos["blue"]
    c.background.set_zoom(3.0)
    c.background.pan_x_frac = 0.1
    win.reset_bg_view_action.trigger()
    assert (c.background.zoom, c.background.pan_x_frac) == (1.0, 0.5)
    win.clear_bg_action.trigger()
    assert c.background is None
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"x")
    _file_dialogs(monkeypatch, open_path=str(bad))
    win.bg_action.trigger()
    assert c.background is None and messages[-1][0] == "warning"


def test_arrange_buttons_are_undoable_and_skip_text(win, photos):
    c = win.canvas
    for k in ("red", "green", "blue"):
        c.add_image(photos[k])
    title = c.add_text("<b>Title</b>", x_mm=10, y_mm=10, style="h1")
    before_title = _geom(title)
    for action in (win.scatter_action, win.fan_action, win.grid_action):
        before = [_geom(s) for s in c.shapes_to_draw]
        action.trigger()
        after = [_geom(s) for s in c.shapes_to_draw]
        assert after[:3] != before[:3], action.text()
        assert _geom(title) == before_title, action.text()
        win.undo_action.trigger()                       # each arrangement is one undo step
        assert [_geom(s) for s in c.shapes_to_draw] == before, action.text()
        win.redo_action.trigger()


def test_layout_gallery_fill_and_sketch(win, monkeypatch, photos, messages):
    from pyfigures.poster import poster_layout_dialog as dlg_mod
    c = win.canvas

    def pick(name, sketch):
        def fake_exec(self):
            self.selected_layout = name
            self.sketch_mode = sketch
            return 1
        monkeypatch.setattr(dlg_mod.LayoutGalleryDialog, "exec", fake_exec)

    pick("diptych", False)
    win.layouts_action.trigger()                        # no photos yet -> explained, nothing added
    assert c.shapes_to_draw == [] and messages[-1][1] == "No images"
    pick("grid_2x2", True)
    win.layouts_action.trigger()
    assert len(c.shapes_to_draw) == 4 and all(s.is_template for s in c.shapes_to_draw)
    c.shapes_to_draw.clear()
    c.add_image(photos["red"])
    c.add_image(photos["blue"])
    pick("diptych", False)
    win.layouts_action.trigger()
    gids = {s.group_id for s in c.shapes_to_draw}
    assert len(gids) == 1 and None not in gids
    c.selected = c.shapes_to_draw[0]
    win.ungroup_action.trigger()
    assert all(s.group_id is None for s in c.shapes_to_draw)


def test_layout_gallery_dialog_itself(qapp):
    from pyfigures.poster.poster_layout_dialog import LayoutGalleryDialog
    from pyfigures.poster.poster_templates import LAYOUTS
    d = LayoutGalleryDialog(image_count=4)
    assert d.list_widget.count() == len(LAYOUTS)
    first = d.list_widget.item(0).data(Qt.ItemDataRole.UserRole)
    assert len(LAYOUTS[first]["slots"]) == 4             # matching count listed first
    d.sketch_checkbox.setChecked(True)
    d._accept_current()
    assert d.selected_layout == first and d.sketch_mode is True
    d2 = LayoutGalleryDialog()
    d2._accept_item(d2.list_widget.item(2))
    assert d2.selected_layout == d2.list_widget.item(2).data(Qt.ItemDataRole.UserRole)


@pytest.mark.parametrize("mode", ["left", "right", "top", "bottom", "center_h", "center_v"])
def test_align_menu(win, photos, mode):
    c = win.canvas
    a = c.add_image(photos["red"], x_mm=10, y_mm=10, width_mm=40)
    b = c.add_image(photos["blue"], x_mm=90, y_mm=120, width_mm=30)
    c.multi_selected = [a, b]
    menu = win.findChild(QToolBar_type()).widgetForAction(win.align_action).menu()
    label = {"left": "Align left", "right": "Align right", "top": "Align top", "bottom": "Align bottom",
             "center_h": "horizontal", "center_v": "vertical"}[mode]
    next(x for x in menu.actions() if label in x.text()).trigger()
    ra, rb = a.bounding_rect_mm(), b.bounding_rect_mm()
    get = {"left": lambda r: r.left(), "right": lambda r: r.right(), "top": lambda r: r.top(),
           "bottom": lambda r: r.bottom(), "center_h": lambda r: r.center().x(),
           "center_v": lambda r: r.center().y()}[mode]
    assert get(ra) == pytest.approx(get(rb))
    assert c.can_undo()


def QToolBar_type():
    from qtpy.QtWidgets import QToolBar
    return QToolBar


def test_distribute_menu(win, photos):
    c = win.canvas
    shapes = [c.add_image(photos["blue"], x_mm=x, y_mm=50, width_mm=10, height_mm=10) for x in (10, 30, 150)]
    c.multi_selected = list(shapes)
    menu = win.findChild(QToolBar_type()).widgetForAction(win.distribute_action).menu()
    next(x for x in menu.actions() if "horizontally" in x.text()).trigger()
    assert [s.center_mm().x() for s in shapes] == pytest.approx([15, 85, 155])
    next(x for x in menu.actions() if "vertically" in x.text()).trigger()   # same y: unchanged
    assert [s.center_mm().y() for s in shapes] == pytest.approx([55, 55, 55])


def test_zoom_buttons(win):
    c = win.canvas
    s0 = c._mm_to_px.scale
    win.zoom_in_action.trigger()
    assert c._mm_to_px.scale == pytest.approx(s0 * 1.1)
    win.zoom_out_action.trigger()
    win.zoom_out_action.trigger()
    assert c._mm_to_px.scale == pytest.approx(s0 * 1.1 * 0.81)
    w_before = c.width()
    win.zoom_reset_action.trigger()
    assert c._mm_to_px.scale == s0 and c.width() > w_before


def test_page_size_combo_is_undoable(win):
    c = win.canvas
    win.page_combo.setCurrentText("A3")
    assert (c.page_width_mm, c.page_height_mm) == (297, 420)
    assert c.base_page_width_mm == 297 and c.is_modified()
    win.undo_action.trigger()
    assert (c.page_width_mm, c.page_height_mm) == (210, 297)
    assert win.page_combo.currentText() == "A4"


# ---------------------------------------------------------------------------
# file actions + unsaved changes
# ---------------------------------------------------------------------------

def test_save_open_new_and_dirty_prompt(win, monkeypatch, photos, tmp_path, messages):
    c = win.canvas
    c.add_image(photos["red"])
    path = str(tmp_path / "mine")                       # extension added automatically
    _file_dialogs(monkeypatch, save_path=path)
    win.save_action.trigger()
    assert c.file_path == path + ".pyfposter" and os.path.isfile(c.file_path)
    assert not c.is_modified() and win.windowTitle().startswith("mine.pyfposter")

    c.add_image(photos["blue"])
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: asked.append(1) or QMessageBox.Cancel))
    win.new_action.trigger()                            # Cancel keeps the document
    assert asked and len(c.shapes_to_draw) == 2
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Discard))
    win.new_action.trigger()
    assert c.shapes_to_draw == [] and c.file_path is None

    _file_dialogs(monkeypatch, open_path=path + ".pyfposter")
    win.open_action.trigger()
    assert len(c.shapes_to_draw) == 1 and not c.is_modified()

    c.add_image(photos["blue"])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Save))
    win.new_action.trigger()                            # Save writes then clears
    assert c.shapes_to_draw == []
    from pyfigures.poster.poster_canvas import PosterCanvas
    reread = PosterCanvas()
    reread.load(path + ".pyfposter")
    assert len(reread.shapes_to_draw) == 2


def test_close_event_respects_cancel(win, monkeypatch, photos):
    win.canvas.add_image(photos["red"])
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Cancel))
    win.close()
    assert win.isVisible()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Discard))
    win.close()
    assert not win.isVisible()


def test_saving_an_album_started_as_poster_writes_pyfalbum(win, monkeypatch, tmp_path, photos):
    c = win.canvas
    c.add_image(photos["red"])
    _file_dialogs(monkeypatch, save_path=str(tmp_path / "trip.pyfposter"))
    win.save_action.trigger()
    c.add_page("spread")
    win.save_action.trigger()                           # can't go into the .pyfposter any more
    assert c.file_path == str(tmp_path / "trip.pyfalbum") and os.path.isfile(c.file_path)
    assert not c.is_modified()


def test_save_failure_is_reported_not_raised(win, monkeypatch, tmp_path, messages):
    win.canvas.add_text("x")
    _file_dialogs(monkeypatch, save_path=str(tmp_path / "no_such_dir" / "deeper" / "f.pyfposter"))
    assert win.save_poster() is False
    assert messages[-1][0] == "critical" and win.canvas.is_modified()


def test_open_warns_about_missing_images(win, monkeypatch, photos, tmp_path, messages):
    import shutil
    from pyfigures.poster.poster_canvas import PosterCanvas
    gone = shutil.copy(photos["red"], tmp_path / "gone.png")
    c = PosterCanvas()
    c.add_image(str(gone))
    c.add_image(photos["blue"])
    doc = str(tmp_path / "m.pyfposter")
    c.save(doc, filetype="pyfposter")
    os.remove(gone)
    _file_dialogs(monkeypatch, open_path=doc)
    win.open_action.trigger()
    assert messages[-1][1] == "Missing images" and "gone.png" in messages[-1][2]


def test_open_corrupt_file_is_reported(win, monkeypatch, tmp_path, messages):
    bad = tmp_path / "bad.pyfposter"
    bad.write_text("<not xml", encoding="utf-8")
    _file_dialogs(monkeypatch, open_path=str(bad))
    win.open_action.trigger()
    assert messages[-1][0] == "critical"


def test_export_buttons(win, monkeypatch, photos, tmp_path, messages):
    from PIL import Image
    c = win.canvas
    c.add_image(photos["red"])
    for ext in ("png", "jpg", "tif", "pdf", "svg"):
        out = str(tmp_path / f"page.{ext}")
        _file_dialogs(monkeypatch, save_path=out)
        _items(monkeypatch, "72")
        win.export_action.trigger()
        assert os.path.getsize(out) > 0, ext
    assert Image.open(str(tmp_path / "page.png")).size == (round(210 * 72 / 25.4), round(297 * 72 / 25.4))

    _file_dialogs(monkeypatch, save_path=str(tmp_path / "book"))
    _items(monkeypatch, "72")
    win.export_album_action.trigger()
    assert os.path.getsize(tmp_path / "book.pdf") > 0

    # print-ready: current page, tiff, cmyk, 150 dpi
    _file_dialogs(monkeypatch, save_path=str(tmp_path / "print"))
    _items(monkeypatch, "Current page", "tiff", "cmyk", "150")
    win.export_print_action.trigger()
    assert Image.open(tmp_path / "print.tif").mode == "CMYK"
    # whole document as a folder of pages
    folder = tmp_path / "pages"
    folder.mkdir()
    _file_dialogs(monkeypatch, folder=str(folder))
    _items(monkeypatch, "Whole document", "svg", "150")
    win.export_print_action.trigger()
    assert sorted(os.listdir(folder)) == ["manifest.json", "page_01_single.svg"]

    _file_dialogs(monkeypatch, save_path=str(tmp_path / "web"))
    win.export_web_action.trigger()
    assert "data:image/jpeg;base64," in (tmp_path / "web.html").read_text(encoding="utf-8")


def test_export_cancelled_dialogs_do_nothing(win, monkeypatch, tmp_path):
    _file_dialogs(monkeypatch)                          # every dialog cancelled
    for act in (win.export_action, win.export_album_action, win.export_web_action, win.open_action,
                win.add_image_action, win.bg_action):
        act.trigger()
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    win.export_print_action.trigger()
    assert win.canvas.shapes_to_draw == [] and not win.canvas.is_modified()


def test_source_data_button_saves_then_bundles(win, monkeypatch, photos, tmp_path, messages):
    c = win.canvas
    c.add_image(photos["red"])
    out = tmp_path / "bundle"
    _file_dialogs(monkeypatch, save_path=str(tmp_path / "sd"), folder=str(out))
    win.export_source_data_action.trigger()
    assert os.path.isfile(tmp_path / "sd.pyfposter")
    assert messages[-1][1] == "Source-data bundle", messages
    assert os.path.isfile(out / "manifest.json") and os.path.isfile(out / "sd.pyfposter")


# ---------------------------------------------------------------------------
# page dock
# ---------------------------------------------------------------------------

def test_page_dock_add_duplicate_move_delete(win, photos, messages):
    c = win.canvas
    c.add_image(photos["red"])
    labels = {a.text(): a for a in win.page_add_menu.actions()}
    labels["Spread (two pages)"].trigger()
    assert win.page_list.count() == 2 and c.current_page_index == 1 and c.current_page.kind == "spread"
    labels["Front cover"].trigger()
    labels["Back cover"].trigger()
    labels["Plain page"].trigger()
    assert [p.kind for p in c.pages] == ["single", "spread", "cover_front", "cover_back", "single"]
    win.page_list.setCurrentRow(0)
    assert c.current_page_index == 0
    win.page_dup_button.click()
    assert win.page_list.count() == 6 and len(c.pages[1].shapes_to_draw) == 1
    win.page_down_button.click()
    assert c.current_page_index == 2 and len(c.pages[2].shapes_to_draw) == 1
    win.page_up_button.click()
    assert c.current_page_index == 1
    win.page_del_button.click()
    assert win.page_list.count() == 5
    while c.page_count() > 1:
        win.page_del_button.click()
    win.page_del_button.click()                         # last page: explained, not removed
    assert c.page_count() == 1 and messages[-1][1] == "Only page"


@pytest.fixture
def album_win(qapp, monkeypatch, messages):
    from pyfigures.poster.poster_window import PosterWindow
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Discard))
    w = PosterWindow(album=True)
    w.show()
    qapp.processEvents()
    yield w
    w.canvas.mark_saved()
    w.close()


def test_poster_window_cannot_become_an_album(win):
    from qtpy.QtWidgets import QCheckBox
    assert not win.album and not win.canvas.album_mode
    assert not win.page_dock.findChildren(QCheckBox)     # no album toggle any more
    assert not hasattr(win, "album_mode_check")
    labels = [a.text() for a in win.page_add_menu.actions() if a.isVisible()]
    assert labels == ["Spread (two pages)", "Front cover", "Back cover", "Plain page"]
    win.new_action.trigger()
    assert not win.canvas.album_mode and [p.kind for p in win.canvas.pages] == ["single"]


def test_album_window_starts_as_an_album_with_pinned_covers(album_win, photos):
    win = album_win
    c = win.canvas
    assert win.album and c.album_mode and not c.is_modified() and not c.can_undo()
    assert "Photo Album Designer" in win.windowTitle()
    assert [p.kind for p in c.pages] == ["cover_front", "spread", "cover_back"]
    assert c.pages[1].width_mm == 2 * c.pages[0].width_mm
    labels = [a.text() for a in win.page_add_menu.actions() if a.isVisible()]
    assert labels == ["Spread (two pages)"]              # covers/plain pages: never by hand
    win.page_list.setCurrentRow(0)
    assert not win.page_dup_button.isEnabled() and not win.page_del_button.isEnabled()
    assert not win.page_up_button.isEnabled() and not win.page_down_button.isEnabled()
    win.page_list.setCurrentRow(1)
    c.add_image(photos["red"])
    assert win.page_dup_button.isEnabled() and not win.page_up_button.isEnabled()
    assert not win.page_down_button.isEnabled()          # the back cover is next
    win.page_add_menu.actions()[0].trigger()
    assert [p.kind for p in c.pages] == ["cover_front", "spread", "spread", "cover_back"]
    win.undo_action.trigger()
    assert win.page_list.count() == 3                    # dock follows undo
    c.mark_saved()
    win.new_action.trigger()                             # New: a blank album again
    assert c.album_mode and [p.kind for p in c.pages] == ["cover_front", "spread", "cover_back"]
    assert not c.is_modified()


def test_album_window_saves_pyfalbum_and_reopens_it(album_win, monkeypatch, tmp_path, photos):
    from pyfigures.poster.serialization import is_photo_album
    c = album_win.canvas
    c.goto_page(1)
    c.add_image(photos["red"])
    _file_dialogs(monkeypatch, save_path=str(tmp_path / "trip"))
    album_win.save_action.trigger()
    path = str(tmp_path / "trip.pyfalbum")
    assert c.file_path == path and is_photo_album(path)
    album_win.new_action.trigger()
    album_win.open_poster(path)
    assert c.album_mode and c.page_count() == 3 and c.file_path == path


def test_each_designer_refuses_the_others_documents(win, album_win, tmp_path, photos, messages):
    from pyfigures.poster.serialization import is_photo_album
    album_win.canvas.goto_page(1)
    album_win.canvas.add_image(photos["red"])
    album = str(tmp_path / "book.pyfalbum")
    album_win.canvas.save(album, filetype="pyfalbum")
    win.canvas.add_image(photos["blue"])
    poster = str(tmp_path / "one.pyfposter")
    win.canvas.save(poster, filetype="pyfposter")
    win.canvas.add_page("spread")
    pages = str(tmp_path / "pages.pyfalbum")              # multi-page, but not a photo album
    win.canvas.save(pages, filetype="pyfalbum")
    assert is_photo_album(album) and not is_photo_album(poster) and not is_photo_album(pages)

    win.open_poster(album)
    assert messages[-1][1] == "Photo album" and "pyfigures.album" in messages[-1][2]
    assert not win.canvas.album_mode and win.canvas.file_path == pages     # nothing replaced
    for other in (poster, pages):
        album_win.open_poster(other)
        assert messages[-1][1] == "Not a photo album"
        assert album_win.canvas.file_path == album
    win.open_poster(poster)
    assert win.canvas.file_path == poster


def test_each_designer_refuses_the_others_recipes(win, album_win, tmp_path, photos, messages):
    import shutil
    shutil.copy(photos["red"], tmp_path / "a.png")
    (tmp_path / "album.yaml").write_text(
        "output: book.pyfalbum\nalbum: true\nspreads:\n  - images: [a.png]\n", encoding="utf-8")
    (tmp_path / "poster.yaml").write_text("output: p.pyfposter\nimages: [a.png]\n", encoding="utf-8")
    win.build_from_recipe(str(tmp_path / "album.yaml"))
    assert messages[-1][1] == "Photo album" and not (tmp_path / "book.pyfalbum").exists()
    album_win.build_from_recipe(str(tmp_path / "poster.yaml"))
    assert messages[-1][1] == "Not a photo album" and not (tmp_path / "p.pyfposter").exists()
    album_win.build_from_recipe(str(tmp_path / "album.yaml"))
    assert messages[-1][1] == "Recipe built" and album_win.canvas.album_mode
    win.build_from_recipe(str(tmp_path / "poster.yaml"))
    assert messages[-1][1] == "Recipe built" and not win.canvas.album_mode


def test_album_launcher_opens_the_album_designer(monkeypatch):
    import runpy
    import pyfigures.poster.__main__ as poster_main
    calls = []
    monkeypatch.setattr(poster_main, "run_poster_designer", lambda album=False: calls.append(album))
    runpy.run_module("pyfigures.album", run_name="__main__")
    assert calls == [True]


def test_page_thumbnails_show_content(win, photos):
    c = win.canvas
    c.set_background(photos["blue"])
    win._refresh_page_list()
    img = win.page_list.item(0).icon().pixmap(64, 64).toImage()
    color = img.pixelColor(img.width() // 2, img.height() // 2)
    assert color.blue() > 150 and color.red() < 100


# ---------------------------------------------------------------------------
# mouse gestures on the canvas
# ---------------------------------------------------------------------------

@pytest.fixture
def canvas(win):
    return win.canvas


def test_click_selects_without_marking_modified(canvas, photos):
    s = canvas.add_image(photos["red"], x_mm=50, y_mm=50, width_mm=40)
    canvas.mark_saved()
    canvas.selected = None
    p = _px(canvas, 70, 60)
    _mouse(canvas, "press", p)
    _mouse(canvas, "release", p)
    assert canvas.selected is s
    assert not canvas.is_modified()                      # used to push an undo step per click
    _mouse(canvas, "press", _px(canvas, 200, 280))       # empty page: deselect
    _mouse(canvas, "release", _px(canvas, 200, 280))
    assert canvas.selected is None


def test_drag_moves_shape_one_undo_step(canvas, photos):
    s = canvas.add_image(photos["red"], x_mm=50, y_mm=50, width_mm=40)
    canvas.mark_saved()
    _drag(canvas, _px(canvas, 70, 60), _px(canvas, 100, 120), mods=Qt.KeyboardModifier.AltModifier)
    assert (s.x_mm, s.y_mm) == pytest.approx((80, 110), abs=0.01)    # Alt: no snapping
    assert canvas.is_modified()
    canvas.undo()
    s0 = canvas.shapes_to_draw[0]
    assert (s0.x_mm, s0.y_mm) == pytest.approx((50, 50))
    assert not canvas.is_modified()


def test_drag_snaps_to_page_centre(canvas, photos):
    s = canvas.add_image(photos["blue"], x_mm=40, y_mm=40, width_mm=20, height_mm=20)
    # centre lands 0.3 mm from the page's vertical centre line (105 mm)
    _drag(canvas, _px(canvas, 50, 50), _px(canvas, 50 + 54.7, 50))
    assert s.center_mm().x() != pytest.approx(104.7, abs=1e-6)       # pulled towards 105
    assert abs(s.center_mm().x() - 105) < 0.3


def test_group_drag_moves_every_member(canvas, photos):
    a = canvas.add_image(photos["red"], x_mm=20, y_mm=20, width_mm=40)
    b = canvas.add_image(photos["blue"], x_mm=120, y_mm=150, width_mm=30)
    t = canvas.add_text("lonely", x_mm=150, y_mm=20)
    a.group_id = b.group_id = "g1"
    tb = _geom(t)
    _drag(canvas, _px(canvas, 30, 30), _px(canvas, 40, 50))
    assert (a.x_mm, a.y_mm) == pytest.approx((30, 40), abs=0.01)
    assert (b.x_mm, b.y_mm) == pytest.approx((130, 170), abs=0.01)
    assert _geom(t) == tb


def test_shift_click_multi_select_then_drag_together(canvas, photos):
    a = canvas.add_image(photos["red"], x_mm=20, y_mm=20, width_mm=40)
    b = canvas.add_image(photos["blue"], x_mm=120, y_mm=150, width_mm=30)
    shift = Qt.KeyboardModifier.ShiftModifier
    for s, pos in ((a, _px(canvas, 30, 30)), (b, _px(canvas, 130, 160))):
        _mouse(canvas, "press", pos, shift)
        _mouse(canvas, "release", pos, shift)
    assert canvas.multi_selected == [a, b]
    _drag(canvas, _px(canvas, 30, 30), _px(canvas, 35, 30))
    assert (a.x_mm, b.x_mm) == pytest.approx((25, 125), abs=0.01)
    _mouse(canvas, "press", _px(canvas, 130, 160), shift)             # shift-click again removes
    _mouse(canvas, "release", _px(canvas, 130, 160), shift)
    assert canvas.multi_selected == [a]
    _mouse(canvas, "press", _px(canvas, 200, 280))                    # plain click elsewhere clears
    assert canvas.multi_selected == []


def test_rotate_handle_with_shift_snaps_to_15_degrees(canvas, photos):
    s = canvas.add_image(photos["blue"], x_mm=80, y_mm=100, width_mm=40, height_mm=40)
    canvas.selected = s
    handle = s.rotate_handle_pos_mm()
    c = s.center_mm()
    # drag the handle to the right of the centre, a bit below horizontal (~ 97°)
    target = _px(canvas, c.x() + 40, c.y() + 5)
    _drag(canvas, _px(canvas, handle.x(), handle.y()), target)
    assert 90 < s.theta < 100
    canvas.selected = s
    handle = s.rotate_handle_pos_mm()
    _drag(canvas, _px(canvas, handle.x(), handle.y()), target, mods=Qt.KeyboardModifier.ShiftModifier)
    assert s.theta == pytest.approx(90.0)


def test_corner_resize_keeps_aspect(canvas, photos):
    s = canvas.add_image(photos["red"], x_mm=50, y_mm=50, width_mm=40)     # 40 x 20
    canvas.selected = s
    br = s.corner_handles_mm()["br"]
    _drag(canvas, _px(canvas, br.x(), br.y()), _px(canvas, br.x() + 40, br.y() + 5))
    assert (s.x_mm, s.y_mm) == pytest.approx((50, 50))                       # anchor stays
    assert s.width_mm / s.height_mm == pytest.approx(2.0)
    assert s.width_mm == pytest.approx(80, abs=0.01)
    # never below the minimum size, never inverted
    br = s.corner_handles_mm()["br"]
    _drag(canvas, _px(canvas, br.x(), br.y()), _px(canvas, 0, 0))
    assert s.width_mm >= 10 - 1e-9 and s.height_mm >= 10 - 1e-9 and s.x_mm == pytest.approx(50)


def test_ctrl_corner_crops_then_ctrl_drag_pans_crop(canvas, photos):
    s = canvas.add_image(photos["red"], x_mm=50, y_mm=50, width_mm=100)    # 100 x 50
    canvas.selected = s
    ctrl = Qt.KeyboardModifier.ControlModifier
    br = s.corner_handles_mm()["br"]
    _drag(canvas, _px(canvas, br.x(), br.y()), _px(canvas, br.x() - 50, br.y() - 25), mods=ctrl)
    assert s.width_mm == pytest.approx(50, abs=0.05)
    assert s.crop_right == pytest.approx(0.5, abs=0.01) and s.crop_bottom == pytest.approx(0.5, abs=0.01)
    assert s.crop_left == 0 and s.crop_top == 0
    # a crop can never hide more than 85 % of an axis
    br = s.corner_handles_mm()["br"]
    _drag(canvas, _px(canvas, br.x(), br.y()), _px(canvas, s.x_mm, s.y_mm), mods=ctrl)
    assert s.crop_right <= 0.85 + 1e-9
    # Ctrl+drag on the body slides the crop window, box unchanged
    box = _geom(s)
    total = s.crop_left + s.crop_right
    c = s.center_mm()
    _drag(canvas, _px(canvas, c.x(), c.y()), _px(canvas, c.x() - 3, c.y()), mods=ctrl)
    assert _geom(s) == box
    assert s.crop_left + s.crop_right == pytest.approx(total)
    assert s.crop_left > 0


def test_background_drag_pans_and_wheel_zooms(canvas, photos):
    canvas.set_background(photos["green"])                 # portrait on A4: vertical slack
    bg = canvas.background
    canvas.mark_saved()
    _drag(canvas, _px(canvas, 100, 150), _px(canvas, 100, 120))
    assert bg.pan_y_frac > 0.5 and canvas.is_modified()
    pos = _px(canvas, 100, 150)
    ev = QWheelEvent(pos, canvas.mapToGlobal(pos), QPoint(0, 0), QPoint(0, 240),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    n = len(canvas._undo_stack)
    canvas.wheelEvent(ev)
    assert bg.zoom == pytest.approx(1.21) and len(canvas._undo_stack) == n + 1


def test_wheel_over_a_photo_is_left_to_the_scroll_area(canvas, photos):
    canvas.add_image(photos["red"], x_mm=50, y_mm=50, width_mm=40)
    pos = _px(canvas, 60, 55)
    ev = QWheelEvent(pos, canvas.mapToGlobal(pos), QPoint(0, 0), QPoint(0, 120),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    canvas.wheelEvent(ev)
    assert not ev.isAccepted()


def test_double_click_text_opens_editor(canvas, monkeypatch):
    opened = []
    monkeypatch.setattr(type(canvas), "edit_text", lambda self, shape: opened.append(shape))
    t = canvas.add_text("hello", x_mm=50, y_mm=50)
    c = t.center_mm()
    _mouse(canvas, "dbl", _px(canvas, c.x(), c.y()))
    assert opened == [t]


def test_text_editor_dialog_style_combo(qapp):
    from pyfigures.poster.poster_shapes import PosterText
    from pyfigures.poster.poster_text_dialog import PosterTextDialog
    t = PosterText("Hi", style="body", height_mm=4)
    changed = []
    d = PosterTextDialog(t, on_change=lambda: changed.append(1), page_height_mm=297)
    assert d.style_combo.currentData() == "body"
    d.style_combo.setCurrentIndex(d.style_combo.findData("h1"))
    assert t.style == "h1" and t.height_mm == pytest.approx(297 * 0.05) and changed


# ---------------------------------------------------------------------------
# drag and drop from the file manager
# ---------------------------------------------------------------------------

def test_drop_requires_urls(canvas):
    enter = _drop(canvas, [], _px(canvas, 50, 50), text_only=True)
    assert not enter.isAccepted()
    assert canvas.shapes_to_draw == []


def test_drop_single_image_add_or_background(canvas, monkeypatch, photos):
    shown = _menu_picks(monkeypatch, "Add to page", "Set as background", None)
    _drop(canvas, [photos["red"]], _px(canvas, 50, 50))
    assert len(canvas.shapes_to_draw) == 1 and shown[0] == ["Add to page", "Set as background"]
    _drop(canvas, [photos["blue"]], _px(canvas, 150, 200))
    assert canvas.background.path == photos["blue"] and len(canvas.shapes_to_draw) == 1
    _drop(canvas, [photos["green"]], _px(canvas, 50, 50))      # menu dismissed: nothing
    assert len(canvas.shapes_to_draw) == 1


@pytest.mark.parametrize("choice,check", [
    ("Scatter", lambda shapes: any(s.theta != 0 for s in shapes)),
    ("Fan", lambda shapes: shapes[0].theta < 0 < shapes[-1].theta),
    ("Grid", lambda shapes: all(s.theta == 0 for s in shapes)),
    ("Just add them", lambda shapes: len({(round(s.center_mm().x(), 6), round(s.center_mm().y(), 6))
                                           for s in shapes}) == 1),
])
def test_drop_several_images_arrangement_menu(canvas, monkeypatch, photos, choice, check):
    shown = _menu_picks(monkeypatch, choice)
    n0 = len(canvas._undo_stack)
    _drop(canvas, [photos["red"], photos["green"], photos["blue"]], _px(canvas, 50, 50))
    assert shown[0][0] == "Arrange 3 dropped images as..."
    assert len(canvas.shapes_to_draw) == 3 and check(canvas.shapes_to_draw)
    assert len(canvas._undo_stack) == n0 + 1                  # the whole drop is one undo step
    canvas.undo()
    assert canvas.shapes_to_draw == []


def test_drop_several_images_dismissed_adds_nothing(canvas, monkeypatch, photos):
    _menu_picks(monkeypatch, None)
    _drop(canvas, [photos["red"], photos["green"]], _px(canvas, 50, 50))
    assert canvas.shapes_to_draw == []


def test_drop_several_with_layout_gallery(canvas, monkeypatch, photos):
    from pyfigures.poster import poster_layout_dialog as dlg_mod

    def fake_exec(self):
        self.selected_layout = "triptych"
        return 1
    monkeypatch.setattr(dlg_mod.LayoutGalleryDialog, "exec", fake_exec)
    _menu_picks(monkeypatch, "Choose a layout")
    _drop(canvas, [photos["red"], photos["green"], photos["blue"]], _px(canvas, 50, 50))
    xs = [s.center_mm().x() for s in canvas.shapes_to_draw]
    assert xs == sorted(xs) and len({s.group_id for s in canvas.shapes_to_draw}) == 1


def test_drop_folder_walks_and_filters(canvas, monkeypatch, photos, tmp_path):
    sub = tmp_path / "photos" / "sub"
    sub.mkdir()
    _png(sub / "deep.png", (50, 50), (1, 2, 3))
    (tmp_path / "photos" / "notes.txt").write_text("not an image")
    shown = _menu_picks(monkeypatch, "Grid")
    _drop(canvas, [str(tmp_path / "photos")], _px(canvas, 50, 50))
    assert shown[0][0] == "Arrange 4 dropped images as..."
    assert sorted(os.path.basename(s.path) for s in canvas.shapes_to_draw) == \
        ["blue.png", "deep.png", "green.png", "red.png"]


def test_drop_onto_empty_slot_fills_it(canvas, monkeypatch, photos):
    slots = canvas.sketch_layout("diptych")
    target = slots[1]
    c = target.center_mm()
    shown = _menu_picks(monkeypatch)                          # no menu expected
    _drop(canvas, [photos["green"]], _px(canvas, c.x(), c.y()))
    assert shown == []
    assert not target.is_template and target.path == photos["green"]
    assert slots[0].is_template


def test_drop_several_fills_slots_in_order(canvas, monkeypatch, photos):
    slots = canvas.sketch_layout("diptych")
    _menu_picks(monkeypatch, "Fill 2 empty template slots")
    _drop(canvas, [photos["red"], photos["green"], photos["blue"]], _px(canvas, 5, 5))
    assert [s.path for s in slots] == [photos["red"], photos["green"]]
    assert len(canvas.shapes_to_draw) == 3                    # the leftover is added too


def test_drop_skips_unreadable_files(canvas, monkeypatch, photos, tmp_path, messages):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"nope")
    _menu_picks(monkeypatch, "Grid")
    _drop(canvas, [photos["red"], str(bad), photos["blue"]], _px(canvas, 50, 50))
    assert len(canvas.shapes_to_draw) == 2
    assert messages[-1][1] == "Some files were skipped" and "broken.png" in messages[-1][2]
    _menu_picks(monkeypatch, "Add to page")
    _drop(canvas, [str(bad)], _px(canvas, 50, 50))
    assert len(canvas.shapes_to_draw) == 2 and messages[-1][1] == "Could not add image"


def test_drop_pyf_is_flattened_and_tagged(canvas, monkeypatch, photos, tmp_path):
    from pyfigures.poster import poster_canvas
    pyf = tmp_path / "fig.pyf"
    pyf.write_text("<x/>", encoding="utf-8")
    rendered = []

    def fake_render(path, dpi=300, parent=None):
        rendered.append(path)
        return photos["blue"]
    monkeypatch.setattr(poster_canvas, "_render_pyf_to_png", fake_render)
    shown = _menu_picks(monkeypatch)
    _drop(canvas, [str(pyf)], _px(canvas, 50, 50))
    assert shown == []                                        # a figure is never a background: no menu
    assert rendered == [str(pyf)]
    s = canvas.shapes_to_draw[0]
    assert s.path == photos["blue"] and s.source_pyf == str(pyf)


def test_drop_pyf_render_failure_is_reported(canvas, monkeypatch, tmp_path, messages):
    from pyfigures.poster import poster_canvas
    pyf = tmp_path / "broken.pyf"
    pyf.write_text("x", encoding="utf-8")

    def boom(path, dpi=300, parent=None):
        raise RuntimeError("render exploded")
    monkeypatch.setattr(poster_canvas, "_render_pyf_to_png", boom)
    _drop(canvas, [str(pyf)], _px(canvas, 50, 50))
    assert canvas.shapes_to_draw == []
    assert messages[-1][1] == "Could not render figure(s)" and "render exploded" in messages[-1][2]


def test_painted_canvas_shows_selection_and_page(canvas, photos):
    s = canvas.add_image(photos["red"], x_mm=50, y_mm=50, width_mm=40)
    canvas.selected = s
    img = canvas.grab().toImage()
    p = _px(canvas, 70, 60)
    col = img.pixelColor(int(p.x()), int(p.y()))
    assert col.red() > 180 and col.green() < 80
    page_corner = _px(canvas, 200, 280)
    assert img.pixelColor(int(page_corner.x()), int(page_corner.y())).lightness() > 240
    outside = _px(canvas, -5, -5)                               # the dark mat around the page
    assert img.pixelColor(int(outside.x()), int(outside.y())).lightness() < 240
