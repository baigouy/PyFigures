"""An image's opacity survives a reload and the editor's clone (2026-10-25:
Image2D's constructor reset it to 1, so transform_image(opacity=…) and any
saved opacity were lost when the GUI opened the figure)."""
from __future__ import annotations

import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pyfigures.mcp_server as M


def test_opacity_set_by_mcp_is_read_by_the_gui_and_kept_by_a_clone(qapp, tmp_path):
    import gui_e2e_harness as H
    from PIL import Image
    from batoolset.serializations.tools import clone_object
    png = tmp_path / "a.png"
    Image.fromarray(np.full((40, 60), 120, np.uint8)).save(png)
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], str(png))
    assert not M.transform_image(pyf, [0], 0, opacity=0.4).startswith("ERROR")
    g = H.new_gui(qapp)
    try:
        H.load(qapp, g, pyf)
        img = H.images(g)[0]
        assert abs(img.opacity - 0.4) < 1e-9
        assert abs(clone_object(img).opacity - 0.4) < 1e-9
    finally:
        g._mark_clean()
        H.close_gui(qapp, g)


def test_bad_opacity_values_fall_back_or_clamp():
    from batoolset.drawings.shapes.image2d import Image2D
    assert Image2D(data=np.zeros((4, 4), np.uint8), opacity=None).opacity == 1.0
    assert Image2D(data=np.zeros((4, 4), np.uint8), opacity="x").opacity == 1.0
    assert Image2D(data=np.zeros((4, 4), np.uint8), opacity=3).opacity == 1.0
    assert Image2D(data=np.zeros((4, 4), np.uint8), opacity=0.25).opacity == 0.25
