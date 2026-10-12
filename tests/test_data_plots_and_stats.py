"""
Tests for the data-plot + statistics feature:
- staplot.api façade (auto test selection, normality discrimination)
- add_data_plot MCP tool (scripted live panel + stats-provenance sidecar)
- add_significance_bracket_from_data (data-driven stars + sidecar)
- export_adjustment_ledger surfacing the statistics section
- the GUI "Add data plot from CSV…" action

Run with PYTEST_QT_API=pyqt6. The stats-dependent tests skip if staplot isn't
importable.
"""
from __future__ import annotations

import csv
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import matplotlib
matplotlib.use("Agg")

try:
    from staplot import api as sapi
    _STAPLOT = True
except Exception:
    _STAPLOT = False

needs_staplot = pytest.mark.skipif(not _STAPLOT, reason="staplot not importable")


def _wide_csv(path, columns: dict):
    n = max(len(v) for v in columns.values())
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(list(columns.keys()))
        for i in range(n):
            w.writerow([columns[k][i] if i < len(columns[k]) else "" for k in columns])
    return path


def _grouped_csv(path, rng):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["treatment", "time", "value"])
        for v in rng.normal(10, 1, 6):
            w.writerow(["ctrl", "0h", v])
        for v in rng.normal(11, 1, 6):
            w.writerow(["ctrl", "24h", v])
        for v in rng.normal(10, 1, 6):
            w.writerow(["drug", "0h", v])
        for v in rng.normal(18, 1, 6):
            w.writerow(["drug", "24h", v])
    return path


def _xy_csv(path, rng):
    x = np.linspace(0, 10, 30)
    y = 2 * x + rng.normal(0, 1, 30)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dose", "response"])
        for i in range(30):
            w.writerow([x[i], y[i]])
    return path


# ── staplot.api façade ──────────────────────────────────────────────────────

@needs_staplot
def test_is_normal_discriminates():
    rng = np.random.default_rng(0)
    assert sapi._is_normal(rng.normal(0, 1, 200))
    # a heavily skewed sample should fail the normality gate
    assert not sapi._is_normal(rng.exponential(1.0, 200))


@needs_staplot
def test_auto_test_two_groups_significant():
    rng = np.random.default_rng(1)
    t = sapi.table_from_columns({"WT": rng.normal(10, 1, 12).tolist(),
                                 "KO": rng.normal(15, 1, 12).tolist()})
    rec = sapi.auto_test(t)
    assert rec["n_groups"] == 2
    assert rec["test"] in ("Welch's t-test", "Mann-Whitney U test")
    assert len(rec["comparisons"]) == 1
    assert rec["comparisons"][0]["p"] < 0.05
    assert rec["sig_pairs"] and rec["sig_pairs"][0][0:2] == ("WT", "KO")


@needs_staplot
def test_auto_test_three_groups_has_omnibus_and_pairwise():
    rng = np.random.default_rng(2)
    t = sapi.table_from_columns({"A": rng.normal(10, 1, 10).tolist(),
                                 "B": rng.normal(10, 1, 10).tolist(),
                                 "C": rng.normal(16, 1, 10).tolist()})
    rec = sapi.auto_test(t)
    assert rec["n_groups"] == 3
    assert ("ANOVA" in rec["test"]) or ("Kruskal" in rec["test"])
    assert rec["omnibus"] and "p" in rec["omnibus"]
    # 3 groups → 3 pairwise comparisons
    assert len(rec["comparisons"]) == 3


@needs_staplot
def test_plot_returns_figure_and_record():
    rng = np.random.default_rng(3)
    t = sapi.table_from_columns({"WT": rng.normal(10, 1, 10).tolist(),
                                 "KO": rng.normal(14, 1, 10).tolist()})
    for kind in ("bar", "box", "violin"):
        fig, rec = sapi.plot(t, kind=kind, ylabel="signal")
        assert fig.__class__.__name__ == "Figure"
        assert rec is not None and "test" in rec
    fig, rec = sapi.plot(t, kind="scatter")
    assert rec is not None and "correlation" in rec["test"].lower()  # scatter → correlation


# ── add_data_plot MCP tool ──────────────────────────────────────────────────

@needs_staplot
def test_add_data_plot_adds_panel_and_stats_sidecar(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot, _decode
    from batoolset.drawings.shapes.image2d import Image2D
    import xml.etree.ElementTree as ET

    d = str(tmp_path)
    rng = np.random.default_rng(4)
    csvp = _wide_csv(os.path.join(d, "counts.csv"),
                     {"WT": rng.normal(10, 1, 10).round(3).tolist(),
                      "KO": rng.normal(15, 1, 10).round(3).tolist()})
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    msg = add_data_plot(pyf, [], csvp, kind="box", ylabel="cells/field", label="D")
    assert "Data-plot panel" in msg and "ERROR" not in msg

    root = ET.parse(pyf).getroot()
    scripts = [_decode(im.findtext("custom_loading_script"))
               for im in root.iter("Image2D")
               if im.findtext("custom_loading_script")]
    assert scripts and "staplot" in scripts[0] and "self.img" in scripts[0]

    sidecar = os.path.splitext(pyf)[0] + ".stats.json"
    assert os.path.isfile(sidecar)
    entries = json.load(open(sidecar, encoding="utf-8"))
    assert entries[0]["source"] == "data_plot"
    assert entries[0]["test"] and len(entries[0]["comparisons"]) == 1


@needs_staplot
def test_data_plot_script_executes_to_figure(tmp_path):
    """The generated live script must render under split globals/locals."""
    from pyfigures.mcp_server import create_figure, add_data_plot, _decode
    import xml.etree.ElementTree as ET
    import matplotlib.pyplot as plt

    d = str(tmp_path)
    os.chdir(d)  # use the installed staplot, not the source namespace dir
    rng = np.random.default_rng(5)
    csvp = _wide_csv(os.path.join(d, "c.csv"),
                     {"A": rng.normal(5, 1, 8).tolist(),
                      "B": rng.normal(9, 1, 8).tolist()})
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    add_data_plot(pyf, [], csvp, kind="bar", label="D")
    root = ET.parse(pyf).getroot()
    code = _decode(next(im.findtext("custom_loading_script")
                        for im in root.iter("Image2D")
                        if im.findtext("custom_loading_script")))
    ns = {"self": type("S", (), {"img": None})()}
    exec(code, {"np": np, "plt": plt}, ns)   # must not raise
    assert ns["self"].img is not None and ns["self"].img.__class__.__name__ == "Figure"
    plt.close("all")


@needs_staplot
def test_add_data_plot_bad_kind_errors(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    d = str(tmp_path)
    csvp = _wide_csv(os.path.join(d, "c.csv"), {"A": [1, 2, 3], "B": [4, 5, 6]})
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    assert add_data_plot(pyf, [], csvp, kind="pie").startswith("ERROR")
    assert add_data_plot(pyf, [], os.path.join(d, "missing.csv")).startswith("ERROR")


# ── add_significance_bracket_from_data ──────────────────────────────────────

@needs_staplot
def test_bracket_from_data_significant_and_ns(tmp_path):
    from pyfigures.mcp_server import (create_figure, add_image,
                                      add_significance_bracket_from_data)
    from batoolset.img import Img

    d = str(tmp_path)
    img_path = os.path.join(d, "a.tif")
    Img(np.full((40, 60), 120, dtype=np.uint8), dimensions='hw').save(img_path)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], img_path, label="A")

    rng = np.random.default_rng(6)
    a = rng.normal(1.0, 0.2, 10).tolist()
    b_diff = rng.normal(3.0, 0.2, 10).tolist()
    msg = add_significance_bracket_from_data(pyf, [], 0, x1=10, x2=50, y=6,
                                             values_a=a, values_b=b_diff,
                                             group_a="WT", group_b="KO")
    assert "ERROR" not in msg and ("*" in msg)

    # near-identical groups → n.s.
    b_same = [x + 0.001 for x in a]
    msg2 = add_significance_bracket_from_data(pyf, [], 0, x1=10, x2=50, y=16,
                                              values_a=a, values_b=b_same,
                                              group_a="WT", group_b="WT2")
    assert "n.s." in msg2

    sidecar = os.path.splitext(pyf)[0] + ".stats.json"
    entries = json.load(open(sidecar, encoding="utf-8"))
    assert len(entries) == 2
    assert all(e["source"] == "significance_bracket" for e in entries)


@needs_staplot
def test_ledger_includes_statistics(tmp_path):
    from pyfigures.mcp_server import (create_figure, add_data_plot,
                                      export_adjustment_ledger)
    d = str(tmp_path)
    rng = np.random.default_rng(7)
    csvp = _wide_csv(os.path.join(d, "counts.csv"),
                     {"WT": rng.normal(10, 1, 10).tolist(),
                      "KO": rng.normal(16, 1, 10).tolist()})
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    add_data_plot(pyf, [], csvp, kind="bar", label="D")
    led = json.loads(export_adjustment_ledger(pyf))
    assert led["statistics"] and led["statistics_methods_paragraph"]
    assert "Statistical analysis" in led["statistics_methods_paragraph"]


# ── GUI action ──────────────────────────────────────────────────────────────

@needs_staplot
def test_add_data_plot_action_adds_panel(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox, QDialog
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure
    from batoolset.drawings.shapes.image2d import Image2D

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    d = str(tmp_path)
    rng = np.random.default_rng(8)
    csvp = _wide_csv(os.path.join(d, "counts.csv"),
                     {"WT": rng.normal(10, 1, 10).tolist(),
                      "KO": rng.normal(15, 1, 10).tolist()})
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)

    monkeypatch.setattr(pfgui, "openFileNamesDialog", staticmethod(lambda *a, **k: [csvp]))

    class _OK:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _OK)

    n0 = len([s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)])
    g.add_data_plot_action()
    imgs = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)]
    assert len(imgs) == n0 + 1
    g._dirty = False


# ── two-way ANOVA / correlation / stats_mode override ───────────────────────

@needs_staplot
def test_auto_test_parametric_override():
    rng = np.random.default_rng(9)
    # skewed data → auto would go non-parametric; force each way and check
    t = sapi.table_from_columns({"A": rng.exponential(1.0, 12).tolist(),
                                 "B": (rng.exponential(1.0, 12) + 2).tolist()})
    assert sapi.auto_test(t, parametric=True)["test"] == "Welch's t-test"
    assert sapi.auto_test(t, parametric=False)["test"] == "Mann-Whitney U test"


@needs_staplot
def test_two_way_test_reports_effects(tmp_path):
    rng = np.random.default_rng(10)
    g = sapi.grouped_table_from_csv(_grouped_csv(os.path.join(str(tmp_path), "g.csv"), rng))
    rec = sapi.two_way_test(g)
    assert rec["test"] == "Two-way ANOVA"
    assert len(rec["effects"]) == 3
    labels = {e["effect"] for e in rec["effects"]}
    assert labels == {"factor A", "factor B", "A x B"}
    assert all(e["p"] is not None for e in rec["effects"])


@needs_staplot
def test_correlation_test_strong_linear(tmp_path):
    rng = np.random.default_rng(11)
    t = sapi.table_from_csv(_xy_csv(os.path.join(str(tmp_path), "xy.csv"), rng))
    rec = sapi.correlation_test(t)
    assert "Pearson" in rec["test"]
    assert rec["r"] > 0.9 and rec["p"] < 1e-6 and rec["n"] == 30


@needs_staplot
def test_add_data_plot_grouped_records_two_way(tmp_path):
    from pyfigures.mcp_server import (create_figure, add_data_plot,
                                      export_adjustment_ledger)
    d = str(tmp_path)
    rng = np.random.default_rng(12)
    csvp = _grouped_csv(os.path.join(d, "g.csv"), rng)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    msg = add_data_plot(pyf, [], csvp, kind="grouped", ylabel="signal", label="E")
    assert "ERROR" not in msg
    entries = json.load(open(os.path.splitext(pyf)[0] + ".stats.json", encoding="utf-8"))
    assert entries[0]["kind"] == "grouped" and entries[0]["effects"]
    led = json.loads(export_adjustment_ledger(pyf))
    assert "Two-way ANOVA" in led["statistics_methods_paragraph"]


@needs_staplot
def test_add_data_plot_scatter_records_correlation(tmp_path):
    from pyfigures.mcp_server import (create_figure, add_data_plot,
                                      export_adjustment_ledger)
    d = str(tmp_path)
    rng = np.random.default_rng(13)
    csvp = _xy_csv(os.path.join(d, "xy.csv"), rng)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    msg = add_data_plot(pyf, [], csvp, kind="scatter", label="F")
    assert "ERROR" not in msg
    entries = json.load(open(os.path.splitext(pyf)[0] + ".stats.json", encoding="utf-8"))
    assert entries[0]["kind"] == "scatter" and entries[0]["r"] is not None
    led = json.loads(export_adjustment_ledger(pyf))
    assert "correlation" in led["statistics_methods_paragraph"].lower()


@needs_staplot
def test_add_data_plot_stats_mode_validation(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    d = str(tmp_path)
    csvp = _wide_csv(os.path.join(d, "c.csv"), {"A": [1, 2, 3], "B": [4, 5, 6]})
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    assert add_data_plot(pyf, [], csvp, stats_mode="bogus").startswith("ERROR")


@needs_staplot
def test_grouped_and_scatter_scripts_execute(tmp_path):
    """The grouped and scatter live scripts must render to a Figure too."""
    from pyfigures.mcp_server import create_figure, add_data_plot, _decode
    import xml.etree.ElementTree as ET
    import matplotlib.pyplot as plt
    d = str(tmp_path)
    os.chdir(d)
    rng = np.random.default_rng(14)
    for kind, mk in (("grouped", _grouped_csv), ("scatter", _xy_csv)):
        csvp = mk(os.path.join(d, f"{kind}.csv"), rng)
        pyf = os.path.join(d, f"{kind}.pyf")
        create_figure(pyf, mode="canvas")
        add_data_plot(pyf, [], csvp, kind=kind)
        root = ET.parse(pyf).getroot()
        code = _decode(next(im.findtext("custom_loading_script")
                            for im in root.iter("Image2D")
                            if im.findtext("custom_loading_script")))
        ns = {"self": type("S", (), {"img": None})()}
        exec(code, {"np": np, "plt": plt}, ns)
        assert ns["self"].img.__class__.__name__ == "Figure"
        plt.close("all")
