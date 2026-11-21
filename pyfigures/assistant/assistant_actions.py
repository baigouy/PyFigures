"""Message checkpoints (Undo / Redo of one answer) and the durable action journal."""
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


def _panel_rects(shapes):
    from batoolset.drawings.shapes.group import Group
    out = []
    for shape in shapes:
        if isinstance(shape, Group):
            out += _panel_rects(shape.content)
        else:
            r = shape.getRect(all=True)
            out.append((round(r.x()), round(r.width()), round(r.height())))
    return out


def _fit_rows_to_width(window, canvas, width, rounds=3):
    """Fit every row to the figure width, as the width spinner does, then draw the
    figure and fit again until no panel moves: a data plot's shape changes when its
    text is fitted to the page at its new size."""
    for _ in range(rounds):
        for shape in list(canvas.shapes_to_draw):
            try:
                if getattr(shape, 'content', None):
                    window.update_size_of_object(shape, width)
            except Exception:
                pass
        canvas.repack_all()
        laid_out = _panel_rects(canvas.shapes_to_draw)
        try:
            canvas.grab()                     # the screen's own drawing fits the plots
        except Exception:
            return
        if _panel_rects(canvas.shapes_to_draw) == laid_out:
            return


def settle_drawn_plots(window):
    """After a document reload: draw the figure once; if drawing changed a panel's shape
    (a data plot's text fitted to the page at its size), fit the rows to the figure width
    again until it holds still. Nothing is touched when drawing changes nothing."""
    canvas = window.paint.EZFIG_panel
    laid_out = _panel_rects(canvas.shapes_to_draw)
    try:
        canvas.grab()
    except Exception:
        return
    if _panel_rects(canvas.shapes_to_draw) != laid_out:
        _fit_rows_to_width(window, canvas, window.size_spinbox.value())
        window.update_letters()
        canvas.update_size()


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
    # a row whose panel changed size (a plot's text made bigger: its shape changes) kept
    # its old widths: the spacing went wrong until the width spinner was nudged (user,
    # 2026-11-19). The spinner's own step: each row fitted to the figure width again,
    # every row: a row can keep its total width while its panels overlap (two plots of
    # a row edited at once, 2026-11-19).
    # A plot's text is fitted to the page when it is drawn, which changes its shape once
    # more (14 pt text: 105 -> 121 px wide, the two plots of a row overlapped): draw,
    # refit, until the panels hold still (one round settles it).
    _fit_rows_to_width(w, canvas, meta['width'])
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

    def begin(self, text=''):
        if self.active:
            raise ValueError('Finish the current action before sending another edit.')
        self.session._turn_submission_target=None
        from .submission_review import target_from_text
        named = target_from_text(text)
        if named:                    # kept for later turns ("is it ready?")
            self.session._named_submission_target = named
        start = time.monotonic()
        ident = uuid.uuid4().hex
        folder = self.root / ident
        folder.mkdir()
        before = folder / 'before.pyf'
        baseline = capture(self.session, before)
        record = dict(id=ident, request=text, status='running',
                      before=str(before), baseline=baseline, operations=[], created_at=time.time())
        self.active = dict(folder=folder, record=record)
        record['checkpoint_ms'] = round((time.monotonic() - start) * 1000, 1)
        self.persist()
        return dict(id=ident, checkpoint_ms=record['checkpoint_ms'])

    def dispatch(self, req):
        a = self.active
        target = self.session
        op = req['operation']
        mutating = op not in ('inspect', 'letter_state', 'preview', 'panel_source', 'overlay_contrast', 'readability', 'submission_review', 'inspect_annotation_objects')
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
        after = a['folder'] / 'after.pyf'
        a['record']['after'] = str(after)
        a['record']['after_digest'] = capture(self.session, after)
        changed = a['record']['baseline'] != a['record']['after_digest']
        a['record']['changed'] = changed
        a['record']['status'] = 'interrupted' if interrupted else 'applied' if changed else 'no_change'
        self.persist()
        record = dict(a['record'])
        self.active = None
        return record

    def undo(self, ident):
        if self.active:
            raise ValueError('Finish the current action first')
        folder = self.folder(ident)
        record = json.loads((folder / 'journal.json').read_text())
        # an old journal's never-applied draft (the preview mode removed 2026-11-21) is not undone
        if record['status'] not in ('applied', 'interrupted') or (record['status'] == 'interrupted' and record.get('preview')):
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
            raise ValueError('Finish the current action before redoing a message')
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

    def recover(self, ident=None):
        """An unfinished action (the application stopped mid-turn): its edits are already in
        the figure, so it is reported for inspection; never replayed."""
        if self.active:
            raise ValueError('Finish the current action first')
        candidates = [self.folder(ident) / 'journal.json'] if ident else sorted(self.root.glob('*/journal.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates:
            old = json.loads(path.read_text())
            if old['status'] not in ('running', 'interrupted'):
                continue
            return dict(status='inspect_only', request=old['request'], operations=old['operations'],
                        note='Live edits may already exist. No operation replayed. Inspect current figure before asking for remaining work.')
        return dict(status='none', note='No unfinished action found')
