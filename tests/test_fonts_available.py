"""list_fonts lists the fonts that can be used; the journal check reports the
font each text is really drawn and exported in, not only the one requested."""
import json
import os

import numpy as np
import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import mcp_server as M


@pytest.fixture(scope="module")
def fonts():
    return json.loads(M.list_fonts())


def _figure(tmp_path, font):
    src = str(tmp_path / "a.png")
    Image.fromarray(np.zeros((40, 60, 3), np.uint8)).save(src)
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="canvas")
    M.add_image(pyf, [], src, label="a")
    M.set_figure_properties(pyf, font_family=font)
    return pyf


def _font_line(pyf):
    report = M.check_journal_compliance(pyf, "cell")
    return next(line for line in report.splitlines() if "sans-serif font" in line)


def test_list_fonts_lists_the_installed_families(fonts):
    assert fonts["count"] == len(fonts["installed_families"]) > 1
    assert "DejaVu Sans" in fonts["installed_families"]          # always loaded by PyFigures
    assert not any(f.startswith("@") for f in fonts["installed_families"])
    assert fonts["installed_families"] == sorted(fonts["installed_families"], key=str.lower)


def test_list_fonts_query_filters_by_name():
    hits = json.loads(M.list_fonts("dejavu"))
    assert hits["query"] == "dejavu"
    assert hits["installed_families"] and all("dejavu" in f.lower() for f in hits["installed_families"])
    assert json.loads(M.list_fonts("no-such-font-xyz"))["count"] == 0


def test_journal_check_names_the_font_a_missing_one_is_exported_in(tmp_path, fonts):
    pyf = _figure(tmp_path, "NoSuchFontXyz")
    line = _font_line(pyf)
    assert "'NoSuchFontXyz' (not installed here: drawn and exported as '" in line, line


def test_journal_check_installed_font_is_reported_as_is(tmp_path):
    line = _font_line(_figure(tmp_path, "DejaVu Sans"))
    assert "[ok]" in line and "'DejaVu Sans'" in line and "not installed" not in line, line


def test_journal_check_helvetica_says_what_it_really_is(tmp_path, fonts):
    line = _font_line(_figure(tmp_path, "Helvetica"))
    if fonts["has_true_helvetica"]:
        assert "not installed" not in line, line
    else:
        assert f"exported as '{fonts['helvetica_resolves_to']}'" in line, line


def test_journal_check_fails_a_serif_font(tmp_path, fonts):
    if "Times New Roman" not in fonts["installed_families"]:
        pytest.skip("Times New Roman is not installed")
    line = _font_line(_figure(tmp_path, "Times New Roman"))
    assert "[FAIL]" in line, line
