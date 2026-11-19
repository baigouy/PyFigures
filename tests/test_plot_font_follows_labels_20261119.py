"""2026-11-19 (user): "add a font-family option for data plots ... ideally use the same
font for the graph as default image fonts", "and font size should ideally fit size of
label font (can be different from letter font in some cases)", "and label font is
normally smaller than letter font". A data plot's text now follows the figure's labels
(the texts other than the panel letters), in font and size, unless set."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PG = os.path.join(os.path.dirname(__file__), "..", "demo_figures", "plots_playground")
TABLE = os.path.join(PG, "measurements.xlsx")
LABEL = "<span style=\"font-family:'Times New Roman'; font-size:6pt;\">ctrl</span>"


def _figure(tmp_path, label=True):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image
    from pyfigures.mcp_tools.core import _load, _save, _new_tatext2d
    png = tmp_path / "cells.png"
    Image.new("L", (40, 30)).save(png)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    add_image(pyf, [], str(png))
    if label:
        tree, root = _load(pyf)
        img = next(root.iter("Image2D"))
        annots = img.find("annotations")
        if annots is None:
            import xml.etree.ElementTree as ET
            annots = ET.SubElement(img, "annotations")
        annots.append(_new_tatext2d(LABEL, is_letter=False))
        _save(tree, pyf)
    return pyf


def _plot(pyf):
    from pyfigures.mcp_tools.core import _load, _child_text, _decode
    _t, root = _load(pyf)
    img = [i for i in root.iter("Image2D")
           if _decode(_child_text(i, "custom_loading_script")) not in (None, "", "None")][-1]
    def value(k):
        v = _child_text(img, k)
        return _decode(v) if isinstance(v, str) else v
    return {k: value(k) for k in
            ("publication_font", "publication_font_size", "publication_font_size_from_labels")}


def test_a_new_plot_takes_the_labels_font_and_size(tmp_path):
    from pyfigures.mcp_server import add_data_plot
    pyf = _figure(tmp_path)
    assert "ERROR" not in add_data_plot(pyf, [], TABLE)
    p = _plot(pyf)
    assert p["publication_font"] == "figure"
    assert float(p["publication_font_size"]) == 6 and p["publication_font_size_from_labels"] is True


def test_with_no_labels_the_size_is_7_pt_not_the_letters(tmp_path):
    from pyfigures.mcp_server import add_data_plot
    pyf = _figure(tmp_path, label=False)
    add_data_plot(pyf, [], TABLE)
    p = _plot(pyf)
    assert float(p["publication_font_size"]) == 7 and p["publication_font_size_from_labels"] is True


def test_edit_sets_and_gives_back_the_font_and_size(tmp_path):
    from pyfigures.mcp_server import add_data_plot, edit_data_plot
    pyf = _figure(tmp_path)
    add_data_plot(pyf, [], TABLE)
    out = edit_data_plot(pyf, [], 1, font_family="Verdana", font_pt=9)
    assert "Verdana" in out, out
    p = _plot(pyf)
    assert p["publication_font"] == "Verdana" and float(p["publication_font_size"]) == 9
    assert p["publication_font_size_from_labels"] is False
    out = edit_data_plot(pyf, [], 1, font_family="labels", font_pt="labels")
    assert "labels' font" in out and "labels' size" in out, out
    p = _plot(pyf)
    assert p["publication_font"] == "figure" and p["publication_font_size_from_labels"] is True


def test_the_plot_is_drawn_in_the_labels_style_read_when_drawn():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from batoolset.drawings.shapes import image2d
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.matplolibs.tools import best_helvetica_clone
    fig = plt.figure()
    img = Image2D(fig, publication_font="figure", publication_font_size=7,
                  publication_font_size_from_labels=True, publication_font_on_page=True)
    saved = image2d.label_text_style_source
    try:
        image2d.label_text_style_source = lambda: {"family": "Times New Roman", "size": 6.0}
        assert img._publication_family() == "Times New Roman" and img._page_font_pt() == 6
        image2d.label_text_style_source = lambda: {"family": "Verdana", "size": None}
        assert img._publication_family() == "Verdana" and img._page_font_pt() == 7
        image2d.label_text_style_source = None             # no figure to ask: kept values
        assert img._publication_family() == best_helvetica_clone() and img._page_font_pt() == 7
    finally:
        image2d.label_text_style_source = saved
        plt.close(fig)


def test_the_open_figure_gives_its_labels_style():
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.text_fonts import label_style
    texts = [TAText2D(LABEL), TAText2D(LABEL)]
    style = label_style(texts, "Segoe UI")
    assert style == {"family": "Times New Roman", "size": 6.0}
    assert label_style([], "Segoe UI") == {"family": "Segoe UI", "size": None}
