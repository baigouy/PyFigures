"""User, 2026-11-20 (chat log): "make title bigger" made ALL the plot's text bigger
(font_pt 7 -> 9): "for graphs, labels, titles, or axes fonts or font size should be able to
be changed independently ... and maybe indeed also to the whole graph". A plot's title,
axis labels, tick labels and legend can now each have their own size and font
(edit_data_plot text_pt / text_font, the panel editor's publication tab); font_pt and
font_family stay the whole plot's."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from _tables import measurements_xlsx  # noqa: E402


def _fig():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [1, 3, 2], label="WT")
    ax.set_title("toto")
    ax.set_xlabel("day")
    ax.set_ylabel("area")
    ax.legend()
    return fig, ax


def _sizes(fig, ax):
    fig.canvas.draw()
    return {"title": ax.title.get_fontsize(), "xlabel": ax.xaxis.label.get_fontsize(),
            "ticks": {t.get_fontsize() for t in ax.get_xticklabels() if t.get_text()},
            "legend": ax.get_legend().get_texts()[0].get_fontsize()}


def test_the_parts_are_drawn_with_their_own_size_and_font(monkeypatch):
    from batoolset.drawings.shapes.image2d import Image2D
    fig, ax = _fig()
    parts = {"title": {"pt": 12, "font": "DejaVu Serif"}, "ticks": {"pt": 5}}
    img = Image2D(fig, publication_font_size=7, publication_text_parts=json.dumps(parts))
    saved = img._apply_publication_style()
    s = _sizes(fig, ax)
    assert s["title"] == 12 and "DejaVu Serif" in ax.title.get_fontfamily()
    assert s["xlabel"] == 7 and s["legend"] == 7          # not set: the whole plot's size
    assert s["ticks"] == {5}
    img._restore_publication_style(saved)


def test_on_the_page_the_sizes_keep_their_ratio(monkeypatch):
    """A plot sized on the page (the default): its sizes are page points, scaled with it."""
    from batoolset.drawings.shapes.image2d import Image2D
    fig, ax = _fig()
    img = Image2D(fig, publication_font_size=7, publication_font_on_page=True,
                  publication_text_parts=json.dumps({"title": {"pt": 14}, "ticks": {"pt": 5}}))
    img.scale = 0.5
    kept = {}
    monkeypatch.setattr(Image2D, "_restore_publication_style", lambda self, saved: kept.update(saved=saved))
    img._toBuffer(bufferType="svg", apply_publication=True)
    s = _sizes(fig, ax)
    assert abs(s["title"] / s["xlabel"] - 2) < 0.01, s
    assert all(abs(t / s["xlabel"] - 5 / 7) < 0.01 for t in s["ticks"]), s


def test_the_model_sets_and_clears_one_part(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, add_data_plot, edit_data_plot
    from pyfigures.mcp_tools.core import _load
    from pyfigures.mcp_tools.content import text_parts_of
    png = tmp_path / "cells.png"
    Image.new("L", (40, 30)).save(png)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    add_image(pyf, [], str(png))
    assert "ERROR" not in add_data_plot(pyf, [], measurements_xlsx(tmp_path))

    def parts():
        _t, root = _load(pyf)
        return text_parts_of(list(root.iter("Image2D"))[-1])
    out = edit_data_plot(pyf, [], 1, title="toto", text_pt={"title": 9}, text_font={"ticks": "Arial"})
    assert "ERROR" not in out and "title 9 pt" in out, out
    assert parts() == {"title": {"pt": 9.0}, "ticks": {"font": "Arial"}}
    out = edit_data_plot(pyf, [], 1, text_pt={"tick_labels": 6})        # the user's words
    assert parts()["ticks"] == {"font": "Arial", "pt": 6.0}, out
    edit_data_plot(pyf, [], 1, text_pt={"title": None}, text_font={"ticks": ""})
    assert parts() == {"ticks": {"pt": 6.0}}
    assert edit_data_plot(pyf, [], 1, text_pt={"subtitle": 9}).startswith("ERROR")
    assert edit_data_plot(pyf, [], 1, text_pt={"title": 200}).startswith("ERROR")


def test_they_are_saved_with_the_panel():
    from batoolset.drawings.shapes.image2d import Image2D, parse_text_parts
    fig, _ax = _fig()
    img = Image2D(fig, publication_font_size=7,
                  publication_text_parts=json.dumps({"legend": {"pt": 6, "font": "Arial"}}))
    assert parse_text_parts(img.publication_text_parts) == {"legend": {"pt": 6.0, "font": "Arial"}}
    assert "publication_text_parts" in img.to_dict()                    # saved with the figure
