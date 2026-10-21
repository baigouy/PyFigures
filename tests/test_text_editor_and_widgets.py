"""The rich-text editor used for every label/text annotation, the canvas zoom
controls, and every small dialog widget of the editor (lettering, scale bar,
LUTs, inset, page limits, panel grid, empty image, spacing, translation,
font, background colour, tips, colour assistant).

Each control is operated like a user would (click, type, pick) and the value
the dialog hands back to the editor is checked.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from qtpy.QtWidgets import QColorDialog, QDialog, QFontDialog, QToolButton


@pytest.fixture
def dialogs(monkeypatch):
    st = {"color": QColor(12, 34, 56), "font": QFont("Courier New", 17)}
    monkeypatch.setattr(QColorDialog, "exec_", lambda self: QDialog.Accepted, raising=False)
    monkeypatch.setattr(QColorDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(QColorDialog, "selectedColor", lambda self: st["color"])
    monkeypatch.setattr(QColorDialog, "currentColor", lambda self: st["color"])
    monkeypatch.setattr(QColorDialog, "show", lambda self: None)
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: st["color"]))
    monkeypatch.setattr(QFontDialog, "exec_", lambda self: QDialog.Accepted, raising=False)
    monkeypatch.setattr(QFontDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(QFontDialog, "selectedFont", lambda self: st["font"])
    monkeypatch.setattr(QFontDialog, "getFont", staticmethod(lambda *a, **k: (st["font"], True)))
    return st


# ---------------------------------------------------------------------------
# rich-text editor
# ---------------------------------------------------------------------------

@pytest.fixture
def editor(qapp, dialogs):
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.gui.simple_text_editor import TextEditor
    t = TAText2D("Hello world", placement=None)
    ed = TextEditor(t, show_position=True, show_text_orientation=True, show_range=True)
    return ed, t


def _fmt(ed, pos=2):
    c = QTextCursor(ed.textDocument)
    c.setPosition(pos)
    c.setPosition(pos + 1, QTextCursor.KeepAnchor)
    return c.charFormat()


@pytest.mark.parametrize("action,check", [
    ("boldAction", lambda f: f.fontWeight() == QFont.Bold),
    ("italicAction", lambda f: f.fontItalic()),
    ("underlineAction", lambda f: f.fontUnderline()),
    ("superscriptAction", lambda f: f.verticalAlignment() == QTextCharFormat.AlignSuperScript),
    ("subcriptAction", lambda f: f.verticalAlignment() == QTextCharFormat.AlignSubScript),
])
def test_format_buttons_toggle_on_and_off(editor, action, check):
    ed, t = editor
    getattr(ed, action).trigger()              # no selection: applies to all the text
    assert check(_fmt(ed)), action
    assert check(_fmt(ed, 8)), action
    getattr(ed, action).trigger()
    assert not check(_fmt(ed)), f"{action} could not be switched off"


def test_format_applies_to_selection_only(editor):
    ed, _t = editor
    c = ed.textEdit.textCursor()
    c.setPosition(0)
    c.setPosition(5, QTextCursor.KeepAnchor)       # "Hello"
    ed.textEdit.setTextCursor(c)
    ed.boldAction.trigger()
    assert _fmt(ed, 1).fontWeight() == QFont.Bold
    assert _fmt(ed, 8).fontWeight() != QFont.Bold
    sel = ed.textEdit.textCursor()
    assert (sel.selectionStart(), sel.selectionEnd()) == (0, 5)     # selection kept


def test_font_size_spinner_and_font_dialog(editor, dialogs):
    ed, _t = editor
    ed.fontSizeSpinner.setValue(23)
    assert _fmt(ed).fontPointSize() == 23
    ed.fontAction.trigger()
    f = _fmt(ed)
    assert f.fontFamilies() and f.fontFamilies()[0] == "Courier New" if hasattr(f, "fontFamilies") \
        else f.fontFamily() == "Courier New"
    assert f.fontPointSize() == 17


def test_colours(editor, dialogs):
    ed, t = editor
    ed.fgColorAction.trigger()
    assert _fmt(ed).foreground().color() == QColor(12, 34, 56)
    dialogs["color"] = QColor(250, 240, 10)
    ed.bgColorAction.trigger()
    assert t.fill_color == 0xFAF00A


def test_typing_updates_the_annotation(editor):
    ed, t = editor
    ed.textEdit.selectAll()
    ed.textEdit.insertPlainText("10 µm")
    assert "10 µm" in t.getPlainText()


def test_greek_letter_menu_inserts(editor):
    ed, t = editor
    btn = next(b for b in ed.findChildren(QToolButton) if b.menu() is not None and b.menu().title() == "µ")
    acts = [a for a in btn.menu().actions() if a.text()]
    assert len(acts) >= 30                          # lower + distinct upper-case Greek + µ
    ed.textEdit.moveCursor(QTextCursor.End)
    alpha = next(a for a in acts if a.text() == "α")
    alpha.trigger()
    assert t.getPlainText().endswith("α")


def test_position_and_orientation(qapp, dialogs):
    # the position combos exist for a text placed on a panel (letters,
    # labels) — not for a free-floating one
    from batoolset.drawings.shapes.txt2d import TAText2D
    from batoolset.drawings.shapes.Position import Position
    from pyfigures.gui.simple_text_editor import TextEditor
    t = TAText2D("A", placement=Position("top-left"))
    ed = TextEditor(t, show_position=True, show_text_orientation=True)
    assert ed.vertical_combo.currentText() == "Top" and ed.horizontal_combo.currentText() == "Left"
    ed.vertical_combo.setCurrentText("Bottom")
    ed.horizontal_combo.setCurrentText("Right")
    pos = t.placement.position_to_string().lower()
    assert "bottom" in pos and "right" in pos
    ed.text_orientation_combo.setCurrentIndex(ed.text_orientation_combo.count() - 1)
    assert t.text_orientation == ed.text_orientation_combo.currentText()
    floating = TextEditor(TAText2D("x", placement=None), show_position=True)
    assert not hasattr(floating, "vertical_combo")


def test_range_spinners_stay_ordered(editor):
    ed, t = editor
    ed.end_position_spinner.setValue(1)
    ed.begin_position_spinner.setValue(3)          # start past end: end follows
    assert ed.end_position_spinner.value() == 3 and t.range == [3, 3]
    ed.end_position_spinner.setValue(2)            # end before start: start follows
    assert ed.begin_position_spinner.value() == 2 and t.range == [2, 2]


# ---------------------------------------------------------------------------
# zoom (scrollable canvas)
# ---------------------------------------------------------------------------

@pytest.fixture
def gui(qapp, monkeypatch):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.resize(1000, 700)
    g.show()
    yield g
    g._dirty = False
    g.close()


def test_zoom_in_out_reset_and_fit(gui, tmp_path):
    import numpy as np
    from batoolset.img import Img
    from batoolset.drawings.shapes.image2d import Image2D
    p = str(tmp_path / "a.tif")
    Img(np.full((200, 300), 90, np.uint8), dimensions="hw").save(p)
    view = gui.paint
    panel = view.EZFIG_panel
    for fit in (view.fit_to_width, view.fit_to_height, view.fit_to_window, view.fit_to_width_or_height):
        fit()                                        # empty canvas: no ZeroDivisionError
    panel.shapes_to_draw.append(Image2D(p))
    panel.update_size()
    view.zoom_reset()
    assert panel.scale == 1.0
    view.zoomIn()
    assert panel.scale == pytest.approx(1.1)
    view.zoomOut()
    assert panel.scale == pytest.approx(0.99)
    for _ in range(100):
        view.zoomOut()
    assert panel.scale >= 0.01                       # clamped, never 0 or negative
    view.fit_to_width()
    w = view.scrollArea.width() - 2 - view.scrollArea.verticalScrollBar().sizeHint().width()
    assert panel.updateBounds().width() * panel.scale == pytest.approx(w, abs=1)
    view.fit_to_width_or_height()
    view.fit_to_width_or_height()
    view.fit_to_window()
    assert panel.scale > 0


def test_click_outside_canvas_deselects(gui, tmp_path):
    import numpy as np
    from batoolset.img import Img
    from batoolset.drawings.shapes.image2d import Image2D
    p = str(tmp_path / "a.tif")
    Img(np.full((50, 50), 90, np.uint8), dimensions="hw").save(p)
    panel = gui.paint.EZFIG_panel
    im = Image2D(p)
    panel.shapes_to_draw.append(im)
    panel.set_current_selection(im)
    gui.paint.handle_mouse_click_outside_drawing_panel()
    assert not panel.selected_shape


# ---------------------------------------------------------------------------
# small dialog widgets
# ---------------------------------------------------------------------------

def test_auto_lettering_options_round_trip(qapp, dialogs):
    from batoolset.drawings.shapes.serializablefont import SerializableQFont
    from batoolset.drawings.shapes.Position import Position
    from pyfigures.gui.autolettering_widget import AutoLetteringOptions
    w = AutoLetteringOptions()
    w.bg_color_button.click()
    dialogs["color"] = QColor(255, 255, 0)
    w.fg_color_button.click()
    w.font_button.click()
    w.vertical_combo.setCurrentText("Bottom")
    w.horizontal_combo.setCurrentText("Right")
    f = w.get_serializable_font()
    assert f.background & 0xFFFFFF == 0x0C2238 and f.foreground & 0xFFFFFF == 0xFFFF00
    assert f.family() == "Courier New"
    assert "bottom" in f.placement.position_to_string().lower()
    assert w.get_options()["font_size"] == 17
    w.bg_color_check.setChecked(False)
    assert not w.bg_color_button.isEnabled() and w.get_bg_color() is None
    # reopening on a saved font shows it (and used to crash on its placement)
    saved = SerializableQFont("Arial", 9, foreground=0x00FF00, background=None, placement=Position("bottom-right"))
    w2 = AutoLetteringOptions(font=saved)
    assert not w2.bg_color_check.isChecked()
    assert w2.vertical_combo.currentText() == "Bottom" and w2.horizontal_combo.currentText() == "Right"
    assert w2.get_fg_color() & 0xFFFFFF == 0x00FF00


def test_lettering_dialog_starts_from_current_font(qapp, monkeypatch):
    from batoolset.GUI.customdialog import CustomDialog
    from batoolset.drawings.shapes.serializablefont import SerializableQFont
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.serializable_font = SerializableQFont("Arial", 21, foreground=0xFF0000)
    seen = {}

    def accept(self, *a, **k):
        seen["size"] = self.main_widget.get_font().pointSize()
        return QDialog.Accepted
    monkeypatch.setattr(CustomDialog, "exec_", accept, raising=False)
    monkeypatch.setattr(CustomDialog, "exec", accept)
    g.change_lettering_parameters()
    assert seen["size"] == 21
    assert g.serializable_font.foreground & 0xFFFFFF == 0xFF0000
    g._dirty = False
    g.close()


def test_scale_bar_editor_with_and_without_bar(qapp):
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.gui.scalebareditor import ScaleBarEditor
    ed = ScaleBarEditor(scale_bar=None)                 # used to raise AttributeError
    ed.size_spinner.setValue(25)
    ed.vertical_combo.setCurrentText("Top")
    ed.horizontal_combo.setCurrentText("Left")
    sb = ed.getScaleBar()
    assert sb.bar_width_in_units == 25 and "top" in sb.placement.position_to_string().lower()
    bar = ScaleBar(10, TAText2D("10 µm"))
    ed2 = ScaleBarEditor(scale_bar=bar)
    assert ed2.size_spinner.value() == 10
    ed2.size_spinner.setValue(50)
    ed2.check_box.setChecked(False)
    assert ed2.text_editor.isHidden()
    out = ed2.getScaleBar()
    assert out is bar and out.bar_width_in_units == 50 and out.legend is None


def test_lut_widget(qapp):
    from pyfigures.gui.lutmultiselector import LutWidget
    w = LutWidget(3, user_specified_luts=[None, None, "DNA"])
    luts = w.getAllLuts()
    assert luts[:2] == [None, None] and luts[2] and luts[2].lower() == "dna"
    w.all_LUTs[0].setCurrentIndex(1)                  # updates the preview strip too
    assert w.getAllLuts()[0] == w.all_LUTs[0].currentText()
    assert not w.label.pixmap().isNull()


def test_inset_widget(qapp, dialogs):
    from pyfigures.gui.widget_for_inset import InsetWidget
    w = InsetWidget()
    w.percentage_spinner.setValue(0.4)
    w.border_spinner.setValue(5)
    w.color_button.click()
    v = w.get_values()
    assert v["percentage"] == pytest.approx(0.4) and v["border_size"] == 5
    assert v["color"] == QColor(12, 34, 56)
    w.border_spinner.setValue(0)
    assert w.get_values()["color"] is None


def test_page_limits_widget_units(qapp):
    from pyfigures.gui.pagelimitswidget import PageLimitsWidget
    w = PageLimitsWidget()
    px_cm = w.get_values()
    w.unit_combobox.setCurrentText("inches")
    assert w.width_spinbox.suffix() == " in" and w.width_spinbox.value() == pytest.approx(21 / 2.54, abs=0.01)
    px_in = w.get_values()
    assert px_in[0] == pytest.approx(px_cm[0], rel=0.01)    # same page, other unit
    w.unit_combobox.setCurrentText("cm")
    assert w.width_spinbox.value() == pytest.approx(21.0, abs=0.02)


@pytest.mark.parametrize("n,rows,cols", [(10, 2, 5), (7, 3, 3), (1, 1, 1)])
def test_panel_creator_fills_the_other_dimension(qapp, n, rows, cols):
    from pyfigures.gui.panelcreationwidget import PanelCreator
    w = PanelCreator(None, n)
    w.num_rows.setValue(rows)
    v = w.get_values()
    assert v["num_cols"] == cols and v["num_rows"] * v["num_cols"] >= n
    w.col_radio.setChecked(True)
    w.num_cols.setValue(cols)
    assert w.get_values()["num_rows"] * cols >= n
    w.order_radio_top_down.setChecked(True)
    assert w.get_values()["order"] == "Y"


def test_single_or_panel_toggle(qapp):
    from pyfigures.gui.asingleoraspanel import AsSingleOrPanel
    w = AsSingleOrPanel(num_widgets=4)
    w.check_box.setChecked(True)
    assert w.is_checkbox_selected() and not w.panel_creator.isEnabled()
    w.check_box.setChecked(False)
    assert w.panel_creator.isEnabled()


def test_simple_value_widgets(qapp, dialogs):
    from pyfigures.gui.emptyimagedialog import EmptyImageParametersWidget
    from pyfigures.gui.user_extra_translation import ExtraTranslationWidget
    from pyfigures.gui.spaceselector import SpaceSelectorWidget
    from pyfigures.gui.dimchooser import DimensionChooser
    from pyfigures.gui.group_builder_GUI import PanelOrRow
    from pyfigures.gui.fontselectorgui import FontSelector
    from pyfigures.gui.bg_color_selection import BackgroundColorPicker
    e = EmptyImageParametersWidget()
    e.width_spinbox.setValue(300)
    e.height_spinbox.setValue(150)
    assert e.get_parameters() == (300, 150) and e.aspect_ratio_label.text() == "AR: 2.000"
    t = ExtraTranslationWidget()
    t.dx_spinbox.setValue(-7)
    t.dy_spinbox.setValue(12)
    assert t.get_translation() == (-7, 12)
    s = SpaceSelectorWidget()
    s.spinbox.setValue(8)
    s.apply_to_page.setChecked(True)
    assert (s.get_space_value(), s.is_apply_to_page_checked()) == (8, True)
    d = DimensionChooser("dhwc")
    d.combo_box.setCurrentIndex(1)
    assert d.get_current_dimension() == "h"
    r = PanelOrRow()
    r.orientation_combo.setCurrentText("Y")
    r.space_spinbox.setValue(11)
    assert r.get_parameters() == ("Y", 512, 11)
    f = FontSelector()
    f.font_button.click()
    assert f.get_font().family() == "Courier New" and f.get_font().pointSize() != 17   # size kept by default
    f.keep_original_size.setChecked(False)
    assert f.get_font().pointSize() == 17
    b = BackgroundColorPicker()
    b.color_button.click()
    assert b.get_color() == 0x0C2238
    b.reset_button.click()
    assert b.get_color() is None


def test_tip_dialog_navigation(qapp):
    from pyfigures.gui.tipdialog import TipDialog
    from pyfigures.gui import user_prefs
    tips = ["one", "two", "three"]
    d = TipDialog(None, tips)
    assert "one" in d.tip_text_edit.toPlainText()
    d.next_button.click()
    assert "two" in d.tip_text_edit.toPlainText() and not d.auto_show_checkbox.isChecked()
    d.previous_button.click()
    d.previous_button.click()
    assert "three" in d.tip_text_edit.toPlainText()      # wraps around
    d.show_random_tip()
    assert d.tip_text_edit.toPlainText() in ("two", "three")
    d.auto_show_checkbox.setChecked(True)
    assert user_prefs.load_auto_show_tips() is True and d.auto_show_timer.isActive()
    d.auto_show_checkbox.setChecked(False)
    assert user_prefs.load_auto_show_tips() is False and not d.auto_show_timer.isActive()
    TipDialog(None, ["only one"]).show_random_tip()      # used to raise ValueError
    TipDialog(None, [])                                   # no tips: closes quietly


def test_colour_assistant_uses_no_real_screen(qapp):
    from pyfigures.gui.colorassistant import ColorAssistant
    w = ColorAssistant(capture_width=32, capture_height=16)
    w.resize(64, 96)
    w.update_pixel_color()
    pm = w._label_red.pixmap()
    assert pm is not None and not pm.isNull()
    img = pm.toImage()
    assert img.pixelColor(img.width() // 2, img.height() // 2).red() == 200   # the synthetic patch's red
    w.close()
