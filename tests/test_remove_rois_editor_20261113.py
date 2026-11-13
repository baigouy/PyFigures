"""The panel editor's Remove all ROIs button (2026-11-13): every rectangle, ellipse and
polygon of the image in one click, lines and texts kept, Ctrl+Z puts them back."""
from __future__ import annotations

from qtpy.QtWidgets import QApplication

from test_panel_editor import ui, fig, edit, draw, tool, _mouse  # noqa: F401  (fixtures)


def _kinds(ed):
    return [type(s).__name__ for s in ed.qt_viewer.shapes]


def test_arrow_keys_nudge_the_selection(fig, ui):
    """The GUI side of move_annotations: arrow keys move the selected shapes by
    1 px, Shift+arrow by 10 px; Ctrl+Z puts them back."""
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest
    out = {}

    def do(ed):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        rect = Rectangle2D(10, 10, 30, 30)
        ed.update_annotations_list(lst=list(ed.qt_viewer.shapes) + [rect], update=True, repopulate_list=True,
                                   repopulate_texts=True)
        ed.qt_viewer.selected_shape = [rect]
        ed.qt_viewer.setFocus()
        QApplication.processEvents()
        QTest.keyClick(ed.qt_viewer, Qt.Key.Key_Right)
        QTest.keyClick(ed.qt_viewer, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
        out['moved'] = (rect.x(), rect.y())
        assert ed.qt_viewer.undo()
        out['undone'] = (rect.x(), rect.y())
    edit(fig, ui, "gray", do, accept=False)
    assert out['moved'] == (11, 20) and out['undone'] == (11, 10)


def test_remove_all_rois_button_then_undo(fig, ui):
    out = {}

    def do(ed):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        from batoolset.drawings.shapes.ellipse2d import Ellipse2D
        from batoolset.drawings.shapes.circle2d import Circle2D
        from batoolset.drawings.shapes.line2d import Line2D
        shapes = list(ed.qt_viewer.shapes) + [Rectangle2D(10, 10, 30, 30), Ellipse2D(60, 10, 30, 30),
                                              Circle2D(10, 60, 30), Line2D(60, 60, 100, 100)]
        ed.update_annotations_list(lst=shapes, update=True, repopulate_list=True, repopulate_texts=True)
        QApplication.processEvents()
        out['before'] = _kinds(ed)
        ed.removeAllRois.click()
        out['after'] = _kinds(ed)
        assert ed.qt_viewer.undo()
        out['undone'] = _kinds(ed)
        ed.removeAllRois.click()
        ed.removeAllRois.click()                    # nothing left: a message, no crash
    edit(fig, ui, "gray", do, accept=False)
    assert {'Rectangle2D', 'Ellipse2D', 'Circle2D', 'Line2D'} <= set(out['before'])
    assert set(out['after']) & {'Rectangle2D', 'Ellipse2D', 'Circle2D'} == set()
    assert 'Line2D' in out['after']
    assert sorted(out['undone']) == sorted(out['before'])
