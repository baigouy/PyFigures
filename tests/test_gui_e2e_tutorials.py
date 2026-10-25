"""Every Help tutorial run end to end (marker ``gui_e2e``).

Each tutorial is started from its Help-menu entry on an empty window. At
every step: when the step needs what an earlier step makes and it is
missing, "Set it up for me" is clicked and must provide it; then the step is
PERFORMED the way its text says — files dropped, panels dragged, menus and
dialogs used, the image editor driven — and the tutorial itself must see the
step as done (its completion check, polled by the tutorial) before Next is
clicked. Steps without a check ("look at…", "use menu X") are performed too
when they name an action. Finally every "Show me how" guide is started and
must highlight real, visible targets.
"""
from __future__ import annotations

import os
import re
import time

import pytest

import gui_e2e_harness as H
import test_gui_e2e_menus as M
from gui_e2e_harness import e2e_files, menus, no_file_dialogs, watch  # noqa: F401
from test_gui_e2e_image_editor import _draw, _open_editor_by_double_click, _tool

pytestmark = pytest.mark.gui_e2e

TUTORIAL_KEYS = {
    "menu: Help > ▶  Beginner Tutorial": "beginner",
    "menu: Help > ▶  Medium Tutorial": "medium",
    "menu: Help > ▶  Advanced Tutorial": "advanced",
    "menu: Help > ▶  Publication & QC Tutorial": "publication",
    "menu: Help > ▶  Sharing, Review & Accessibility Tutorial": "sharing",
    "menu: Help > ▶  Stacks, Channels & Movies Tutorial": "stacks",
    "menu: Help > ▶  Automate: Drafts, Recipes & Library Tutorial": "automation",
}
# the poster / album tutorials run in their own windows:
ELSEWHERE = {
    "menu: Help > ▶  Poster Tutorial": ["test_tutorial_controller.py::test_poster_tutorial_from_the_help_menu",
                                       "test_tutorial_controller.py::test_poster_tutorial_skip_and_set_up"],
    "menu: Help > ▶  Photo Album Tutorial": ["test_tutorial_controller.py::test_album_tutorial_from_the_help_menu",
                                            "test_tutorial_controller.py::test_album_tutorial_skip_and_set_up"],
}


@pytest.fixture
def win(qapp, monkeypatch, tmp_path):
    from pyfigures.gui import tutorial as T
    samples = tmp_path / "samples"
    samples.mkdir()
    monkeypatch.setattr(T, "_DEMO_DIR", [str(samples)])
    g = H.new_gui(qapp)
    g.new_fig()
    H.settle(qapp, g)
    yield g
    g._tutorial.stop()
    H.close_gui(qapp, g)


# ---------------------------------------------------------------------------
# doing what a step says
# ---------------------------------------------------------------------------

class Ctx:
    def __init__(self, qapp, g, files, answers, out, menus):
        self.qapp, self.g, self.files, self.answers, self.out, self.menus = qapp, g, files, answers, out, menus
        self.run = {"out": str(out)}
        # where "Save" lands when a step (or its set-up) saves the figure
        answers["save"] = os.path.join(str(out), "tutorial.pyf")

    def menu(self, key):
        pilot, _run = M.perform(self.qapp, self.g, self.files, self.answers, self.out, key, self.run)
        assert not pilot.unexpected, (key, pilot.unexpected)

    def drop(self, names, choice, where=None, dialogs=()):
        g = self.g
        assert H.drop_files(g, [self.files[n] for n in names], where)
        with H.dialogs() as pilot:
            for m, h in dialogs:
                pilot.expect(m, h)
            H.click_drop_choice(g, choice)
            H.settle(self.qapp, g, lambda: not pilot.queue)
        H.settle(self.qapp, g)

    def editor(self, shape, edit, nested=()):
        def annotate(dlg):
            edit(dlg.main_widget)
            self.qapp.processEvents()
            H.accept(dlg)
        with H.dialogs() as pilot:
            pilot.expect("Annotate the image", annotate)
            for m, h in nested:
                pilot.expect(m, h)
            _open_editor_by_double_click(self.qapp, self.g, shape)
            H.settle(self.qapp, self.g, lambda: not pilot.queue, timeout=20)
        assert not pilot.queue, (pilot.seen, pilot.queue)

    def right_click(self, shape, entry, dialogs=(), pos=None):
        with H.dialogs() as pilot:
            for m, h in dialogs:
                pilot.expect(m, h)
            H.right_click(self.g, self.menus, shape, pos=pos, pick=entry)
            H.settle(self.qapp, self.g, lambda: not pilot.queue)
        H.settle(self.qapp, self.g)
        assert not pilot.queue, (entry, pilot.seen)

    # what is on the canvas
    def photos(self):
        return [i for i in H.images(self.g) if not i.isText and i.filename not in (None, "@template@")]

    def row(self):
        return next(r for r in H.rows(self.g) if len(H.images(r)) > 1)

    def loose(self):
        return [s for s in H.panel(self.g).shapes_to_draw if type(s).__name__ == "Image2D" and not s.isText]


def _click(c, pos):
    H.mouse(c.g, "press", pos)
    H.mouse(c.g, "release", pos)
    H.settle(c.qapp, c.g)


def _click_until(c, target, want, tries=3):
    """Click *target* as a user does until *want* is selected (a first click
    on a panel of a row selects the row, the next one the panel)."""
    for _ in range(tries):
        if H.panel(c.g).selected_shape is want:
            return
        _click(c, H.centre(c.g, target))
    assert H.panel(c.g).selected_shape is want, (want, H.panel(c.g).selected_shape)


def _select_row(c):
    _click_empty(c)
    row = c.row()
    _click_until(c, H.images(row)[0], row)


def _click_image_in_row(c):
    row = c.row()
    img = H.images(row)[0]
    if H.panel(c.g).selected_shape is not row:
        _select_row(c)
    _click_until(c, img, img)


def _click_empty(c):
    _click(c, H.empty_point(c.g))


def _resize(c):
    from test_gui_e2e_menus import _key, _wait_timer
    from qtpy.QtCore import Qt
    H.panel(c.g).set_current_selection(None)
    c.g.size_spinbox.setValue(c.g.size_spinbox.value() - 60)
    _key(c.g.size_spinbox, Qt.Key.Key_Return)
    _wait_timer(c.qapp, c.g, c.g.value_changed_timer)


def _arrows(which, n=2):
    def do(c):
        sc = getattr(c.g, f"_{which}_shortcut")
        for _ in range(n):
            sc.activated.emit()
            H.settle(c.qapp, c.g)
    return do


def _combine_by_drag(c):
    a, b = c.loose()[:2]
    c.menus.pick = "To row"
    H.drag(c.g, a, H.centre(c.g, b))
    c.menus.pick = None
    H.settle(c.qapp, c.g)


def _edit_label(c):
    from pyfigures.gui.simple_text_editor import TextEditor
    label = next(i for i in H.images(c.g) if i.isText)

    def h(dlg):
        dlg.findChild(TextEditor).textEdit.setPlainText("WT embryo")
        H.accept(dlg)
    c.right_click(label, "Edit text", [("Edit text", h)])


def _editor_on_photo(edit, nested=()):
    def do(c):
        c.editor(c.photos()[0], edit, nested)
    return do


def _rectangle(ed):
    from test_gui_e2e_image_editor import _shape_tool
    _shape_tool("Rectangle")(ed)


def _inset(ed):
    _rectangle(ed)
    ed.toInset.click()


def _rotate(ed):
    ed.rotate_image_spinbox.setValue(15)


def _luts(ed):
    from qtpy.QtWidgets import QPushButton
    next(b for b in ed.findChildren(QPushButton) if b.text() == "Set LUTs").click()


def _text(ed):
    ed.add_text_button.click()


def _script(text):
    def edit(ed):
        ed.script_text_edit.setText(text)
        ed.execute_script_button.click()
    return edit


def _script_step(text):
    def do(c):
        from batoolset.drawings.shapes.image2d import Image2D
        target = next(i for i in H.images(c.g) if isinstance(i, Image2D) and not i.isText
                      and (i.custom_loading_script or not i.filename))
        c.editor(target, _script(text), [("Warning", H.accept)])     # "executing code" confirmation
    return do


def _project(c):
    from pyfigures.gui import tutorial as T
    z = T._panels(c.g, T._is_z_panel)[0]

    def edit(ed):
        ed.projection_combo_box.setCurrentIndex(ed.projection_combo_box.findData("max"))
    c.editor(z, edit)


def _fill_template(c):
    slot = next(i for i in H.images(c.g) if i.filename == "@template@")
    c.drop(["png2"], "⬜  Assign to template slot", where=H.centre(c.g, slot))


def _caption(c):
    c.menu("menu: File > Figure caption / legend…")


def _reviewed_html(c):
    """What a reviewer sends back: the exported page with a pinned comment."""
    import json
    import pyfigures.gui.review as review
    html = os.path.join(str(c.out), "saved.html")
    if not os.path.isfile(html):
        c.menu("menu: File > Review comments > Export for review…")
    with open(html, encoding="utf-8") as fh:
        text = fh.read()
    payload = json.dumps({"comments": [{"x": 0.5, "y": 0.5, "text": "tutorial comment", "author": "r",
                                        "ts": "2026-10-20T10:00"}], "author": "r", "owner_email": ""})
    text = review.html_export._COMMENT_BLOCK_RE.sub(lambda m: m.group(0).replace(m.group(1), payload), text)
    path = os.path.join(str(c.out), "reviewed.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    c.answers["open"] = path

    def look(dlg):
        H.reject(dlg)
    with H.dialogs() as pilot:
        pilot.expect("Review comments", look)
        H.action(c.g, "menu: File > Review comments > Import review comments…").trigger()
        H.settle(c.qapp, c.g, lambda: not pilot.queue)
    assert not pilot.queue, pilot.seen


def _view_review(c):
    with H.dialogs() as pilot:
        pilot.expect("Review comments", H.reject)
        H.action(c.g, "menu: File > Review comments > View review comments").trigger()
        H.settle(c.qapp, c.g, lambda: not pilot.queue)
    assert not pilot.queue, pilot.seen


def _theme(c):
    acts = H.actions(c.g)
    acts["menu: View > Theme > Dark"].trigger()
    acts["menu: View > Theme > Light"].trigger()


def _assistant(c):
    H.action(c.g, "menu: QC > Show color-blind assistant").trigger()
    H.settle(c.qapp, c.g)
    assert c.g.color_assistant.isVisible()
    c.g.color_assistant.close()


def _menu(key):
    return lambda c: c.menu(key)


def _on_panel(pred_name, key):
    """Click the panel the step names (as its text says), then the menu."""
    def do(c):
        from pyfigures.gui import tutorial as T
        target = T._panels(c.g, getattr(T, pred_name))[0]
        _click_empty(c)
        _click_until(c, target, target)
        c.menu(key)
    return do


def _drop(names, choice, dialogs=()):
    return lambda c: c.drop(names, choice, dialogs=dialogs)


TO_ROW = "↔  To row"
SINGLE = "➕  As single image(s)"

# step title (without "Step N — ") -> what the user does
PERFORM = {
    # beginner
    "Drop your first image": _drop(["big"], SINGLE),
    "Build a row": _drop(["png", "tif16"], TO_ROW),
    "Select the whole row": _select_row,
    "Focus on a single image": _click_image_in_row,
    "No selection = everything": _click_empty,
    "Resize the whole figure": _resize,
    "Add a scale bar": _menu("menu: Annotations > Add scale bar to all panels…"),
    "Toggle auto-lettering off": lambda c: c.g.auto_lettering_checkbox.click(),
    "Toggle auto-lettering back on": lambda c: c.g.auto_lettering_checkbox.click(),
    "Save your figure": _menu("menu: File > Save As..."),
    # medium
    "Drop two images as singles": _drop(["png", "png2"], SINGLE),
    "Combine into a row by drag-and-drop": _combine_by_drag,
    "Reorder images within the row": lambda c: (_click_image_in_row(c), _arrows("right")(c)),
    "Create a 3-image row at once": _drop(["png", "png2", "tif16"], TO_ROW),
    "Select a row": _select_row,
    "Rearrange rows with arrow keys": lambda c: (_select_row(c), _arrows("down")(c)),
    "Add labels above a row": lambda c: c.right_click(c.row(), "Add labels ▶ / Above the row"),
    "Edit a label": _edit_label,
    "Text annotation on an image": _editor_on_photo(_text),
    "Convert to template": _menu("menu: File > Convert figure to template"),
    "Fill the template": _fill_template,
    "Export as SVG": _menu("menu: File > Export As > SVG"),
    # advanced
    "Drop one image": _drop(["big"], SINGLE),
    "Draw shapes on the image": _editor_on_photo(_rectangle),
    "Create a zoom-in inset": _editor_on_photo(_inset),
    "Crop or rotate the image": _editor_on_photo(_rotate),
    "Apply Look-Up Tables (LUTs)": _editor_on_photo(_luts, [("Edit Look Up Tables (LUTs)", H.accept)]),
    "Add an empty image slot": lambda c: c.right_click(c.row(), "Add Empty Image", [("Add empty image", H.accept)]),
    "Script the empty image": lambda c: _script_step(__import__("pyfigures.gui.tutorial",
                                                                fromlist=["_MATPLOTLIB_SCRIPT"])._MATPLOTLIB_SCRIPT)(c),
    "Edit the script": lambda c: _script_step(__import__("pyfigures.gui.tutorial", fromlist=["_MATPLOTLIB_SCRIPT"])
                                              ._MATPLOTLIB_SCRIPT.replace("plot(", "scatter(", 1))(c),
    "Save and Consolidate": _menu("menu: File > Save And Consolidate..."),
    # publication
    "Start from a multi-panel figure": _drop(["png", "png2", "tif8"], TO_ROW),
    "Scale bar on every panel": _menu("menu: Annotations > Add scale bar to all panels…"),
    "Tidy text typography": _menu("menu: Annotations > Tidy text typography (×, °, units, ranges…)"),
    "Add a LUT colour bar": _menu("menu: Insert > LUT colour bar…"),
    "Add a data plot from a CSV": _menu("menu: Insert > Data plot from CSV…"),
    "Audit the figure": _menu("menu: QC > Audit figure (missing scale bars / labels)"),
    "Check print resolution": _menu("menu: QC > Check print resolution…"),
    "Enforce a minimum font size": _menu("menu: QC > Enforce minimum font size…"),
    "Journal compliance": _menu("menu: QC > Check journal compliance…"),
    "Image-integrity screen": _menu("menu: QC > Check image integrity (duplicates / clones)…"),
    "Adjustment provenance ledger": _menu("menu: QC > Adjustment provenance ledger (Methods)…"),
    "Check the fonts": _menu("menu: QC > Fonts (portable / Helvetica)…"),
    "Write the caption / legend": _caption,
    "Export for submission": _menu("menu: File > Export As > PDF"),
    # sharing
    "Export for review": _menu("menu: File > Review comments > Export for review…"),
    "Import review comments": _reviewed_html,
    "View review comments": _view_review,
    "Merge another figure in": _menu("menu: File > Merge into current figure…"),
    "Fix moved-file links": _menu("menu: QC > Remap image paths…"),
    "Colour-blind assistant": _assistant,
    "Preview under colour-blindness": _menu("menu: QC > Preview figure under colour-blindness…"),
    "Switch the interface theme": _theme,
    # stacks
    "Bring in some stacks": _drop(["zstack", "rgb", "tstack"], TO_ROW),
    "Project a Z stack": _project,
    "Channel split": _on_panel("_is_channel_panel",
                               "menu: Insert > Stack views > Channel split (each channel + merge)…"),
    "Montage of frames": _on_panel("_is_t_panel", "menu: Insert > Stack views > Montage of frames (time / Z)…"),
    "Kymograph": _on_panel("_is_t_panel", "menu: Insert > Stack views > Kymograph along a line…"),
    "Orthogonal views": _on_panel("_is_z_panel", "menu: Insert > Stack views > Orthogonal views (XZ / YZ)…"),
    "Merge separate channel files": _menu("menu: Insert > Multi-channel merge…"),
    "Export a movie": _menu("menu: File > Export As > Video (animate time-stacks)…"),
    # automation
    "Draft a figure from a folder": _menu("menu: File > Draft figure from folder…"),
    "Build a figure from a recipe": _menu("menu: File > Build figure from recipe…"),
    "Search your figure library": _menu("menu: File > Search figure library…"),
    "Compare two versions": _menu("menu: File > Compare with another version…"),
    "Copy the style of another figure": _menu("menu: File > Copy style from another figure…"),
    "Alt text for accessibility": _menu("menu: File > Alt text (accessibility)…"),
    "Pre-submission review": _menu("menu: QC > Pre-submission review (all checks)…"),
    "Changed source files": _menu("menu: QC > Check for changed source files…"),
}


def _short(title):
    import html
    t = html.unescape(title)
    m = re.match(r"Step \d+ — (.*)", t)
    return m.group(1) if m else t


def _wait(qapp, cond, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.parametrize("key", list(TUTORIAL_KEYS))
def test_tutorial_end_to_end(qapp, win, e2e_files, no_file_dialogs, menus, tmp_path, watch, key):
    g = win
    out = tmp_path / "out"
    out.mkdir()
    c = Ctx(qapp, g, e2e_files, no_file_dialogs, out, menus)
    H.action(g, key).trigger()
    ctrl = g._tutorial
    assert ctrl._bubble.isVisible() and ctrl._index == 0
    walked, set_up, performed = [], [], []
    for _ in range(40):
        if not ctrl._bubble.isVisible():
            break
        i = ctrl._index
        step = ctrl._current_step()
        short = _short(step.title)
        walked.append(short)
        assert ctrl._bubble._title.text() == step.title
        if step.get_target is not None:
            assert ctrl._target_rect() is not None, f"{short}: its highlighted target is missing"
        ctrl._check_completion()                       # what the poll does; records baselines
        if ctrl._missing and step.prepare is not None:
            assert ctrl._bubble._btn_prepare.isVisible(), short
            ctrl._bubble._btn_prepare.click()
            assert _wait(qapp, lambda: step.requires(g)), f"'Set it up for me' did not set up: {short}"
            H.settle(qapp, g)
            set_up.append(short)
            ctrl._check_completion()
        if H.RECORD:
            print(f"\n[RECORD] {short}: missing={ctrl._missing} done={ctrl._done_flag} "
                  f"rows={[[os.path.basename(str(x.filename)) for x in H.images(r)] for r in H.rows(g)]} "
                  f"sel={type(H.panel(g).selected_shape).__name__}")
        if ctrl._index != i or ctrl._done_flag:
            pass                                       # already done by the set-up
        elif short in PERFORM:
            PERFORM[short](c)
            H.settle(qapp, g)
            performed.append(short)
        elif step.completion_check is not None:
            raise AssertionError(f"{key}: no way to perform '{short}' in this test")
        if step.completion_check is not None and ctrl._index == i:
            assert _wait(qapp, lambda: ctrl._done_flag or ctrl._index != i), \
                f"{key}: the tutorial did not see '{short}' as done after performing it"
        if ctrl._index == i and ctrl._bubble.isVisible():
            ctrl._bubble._btn_next.click()
            H.settle(qapp, g)
        watch.check(f"{key}: {short}")
    assert not ctrl._bubble.isVisible(), f"{key}: still running after {walked}"
    if H.RECORD:
        print(f"\n[RECORD] {key}: performed {performed} set up {set_up}")
    with_checks = [s for s in walked if s in PERFORM]
    assert with_checks, walked


# ---------------------------------------------------------------------------
# Show me how
# ---------------------------------------------------------------------------

def _guide_keys():
    from pyfigures.guides import GUIDES
    return {f"menu: Help > Show me how… > {g['title']}": gid for gid, g in GUIDES.items()}


GUIDE_KEYS = _guide_keys()


def _guide_context(c, guide_id):
    """The right-click / double-click route a guide describes."""
    img = H.panel(c.g).selected_shape
    if guide_id == "set_lut":
        def green(dlg):
            from qtpy.QtWidgets import QComboBox
            for cb in dlg.findChildren(QComboBox):
                i = cb.findText("GREEN")
                if i >= 0:
                    cb.setCurrentIndex(i)
                    break
            H.accept(dlg)
        c.right_click(img, "Appearance ▶ / Set LUT(s)", [("Edit Look Up Tables (LUTs)", green)])
    elif guide_id == "crop_image":
        c.editor(img, lambda ed: ed.crop_left_spinbox.setValue(5))
    elif guide_id == "reorder_panels":
        # the → arrow moves the selected panel inside its row
        from qtpy.QtCore import Qt
        from qtpy.QtGui import QKeySequence
        from qtpy.QtWidgets import QShortcut
        seq = QKeySequence(Qt.Key.Key_Right)
        hits = [s for s in c.g.findChildren(QShortcut) if s.key() == seq]
        assert hits, "no shortcut for the right arrow"
        hits[0].activated.emit()
        H.settle(c.qapp, c.g)
    elif guide_id in ("edit_text", "edit_inset"):
        # the panel's editor (double-click), accepted
        c.editor(img, lambda ed: None)
    elif guide_id == "stack_in_row":
        # drag the selected panel onto an image of the other row
        c.menus.pick = "Stack with it (column in the row)"
        H.drag(c.g, img, H.centre(c.g, H.by_name(c.g, "rgb")))
        c.menus.pick = None
        H.settle(c.qapp, c.g)
    else:
        raise AssertionError(f"no context route for guide {guide_id}")


@pytest.mark.parametrize("key", list(GUIDE_KEYS))
def test_show_me_how_guide(qapp, win, e2e_files, no_file_dialogs, menus, tmp_path, watch, monkeypatch, key):
    """The guide starts on a figure, every step highlights a real target,
    and doing what it says (select, menu + dialog, or the right-click /
    double-click route) completes it: the guide sees the result and ends."""
    from pyfigures.guides import GUIDES
    g = win
    # the guide polls every 400 ms: a dialog answered in 15 ms is never seen open
    monkeypatch.setattr(H, "DIALOG_DWELL", 0.6)
    out = tmp_path / "out"
    out.mkdir()
    H.load(qapp, g, H.base_figure(tmp_path, e2e_files))
    g.current_file = str(tmp_path / "base.pyf")
    c = Ctx(qapp, g, e2e_files, no_file_dialogs, out, menus)
    gid = GUIDE_KEYS[key]
    H.action(g, key).trigger()
    H.settle(qapp, g)
    runner = g._guides
    assert runner.active() and runner.status()["status"] == "guidance_shown", runner.status()
    ctrl = g._tutorial
    assert ctrl._target_rect() is not None, f"{key}: first step highlights nothing"
    for spec in GUIDES[gid]["steps"]:
        if "select" in spec:
            # click the image: the first click selects its row, the next the image
            img = H.by_name(g, "rgb" if spec["select"] == "channel_image" else "gray8")
            _click_empty(c)
            _click_until(c, img, img)
        elif "menu" in spec:
            mkey = "menu: " + " > ".join(spec["menu"])
            assert ctrl._target_rect() is not None, f"{key}: {mkey} not highlighted"
            c.menu(mkey)
        elif "context" in spec:
            _guide_context(c, gid)
    assert _wait(qapp, lambda: runner.completed), f"{key}: the guide did not see the result ({runner.status()})"
    assert _wait(qapp, lambda: runner.status()["status"] == "completed" and not ctrl._bubble.isVisible(),
                 timeout=5), f"{key}: the guide did not end ({runner.status()})"
    watch.check(key)
