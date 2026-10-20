# GUI end-to-end tests

The `gui_e2e` tests drive the figure editor the way a user does and check
what each action PRODUCED, not only that it did not crash.

## Running them

Run them in ONE pytest process (never in parallel: several Qt test processes
at once in a OneDrive folder have crashed the machine):

```bash
QT_API=pyqt6 PYTEST_QT_API=pyqt6 QT_QPA_PLATFORM=offscreen \
  python -m pytest -m gui_e2e tests -p no:cacheprovider -W ignore::DeprecationWarning
```

The whole layer takes under ten minutes. The tests are part of the normal
suite too (`pytest tests` runs them); `-m "not gui_e2e"` leaves them out.

Useful switches:

| variable | effect |
|---|---|
| `PYF_E2E_RECORD=1` | print what each scenario did (dialogs seen, layout before → after) instead of asserting the layout rows: for writing new expectations |
| `PYF_E2E_UPDATE_GOLDEN=1` | rewrite the golden images of `test_gui_e2e_visual.py` (only on purpose, after checking the renders) |
| `PYF_E2E_FULL=1` | run every right-click entry on every kind of selection (≈ 260 cases, +3 min) instead of each entry on the kinds where it can behave differently |
| `PYF_E2E_SEED=<n>` | replay one monkey sequence (`test_gui_e2e_monkey.py` prints the seed and the actions when it fails) |
| `PYF_E2E_MONKEY_STEPS=<n>` | length of each monkey sequence (default 18) |
| `PYF_E2E_COVERAGE=<file.md>` | write the actions × tests table (see `GUI_E2E_COVERAGE.md`) |

Add `-o faulthandler_timeout=90` to get a traceback if a scenario ever waits
on a dialog nobody answers.

## How a scenario works

`tests/gui_e2e_harness.py` holds the tools:

* **Real events.** External drops are `QDragEnterEvent` / `QDragMoveEvent` /
  `QDropEvent` carrying file URLs at a computed canvas position, followed by
  a click on the in-window drop menu's button. Internal drags and right-clicks
  are mouse press / move / release events sent through the canvas handlers.
  No OS-level mouse input is ever injected.
* **Real dialogs.** Dialogs really run (`exec`); a `DialogPilot` timer finds
  the active modal dialog, fills its widgets (`widget_by(dialog, QSpinBox,
  label="Rows")`) and clicks its buttons. A dialog nobody expected is
  cancelled and fails the test; a handler that raises cancels its dialog
  instead of leaving the test hanging. File pickers are native OS windows and
  are answered with prepared paths (`no_file_dialogs` fixture).
* **The result, from a saved file.** `snapshot()` saves the figure and reads
  it back: `layout_rows` (what the MCP tools report) plus every panel's
  crop, rotation, LUTs, channels, projection, display range, background,
  script, series, letters, texts, scale bars, ROIs, insets and size.
* **Invariants after every action.** `check_invariants()`: Undo gives the
  figure before the action back, Redo the one after, and a save / reopen
  keeps it. `Watch` fails the test on any uncaught exception, Qt warning or
  ERROR logged by pyfigures / batoolset.

Sample inputs (`make_files`): 8- and 16-bit TIFFs, PNGs, an RGB image, a Z
stack, a time stack, a two-page PDF (multi-series), a CSV, a text file, a
`.tex` equation, a short MP4, a folder and a `.pyf`.

## The files

| file | what it covers |
|---|---|
| `test_gui_e2e_dnd.py` | every drop situation × every drop-menu button (incl. dialogs: grid panel, montage, series), drops without a menu, and every internal-drag situation × menu entry |
| `test_gui_e2e_context_menu.py` | the canvas right-click menu for each kind of selection (nothing, image, standalone image, several images, row, label row, equation, inset, template slot, RGB image, Z stack): entries offered, and every entry run with its dialog |
| `test_gui_e2e_menus.py` | every menu-bar entry and toolbar button / widget: exports checked on the written files, reports on their text, figure changes on the saved state |
| `test_gui_e2e_image_editor.py` | double-click → image editor: crop, rotate, LUTs, projection, text, scale bar, every ROI tool, Cancel |
| `test_gui_e2e_tutorials.py` | each Help tutorial: "Set it up for me" where needed, then every step performed until the tutorial sees it done; each "Show me how" guide followed to its end |
| `test_gui_e2e_visual.py` | renders of key scenarios against `tests/golden_gui/*.png` (≤ 0.5 % of pixels may differ) |
| `test_gui_e2e_monkey.py` | seeded random sequences of right-clicks, drags, drops and undo, with the invariants after every action |
| `test_gui_e2e_coverage.py` | the guard (below) |
| `test_bugs_found_by_gui_e2e.py` | one regression test per bug the layer found |

## Following an evolving GUI

The layer reads the GUI it runs against instead of a frozen copy of it:

* **Everything is discovered live.** Menu-bar and toolbar entries, toolbar
  widgets, the right-click menu of each selection kind, the drop menu of each
  drop situation and the drag menu of each drag situation are enumerated from
  the running window at every run.
* **Renames and moves are followed.** Labels are compared without their
  cosmetics (`label_key`: case, `…` / `...`, arrows, emoji, `&`, shortcut
  text, spacing), and an entry that moved to another menu is found by its
  name when that name is unique (`resolve_key`, `find_action`). Tables keep
  working; the guard prints which keys it followed so they can be updated
  when convenient.
* **Removals skip, they do not crash.** A table row whose entry the GUI no
  longer offers is skipped with the reason; only the "what does this menu
  offer" tests (`test_each_selection_offers_its_entries`,
  `test_drop_menu_offers_what_each_situation_allows`,
  `test_drag_menus_offer_the_right_choices`) fail, once, when an entry
  expected there disappeared — remove it from `OFFERED` / `DROP_OFFERS` /
  `DRAGS` if that was intended.
* **New entries are exercised at once.** `test_unregistered_actions_are_swept_generically`
  runs every live action no table covers yet the way a user reaches it —
  dialogs accepted with their defaults, file pickers cancelled — and
  requires no exception / Qt warning / logged error, every dialog closed, and
  undo / redo / reopen consistent. The guard still fails until a row
  checking the action's RESULT is added.
* **Dialogs are answered by what they contain.** Handlers find widgets by
  their label (`widget_by(dialog, QSpinBox, label="Rows")`), dialogs are
  matched by a fragment of their title (cosmetics ignored), OK buttons that
  wait for a preview are waited for, and a handler that fails cancels its
  dialog instead of leaving the run blocked.

## The coverage guard

`test_gui_e2e_coverage.py` lists every action reachable in the live window
— menu bar, toolbar (buttons, Background menu, widgets), right-click menu
per selection kind, drop menu per drop situation, drag menu per drag
situation — and fails when one has no behaviour test in
`tests/gui_e2e_registry.py` or when a registered test does not exist
(registered actions the GUI no longer offers are reported as warnings).

Adding a menu entry therefore means adding its row to the matching table
(`ACTIONS` in `test_gui_e2e_menus.py`, `ENTRIES` in
`test_gui_e2e_context_menu.py`, `DROPS` / `DRAGS` in `test_gui_e2e_dnd.py`)
— the row IS the registration — or, for an action tested elsewhere, a line
in `LINKED` / `ELSEWHERE` naming that test.

Keys look like:

```
menu: File > Export As > PNG
toolbar: Background > White
toolbar-widget: size_spinbox
right-click: Crop & size ▶ / Reset crop only
drop [onto a group]: ↕  To column (with image below)
drag [row onto row]: Swap
```
