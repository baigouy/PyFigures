"""Typed advanced annotation edits on the Qt thread; no arbitrary script execution."""
import hashlib
import json
import math

def describe(obj):
    result = {'type': type(obj).__name__}
    if hasattr(obj, 'doc'):
        result.update(text=obj.doc.toPlainText(), html=obj.doc.toHtml(),
                      is_panel_letter=bool(getattr(obj, 'is_letter', False)))
    for field in ('color','fill_color','stroke','opacity','theta','arrow','arrow_at_both_ends','border_size','border_color','fraction_of_parent_image_width_if_image_is_inset','crop_left','crop_right','crop_top','crop_bottom'):
        if hasattr(obj, field):
            result[field] = getattr(obj, field)
    if all(callable(getattr(obj, f, None)) for f in ('x','y','width','height')):
        result['geometry'] = [obj.x(), obj.y(), obj.width(), obj.height()]
    if all(callable(getattr(obj, f, None)) for f in ('x1','y1','x2','y2')):
        result['endpoints'] = [obj.x1(), obj.y1(), obj.x2(), obj.y2()]
    if hasattr(obj,'placement'):result['placement']=str(obj.placement)
    if hasattr(obj,'text_orientation'):result['text_orientation']=str(obj.text_orientation)
    from qtpy.QtGui import QPolygonF
    if isinstance(obj,QPolygonF):result['vertices']=[[point.x(),point.y()] for point in obj]
    if type(obj).__name__=='Image2D':
        result['filename']=str(getattr(obj,'filename',''))
        result['script']=str(getattr(obj,'custom_loading_script','') or '')
    semantic = dict(result)
    # Anchored text x/y are paint caches, not user changes.
    if hasattr(obj, 'doc') or (type(obj).__name__=='Image2D' and bool(str(getattr(obj,'placement','')))):
        semantic.pop('geometry', None)
    result['token'] = hashlib.sha256(json.dumps(semantic, sort_keys=True, default=str).encode()).hexdigest()
    return result

def inspect_objects(session, panel_ref=None, offset=0, limit=12, include_panel_letters=False):
    if isinstance(offset,bool) or isinstance(limit,bool) or not isinstance(offset,int) or not isinstance(limit,int) or offset<0 or not 1<=limit<=24:
        raise ValueError("Use nonnegative offset and limit 1 to 24")
    from .gui_selection import resolve_panel
    from .partner_gui import panels
    chosen = resolve_panel(session.window, panel_ref) if panel_ref else None
    items=[]
    for gp, ix, panel in panels(session.window.paint.EZFIG_panel.shapes_to_draw):
        if chosen is not None and panel is not chosen:
            continue
        pid='/'.join(map(str, (*gp,ix)))
        for index, obj in enumerate(panel.annotations or []):
            if getattr(obj,'is_letter',False) and not include_panel_letters:continue
            items.append(dict(panel_id=pid, annotation_index=index, **describe(obj)))
    from .gui_selection import sync_editor
    _,viewer=sync_editor(session)
    editor_objects=[]
    if viewer is not None:
        for index,obj in enumerate(viewer.shapes):
            editor_objects.append(dict(annotation_index=index,selected=any(obj is x for x in viewer.selected_shape),**describe(obj)))
    return {'objects':items[offset:offset+limit], 'total_objects':len(items),
            'next_offset':offset+limit if offset+limit<len(items) else None,
            'editor_draft_objects':editor_objects,
            'editor_panel_id':getattr(session,'_annotation_editor_panel_id',None),
            'editor_open':bool(getattr(session, '_annotation_editor_pending',False)),
            'editor_status':getattr(session,'_annotation_editor_status',None),
            'coordinates':'ROI geometry is in source-image pixels, not scene/display pixels.'}

def number(value, positive=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('A finite numeric value is required')
    if positive and value<=0:
        raise ValueError('Size and stroke must be positive')
    return float(value)

def color(value, transparent=False):
    from qtpy.QtGui import QColor
    if transparent and (value is None or value=='none'):
        return None
    if isinstance(value,bool) or not isinstance(value,(str,int)):
        raise ValueError('Use a named color, #RRGGBB, integer RGB, or none for fill')
    q=QColor(value)
    if not q.isValid():
        raise ValueError('Invalid color')
    return q.rgb() & 0xffffff

def prepare_text(obj, changes, substring=None, occurrence=None):
    from qtpy.QtGui import QTextCursor,QTextCharFormat,QFont,QColor
    allowed={'text','bold','italic','underline','font_family','font_size','color','background','vertical_alignment','placement'}
    if not changes or set(changes)-allowed:
        raise ValueError('Unsupported or empty rich-text changes')
    if getattr(obj,'is_letter',False):
        raise ValueError('Use scoped panel-letter tools for automatic labels; this editor is for ordinary annotations')
    doc=obj.doc.clone()
    cursor=QTextCursor(doc)
    if substring is None:
        if occurrence is not None:
            raise ValueError('occurrence requires substring')
        cursor.select(QTextCursor.SelectionType.Document)
    else:
        if not isinstance(substring,str) or not substring:
            raise ValueError('substring must be nonempty literal text')
        matches=[]
        found=doc.find(substring,0)
        while not found.isNull():
            matches.append((found.selectionStart(),found.selectionEnd()))
            found=doc.find(substring,found.selectionEnd())
        if not matches:
            raise ValueError('Requested text is absent')
        if occurrence is None and len(matches)!=1:
            raise ValueError('CLARIFICATION_REQUIRED: Text occurs more than once; specify a 1-based occurrence')
        n=1 if occurrence is None else occurrence
        if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=len(matches):
            raise ValueError('Occurrence is outside the matching text range')
        start,end=matches[n-1]
        cursor.setPosition(start)
        cursor.setPosition(end,QTextCursor.MoveMode.KeepAnchor)
    fmt=QTextCharFormat()
    for key, setter in [('bold',lambda v:fmt.setFontWeight(QFont.Weight.Bold if v else QFont.Weight.Normal)),
                        ('italic',fmt.setFontItalic),('underline',fmt.setFontUnderline)]:
        if key in changes:
            if not isinstance(changes[key],bool):
                raise ValueError(key+' must be boolean')
            setter(changes[key])
    if 'font_family' in changes:
        if not isinstance(changes['font_family'],str) or not changes['font_family'].strip():
            raise ValueError('font_family must be nonempty')
        fmt.setFontFamilies([changes['font_family']])
    if 'font_size' in changes:fmt.setFontPointSize(number(changes['font_size'],True))
    if 'color' in changes:fmt.setForeground(QColor(color(changes['color'])))
    if 'background' in changes:
        v=color(changes['background'],True)
        from qtpy.QtCore import Qt
        from qtpy.QtGui import QBrush
        fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush) if v is None else QBrush(QColor(v)))
    if 'vertical_alignment' in changes:
        modes={'normal':QTextCharFormat.VerticalAlignment.AlignNormal,
               'subscript':QTextCharFormat.VerticalAlignment.AlignSubScript,
               'superscript':QTextCharFormat.VerticalAlignment.AlignSuperScript}
        if changes['vertical_alignment'] not in modes:raise ValueError('Unknown vertical_alignment')
        fmt.setVerticalAlignment(modes[changes['vertical_alignment']])
    cursor.mergeCharFormat(fmt)
    if 'text' in changes:
        replacement=changes['text']
        if not isinstance(replacement,str) or len(replacement)>10000:
            raise ValueError('Replacement text must be a string up to 10000 characters')
        # Insert literal text (Greek/Unicode allowed), never interpret user text as HTML.
        cursor.insertText(replacement, cursor.charFormat())
    placement=None
    if 'placement' in changes:
        if not isinstance(changes['placement'],str):raise ValueError('placement must be a named corner or center')
        placement=' '.join(changes['placement'].lower().replace('-',' ').split()).replace('lower','bottom').replace('upper','top')
        if placement in ('center','centre','middle'):placement='center_h center_v'
        if placement not in ('top left','top right','bottom left','bottom right','center_h center_v'):
            raise ValueError('Use a named corner or center')
    doc.adjustSize()
    def apply():
        obj.setText(doc.toHtml())
        if placement is not None:
            from batoolset.drawings.shapes.Position import Position
            obj.placement=Position(placement)
    return apply

def prepare_roi(obj, changes):
    supported={'Rect2D','Rectangle2D','Ellipse2D','Line2D'}
    if type(obj).__name__ not in supported:
        raise ValueError('This shape requires its native property editor; supported direct ROI types: Rect2D, Ellipse2D, Line2D')
    allowed={'color','fill_color','stroke','opacity','geometry','endpoints'}
    if not changes or set(changes)-allowed:raise ValueError('Unsupported or empty ROI changes')
    plan={}
    for key,v in changes.items():
        if key in ('color','fill_color'):plan[key]=color(v,key=='fill_color')
        elif key=='stroke':plan[key]=number(v,True)
        elif key=='opacity':
            plan[key]=number(v)
            if not 0<=plan[key]<=1:raise ValueError('opacity must be between 0 and 1')
        elif key=='geometry':
            if type(obj).__name__=='Line2D' or not isinstance(v,list) or len(v)!=4:
                raise ValueError('geometry is [x,y,width,height] for rectangle/ellipse only')
            plan[key]=[number(x,i>=2) for i,x in enumerate(v)]
        elif key=='endpoints':
            if type(obj).__name__!='Line2D' or not isinstance(v,list) or len(v)!=4:
                raise ValueError('endpoints is [x1,y1,x2,y2] for a line only')
            plan[key]=[number(x) for x in v]
    def apply():
        for key,v in plan.items():
            if key=='geometry':obj.setRect(*v)
            elif key=='endpoints':obj.setLine(*v)
            else:
                if not hasattr(obj,key):raise ValueError('Shape does not support '+key)
                setattr(obj,key,v)
    return apply

def edit(session,panel_ref,annotation_index,token,changes,substring=None,occurrence=None):
    from .gui_selection import resolve_panel
    from .session import STATE
    import uuid
    from .gui_selection import sync_editor
    sync_editor(session)
    if getattr(session,'_annotation_editor_pending',False):
        return edit_draft(session,panel_ref,annotation_index,token,changes,substring,occurrence)
    panel=resolve_panel(session.window,panel_ref)
    if isinstance(annotation_index,bool) or not isinstance(annotation_index,int) or not 0<=annotation_index<len(panel.annotations or []):
        raise ValueError('Annotation index not found; inspect again')
    obj=panel.annotations[annotation_index]
    before=describe(obj)
    if token!=before['token']:raise ValueError('STALE_ANNOTATION: Inspect the object again before editing')
    if not isinstance(changes,dict):raise ValueError('changes must be an object')
    if hasattr(obj,'doc'):apply=prepare_text(obj,changes,substring,occurrence)
    else:
        if substring is not None or occurrence is not None:raise ValueError('Text selection cannot target an ROI')
        apply=prepare_roi(obj,changes)
    w=session.window
    folder=STATE/('annotation_'+uuid.uuid4().hex);folder.mkdir()
    backup=folder/'before.pyf';w._save_state_to_file(str(backup))
    history=(list(w.undo_stack),list(w.redo_stack),w.current_index,w.last_called_state)
    path,dirty=w.current_file,w._dirty
    try:
        if w.save_state(show_popup=False) is None:raise RuntimeError('Could not checkpoint annotation edit')
        apply()
        after=describe(obj)
        changed=before['token']!=after['token']
        if changed:
            w.paint.EZFIG_panel.update();w.paint.EZFIG_panel.repaint()
            if w.save_state(show_popup=False) is None:raise RuntimeError('Could not checkpoint edited annotation')
            w._mark_dirty()
        return {'changed':changed,'outcome':'VERIFIED_CHANGE' if changed else 'NO_CHANGE','before':before,'after':after,
                'verification':'Read back actual native annotation properties; visual readability is not guaranteed.'}
    except Exception:
        w.reload_state(str(backup),append=False,skip_add_to_stack=True)
        w.undo_stack,w.redo_stack,w.current_index,w.last_called_state=history
        w.current_file=path
        w._mark_dirty() if dirty else w._mark_clean()
        w.update_button_state()
        raise

def edit_draft(session,panel_ref,annotation_index,token,changes,substring=None,occurrence=None):
    """The panel's editor is open: edit its DRAFT object, as the editor's own
    controls do. The figure is untouched until the user clicks OK (Cancel
    drops the change), so native OK/Cancel semantics stay intact."""
    from .gui_selection import resolve_panel,native_editor,native_dialog_titles
    from .partner_gui import panels
    panel=resolve_panel(session.window,panel_ref)
    owner=next('/'.join(map(str,(*gp,ix))) for gp,ix,p in panels(session.window.paint.EZFIG_panel.shapes_to_draw) if p is panel)
    if getattr(session,'_annotation_editor_panel_id',None)!=owner:
        raise ValueError('The open editor is for another panel; finish or cancel it first')
    if any(t in ('Edit text','Edit ScaleBar','Edit Inset') for t in native_dialog_titles(session)):
        raise ValueError('Finish or cancel the open property dialog first')
    _,viewer=native_editor(session)
    if viewer is None:raise ValueError('The editor is still opening; inspect again')
    if isinstance(annotation_index,bool) or not isinstance(annotation_index,int) or not 0<=annotation_index<len(viewer.shapes):
        raise ValueError('Draft annotation index not found; inspect the editor draft again')
    draft=viewer.shapes[annotation_index]
    main=panel.annotations[annotation_index] if annotation_index<len(panel.annotations or []) else None
    before=describe(draft)
    valid=before['token']==token or (main is not None and describe(main)['token']==token and draft_matches(main,draft))
    if not valid:raise ValueError('STALE_ANNOTATION: Inspect the current editor draft again')
    if not isinstance(changes,dict):raise ValueError('changes must be an object')
    if hasattr(draft,'doc'):apply=prepare_text(draft,changes,substring,occurrence)
    else:
        if substring is not None or occurrence is not None:raise ValueError('Text selection cannot target an ROI')
        apply=prepare_roi(draft,changes)
    apply()
    after=describe(draft)
    changed=before['token']!=after['token']
    if changed:
        viewer.shapeChanged.emit() if hasattr(viewer,'shapeChanged') else None
        viewer.update()
    return {'changed':changed,'target':'editor_draft','document_changed':False,
            'outcome':'VERIFIED_DRAFT_CHANGE' if changed else 'NO_CHANGE','before':before,'after':after,
            'verification':'Read back the open editor draft. The figure changes only when the user clicks OK in the editor; Cancel discards it.'}

def open_properties(session,panel_ref,annotation_index,token):
    """Select a draft object and open its actual native double-click properties."""
    from .gui_selection import resolve_panel,open_editor,sync_editor,native_editor,native_dialog_titles
    from .partner_gui import panels
    from qtpy.QtCore import QTimer
    if isinstance(annotation_index,bool) or not isinstance(annotation_index,int) or annotation_index<0:
        raise ValueError('Annotation index must be a nonnegative integer')
    sync_editor(session)
    panel=resolve_panel(session.window,panel_ref)
    owner=next('/'.join(map(str,(*gp,ix))) for gp,ix,p in panels(session.window.paint.EZFIG_panel.shapes_to_draw) if p is panel)
    main=panel.annotations[annotation_index] if annotation_index<len(panel.annotations or []) else None
    existing=bool(getattr(session,'_annotation_editor_pending',False))
    dialogs={'TAText2D':'text','ScaleBar':'scale bar','Image2D':'inset'}
    _,open_viewer=native_editor(session) if existing else (None,None)
    objects=list(open_viewer.shapes if open_viewer is not None else panel.annotations or [])
    if annotation_index<len(objects) and type(objects[annotation_index]).__name__ not in dialogs:
        # Otherwise the object is merely selected and "scheduled" reads as success.
        others=', '.join(f'{i} ({dialogs[type(a).__name__]})' for i,a in enumerate(objects) if type(a).__name__ in dialogs) or 'none'
        raise ValueError(f'Annotation {annotation_index} is a {type(objects[annotation_index]).__name__}, which has no properties dialog '
                         f'(edit it with edit_annotation_properties). Objects with a properties dialog on this panel: {others}. Nothing was opened.')
    if existing:
        if getattr(session,'_annotation_editor_panel_id',None)!=owner:
            raise ValueError('Finish the current panel editor before opening another panel properties')
        _,viewer=native_editor(session)
        if viewer is not None:
            if annotation_index>=len(viewer.shapes):raise ValueError('Draft annotation index not found; inspect again')
            candidate=viewer.shapes[annotation_index]
            valid=describe(candidate)['token']==token or (main is not None and describe(main)['token']==token and draft_matches(main,candidate))
            if not valid:raise ValueError('STALE_ANNOTATION: Inspect the current editor draft again')
            titles=native_dialog_titles(session)
            expected={'TAText2D':'Edit text','ScaleBar':'Edit ScaleBar','Image2D':'Edit Inset'}.get(type(candidate).__name__)
            if any(t in ('Edit text','Edit ScaleBar','Edit Inset') for t in titles):
                if expected in titles and any(candidate is a for a in viewer.selected_shape):
                    return {'status':'already_open','document_changed':False,'message':'The requested native properties are already open.'}
                raise ValueError('Finish or cancel the current property dialog before selecting another annotation')
        result={'status':'scheduled','document_changed':False}
    else:
        if main is None or describe(main)['token']!=token:raise ValueError('STALE_ANNOTATION: Inspect again')
        result=open_editor(session,panel_ref)
    attempts=[0]
    def choose():
        attempts[0]+=1
        if not getattr(session,'_annotation_editor_pending',False):return
        _,viewer=sync_editor(session)
        if viewer is None and attempts[0]<100:
            QTimer.singleShot(50,choose);return
        try:
            if viewer is None:raise ValueError('Native annotation canvas was not available')
            if getattr(session,'_annotation_editor_panel_id',None)!=owner:raise ValueError('Native editor owner changed')
            if annotation_index>=len(viewer.shapes):raise ValueError('Annotation draft changed; inspect again')
            draft=viewer.shapes[annotation_index]
            valid=describe(draft)['token']==token or (main is not None and describe(main)['token']==token and draft_matches(main,draft))
            if not valid:raise ValueError('Annotation draft differs; inspect current editor before editing')
            viewer.selected_shape=[draft];viewer.currently_drawn_shape=None
            viewer.selectionChanged.emit();viewer.update()
            session._annotation_editor_status='annotation selected; native controls available'
            if type(draft).__name__ in ('TAText2D','ScaleBar','Image2D'):
                session._annotation_editor_status='native annotation property dialog open'
                viewer.mouseDoubleClickEvent(None)
                session._annotation_editor_status='annotation editor open; accept or cancel parent dialog'
        except Exception as exc:
            session._annotation_editor_status='property selection failed: '+str(exc)
    QTimer.singleShot(80 if existing else 250,choose)
    return {**result,'message':'Native properties requested for the selected annotation. Uses the current editor draft when already open. Inspect actual dialogs; queued is not applied. Both native OK/Cancel levels remain in effect.'}

def draft_matches(original,draft):
    """Native TextEditor resolves inherited fonts while cloning; compare effective styles."""
    if type(original).__name__!=type(draft).__name__:return False
    if not hasattr(original,'doc'):return describe(original)['token']==describe(draft)['token']
    left,right=describe(original),describe(draft)
    for key in set(left)|set(right):
        if key not in ('geometry','html','token') and left.get(key)!=right.get(key):return False
    if original.doc.toPlainText()!=draft.doc.toPlainText():return False
    def runs(doc):
        result=[]
        block=doc.begin()
        while block.isValid():
            iterator=block.begin()
            while not iterator.atEnd():
                fragment=iterator.fragment()
                if fragment.isValid():
                    fmt=fragment.charFormat()
                    font=fmt.font().resolve(doc.defaultFont())
                    appearance=(font.family(),font.pointSizeF(),font.weight(),font.italic(),font.underline(),
                                fmt.verticalAlignment(),fmt.foreground().style(),fmt.foreground().color().rgba(),
                                fmt.background().style(),fmt.background().color().rgba(),block.blockFormat().alignment())
                    for char in fragment.text():result.append((char,appearance))
                iterator+=1
            block=block.next()
        return result
    return runs(original.doc)==runs(draft.doc)
