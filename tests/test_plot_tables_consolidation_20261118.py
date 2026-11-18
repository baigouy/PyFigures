"""Consolidation gathers the tables of plot panels too (user, 2026-11-18: "staplot should
also handle the consolidation, which is just the excel file in this case"; "consolidation
in pyfig means gathering of raw data"; "you should also add tests for that, that is
really key").

A data plot or a seaborn plot has no image file: its table is named in its script, so
Save & Consolidate left the Excel / CSV file behind and the bundle was not
self-contained."""
import os
import shutil

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import plot_tables as PT  # noqa: E402
from pyfigures.mcp_tools import content as C  # noqa: E402
from pyfigures.mcp_tools.core import _child_text, _load  # noqa: E402

pytest.importorskip("openpyxl")


def _scripts(pyf):
    _tree, root = _load(str(pyf))
    return [C._decode_text(_child_text(i, "custom_loading_script")) for i in root.iter("Image2D")]


@pytest.fixture
def figure(tmp_path, qapp):
    """A figure in tmp/work with: a box plot of an Excel sheet, a seaborn plot of
    another sheet of the same workbook, a bar plot of a CSV, and a box plot of a
    different CSV of the same name (other folder)."""
    data = tmp_path / "raw data"
    other = tmp_path / "other"
    data.mkdir()
    other.mkdir()
    rng = np.random.default_rng(0)
    wide = pd.DataFrame({"WT": rng.normal(42, 2, 8), "mut": rng.normal(35, 2, 8)})
    tidy = pd.DataFrame({"genotype": ["WT", "mut"] * 12, "day": ["d1"] * 12 + ["d2"] * 12,
                         "length": rng.normal(10, 1, 24)})
    with pd.ExcelWriter(data / "measurements.xlsx", engine="openpyxl") as w:
        wide.to_excel(w, sheet_name="counts", index=False)
        tidy.to_excel(w, sheet_name="growth", index=False)
    wide.to_csv(data / "counts.csv", index=False)
    (wide + 5).to_csv(other / "counts.csv", index=False)          # same name, other data
    work = tmp_path / "work"
    work.mkdir()
    (work / "f.yaml").write_text(
        "output: f.pyf\nrows:\n"
        f"  - - {{plot: '{(data / 'measurements.xlsx').as_posix()}', sheet: counts, kind: box}}\n"
        f"    - {{seaborn: '{(data / 'measurements.xlsx').as_posix()}', sheet: growth, function: catplot, "
        "kind: box, x: genotype, y: length, col: day}\n"
        f"  - - {{plot: '{(data / 'counts.csv').as_posix()}', kind: bar}}\n"
        f"    - {{plot: '{(other / 'counts.csv').as_posix()}', kind: box}}\n", encoding="utf-8")
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    res = build_figure_from_recipe(str(work / "f.yaml"))
    assert not res.startswith("ERROR"), res
    return work / "f.pyf", data, other


def test_the_tables_of_plot_panels_are_found(figure):
    pyf, data, other = figure
    found = [PT.table_paths(s) for s in _scripts(pyf)]
    assert found == [[str(data / "measurements.xlsx")], [str(data / "measurements.xlsx")],
                     [str(data / "counts.csv")], [str(other / "counts.csv")]]
    assert PT.table_paths("self.img = 1\nx = r'C:/not/a/plot.csv'") == []         # not a plot script


def test_consolidation_copies_each_table_once_and_points_the_plots_at_the_copies(figure):
    pyf, data, other = figure
    bundle = str(pyf)[:-4] + ".files"
    copied = dict(PT.consolidate_plot_tables(str(pyf)))
    # the workbook used by two panels is copied once; the two counts.csv keep apart
    assert sorted(os.path.basename(v) for v in copied.values()) == ["counts.csv", "counts_2.csv",
                                                                     "measurements.xlsx"]
    assert all(os.path.dirname(v) == bundle for v in copied.values())
    scripts = _scripts(pyf)
    from pyfigures.assistant.plot_info import parse_data_plot
    from pyfigures.seaborn_plot import parse
    assert parse_data_plot(scripts[0])["csv"] == os.path.join(bundle, "measurements.xlsx") + "::counts"
    # the seaborn plot: its code and its settings header both name the copy and the sheet
    assert parse(scripts[1])["csv"] == os.path.join(bundle, "measurements.xlsx") + "::growth"
    assert str(data) not in scripts[1]
    assert {parse_data_plot(s)["csv"] for s in scripts[2:]} == {
        os.path.join(bundle, "counts.csv"), os.path.join(bundle, "counts_2.csv")}
    # each copy holds the data of its own source
    assert pd.read_csv(copied[str(other / "counts.csv")]).equals(pd.read_csv(other / "counts.csv"))
    # a second consolidation finds everything already in the bundle
    assert PT.consolidate_plot_tables(str(pyf)) == []
    assert _scripts(pyf) == scripts


def test_a_consolidated_figure_plots_without_its_original_tables(figure):
    pyf, data, other = figure
    PT.consolidate_plot_tables(str(pyf))
    shutil.rmtree(data)
    shutil.rmtree(other)

    class Panel:
        img = None
    for script in _scripts(pyf):
        panel = Panel()
        exec(compile(script, "panel", "exec"), {}, {"self": panel})
        assert type(panel.img).__name__ == "Figure", script[:200]


def test_a_moved_bundle_finds_its_tables_sheets_and_seaborn_settings(figure, tmp_path):
    pyf, data, other = figure
    PT.consolidate_plot_tables(str(pyf))
    moved = tmp_path / "elsewhere" / "deeper"
    moved.mkdir(parents=True)
    shutil.copy2(pyf, moved / "f.pyf")
    shutil.copytree(str(pyf)[:-4] + ".files", moved / "f.files")
    shutil.rmtree(pyf.parent)
    from pyfigures.path_resolution import resolve_moved_paths
    xml = (moved / "f.pyf").read_text(encoding="utf-8")
    xml, relocated = resolve_moved_paths(xml, str(moved / "f.pyf"))
    assert relocated
    (moved / "f.pyf").write_text(xml, encoding="utf-8")
    scripts = _scripts(moved / "f.pyf")
    from pyfigures.seaborn_plot import parse
    new_book = os.path.normcase(os.path.normpath(str(moved / "f.files" / "measurements.xlsx")))
    sns_csv = parse(scripts[1])["csv"]
    assert sns_csv.endswith("::growth")
    assert os.path.normcase(os.path.normpath(sns_csv[:-len("::growth")])) == new_book
    for script in scripts:                       # every table path now points into the moved bundle
        for path in PT.table_paths(script):
            assert os.path.normcase(str(moved / "f.files")) in os.path.normcase(path), path


def test_rewriting_keeps_the_sheet_and_leaves_other_strings():
    script = "_csv = 'C:/a/book.xlsx::counts'\nlabel = 'C:/a/book.xlsx is my data'\n_x = 'C:/a/book.xlsx'\n"
    out = PT.rewrite_table_paths(script, {"C:/a/book.xlsx": "D:/b/book.xlsx"})
    assert "'D:/b/book.xlsx::counts'" in out and "'D:/b/book.xlsx'" in out
    assert "'C:/a/book.xlsx is my data'" in out


def test_headless_consolidate_gathers_the_tables(figure, tmp_path):
    pyf, data, other = figure
    from pyfigures.gui.headless_ops import consolidate
    out = consolidate(str(pyf), str(tmp_path / "bundle" / "g.pyf"))
    files = sorted(os.listdir(tmp_path / "bundle" / "g.files"))
    assert {"measurements.xlsx", "counts.csv", "counts_2.csv"} <= set(files), files
    assert all(str(tmp_path / "bundle" / "g.files") in "".join(PT.table_paths(s)) or not PT.table_paths(s)
               for s in _scripts(out))
