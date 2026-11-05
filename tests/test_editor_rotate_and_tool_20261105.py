"""User reports 2026-11-05 on the panel editor.
- Rotate + Crop: at an angle with no crop only the crop handles turned; the
  outline stayed on the upright image. The rotated frame is now drawn and the
  view moves so its top / left part is on screen too.
- Opened by the chat to move an ROI, a click that missed drew a new rectangle:
  opened by the chat, the editor has no drawing tool on."""
from qtpy.QtCore import QEvent, QPointF, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QTabWidget

from test_panel_editor import fig, ui, edit, _get  # noqa: F401


def _to_tab(ed, title):
    for t in ed.findChildren(QTabWidget):
        for i in range(t.count()):
            if t.tabText(i) == title:
                t.setCurrentIndex(i)


def _mouse(v, kind, image_point):
    pos = (image_point + v.view_origin) * v.scale
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease}[kind]
    btn = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.NoButton if kind == "release" else Qt.MouseButton.LeftButton
    ev = QMouseEvent(t, pos, v.mapToGlobal(pos), btn, held, Qt.KeyboardModifier.NoModifier)
    {"press": v.mousePressEvent, "move": v.mouseMoveEvent, "release": v.mouseReleaseEvent}[kind](ev)


def test_a_rotation_alone_draws_the_whole_rotated_frame(fig, ui):
    seen = {}

    def do(ed):
        _to_tab(ed, "Rotate + Crop")
        v = ed.qt_viewer
        assert v.rotate_n_crop_lines is None and v.view_origin == QPointF(0, 0)
        ed.rotate_image_spinbox.setValue(30)
        seen["lines"] = v.rotate_n_crop_lines
        seen["origin"] = QPointF(v.view_origin)
        origin, corner = v.frame_extent()
        seen["fits"] = (v.minimumWidth() >= (corner.x() + origin.x()) * v.scale - 1
                        and v.minimumHeight() >= (corner.y() + origin.y()) * v.scale - 1)
        # the mouse still lands on the right image pixel
        ev = QMouseEvent(QEvent.Type.MouseMove, (QPointF(50, 60) + v.view_origin) * v.scale, Qt.MouseButton.NoButton,
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        p = v._image_point(ev)
        seen["point"] = (round(p.x(), 6), round(p.y(), 6))
        ed.rotate_image_spinbox.setValue(0)
        seen["back"] = QPointF(v.view_origin)
    edit(fig, ui, "rgb", do, accept=False)
    assert seen["lines"] is not None                           # the rotated frame is drawn
    assert seen["origin"].x() > 0 and seen["origin"].y() > 0   # its top-left part is on screen
    assert seen["fits"] and seen["point"] == (50, 60)
    assert seen["back"] == QPointF(0, 0)


def test_opened_by_the_chat_a_click_selects_and_never_draws(fig, ui):
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    g = fig
    panel = _get(g, "gray")
    panel.annotations = [Rectangle2D(100, 50, 60, 40, stroke=2, color=0xFFFF00)]
    seen = {}

    def do(ed):
        v = ed.qt_viewer
        seen["tool"] = v.shape_to_draw
        n = len(v.shapes)
        for kind, p in (("press", QPointF(20, 150)), ("move", QPointF(60, 180)), ("release", QPointF(60, 180))):
            _mouse(v, kind, p)                                 # a drag that misses everything
        seen["drawn"] = len(v.shapes) - n
        _mouse(v, "press", QPointF(130, 70))                   # inside the ROI
        seen["selected"] = [type(s).__name__ for s in v.selected_shape]
        _mouse(v, "release", QPointF(130, 70))
    ui["edit"] = do
    ui["accept"] = False
    g.paint.EZFIG_panel.update_image_annotations(image2d=panel, draw_tool=False)
    assert seen == {"tool": None, "drawn": 0, "selected": ["Rectangle2D"]}


def test_a_double_click_still_opens_with_the_rectangle_tool(fig, ui):
    seen = {}
    edit(fig, ui, "gray", lambda ed: seen.setdefault("tool", ed.qt_viewer.shape_to_draw), accept=False)
    assert seen["tool"] is not None
