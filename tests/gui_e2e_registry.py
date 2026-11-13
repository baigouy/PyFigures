"""Which test checks the RESULT of each user action of the figure editor.

Keys (see gui_e2e_harness):
    'menu: File > Export As > PNG'            a menu-bar entry
    'toolbar: Undo'                           a toolbar button / Background menu entry
    'toolbar-widget: size_spinbox'            a toolbar spin box, combo, check box…
    'right-click: Crop & size ▶ / Reset crop only'   a canvas right-click entry
    'drop [onto a group]: ↕  To column (with image below)'   a drop-menu button
    'drag [row onto row]: Swap'               an internal-drag menu entry

Values: the tests ('file.py::test_name') that perform the action and check
what it produced. Most keys come from the e2e test tables themselves (a
table row IS the behaviour test); ``LINKED`` adds the actions whose result
is checked by an older, focused test. test_gui_e2e_coverage.py fails when
an action reachable in the GUI has no entry here.
"""
from __future__ import annotations

import gui_e2e_harness as H

# menu-bar actions whose result is checked by a focused test outside the
# e2e tables (each of those tests runs the action and asserts on its output)
LINKED = {
    # the button only opens its menu: each entry of that menu has its test
    "toolbar-widget: page_background_button": ["test_gui_e2e_menus.py::test_menu_action"],
    # a model reads the guidelines: the editor is driven with a fake model there
    "menu: QC > Journal styles (from a journal's guidelines)…": [
        "test_journal_styles.py::test_qc_menu_opens_the_editor",
        "test_journal_styles.py::test_editor_import_edit_review_save_and_use_in_the_journal_dialog"],
    # downloads TinyTeX: the download is faked there
    "menu: Help > Install LaTeX for PyFigures…": ["test_tex_install.py::test_gui_menu_and_tex_drop_offer",
                                                 "test_tex_install.py::test_gui_offer_and_progress"],
    # registers servers in the user's client configs: done in a fake home there
    "menu: Tools > MCP server…": ["test_mcp_control.py::test_gui_menu_opens_the_dialog",
                                  "test_mcp_control.py::test_gui_dialog_registers_and_starts_the_http_server"],
    "toolbar: Chat": ["test_mcp_control.py::test_gui_menu_opens_the_dialog"],
    "menu: View > Open the chat at start-up": ["test_mcp_control.py::test_gui_menu_opens_the_dialog"],
    "menu: Annotations > Text style (letters, labels, scale bars…)…": [
        "test_restyle_texts.py::test_gui_text_style_dialog", "test_restyle_texts.py::test_restyle_labels_only"],
    # A | (B / C): a panel stacked with the one it is dropped on, inside its row
    "drag [loose image onto image in row]: Stack with it (column in the row)": [
        "test_bugs_found_by_gui_e2e.py::test_image_dropped_on_an_image_of_a_row_can_stack_with_it_in_the_row"],
    "drag [image onto image of another row]: Stack with it (column in the row)": [
        "test_bugs_found_by_gui_e2e.py::test_image_dropped_on_an_image_of_a_row_can_stack_with_it_in_the_row"],
    # opens the poster designer with the saved figure on it: done there
    "menu: Tools > Send this figure to the poster designer": [
        "test_send_to_poster.py::test_tools_menu_entry",
        "test_send_to_poster.py::test_a_saved_figure_goes_onto_the_poster",
        "test_send_to_poster.py::test_unsaved_work_is_saved_first_or_nothing_happens"],
    # serves the window on 127.0.0.1 (a plain window hands over to a shareable one): done there
    "menu: Tools > Share the open figure with the MCP server": [
        "test_assistant_live.py::test_tools_menu_share_toggle",
        "test_assistant_live.py::test_a_plain_window_hands_its_figure_over"],
    "menu: Tools > Chat sidebar (local model)…": [
        "test_assistant_live.py::test_chat_sidebar_docks_the_sidecar",
        "test_assistant_live.py::test_chat_sidebar_without_the_package_says_how_to_install"],
    # docks an online chat page (clipboard mode in tests: no WebEngine offscreen)
    "menu: Tools > Chat in a web page (experimental, not recommended)…": [
        "test_web_chat_20261109.py::test_a_round_with_the_figure",
        "test_web_chat_20261109.py::test_launch_flag_docks_the_web_chat"],
    # steps of a recorded chat on the open figure (a recorded log is written there)
    "menu: Tools > Replay a chat…": ["test_chat_replay_20261113.py::test_the_dialog_steps_through_a_chat_and_resets"],
    "menu: Tools > Save the last chat as a procedure…": [
        "test_chat_replay_20261113.py::test_save_the_last_chat_and_run_it_from_the_chat"],
    "menu: Tools > Run a procedure…": ["test_chat_replay_20261113.py::test_run_a_procedure_on_the_open_figure"],
    "menu: Tools > MCP call history / undo…": [
        "test_mcp_history.py::test_gui_shows_the_history_and_undoes_the_last_mcp_change"],
    # records the user's own clicks: real events are sent through the application there
    "menu: Help > Debug > Start recording a bug…": [
        "test_bug_recorder.py::test_a_session_is_recorded_as_replayable_steps"],
    "menu: Help > Debug > Stop recording and describe the bug…": [
        "test_bug_recorder.py::test_a_session_is_recorded_as_replayable_steps",
        "test_bug_recorder.py::test_report_dialog_notes_and_discard"],
    "menu: Help > Debug > Open the recordings folder": ["test_bug_recorder.py::test_help_menu_entries"],
}


def _test_file_of(module):
    return module.__name__ + ".py"


def registry() -> dict:
    reg = {}

    def add(key, test):
        tests = reg.setdefault(key, [])
        if test not in tests:
            tests.append(test)

    import test_gui_e2e_context_menu as C
    for _kind, entry in C.ALL_CASES:
        add(H.ctx_key(entry), "test_gui_e2e_context_menu.py::test_right_click_entry")
    import test_gui_e2e_dnd as D
    for row in D.DROPS:
        add(H.drop_key(row[0], row[4]), "test_gui_e2e_dnd.py::test_drop")
    for situation, *_rest in D.DROP_OFFERS:
        add(H.drop_key(situation, "✕  Cancel"), "test_gui_e2e_dnd.py::test_drop_menu_offers_what_each_situation_allows")
    for situation, choice, _rows in D.DRAGS:
        add(H.drag_key(situation, choice), "test_gui_e2e_dnd.py::test_internal_drag")
    import test_gui_e2e_menus as M
    for key in M.ACTIONS:
        add(key, "test_gui_e2e_menus.py::test_menu_action")
    for key in M.WIDGETS:
        add(key, "test_gui_e2e_menus.py::test_toolbar_widget")
    for key, tests in M.ELSEWHERE.items():
        for t in tests:
            add(key, t)
    import test_gui_e2e_tutorials as T
    for key in T.TUTORIAL_KEYS:
        add(key, "test_gui_e2e_tutorials.py::test_tutorial_end_to_end")
    for key in T.GUIDE_KEYS:
        add(key, "test_gui_e2e_tutorials.py::test_show_me_how_guide")
    for key, tests in T.ELSEWHERE.items():
        for t in tests:
            add(key, t)
    for key, tests in LINKED.items():
        for t in tests:
            add(key, t)
    return reg
