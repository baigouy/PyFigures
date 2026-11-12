"""One property of an existing scale bar, the way people ask in the chat:
"too thick", "no text on the bars", "move it to the left", "bars in black".
The tool needed the length again each time, had no thickness, and an empty
label did not hide the text (Mistral Large 4 ran out of steps on each,
2026-11-12).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def fig(tmp_path):
    """A row of a PNG (no pixel size) and an ImageJ TIFF at 0.25 µm/px."""
    import tifffile
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image
    d = str(tmp_path)
    png = os.path.join(d, "plain.png")
    Image.fromarray(np.full((80, 100), 40, np.uint8)).save(png)
    tif = os.path.join(d, "calibrated.tif")
    tifffile.imwrite(tif, np.full((80, 100), 40, np.uint8),
                     imagej=True, resolution=(4.0, 4.0), metadata={"unit": "um"})
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(pyf, [0], png)
    add_image(pyf, [0], tif)
    return pyf


def _bar(pyf, index):
    from pyfigures.mcp_server import get_scale_bar
    return json.loads(get_scale_bar(pyf, [0], index))


def test_one_property_changes_and_the_rest_is_kept(fig):
    from pyfigures.mcp_server import set_scale_bar
    assert "added" in set_scale_bar(fig, [0], 1, 10, placement="top left", bar_color="yellow", label_color="yellow")
    before = _bar(fig, 1)
    assert before["bar_height_px"] == 3 and before["label_plain"] == "10 µm" and before["has_text"]

    reply = set_scale_bar(fig, [0], 1, bar_height_px=1.5)                 # "too thick"
    assert "updated" in reply and "1.5 px thick" in reply and "10 µm" in reply
    after = _bar(fig, 1)
    assert after["bar_height_px"] == 1.5
    for key in ("bar_width_in_units", "placement", "bar_color", "label_html"):
        assert after[key] == before[key], key

    assert "bottom left" in set_scale_bar(fig, [0], 1, placement="bottom left")   # "move it to the left"
    assert _bar(fig, 1)["placement"] == "bottom left" and _bar(fig, 1)["bar_color"] == before["bar_color"]

    set_scale_bar(fig, [0], 1, bar_color="black")                          # "bars in black"
    bar = _bar(fig, 1)
    assert bar["bar_color"] == 0 and bar["label_html"] == before["label_html"] and bar["bar_height_px"] == 1.5

    set_scale_bar(fig, [0], 1, label_color="black")                        # the text only
    bar = _bar(fig, 1)
    assert bar["label_plain"] == "10 µm" and "#000000" in bar["label_html"]

    set_scale_bar(fig, [0], 1, 20)                                         # a new length: new text, same style
    bar = _bar(fig, 1)
    assert bar["label_plain"] == "20 µm" and "#000000" in bar["label_html"] and bar["placement"] == "bottom left"


@pytest.mark.parametrize("index, label", [(1, ""), (0, ""), (1, "none")])
def test_no_text_on_the_bar(fig, index, label):
    """Also on an image without pixel size: there the '10 px' text came back."""
    from pyfigures.mcp_server import set_scale_bar
    set_scale_bar(fig, [0], index, 10)
    assert _bar(fig, index)["has_text"]
    assert "no text" in set_scale_bar(fig, [0], index, label=label)
    bar = _bar(fig, index)
    assert not bar["has_text"] and bar["label_plain"] == "" and float(bar["bar_width_in_units"]) == 10
    set_scale_bar(fig, [0], index, 20)                    # a new length does not bring the text back
    assert not _bar(fig, index)["has_text"]
    set_scale_bar(fig, [0], index, label="20 µm")         # asking for a text does
    assert _bar(fig, index)["label_plain"] == "20 µm"


def test_all_the_bars_restyled_at_once(fig):
    """'no text on the bars', 'bars in black', 'thinner': the bars that exist, lengths kept."""
    from pyfigures.mcp_server import set_scale_bar, set_scale_bar_all
    assert set_scale_bar_all(fig, label="").startswith("ERROR")        # none yet: nothing to restyle
    set_scale_bar(fig, [0], 1, 10, placement="top left")
    reply = set_scale_bar_all(fig, label="", bar_color="black", bar_height_px=2)
    assert "1 existing scale bar(s) restyled" in reply and "no text" in reply and "1 image(s) without" in reply
    bar = _bar(fig, 1)
    assert not bar["has_text"] and bar["bar_color"] == 0 and bar["bar_height_px"] == 2
    assert bar["placement"] == "top left" and float(bar["bar_width_in_units"]) == 10
    assert "No scale bar" in __import__("pyfigures.mcp_server", fromlist=["x"]).get_scale_bar(fig, [0], 0)
    # with a length it still adds everywhere, here thin and without text
    reply = set_scale_bar_all(fig, 5, label="", bar_height_px=1)
    assert "1 added, 1 updated" in reply and "no text" in reply
    assert not _bar(fig, 0)["has_text"] and _bar(fig, 0)["bar_height_px"] == 1


def test_recipe_thickness_and_bar_only(tmp_path, qapp):
    import tifffile
    from pyfigures.recipe import build_figure_from_recipe
    tifffile.imwrite(tmp_path / "c.tif", np.full((80, 100), 40, np.uint8), imagej=True,
                     resolution=(4.0, 4.0), metadata={"unit": "um"})
    (tmp_path / "r.yaml").write_text(
        "output: r.pyf\n"
        "rows:\n  - - {image: c.tif, scale_bar: {units: 10, thickness: 1.5, label: \"\"}}\n", encoding="utf-8")
    build_figure_from_recipe(str(tmp_path / "r.yaml"))
    bar = _bar(str(tmp_path / "r.pyf"), 0)
    assert bar["bar_height_px"] == 1.5 and not bar["has_text"] and float(bar["bar_width_in_units"]) == 10


def test_a_new_bar_needs_a_length_and_a_sane_thickness(fig):
    from pyfigures.mcp_server import set_scale_bar
    reply = set_scale_bar(fig, [0], 1, placement="bottom left")
    assert reply.startswith("ERROR") and "bar_width_in_units" in reply
    assert set_scale_bar(fig, [0], 1, 10, bar_height_px=0).startswith("ERROR")
    assert "No scale bar" in __import__("pyfigures.mcp_server", fromlist=["x"]).get_scale_bar(fig, [0], 1)


def test_the_figure_draws_the_thickness_and_no_text(fig, qapp, tmp_path):
    """Rendered: the white bar is as thick as asked, and nothing else is white."""
    from PIL import Image
    from pyfigures.mcp_server import set_scale_bar, export_figure

    def white_rows(thickness, label):
        set_scale_bar(fig, [0], 1, 10, bar_height_px=thickness, label=label)
        out = str(tmp_path / f"out_{thickness}_{bool(label)}.png")
        reply = export_figure(fig, out)
        assert os.path.isfile(out), reply
        pixels = np.asarray(Image.open(out).convert("L"))
        right = pixels[:, pixels.shape[1] // 2:]              # the calibrated panel
        return int((right > 250).any(axis=1).sum())

    thin = white_rows(2, "")
    thick = white_rows(8, "")
    with_text = white_rows(8, "10 µm")
    assert 0 < thin < thick                 # a thicker bar
    assert thick < with_text                # the text adds white rows above the bar
    assert thick >= 3 * thin
