"""Main-window workflows that go through several dialogs: the figure caption,
LaTeX export with that caption, the review round trip (export HTML -> email
draft -> import a reviewer's comments), closing with unsaved changes, and the
"which series?" picker for multi-series files.

Dialogs are answered by patching the Qt static helpers; nothing is shown and
no mail client or file manager is opened.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import QEvent
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import QDialog, QInputDialog, QListWidget, QMessageBox, QPushButton

from test_gui_more_actions import ui, gui  # noqa: E402,F401  (fixtures)


@pytest.fixture
def saved(gui, tmp_path):
    out = str(tmp_path / "saved.pyf")
    assert gui.save_pyfigures(file=out)
    return out


def _answers(monkeypatch, text=(), multiline=()):
    text, multiline = list(text), list(multiline)
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: text.pop(0) if text else ("", False)))
    monkeypatch.setattr(QInputDialog, "getMultiLineText",
                        staticmethod(lambda *a, **k: multiline.pop(0) if multiline else ("", False)))


# ---------------------------------------------------------------------------
# figure caption
# ---------------------------------------------------------------------------

def test_caption_needs_a_saved_figure(gui, ui):
    gui.current_file = None
    gui.figure_caption_action()
    assert ui["msg"][-1][1] == "Save the figure first"


def test_caption_set_then_prefilled(gui, saved, monkeypatch):
    from pyfigures.mcp_server import get_figure_caption
    _answers(monkeypatch, text=[("Figure 2", True)], multiline=[("Cells divide.", True)])
    gui.figure_caption_action()
    d = json.loads(get_figure_caption(saved))
    assert d["title"] == "Figure 2" and d["caption"] == "Cells divide."
    assert "caption saved" in gui.statusBar().currentMessage().lower()
    seen = {}

    def get_text(*a, **k):
        seen["title"] = k.get("text")
        return ("", False)                                 # then cancel
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(get_text))
    gui.figure_caption_action()
    assert seen["title"] == "Figure 2"                    # the dialog opens on the stored title
    assert json.loads(get_figure_caption(saved))["caption"] == "Cells divide."   # cancel kept it


def test_caption_cancel_on_text_keeps_old(gui, saved, monkeypatch):
    from pyfigures.mcp_server import get_figure_caption, set_figure_caption
    set_figure_caption(saved, "old text", title="T")
    _answers(monkeypatch, text=[("New title", True)], multiline=[("", False)])
    gui.figure_caption_action()
    assert json.loads(get_figure_caption(saved))["caption"] == "old text"


@pytest.mark.parametrize("include", [True, False])
def test_latex_export_offers_the_stored_caption(gui, saved, monkeypatch, tmp_path, include):
    from pyfigures.gui import pfgui
    from pyfigures.mcp_server import set_figure_caption
    set_figure_caption(saved, "Scale bar 10 um.", title="Figure 3")
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: asked.append(a[1]) or
                                     (QMessageBox.Yes if include else QMessageBox.No)))
    out = str(tmp_path / "fig_latex.pdf")
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out)
    gui.export_as_latex()
    assert asked == ["Include caption?"]
    tex = next(os.path.join(str(tmp_path), f) for f in os.listdir(str(tmp_path)) if f.endswith("_tex"))
    body = open(tex, encoding="utf-8").read()
    assert ("\\caption" in body and "Scale bar 10 um." in body) == include


# ---------------------------------------------------------------------------
# review round trip
# ---------------------------------------------------------------------------

def test_review_export_email_draft_and_import(gui, saved, monkeypatch, tmp_path, ui):
    from pyfigures.gui import pfgui
    import pyfigures.gui.review as review
    html = str(tmp_path / "for_review.html")
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: html)
    _answers(monkeypatch, text=[("  me@lab.org ", True), ("rev1@x.org, rev2@y.org", True)])
    monkeypatch.setattr(gui, "_review_send_choice", lambda path: "mail")
    opened, revealed = [], []
    monkeypatch.setattr(pfgui.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString())))
    monkeypatch.setattr(review, "reveal_in_file_manager", lambda p: revealed.append(p))
    gui.export_for_review()
    assert os.path.isfile(html) and gui._review_owner_email == "me@lab.org"
    assert opened and opened[0].startswith("mailto:") and "rev1" in opened[0] and "rev2" in opened[0]
    assert revealed == [html]
    assert ui["msg"][-1][1] == "Almost done"
    data = review.html_export._COMMENT_BLOCK_RE.search(open(html, encoding="utf-8").read()).group(1)
    assert json.loads(data)["owner_email"] == "me@lab.org"

    # the reviewer pins a comment in their browser and sends the file back
    reviewed = str(tmp_path / "reviewed.html")
    payload = json.dumps({"comments": [{"x": 0.25, "y": 0.5, "text": "Panel B too dark", "author": "rev1",
                                        "ts": "2026-10-08T10:00"}], "author": "rev1", "owner_email": "me@lab.org"})
    text = open(html, encoding="utf-8").read()
    text = review.html_export._COMMENT_BLOCK_RE.sub(
        lambda m: m.group(0).replace(m.group(1), payload), text)
    open(reviewed, "w", encoding="utf-8").write(text)
    shown = []
    monkeypatch.setattr(review, "show_review_comments_dialog",
                        lambda parent, png, comments, on_clear=None: shown.append((os.path.isfile(png), comments)))
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda *a, **k: reviewed)
    gui.import_review_comments()
    gui.import_review_comments()                              # importing twice adds nothing
    assert review.load_sidecar_comments(saved) and len(review.load_sidecar_comments(saved)) == 1
    assert shown[-1][0] and shown[-1][1][0]["text"] == "Panel B too dark"


def test_review_export_declining_email_stops_there(gui, saved, monkeypatch, tmp_path):
    from pyfigures.gui import pfgui
    html = str(tmp_path / "r.html")
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: html)
    _answers(monkeypatch, text=[("", False)])
    monkeypatch.setattr(gui, "_review_send_choice", lambda path: None)
    opened = []
    monkeypatch.setattr(pfgui.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url)))
    gui.export_for_review()
    assert os.path.isfile(html) and opened == []


def test_review_export_copies_a_ready_message(gui, saved, monkeypatch, tmp_path, ui):
    """22 Oct report: 'Send by email' opened Outlook, which the user does not
    use; a ready message can be copied for any mail or chat instead."""
    from pyfigures.gui import pfgui
    import pyfigures.gui.review as review
    from qtpy.QtWidgets import QApplication
    html = str(tmp_path / "c.html")
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: html)
    _answers(monkeypatch, text=[("", False)])
    monkeypatch.setattr(gui, "_review_send_choice", lambda path: "copy")
    monkeypatch.setattr(review, "reveal_in_file_manager", lambda p: None)
    opened = []
    monkeypatch.setattr(pfgui.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url)))
    gui.export_for_review()
    text = QApplication.clipboard().text()
    assert opened == [] and "Figure review" in text and "c.html" in text
    assert ui["msg"][-1][1] == "Message copied"


def test_review_regions_and_whole_figure_comments_round_trip(tmp_path):
    """Reviewers can comment on a drawn region and on the whole figure (only
    point comments existed)."""
    import pyfigures.gui.review as review
    from PIL import Image
    png = str(tmp_path / "f.png")
    Image.new("RGB", (40, 30), "white").save(png)
    seed = [{"x": None, "y": None, "general": True, "text": "Nice overall", "author": "r"},
            {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4, "text": "this region", "author": "r", "ts": "t"}]
    out = str(tmp_path / "r.html")
    open(out, "w", encoding="utf-8").write(review.build_review_html(png, "f", comments=seed))
    html = open(out, encoding="utf-8").read()
    assert "Copy my comments" in html and 'id="general"' in html and "Comment on this region" in html
    back = review.extract_comments(out)
    assert back[0]["general"] and back[0]["text"] == "Nice overall"
    assert back[1]["w"] == 0.3 and back[1]["text"] == "this region"
    merged = review.merge_comments([], back)
    assert len(review.merge_comments(merged, back)) == 2          # no duplicates, no crash on x=None


def test_import_review_rejects_a_foreign_html(gui, saved, monkeypatch, tmp_path, ui):
    from pyfigures.gui import pfgui
    other = tmp_path / "other.html"
    other.write_text("<html><body>hello</body></html>", encoding="utf-8")
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda *a, **k: str(other))
    gui.import_review_comments()
    assert ui["msg"][-1][1] == "Import failed"
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda *a, **k: None)
    gui.import_review_comments()                              # cancelled picker: nothing happens
    assert ui["msg"][-1][1] == "Import failed"


def test_import_review_needs_a_saved_figure(gui, ui):
    gui.current_file = None
    gui.import_review_comments()
    assert ui["msg"][-1][1] == "No figure open"


# ---------------------------------------------------------------------------
# closing with unsaved changes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("answer,closes", [("Cancel", False), ("Discard", True)])
def test_close_with_unsaved_changes(gui, monkeypatch, answer, closes):
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: getattr(QMessageBox, answer)))
    gui._dirty = True
    ev = QCloseEvent()
    gui.closeEvent(ev)
    assert ev.isAccepted() == closes
    if not closes:
        assert gui._dirty                                       # still there, nothing lost


def test_close_with_unsaved_changes_save_writes_file(gui, monkeypatch, saved):
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Save))
    gui._dirty = True
    os.remove(saved)
    ev = QCloseEvent()
    gui.closeEvent(ev)
    assert ev.isAccepted() and os.path.isfile(saved) and not gui._dirty


# ---------------------------------------------------------------------------
# multi-series picker
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("button,row,expected", [("Open", 2, 2), ("Skip file", 1, None)])
def test_series_dialog(gui, monkeypatch, button, row, expected):
    seen = {}

    def fake_exec(dlg, *a, **k):
        lw = dlg.findChild(QListWidget)
        seen["items"] = [lw.item(i).text() for i in range(lw.count())]
        lw.setCurrentRow(row)
        next(b for b in dlg.findChildren(QPushButton) if b.text() == button).click()
        return dlg.result()
    monkeypatch.setattr(QDialog, "exec_", fake_exec, raising=False)
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    got = gui._show_series_dialog(os.path.join("x", "multi.lif"), ["s0", "s1", "s2"])
    assert seen["items"] == ["[0] s0", "[1] s1", "[2] s2"]
    assert got == expected
