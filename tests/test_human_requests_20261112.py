"""Ninety short, human-style chat requests on a nine-panel figure (Mistral
Large 4 over its API, 2026-11-12): what the application refused or lacked.
- "no letters" was refused (only remove / hide / delete counted as asking).
- "rename g to G'": no operation gave one panel its own letter text.
- "use numbers instead of letters": the error did not say it is not available.
- (scale bars: test_scale_bar_one_property_20261112.py; the chat sidecar's own
  guards: qtpy_ai_sidecar/tests.)
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import _figure, gui, runtime  # noqa: E402,F401  (fixtures)


def _lettered(gui, tmp_path):  # noqa: F811
    from pyfigures.assistant.partner_gui import letters, panels
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    g.auto_lettering_checkbox.setChecked(True)
    g.update_letters()
    found = [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)]
    return g, found, lambda: [[a.getPlainText() for a in letters(p)] for p in found]


@pytest.mark.parametrize("words", ["no letters", "get rid of the letters", "i don't want the letters",
                                   "without labels please", "sans lettres", "enlève les lettres",
                                   "take the letters off", "drop the panel letters"])
def test_everyday_ways_of_asking_for_no_letters(qapp, gui, runtime, tmp_path, words):  # noqa: F811
    g, found, texts = _lettered(gui, tmp_path)
    assert texts() == [["a"], ["b"]]
    g.edit_panel_letters(action="remove", scope="all", removal_request=words)
    assert texts() == [[], []]


@pytest.mark.parametrize("words", [None, "", "swap the letters of a and b", "rename the letter a",
                                   "make it nicer", "bigger letters"])
def test_letters_are_still_not_removed_without_being_asked(qapp, gui, runtime, tmp_path, words):  # noqa: F811
    g, found, texts = _lettered(gui, tmp_path)
    with pytest.raises(ValueError, match="CLARIFICATION_REQUIRED"):
        g.edit_panel_letters(action="remove", scope="all", removal_request=words)
    assert texts() == [["a"], ["b"]]


def test_one_panel_gets_its_own_letter_text(qapp, gui, runtime, tmp_path):  # noqa: F811
    g, found, texts = _lettered(gui, tmp_path)
    g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/1"], text="B'")
    assert texts() == [["a"], ["B'"]]
    g.update_letters()                                   # it stays through a refresh
    assert texts() == [["a"], ["B'"]]
    g.edit_panel_letters(action="style", scope="all", font_size=14)      # and through a restyle of all
    assert texts() == [["a"], ["B'"]]
    for bad in (dict(scope="all"), dict(scope="panels", panel_ids=["0/0", "0/1"]),
                dict(scope="panels", panel_ids=["0/1"], action="renumber")):
        with pytest.raises(ValueError, match="one text per panel_ids entry"):
            g.edit_panel_letters(**{"action": "style", "text": "Z", **bad})
    with pytest.raises(ValueError, match="1 to 12 characters"):
        g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/1"], text="   ")
    assert texts() == [["a"], ["B'"]]


def test_one_panel_letter_can_be_bold_through_the_chat(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'rotate A, then make the letter bold on every rotated panel' (2026-11-12): there was no
    way to bold SOME letters; restyle_texts bolded all nine and the model undid it."""
    from test_assistant_live import _call
    from pyfigures.assistant.partner_gui import letters, letter_info, panels
    g, run, shown = _live(qapp, gui, tmp_path)

    def bold():
        return [[letter_info(a)['bold'] for a in letters(p)] for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)]
    state = _call(qapp, "inspect")
    _call(qapp, "bulk_letters", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"action": "style", "scope": "panels", "panel_ids": ["0/1"], "bold": True}, request_id="b1")
    assert bold() == [[False], [True]]
    g.update_letters()                                          # it stays through a refresh
    assert bold() == [[False], [True]] and shown() == [["a"], ["b"]]
    state = _call(qapp, "inspect")
    _call(qapp, "bulk_letters", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"action": "style", "scope": "panels", "panel_ids": ["0/1"], "bold": False,
                     "italic": True}, request_id="b2")
    assert bold() == [[False], [False]]
    assert [letter_info(a)['italic'] for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)
            for a in letters(p)] == [False, True]


def test_an_empty_first_letter_box_removes_every_letter(qapp, gui, runtime, tmp_path):  # noqa: F811
    """Clearing the toolbar's first-letter box with Letters ticked removed all letters
    in early versions; letters the chat had styled or renamed came back (2026-11-12)."""
    g, found, texts = _lettered(gui, tmp_path)
    g.edit_panel_letters(action="style", scope="all", font_size=14)            # chat policies
    g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/1"], text="B'")
    assert texts() == [["a"], ["B'"]]
    g.letter_line_edit.setText("")
    g.update_letters()
    assert texts() == [[], []]
    g.letter_line_edit.setText("a")                                            # back as they were
    g.update_letters()
    assert texts() == [["a"], ["B'"]]


def test_a_panel_without_letter_is_named_by_its_number():
    """'which images are max proj' after 'remove all letters' (user chat 2026-11-12) was
    answered '1/1 (formerly E)': the user sees '#5' on the canvas, never a panel_id."""
    from pyfigures.assistant.session import panel_name
    assert panel_name({'panel_id': '0/0', 'letters': ['A'], 'number': 1}) == 'A'
    assert panel_name({'panel_id': '1/1', 'letters': [], 'number': 5}) == '#5'
    assert panel_name({'panel_id': '1/1', 'letters': [' '], 'number': 5}) == '#5'


def test_one_panel_gets_its_own_letter_through_the_chat(qapp, gui, runtime, tmp_path):  # noqa: F811
    """The same through the live session the chat uses: its style check rolled the
    text back as "STYLE_PRESERVATION_FAILED: Unrequested change to 2/0.text"."""
    from test_assistant_live import _call
    g, run, shown = _live(qapp, gui, tmp_path)
    state = _call(qapp, "inspect")
    _call(qapp, "bulk_letters", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"action": "style", "scope": "panels", "panel_ids": ["0/1"], "text": "B'"}, request_id="t1")
    assert shown() == [["a"], ["B'"]]
    state = _call(qapp, "inspect")
    _call(qapp, "bulk_letters", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"action": "style", "scope": "panels", "panel_ids": ["#1"], "text": "1"}, request_id="t2")
    assert shown() == [["1"], ["B'"]]


def test_numbers_for_every_panel_in_one_call(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'use numbers instead of letters': nine one-panel calls hit the chat's step limit."""
    g, found, texts = _lettered(gui, tmp_path)
    g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/0", "#2"], text=["1", "2"])
    assert texts() == [["1"], ["2"]]
    g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/0", "0/1"], text=["I", "II"])
    assert texts() == [["I"], ["II"]]
    with pytest.raises(ValueError, match="one text per panel_ids entry"):
        g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/0", "0/1"], text=["1"])
    with pytest.raises(ValueError, match="same panel twice"):
        g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/0", "#1"], text=["1", "2"])
    assert texts() == [["I"], ["II"]]


def test_numbers_as_a_sequence_say_they_are_not_available(qapp, gui, runtime, tmp_path):  # noqa: F811
    g, found, texts = _lettered(gui, tmp_path)
    with pytest.raises(ValueError) as error:
        g.edit_panel_letters(action="renumber", scope="all", start_letter="1")
    message = str(error.value)
    assert "alphabetic only" in message and "roman numerals" in message and "Do not search" in message
    assert texts() == [["a"], ["b"]]


def test_property_names_people_say(tmp_path):
    """'the pixel size of g is 0.5 um': five searches before the real name was found."""
    from pyfigures.mcp_server import get_image_property, set_image_property
    pyf = _figure(tmp_path)
    for name in ("px_to_unit", "pixel_size", "Pixel Size"):
        assert not set_image_property(pyf, [0], 0, name, "0.5").startswith("ERROR")
        assert "0.5" in get_image_property(pyf, [0], 0, "px_to_unit_conversion_factor")
        assert "0.5" in get_image_property(pyf, [0], 0, name)
    set_image_property(pyf, [0], 0, "background", "0")
    assert "0" in get_image_property(pyf, [0], 0, "fill_color")


def test_one_image_cannot_be_resized_and_the_reply_says_what_can_be_done(tmp_path):
    """'b looks smaller than the others, fix it': the model set 'scale', was sent to
    set_size, and searched until it was stopped."""
    from pyfigures.mcp_server import set_image_property
    reply = set_image_property(_figure(tmp_path), [0], 1, "scale", "2.17")
    assert reply.startswith("ERROR") and "same height" in reply
    for way in ("transform_image", "arrange_live_images", "resize_figure", "Tell the user"):
        assert way in reply


def test_a_value_for_a_tab_bar_sets_it_without_naming_the_operation(qapp, gui, runtime, tmp_path):  # noqa: F811
    """use_native_gui(control_id, value='File Infos + Scale') was refused three times in a row."""
    from types import SimpleNamespace
    from qtpy.QtWidgets import QLabel, QTabWidget
    from pyfigures.assistant.native_gui import NativeGUI
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    tabs = QTabWidget()
    for name in ("File Infos + Scale", "Annotations", "Rotate + Crop"):
        tabs.addTab(QLabel(name), name)
    tabs.show()
    native = NativeGUI(SimpleNamespace(window=g))
    ident = native.register(tabs)
    assert native.describe(tabs)["operations"] == ["set", "keys"]
    native.operate(ident, value="Rotate + Crop", request_id="r1")       # operation left at its default
    deadline = __import__("time").time() + 3
    while tabs.tabText(tabs.currentIndex()) != "Rotate + Crop" and __import__("time").time() < deadline:
        qapp.processEvents()
    assert tabs.tabText(tabs.currentIndex()) == "Rotate + Crop"
    with pytest.raises(ValueError, match="Operation unavailable"):
        native.operate(ident, operation="accept", request_id="r2")
    tabs.close()


@pytest.mark.parametrize("query, first", [
    ("brightness contrast adjust image panel", "configure_image"),
    ("make panel brighter", "configure_image"),
    ("set pixel size calibration px_to_unit image panel", "set_image_property"),
    ("rename change panel letter text to custom string prime", "edit_panel_letters"),
    ("letter outside image above panel margin", "edit_panel_letters"),
    ("numbers instead of letters numbering", "edit_panel_letters"),
])
def test_discovery_finds_the_operation_at_once(query, first):
    import asyncio
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    server = build_server(live_mcp.mcp, live_mcp.request)
    result = asyncio.run(server.call_tool("find_pyfigures_tools", {"query": query}))
    text = result[0][0].text if isinstance(result, tuple) else result[0].text
    import json
    assert json.loads(text)["tools"][0]["name"] == first


def _live(qapp, gui, tmp_path):  # noqa: F811
    """An open, automatically lettered figure and a way to run the file-based tools on it."""
    from test_assistant_live import _call
    from pyfigures.assistant import launch
    g, found, texts = _lettered(gui, tmp_path)
    launch.start_live_session(g)

    def run(tool, **arguments):
        state = _call(qapp, "inspect")
        return _call(qapp, "original_tool", session_id=state["session_id"], expected_revision=state["revision"],
                     arguments={"tool": tool, "arguments": {"pyf_path": "live", **arguments}},
                     request_id=tool + str(state["revision"]))

    def shown():
        return [p["letters"] for p in _call(qapp, "inspect")["panel_references"]]
    return g, run, shown


def test_a_bright_and_a_dark_image_can_be_swapped(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'swap c and e' (user chat 2026-11-12, sidecar-debug-5): every image swap failed with
    'slot lettering changed': an automatic letter is black on a bright image and white on a
    dark one, so its colour follows the image moved into the slot."""
    from batoolset.img import Img
    import numpy as np
    from pyfigures.mcp_server import create_figure, add_image
    from pyfigures.assistant.partner_gui import letters, letter_info, panels
    pyf = str(tmp_path / "bd.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    for name, value in (("bright", 250), ("dark", 5)):
        p = str(tmp_path / f"{name}.tif")
        Img(np.full((40, 50), value, dtype=np.uint8), dimensions="hw").save(p)
        add_image(pyf, [0], p)
    g = gui(shareable=True)
    g.reload_state(pyf, append=False)
    g.auto_lettering_checkbox.setChecked(True)
    g.update_letters()

    def shown():
        return [(os.path.basename(str(p.filename)), [letter_info(a)['text'] for a in letters(p)])
                for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)]
    assert shown() == [("bright.tif", ["a"]), ("dark.tif", ["b"])]
    g.swap_panels("a", "b")
    assert shown() == [("dark.tif", ["a"]), ("bright.tif", ["b"])]


def test_a_duplicated_panel_gets_the_next_letter(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'duplicate a': the copy kept the letter A (A, B, C, A, D…) and renumbering
    everything changed nothing."""
    g, run, shown = _live(qapp, gui, tmp_path)
    assert shown() == [["a"], ["b"]]
    run("clone_image", src_group_path=[0], src_image_index=0, dst_group_path=[0], dst_image_index=-1)
    assert shown() == [["a"], ["b"], ["c"]]


def test_the_letters_follow_when_a_panel_is_deleted(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'delete the images in the second row' left A, B, C, G, H, I."""
    g, run, shown = _live(qapp, gui, tmp_path)
    run("remove_image", group_path=[0], image_index=0)
    assert shown() == [["a"]]


def test_letters_pinned_as_the_plain_sequence_follow_the_panels(qapp, gui, runtime, tmp_path):  # noqa: F811
    """A figure built through the chat has every letter pinned (A, B, C…): a copy of A
    was a second A, "renumber all" changed nothing, a deleted row left a hole."""
    g, run, shown = _live(qapp, gui, tmp_path)
    for pid, text in (("0/0", "A"), ("0/1", "B")):
        g.edit_panel_letters(action="style", scope="panels", panel_ids=[pid], text=text)
    run("clone_image", src_group_path=[0], src_image_index=0, dst_group_path=[0], dst_image_index=-1)
    assert shown() == [["A"], ["B"], ["C"]]
    run("remove_image", group_path=[0], image_index=0)
    assert shown() == [["A"], ["B"]]


def test_deleting_a_row_of_pinned_letters_letters_the_rest_again(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'delete the images in the second row' left A, B, C, G, H, I: remove_group is a
    layout operation and returned before the letters were looked at (rerun 2026-11-12)."""
    from test_assistant_live import _call
    from pyfigures.assistant import launch
    from pyfigures.mcp_server import add_group, add_image
    pyf = _figure(tmp_path)
    add_group(pyf, orientation="X")
    add_group(pyf, orientation="X")
    for row in (1, 2):
        for name in "ab":
            add_image(pyf, [row], str(tmp_path / f"{name}.tif"))
    g = gui(shareable=True)
    g.reload_state(pyf, append=False)
    g.auto_lettering_checkbox.setChecked(True)
    g.update_letters()
    launch.start_live_session(g)
    ids = ["0/0", "0/1", "1/0", "1/1", "2/0", "2/1"]
    g.edit_panel_letters(action="style", scope="panels", panel_ids=ids, text=list("ABCDEF"))
    state = _call(qapp, "inspect")
    _call(qapp, "original_tool", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"tool": "remove_group", "arguments": {"pyf_path": "live", "group_path": [1]}}, request_id="rg")
    assert [p["letters"] for p in _call(qapp, "inspect")["panel_references"]] == [["A"], ["B"], ["C"], ["D"]]


def test_renumbering_everything_replaces_pinned_letters(qapp, gui, runtime, tmp_path):  # noqa: F811
    g, found, texts = _lettered(gui, tmp_path)
    g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/1"], text="a")
    assert texts() == [["a"], ["a"]]
    g.edit_panel_letters(action="renumber", scope="all", start_letter="A")
    assert texts() == [["A"], ["B"]]


def test_letters_the_user_chose_stay_when_a_panel_is_deleted(qapp, gui, runtime, tmp_path):  # noqa: F811
    g, run, shown = _live(qapp, gui, tmp_path)
    g.edit_panel_letters(action="style", scope="panels", panel_ids=["0/1"], text="X")
    run("remove_image", group_path=[0], image_index=0)
    assert shown() == [["X"]]


def test_a_visible_letter_names_the_panel_in_panel_ids(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'remove the letter of b' with panel_ids=["B"]: "No matching image panels"."""
    g, found, texts = _lettered(gui, tmp_path)
    g.edit_panel_letters(action="remove", scope="panels", panel_ids=["B"], removal_request="remove the letter of b")
    assert texts() == [["a"], []]
    with pytest.raises(ValueError, match="No single panel shows the letter 'Q'"):
        g.edit_panel_letters(action="style", scope="panels", panel_ids=["Q"], font_size=12)


def test_annotations_of_one_panel(tmp_path):
    """get_annotations(panel_ref="C") was refused as an unknown argument."""
    import json
    from pyfigures.assistant.original_registry import annotations_of_panel
    from pyfigures.mcp_server import add_annotation, get_annotations
    pyf = _figure(tmp_path)
    add_annotation(pyf, [0], 1, "hello")
    state = {"panel_references": [{"panel_id": "0/0", "letters": ["A"], "group_path": [0], "image_index": 0},
                                  {"panel_id": "0/1", "letters": ["B"], "group_path": [0], "image_index": 1}]}
    for ref in ("b", "B", "0/1"):
        kept = json.loads(annotations_of_panel(get_annotations(pyf), state, ref))
        assert [k["text"] for k in kept] == ["hello"]
    assert json.loads(annotations_of_panel(get_annotations(pyf), state, "a")) == []
    with pytest.raises(ValueError, match="No single panel is named 'z'"):
        annotations_of_panel(get_annotations(pyf), state, "z")


def test_a_bracket_says_which_annotations_it_is(tmp_path):
    """'add a significance bar with *** on h': not seeing its thin black bracket, the model
    added it five times and removed pieces by stale indices until it was stopped."""
    from pyfigures.mcp_server import add_significance_bracket
    reply = add_significance_bracket(_figure(tmp_path), [0], 0, 5, 40, 10, "***")
    assert "4 annotations" in reply and "annotation_index 0 to 3" in reply and "do not add it again" in reply


def _guidance(query):
    import asyncio
    import json
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    server = build_server(live_mcp.mcp, live_mcp.request)
    result = asyncio.run(server.call_tool("find_pyfigures_tools", {"query": query}))
    return json.loads(result[0][0].text if isinstance(result, tuple) else result[0].text)["guidance"]


@pytest.mark.parametrize("query", ["resize row height make row taller", "set row height equal rows",
                                   "resize one image panel bigger"])
def test_a_search_for_row_height_is_told_there_is_none(query):
    """'make the 2nd row a little taller': thirty calls, then a row wider than the figure."""
    note = _guidance(query)
    assert note.startswith("ROW HEIGHT") and "arrange_live_images" in note and "do not search further" in note


@pytest.mark.parametrize("query", ["next z slice z-stack position", "show slice 7 of the stack", "single z plane shown"])
def test_a_search_for_one_z_slice_is_told_how(query):
    """'show the next z in a': eight searches, then "I stopped before finishing"."""
    note = _guidance(query)
    assert note.startswith("ONE Z SLICE") and "projection_z_start=k" in note


@pytest.mark.parametrize("query", ["swap two image panels", "set scale bar length", "resize figure width mm",
                                   "montage of z slices"])
def test_other_searches_get_no_such_note(query):
    note = _guidance(query)
    assert "ROW HEIGHT" not in note and "ONE Z SLICE" not in note


def test_one_z_slice_is_a_projection_of_that_slice(tmp_path):
    from pyfigures.mcp_server import configure_image
    assert "projection_z_start=7, projection_z_end=8" in configure_image.__doc__
    import numpy as np
    from batoolset.img import Img
    from pyfigures.mcp_server import add_image, create_figure
    pyf = str(tmp_path / "z.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    stack = str(tmp_path / "stack.tif")
    Img((np.random.default_rng(3).random((4, 40, 50)) * 255).astype(np.uint8), dimensions="dhw").save(stack)
    add_image(pyf, [0], stack)
    reply = configure_image(pyf, [0], 0, projection="max", projection_z_start=1, projection_z_end=2)
    assert not reply.startswith("ERROR"), reply
    assert configure_image(_figure(tmp_path), [0], 0, projection_z_start=1, projection_z_end=2).startswith("ERROR: the file has no Z axis")


def test_inspect_says_which_panels_are_stacks(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'tell me which images are stacks?': thirty searches, then "I stopped before finishing"
    (user chat 2026-11-12): no tool said it."""
    import numpy as np
    from batoolset.img import Img
    from test_assistant_live import _call
    from pyfigures.assistant import launch
    from pyfigures.mcp_server import add_image, configure_image
    pyf = _figure(tmp_path)
    stack = str(tmp_path / "zstack.tif")
    Img((np.random.default_rng(5).random((6, 40, 50)) * 255).astype(np.uint8), dimensions="dhw").save(stack)
    add_image(pyf, [0], stack)
    configure_image(pyf, [0], 2, projection="max")
    g = gui(shareable=True)
    g.reload_state(pyf, append=False)
    launch.start_live_session(g)
    state = _call(qapp, "inspect")
    assert [r["kind"] for r in state["panel_references"]] == ["image", "image", "image"]
    stacks = [r["stack"] for r in state["panel_references"]]
    assert stacks[:2] == [None, None]
    assert stacks[2]["z"] == 6 and stacks[2]["t"] == 1 and stacks[2]["shown"] == "max projection of z 0-6"
    name = (state["panel_references"][2]["letters"] or ["#3"])[0]       # no letter: its number
    assert state["panel_references"][2]["name"] == name
    assert f"stacks: {name} (6 z)" in state["figure_summary"]["answer"]


def test_stack_sizes_come_from_the_header_only(tmp_path, monkeypatch):
    """Inspection runs at every chat turn: reading the user's .IPL file started Fiji."""
    import numpy as np
    import tifffile
    from pyfigures import stack_info
    monkeypatch.setattr(stack_info, "stack_info", lambda *a, **k: pytest.fail("full read"))
    hyper = str(tmp_path / "h.tif")
    tifffile.imwrite(hyper, np.zeros((3, 4, 2, 8, 9), np.uint8), imagej=True, metadata={"axes": "TZCYX"})
    rgb = str(tmp_path / "rgb.tif")
    tifffile.imwrite(rgb, np.zeros((8, 9, 3), np.uint8), photometric="rgb")
    assert stack_info.header_sizes(hyper) == {"d": 4, "t": 3, "c": 2}
    assert stack_info.header_sizes(rgb) == {"d": 1, "t": 1, "c": 3}
    for name in ("photo.jpg", "x.IPL", "scan.dcm", "a.czi"):
        (tmp_path / name).write_bytes(b"x")
    for name in ("photo.jpg", "x.IPL", "scan.dcm", "gone.tif"):
        assert stack_info.header_sizes(str(tmp_path / name)) is None
    assert stack_info.header_sizes(str(tmp_path / "a.czi")) == "unknown"


def test_a_panel_number_names_the_panel(qapp, gui, runtime, tmp_path):  # noqa: F811
    """The canvas numbers selected panels (1, 2…): the chat accepts "#2" where there
    are no letters, or letters outside the rows."""
    from test_assistant_live import _call
    from pyfigures.assistant.gui_selection import resolve_panel
    g, run, shown = _live(qapp, gui, tmp_path)
    found = [r["number"] for r in _call(qapp, "inspect")["panel_references"]]
    assert found == [1, 2]
    second = resolve_panel(g, "#2")
    assert second is resolve_panel(g, "0/1") and resolve_panel(g, "number 2") is second
    with pytest.raises(ValueError, match="there is no panel #5"):
        resolve_panel(g, "#5")
    g.edit_panel_letters(action="style", scope="panels", panel_ids=["#2"], text="Z")
    assert shown() == [["a"], ["Z"]]
    g.swap_panels("#1", "#2")


def test_selected_panels_show_their_number_stack_and_changed_channels(qapp, gui, runtime, tmp_path):  # noqa: F811
    """Marks on the selected panels (the user's idea, 2026-11-12): the number the chat
    accepts, the stack size, and 'ch' when colours differ from the file. Screen only."""
    import numpy as np
    from batoolset.img import Img
    from qtpy.QtGui import QImage, QPainter
    from pyfigures.gui import selection_badges as sb
    from pyfigures.mcp_server import add_image, set_lut
    pyf = _figure(tmp_path)
    stack = str(tmp_path / "zstack.tif")
    Img((np.random.default_rng(5).random((6, 40, 50)) * 255).astype(np.uint8), dimensions="dhw").save(stack)
    add_image(pyf, [0], stack)
    set_lut(pyf, [0], 1, ["MAGENTA"])
    g = gui(shareable=True)
    g.reload_state(pyf, append=False)
    canvas = g.paint.EZFIG_panel
    found = sb.numbered_panels(canvas.shapes_to_draw)
    assert [n for n, _ in found] == [1, 2, 3]
    info = [[t for t, kind in sb.badges(p, n) if kind == sb.INFO] for n, p in found]
    assert info == [["#1", "▦ image"], ["#2", "▦ image", "◐ ch"], ["#3", "▦ image", "▤ 6z (max)"]]
    assert sb.selected_panels(None) == [] and len(sb.selected_panels(list(canvas.shapes_to_draw))) == 3
    assert sb.selected_panels(found[1][1]) == [found[1][1]]
    dots = []
    real_warnings = sb.warnings
    try:
        sb.warnings = lambda panel, ctx=None: dots.append(panel) or real_warnings(panel, ctx)
        image = QImage(800, 600, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        drawn = []
        real_text = painter.drawText
        painter.drawText = lambda *a: drawn.append(a[-1]) or real_text(*a)
        sb.draw_badges(painter, canvas.shapes_to_draw, found[2][1], scale=1.5)
        painter.end()
        numbers = [t for t in drawn if t.startswith("#")]
        assert numbers == ["#3"] and "▤ 6z (max)" in drawn   # the selected panel only
        assert dots == [found[2][1]]
        dots.clear()
        painter = QPainter(image)
        sb.draw_badges(painter, canvas.shapes_to_draw, None)
        painter.end()
        assert dots == []                     # nothing selected: nothing checked, nothing drawn
    finally:
        sb.warnings = real_warnings
    # an export draws no marks: only the on-screen paintEvent draws the selection
    import inspect
    from pyfigures.gui import ezfig
    source = inspect.getsource(ezfig)
    methods = {m.split("(")[0]: m for m in source.split("\n    def ")[1:]}
    assert [n for n, m in methods.items() if "self.draw_selection(" in m] == ["_paint"]
    assert [n for n, m in methods.items() if "self._paint(" in m] == ["paintEvent"]


def test_marks_for_changes_and_warnings(tmp_path):
    """Crop, rotation, flip, contrast, series; low resolution, the same image twice, a
    missing file (the user's list, 2026-11-12)."""
    from types import SimpleNamespace
    import numpy as np
    from pyfigures.gui import selection_badges as sb
    path = str(tmp_path / "a.tif")
    open(path, "wb").close()

    def panel(**kw):
        base = dict(filename=path, crop_left=0, crop_top=0, crop_right=0, crop_bottom=0, theta=0,
                    flip_h=False, flip_v=False, normalization=None, serie_to_open=None, channels=None, LUTs=None,
                    projection=None, projection_z_start=None, projection_z_end=None, img=None)
        base.update(kw)
        return SimpleNamespace(**base)

    def texts(p, ctx=None):
        return [t for t, _ in sb.badges(p, 1, ctx)][2:]          # after the number and the kind
    assert sb.badges(panel(), 4)[:2] == [("#4", sb.INFO), ("▦ image", sb.INFO)]
    assert sb.panel_kind(panel(custom_loading_script="plt.plot([1, 2])")) == "code"
    assert sb.panel_kind(panel(filename=str(tmp_path / "chart.svg"))) == "vector"
    assert texts(panel()) == []
    assert texts(panel(crop_left=10, theta=30, flip_h=True, normalization={"per_channel": True}, serie_to_open=1)) == [
        "series 2", "⌗ crop", "↻ 30°", "⇋ flip", "◑ contrast"]
    # 600 px shown 4 inches wide = 150 dpi; 1200 px = 300 dpi passes
    low = panel(img=np.zeros((10, 600)), get_raw_size=lambda: (600, 10), width=lambda all=True: 4 * 72)
    assert texts(low) == ["⚠ 150 dpi"]
    ok = panel(img=np.zeros((10, 1200)), get_raw_size=lambda: (1200, 10), width=lambda all=True: 4 * 72)
    assert texts(ok) == []
    cropped = panel(img=np.zeros((10, 1200)), get_raw_size=lambda: (1200, 10), width=lambda all=True: 4 * 72,
                    crop_left=300, crop_right=300)
    assert "⚠ 150 dpi" in texts(cropped)              # the crop removes pixels
    assert texts(panel(filename=str(tmp_path / "gone.tif"))) == ["⚠ missing"]
    first, again, split = panel(), panel(), panel(channels=[True, False])
    ctx = {"numbered": [], "repeats": {}}
    keys = {}
    for number, p in enumerate((first, again, split), 1):
        key = sb._view_key(p)
        if key in keys:
            ctx["repeats"][id(p)] = keys[key]
        else:
            keys[key] = number
    assert texts(again, ctx) == ["⚠ same as #1"]
    assert "⚠ same as #1" not in texts(split, ctx)   # a channel split is not a reuse


def test_marks_stay_inside_small_panels():
    """A short row spilled its marks over the next row: they wrap to the width, and
    when too many for the height keep the number and warnings first, then "+N"."""
    from pyfigures.gui import selection_badges as sb
    items = [("#7", sb.INFO), ("▦ image", sb.INFO), ("⌗ crop", sb.INFO), ("↻ 30°", sb.INFO),
             ("⚠ 120 dpi", sb.WARNING)]

    def width(text):
        return 10 * len(text)

    def texts(lines):
        return [[i[0] for i, _ in line] for line in lines]
    assert texts(sb.fit(items, width, 1000, 100, 10, 2)) == [["#7", "▦ image", "⌗ crop", "↻ 30°", "⚠ 120 dpi"]]
    assert texts(sb.fit(items, width, 160, 100, 10, 2)) == [["#7", "▦ image", "⌗ crop"], ["↻ 30°", "⚠ 120 dpi"]]
    assert texts(sb.fit(items, width, 160, 10, 10, 2)) == [["#7", "⚠ 120 dpi", "+3"]]   # warnings before the rest
    assert texts(sb.fit(items, width, 60, 10, 10, 2)) == [["#7", "+4"]]
    for lines in (sb.fit(items, width, 160, h, 10, 2) for h in (10, 22, 34, 100)):
        assert all(sum(w for _, w in line) + 2 * (len(line) - 1) <= 160 for line in lines)


def test_marks_keep_clear_of_the_selection_name():
    """The selected object's name is written at the selection's centre: with one image
    selected the marks covered it (the user, 2026-11-12)."""
    from qtpy.QtCore import QRectF
    from pyfigures.gui.selection_badges import place_block
    panel = QRectF(0, 0, 200, 100)
    name = QRectF(60, 45, 80, 10)
    assert place_block(panel, 60, 20) == 40                       # centred without a name
    y = place_block(panel, 60, 20, name)
    assert y == 57 and not QRectF(70, y, 60, 20).intersects(name)  # below the name
    low_name = QRectF(60, 60, 80, 10)
    assert place_block(panel, 60, 40, low_name) == 60 - 2 - 40     # no room below: above it
    assert place_block(panel, 60, 20, QRectF(500, 500, 10, 10)) == 40   # elsewhere: centred


def test_marks_cost_little_on_a_large_figure(qapp, gui, runtime, tmp_path):  # noqa: F811
    """The marks are drawn at every repaint: 200 panels must stay far below a frame."""
    import time
    from qtpy.QtGui import QImage, QPainter
    from pyfigures.gui import selection_badges as sb
    import copy
    import xml.etree.ElementTree as ET
    pyf = _figure(tmp_path)
    tree = ET.parse(pyf)
    row = tree.getroot().find(".//Group/content")
    first = [c for c in row if c.tag == "Image2D"][0]
    for _ in range(198):
        row.append(copy.deepcopy(first))
    tree.write(pyf, encoding="utf-8")
    g = gui(shareable=True)
    g.reload_state(pyf, append=False)
    canvas = g.paint.EZFIG_panel
    image = QImage(1600, 1200, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    sb.draw_badges(painter, canvas.shapes_to_draw, None)          # warm the caches
    start = time.perf_counter()
    for _ in range(10):
        sb.draw_badges(painter, canvas.shapes_to_draw, None)
    nothing_selected = (time.perf_counter() - start) / 10
    start = time.perf_counter()
    for _ in range(10):
        sb.draw_badges(painter, canvas.shapes_to_draw, list(canvas.shapes_to_draw))
    all_selected = (time.perf_counter() - start) / 10
    painter.end()
    print(f"200 panels: {nothing_selected * 1000:.1f} ms, all selected {all_selected * 1000:.1f} ms")
    assert nothing_selected < 0.001 and all_selected < 0.03


def _label_and_bar(tmp_path):
    from pyfigures.mcp_server import add_annotation, set_image_property, set_scale_bar
    pyf = _figure(tmp_path)
    set_image_property(pyf, [0], 0, "px_to_unit_conversion_factor", "0.1")
    add_annotation(pyf, [0], 0, "a label", placement="bottom right")
    set_scale_bar(pyf, [0], 0, bar_width_in_units=1, placement="bottom right")
    return pyf


def test_the_scale_bar_can_go_below_a_label_in_the_same_corner(tmp_path):
    """'put the scale bar bottom most' (user chat 2026-11-12): the bar was moved to the
    other corner and the user was told only the two corners exist."""
    import json
    from pyfigures.mcp_server import get_annotations, move_annotation_in_corner

    def order():
        return [a["type"].split()[0] for a in json.loads(get_annotations(pyf))]
    pyf = _label_and_bar(tmp_path)
    assert order() == ["TAText2D", "scale_bar"]                     # the label sits in the corner
    reply = move_annotation_in_corner(pyf, [0], 0, 1, to="corner")
    assert 'from top to bottom is now: the text "a label"; the scale bar' in reply
    assert "do not call this again" in reply
    assert order() == ["scale_bar", "TAText2D"]
    assert "Already so" in move_annotation_in_corner(pyf, [0], 0, 0, to="corner")
    move_annotation_in_corner(pyf, [0], 0, 0, to="away")
    assert order() == ["TAText2D", "scale_bar"]
    assert move_annotation_in_corner(pyf, [0], 0, 0, to="up").startswith("ERROR")
    assert move_annotation_in_corner(pyf, [0], 0, 5).startswith("ERROR")


def test_bottom_and_top_mean_what_the_user_sees(tmp_path):
    """'put the scale bar on the right below the text' (user chat 2026-11-12): the model
    moved the bar to the bottom, misread 'Stack from the corner inward: ScaleBar,
    TAText2D' and moved it back. 'bottom'/'top' and a top-to-bottom reply."""
    import json
    from pyfigures.mcp_server import get_annotations, move_annotation_in_corner, set_scale_bar

    def order():
        return [a["type"].split()[0] for a in json.loads(get_annotations(pyf))]
    pyf = _label_and_bar(tmp_path)
    reply = move_annotation_in_corner(pyf, [0], 0, 1, to="bottom")      # bar below the label
    assert order() == ["scale_bar", "TAText2D"] and reply.startswith("Done.")
    assert "Already so" in move_annotation_in_corner(pyf, [0], 0, 0, to="below")
    move_annotation_in_corner(pyf, [0], 0, 0, to="top")                 # the bar back on top
    assert order() == ["TAText2D", "scale_bar"]
    # a TOP corner stacks downward: its lowest item is the farthest from the corner
    from pyfigures.mcp_server import add_annotation, set_image_property
    top = tmp_path / "top"
    top.mkdir()
    pyf = _figure(top)
    set_image_property(pyf, [0], 0, "px_to_unit_conversion_factor", "0.1")
    add_annotation(pyf, [0], 0, "a label", placement="top right")
    set_scale_bar(pyf, [0], 0, bar_width_in_units=1, placement="top right")
    assert order() == ["TAText2D", "scale_bar"]                         # label highest
    reply = move_annotation_in_corner(pyf, [0], 0, 0, to="bottom")     # the label lowest
    assert order() == ["scale_bar", "TAText2D"], reply
    assert 'top to bottom is now: the scale bar; the text "a label"' in reply


def test_the_corner_order_is_what_the_canvas_draws(qapp, gui, runtime, tmp_path):  # noqa: F811
    from pyfigures.mcp_server import move_annotation_in_corner
    from pyfigures.assistant.partner_gui import panels

    def bar_below_label():
        g = gui(shareable=True)
        g.reload_state(pyf, append=False)
        g.show()
        for _ in range(5):
            qapp.processEvents()
        g.paint.EZFIG_panel.grab()
        panel = [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)][0]
        bar = next(a for a in panel.annotations if type(a).__name__ == "ScaleBar")
        label = next(a for a in panel.annotations if type(a).__name__ == "TAText2D" and not a.is_letter)
        return bar.y() > label.y()
    pyf = _label_and_bar(tmp_path)
    assert not bar_below_label()
    move_annotation_in_corner(pyf, [0], 0, 1, to="corner")
    assert bar_below_label()


@pytest.mark.parametrize("query", ["scale bar bottom most below the label same corner",
                                   "order of annotations stacked in a corner",
                                   "put the label above the scale bar"])
def test_discovery_finds_the_corner_order(query):
    import asyncio
    import json
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    server = build_server(live_mcp.mcp, live_mcp.request)
    result = asyncio.run(server.call_tool("find_pyfigures_tools", {"query": query}))
    names = [t["name"] for t in json.loads(result[0][0].text if isinstance(result, tuple) else result[0].text)["tools"]]
    assert "move_annotation_in_corner" in names[:3], names


def test_the_file_own_colours_are_offered_for_unnatural_colours():
    """'the colors look unnatural can this be fixed' (user chat 2026-11-12): the model
    offered RED or GRAY, never the file's own colours (set_lut NONE)."""
    from types import SimpleNamespace
    from pyfigures.assistant.session import channel_colours, file_colours
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    text = build_server(live_mcp.mcp, live_mcp.request).instructions
    img = SimpleNamespace(metadata={'LUTs': ['RED', 'GREEN', None]})
    panel = SimpleNamespace(LUTs=['RED_HOT', None, 'BLUE'], img=img)
    assert channel_colours(panel) == ['RED_HOT', 'GREEN', 'BLUE']    # what it shows now
    assert file_colours(panel) == ['RED', 'GREEN', None]             # what NONE gives back
    assert file_colours(SimpleNamespace(LUTs=['RED'], img=SimpleNamespace(metadata={}))) is None
    assert "file_colours in the panel state" in text and '"NONE" for each channel' in text


def test_bigger_needs_no_number():
    """'mak lettrs biger' was answered twice with "what size?"."""
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    rules = build_server(live_mcp.mcp, live_mcp.request).instructions
    assert "RELATIVE requests" in rules and "Never ask for a number first" in rules and "Misspelt" in rules


def test_the_letters_tool_says_what_it_cannot_do():
    from pyfigures.assistant import live_mcp
    doc = live_mcp.edit_panel_letters.__doc__
    assert 'text="G\'"' in doc and "OUTSIDE each image are not available" in doc and "alphabetic only" in doc
