"""User 2026-11-23: the grid panel dialog (images dropped "To a grid panel", Insert > Images
from files > To a grid panel) always offered 2 rows ("2 rows with plenty of cols"): offer
3-5 images a row and no row with one real image among empty slots; the user can change it."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pyfigures.gui.panelcreationwidget import PanelCreator, default_grid_shape  # noqa: E402


@pytest.mark.parametrize("n, shape", [
    (1, (1, 1)), (3, (1, 3)), (5, (1, 5)), (6, (2, 3)), (7, (2, 4)), (8, (2, 4)), (9, (3, 3)),
    (10, (2, 5)), (11, (3, 4)), (12, (3, 4)), (13, (3, 5)), (16, (4, 4)), (14, (3, 5)), (20, (4, 5)), (21, (7, 3)),
])
def test_default_shape(n, shape):
    assert default_grid_shape(n) == shape


@pytest.mark.parametrize("n", range(2, 60))
def test_rows_are_three_to_five_wide_and_no_lonely_last_image(n):
    rows, cols = default_grid_shape(n)
    assert rows * cols >= n and (rows - 1) * cols < n          # every row holds an image
    last = n - (rows - 1) * cols
    assert rows == 1 or last >= 2
    assert 3 <= cols <= 5 or n <= 5


def test_the_dialog_starts_on_it_and_the_user_can_change_it(qapp):
    w = PanelCreator(None, 13)
    v = w.get_values()
    assert (v["num_rows"], v["num_cols"]) == (3, 5)
    w.num_rows.setValue(2)                                       # the user's choice wins
    assert (w.get_values()["num_rows"], w.get_values()["num_cols"]) == (2, 7)
    w.deleteLater()
