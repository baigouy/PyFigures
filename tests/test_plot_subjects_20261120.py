"""Several cells per animal (user 2026-11-20): a data plot's subject= column makes the
animals the replicates (statistics on their means, a large dot per animal)."""
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("staplot.stats.nested")


def test_subjects_are_the_replicates(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot, edit_data_plot
    from pyfigures.mcp_tools.core import _load, _child_text
    from pyfigures.assistant.plot_info import parse_data_plot
    from batoolset.drawings.shapes.image2d import Image2D
    from staplot import api
    rng = np.random.default_rng(1)
    rows = ["genotype,animal,area"] + [f"{g},{g}{a},{b + rng.normal():.3f}" for g, b in (("WT", 10), ("KO", 12))
                                       for a in range(3) for _ in range(10)]
    csv = tmp_path / "cells.csv"
    csv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    out = add_data_plot(pyf, [], str(csv), kind="box", columns=["genotype", "area"], subject="animal")
    assert "ERROR" not in out, out

    def script():
        _t, root = _load(pyf)
        return _child_text(list(root.iter("Image2D"))[-1], "custom_loading_script")
    assert parse_data_plot(script())["subject"] == "animal"
    fig = Image2D(custom_loading_script=script()).img
    dots = [a for a in fig.findobj() if api.plot_part(a) == "subject_means"]
    assert sum(len(d.get_offsets()) for d in dots) == 6
    _t, root = _load(pyf)
    stats = [json.loads(e.text) for e in root.iter() if e.tag == "stats_provenance" and e.text] or []
    assert "ERROR" not in edit_data_plot(pyf, [], 0, subject="")
    assert parse_data_plot(script()).get("subject") is None
    assert edit_data_plot(pyf, [], 0, subject="animal", kind="scatter").startswith("ERROR")
    assert stats is not None
