"""Unsaved changes are recalled from time to time, with the chat's recovery
folder: a figure built in the chat was closed with no idea where it went
(2026-11-03)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def gui(qapp, monkeypatch):
    from pyfigures.gui import pfgui
    pfgui.EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(pfgui, "_nobody_to_ask", lambda: False)    # a person is there
    g = pfgui.EZFIG_GUI()
    g.show()
    yield g
    g._dirty = False


def test_unsaved_changes_are_recalled_every_ten_minutes(gui):
    gui._mark_dirty()
    start = gui._dirty_since
    assert gui._save_reminder_timer.isActive()
    assert gui._save_reminder_tick(start + 60) is None                # too soon
    box = gui._save_reminder_tick(start + 601)
    assert box is not None and "Unsaved changes for 10 min" in box.label.text()
    assert "never been saved" in box.label.text() and "recovery" not in box.label.text()
    assert gui._save_reminder_tick(start + 700) is None               # not again for 10 minutes
    assert gui._save_reminder_tick(start + 1202) is not None
    box.dont.setChecked(True)                                         # "Don't show this again"
    assert gui._save_reminder_tick(start + 2000) is None
    gui._save_reminders_off = False
    gui._mark_clean()
    assert gui._save_reminder_tick(start + 4000) is None              # saved: nothing to recall


def test_the_reminder_and_the_quit_prompt_name_the_recovery_folder(gui, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from qtpy.QtWidgets import QMessageBox
    gui._live_session = SimpleNamespace(recovery=SimpleNamespace(folder=tmp_path))
    gui.current_file = str(tmp_path / "fig.pyf")
    gui._mark_dirty()
    box = gui._save_reminder_tick(gui._dirty_since + 601)
    assert "fig.pyf" in box.label.text() and str(tmp_path) in box.label.text()
    asked = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: asked.append(a[2]) or QMessageBox.Cancel))
    assert gui._maybe_save_before_discard("quitting") is False
    assert str(tmp_path) in asked[0]
    del gui._live_session
