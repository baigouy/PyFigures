"""Prototype-only GUI behavior: explicit letter overrides survive auto-letter refresh."""
import html
import json
import re
import xml.etree.ElementTree as ET
from pyfigures.gui.pfgui import EZFIG_GUI as BaseGUI, TAText2D, Image2D
from batoolset.drawings.shapes.group import Group
from batoolset.drawings.shapes.Position import Position
from qtpy.QtGui import QColor, QTextCursor
from pyfigures.mcp_tools.core import _decode

from .plot_lifecycle import scene_transaction,close_scene_figures

POLICY = 'live_letter_policy'


def panels(items, path=()):
    group_index, image_index = 0, 0
    for obj in items:
        if isinstance(obj, Group):
            if not obj.isText:
                yield from panels(obj.content, path + (group_index,))
            group_index += 1
        elif isinstance(obj, Image2D):
            if not obj.isText:
                yield path, image_index, obj
            image_index += 1


def selection_state(window):
    import hashlib
    roots = window.paint.EZFIG_panel.shapes_to_draw
    groups, group_paths, live, records = [], {}, {}, {}
    panel_map = {id(p): (gp, ix, p) for gp, ix, p in panels(roots)}
    def walk(items, path=()):
        gi = 0
        for obj in items:
            if isinstance(obj, Group):
                gp = path + (gi,)
                groups.append((gp, obj))
                group_paths[id(obj)] = list(gp)
                walk(obj.content, gp)
                gi += 1
    walk(roots)
    def visit(obj, address, owner=None):
        if id(obj) in live:
            return
        live[id(obj)] = obj
        record = {'object_id': address, 'class': type(obj).__name__}
        if isinstance(obj, Group):
            orientation = str(obj.orientation).upper()
            record.update(kind='text_group' if obj.isText else 'row' if orientation == 'X' else 'column' if orientation == 'Y' else 'group',
                          orientation=orientation, group_path=group_paths.get(id(obj)), child_count=len(obj.content))
        elif isinstance(obj, Image2D):
            from qtpy.QtSvg import QSvgRenderer
            script = bool(getattr(obj, 'custom_loading_script', None))
            filename = str(getattr(obj, 'filename', '') or '')
            vector = isinstance(getattr(obj, 'img', None), QSvgRenderer) or filename.lower().endswith(('.svg', '.pdf'))
            record.update(kind='text_panel' if obj.isText else 'scripted_image' if script else 'vector_image' if vector else 'image2d',
                          representation='vector' if vector else 'raster', filename=filename,
                          has_custom_loading_script=script)
        elif isinstance(obj, TAText2D):
            record.update(kind='letter' if obj.is_letter else 'text_annotation', text=obj.getPlainText()[:1000])
        else:
            record['kind'] = 'annotation' if owner else 'shape'
        if id(obj) in panel_map:
            gp, ix, _ = panel_map[id(obj)]
            owner = '/'.join(map(str, (*gp, ix)))
            record.update(panel_id=owner, group_path=list(gp), image_index=ix,
                          letters=[a.getPlainText() for a in letters(obj)],
                          letter_styles=[letter_info(a) for a in letters(obj)])
        elif owner:
            record['owner_panel_id'] = owner
        records[id(obj)] = record
        if isinstance(obj, Group):
            for index, child in enumerate(obj.content):
                visit(child, f'{address}/content/{index}', owner)
        for index, child in enumerate(getattr(obj, 'annotations', None) or []):
            visit(child, f'{address}/annotations/{index}', owner)
    for index, obj in enumerate(roots):
        visit(obj, f'root/{index}')
    raw = window.paint.EZFIG_panel.selected_shape
    chosen = list(raw) if isinstance(raw, (list, tuple)) else [raw] if raw is not None else []
    selected = [obj for obj in chosen if id(obj) in live]
    image_ids = set()
    for obj in selected:
        if isinstance(obj, Group):
            image_ids.update(id(p) for _, _, p in panels(obj.content))
        elif isinstance(obj, Image2D) and not obj.isText:
            image_ids.add(id(obj))
        elif isinstance(obj, TAText2D) and obj.is_letter:
            owner = records[id(obj)].get('owner_panel_id')
            image_ids.update(id(p) for gp, ix, p in panel_map.values() if '/'.join(map(str, (*gp, ix))) == owner)
    refs = [records[id(p)] for gp, ix, p in panels(roots) if id(p) in image_ids]
    row_paths = [list(gp) for gp, row in groups if not row.isText and str(row.orientation).upper() == 'X'
                 and row.content and all(isinstance(p, Image2D) and not p.isText for p in row.content)
                 and any(id(p) in image_ids for p in row.content)]
    result = dict(has_selection=bool(selected), selected_object_count=len(selected),
                  stale_selection=bool(chosen) and len(selected) != len(chosen),
                  selected_objects=[records[id(obj)] for obj in selected],
                  selection_kind=records[id(selected[0])]['kind'] if len(selected) == 1 else 'mixed' if selected else 'none',
                  selected_panels=refs, selected_group_paths=[list(gp) for gp, g in groups if any(g is x for x in selected)],
                  containing_row_paths=row_paths,
                  containing_column_paths=[list(gp) for gp, g in groups if not g.isText and str(g.orientation).upper() == 'Y'
                                           and any(id(p) in image_ids for _, _, p in panels(g.content))])
    result['token'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def letters(panel):
    return [a for a in panel.annotations or [] if isinstance(a, TAText2D) and a.is_letter]


def color(value, transparent=False):
    if transparent and (value is None or str(value).lower() in ('none', 'transparent')):
        return None
    if isinstance(value, bool):
        raise ValueError('A boolean is not a color')
    if isinstance(value, int):
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError('Color integer out of range')
        if value > 0xFFFFFF:
            q = QColor.fromRgba(value)
            if q.alpha() == 0:
                if transparent:
                    return None
                raise ValueError('Foreground cannot be transparent')
            if q.alpha() != 255:
                raise ValueError('Use opaque colors or background="none"')
            value = q.rgb() & 0xFFFFFF
        return f'#{value:06x}'
    if not isinstance(value, str):
        raise ValueError('Use a color name, #RRGGBB, or RGB integer')
    q = QColor(value)
    if not q.isValid() or q.alpha() != 255:
        raise ValueError('Use an opaque color name/#RRGGBB; background="none" removes fill')
    return q.name()


def letter_info(a):
    cursor = QTextCursor(a.doc)
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
    fmt = cursor.charFormat()
    font = fmt.font()
    default = a.doc.defaultFont()
    return {'text': a.getPlainText(), 'placement': str(a.placement),
            'font_family': font.family() or default.family(),
            'font_size': font.pointSizeF() if font.pointSizeF() > 0 else default.pointSizeF(),
            'color': fmt.foreground().color().name(),
            'background': color(a.fill_color, True), 'opacity': a.opacity,
            'bold': font.bold(), 'italic': font.italic(), 'underline': font.underline()}


def state(window):
    entries = []
    for path, index, panel in panels(window.paint.EZFIG_panel.shapes_to_draw):
        entries.append({'panel_id': '/'.join(map(str, (*path, index))), 'group_path': list(path),
                        'image_index': index, 'filename': str(panel.filename),
                        'letters': [letter_info(a) for a in letters(panel)],
                        'override': json.loads(getattr(panel, POLICY, '{}'))})
    references={}
    for entry in entries:
        for annotation in entry['letters']:
            references.setdefault(annotation['text'].casefold(),[]).append(entry['panel_id'])
    duplicates={text:ids for text,ids in references.items() if len(ids)>1}
    canvas = window.paint.EZFIG_panel
    from pyfigures.gui.row_letters import normalise_layout, normalise_align
    layout = normalise_layout(getattr(canvas, 'letter_layout', None))
    # one letter per row, outside the rows (drawn by the canvas, not on a panel)
    row_letters = [{'row': k, 'text': t.getPlainText()}
                   for k, t in enumerate(canvas.row_letter_items())] if layout == 'row' else []
    return {'duplicate_letter_references':duplicates,
            'visible_letter_count': sum(len(p['letters']) for p in entries) + len(row_letters),
            'unlettered_panel_ids': [p['panel_id'] for p in entries if not p['letters']] if layout != 'row' else [],
            'auto_lettering': window.auto_lettering_checkbox.isChecked(),
            'first_letter': window.letter_line_edit.text(),
            'letter_layout': layout,
            'row_letter_align': normalise_align(getattr(canvas, 'row_letter_align', None)),
            'row_letters': row_letters,
            'default_position': str(window.serializable_font.placement), 'panels': entries}


def carry_policies(before, after):
    from pyfigures.mcp_tools.core import _html_to_plain, _encode_str
    old_root, new_root = ET.fromstring(before), ET.fromstring(after)
    def key(node):
        texts = tuple(_html_to_plain(_decode(a.findtext('text')) or '')
                      for a in node.findall('annotations/TAText2D') if a.findtext('is_letter') == 'True')
        return node.findtext('filename'), node.findtext('custom_loading_script'), texts
    known = {}
    for node in old_root.iter('Image2D'):
        if node.find(POLICY) is not None:
            known.setdefault(key(node), []).append(node.findtext(POLICY))
    for node in new_root.iter('Image2D'):
        if node.find(POLICY) is None and key(node) in known:
            matches = known[key(node)]
            # Multiple identical panels with different overrides are ambiguous.
            if len(set(matches)) == 1:
                ET.SubElement(node, POLICY).text = matches[0]
    return ET.tostring(new_root, encoding='utf-8', xml_declaration=True)


def restore_policies(nodes, objects):
    nodes = [n for n in nodes if n.tag in ('Image2D', 'Group')]
    for node, obj in zip(nodes, objects):
        if isinstance(obj, Image2D):
            # Native Image2D currently discards its opacity constructor argument.
            # Restore the declared document value, including undo/reload adoption.
            opacity=node.findtext('opacity')
            if opacity is not None:
                import math
                opacity=float(opacity)
                if not math.isfinite(opacity) or not 0<=opacity<=1:
                    raise ValueError('Invalid serialized image opacity')
                obj.opacity=opacity
            value = _decode(node.findtext(POLICY))
            if isinstance(value, str):
                json.loads(value)
                setattr(obj, POLICY, value)
        elif isinstance(obj, Group):
            from .live_structure import restore_group_marker
            restore_group_marker(node,obj)
            restore_policies(list(node.find('content') or []), obj.content)
            from .live_structure import reflow_intermediate_parent
            reflow_intermediate_parent(node,obj)


class PartnerGUI(BaseGUI):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from .live_structure import install_canvas
        install_canvas(self.paint.EZFIG_panel)


    def showEvent(self,event):
        from .live_structure import install_canvas
        install_canvas(self.paint.EZFIG_panel)
        super().showEvent(event)

    def _save_state_to_file(self,file,popup=None):
        result=super()._save_state_to_file(file,popup=popup)
        from pathlib import Path
        from .live_structure import sanitize_saved_structure
        from pyfigures.atomic_io import write_atomic
        path=Path(file);before=path.read_bytes();after=sanitize_saved_structure(before)
        if after!=before:write_atomic(str(path),after.decode('utf-8'))
        return result

    @scene_transaction
    def reload_state(self, path_to_xml_file, *args, **kwargs):
        self._live_loading = True
        try:
            result = super().reload_state(path_to_xml_file, *args, **kwargs)
            if path_to_xml_file:
                root = ET.parse(path_to_xml_file).getroot()
                if kwargs.get('append', args[0] if args else True) is False:
                    restore_policies(list(root), self.paint.EZFIG_panel.shapes_to_draw)
        finally:
            self._live_loading = False
        self.update_letters()
        if kwargs.get('append', args[0] if args else True) is False:
            # Recovery/adoption must also synchronize the control used by Split.
            from qtpy.QtCore import QSignalBlocker
            widths = [obj.width() for obj in self.paint.EZFIG_panel.shapes_to_draw
                      if not getattr(obj, 'isText', False) and hasattr(obj, 'width')]
            if widths:
                with QSignalBlocker(self.size_spinbox):
                    self.size_spinbox.setValue(int(round(max(widths))))
                self.update_size_in_unit()           # the mm / cm label beside it
        return result

    def _on_pyf_file_ready(self, path, properties, has_script):
        # File > Open uses the original asynchronous loader rather than reload_state.
        replace = getattr(self, '_pyf_replace_pending', False)
        old_count = len(self.paint.EZFIG_panel.shapes_to_draw)
        self._live_loading = True
        try:
            result = super()._on_pyf_file_ready(path, properties, has_script)
        finally:
            self._live_loading = False
        if replace and getattr(self, '_pyf_replace_pending', False):
            return result  # user declined loading a scripted file
        objects = self.paint.EZFIG_panel.shapes_to_draw
        restore_policies(list(ET.parse(path).getroot()), objects if replace else objects[old_count:])
        self.update_letters()
        return result

    def _sync_first_letter_box(self):
        """The toolbar's first-letter box follows the letters the panels were
        given one by one through the chat / MCP (A, B, C… kept in their
        policies): it showed "a" above a figure lettered in capitals, and a
        panel that lost its letter got a lower-case one back (2026-11-10).
        The sequence's first letter when the letters follow each other from
        it, else only its case."""
        from batoolset.strings.tools import increment_letter
        texts = []
        starts_the_figure = None
        automatic = 0
        for _, _, panel in panels(self.paint.EZFIG_panel.shapes_to_draw):
            policy = json.loads(getattr(panel, POLICY, '{}'))
            if policy.get('visible') is False:
                continue
            pinned = not policy.get('automatic_text', 'text' not in policy)
            if starts_the_figure is None:
                starts_the_figure = pinned
            if not pinned:
                automatic += 1
                continue
            text = policy.get('text')
            if isinstance(text, str) and len(text) == 1 and text.isalpha():
                texts.append(text)
        box = self.letter_line_edit.text()
        # one panel given its own letter among automatic ones sets nothing for the others
        if not texts or not box or automatic >= len(texts):
            return
        # only a sequence pinned from the FIRST panel on sets where it starts: "rename b
        # to Z" restarted every other letter at Z (2026-11-12)
        expected, sequence = texts[0], bool(starts_the_figure)
        for text in texts:
            sequence = sequence and text == expected
            expected = increment_letter(expected)
        if sequence:
            wanted = texts[0]
        elif all(t.isupper() for t in texts):
            wanted = box.upper()
        elif all(t.islower() for t in texts):
            wanted = box.lower()
        else:
            return
        if wanted != box:
            self.letter_line_edit.blockSignals(True)
            self.letter_line_edit.setText(wanted)
            self.letter_line_edit.blockSignals(False)

    def update_letters(self):
        if getattr(self, '_live_loading', False):
            return
        # Empty <annotations/> is decoded as a string by the native loader.
        # Normalize only empty values before the native GUI inserts letters.
        for _, _, panel in panels(self.paint.EZFIG_panel.shapes_to_draw):
            if isinstance(panel.annotations, str) and panel.annotations.strip() in ('', '[]', 'None'):
                panel.annotations = []
        self._sync_first_letter_box()
        super().update_letters()
        # an empty first-letter box with Letters ticked means no letters at all, as it
        # always did: letters the chat had styled or pinned came back (2026-11-12). Their
        # policies stay, so typing a letter again brings them back as they were.
        no_letters = self.auto_lettering_checkbox.isChecked() and not self.letter_line_edit.text().strip()
        for _, _, panel in panels(self.paint.EZFIG_panel.shapes_to_draw):
            policy = json.loads(getattr(panel, POLICY, '{}'))
            if not policy:
                continue
            existing = letters(panel)
            if no_letters:
                for a in existing:
                    panel.annotations.remove(a)
                continue
            if policy.get('visible') is False:
                for a in existing:
                    panel.annotations.remove(a)
                continue
            if not existing and policy.get('visible') is not True:
                continue
            a = existing[0] if existing else TAText2D('', is_letter=True)
            if not existing:
                panel.annotations.insert(0, a)
            for duplicate in existing[1:]:
                panel.annotations.remove(duplicate)
            # A stored base style makes explicit per-panel changes independent of defaults.
            base = policy.get('base', {})
            text = a.getPlainText() if policy.get('automatic_text', 'text' not in policy and self.auto_lettering_checkbox.isChecked()) else policy.get('text', base.get('text', a.getPlainText()))
            family = policy.get('font_family', base.get('font_family', self.serializable_font.family()))
            size = policy.get('font_size', base.get('font_size', self.serializable_font.pointSize()))
            foreground = policy.get('color', base.get('color', '#000000'))
            weight = 'bold' if policy.get('bold', base.get('bold')) else 'normal'
            italic = 'italic' if policy.get('italic', base.get('italic')) else 'normal'
            decoration = 'underline' if policy.get('underline', base.get('underline')) else 'none'
            body = f'<span style="font-family:&quot;{html.escape(family, quote=True)}&quot;;font-size:{size:g}pt;color:{foreground};font-weight:{weight};font-style:{italic};text-decoration:{decoration}">{html.escape(text)}</span>'
            # Base auto-lettering may reset the QTextDocument style while leaving
            # text and our cached HTML unchanged. Reapply the effective style,
            # rather than trusting a cache that does not describe the actual doc.
            a.setText(body)
            # the native pass must not take its cached HTML for what the letter shows now:
            # "renumber all" changed nothing on letters that had been pinned (2026-11-12)
            a._letter_source_html = None
            a.placement = Position(policy.get('placement', base.get('placement', 'top left')))
            fill = policy.get('background', base.get('background'))
            a.fill_color = None if fill is None else int(fill.lstrip('#'), 16)
            a.opacity = base.get('opacity', 1.0)



    def _roi_at_click(self, panel, box_size):
        """A square ROI of *box_size* raw pixels centred on the user's last
        canvas click, when that click is on *panel* (a person points rather
        than typing coordinates); slid inside the image near an edge."""
        session = getattr(self, '_live_session', None)
        click = session.pointer.snapshot() if session is not None and getattr(session, 'pointer', None) else None
        canvas = self.paint.EZFIG_panel
        pid = next(('/'.join(map(str, (*gp, ix))) for gp, ix, p in panels(canvas.shapes_to_draw) if p is panel), None)
        if not click or not click.get('valid') or click.get('panel_id') != pid:
            return None
        width, height = panel.get_raw_size()
        side = float(box_size)
        if not (side > 0):
            raise ValueError('box_size must be a positive number of image pixels')
        w_box, h_box = min(side, width), min(side, height)
        cx, cy = click['image_position']
        x = min(max(cx - w_box / 2, 0), width - w_box)
        y = min(max(cy - h_box / 2, 0), height - h_box)
        return x, y, w_box, h_box

    def roi_to_inset(self, panel_ref, annotation_index=None, box_size=120, validate_only=False):
        from .gui_selection import resolve_panel
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        from batoolset.serializations.tools import clone_object
        from batoolset.pyqts.tools import get_original_shape_from_rect_and_angle
        panel = resolve_panel(self, panel_ref)
        candidates = [(i, a) for i, a in enumerate(panel.annotations or []) if isinstance(a, Rectangle2D)
                      and not isinstance(a, (Image2D, TAText2D))]
        at_click = None
        if annotation_index is not None:
            candidates = [(i, a) for i, a in candidates if i == annotation_index]
        elif not candidates:
            at_click = self._roi_at_click(panel, box_size)
            if at_click is None:
                raise ValueError('CLARIFICATION_REQUIRED: This panel has no rectangular ROI and the last canvas click is '
                                 'not on it. Ask the user to click the region to magnify (or draw an ROI) on this panel.')
        if at_click is None and len(candidates) != 1:
            raise ValueError('CLARIFICATION_REQUIRED: Choose one rectangular ROI using its inspected annotation_index')
        if validate_only:
            return
        if at_click is not None:
            # the ROI is kept on the panel, as the native Rect ROI --> Inset keeps it
            panel.annotations = list(panel.annotations or [])
            panel.annotations.append(Rectangle2D(*at_click, stroke=2, color=0xFFFF00))
            candidates = [(len(panel.annotations) - 1, panel.annotations[-1])]
        index, roi = candidates[0]
        # Same helper and clone/crop steps as native Rect ROI --> Inset.
        from qtpy.QtCore import QRectF
        width, height = panel.get_raw_size()
        angle, left, right, top, bottom = get_original_shape_from_rect_and_angle(QRectF(0, 0, width, height), roi.getRect(), roi.theta)
        inset = clone_object(panel)
        inset.setTopLeft(0, 0)
        inset.set_to_scale(1)
        inset.border_size, inset.border_color = 3, roi.color
        inset.crop(left, right, top, bottom)
        inset.theta = angle
        inset.annotations = []
        if hasattr(inset, POLICY):
            delattr(inset, POLICY)
        inset = clone_object(inset)
        # it re-crops to the ROI when the ROI is moved (by hand in the editor too, 2026-11-12)
        from pyfigures.connectors import follow_roi
        follow_roi(inset, roi)
        original = list(panel.annotations)
        panel.annotations.append(inset)
        canvas = self.paint.EZFIG_panel
        canvas.update()
        canvas.repack_all()
        self.update_letters()
        canvas.update_size()
        canvas.repaint()
        if len(panel.annotations) != len(original)+1 or any(a is not b for a,b in zip(original, panel.annotations)):
            raise ValueError('Inset verification failed: original annotations changed')
        pid = next('/'.join(map(str, (*gp, ix))) for gp, ix, p in panels(canvas.shapes_to_draw) if p is panel)
        return dict(action='roi_to_inset', changed=1, matched_panel_ids=[pid], changed_panel_ids=[pid],
                    completion_verified=True, source_roi_index=index, inset_index=len(panel.annotations)-1,
                    crop=dict(left=left,right=right,top=top,bottom=bottom), rotation_degrees=angle,
                    source_filename=str(inset.filename), roi_preserved=True,
                    connect_hint='to join the ROI and this inset with leader lines: connect_roi_to_inset (computes the ends)',
                    resize_hint='to make this inset larger or smaller later: edit_annotation_properties on it '
                                '(inset_index) with changes {"size_fraction": ...}; never add a second inset',
                    **({'roi_from_last_click': dict(x=at_click[0], y=at_click[1], width=at_click[2], height=at_click[3],
                                                    note='square ROI centred on the last canvas click')}
                       if at_click is not None else {}))

    def swap_rows(self, first_row, second_row, validate_only=False):
        canvas = self.paint.EZFIG_panel
        roots = canvas.shapes_to_draw
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 or n > len(roots) for n in (first_row, second_row)):
            raise ValueError('Use visible row numbers starting at 1')
        if any(not isinstance(g, Group) or g.isText or str(g.orientation).upper() != 'X' for g in roots):
            raise ValueError('CLARIFICATION_REQUIRED: This canvas is not a flat list of horizontal rows')
        if validate_only:
            return
        from pyfigures.gui.row_letters import normalise_layout
        if normalise_layout(getattr(canvas, 'letter_layout', None)) == 'row':
            # one letter per row, outside the rows: the letters follow the row
            # order by themselves and the panels carry none (recording "no
            # letter" policies on them hid their letters for good once the
            # figure went back to a letter in each panel)
            a, b = first_row - 1, second_row - 1
            roots[a], roots[b] = roots[b], roots[a]
            canvas.update()
            canvas.repack_all()
            canvas.update_letters_required.emit()
            canvas.update_text_rows.emit()
            canvas.update_size()
            canvas.repaint()
            return dict(action='swap_rows', changed=int(a != b), matched_panel_ids=[], changed_panel_ids=[],
                        first_row=first_row, second_row=second_row, completion_verified=True,
                        lettering_mode='row_letters',
                        row_letters=[t.getPlainText() for t in canvas.row_letter_items()])
        automatic = self.auto_lettering_checkbox.isChecked() and bool(self.letter_line_edit.text())
        before = state(self)
        original = [p for _, _, p in panels(roots)]
        info = {id(p): entry for p, entry in zip(original, before['panels'])}
        for p in original:
            saved = info[id(p)]['letters']
            if len(saved) > 1:
                raise ValueError('Multiple letters require clarification')
            policy = json.loads(getattr(p, POLICY, '{}'))
            if saved:
                base = dict(saved[0])
                if automatic:
                    base.pop('text', None)
                    policy.pop('text', None)
                    policy.update(visible=True, base=base)
                else:
                    policy.update(automatic_text=False, visible=True, text=saved[0]['text'], base=base)
            else:
                policy['visible'] = False
            setattr(p, POLICY, json.dumps(policy))
        expected = list(roots)
        a, b = first_row - 1, second_row - 1
        expected[a], expected[b] = expected[b], expected[a]
        roots[:] = expected
        native_text = {}
        if automatic:
            # Native relettering owns text; our policies preserve styling only.
            for p in original:
                for annotation in letters(p):
                    annotation._letter_source_html = None
            BaseGUI.update_letters(self)
            native_text = {id(p): [a.getPlainText() for a in letters(p)] for p in original}
            self.update_letters()
        canvas.update()
        canvas.repack_all()
        canvas.update_letters_required.emit()
        canvas.update_text_rows.emit()
        canvas.update_size()
        canvas.repaint()
        after = state(self)
        objects = [p for _, _, p in panels(roots)]
        aligned = [{**info[id(p)], 'panel_id': entry['panel_id']} for p, entry in zip(objects, after['panels'])]
        if automatic:
            aligned = [{**entry, 'letters': [
                {**style, 'text': native_text[id(p)][i]} for i, style in enumerate(entry['letters'])
            ]} for p, entry in zip(objects, aligned)]
        from .figure_state import changes
        if any(x is not y for x, y in zip(roots, expected)) or changes({**before, 'panels': aligned}, after):
            raise ValueError('ROW_SWAP_VERIFICATION_FAILED')
        return dict(action='swap_rows', changed=int(a != b), matched_panel_ids=[], changed_panel_ids=[],
                    first_row=first_row, second_row=second_row, completion_verified=True, lettering_mode='automatic_position' if automatic else 'preserved', aligned_before=aligned)

    def reverse_selected_row(self, expected_selection_token=None, validate_only=False):
        selection = selection_state(self)
        if expected_selection_token and expected_selection_token != selection['token']:
            raise ValueError('SELECTION_CHANGED: Inspect the current selection before editing')
        if selection['stale_selection'] or len(selection['containing_row_paths']) != 1:
            raise ValueError('CLARIFICATION_REQUIRED: Select one horizontal image row or panels within exactly one row. No edit submitted.')
        path = selection['containing_row_paths'][0]
        items = self.paint.EZFIG_panel.shapes_to_draw
        row = None
        for index in path:
            row = [obj for obj in items if isinstance(obj, Group)][index]
            items = row.content
        if validate_only:
            return
        before = state(self)
        originals = [p for _, _, p in panels(self.paint.EZFIG_panel.shapes_to_draw)]
        info = {id(p): entry for p, entry in zip(originals, before['panels'])}
        row_before = list(row.content)
        replacement = {id(old): new for old, new in zip(row_before, reversed(row_before))}
        expected_objects = [replacement.get(id(p), p) for p in originals]
        annotations = {id(p): list(p.annotations or []) for p in originals}
        for p in originals:
            saved = info[id(p)]
            policy = json.loads(getattr(p, POLICY, '{}'))
            if len(saved['letters']) > 1:
                raise ValueError('Multiple panel letters require clarification')
            if saved['letters']:
                policy.update(automatic_text=False, visible=True, text=saved['letters'][0]['text'], base=dict(saved['letters'][0]))
            else:
                policy['visible'] = False
            setattr(p, POLICY, json.dumps(policy))
        row.content[:] = list(reversed(row_before))
        row.update()
        canvas = self.paint.EZFIG_panel
        canvas.update()
        canvas.repack_all()
        canvas.update_letters_required.emit()
        canvas.update_text_rows.emit()
        canvas.set_current_selection(row)
        canvas.update_size()
        canvas.repaint()
        after_objects = [p for _, _, p in panels(canvas.shapes_to_draw)]
        after = state(self)
        aligned = [{**info[id(p)], 'panel_id': current['panel_id']} for p, current in zip(after_objects, after['panels'])]
        from .figure_state import changes
        if (row.content != list(reversed(row_before)) or after_objects != expected_objects
                or changes({**before, 'panels': aligned}, after)
                or any(list(p.annotations or []) != annotations[id(p)] for p in after_objects)):
            raise ValueError('REVERSE_VERIFICATION_FAILED: Wrong order or altered image letters/annotations; rolled back')
        return dict(action='reverse_selected_row', changed=int(len(row_before) > 1), matched_panel_ids=[], changed_panel_ids=[],
                    selected_row_path=path, completion_verified=True,
                    before_letters=[[a['text'] for a in info[id(p)]['letters']] for p in row_before],
                    after_letters=[[a['text'] for a in info[id(p)]['letters']] for p in row.content],
                    aligned_before=aligned)

    def delete_last_rows(self, count=2, validate_only=False):
        canvas = self.paint.EZFIG_panel
        rows = list(canvas.shapes_to_draw)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError('Invalid row count; use a positive integer. No rows deleted')
        requested_count = count
        count = min(count, len(rows))
        # A visual row is unambiguous only for flat horizontal image groups.
        if any(not isinstance(row, Group) or row.isText or str(row.orientation).upper() != 'X'
               or not row.content or any(not isinstance(p, Image2D) or p.isText for p in row.content) for row in rows):
            raise ValueError('CLARIFICATION_REQUIRED: Rows are not simple horizontal image groups. No deletion submitted; inspect the nested/free-canvas/text structure first.')
        if validate_only:
            return
        before = state(self)
        keep = rows[:-count] if count else rows
        removed_count = sum(len(row.content) for row in rows[-count:])
        survivors = [p for row in keep for p in row.content]
        saved = before['panels'][:len(survivors)]
        canvas.shapes_to_draw = keep
        canvas.set_current_selection(None)
        canvas.update()
        canvas.repack_all()
        canvas.update_letters_required.emit()
        canvas.update_text_rows.emit()
        canvas.update_size()
        canvas.repaint()
        after = state(self)
        if (list(canvas.shapes_to_draw) != keep or [p for _, _, p in panels(canvas.shapes_to_draw)] != survivors
                or len(after['panels']) != len(before['panels']) - removed_count
                or [p['letters'] for p in after['panels']] != [p['letters'] for p in saved]):
            raise ValueError('DELETE_VERIFICATION_FAILED: Wrong targets or changed surviving letters; entire deletion rolled back')
        return dict(action='delete_rows', changed=count, rows_deleted=count,
                    rows_requested=requested_count, count_clamped=requested_count > count,
                    rows_before=len(rows), rows_after=len(keep),
                    deleted_original_row_indices=list(range(len(keep), len(rows))),
                    remaining_original_row_indices=list(range(len(keep))),
                    image_count_before=len(before['panels']), image_count_after=len(after['panels']),
                    removed_images=before['panels'][len(survivors):],
                    completion_verified=True, changed_panel_ids=[], matched_panel_ids=[],
                    surviving_before=saved)

    def ungroup_all_images(self, validate_only=False):
        original = state(self)
        targets = list(panels(self.paint.EZFIG_panel.shapes_to_draw))
        grouped_before = sum(bool(gp) for gp, _, _ in targets)
        if any(len(p['letters']) > 1 for p in original['panels']):
            raise ValueError('Multiple panel letters require clarification before ungrouping')
        if validate_only:
            return
        if not grouped_before:
            canvas = self.paint.EZFIG_panel
            before_geometry = [(p.x(), p.y(), p.width(), p.height()) for _, _, p in targets]
            canvas.set_current_selection(None)
            canvas.update()
            canvas.repack_all()
            canvas.update_size()
            canvas.repaint()
            layout_changed = before_geometry != [(p.x(), p.y(), p.width(), p.height()) for _, _, p in targets]
            return dict(action='ungroup', changed=0, groups_removed=0,
                        image_count_before=len(targets), image_count_after=len(targets),
                        grouped_images_before=0, grouped_images_after=0, remaining_groups=0,
                        already_ungrouped=True, layout_changed=layout_changed, automatic_layout_applied=True,
                        changed_panel_ids=[], matched_panel_ids=[])
        for (_, _, image), saved in zip(targets, original['panels']):
            existing = json.loads(getattr(image, POLICY, '{}'))
            if saved['letters']:
                actual = saved['letters'][0]
                existing.update(automatic_text=False, visible=True, text=actual['text'], base=dict(actual))
            else:
                existing['visible'] = False
            setattr(image, POLICY, json.dumps(existing))
        groups = 0
        def flatten(items):
            nonlocal groups
            result = []
            for item in items:
                if isinstance(item, Group) and not item.isText:
                    groups += 1
                    result.extend(flatten(item.content))
                else:
                    result.append(item)
            return result
        self.paint.EZFIG_panel.shapes_to_draw = flatten(self.paint.EZFIG_panel.shapes_to_draw)
        canvas = self.paint.EZFIG_panel
        # Follow all_as_single's native refresh, without its extra undo signal.
        for _, _, image in targets:
            canvas.force_update_size_of_parent.emit(image)
        canvas.update()  # invalidates _layout_dirty; repaint alone does not
        canvas.repack_all()
        canvas.update_size()
        canvas.update_letters_required.emit()
        canvas.update_text_rows.emit()
        canvas.set_current_selection(None)
        canvas.repaint()
        after = state(self)
        remaining_grouped = sum(bool(p['group_path']) for p in after['panels'])
        remaining_groups = sum(isinstance(obj, Group) and not obj.isText for obj in self.paint.EZFIG_panel.shapes_to_draw)
        if remaining_grouped or remaining_groups:
            raise ValueError('Ungroup verification failed: image groups remain; rolled back')
        if [p['filename'] for p in after['panels']] != [p['filename'] for p in original['panels']] or [p['letters'] for p in after['panels']] != [p['letters'] for p in original['panels']]:
            raise ValueError('Ungroup verification failed: images or letters changed')
        return dict(action='ungroup', changed=groups, groups_removed=groups,
                    grouped_images_before=grouped_before, grouped_images_after=remaining_grouped,
                    remaining_groups=remaining_groups, automatic_layout_applied=True, layout_changed=True, already_ungrouped=False,
                    image_count_before=len(targets), image_count_after=len(after['panels']),
                    changed_panel_ids=[p['panel_id'] for p in after['panels']],
                    matched_panel_ids=[p['panel_id'] for p in after['panels']])

    def remove_scale_bars_all(self, validate_only=False):
        """Remove ScaleBar annotations across all panels, preserving other annotations."""
        from batoolset.drawings.shapes.scalebar import ScaleBar
        targets = list(panels(self.paint.EZFIG_panel.shapes_to_draw))
        changed = ['/'.join(map(str, [*gp, ix])) for gp, ix, image in targets
                   if any(isinstance(a, ScaleBar) for a in image.annotations or [])]
        before = sum(isinstance(a, ScaleBar) for _, _, image in targets for a in image.annotations or [])
        if validate_only:
            return
        for _, _, image in targets:
            if any(isinstance(a, ScaleBar) for a in image.annotations or []):
                image.annotations = [a for a in image.annotations if not isinstance(a, ScaleBar)]
        after = sum(isinstance(a, ScaleBar) for _, _, image in targets for a in image.annotations or [])
        if after:
            raise ValueError('Scale-bar removal verification failed')
        return dict(action='remove_scale_bars', changed=len(changed), changed_panel_ids=changed,
                    matched_panel_ids=['/'.join(map(str, [*gp, ix])) for gp, ix, _ in targets],
                    scale_bars_before=before, scale_bars_after=after, removed=before,
                    scope='all', panels_inspected=len(targets))

    def edit_panel_letters(self, action='style', scope='all', group_path=None,
                           panel_ids=None, placement=None, font_family=None,
                           font_size=None, color_value=None, background=None,
                           start_letter=None, replace_overrides=False, validate_only=False,
                           removal_request=None, text=None, bold=None, italic=None, underline=None):
        if text is not None:
            # "rename g to G'": one panel's own letter text (it had no operation: the model searched until
            # stopped); a list, one text per panel_ids entry: "numbers instead of letters" in one call
            # (nine calls hit the chat's step limit, 2026-11-12)
            texts = text if isinstance(text, list) else [text]
            if action != 'style' or scope != 'panels' or not panel_ids or len(panel_ids) != len(texts):
                raise ValueError('text sets the letters of the panels named in panel_ids: action=style, scope=panels, and '
                                 'one text per panel_ids entry (a string for one panel, a list for several). '
                                 'For an alphabetic sequence use action=renumber with start_letter. No edit performed.')
            if any(not isinstance(t, str) or not t.strip() or len(t.strip()) > 12 for t in texts):
                raise ValueError('text must be the new letter, 1 to 12 characters. No edit performed.')
            texts = [t.strip() for t in texts]
        if action == 'remove':
            request = (removal_request or '').lower()
            # "no letters", "get rid of the letters", "sans lettres" ask for it too (2026-11-12)
            if (not re.search(r"\b(remove|hide|delete|erase|clear|no|without|drop|strip|lose|kill|off|rid|"
                              r"take\s+(?:out|away)|don'?t\s+want|enl[eè]ve\w*|supprime\w*|retire\w*|sans|pas\s+de)\b", request)
                    or not re.search(r'\b(letters?|lettering|labels?|lettres?)\b', request)
                    or re.search(r'\b(swap|exchange|relabel|rename|replace)\b', request)):
                raise ValueError('CLARIFICATION_REQUIRED: Removing letters requires removal_request quoting an explicit user request to remove/hide letters. Never remove letters to swap images or rename letters. Ask which meaning was intended; no edit performed.')
        if action not in ('style', 'remove', 'restore', 'renumber'):
            raise ValueError('action must be style, remove, restore or renumber')
        if scope not in ('all', 'group', 'panels', 'selection'):
            raise ValueError('scope must be all, group, panels or selection')
        if scope == 'group' and group_path is None:
            raise ValueError('group_path is required for group scope')
        if scope == 'panels' and not panel_ids:
            raise ValueError('panel_ids from inspect_panel_letters are required')
        from pyfigures.gui.row_letters import normalise_layout
        row_mode = normalise_layout(getattr(self.paint.EZFIG_panel, 'letter_layout', None)) == 'row'
        if row_mode and action == 'style' and scope != 'all':
            raise ValueError('The figure has one letter per row (outside the rows): those letters share one '
                             'style, so style them with scope="all".')
        if placement is not None and re.search(r'\b(outside|outer|margin|per row|beside)\b', str(placement).lower()):
            # "put letters outside": a model passed placement="outside", got
            # "Use a corner", undid the row letters it had just set and searched
            # until stopped (2026-11-06)
            if row_mode:
                raise ValueError('ALREADY_DONE: the letters are already outside the panels (one per row, in a '
                                 'margin on the left). Nothing to change; report that to the user.')
            raise ValueError('Letters outside the panels: call set_panel_letter_layout(letter_layout="row") '
                             '(one letter per row, in a margin left of the row). Letters of single panels '
                             'always sit in a corner inside the panel; placement takes a corner.')
        if placement is not None:
            placement = ' '.join(placement.lower().replace('-', ' ').split())
            placement = placement.replace('upper', 'top').replace('lower', 'bottom')
            if placement in ('center', 'centre', 'middle', 'center center', 'centre centre'):
                placement = 'center_h center_v'
            if placement not in ('top left', 'top right', 'bottom left', 'bottom right', 'center_h center_v'):
                raise ValueError('Use a corner (top left, top right, bottom left, bottom right)')
        if font_family is not None and (not isinstance(font_family, str) or not font_family.strip()):
            raise ValueError('font_family must be a nonempty font name')
        if font_size is not None and (not isinstance(font_size, (int, float)) or not 1 <= font_size <= 200):
            raise ValueError('font_size must be between 1 and 200 pt')
        foreground = color(color_value) if color_value is not None else None
        fill = color(background, True) if background is not None else None
        if start_letter is not None and not re.fullmatch('[A-Za-z]{1,3}', start_letter):
            raise ValueError('start_letter must contain one to three letters. Automatic lettering is alphabetic only: '
                             'numbers (1, 2, 3) and roman numerals are not available as a sequence. Give every panel its '
                             'text in ONE call instead: action=style, scope=panels, panel_ids=[every panel ID in reading '
                             'order], text=["1", "2", ...] (or "I", "II", ...). Tell the user these labels no longer '
                             'follow when panels are added or moved. Do not search for another operation. No edit performed.')
        all_panels = list(panels(self.paint.EZFIG_panel.shapes_to_draw))
        if scope == 'panels':
            # panel_ids=["B"]: the visible letter names the panel too ("remove the letter of b"
            # was refused as "No matching image panels", 2026-11-12)
            by_letter = {}
            for path, index, panel in all_panels:
                shown = [a.getPlainText().strip().casefold() for a in letters(panel)]
                if len(shown) == 1:
                    by_letter.setdefault(shown[0], []).append('/'.join(map(str, (*path, index))))
            resolved = []
            from .gui_selection import panel_number
            for ref in panel_ids:
                ref = str(ref).strip()
                numbered = panel_number(ref, all_panels)
                if numbered == 'missing':
                    raise ValueError(f'There is no panel {ref}; the figure has {len(all_panels)} panels. No edit performed.')
                if numbered is not None:
                    ref = '/'.join(map(str, (*numbered[0], numbered[1])))
                elif not re.fullmatch(r'\d+(?:/\d+)*', ref):
                    hits = by_letter.get(ref.casefold(), [])
                    if len(hits) != 1:
                        raise ValueError(f'No single panel shows the letter {ref!r}; use the panel IDs of '
                                         'inspect_panel_letters (like "0/1"). No edit performed.')
                    ref = hits[0]
                resolved.append(ref)
            panel_ids = resolved
        text_for = dict(zip(panel_ids, texts)) if text is not None else {}
        if text is not None and len(text_for) != len(texts):
            raise ValueError('panel_ids names the same panel twice. No edit performed.')
        selected = self.paint.EZFIG_panel.selected_shape
        selected = selected if isinstance(selected, list) else [selected]
        selected_ids = set()
        for item in selected:
            if isinstance(item, Group):
                selected_ids.update(id(p) for _, _, p in panels(item.content))
            elif item is not None:
                selected_ids.add(id(item))
        candidates = []
        for path, index, panel in all_panels:
            pid = '/'.join(map(str, (*path, index)))
            if scope == 'group' and tuple(path[:len(group_path)]) != tuple(group_path):
                continue
            if scope == 'panels' and pid not in panel_ids:
                continue
            if scope == 'selection' and id(panel) not in selected_ids:
                continue
            candidates.append((pid, panel))
        if not candidates:
            raise ValueError('No matching image panels')
        if scope == 'panels' and set(panel_ids) - {pid for pid, _ in candidates}:
            raise ValueError('Unknown panel ID; inspect again')
        from batoolset.strings.tools import increment_letter
        planned_text = {}
        if action in ('restore', 'renumber'):
            from .letter_sequence import plan_letters
            entries = [('/'.join(map(str, (*gp, ix))), [a.getPlainText() for a in letters(panel)] or [json.loads(getattr(panel, POLICY, '{}')).get('text')]) for gp, ix, panel in all_panels]
            entries = [(pid, [t for t in texts if t]) for pid, texts in entries]
            planned_text = plan_letters(entries, [pid for pid, _ in candidates], 'renumber' if scope == 'all' else action, (start_letter or 'a') if scope == 'all' else start_letter, self.letter_line_edit.text() or 'a', increment_letter)
        if validate_only:
            return {'matched': len(candidates)}
        changed, skipped = [], []
        before_states = {pid: [letter_info(a) for a in letters(panel)] for pid, panel in candidates}
        row_style_before = self._row_letter_style() if row_mode else None
        for pid, panel in candidates:
            existing = letters(panel)
            policy = json.loads(getattr(panel, POLICY, '{}'))
            if not policy.get('base') and existing:
                policy['base'] = letter_info(existing[0])
            if action == 'style' and not existing:
                if not row_mode:       # lettered per row: no letter in a panel is expected
                    skipped.append({'panel_id': pid, 'reason': 'No panel letter; use restore to add it'})
                continue
            local = set(policy.get('local_fields', []))
            if replace_overrides and scope == 'all':
                # Replace only the properties explicitly supplied, not the whole
                # accepted appearance (which would resurrect the old base font).
                requested_fields = {'placement': placement, 'font_family': font_family,
                    'font_size': font_size, 'color': color_value, 'background': background}
                local.difference_update(key for key, value in requested_fields.items() if value is not None)
            def assign(key, value):
                if scope != 'all' or replace_overrides or key not in local:
                    policy[key] = value
                    if scope != 'all':
                        local.add(key)
            if action == 'remove':
                policy['visible'] = False
            else:
                policy['visible'] = True
                if action in ('restore', 'renumber'):
                    policy['text'] = planned_text[pid]
                    policy['automatic_text'] = scope == 'all'
                    if scope == 'all':
                        policy.pop('text', None)
                        policy.get('base', {}).pop('text', None)
                if text is not None:
                    policy['text'] = text_for[pid]
                    policy['automatic_text'] = False
                if placement is not None:
                    assign('placement', placement)
                if font_family is not None:
                    assign('font_family', font_family)
                if font_size is not None:
                    assign('font_size', font_size)
                if foreground is not None:
                    assign('color', foreground)
                if background is not None:
                    assign('background', fill)
                # "the letter bold on every rotated panel": per panel, as the other fields
                for key, value in (('bold', bold), ('italic', italic), ('underline', underline)):
                    if value is not None:
                        assign(key, bool(value))
            policy['local_fields'] = sorted(local)
            setattr(panel, POLICY, json.dumps(policy, sort_keys=True))
            changed.append(pid)
        if scope == 'all' and action == 'remove':
            self.auto_lettering_checkbox.blockSignals(True)
            self.auto_lettering_checkbox.setChecked(False)
            self.auto_lettering_checkbox.blockSignals(False)
        elif action in ('restore', 'renumber') and scope == 'all':
            self.auto_lettering_checkbox.blockSignals(True)
            self.auto_lettering_checkbox.setChecked(True)
            self.auto_lettering_checkbox.blockSignals(False)
            self.letter_line_edit.blockSignals(True)
            self.letter_line_edit.setText(start_letter or 'a')
            self.letter_line_edit.blockSignals(False)
        if scope == 'all' and action != 'remove':
            if placement is not None:
                self.serializable_font.placement = Position(placement)
            if font_family is not None:
                self.serializable_font.setFamily(font_family)
            if font_size is not None:
                self.serializable_font.setPointSizeF(font_size)
            if foreground is not None:
                self.serializable_font.foreground = int(foreground[1:], 16)
            if background is not None:
                self.serializable_font.background = None if fill is None else int(fill[1:], 16)
        self.update_letters()
        changed = [pid for pid, panel in candidates if before_states[pid] != [letter_info(a) for a in letters(panel)]]
        report = {'matched': len(candidates), 'matched_panel_ids': [pid for pid, _ in candidates],
                  'changed': len(changed), 'changed_panel_ids': changed,
                  'skipped': skipped, 'scope': scope, 'action': action,
                  'warnings': ['Explicit colors are honored; white on bright image content may be hard to see.'] if foreground == '#ffffff' and fill is None else []}
        if row_mode:
            # the row letters are drawn from the figure letter font set above:
            # report them, or "0 changed" sent the chat looking for another
            # tool for a minute although the edit was done (2026-11-06)
            restyled = self._row_letter_style() != row_style_before
            report['letter_layout'] = 'row'
            report['row_letters_restyled'] = (
                [t.getPlainText() for _, t in self.paint.EZFIG_panel._row_letter_texts()] if restyled else [])
            if placement is not None:
                report['warnings'].append('Row letters always sit outside the rows on the left; placement '
                                          'only applies to letters inside panels.')
        return report

    def _row_letter_style(self):
        f = self.serializable_font
        return (f.toString(), getattr(f, 'foreground', None), getattr(f, 'background', None))

    def swap_panels(self, first, second, target='images', validate_only=False):
        if target not in ('images', 'letters'):
            raise ValueError('CLARIFICATION_REQUIRED: Ask whether to exchange image panels or only their letter text. target must be images or letters.')
        entries = list(panels(self.paint.EZFIG_panel.shapes_to_draw))
        def resolve(value):
            from .gui_selection import panel_number
            numbered = panel_number(value, entries)
            if numbered not in (None, 'missing'):
                return numbered
            matches = [(path, index, p) for path, index, p in entries
                       if '/'.join(map(str, (*path, index))) == value
                       or any(a.getPlainText() == value for a in letters(p))]
            if len(matches) != 1:
                available = [a.getPlainText() for _, _, panel in entries for a in letters(panel)]
                if not matches:
                    raise ValueError('UNKNOWN_PANEL_REFERENCE: '+str(value)+' does not identify an existing panel. Available visible letters: '+', '.join(available)+'. No edit performed. Ask the user for a corrected reference; do not substitute a guessed panel ID, ordinal or last panel.')
                raise ValueError('AMBIGUOUS_PANEL_REFERENCE: '+str(value)+' identifies multiple panels. Ask the user which panel; do not substitute a guessed panel ID. No edit performed.')
            return matches[0]
        a, b = resolve(first), resolve(second)
        if a[2] is b[2]:
            if validate_only:return
            pid='/'.join(map(str,(*a[0],a[1])))
            current=[p for p in state(self)['panels'] if p['panel_id']==pid]
            return {'action':'swap','target':target,'changed_panel_ids':[],'changed':0,
                    'matched':1,'matched_panel_ids':[pid],'same_panel':True,
                    'before_panels':current,'after_panels':current,
                    'message':'No change: both references identify the same panel '+pid}

        if len(letters(a[2])) != 1 or len(letters(b[2])) != 1:
            raise ValueError('Swap currently requires exactly one visible letter on each target')
        if validate_only:
            return
        before = state(self)
        if target == 'letters':
            for item, other in ((a, b), (b, a)):
                policy = json.loads(getattr(item[2], POLICY, '{}'))
                policy['text'] = next(p['letters'][0]['text'] for p in before['panels']
                                      if p['panel_id'] == '/'.join(map(str, (*other[0], other[1]))))
                policy['automatic_text'] = False
                policy['visible'] = True
                setattr(item[2], POLICY, json.dumps(policy))
            self.update_letters()
        else:
            import copy
            import tempfile
            from pathlib import Path
            from .existing_tools import checked, tools
            with tempfile.TemporaryDirectory(prefix='swap_') as folder:
                path = Path(folder) / 'swap.pyf'
                self._save_state_to_file(str(path))
                root = ET.parse(path).getroot()
                def locate(ref):
                    container = root
                    for group in ref[0]:
                        container = [n for n in container if n.tag == 'Group'][group].find('content')
                    node = [n for n in container if n.tag == 'Image2D'][ref[1]]
                    return container, list(container).index(node), node
                ca, ia, na = locate(a)
                cb, ib, nb = locate(b)
                # Letter identity and appearance belong to the destination slot.
                for node, slot in ((na, copy.deepcopy(nb)), (nb, copy.deepcopy(na))):
                    annotations = node.find('annotations')
                    if annotations is None:
                        annotations = ET.SubElement(node, 'annotations')
                    for label in list(annotations):
                        if label.tag == 'TAText2D' and _decode(label.findtext('is_letter')) is True:
                            annotations.remove(label)
                    annotations.extend(copy.deepcopy(label) for label in slot.findall('annotations/TAText2D')
                                       if _decode(label.findtext('is_letter')) is True)
                    old = node.find(POLICY)
                    if old is not None:
                        node.remove(old)
                    if slot.find(POLICY) is not None:
                        node.append(copy.deepcopy(slot.find(POLICY)))
                ca.remove(na)
                cb.remove(nb)
                if ca is cb:
                    for index, node in sorted(((ia, nb), (ib, na))):
                        ca.insert(index, node)
                else:
                    ca.insert(ia, nb)
                    cb.insert(ib, na)
                path.write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
                original = path.read_bytes()
                checked(tools.recompute_layout(str(path)))
                path.write_bytes(carry_policies(original, path.read_bytes()))
                self.reload_state(str(path), append=False, skip_add_to_stack=True)
        after = state(self)
        ids = ['/'.join(map(str, (*item[0], item[1]))) for item in (a, b)]
        if after['visible_letter_count'] != before['visible_letter_count']:
            raise RuntimeError('Swap verification failed: letter count changed')

        def slot_letters(panel):
            # an automatic letter is black on a bright image and white on a dark one: its
            # colour follows the image moved into the slot ("swap c and e" failed on every
            # try, 2026-11-12); a colour set by hand stays part of the slot
            pinned = 'color' in (panel.get('override') or {}).get('local_fields', [])
            return [a if pinned else {k: v for k, v in a.items() if k != 'color'} for a in panel['letters']]
        for old, new in zip(before['panels'], after['panels']):
            if old['panel_id'] not in ids and old != new:
                raise RuntimeError('Swap verification failed: unrelated panel changed')
            if target == 'images' and slot_letters(old) != slot_letters(new):
                raise RuntimeError('Swap verification failed: slot lettering changed')
        affected = [p for p in after['panels'] if p['panel_id'] in ids]
        previous = [p for p in before['panels'] if p['panel_id'] in ids]
        field = 'filename' if target == 'images' else 'letters'
        if target == 'images' and [p[field] for p in affected] != [p[field] for p in reversed(previous)]:
            raise RuntimeError('Swap verification failed: image identities were not exchanged')
        if target == 'letters' and [p['letters'][0]['text'] for p in affected] != [p['letters'][0]['text'] for p in reversed(previous)]:
            raise RuntimeError('Swap verification failed: letter texts were not exchanged')
        return {'action': 'swap', 'target': target, 'changed_panel_ids': ids, 'changed': 2,
                'matched': 2, 'before_panels': previous, 'after_panels': affected}

    def closeEvent(self, event):
        session = getattr(self, '_live_session', None)
        if session is not None:
            session.auto_recover()
        super().closeEvent(event)
        if event.isAccepted():
            close_scene_figures(self)
            from .live_structure import uninstall_canvas
            uninstall_canvas(self.paint.EZFIG_panel)
