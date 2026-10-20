"""Regression tests for the bugs the end-to-end GUI layer (test_gui_e2e_*.py)
found. Each test names the user-visible symptom it guards against."""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _tif(path, val, shape=(20, 30)):
    from batoolset.img import Img
    Img(np.full(shape, val, np.uint8), dimensions="hw").save(str(path))
    return str(path)


def test_mixed_rows_and_loose_images_keep_their_order_when_reloaded(qapp, tmp_path):
    """The .pyf reader grouped children by tag: [row, image, row] came back
    as [row, row, image] — undo after a Swap and reopening a saved figure
    showed another arrangement. Same inside a group's content."""
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.serializations.tools import create_object, deserialize_to_dict, object_to_xml
    a, b, c, d, e = (Image2D(_tif(tmp_path / f"{n}.tif", 40 * (i + 1))) for i, n in enumerate("abcde"))
    inner = Group(Image2D(_tif(tmp_path / "f.tif", 9)), Image2D(_tif(tmp_path / "g.tif", 99)), orientation="Y")
    mixed = Group(c, inner, d, orientation="X")           # image, group, image inside a row
    top = [Group(a, orientation="X"), e, mixed, b]          # row, image, row, image at the top
    back = create_object(list.__name__, deserialize_to_dict(object_to_xml(top, is_list=True)))

    def names(s):
        if isinstance(s, Image2D):
            return os.path.basename(s.filename)
        return [names(x) for x in s.content]
    assert [names(s) for s in back] == [["a.tif"], "e.tif", ["c.tif", ["f.tif", "g.tif"], "d.tif"], "b.tif"]


@pytest.fixture
def two_rows(qapp, tmp_path, monkeypatch):
    """Rows [a b] [c d] + a loose image e, in a real window; QMenu.exec
    replaced by a pilot (see gui_e2e_harness.MenuPilot)."""
    import gui_e2e_harness as H
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    for row, names in ((0, "ab"), (1, "cd")):
        for i, n in enumerate(names):
            M.add_image(pyf, [row], _tif(tmp_path / f"{n}.tif", 30 + 50 * i, (20 + 10 * row, 30)))
    g = H.new_gui(qapp)
    H.load(qapp, g, pyf)
    g.all_images_directly([_tif(tmp_path / "e.tif", 200)])
    H.settle(qapp, g, lambda: len(H.images(g)) == 5)
    menus = H.MenuPilot(monkeypatch)
    yield g, H, menus, tmp_path
    H.close_gui(qapp, g)


def test_swap_can_be_undone(qapp, two_rows):
    """Swap recorded no undo checkpoint: Undo went back further (or nowhere)."""
    g, H, menus, d = two_rows
    g._save_state_to_file(str(d / "start.pyf"))
    H.load(qapp, g, str(d / "start.pyf"))
    before = H.snapshot(g, d)
    menus.pick = "Swap"
    H.drag(g, H.rows(g)[0], H.centre(g, H.rows(g)[1]))
    after = H.snapshot(g, d)
    assert after["rows"] == ["row 1: c.tif | d.tif", "row 2: a.tif | b.tif", "row 3: e.tif"]
    g.undo()
    H.settle(qapp, g)
    assert H.snapshot(g, d)["rows"] == before["rows"]


def test_image_dropped_on_an_image_of_another_row_can_swap_with_it(qapp, two_rows):
    """Only Add-to-group / To row / To column were offered: two images of
    different rows could not trade places."""
    g, H, menus, d = two_rows
    menus.pick = "Swap"
    H.drag(g, H.by_name(g, "a"), H.centre(g, H.by_name(g, "d")))
    assert H.snapshot(g, d)["rows"] == ["row 1: d.tif | b.tif", "row 2: c.tif | a.tif", "row 3: e.tif"]


def test_a_new_group_takes_the_place_of_the_row_it_is_made_from(qapp, two_rows):
    """Dropping a file onto row 1 and choosing 'To row (with image below)'
    moved row 1 to the bottom of the figure."""
    g, H, menus, d = two_rows
    g.add_images_combined_with_target([_tif(d / "z.tif", 7)], H.rows(g)[0], "X")
    H.settle(qapp, g, lambda: len(H.images(g)) == 6)
    assert H.snapshot(g, d)["rows"][0] == "row 1: (a.tif | b.tif) | z.tif"


def test_dropping_an_equation_or_a_pdf_does_not_read_it_to_build_the_menu(qapp, two_rows, monkeypatch):
    """The drop menu asked stack_info() whether a .svg / .pdf was a movie:
    a full read that started Fiji's JVM (seconds) before the menu appeared."""
    g, H, menus, d = two_rows
    import pyfigures.stack_info as S
    called = []
    monkeypatch.setattr(S, "stack_info", lambda *a, **k: called.append(a) or {})
    for ext in (".svg", ".pdf"):
        assert g._stack_axes_of_file(str(d / f"x{ext}")) == []
    assert called == []


@pytest.mark.parametrize("dims,shape,axes", [
    ("thw", (5, 20, 30), "TYX"), ("dhw", (4, 20, 30), "ZYX"), ("tdhw", (3, 4, 20, 30), "TZYX"),
    ("thwc", (5, 20, 30, 2), "TCYX"), ("dhwc", (4, 20, 30, 2), "ZCYX"), ("hw", (20, 30), "YX"),
])
def test_saved_time_stack_stays_a_time_stack(tmp_path, dims, shape, axes):
    """Img(..., dimensions='thw').save() wrote the frames as Z slices: a movie
    saved by PyFigures reopened as a Z stack (max-projected, 'Z' montage)."""
    import tifffile
    from batoolset.img import Img, save_as_tiff
    a = np.random.default_rng(0).integers(0, 255, shape).astype(np.uint8)
    for k, write in enumerate((lambda p: Img(a, dimensions=dims).save(p),
                               lambda p: save_as_tiff(Img(a, dimensions=dims), p))):
        p = str(tmp_path / f"{dims}_{k}.tif")
        write(p)
        assert tifffile.TiffFile(p).series[0].axes == axes
        back = Img(p)
        assert back.metadata["dimensions"] == dims
        assert np.array_equal(np.asarray(back), a)
