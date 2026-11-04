"""Visual regression of the figure editor (marker ``gui_e2e``).

Key scenarios are built through the GUI's own code paths, rendered with the
same code as File > Export As > PNG (72 dpi) and compared with the golden
images in tests/golden_gui/: same size within 2 % and at most 0.5 % of the
pixels differing by more than 20 grey levels (the pixel diff of the MCP
figure-diff tool, pyfigures.mcp_tools.export._make_pixel_diff; a render up
to 2 % taller / wider — an equation typeset by the other engine — is
resampled to the golden size first). On a
mismatch the render and a red-tinted diff overlay are kept next to the test
output for inspection.

Golden images are only (re)written on purpose:
    PYF_E2E_UPDATE_GOLDEN=1 pytest -m gui_e2e tests/test_gui_e2e_visual.py
"""
from __future__ import annotations

import os
import shutil

import pytest

import gui_e2e_harness as H
from gui_e2e_harness import e2e_files, e2e_gui, menus, watch  # noqa: F401

pytestmark = pytest.mark.gui_e2e

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_gui")
UPDATE = bool(os.environ.get("PYF_E2E_UPDATE_GOLDEN"))
MAX_CHANGED = 0.005
# the equation panel is typeset by matplotlib's mathtext, whose glyph sizes
# change between matplotlib versions: the row reflows by a pixel or two and
# shifts every border after it (0.9 % with matplotlib 3.11 vs 3.10)
MAX_CHANGED_FOR = {"labels_and_equation": 0.015}


def _base(qapp, g, d, files):
    H.load(qapp, g, H.base_figure(d, files))


def _panel_drop(qapp, g, d, files):
    _base(qapp, g, d, files)
    H.drop_files(g, [files["png2"], files["tif16"], files["tif8"]])

    def two_rows(dlg):
        from qtpy.QtWidgets import QRadioButton, QSpinBox
        H.widget_by(dlg, QRadioButton, label="Specify Rows").setChecked(True)
        dlg.findChildren(QSpinBox)[0].setValue(2)
        H.accept(dlg)
    with H.dialogs() as pilot:
        pilot.expect("Panel", two_rows)
        H.click_drop_choice(g, "▦  To panel")
        H.settle(qapp, g, lambda: not pilot.queue)
    H.settle(qapp, g)


def _green_lut_and_crop(qapp, g, d, files):
    """Crop in the image editor (double-click, spin boxes, Ok), then
    right-click › Appearance › Set LUT(s) › GREEN."""
    from qtpy.QtWidgets import QComboBox
    from test_gui_e2e_image_editor import _open_editor_by_double_click
    _base(qapp, g, d, files)

    def crop(dlg):
        dlg.main_widget.crop_left_spinbox.setValue(10)
        dlg.main_widget.crop_top_spinbox.setValue(6)
        H.accept(dlg)

    def green(dlg):
        for cb in dlg.findChildren(QComboBox):
            if cb.findText("GREEN") >= 0:
                cb.setCurrentIndex(cb.findText("GREEN"))
                break
        H.accept(dlg)
    with H.dialogs() as pilot:
        pilot.expect("Annotate the image", crop)
        _open_editor_by_double_click(qapp, g, H.by_name(g, "cells"))
        H.settle(qapp, g, lambda: not pilot.queue)
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    try:
        menus = H.MenuPilot(mp)
        with H.dialogs() as pilot:
            pilot.expect("Edit Look Up Tables (LUTs)", green)
            H.right_click(g, menus, H.by_name(g, "cells"), pick="Appearance ▶ / Set LUT(s)")
            H.settle(qapp, g, lambda: not pilot.queue)
    finally:
        mp.undo()
    H.settle(qapp, g)


def _template(qapp, g, d, files):
    _base(qapp, g, d, files)
    g.templatify_figure()
    H.settle(qapp, g)


def _swapped_rows(qapp, g, d, files):
    _base(qapp, g, d, files)
    H.panel(g).swap_images(H.by_name(g, "gray8"), H.by_name(g, "zstack"))
    H.settle(qapp, g)


def _labels_and_equation(qapp, g, d, files):
    from pyfigures import mcp_server as M
    pyf = H.base_figure(d, files)
    M.add_equation(pyf, [1], r"\alpha + \beta")
    H.load(qapp, g, pyf)
    H.panel(g).set_current_selection(H.rows(g)[0])
    H.panel(g).associate_text_row(sensitivity="below")
    H.panel(g).set_current_selection(None)
    H.settle(qapp, g)


SCENARIOS = {
    "base": _base,
    "drop_to_panel": _panel_drop,
    "green_lut_and_crop": _green_lut_and_crop,
    "template": _template,
    "swapped_images": _swapped_rows,
    "labels_and_equation": _labels_and_equation,
}


def _changed_fraction(golden, render, overlay):
    """(golden size, render size, fraction of pixels that differ). A render
    a few pixels taller or wider (an equation typeset by another engine) is
    resampled to the golden size first."""
    from PIL import Image
    from pyfigures.mcp_tools.export import _make_pixel_diff
    with Image.open(golden) as a, Image.open(render) as b:
        sa, sb = a.size, b.size
        if sa != sb:
            resized = render[:-4] + "_resized.png"
            b.convert("RGB").resize(sa, Image.Resampling.LANCZOS).save(resized)
            render = resized
    frac = _make_pixel_diff(golden, render, overlay)
    return sa, sb, frac


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_render_matches_golden(qapp, e2e_gui, e2e_files, tmp_path, watch, name):
    g = e2e_gui
    SCENARIOS[name](qapp, g, tmp_path, e2e_files)
    H.panel(g).set_current_selection(None)
    H.settle(qapp, g)
    render = str(tmp_path / f"{name}.png")
    g._render_png_without_prompt(render, dpi=72)
    watch.check(name)
    golden = os.path.join(GOLDEN, f"{name}.png")
    if UPDATE or not os.path.isfile(golden):
        if not UPDATE:
            pytest.fail(f"no golden image {golden}: run with PYF_E2E_UPDATE_GOLDEN=1 to create it")
        os.makedirs(GOLDEN, exist_ok=True)
        shutil.copy(render, golden)
        return
    overlay = str(tmp_path / f"{name}_diff.png")
    sa, sb, frac = _changed_fraction(golden, render, overlay)
    assert abs(sa[0] - sb[0]) <= max(2, 0.02 * sa[0]) and abs(sa[1] - sb[1]) <= max(2, 0.02 * sa[1]), \
        f"{name}: size {sb} != golden {sa} (render {render}, diff {overlay})"
    assert frac <= MAX_CHANGED_FOR.get(name, MAX_CHANGED), f"{name}: {frac:.2%} of pixels differ (render {render}, diff {overlay})"
