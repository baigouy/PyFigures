"""User 2026-11-23: images dropped with an .xlsx and a .csv "To row": "again a spacing
error when the xls or csv, the error went away as soon as I clicked/selected the row".
After the drop has settled, the row is packed: every panel has the row's height and the
gaps are the row's spacing, without the user touching it."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_dnd_main_editor import _tif, _wait, click, drop, gui, ui  # noqa: E402,F401


def _row_geometry(row):
    rects = [i.getRect(all=True) for i in row.content]
    heights = [round(r.height(), 1) for r in rects]
    gaps = [round(b.left() - a.right(), 1) for a, b in zip(rects, rects[1:])]
    return heights, gaps


@pytest.fixture
def mixed(tmp_path):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    d = tmp_path / "drop"
    d.mkdir()
    book = str(d / "aaa_measurements.xlsx")
    pd.DataFrame({"WT": [1.0, 2.0, 3.0, 2.5], "mut": [4.0, 5.0, 6.0, 5.5]}).to_excel(book, index=False)
    table = d / "aaa_two_factors.csv"
    table.write_text("genotype,day,length\n" + "".join(
        f"{g},{dd},{10 + i + k}\n" for g in ("WT", "mut") for i, dd in enumerate(("d1", "d2")) for k in range(4)))
    shapes = [(40, 60), (90, 50), (30, 80), (64, 64), (50, 120)]
    imgs = [_tif(d / f"img{i}.tif", 40 * (i + 1), shape=s) for i, s in enumerate(shapes)]
    return imgs[:2] + [book, str(table)] + imgs[2:]


def test_images_and_tables_dropped_to_a_row_are_packed(gui, qapp, mixed):
    drop(gui, mixed)
    click(gui, "↔  To row")
    _wait(qapp, gui, timeout=30)
    for _ in range(20):
        qapp.processEvents()
    row = [s for s in gui.paint.EZFIG_panel.shapes_to_draw if hasattr(s, "content")][-1]
    assert len(row.content) == 7
    heights, gaps = _row_geometry(row)
    assert len(set(heights)) == 1, ("heights", heights)
    assert max(gaps) - min(gaps) < 0.6, ("gaps", gaps)
