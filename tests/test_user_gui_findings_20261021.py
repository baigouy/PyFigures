"""Bugs the user found in a few minutes of playing with the GUI (2026-10-21):
two drop menus at once, no max projection offered for a dropped time stack, a
full-screen montage dialog with no help, white letters on their white box, the
scale bar's placeholder text kept in the figure, projection controls (and an
odd empty Dimensions box) on a plain 2-D image, 'Force same width and height'
offered on a split whose panels already match."""
from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit

from test_dnd_main_editor import ui, gui, drop, menu_buttons, click, drop_menu, _wait, _all_images  # noqa: F401


def _stack(path, axes, shape):
    import tifffile
    data = (np.arange(int(np.prod(shape))) % 251).astype(np.uint8).reshape(shape)
    tifffile.imwrite(str(path), data, imagej=True, metadata={"axes": axes})
    return str(path)


def _plain(path):
    from batoolset.img import Img
    Img(np.full((40, 60), 90, np.uint8), dimensions="hw").save(str(path))
    return str(path)


# --- drop menu ---------------------------------------------------------------

def test_a_second_drop_replaces_the_first_drop_menu(gui, tmp_path):
    a, b = _plain(tmp_path / "a.tif"), _plain(tmp_path / "b.tif")
    drop(gui, [a])
    first = drop_menu(gui)
    assert first is not None
    drop(gui, [b])
    from pyfigures.gui.pfgui import QFrame, QPushButton
    shown = [f for f in gui.findChildren(QFrame) if f.isVisible() and f.parent() is gui
             and f.findChildren(QPushButton)]
    assert len(shown) == 1, "two drop menus on screen"
    click(gui, "✕  Cancel")
    assert drop_menu(gui) is None and gui._dnd_menu is None


def test_a_dropped_time_stack_can_be_added_as_its_max_projection(gui, qapp, tmp_path):
    movie = _stack(tmp_path / "movie.tif", "TYX", (5, 30, 40))
    drop(gui, [movie])
    label = "▣  As max projection over time (5 frames)"
    buttons = menu_buttons(gui)
    # a time series: the montage comes first, the projection is offered, not imposed
    assert buttons.index("🎞  Montage of frames (time / Z)…") < buttons.index(label) \
        < buttons.index("➕  As single image(s)"), buttons
    from qtpy.QtWidgets import QPushButton
    tips = {b.text(): b.toolTip() for b in drop_menu(gui).findChildren(QPushButton)}
    assert "movie" in tips["➕  As single image(s)"]
    click(gui, label)
    _wait(qapp, gui, lambda: _all_images(gui))
    img = _all_images(gui)[0]
    assert img.projection == "max"


def test_z_stack_shown_projected_already_gets_no_duplicate_entry(gui, tmp_path):
    z = _stack(tmp_path / "z.tif", "ZYX", (4, 30, 40))
    gui.max_proj_action.setChecked(True)
    drop(gui, [z])
    assert not any(t.startswith("▣") for t in menu_buttons(gui))
    gui.max_proj_action.setChecked(False)
    click(gui, "✕  Cancel")
    drop(gui, [z])
    assert "▣  As max projection over Z (4 slices)" in menu_buttons(gui)
    click(gui, "✕  Cancel")
    gui.max_proj_action.setChecked(True)


# --- montage dialog ------------------------------------------------------------

def test_montage_dialog_fits_its_content_and_explains_its_options(gui, tmp_path, monkeypatch):
    from batoolset.GUI.customdialog import CustomDialog
    from pyfigures.gui.pfgui import QDialog
    seen = {}

    def exec_(dlg, *a, **k):
        seen["dlg"] = dlg
        seen["size"] = dlg.size()
        frame = dlg.main_widget
        seen["tips"] = {lab.text(): lab.toolTip() for lab in frame.findChildren(QLabel)}
        axis = frame.findChildren(QComboBox)[0]
        data = [axis.itemData(i) for i in range(axis.count())]
        axis.setCurrentIndex(data.index("z"))
        seen["hidden"] = [lab.text() for lab in frame.findChildren(QLabel) if lab.isHidden()]
        axis.setCurrentIndex(data.index("t"))
        seen["hidden_time"] = [lab.text() for lab in frame.findChildren(QLabel) if lab.isHidden()]
        return QDialog.Rejected
    monkeypatch.setattr(CustomDialog, "exec_", exec_, raising=False)
    monkeypatch.setattr(CustomDialog, "exec", exec_)
    stack = _stack(tmp_path / "zt.tif", "TZYX", (3, 4, 30, 40))
    assert gui.montage_from_file(stack) is False
    screen = QApplication.primaryScreen().geometry()
    assert seen["size"].height() < 0.85 * screen.height() - 1      # not 85 % of the screen
    for label in ("Frames along:", "Which frames:", "Panels per row:", "Time between frames:"):
        assert seen["tips"][label], label                         # every option explained
    # Z montage: no time interval / unit / projection-per-time-point fields
    assert {"Time between frames:", "Time unit:", "Z projection of each time point:"} <= set(seen["hidden"])
    assert not {"Time between frames:", "Z projection of each time point:"} & set(seen["hidden_time"])


def test_small_form_dialogs_are_not_full_screen():
    import inspect
    from pyfigures.gui import pfgui
    src = inspect.getsource(pfgui)
    assert "main_widget=frame, options=['Ok', 'Cancel'], parent=self)" not in src
    assert "main_widget=dlg, options=['Ok', 'Cancel'], parent=self)" not in src


# --- letters ---------------------------------------------------------------------

def test_letter_on_its_box_keeps_the_font_colour(tmp_path):
    """White was picked for a dark corner and drawn on the default white box."""
    from batoolset.drawings.shapes.Position import Position
    from pyfigures.gui.pfgui import EZFIG_GUI
    dark = tmp_path / "dark.png"
    from PIL import Image
    Image.fromarray(np.zeros((40, 60), np.uint8)).save(dark)
    panel = SimpleNamespace(img=np.zeros((40, 60), np.uint8), filename=str(dark),
                            custom_loading_script=None, crop_left=0, crop_right=0,
                            crop_top=0, crop_bottom=0, LUTs=None)

    def gui_(bg):
        return SimpleNamespace(serializable_font=SimpleNamespace(
            foreground=0x000000, background=bg, placement=Position("top left")))
    assert EZFIG_GUI._letter_colour_override(gui_(0xFFFFFF), panel) is None   # black on white box
    assert EZFIG_GUI._letter_colour_override(gui_(None), panel) == 0xFFFFFF   # no box: white


def test_one_letter_colour_per_figure_switched_only_where_it_would_vanish():
    from pyfigures.mcp_tools.core import letter_colours
    W, B = 0xFFFFFF, 0x000000
    assert letter_colours([0.1, 0.2, 0.9]) == [W, W, B]        # mostly dark: white, black where bright
    assert letter_colours([0.9, 0.8, 0.1]) == [B, B, W]        # mostly bright: black
    assert letter_colours([0.1, 0.5, None]) == [W, W, W]       # mid grey / unknown: the figure colour
    assert letter_colours([None, None]) == [W, W]
    assert letter_colours([]) == []


def _grey(path, value):
    from PIL import Image
    Image.fromarray(np.full((40, 60), value, np.uint8)).save(path)
    return str(path)


def test_gui_letters_are_plain_and_follow_the_figure_rule(gui, qapp, tmp_path):
    import re
    from batoolset.drawings.shapes.txt2d import TAText2D
    assert gui.serializable_font.background is None               # no box by default
    files = [_grey(tmp_path / "d1.png", 10), _grey(tmp_path / "b.png", 245), _grey(tmp_path / "d2.png", 20)]
    gui.add_images_to_new_row(files)
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 3)
    gui.auto_lettering_checkbox.setChecked(True)
    gui.update_letters()
    found = {}
    for im in _all_images(gui):
        letter = next(a for a in im.annotations if isinstance(a, TAText2D) and a.is_letter)
        assert letter.fill_color is None
        found[os.path.basename(im.filename)] = re.findall(r"color:(#[0-9a-f]{6})", letter.getHtmlText())
    assert found == {"d1.png": ["#ffffff"], "b.png": ["#000000"], "d2.png": ["#ffffff"]}, found


def test_recipe_letters_follow_the_figure_rule(tmp_path, qapp):
    import json
    import re
    import xml.etree.ElementTree as ET
    import pyfigures.mcp_server as M
    _grey(tmp_path / "d1.png", 10)
    _grey(tmp_path / "b.png", 245)
    _grey(tmp_path / "d2.png", 20)
    out = json.loads(M.build_figure_from_recipe(str(tmp_path / "r.yaml"), recipe_text=(
        "output: r.pyf\nrows:\n  - [d1.png, b.png, d2.png]\n")))
    root = ET.parse(out["output"] if "output" in out else str(tmp_path / "r.pyf")).getroot()
    colours = []
    for ta in root.iter("TAText2D"):
        if ta.findtext("is_letter") == "True":
            colours += re.findall(r"color[:=]#([0-9a-f]{6})", ta.findtext("text"))
    assert colours == ["ffffff", "000000", "ffffff"], colours


def test_letters_without_ascender_are_not_lower_than_b(tmp_path, qapp):
    """'a' and 'c' sat lower in the corner than 'b': the line box leaves room
    above letters with no ascender. Their ink top now lines up with b's."""
    from qtpy.QtGui import QImage, QPainter
    from batoolset.drawings.shapes.Position import Position
    from batoolset.drawings.shapes.txt2d import TAText2D

    def ink_top(text, placement="top left"):
        letter = TAText2D(f'<span style="font-family:Arial; font-size:40pt; color:#000000">{text}</span>',
                          placement=Position(placement), is_letter=True)
        img = QImage(200, 200, QImage.Format.Format_RGB32)
        img.fill(0xFFFFFF)
        p = QPainter(img)
        letter.draw(p)
        p.end()
        arr = np.frombuffer(img.constBits().asstring(img.sizeInBytes()), np.uint8).reshape(200, img.bytesPerLine() // 4, 4)
        return int(np.flatnonzero((arr[..., :3].min(axis=2) < 128).any(axis=1))[0])

    b = ink_top("b")
    for t in ("a", "c", "e", "s"):
        assert abs(ink_top(t) - b) <= 1, (t, ink_top(t), b)
    assert abs(ink_top("A") - ink_top("B")) <= 1
    assert b <= 1 and ink_top("a") <= 1        # the ink starts at the top of the letter's box
    # bottom letters sit on the baseline: not moved
    assert ink_top("a", "bottom left") > ink_top("b", "bottom left") + 5


def test_pinned_elements_keep_a_gap_from_the_edge_but_insets_sit_flush(qapp):
    from qtpy.QtGui import QImage, QPainter
    from batoolset.drawings.shapes.Position import Position
    from batoolset.drawings.shapes.image2d import EDGE_MARGIN, Image2D
    from batoolset.drawings.shapes.txt2d import TAText2D
    panel = Image2D(np.zeros((200, 300), np.uint8))
    panel.setTopLeft(10, 20)
    letter = TAText2D("a", placement=Position("top left"), is_letter=True)
    label = TAText2D("label", placement=Position("bottom right"))
    inset = Image2D(np.zeros((40, 60), np.uint8))
    inset.placement = Position("top right")
    inset.fraction_of_parent_image_width_if_image_is_inset = 0.2
    panel.annotations = [letter, label, inset]
    img = QImage(400, 300, QImage.Format.Format_RGB32)
    p = QPainter(img)
    panel.draw(p)
    p.end()
    assert EDGE_MARGIN == 2
    assert (letter.x(), letter.y()) == (10 + 2, 20 + 2)
    assert label.x() + label.width(all=True) == pytest.approx(10 + panel.width(all=True) - 2)
    assert label.y() + label.height(all=True) == pytest.approx(20 + panel.height(all=True) - 2)
    assert inset.y() == 20 and inset.x() + inset.width(all=True) == pytest.approx(10 + panel.width(all=True))


def test_the_tip_bubble_closes_on_a_double_click(gui, qapp):
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest
    gui._edit_hint_shown = False
    gui.edit_hint_action.setChecked(True)
    box = gui._maybe_show_edit_hint()
    assert box.isVisible()
    QTest.mouseDClick(gui.paint, Qt.MouseButton.LeftButton)        # double click on the canvas
    QApplication.processEvents()
    assert not box.isVisible()
    QTest.mouseDClick(gui.paint, Qt.MouseButton.LeftButton)        # the filter is gone: no error
    gui._edit_hint_shown = True


# --- scale bar ---------------------------------------------------------------------

def test_scale_bar_has_no_text_unless_one_is_typed(qapp):
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.gui.scalebareditor import ScaleBarEditor
    ed = ScaleBarEditor(scale_bar=ScaleBar(10, legend=TAText2D("")))
    assert "empty" in ed.text_editor.textEdit.placeholderText()
    assert ed.getScaleBar().legend is None
    ed2 = ScaleBarEditor(scale_bar=ScaleBar(10, legend=TAText2D("10 µm")))
    assert ed2.getScaleBar().legend.getPlainText() == "10 µm"
    import inspect
    from pyfigures.gui import annotation_editor_former_000_TOP_vectorial2 as E
    src = inspect.getsource(E)
    assert "TAText2D('<font color=#FFFFFF>Double click" not in src   # no placeholder legend


# --- image editor: projection only for stacks ------------------------------------------

@pytest.mark.parametrize("kind,projectable", [("plain", False), ("zstack", True)])
def test_editor_offers_projection_only_for_stacks(qapp, tmp_path, kind, projectable):
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.gui.annotation_editor_former_000_TOP_vectorial2 import VectorialDrawPane2, MainWindow
    path = _plain(tmp_path / "p.tif") if kind == "plain" else _stack(tmp_path / "z.tif", "ZYX", (4, 30, 40))
    main = MainWindow(qt_viewer=VectorialDrawPane2(background=Image2D(path)))
    main.update_dimension_sliders()
    assert main.image_projection_box.isVisibleTo(main) is projectable
    assert main.image_dimension_browser_toolbox.isVisibleTo(main) is projectable
    if projectable:
        # projecting the only extra axis leaves no slider: the box goes away
        # instead of being squeezed into an odd empty shape
        main.projection_combo_box.setCurrentIndex(main.projection_combo_box.findData("max"))
        assert not main.image_dimension_browser_toolbox.isVisibleTo(main)
        main.projection_combo_box.setCurrentIndex(0)
        assert main.image_dimension_browser_toolbox.isVisibleTo(main)
    main.close()


# --- 'Match first image' greyed out when nothing would change ------------------------------

def test_force_same_size_is_greyed_out_when_already_the_case(gui, qapp, tmp_path):
    a, b = _plain(tmp_path / "a.tif"), _plain(tmp_path / "b.tif")
    gui.add_images_to_new_row([a, b])
    _wait(qapp, gui, lambda: len(_all_images(gui)) == 2)
    panel = gui.paint.EZFIG_panel
    row = panel.shapes_to_draw[-1]
    panel.selected_shape = row
    assert {"size", "ratio", "crop"} <= panel._already_matching()
    _all_images(gui)[1].crop_left = 10
    panel.selected_shape = row
    assert not {"size", "crop"} & panel._already_matching()


# --- rulers span the whole visible canvas, not just the figure (~400 px at start) ----------

def test_the_canvas_and_its_rulers_fill_the_visible_area(gui, qapp):
    area = gui.paint.scrollArea
    canvas = gui.paint.EZFIG_panel
    gui.resize(1400, 1000)
    gui.show()
    qapp.processEvents()
    vp = area.viewport().size()
    assert vp.width() > 600 and vp.height() > 500
    assert canvas.width() >= vp.width() and canvas.height() >= vp.height()
    # exactly the visible area: no scroll bar for an empty figure
    assert not area.horizontalScrollBar().isVisible() and not area.verticalScrollBar().isVisible()
    gui.resize(1700, 1200)                  # follows the window
    qapp.processEvents()
    assert canvas.width() >= area.viewport().width() > vp.width()
