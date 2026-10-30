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


def _label(width, height=14):
    from batoolset.drawings.shapes.image2d import Image2D
    lbl = Image2D(width=width, height=height, isText=True)
    lbl.annotations = []
    return lbl


def _labelled_column_row(tmp_path):
    """Monkey seed 144: (label / (gray16 | gray8) / label) above movie and
    cells2, that column beside rgb."""
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    im = [Image2D(filename=_png(tmp_path / f"i{k}.png", (40, 60))) for k in range(5)]
    labelled = Group(_label(36), Group(im[0], im[1], orientation="X"), _label(36), orientation="Y")
    column = Group(labelled, im[2], im[3], orientation="Y")
    return Group(column, im[4], orientation="X"), im


def test_a_column_with_labels_is_laid_out_the_same_from_any_start(gui, tmp_path):
    """The layout was a fixed-point iteration that took groups as scaling
    like images: with labels stacked in a column it did not converge, so the
    result depended on the sizes before (undo/redo came back different) and
    could even be negative (seed 144: scale -35, panels not drawn)."""
    from batoolset.drawings.shapes.group import set_to_width
    row, im = _labelled_column_row(tmp_path)
    set_to_width(row, 512)
    first = [round(i.scale, 6) for i in im]
    for k, i in enumerate(im):                    # another starting point
        i.scale = 0.05 + 0.4 * k
    row.set_to_size(512)
    set_to_width(row, 512)
    assert [round(i.scale, 6) for i in im] == first
    assert all(s > 0 for s in first)
    assert abs(row.getRect(all=True).width() - 512) < 0.01
    tops = [i.getRect(all=True) for i in (im[2], im[4])]   # the row's panels line up at the bottom
    assert abs(row.getRect(all=True).height() - tops[1].height()) < 0.01


def test_a_squeezed_row_keeps_its_size_on_every_relayout(gui, tmp_path):
    """Monkey seed 122: nested deep enough that a panel hit its 1 px
    minimum, the row came out wider than asked; that width became its size,
    so each relayout (undo, redo, reopen) gave other scales."""
    from batoolset.drawings.shapes.group import Group, set_to_width
    from batoolset.drawings.shapes.image2d import Image2D
    images = [Image2D(filename=_png(tmp_path / "deep.png", (40, 60)))]
    shape = images[0]
    for k in range(14):                           # deep enough to squeeze the innermost panel
        images.append(Image2D(filename=_png(tmp_path / f"o{k}.png", (40, 60))))
        shape = Group(shape, images[-1], orientation="XY"[k % 2])
    set_to_width(shape, 60)
    deep = images[0].getRect(all=True)
    assert min(deep.width(), deep.height()) <= 1.0001         # squeezed to its minimum
    scales = [round(i.scale, 9) for i in images]
    for _ in range(3):
        shape.set_to_size(shape.size)
        set_to_width(shape, shape.size)
    assert shape.size == 60
    assert [round(i.scale, 9) for i in images] == scales


def test_stacked_label_rows_both_fit_the_row_they_label(gui, tmp_path):
    """Monkey seeds 143-164: two label rows on top of each other label the
    row after them; the first one was fitted by neither the canvas nor
    reopening (512 px one way, 326 px the other)."""
    from batoolset.drawings.shapes.group import Group
    from pyfigures.gui.label_rows import fit_label_rows
    from batoolset.drawings.shapes.image2d import Image2D
    im = [Image2D(filename=_png(tmp_path / f"i{k}.png", (40, 60))) for k in range(2)]
    row = Group(*im, orientation="X")
    top = Group(_label(500), orientation="X", isText="below")
    second = Group(_label(100), _label(100), orientation="X", isText="below")
    p = gui.paint.EZFIG_panel
    p.shapes_to_draw = [top, second, row]
    for arrange in (fit_label_rows, lambda _s: p.repack_all(), lambda _s: gui.arrange_text_rows()):
        top.content[0].setWidth(500)
        arrange(p.shapes_to_draw)
        assert abs(top.content[0].width(all=True) - im[0].width(all=True)) < 0.01
        for lbl, img in zip(second.content, im):
            assert abs(lbl.width(all=True) - img.width(all=True)) < 0.01
            assert abs(lbl.x() - img.x()) < 0.01


def test_a_label_spanning_panels_gets_their_width(gui, tmp_path):
    """The canvas sized labels per panel, arrange_text_rows per range: a
    label over two panels changed width at every undo."""
    from batoolset.drawings.shapes.group import Group
    from pyfigures.gui.label_rows import fit_label_rows
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.txt2d import TAText2D
    im = [Image2D(filename=_png(tmp_path / f"i{k}.png", (40, 60))) for k in range(3)]
    row = Group(*im, orientation="X")
    lbl = _label(50)
    lbl.annotations = [TAText2D("both")]
    lbl.annotations[0].range = [0, 1]
    labels = Group(lbl, orientation="X", isText="above")
    fit_label_rows([row, labels])
    span = im[1].x() + im[1].width(all=True) - im[0].x()
    assert abs(lbl.width(all=True) - span) < 0.01


def test_an_emptied_group_is_dropped_and_adds_no_gap(gui, tmp_path):
    """Monkey seeds 143 / 119: a drag took the last panel out of a nested
    group. Its bounds were infinite (row size -inf, NaN coordinates, an error
    while painting, then a native crash), and reopening counted it as one
    more gap (scales 0.236 -> 0.237)."""
    import math
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    empty = Group(orientation="Y")
    empty.content = []
    empty.update_bounds()
    assert all(math.isfinite(v) for v in (empty.width(), empty.height()))
    pyf = _two_rows(tmp_path)
    gui.reload_state(pyf, append=False)
    p = gui.paint.EZFIG_panel
    p.ensure_layout()
    row = [s for s in p.shapes_to_draw if not s.isText][0]
    inner = Group(Image2D(filename=_png(tmp_path / "x.png", (40, 60))), orientation="Y")
    row.content.append(inner)
    inner.content.clear()                         # what the drag leaves
    first = str(tmp_path / "first.pyf")
    gui._save_state_to_file(first)
    shown = _geometry(gui)
    assert inner not in row.content
    gui.reload_state(first, append=False)
    gui.paint.EZFIG_panel.ensure_layout()
    assert _geometry(gui) == shown


def test_an_empty_group_keeps_its_width_for_the_panels_added_later():
    """An empty group measured 0 px wide (it used to be ±inf, then replaced
    by 512); that 0 became its size, and the panels added to it next were
    laid out 1 px small."""
    from batoolset.drawings.shapes.group import Group, set_to_width, set_to_height
    for orientation in "XY":
        empty = Group(orientation=orientation)
        assert empty.size == 512
        set_to_width(empty, 300)
        assert empty.size == 300
        set_to_height(empty, 200)                 # divided by its 0 size
        assert empty.size == 200


def test_a_vertical_label_measures_the_same_wherever_it_is(qapp):
    """Monkey seed 149: a side label's rotated box was rounded to whole
    pixels at its current position, 15 x 494 at one place and 16 x 493 at
    another, so its row changed after undo / redo and reopening."""
    from batoolset.drawings.shapes.txt2d import TAText2D
    txt = TAText2D("<p>a side label</p>")
    txt.text_orientation = "Y"
    sizes = set()
    for x, y in ((0, 0), (10.4, 3.6), (10.6, 3.4), (123.5, 77.5)):
        txt.setTopLeft(x, y)
        r = txt.getRect(all=True)
        sizes.add((round(r.width(), 6), round(r.height(), 6)))
    assert len(sizes) == 1, sizes
    w, h = sizes.pop()
    flat = txt.getRect()
    assert (w, h) == (round(flat.height(), 6), round(flat.width(), 6))


def test_a_figure_with_no_room_for_its_panels_is_not_exported(tmp_path, qapp):
    """The layout keeps squeezed panels at 1 px instead of going negative, so
    the figure's size no longer gave it away: a 4 px figure exported as
    1 px panels instead of saying there is no room."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for k in range(2):
        M.add_image(pyf, [0], _png(tmp_path / f"a{k}.png", (40, 60)))
    M.set_size(pyf, 4)
    assert "no room" in M.export_figure(pyf, str(tmp_path / "f.png"), 72)
    assert "no room" in M.export_pptx(pyf, str(tmp_path / "f.pptx"))


def test_an_error_while_painting_ends_the_painter(gui, qapp):
    """An exception in paintEvent left the QPainter active ('endPaint()
    called with active painter'); Qt crashed natively a moment later."""
    import sys
    p = gui.paint.EZFIG_panel
    errors = []
    old_hook = sys.excepthook
    sys.excepthook = lambda *a: errors.append(a[1])
    real = p.draw_selection
    painters = []

    def boom(painter):
        painters.append(painter)
        raise ValueError("cannot convert float NaN to integer")
    p.draw_selection = boom
    try:
        p.grab()
        qapp.processEvents()
    finally:
        p.draw_selection = real
        sys.excepthook = old_hook
    assert errors and isinstance(errors[0], ValueError)   # still reported
    assert painters and not painters[0].isActive()
    assert not p.grab().isNull()                  # painting works again


def test_a_label_without_its_text_does_not_break_the_layout():
    from batoolset.drawings.shapes.compute_optimal_size_all_merged import resize_incompressible_rects
    from batoolset.drawings.shapes.image2d import Image2D
    lbl = Image2D(width=50, height=14, isText=True)
    lbl.annotations = []
    resize_incompressible_rects([lbl], None, 20)          # IndexError before
