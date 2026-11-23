"""2026-11-19 (user, live app): "massively increase font size in c and d" made both
plots' text 16 pt, but the row's spacing went wrong until the width spinner was
nudged: the open figure took the edit up without fitting the rows to the figure
width again, and a plot with bigger text has another shape."""
import asyncio
import os
import threading

from test_assistant_live import gui, runtime  # noqa: F401  (fixtures)

from _tables import measurements_xlsx  # noqa: E402  (the playground file is not in the repository)


def test_a_plot_edit_keeps_every_row_at_the_figure_width(qapp, gui, runtime, tmp_path):  # noqa: F811
    from test_human_requests_20261112 import _live
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    g, _run, _ = _live(qapp, gui, tmp_path)
    dispatch = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools['use_pyfigures_tool'].fn

    def call(tool_name, arguments, **more):
        box = {}

        def work():
            try:
                box['out'] = asyncio.run(dispatch(tool_name=tool_name, arguments=arguments, **more))
            except Exception as e:
                box['error'] = e
        t = threading.Thread(target=work)
        t.start()
        while t.is_alive():
            qapp.processEvents()
            t.join(0.02)
        if 'error' in box:
            raise box['error']
        return box['out']

    for _ in range(2):                                    # two plots in one row, like c and d
        out = call('add_data_plot', {'group_path': [0], 'csv_path': measurements_xlsx(tmp_path)})
        assert 'ERROR' not in str(out), out
    width = g.size_spinbox.value()
    from pyfigures.assistant.partner_gui import panels
    n = len(list(panels(g.paint.EZFIG_panel.shapes_to_draw)))
    refs = [chr(ord('a') + n - 2), chr(ord('a') + n - 1)]   # the plots are the last panels
    # "make font of graphs much wider": both plots of the row at once, as the chat did
    out = call('edit_data_plot', {}, batch=[{'panel_ref': r, 'font_pt': 14} for r in refs])
    assert out['batch_done'] == 2, out
    canvas = g.paint.EZFIG_panel
    # drawn as the screen does: drawing fits the plots' text again, which changed their
    # shape after the layout (14 pt: each plot 105 -> 121 px, overlapping its neighbour)
    canvas.grab()
    # since 2026-11-23 a screen paint refits the plots' text 400 ms later (Image2D
    # PAGE_TEXT_REDRAW_DELAY_MS, no LaTeX redraw per paint) and the rows are repacked
    # after it: check the layout the user sees once that settled
    import time
    end = time.time() + 1.5
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.02)
    canvas.grab()
    qapp.processEvents()
    for shape in canvas.shapes_to_draw:
        if getattr(shape, 'content', None):
            assert abs(shape.getRect(all=False).width() - width) <= 0.5, (shape.getRect(all=False).width(), width)
    rects = [p.getRect(all=True) for _path, _i, p in panels(canvas.shapes_to_draw)]
    for i, a in enumerate(rects):                         # no panel drawn over another
        for b in rects[i + 1:]:
            inter = a.intersected(b)
            assert inter.width() <= 0.5 or inter.height() <= 0.5, (a, b)
