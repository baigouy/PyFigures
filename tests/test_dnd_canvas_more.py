"""More internal drag-and-drop on the canvas: loose (top-level) images and
rows dropped onto each other, the menu each drop offers, and what every
choice does. The image inventory must never change (nothing lost, nothing
duplicated) and the figure must not end up with overlapping blocks.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_dnd_main_editor import (  # noqa: E402,F401  (fixtures + helpers)
    ui, files, canvas_fig, drag, _centre, _inventory, _no_overlap, _offered, _all_images, _wait, _tif,
)


@pytest.fixture
def loose_fig(canvas_fig, qapp, tmp_path):
    """Rows [A B] and [C D] plus two loose images E and F."""
    g, e = canvas_fig
    f = _tif(tmp_path / "loose_f.tif", 140, (44, 44))
    g.all_images_directly([e, f])
    _wait(qapp, g, lambda: len(_all_images(g)) == 6)
    return g


def loose(g):
    return [s for s in g.paint.EZFIG_panel.shapes_to_draw if type(s).__name__ == "Image2D"]


def groups(g):
    return [s for s in g.paint.EZFIG_panel.shapes_to_draw if type(s).__name__ == "Group"]


def _drop(g, ui, shape, target, pick=None):
    ui["pick"] = pick
    drag(g, shape, _centre(g.paint.EZFIG_panel, target))
    ui["pick"] = None
    g.paint.EZFIG_panel.update_size()
    return _offered(ui)


# ---------------------------------------------------------------------------
# loose image onto loose image
# ---------------------------------------------------------------------------

def test_loose_onto_loose_offers_row_column_swap(loose_fig, ui):
    e, f = loose(loose_fig)
    offered = _drop(loose_fig, ui, e, f)
    assert {"To row", "To column", "Swap"} <= set(offered), offered


@pytest.mark.parametrize("choice,orientation", [("To row", "X"), ("To column", "Y")])
def test_loose_onto_loose_makes_a_group(loose_fig, ui, choice, orientation):
    g = loose_fig
    before = _inventory(g)
    n_groups = len(groups(g))
    e, f = loose(g)
    _drop(g, ui, e, f, pick=choice)
    assert _inventory(g) == before
    assert loose(g) == []                                  # both went into the new group
    assert len(groups(g)) == n_groups + 1
    new = groups(g)[-1]
    assert new.orientation == orientation and set(map(id, new.content)) == {id(e), id(f)}
    _no_overlap(g)


def test_loose_onto_loose_swap(loose_fig, ui):
    g = loose_fig
    panel = g.paint.EZFIG_panel
    before = _inventory(g)
    e, f = loose(g)
    i_e, i_f = panel.shapes_to_draw.index(e), panel.shapes_to_draw.index(f)
    _drop(g, ui, e, f, pick="Swap")
    assert _inventory(g) == before
    assert panel.shapes_to_draw.index(e) == i_f and panel.shapes_to_draw.index(f) == i_e
    _no_overlap(g)


# ---------------------------------------------------------------------------
# a row onto a loose image, a loose image onto a row
# ---------------------------------------------------------------------------

def test_row_onto_loose_image_offers_add_to_group(loose_fig, ui):
    g = loose_fig
    row = groups(g)[0]
    offered = _drop(g, ui, row, loose(g)[0])
    assert {"Add to group", "To row", "To column"} <= set(offered), offered


@pytest.mark.parametrize("choice", ["Add to group", "To row", "To column"])
def test_row_onto_loose_image_choices_keep_every_image(loose_fig, ui, choice):
    g = loose_fig
    panel = g.paint.EZFIG_panel
    before = _inventory(g)
    row = groups(g)[0]
    row_imgs = list(row.content)
    target = loose(g)[0]
    _drop(g, ui, row, target, pick=choice)
    assert _inventory(g) == before, choice
    assert target not in panel.shapes_to_draw              # the loose image joined a group
    top = panel.get_top_parent_of_shape(target)
    if choice == "Add to group":
        assert top is row
    elif choice == "To row":                               # a row into a row: merged flat
        assert top.orientation == "X" and all(i in top.content for i in row_imgs + [target])
    else:                                                  # a row into a column: kept as a row
        assert top.orientation == "Y" and row in top.content
    _no_overlap(g)


def test_loose_image_onto_image_in_row(loose_fig, ui):
    g = loose_fig
    panel = g.paint.EZFIG_panel
    row = groups(g)[0]
    e = loose(g)[0]
    offered = _drop(g, ui, e, row.content[0])
    assert offered, "no menu when a loose image is dropped onto a row"
    add = next((x for x in offered if x.startswith("Add to group")), None)
    assert add, offered
    before = _inventory(g)
    _drop(g, ui, e, row.content[0], pick=add)
    assert _inventory(g) == before
    assert panel.get_top_parent_of_shape(e) is row
    _no_overlap(g)


def test_dismissed_drop_menu_puts_the_shape_back(loose_fig, ui):
    g = loose_fig
    e, f = loose(g)
    r0 = e.boundingRect()
    order = list(g.paint.EZFIG_panel.shapes_to_draw)
    _drop(g, ui, e, f, pick=None)                           # Esc / click elsewhere
    assert list(g.paint.EZFIG_panel.shapes_to_draw) == order
    r1 = e.boundingRect()
    assert abs(r1.x() - r0.x()) < 1 and abs(r1.y() - r0.y()) < 1


def test_drag_onto_itself_does_nothing(loose_fig, ui):
    g = loose_fig
    e = loose(g)[0]
    order = list(g.paint.EZFIG_panel.shapes_to_draw)
    n_menus = len(ui["menus"])
    drag(g, e, _centre(g.paint.EZFIG_panel, e, dx=15, dy=15))
    assert list(g.paint.EZFIG_panel.shapes_to_draw) == order
    assert len(ui["menus"]) == n_menus or "Swap" not in ui["menus"][-1]
