"""Found by long GUI monkey runs (30 October 2026): undo + redo and save +
reopen came back with other panel sizes. Opening a figure lays every row out
again (Group.__init__) while the canvas kept whatever an action left; label
rows were fitted to the row before them even when they label the row after;
a label without its text broke the layout of its row."""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from PIL import Image  # noqa: E402

import pyfigures.mcp_server as M  # noqa: E402
from test_dnd_main_editor import ui, gui  # noqa: F401,E402


def _png(path, shape, value=90):
    Image.fromarray(np.full(shape, value, np.uint8)).save(path)
    return str(path)


def _two_rows(tmp_path, n_second=3):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=2)
    for k in range(2):
        M.add_image(pyf, [0], _png(tmp_path / f"a{k}.png", (40, 60)))
    for k in range(n_second):
        M.add_image(pyf, [1], _png(tmp_path / f"b{k}.png", (60, 40)))
    return pyf


def _geometry(gui):
    from batoolset.drawings.shapes.image2d import Image2D
    out, stack = [], list(gui.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        s = stack.pop(0)
        if isinstance(s, Image2D):
            r = s.getRect(all=True)
            out.append((round(r.x(), 1), round(r.y(), 1), round(r.width(), 1), round(r.height(), 1)))
        stack[0:0] = list(getattr(s, "content", None) or [])
    return out


def test_a_row_left_unpacked_saves_as_it_reopens(gui, tmp_path):
    """An action that leaves a row laid out otherwise than opening does
    (a drag 'Take H into the dragged row') came back different on undo +
    redo: the canvas now lays rows out the way opening the figure does."""
    pyf = _two_rows(tmp_path)
    gui.reload_state(pyf, append=False)
    row = [s for s in gui.paint.EZFIG_panel.shapes_to_draw if not s.isText][1]
    for img in row.content:                      # what such an action leaves
        img.scale = img.scale * 1.07
    gui.paint.EZFIG_panel._layout_dirty = True
    first = str(tmp_path / "first.pyf")
    gui._save_state_to_file(first)
    shown = _geometry(gui)
    gui.reload_state(first, append=False)
    gui.paint.EZFIG_panel.ensure_layout()
    assert _geometry(gui) == shown


def test_a_label_row_fits_the_row_it_labels(gui, tmp_path):
    """add_label_row(position='above') on the second row stores the label row
    between the two rows; reopening fitted it to the FIRST row (2 panels)."""
    pyf = _two_rows(tmp_path, n_second=3)
    assert not M.add_label_row(pyf, [1], ["x", "y", "z"], position="above").startswith("ERROR")
    gui.reload_state(pyf, append=False)
    gui.paint.EZFIG_panel.ensure_layout()
    shapes = gui.paint.EZFIG_panel.shapes_to_draw
    labels = [s for s in shapes if s.isText][0]
    target = shapes[shapes.index(labels) + 1]
    images = [c for c in target.content if not c.isText]
    assert len(labels.content) == len(images) == 3
    for lbl, img in zip(labels.content, images):
        assert abs(lbl.getRect(all=True).x() - img.getRect(all=True).x()) < 1.5
        assert abs(lbl.getRect(all=True).width() - img.getRect(all=True).width()) < 1.5


def _shared(panel):
    seen, twice, stack = set(), [], list(panel.shapes_to_draw)
    while stack:
        s = stack.pop()
        if id(s) in seen:
            twice.append(s)
            continue
        seen.add(id(s))
        stack.extend(getattr(s, "content", None) or [])
    return twice


@pytest.mark.parametrize("orientation", ["col", "row"])
def test_dragging_a_nested_panel_onto_its_own_row_moves_it(gui, tmp_path, orientation):
    """Monkey seed 102: zstack dragged out of (rgb | zstack) / gray16 / movie
    (nested in row 1) onto row 1 -> To column: the row left the canvas first,
    zstack's group was then not found, and zstack stayed there AND joined the
    new column — one panel in two places."""
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    im = {n: Image2D(filename=_png(tmp_path / f"{n}.png", (40, 60))) for n in
          ("rgb", "zstack", "gray16", "movie", "cells")}
    inner = Group(im["rgb"], im["zstack"], orientation="X")
    column = Group(inner, im["gray16"], im["movie"], orientation="Y")
    row1 = Group(column, im["cells"], orientation="X")
    p = gui.paint.EZFIG_panel
    p.shapes_to_draw = [row1]
    (p.create_col_with if orientation == "col" else p.create_row_with)(row1, im["zstack"])
    assert not _shared(p), _shared(p)
    assert all(im["zstack"] is not c for c in inner.content)


def test_a_label_without_its_text_does_not_break_the_layout():
    from batoolset.drawings.shapes.compute_optimal_size_all_merged import resize_incompressible_rects
    from batoolset.drawings.shapes.image2d import Image2D
    lbl = Image2D(width=50, height=14, isText=True)
    lbl.annotations = []
    resize_incompressible_rects([lbl], None, 20)          # IndexError before
