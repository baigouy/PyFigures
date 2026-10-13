"""An export started right after opening a figure waits for the images that
are still loading in the background, instead of exporting empty panels.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def test_export_right_after_open_has_every_panel(qapp, tmp_path):
    from PIL import Image
    from batoolset.img import Img
    from pyfigures import mcp_server as M
    from pyfigures.gui.pfgui import EZFIG_GUI
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=0)
    rng = np.random.default_rng(0)
    for k in range(4):
        arr = rng.integers(0, 256, (1500, 1500), dtype=np.uint8)
        path = str(tmp_path / f"im{k}.tif")
        Img(arr, dimensions="hw").save(path)
        M.add_image(pyf, [0], path)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    try:
        g._start_pyf_loader([pyf], append=False, reset_undo=True)
        # only until the layout is on the canvas: the pixels are still loading
        for _ in range(2000):
            qapp.processEvents()
            if g.paint.EZFIG_panel.shapes_to_draw:
                break
        out = str(tmp_path / "o.png")
        g.paint.EZFIG_panel.get_dpi = lambda: 30
        g.paint.EZFIG_panel.save(out)
        assert not g._images_loading()
        im = np.asarray(Image.open(out).convert("RGBA")).astype(int)
        w = im.shape[1]
        for k in range(4):                                # every panel has its pixels
            tile = im[5:-5, int(w * k / 4) + 5: int(w * (k + 1) / 4) - 5]
            # noise averaged at 30 dpi: mid-grey (an unloaded panel is not)
            assert tile[..., 3].min() == 255 and 90 < tile[..., :3].mean() < 165, (k, tile[..., :3].mean())
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()
