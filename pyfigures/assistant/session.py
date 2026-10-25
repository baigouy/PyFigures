"""Live session of the open figure editor: requests from the local HTTP
bridge run on the Qt thread, with revisions, recovery copies and one undo
step per edit. State lives in ``pyfigures.assistant.runtime_dir()``.
Ported from the MCP partner prototype by packaging/port_assistant.py."""
import os
import sys
from pathlib import Path
import argparse
import hashlib
import html
import json
import queue
import secrets
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pyfigures.assistant import runtime_dir
from pyfigures.gui.pfgui import EZFIG_GUI, QApplication, QTimer, object_to_xml, TAText2D, Image2D
from qtpy.QtCore import QSettings
from .partner_gui import PartnerGUI
EZFIG_GUI = PartnerGUI

STATE = runtime_dir()


class Session:
    def __init__(self, window, recovery_dir=None):
        self.window = window
        self.id = str(uuid.uuid4())
        self.revision = 0
        self.fingerprint = None
        self.requests = queue.Queue(maxsize=100)
        self.results = {}
        from .recovery import Recovery
        self.runtime = STATE
        self.recovery = Recovery(self, recovery_dir or STATE)
        window._live_session = self
        from .pointer_context import PointerContext
        self.pointer = PointerContext(self)
        self.timer = QTimer(window)
        self.timer.timeout.connect(self.drain)
        self.timer.start(40)
        self.recovery_timer = QTimer(window)
        self.recovery_timer.timeout.connect(self.auto_recover)
        self.recovery_timer.start(1500)

    def auto_recover(self):
        try:
            self.sync()
        except Exception as exc:
            self.recovery.error = str(exc)

    def sync(self):
        w = self.window
        w._flush_pending_checkpoints()
        w.paint.EZFIG_panel.repaint()
        data = object_to_xml(list(w.paint.EZFIG_panel.shapes_to_draw) + [w.serializable_font], is_list=True)
        metadata = (w.main_space_spinner.value(), w.auto_lettering_checkbox.isChecked(),
                    w.letter_line_edit.text(), str(w.paint.EZFIG_panel.page_background), w.current_file)
        staged = STATE / ('original_' + self.id)
        metadata += tuple((ext, hashlib.sha256((staged / ('current' + ext)).read_bytes()).hexdigest())
                          for ext in ('.caption.json', '.stats.json', '.alttext.json', '.target.json')
                          if (staged / ('current' + ext)).exists())
        digest = hashlib.sha256((data + repr(metadata)).encode()).hexdigest()
        if digest != self.fingerprint:
            self.revision += 1
            self.fingerprint = digest
            self.recovery.capture()

    def snapshot(self):
        self.sync()
        from .gui_selection import sync_editor,native_dialog_titles
        sync_editor(self)
        from .partner_gui import panels, letters, state as lettering_state, selection_state
        from .figure_state import specification
        from .pointer_context import geometry
        references = [{'panel_id': '/'.join(map(str, (*gp, ix))), 'group_path': list(gp),
                       'image_index': ix, 'letters': [a.getPlainText() for a in letters(p)],
                       'rotation_degrees': getattr(p, 'theta', 0), 'geometry': geometry(p)}
                      for gp, ix, p in panels(self.window.paint.EZFIG_panel.shapes_to_draw)]
        from .advanced_annotations import describe, text_inspection_record
        annotations = [text_inspection_record(a, '/'.join(map(str, (*gp, ix))), gp, ix,
                        index, sum(isinstance(v, TAText2D) for v in p.annotations[:index]))
                       for gp, ix, p in panels(self.window.paint.EZFIG_panel.shapes_to_draw)
                       for index, a in enumerate(p.annotations or []) if isinstance(a, TAText2D) and not a.is_letter]
        rois=[dict(panel_id='/'.join(map(str,(*gp,ix))),annotation_index=index,**describe(a))
              for gp,ix,p in panels(self.window.paint.EZFIG_panel.shapes_to_draw)
              for index,a in enumerate(p.annotations or [])
              if type(a).__name__ in ('Rectangle2D','Rect2D','Ellipse2D','Circle2D','Square2D','Line2D','Polygon2D','PolyLine2D','Freehand2D')]
        return {'session_id': self.id, 'revision': self.revision,
                'text_annotations': annotations,
                'roi_annotations': rois,
                'selection': selection_state(self.window),
                'verified_letter_specification': specification(lettering_state(self.window)),
                'panel_references': references,
                'last_canvas_click': self.pointer.snapshot(),
                'annotation_editor_status': getattr(self, '_annotation_editor_status', 'closed'),
                'annotation_editor_open': bool(getattr(self, '_annotation_editor_pending', False)),
                'annotation_editor_panel_id': getattr(self, '_annotation_editor_panel_id', None),
                'native_gui_available': True,
                'native_dialogs': native_dialog_titles(self),
                'native_gui_jobs': list(self.native_gui.jobs.values())[-10:] if hasattr(self,'native_gui') else [],
                'path': self.window.current_file, 'dirty': self.window._dirty,
                'row_spacing_px': self.window.main_space_spinner.value(),
                'persistence': {'source_saved': not self.window._dirty,
                                'recovery_snapshot': self.recovery.latest,
                                'recovery_error': self.recovery.error},
                'lettering': {'automatic': self.window.auto_lettering_checkbox.isChecked(),
                              'default_position': str(self.window.serializable_font.placement),
                              'bulk_operation': 'edit_panel_letters'},
                'objects': [{'id': str(i), 'type': type(obj).__name__,
                             'image_count': count_images(obj),
                             'text': label_text(obj).getPlainText() if label_text(obj) else None}
                            for i, obj in enumerate(self.window.paint.EZFIG_panel.shapes_to_draw)],
                'capabilities': ['bulk_letters', 'letter_state', 'save_copy', 'recover', 'add_label', 'set_label', 'preview', 'undo', 'redo',
                                 'arrange_rows', 'existing_read', 'existing_batch', 'original_tool']}

    def execute(self, req):
        from .gui_selection import sync_editor
        sync_editor(self)
        if req['operation'] == 'manual_guide':
            from .manual_help import explain
            return explain(req.get('arguments', {}).get('topic', 'overview'))
        if not getattr(self, '_action_passthrough', False):
            op = req['operation']
            controls = {'action_begin', 'action_finish', 'action_apply', 'action_discard', 'action_undo', 'action_redo', 'action_recover', 'action_continue'}
            if op in controls:
                if not hasattr(self, 'actions'):
                    from .assistant_actions import ActionManager
                    self.actions = ActionManager(self)
                args = req.get('arguments', {})
                method = {'action_begin': 'begin', 'action_finish': 'finish', 'action_apply': 'apply',
                          'action_discard': 'discard', 'action_undo': 'undo', 'action_redo': 'redo', 'action_recover': 'recover', 'action_continue': 'continue_action'}[op]
                return getattr(self.actions, method)(**args)
            if op in ('inspect_native_gui','use_native_gui','open_native_menu','native_gesture','native_drop_files','native_keys'):
                if not hasattr(self,'native_gui'):
                    from .native_gui import NativeGUI
                    self.native_gui=NativeGUI(self)
                args=dict(req.get('arguments',{}))
                if op=='inspect_native_gui': return self.native_gui.inventory(**args)
                self.sync()
                if req.get('session_id')!=self.id or req.get('expected_revision')!=self.revision:
                    raise ValueError('STALE_STATE: Inspect before interacting with native GUI')
                args['request_id']=req.get('request_id')
                method={'use_native_gui':'operate','open_native_menu':'open_menu','native_gesture':'gesture','native_drop_files':'drop_files','native_keys':'keys'}[op]
                return getattr(self.native_gui,method)(**args)
            if op == 'edit_annotation_properties':
                from .gui_selection import sync_editor
                sync_editor(self)
                if getattr(self, '_annotation_editor_pending', False):
                    # the panel's editor is open: change its draft (OK/Cancel decide)
                    self.sync()
                    if req.get('session_id') != self.id or req.get('expected_revision') != self.revision:
                        raise ValueError('STALE_STATE: Inspect before editing the editor draft')
                    from .advanced_annotations import edit_draft
                    return edit_draft(self, **req.get('arguments', {}))
            if getattr(self, '_annotation_editor_pending', False) and op not in ('inspect', 'readability', 'inspect_annotation_objects', 'open_annotation_properties'):
                raise ValueError('ANNOTATION_EDITOR_OPEN: Finish or cancel the native editor before another tool action')
            if op in ('select_live_objects', 'open_annotation_editor', 'open_annotation_properties'):
                self.sync()
                if req.get('session_id') != self.id or req.get('expected_revision') != self.revision:
                    raise ValueError('STALE_STATE: Inspect before selecting or opening an editor')
                if op == 'open_annotation_properties':
                    from .advanced_annotations import open_properties
                    return open_properties(self, **req.get('arguments', {}))
                from .gui_selection import select, open_editor
                return select(self.window, **req.get('arguments', {})) if op == 'select_live_objects' else open_editor(self, **req.get('arguments', {}))
            if getattr(self, 'actions', None) and self.actions.active:
                return self.actions.dispatch(req)
            if op == 'readability':
                from .readability import inspect_readability
                return inspect_readability(self.window)
        if req['operation'] == 'readability':
            from .readability import inspect_readability
            return inspect_readability(self.window)
        if req['operation']=='submission_review':
            from .submission_review import review_live
            return review_live(self,dict(req.get('arguments',{})))
        request_id = req['request_id']
        signature = json.dumps(req, sort_keys=True)
        if request_id in self.results:
            old_signature, result = self.results[request_id]
            if signature != old_signature:
                raise ValueError('Request ID reused with different content')
            return result
        self.sync()
        op = req['operation']
        if op == 'inspect':
            result = self.snapshot()
        elif op == 'list_recoveries':
            result = {'snapshots': self.recovery.list()}
        else:
            if req.get('session_id') != self.id:
                raise ValueError('Session unavailable; inspect again')
            if req.get('expected_revision') != self.revision:
                raise ValueError(f'Stale revision; current revision is {self.revision}. Inspect and retry.')
            w = self.window
            panel = w.paint.EZFIG_panel
            args = req.get('arguments', {})
            if op == 'letter_state':
                from .partner_gui import state
                result = {**state(w), 'revision': self.revision}
            elif op == 'inspect_annotation_objects':
                from .advanced_annotations import inspect_objects
                result = inspect_objects(self, **args)
            elif op == 'edit_annotation_properties':
                from .advanced_annotations import edit
                result = edit(self, **args)
            elif op == 'bulk_letters':
                result = self.bulk_letters(args)
            elif op == 'roi_to_inset':
                result = self.bulk_letters(args, roi_inset=True)
            elif op == 'swap_rows':
                result = self.bulk_letters(args, row_swap=True)
            elif op == 'swap_panels':
                result = self.bulk_letters(args, swap=True)
            elif op == 'remove_scale_bars_all':
                result = self.bulk_letters(args, scale_bars=True)
            elif op == 'ungroup_all_images':
                result = self.bulk_letters(args, ungroup=True)
            elif op == 'delete_last_rows':
                result = self.bulk_letters(args, deletion=True)
            elif op == 'reverse_selected_row':
                result = self.bulk_letters(args, reverse_selection=True)
            elif op == 'recover':
                result = self.restore_recovery(args)
            elif op == 'save_copy':
                result = self.save_copy(args)
            elif op == 'original_tool':
                result = self.original_tool(args)
            elif op in ('arrange_rows', 'existing_read', 'existing_batch', 'letter_position'):
                from .existing_tools import arrange_rows, run, set_letter_position
                with tempfile.TemporaryDirectory(prefix='live_tools_', dir=STATE) as directory:
                    path = str(Path(directory) / 'snapshot.pyf')
                    w._save_state_to_file(path)
                    if op == 'existing_read':
                        result = {'results': run(path, args['calls'], read_only=True), **self.snapshot()}
                    else:
                        if op == 'letter_position':
                            response = set_letter_position(path, args['placement'])
                        elif op == 'arrange_rows':
                            response = arrange_rows(path, args.get('columns', 4),
                                args.get('row_width_px') or int(w.size_spinbox.value()),
                                args.get('spacing_px', 3))
                        else:
                            response = run(path, args['calls'])
                        # Original tools only touched a temporary snapshot so far.
                        if w.save_state(show_popup=False) is None:
                            raise RuntimeError('Could not checkpoint current document')
                        backup = str(Path(directory) / 'before.pyf')
                        w._save_state_to_file(backup)
                        old_path, old_dirty = w.current_file, w._dirty
                        old_history = (list(w.undo_stack), list(w.redo_stack), w.current_index, w.last_called_state)
                        try:
                            w.reload_state(path, append=False, skip_add_to_stack=True)
                            panel.repaint()
                            if w.save_state(show_popup=False) is None:
                                raise RuntimeError('Could not checkpoint edit')
                            w._mark_dirty()
                        except Exception:
                            w.reload_state(backup, append=False, skip_add_to_stack=True)
                            w.undo_stack, w.redo_stack, w.current_index, w.last_called_state = old_history
                            w.current_file = old_path
                            w._mark_dirty() if old_dirty else w._mark_clean()
                            w.update_button_state()
                            raise
                        w.current_file = old_path
                        result = {'operation_result': response, **self.snapshot()}
            elif op == 'preview':
                # Captures the visible canvas, including its current zoom.
                output = STATE / 'canvas.png'
                if not panel.grab().save(str(output)):
                    raise RuntimeError('Could not capture canvas')
                result = {'path': str(output), 'revision': self.revision}
            elif op in ('undo', 'redo'):
                getattr(w, op)()
                result = self.snapshot()
            elif op in ('add_label', 'set_label'):
                text = args['text']
                if not isinstance(text, str) or len(text) > 10000:
                    raise ValueError('Text must be a string of at most 10000 characters')
                escaped = html.escape(text).replace('\n', '<br>')
                target = None
                if op == 'set_label':
                    target = panel.shapes_to_draw[int(args['object_id'])]
                    target = label_text(target)
                    if target is None:
                        raise ValueError('Only top-level text labels are supported')
                    old_text = target.getHtmlText()
                else:
                    x, y = float(args.get('x', 20)), float(args.get('y', 20))
                    import math
                    if not all(math.isfinite(v) and abs(v) <= 100000 for v in (x, y)):
                        raise ValueError('Invalid label position')
                    label = TAText2D(escaped)
                    target = Image2D(x=x, y=y, width=max(100, label.width()),
                                     height=max(30, label.height()), isText=True, annotations=[label])
                # Capture existing unsaved user edits before the transaction.
                if w.save_state(show_popup=False) is None:
                    raise RuntimeError('Could not checkpoint current document')
                try:
                    if op == 'add_label':
                        panel.shapes_to_draw.append(target)
                    else:
                        target.setText(escaped)
                    panel.update()
                    panel.repaint()
                    if w.save_state(show_popup=False) is None:
                        raise RuntimeError('Could not checkpoint edit')
                except Exception:
                    if op == 'add_label':
                        panel.shapes_to_draw.remove(target)
                    else:
                        target.setText(old_text)
                    panel.update()
                    raise
                w._mark_dirty()
                result = self.snapshot()
            else:
                raise ValueError('Unsupported live operation')
        self.results[request_id] = (signature, result)
        # Fail closed when full; never evict IDs and accidentally repeat an edit.
        return result

    def bulk_letters(self, arguments, swap=False, scale_bars=False, ungroup=False, deletion=False, reverse_selection=False, row_swap=False, roi_inset=False):
        w = self.window
        edit = w.roi_to_inset if roi_inset else w.swap_rows if row_swap else w.reverse_selected_row if reverse_selection else w.delete_last_rows if deletion else w.ungroup_all_images if ungroup else w.remove_scale_bars_all if scale_bars else w.swap_panels if swap else w.edit_panel_letters
        edit(**arguments, validate_only=True)
        from .partner_gui import state
        before_letters = state(w)
        # Validate and edit a separate deserialized instance? Instead use rollback of a
        # complete snapshot on the Qt thread: no repaint/event processing mid-transaction.
        folder = STATE / ('transaction_' + uuid.uuid4().hex)
        folder.mkdir()
        before = folder / 'before.pyf'
        w._save_state_to_file(str(before))
        old_path, old_dirty = w.current_file, w._dirty
        history = (list(w.undo_stack), list(w.redo_stack), w.current_index, w.last_called_state)
        try:
            if w.save_state(show_popup=False) is None:
                raise RuntimeError('Could not checkpoint document')
            report = edit(**arguments)
            w.paint.EZFIG_panel.repaint()
            from .partner_gui import state
            verified = state(w)
            from .figure_state import changes, specification, verify_style
            if reverse_selection or row_swap:
                deltas = changes({**before_letters, 'panels': report.pop('aligned_before')}, verified)
                if deltas:
                    raise ValueError('Row rearrangement changed unexpected letter properties; rolled back')
            elif deletion:
                deltas = changes({**before_letters, 'panels': report.pop('surviving_before')}, verified)
                if deltas or len(verified['panels']) != report['image_count_after']:
                    raise ValueError('DELETE_VERIFICATION_FAILED: Final state changed; deletion rolled back')
            elif ungroup:
                # Container indices change; compare the same ordered image identities.
                aligned = {**before_letters, 'panels': [{**old, 'panel_id': new['panel_id']} for old, new in zip(before_letters['panels'], verified['panels'])]}
                deltas = changes(aligned, verified)
                if deltas:
                    raise ValueError('Ungroup changed lettering; rolled back')
            elif not swap and not scale_bars and not roi_inset and arguments.get('action', 'style') == 'style':
                deltas = verify_style(before_letters, verified, arguments, set(report['matched_panel_ids']))
            else:
                deltas = changes(before_letters, verified)
            report['verified_changes'] = deltas
            if (scale_bars or roi_inset) and deltas:
                raise ValueError('Scale-bar removal changed panel lettering; edit rolled back')
            report['verified_specification'] = specification(verified)
            report['visible_letter_count_before'] = before_letters['visible_letter_count']
            report['visible_letter_count_after'] = verified['visible_letter_count']
            report['unlettered_panel_ids'] = verified['unlettered_panel_ids']
            report['outcome'] = ('LETTERS_REMOVED' if report['action'] == 'remove' else
                                 'NO_VISIBLE_CHANGE' if not report['changed'] else 'VERIFIED_CHANGE')
            if ungroup:
                report['outcome'] = ('LAYOUT_REFRESHED' if report.get('layout_changed') else 'ALREADY_UNGROUPED') if report['already_ungrouped'] else 'VERIFIED_STRUCTURE_CHANGE'
            affected = set(report['changed_panel_ids'])
            report['verified_panels'] = [p for p in verified['panels'] if p['panel_id'] in affected]
            report['verification'] = 'Actual text styles and placements after GUI lettering refresh; not a guarantee of contrast against every image.'
            if scale_bars:
                report['verification'] = 'All panel ScaleBar annotations removed; letter properties unchanged. One undo step.'
            if deletion:
                report['outcome'] = 'VERIFIED_ROW_DELETION'
                report['verification'] = 'Exact original tail rows absent; all untargeted image objects and actual lettering retained; native layout refreshed. One undo step.'
            if ungroup:
                report['verification'] = 'Zero remaining grouped images verified; native automatic layout refreshed. If ALREADY_UNGROUPED, no change was made; LAYOUT_REFRESHED means structure was already flat but geometry changed.'
                if report['already_ungrouped'] and not report.get('layout_changed'):
                    return {'operation_result': report, **self.snapshot()}
            if w.save_state(show_popup=False) is None:
                raise RuntimeError('Could not checkpoint edit')
            w._mark_dirty()
            return {'operation_result': report, **self.snapshot()}
        except Exception:
            w.reload_state(str(before), append=False, skip_add_to_stack=True)
            w.undo_stack, w.redo_stack, w.current_index, w.last_called_state = history
            w.current_file = old_path
            w._mark_dirty() if old_dirty else w._mark_clean()
            w.update_button_state()
            raise

    def save_copy(self, arguments):
        from datetime import datetime
        destination = arguments.get('path')
        if not destination:
            stem = Path(self.window.current_file or 'untitled').stem
            destination = STATE / 'saved_figures' / f'{stem}_{datetime.now():%Y%m%d_%H%M%S_%f}.pyf'
        destination = Path(destination).resolve()
        if destination.suffix.lower() != '.pyf':
            raise ValueError('Save paths must be .pyf files')
        if destination.exists() and not arguments.get('overwrite', False):
            raise ValueError('File exists; choose another path or explicitly request overwrite')
        destination.parent.mkdir(parents=True, exist_ok=True)
        w = self.window
        w._save_state_to_file(str(destination))
        w._copy_sidecars(w._sidecar_base(), str(destination.with_suffix('')))
        staged = STATE / ('original_' + self.id) / 'current.pyf'
        if staged.exists():
            w._copy_sidecars(str(staged.with_suffix('')), str(destination.with_suffix('')))
        import xml.etree.ElementTree as ET
        ET.parse(destination)
        w.current_file = str(destination)
        w._mark_clean()
        self.sync()
        return {'saved_path': str(destination), 'saved': True, **self.snapshot()}

    def restore_recovery(self, arguments):
        path = self.recovery.resolve(arguments['snapshot'])
        import xml.etree.ElementTree as ET
        if ET.parse(path).getroot().tag != 'list':
            raise ValueError('Recovery file is not a PyFigures document')
        w = self.window
        old_path = w.current_file
        old_dirty = w._dirty
        backup = STATE / ('restore_before_' + uuid.uuid4().hex + '.pyf')
        w._save_state_to_file(str(backup))
        if w.save_state(show_popup=False) is None:
            raise RuntimeError('Could not checkpoint document')
        staged = STATE / ('original_' + self.id)
        staged.mkdir(exist_ok=True)
        old_metadata = {ext: (staged / ('current' + ext)).read_bytes()
                        for ext in w._SIDECAR_EXTS if (staged / ('current' + ext)).exists()}
        history = (list(w.undo_stack), list(w.redo_stack), w.current_index, w.last_called_state)
        try:
            w.reload_state(str(path), append=False, skip_add_to_stack=True)
            manifest_path = path.with_suffix('.recovery.json')
            manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
            w.current_file = manifest.get('source_path') or old_path
            for ext in w._SIDECAR_EXTS:
                source = Path(str(path.with_suffix('')) + ext)
                target = staged / ('current' + ext)
                if source.exists():
                    import shutil
                    shutil.copy2(source, target)
                elif target.exists():
                    target.unlink()
            w._save_state_to_file(str(staged / 'current.pyf'))
            if w.save_state(show_popup=False) is None:
                raise RuntimeError('Could not checkpoint recovered figure')
            w._mark_dirty()
        except Exception:
            w.reload_state(str(backup), append=False, skip_add_to_stack=True)
            w.current_file = old_path
            w.undo_stack, w.redo_stack, w.current_index, w.last_called_state = history
            for ext in w._SIDECAR_EXTS:
                target = staged / ('current' + ext)
                if ext in old_metadata:
                    target.write_bytes(old_metadata[ext])
                elif target.exists():
                    target.unlink()
            w._mark_dirty() if old_dirty else w._mark_clean()
            w.update_button_state()
            raise
        return {'restored_snapshot': str(path), **self.snapshot()}

    from .plot_lifecycle import scene_transaction
    @scene_transaction
    def original_tool(self, args):
        """Invoke any original figure tool on a retained live-session workspace."""
        import shutil
        from .original_registry import registry, live_parameter, encode
        from .existing_tools import checked
        name = args['tool']
        parameter = live_parameter(name)
        if not parameter:
            raise ValueError('This tool requires its original explicit paths')
        supplied = dict(args.get('arguments', {}))
        from .gui_selection import resolve_panel_arguments
        supplied = resolve_panel_arguments(self.window, supplied)
        supplied[parameter] = 'live'
        w = self.window
        from .partner_gui import state as letter_state, panels as image_panels
        letters_before = letter_state(w)
        folder = STATE / ('original_' + self.id)
        folder.mkdir(exist_ok=True)
        path = folder / 'current.pyf'
        first = not path.exists()
        w._save_state_to_file(str(path))
        if first:
            w._copy_sidecars(w._sidecar_base(), str(path.with_suffix('')))
        before = path.read_bytes()
        backup = folder / 'before.pyf'
        backup.write_bytes(before)
        sidecars = {p.name: p.read_bytes() for p in folder.glob('current.*') if p.is_file()}
        supplied[parameter] = str(path)
        fn = registry()[name].fn
        if name.startswith('export_') or name in ('render_preview', 'simulate_color_blindness'):
            # Native renderers use the unmodified original GUI, which cannot read
            # prototype policies. Bake actual letter styles into ordinary labels in
            # a separate OUTPUT snapshot so native auto-lettering cannot overwrite them.
            import xml.etree.ElementTree as ET
            root = ET.fromstring(before)
            for annotation in root.iter('TAText2D'):
                if annotation.findtext('is_letter') == 'True':
                    annotation.find('is_letter').text = 'False'
            settings = root.find('SerializableGUIparameters')
            if settings is not None:
                field = settings.find('auto_lettering')
                if field is None:
                    field = ET.SubElement(settings, 'auto_lettering')
                field.text = 'False'
            output_snapshot = folder / 'output_snapshot.pyf'
            output_snapshot.write_text(ET.tostring(root, encoding='unicode'), encoding='utf-8')
            w._copy_sidecars(str(path.with_suffix('')), str(output_snapshot.with_suffix('')))
            supplied[parameter] = str(output_snapshot)
        try:
            response = checked(fn(**supplied))
            # Some original layout tools deserialize/reserialize with the original
            # classes, dropping extension metadata. Retain policies only for panels
            # whose filename/script/letter text still identify an exact match.
            if path.read_bytes() != before:
                from .partner_gui import carry_policies
                path.write_bytes(carry_policies(before, path.read_bytes()))
                from .live_structure import protect_empty_groups
                path.write_bytes(protect_empty_groups(path.read_bytes()))
            # Convert images while their temporary render assets still exist.
            encoded = encode(response)
        except Exception:
            path.write_bytes(before)
            for p in folder.glob('current.*'):
                if p.is_file() and p.name not in sidecars:
                    p.unlink()
            for filename, data in sidecars.items():
                (folder / filename).write_bytes(data)
            raise
        changed = path.read_bytes() != before
        sidecar_changed = any(p.read_bytes() != sidecars.get(p.name)
            for p in folder.glob('current.*') if p.is_file() and p.suffix == '.json'
            and any(p.name.endswith(ext) for ext in ('.caption.json', '.stats.json', '.alttext.json', '.target.json')))
        if sidecar_changed:
            w._mark_dirty()
        if changed:
            if w.save_state(show_popup=False) is None:
                path.write_bytes(before)
                raise RuntimeError('Could not checkpoint current document')
            old_path, old_dirty = w.current_file, w._dirty
            old_history = (list(w.undo_stack), list(w.redo_stack), w.current_index, w.last_called_state)
            try:
                w.reload_state(str(path), append=False, skip_add_to_stack=True)
                if name == 'resize_figure':
                    # Native file tools update geometry, not the live GUI control
                    # used by subsequent Split/resize actions. Use effective
                    # geometry, which may differ from width_mm after fit-height.
                    from qtpy.QtCore import QSignalBlocker
                    widths = [obj.width() for obj in w.paint.EZFIG_panel.shapes_to_draw
                              if not getattr(obj, 'isText', False) and hasattr(obj, 'width')]
                    if widths:
                        with QSignalBlocker(w.size_spinbox):
                            w.size_spinbox.setValue(int(round(max(widths))))
                if name == 'set_figure_properties':
                    translated = {new: supplied[old] for old, new in [
                        ('font_family', 'font_family'), ('font_size', 'font_size'),
                        ('foreground_color', 'color_value'), ('background_color', 'background')]
                        if supplied.get(old) is not None}
                    if translated:
                        w.edit_panel_letters(**translated)
                elif name == 'set_label_background' and supplied.get('include_letters', True):
                    group = supplied.get('group_path')
                    w.edit_panel_letters(background=supplied.get('color', 'black'),
                        scope='group' if group else 'all', group_path=group)
                w.paint.EZFIG_panel.repaint()
                from .live_structure import verify_adoption
                verify_adoption(path.read_bytes(),w.paint.EZFIG_panel.shapes_to_draw)
                from .live_structure import adopt_letter_deltas
                adopt_letter_deltas(before,path.read_bytes(),w,name)
                if name == 'move_image':
                    from .figure_state import movement_changes
                    movement_changes(letters_before, letter_state(w))
                if name == 'set_label_background' and supplied.get('include_letters', True):
                    from .figure_state import verify_style
                    group = supplied.get('group_path') or []
                    ids = {p['panel_id'] for p in letters_before['panels'] if p['group_path'][:len(group)] == group}
                    verify_style(letters_before, letter_state(w), {'background': supplied.get('color', 'black')}, ids)
                if name == 'set_annotation_text':
                    targets = [p for gp, ix, p in image_panels(w.paint.EZFIG_panel.shapes_to_draw)
                               if list(gp) == supplied.get('group_path') and ix == supplied.get('image_index')]
                    texts = [a for p in targets for a in p.annotations or [] if isinstance(a, TAText2D)]
                    index = supplied.get('annotation_index', -1)
                    from pyfigures.mcp_tools.core import _html_to_plain
                    expected = _html_to_plain(supplied.get('html_text', ''))
                    if not 0 <= index < len(texts) or texts[index].getPlainText() != expected:
                        raise ValueError('VERIFICATION_FAILED: Requested annotation text did not survive GUI refresh; edit rolled back. Persistent panel lettering can override this native setter. Discover swap_live_panels for an atomic image or letter-text swap; do not retry individual annotation setters.')
                if name == 'add_corner_labels':
                    targets = [p for gp, ix, p in image_panels(w.paint.EZFIG_panel.shapes_to_draw)
                               if list(gp) == supplied.get('group_path') and ix == supplied.get('image_index')]
                    actual_texts = [a.getPlainText() for p in targets for a in p.annotations or []
                                    if isinstance(a, TAText2D)]
                    from pyfigures.mcp_tools.core import _html_to_plain
                    expected = [_html_to_plain(text) for corner in ('top_left', 'top_right', 'bottom_left', 'bottom_right')
                                for text in (supplied.get(corner) or [])]
                    if not targets or any(text not in actual_texts for text in expected):
                        raise ValueError('VERIFICATION_FAILED: Native add_corner_labels reported success, but requested text is absent after GUI refresh. Edit rolled back. Use swap_live_panels for swaps; do not remove/recreate panel letters.')
                if w.save_state(show_popup=False) is None:
                    raise RuntimeError('Could not checkpoint changed document')
                w._mark_dirty()
            except Exception:
                w.reload_state(str(backup), append=False, skip_add_to_stack=True)
                path.write_bytes(before)
                for p in folder.glob('current.*'):
                    if p.is_file() and p.name not in sidecars:p.unlink()
                for filename,data in sidecars.items():(folder/filename).write_bytes(data)
                w.undo_stack, w.redo_stack, w.current_index, w.last_called_state = old_history
                w._mark_dirty() if old_dirty else w._mark_clean()
                w.update_button_state()
                raise
            finally:
                w.current_file = old_path
        actual_state = self.snapshot()
        letters_after = letter_state(w)
        from .figure_state import changes, specification
        from .figure_state import movement_changes
        return {'tool_result': encoded, 'document_changed': changed, 'metadata_changed': sidecar_changed,
                'verified_changes': movement_changes(letters_before, letters_after) if name == 'move_image' else changes(letters_before, letters_after),
                'verified_specification': specification(letters_after),
                'verified_lettering': {'visible_count_before': letters_before['visible_letter_count'],
                                      'visible_count_after': letters_after['visible_letter_count'],
                                      'unlettered_panel_ids': letters_after['unlettered_panel_ids'],
                                      'warning': 'No panel letters are visible. Do not claim a letter swap succeeded.' if not letters_after['visible_letter_count'] else None},
                'persistence': actual_state['persistence'],
                'verification': 'GUI adopted the resulting document; inspect_panel_letters reports actual letter styles. A setter alone does not guarantee contrast.',
                'session_id': self.id, 'revision': actual_state['revision'],
                'workspace': str(folder)}

    def drain(self):
        while not self.requests.empty():
            req, reply = self.requests.get_nowait()
            try:
                if len(self.results) >= 10000 and req['request_id'] not in self.results:
                    raise RuntimeError('Session request limit reached; restart prototype')
                reply.put({'result': self.execute(req)})
            except Exception as exc:
                message = str(exc)
                code = ('SESSION_CHANGED' if message.startswith('Session unavailable') else
                        'REVISION_CONFLICT' if message.startswith('Stale revision') else 'TOOL_FAILED')
                reply.put({'error': message, 'error_code': code})


def label_text(obj):
    if isinstance(obj, Image2D) and obj.isText:
        return next((a for a in obj.annotations if isinstance(a, TAText2D)), None)
    return None


def count_images(obj):
    from batoolset.drawings.shapes.group import Group
    if getattr(obj, 'isText', False):
        return 0
    if isinstance(obj, Image2D):
        return 1
    if isinstance(obj, Group):
        return sum(count_images(child) for child in obj.content)
    return 0


def serve(session, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.headers.get('Authorization') != 'Bearer ' + token:
                self.send_error(403)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536:
                    raise ValueError('Invalid request size')
                self.connection.settimeout(5)
                req = json.loads(self.rfile.read(size))
                if not isinstance(req.get('request_id'), str) or len(req['request_id']) > 100:
                    raise ValueError('Invalid request ID')
                reply = queue.Queue(maxsize=1)
                session.requests.put_nowait((req, reply))
                result = reply.get(timeout=300 if req.get('operation') == 'original_tool' else 20)
            except queue.Empty:
                result = {'error': 'Outcome unknown; retry with exactly the same request ID and content'}
            except Exception as exc:
                result = {'error': str(exc)}
            payload = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
