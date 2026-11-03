"""The guided-tutorial machinery itself (test_tutorials.py checks the step
lists): the hint bubble's Next / Prev / Exit buttons, step completion and
auto-advance, skipping steps already done, the dimmed overlay with its
highlighted target, dragging the bubble, and the hint embedded into the
panel editor dialog while a tutorial runs.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import Qt, QPoint, QPointF, QEvent, QRect
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QApplication, QDialog, QLabel

from pyfigures.gui import tutorial as T
from test_tutorials import gui, _TUTORIALS  # noqa: E402,F401  (fixture)


@pytest.fixture
def win(gui, qapp):
    gui.resize(1200, 800)
    gui.show()
    qapp.processEvents()
    yield gui
    gui._tutorial.stop()


def _process(n=5):
    for _ in range(n):
        QApplication.processEvents()


def _steps(n, checks=None, auto=True):
    checks = checks or {}
    return [T.TutorialStep(f"Step title {i}", f"message {i}", completion_check=checks.get(i),
                           auto_advance=auto) for i in range(n)]


def counter(ctrl):
    return ctrl._bubble._counter.text()


def test_start_shows_overlay_and_bubble(win):
    ctrl = win._tutorial
    win.start_beginner_tutorial()
    _process()
    assert ctrl._overlay.isVisible() and ctrl._bubble.isVisible()
    assert counter(ctrl).startswith(f"Step {ctrl._index + 1} of {len(ctrl._steps)}")
    assert ctrl._bubble._title.text() == ctrl._steps[ctrl._index].title
    assert ctrl._poll.isActive()
    # the bubble sits inside the window, bottom-right
    b = ctrl._bubble.geometry()
    assert b.right() <= win.width() and b.bottom() <= win.height()


def test_next_prev_exit_buttons(win):
    ctrl = win._tutorial
    ctrl.start(_steps(4))
    assert ctrl._index == 0 and not ctrl._bubble._btn_prev.isEnabled()
    ctrl._bubble._btn_next.click()
    ctrl._bubble._btn_next.click()
    assert ctrl._index == 2 and counter(ctrl) == "Step 3 of 4"
    ctrl._bubble._btn_prev.click()
    assert ctrl._index == 1 and ctrl._bubble._btn_prev.isEnabled()
    ctrl._bubble._btn_skip.click()
    assert not ctrl._overlay.isVisible() and not ctrl._bubble.isVisible() and not ctrl._poll.isActive()


def test_last_step_button_finishes(win):
    ctrl = win._tutorial
    ctrl.start(_steps(2))
    ctrl._bubble._btn_next.click()
    assert ctrl._bubble._btn_next.text() == "Finish"
    ctrl._bubble._btn_next.click()
    assert not ctrl._bubble.isVisible()


def test_completion_marks_done_then_auto_advances(win):
    ctrl = win._tutorial
    state = {"done": False}
    ctrl.start(_steps(3, checks={0: lambda w: state["done"]}))
    ctrl._check_completion()
    assert not ctrl._done_flag and ctrl._bubble._done_label.isHidden()
    state["done"] = True
    ctrl._check_completion()
    assert ctrl._done_flag and not ctrl._bubble._done_label.isHidden()
    assert ctrl._auto_timer.isActive()
    ctrl._auto_timer.timeout.emit()                       # 1.2 s later
    assert ctrl._index == 1 and not ctrl._done_flag


def test_no_auto_advance_when_disabled(win):
    ctrl = win._tutorial
    ctrl.start(_steps(3, checks={0: lambda w: False}, auto=False))
    ctrl._steps[0].completion_check = lambda w: True
    ctrl._check_completion()
    assert ctrl._done_flag and not ctrl._auto_timer.isActive() and ctrl._index == 0


def test_failing_check_is_ignored(win):
    ctrl = win._tutorial

    def boom(w):
        raise RuntimeError("check bug")
    ctrl.start(_steps(2, checks={0: boom}))
    ctrl._check_completion()                              # must not raise
    assert not ctrl._done_flag


def test_steps_already_done_are_skipped(win):
    ctrl = win._tutorial
    ctrl.start(_steps(4, checks={0: lambda w: True, 1: lambda w: True, 2: lambda w: False}))
    assert ctrl._index == 2


def test_on_show_runs_when_step_is_entered(win):
    ctrl = win._tutorial
    seen = []
    steps = _steps(2)
    steps[1].on_show = lambda w: seen.append(w)
    ctrl.start(steps)
    assert seen == []
    ctrl._next()
    assert seen == [win]


def test_overlay_highlights_the_target(win):
    ctrl = win._tutorial
    steps = _steps(2)
    steps[0].get_target = lambda w: w.paint
    ctrl.start(steps)
    _process()
    rect = ctrl._target_rect()
    assert isinstance(rect, QRect) and rect.width() > 0 and rect.height() > 0
    img = ctrl._overlay.grab().toImage()                  # runs paintEvent
    inside = img.pixelColor(rect.center().x(), rect.center().y())
    outside = img.pixelColor(2, 2) if not rect.contains(2, 2) else img.pixelColor(img.width() - 3, img.height() - 3)
    assert inside.alpha() < outside.alpha() or inside != outside   # target cut out of the dim layer
    ctrl._overlay.set_target(rect, done=True)             # the "done" (green) frame paints too
    assert not ctrl._overlay.grab().toImage().isNull()


def test_resize_keeps_overlay_full_window(win, qapp):
    ctrl = win._tutorial
    ctrl.start(_steps(2))
    win.resize(900, 650)
    _process()
    ctrl.handle_resize()
    assert ctrl._overlay.size() == win.size()


def _drag(target, start, end, via_filter_of=None):
    for t, pos, held in ((QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton),
                         (QEvent.Type.MouseMove, end, Qt.MouseButton.LeftButton),
                         (QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)):
        btn = Qt.MouseButton.NoButton if t == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        ev = QMouseEvent(t, QPointF(0, 0), QPointF(pos), btn, held, Qt.KeyboardModifier.NoModifier)
        if via_filter_of is not None:
            via_filter_of.eventFilter(target, ev)
        else:
            {QEvent.Type.MouseButtonPress: target.mousePressEvent, QEvent.Type.MouseMove: target.mouseMoveEvent,
             QEvent.Type.MouseButtonRelease: target.mouseReleaseEvent}[t](ev)


def test_bubble_can_be_dragged(win):
    ctrl = win._tutorial
    ctrl.start(_steps(2))
    b = ctrl._bubble
    p0 = b.pos()
    _drag(b, QPoint(500, 500), QPoint(400, 450))
    assert b.pos() == p0 + QPoint(-100, -50)
    title = b._title                                       # dragging by the text also works
    p1 = b.pos()
    _drag(title, QPoint(300, 300), QPoint(320, 310), via_filter_of=b)
    assert b.pos() == p1 + QPoint(20, 10)


def test_hint_is_embedded_in_the_panel_editor_dialog(win, qapp, monkeypatch):
    ctrl = win._tutorial
    ctrl.start(_steps(2))
    monkeypatch.setattr(T._DialogInjector, "_is_annotation_editor_dialog", staticmethod(lambda d: True))
    dlg = QDialog(win)
    dlg.resize(700, 500)
    dlg.show()
    t0 = time.time()
    while id(dlg) not in ctrl._dialog_injector._hints and time.time() - t0 < 3:
        qapp.processEvents()
        time.sleep(0.01)
    hint = ctrl._dialog_injector._hints.get(id(dlg))
    assert hint is not None and hint.parent() is dlg
    assert any(ctrl._steps[0].title in lab.text() for lab in hint.findChildren(QLabel))
    g = hint.geometry()
    assert g.right() <= dlg.width() and g.bottom() <= dlg.height()
    # the hint can be moved by its title, but stays inside the dialog
    title = hint.findChildren(QLabel)[0]
    _drag(title, QPoint(100, 100), QPoint(-5000, -5000), via_filter_of=hint)
    assert hint.pos() == QPoint(0, 0)
    dlg.resize(800, 600)
    _process()
    dlg.hide()
    _process()
    assert id(dlg) not in ctrl._dialog_injector._hints


def test_no_hint_for_other_dialogs_or_when_stopped(win, qapp):
    ctrl = win._tutorial
    ctrl.start(_steps(2))
    dlg = QDialog(win)                                     # not the panel editor
    dlg.show()
    t0 = time.time()
    while time.time() - t0 < 0.4:
        qapp.processEvents()
        time.sleep(0.01)
    assert id(dlg) not in ctrl._dialog_injector._hints
    dlg.hide()
    ctrl.stop()
    ctrl._dialog_injector._inject(dlg)                     # bubble hidden: nothing injected
    assert id(dlg) not in ctrl._dialog_injector._hints


# ---------------------------------------------------------------------------
# skipping steps: "Set it up for me" must always unblock the next step
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_win(qapp, monkeypatch, tmp_path):
    """A window with NO figure — the user skips straight through."""
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from batoolset.GUI.customdialog import CustomDialog
    EZFIG_GUI.show_tips = lambda self: None
    for kind in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    monkeypatch.setattr(CustomDialog, "exec", lambda self, *a, **k: QDialog.Accepted)
    monkeypatch.setattr(CustomDialog, "exec_", lambda self, *a, **k: QDialog.Accepted, raising=False)
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: str(tmp_path / "tuto.pyf"))
    monkeypatch.setattr(T, "_DEMO_DIR", [str(tmp_path / "samples")])
    os.makedirs(str(tmp_path / "samples"))
    g = EZFIG_GUI()
    g.resize(1200, 800)
    g.show()
    qapp.processEvents()
    yield g
    g._tutorial.stop()
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def _wait(qapp, cond, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _walk_with_setups(ctrl, qapp, win, on_step=None):
    """Skip every step; where the step is blocked, press "Set it up for me"."""
    blocked = []
    while ctrl._bubble.isVisible():
        step = ctrl._current_step()
        if ctrl._missing:
            assert not ctrl._bubble._needs_label.isHidden(), step.title
            if step.prepare is not None:
                assert not ctrl._bubble._btn_prepare.isHidden(), step.title
                ctrl._bubble._btn_prepare.click()
                ok = _wait(qapp, lambda: step.requires(win))
                assert ok, f"'Set it up for me' did not satisfy: {step.title}"
                ctrl._check_completion()
                assert ctrl._bubble._needs_label.isHidden(), step.title
            else:
                blocked.append(step.title)
        if on_step is not None:
            on_step(step)
        ctrl._bubble._btn_next.click()
        _process(3)
    return blocked


@pytest.mark.parametrize("name", list(_TUTORIALS))
def test_skipping_every_step_never_blocks(empty_win, qapp, name):
    ctrl = empty_win._tutorial
    ctrl.start(_TUTORIALS[name]())
    blocked = _walk_with_setups(ctrl, qapp, empty_win)
    # only a step that edits what a previous step made may need "Prev"
    assert all("Edit the script" in t for t in blocked), blocked


@pytest.mark.parametrize("steps, first, row", [(T.beginner_steps, "Step 1 —", "Step 2 —"),
                                                (T.advanced_steps, "Step 1 —", "Step 6 —")])
def test_row_setup_reuses_the_image_already_dropped(empty_win, qapp, steps, first, row):
    """"Set it up for me" on the first step drops ONE image; on the row step
    it must build the row from that image plus a sample, not leave it alone
    beside a separate row of two new samples."""
    from batoolset.drawings.shapes.image2d import Image2D
    win = empty_win
    all_steps = steps()
    step1 = next(s for s in all_steps if s.title.startswith(first))
    step_row = next(s for s in all_steps if s.title.startswith(row))
    step1.prepare(win)
    assert _wait(qapp, lambda: T._lone_image(win) is not None)
    dropped = T._lone_image(win).filename
    assert not step_row.requires(win)
    step_row.prepare(win)
    assert _wait(qapp, lambda: step_row.requires(win))
    shapes = win.paint.EZFIG_panel.shapes_to_draw
    assert not any(isinstance(s, Image2D) for s in shapes)          # nothing left alone
    assert len(T._groups(win)) == 1
    files = [c.filename for c in T._groups(win)[0].content]
    assert len(files) == 2 and files[0] == dropped


def _sample_paths(text):
    import html
    import re
    return [html.unescape(p) for p in re.findall(r"<code>(.*?)</code>", text)]


@pytest.mark.parametrize("name", list(_TUTORIALS))
def test_sample_files_buttons_write_usable_files(empty_win, qapp, name):
    """Steps whose dialog asks for files the user may not have (a CSV, a
    recipe, another figure, a reviewed copy…) offer "Give me sample files":
    the files exist and are the kind the dialog reads."""
    import json
    from pyfigures.gui.review.html_export import extract_comments
    from pyfigures.recipe import build_figure_from_recipe
    from pyfigures.mcp_tools.export import index_figures, search_figures
    win = empty_win
    ctrl = win._tutorial
    ctrl.start(_TUTORIALS[name]())
    seen = []

    def on_step(step):
        if step.samples is None:
            return
        assert not ctrl._bubble._btn_samples.isHidden(), step.title
        ctrl._bubble._btn_samples.click()
        _process(3)
        text = ctrl._bubble._samples_label.text()
        assert not ctrl._bubble._samples_label.isHidden() and "Could not" not in text, (step.title, text)
        paths = _sample_paths(text)
        assert paths and all(os.path.exists(p) for p in paths), (step.title, text)
        p = paths[0]
        if p.endswith(".csv"):
            head = open(p, encoding="utf-8").readline().strip().split(",")
            assert len(head) == 3
        elif p.endswith(".yaml"):
            assert os.path.isfile(build_figure_from_recipe(p)["output"])
        elif p.endswith(".html"):
            assert len(extract_comments(p)) == 2
        elif p.endswith(".pyf"):
            assert os.path.getsize(p) > 0
        elif "library" in p:
            idx = os.path.join(p, "index.json")
            index_figures(p, idx)
            assert "actin_staining" in search_figures("actin", idx)
        seen.append(step.title)

    _walk_with_setups(ctrl, qapp, win, on_step=on_step)
    expected = {"publication": 1, "sharing": 3, "stacks": 1, "automation": 5}.get(name, 0)
    assert len(seen) == expected, seen


def test_stack_steps_really_work_on_the_samples(empty_win, qapp):
    """Run each Stack views action on the sample stacks (dialogs accepted
    with their defaults) and check the tutorial sees the step as done."""
    win = empty_win
    ctrl = win._tutorial
    ctrl.start(T.stacks_steps())
    actions = {
        "Step 3 — Channel split": win.add_channel_split_action,
        "Step 4 — Montage of frames": win.add_stack_montage_action,
        "Step 5 — Kymograph": win.add_kymograph_action,
        "Step 6 — Orthogonal views": win.add_orthogonal_views_action,
    }
    done = []
    while ctrl._bubble.isVisible():
        step = ctrl._current_step()
        if step.prepare is not None and (ctrl._missing or step.title in actions):
            step.prepare(win)                  # also selects the right panel
            assert _wait(qapp, lambda: step.requires(win) and win.paint.EZFIG_panel.selected_shape is not None
                         if step.title in actions else step.requires(win)), step.title
        if step.title in actions:
            n0 = T._n_images(win)
            step.completion_check(win)         # baseline
            actions[step.title]()
            assert _wait(qapp, lambda: T._n_images(win) > n0), f"{step.title}: nothing added"
            assert step.completion_check(win), step.title
            done.append(step.title)
        if step.title.startswith("Step 2 — Project"):
            z = T._panels(win, T._is_z_panel)[0]
            z.projection = "max"
            assert step.completion_check(win)
        ctrl._bubble._btn_next.click()
        _process(3)
    assert sorted(done) == sorted(actions)


def test_template_fill_check_needs_a_real_fill(empty_win, qapp):
    """Skipping "Convert to template" must not make "Fill the template" pass."""
    win = empty_win
    check = T._make_template_filled_check()
    T._prep_row(2)(win)
    assert _wait(qapp, lambda: T._has_real_image(win))
    assert check(win) is False                 # baseline: no slot
    assert check(win) is False                 # a figure that never was a template
    win.templatify_figure()
    assert _wait(qapp, lambda: T._has_template_slot(win))
    assert check(win) is False                 # slots appeared: new baseline
    slot = T._template_slots(win)[0]
    slot.filename = T._demo_image_paths(1)[0]  # what "Assign to template slot" does
    assert check(win) is True


def test_prev_then_next_re_arms_stateful_checks(win):
    ctrl = win._tutorial
    state = {"v": 0}
    check = T._make_count_increase_check(lambda w: state["v"])
    steps = _steps(3)
    steps[1].completion_check = check
    steps[1].auto_advance = False
    ctrl.start(steps)
    ctrl._next()
    ctrl._check_completion()                   # baseline 0
    state["v"] = 1
    ctrl._check_completion()
    assert ctrl._done_flag
    ctrl._prev()
    ctrl._next()                               # re-entered: baseline is now 1
    ctrl._check_completion()
    assert not ctrl._done_flag
    state["v"] = 2
    ctrl._check_completion()
    assert ctrl._done_flag


# ---------------------------------------------------------------------------
# the poster tutorial, in the poster window
# ---------------------------------------------------------------------------

@pytest.fixture
def poster_win(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox, QFileDialog
    from pyfigures.poster.poster_window import PosterWindow
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Discard))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "album.pyfposter"), "")))
    monkeypatch.setattr(T, "_DEMO_DIR", [str(tmp_path / "samples")])
    os.makedirs(str(tmp_path / "samples"))
    w = PosterWindow()
    w.resize(1300, 900)
    yield w
    if getattr(w, "_tutorial", None) is not None:
        w._tutorial.stop()
    w.canvas.mark_saved()
    w.close()


def test_poster_tutorial_from_the_help_menu(qapp, monkeypatch, tmp_path):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        g.start_poster_tutorial()
        _process()
        pw = g._poster_window
        assert pw.isVisible() and pw._tutorial._bubble.isVisible()
        assert pw._tutorial._bubble._title.text().startswith("Poster")
        pw._tutorial.stop()
        pw.canvas.mark_saved()
        pw.close()
    finally:
        g._dirty = False
        g.close()


def test_chat_tutorial_from_the_help_menu(qapp, monkeypatch, tmp_path):
    """It hands the figure over to a window that can share it first (opening
    the chat from a plain window would end the tutorial halfway), then the
    chat opens in that same window and every step can be set up or skipped."""
    from qtpy.QtWidgets import QMessageBox
    import pyfigures.assistant as A
    from pyfigures.assistant import launch, session
    from pyfigures.assistant.partner_gui import PartnerGUI
    from pyfigures.gui.pfgui import EZFIG_GUI
    monkeypatch.setenv("PYFIGURES_LIVE_RUNTIME", str(tmp_path / "runtime"))
    monkeypatch.setattr(session, "STATE", tmp_path / "runtime")
    (tmp_path / "runtime").mkdir()
    monkeypatch.setattr(T, "_DEMO_DIR", [str(tmp_path / "samples")])
    os.makedirs(str(tmp_path / "samples"))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))

    def warning(parent, title, text, *a, **k):
        # a modal warning hung the whole suite (2026-11-03): fail with its text instead
        raise AssertionError(f"{title}: {text}")
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(warning))
    # the chat's own settings, not the user's saved connection (read by Config.load)
    profile = tmp_path / "sidecar.json"
    profile.write_text(json.dumps({"application": "PyFigures", "state_dir": str(tmp_path / "sidecar_state")}))
    monkeypatch.setenv("PYFIGURES_SIDECAR_CONFIG", str(profile))
    monkeypatch.setattr(launch, "lm_studio_model", lambda: None)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    win = None
    try:
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel))
        assert g.start_chat_tutorial() is None and not g._tutorial._bubble.isVisible()
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
        win = g.start_chat_tutorial()
        _process()
        assert isinstance(win, PartnerGUI) and win._tutorial._bubble.isVisible()
        ctrl = win._tutorial

        def on_step(step):
            if "Open the chat" in step.title and A.sidecar_available():
                dock = win.open_chat_sidebar()
                assert dock is not None and dock.parent() is win
                assert step.completion_check(win), (win.isVisible(), dock.isHidden())
            if "Ask for a change" in step.title:
                # what the model's set_scale_bar_all call does, done directly
                from batoolset.drawings.shapes.image2d import Image2D
                from batoolset.drawings.shapes.scalebar import ScaleBar
                from batoolset.drawings.shapes.group import get_all_contained_images
                imgs = [i for s in win.paint.EZFIG_panel.shapes_to_draw
                        for i in ([s] if isinstance(s, Image2D) else get_all_contained_images(s))]
                imgs[0].annotations.append(ScaleBar(bar_width_in_units=10, unit_to_pixel_conversion_factor=0.1))
                assert step.completion_check(win)
        assert _walk_with_setups(ctrl, qapp, win, on_step=on_step) == []
        assert not ctrl._bubble.isVisible()
    finally:
        for w in qapp.topLevelWidgets():
            if isinstance(w, EZFIG_GUI):
                launch.stop_live_session(w)
                w._tutorial.stop()
                w._dirty = False
                w.close()
        _process()


def test_album_tutorial_from_the_help_menu(qapp, monkeypatch, tmp_path):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        g.start_album_tutorial()
        _process()
        aw = g._album_window
        assert aw.album and aw.isVisible() and aw._tutorial._bubble.isVisible()
        assert aw._tutorial._bubble._title.text() == "Photo Album tutorial"
        assert getattr(g, "_poster_window", None) is None      # a separate window
        aw._tutorial.stop()
        aw.canvas.mark_saved()
        aw.close()
    finally:
        g._dirty = False
        g.close()


def test_album_tutorial_skip_and_set_up(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox, QFileDialog
    from pyfigures.poster.poster_window import PosterWindow
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Discard))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "book.pyfalbum"), "")))
    monkeypatch.setattr(T, "_DEMO_DIR", [str(tmp_path / "samples")])
    os.makedirs(str(tmp_path / "samples"))
    w = PosterWindow(album=True)
    w.resize(1300, 900)
    try:
        w.tutorial_action.trigger()
        ctrl = w._tutorial
        titles = [s.title for s in ctrl._steps]
        assert titles[0] == "Photo Album tutorial" and titles[-1] == "Photo Album complete!"
        assert "Step 7 — Pages of the album" in titles

        def on_step(step):
            if step.title == "Step 7 — Pages of the album":
                assert not ctrl._current_step().completion_check(w)
                w._add_page("spread")
                assert ctrl._current_step().completion_check(w)
            if step.title == "Step 8 — Save":
                assert w.save_poster()
                assert ctrl._current_step().completion_check(w)
        assert _walk_with_setups(ctrl, qapp, w, on_step=on_step) == []
        assert w.canvas.album_mode and w.canvas.file_path == str(tmp_path / "book.pyfalbum")
    finally:
        if getattr(w, "_tutorial", None) is not None:
            w._tutorial.stop()
        w.canvas.mark_saved()
        w.close()


def test_poster_tutorial_skip_and_set_up(poster_win, qapp):
    w = poster_win
    w.tutorial_action.trigger()                # the toolbar's Tutorial button
    ctrl = w._tutorial
    assert ctrl._bubble.isVisible() and ctrl._index == 0
    seen = {}

    def on_step(step):
        if step.get_target is not None:
            seen[step.title] = ctrl._target_rect()
        if step.title == "Step 2 — Arrange them in one click":
            ctrl._check_completion()           # the 400 ms poll records the starting layout
            w.grid_action.trigger()
            assert ctrl._current_step().completion_check(w)
        if step.title == "Step 5 — Add a title":
            w.canvas.add_text("Hello", style="h1")
            assert ctrl._current_step().completion_check(w)
        if step.title == "Step 7 — Pages":
            w._add_page("single")
            assert ctrl._current_step().completion_check(w)
        if step.title == "Step 8 — Save":
            assert w.save_poster()
            assert ctrl._current_step().completion_check(w)
    blocked = _walk_with_setups(ctrl, qapp, w, on_step=on_step)
    assert blocked == []
    assert all(r is not None and r.width() > 0 for r in seen.values()), seen    # every target found
    first = w.canvas.pages[0]                  # step 7 moved on to a new, empty page
    assert sum(type(s).__name__ == "PosterImage" for s in first.shapes_to_draw) >= 3
    assert first.background is not None


@pytest.mark.parametrize("name", list(_TUTORIALS))
def test_click_through_every_tutorial(win, name):
    """Next through every step of each tutorial: on_show hooks, targets and
    the bubble update must all work on a real window."""
    ctrl = win._tutorial
    ctrl.start(_TUTORIALS[name]())
    n = len(ctrl._steps)
    seen = set()
    for _ in range(n + 1):
        if not ctrl._bubble.isVisible():
            break
        seen.add(ctrl._index)
        assert ctrl._bubble._title.text() == ctrl._steps[ctrl._index].title
        ctrl._check_completion()
        ctrl._bubble._btn_next.click()
        _process(2)
    assert not ctrl._bubble.isVisible()                    # Finish closed it
    assert seen and max(seen) == n - 1
