"""'Show me where to click' (user request, 2026-11-05): the chat teaches the GUI
instead of clicking. Every entry on every route is outlined at once (the user
follows any route and may try things), all outlines go as soon as the figure
changed, menus open only when the user asked to be shown, the mouse never moves.
Help > Find in menus… is the GUI counterpart."""
from __future__ import annotations

import uuid

import numpy as np
import pytest
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QDialog, QMenu, QPushButton, QTabWidget, QVBoxLayout, QWidget

from test_assistant_live import runtime, gui  # noqa: F401  (fixtures)


def _figure(tmp_path, n=4):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=2)
    for i in range(n):
        p = str(tmp_path / f"{i}.tif")
        Img(np.full((30, 40), 30 * i + 20, np.uint8), dimensions="hw").save(p)
        add_image(pyf, [i // 2], p)
    return pyf


def _spin(qapp, n=6):
    for _ in range(n):
        qapp.processEvents()


def _highlights(widget):
    # shown (the test window itself may be hidden offscreen)
    return [f for f in widget.findChildren(QWidget, "clickGuideHighlight") if not f.isHidden()]


def test_menu_routes_are_all_outlined_and_nothing_opens_by_itself(qapp, gui, tmp_path):
    from pyfigures.gui.show_me_where import ClickGuide
    g = gui()
    g.reload_state(_figure(tmp_path), append=False)
    guide = ClickGuide(g)
    mouse = QCursor.pos()
    edit = next(a for a in g.menuBar.actions() if a.text().replace("&", "") == "Edit").menu()
    out = guide.start([["Edit", "Arrange all images in rows…"], ["Edit", "Duplicate Selection"],
                       ["Help", "Find in menus…"]], where="menu")
    _spin(qapp)
    assert out["status"] == "guidance_shown" and not out["operation_executed"]
    assert len(_highlights(g.menuBar)) == 2                       # Edit and Help
    assert not edit.isVisible()                                   # not opened for the user
    edit.popup(g.mapToGlobal(g.rect().center()))                  # the user opens Edit
    _spin(qapp)
    assert len(_highlights(edit)) == 2                            # both of its routes at once
    assert QCursor.pos() == mouse                                 # the pointer never moved
    edit.hide()
    guide.stop()
    assert not _highlights(g.menuBar)


def test_a_wrong_route_says_what_the_menu_offers(qapp, gui):
    from pyfigures.gui.show_me_where import ClickGuide
    g = gui()
    out = ClickGuide(g).start([["Edit", "Make it pretty"]], where="menu")
    assert out["status"] == "route_not_found" and out["missing"] == "Make it pretty"
    assert "Duplicate Selection" in out["offered_here"]


def test_all_highlights_go_once_it_worked(qapp, gui, tmp_path):
    from pyfigures.gui.show_me_where import ClickGuide
    g = gui()
    g.reload_state(_figure(tmp_path), append=False)
    guide = ClickGuide(g)
    guide.start([["Edit", "Arrange all images in rows…"]], where="menu")
    _spin(qapp)
    assert _highlights(g.menuBar)
    g.arrange_images_in_rows("3-1")                               # the user did it
    guide._watch()
    _spin(qapp)
    assert guide.state == "completed" and not _highlights(g.menuBar)
    assert "Done" in g.statusBar().currentMessage()


def test_right_click_routes_follow_the_menus_the_user_opens(qapp, gui, tmp_path):
    from pyfigures.gui.show_me_where import ClickGuide
    g = gui()
    canvas = g.paint.EZFIG_panel
    guide = ClickGuide(g)
    guide.start([["Crop & size", "Reset crop only"], ["Crop & size", "Reset crop and rotation"],
                 ["Duplicate Selection"]], where="context")
    menu = QMenu(canvas)                                          # what a right-click builds
    sub = menu.addMenu("Crop && size")
    sub.addAction("Reset crop only")
    sub.addAction("Reset crop and rotation")
    sub.addAction("Reset rotation only")
    menu.addAction("Duplicate Selection")
    menu.addAction("Delete")
    menu.popup(g.mapToGlobal(g.rect().center()))
    _spin(qapp)
    assert len(_highlights(menu)) == 2                            # Crop & size + Duplicate
    assert not sub.isVisible()                                    # not opened unasked
    sub.popup(g.mapToGlobal(g.rect().center()))
    _spin(qapp)
    assert len(_highlights(sub)) == 2                             # both resets, not the third
    menu.hide()
    sub.hide()
    guide.stop()


def test_asked_to_be_shown_the_menu_opens_down_to_the_choice(qapp, gui):
    from pyfigures.gui.show_me_where import ClickGuide
    g = gui()
    guide = ClickGuide(g)
    guide.start([["Crop & size", "Reset crop only"], ["Crop & size", "Reset rotation only"]],
                where="context", open_menus=True)
    menu = QMenu(g.paint.EZFIG_panel)
    sub = menu.addMenu("Crop && size")
    sub.addAction("Reset crop only")
    sub.addAction("Reset rotation only")
    menu.popup(g.mapToGlobal(g.rect().center()))
    _spin(qapp, 12)
    assert sub.isVisible() and len(_highlights(sub)) == 2         # stops where the user decides
    menu.hide()
    guide.stop()


def test_editor_tab_and_buttons_are_outlined(qapp, gui):
    from pyfigures.gui.show_me_where import ClickGuide
    g = gui()
    guide = ClickGuide(g)
    guide.start([], where="editor", editor_tab="File Infos + Scale", controls=["Reset all LUTs"])
    dialog = QDialog(g)
    tabs = QTabWidget(dialog)
    page = QWidget()
    lay = QVBoxLayout(page)
    lay.addWidget(QPushButton("Set LUTs"))
    lay.addWidget(QPushButton("Reset all LUTs"))
    tabs.addTab(QWidget(), "Annotations")
    tabs.addTab(page, "File Infos + Scale")
    QVBoxLayout(dialog).addWidget(tabs)
    tabs.setCurrentIndex(1)
    dialog.show()
    _spin(qapp, 10)
    assert len(_highlights(tabs.tabBar())) == 1 and len(_highlights(page)) == 1, (
        [(f.parent().__class__.__name__, f.geometry()) for f in guide._frames])
    dialog.close()
    guide.stop()


def test_the_chat_tool_selects_the_row_and_guides(qapp, gui, runtime, tmp_path):
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    session = launch.start_live_session(g)

    def cmd(operation, **arguments):
        s = session.snapshot()
        return session.execute(dict(operation=operation, arguments=arguments, request_id=str(uuid.uuid4()),
                                    session_id=s["session_id"], expected_revision=s["revision"]))

    out = cmd("show_me_where", routes=[["Duplicate Selection"]], where="context", panel_ref="0/0", level="row")
    assert out["status"] == "guidance_shown"
    assert g.paint.EZFIG_panel.selected_shape is g.paint.EZFIG_panel.shapes_to_draw[0]   # the whole row
    assert cmd("show_me_where_status")["status"] == "guidance_shown"
    assert cmd("show_me_where", stop=True)["status"] == "cancelled"
    bad = cmd("show_me_where", routes=[["Edit", "Nope"]], where="menu")
    assert bad["status"] == "route_not_found"


def test_open_it_for_me_opens_the_editor_on_its_tab_with_buttons_outlined(qapp, gui, runtime, tmp_path, monkeypatch):
    # "Should I highlight where to click, or open it for me?" -> "open it for me"
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    session = launch.start_live_session(g)
    opened = []
    monkeypatch.setattr(g.paint.EZFIG_panel, "update_image_annotations",
                        lambda image2d=None, tab=None: opened.append(tab))
    s = session.snapshot()
    out = session.execute(dict(operation="show_me_where", arguments=dict(where="editor", panel_ref="0/1", editor_tab="scale",
                                                                          controls=["Reset all LUTs"], open_menus=True),
                               request_id=str(uuid.uuid4()), session_id=s["session_id"], expected_revision=s["revision"]))
    assert out["status"] == "guidance_shown" and out["editor"] == "scheduled"
    assert session.click_guide.editor_tab == "File Infos + Scale"          # the title that gets outlined
    import time
    end = time.time() + 2
    while not opened and time.time() < end:
        qapp.processEvents()
    assert opened == ["File Infos + Scale"]
    session.click_guide.stop()


def test_the_chat_tool_is_offered_and_documented():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server, category_for
    tool = live_mcp.mcp._tool_manager._tools["show_me_where"]
    assert "mouse pointer never moves" in tool.description and "EVERY entry" in tool.description
    assert "show_me_where" in build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools \
        or category_for("show_me_where") == "help"


def test_help_find_in_menus_outlines_every_match(qapp, gui):
    g = gui()
    routes = g.menu_routes_matching("LUT")
    assert routes and all(any("lut" in t.lower() for t in r[-1:]) for r in routes)
    assert not any("resolution" in r[-1].lower() for r in routes)     # word starts only
    out = g.find_in_menus("Arrange all images")
    assert out["status"] == "guidance_shown" and ["Edit", "Arrange all images in rows…"] in out["routes"]
    _spin(qapp)
    assert _highlights(g.menuBar)
    g._click_guide.stop()
    assert g.find_in_menus("zzzz-nothing")["status"] == "route_not_found"
