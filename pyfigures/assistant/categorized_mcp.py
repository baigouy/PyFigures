"""Small, stable MCP surface backed by the complete original registry."""
import json
import re
import uuid
from mcp.server.fastmcp import FastMCP, Image
from mcp.types import ToolAnnotations

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
    if name in ('inspect_annotation_objects','edit_annotation_properties','open_annotation_properties'):return 'annotations'
    if name=='restyle_texts':return 'lettering'
    if name=='review_submission_readiness':return 'quality'
    if name in ('inspect_native_gui','use_native_gui','open_native_menu') or name.startswith('native_gui_'):
        return 'native_gui'
    if name == 'explain_live_interaction':
        return 'help'
    if name == 'inspect_figure':
        return 'inspect'
    if name in ('open_annotation_editor', 'roi_to_inset'):
        return 'annotations'
    if name in ('list_how_to_guides', 'explain_how', 'show_me_how', 'guidance_status', 'close_guidance'):
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


def build_server(full_server, send):
    from .original_registry import registry
    originals = set(registry())
    names = originals | {'arrange_live_images', 'set_panel_letter_position', 'edit_live_label',
        'edit_panel_letters', 'inspect_panel_letters', 'swap_live_panels', 'swap_rows', 'select_live_objects', 'open_annotation_editor', 'roi_to_inset', 'explain_live_interaction', 'save_live_figure',
        'list_recovery_snapshots', 'restore_recovery_snapshot', 'remove_scale_bar_all', 'ungroup_all_images', 'delete_last_rows', 'reverse_selected_row'}
    names.update({'open_annotation_properties','inspect_annotation_objects','edit_annotation_properties','review_submission_readiness','inspect_native_gui','use_native_gui','open_native_menu','native_gui_keys','native_gui_gesture','native_gui_drop_files'})
    available = {n: t for n, t in full_server._tool_manager._tools.items() if n in names}
    server = FastMCP('PyFigures categorized live prototype', instructions=(
        'Edit scientific figures in the open PyFigures GUI. Start with a small tool surface. '
        'Only the six advertised top-level functions are callable. Names returned by find_pyfigures_tools are inner operations, NOT callable functions. Invoke them through use_pyfigures_tool(tool_name=the_discovered_name, arguments=the_exact_arguments). This applies equally to read-only explain_live_interaction and other guide operations. '
        'inspect_figure.selection contains the live user-selected panels, groups and containing row paths. Use it for this/selected row or image; do not ask users to repeat an unambiguous selection. Reverse/invert the selected row with reverse_selected_row. Reject missing or multi-row selection, never guess. '
        'For manual drag cancellation: release the mouse, then choose Ignore or dismiss the opened context menu. Escape is verified for the open menu, not during the active drag; do not invent clicking empty canvas as cancellation. '
        'For manual questions use explain_live_interaction with the actual topic or explain_how; follow returned current menu paths. Manual teaching never authorizes editing. API examples inside tool descriptions are developer references, not user-facing instructions: omit them unless code or recipe is explicitly requested. Panel-by-panel joining is ONE drop/operation with ordered contents. '
        'HOW-TO requests mean human GUI instructions by default: discover explain_how or list_how_to_guides, give authored menu/right-click paths, and offer to do the edit from natural language. Show commands only if the user explicitly asks for code or recipe; teaching is not permission to edit. '
        'An invalid quantity or unsupported value requires clarification. For row deletion, a count larger than available means delete all available rows and report the ACTUAL number removed, using the bulk operation once. Do not turn zero columns into one, change a negative size to a positive size, or choose a substitute LUT/corner after validation fails. Explain the valid range and ask the user for a corrected value. '
        'A missing or ambiguous named panel is unresolved user intent, not an instruction to choose another panel. After UNKNOWN_PANEL_REFERENCE or AMBIGUOUS_PANEL_REFERENCE, ask for the corrected target and stop that edit. Never replace a failed letter with guessed numeric coordinates, an ordinal, or the last panel; inspection cannot establish which replacement the user intended. '
        'SWAPS: swap q and o means swap image PANELS identified by those letters. Default target=images. '
        'Exchange letter text only when explicitly requested; do not ask images-versus-letters for normal swaps. '
        'If both swap references identify the same panel (including a letter and its equivalent panel ID), report no change. Repeating a reference is not evidence of duplicate panel letters; use actual duplicate_letter_references from state before claiming ambiguity. '
        'Use swap_live_panels; never delete/recreate letters to swap or relabel. '
        'Removal is only for an explicit user request to remove letters; removal_request must quote it. '
        'Readiness requires review_submission_readiness: actual resolution AND journal checks. audit_figure is inventory, not readiness. Report measured blockers and incomplete evidence; never infer readiness from labels or export DPI. '
        'For multi-clause requests, satisfy and verify every clause before saying done. A named target in edit arguments does not select it in the GUI: explicit select-plus-edit requests need select_live_objects as well as the edit. Preserve the selection and check the final outline/state. '
        'A successful tool call is not task success. Report verified after-state; if counts show zero letters, '
        'say letters are absent, never claim a lettering swap succeeded. '
        'When the human supplies annotation content, such as write a text note on a named panel, create the ordinary annotation with add_annotation. Merely opening an editor does not fulfill a request to write the supplied content. Offer/open the editor for unspecified content or an explicit editor request. '
        'When no dedicated operation covers a GUI feature, discover native_gui: inspect actual native menu/dialog controls, invoke their exact IDs, complete or cancel the dialog, then verify jobs and document state. Queued is not success. Never substitute code for a normal manual how-to request. '
        'For rearranging EXISTING images into regular rows/columns, prefer arrange_live_images once. Derive columns from current image count when a row count is requested; ask if equal rows are impossible. Do not rebuild existing rows with per-image move loops. '
        'To construct NEW rows/columns, call add_group and use its returned path before adding images/plots. Requested row numbers are not existing group paths. On a missing-container error inspect/create the intended container; never fall back into an unrelated existing row. '
        'Discover relevant operations with find_pyfigures_tools; its results include exact '
        'argument schemas. Execute the selected operation with use_pyfigures_tool. '
        'Never guess argument names. Discover the exact schema before first use. undo_redo is directly available and also searchable; do not repeatedly search after a no-match. '
        'Category descriptions are guidance, not restrictions: search by words across all '
        'categories if needed. All original functions remain available underneath. '
        'Figure targets default to live; explicit paths retain file-based behavior. Caption metadata uses set_figure_caption; preserve the supplied wording and punctuation and put requested italics in caption_markdown. '
        'For figure/group LETTER edits, removal or restoration prefer edit_panel_letters '
        'once at the intended scope, not per-image add/remove/style loops. That tool supports placement, family, size, foreground and background; bold/italic/underline are handled by restyle_texts(target=letters), not guessed edit_panel_letters fields. '
        'For ALL scale bars use remove_scale_bar_all or set_scale_bar_all once. '
        'For deleting last N rows use delete_last_rows in one call. Never guess shifted indices after an error; verify actual removed targets before claiming success. '
        'For ungroup all / images as single images / move all to free canvas use ungroup_all_images once; never consolidate into one group or loop over shifting indices. '
        'Single-panel scale-bar tools are for an explicitly limited panel, not figure-wide loops. A named panel, even a short or mistyped name, never authorizes set_scale_bar_all. Resolve the panel or ask; bulk only when all/every/whole figure was requested. '
        'inspect_panel_letters verifies text/color/background/placement after refresh. '
        'Explicit white stays white; background="none" means transparent, black does not. '
        'Recovery copies are automatic but differ from saving: report persistence state '
        'accurately. save_live_figure makes a saved copy inside the prototype. '
        'Session IDs/revisions are internal: do not supply remembered values. '
        'On GUI_OFFLINE stop and ask the user to reopen it; never repeat destructive loops. '
        'For edits pass only properties explicitly requested plus required target arguments. Readback records contain fields that setters may not accept: use the exact discovered arguments_schema, not the inspection shape. Omitted styling properties preserve accepted appearance. '
        'Do not ask the human to name tools. Inspect/preview to verify actual outcomes.'))

    @server.tool()
    def inspect_figure() -> dict:
        """Read the open figure, panel scene geometry, source sizes, current selection and last_canvas_click. Valid image_position is raw image pixels for clicked ROI/arrow placement; never use invalid or stale points."""
        return send('inspect')

    @server.tool()
    def preview_figure() -> Image:
        """Show the current GUI canvas; no session parameters required."""
        from .live_mcp import call_live
        result = call_live('preview')
        return Image(path=result['path'])

    @server.tool()
    def undo_redo(action: str = 'undo') -> dict:
        """Undo or redo one GUI document edit. action: undo or redo."""
        if action not in ('undo', 'redo'):
            raise ValueError('Use undo or redo')
        from .live_mcp import call_live
        return call_live(action)

    # The tool is already advertised directly; also resolve wrapped calls and searches.
    available['undo_redo'] = server._tool_manager._tools['undo_redo']
    for direct in ('inspect_figure', 'preview_figure'):
        available[direct] = server._tool_manager._tools[direct]

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def list_pyfigures_categories() -> dict:
        """List operation categories and counts without loading every tool schema."""
        return {key: {'description': value,
                      'operations': sum(category_for(n) == key for n in available)}
                for key, value in CATEGORIES.items()}

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_pyfigures_tools(query: str = '', category: str = '', limit: int = 6, offset: int = 0) -> dict:
        """Find operations and retrieve their exact arguments before executing. Search natural words (e.g. spacing, panel letter position, scale bar), optionally within a category. Default at most six schemas; use offset for more. No GUI edits."""
        if category and category not in CATEGORIES:
            raise ValueError('Unknown category. Use list_pyfigures_categories.')
        if not 1 <= limit <= 12 or offset < 0:
            raise ValueError('limit must be 1Ã¢â‚¬â€œ12 and offset nonnegative')
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
            if query.strip().lower()==name.lower():score+=1000
            # Concrete output/metadata intent must outrank generic figure inspection.
            if name=='export_figure' and any(w in ('export','png','svg','pdf','tiff','jpeg') for w in words):score+=320
            if name in ('set_figure_caption','get_figure_caption') and 'caption' in words:
                score+=300 if name.startswith('set_') and not any(w in ('get','read','inspect') for w in words) else 200
            if name in ('inspect_annotation_objects','edit_annotation_properties','open_annotation_properties') and any(w in ('subscript','superscript','rich','substring','roi','properties') for w in words):score+=230
            if name=='restyle_texts' and any(w in ('bold','italic','underline') for w in words):score+=250

            if name=='review_submission_readiness' and any(w in ('ready','readiness','submission','publish','publication','compliance','resolution','dpi') for w in words):
                score+=400
            if name == 'inspect_native_gui' and any(w in ('gui','menu','dialog','button','control','native') for w in words):
                score += 350
            if name == 'open_native_menu' and any(w in ('context','drag','drop') for w in words) and 'menu' in words:
                score += 350
            if name == 'explain_live_interaction' and any(w in ('arrow', 'arrows', 'keyboard', 'shortcut', 'shortcuts', 'drag', 'drop', 'dnd', 'split', 'channel', 'channels') for w in words):
                score += 300
            if name == 'roi_to_inset' and 'inset' in words and any(w in ('roi', 'convert', 'rectangle') for w in words):
                score += 350
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
        for _, n, t, c in ranked[offset:offset + limit]:
            schema = copy.deepcopy(t.parameters)
            internal = {'session_id', 'expected_revision', 'request_id'}
            for key in internal:
                schema.get('properties', {}).pop(key, None)
            schema['required'] = [k for k in schema.get('required', []) if k not in internal]
            found.append({'name': n, 'callable_directly': False, 'dispatcher': 'use_pyfigures_tool', 'category': c, 'description': t.description,
                          'arguments_schema': schema})
        manual_guides=None
        if manual_guides is None and query:
            from .manual_help import explain
            candidate=explain(query)
            if candidate.get('status') in ('explained','source_reviewed'):
                manual_guides=candidate
        if manual_guides is None and any(w in ('keyboard','shortcut','shortcuts','drag','drop','dnd','split','channel','channels') for w in words):
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
        return {'manual_guides':manual_guides,'guidance': ('Swap references identify IMAGE PANELS by default. Use target=images; target=letters only for explicit letter-text requests. Clarification is needed only for missing or non-unique references. Never remove letters as a swap workaround.'
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
        unknown = set(arguments) - set(properties)
        if unknown:
            hint = (' edit_panel_letters has no letters argument. To restore a missing panel letter use action=restore, start_letter=desired text, scoped panel_ids. Style alone cannot restore it. For exchanging two panels or letter texts, discover swap_live_panels and use target images by default, or letters only when explicitly requested.'
                    if tool_name == 'edit_panel_letters' and 'letters' in unknown else ' Discover this operation to read its exact arguments_schema.')
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
    for name in ('edit_panel_letters','swap_live_panels','remove_annotation'):
        tool=available.get(name)
        if tool:
            schema=tool.parameters
            keys=[k for k in schema.get('properties',{}) if k not in ('session_id','expected_revision','request_id','pyf_path')]
            choices={k:v['enum'] for k,v in schema.get('properties',{}).items() if 'enum' in v}
            contracts.append(name+': fields='+','.join(keys)+'; choices='+json.dumps(choices)+'; required='+','.join(k for k in schema.get('required',[]) if k in keys))
    dispatcher=server._tool_manager._tools['use_pyfigures_tool']
    dispatcher.description+=' Common exact contracts: '+' | '.join(contracts)+'. Pass only requested flat edit fields. Never copy inspection letters/style objects into arguments. For other operations discover the schema first.'

    return server
