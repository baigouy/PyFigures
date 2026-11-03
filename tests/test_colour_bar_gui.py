"""
Tests for the GUI "Add LUT colour bar…" action and the shared colour-bar
script builder used by both the GUI and the MCP tool.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures.colorbar_script import build_calibration_bar_script


# -------------------------------------------------- shared builder (no Qt)
def test_builder_basic_script():
    s = build_calibration_bar_script(lut="AFM_HOT", vmin=0, vmax=255,
                                     label="Intensity (a.u.)")
    assert "ColorbarBase" in s
    assert "'AFM_HOT'" in s
    assert "self.img = fig" in s
    assert s.strip().endswith("self.img = fig")


def test_builder_ticks_and_labels():
    s = build_calibration_bar_script(lut="GRAY", ticks=[0, 128, 255],
                                     tick_labels=["lo", "mid", "hi"])
    assert "set_ticks" in s and "set_ticklabels" in s


def test_builder_bad_orientation():
    with pytest.raises(ValueError):
        build_calibration_bar_script(lut="GRAY", orientation="diagonal")


def test_builder_tick_length_mismatch():
    with pytest.raises(ValueError):
        build_calibration_bar_script(lut="GRAY", ticks=[0, 255],
                                     tick_labels=["only-one"])


# ---------------------------------------------------------- GUI action
try:
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication  # noqa: F401
    _QT = True
except Exception:
    _QT = False

needs_qt = pytest.mark.skipif(not _QT, reason="Qt not available")


@pytest.fixture
def gui(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    yield g
    g._dirty = False


@needs_qt
def test_dialog_parses_values(gui):
    from pyfigures.gui.pfgui import _ColourBarDialog
    d = _ColourBarDialog(gui)
    d.lut_combo.setCurrentText("AFM_HOT")
    d.vmax_edit.setText("4000")
    d.ticks_edit.setText("0, 4000")
    d.tick_labels_edit.setText("low, high")
    v = d.values()
    assert v["lut"] == "AFM_HOT" and v["vmax"] == 4000.0
    assert v["ticks"] == [0.0, 4000.0] and v["tick_labels"] == ["low", "high"]


@needs_qt
def test_dialog_rejects_bad_numbers(gui):
    from pyfigures.gui.pfgui import _ColourBarDialog
    d = _ColourBarDialog(gui)
    d.vmin_edit.setText("not-a-number")
    with pytest.raises(ValueError):
        d.values()


@needs_qt
def test_add_colour_bar_inserts_scripted_panel(gui, monkeypatch):
    from qtpy.QtWidgets import QDialog
    from pyfigures.gui import pfgui

    class _AutoAccept:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QDialog.Accepted

    monkeypatch.setattr(pfgui, "CustomDialog", _AutoAccept)
    monkeypatch.setattr(pfgui._ColourBarDialog, "values", lambda self: {
        "lut": "AFM_HOT", "vmin": 0.0, "vmax": 255.0, "label": "Intensity",
        "orientation": "vertical", "ticks": None, "tick_labels": None,
    })

    panel = gui.paint.EZFIG_panel
    n0 = len(panel.shapes_to_draw)
    gui.add_colour_bar()
    assert len(panel.shapes_to_draw) == n0 + 1
    new = panel.shapes_to_draw[-1]
    assert "ColorbarBase" in (new.custom_loading_script or "")
    assert new.img is not None            # the script ran and built a figure


@needs_qt
def test_colour_bar_follows_the_selected_panel(gui, monkeypatch):
    """'add the corresponding LUT on the right of b' (2026-11-03): the dialog
    starts on the selected panel's colour map and the bar lands right after it."""
    from qtpy.QtWidgets import QDialog
    from pyfigures.gui import pfgui
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.group import Group

    class _AutoAccept:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QDialog.Accepted

    monkeypatch.setattr(pfgui, "CustomDialog", _AutoAccept)
    script = ("x = np.linspace(0, 1, 64)\nfig, ax = plt.subplots()\n"
              "ax.imshow(np.tile(x, (64, 1)), cmap='magma')\nself.img = fig")
    first, second = Image2D(custom_loading_script=script), Image2D(custom_loading_script=script)
    row = Group(first, second, orientation="X")
    panel = gui.paint.EZFIG_panel
    panel.shapes_to_draw.append(row)
    panel.selected_shape = first
    gui.add_colour_bar()
    assert len(row.content) == 3 and row.content[0] is first and row.content[2] is second
    assert "'MATPLOTLIB_magma'" in row.content[1].custom_loading_script


def test_panel_lut_reads_luts_then_the_plot_script():
    from pyfigures.colorbar_script import panel_lut
    assert panel_lut(["GRAY_INVERTED", None], None) == "GRAY_INVERTED"
    assert panel_lut([None], "ax.imshow(a, cmap='viridis_r')") == "MATPLOTLIB_viridis_r"
    assert panel_lut(["DEFAULT"], None) is None


@needs_qt
def test_add_colour_bar_cancel_adds_nothing(gui, monkeypatch):
    from qtpy.QtWidgets import QDialog
    from pyfigures.gui import pfgui

    class _Cancel:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QDialog.Rejected

    monkeypatch.setattr(pfgui, "CustomDialog", _Cancel)
    panel = gui.paint.EZFIG_panel
    n0 = len(panel.shapes_to_draw)
    gui.add_colour_bar()
    assert len(panel.shapes_to_draw) == n0
