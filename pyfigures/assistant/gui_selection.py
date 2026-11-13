"""Prototype UI actions using native selection and annotation editor."""
import re

from qtpy.QtCore import QTimer
from batoolset.drawings.shapes.group import Group
from .partner_gui import panels, letters, selection_state

def panel_number(ref, entries):
    """'#3' / '# 3' / 'no 3': the number the canvas shows on a selected panel (reading
    order, from 1), for figures without letters or with letters outside the rows."""
    found = re.fullmatch(r'\s*(?:#|n[o°]\.?|number)\s*(\d+)\s*', str(ref), re.I)
    if not found:
        return None
    number = int(found[1])
    return entries[number - 1] if 1 <= number <= len(entries) else 'missing'


def resolve_panel(window, ref):
    entries = list(panels(window.paint.EZFIG_panel.shapes_to_draw))
    numbered = panel_number(ref, entries)
    if numbered == 'missing':
        raise ValueError(f'UNKNOWN_PANEL_REFERENCE: there is no panel {ref} (the figure has {len(entries)} panels, '
                         'numbered 1 to that). Ask the user; no edit performed.')
    if numbered is not None:
        return numbered[2]
    matches = [p for gp, ix, p in entries
               if '/'.join(map(str, (*gp, ix))) == ref or any(a.getPlainText() == ref for a in letters(p))]
    if not matches and isinstance(ref, str) and ref.strip():
        # "crop e" on a figure lettered A, B, C…: the letter in the other case, when only
        # one panel has it
        wanted = ref.strip().casefold()
        matches = [p for gp, ix, p in entries if any(a.getPlainText().strip().casefold() == wanted for a in letters(p))]
    if len(matches) != 1:
        raise ValueError('CLARIFICATION_REQUIRED: Panel reference must identify exactly one current image')
    return matches[0]

def select(window, panel_refs=None, group_paths=None, row_numbers=None, clear=False):
    canvas = window.paint.EZFIG_panel
    families = sum(bool(x) for x in (panel_refs, group_paths, row_numbers))
    if clear:
        if families:
            raise ValueError('Clear selection cannot also specify targets')
        chosen = []
    elif families != 1:
        raise ValueError('Specify panel_refs OR group_paths OR visible row_numbers')
    elif panel_refs:
        chosen = [resolve_panel(window, ref) for ref in panel_refs]
    elif group_paths:
        chosen = []
        for path in group_paths:
            if not path:
                raise ValueError('A group path cannot be empty')
            items = canvas.shapes_to_draw
            for index in path:
                groups = [g for g in items if isinstance(g, Group)]
                if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(groups):
                    raise ValueError('Group path not found')
                group = groups[index]
                items = group.content
            chosen.append(group)
    else:
        roots = canvas.shapes_to_draw
        chosen = []
        for number in row_numbers:
            if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(roots):
                raise ValueError('Visible row numbers start at 1')
            row = roots[number-1]
            if not isinstance(row, Group) or row.isText or str(row.orientation).upper() != 'X':
                raise ValueError('CLARIFICATION_REQUIRED: Target is not a horizontal image row')
            chosen.append(row)
    chosen = list({id(p): p for p in chosen}.values())
    canvas.set_current_selection(chosen[0] if len(chosen)==1 else chosen if chosen else None)
    canvas.update()
    actual = selection_state(window)
    if actual['selected_object_count'] != len(chosen) or actual['stale_selection']:
        raise RuntimeError('Selection verification failed')
    return dict(status='selected' if chosen else 'cleared', selection=actual, document_changed=False)

# the image editor's tabs, by the words a request uses for them
EDITOR_TABS = {'annotations': 'Annotations', 'draw': 'Annotations', 'roi': 'Annotations',
               'crop': 'Rotate + Crop', 'rotate': 'Rotate + Crop', 'rotation': 'Rotate + Crop', 'flip': 'Rotate + Crop',
               'text': 'Texts', 'texts': 'Texts', 'scale': 'File Infos + Scale', 'info': 'File Infos + Scale',
               'pixel': 'File Infos + Scale', 'script': 'Script', 'export': 'Export style', 'style': 'Export style',
               'layers': 'Layers'}


def editor_tab(tab):
    """The editor tab title for *tab* (a title or one of EDITOR_TABS' words)."""
    if not tab:
        return 'Annotations'
    key = str(tab).strip().lower()
    titles = set(EDITOR_TABS.values())
    for title in titles:
        if re.sub(r'[^a-z0-9]', '', key) == re.sub(r'[^a-z0-9]', '', title.lower()):
            return title
    for word, title in EDITOR_TABS.items():
        if word in re.split(r'[^a-z0-9]+', key) or key == word:   # 'rotate_crop', 'Rotate + Crop'
            return title
    raise ValueError('Unknown editor tab ' + repr(tab) + '; use one of: ' + ', '.join(sorted(titles)))


def editor_tab_in(entries):
    """The editor tab one of *entries* names (route entries, button titles:
    'Rotate + Crop'), or None: a tab's title first, then EDITOR_TABS' words."""
    titles = {re.sub(r'[^a-z0-9]', '', t.lower()): t for t in EDITOR_TABS.values()}
    entries = [str(e) for e in entries if e]
    for entry in entries:
        title = titles.get(re.sub(r'[^a-z0-9]', '', entry.lower()))
        if title and title != 'Annotations':
            return title
    for entry in entries:
        words = re.split(r'[^a-z0-9]+', entry.lower())
        for word, title in EDITOR_TABS.items():
            if word in words and title != 'Annotations':
                return title
    return None


def open_editor(session, panel_ref=None, tab=None):
    window = session.window
    canvas = window.paint.EZFIG_panel
    title = editor_tab(tab)
    if getattr(session, '_annotation_editor_pending', False):
        raise ValueError('Annotation editor already opening or open')
    if panel_ref is not None:
        panel = resolve_panel(window, panel_ref)
    else:
        selected = selection_state(window)['selected_panels']
        if len(selected) != 1:
            raise ValueError('CLARIFICATION_REQUIRED: Select or name one panel to annotate')
        panel = resolve_panel(window, selected[0]['panel_id'])
    select(window, panel_refs=['/'.join(map(str, (*gp, ix))) for gp, ix, p in panels(canvas.shapes_to_draw) if p is panel])
    from .partner_gui import POLICY
    policy = getattr(panel, POLICY, None)
    panel_id = next('/'.join(map(str, (*gp, ix))) for gp, ix, p in panels(canvas.shapes_to_draw) if p is panel)
    session._annotation_editor_panel_id = panel_id
    session._annotation_editor_pending = True
    session._annotation_editor_status = 'scheduled'
    def launch():
        try:
            if not any(p is panel for _, _, p in panels(canvas.shapes_to_draw)):
                raise ValueError('Panel changed before editor opened')
            session._annotation_editor_status = 'open'
            canvas.update_image_annotations(image2d=panel, tab=title, draw_tool=False)
            current = resolve_panel(window, panel_id)
            if current is not panel and policy is not None and not getattr(current, POLICY, None):
                # Native clone drops prototype-only extension metadata.
                setattr(current, POLICY, policy)
                window.update_letters()
                canvas.update()
                canvas.repaint()
            session._annotation_editor_status = 'closed'
        except Exception as exc:
            session._annotation_editor_status = 'failed: ' + str(exc)
        finally:
            session._annotation_editor_pending = False
    QTimer.singleShot(200, launch)
    return dict(status='scheduled', selection=selection_state(window), document_changed=False, tab=title,
                message='Native image editor will open for this panel on its "' + title + '" tab. Human edits use native OK/Cancel; nothing has been changed by this tool.')


def resolve_panel_arguments(window,arguments):
    """Resolve named native-tool targets before any temporary file is edited."""
    args=dict(arguments)
    ref=args.pop('panel_ref',None)
    if ref is None:return args
    if not isinstance(ref,str) or not ref.strip():raise ValueError('panel_ref must be a current visible letter or panel ID')
    panel=resolve_panel(window,ref)
    matches=[(list(gp),ix) for gp,ix,p in panels(window.paint.EZFIG_panel.shapes_to_draw) if p is panel]
    if len(matches)!=1:raise ValueError('STALE_PANEL_REFERENCE: Inspect the figure again')
    path,index=matches[0]
    for key,wanted in (('group_path',path),('image_index',index)):
        supplied=args.get(key)
        if supplied is not None and (isinstance(supplied,bool) or supplied!=wanted):
            raise ValueError('PANEL_ADDRESS_CONFLICT: '+ref+' resolves to '+str(path)+' image '+str(index)+'. Omit numeric addresses when using panel_ref; no edit performed.')
        args[key]=wanted
    return args

def owned_by(window,dialog):
    """True when *dialog* belongs to *window* (directly or through other
    dialogs). Not isAncestorOf: it stops at window boundaries, and a dialog
    is always its own window."""
    owner=dialog.parentWidget()
    while owner is not None and owner is not window:owner=owner.parentWidget()
    return owner is not None

def native_editor(session):
    from qtpy.QtWidgets import QApplication,QDialog,QWidget
    viewers=[]
    for dialog in QApplication.topLevelWidgets():
        if not isinstance(dialog,QDialog) or dialog.windowTitle()!='Annotate the image' or not dialog.isVisible():continue
        if not owned_by(session.window,dialog):continue
        for widget in dialog.findChildren(QWidget):
            viewer=getattr(widget,'qt_viewer',None)
            if viewer is not None and all(viewer is not found[1] for found in viewers):
                viewers.append((dialog,viewer))
    if len(viewers)>1:raise ValueError('Several native editors belong to this window; finish one before continuing')
    return viewers[0] if viewers else (None,None)

def sync_editor(session):
    """Observe real dialogs too, including editors opened by a human double-click."""
    dialog,viewer=native_editor(session)
    observed=getattr(session,'_annotation_editor_observed',False)
    pending=getattr(session,'_annotation_editor_pending',False)
    if viewer is not None:
        if not observed and not pending:
            selected=selection_state(session.window)['selected_panels']
            owner=selected[0]['panel_id'] if len(selected)==1 else None
            if owner is None:
                background=viewer.background
                matches=['/'.join(map(str,(*gp,ix))) for gp,ix,p in panels(session.window.paint.EZFIG_panel.shapes_to_draw)
                         if str(p.filename)==str(background.filename) and str(getattr(p,'custom_loading_script',''))==str(getattr(background,'custom_loading_script',''))]
                if len(matches)==1:owner=matches[0]
            session._annotation_editor_panel_id=owner
            session._annotation_editor_status='open (native GUI)'
        session._annotation_editor_observed=True
        session._annotation_editor_pending=True
    elif observed:
        session._annotation_editor_observed=False
        session._annotation_editor_pending=False
        session._annotation_editor_panel_id=None
        session._annotation_editor_status='closed'
    return dialog,viewer

def native_dialog_titles(session):
    from qtpy.QtWidgets import QApplication,QDialog
    return [d.windowTitle() for d in QApplication.topLevelWidgets()
            if isinstance(d,QDialog) and d.isVisible() and owned_by(session.window,d)]
