"""What 50 human-like requests to Mistral Large 4 showed (2026-11-18), and the fixes.

- data plots were "code panels" to the model: no p-values, no comparisons, edited
  by hand into an error -> described with their settings, data and statistics;
  edit_data_plot / list_data_plot_kinds;
- "same magnification as A" overwrote D's pixel size -> a calibrated pixel size is
  only changed with confirm_recalibration (the user says it is wrong);
- "same brightness so they're comparable" used per-image auto-contrast ->
  match_display_range (one shared range);
- time stamps on a Z stack -> refused;
- empty panels padding a montage -> pad_last_row / remove_empty_placeholders;
- "make the text bigger everywhere" changed the letters only -> change_text_size;
- missing / non-numeric cells in a CSV: left out and said;
- seaborn plots, faceted like ggplot2 (user: "seaborn is the real replacement for R").
"""
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures.mcp_tools import content as C  # noqa: E402
from pyfigures.mcp_tools import overlays as O  # noqa: E402
from pyfigures.mcp_tools import qc as Q  # noqa: E402
from pyfigures.mcp_tools import stacks as S  # noqa: E402
from pyfigures.mcp_tools import structure as ST  # noqa: E402
from pyfigures.mcp_tools.core import _child_text, _get_container, _load, _pixel_size  # noqa: E402


def _tif(path, arr, um):
    import tifffile
    tifffile.imwrite(str(path), arr, imagej=True, resolution=(1 / um, 1 / um), metadata={"unit": "um"})


@pytest.fixture
def figure(tmp_path, qapp):
    """Two calibrated images (1.24 and 0.107 µm/px), a box plot of a CSV with gaps."""
    rng = np.random.default_rng(0)
    _tif(tmp_path / "a.tif", (rng.random((60, 80)) * 200).astype(np.uint8), 1.24)
    _tif(tmp_path / "d.tif", (rng.random((50, 50)) * 255).astype(np.uint8), 0.107)
    (tmp_path / "counts.csv").write_text(
        "WT,mutA,mutB\n42,33,45\n40,,44\n45,NA,46\n39,35,43\n41,31,47\n44,abc,45\n", encoding="utf-8")
    (tmp_path / "f.yaml").write_text(
        "output: f.pyf\nwidth_mm: 120\nrows:\n  - - a.tif\n    - d.tif\n"
        "    - {plot: counts.csv, kind: box, stats_mode: auto}\n", encoding="utf-8")
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    res = build_figure_from_recipe(str(tmp_path / "f.yaml"))
    assert not res.startswith("ERROR"), res
    return tmp_path / "f.pyf"


def _images(pyf, gp=(0,)):
    tree, root = _load(str(pyf))
    container, _ = _get_container(root, list(gp))
    return [c for c in container if c.tag == "Image2D"]


# --- data plots -------------------------------------------------------------------------

def test_a_data_plot_is_described_with_its_data_and_statistics(figure):
    from pyfigures.assistant.plot_info import parse_data_plot, plot_statistics, data_cleaning
    spec = parse_data_plot(C._decode_text(_child_text(_images(figure)[2], "custom_loading_script")))
    assert spec["kind"] == "box" and spec["csv"].endswith("counts.csv")
    stats = plot_statistics(spec)
    assert stats["test"] and len(stats["comparisons"]) == 3 and all("p_text" in c for c in stats["comparisons"])
    cleaning = data_cleaning(spec)
    assert "mutA: n=3" in cleaning and "'abc'" in cleaning and "never filled in" in cleaning


def test_edit_data_plot_switches_the_kind_and_keeps_the_rest(figure):
    from pyfigures.assistant.plot_info import parse_data_plot
    res = C.edit_data_plot(str(figure), [0], 2, kind="violin", only_significant=False)
    assert res.startswith("Data plot changed") and "'box' -> 'violin'" in res, res
    spec = parse_data_plot(C._decode_text(_child_text(_images(figure)[2], "custom_loading_script")))
    assert spec["kind"] == "violin" and spec["only_significant"] is False and spec["stats_mode"] == "auto"
    assert C.edit_data_plot(str(figure), [0], 0, kind="bar").startswith("ERROR: this panel is not a data plot")
    assert C.edit_data_plot(str(figure), [0], 2, kind="pie").startswith("ERROR: kind must be ")


def test_list_data_plot_kinds_names_the_kinds_and_the_seaborn_functions():
    text = C.list_data_plot_kinds()
    for kind in ("bar", "box", "violin", "scatter", "grouped", "catplot", "relplot", "displot", "heatmap"):
        assert kind in text


def test_adding_a_data_plot_says_what_was_left_out(figure, tmp_path):
    res = C.add_data_plot(str(figure), [0], str(tmp_path / "counts.csv"), kind="bar")
    assert "DATA:" in res and "'abc'" in res and "Tell the user" in res


# --- calibration ------------------------------------------------------------------------

def test_a_calibrated_pixel_size_is_not_overwritten_to_match(figure):
    res = ST.set_image_property(str(figure), [0], 1, "pixel_size", "1.24")
    assert res.startswith("ERROR") and "0.107" in res and "confirm_recalibration" in res, res
    assert O.set_scale_bar(str(figure), [0], 1, 10, px_to_unit=1.24).startswith("ERROR")
    assert O.set_scale_bar_all(str(figure), 10, px_to_unit=1.24).startswith("ERROR")
    assert abs(_pixel_size(_images(figure)[1])[0] - 0.107) < 1e-6           # unchanged
    # the user says the calibration is wrong: it changes
    res = ST.set_image_property(str(figure), [0], 1, "pixel_size", "0.2", confirm_recalibration=True)
    assert not res.startswith("ERROR"), res
    assert abs(_pixel_size(_images(figure)[1])[0] - 0.2) < 1e-6
    # the same value, or images without a calibration, are never refused
    assert not ST.set_image_property(str(figure), [0], 0, "pixel_size", "1.24").startswith("ERROR")


# --- comparable display -----------------------------------------------------------------

def test_match_display_range_sets_one_shared_range(figure):
    res = C.match_display_range(str(figure), files=["a.tif", "d.tif"])
    assert res.startswith("One shared display range"), res
    norms = {_child_text(i, "normalization") for i in _images(figure)[:2]}
    assert len(norms) == 1 and "custom" in norms.pop()
    assert C.match_display_range(str(figure), files=["nope.tif"]).startswith("ERROR")


# --- stacks -----------------------------------------------------------------------------

def test_time_stamps_on_a_z_stack_are_refused_and_padding_can_go(tmp_path, qapp):
    import tifffile
    stack = tmp_path / "z.tif"
    tifffile.imwrite(str(stack), (np.random.default_rng(1).random((8, 30, 30)) * 255).astype(np.uint8),
                     imagej=True, metadata={"axes": "ZYX"})
    (tmp_path / "f.yaml").write_text("output: f.pyf\nrows:\n  - - z.tif\n", encoding="utf-8")
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    build_figure_from_recipe(str(tmp_path / "f.yaml"))
    pyf = str(tmp_path / "f.pyf")
    res = S.add_stack_montage(pyf, str(stack), axis="z", frames="all", interval=5, unit="min")
    assert res.startswith("ERROR") and "time" in res and "Z stack" in res
    res = S.add_stack_montage(pyf, str(stack), axis="z", frames=[0, 1, 2, 3, 4, 5, 6], columns=3)
    assert "2 empty panel(s) pad the last row" in res and "slice numbers" in res, res
    assert S.remove_empty_placeholders(pyf).startswith("Removed 2")
    assert S.remove_empty_placeholders(pyf).startswith("No empty placeholder")
    res = S.add_stack_montage(pyf, str(stack), axis="z", frames=[0, 1, 2, 3, 4, 5, 6], columns=3, pad_last_row=False)
    assert "empty panel" not in res


# --- text -------------------------------------------------------------------------------

def test_change_text_size_changes_every_text(figure):
    tree, root = _load(str(figure))
    before = float(_child_text(root.find("SerializableQFont"), "size"))
    res = Q.change_text_size(str(figure), 2)
    assert res.startswith("All text sizes changed by +2 pt"), res
    tree, root = _load(str(figure))
    assert float(_child_text(root.find("SerializableQFont"), "size")) == before + 2
    plot_font = float(_child_text(_images(figure)[2], "publication_font_size"))
    Q.change_text_size(str(figure), -50 + 21)                     # never below 4 pt
    assert float(_child_text(_images(figure)[2], "publication_font_size")) >= 4
    assert plot_font > 0
    assert Q.change_text_size(str(figure), 0).startswith("ERROR")


# --- seaborn ----------------------------------------------------------------------------

def _tidy(tmp_path):
    rng = np.random.default_rng(2)
    lines = ["genotype,day,length"]
    for g in ("WT", "mut"):
        for d in ("d1", "d2"):
            lines += [f"{g},{d},{10 + rng.normal():.2f}" for _ in range(6)]
    lines.append("WT,d1,")
    (tmp_path / "tidy.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(tmp_path / "tidy.csv")


def test_a_faceted_seaborn_plot_is_added_described_and_edited(figure, tmp_path):
    from pyfigures.seaborn_plot import parse
    csv = _tidy(tmp_path)
    res = C.add_seaborn_plot(str(figure), [0], csv, "catplot", kind="box", x="genotype", y="length", col="day")
    assert "faceted by day" in res and "1 of 25 row(s) left out" in res, res
    script = C._decode_text(_child_text(_images(figure)[-1], "custom_loading_script"))
    assert parse(script)["col"] == "day"
    # it runs as PyFigures runs panel scripts: separate globals and locals
    class Panel:
        img = None
    panel = Panel()
    exec(compile(script, "panel", "exec"), {}, {"self": panel})
    assert type(panel.img).__name__ == "Figure" and len(panel.img.axes) == 2      # two facets
    res = C.edit_seaborn_plot(str(figure), [0], len(_images(figure)) - 1, kind="violin", remove=["col"])
    assert "'box' -> 'violin'" in res and "col 'day' -> None" in res, res
    assert C.add_seaborn_plot(str(figure), [0], csv, "boxplot", x="genotype", y="length",
                              col="day").startswith("ERROR: boxplot cannot facet")
    assert "its columns are" in C.add_seaborn_plot(str(figure), [0], csv, "relplot", x="day", y="lenght")
    assert C.edit_seaborn_plot(str(figure), [0], 0, kind="box").startswith("ERROR: this panel is not a seaborn plot")


def test_a_panel_added_to_the_canvas_gets_a_row_as_wide_as_the_others(figure, tmp_path):
    """User: "in your render.png the last row is not same length as the others" (a seaborn
    plot added to the canvas kept its natural 968 px under rows of 120 mm)."""
    csv = _tidy(tmp_path)
    res = C.add_seaborn_plot(str(figure), [], csv, "catplot", kind="box", x="genotype", y="length", col="day")
    assert not res.startswith("ERROR") and "group [1]" in res, res
    tree, root = _load(str(figure))
    rows = [c for c in root if c.tag == "Group"]
    assert len(rows) == 2 and not [c for c in root if c.tag == "Image2D"]
    widths = []
    for row in rows:
        # shown width = stored width / scale
        xs = [(float(_child_text(i, "x")),
               float(_child_text(i, "x")) + float(_child_text(i, "width")) / float(_child_text(i, "scale")))
              for i in row.iter("Image2D")]
        widths.append(max(b for _, b in xs) - min(a for a, _ in xs))
    assert abs(widths[0] - widths[1]) < 2, widths


def test_plots_read_excel_sheets(figure, tmp_path):
    """User: "is there also support for xls files, I think this is mandatory"."""
    pytest.importorskip("openpyxl")
    import pandas as pd
    book = tmp_path / "m.xlsx"
    with pd.ExcelWriter(book, engine="openpyxl") as w:
        pd.DataFrame({"note": ["no numbers here"]}).to_excel(w, sheet_name="notes", index=False)
        pd.read_csv(tmp_path / "counts.csv").to_excel(w, sheet_name="counts", index=False, startrow=1)
        pd.read_csv(_tidy(tmp_path)).to_excel(w, sheet_name="growth", index=False)
    res = C.add_data_plot(str(figure), [0], str(book), kind="box", sheet="counts")
    assert res.startswith("Data plot") or "added" in res, res
    assert "'abc'" in res                               # the cleaning note works on a sheet too
    from pyfigures.assistant.plot_info import parse_data_plot
    spec = parse_data_plot(C._decode_text(_child_text(_images(figure)[-1], "custom_loading_script")))
    assert spec["csv"].endswith("m.xlsx::counts")
    assert C.add_data_plot(str(figure), [0], str(book), sheet="nope").startswith("ERROR: no sheet 'nope'")
    assert "holds no numbers" in C.add_data_plot(str(figure), [0], str(book))           # first sheet: notes
    assert C.add_data_plot(str(figure), [0], str(tmp_path / "counts.csv"), sheet="x").startswith(
        "ERROR: sheet applies to Excel")
    res = C.add_seaborn_plot(str(figure), [0], str(book), "catplot", kind="box", x="genotype", y="length",
                             col="day", sheet="growth")
    assert "faceted by day" in res, res
    script = C._decode_text(_child_text(_images(figure)[-1], "custom_loading_script"))

    class Panel:
        img = None
    panel = Panel()
    exec(compile(script, "panel", "exec"), {}, {"self": panel})
    assert len(panel.img.axes) == 2


def test_a_recipe_takes_seaborn_panels(tmp_path, qapp):
    _tidy(tmp_path)
    (tmp_path / "s.yaml").write_text(
        "output: s.pyf\nrows:\n  - - {seaborn: tidy.csv, function: displot, kind: kde, x: length, row: genotype}\n",
        encoding="utf-8")
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    res = build_figure_from_recipe(str(tmp_path / "s.yaml"))
    assert not res.startswith("ERROR"), res
    summary = json.loads(res) if res.lstrip().startswith("{") else {"summary": res}
    assert "1 data plot" in json.dumps(summary)
