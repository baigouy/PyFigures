"""Figures built automatically stay within one printed page (2026-11-16):
ten images added in the chat went one below the other at the full figure
width, several pages tall. After images are added (GUI or chat) a figure
taller than the page gets rows, then a narrower width; View → Fit new layouts
to the page turns it off; the rows the chat was asked for are kept."""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_dnd_main_editor import ui, gui  # noqa: F401,E402
from test_assistant_live import runtime  # noqa: F401,E402  (an own live-session folder)

MM = 25.4 / 72.0
SHAPES = [(100, 100), (80, 120), (120, 60), (100, 100), (90, 140)]


@pytest.fixture
def fit_on(monkeypatch):
    from pyfigures.gui import user_prefs, page_fit
    monkeypatch.setattr(page_fit, "enabled", lambda: True)      # conftest turns it off
    monkeypatch.setattr(user_prefs, "load_page_size", lambda: "A4")


def _images(tmp_path, shapes):
    from batoolset.img import Img
    from batoolset.drawings.shapes.image2d import Image2D
    out = []
    for i, shape in enumerate(shapes):
        p = str(tmp_path / f"i{i}.tif")
        Img((np.random.default_rng(i).random(shape) * 255).astype(np.uint8), dimensions="hw").save(p)
        out.append(Image2D(p))
    return out


def _size_mm(gui):
    from pyfigures.gui.page_fit import figure_size_pt
    w, h = figure_size_pt(gui.paint.EZFIG_panel)
    return w * MM, h * MM


def test_ten_images_added_go_into_rows_within_the_page(gui, tmp_path, fit_on):
    from batoolset.drawings.shapes.group import Group
    gui._finish_add_single_images(_images(tmp_path, SHAPES * 2))
    w, h = _size_mm(gui)
    assert h <= 247.5 and w > 170, (w, h)              # full width kept, rows instead
    shapes = gui.paint.EZFIG_panel.shapes_to_draw
    assert all(isinstance(s, Group) for s in shapes) and sum(len(s.content) for s in shapes) == 10
    assert "A4 page" in gui.statusBar().currentMessage()
    gui.undo()                                           # one undo step takes back the add and the fit
    assert not gui.paint.EZFIG_panel.shapes_to_draw


def test_off_keeps_the_images_one_below_the_other(gui, tmp_path, monkeypatch):
    from pyfigures.gui import user_prefs, page_fit
    monkeypatch.setattr(page_fit, "enabled", page_fit.prefs_enabled)   # the View setting decides
    monkeypatch.setattr(user_prefs, "load_fit_to_page", lambda: False)
    gui._finish_add_single_images(_images(tmp_path, SHAPES * 2))
    assert len(gui.paint.EZFIG_panel.shapes_to_draw) == 10 and _size_mm(gui)[1] > 1000


def test_a_short_figure_is_not_touched(gui, tmp_path, fit_on):
    gui._finish_add_single_images(_images(tmp_path, [(100, 100)]))
    assert len(gui.paint.EZFIG_panel.shapes_to_draw) == 1
    assert gui.size_spinbox.value() == 512 and gui.statusBar().currentMessage() == ""


def test_one_very_tall_image_is_narrowed_to_fit(gui, tmp_path, fit_on):
    gui._finish_add_single_images(_images(tmp_path, [(400, 100)]))     # 4 times as tall as wide
    w, h = _size_mm(gui)
    assert h <= 247.5 and 55 < w < 65, (w, h)
    assert gui.size_spinbox.value() < 512                 # the width shown follows


def test_a_column_too_long_to_fit_is_reported_not_squeezed(gui, tmp_path, fit_on):
    from pyfigures.gui.page_fit import fit_to_page
    from batoolset.drawings.shapes.group import Group
    panel = gui.paint.EZFIG_panel
    column = Group(*_images(tmp_path, [(100, 100)] * 20), orientation="Y")   # the user's own column
    panel.shapes_to_draw.append(column)
    gui.update_size_of_object(column)
    note = fit_to_page(gui)
    assert "too small to read" in note and gui.size_spinbox.value() == 512, note


def test_the_rows_the_chat_asked_for_are_kept_and_narrowed(gui, tmp_path, fit_on):
    """arrange_live_images(columns=1) for ten images: one per row, as asked,
    then narrower so the page holds them (or a note when it cannot)."""
    from pyfigures.gui.page_fit import fit_to_page
    from batoolset.drawings.shapes.group import Group
    panel = gui.paint.EZFIG_panel
    for img in _images(tmp_path, [(200, 100)] * 3):          # three tall images, one per row
        row = Group(img, orientation="X")
        panel.shapes_to_draw.append(row)
        gui.update_size_of_object(row)
    note = fit_to_page(gui)
    w, h = _size_mm(gui)
    assert len(panel.shapes_to_draw) == 3 and h <= 247.5 and "narrowed" in note, (w, h, note)


def test_page_sizes_and_menu(gui):
    from pyfigures.gui.page_fit import PAGES_MM
    assert PAGES_MM["A4"] == (180.0, 247.0)
    assert gui.fit_page_action.isCheckable() and set(gui.page_size_actions) == {"A4", "Letter"}


def test_ten_images_added_by_the_chat_fit_the_page(qapp, runtime, tmp_path, fit_on):  # noqa: F811
    """The chat's add_image batch (the 2026-11-16 request "a fig with 10 random
    images"): the result says how the figure was fitted."""
    import uuid
    from batoolset.img import Img
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import PartnerGUI
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = PartnerGUI()
    try:
        files = []
        for i, shape in enumerate(SHAPES * 2):
            f = str(tmp_path / f"c{i}.tif")
            Img((np.random.default_rng(i).random(shape) * 255).astype(np.uint8), dimensions="hw").save(f)
            files.append(f)
        session = launch.start_live_session(g)
        s = session.snapshot()
        result = session.execute(dict(operation="original_tool", request_id=str(uuid.uuid4()),
                                      session_id=s["session_id"], expected_revision=s["revision"],
                                      arguments={"tool": "add_image", "arguments": {"group_path": []},
                                                 "batch": [{"group_path": [], "filename": f} for f in files]}))
        assert "A4 page" in result.get("page_fit", ""), result.get("page_fit")
        assert _size_mm(g)[1] <= 247.5
    finally:
        launch.stop_live_session(g)
        g._dirty = False
        g.close()


def test_a_figure_wider_than_the_page_is_brought_to_the_page_width(gui, tmp_path, fit_on):
    """After the chat added images the figure took the width of its widest
    image (2000 px = 705 mm): rows 705 mm wide 'fitted' the page height only."""
    from pyfigures.gui.page_fit import fit_to_page
    gui.size_spinbox.blockSignals(True)
    gui.size_spinbox.setValue(2000)
    gui.size_spinbox.blockSignals(False)
    panel = gui.paint.EZFIG_panel
    for img in _images(tmp_path, SHAPES * 2):
        panel.shapes_to_draw.append(img)
        gui.update_size_of_object(img, 2000)
    note = fit_to_page(gui)
    w, h = _size_mm(gui)
    assert w <= 180.5 and h <= 247.5, (w, h, note)
    assert abs(gui.size_spinbox.value() * MM - w) < 2      # the next layout starts from it


def test_never_more_than_five_images_per_row_unless_asked(gui, tmp_path, fit_on):
    """Twenty small images: rows of 5 at most (the user: a longer row is hard
    to read), even when more per row would fit the page."""
    from batoolset.drawings.shapes.group import Group
    from pyfigures.mcp_tools.workflow import _auto_grid
    gui._finish_add_single_images(_images(tmp_path, [(60, 100)] * 20))
    rows = gui.paint.EZFIG_panel.shapes_to_draw
    assert all(isinstance(r, Group) and len(r.content) <= 5 for r in rows)
    assert sum(len(r.content) for r in rows) == 20
    assert all(_auto_grid(n)[0] <= 5 for n in range(1, 60))     # create_figure_from_folder / draft


def test_chat_edits_say_they_are_working():
    """Sixteen images took 7 s on the GUI thread: the window looked frozen
    (2026-11-16). Edits now show a wait cursor and say what runs."""
    from pyfigures.assistant.session import busy_message
    add = {"operation": "original_tool", "arguments": {"tool": "add_image", "batch": [{}] * 16}}
    assert busy_message(add) == "Chat: adding 16 images…"
    assert busy_message({"operation": "arrange_rows"}) == "Chat: arranging the images in rows…"
    assert busy_message({"operation": "original_tool", "arguments": {"tool": "get_image_property"}}) is None
    assert busy_message({"operation": "inspect"}) is None
