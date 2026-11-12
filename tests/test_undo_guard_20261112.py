"""User chat 2026-11-12: "i wanna edit smallest ROI inset in b" made a second inset of
that ROI; the user undid it with the message's undo button and said "No I just wanted you
to open the dialog": the model's own undo then removed the step before (the figure being
opened), the canvas went empty, and it had to redo.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import uuid

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import gui, runtime  # noqa: E402,F401  (fixtures)


def _figure(tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    p = str(tmp_path / "w.tif")
    Img((np.random.default_rng(2).random((200, 300)) * 255).astype(np.uint8), dimensions="hw").save(p)
    pyf = str(tmp_path / "w.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], p)
    return pyf


@pytest.fixture
def live(qapp, gui, tmp_path):  # noqa: F811
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import panels
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    session = launch.start_live_session(g)
    panel = next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    panel.annotations.append(Rectangle2D(20, 30, 60, 40, color=0xFFFF00, stroke=2))
    g.save_state(show_popup=False)

    def cmd(operation, **arguments):
        s = session.snapshot()
        return session.execute(dict(operation=operation, arguments=arguments, request_id=str(uuid.uuid4()),
                                    session_id=s["session_id"], expected_revision=s["revision"]))
    return g, session, cmd, panel


def test_an_roi_that_has_its_inset_gets_no_second_one(live):
    g, session, cmd, panel = live
    cmd("roi_to_inset", panel_ref="0/0")
    count = len(panel.annotations)
    with pytest.raises(ValueError, match="ALREADY_HAS_INSET"):
        cmd("roi_to_inset", panel_ref="0/0", annotation_index=0)
    assert len(panel.annotations) == count


def test_the_chat_does_not_undo_again_what_the_user_already_undid(live):
    g, session, cmd, panel = live
    first = cmd("action_begin", text="i wanna edit smallest ROI inset in b")
    cmd("roi_to_inset", panel_ref="0/0")
    cmd("action_finish")
    assert len(panel.annotations) == 2
    cmd("action_undo", ident=first["id"])                  # the user's undo button
    from pyfigures.assistant.partner_gui import panels
    panel = next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    assert len(panel.annotations) == 1
    cmd("action_begin", text="No I just wanted you to open the dialog so I can edit it myself")
    with pytest.raises(ValueError, match="ALREADY_UNDONE"):
        cmd("undo")
    cmd("action_finish")
    assert g.paint.EZFIG_panel.shapes_to_draw                # the figure is still there


def test_the_user_ctrl_z_counts_against_the_chat_undos(live):
    """"If I do an undo the model should do one less undo than it wanted if it saved
    many times, and nothing if it saved all at once" (user request 2026-11-12)."""
    g, session, cmd, panel = live
    n = len(g.paint.EZFIG_panel.shapes_to_draw)
    cmd("action_begin", text="add two labels")
    cmd("add_label", text="one")
    cmd("add_label", text="two")                        # two GUI undo steps
    cmd("action_finish")
    assert len(g.paint.EZFIG_panel.shapes_to_draw) == n + 2
    g.undo()                                            # the user's Ctrl+Z: "two" goes
    assert len(g.paint.EZFIG_panel.shapes_to_draw) == n + 1
    cmd("action_begin", text="restore it as it was")
    cmd("undo")                                        # one left for the chat: "one" goes
    assert len(g.paint.EZFIG_panel.shapes_to_draw) == n
    with pytest.raises(ValueError, match="ALREADY_UNDONE"):
        cmd("undo")                                      # never into the user's figure
    cmd("action_finish")
    assert len(g.paint.EZFIG_panel.shapes_to_draw) == n

    cmd("action_begin", text="add a label")
    cmd("add_label", text="three")                       # one GUI undo step
    cmd("action_finish")
    g.undo()                                             # the user's Ctrl+Z took it all back
    cmd("action_begin", text="no, undo that")
    with pytest.raises(ValueError, match="ALREADY_UNDONE"):
        cmd("undo")
    cmd("action_finish")
    assert len(g.paint.EZFIG_panel.shapes_to_draw) == n


def test_i_wanna_edit_it_myself_opens_the_editor_through_the_bridge(qapp, gui, runtime, tmp_path):  # noqa: F811
    """The chat opens the panel's editor itself for "I wanna edit the ROI of the inset in
    b" (two questions came first, user chat 2026-11-12)."""
    import threading
    import time
    pytest.importorskip("qtpy_ai_sidecar")
    from qtpy_ai_sidecar.adapters.pyfigures import PyFiguresAdapter
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    launch.start_live_session(g)
    g.auto_lettering_checkbox.setChecked(True)
    g.update_letters()
    opened = []
    g.paint.EZFIG_panel.update_image_annotations = lambda image2d=None, tab=None, draw_tool=True: opened.append(tab)
    adapter = PyFiguresAdapter(runtime / "connection.json")
    box = {}

    def run():
        box["out"] = adapter.preflight_manual_response("I wanna edit the ROI of the inset in panel a")
    t = threading.Thread(target=run)
    t.start()
    while t.is_alive():
        qapp.processEvents()
        t.join(0.02)
    end = time.time() + 2
    while not opened and time.time() < end:
        qapp.processEvents()
    assert box["out"] and "OK" in box["out"]["content"] and opened == ["Annotations"]


def test_an_undo_never_empties_the_figure(qapp, gui, tmp_path):  # noqa: F811
    """PyFigures opened empty, the figure dropped on it: undoing that empties the canvas."""
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.save_state(show_popup=False)                         # the empty canvas
    g.reload_state(_figure(tmp_path), append=True)
    g.save_state(show_popup=False)
    g.undo()
    if g.paint.EZFIG_panel.shapes_to_draw:
        pytest.skip("this history does not go back to an empty canvas")
    g.redo()
    assert g.paint.EZFIG_panel.shapes_to_draw
    session = launch.start_live_session(g)
    s = session.snapshot()
    with pytest.raises(ValueError, match="UNDO_WOULD_EMPTY"):
        session.execute(dict(operation="undo", arguments={}, request_id=str(uuid.uuid4()),
                             session_id=s["session_id"], expected_revision=s["revision"]))
    assert g.paint.EZFIG_panel.shapes_to_draw
