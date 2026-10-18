"""Text inside data plots stays editable in the PowerPoint and Illustrator exports.

Qt draws SVG text as glyph outlines into another SVG, so tick labels, axis
titles and significance stars of a Matplotlib plot arrived as shapes and could
not be edited. During the editable export the plot is now rendered with
svg.fonttype 'none' and its text drawn as real text
(batoolset.drawings.svg_text_renderer).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")
pptx = pytest.importorskip("pptx")


def _plot_figure(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("Control,Treated\n1,4\n2,5\n3,6\n2,5\n", encoding="utf-8")
    pyf = tmp_path / "fig.pyf"
    M.create_figure(str(pyf), mode="canvas")
    res = M.add_data_plot(str(pyf), [], str(csv), kind="box", annotate_stats=True)
    assert not res.startswith("ERROR"), res
    return pyf


def _pptx_texts(path):
    from pptx import Presentation
    texts = []

    def walk(shapes):
        for s in shapes:
            if s.has_text_frame and s.text:
                texts.append(s.text)
            if s.shape_type == 6:
                walk(s.shapes)

    for slide in Presentation(str(path)).slides:
        walk(slide.shapes)
    return texts


def test_plot_labels_are_native_text_in_powerpoint(tmp_path, qapp):
    pyf = _plot_figure(tmp_path)
    out = tmp_path / "fig.pptx"
    M.export_pptx(str(pyf), str(out))
    texts = _pptx_texts(out)
    for label in ("Control", "Treated", "Value", "**", "1", "6"):
        assert label in texts, texts
    # the boxes are shapes, not pictures: a clip path that cuts nothing
    # (Matplotlib clips every artist to its axes) no longer turns an element
    # into an image
    from pptx import Presentation
    pictures = []

    def walk(shapes):
        for s in shapes:
            if s.shape_type == 13:
                pictures.append(s)
            if s.shape_type == 6:
                walk(s.shapes)

    for slide in Presentation(str(out)).slides:
        walk(slide.shapes)
    assert pictures == []


def test_plot_labels_are_native_text_in_illustrator(tmp_path, qapp):
    pyf = _plot_figure(tmp_path)
    out = tmp_path / "fig.jsx"
    M.export_illustrator_script(str(pyf), str(out))
    jsx = out.read_text(encoding="utf-8-sig")
    assert '"Control"' in jsx and '"Treated"' in jsx and '"Value"' in jsx


def test_ordinary_exports_keep_plot_text_as_drawn(tmp_path, qapp):
    """The flag is only on during the editable export."""
    from batoolset.drawings.shapes.image2d import Image2D
    pyf = _plot_figure(tmp_path)
    M.export_pptx(str(pyf), str(tmp_path / "fig.pptx"))
    assert Image2D._export_editable_text is False


def test_mathtext_label_is_one_run(qapp):
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from batoolset.drawings.svg_text_renderer import make_text_renderer
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.set_ylabel(r"Length ($\mu$m)")
    buf = io.BytesIO()
    with matplotlib.rc_context({"svg.fonttype": "none"}):
        fig.savefig(buf, format="svg")
    plt.close(fig)
    renderer = make_text_renderer(buf.getvalue())
    texts = [t for t, _x, _y in renderer.text_runs()]
    assert "Length (μm)" in texts, texts
