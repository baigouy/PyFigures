"""Regression tests for the bugs the end-to-end GUI layer (test_gui_e2e_*.py)
found. Each test names the user-visible symptom it guards against."""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _tif(path, val, shape=(20, 30)):
    from batoolset.img import Img
    Img(np.full(shape, val, np.uint8), dimensions="hw").save(str(path))
    return str(path)


def test_mixed_rows_and_loose_images_keep_their_order_when_reloaded(qapp, tmp_path):
    """The .pyf reader grouped children by tag: [row, image, row] came back
    as [row, row, image] — undo after a Swap and reopening a saved figure
    showed another arrangement. Same inside a group's content."""
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.serializations.tools import create_object, deserialize_to_dict, object_to_xml
    a, b, c, d, e = (Image2D(_tif(tmp_path / f"{n}.tif", 40 * (i + 1))) for i, n in enumerate("abcde"))
    inner = Group(Image2D(_tif(tmp_path / "f.tif", 9)), Image2D(_tif(tmp_path / "g.tif", 99)), orientation="Y")
    mixed = Group(c, inner, d, orientation="X")           # image, group, image inside a row
    top = [Group(a, orientation="X"), e, mixed, b]          # row, image, row, image at the top
    back = create_object(list.__name__, deserialize_to_dict(object_to_xml(top, is_list=True)))

    def names(s):
        if isinstance(s, Image2D):
            return os.path.basename(s.filename)
        return [names(x) for x in s.content]
    assert [names(s) for s in back] == [["a.tif"], "e.tif", ["c.tif", ["f.tif", "g.tif"], "d.tif"], "b.tif"]


@pytest.fixture
def two_rows(qapp, tmp_path, monkeypatch):
    """Rows [a b] [c d] + a loose image e, in a real window; QMenu.exec
    replaced by a pilot (see gui_e2e_harness.MenuPilot)."""
    import gui_e2e_harness as H
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    for row, names in ((0, "ab"), (1, "cd")):
        for i, n in enumerate(names):
            M.add_image(pyf, [row], _tif(tmp_path / f"{n}.tif", 30 + 50 * i, (20 + 10 * row, 30)))
    g = H.new_gui(qapp)
    H.load(qapp, g, pyf)
    g.all_images_directly([_tif(tmp_path / "e.tif", 200)])
    H.settle(qapp, g, lambda: len(H.images(g)) == 5)
    menus = H.MenuPilot(monkeypatch)
    yield g, H, menus, tmp_path
    H.close_gui(qapp, g)


def test_swap_can_be_undone(qapp, two_rows):
    """Swap recorded no undo checkpoint: Undo went back further (or nowhere)."""
    g, H, menus, d = two_rows
    g._save_state_to_file(str(d / "start.pyf"))
    H.load(qapp, g, str(d / "start.pyf"))
    before = H.snapshot(g, d)
    menus.pick = "Swap"
    H.drag(g, H.rows(g)[0], H.centre(g, H.rows(g)[1]))
    after = H.snapshot(g, d)
    assert after["rows"] == ["row 1: c.tif | d.tif", "row 2: a.tif | b.tif", "row 3: e.tif"]
    g.undo()
    H.settle(qapp, g)
    assert H.snapshot(g, d)["rows"] == before["rows"]


def test_image_dropped_on_an_image_of_another_row_can_swap_with_it(qapp, two_rows):
    """Only Add-to-group / To row / To column were offered: two images of
    different rows could not trade places."""
    g, H, menus, d = two_rows
    menus.pick = "Swap"
    H.drag(g, H.by_name(g, "a"), H.centre(g, H.by_name(g, "d")))
    assert H.snapshot(g, d)["rows"] == ["row 1: d.tif | b.tif", "row 2: c.tif | a.tif", "row 3: e.tif"]


def test_image_dropped_on_an_image_of_a_row_can_stack_with_it_in_the_row(qapp, two_rows):
    """User report (missing_dnd_option.pyf): dropping C on B of the row A | B
    offered no way to get A | (B / C) — To column made a new top-level
    column and left A alone."""
    g, H, menus, d = two_rows
    menus.pick = "Stack with it (column in the row)"
    H.drag(g, H.by_name(g, "e"), H.centre(g, H.by_name(g, "b")))
    rows = H.snapshot(g, d)["rows"]
    assert rows[0] == "row 1: a.tif | (b.tif / e.tif)" and len(rows) == 2, rows
    g.undo()
    H.settle(qapp, g)
    assert "e.tif" in " ".join(H.snapshot(g, d)["rows"][2:])


def test_a_new_group_takes_the_place_of_the_row_it_is_made_from(qapp, two_rows):
    """Dropping a file onto row 1 and choosing 'To row (with image below)'
    moved row 1 to the bottom of the figure."""
    g, H, menus, d = two_rows
    g.add_images_combined_with_target([_tif(d / "z.tif", 7)], H.rows(g)[0], "X")
    H.settle(qapp, g, lambda: len(H.images(g)) == 6)
    assert H.snapshot(g, d)["rows"][0] == "row 1: (a.tif | b.tif) | z.tif"


def test_dropping_an_equation_or_a_pdf_does_not_read_it_to_build_the_menu(qapp, two_rows, monkeypatch):
    """The drop menu asked stack_info() whether a .svg / .pdf was a movie:
    a full read that started Fiji's JVM (seconds) before the menu appeared."""
    g, H, menus, d = two_rows
    import pyfigures.stack_info as S
    called = []
    monkeypatch.setattr(S, "stack_info", lambda *a, **k: called.append(a) or {})
    for ext in (".svg", ".pdf"):
        assert g._stack_axes_of_file(str(d / f"x{ext}")) == []
    assert called == []


def _answer_custom(monkeypatch, fill=None):
    """CustomDialog.exec_ → Accepted after *fill(main_widget)*; records titles."""
    from qtpy.QtWidgets import QDialog
    from batoolset.GUI.customdialog import CustomDialog
    titles = []

    def run(self, *a, **k):
        titles.append(self.windowTitle())
        if fill is not None:
            fill(self.main_widget)
        return QDialog.Accepted
    monkeypatch.setattr(CustomDialog, "exec_", run, raising=False)
    monkeypatch.setattr(CustomDialog, "exec", run)
    return titles


def test_change_space_with_several_panels_of_a_row_sets_the_rows_space(qapp, two_rows, monkeypatch):
    """Right-click > Change space between elements on two panels of a row
    opened nothing and changed nothing (only a selected row worked)."""
    g, H, menus, d = two_rows
    p = H.panel(g)
    from qtpy.QtWidgets import QSpinBox

    def space_17(widget):
        widget.findChildren(QSpinBox)[0].setValue(17)
    titles = _answer_custom(monkeypatch, space_17)
    p.set_current_selection([H.by_name(g, "a"), H.by_name(g, "b")])
    p.set_space()
    assert titles == ["Change space"]
    assert H.rows(g)[0].space == 17 and H.rows(g)[1].space != 17


def test_set_lut_on_a_template_slot_says_why_and_reset_clears_it(qapp, two_rows, monkeypatch):
    """Set LUT(s) on a slot (no channels) did nothing without a word, and
    Reset LUT(s) left a LUT set on it before in place."""
    g, H, menus, d = two_rows
    p = H.panel(g)
    loose = H.by_name(g, "e")
    p.templatify(loose)
    slot = next(i for i in H.images(g) if i.filename == "@template@")
    titles = _answer_custom(monkeypatch)
    said = []
    p.informative_message_required.connect(said.append)
    p.set_current_selection(slot)
    p.set_luts()
    assert titles == [] and said and "No LUT" in said[-1]
    slot.LUTs = ["RED"]
    p.set_luts(force_reset=True)
    assert slot.LUTs is None


def test_editing_an_equation_can_be_undone(qapp, two_rows, monkeypatch):
    """Right-click > Edit equation… recorded no undo step."""
    g, H, menus, d = two_rows
    from pyfigures import mcp_server as M
    pyf = str(d / "eq.pyf")
    g._save_state_to_file(pyf)
    M.add_equation(pyf, [0], r"\alpha")
    H.load(qapp, g, pyf)
    eq = next(i for i in H.images(g) if str(i.filename).endswith(".svg"))
    first = eq.filename
    from pyfigures.gui.equation_dialog import EquationDialog
    from qtpy.QtWidgets import QDialog

    def accept(self):
        self.latex_edit.setPlainText(r"\beta")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(EquationDialog, "exec", accept)
    g.edit_equation(eq)
    H.settle(qapp, g)
    assert H.by_name(g, "eq").filename != first
    g._flush_pending_checkpoints()
    g.undo()
    H.settle(qapp, g)
    assert next(i for i in H.images(g) if str(i.filename).endswith(".svg")).filename == first


def test_an_action_saving_two_identical_checkpoints_is_undone_by_one_undo(qapp, two_rows):
    """Insert > LaTeX code panel asked for two checkpoints of the same
    figure: the first Undo seemed to do nothing."""
    g, H, menus, d = two_rows
    g._save_state_to_file(str(d / "s.pyf"))
    H.load(qapp, g, str(d / "s.pyf"))
    n0 = len(H.images(g))
    H.panel(g).set_current_selection(H.by_name(g, "a"))
    H.panel(g).duplicate()
    g._flush_pending_checkpoints()
    g.save_state(show_popup=False)            # the same figure again
    g.save_state(show_popup=False)
    g.undo()
    H.settle(qapp, g)
    assert len(H.images(g)) == n0


def test_convert_to_template_right_after_an_unchanged_checkpoint(qapp, two_rows):
    """A checkpoint identical to the previous one is dropped (see above):
    Convert figure to template then got None for its state file (TypeError)."""
    g, H, menus, d = two_rows
    g.save_state(show_popup=False)
    assert g.save_state(show_popup=False)            # still a state file to read
    g.templatify_figure()
    H.settle(qapp, g)
    assert all(i.filename == "@template@" for i in H.images(g) if not i.isText)


def test_merge_and_page_background_can_be_undone(qapp, two_rows, monkeypatch, tmp_path):
    """File > Merge reset the undo history (the merge could not be undone)
    and the toolbar Background recorded no undo step."""
    g, H, menus, d = two_rows
    from pyfigures.gui import pfgui
    g._save_state_to_file(str(d / "s.pyf"))
    H.load(qapp, g, str(d / "s.pyf"))
    rows0 = H.snapshot(g, tmp_path)["rows"]
    g._choose_page_background(0x000000)
    H.settle(qapp, g)
    g.undo()
    H.settle(qapp, g)
    assert H.panel(g).page_background is None
    other = str(d / "other.pyf")
    g._save_state_to_file(other)
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda *a, **k: other)
    g.open_figure(append=True)
    H.settle(qapp, g, lambda: len(H.rows(g)) > len(rows0))
    assert len(H.snapshot(g, tmp_path)["rows"]) == 2 * len(rows0)
    g.undo()
    H.settle(qapp, g)
    assert H.snapshot(g, tmp_path)["rows"] == rows0


def test_dragging_a_panel_out_of_a_nested_group_moves_it(qapp, two_rows, tmp_path):
    """'To column' with a panel that sat in a sub-group left it in its old
    group too: the same image was drawn, lettered and saved twice. And the
    row it left kept its old, shrunk layout (reopening laid it out anew)."""
    g, H, menus, d = two_rows
    p = H.panel(g)
    p.add(H.rows(g)[0], H.rows(g)[1])        # drag row 1 into row 2, keeping its layout
    H.settle(qapp, g)
    assert any(type(s).__name__ == "Group" for r in H.rows(g) for s in r.content)
    p.create_col_with(H.by_name(g, "e"), H.by_name(g, "a"))      # a leaves its sub-group
    H.settle(qapp, g)
    H.assert_no_shared_panels(g)
    names = sorted(os.path.basename(i.filename) for i in H.images(g))
    assert names == ["a.tif", "b.tif", "c.tif", "d.tif", "e.tif"], names
    live = H.snapshot(g, tmp_path)
    H.load(qapp, g, live["_file"])
    assert H.same(H.snapshot(g, tmp_path), live), "the figure on screen is not the one saved"


def test_tutorial_hint_injector_ignores_a_dialog_already_deleted(qapp):
    """During a tutorial, a QInputDialog / QMessageBox closed within 150 ms
    was already deleted when the hint injector's timer touched it: an
    exception in a Qt slot, which aborts a PyQt6 application."""
    from qtpy.QtWidgets import QDialog, QWidget
    from pyfigures.gui.tutorial import _DialogInjector

    class Ctrl:
        class _bubble:
            @staticmethod
            def isVisible():
                return True

    inj = _DialogInjector(Ctrl())
    owner = QWidget()
    dlg = QDialog(owner)
    owner.deleteLater()                       # takes the dialog with it
    qapp.processEvents()
    from qtpy.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    inj._inject(dlg)                          # must not raise


def test_tutorial_hint_timer_skips_a_destroyed_dialog(qapp):
    """A dialog Qt made itself is not tracked by sip: isdeleted() stays False
    after it is destroyed and the 150 ms timer touched freed memory (access
    violation during Review → Import comments). The timer now checks that the
    dialog was not destroyed."""
    import time
    from qtpy.QtCore import QEvent
    from qtpy.QtWidgets import QDialog
    from pyfigures.gui.tutorial import _DialogInjector

    class Ctrl:
        class _bubble:
            @staticmethod
            def isVisible():
                return True
    inj = _DialogInjector(Ctrl())
    touched = []
    inj._inject = lambda d: touched.append(d)
    dlg = QDialog()
    inj.eventFilter(dlg, QEvent(QEvent.Type.Show))
    dlg.deleteLater()
    from qtpy.QtCore import QCoreApplication
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    t0 = time.time()
    while time.time() - t0 < 0.4:
        qapp.processEvents()
        time.sleep(0.01)
    assert touched == []
    alive = QDialog()
    inj.eventFilter(alive, QEvent(QEvent.Type.Show))
    t0 = time.time()
    while time.time() - t0 < 0.4:
        qapp.processEvents()
        time.sleep(0.01)
    assert touched == [alive]


def test_crop_guide_follows_the_panel_the_editor_replaced(qapp, two_rows):
    """Show me how › Crop: the image editor replaces the edited panel by its
    clone, so the guide watching the old object never saw the crop."""
    g, H, menus, d = two_rows
    from pyfigures.gui.show_me_how import GuideRunner
    runner = GuideRunner(g)
    old = H.by_name(g, "a")
    runner._target_image = old
    runner._image_state0 = runner._image_state(old)
    clone = type(old)(old.filename)
    clone.crop_left = 4
    content = g.paint.EZFIG_panel._container_of(old)
    content[content.index(old)] = clone       # what pressing Ok in the editor does
    g.paint.EZFIG_panel.set_current_selection(clone)
    assert runner._done("crop_changed")


def test_series_of_a_template_slot_or_missing_file_never_starts_bioformats(monkeypatch, tmp_path):
    """Opening the image editor on an empty template slot asked Bio-Formats
    for the series of '@template@': the Fiji JVM started (seconds, and an
    access-violation trace on Windows)."""
    import batoolset.IJ.ij_reader as R
    from batoolset.img import get_series_info
    called = []
    monkeypatch.setattr(R, "count_series", lambda f, *a, **k: called.append(f) or 3)
    for name in ("@template@", str(tmp_path / "moved_away.czi"), str(tmp_path)):
        assert get_series_info(name) == (1, None)
    assert called == []


@pytest.mark.parametrize("dims,shape,axes", [
    ("thw", (5, 20, 30), "TYX"), ("dhw", (4, 20, 30), "ZYX"), ("tdhw", (3, 4, 20, 30), "TZYX"),
    ("thwc", (5, 20, 30, 2), "TCYX"), ("dhwc", (4, 20, 30, 2), "ZCYX"), ("hw", (20, 30), "YX"),
])
def test_saved_time_stack_stays_a_time_stack(tmp_path, dims, shape, axes):
    """Img(..., dimensions='thw').save() wrote the frames as Z slices: a movie
    saved by PyFigures reopened as a Z stack (max-projected, 'Z' montage)."""
    import tifffile
    from batoolset.img import Img, save_as_tiff
    a = np.random.default_rng(0).integers(0, 255, shape).astype(np.uint8)
    for k, write in enumerate((lambda p: Img(a, dimensions=dims).save(p),
                               lambda p: save_as_tiff(Img(a, dimensions=dims), p))):
        p = str(tmp_path / f"{dims}_{k}.tif")
        write(p)
        assert tifffile.TiffFile(p).series[0].axes == axes
        back = Img(p)
        assert back.metadata["dimensions"] == dims
        assert np.array_equal(np.asarray(back), a)


def test_label_text_stays_black_on_a_dark_ui_theme(qapp):
    """Text with no colour of its own took the application palette's colour:
    with View > Theme > Dark (or Windows in dark mode, as 'System') the
    'double click to edit' labels and every plain caption were light grey on
    the white figure, in the exported PNG / PDF too."""
    from qtpy.QtGui import QImage, QPainter
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.gui import theme
    old = qapp.palette()
    try:
        qapp.setPalette(theme._dark_palette())
        txt = TAText2D("<p style='font-size:40pt'>MMMM</p>")
        img = QImage(400, 120, QImage.Format.Format_RGB32)
        img.fill(0xFFFFFF)
        p = QPainter(img)
        txt.draw(p)
        p.end()
        a = np.frombuffer(img.constBits().asstring(img.sizeInBytes()), np.uint8).reshape(120, 400, 4)[..., :3]
        assert a.min() < 40                  # the darkest glyph pixels are black, not light grey
    finally:
        qapp.setPalette(old)


def test_equation_size_does_not_depend_on_an_earlier_data_plot(tmp_path):
    """staplot styles (data plots) change matplotlib's global rcParams; an
    equation typeset after a data plot came out a different size (41.6 →
    39.5 pt high), so the same figure laid out differently in a session
    that had made a plot."""
    import re
    import matplotlib
    from pyfigures.equations import render_svg

    def size(p):
        s = open(p, encoding="utf-8").read()
        return re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', s).groups()
    with matplotlib.rc_context():
        render_svg(r"\alpha + \beta", str(tmp_path / "a.svg"), 40)
        # staplot no longer changes the global rcParams: do what it used to do
        from staplot.plots import styles
        matplotlib.rcParams.update(styles.rc())
        render_svg(r"\alpha + \beta", str(tmp_path / "b.svg"), 40)
    assert size(tmp_path / "a.svg") == size(tmp_path / "b.svg")


def test_headless_render_gives_qmessagebox_warning_back(qapp, tmp_path):
    """render_pyf / headless_ops replaced QMessageBox.warning by 'answer Yes'
    for the rest of the process: in a process that also shows the GUI (an
    MCP host, the test suite) every later warning — 'discard unsaved
    changes?' included — was answered Yes without being shown."""
    import inspect
    from qtpy.QtWidgets import QMessageBox
    from pyfigures import mcp_server as M
    from pyfigures.gui.render_headless import render_pyf
    getattr(QMessageBox, "warning")
    real = QMessageBox.__dict__["warning"]
    assert not inspect.isfunction(getattr(real, "__func__", real))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    M.add_image(pyf, [], _tif(tmp_path / "a.tif", 120))
    keep = []
    render_pyf(pyf, str(tmp_path / "f.png"), dpi=72, _keep_alive=keep)
    assert os.path.isfile(tmp_path / "f.png")
    assert QMessageBox.__dict__["warning"] is real


def test_clearing_dialog_stubs_keeps_qtpys_exec_alias(qapp, monkeypatch):
    """The e2e harness removes dialog stubs other tests leave behind; it also
    removed qtpy's own QDialog.exec_ alias (a Python lambda on PyQt6), so
    every later CustomDialog(...).exec_() raised AttributeError and ~50
    menu / tutorial tests after it failed."""
    from qtpy.QtWidgets import QDialog, QMessageBox
    import gui_e2e_harness as H
    H.ensure_real_dialogs()
    assert callable(getattr(QDialog, "exec_", None))
    assert callable(getattr(QMessageBox, "exec_", None))
    # a stub that replaced the alias is removed and the alias comes back
    monkeypatch.setattr(QDialog, "exec_", lambda self: 0)
    assert "QDialog.exec_" in H.ensure_real_dialogs()
    d = QDialog()
    monkeypatch.setattr(d, "exec", lambda: 7)
    assert d.exec_() == 7
    # a stub over Qt's own static method is replaced by Qt's method, not
    # deleted: QMessageBox was left with no 'warning' at all
    real = QMessageBox.__dict__["warning"]
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    assert "QMessageBox.warning" in H.ensure_real_dialogs()
    assert QMessageBox.__dict__.get("warning") is real
