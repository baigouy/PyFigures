"""The user's own requests while trying plots with Mistral Large 4 (2026-11-18), kept as
human requests (the chat side, its guards and offers: qtpy_ai_sidecar/tests/
test_chat_choices_20261118.py):

  "create a plot from measurements.xlsx", "rather make it a violin plot",
  "why are the violins so truncated at top and bottom", "any other way to plot that?",
  "show me all plots so I can pick", "I'll go for the box plot finally",
  "I prefer SD, journals also prefer SD to SEM", "is there also support for xls files
  (xls and xlsx)", "the last row is not same length as the others",
  "staplot should also handle the consolidation, which is just the excel file".
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures.mcp_tools import content as C  # noqa: E402
from pyfigures.mcp_tools.core import _child_text, _load  # noqa: E402

pytest.importorskip("openpyxl")


@pytest.fixture
def book(tmp_path):
    rng = np.random.default_rng(3)
    path = tmp_path / "measurements.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame({"WT": rng.normal(42, 2.5, 10), "mutA": rng.normal(35, 2, 10),
                      "mutB": rng.normal(41, 2.5, 10)}).to_excel(w, sheet_name="counts", index=False)
        rows = [(g, d, 10 + 2 * i + rng.normal()) for g in ("WT", "mut") for i, d in enumerate(("d1", "d2"))
                for _ in range(8)]
        pd.DataFrame(rows, columns=["genotype", "day", "length"]).to_excel(w, sheet_name="growth", index=False)
    return str(path)


@pytest.fixture
def pyf(tmp_path, qapp):
    path = str(tmp_path / "f.pyf")
    import pyfigures.mcp_server as M
    M.create_figure(path, num_groups=0)
    return path


def _scripts(pyf):
    _tree, root = _load(pyf)
    return [C._decode_text(_child_text(i, "custom_loading_script")) for i in root.iter("Image2D")]


def test_create_a_plot_from_an_excel_file(pyf, book):
    res = C.add_data_plot(pyf, [], book)
    assert "added" in res and "measurements.xlsx" in res, res
    from pyfigures.assistant.plot_info import parse_data_plot, plot_statistics
    spec = parse_data_plot(_scripts(pyf)[-1])
    assert spec["csv"] == book                                   # the first sheet
    assert plot_statistics(spec)["test"]                         # described with its test


def test_journals_prefer_sd_so_it_is_the_default(pyf, book):
    C.add_data_plot(pyf, [], book, kind="bar")
    from pyfigures.assistant.plot_info import parse_data_plot
    assert parse_data_plot(_scripts(pyf)[-1])["error"] == "sd"
    import inspect
    from staplot import api
    assert inspect.signature(api.plot).parameters["error"].default == "sd"


def test_rather_a_violin_and_the_violins_taper_past_the_data(pyf, book):
    C.add_data_plot(pyf, [], book, kind="bar")
    assert "'bar' -> 'violin'" in C.edit_data_plot(pyf, [], 0, kind="violin")
    # "why are the violins so truncated at top and bottom": they ended flat at the
    # smallest and largest value; now the shape goes past them
    from staplot import api
    table = api.table_from_csv(book)
    fig, _ = api.plot(table, kind="violin", annotate=False)
    bodies = [c for c in fig.axes[0].collections if type(c).__name__ in ("PolyCollection", "FillBetweenPolyCollection")]
    assert bodies
    lowest = min(float(b.get_paths()[0].vertices[:, 1].min()) for b in bodies)
    data_min = min(float(np.min(c.valid_values())) for c in table.columns)
    assert lowest < data_min


def test_make_the_plot_wider_or_taller(pyf, book):
    """"make k plot wider, it's too small": the model said panels have no width of their
    own. A plot does: its aspect (width / height), only when asked; the default shape
    stays staplot's."""
    C.add_data_plot(pyf, [], book, kind="box")
    from pyfigures.assistant.plot_info import parse_data_plot
    assert parse_data_plot(_scripts(pyf)[-1])["aspect"] is None            # default unchanged
    res = C.edit_data_plot(pyf, [], 0, aspect=2.0)
    assert "aspect None -> 2.0" in res, res
    assert parse_data_plot(_scripts(pyf)[-1])["aspect"] == 2.0
    from staplot import api
    table = api.table_from_csv(book)
    w0, h0 = api.plot(table, kind="box", annotate=False)[0].get_size_inches()
    w, h = api.plot(table, kind="box", annotate=False, aspect=2.0)[0].get_size_inches()
    assert h == h0 and abs(w / h - 2.0) < 1e-6
    w, h = api.plot(table, kind="box", annotate=False, aspect=0.6)[0].get_size_inches()
    assert abs(w / h - 0.6) < 1e-6                                        # taller


def test_any_other_way_to_plot_that(pyf):
    kinds = C.list_data_plot_kinds()
    for kind in ("bar", "box", "violin", "scatter", "grouped", "catplot"):
        assert kind in kinds


def test_box_plots_per_day_from_another_sheet(pyf, book):
    res = C.add_seaborn_plot(pyf, [], book, "catplot", kind="box", x="genotype", y="length", col="day",
                             sheet="growth")
    assert "faceted by day" in res, res
    assert C.add_data_plot(pyf, [], book, sheet="nope").startswith("ERROR: no sheet 'nope'")
    # another sheet of the same workbook for an existing plot
    C.add_data_plot(pyf, [], book, kind="box")
    from pyfigures.assistant.plot_info import parse_data_plot
    idx = len(_scripts(pyf)) - 1                 # an empty canvas: the panels stay on it
    res = C.edit_data_plot(pyf, [], idx, sheet="counts")
    assert not res.startswith("ERROR"), res
    assert parse_data_plot(_scripts(pyf)[idx])["csv"].endswith("::counts")


def test_consolidation_takes_the_excel_file(pyf, book, tmp_path):
    C.add_data_plot(pyf, [], book, kind="box")
    from pyfigures.plot_tables import consolidate_plot_tables
    copied = consolidate_plot_tables(pyf)
    assert [os.path.basename(c) for _s, c in copied] == ["measurements.xlsx"]
    from pyfigures.assistant.plot_info import parse_data_plot
    assert parse_data_plot(_scripts(pyf)[-1])["csv"] == copied[0][1]


def test_the_chat_sees_the_plot_as_code_and_can_get_all_of_it(pyf, book, tmp_path, qapp):
    """"that could also be sent to the model and help it modify the parameters"."""
    C.add_data_plot(pyf, [], book, kind="box", ylabel="cells / field")
    from pyfigures.assistant.plot_info import parse_data_plot, staplot_call
    call = staplot_call(parse_data_plot(_scripts(pyf)[-1]))
    assert "kind='box'" in call and "ylabel='cells / field'" in call and "api.plot(" in call
    code = C.data_plot_code(pyf, [], 0, out_path=str(tmp_path / "plot.py"))
    assert code.startswith("Saved to") and (tmp_path / "plot.py").read_text(encoding="utf-8").count("api.plot(") == 1
    C.add_seaborn_plot(pyf, [], book, "catplot", kind="box", x="genotype", y="length", col="day", sheet="growth")
    sns_code = C.data_plot_code(pyf, [], 1)
    ns = {}
    import matplotlib
    matplotlib.use("Agg")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        exec(compile(sns_code, "sns", "exec"), ns)
    finally:
        os.chdir(cwd)
    assert (tmp_path / "plot.pdf").is_file()
    import pyfigures.mcp_server as M
    M.add_scripted_image(pyf, [], "fig, ax = plt.subplots()\nself.img = fig\n")
    assert C.data_plot_code(pyf, [], 2).startswith("ERROR: this panel is not a data plot")


def test_show_plot_code_in_the_gui(qapp, book):
    from pyfigures.gui.pfgui import EZFIG_GUI

    class Panel:
        custom_loading_script = C._make_data_plot_script(book, "violin", "sd", True, True, "", "", "")
    g = EZFIG_GUI()
    try:
        dlg = g.show_plot_code(Panel())
        from qtpy.QtWidgets import QPlainTextEdit
        text = dlg.findChild(QPlainTextEdit).toPlainText()
        assert "kind='violin'" in text and "pd.read_excel(" in text
        dlg.close()
    finally:
        g._dirty = False
        g.close()


def test_the_code_of_a_plot_reads_the_sheet_and_reruns_the_test(book, tmp_path):
    """"can staplot print the code it used to generate the fig": a script that redraws
    the plot and runs the same test with pandas / scipy alone, from the Excel sheet."""
    from staplot import api
    code = api.plot_code(book + "::counts", "box")
    assert "api.plot(" in code and "pd.read_excel(" in code and "sheet_name='counts'" in code
    assert "stats.f_oneway" in code or "stats.kruskal" in code or "ttest_ind" in code
    out = {}
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        import matplotlib
        matplotlib.use("Agg")
        cwd = os.getcwd()
        os.chdir(tmp_path)                       # the script saves plot.pdf where it runs
        try:
            exec(compile(code, "plot_code", "exec"), out)
        finally:
            os.chdir(cwd)
    assert sorted(out["names"]) == ["WT", "mutA", "mutB"]
    assert [len(a) for a in out["arrays"]] == [10, 10, 10]


def test_size_and_layout_of_a_plot_only_when_asked(pyf, book):
    """"the plot part of the MCP should allow layout changes, and/or size changes"."""
    C.add_data_plot(pyf, [], book, kind="box")
    from pyfigures.assistant.plot_info import parse_data_plot
    spec = parse_data_plot(_scripts(pyf)[-1])
    assert all(spec[k] is None for k in ("width", "height", "font_scale", "order", "ylim", "legend"))
    res = C.edit_data_plot(pyf, [], 0, width=3, font_scale=1.3, order=["mutb", "WT"], ylim=[0, None],
                           xtick_rotation=45)
    assert "width None -> 3.0" in res and "order None -> ['mutB', 'WT']" in res, res
    spec = parse_data_plot(_scripts(pyf)[-1])
    assert spec["font_scale"] == 1.3 and spec["ylim"] == [0.0, None]
    assert C.edit_data_plot(pyf, [], 0, order=["nope"]).startswith("ERROR: no group named")
    assert "font_scale 1.3 -> None" in C.edit_data_plot(pyf, [], 0, font_scale=0)       # 0 resets
    assert C.edit_data_plot(pyf, [], 0, legend="left").startswith("ERROR: legend must be")
    from pyfigures.assistant.plot_info import staplot_call
    assert "order=['mutB', 'WT']" in staplot_call(parse_data_plot(_scripts(pyf)[-1]))


def test_auto_picks_the_kind_and_says_why(pyf, book, tmp_path):
    """"the plot interface should also offer an auto by default that plots the plot with
    the optimal way of plotting it from the data"."""
    res = C.add_data_plot(pyf, [], book)                       # 10 per group
    assert "KIND: auto chose box" in res, res
    res = C.add_data_plot(pyf, [], book, sheet="growth")       # genotype x day -> length
    assert "KIND: auto chose grouped" in res, res
    tidy = tmp_path / "tidy.csv"
    pd.DataFrame([(g, t, d, 1.0 + i, 2.0) for i, (g, t, d) in enumerate(
        (g, t, d) for g in ("WT", "mut") for t in ("a", "b") for d in ("d1", "d2"))],
        columns=["genotype", "treatment", "day", "length", "width"]).to_csv(tidy, index=False)
    res = C.add_data_plot(pyf, [], str(tidy))                  # several factors: say so
    assert res.startswith("ERROR: no plot kind fits this table on its own") and "seaborn" in res, res


def test_remove_the_y_label_means_no_label(pyf, book):
    """"I did not say replace it by value, I said I want the label of the y axis gone"."""
    C.add_data_plot(pyf, [], book, kind="box", ylabel="tutu")
    assert "show_ylabel True -> False" in C.edit_data_plot(pyf, [], 0, ylabel="")
    from pyfigures.assistant.plot_info import parse_data_plot
    from staplot import api
    spec = parse_data_plot(_scripts(pyf)[-1])
    assert spec["show_ylabel"] is False and spec["ylabel"] == ""
    fig, _ = api.plot(api.table_from_csv(book), kind="box", annotate=False, show_ylabel=False)
    assert fig.axes[0].get_ylabel() == ""
    assert "show_ylabel False -> True" in C.edit_data_plot(pyf, [], 0, ylabel="auto")


def test_scale_bars_get_the_colour_that_reads_on_each_panel(pyf, tmp_path):
    """"many scale bars are not visible, ensure each panel gets a visible scale bar";
    "uniformity is less important than visibility"."""
    from PIL import Image
    dark, bright = tmp_path / "dark.png", tmp_path / "bright.png"
    Image.fromarray(np.full((200, 300), 15, np.uint8)).save(dark)
    Image.fromarray(np.full((200, 300), 240, np.uint8)).save(bright)
    import pyfigures.mcp_server as M
    M.add_image(pyf, [], str(dark))
    M.add_image(pyf, [], str(bright))
    res = M.set_scale_bar_all(pyf)
    assert "white: dark.png" in res and "black: bright.png" in res, res
    res = M.set_scale_bar_all(pyf, bar_color="black")            # asked: kept, with a word
    assert "hard to see on dark.png" in res, res
    res = M.set_scale_bar_all(pyf, bar_color="auto")
    assert "white: dark.png" in res, res


def test_plot_text_is_seven_points_on_the_page(pyf, book, qapp):
    """"plots should fit the text font recommended by journals by default unless the
    user explicitly asks for a given size"; "make it so it fits the default letter font
    size" (the chat reset font_scale and said it matched)."""
    C.add_data_plot(pyf, [], book, kind="box")
    _tree, root = _load(pyf)
    img = list(root.iter("Image2D"))[-1]
    assert str(_child_text(img, "publication_font_on_page")) == "True"
    assert float(_child_text(img, "publication_font_size")) == 7
    res = C.edit_data_plot(pyf, [], 0, font_pt=9)
    assert "-> 9 pt on the page" in res, res
    assert C.edit_data_plot(pyf, [], 0, font_pt=200).startswith("ERROR: font_pt")
    # drawn: whatever the panel's scale, the text measures 9 pt once the plot is fitted
    from batoolset.serializations.tools import element_to_dict, create_object
    _tree, root = _load(pyf)
    props = element_to_dict(list(root.iter("Image2D"))[-1])
    for scale in (1.0, 2.5):
        panel = create_object("Image2D", props.get("Image2D", props))
        panel.scale = scale
        from batoolset.matplolibs.tools import get_fig_rect, figure_pad_inches
        shown_pt = get_fig_rect(panel.img).width() / scale
        saved = panel._apply_publication_style()
        try:
            fig = panel.img
            drawn_pt = fig.get_tightbbox(fig.canvas.get_renderer()).padded(figure_pad_inches(fig)).width * 72
            tick = fig.axes[0].get_yticklabels()[0].get_fontsize()
            assert abs(tick * shown_pt / drawn_pt - 9) < 0.3, (scale, tick * shown_pt / drawn_pt)
        finally:
            panel._restore_publication_style(saved)


def test_a_bigger_plot_font_shows_on_the_canvas_too(pyf, book, qapp):
    """"I have the feeling changing font does nothing or image is not refreshed": the
    page size was applied to exports only; the canvas kept the plot's own fonts."""
    from batoolset.serializations.tools import element_to_dict, create_object
    from pyfigures.panel_source_preview import qimage_to_rgb
    from qtpy.QtGui import QImage, QPainter, QColor
    C.add_data_plot(pyf, [], book, kind="box")
    inks = []
    for pt in (7, 20):
        C.edit_data_plot(pyf, [], 0, font_pt=pt)
        _tree, root = _load(pyf)
        props = element_to_dict(list(root.iter("Image2D"))[-1])
        panel = create_object("Image2D", props.get("Image2D", props))
        panel.scale = 2.0
        rect = panel.getRect(all=True)
        image = QImage(int(rect.width()) + 2, int(rect.height()) + 2, QImage.Format.Format_RGBA8888)
        image.fill(QColor(255, 255, 255))
        painter = QPainter(image)                 # no antialiasing: the screen path
        painter.translate(-rect.x(), -rect.y())
        panel.draw(painter)
        painter.end()
        assert panel.renderer._pyf_page_key[1] == pt
        rgb = qimage_to_rgb(image)
        inks.append(int((rgb.sum(-1) < 200).sum()))
    assert inks[1] > inks[0] * 1.3, inks         # far more dark (text) pixels at 20 pt


def test_a_restyled_plot_still_fills_its_panel(pyf, book, qapp):
    """"it is not occupying the full space, which is a layout bug": its text set to the
    page size changed the plot's outline, and the panel kept the old shape."""
    import re as _re
    from batoolset.serializations.tools import element_to_dict, create_object
    from batoolset.matplolibs.tools import get_fig_rect
    C.add_data_plot(pyf, [], book, kind="violin")
    for pt, scale in ((7, 2.0), (20, 2.0), (7, 0.7)):
        C.edit_data_plot(pyf, [], 0, font_pt=pt)
        _tree, root = _load(pyf)
        props = element_to_dict(list(root.iter("Image2D"))[-1])
        panel = create_object("Image2D", props.get("Image2D", props))
        panel.scale = scale
        rect = get_fig_rect(panel.img)
        size = tuple(panel.img.get_size_inches())
        svg = panel._toBuffer(bufferType="svg", apply_publication=True).read().decode("utf-8", "replace")
        w, h = (float(v) for v in _re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', svg).groups())
        assert abs((w / h) / (rect.width() / rect.height()) - 1) < 0.02, (pt, scale, w / h)
        assert tuple(panel.img.get_size_inches()) == size          # put back


def test_the_scale_of_a_plot_is_its_y_axis(pyf, book):
    """"make the scale bar start at 0 and go to 50", just after editing plot g: the chat
    looked for an image scale bar and asked which panel."""
    from pyfigures.assistant.categorized_mcp import __file__ as hints_file
    hints = open(hints_file, encoding="utf-8").read()
    assert '"start at 0 and go to 50" mean its y axis: ylim=[0, 50]' in hints
    C.add_data_plot(pyf, [], book, kind="violin")
    assert "ylim None -> [0.0, 50.0]" in C.edit_data_plot(pyf, [], 0, ylim=[0, 50])


def test_rename_a_group_and_rotate_its_name_left(pyf, book):
    """"rename mutA into mutant A" (the chat said to edit the Excel file); "rotate x
    labels by 45 degrees left" (it chose -45, the user meant +45)."""
    C.add_data_plot(pyf, [], book, kind="violin")
    res = C.edit_data_plot(pyf, [], 0, rename={"muta": "mutant A"})
    assert "rename None -> {'mutA': 'mutant A'}" in res, res
    assert C.edit_data_plot(pyf, [], 0, rename={"zz": "x"}).startswith("ERROR: no group named")
    from pyfigures.assistant.plot_info import parse_data_plot, staplot_call
    assert "rename={'mutA': 'mutant A'}" in staplot_call(parse_data_plot(_scripts(pyf)[-1]))
    assert "rename {'mutA': 'mutant A'} -> None" in C.edit_data_plot(pyf, [], 0, rename={})
    doc = C.edit_data_plot.__doc__
    assert '"rotate\n      left" / "anticlockwise" = positive' in doc
    from pyfigures.assistant.categorized_mcp import __file__ as hints_file
    assert '"rotate left" = +45' in open(hints_file, encoding="utf-8").read()
