"""A scale bar asked for without a length gets a round one of about 15 % of the
image width: local models asked for the length again and again (live replay,
2026-11-15). The user wants 10, 15, 20 ... rather than 12 or 14."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")
from pyfigures.mcp_tools.core import _default_bar_length  # noqa: E402


@pytest.mark.parametrize("width, expected", [
    (100, (15, "µm")), (51.2, (10, "µm")), (400, (50, "µm")), (130, (20, "µm")),
    (1000, (150, "µm")), (2048, (300, "µm")), (8, (1, "µm")), (2, (300, "nm")),
])
def test_round_lengths_of_ten_to_25_percent(width, expected):
    length, unit = _default_bar_length(width)
    assert (length, unit) == (float(expected[0]), expected[1])
    shown = width * (1000 if unit == "nm" else 1)
    assert length == int(length) and 0.10 <= length / shown <= 0.25 or width < 4.1
    assert int(length) not in (12, 14)


def test_unknown_width_gives_no_length():
    assert _default_bar_length(0) is None


def test_a_bar_without_length_is_added_not_asked(tmp_path, qapp):
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("L", (512, 300), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    M.add_image(str(pyf), [0], str(src))
    reply = M.set_scale_bar(str(pyf), [0], 0, px_to_unit=0.2)       # 102.4 µm wide
    assert not reply.startswith("ERROR") and "No length was given" in reply
    assert json.loads(M.get_scale_bar(str(pyf), [0], 0))["label_plain"] == "15 µm"
    # uncalibrated: a round length in pixels, flagged as not calibrated
    reply = M.set_scale_bar(str(pyf), [0], 1)
    assert "No length was given: 100 px" in reply and "not µm" in reply
