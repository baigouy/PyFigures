"""Every MCP call on a figure is logged beside it and its changes can be
undone (pyfigures/history.py): through the MCP tools list_history / undo_last,
the command line (python -m pyfigures.history) and the GUI (QC > MCP call
history / undo…)."""
from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def _call(name, **args):
    """A call as an MCP client makes it (through the registered tool)."""
    try:
        res = asyncio.run(M.mcp.call_tool(name, args))
    except Exception as e:                  # a refused call is an MCP error
        return f"ERROR: {e}"
    content = res[0] if isinstance(res, tuple) else res
    return "\n".join(getattr(c, "text", "") for c in content)


@pytest.fixture
def figure(tmp_path, qapp):
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("L", (200, 150), 90).save(src)
    return tmp_path / "f.pyf", src


def test_calls_are_logged_and_changes_undone_in_order(figure):
    from pyfigures import history
    pyf, src = figure
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    after_create = pyf.read_bytes()
    _call("add_image", pyf_path=str(pyf), group_path=[0], filename=str(src))
    after_add = pyf.read_bytes()
    _call("set_figure_caption", pyf_path=str(pyf), caption="A caption.")
    _call("describe_figure", pyf_path=str(pyf))                  # read-only, logged too
    log = history.entries(str(pyf))
    assert [e["tool"] for e in log] == ["create_figure", "add_image", "set_figure_caption",
                                        "describe_figure"]
    assert [e["changed"] for e in log] == [True, True, True, False]
    assert log[1]["arguments"]["filename"] == str(src)
    listing = _call("list_history", pyf_path=str(pyf))
    assert "add_image" in listing and "4 logged call(s)" in listing
    caption = pyf.with_suffix(".caption.json")
    assert caption.exists()
    assert "Undid call 3" in _call("undo_last", pyf_path=str(pyf))
    assert not caption.exists()                                 # the sidecar it added is gone
    assert pyf.read_bytes() == after_add
    _call("undo_last", pyf_path=str(pyf))
    assert pyf.read_bytes() == after_create
    assert "undone" in _call("list_history", pyf_path=str(pyf))
    # the snapshots are never taken for figures by folder scans
    hist = history.history_dir(str(pyf))
    assert not [f for _, _, fs in os.walk(hist) for f in fs if f.endswith(".pyf")]


def test_errors_are_logged_and_python_calls_are_not(figure):
    from pyfigures import history
    pyf, src = figure
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    res = _call("set_scale_bar", pyf_path=str(pyf), group_path=[0], image_index=5,
                bar_width_in_units=1)
    assert res.startswith("ERROR")
    M.add_image(str(pyf), [0], str(src))                         # a Python caller (recipe, GUI)
    log = history.entries(str(pyf))
    assert [e["tool"] for e in log] == ["create_figure", "set_scale_bar"]
    assert log[1]["status"] == "error" and not log[1]["changed"]
    # misspelt figure: nothing is left behind
    _call("describe_figure", pyf_path=str(pyf.with_name("nope.pyf")))
    assert not os.path.exists(history.history_dir(str(pyf.with_name("nope.pyf"))))


def test_undo_refuses_to_drop_a_change_made_outside_the_server(figure):
    pyf, src = figure
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    _call("add_image", pyf_path=str(pyf), group_path=[0], filename=str(src))
    M.set_figure_caption(str(pyf), "Typed in the GUI.")         # not logged
    gui_state = pyf.read_bytes()
    res = _call("undo_last", pyf_path=str(pyf))
    assert res.startswith("ERROR") and "not in the log" in res
    assert pyf.read_bytes() == gui_state
    assert "Undid call 2" in _call("undo_last", pyf_path=str(pyf), force=True)


def test_recipe_builds_are_logged_under_their_output(tmp_path, qapp):
    from PIL import Image
    from pyfigures import history
    Image.new("L", (64, 48), 120).save(tmp_path / "a.png")
    text = "output: built.pyf\nrows:\n  - [a.png]\n"
    _call("build_figure_from_recipe", recipe_path=str(tmp_path / "r.yaml"), recipe_text=text)
    log = history.entries(str(tmp_path / "built.pyf"))
    assert len(log) == 1 and log[0]["tool"] == "build_figure_from_recipe" and log[0]["changed"]
    assert "rows" in log[0]["arguments"]["recipe_text"]


def test_command_line_lists_and_undoes(figure, capsys):
    from pyfigures import history
    pyf, src = figure
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    first = pyf.read_bytes()
    _call("add_image", pyf_path=str(pyf), group_path=[0], filename=str(src))
    assert history.main([str(pyf)]) == 0
    assert "add_image" in capsys.readouterr().out
    assert history.main([str(pyf), "--undo"]) == 0
    assert pyf.read_bytes() == first
    assert history.main([str(pyf), "--undo", "5"]) == 0          # undoes what is left
    assert history.main([str(pyf), "--undo"]) == 1               # nothing left


def test_old_snapshots_are_pruned(figure, monkeypatch):
    from pyfigures import history
    pyf, _ = figure
    monkeypatch.setattr(history, "MAX_SNAPSHOTS", 3)
    for k in range(6):
        _call("create_figure", pyf_path=str(pyf), num_groups=1 + k % 2)
    snaps = [d for d in os.listdir(history.history_dir(str(pyf))) if d.isdigit()]
    assert len(snaps) == 3
    assert len(history.entries(str(pyf))) == 6                  # the log is kept whole


def test_gui_shows_the_history_and_undoes_the_last_mcp_change(figure, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    pyf, src = figure
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    first = pyf.read_bytes()
    _call("add_image", pyf_path=str(pyf), group_path=[0], filename=str(src))
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    shown = {}

    class _Dlg:
        def __init__(self, *a, main_widget=None, **k):
            from qtpy.QtWidgets import QTextBrowser
            shown["text"] = main_widget.findChild(QTextBrowser).toPlainText()
            self.selected_option = "Undo last MCP change"

        def exec_(self):
            return 1

    monkeypatch.setattr(pfgui, "CustomDialog", _Dlg)
    g = EZFIG_GUI()
    g.reload_state(str(pyf), append=False)
    g.current_file = str(pyf)
    g._dirty = False
    g.mcp_history_dialog()
    assert "add_image" in shown["text"]
    assert pyf.read_bytes() == first
    assert not g._dirty
    # unsaved edits in the window are never overwritten
    _call("add_image", pyf_path=str(pyf), group_path=[0], filename=str(src))
    g._dirty = True
    before = pyf.read_bytes()
    assert g.undo_last_mcp_change() is None and pyf.read_bytes() == before
    g._dirty = False
