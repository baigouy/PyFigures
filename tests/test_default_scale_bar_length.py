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


@pytest.mark.parametrize("value, unit, expected", [
    (50000, "µm", (50, "mm")), (1500, "µm", (1.5, "mm")), (100, "mm", (100, "mm")),
    (150, "µm", (150, "µm")), (999, "µm", (999, "µm")), (2000, "nm", (2, "µm")),
    (5000, "px", (5000, "px")), (1500, "mm", (150, "cm")),
])
def test_at_most_three_digits(value, unit, expected):
    from pyfigures.mcp_tools.core import _readable_length
    assert _readable_length(value, unit) == (float(expected[0]), expected[1])


def test_a_chosen_length_reads_rounder():
    from pyfigures.mcp_tools.core import _readable_length
    assert _readable_length(200, "mm", rounder=True) == (20.0, "cm")
    assert _readable_length(200, "mm") == (200.0, "mm")               # as the user wrote it


def test_a_large_image_gets_mm_not_thousands_of_um():
    length, unit = _default_bar_length(300000)          # a 30 cm wide CT slice, in µm
    assert unit in ("mm", "cm") and length < 1000


def test_the_length_asked_for_is_kept_exactly(tmp_path, qapp):
    """A user length is never changed, only written shorter: 50000 µm is 50 mm."""
    import xml.etree.ElementTree as ET
    from PIL import Image
    src = tmp_path / "ct.png"
    Image.new("L", (600, 400), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    M.add_image(str(pyf), [0], str(src))
    M.set_scale_bar(str(pyf), [0], 0, 50000, px_to_unit=500)       # 0.5 mm per pixel, in µm
    M.set_scale_bar(str(pyf), [0], 1, 12, px_to_unit=0.1)          # 12 µm: as asked, not 10 or 15
    labels = [json.loads(M.get_scale_bar(str(pyf), [0], i))["label_plain"] for i in (0, 1)]
    assert labels == ["50 mm", "12 µm"]
    # the user's own wording, when they want it, and a tiny bar: done, with a warning only
    reply = M.set_scale_bar(str(pyf), [0], 0, 1000, label="1000 µm", px_to_unit=500)
    assert not reply.startswith("ERROR") and "WARNING" in reply
    assert json.loads(M.get_scale_bar(str(pyf), [0], 0))["label_plain"] == "1000 µm"
    M.set_scale_bar(str(pyf), [0], 0, 50000, label="50000 µm")
    imgs = list(ET.parse(pyf).getroot().iter("Image2D"))
    # the same 100 px bar: 50000 µm at 500 µm per pixel, the pixel size kept in µm
    assert float(imgs[0].findtext("px_to_unit_conversion_factor")) == pytest.approx(500)
    assert float(imgs[0].find("annotations/ScaleBar").findtext("bar_width_in_units")) == pytest.approx(50000)


def test_the_audit_flags_a_bar_of_a_few_percent(tmp_path, qapp):
    from PIL import Image
    from pyfigures.gui.qc_reports import audit_report
    src = tmp_path / "i.png"
    Image.new("L", (1000, 600), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    M.add_image(str(pyf), [0], str(src))
    M.set_scale_bar(str(pyf), [0], 0, 2, px_to_unit=0.1)           # 20 px of 1000: 2 %
    M.set_scale_bar(str(pyf), [0], 1, 15, px_to_unit=0.1)          # 150 px: 15 %
    raw = M.audit_figure(str(pyf))
    small = json.loads(raw)["scale_bars_too_small"]
    assert [(e["image_index"], e["percent"], e["suggested"]) for e in small] == [(0, 2.0, "15 µm")]
    assert "very small" in audit_report(raw)


def test_the_audit_lists_images_without_pixel_size_but_not_plots(tmp_path, qapp):
    from PIL import Image
    from pyfigures.gui.qc_reports import audit_report
    src = tmp_path / "plain.png"
    Image.new("L", (300, 200), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    M.add_image(str(pyf), [0], str(src))
    M.set_scale_bar(str(pyf), [0], 1, 10, px_to_unit=0.1)          # this one has a pixel size
    M.add_scripted_image(str(pyf), [0], "import matplotlib.pyplot as plt\nself.img = plt.figure(figsize=(2, 2))")
    raw = M.audit_figure(str(pyf))
    assert [e["image_index"] for e in json.loads(raw)["images_without_pixel_size"]] == [0]
    assert "no pixel size" in audit_report(raw)


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
