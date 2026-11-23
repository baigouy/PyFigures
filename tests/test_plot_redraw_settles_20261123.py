"""User 2026-11-23: "I dropped images and the tool seems lagging". On screen, a plot whose
text is sized on the page is redrawn by matplotlib when its scale changes; images dropped
load one by one, each moved the layout, and a plot typeset by LaTeX (~1 s a run) was redrawn
after every image (13 LaTeX runs in 13 s). A plot already drawn is now redrawn once, when
its layout has stopped moving; the previous drawing is shown meanwhile. Exports and
off-screen drawing still redraw at once."""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_human_requests_20261118 import book, pyf  # noqa: E402,F401


class _Painter:
    def __init__(self, device):
        self._device = device

    def device(self):
        return self._device


def _wait(qapp, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)


@pytest.fixture
def panel(pyf, book, qapp):
    from batoolset.serializations.tools import element_to_dict, create_object
    from pyfigures.mcp_tools import content as C
    from pyfigures.mcp_tools.core import _load
    C.add_data_plot(pyf, [], book, kind="box")
    _tree, root = _load(pyf)
    props = element_to_dict(list(root.iter("Image2D"))[-1])
    p = create_object("Image2D", props.get("Image2D", props))
    p.publication_font_on_page = True
    p.publication_style = True
    return p


def test_a_moving_layout_redraws_the_plot_once_it_settles(panel, qapp, monkeypatch):
    from qtpy.QtWidgets import QWidget

    class Canvas(QWidget):
        updates = 0

        def update(self):
            Canvas.updates += 1
            super().update()
    canvas = Canvas()
    on_screen = _Painter(canvas)
    drawn = []
    real = panel._redraw_page_text
    monkeypatch.setattr(panel, "_redraw_page_text", lambda key: (drawn.append(key[0]), real(key)))

    panel.scale = 2.0
    panel._refresh_page_text_renderer(on_screen)         # never drawn: drawn at once
    assert drawn == [2.0]
    for s in (2.1, 2.2, 2.3, 2.4):                        # images arriving one by one
        panel.scale = s
        panel._refresh_page_text_renderer(on_screen)
        panel._refresh_page_text_renderer(on_screen)     # repaints of one layout: one wait
        _wait(qapp, 100)
    assert drawn == [2.0] and panel.renderer._pyf_page_key[0] == 2.0   # the old drawing, scaled
    _wait(qapp, panel.PAGE_TEXT_REDRAW_DELAY_MS + 300)
    assert drawn == [2.0, 2.4] and panel.renderer._pyf_page_key[0] == 2.4
    assert Canvas.updates == 1
    assert "_page_redraw_gen" not in panel.to_dict() and "_page_redraw_key" not in panel.to_dict()

    panel.scale = 3.0
    panel._refresh_page_text_renderer(None)              # export / off-screen: at once
    assert drawn[-1] == 3.0
    canvas.deleteLater()
