"""Matplotlib writes the space glyph as a <path/> with no 'd'. Qt >= 6.5 warns
'Invalid path data; path truncated.' and 'link #DejaVuSans-3 is undefined!'
for each data-plot panel; batoolset-gui fills those paths before rendering."""
from __future__ import annotations

import io
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _plot_svg():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.bar(["a", "b"], [1, 2])
    ax.set_ylabel("two words")      # a space: the empty glyph
    buf = io.BytesIO()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    return buf.getvalue()


def test_empty_glyph_paths_get_a_d():
    image2d = pytest.importorskip("batoolset.drawings.shapes.image2d")
    fill = getattr(image2d, "fill_empty_svg_paths", None)
    if fill is None:
        pytest.skip("installed batoolset-gui predates fill_empty_svg_paths")
    data = _plot_svg()
    fixed = fill(data)
    assert image2d._EMPTY_SVG_PATH.search(fixed) is None
    assert fixed.count(b"<path") == data.count(b"<path")
    assert fill(b'<path d="M 1 2 L 3 4"/>') == b'<path d="M 1 2 L 3 4"/>'
    assert fill(b'<path id="g" transform="scale(2)"/>') == b'<path id="g" transform="scale(2)" d="M 0 0"/>'


def test_svg_panel_renders_without_qt_warnings(qapp):
    image2d = pytest.importorskip("batoolset.drawings.shapes.image2d")
    if not hasattr(image2d, "fill_empty_svg_paths"):
        pytest.skip("installed batoolset-gui predates fill_empty_svg_paths")
    from qtpy.QtCore import QByteArray, qInstallMessageHandler
    msgs = []
    old = qInstallMessageHandler(lambda mode, ctx, msg: msgs.append(msg))
    try:
        r = image2d._make_svg_renderer(QByteArray(_plot_svg()))
    finally:
        qInstallMessageHandler(old)
    assert r.isValid()
    assert not [m for m in msgs if "path" in m or "undefined" in m], msgs
