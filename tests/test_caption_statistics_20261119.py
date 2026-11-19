"""2026-11-19 (user): the statistics belong in the text that goes with the figure, not
printed under the plots; the user can edit that text, so an edited paragraph is never
rewritten."""
import json
import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(__file__)
PLAYGROUND = os.path.join(HERE, "..", "demo_figures", "plots_playground")


def _two_factors(tmp_path):
    import numpy as np
    rng = np.random.default_rng(1)
    rows = ["genotype,treatment,value"]
    for g, m in (("WT", 30), ("mutA", 22)):
        for t, d in (("ctrl", 0), ("drug", 4)):
            rows += [f"{g},{t},{v:.2f}" for v in rng.normal(m + d, 1.0, 8)]
    p = tmp_path / "two.csv"
    p.write_text("\n".join(rows), encoding="utf-8")
    return str(p)


def _figure(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    pyf = str(tmp_path / "fig.pyf")
    create_figure(pyf)
    out = add_data_plot(pyf, [], _two_factors(tmp_path), kind="grouped")
    assert not str(out).startswith("ERROR"), out
    return pyf


def test_the_paragraph_names_the_test_effects_and_stars(tmp_path):
    from pyfigures.stats_legend import statistics_text
    text = statistics_text(_figure(tmp_path))
    assert text.startswith("Statistics: ")
    assert "two-way ANOVA (genotype p" in text and "genotype × treatment" in text
    assert "within each treatment level" in text and "****p < 0.0001" in text


def test_added_updated_and_an_edited_paragraph_left_alone(tmp_path):
    from pyfigures.mcp_server import (add_statistics_to_caption, caption_statistics, get_figure_caption,
                                      set_figure_caption)
    pyf = _figure(tmp_path)
    set_figure_caption(pyf, "Growth of the mutants.")
    out = add_statistics_to_caption(pyf)
    assert out.startswith("Statistics paragraph added")
    cap = json.loads(get_figure_caption(pyf))["caption"]
    assert cap.startswith("Growth of the mutants.\n\nStatistics: ")
    assert add_statistics_to_caption(pyf).startswith("The caption's statistics are up to date")
    # the user edits the caption elsewhere (the statistics text stays remembered)
    set_figure_caption(pyf, cap + " Three replicates.")
    assert "up to date" in add_statistics_to_caption(pyf)
    # the user rewrites the paragraph itself: never replaced
    set_figure_caption(pyf, "Growth. Statistics: my own words.")
    out = add_statistics_to_caption(pyf)
    assert "edited by hand" in out
    assert json.loads(get_figure_caption(pyf))["caption"] == "Growth. Statistics: my own words."
    assert add_statistics_to_caption(pyf, force=True).startswith("Statistics paragraph added")
    assert caption_statistics(pyf).startswith("Statistics: ")


def test_a_stale_paragraph_is_reported_then_updated(tmp_path):
    from pyfigures.mcp_server import add_statistics_to_caption, get_figure_caption
    pyf = _figure(tmp_path)
    add_statistics_to_caption(pyf)
    side = os.path.splitext(pyf)[0] + ".caption.json"
    entry = json.load(open(side, encoding="utf-8"))
    old = entry["statistics"].replace("Statistics: ", "Statistics: (old) ")
    entry["statistics"], entry["caption"] = old, old          # as if the data had changed since
    json.dump(entry, open(side, "w", encoding="utf-8"))
    assert "no longer match" in json.loads(get_figure_caption(pyf))["statistics_note"]
    assert add_statistics_to_caption(pyf).startswith("Statistics paragraph of the caption updated")
    assert "statistics_note" not in json.loads(get_figure_caption(pyf))


def test_the_caption_dialog_inserts_and_keeps_an_edit(qtbot):
    from pyfigures.gui.caption_dialog import CaptionDialog
    dlg = CaptionDialog(None, "", "Legend.", statistics=lambda: "Statistics: (a) t-test.")
    qtbot.addWidget(dlg)
    dlg.insert_statistics()
    assert dlg.doc.toPlainText() == "Legend.\n\nStatistics: (a) t-test."
    assert dlg.values()["statistics"] == "Statistics: (a) t-test."
    dlg._statistics = lambda: "Statistics: (a) Welch's t-test."
    dlg.insert_statistics()
    assert dlg.doc.toPlainText() == "Legend.\n\nStatistics: (a) Welch's t-test."
    dlg.doc.setPlainText("Legend.\n\nStatistics: rewritten by me.")
    dlg._statistics = lambda: "Statistics: (a) Mann-Whitney."
    dlg.insert_statistics()
    assert "rewritten by me" in dlg.doc.toPlainText() and "Mann-Whitney" not in dlg.doc.toPlainText()
    assert "edited by hand" in dlg.stats_note.text()


@pytest.mark.skipif(not os.path.isfile(os.path.join(PLAYGROUND, "06_split_violins.pyf")), reason="demo figures")
def test_split_violins_name_their_halves():
    from pyfigures.stats_legend import statistics_text
    text = statistics_text(os.path.join(PLAYGROUND, "06_split_violins.pyf"))
    assert "at each genotype, female vs male compared" in text
