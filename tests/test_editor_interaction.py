"""Image editor mouse editing (user findings 2026-11-04): line ends dragged
by handles, Ctrl+Z, zoom, the crop rectangle dragged with the mouse, the
editor opening on its drawing tools, and the bracket button no longer hiding
the arrowhead button."""
from __future__ import annotations

import pytest
from qtpy.QtCore import QLineF, QPointF, Qt
from qtpy.QtWidgets import QApplication, QPushButton, QShortcut

from test_panel_editor import ui, fig, edit, draw, tool, _mouse  # noqa: F401  (fixtures)
from pyfigures.gui import editor_interaction as EI


def _drag(ed, a, b, steps=4):
    draw(ed, a[0], a[1], b[0], b[1], steps=steps)
    for _ in range(2):
        QApplication.processEvents()      # the undo step is recorded after the release


def _lines(ed):
    from batoolset.drawings.shapes.line2d import Line2D
    return [s for s in ed.qt_viewer.shapes if isinstance(s, Line2D)]


# -- pure helpers --------------------------------------------------------------
def test_line_handles_grab_the_nearest_end_only_near_it():
    line = QLineF(10, 10, 100, 50)
    assert EI.line_handle_at(line, QPointF(12, 11), 1.0) == 1
    assert EI.line_handle_at(line, QPointF(98, 49), 1.0) == 2
    assert EI.line_handle_at(line, QPointF(55, 30), 1.0) is None
    # the grab distance is in screen pixels: zoomed out 10x it is 70 image px
    assert EI.line_handle_at(line, QPointF(25, 15), 1.0) is None
    assert EI.line_handle_at(line, QPointF(25, 15), 0.1) == 1


def test_crop_drag_by_side_corner_and_inside():
    crops = (0, 0, 0, 0)
    assert EI.crop_hit(QPointF(1, 50), 200, 100, 0, crops, 1.0) == ('left',)
    assert EI.crop_hit(QPointF(199, 99), 200, 100, 0, crops, 1.0) == ('right', 'bottom')
    assert EI.crop_hit(QPointF(100, 50), 200, 100, 0, crops, 1.0) == ('move',)
    assert EI.crop_hit(QPointF(300, 50), 200, 100, 0, crops, 1.0) is None
    assert EI.drag_crops(('left',), crops, QPointF(0, 50), QPointF(30, 60), 200, 100, 0) == (30, 0, 0, 0)
    assert EI.drag_crops(('right', 'bottom'), crops, QPointF(200, 100), QPointF(150, 80), 200, 100, 0) == (0, 50, 0, 20)
    # inside: the rectangle keeps its size and stays in the image
    assert EI.drag_crops(('move',), (20, 30, 10, 10), QPointF(100, 50), QPointF(80, 40), 200, 100, 0) == (0, 50, 0, 20)
    # a side stops before crossing the other one
    l, r, t, b = EI.drag_crops(('left',), (0, 50, 0, 0), QPointF(0, 50), QPointF(500, 50), 200, 100, 0)
    assert l + r <= 200 and l > 0


def test_editor_tab_words_any_spelling():
    from pyfigures.assistant.gui_selection import editor_tab
    assert editor_tab('rotate_crop') == 'Rotate + Crop'
    assert editor_tab('annotations') == 'Annotations'
    assert editor_tab('ROTATE+CROP') == 'Rotate + Crop'


# -- in the editor ---------------------------------------------------------------
def test_editor_opens_on_the_drawing_tools(fig, ui):
    seen = {}

    def do(ed):
        seen['tab'] = ed.tab_widget.tabText(ed.tab_widget.currentIndex())
    edit(fig, ui, "gray", do, accept=False)
    assert seen['tab'] == 'Annotations'


def test_line_end_drag_middle_moves_and_undo(fig, ui):
    out = {}

    def do(ed):
        tool(ed, "Line")
        _drag(ed, (20, 20), (120, 80))
        line = _lines(ed)[0]
        assert ed.qt_viewer.selected_shape == [line]
        # an end: only that end moves
        _drag(ed, (120, 80), (150, 150))
        assert (line.p1().x(), line.p1().y()) == pytest.approx((20, 20), abs=1)
        assert (line.p2().x(), line.p2().y()) == pytest.approx((150, 150), abs=1)
        # the middle: the whole line moves
        _drag(ed, (85, 85), (95, 95))
        assert (line.p1().x(), line.p1().y()) == pytest.approx((30, 30), abs=1)
        # Ctrl+Z, step by step: the move, the end drag, the drawing
        assert ed.undo()
        assert (line.p1().x(), line.p1().y()) == pytest.approx((20, 20), abs=1)
        assert ed.undo()
        assert (line.p2().x(), line.p2().y()) == pytest.approx((120, 80), abs=1)
        assert ed.undo()
        out['lines_after_undo'] = len(_lines(ed))
    edit(fig, ui, "gray", do, accept=False)
    assert out['lines_after_undo'] == 0


def test_delete_can_be_undone(fig, ui):
    out = {}

    def do(ed):
        tool(ed, "Rectangle")
        _drag(ed, (20, 20), (120, 90))
        n = len(ed.qt_viewer.shapes)
        ed.down()                        # the Delete key
        assert len(ed.qt_viewer.shapes) == n - 1
        assert ed.undo()
        out['n'] = (n, len(ed.qt_viewer.shapes), len(ed.qt_viewer.background.annotations))
    edit(fig, ui, "gray", do, accept=False)
    n, now, annotations = out['n']
    assert now == n and annotations == n


def test_crop_rectangle_dragged_with_the_mouse(fig, ui):
    def do(ed):
        assert ed.open_tab('rotate + crop')
        assert ed.qt_viewer.crop_controller is ed
        _drag(ed, (1, 100), (40, 100))                  # the left side
        assert ed.current_crops()[0] == pytest.approx(40, abs=1)
        _drag(ed, (299, 199), (280, 170))               # the bottom-right corner
        l, r, t, b = ed.current_crops()
        assert r == pytest.approx(20, abs=1) and b == pytest.approx(30, abs=1)
        _drag(ed, (150, 80), (140, 70))                 # inside: moves, same size
        # (the top is already 0: the rectangle only moves left)
        assert ed.current_crops() == pytest.approx((30, 30, 0, 30), abs=1)
        assert ed.undo()                                # Ctrl+Z undoes the move
        assert ed.current_crops() == pytest.approx((40, 20, 0, 30), abs=1)
        ed.open_tab('Annotations')
        assert ed.qt_viewer.crop_controller is None     # clicks select shapes again
    img = edit(fig, ui, "gray", do)
    assert (img.crop_left, img.crop_right, img.crop_top, img.crop_bottom) == pytest.approx((40, 20, 0, 30), abs=1)


def test_zoom_steps_multiply_and_fit_shows_the_whole_image(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        v.set_scale(1.0)
        v.zoom_in()
        assert v.scale == pytest.approx(1.25)
        v.zoom_out()
        v.zoom_out()
        assert v.scale == pytest.approx(0.8)
        assert ed.zoom_label.text() == '80 %'
        ed.scrollArea.viewport().resize(160, 120)
        ed.fit_whole()
        assert v.scale < 0.6                            # 300 x 200 image in a ~150 px view
        assert v.min_scaling_factor <= 0.01
    edit(fig, ui, "gray", do, accept=False)


def test_zoom_buttons_above_the_image(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        assert set(ed.zoom_buttons) == {'in', 'out', 'fit', '100'}
        assert not ed.zoom_buttons['in'].icon().isNull()
        v.set_scale(1.0)
        ed.zoom_buttons['in'].click()
        assert v.scale == pytest.approx(1.25)
        ed.zoom_buttons['out'].click()
        ed.zoom_buttons['out'].click()
        assert v.scale == pytest.approx(0.8)
        ed.zoom_buttons['100'].click()
        assert v.scale == pytest.approx(1.0)
        assert ed.zoom_label.text() == '100 %'
        ed.scrollArea.viewport().resize(160, 120)
        ed.zoom_buttons['fit'].click()
        assert v.scale < 0.6
    edit(fig, ui, "gray", do, accept=False)


def test_bracket_button_does_not_cover_the_arrowhead_button(fig, ui):
    def do(ed):
        buttons = ed.findChildren(QPushButton)
        bracket = next(b for b in buttons if b.text() == 'Significance (*)')
        head = next(b for b in buttons if b.toolTip().startswith('Arrowhead only'))
        layout = bracket.parentWidget().layout()
        cells = {}
        for w in (bracket, head):
            r, c, rs, cs = layout.getItemPosition(layout.indexOf(w))
            cells[w] = {(r + i, c + j) for i in range(rs) for j in range(cs)}
        assert not (cells[bracket] & cells[head])
    edit(fig, ui, "gray", do, accept=False)


def test_figure_shortcuts_stay_in_the_figure_window(fig):
    """Application-wide Ctrl+Z / Delete / Ctrl +/- reached the image editor
    dialog too: they edited the figure behind it, or clashed with the
    editor's own keys so neither ran."""
    wide = [s.key().toString() for s in fig.findChildren(QShortcut)
            if s.context() == Qt.ShortcutContext.ApplicationShortcut]
    assert wide == []
