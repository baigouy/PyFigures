"""2026-11-19 replay (Mistral Large 4, turns 39-40): the model wrote "200 µm" next to scale
bars of another length, and nothing said so. The text stays the user's to choose (no
refusal), but the reply now warns, and QC (audit_figure, QC > Audit figure) reports it
(user, 2026-11-20: "you should at least return a warning ... and QC should report it")."""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def fig(tmp_path):
    """A PNG (no pixel size) and an ImageJ TIFF at 0.25 µm/px, 100 px wide."""
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


def test_the_check_itself():
    from pyfigures.mcp_tools.core import scale_bar_label_mismatch as m
    assert m("200 µm", 5.0)
    assert m("10 µm", 10.0) is None
    assert m("10 um", 10.0) is None
    assert m("0.5 mm", 500.0) is None
    assert m("500 nm", 0.5) is None
    assert m("2,5 µm", 2.5) is None
    assert m("scale", 5.0) is None                   # no length named
    assert m("10 px", 5.0) is None                   # not a physical length
    assert m("200 µm", 5.0, calibrated=False) is None


def test_a_wrong_text_is_kept_and_warned(fig):
    from pyfigures.mcp_server import set_scale_bar
    out = set_scale_bar(fig, [0], 1, 5, label="200 µm")
    assert not out.startswith("ERROR"), out
    assert "WARNING" in out and "200 µm" in out and "5 µm" in out, out
    assert "200 µm" in open(fig, encoding="utf-8").read()       # kept as given


def test_a_matching_text_has_no_warning(fig):
    from pyfigures.mcp_server import set_scale_bar
    assert "WARNING" not in set_scale_bar(fig, [0], 1, 5, label="5 µm")
    assert "WARNING" not in set_scale_bar(fig, [0], 1, 5)


def test_a_new_length_under_an_old_text_is_warned(fig):
    """"make it 10 µm" on a bar whose text was given by hand: the text no longer fits."""
    from pyfigures.mcp_server import set_scale_bar
    set_scale_bar(fig, [0], 1, 5, label="5 µm")
    out = set_scale_bar(fig, [0], 1, 10, label="5 µm")
    assert "WARNING" in out, out


def test_all_bars_at_once_are_warned(fig):
    from pyfigures.mcp_server import set_scale_bar_all
    out = set_scale_bar_all(fig, 5, label="200 µm")
    assert "WARNING" in out and "calibrated.tif" in out, out
    line = next(x for x in out.splitlines() if "does not match its length" in x)
    assert "plain.png" not in line                               # no pixel size: told elsewhere


def test_qc_reports_it(fig):
    from pyfigures.mcp_server import set_scale_bar, audit_figure
    from pyfigures.gui.qc_reports import audit_report
    set_scale_bar(fig, [0], 1, 5, label="200 µm")
    raw = audit_figure(fig)
    d = json.loads(raw)
    assert len(d["scale_bars_text_mismatch"]) == 1, d["scale_bars_text_mismatch"]
    assert d["scale_bars_text_mismatch"][0]["image_index"] == 1
    assert "another length" in audit_report(raw)
    set_scale_bar(fig, [0], 1, 5, label="5 µm")
    assert json.loads(audit_figure(fig))["scale_bars_text_mismatch"] == []
