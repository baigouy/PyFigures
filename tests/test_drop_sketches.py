"""Sketches in the menus shown when files are dropped from the file browser:
on the figure (To row, To column, panel, with the image below, single
images, montage) and on a poster page (scatter, fan, grid, add, background).
Each choice shows what it gives; the scatter sketch is the real throw.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import QPoint  # noqa: E402
from qtpy.QtWidgets import QMenu, QMessageBox, QPushButton  # noqa: E402


def _png(path, size, value=120):
    from PIL import Image
    Image.new("RGB", size, (value, value, value)).save(path)
    return str(path)


def _tif_stack(path, frames, hw=(30, 40)):
    import tifffile
    tifffile.imwrite(path, np.zeros((frames,) + hw, np.uint8), imagej=True, metadata={"axes": "TYX"})
    return str(path)


def _pixels(icon):
    return icon.pixmap(72, 48).toImage()


@pytest.fixture
def gui(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Yes))
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    yield g
    g._close_dnd_menu()
    g._dirty = False
    g.close()


def _choices(panel):
    return [a for a in panel.contextMenu.actions()
            if not a.isSeparator() and a.isEnabled() and a.text() != "Ignore"]


def test_file_size_reads_the_header_only(tmp_path):
    from pyfigures.gui.drop_sketch import file_size
    assert file_size(_png(tmp_path / "a.png", (60, 20))) == (60, 20)
    assert file_size(_tif_stack(tmp_path / "s.tif", 3)) == (40, 30)
    assert file_size(str(tmp_path / "missing.png")) is None


def test_figure_drop_menu_sketches_differ(gui, tmp_path):
    from batoolset.drawings.shapes.image2d import Image2D
    panel = gui.paint.EZFIG_panel
    existing = Image2D(_png(tmp_path / "old.png", (50, 50)))
    panel.shapes_to_draw.append(existing)
    panel.update_size()
    files = [_png(tmp_path / "a.png", (80, 40)), _png(tmp_path / "b.png", (80, 40)),
             _png(tmp_path / "c.png", (80, 40))]
    gui.add_image_from_an_external_source_context_menu(files, [existing])
    acts = _choices(panel)
    names = [a.text() for a in acts]
    assert any("To row" == n.split("  ")[-1] for n in names), names
    assert all(not a.icon().isNull() for a in acts), [a.text() for a in acts if a.icon().isNull()]
    # row, column, panel, with the image below (row/col), single: all different pictures
    pics = [_pixels(a.icon()) for a in acts]
    same = [(names[i], names[j]) for i in range(len(pics)) for j in range(i + 1, len(pics)) if pics[i] == pics[j]]
    assert not same, same


def test_dropped_files_as_row_go_after_the_figure(gui, tmp_path):
    # the row was put above the first row: the new images (at 0, 0) were taken
    # as being in it, the parent being found by geometry
    from batoolset.drawings.shapes.image2d import Image2D
    panel = gui.paint.EZFIG_panel
    first = Image2D(_png(tmp_path / "first.png", (300, 200)))
    panel.shapes_to_draw.append(first)
    panel.force_update_size_of_parent.emit(first)
    new = [Image2D(_png(tmp_path / f"n{i}.png", (60, 40))) for i in range(3)]
    panel._add_as_new_group(new, orientation="X", remove_from_parents=False)
    assert panel.shapes_to_draw[0] is first
    assert list(panel.shapes_to_draw[1].content) == new


def test_panel_dropped_on_is_orange(gui, tmp_path):
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.gui.drop_sketch import _canvas_result
    panel = gui.paint.EZFIG_panel
    existing = Image2D(_png(tmp_path / "old.png", (50, 50)))
    panel.shapes_to_draw.append(existing)
    files = [_png(tmp_path / "a.png", (80, 40))]
    _shapes, new, target = _canvas_result(panel, "with_row", files, existing, None)
    assert target == {id(existing)} and len(new) == 1


def test_figure_drop_buttons_show_the_sketches(gui, tmp_path):
    files = [_png(tmp_path / "a.png", (80, 40)), _png(tmp_path / "b.png", (40, 80))]
    gui.add_image_from_an_external_source_context_menu(files, [])
    gui._show_dnd_menu(gui.mapToGlobal(QPoint(50, 50)))
    buttons = [b for b in gui._dnd_menu.findChildren(QPushButton) if b.isEnabled() and "Cancel" not in b.text()]
    assert buttons and all(not b.icon().isNull() for b in buttons), [b.text() for b in buttons]
    assert all(b.iconSize().width() >= 48 for b in buttons)


def test_montage_sketch_uses_the_dialog_layout(gui, tmp_path):
    from batoolset.drawings.shapes.group import Group
    from pyfigures.gui.drop_sketch import _canvas_result
    panel = gui.paint.EZFIG_panel
    shapes, new, _t = _canvas_result(panel, "montage", [], None, (8, (40, 30)))
    grp = shapes[-1]
    # 8 frames: two rows of 4 (at most 6 per row, as even as possible)
    assert isinstance(grp, Group) and grp.orientation == "Y"
    assert [len(r.content) for r in grp.content] == [4, 4]
    assert len(new) == 8


def test_single_time_stack_drop_has_a_montage_sketch(gui, tmp_path):
    stack = _tif_stack(tmp_path / "movie.tif", 9)
    gui.add_image_from_an_external_source_context_menu([stack], [])
    acts = _choices(gui.paint.EZFIG_panel)
    montage = next(a for a in acts if "Montage" in a.text())
    single = next(a for a in acts if "single" in a.text())
    assert not montage.icon().isNull() and _pixels(montage.icon()) != _pixels(single.icon())


def test_edit_group_dialog_sketches_the_choice(qapp, tmp_path):
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.gui.group_builder_GUI import PanelOrRow
    row = Group(*[Image2D(_png(tmp_path / f"g{i}.png", (60, 40))) for i in range(3)], orientation="X")
    w = PanelOrRow(row, hide_size=True)
    assert all(not w.orientation_combo.itemIcon(i).isNull() for i in range(2))
    assert w.preview.isVisible() or not w.preview.pixmap().isNull()
    as_row = w.preview.pixmap().toImage()
    w.orientation_combo.setCurrentIndex(w.orientation_combo.findData("Y"))
    assert w.get_parameters()[0] == "Y" and w.preview.pixmap().toImage() != as_row
    assert row.orientation == "X"                       # the figure is untouched until OK


# ---------------------------------------------------------------------------
# poster page
# ---------------------------------------------------------------------------

@pytest.fixture
def poster(qapp):
    from pyfigures.poster.poster_canvas import PosterCanvas
    return PosterCanvas()


def test_poster_scatter_sketch_is_the_real_throw(poster, tmp_path):
    from pyfigures.gui.drop_sketch import poster_arrangement
    paths = [_png(tmp_path / f"p{i}.png", (300, 200)) for i in range(3)]
    _grey, blue = poster_arrangement(poster, paths, "scatter", seed=7)
    poster.apply_drop_arrangement(paths, "scatter", seed=7)
    real = poster.shapes_to_draw[-3:]
    for s, r in zip(blue, real):
        assert s.theta == pytest.approx(r.theta)
        assert s.center_mm().x() == pytest.approx(r.center_mm().x(), abs=0.01)
        assert s.width_mm == pytest.approx(r.width_mm, rel=1e-3)


def test_poster_drop_menus_have_sketches(poster, tmp_path, monkeypatch):
    seen = []

    def fake_exec(self, *a, **k):
        seen.append([(x.text(), x.icon().isNull()) for x in self.actions() if not x.isSeparator()])
        return None
    monkeypatch.setattr(QMenu, "exec", fake_exec)
    paths = [_png(tmp_path / f"p{i}.png", (300, 200)) for i in range(3)]
    poster._offer_drop_layout(paths, QPoint(0, 0))
    no_icon = [t for t, null in seen[-1] if null]
    # the header and the gallery (chosen in a dialog next) have no sketch
    assert len(no_icon) == 2 and any("gallery" in t for t in no_icon), seen[-1]
    poster._offer_single_drop(paths[0], QPoint(0, 0))
    assert all(not null for _t, null in seen[-1]), seen[-1]
