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


def test_split_by_a_dimension_uses_the_panel_it_was_asked_for(gui, qapp, tmp_path):
    """Monkey seed 113: the split runs 100 ms after the click and read the
    selection then; cleared meanwhile -> AttributeError in a slot (PyQt6
    aborts the app). The panel is now taken when the action runs."""
    import time
    import tifffile
    from batoolset.drawings.shapes.image2d import Image2D
    z = str(tmp_path / "z.tif")
    tifffile.imwrite(z, (np.arange(4 * 30 * 30) % 200).astype(np.uint8).reshape(4, 30, 30),
                     imagej=True, metadata={"axes": "ZYX"})
    p = gui.paint.EZFIG_panel
    img = Image2D(filename=z)
    p.shapes_to_draw = [img]
    p.selected_shape = img
    errors = []
    import sys
    old_hook = sys.excepthook
    sys.excepthook = lambda *a: errors.append(a[1])
    try:
        p.run_split()
        p.selected_shape = None                  # the selection changes meanwhile
        t0 = time.time()
        while time.time() - t0 < 1.0:
            qapp.processEvents()
            time.sleep(0.01)
    finally:
        sys.excepthook = old_hook
    assert not errors, errors
    from test_dnd_main_editor import _all_images
    assert len(_all_images(gui)) == 5, _all_images(gui)     # the stack + its 4 planes


def test_a_label_left_after_its_panel_moved_keeps_its_width_on_reopen(gui, tmp_path):
    """Monkey seeds 125 / 137: a panel dragged out of a labelled row left its
    label behind; the canvas kept the label's old width, reopening (and undo
    + redo) put it on the last panel — two different figures."""
    pyf = _two_rows(tmp_path, n_second=3)
    assert not M.add_label_row(pyf, [1], ["x", "y", "z"], position="above").startswith("ERROR")
    gui.reload_state(pyf, append=False)
    p = gui.paint.EZFIG_panel
    p.ensure_layout()
    row = [s for s in p.shapes_to_draw if not s.isText][1]
    moved = row.content.pop(1)                    # what a drag out of the row does
    p.shapes_to_draw.append(moved)
    p._layout_dirty = True
    first = str(tmp_path / "first.pyf")
    gui._save_state_to_file(first)
    shown = _geometry(gui)
    gui.reload_state(first, append=False)
    gui.paint.EZFIG_panel.ensure_layout()
    assert _geometry(gui) == shown


def test_an_edit_run_a_moment_later_happens_before_an_undo(gui, qapp, tmp_path):
    """Monkey seed 130: 'To panel' runs 0.3 s after the click; an undo in
    between undid the previous action and the panel landed after it. Undo now
    lets the waiting edit run first."""
    p = gui.paint.EZFIG_panel
    pyf = _two_rows(tmp_path)
    gui.reload_state(pyf, append=False)
    done = []
    p.defer_edit(300, lambda: done.append(True))
    assert gui._images_loading()                 # exports wait for it as well
    gui.undo()
    assert done == [True]
    assert not gui._images_loading()


def test_a_label_without_its_text_does_not_break_the_layout():
    from batoolset.drawings.shapes.compute_optimal_size_all_merged import resize_incompressible_rects
    from batoolset.drawings.shapes.image2d import Image2D
    lbl = Image2D(width=50, height=14, isText=True)
    lbl.annotations = []
    resize_incompressible_rects([lbl], None, 20)          # IndexError before
