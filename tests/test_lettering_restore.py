"""Opening a figure keeps its own panel letters.

The GUI used to re-letter every opened figure from its toolbar defaults
("a", lettering on): a figure built by a recipe or the MCP server with A, B
showed a, b, and one built without letters got some. The first letter and
the on/off switch are now saved with the figure, and read from the panels'
letters for older files.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _recipe_figure(tmp_path, name, letters=True):
    from PIL import Image
    from pyfigures.recipe import build_figure_from_recipe
    Image.fromarray(np.full((40, 60), 120, np.uint8)).save(tmp_path / "a.png")
    out = str(tmp_path / f"{name}.pyf")
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"output": out, "letter_panels": letters,
                                "rows": [["a.png", "a.png"]]}), encoding="utf-8")
    build_figure_from_recipe(str(path))
    return out


def _letters(gui, qapp):
    from batoolset.drawings.shapes.txt2d import TAText2D
    t0 = time.time()
    while time.time() - t0 < 5:
        qapp.processEvents()
        time.sleep(0.02)
    gui.update_letters()
    _, images = gui.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation(
        exclude_images_without_filename=False, include_insets=False)
    return [a.getPlainText() for im in images for a in (im.annotations or [])
            if isinstance(a, TAText2D) and a.is_letter]


@pytest.fixture
def gui(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    yield g
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def test_recipe_letters_kept_when_opened(gui, qapp, tmp_path):
    pyf = _recipe_figure(tmp_path, "upper")
    gui.reload_state(pyf, append=False)
    assert _letters(gui, qapp) == ["A", "B"]
    assert gui.letter_line_edit.text() == "A" and gui.auto_lettering_checkbox.isChecked()


def test_figure_without_letters_stays_without(gui, qapp, tmp_path):
    pyf = _recipe_figure(tmp_path, "none", letters=False)
    gui.reload_state(pyf, append=False)
    assert _letters(gui, qapp) == [] and not gui.auto_lettering_checkbox.isChecked()


def test_lettering_saved_with_the_figure(gui, qapp, tmp_path):
    pyf = _recipe_figure(tmp_path, "saved")
    gui.reload_state(pyf, append=False)
    gui.letter_line_edit.setText("c")
    assert _letters(gui, qapp) == ["c", "d"]
    out = str(tmp_path / "resaved.pyf")
    gui._save_state_to_file(out)
    text = open(out, encoding="utf-8").read()
    assert "<first_letter>" in text and "<auto_lettering>True" in text
    gui.letter_line_edit.setText("a")
    gui.reload_state(out, append=False)
    assert gui.letter_line_edit.text() == "c" and _letters(gui, qapp) == ["c", "d"]
