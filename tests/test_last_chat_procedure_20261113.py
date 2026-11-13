"""The user's last chat before the replay tool (2026-11-13 14:15, tests/data/chats/
chat_20261113_1415.jsonl: requests, tool calls and results only), replayed as a procedure
on a figure laid out like theirs: panels a, b, c in the first row, d, e in the second;
4 lines and 2 boxes on b, 49 ellipses on d, 26 triangles on e.

The six steps it kept: rotate all 25°, black panel backgrounds, stroke 0.65 on the
4 lines of b, then on the 77 other ROIs, white letters, panel backgrounds from the
images (the request that failed before fill_color="auto" existed)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import gui, runtime  # noqa: E402,F401  (fixtures)
from pyfigures.assistant import chat_replay as R  # noqa: E402

CHAT = Path(__file__).parent / 'data' / 'chats' / 'chat_20261113_1415.jsonl'


def test_the_chat_gives_its_six_steps():
    steps = R.procedure_steps(R.load_steps(CHAT))
    assert [(s.tool, len(s.batch or [])) for s in steps] == [
        ('transform_image', 5), ('set_image_property', 5), ('set_roi_properties', 4),
        ('set_roi_properties', 77), ('edit_panel_letters', 0), ('set_image_property', 5)]
    assert steps[-1].arguments == {'property_name': 'fill_color', 'value': 'auto'}


def _figure(tmp_path):
    """Five panels (a b c / d e), each with a plain background of its own colour."""
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / 'wing_figure.pyf')
    create_figure(pyf, mode='groups', num_groups=2)
    shades = {'a': 250, 'b': 240, 'c': 200, 'd': 10, 'e': 180}
    for k, (name, bg) in enumerate(shades.items()):
        img = np.full((120, 160), bg, np.uint8)
        img[40:80, 60:100] = 255 - bg                         # something on the background
        p = str(tmp_path / f'{name}.tif')
        Img(img, dimensions='hw').save(p)
        add_image(pyf, [0 if k < 3 else 1], p)
    return pyf


def test_the_last_chat_as_a_procedure_on_a_figure_like_the_users(qapp, gui, runtime, tmp_path):  # noqa: F811
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import panels as image_panels
    from pyfigures.gui.replay_dialog import run_in_thread, run_procedure_on_window
    from pyfigures.panel_source_preview import border_colour
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    g.auto_lettering_checkbox.setChecked(True)
    g.update_letters()
    launch.start_live_session(g)
    panels = lambda: [p for _, _, p in image_panels(g.paint.EZFIG_panel.shapes_to_draw)]
    assert len(panels()) == 5

    # the ROIs the chat recoloured, after each panel's letter (annotation 0), thick (2 pt)
    runner = R.Runner()
    roi = lambda tool, ref, items: run_in_thread(lambda: runner.run(R.Step('', 0, tool, {
        'panel_ref': ref, 'stroke': 2.0}, items)))
    box = lambda x: {'x': x, 'y': 5, 'width': 10, 'height': 10}
    line = lambda x: {'x1': x, 'y1': 30, 'x2': x + 20, 'y2': 50}
    for kind, item in (('ellipse', box(2)), ('rect', box(20)), ('line', line(5)), ('line', line(30)),
                       ('ellipse', box(60)), ('rect', box(80)), ('line', line(60)), ('line', line(90))):
        roi('add_roi_' + kind, 'b', [item])
    roi('add_roi_ellipse', 'd', [box(2 + 3 * (k % 50)) for k in range(49)])
    roi('add_roi_polygon', 'e', [{'points': [[5 + 6 * k, 5], [8 + 6 * k, 12], [2 + 6 * k, 12]]} for k in range(26)])

    def strokes(ref):
        p = panels()['abcde'.index(ref)]
        return [a.stroke for a in p.annotations if type(a).__name__ in
                ('Line2D', 'Rectangle2D', 'Ellipse2D', 'Polygon2D')]
    assert strokes('b') == [2.0] * 8 and len(strokes('d')) == 49 and len(strokes('e')) == 26

    procedure = tmp_path / 'last_chat.json'
    R.save_procedure(R.procedure_steps(R.load_steps(CHAT)), procedure, source=CHAT)
    done, total, failed = run_procedure_on_window(g, str(procedure))
    assert (done, total, failed) == (6, 6, []), failed

    assert [p.theta for p in panels()] == [25] * 5
    assert [p.fill_color for p in panels()] == [border_colour(p) for p in panels()]
    assert panels()[3].fill_color == border_colour(panels()[3]) != panels()[0].fill_color
    # b: the chat changed annotations 3, 4, 7, 8 (lines) then 2, 6 (boxes); its ellipses 1, 5 stay
    assert strokes('b') == [2.0, 0.65, 0.65, 0.65, 2.0, 0.65, 0.65, 0.65]
    assert strokes('d') == [0.65] * 49 and strokes('e') == [0.65] * 26
