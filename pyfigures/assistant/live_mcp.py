"""MCP stdio adapter for the isolated, explicitly launched GUI session."""
import json
import os
import sys
import uuid
from typing import Literal
import urllib.request
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Image

from pyfigures.assistant import runtime_dir
mcp = FastMCP('PyFigures live', instructions='This controls PyFigures scientific figures, not Figma. All original PyFigures tools are exposed by name. Figure tools default their pyf_path to "live", meaning the open GUI document including unsaved work. Omit pyf_path when working on that document; explicit paths use native file behavior. Other tools retain original file/service semantics. Figure-document edits update the canvas with GUI undo; sidecars remain in the session workspace and exports write to specified paths. Prototype tools also support explicit session/revision checks. Inspect when needed to identify panels. No automatic save of the live source figure.')


class LiveBridgeError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f'[{code}] {message}')


def request(operation, session_id=None, expected_revision=None, arguments=None, request_id=None):
    import urllib.error
    descriptor = runtime_dir() / 'connection.json'
    try:
        connection = json.loads(descriptor.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise LiveBridgeError('GUI_OFFLINE', 'The PyFigures window is closed or not sharing its figure (Tools > Share the open figure with the MCP server). Start it, then inspect the new session. No edit was submitted; do not repeat delete/add loops.') from exc
    payload = dict(operation=operation, session_id=session_id, expected_revision=expected_revision,
                   arguments=arguments or {}, request_id=request_id or str(uuid.uuid4()))
    req = urllib.request.Request(connection['url'], data=json.dumps(payload).encode(),
                                 headers={'Authorization': 'Bearer ' + connection['token'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=310 if operation == 'original_tool' else 25) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise LiveBridgeError('CONNECTION_REJECTED', 'The live connection changed. Reinspect the live figure before editing.') from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError,)):
            raise LiveBridgeError('OUTCOME_UNCERTAIN', 'The edit may still be running. Inspect the figure before resubmitting a mutation.') from exc
        raise LiveBridgeError('GUI_OFFLINE', 'PyFigures is not responding. Reopen its window. Do not keep retrying destructive operations.') from exc
    except TimeoutError as exc:
        raise LiveBridgeError('OUTCOME_UNCERTAIN', 'The operation may still be running. Inspect before repeating an edit.') from exc
    if 'error' in result:
        raise LiveBridgeError(result.get('error_code', 'TOOL_FAILED'), result['error'])
    return result['result']


def call_live(operation, arguments=None):
    """Retry only explicit pre-mutation state rejections, never uncertain edits."""
    for attempt in range(2):
        state = request('inspect')
        try:
            return request(operation, state['session_id'], state['revision'], arguments)
        except LiveBridgeError as exc:
            if attempt or exc.code not in ('REVISION_CONFLICT', 'SESSION_CHANGED'):
                raise


@mcp.tool()
def inspect_live_figure() -> dict:
    """Read the open PyFigures document, including unsaved labels, image counts, and row_spacing_px (gap between top-level rows)."""
    return request('inspect')


@mcp.tool()
def edit_live_label(session_id: str, expected_revision: int, text: str, request_id: str,
                    object_id: str = '', x: float = 20, y: float = 20) -> dict:
    """Edit an existing top-level label by object_id, or add one if empty. One normal undo step; no disk save. Use a fresh request_id per logical edit."""
    return request('set_label' if object_id else 'add_label', session_id, expected_revision,
                   dict(object_id=object_id, text=text, x=x, y=y), request_id)


@mcp.tool()
def live_history(session_id: str, expected_revision: int, action: str, request_id: str) -> dict:
    """Use normal GUI undo or redo. action must be undo or redo."""
    if action not in ('undo', 'redo'):
        raise ValueError('action must be undo or redo')
    return request(action, session_id, expected_revision, request_id=request_id)


@mcp.tool()
def preview_live_figure(session_id: str, expected_revision: int) -> Image:
    """Capture the visible canvas at its current zoom."""
    result = request('preview', session_id, expected_revision)
    return Image(path=result['path'])


@mcp.tool()
def arrange_live_images(session_id: str, expected_revision: int, request_id: str,
                        columns: int = 4, row_width_px: int = 0, spacing_px: int = 3) -> dict:
    """Regroup ALL image panels into horizontal rows of columns images, in current traversal order. Final row may be shorter. Preserve panel annotations/crops/insets; replace previous group structure. Standalone labels follow rows; nested text rows are rejected. Uses existing PyFigures XML/layout tools on a temporary snapshot. One undo step; no save. row_width_px=0 keeps GUI width."""
    return request('arrange_rows', session_id, expected_revision,
                   dict(columns=columns, row_width_px=row_width_px, spacing_px=spacing_px), request_id)


@mcp.tool()
def live_pyfigures_tool_catalogue() -> dict:
    """Catalogue of ALL original PyFigures tools, with original arguments, live target parameter, and batch_supported flag. All are directly callable by their own names. The legacy batch adapter accepts only batch_supported tools."""
    from .existing_tools import catalogue
    return catalogue()


@mcp.tool()
def run_live_pyfigures_tools(session_id: str, expected_revision: int, request_id: str,
                             calls: list[dict], read_only: bool = False) -> dict:
    """Run supported existing PyFigures commands against the OPEN figure's temporary snapshot. Get names/arguments from live_pyfigures_tool_catalogue. calls=[{tool: name, arguments: {...}}]. Reads include describe_figure/list_images/get_annotations/get_figure_properties. set_spacing changes spacing inside a group, along its orientation; set_figure_properties(default_spacing=...) changes spacing BETWEEN top-level rows. Edits commit as ONE undoable transaction only if all calls succeed; no original disk save. Group paths refer to current snapshot and change as calls execute."""
    return request('existing_read' if read_only else 'existing_batch', session_id,
                   expected_revision, dict(calls=calls), request_id)


@mcp.tool()
def set_panel_letter_position(placement: str = 'top left') -> dict:
    """Move the existing automatic PANEL LETTERS (A, B, C...) to a corner of every image. Updates the figure's global lettering position so GUI auto-lettering preserves it on refresh. Use top left, top right, bottom left or bottom right. Preserve letters, font, size, colors and other annotations. One GUI undo step; no source save. For moving panel letters use this instead of deleting them or adding ordinary corner labels, which auto-lettering can replace."""
    return call_live('bulk_letters', {'action': 'style', 'placement': placement})


@mcp.tool()
def inspect_panel_letters() -> dict:
    """Inspect actual panel letter text, position, font, foreground, background and per-panel IDs after GUI refresh. Distinguishes hidden letters from other annotations."""
    return call_live('letter_state')


@mcp.tool()
def edit_panel_letters(action: Literal['style','remove','restore','renumber'] = 'style', scope: Literal['auto','all','group','panels','selection'] = 'auto', group_path: list[int] | None = None,
                       panel_ids: list[str] | None = None, placement: str | None = None,
                       font_family: str | None = None, font_size: float | None = None,
                       color: str | int | None = None, background: str | int | None = None,
                       start_letter: str | None = None, replace_overrides: bool = False,
                       removal_request: str | None = None) -> dict:
    """Preferred ONE-CALL bulk operation for panel-letter placement, font family/size, color/background, removal and restoration. For bold/italic/underline use restyle_texts(target=letters); those are not fields of this function. placement accepts center/centre/middle or a corner. action=style preserves existing text; renumber scope=all creates a complete unique sequence for a newly constructed figure when asked to letter the panels; partial restore preserves existing IDs and is not a whole-figure renumber; remove requires removal_request quoting an explicit user request to remove/hide letters (never a swap), and hides panel letters persistently without deleting captions/scale bars; restore without start_letter preserves an existing or hidden panel text and otherwise uses its automatic position; explicit start_letter sets a new sequence; renumber changes sequence. scope=auto infers panels from panel_ids, group from group_path, otherwise all; explicit panels/group/selection/all are supported. Supplying panel_ids can never broaden to all panels. For WHITE Arial 12 with NO background use color="white", font_family="Arial", font_size=12, background="none". Black is a color, NOT transparent. Unspecified appearance is preserved. Per-panel overrides survive whole-figure style changes unless replace_overrides=true. One undo step. Returns actual styles, changed/skipped counts, and recovery status. Do not loop over individual annotations for figure/group requests."""
    if panel_ids and scope in ('auto', 'all'):
        scope = 'panels'
    elif group_path is not None and scope == 'auto':
        scope = 'group'
    elif scope == 'auto':
        scope = 'all'
    return call_live('bulk_letters', dict(action=action, scope=scope, group_path=group_path,
        panel_ids=panel_ids, placement=placement, font_family=font_family, font_size=font_size,
        color_value=color, background=background, start_letter=start_letter,
        replace_overrides=replace_overrides, removal_request=removal_request))


@mcp.tool()
def swap_live_panels(first: str, second: str, target: str = 'images') -> dict:
    """Exchange two image panels OR only their letter texts, in one verified undo step. first/second are unique visible letters or panel IDs from inspect_panel_letters. target defaults to images: 'swap q and o' exchanges PANELS identified by those letters. Use letters only when the user explicitly asks to exchange letter text; do not ask images-versus-letters for ordinary swap requests. Images mode keeps slot lettering and swaps image content with its other annotations. Never remove/recreate letters to swap. Reports actual identities and letter counts; rolls back if verification fails."""
    return call_live('swap_panels', dict(first=first, second=second, target=target))


@mcp.tool()
def reverse_selected_row(expected_selection_token: str | None = None) -> dict:
    """Reverse/invert panel order in the CURRENT selected horizontal row, or the single row containing selected image(s), in one verified undo step. Read inspect_figure.selection first; do not ask the row number if it identifies one row. Letters/styles move with their images. Reject absent, stale or multi-row selections. Optionally pass the inspected selection token to reject selection changes before dispatch."""
    current = request('inspect')
    return request('reverse_selected_row', current['session_id'], current['revision'],
                   {'expected_selection_token': expected_selection_token or current['selection']['token']})


@mcp.tool()
def delete_last_rows(count: int = 2) -> dict:
    """Delete the last N horizontal image rows in ONE atomic undo step. If N exceeds available rows, delete all available rows and report rows_deleted as the actual count, plus rows_requested. An already empty figure is a verified no-op. Prefer for 'delete/remove last two rows'; never loop over shifting remove_group indices. Resolves target rows from one current snapshot, verifies exact removed images and retained rows/styles. Rejects ambiguous nested/free-canvas/text structures without editing. completion_verified must be true before claiming success; returns before/after counts and original row indices."""
    return call_live('delete_last_rows', {'count': count})


@mcp.tool()
def ungroup_all_images() -> dict:
    """Ungroup ALL images onto free canvas in ONE verified undo step, using native automatic layout and canvas refresh. Use for 'ungroup all', 'all images as single images'. Verify grouped_images_after=0 and automatic_layout_applied. Report actual groups removed. ALREADY_UNGROUPED means no change; LAYOUT_REFRESHED means structure was flat but stale layout was refreshed. Never claim groups removed in either case. Preserves image content/order, annotations and actual letters. No delete/recreate or per-image move loops."""
    return call_live('ungroup_all_images', {})


@mcp.tool()
def remove_scale_bar_all() -> dict:
    """Remove ALL scale bars throughout the open figure in ONE verified, undoable operation. Prefer this for 'remove all scale bars'; never loop over remove_scale_bar on every image. Recurses nested panels and reports actual before/after bar counts. Preserves image data, panel letters and other annotations. No calibration required for removal. For only one specific panel use the original remove_scale_bar."""
    return call_live('remove_scale_bars_all', {})


@mcp.tool()
def save_live_figure(path: str | None = None, overwrite: bool = False) -> dict:
    """Save the live figure and staged metadata as a .pyf COPY. Omit path for a timestamped file in saved_figures. Does not overwrite the original source. Recovery snapshots happen automatically; this operation is an explicit save. Existing files require overwrite=true."""
    return call_live('save_copy', {'path': path, 'overwrite': overwrite})


@mcp.tool()
def list_recovery_snapshots() -> dict:
    """List automatic recoverable figure versions from earlier live sessions. Recovery copies differ from an explicit saved source file."""
    root = runtime_dir() / 'recovery'
    snapshots = []
    for manifest in root.glob('*/latest.json'):
        try:
            snapshots.append(json.loads(manifest.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            continue
    return {'snapshots': sorted(snapshots, key=lambda s: s['created_at'], reverse=True)[:30]}


@mcp.tool()
def restore_recovery_snapshot(snapshot: str) -> dict:
    """Restore a .pyf snapshot reported by list_recovery_snapshots into the live GUI as unsaved work. Original source untouched; undoable."""
    return call_live('recover', {'snapshot': snapshot})


from .original_registry import register_all
ORIGINAL_TOOL_COUNT = register_all(mcp, request)



@mcp.tool()
def swap_rows(first_row: int, second_row: int) -> dict:
    """Swap two complete horizontal rows in ONE atomic verified undo step. Use visible human row numbers starting at 1: row 1 and row 2 means first_row=1, second_row=2. Preserve image order within rows, annotations and letter styles. With automatic lettering enabled, letters follow their NEW positions, matching native keyboard rearrangement; do not preserve old letter text. With automatic lettering disabled, retain existing text. Prefer this over individual move_image operations. Reject ambiguous non-row canvases."""
    return call_live('swap_rows', dict(first_row=first_row, second_row=second_row))



@mcp.tool()
def select_live_objects(panel_refs: list[str] | None = None, group_paths: list[list[int]] | None = None,
                        row_numbers: list[int] | None = None, clear: bool = False) -> dict:
    """Select actual GUI image panels, rows or columns; no document edit. Use ONE selector: panel_refs are visible letters or panel IDs, group_paths from inspection can select rows/columns/nested groups, row_numbers are visible top-level row numbers starting at 1. Multiple targets supported. clear=true clears selection. Returns verified live selection. For reverse last row, select its row_number then reverse_selected_row; never swap individual images repeatedly."""
    return call_live('select_live_objects', dict(panel_refs=panel_refs, group_paths=group_paths, row_numbers=row_numbers, clear=clear))

@mcp.tool()
def open_annotation_editor(panel_ref: str | None = None) -> dict:
    """Select a named panel and open its NATIVE annotation editor, just like GUI double-click. Omit panel_ref only when one panel is already selected. Does not invent/add annotations; human uses native OK/Cancel. Result scheduled means opening requested, not annotation completed. For a vague annotate-panel request first ask what annotation to add or offer this editor. Never add placeholder text like Panel o."""
    return call_live('open_annotation_editor', dict(panel_ref=panel_ref))


@mcp.tool()
def roi_to_inset(panel_ref: str, annotation_index: int | None = None) -> dict:
    """Convert an EXISTING rectangular ROI into an inset from the SAME panel source, matching native Rect ROI --> Inset. No external image filename needed. panel_ref is a visible letter or panel ID. If exactly one rectangle exists, omit annotation_index; otherwise inspect get_annotations and specify its index. Keeps the source ROI, other annotations, letter styles, channels/LUTs and source. One verified undo transaction. Existing native ROI rotation/crop helper is reused."""
    return call_live('roi_to_inset', dict(panel_ref=panel_ref, annotation_index=annotation_index))


@mcp.tool()
def explain_live_interaction(topic: str = 'overview') -> dict:
    """Human manual instructions for native arrow-key rearrangement and internal drag-and-drop choices. topic shortcuts/drag_and_drop/split/overview, or the user's words. Read-only: never rearranges the figure. Explains the current right-click Split > Channel split (Gray mode) path, selection level, figure focus, Left/Right and Up/Down, Swap, To row, To column, Join as block versus panel by panel, Extrude and cancelling. Exact availability depends on source/target. Reports needs_review if native code changed; never invent shortcuts or modifiers."""
    from .manual_help import explain
    return explain(topic)


@mcp.tool()
def inspect_native_gui(query: str = '', scope: str = 'active', limit: int = 40, offset: int = 0) -> dict:
    """Discover REAL native menu actions and visible controls, including dialogs/editors. Query labels/path/tooltip; scopes active/main/all. Returns control_id, exact choices/values/enabled state, shortcuts and asynchronous job status. No document edit. Covers native GUI features not yet having dedicated tools. Prefer dedicated tools for common edits; do not invent menu/control IDs."""
    return request('inspect_native_gui', arguments=dict(query=query,scope=scope,limit=limit,offset=offset))

@mcp.tool()
def use_native_gui(control_id: str, operation: str = 'activate', value: object = None) -> dict:
    """Invoke an INSPECTED native control. operation activate (menu/button), set (text/number/toggle/exact choice), accept/reject (dialog). Uses native signals and validations. Returns QUEUED job, not edit success. Inspect jobs/active controls next; fill any modal dialog and accept/cancel according to user intent. Verify document state before claiming changes. No arbitrary Python/method calls. Interactive native controls are not preview-draft operations."""
    return call_live('use_native_gui',dict(control_id=control_id,operation=operation,value=value))

@mcp.tool()
def open_native_menu(source: str | None = None, target: str | None = None) -> dict:
    """Open native right-click or drag/drop context menu. source is panel letter/ID, row:2 (one-based top-level row), group:0/1 (zero-based group path), or omit for current single selection. With target set, open the REAL native drop choices for source onto target. Then inspect_native_gui and activate one actual menu choice (Swap, Join, To row/column, Extrude...) or cancel. No assumed universal drag menu. Opening the menu alone does not commit a layout edit. Same-row drops may offer no choices: native Left/Right or the dedicated swap tool handles that."""
    return call_live('open_native_menu',dict(source=source,target=target))

@mcp.tool()
def native_gui_keys(control_id: str, sequence: str) -> dict:
    """Send native keyboard shortcut to inspected control, e.g. Left/Right on figure canvas. Respect exact shortcut returned by inspect_native_gui and platform modifiers. Uses native keyboard behaviour and undo; verify job/document after. Avoid sending figure shortcuts to chat/text fields."""
    return call_live('native_keys',dict(control_id=control_id,sequence=sequence))

@mcp.tool()
def native_gui_gesture(control_id: str, points: list[list[float]], kind: str = 'drag',
                       coordinate_system: str = 'widget', button: str = 'left') -> dict:
    """Use the currently selected NATIVE canvas/editor tool with actual click/double_click/drag points. Widget coordinates are logical pixels; scene coordinates divide out the reported scene_zoom. Neither implies raw-image coordinates for rotated/cropped images. Inspect native tool/geometry first. Useful for native drawing tools missing dedicated MCP operations. Returns queued job; verify annotations/state afterward."""
    return call_live('native_gesture',dict(control_id=control_id,points=points,kind=kind,coordinate_system=coordinate_system,button=button))

@mcp.tool()
def native_gui_drop_files(control_id: str, paths: list[str]) -> dict:
    """Drop existing local files onto an INSPECTED native drop target. Uses original drag-enter/drop handlers; rejection is reported, not guessed as success. Inspect target and verify resulting files/panels. Existing native dialogs may require more input. Does not invent external drag MIME behaviours."""
    return call_live('native_drop_files',dict(control_id=control_id,paths=paths))


@mcp.tool()
def review_submission_readiness(pyf_path: str = 'live', journal: str | None = None,
                                column: str = 'single', width_mm: float | None = None,
                                min_dpi: int = 300) -> dict:
    """Read-only technical readiness review: runs BOTH native resolution and journal compliance checks on actual current state. Returns measured blockers, pass/incomplete statuses and raw evidence. Use for ready/submission/publication questions; audit_figure inventories labels/bars but cannot establish readiness. Omit journal/width to use stored target; no valid target means incomplete, never ready. Does not certify scientific content or statistical assumptions."""
    arguments=dict(journal=journal,column=column,width_mm=width_mm,min_dpi=min_dpi)
    if pyf_path=='live':return call_live('submission_review',arguments)
    from .submission_review import review_file
    return review_file(Path(pyf_path),arguments)

@mcp.tool()
def inspect_annotation_objects(panel_ref: str | None = None, offset: int = 0, limit: int = 12, include_panel_letters: bool = False) -> dict:
    """Inspect ordinary rich-text annotations and ROI geometry with per-object stale-check tokens. panel_ref is a visible letter or panel ID. Read actual HTML/text, geometry and properties before advanced edits. Automatic panel letters are flagged; use scoped letter tools for those."""
    return call_live('inspect_annotation_objects', dict(panel_ref=panel_ref,offset=offset,limit=limit,include_panel_letters=include_panel_letters))

@mcp.tool()
def edit_annotation_properties(panel_ref: str, annotation_index: int, token: str, changes: dict, substring: str | None = None, occurrence: int | None = None) -> dict:
    """Advanced ordinary text or ROI edit, one undo transaction. First inspect_annotation_objects for index/token. Text changes: literal text replacement, bold/italic/underline booleans, font_family, font_size, color, background (none clears), vertical_alignment normal/subscript/superscript, placement named corner or center for the whole annotation. substring optionally limits formatting/replacement to literal text; repeated matches require 1-based occurrence. Preserves unrequested formatting. ROI changes: color, fill_color (none clears), stroke, opacity, geometry [x,y,width,height] for Rect2D/Ellipse2D or endpoints [x1,y1,x2,y2] for Line2D; source-image pixels. Unsupported shapes use native annotation editor controls. Finish/cancel any open native editor first. Returns actual before/after; NO_CHANGE is not success."""
    return call_live('edit_annotation_properties', dict(panel_ref=panel_ref,annotation_index=annotation_index,token=token,changes=changes,substring=substring,occurrence=occurrence))

@mcp.tool()
def open_annotation_properties(panel_ref: str, annotation_index: int, token: str) -> dict:
    """Open and select an existing annotation using the actual native property editor. First inspect_annotation_objects. If the native editor is already open for that panel, use the current draft annotation index/token; its edits are retained. Text, scale bars and insets open the same dialog as double-click; other ROI types are selected with native controls. Scheduled is not applied. Inspect_native_gui to use exact control IDs; native OK/Cancel remains in effect, including the outer annotation editor."""
    return call_live('open_annotation_properties', dict(panel_ref=panel_ref,annotation_index=annotation_index,token=token))


if __name__ == '__main__':
    from pyfigures.mcp_server import run_stdio
    if os.environ.get('PYFIGURES_MCP_SURFACE', 'categories') == 'all':
        active_server = mcp
    else:
        from .categorized_mcp import build_server
        active_server = build_server(mcp, request)
    run_stdio(active_server)





