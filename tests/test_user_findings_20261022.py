"""Bugs from the user's manual testing of 22 Oct 2026 (chatGPT_validation
handoff): the image editor froze on an arrow, Draw ROIs opened on the wrong
tab.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import sys

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _figure_with_arrow(tmp_path):
    from batoolset.img import Img
    from batoolset.serializations.tools import create_object, deserialize_to_dict
    from pyfigures.mcp_server import create_figure, add_image, add_arrow
    p = str(tmp_path / "a.tif")
    Img((np.random.default_rng(0).random((200, 300)) * 255).astype(np.uint8), dimensions="hw").save(p)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], p)
    add_arrow(pyf, [0], 0, tip_x=150, tip_y=120, label="cell")
    objs = create_object(list.__name__, deserialize_to_dict(open(pyf, encoding="utf-8").read()))
    return [o for o in objs if hasattr(o, "content")][0].content[0]


def test_selecting_an_arrow_from_the_menu_does_not_break_the_editor(qapp, tmp_path, monkeypatch):
    """Annotations → Add arrow… stores float head sizes; selecting the arrow
    in the image editor raised TypeError in a slot (the editor looked frozen,
    the arrow could not be moved)."""
    from qtpy.QtCore import QEvent, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication
    from pyfigures.gui.annotation_editor import VectorialDrawPane2, MainWindow
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda t, v, tb: errors.append(f"{t.__name__}: {v}"))
    bg = _figure_with_arrow(tmp_path)
    arrow = next(a for a in bg.annotations if type(a).__name__ == "Line2D")
    viewer = VectorialDrawPane2(background=bg)
    main = MainWindow(qt_viewer=viewer)
    main.resize(900, 700)
    main.show()
    mid = QPointF((arrow.p1().x() + arrow.p2().x()) / 2, (arrow.p1().y() + arrow.p2().y()) / 2)

    def mouse(kind, pos):
        t = {"press": QEvent.Type.MouseButtonPress, "release": QEvent.Type.MouseButtonRelease,
             "move": QEvent.Type.MouseMove}[kind]
        b = Qt.MouseButton.LeftButton
        QApplication.sendEvent(viewer, QMouseEvent(t, pos, QPointF(viewer.mapToGlobal(pos.toPoint())), b,
                                                   b if kind != "release" else Qt.MouseButton.NoButton,
                                                   Qt.KeyboardModifier.NoModifier))
    before = arrow.p2()
    mouse("press", mid)
    mouse("release", mid)
    mouse("press", mid)
    for i in range(1, 6):
        mouse("move", QPointF(mid.x() + 10 * i, mid.y() + 5 * i))
    mouse("release", QPointF(mid.x() + 50, mid.y() + 25))
    qapp.processEvents()
    assert errors == []
    assert viewer.selected_shape and main.arrow_width_scaler.value() > 0
    assert viewer.selected_shape[0].p2() != before          # it moved
    main.close()


def test_editor_opens_on_the_drawing_tools(qapp, tmp_path):
    from pyfigures.gui.annotation_editor import VectorialDrawPane2, MainWindow
    main = MainWindow(qt_viewer=VectorialDrawPane2(background=_figure_with_arrow(tmp_path)))
    # 2026-11-04: a double click opens on the drawing tools too (the guides said
    # so; it opened on File Infos and the user looked for the line tool)
    assert main.tab_widget.tabText(main.tab_widget.currentIndex()) == "Annotations"
    assert main.open_tab("File Infos + Scale")
    assert main.tab_widget.tabText(main.tab_widget.currentIndex()) == "File Infos + Scale"
    assert not main.open_tab("No such tab")
    main.close()


def _callout(tmp_path):
    from batoolset.img import Img
    from batoolset.serializations.tools import create_object, deserialize_to_dict
    from pyfigures.mcp_server import create_figure, add_image, add_zoom_callout
    p = str(tmp_path / "z.tif")
    Img((np.random.default_rng(1).random((200, 300)) * 255).astype(np.uint8), dimensions="hw").save(p)
    pyf = str(tmp_path / "z.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], p)
    add_zoom_callout(pyf, [0], 0, 40, 120, 40, 40, 300, 200, inset_fraction=0.3)
    objs = create_object(list.__name__, deserialize_to_dict(open(pyf, encoding="utf-8").read()))
    return [o for o in objs if hasattr(o, "content")][0].content[0]


def test_zoom_leaders_follow_the_inset_and_the_box(qapp, tmp_path):
    """Moving a zoom callout's inset left its leader lines behind; moving the
    box left the lines and the magnified region behind."""
    from qtpy.QtCore import QPointF
    from batoolset.drawings.shapes.line2d import Line2D
    from pyfigures.gui.zoom_links import zoom_links, follow_zoom_links
    from pyfigures.gui.annotation_editor import VectorialDrawPane2, MainWindow
    viewer = VectorialDrawPane2(background=_callout(tmp_path))
    main = MainWindow(qt_viewer=viewer)
    main.resize(900, 700)
    main.show()
    viewer.repaint()                              # lays the inset out in its corner
    qapp.processEvents()
    shapes = list(viewer.shapes)
    box, l1, l2, inset = shapes
    assert isinstance(l1, Line2D)
    ends = [(l.p1(), l.p2()) for l in (l1, l2)]
    links = zoom_links(shapes, inset)
    assert len(links) == 2                        # the two leaders, at their inset end
    d = QPointF(-60, 40)
    inset.translate(d)
    follow_zoom_links(links, d)
    assert l1.p1() == ends[0][0] and l1.p2() == ends[0][1] + d     # box end kept, inset end moved
    # moving the box: leader box ends and the inset crop follow
    crop = (inset.crop_left, inset.crop_top)
    links = zoom_links(shapes, box)
    assert ("crop", (inset, box)) in links and len(links) == 3
    d = QPointF(10, -20)
    box.translate(d)
    follow_zoom_links(links, d)
    assert (inset.crop_left, inset.crop_top) == (crop[0] + 10, crop[1] - 20)
    assert l1.p1() == ends[0][0] + d
    # a plain rectangle / line is linked to nothing
    assert zoom_links(shapes, l1) == []
    main.close()


def test_zoom_leaders_follow_a_drag_in_the_editor(qapp, tmp_path):
    from qtpy.QtCore import QEvent, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication
    from pyfigures.gui.annotation_editor import VectorialDrawPane2, MainWindow
    viewer = VectorialDrawPane2(background=_callout(tmp_path))
    main = MainWindow(qt_viewer=viewer)
    main.resize(900, 700)
    main.show()
    viewer.repaint()
    qapp.processEvents()
    box, l1, l2, inset = viewer.shapes
    before = l1.p2()
    viewer.selected_shape = [inset]
    start = QPointF(255 * viewer.scale, 45 * viewer.scale)      # inside the shown inset

    def mouse(kind, pos):
        t = {"press": QEvent.Type.MouseButtonPress, "release": QEvent.Type.MouseButtonRelease,
             "move": QEvent.Type.MouseMove}[kind]
        b = Qt.MouseButton.LeftButton
        QApplication.sendEvent(viewer, QMouseEvent(t, pos, QPointF(viewer.mapToGlobal(pos.toPoint())), b,
                                                   b if kind != "release" else Qt.MouseButton.NoButton,
                                                   Qt.KeyboardModifier.NoModifier))
    mouse("press", start)
    for i in range(1, 5):
        mouse("move", QPointF(start.x() - 10 * i, start.y() + 10 * i))
    mouse("release", QPointF(start.x() - 40, start.y() + 40))
    moved = l1.p2() - before
    assert abs(moved.x() + 40 / viewer.scale) < 1.5 and abs(moved.y() - 40 / viewer.scale) < 1.5, moved
    main.close()


def test_an_empty_annotations_element_reads_back_as_a_list(qapp, tmp_path):
    """Flagged by the sidecar prototype: a panel whose last annotation was
    removed saved <annotations/>, read back as '' — automatic lettering then
    called ''.insert and failed."""
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.serializations.tools import create_object, deserialize_to_dict, object_to_xml
    img = Image2D(width=30, height=20)
    img.annotations = []
    back = create_object(list.__name__, deserialize_to_dict(object_to_xml([img], is_list=True)))[0]
    assert back.annotations == []
    for text in ("", "[]", "None"):
        assert Image2D(width=3, height=2, annotations=text).annotations == []


def test_draw_rois_menu_asks_for_the_drawing_tab(qapp, monkeypatch):
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        asked = []
        monkeypatch.setattr(g.paint.EZFIG_panel, "update_image_annotations",
                            lambda image2d=None, tab=None: asked.append(tab))
        g.paint.EZFIG_panel.selected_shape = Image2D(width=30, height=20)
        assert g.edit_selected_image_action()
        assert asked == ["Annotations"]
    finally:
        g.paint.EZFIG_panel.selected_shape = None
        g._dirty = False
        g.close()
