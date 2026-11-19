"""2026-11-19 (user): the empty canvas sketches how a figure is built: drop files,
drop a panel onto another (row / column / swap...), drag one to empty space (extrude)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_the_empty_canvas_draws_the_three_gestures(qtbot):
    from qtpy.QtGui import QImage, QPainter
    from pyfigures.gui.ezfig import MyWidget
    w = MyWidget()
    qtbot.addWidget(w)
    titles = [t for _k, t, _d in w.BUILD_HINTS]
    assert titles == ["Drop image files", "Drag a panel onto another", "Drag a panel to empty space"]
    assert "Extrude" in w.BUILD_HINTS[2][2] and "To row" in w.BUILD_HINTS[1][2]
    for width in (1200, 380):                  # sketches side by side, or words when narrow
        w.resize(width, 700)
        img = QImage(w.size(), QImage.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        w.render(p)
        p.end()
        assert not img.isNull()


def test_plot_tools_have_their_own_category():
    """2026-11-19: every plot / table tool fell into 'setup' (server info), where a model
    browsing the chat's categories never looks; 30 other tools too."""
    import asyncio
    from pyfigures.assistant.categorized_mcp import CATEGORIES, category_for
    from pyfigures import mcp_server as m
    assert "plots" in CATEGORIES
    for n in ("add_data_plot", "edit_data_plot", "data_plot_code", "add_seaborn_plot", "add_table_panel",
              "describe_table", "list_factor_columns", "summarize_table"):
        assert category_for(n) == "plots", n
    setup = sorted(n for n in (t.name for t in asyncio.run(m.mcp.list_tools())) if category_for(n) == "setup")
    assert "remove_rois" not in setup and "match_display_range" not in setup and len(setup) <= 15, setup
