"""User report 2026-11-06: "remove letter bg" on a figure lettered per row was
done by the first call, but edit_panel_letters reported 0 changed /
NO_VISIBLE_CHANGE (it counted only letters inside panels, and listed every
panel as "No panel letter; use restore"), so the chat searched for another
tool for a minute; set_label_background then said "0 label(s)". Both now
report the row letters.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_row_letters_gui import _recipe_figure, _open  # noqa: E402


@pytest.fixture
def gui(qapp):
    """The chat's window (letter policies, verified bulk edits)."""
    from pyfigures.assistant.partner_gui import PartnerGUI
    PartnerGUI.show_tips = lambda self: None
    w = PartnerGUI()
    w.show()
    yield w
    w._dirty = False
    w._stop_all_img_loaders()
    w.close()


def test_style_on_row_letters_is_reported_as_a_change(gui, qapp, tmp_path):
    from pyfigures.assistant.session import Session
    pyf, _ = _recipe_figure(tmp_path)
    canvas = _open(gui, qapp, pyf)
    gui.serializable_font.background = 0xFFFFFF
    gui.update_letters()
    s = Session(gui, recovery_dir=tmp_path / "rec")
    try:
        report = s.bulk_letters(dict(action="style", scope="all", background="none"))["operation_result"]
    finally:
        s.timer.stop()
        s.recovery_timer.stop()
    assert gui.serializable_font.background is None
    assert report["row_letters_restyled"] == ["A", "B"]
    assert report["outcome"] == "VERIFIED_CHANGE"
    assert report["skipped"] == []
    assert [t.getPlainText() for _, t in canvas._row_letter_texts()] == ["A", "B"]


def test_row_letters_refuse_a_partial_scope(gui, qapp, tmp_path):
    pyf, _ = _recipe_figure(tmp_path)
    _open(gui, qapp, pyf)
    with pytest.raises(ValueError, match="scope=\"all\""):
        gui.edit_panel_letters(action="style", scope="group", group_path=[0], background="none")


def test_set_label_background_names_the_row_letters(tmp_path):
    from pyfigures.mcp_server import set_label_background
    pyf, _ = _recipe_figure(tmp_path)
    out = set_label_background(pyf, color="none")
    assert "0 label(s)" in out and "row letters" in out and "no box" in out
    pyf2, _ = _recipe_figure(tmp_path, name="panels", layout=None)
    assert "row letters" not in set_label_background(pyf2, color="none")
