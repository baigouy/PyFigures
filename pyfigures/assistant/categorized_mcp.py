"""Small, stable MCP surface backed by the complete original registry."""
import inspect
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
    'layout': 'Arrange rows, group, move, resize, change horizontal or vertical spacing, empty placeholder panels.',
    'lettering': 'Automatic panel-letter positions, fonts, text labels, captions and alt text.',
    'images': 'Image files, crop, rotation, channels, LUTs, normalization and stack views.',
    'annotations': 'Scale bars, arrows, ROIs, connectors, equations, significance brackets and insets.',
    'scale_bars': 'Scale bars only: inspect one, add/update one or all, remove one or ALL in one operation. Use bulk operations for whole-figure requests.',
    'plots': 'Data plots with statistics (bar, box, violin, split violin, paired, line, grouped, scatter; facets), seaborn plots, table panels; reading tables (columns, factors, group summaries) and the code of a plot.',
    'create_export': 'Create figures, recipes, render, export and compare files.',
    'quality': 'Scientific checks, journals, resolution, image integrity and provenance.',
    'posters': 'Poster and album documents, pages, layout, preview and export.',
    'setup': 'Server information, installation, guides, bug recordings and history.'}


def category_for(name):
    if any(k in name for k in ('data_plot', 'seaborn', 'table_panel', 'describe_table', 'factor_columns',
                               'summarize_table', 'plot_panel_code')):
        return 'plots'
    # 2026-11-19: these fell into 'setup' (server info) where no model looks for them
    if name in ('remove_rois', 'move_annotations', 'move_annotation_in_corner', 'add_connector',
                'add_equation', 'add_latex_code', 'update_latex_panels'):
        return 'annotations'
    if name in ('inspect_ome_zarr', 'match_display_range', 'list_colors', 'set_figure_colors',
                'detect_objects', 'preview_panel_source'):
        return 'images'
    if name in ('add_placeholder_grid', 'remove_empty_placeholders'):
        return 'layout'
    if name in ('simulate_color_blindness', 'list_review_comments', 'import_review_comments'):
        return 'quality'
    if name in ('templatify_figure', 'write_xml'):
        return 'create_export'
    if name in ('index_image_folder', 'search_images', 'add_folder_files'):return 'images'
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


_PLOT_OPTIONS = 'edit_data_plot(panel_ref, kind="violin"|"box"|"bar"|"scatter"|"grouped"|"split_violin" (two conditions, e.g. sex, as the two halves of each violin; a two-factor table)|"paired" (before / after on the same subjects: a line per subject, paired tests)|"line" (a time course: mean ± error per group across days / doses, columns=[group, x, value]), error, only_significant, annotate_stats, stats_mode, ylabel, aspect=width/height only when asked: "wider" = 1.5-2, "taller" = 0.6-0.8; a plot can take any shape, unlike an image; text size: font_pt = the plot\'s text in the printed figure (default the labels\' size, else 7 pt; "bigger text" 8-9, "like the letters" their pt; "labels" = the labels\' size again); font_family="Verdana" ("labels" = the labels\' font, the default); ONE part only ("bigger title", "smaller tick labels"): text_pt={"title": 9} / text_font={"ticks": "Arial"}, parts title|axis_labels|ticks|legend, null = as the whole plot; size: width/height in inches; layout: order=[group names], ylim=[low, high] ([0, null] = y from 0; on a plot "the scale", "the scale bar", "the range", "start at 0 and go to 50" mean its y axis: ylim=[0, 50]; a plot has no scale bar; the plot just discussed is the one meant), log_y, xtick_rotation=45 for overlapping names (degrees ANTICLOCKWISE, unlike image rotation: "rotate left" = +45, names rising "/"; "rotate right" = -45), rename={"mutA": "mutant A"} for a group\'s shown name (never ask the user to edit the table), show_points=False ("remove the point cloud"), point_style="swarm" (points side by side, a beeswarm) | "line" | "jitter", violin_inner="box" ("a box plot within the violin") | "lines" | "none", violin_side="left" ("half violins", points on the other side) | "right" | "both" ("what can I put in / change on my plot?": list_data_plot_kinds lists every option per kind), legend="inside"|"outside"|"none", element_colors={"points": "black", "median": "red", "edges": "none", "brackets": "grey"} (colour of PARTS of the plot; the groups\' own colours = colors=[...]), columns=[x, (split,) value] of a tidy table, where="day == 14" (only some rows), control="WT" ("compare everything to WT": Dunnett\'s test), normalize="WT" ("as % of control"), pairs=[["WT", "mutA"]] ("only show WT vs mutA"; [] = every significant pair), stats_text=True (grouped / split / line: the two-way ANOVA written under the axes; off by default, stars only; "remove the stats text at the bottom" = stats_text=False, NOT annotate_stats=False which removes the stars too), show_n=True ("add the n"), p_format="p" ("p values instead of stars"), show_mean=True, hlines=[1.0] (a dashed reference line; [{"y": 100, "label": "control"}]), facet="day" (one plot per day, each tested; facet_row="sex" a grid; "split plots" / "facets"), skip_rows=3 (lines above the table; found automatically otherwise); 0 / "" / [] resets one; seaborn plots: edit_seaborn_plot height/aspect, title, palette={"female": "red", "male": "blue"} (a colour per group), legend="outside"|"top"|"inside"|"none", xlim/ylim=[low, high], col/row facets, rename={"weight_g": "weight (g)"} for column or value names, where, options={"cumulative": true, "element": "step", "fill": false} = cumulative histogram (function="histplot"; or "ecdfplot")) for a DATA PLOT; add_table_panel(group_path, csv_path, by=["genotype"], value="area", stats=["n", "mean±sd"]) = a TABLE as a figure panel (raw rows, or a summary per group; edit_table_panel changes it), describe_table(csv_path, sheet) = a table\'s columns, types, levels, first rows and the plots that fit (use it before add_seaborn_plot / add_data_plot when the columns are not known; never search for it), list_factor_columns(csv_path, sheet) = the columns that can split / colour / facet the data, with their levels, summarize_table(csv_path, value, by, where) = n / mean / sd / median per group (a DATA PLOT is a panel whose panel_references "code" says type data_plot; its statistics and p-values are there too; list_data_plot_kinds lists the kinds; never set_script on a data plot).'


# The rules of one topic, said by find_pyfigures_tools when the search words fit it
# (they were all in the server instructions, 18 kB on every turn: user 2026-11-19,
# "first messages small and explicit, then upon request the details").
TOPIC_RULES = (
    ({'swap', 'swaps', 'exchange', 'switch', 'interchange'},
     'SWAPS: "swap q and o" swaps the image PANELS with those letters (swap_live_panels, target=images); letter '
     'TEXT swaps only on an explicit swap-the-letters request. A missing or non-unique reference: STOP and ask; '
     'never substitute a panel or retry with other references. Both references the same panel: report no change. '
     'Repeating a reference is not evidence of duplicate letters (use duplicate_letter_references from the state). '
     'Never delete / recreate letters to swap or relabel.'),
    ({'letter', 'letters', 'lettering', 'label', 'labels', 'abc', 'font', 'fonts', 'consistent', 'same'},
     'LETTERS: edit_panel_letters once at the intended scope (placement, family, size, bold / italic / underline, '
     'colour, background), never per-image loops. Letters stay alike: a style asked for one letter ("I can\'t see '
     'the letter b") goes to every letter; only when the user explicitly wants some different ("only b bold") use '
     'scope=panels with panel_ids and only_these_letters_request quoting them. Removal only on an explicit request '
     '(removal_request quotes it). inspect_panel_letters verifies after the edit; zero letters = say they are '
     'absent. Explicit white stays white; background="none" is transparent. A "bg" asked for a panel named by its letter ("add a black bg to g") is the PANEL background (set_image_property fill_color), not the letter background, unless the words name the letter. "Consistent / the same letters": the '
     'same font, size, bold, italic, underline and box for all; if one was made different on purpose, ask whether '
     'to spread it or undo it. All texts stay coherent: scale-bar labels alike (restyle_texts target="scale_bars"), '
     'every text but the letters in one font; check_text_consistency checks it. Is a font available? '
     'list_fonts(query=the_font), answer from font_check.'),
    ({'background', 'backgrounds', 'bg', 'fill', 'behind', 'box'},
     'BACKGROUND: asked for a panel named by its letter ("add a black bg to g") it is the PANEL background, '
     'behind the image, seen once it is rotated: set_image_property property_name="fill_color" (black "0", white '
     '"16777215", "None" removes it; "auto" = the colour of the image\'s own background, read from its edge pixels (a plot\'s too, as drawn; a '
     'plot\'s element_colors background is inside the plot, not behind its rotated corners); '
     'all panels = one call with batch). Only words naming the letter or label ("black box behind the letter g") '
     'mean the letter background (edit_panel_letters background, background_request quoting them). When the words '
     'fit both, ask which one before changing anything. There is no pixel-sampling tool.'),
    ({'ready', 'readiness', 'submission', 'submit', 'journal', 'publication', 'publish'},
     'READINESS: review_submission_readiness (actual resolution AND journal checks); audit_figure is an '
     'inventory, not readiness. Report measured blockers and missing evidence; never infer readiness from labels '
     'or export DPI.'),
    ({'how', 'help', 'where', 'show', 'teach', 'menu', 'menus', 'click', 'manual', 'tutorial', 'guide'},
     'HOW-TO: human GUI steps by default: explain_how or list_how_to_guides (or explain_live_interaction), their '
     'authored menu / right-click paths; code or recipe only when asked; teaching is not permission to edit. '
     'Whenever you list choices for a change (always for a HELP request such as "help me change the channel '
     'colours of e"), add "show me where to click". End every answer that tells how to do something in the GUI '
     'with: "Should I **highlight where to click**, or **open it for me**?". Highlight = show_me_where with EVERY '
     'route (menu bar, right-click menu of the object at the right level, panel editor tab + buttons), outlined '
     'at once; say what the yellow selection outline surrounds and what to click first. Open it for me = the same call with '
     'open_menus=true (only when asked); never perform the edit itself. A feature with no operation: native_gui '
     '(inspect the real menu / dialog controls, invoke their ids, verify; queued is not success). Cancelling a '
     'drag: release the mouse, then Ignore or dismiss the menu. Panel-by-panel joining is ONE drop with ordered '
     'contents.'),
    ({'row', 'rows', 'column', 'columns', 'arrange', 'grid', 'rearrange', 'group', 'groups', 'ungroup', 'reverse',
      'invert', 'heading', 'headers', 'header', 'layout'},
     'ROWS: rearranging EXISTING images into rows / columns: arrange_live_images once (columns, or row_counts '
     'when equal rows are impossible: ask which split, e.g. 9 images in 4 rows = [3, 2, 2, 2]); order and letters '
     'kept; never per-image move loops. NEW rows: add_group, then use its returned path; requested row numbers are '
     'not group paths; on a missing-container error inspect / create it, never fall back into another row. '
     'Reverse the selected row: reverse_selected_row (missing or several rows selected: ask). Delete the last N '
     'rows: delete_last_rows once (more than exist = all, report the actual number). Ungroup all / every image '
     'loose: ungroup_all_images once. Never guess shifted indices after an error. Column headers or a heading '
     'above / below a row: add_label_row(group_path=[row], labels=[one per image] or one string); beside a row: '
     'add_side_label; add_annotation writes INSIDE an image. Zero columns or a negative size: ask.'),
    ({'scale', 'scalebar', 'scalebars', 'bar', 'bars'},
     'SCALE BARS: all of them = set_scale_bar_all / remove_scale_bar_all once ("add scale bars to all" with no '
     'length = no bar_width_in_units: each image gets a round one). Single-panel tools only for named panels; a '
     'named panel, even mistyped, never authorizes the _all tools: resolve it or ask.'),
    ({'channel', 'channels', 'colour', 'colours', 'color', 'colors', 'lut', 'luts', 'magenta', 'green', 'red',
      'blue', 'cyan', 'yellow', 'unnatural', 'weird', 'original', 'normal', 'default'},
     'COLOURS: channels cannot be reordered, but each channel colour can be set (set_lut; null keeps a channel): '
     'for "swap channels 3->1, 1->2" permute the panel\'s channel_colours ([RED, GREEN, BLUE] with 1<->2 = '
     'luts=["GREEN", "RED", "BLUE"]) or show the GUI way (right-click > Appearance > Set LUT(s); Annotations > '
     'Figure colours…). The channels property is only show / hide. Colours named without a target ("use magenta '
     'and green") on a figure whose only coloured things are multichannel images = the CHANNEL colours '
     '(set_figure_colors, one per channel); if ROIs, arrows or text are coloured too, ask which. Unnatural colours '
     'or "back to the original / default colours": first offer (or apply on "restore") the file\'s own colours, '
     'file_colours in the panel state: set_lut with "NONE" for each channel; name them; other LUTs after. LUT '
     'names: list_luts(query) (pass its exact_key); colour names: list_colors(query).'),
    ({'roi', 'rois', 'cell', 'cells', 'nucleus', 'nuclei', 'detect', 'count', 'objects', 'embryos', 'boxes',
      'ellipses', 'squares', 'arrow', 'arrows', 'move', 'inset', 'insets', 'zoom'},
     'ROIs: over every cell / nucleus ("how many cells"): detect_objects(panel_ref) in one call (dry_run=true '
     'counts; region=[x0, y0, x1, y1] from preview_panel\'s rulers for one part, never crop to aim; nuclei in '
     'stained cells: the nuclei channel, number from 1 or its colour); then preview_panel to check, and say it is '
     'an automatic threshold the user can fix in the editor. Remove several: remove_rois(panel_ref) once '
     '(shapes=[...], annotation_indexes=[...], or max_size for the tiny ones), never one remove_annotation each. '
     'Move: move_annotations(panel_ref, dx, dy, annotation_indexes) (dy negative = up). An INSET sits in a corner '
     'of its panel and cannot be moved freely: offer another corner (set_inset_property placement) or moving its '
     'ROI (state: insets with roi_annotation_index and shows_region). Coordinates come from preview_panel(panel_ref) '
     'rulers (the panel\'s own pixels; never preview_figure). get_annotations text_index is for style_annotation / '
     'set_annotation_text; annotation_index is the full list index for ROI / removal tools. Arrows / arrowheads '
     'AT a feature: add_arrow(panel_ref, tip_x, tip_y, from_direction, style="arrowhead" for the head alone), the '
     'tip read once off preview_panel(panel_ref) rulers; several = one call with batch.'),
    ({'duplicate', 'duplicated', 'duplicates', 'identical', 'reused', 'reuse', 'integrity', 'inverted', 'flipped',
      'investigate', 'compare', 'similar', 'copy', 'copies'},
     'INTEGRITY: "are n and o the same image?", "investigate n and o", duplicated / reused / flipped / inverted '
     'panels: check_image_integrity once (whole figure: exact file reuse, cross-panel duplicates including '
     'flipped, rotated and contrast-INVERTED ones, clones inside a panel) and report its findings by panel letter; '
     'previews alone miss an inverted copy. Say a match is a red flag to check, not proof of misconduct.'),
    ({'illustrate', 'illustration', 'diagram', 'schematic', 'scheme', 'sketch', 'cartoon', 'drawing'},
     'DRAWINGS: a schematic / diagram / cartoon (bars for chromosomes, arrows between boxes, a model): '
     'add_scripted_image(group_path, script) = ONE new panel drawn by matplotlib code you write (patches, lines, '
     'text); set_script redraws it. Never build it from ROIs on an image or from placeholders. Say what you drew.'),
    ({'text', 'note', 'write', 'annotation', 'annotations', 'edit', 'editor', 'myself', 'manually', 'adjust'},
     'TEXT / EDITOR: text the user supplies ("write ... on b"): add_annotation; opening an editor does not do it. '
     '"I want to edit / adjust X", "let me edit the b crop", "so I can do it myself": '
     'open_annotation_editor(panel_ref, tab="crop" for a crop or rotation, "scale" for the scale bar or channel '
     'colours, "text" for texts, else "annotations") and change nothing: the panel the user names, never the '
     'selected one instead.'),
    ({'procedure', 'procedures', 'macro', 'repeat', 'replay'},
     'PROCEDURES: "save what we did as a procedure / macro": save_chat_procedure(procedure_path=document.folder + '
     '"/" + document.name + "_procedure.json") once (it runs with Tools > Run a procedure… or by dropping the file '
     'on a figure); "run my procedure on this figure": run_procedure_here(procedure_path).'),
    ({'save', 'export', 'pdf', 'png', 'tif', 'tiff', 'svg', 'pptx', 'name', 'file'},
     'FILES: the open figure\'s file is document in the state ("export it with the same name as the pyf" = '
     'document.folder + document.name + the extension). Recovery copies are automatic but are not saving: say '
     'which.'),
    ({'fake', 'dummy', 'placeholder', 'placeholders', 'empty', 'slots', 'template'},
     'PLACEHOLDERS: fake / dummy images or a layout before the images exist ("3 rows of 2 panels"): '
     'add_placeholder_grid once, never invented scripted images; the user fills the slots later.'),
    ({'caption', 'legend', 'italic', 'italics'},
     'CAPTION: set_figure_caption keeps the supplied wording and punctuation; italics go in caption_markdown.'),
    ({'select', 'selected', 'selection', 'highlight'},
     'SELECTION: an edit does not select its target in the GUI: select-plus-edit requests need '
     'select_live_objects too; check the final outline.'),
    ({'files', 'folder', 'folders', 'directory'},
     'FOLDERS: "the (first N) files of a folder" are all its files, tables too: add_folder_files(folder, '
     'first=N) once, never add_image batches (it adds tables as data plots, in the folder\'s order); '
     '"images" of a folder = add_image. Say once that a table panel is possible.'),
)


# the operations each topic governs: their rules come with a search that finds them,
# and an edit made with one before the model got its rules is answered with them first
TOPIC_TOOLS = {
    'SWAPS': {'swap_live_panels', 'swap_rows'},
    'LETTERS': {'edit_panel_letters', 'restyle_texts', 'set_panel_letter_position', 'set_panel_letter_layout',
                'add_corner_labels', 'set_label_background'},
    'BACKGROUND': {'set_image_property:fill_color', 'edit_panel_letters:background', 'set_label_background'},
    'ROWS': {'arrange_live_images', 'add_group', 'delete_last_rows', 'ungroup_all_images', 'reverse_selected_row',
             'add_label_row', 'add_side_label', 'move_image'},
    'SCALE BARS': {'set_scale_bar', 'set_scale_bar_all', 'remove_scale_bar', 'remove_scale_bar_all'},
    'COLOURS': {'set_lut', 'set_figure_colors'},
    'ROIs': {'detect_objects', 'remove_rois', 'move_annotations', 'set_inset_property', 'add_arrow'},
    'TEXT / EDITOR': {'add_annotation'},
    'PROCEDURES': {'save_chat_procedure', 'run_procedure_here'},
    'PLACEHOLDERS': {'add_placeholder_grid'},
    'CAPTION': {'set_figure_caption'},
    'DRAWINGS': {'add_scripted_image'},
    'INTEGRITY': {'check_image_integrity'},
    'FOLDERS': {'scan_folder', 'add_folder_files'},
}


# Hold an edit once to hand the model its topic's rules first. OFF by default (user,
# 2026-11-19: "if we can get one call less and good results I'd prefer that"): over the
# 82 turns of a live Mistral replay with and without it, the run without had 2 wrong
# turns, with it 5, and every held edit costs one more call. Searches still return the
# rules of the operations they find. PYFIGURES_RULES_FIRST=1 turns the hold back on.
RULES_FIRST = os.environ.get('PYFIGURES_RULES_FIRST') == '1'


def _topic(rule: str) -> str:
    return rule.split(':', 1)[0]


def topics_of(tool_name: str, arguments: dict | None = None) -> list[str]:
    """The topics whose rules govern this call."""
    names = {tool_name}
    prop = str((arguments or {}).get('property_name') or '')
    if prop:
        names.add(f'{tool_name}:{prop}')
    # an argument names a topic too: a letter background is also a BACKGROUND question
    # (Mistral 2026-11-19: "add a black bg to g" went to edit_panel_letters, never told
    # that a panel named by its letter means the PANEL background)
    names.update(f'{tool_name}:{key}' for key in (arguments or {}))
    return [t for t, tools in TOPIC_TOOLS.items() if names & tools]


def rules_of(topics) -> str:
    return ' '.join(rule for _k, rule in TOPIC_RULES if _topic(rule) in set(topics))


def _stem(word: str) -> str:
    """swap / swapping / swapped, save / saved, label / labelling, colour / coloured: one stem."""
    w = word.lower()
    for suffix in ('ing', 'ed', 'es', 's'):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[:-len(suffix)]
            break
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in 'aeiou':
        w = w[:-1]                      # swapp -> swap, labell -> label
    return w[:-1] if len(w) > 3 and w.endswith('e') else w


def _fits(words, keys) -> bool:
    stems = {_stem(w) for w in words}
    return bool(set(words) & keys or stems & {_stem(k) for k in keys})


def topic_rules(words) -> str:
    """The rules of every topic the search words fit (any form of the word)."""
    words = set(words)
    return ' '.join(rule for keys, rule in TOPIC_RULES if _fits(words, keys))


def request_rules(text: str, earlier: str = '') -> str:
    """The topic rules a user's request calls for, sent by the chat WITH the request
    (2026-11-19 benchmark: with the rules only in search results, Mistral previewed
    panel e seven times for "draw ROIs over every cell in e" and never learned that
    detect_objects does it in one call). Only the topics its words fit: a follow-up
    with no topic words ("you did not finish", "two bars side by side") takes the previous
    request's. Empty when nothing fits, so the first message stays small."""
    words = re.findall(r'[a-z0-9]+', str(text or '').lower())
    topics = _request_topics(words)
    if not topics:                  # a follow-up ("continue", "two bars side by side"): the previous request's
        topics = _request_topics(re.findall(r'[a-z0-9]+', str(earlier or '').lower()))
    return rules_of(topics)


# The user's own words that call for a topic. Stricter than the search keys: a user's
# sentence is not a search query ("not bad" is no NOTE, "two bars side by side" no
# scale bar, "same of the second image" no lettering rule), and a wrong rule sent with
# a request misleads more than none.
REQUEST_KEYS = {
    'SWAPS': {'swap', 'exchange', 'switch', 'interchange'},
    'LETTERS': {'letter', 'lettering', 'abc', 'label'},
    'BACKGROUND': {'background', 'bg'},
    'READINESS': {'submission', 'submit', 'journal', 'publication', 'ready'},
    'HOW-TO': {'how', 'help', 'where', 'teach', 'menu', 'tutorial', 'manual', 'guide', 'click'},
    'ROWS': {'row', 'column', 'arrange', 'grid', 'rearrange', 'ungroup', 'heading', 'header'},
    'SCALE BARS': {'scale', 'scalebar'},
    'COLOURS': {'channel', 'lut', 'colour', 'color', 'colormap', 'colourmap', 'magenta', 'green', 'red', 'blue',
                'cyan', 'yellow'},
    'ROIs': {'roi', 'cell', 'nucleus', 'nuclei', 'detect', 'segment', 'embryo', 'inset', 'arrow', 'arrowhead',
             'ellipse', 'square', 'triangle', 'polygon'},
    'TEXT / EDITOR': {'annotation', 'edit', 'editor', 'myself', 'manually', 'write', 'text', 'adjust', 'tweak',
                      'refine'},
    'PROCEDURES': {'procedure', 'macro'},
    'FILES': {'save', 'export', 'pdf', 'png', 'tif', 'tiff', 'svg', 'pptx', 'ppt'},
    'PLACEHOLDERS': {'fake', 'dummy', 'placeholder', 'template'},
    'CAPTION': {'caption', 'legend'},
    'SELECTION': {'select', 'selected', 'selection'},
    'DRAWINGS': {'illustrate', 'illustration', 'diagram', 'schematic', 'scheme', 'sketch', 'cartoon'},
    'INTEGRITY': {'duplicate', 'identical', 'reused', 'integrity', 'inverted', 'investigate', 'similar'},
    'FOLDERS': {'files', 'folder', 'directory'},
}


def _request_topics(words) -> list[str]:
    """Topics whose keys a word of the request is, or starts (letters, coloured, arrowheads)."""
    found = []
    for topic, keys in REQUEST_KEYS.items():
        if any(w in keys or (w.endswith('s') and w[:-1] in keys)                      # luts, rois
               or any(len(k) >= 4 and w.startswith(k) for k in keys) for w in words):
            found.append(topic)
    return found


def all_guidance(server) -> str:
    """The server instructions and every topic rule (what a model can be told)."""
    return (server.instructions or '') + ' ' + ' '.join(rule for _k, rule in TOPIC_RULES)


def topic_note(words):
    """What a search cannot find because it does not exist, or hides under another name:
    said at once, before the tool list (2026-11-12: "make the 2nd row a little taller"
    took thirty calls and ended in a row wider than the figure; "show the next z" was
    searched eight times)."""
    words = set(words)
    return _special_note(words) + topic_rules(words)


def _special_note(words):
    words = set(words)
    if (words & {'same', 'equal', 'uniform', 'equalize', 'equalise', 'consistent'}
            and words & {'size', 'sizes', 'width', 'widths', 'scale'}
            and words & {'all', 'images', 'panels', 'every', 'each', 'batch'}) \
            or words & {'stacked', 'grid', 'tidy', 'ugly', 'messy'}:
        # 2026-11-16: "they are all stacked and don't have the same size": eight searches
        # for a "same size" tool, arrange_live_images found four times and never called
        return ('IMAGES STACKED / OF DIFFERENT SIZES: call arrange_live_images (columns=N, or row_counts) now. It '
                'puts every image in rows; the images of a row share one height and every row spans the figure '
                'width, which is what evens out their sizes. There is no separate "same size" tool: do not search '
                'further. ')
    if words & {'row', 'rows'} and words & {'height', 'taller', 'shorter', 'tall', 'heights', 'equal', 'same'} \
            or words & {'image', 'panel', 'picture'} and words & {'bigger', 'larger', 'smaller', 'resize'} and 'figure' not in words:
        return ('ROW HEIGHT / SIZE OF ONE IMAGE: there is no such property. Every row spans the figure width and the '
                'images of a row share one height, so a row is as tall as the shapes of its images make it. To make a row '
                'taller: put fewer images in it (arrange_live_images row_counts), crop its images narrower '
                '(transform_image), or widen the whole figure (resize_figure). set_size on one row makes it wider than '
                'the others: not what is asked. Say this and offer these choices; do not search further. ')
    if words & {'column', 'columns', 'sheet', 'sheets', 'head', 'preview', 'factor', 'factors', 'factorizable',
                'levels', 'mean', 'means', 'summary', 'summarize', 'summarise'} \
            and words & {'table', 'tables', 'csv', 'excel', 'xlsx', 'xls', 'sqlite', 'data', 'dataframe'}:
        # 2026-11-18: eight searches for a way to read a table's columns, then stopped
        return ('TABLES: describe_table(csv_path, sheet) = its columns, types, levels, first rows and the plots '
                'that fit; list_factor_columns(csv_path, sheet) = the columns that can split / colour / facet; '
                'summarize_table(csv_path, value, by, where) = n, mean, SD per group; add_table_panel = a table '
                'as a figure panel. A data plot / seaborn plot panel already says its table in panel_references. '
                'Call one of them now; do not search further. ')
    if words & {'half', 'split', 'splitted', 'raincloud'} and words & {'violin', 'violins'}:
        return ('HALF / SPLIT VIOLINS: edit_data_plot(panel_ref, violin_side="left") = half violins (points on the '
                'other side); kind="split_violin" with columns=[x, two-level column, value] = two conditions as the '
                'two halves (e.g. sex); seaborn: add_seaborn_plot(function="violinplot", hue=..., options={"split": '
                'true}). Do not search further. ')
    if words & {'facet', 'facets', 'faceted'}:
        return ('FACETS: add_data_plot / edit_data_plot(facet="day") = one plot per value, each with its '
                'statistics (facet_row for a grid); seaborn: col= / row=. Do not search further. ')
    if words & {'plot', 'plots', 'chart', 'graph', 'violin', 'violins', 'boxplot', 'histogram', 'seaborn',
                'anova', 'stars', 'stats', 'statistics', 'significance', 'pvalue', 'pvalues', 'swarm'}:
        # the plot options, said only when the model asks about plots: they were 8 kB of the
        # tool description sent on every turn (user, 2026-11-19: first messages small)
        return ('PLOT OPTIONS: ' + _PLOT_OPTIONS + ' The tests in the figure LEGEND / caption ("put the stats in '
                'the legend"): add_statistics_to_caption (caption_statistics reads it). ')
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
        'list_recovery_snapshots', 'restore_recovery_snapshot', 'remove_scale_bar_all', 'ungroup_all_images', 'delete_last_rows', 'reverse_selected_row',
        'run_procedure_here'}
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
        'Edit scientific figures in the open PyFigures GUI. Only the seven listed functions are callable. '
        'Find an operation with find_pyfigures_tools (search with the user\'s words: the result gives its exact '
        'argument schema AND the rules for that topic: follow them), then run it with '
        'use_pyfigures_tool(tool_name=..., arguments=...). Never guess argument names'
        + (', except the common operations listed in use_pyfigures_tool, after checking their scope' if common else '')
        + '; do not search again after a no-match. '
        'For a named panel pass panel_ref (its letter, or "#3"), not group_path/image_index. Call a panel by its '
        'letter, else "#3", never by a panel_id such as "1/1". inspect_figure.selection is what the user selected '
        '("this row", "the selected image"): use it, do not ask again. figure_summary in the state answers "what is '
        'in the figure?"; when it says empty=true, reply at once from it, without calling tools. '
        'A missing, unknown or ambiguous panel (UNKNOWN_PANEL_REFERENCE / AMBIGUOUS_PANEL_REFERENCE): ask which one '
        'and stop that edit; never substitute another panel or guess coordinates. A uniquely named panel wins over '
        'a positional description. Short requests that fit several things of a panel ("the colour of a", "make g '
        'bigger", "delete g", "the text": the letter, the image, a channel colour, a scale bar, an annotation): when '
        'only one exists or fits, do it and say which; when several fit, ask which one in one short question and '
        'change nothing first; offer "open the panel editor so you do it yourself" among the choices. Never edit '
        'then undo to ask. An invalid or unsupported value: explain the valid range and ask; never substitute one. '
        'RELATIVE requests (bigger, thicker, a bit more, brighter) need no number: change the current value by '
        'about a third (half for "a bit"), say the old and new value, offer to go further. Never ask for a number '
        'first. Misspelt words are read as the obvious word ("mak lettrs biger" = make the letters bigger). '
        'Pass only the properties asked for plus the target. The SAME OPERATION ON MANY ITEMS (all panels, 20 '
        'ROIs): ONE use_pyfigures_tool call with batch=[{item 1}, {item 2}, ...], never one call per item; '
        'figure-wide operations (*_all, arrange_live_images, edit_panel_letters) once, never loops. '
        'HOW-TO and HELP requests ("how do I…", "help me change the channel colours of e") get GUI steps (explain_how), not code, change nothing, and end by offering to highlight where to click (search "how" for that rule). '
        'To say how a panel LOOKS use preview_panel(panel_ref, view="figure") first. Never say what a panel looks like without it. '
        'A successful call is not task success: verify every clause of the request, report the verified change '
        'briefly. "Put it back / undo that" just after your edit: undo_redo(action="undo"). On GUI_OFFLINE stop and '
        'ask the user to reopen the window. Session ids and revisions are internal. Recovery copies are not saving '
        '(save_live_figure saves).'))

    @server.tool()
    def inspect_figure() -> dict:
        """Read the open figure, panel scene geometry, source sizes, current selection and last_canvas_click. Each panel_references entry also gives pixel_size (None = uncalibrated, pixels only), scale_bars (count), luts (channel colour tables), channel_colours (what each channel shows), file_colours (the file's own colours: what set_lut "NONE" restores), stack (None = a single image; else z, t and channel counts and what is shown: "which images are stacks?" is answered here, no other tool), kind ('image' pixels from a file, 'code' made by a script or plot, 'vector' SVG/PDF), name (what to call it in a reply: its letter, else "#N"), number (shown on the canvas on a selected panel: "#3" or "number 3" from the user is panel_ref "#3"), hard_to_see (its letter, texts, scale bar, ROIs or arrows that are hard to read as drawn: colour, colour behind, contrast ratio; None = all read well), source_file and source_missing (its image file is gone: the panel shows an error placeholder; missing_source_files says how to fix it). Valid image_position is raw image pixels for clicked ROI/arrow placement; never use invalid or stale points."""
        state = send('inspect')
        summary = state.get('figure_summary') or {}
        if summary.get('empty'):          # nothing else in the state says anything useful
            return {'figure_summary': summary, 'path': state.get('path'), 'revision': state.get('revision')}
        # what is hard to see, measured as drawn: a 9B text-only model always called
        # inspect_figure but never the figure view (benchmark, 2026-11-17)
        import os
        if os.environ.get('QTPY_AI_SIDECAR_VISION') == 'none':
            return state                  # the user keeps everything visual from the model
        try:
            from .live_mcp import call_live
            contrast = call_live('overlay_contrast')
        except Exception:
            return state
        for ref in state.get('panel_references') or []:
            m = (contrast.get('panels') or {}).get(ref.get('panel_id'))
            if m is None:
                continue
            ref['hard_to_see'] = m['problems'] or None
            ref['overlays_that_read_well'] = m['read_well']
        if contrast.get('skipped'):
            state['hard_to_see_not_measured'] = (f"{len(contrast['skipped'])} panels not measured (time limit): "
                                                 "use preview_panel(panel_ref, view='figure') for them")
        return state

    @server.tool()
    def preview_figure():     # Image, or text for an empty figure ('Image | str' breaks FastMCP's schema)
        """Show the current GUI canvas: the layout and overall look of the whole figure, each panel small; its rulers are figure units, not image pixels. To place or check anything in ONE panel's pixels (crops, ROIs, arrows, finding or counting objects) use preview_panel(panel_ref) instead: full size, source-pixel rulers, region zoom. No session parameters required. An empty figure gives a short text instead."""
        from .live_mcp import call_live
        summary = send('inspect').get('figure_summary') or {}
        if summary.get('empty'):
            return summary['answer'] + ' ' + summary['how_to_add_content']
        result = call_live('preview')
        return Image(path=result['path'])

    panel_preview = available.get('preview_panel')
    if panel_preview is not None:
        # Offered directly like preview_figure: behind use_pyfigures_tool, Qwen 27B looked at
        # the whole figure (each panel small) 92 times and at one panel 25 times in a replay,
        # Mistral the other way round (user, 2026-11-19: "seeing could solve a lot of issues").
        @server.tool()
        def preview_panel(panel_ref: str, view: str = 'source', region: list[float] | None = None,
                          brighten: bool = True) -> list:
            """See ONE panel full size. view='source': its whole source image with pixel rulers (crops, ROIs, arrows, finding or counting objects); view='figure': the panel as shown in the figure (letters, texts, scale bar), with contrast measures. region=[x0, y0, x1, y1] in source pixels zooms in. Look before acting on what an image shows, and after, to check it."""
            return panel_preview.fn(panel_ref=panel_ref, view=view, region=region, brighten=brighten)

    @server.tool()
    def undo_redo(action: str = 'undo') -> dict:
        """Undo or redo one GUI document edit. action: undo or redo.

        "Restore it as it was", "put it back", "revert that", "cancel that", "go back" right
        after your edit: call undo once per edit you made for that request (one set_lut =
        one undo), instead of re-creating the old state with a new edit.
        Undo takes back the LAST step first (an arrangement is a step of its own, after
        the images it arranges): undo_redo_effect gives the figure before and after, so
        check which step went. To remove one extra panel use remove_image, not undo."""
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
            # "the scale bar in i does not read well", "is the letter visible": view='figure'
            # shows the panel as drawn and measures each overlay's contrast (2026-11-17)
            if name=='preview_panel' and any(w in ('read','reads','readable','readability','legible','visible','contrast','see','look','looks','appearance','shown') for w in words):score+=300
            # "draw ROIs over every cell in e", "how many cells in b": one thresholding call (2026-11-13)
            if name=='detect_objects' and any(w in ('cell','cells','nucleus','nuclei','object','objects','embryo','embryos','blob','blobs','spot','spots','particles','particle','beads','bead') for w in words) and (any(w in ('every','each','all','many','count','detect','find','segment') for w in words) or any(w in ('roi','rois','box','boxes','circle','circles','outline','outlines','ellipses') for w in words)):score+=620
            # "move the box in b 100 px to the right" (eight searches found nothing, 2026-11-13)
            if name=='move_annotations' and any(w in ('move','shift','nudge','translate','displace','drag','offset') for w in words) and any(w in ('roi','rois','box','boxes','rectangle','ellipse','circle','square','polygon','arrow','arrows','line','lines','inset','insets','annotation','annotations','text','label','shape','shapes','right','left','up','down','px','pixels') for w in words):score+=600
            # "remove all the ROIs", "clear the ellipses": one call, not 26 (2026-11-13)
            if name=='remove_rois' and any(w in ('remove','delete','clear','erase','replace','rid') for w in words) and any(w in ('roi','rois','box','boxes','ellipse','ellipses','circle','circles','rectangle','rectangles','square','squares','polygon','polygons','outlines','shapes','all') for w in words):score+=640
            # "draw ROIs over every cell in e": the model guessed from the whole figure (2026-11-13)
            if name=='preview_panel' and any(w in ('cell','cells','nucleus','nuclei','object','objects','embryo','embryos','blob','blobs','spot','spots','around','over','each','every') for w in words) and any(w in ('roi','rois','box','boxes','rectangle','rectangles','circle','circles','ellipse','ellipses','arrow','arrows','outline','outlines') for w in words):score+=380
            if name=='transform_image' and any(w in ('crop','cropping','rotate','rotation','flip') for w in words):score+=200
            # "fit each panel's bg to the bg of its image", "sample the corner pixel colour": fill_color="auto"
            # (thirteen searches for a pixel sampler, then gave up, 2026-11-13)
            # the words of real chat requests that found nothing (regression table:
            # tests/test_chat_scenarios_20261113.py)
            shape_words=('roi','rois','line','lines','triangle','triangles','box','boxes','ellipse','ellipses','circle','circles',
                         'rectangle','rectangles','square','squares','polygon','polygons','outline','outlines','shapes','arrow','arrows')
            if name=='set_roi_properties' and any(w in shape_words for w in words) and any(w in ('stroke','strokes','thickness','thicker','thinner','width','colour','color','red','green','blue','yellow','white','black','magenta','cyan','dashed','dotted','opacity','fill','filled') for w in words):score+=600
            if name=='set_inset_property' and any(w in ('inset','insets') for w in words) and any(w in ('corner','bottom','top','left','right','placement') for w in words):score+=580   # resizing: edit_annotation_properties
            if name=='transform_image' and any(w in ('uncrop','uncropped') for w in words):score+=450
            if name=='export_pptx' and any(w in ('ppt','pptx','powerpoint','slide','slides') for w in words):score+=650
            # "save what we did as a procedure", "a macro to do the same on my other figures" (2026-11-13)
            # "apply my procedure to this figure", "run wing_procedure.json here"
            if name=='run_procedure_here' and any(w in ('procedure','procedures','macro','macros') for w in words) and any(w in ('run','apply','play','replay','execute','use','do') for w in words):score+=700
            if name=='save_chat_procedure' and not any(w in ('run','apply','play','replay','execute') for w in words) and (any(w in ('procedure','procedures','macro','macros','recipe','workflow') for w in words)
                                                or ('same' in words and any(w in ('other','figures','figs') for w in words))
                                                or ('repeat' in words and any(w in ('steps','this','these','what','did','done') for w in words))):score+=650
            if name=='remove_rois' and 'instead' in words and any(w in shape_words for w in words):score+=500
            if name=='set_image_property' and (any(w in ('bg','background','backgrounds','bgs','fill') for w in words) and any(w in ('image','images','match','matching','fit','same','own','its','picture','pictures','each','auto','panel','panels') for w in words)
                                               or any(w in ('pixel','pixels','corner','border','edge','edges') for w in words) and any(w in ('colour','color','sample','value','rgb','average') for w in words)):score+=560
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
        said = [_topic(rule) for keys, rule in TOPIC_RULES if _fits(set(words), keys)]
        found_topics = []
        for entry in found:
            for t in topics_of(entry.get('name', '')):
                if t not in said and t not in found_topics:
                    found_topics.append(t)
        for t in said + found_topics:
            rules_given[t] = calls['n']
        return {'manual_guides':manual_guides,'guidance': topic_note(words) + rules_of(found_topics) + ('Swap references identify IMAGE PANELS by default. Use target=images; target=letters only for explicit letter-text requests. Missing or non-unique references require clarification: stop, never substitute an existing panel or retry with other references. Never remove letters as a swap workaround.'
                             if any(w in ('swap', 'exchange', 'switch') for w in words) else
                             'Report verified after-state, not merely native success text. Ordinary text/captions are NOT automatic panel letters: inspect get_annotations and remove_annotation for quoted text, preserving letters. removal_request must quote the actual human request verbatim, never an invented clearer request.'),
                'total_matches': len(ranked), 'offset': offset,
                'next_offset': offset + len(found) if offset + len(found) < len(ranked) else None,
                'tools': found}

    # The same operation called again and again, one model step each (2026-11-13: 26
    # add_roi_polygon then 26 set_roi_properties, ~4 s per step, the 32-step limit hit):
    # batch runs them all in one call, and a repeated call is told to batch the rest.
    repeats = {'key': None, 'count': 0}
    BATCH_LIMIT = 400
    # topic -> the call number when its rules were last given; edits held once for their rules
    rules_given, held, calls = {}, set(), {'n': 0}
    RULES_RECENT = 40          # calls after which the rules count as forgotten (a new conversation)

    def _rules_first(tool_name, arguments, batch):
        """The rules of an edit's topic when the model has not had them recently: the
        call is held once (the same call sent again runs)."""
        if not RULES_FIRST or tool_name.startswith(('get_', 'list_', 'inspect_', 'describe_', 'check_', 'find_',
                                                    'preview_', 'explain', 'render_')):
            return None
        topics = topics_of(tool_name, arguments) or [t for item in (batch or [])[:1]
                                                     for t in topics_of(tool_name, {**arguments, **item})]
        missing = [t for t in topics if calls['n'] - rules_given.get(t, -10 ** 6) > RULES_RECENT]
        if not missing:
            return None
        key = json.dumps([tool_name, arguments, batch], sort_keys=True, default=str)
        if key in held:
            return None
        held.add(key)
        for t in missing:
            rules_given[t] = calls['n']
        return {'not_run': True, 'document_changed': False,
                'rules': rules_of(missing),
                'next_step': (f'{tool_name} was NOT run: first read these rules ({", ".join(missing)}). If the call '
                              'still fits them, send exactly the same call again: it will run. If they change what '
                              'to do (ask the user first, another operation, one call instead of several), do that '
                              'instead.')}

    def _short(value, limit=160):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        return text if len(text) <= limit else text[:limit] + '…'

    @server.tool(structured_output=False)
    async def use_pyfigures_tool(tool_name: str = '', arguments: dict | None = None,
                                 batch: list[dict] | None = None) -> object:
        """Execute a discovered original PyFigures operation or live convenience operation. Pass its exact name and arguments matching the schema from find_pyfigures_tools. Omit pyf_path for the open figure. Session/revision/request fields for prototype operations may be omitted: filled automatically. Errors are returned as MCP tool errors; images remain image content.
        FREQUENT OPERATIONS, call them directly without searching first (panel_ref = the panel's letter; a wrong argument returns the exact schema): transform_image(panel_ref, rotation=degrees: POSITIVE = CLOCKWISE as seen, so "25° clockwise" = 25 and "25° counter-clockwise" = -25 (not the maths convention); the absolute angle, 0 = upright, flip_h, flip_v, crop_left/right/top/bottom=px), configure_image(panel_ref, projection="max"|"none", projection_z_start, projection_z_end, channels=[bool,...]), set_lut(panel_ref, luts=["GREEN", ...]), set_image_property(panel_ref, property_name, value), set_scale_bar(panel_ref, bar_width_in_units, unit), add_image(group_path=[], filename) (batch for several), remove_image(panel_ref) (several panels: ONE call, arguments={panel_refs: ["h", "f", "m"]}; every letter is read before anything is removed, so letters that shift during the removal never pick the wrong panel), arrange_live_images(columns or row_counts), edit_data_plot(panel_ref, option=value) changes a DATA PLOT (kind, colours, statistics, labels, facets, rows...; the option names and the user's words for them: list_data_plot_kinds, or search "plot"), edit_seaborn_plot a seaborn plot; TABLES: describe_table / list_factor_columns / summarize_table / add_table_panel (category plots). A data plot is a panel whose panel_references "code" says data_plot; never set_script on it.
        SAME OPERATION ON MANY ITEMS (recolour 26 ROIs, add 20 polygons, move 10 arrows, set 6 panels): ONE call, never one call per item. arguments = the fields shared by all, batch = [{the fields of item 1}, {item 2}, ...]; each item is merged over arguments and run in order. Example: tool_name=set_roi_properties, arguments={panel_ref: "e", color: "red"}, batch=[{annotation_index: 1}, {annotation_index: 2}, ...]."""
        # tool_name put INSIDE arguments: ministral-3b sent {"arguments": {"tool_name":
        # "remove_image", ...}} 20 times and got only a pydantic "Field required" (chat log
        # 2026-11-17); the intent is plain, so it is taken from there
        arguments = dict(arguments or {})
        if not tool_name and isinstance(arguments.get('tool_name'), str):
            tool_name = arguments.pop('tool_name')
            if set(arguments) == {'arguments'} and isinstance(arguments['arguments'], dict):
                arguments = dict(arguments['arguments'])     # {"tool_name": ..., "arguments": {...}}
        if not tool_name:
            raise ValueError('tool_name is missing. It is a top-level field beside arguments, not inside it: '
                             'use_pyfigures_tool(tool_name="remove_image", arguments={"panel_ref": "h"}).')
        calls['n'] += 1
        first = _rules_first(tool_name, arguments, batch)
        if first is not None:
            return first
        # several panels for a one-panel tool ("remove h, f, m, r, x"): one batch, its
        # letters all read before the first edit (chat 2026-11-17: removed one by one)
        refs = arguments.get('panel_refs')
        if not batch and isinstance(refs, list) and refs and 'panel_ref' not in arguments:
            from .original_registry import registry as _originals
            native = _originals().get(tool_name)
            if native is not None and 'group_path' in inspect.signature(native.fn).parameters:
                arguments.pop('panel_refs')
                batch = [{'panel_ref': str(r)} for r in refs]
        if batch:
            if not isinstance(batch, list) or not all(isinstance(item, dict) for item in batch):
                raise ValueError('batch is a list of argument objects, e.g. [{"annotation_index": 1}, {"annotation_index": 2}]')
            # arguments are shared by every item; one that EVERY item replaces by another value was
            # an item of its own (chat 2026-11-19: the first of 20 files, put beside the batch,
            # was silently dropped and re-added last)
            own = {k: v for k, v in arguments.items()
                   if all(k in item and item[k] != v for item in batch)}
            if own:
                arguments = {k: v for k, v in arguments.items() if k not in own}
                batch = [own] + list(batch)
            if len(batch) > BATCH_LIMIT:
                raise ValueError(f'batch holds at most {BATCH_LIMIT} items; split it in two calls')
            if tool_name.startswith(('preview_', 'render_', 'export_')):
                raise ValueError(f'{tool_name} returns images or files: call it once, not in a batch')
            repeats.update(key=None, count=0)
            if tool_name.startswith('remove_') and all(isinstance(i.get('annotation_index'), int) for i in batch):
                # removing index 3 shifts every later one: the highest first keeps the others valid
                batch = sorted(batch, key=lambda i: i['annotation_index'], reverse=True)
            done, errors, results, warnings = 0, [], [], []
            outcomes = []           # (item number, item, result or exception)
            page_fit = ''           # the open figure fitted to the page after the batch
            from .original_registry import batchable_original, collect_batch, stop_collecting, decode
            if batchable_original(tool_name):
                # figure edits: collected, then run by the open figure as ONE batch and one reload
                collected, token = collect_batch()
                numbers = []
                try:
                    for number, item in enumerate(batch, 1):
                        size = len(collected)
                        try:
                            await _run_one(tool_name, {**arguments, **item})
                        except Exception as exc:
                            outcomes.append((number, item, exc))
                            continue
                        if len(collected) > size:
                            numbers.append((number, item))
                finally:
                    stop_collecting(token)
                if collected:
                    reply = None
                    for attempt in range(2):
                        state = send('inspect')
                        try:
                            reply = send('original_tool', state['session_id'], state['revision'],
                                         {'tool': tool_name, 'arguments': collected[0], 'batch': collected})
                            break
                        except ValueError as exc:
                            if attempt or getattr(exc, 'code', '') not in ('REVISION_CONFLICT', 'SESSION_CHANGED'):
                                raise
                    page_fit = (reply or {}).get('page_fit') or ''
                    for (number, item), each in zip(numbers, decode(reply['tool_result'])):
                        outcomes.append((number, item, each.get('result') if each.get('ok') else ValueError(each.get('error'))))
                    outcomes.sort(key=lambda o: o[0])
            else:
                for number, item in enumerate(batch, 1):
                    try:
                        outcomes.append((number, item, await _run_one(tool_name, {**arguments, **item})))
                    except Exception as exc:
                        outcomes.append((number, item, exc))
            for number, item, out in outcomes:
                if isinstance(out, Exception):
                    errors.append({'item': number, 'arguments': item, 'error': _short(str(out), 300)})
                    continue
                text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
                if text.lstrip().startswith('ERROR'):
                    errors.append({'item': number, 'arguments': item, 'error': _short(text, 300)})
                    continue
                done += 1
                if len(results) < 3:
                    results.append({'item': number, 'result': _short(out)})
                elif 'WARNING' in text:
                    # only 3 results are shown: a warning of a later item (a mistyped path,
                    # "does not exist (yet)") was never seen by the model (2026-11-16)
                    warnings.append({'item': number, 'arguments': item,
                                     'warning': _short(text[text.index('WARNING'):], 300)})
            summary = f'{tool_name}: {done} of {len(batch)} item(s) done in one call'
            if errors:
                summary += f'; {len(errors)} failed (see errors, the others are done: do not redo them)'
            reading = tool_name.startswith(('get_', 'list_', 'inspect_', 'describe_', 'check_', 'find_'))
            out = {'result': summary, 'batch_done': done, 'batch_total': len(batch),
                   'document_changed': done > 0 and not reading, 'first_results': results, 'errors': errors[:20]}
            if warnings:
                out['warnings'] = warnings[:20]
                summary += f'; {len(warnings)} with a WARNING (see warnings: check and fix them)'
                out['result'] = summary
            if page_fit:
                # the figure was fitted to the page after the batch: the model says so
                out['page_fit'] = page_fit
            if done and not reading and batchable_original(tool_name):
                # each item's result is the figure's own readback after the one reload: a
                # second inspect + re-read cost 40 s before the answer (2026-11-13)
                out['verified'] = ('Each item was applied to the open figure and read back; do not inspect or '
                                   're-read to check it: answer the user now.')
            return out
        out = await _run_one(tool_name, arguments)
        key = (tool_name, tuple(sorted(arguments)))
        repeats['count'] = repeats['count'] + 1 if repeats['key'] == key else 1
        repeats['key'] = key
        if repeats['count'] >= 2 and not tool_name.startswith(('preview_', 'inspect_', 'get_', 'list_')):
            tip = (f'TIP: this is call #{repeats["count"]} of {tool_name} in a row. Do ALL the remaining items in ONE '
                   f'use_pyfigures_tool call: arguments = the shared fields, batch = [{{fields of item}}, ...].')
            if isinstance(out, dict):
                out = {**out, 'tip': tip}
            elif isinstance(out, str):
                out = out + '\n\n' + tip
        return out

    async def _run_one(tool_name, arguments):
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
        if ('group_path' in properties and 'group_path' not in kwargs
                and 'group_path' in tool.parameters.get('required', [])):
            # the figure itself (chat 2026-11-19: every add_image of a batch of 21 failed on it,
            # then "Retrying with group_path=[]" was shown to the user)
            kwargs['group_path'] = []
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
