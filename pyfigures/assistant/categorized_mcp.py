"""Small, stable MCP surface backed by the complete original registry."""
import json
import os
import re
import uuid
from mcp.server.fastmcp import FastMCP, Image
from mcp.types import ToolAnnotations

FULL_SCHEMAS = 2       # compact discovery: full argument schemas for the best matches only
# The common operations whose exact fields the dispatcher lists, so they can be
# called without a search (small models spent most of their context searching).
COMMON_CONTRACTS = ('edit_panel_letters', 'swap_live_panels', 'remove_annotation', 'set_lut', 'set_scale_bar',
                    'set_scale_bar_all', 'set_figure_caption', 'add_annotation', 'arrange_live_images',
                    'delete_last_rows', 'restyle_texts', 'swap_rows', 'reorder_children', 'set_panel_letter_position',
                    'add_label_row')
CONTRACT_SCOPE = {
    'swap_rows': 'exchanges WHOLE rows; to reorder panels inside one row use reorder_children',
    'reorder_children': 'reorders the panels WITHIN one row/group, e.g. reversing a row',
    'set_panel_letter_position': 'GLOBAL default letter placement for every panel (a corner INSIDE it), not one '
                                 'selected panel letter; letters OUTSIDE the panels = set_panel_letter_layout row',
    'delete_last_rows': 'removes WHOLE rows from the end; only on an explicit removal request',
    'swap_live_panels': 'exchanges two panels, keeping their letters in place',
}

CATEGORIES = {
    'native_gui': 'Actual native menus, dialogs, editor controls, keyboard, context/drop operations and canvas/file interactions. Fallback for capabilities not yet represented by dedicated tools.',
    'help': 'Human GUI help: authored menu paths, selection and right-click steps. Use explain_how or list_how_to_guides for how-to requests, not coding examples.',
    'inspect': 'Read figure structure, panels, annotations, properties and current settings.',
    'layout': 'Arrange rows, group, move, resize and change horizontal or vertical spacing.',
    'lettering': 'Automatic panel-letter positions, fonts, text labels, captions and alt text.',
    'images': 'Image files, crop, rotation, channels, LUTs, normalization and stack views.',
    'annotations': 'Scale bars, arrows, ROIs, significance brackets and insets.',
    'scale_bars': 'Scale bars only: inspect one, add/update one or all, remove one or ALL in one operation. Use bulk operations for whole-figure requests.',
    'create_export': 'Create figures or plots, recipes, render, export and compare files.',
    'quality': 'Scientific checks, journals, resolution, image integrity and provenance.',
    'posters': 'Poster and album documents, pages, layout, preview and export.',
    'setup': 'Server information, installation, guides, bug recordings and history.'}


def category_for(name):
    if name in ('index_image_folder', 'search_images'):return 'images'
    if name in ('inspect_annotation_objects','edit_annotation_properties','open_annotation_properties'):return 'annotations'
    if name=='restyle_texts':return 'lettering'
    if name=='review_submission_readiness':return 'quality'
    if name in ('inspect_native_gui','use_native_gui','open_native_menu') or name.startswith('native_gui_'):
        return 'native_gui'
    if name == 'explain_live_interaction':
        return 'help'
    if name == 'inspect_figure':
        return 'inspect'
    if name == 'preview_panel':
        return 'images'
    if name in ('open_annotation_editor', 'roi_to_inset'):
        return 'annotations'
    if name in ('list_how_to_guides', 'explain_how', 'show_me_how', 'show_me_where', 'guidance_status', 'close_guidance'):
        return 'help'
    if 'scale_bar' in name:
        return 'scale_bars'
    if name in ('swap_live_panels', 'swap_rows', 'select_live_objects', 'open_annotation_editor', 'roi_to_inset', 'explain_live_interaction', 'ungroup_all_images', 'delete_last_rows', 'reverse_selected_row'):
        return 'layout'
    if name in ('save_live_figure', 'list_recovery_snapshots', 'restore_recovery_snapshot'):
        return 'create_export'
    if any(s in name for s in ('poster', 'album')):
        return 'posters'
    if name in ('get_figure_properties', 'describe_figure', 'get_xml', 'list_images',
                'get_annotations', 'list_image_properties', 'get_image_property'):
        return 'inspect'
    if any(s in name for s in ('letter', 'label', 'annotation_text', 'style_annotation',
                               'caption', 'font', 'alt_text', 'tidy_text', 'figure_properties')):
        return 'lettering'
    if name in ('add_annotation', 'remove_annotation') or any(s in name for s in (
            'scale_bar', 'inset', 'zoom_callout', 'roi_', 'arrow', 'significance')):
        return 'annotations'
    if any(s in name for s in ('spacing', 'orientation', 'reorder', 'move_image', 'size',
                               'layout_canvas', 'recompute_layout', 'group', 'arrange_live')):
        return 'layout'
    if name.startswith(('check_', 'audit_', 'journal_', 'apply_journal', 'prepare_journal',
                        'save_journal', 'validate_journal', 'list_journal', 'get_journal',
                        'extract_journal', 'figure_review')):
        return 'quality'
    if name.startswith(('export_', 'render_', 'create_', 'draft_', 'build_', 'scan_',
                        'index_', 'search_', 'diff_', 'consolidate_', 'recipe_', 'copy_style')):
        return 'create_export'
    if any(s in name for s in ('image', 'channel', 'stack', 'lut', 'kymograph', 'orthogonal',
                               'script', 'template', 'transform', 'moved_files', 'remap_paths')):
        return 'images'
    return 'setup'


def topic_note(words):
    """What a search cannot find because it does not exist, or hides under another name:
    said at once, before the tool list (2026-11-12: "make the 2nd row a little taller"
    took thirty calls and ended in a row wider than the figure; "show the next z" was
    searched eight times)."""
    words = set(words)
    if words & {'row', 'rows'} and words & {'height', 'taller', 'shorter', 'tall', 'heights', 'equal', 'same'} \
            or words & {'image', 'panel', 'picture'} and words & {'bigger', 'larger', 'smaller', 'resize'} and 'figure' not in words:
        return ('ROW HEIGHT / SIZE OF ONE IMAGE: there is no such property. Every row spans the figure width and the '
                'images of a row share one height, so a row is as tall as the shapes of its images make it. To make a row '
                'taller: put fewer images in it (arrange_live_images row_counts), crop its images narrower '
                '(transform_image), or widen the whole figure (resize_figure). set_size on one row makes it wider than '
                'the others: not what is asked. Say this and offer these choices; do not search further. ')
    if words & {'z', 'slice', 'slices', 'plane'} and not words & {'montage', 'orthogonal'}:
        return ('ONE Z SLICE: configure_image(projection="max", projection_z_start=k, projection_z_end=k+1) shows slice k '
                '(0-based) alone; "next z" = the current start + 1 (no stored start = a projection of all slices or slice 0: '
                'say which one you show). ')
    return ''


def build_server(full_server, send):
    from .original_registry import registry
    originals = set(registry())
    names = originals | {'arrange_live_images', 'set_panel_letter_position', 'edit_live_label',
        'edit_panel_letters', 'inspect_panel_letters', 'swap_live_panels', 'swap_rows', 'select_live_objects', 'open_annotation_editor', 'show_me_where', 'roi_to_inset', 'preview_panel', 'explain_live_interaction', 'save_live_figure',
        'list_recovery_snapshots', 'restore_recovery_snapshot', 'remove_scale_bar_all', 'ungroup_all_images', 'delete_last_rows', 'reverse_selected_row'}
    names.discard('preview_panel_source')   # the live preview_panel shows the open figure's panel
    names.update({'open_annotation_properties','inspect_annotation_objects','edit_annotation_properties','review_submission_readiness','inspect_native_gui','use_native_gui','open_native_menu','native_gui_keys','native_gui_gesture','native_gui_drop_files'})
    available = {n: t for n, t in full_server._tool_manager._tools.items() if n in names}
    font_tool = available.get('list_fonts')
    if font_tool is not None:
        def compact_list_fonts(query: str | None = None):
            value = font_tool.fn(query=query)
            if query:return value
            from .result_evidence import compact_font_inventory
            return compact_font_inventory(value)
        available['list_fonts'] = type(font_tool).from_function(
            compact_list_fonts, name='list_fonts', description=font_tool.description,
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
            structured_output=False)
    # PYFIGURES_COMMON_CONTRACTS=1 lists the wider common-operation contracts; off by default
    # because Qwen 9B then skipped discovery and picked the wrong scope (swap_rows for a within-row reverse).
    common = os.environ.get('PYFIGURES_COMMON_CONTRACTS', '0') == '1'
    server = FastMCP('PyFigures categorized live prototype', instructions=(
        'Edit scientific figures in the open PyFigures GUI. Start with a small tool surface. '
        'Only the seven advertised top-level functions are directly callable. Other names returned by find_pyfigures_tools are inner operations, NOT callable functions. Invoke them through use_pyfigures_tool(tool_name=the_discovered_name, arguments=the_exact_arguments). This applies equally to read-only explain_live_interaction and other guide operations. '
        'inspect_figure.selection contains the live user-selected panels, groups and containing row paths. Use it for this/selected row or image; do not ask users to repeat an unambiguous selection. Reverse/invert the selected row with reverse_selected_row. Reject missing or multi-row selection, never guess. '
        'For manual drag cancellation: release the mouse, then choose Ignore or dismiss the opened context menu. Escape is verified for the open menu, not during the active drag; do not invent clicking empty canvas as cancellation. '
        'For manual questions use explain_live_interaction with the actual topic or explain_how; follow returned current menu paths. Manual teaching never authorizes editing. API examples inside tool descriptions are developer references, not user-facing instructions: omit them unless code or recipe is explicitly requested. Panel-by-panel joining is ONE drop/operation with ordered contents. '
        'HOW-TO requests mean human GUI instructions by default: discover explain_how or list_how_to_guides, give authored menu/right-click paths, and offer to do the edit from natural language. Show commands only if the user explicitly asks for code or recipe; teaching is not permission to edit. '
        'RELATIVE requests (bigger, smaller, thicker, thinner, a bit more, too much, brighter) carry no number and need none: change the current value by a moderate step (about a third; half that for "a bit"), say the old and the new value, and offer to go further. Never ask for a number first. Misspelt words are read as the obvious word ("mak lettrs biger" = make the letters bigger). '
        'An invalid quantity or unsupported value requires clarification. For row deletion, a count larger than available means delete all available rows and report the ACTUAL number removed, using the bulk operation once. Do not turn zero columns into one, change a negative size to a positive size, or choose a substitute LUT/corner after validation fails. Explain the valid range and ask the user for a corrected value. '
        'A missing or ambiguous named panel is unresolved user intent, not an instruction to choose another panel. After UNKNOWN_PANEL_REFERENCE or AMBIGUOUS_PANEL_REFERENCE, ask for the corrected target and stop that edit. Never replace a failed letter with guessed numeric coordinates, an ordinal, or the last panel; inspection cannot establish which replacement the user intended. '
        'SWAPS: swap q and o means swap image PANELS identified by those letters. Default target=images. '
        'Letter TEXT swaps require an explicit swap-the-letters/labels request; do not ask images-versus-letters for normal swaps. If a reference is missing or non-unique, STOP and ask; never substitute an existing panel or retry the swap with other references. '
        'A uniquely named panel wins over a positional/visual description; act on that name and mention the discrepancy. Never edit then undo to ask. '
        'If both swap references identify the same panel (including a letter and its equivalent panel ID), report no change. Repeating a reference is not evidence of duplicate panel letters; use actual duplicate_letter_references from state before claiming ambiguity. '
        'Use swap_live_panels; never delete/recreate letters to swap or relabel. '
        'Removal is only for an explicit user request to remove letters; removal_request must quote it. '
        'Readiness requires review_submission_readiness: actual resolution AND journal checks. audit_figure is inventory, not readiness. Report measured blockers and incomplete evidence; never infer readiness from labels or export DPI. '
        'For multi-clause requests, satisfy and verify every clause before saying done. A named target in edit arguments does not select it in the GUI: explicit select-plus-edit requests need select_live_objects as well as the edit. Preserve the selection and check the final outline/state. '
        'A successful tool call is not task success. Report verified after-state; if counts show zero letters, '
        'say letters are absent, never claim a lettering swap succeeded. '
        'When the human supplies annotation content, such as write a text note on a named panel, create the ordinary annotation with add_annotation. Merely opening an editor does not fulfill a request to write the supplied content. Offer/open the editor for unspecified content or an explicit editor request. '
        'Whenever you list choices for a change (and always for a HELP request such as "help me change the channel colours of e"), add one more choice: "show me where to click", which teaches the GUI. On that choice call show_me_where with EVERY route that does it (menu bar, right-click menu of the object at the right level: image or whole row, or the panel editor tab + buttons): all are outlined at once and cleared when it worked. Say what the yellow selection outline surrounds and what to click first. Open menus for the user (open_menus=true) only when they explicitly ask to be shown the menu; never click for them in that mode. '
        'End every answer that tells how to do something in the GUI with: "Should I **highlight where to click**, or **open it for me**?". Highlight = show_me_where with every route of that answer; open it for me = the same call with open_menus=true (menus opened down to the entry to click, or where=editor: the panel editor opened on its tab, buttons outlined). Never perform the edit itself. '
        'When no dedicated operation covers a GUI feature, discover native_gui: inspect actual native menu/dialog controls, invoke their exact IDs, complete or cancel the dialog, then verify jobs and document state. Queued is not success. Never substitute code for a normal manual how-to request. '
        'For rearranging EXISTING images into regular rows/columns, prefer arrange_live_images once. Derive columns from current image count when a row count is requested; when equal rows are impossible, ask which split the human wants, then pass it as row_counts (e.g. 9 images in 4 rows: row_counts=[3, 2, 2, 2]) in that ONE call. Reading order and letters are kept. Do not rebuild existing rows with per-image move loops. '
        'To construct NEW rows/columns, call add_group and use its returned path before adding images/plots. Requested row numbers are not existing group paths. On a missing-container error inspect/create the intended container; never fall back into an unrelated existing row. '
        'Discover relevant operations with find_pyfigures_tools; its results include exact '
        'argument schemas. Execute the selected operation with use_pyfigures_tool. '
        'For named live panels, prefer panel_ref on native image/annotation tools; omit numeric group_path/image_index so current GUI state resolves the address. get_annotations text_index is the index for style_annotation/set_annotation_text, while annotation_index is the full list index for ROI/removal tools. The live text wrappers accept text_index explicitly. '
        'Never guess argument names. Discover the exact schema before first use'
        + (', except the common operations listed in use_pyfigures_tool, which you may call through use_pyfigures_tool after checking their scope' if common else '')
        + '. select_live_objects(clear=true) and undo_redo are directly available and also searchable; do not repeatedly search after a no-match. '
        'Category descriptions are guidance, not restrictions: search by words across all '
        'categories if needed. All original functions remain available underneath. '
        'Figure targets default to live; explicit paths retain file-based behavior. Caption metadata uses set_figure_caption; preserve the supplied wording and punctuation and put requested italics in caption_markdown. '
        'For figure/group LETTER edits, removal or restoration prefer edit_panel_letters '
        'once at the intended scope, not per-image add/remove/style loops. That tool supports placement, family, size, bold/italic/underline, foreground and background; bold on SOME letters ("the letter of A", "the rotated panels") is edit_panel_letters scope=panels with panel_ids and bold=true (restyle_texts(target=letters) changes every letter). '
        'For ALL scale bars use remove_scale_bar_all or set_scale_bar_all once. '
        'For deleting last N rows use delete_last_rows in one call. Never guess shifted indices after an error; verify actual removed targets before claiming success. '
        'For ungroup all / images as single images / move all to free canvas use ungroup_all_images once; never consolidate into one group or loop over shifting indices. '
        'Single-panel scale-bar tools are for an explicitly limited panel, not figure-wide loops. A named panel, even a short or mistyped name, never authorizes set_scale_bar_all. Resolve the panel or ask; bulk only when all/every/whole figure was requested. '
        'inspect_panel_letters verifies text/color/background/placement after refresh. '
        'Explicit white stays white; background="none" means transparent, black does not. '
        'A "background" asked for a panel named by its letter ("add a black bg to g") is the PANEL background, the area '
        'behind the image that shows once it is rotated: set_image_property property_name="fill_color" (black "0", white '
        '"16777215", "None" removes it). Only words naming the letter or label ("black box behind the letter g") mean the '
        'letter background (edit_panel_letters background, with background_request quoting them). When the words fit both, '
        'ask which one before changing anything. '
        'The same holds for every short request that fits several things of the named panel: "the colour of a", "make g '
        'bigger", "delete g", "the text" can mean the panel letter, the image itself, a channel colour, a border, a scale '
        'bar or an annotation. When only one of them exists or fits, do it and say which; when several fit, ask which one '
        'in one short question and change nothing first. '
        'Recovery copies are automatic but differ from saving: report persistence state '
        'accurately. save_live_figure makes a saved copy inside the prototype. '
        'Session IDs/revisions are internal: do not supply remembered values. '
        'On GUI_OFFLINE stop and ask the user to reopen it; never repeat destructive loops. '
        'For edits pass only properties explicitly requested plus required target arguments. Readback records contain fields that setters may not accept: use the exact discovered arguments_schema, not the inspection shape. Omitted styling properties preserve accepted appearance. '
        'Is a font available? Use list_fonts(query=the_font), answer from font_check. '
        'Fake, dummy or placeholder images, or a layout before the images exist ("3 rows of 2 panels"): add_placeholder_grid in one call, never invented scripted images; the user fills the grey slots later (fill_template or drag and drop). '
        'figure_summary in the state answers "what is in the figure?". When it says empty=true, reply at once from its answer and how_to_add_content, without calling tools or previewing. '
        'PyFigures cannot reorder channels, but every channel colour can be set on its own, which gives the same picture. For "swap channels 3->1, 1->2, 2->3" say so, then offer: do it now (set_lut with the channel_colours of the panel permuted: what each channel shows now, its LUT or else the own colour of the file; [RED, GREEN, BLUE] swapped 1<->2 is luts=["GREEN", "RED", "BLUE"]), or how to do it yourself in the GUI (right-click the image > Appearance > Set LUT(s); double-click it > File Infos + Scale tab > Set LUTs; Annotations > Figure colours… for every image), with a chat example such as "make channel 1 blue, channel 2 red, channel 3 green". The channels property is only show/hide. '
        'Colours named without a target ("use magenta and green"): on a figure whose only coloured things are multichannel images they mean the CHANNEL colours (set_figure_colors, one per channel in channel order). If it also has coloured ROIs, arrows or text, or the colours could fit several things, ASK which ones the user means before changing anything. Which colour names work? list_colors(query=the_colour), answer from color_check. '
        '"Restore it as it was", "put it back", "revert / cancel that", "go back" just after your edit: use undo_redo(action="undo"), once per edit of that request, not a new edit that rebuilds the old values. If the user already undid your change with its undo button, do not undo again: that would remove an older step. '
        '"I want to edit / adjust X", "let me edit it", "so I can do it myself": the user edits by hand. Open the editor for them (open_annotation_editor on that panel) and change nothing. '
        'In replies, call a panel by its name in the panel state: its visible letter, else its canvas number "#3" (shown when the panel is selected). Never by a panel_id such as "1/1"; a letter it no longer has may only be added ("#5, formerly E"). '
        'Colours that look unnatural, weird, wrong, or "back to normal / the original / default colours", with no colour named: the FIRST option to offer (or to apply when the user asks to restore) is the image file\'s own colours, file_colours in the panel state: set_lut with "NONE" for each channel. Name those colours in the offer; other LUTs come after it. '
        'Which LUTs/colour tables exist, or is a LUT available? Use list_luts(query=the_name), answer from lut_check and pass its exact_key to set_lut. In set_lut, null keeps a channel unchanged. '
        'Column headers or a heading above/below a row: add_label_row(group_path=[row index], labels=[one per image] or one string). A label left/right of a row: add_side_label. add_annotation writes text INSIDE an image, not beside a row. '
        'Unknown-name suggestions require human confirmation; never substitute one silently. For completed edits report brief verified changes, not full state dumps unless asked. Do not ask the human to name tools. Inspect/preview to verify actual outcomes.'))

    @server.tool()
    def inspect_figure() -> dict:
        """Read the open figure, panel scene geometry, source sizes, current selection and last_canvas_click. Each panel_references entry also gives pixel_size (None = uncalibrated, pixels only), scale_bars (count), luts (channel colour tables), channel_colours (what each channel shows), file_colours (the file's own colours: what set_lut "NONE" restores), stack (None = a single image; else z, t and channel counts and what is shown: "which images are stacks?" is answered here, no other tool), kind ('image' pixels from a file, 'code' made by a script or plot, 'vector' SVG/PDF), name (what to call it in a reply: its letter, else "#N"), number (shown on the canvas on a selected panel: "#3" or "number 3" from the user is panel_ref "#3"), source_file and source_missing (its image file is gone: the panel shows an error placeholder; missing_source_files says how to fix it). Valid image_position is raw image pixels for clicked ROI/arrow placement; never use invalid or stale points."""
        state = send('inspect')
        summary = state.get('figure_summary') or {}
        if summary.get('empty'):          # nothing else in the state says anything useful
            return {'figure_summary': summary, 'path': state.get('path'), 'revision': state.get('revision')}
        return state

    @server.tool()
    def preview_figure():     # Image, or text for an empty figure ('Image | str' breaks FastMCP's schema)
        """Show the current GUI canvas; no session parameters required. An empty figure gives a short text instead."""
        from .live_mcp import call_live
        summary = send('inspect').get('figure_summary') or {}
        if summary.get('empty'):
            return summary['answer'] + ' ' + summary['how_to_add_content']
        result = call_live('preview')
        return Image(path=result['path'])

    @server.tool()
    def undo_redo(action: str = 'undo') -> dict:
        """Undo or redo one GUI document edit. action: undo or redo.

        "Restore it as it was", "put it back", "revert that", "cancel that", "go back" right
        after your edit: call undo once per edit you made for that request (one set_lut =
        one undo), instead of re-creating the old state with a new edit."""
        if action not in ('undo', 'redo'):
            raise ValueError('Use undo or redo')
        from .live_mcp import call_live
        return call_live(action)

    selection_tool = available.get('select_live_objects')

    @server.tool()
    def select_live_objects(panel_refs: list[str] | None = None,
                            group_paths: list[list[int]] | None = None,
                            row_numbers: list[int] | None = None, clear: bool = False) -> dict:
        """Select OR clear GUI objects. clear=true clears the selection and needs no panel_refs. A selection change, not a document edit. Use one selector: panel_refs (visible labels/IDs), group_paths, or 1-based row_numbers. Multiple targets are allowed. Returns verified selection."""
        if selection_tool is None:
            raise ValueError('This session has no live selection implementation; no selection changed.')
        return selection_tool.fn(panel_refs=panel_refs, group_paths=group_paths,
                                 row_numbers=row_numbers, clear=clear)

    # The tool is already advertised directly; also resolve wrapped calls and searches.
    available['undo_redo'] = server._tool_manager._tools['undo_redo']
    for direct in ('inspect_figure', 'preview_figure', 'select_live_objects'):
        available[direct] = server._tool_manager._tools[direct]

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def list_pyfigures_categories() -> dict:
        """List operation categories and counts without loading every tool schema."""
        return {key: {'description': value,
                      'operations': sum(category_for(n) == key for n in available)}
                for key, value in CATEGORIES.items()}

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_pyfigures_tools(query: str = '', category: str = '', limit: int = 6, offset: int = 0, compact: bool = False) -> dict:
        """Find operations and retrieve their exact arguments before executing. Search natural words (e.g. spacing, panel letter position, scale bar), optionally within a category. Default at most six schemas; use offset for more. No GUI edits. Leave compact unset: the client sets it when its context is filling."""
        if category and category not in CATEGORIES:
            raise ValueError('Unknown category. Use list_pyfigures_categories.')
        # a model asked for limit=20 and lost a step to the error: clamp instead
        limit = min(max(int(limit or 6), 1), 12)
        offset = max(int(offset or 0), 0)
        # operations named exactly ('move_image schema') come first, with no how-to guides:
        # a model searched move_image ~20 times and got scale-bar guides each time
        named = {n for n in available if re.search(r'(?<![a-z0-9_])' + re.escape(n.lower()) + r'(?![a-z0-9_])', query.lower())}
        words = re.findall(r'[a-z0-9]+', query.lower())
        aliases = {'gaps': 'spacing', 'gap': 'spacing', 'letters': 'letter',
                   'labels': 'label', 'rows': 'row', 'images': 'image', 'fonts': 'font',
                   'unrotate': 'rotation', 'rotate': 'rotation', 'rotated': 'rotation'}
        words = [aliases.get(w, w) for w in words]
        ranked = []
        for name, tool in available.items():
            cat = category_for(name)
            if category and cat != category:
                continue
            title = name.replace('_', ' ')
            help_text = tool.description.lower()
            score = sum(5 * (w in title) + (w in help_text) for w in words)
            if query.strip().lower()==name.lower() or name in named:score+=1000
            # Concrete output/metadata intent must outrank generic figure inspection.
            if name=='export_figure' and any(w in ('export','png','svg','pdf','tiff','jpeg') for w in words):score+=320
            if name in ('set_figure_caption','get_figure_caption') and 'caption' in words:
                score+=300 if name.startswith('set_') and not any(w in ('get','read','inspect') for w in words) else 200
            if name in ('inspect_annotation_objects','edit_annotation_properties','open_annotation_properties') and any(w in ('subscript','superscript','rich','substring','roi','properties') for w in words):score+=230
            if name in ('inspect_annotation_objects','edit_annotation_properties') and any(w in ('inset','insets') for w in words) and any(
                    w in ('larger','bigger','smaller','size','resize','enlarge','shrink','border') for w in words):
                score+=420        # "make the inset larger": size_fraction, not a second inset
            colour_words = {'magenta', 'green', 'red', 'blue', 'cyan', 'yellow', 'gray', 'grey', 'colours', 'colors'}
            if name == 'set_figure_colors' and colour_words & set(words) and not {
                    'roi', 'rois', 'arrow', 'arrows', 'outline', 'border', 'letter', 'letters', 'text',
                    'which', 'available', 'list', 'exist', 'names', 'options'} & set(words):
                score += 380      # "use magenta and green": the channel colours
            if name == 'list_colors' and any(w in ('colour', 'color', 'colours', 'colors') for w in words) and any(
                    w in ('list', 'which', 'available', 'exist', 'names', 'options', 'there', 'can') for w in words):
                score += 360
            lut_words=any(w in ('lut','luts','colormap','colormaps','colourmap','lookup','palette','palettes') for w in words)
            if name=='list_fonts' and not lut_words and any(w in ('font','typeface','helvetica','arial','available','installed') for w in words):score+=300
            if name=='list_luts' and lut_words and any(w in ('list','which','available','exist','exists','names','options','there') for w in words):score+=350
            bar_words=any(w in ('colorbar','colourbar','calibration') for w in words) or re.search(r'\bcolou?r (?:bar|scale)\b|\bintensity scale\b',' '.join(words)) \
                or (lut_words and any(w in ('right','beside','next','corresponding','legend') for w in words))
            if name=='add_lut_calibration_bar' and bar_words:score+=450   # "add the corresponding LUT on the right of b"
            if name=='invert_lut' and any(w in ('invert','inverted','inverse','negative','reverse','reversed') for w in words) and (lut_words or any(w in ('colours','colors','colour','color','gradient') for w in words)):score+=420
            if name=='preview_luts' and lut_words and any(w in ('preview','show','compare','look','see') for w in words):score+=400
            # "crop g to the nuclei": see the whole source with rulers first (a model cropped/uncropped blind until out of steps)
            # (not "zoom"/"region": those ask for an inset)
            if name=='preview_panel' and any(w in ('crop','cropping','cropped','uncropped','uncrop') for w in words):score+=430
            if name=='transform_image' and any(w in ('crop','cropping','rotate','rotation','flip') for w in words):score+=200
            if name=='restyle_texts' and any(w in ('bold','italic','underline') for w in words):score+=250
            # "brighter", "increase the contrast in d": the display range (four searches each, 2026-11-12)
            if name=='configure_image' and any(w in ('brightness','brighter','bright','contrast','darker','dim','dimmer','intensity','normalization','normalisation','saturated','window','gamma') for w in words):score+=420
            # "join these two boxes with a line", "connector between the ROIs" (sticky, 2026-11-12)
            if name=='add_connector' and any(w in ('connect','connector','connectors','join','link','linking','joining') for w in words) and any(w in ('box','boxes','roi','rois','shape','shapes','rectangle','rectangles','ellipse','label','circle','circles') for w in words) and 'inset' not in words:score+=650
            # "the pixel size of g is 0.5 um"
            if name in ('set_image_property','set_scale_bar') and 'pixel' in words and any(w in ('size','calibration','um','micron','microns') for w in words):score+=520 if name=='set_image_property' else 480
            # "put the scale bar bottom most", "the label above the bar": the order of items sharing
            # a corner (the bar was moved to the other corner instead, 2026-11-12)
            if name=='move_annotation_in_corner' and (any(w in ('most','bottommost','topmost','below','above','under','over','order','stacked','stack','closest','lowest','highest') for w in words) and any(w in ('bar','label','text','corner','inset','annotation','annotations','scale') for w in words)):score+=700
            # "letters outside", "rename g to G'", "numbers instead of letters"
            if name=='edit_panel_letters' and any(w in ('letter','lettering','numbering','numerals','numbers','rename') for w in words):score+=260
            side=any(w in ('left','right','side','vertical') for w in words)
            if name in ('add_label_row','add_side_label') and (any(w in ('column','columns','heading','header','headers','above','below','beside') for w in words) or (side and any(w in ('label','labels') for w in words))):
                score+=300 if (name=='add_side_label')==side else 150   # beside a row -> side label, else a label row

            picture_words=any(w in ('image','picture','pictures','photo','photos','micrograph','micrographs','blot','gel','scan','scans') for w in words)
            if name=='search_images' and picture_words and any(w in ('find','search','look','looking','where','which','similar','showing','shows','contain','containing','locate') for w in words):
                score+=420        # "find the image of the gut with DAPI": by content, not by figure keyword
            if name=='index_image_folder' and any(w in ('index','indexing','reindex','catalog','catalogue') for w in words) and (picture_words or 'folder' in words):
                score+=420
            if name=='review_submission_readiness' and any(w in ('ready','readiness','submission','publish','publication','compliance','resolution','dpi') for w in words):
                score+=400
            if name == 'inspect_native_gui' and any(w in ('gui','menu','dialog','button','control','native') for w in words):
                score += 350
            if name == 'open_native_menu' and any(w in ('context','drag','drop') for w in words) and 'menu' in words:
                score += 350
            if name == 'explain_live_interaction' and any(w in ('arrow', 'arrows', 'keyboard', 'shortcut', 'shortcuts', 'drag', 'drop', 'dnd', 'split', 'channel', 'channels') for w in words):
                score += 300
            link_words = any(w in ('connect', 'connecting', 'connected', 'connector', 'connectors', 'link', 'join',
                                   'leader', 'leaders', 'lines', 'line', 'funnel') for w in words)
            if name == 'connect_roi_to_inset' and link_words and any(w in ('roi', 'inset', 'box', 'zoom', 'callout', 'magnified') for w in words):
                score += 500      # "connect the ROI to the inset with 2 lines": computed ends (a model looped until out of steps)
            if name == 'roi_to_inset' and ('inset' in words or 'magnify' in words) and any(
                    w in ('roi', 'convert', 'rectangle', 'click', 'clicked', 'magnify', 'region') for w in words):
                score += 350
            if name == 'add_placeholder_grid' and any(w in ('fake', 'placeholder', 'placeholders', 'empty', 'dummy', 'mock', 'blank', 'grid') for w in words) and any(
                    w in ('image', 'images', 'panel', 'panels', 'rows', 'row', 'cols', 'columns', 'grid', 'layout', 'slots') for w in words):
                score += 450      # "3 rows per 2 cols with fake images": one call, not 25 steps
            if name == 'inspect_figure' and any(w in ('inspect', 'state', 'describe') for w in words):
                score += 250
            if name == 'select_live_objects' and any(w in ('select', 'selection', 'highlight') for w in words):
                score += 250
            if name == 'open_annotation_editor' and (('editor' in words) or (any(w in ('annotate', 'annotation', 'annotations') for w in words) and not any(w in ('remove', 'delete', 'get', 'inspect', 'list') for w in words))):
                score += 180
            if name in ('get_annotations', 'remove_annotation') and any(w in ('text', 'annotation', 'annotations', 'caption') for w in words):
                score += 220 if (name == 'remove_annotation' and any(w in ('remove', 'delete') for w in words)) or (name == 'get_annotations' and any(w in ('get', 'inspect', 'list') for w in words)) else 80
            if name == 'swap_rows' and any(w in ('swap', 'exchange', 'switch', 'reorder') for w in words) and any(w in ('row', 'group') for w in words):
                score += 250
            if name == 'reverse_selected_row' and any(w in ('reverse', 'invert') for w in words):
                score += 150
            if name == 'delete_last_rows' and any(w in ('delete', 'delte', 'remove', 'last') for w in words) and any(w in ('row', 'group', 'panel') for w in words):
                score += 150
            if name == 'ungroup_all_images' and (any(w in ('ungroup', 'ingroup', 'flatten', 'free', 'single') for w in words)):
                score += 100
            if any(w in ('how', 'help', 'learn', 'tutorial') for w in words) and name in ('explain_how', 'list_how_to_guides'):
                score += 100
            if 'scale' in words:
                if name in ('remove_scale_bar_all','set_scale_bar_all') and any(w in ('all','every','whole','entire') for w in words):score+=240
                if name=='set_scale_bar' and not any(w in ('all','every','whole','entire','remove','delete') for w in words):score+=120
            if 'rotation' in words and name in ('set_image_property', 'get_image_property', 'list_image_properties'):
                score += 80
            if name == 'swap_live_panels' and any(w in ('swap', 'exchange', 'switch') for w in words):
                score += 100
            if name == 'edit_panel_letters' and any(w in ('letter', 'lettering', 'font', 'background') for w in words):
                score += 50
            if name == 'arrange_live_images' and any(w in ('row', 'column', 'grid', 'arrange', 'rearrange') for w in words):
                score += 300
            if name == 'save_live_figure' and any(w in ('save', 'saving', 'persist') for w in words):
                score += 35
            if words and not score:
                continue
            ranked.append((score, name, tool, cat))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        import copy
        found = []
        # Compact results: full schemas for the best matches only, one line for the rest.
        # Six full schemas per search filled small models' context (2026-10-27), but always
        # compacting made Qwen 9B slower, so by default ('auto') only a client whose context
        # is filling asks for it. PYFIGURES_COMPACT_DISCOVERY=1 always compacts, =0 never.
        mode = os.environ.get('PYFIGURES_COMPACT_DISCOVERY', 'auto')
        compact = mode == '1' or (mode != '0' and bool(compact))
        for rank, (_, n, t, c) in enumerate(ranked[offset:offset + limit]):
            if compact and rank >= FULL_SCHEMAS and query.strip().lower() != n.lower() and n not in named:
                summary = re.split(r'(?<=[.!?])\s', t.description.strip(), maxsplit=1)[0][:160]
                found.append({'name': n, 'category': c, 'summary': summary,
                              'schema': 'not included: call find_pyfigures_tools(query="' + n + '") for it, or call the operation; a wrong argument returns its exact schema'})
                continue
            schema = copy.deepcopy(t.parameters)
            internal = {'session_id', 'expected_revision', 'request_id'}
            for key in internal:
                schema.get('properties', {}).pop(key, None)
            schema['required'] = [k for k in schema.get('required', []) if k not in internal]
            found.append({'name': n, 'callable_directly': n in server._tool_manager._tools, 'dispatcher': 'use_pyfigures_tool', 'category': c, 'description': t.description,
                          'arguments_schema': schema})
        manual_guides=None
        if query and not named:
            from .manual_help import explain
            candidate=explain(query)
            if candidate.get('status') in ('explained','source_reviewed'):
                manual_guides=candidate
            elif manual_guides is None and candidate.get('status')=='ambiguous' and candidate.get('candidates'):
                # "scale bar calibration pixel size" ties several guides: give their authored
                # steps rather than nothing, or the model answers with tool calls instead
                close=[explain(c) for c in candidate['candidates'][:3]]
                manual_guides={'status':'ambiguous','operation_executed':False,
                               'guides':[g for g in close if g.get('status')=='explained'],
                               'answer_style':'Pick the guide matching the question; human GUI steps, no tool commands.'}
        if manual_guides is None and not named and any(w in ('keyboard','shortcut','shortcuts','drag','drop','dnd','split','channel','channels') for w in words):
            from .manual_help import explain
            topic='split' if any(w in ('split','channel','channels') for w in words) else ('drag_and_drop' if any(w in ('drag','drop','dnd') for w in words) else 'shortcuts')
            manual_guides=explain(topic)
        # Never hand the model half a JSON schema when the engine bounds tool output.
        # Page whole operations; next_offset points to the first entry not returned.
        budget=20000-len(json.dumps(manual_guides,ensure_ascii=False))
        bounded=[]
        used=0
        for entry in found:
            size=len(json.dumps(entry,ensure_ascii=False))
            if bounded and used+size>budget:break
            bounded.append(entry);used+=size
        found=bounded
        return {'manual_guides':manual_guides,'guidance': topic_note(words) + ('Swap references identify IMAGE PANELS by default. Use target=images; target=letters only for explicit letter-text requests. Missing or non-unique references require clarification: stop, never substitute an existing panel or retry with other references. Never remove letters as a swap workaround.'
                             if any(w in ('swap', 'exchange', 'switch') for w in words) else
                             'Report verified after-state, not merely native success text. Ordinary text/captions are NOT automatic panel letters: inspect get_annotations and remove_annotation for quoted text, preserving letters. removal_request must quote the actual human request verbatim, never an invented clearer request.'),
                'total_matches': len(ranked), 'offset': offset,
                'next_offset': offset + len(found) if offset + len(found) < len(ranked) else None,
                'tools': found}

    @server.tool(structured_output=False)
    async def use_pyfigures_tool(tool_name: str, arguments: dict) -> object:
        """Execute a discovered original PyFigures operation or live convenience operation. Pass its exact name and arguments matching the schema from find_pyfigures_tools. Omit pyf_path for the open figure. Session/revision/request fields for prototype operations may be omitted: filled automatically. Errors are returned as MCP tool errors; images remain image content."""
        if tool_name not in available:
            raise ValueError('Unknown operation; search with find_pyfigures_tools')
        tool = available[tool_name]
        properties = tool.parameters.get('properties', {})
        # pyf_path='live' (or empty) names the open figure, which is all a live-only operation acts on;
        # refusing it made Muse retry remove_scale_bar_all unchanged 31 times.
        if 'pyf_path' not in properties and arguments.get('pyf_path', 'live') in ('live', '', None):
            arguments = {k: v for k, v in arguments.items() if k != 'pyf_path'}
        unknown = set(arguments) - set(properties)
        if unknown:
            hint = (' edit_panel_letters has no letters argument. To restore a missing panel letter use action=restore, start_letter=desired text, scoped panel_ids. Style alone cannot restore it. For exchanging two panels or letter texts, discover swap_live_panels and use target images by default, or letters only when explicitly requested.'
                    if tool_name == 'edit_panel_letters' and 'letters' in unknown else ' Discover this operation to read its exact arguments_schema.')
            if tool_name == 'edit_panel_letters':
                hint = (' Pass only the requested appearance fields. scope=all needs no panel_ids; scope=panels needs a nonempty panel_ids list.'
                        ' For italic/bold/underline use restyle_texts(target=letters) directly; opacity is not accepted here.'
                        ' Do not copy the full letter_styles readback or retry unchanged unsupported fields.')
            raise ValueError('Unknown argument(s): ' + ', '.join(sorted(unknown)) + '.' + hint
                             + ' Exact arguments_schema: ' + json.dumps(tool.parameters))
        kwargs = dict(arguments)
        if 'session_id' in properties:
            state = send('inspect')
            for key, value in [('session_id', state['session_id']),
                               ('expected_revision', state['revision']),
                               ('request_id', str(uuid.uuid4()))]:
                if key in properties:
                    kwargs[key] = value
        return await tool.run(kwargs)

    # Small real-schema reminders in the advertised dispatcher prevent copying
    # inspection-state objects into edit arguments without expanding the tool list.
    contracts=[]
    for name in (COMMON_CONTRACTS if common else ('edit_panel_letters','swap_live_panels','remove_annotation')):
        tool=available.get(name)
        if tool:
            schema=tool.parameters
            keys=[k for k in schema.get('properties',{}) if k not in ('session_id','expected_revision','request_id','pyf_path')]
            choices={k:v['enum'] for k,v in schema.get('properties',{}).items() if 'enum' in v}
            scope=(' ('+CONTRACT_SCOPE[name]+')') if common and name in CONTRACT_SCOPE else ''
            contracts.append(name+scope+': fields='+','.join(keys)+(('; choices='+json.dumps(choices)) if choices else '')+'; required='+','.join(k for k in schema.get('required',[]) if k in keys))
    dispatcher=server._tool_manager._tools['use_pyfigures_tool']
    dispatcher.description+=(' Common operations; call them through use_pyfigures_tool, checking the scope in brackets first (exact fields): ' if common else ' Common exact contracts: ')+' | '.join(contracts)+'. Pass only requested flat edit fields. Never copy inspection letters/style objects into arguments. For other operations discover the schema first.'

    return server
