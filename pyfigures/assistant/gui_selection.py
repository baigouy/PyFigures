"""Prototype UI actions using native selection and annotation editor."""
from qtpy.QtCore import QTimer
from batoolset.drawings.shapes.group import Group
from .partner_gui import panels, letters, selection_state

def resolve_panel(window, ref):
    matches = [p for gp, ix, p in panels(window.paint.EZFIG_panel.shapes_to_draw)
               if '/'.join(map(str, (*gp, ix))) == ref or any(a.getPlainText() == ref for a in letters(p))]
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

def open_editor(session, panel_ref=None):
    window = session.window
    canvas = window.paint.EZFIG_panel
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
    session._annotation_editor_pending = True
    session._annotation_editor_status = 'scheduled'
    def launch():
        try:
            if not any(p is panel for _, _, p in panels(canvas.shapes_to_draw)):
                raise ValueError('Panel changed before editor opened')
            session._annotation_editor_status = 'open'
            canvas.update_image_annotations(image2d=panel)
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
    return dict(status='scheduled', selection=selection_state(window), document_changed=False,
                message='Native annotation editor will open for this panel. Human edits use native OK/Cancel; no annotation has been added by this tool.')
