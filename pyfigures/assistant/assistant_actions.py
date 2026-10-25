"""Prototype message checkpoints, optional hidden drafts and durable action journal."""
import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path

SIDECARS = ('.caption.json', '.stats.json', '.alttext.json', '.target.json')


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    # Windows sync/indexing software can briefly hold the destination open.
    for attempt in range(6):
        try:
            temp.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.03 * (attempt + 1))


def ui_state(window):
    return dict(spacing=window.main_space_spinner.value(), width=window.size_spinbox.value(),
                automatic=window.auto_lettering_checkbox.isChecked(), first=window.letter_line_edit.text(),
                background=window.paint.EZFIG_panel.page_background)


def capture(session, path, picture=False):
    session.sync()
    w = session.window
    if picture:
        image = w.paint.EZFIG_panel.grab().toImage()
        if image.isNull() or not image.scaledToWidth(1200).save(str(path.with_suffix('.png'))):
            raise ValueError('Could not render canvas comparison')
    w._save_state_to_file(str(path))
    w._copy_sidecars(w._sidecar_base(), str(path.with_suffix('')))
    staged = session.runtime / ('original_' + session.id) / 'current.pyf'
    if staged.exists():
        w._copy_sidecars(str(staged.with_suffix('')), str(path.with_suffix('')))
    meta = ui_state(w)
    atomic_json(path.with_suffix('.ui.json'), meta)
    return digest(path)


def digest(path):
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    for parent in root.iter():
        for item in list(parent):
            if item.tag == '_proxy_stale' or (parent.tag == 'Group' and item.tag == 'ID'):
                parent.remove(item)
            elif item.tag in ('x', 'y', 'width', 'height', 'scale', 'size') and item.text:
                try:
                    item.text = format(float(item.text), '.10g')
                except ValueError:
                    pass
        # Auto-placed text coordinates are render output, not an authored edit.
        if parent.tag == 'annotations':
            for text in parent.findall('TAText2D'):
                if text.findtext('placement') not in (None, 'None', ''):
                    for field in ('x', 'y'):
                        node = text.find(field)
                        if node is not None:
                            text.remove(node)
    result = hashlib.sha256(ET.tostring(root))
    for suffix in ('.ui.json', *SIDECARS):
        item = path.with_suffix(suffix)
        result.update(suffix.encode())
        if item.exists():
            result.update(item.read_bytes())
    return result.hexdigest()


def adopt(session, path):
    from qtpy.QtCore import QSignalBlocker
    w = session.window
    old_path = w.current_file
    w.reload_state(str(path), append=False, skip_add_to_stack=True)
    meta = json.loads(path.with_suffix('.ui.json').read_text(encoding='utf-8'))
    for widget, value, method in [(w.main_space_spinner, meta['spacing'], 'setValue'),
                                  (w.size_spinbox, meta['width'], 'setValue'),
                                  (w.auto_lettering_checkbox, meta['automatic'], 'setChecked'),
                                  (w.letter_line_edit, meta['first'], 'setText')]:
        with QSignalBlocker(widget):
            getattr(widget, method)(value)
    canvas = w.paint.EZFIG_panel
    canvas.space = meta['spacing']
    canvas.page_background = meta['background']
    canvas.set_current_selection(None)
    canvas.update()
    canvas.repack_all()
    w.update_letters()
    canvas.update_size()
    canvas.repaint()
    target = session.runtime / ('original_' + session.id)
    target.mkdir(exist_ok=True)
    for suffix in SIDECARS:
        source, destination = path.with_suffix(suffix), target / ('current' + suffix)
        if source.exists():
            shutil.copyfile(source, destination)
        else:
            destination.unlink(missing_ok=True)
    w.current_file = old_path
    w._mark_dirty()
    session.sync()


class ActionManager:
    def __init__(self, session):
        self.session = session
        self.root = session.runtime / 'assistant_actions'
        self.root.mkdir(exist_ok=True)
        self.active = None

    def persist(self):
        a = self.active
        atomic_json(a['folder'] / 'journal.json', a['record'])

    def begin(self, text='', preview=False):
        if self.active:
            raise ValueError('Apply/discard the pending preview before sending another edit.')
        self.session._turn_submission_target=None
        start = time.monotonic()
        ident = uuid.uuid4().hex
        folder = self.root / ident
        folder.mkdir()
        before = folder / 'before.pyf'
        baseline = capture(self.session, before, picture=preview)
        record = dict(id=ident, request=text, status='running', preview=preview,
                      before=str(before), baseline=baseline, operations=[], created_at=time.time())
        self.active = dict(folder=folder, record=record, draft=None)
        if preview:
            from .session import EZFIG_GUI, Session
            w = EZFIG_GUI()
            w.resize(self.session.window.size())
            draft = Session(w, recovery_dir=self.session.runtime / 'assistant_drafts')
            adopt(draft, before)
            # Copy selection by opaque scene address, never by Python identity.
            from .partner_gui import selection_state
            selected = selection_state(self.session.window).get('selected_objects', [])
            objects = []
            for item in selected:
                try:
                    parts = item['object_id'].split('/')
                    obj = w.paint.EZFIG_panel.shapes_to_draw[int(parts[1])]
                    for offset in range(2, len(parts), 2):
                        obj = getattr(obj, parts[offset])[int(parts[offset + 1])]
                    objects.append(obj)
                except (AttributeError, ValueError, IndexError):
                    pass
            w.paint.EZFIG_panel.set_current_selection(objects[0] if len(objects) == 1 else objects or None)
            self.active['draft'] = draft
            record['draft_session'] = draft.id
        record['checkpoint_ms'] = round((time.monotonic() - start) * 1000, 1)
        self.persist()
        return dict(id=ident, preview=preview, checkpoint_ms=record['checkpoint_ms'])

    def dispatch(self, req):
        a = self.active
        target = a['draft'] or self.session
        op = req['operation']
        mutating = op not in ('inspect', 'letter_state', 'preview', 'readability', 'submission_review', 'inspect_annotation_objects')
        name = req.get('arguments', {}).get('tool', '')
        read_only_native = op == 'original_tool' and name.startswith(('get_', 'list_', 'describe_', 'inspect_', 'check_', 'explain_'))
        if a['record'].get('resume_guard') and mutating and not read_only_native:
            if any(prior['status'] in ('pending', 'uncertain') for prior in a['record']['operations']):
                raise ValueError('UNCERTAIN_OPERATION: Inspect and review the recovered draft before further edits. Apply/discard it, then give explicit remaining instructions. No uncertain operation replayed.')
            for prior in a['record']['operations']:
                if prior['status'] == 'completed' and prior['operation'] == op and prior['arguments'] == req.get('arguments', {}):
                    raise ValueError('ALREADY_COMPLETED: This operation was recorded as complete before interruption. Inspect current state; do not apply it twice. Ask for clarification if an identical repeated operation is intentional.')
        if a['draft'] and (op == 'save_copy' or (op == 'original_tool' and req.get('arguments', {}).get('tool', '').startswith('export_'))):
            raise ValueError('Export/save cannot be previewed. Apply the draft first, then request export.')
        item = None
        if mutating:
            item = dict(request_id=req['request_id'], operation=op, arguments=req.get('arguments', {}),
                        status='pending', started_at=time.time())
            a['record']['operations'].append(item)
            self.persist()  # intent is durable BEFORE dispatch
        try:
            target._action_passthrough = True
            result = target.execute(req)
            if item is not None:
                item['status'] = 'completed'
                item['revision'] = target.revision
                capture(target, a['folder'] / 'latest.pyf')
            return result
        except Exception as exc:
            if item is not None:
                item['status'] = 'failed'
                item['error'] = str(exc)
            raise
        finally:
            target._action_passthrough = False
            if item is not None:
                a['record']['recovery_snapshot'] = target.recovery.latest
                self.persist()

    def finish(self, interrupted=False):
        a = self.active
        if not a:
            return {}
        target = a['draft'] or self.session
        after = a['folder'] / 'after.pyf'
        a['record']['after'] = str(after)
        a['record']['after_digest'] = capture(target, after, picture=bool(a['draft']))
        changed = a['record']['baseline'] != a['record']['after_digest']
        a['record']['changed'] = changed
        a['record']['status'] = 'interrupted' if interrupted else 'preview' if a['draft'] and changed else 'applied' if changed else 'no_change'
        self.persist()
        record = dict(a['record'])
        if not a['draft'] or not changed:
            self.release()
        return record

    def release(self):
        if self.active and self.active['draft']:
            draft = self.active['draft']
            draft.timer.stop()
            draft.recovery_timer.stop()
            draft.window._mark_clean()
            draft.window.close()
            draft.window.deleteLater()
        self.active = None

    def apply(self):
        a = self.active
        if not a or not a['draft']:
            raise ValueError('No draft to apply')
        current = a['folder'] / 'current_main.pyf'
        if capture(self.session, current) != a['record']['baseline']:
            raise ValueError('The main figure changed after this preview began. Discard and retry; no draft applied.')
        before = a['folder'] / 'before.pyf'
        history = (list(self.session.window.undo_stack), list(self.session.window.redo_stack), self.session.window.current_index, self.session.window.last_called_state)
        try:
            self.session.window.save_state(show_popup=False)
            adopt(self.session, Path(a['record']['after']))
            self.session.window.save_state(show_popup=False)
            a['record']['after_digest'] = capture(self.session, Path(a['record']['after']))
            a['record']['status'] = 'applied'
            self.persist()
            result = dict(a['record'])
        except Exception:
            adopt(self.session, before)
            w = self.session.window
            w.undo_stack, w.redo_stack, w.current_index, w.last_called_state = history
            raise
        self.release()
        return result

    def discard(self):
        if not self.active:
            return {}
        self.active['record']['status'] = 'discarded'
        self.persist()
        result = dict(self.active['record'])
        self.release()
        return result

    def undo(self, ident):
        if self.active:
            raise ValueError('Apply/discard the pending draft first')
        folder = self.folder(ident)
        record = json.loads((folder / 'journal.json').read_text())
        if record['status'] not in ('applied', 'interrupted') or (record['status'] == 'interrupted' and record['preview']):
            raise ValueError('This action is not currently applied')
        if capture(self.session, folder / 'undo_check.pyf') != record['after_digest']:
            raise ValueError('Later edits exist. Undo those first; this message cannot be reversed without overwriting them.')
        w = self.session.window
        history = (list(w.undo_stack), list(w.redo_stack), w.current_index, w.last_called_state)
        old_dirty = w._dirty
        try:
            w.save_state(show_popup=False)
            adopt(self.session, Path(record['before']))
            w.save_state(show_popup=False)
        except Exception:
            adopt(self.session, folder / 'undo_check.pyf')
            w.undo_stack, w.redo_stack, w.current_index, w.last_called_state = history
            w._mark_dirty() if old_dirty else w._mark_clean()
            raise
        record['status'] = 'undone'
        record['undo_digest'] = capture(self.session, folder / 'undone.pyf')
        record['undone_at'] = time.time()
        atomic_json(folder / 'journal.json', record)
        return record

    def redo(self, ident=None):
        if self.active:
            raise ValueError('Finish the current action or draft before redoing a message')
        if ident is None:
            records = [json.loads(p.read_text()) for p in self.root.glob('*/journal.json')]
            undone = [r for r in records if r['status'] == 'undone']
            if not undone:
                raise ValueError('No undone assistant message is available to redo')
            ident = max(undone, key=lambda r: r.get('undone_at', 0))['id']
        folder = self.folder(ident)
        record = json.loads((folder / 'journal.json').read_text())
        if record['status'] != 'undone':
            raise ValueError('This message is not currently undone')
        if capture(self.session, folder / 'redo_check.pyf') != record.get('undo_digest'):
            raise ValueError('Later edits exist. Redo would overwrite them; no change made.')
        w = self.session.window
        history = (list(w.undo_stack), list(w.redo_stack), w.current_index, w.last_called_state)
        old_dirty = w._dirty
        try:
            w.save_state(show_popup=False)
            adopt(self.session, Path(record['after']))
            actual = capture(self.session, folder / 'redo_verified.pyf')
            if actual != record['after_digest']:
                raise ValueError('Redo verification failed')
            w.save_state(show_popup=False)
            record['status'] = 'applied'
            record['redone_at'] = time.time()
            atomic_json(folder / 'journal.json', record)
        except Exception:
            adopt(self.session, folder / 'redo_check.pyf')
            w.undo_stack, w.redo_stack, w.current_index, w.last_called_state = history
            w._mark_dirty() if old_dirty else w._mark_clean()
            raise
        return record

    def folder(self, ident):
        if len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
            raise ValueError('Invalid action identity')
        return self.root / ident

    def continue_action(self, ident):
        if not self.active or self.active['record']['id'] != ident or not self.active['record'].get('recovered_from'):
            raise ValueError('This recovered draft is no longer pending')
        self.active['record']['resume_guard'] = True
        self.active['record']['status'] = 'running'
        self.persist()
        return dict(self.active['record'])

    def recover(self, ident=None):
        """Recover a draft for review; never replay a recorded operation."""
        if self.active:
            raise ValueError('Finish the current draft first')
        candidates = [self.folder(ident) / 'journal.json'] if ident else sorted(self.root.glob('*/journal.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates:
            old = json.loads(path.read_text())
            if old['status'] not in ('running', 'interrupted', 'preview'):
                continue
            if not old['preview']:
                return dict(status='inspect_only', request=old['request'], operations=old['operations'],
                            note='Live edits may already exist. No operation replayed. Inspect current figure before asking for remaining work.')
            if capture(self.session, path.parent / 'recovery_check.pyf') != old['baseline']:
                return dict(status='conflict', request=old['request'], operations=old['operations'],
                            note='Main figure differs from the original action checkpoint. Recovery was not applied or staged; inspect/export before choosing a version. No operation replayed.')
            source = Path(old.get('recovery_snapshot') or old.get('after') or path.parent / 'latest.pyf')
            if not source.is_file() or not source.resolve().is_relative_to(self.session.runtime.resolve()):
                raise ValueError('Recovery draft unavailable; no replay attempted')
            begin = self.begin(old['request'], preview=True)
            draft = self.active['draft']
            # Recovery snapshots have no .ui manifest; use the recorded action state.
            recovered = self.active['folder'] / 'recovered.pyf'
            shutil.copyfile(source, recovered)
            ui = Path(old.get('after', old['before'])).with_suffix('.ui.json')
            shutil.copyfile(ui, recovered.with_suffix('.ui.json'))
            for suffix in SIDECARS:
                if source.with_suffix(suffix).exists():
                    shutil.copyfile(source.with_suffix(suffix), recovered.with_suffix(suffix))
            adopt(draft, recovered)
            self.active['record']['recovered_from'] = old['id']
            self.active['record']['operations'] = old['operations']
            result = self.finish(interrupted=True)
            old['status'] = 'recovered'
            old['recovered_as'] = result['id']
            atomic_json(path, old)
            result['note'] = 'Recovered draft for review. Completed operations were not replayed; pending/uncertain operations require fresh inspection and explicit remaining instructions.'
            return result
        return dict(status='none', note='No unfinished action found')
