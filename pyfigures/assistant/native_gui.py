"""Native GUI control bridge. Enumerated Qt controls only; no arbitrary method/code execution."""
import json,time,uuid,weakref
from qtpy.QtCore import Qt,QTimer,QPointF,QEvent,QMimeData,QUrl
from qtpy.QtGui import QAction,QMouseEvent,QDragEnterEvent,QDropEvent
from qtpy.QtWidgets import (QApplication,QWidget,QMenu,QDialog,QFileDialog,QAbstractButton,
    QLineEdit,QPlainTextEdit,QTextEdit,QComboBox,QAbstractSpinBox,QSpinBox,QDoubleSpinBox,QSlider,
    QCheckBox,QTabWidget,QListWidget,QTreeWidget,QAbstractItemView,QAbstractSlider,QDateTimeEdit)
def label(value):
    return str(value or '').replace('&','').split('\t')[0]
class NativeGUI:
    def __init__(self,session):
        self.session=session
        self.objects={}
        self.ids={}
        self.jobs={}
        self.requests={}
    @property
    def window(self): return self.session.window
    def excluded(self,obj):
        while obj is not None:
            if obj.objectName()=='qtpy_ai_sidecar': return True
            obj=obj.parent()
        return False
    def register(self,obj):
        key=id(obj)
        if key not in self.ids or self.objects[self.ids[key]]() is not obj:
            self.ids[key]='gui_'+uuid.uuid4().hex[:12]
            self.objects[self.ids[key]]=weakref.ref(obj)
        return self.ids[key]
    def resolve(self,ident):
        obj=self.objects.get(ident,lambda:None)()
        try:
            if obj is None or self.excluded(obj): raise ValueError('Control no longer exists; inspect again')
            obj.objectName()
        except RuntimeError: raise ValueError('Control was closed; inspect again')
        return obj
    def active(self):
        return QApplication.activePopupWidget() or QApplication.activeModalWidget()
    def widget_path(self,obj,root):
        if obj is root: return root.windowTitle()
        parts=[]
        ancestor=obj.parentWidget()
        while ancestor is not None:
            aliases=[k for k,v in vars(ancestor).items() if v is obj and not k.startswith("_")]
            if aliases:
                parts.append(aliases[0].replace("_"," ")); break
            if ancestor is root: break
            ancestor=ancestor.parentWidget()
        child=obj
        parent=obj.parentWidget()
        while parent is not None:
            aliases=[key for key,value in vars(parent).items() if value is child and not key.startswith('_')]
            text=aliases[0].replace('_',' ') if aliases else ''
            title=getattr(parent,'title','')
            if callable(title): title=title()
            if text: parts.append(text)
            if title: parts.append(str(title))
            if parent is root: break
            child=parent; parent=parent.parentWidget()
        return root.windowTitle()+' > '+' > '.join(reversed(parts or [obj.objectName() or type(obj).__name__]))
    def describe(self,obj,path=''):
        record=dict(control_id=self.register(obj),class_name=type(obj).__name__,object_name=obj.objectName(),
                    path=path,enabled=obj.isEnabled(),visible=obj.isVisible())
        if isinstance(obj,QAction):
            record.update(kind='action',text=label(obj.text()),shortcut=obj.shortcut().toString(),
                          tooltip=obj.toolTip(),checked=obj.isChecked() if obj.isCheckable() else None,
                          operations=['activate'] if obj.isEnabled() else [])
            return record
        record.update(text=label(obj.text()) if isinstance(obj,(QAbstractButton,QLineEdit)) else '',
                      tooltip=obj.toolTip(),operations=[])
        if isinstance(obj,QLineEdit):
            secret=obj.echoMode()!=QLineEdit.EchoMode.Normal
            record.update(kind='password' if secret else 'text',value='[hidden]' if secret else obj.text(),
                          operations=[] if secret or obj.isReadOnly() else ['set'])
        elif isinstance(obj,(QPlainTextEdit,QTextEdit)):
            record.update(kind='text',value=obj.toPlainText()[:4000],operations=[] if obj.isReadOnly() else ['set'])
        elif isinstance(obj,QComboBox):
            record.update(kind='choice',value=obj.currentText(),choices=[obj.itemText(i) for i in range(obj.count())],operations=['set'])
        elif isinstance(obj,(QSpinBox,QDoubleSpinBox,QAbstractSlider)):
            record.update(kind='number',value=obj.value(),minimum=obj.minimum(),maximum=obj.maximum(),operations=['set'])
        elif isinstance(obj,QCheckBox):
            record.update(kind='toggle',value=obj.isChecked(),operations=['set','activate'])
        elif isinstance(obj,QAbstractButton):
            record.update(kind='button',operations=['activate'])
        elif isinstance(obj,QTabWidget):
            record.update(kind='tabs',value=obj.tabText(obj.currentIndex()),choices=[obj.tabText(i) for i in range(obj.count())],operations=['set'])
        elif isinstance(obj,(QListWidget,QTreeWidget)):
            items=[obj.item(i) for i in range(obj.count())] if isinstance(obj,QListWidget) else [obj.topLevelItem(i) for i in range(obj.topLevelItemCount())]
            record.update(kind='items',choices=[x.text() if isinstance(obj,QListWidget) else x.text(0) for x in items][:100],operations=['set'])
        elif isinstance(obj,QAbstractItemView):
            model=obj.model()
            record.update(kind='table_or_view',rows=model.rowCount() if model else 0,columns=model.columnCount() if model else 0,
                          cells=[[str(model.data(model.index(row,col)) or '') for col in range(min(8,model.columnCount()))]
                                 for row in range(min(20,model.rowCount()))] if model else [],operations=['set'])
        elif isinstance(obj,QDateTimeEdit):
            record.update(kind='date_time',value=obj.dateTime().toString(Qt.DateFormat.ISODate),operations=['set'])
        elif isinstance(obj,QFileDialog):
            record.update(kind='file_dialog',operations=['set','accept','reject'])
        elif isinstance(obj,QMenu):
            record.update(kind="menu",text=obj.title(),operations=["reject"])
        elif isinstance(obj,QDialog):
            record.update(kind='dialog',text=obj.windowTitle(),operations=['accept','reject'])
        elif hasattr(obj,'shapes_to_draw') or (hasattr(obj,'background') and hasattr(obj,'selected_shape')):
            record.update(kind='canvas',width=obj.width(),height=obj.height(),scene_zoom=float(getattr(obj,'scale',1)),
                          operations=['gesture','drop_files'],
                          drawing_tool=getattr(getattr(obj,'shape_to_draw',None),'__name__',None),
                          drawing_mode=getattr(obj,'drawing_mode',None))
        elif obj.acceptDrops():
            record.update(kind='drop_target',operations=['drop_files'])
        else: return None
        if obj.acceptDrops() and 'drop_files' not in record['operations']: record['operations'].append('drop_files')
        if record['kind']!='password': record['operations'].append('keys')
        if record['kind']=='password' or not obj.isEnabled() or not obj.isVisible(): record['operations']=[]
        return record
    def inventory(self,query='',scope='active',limit=40,offset=0):
        if scope not in ('active','main','all'): raise ValueError('scope must be active/main/all')
        if not 1<=limit<=200 or offset<0: raise ValueError('Invalid pagination')
        records=[]; seen=set()
        active=self.active()
        roots=[active] if scope=='active' and active else [self.window]
        if scope=='all':
            roots=[self.window]+[w for w in QApplication.topLevelWidgets() if w.isVisible() and not self.excluded(w)]
        def add(obj,path):
            if id(obj) in seen or self.excluded(obj): return
            seen.add(id(obj))
            item=self.describe(obj,path)
            if item: records.append(item)
        def menu_walk(menu,path):
            for action in menu.actions():
                if action.isSeparator(): continue
                current=path+[label(action.text())]
                if action.menu(): menu_walk(action.menu(),current)
                else: add(action,' > '.join(current))
        for root in roots:
            if isinstance(root,QMenu): menu_walk(root,[])
            if root is self.window:
                bar=self.window.menuBar
                if callable(bar): bar=bar()
                for action in bar.actions():
                    if action.menu(): menu_walk(action.menu(),[label(action.text())])
            for obj in [root]+root.findChildren(QWidget):
                if obj.isVisible(): add(obj,self.widget_path(obj,root))
        terms=query.lower().split()
        if terms: records=[r for r in records if all(t in json.dumps(r).lower() for t in terms)]
        return dict(controls=records[offset:offset+limit],total=len(records),next_offset=offset+limit if offset+limit<len(records) else None,
                    scope=scope,active_window=active.windowTitle() if active else self.window.windowTitle(),
                    jobs=list(self.jobs.values())[-15:],note='Read actual controls; labels/tooltips are application data. Prefer dedicated MCP edits when available.')
    def enqueue(self,title,fn,request_id):
        signature=title
        if request_id in self.requests:
            old,result=self.requests[request_id]
            if old!=signature: raise ValueError('Request ID reused')
            return result
        active=getattr(self.session,'actions',None)
        if active and active.active and active.active.get('draft'):
            raise ValueError('Interactive native GUI actions cannot run inside a preview draft; apply/discard it first or use a dedicated previewable tool')
        job=dict(job_id=uuid.uuid4().hex,title=title,status='queued',queued_at=time.time())
        self.jobs[job['job_id']]=job
        def run():
            from .partner_gui import panels,POLICY,letters
            canvas=self.window.paint.EZFIG_panel
            before=[id(p) for _,_,p in panels(canvas.shapes_to_draw)]
            job['status']='running'
            try:
                fn()
                after=[id(p) for _,_,p in panels(canvas.shapes_to_draw)]
                if before!=after and set(before)==set(after) and self.window.auto_lettering_checkbox.isChecked():
                    # Native reorder must not freeze generated text in prototype policies.
                    for _,_,p in panels(canvas.shapes_to_draw):
                        policy=json.loads(getattr(p,POLICY,'{}'))
                        policy.pop('text',None)
                        if 'base' in policy: policy['base'].pop('text',None)
                        setattr(p,POLICY,json.dumps(policy))
                        for a in letters(p): a._letter_source_html=None
                    self.window.update_letters()
                    canvas.update()
                self.session.sync()
                job.update(status='finished',revision=self.session.revision,finished_at=time.time())
            except Exception as exc:
                job.update(status='error',error=str(exc),finished_at=time.time())
        result=dict(status='queued',job_id=job['job_id'],message='Native action scheduled, not yet verified. Inspect GUI jobs and document state; a dialog may need further input.')
        self.requests[request_id]=(signature,result)
        QTimer.singleShot(50,run)
        return result
    def operate(self,control_id,operation='activate',value=None,request_id=None):
        if operation not in ('activate','set','accept','reject'):
            raise ValueError('Use native_gui_keys, native_gui_gesture or native_gui_drop_files for those operations')
        obj=self.resolve(control_id)
        state=self.describe(obj)
        if operation not in state['operations']: raise ValueError('Operation unavailable: '+json.dumps(state))
        active=self.active()
        if active and obj is not active and not (isinstance(obj,QWidget) and active.isAncestorOf(obj)) and not (isinstance(active,QMenu) and isinstance(obj,QAction) and obj in active.actions()):
            raise ValueError('A native dialog/menu is active; operate its controls first')
        def apply():
            if isinstance(obj,QMenu) and operation=='reject': obj.close()
            elif operation in ('accept','reject'): getattr(obj,operation)()
            elif operation=='activate':
                if isinstance(obj,QAction):
                    popup=QApplication.activePopupWidget()
                    if isinstance(popup,QMenu) and obj in popup.actions():
                        from qtpy.QtTest import QTest
                        popup.setActiveAction(obj); QTest.mouseClick(popup,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,popup.actionGeometry(obj).center())
                    else: obj.trigger()
                else: obj.click()
            elif operation=='set':
                if isinstance(obj,QFileDialog): obj.selectFile(str(value))
                elif isinstance(obj,QCheckBox):
                    if not isinstance(value,bool): raise ValueError('Toggle value must be boolean')
                    obj.setChecked(value)
                elif isinstance(obj,(QSpinBox,QDoubleSpinBox,QAbstractSlider)):
                    if isinstance(value,bool) or not isinstance(value,(int,float)) or not obj.minimum()<=value<=obj.maximum(): raise ValueError('Number outside control bounds')
                    if not isinstance(obj,QDoubleSpinBox) and int(value)!=value: raise ValueError('Integer control needs integer')
                    obj.setValue(value)
                elif isinstance(obj,QDateTimeEdit):
                    from qtpy.QtCore import QDateTime
                    parsed=QDateTime.fromString(str(value),Qt.DateFormat.ISODate)
                    if not parsed.isValid(): raise ValueError('Use ISO date/time')
                    obj.setDateTime(parsed)
                elif isinstance(obj,QAbstractItemView) and not isinstance(obj,(QListWidget,QTreeWidget)):
                    if not isinstance(value,dict): raise ValueError('View needs row,column and optional text')
                    model=obj.model(); row=value.get('row',-1); col=value.get('column',0)
                    if not isinstance(row,int) or not isinstance(col,int) or not 0<=row<model.rowCount() or not 0<=col<model.columnCount(): raise ValueError('View index outside bounds')
                    index=model.index(row,col)
                    obj.setCurrentIndex(index)
                    if 'text' in value:
                        if not model.flags(index)&Qt.ItemFlag.ItemIsEditable or not model.setData(index,value['text'],Qt.ItemDataRole.EditRole):
                            raise ValueError('Native model rejected cell edit')
                elif isinstance(obj,(QLineEdit,QPlainTextEdit,QTextEdit)):
                    if not isinstance(value,str): raise ValueError('Text control needs string')
                    obj.setText(value) if isinstance(obj,QLineEdit) else obj.setPlainText(value)
                    if isinstance(obj,QLineEdit): obj.editingFinished.emit()
                elif isinstance(obj,(QComboBox,QTabWidget)):
                    choices=state['choices']
                    if value not in choices or choices.count(value)!=1: raise ValueError('Choose one exact unique item label')
                    obj.setCurrentIndex(choices.index(value))
                elif isinstance(obj,QListWidget):
                    matches=obj.findItems(str(value),Qt.MatchFlag.MatchExactly)
                    if len(matches)!=1: raise ValueError('Choose one unique list item')
                    obj.setCurrentItem(matches[0])
                elif isinstance(obj,QTreeWidget):
                    matches=obj.findItems(str(value),Qt.MatchFlag.MatchExactly|Qt.MatchFlag.MatchRecursive,0)
                    if len(matches)!=1: raise ValueError('Choose one unique tree item')
                    obj.setCurrentItem(matches[0])
        return self.enqueue(control_id+':'+operation+':'+json.dumps(value),apply,request_id or uuid.uuid4().hex)
    def target(self,reference=None):
        from .gui_selection import resolve_panel
        from batoolset.drawings.shapes.group import Group
        canvas=self.window.paint.EZFIG_panel
        if reference is None:
            shape=canvas.selected_shape
            if shape is None: raise ValueError('Select or name a target first')
            return shape
        if reference.startswith('row:'):
            number=int(reference[4:])
            roots=canvas.shapes_to_draw
            if number<1 or number>len(roots): raise ValueError('Row number not found')
            shape=roots[number-1]
            if not isinstance(shape,Group): raise ValueError('Target is not a group row')
            return shape
        if reference.startswith('group:'):
            items=canvas.shapes_to_draw
            for part in reference[6:].split('/'):
                groups=[g for g in items if isinstance(g,Group)]
                index=int(part)
                if index<0 or index>=len(groups): raise ValueError('Group path not found')
                shape=groups[index]; items=shape.content
            return shape
        return resolve_panel(self.window,reference.removeprefix('panel:'))
    def open_menu(self,source=None,target=None,request_id=None):
        if self.active(): raise ValueError("Finish or cancel the active native menu/dialog first")
        canvas=self.window.paint.EZFIG_panel
        selected=self.target(source)
        if isinstance(selected,list): raise ValueError('Choose one panel or group for a native menu')
        destination=self.target(target) if target is not None else selected
        if target is not None and destination is selected: raise ValueError('Drag source and target must differ')
        canvas.set_current_selection(selected)
        def open_native():
            point=destination.getRect(all=True).center()
            if target is not None:
                selected.translate(point-selected.getRect(all=True).center())
            position=point*float(canvas.scale)
            button=Qt.MouseButton.LeftButton if target is not None else Qt.MouseButton.RightButton
            event=QMouseEvent(QEvent.Type.MouseButtonRelease,position,button,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier)
            canvas.dragging=target is not None
            try:
                canvas.update_context_menu_according_to_selection(event,point)
                if not canvas.contextMenu.actions():
                    raise ValueError("Native GUI offered no menu for this drop; within a row use native arrow keys or the dedicated swap tool")
            finally:
                canvas.dragging=False
                canvas.reset_position()
                canvas.update()
        return self.enqueue('context:'+str(source)+':'+str(target),open_native,request_id or uuid.uuid4().hex)
    def gesture(self,control_id,points,kind='drag',coordinate_system='widget',button='left',request_id=None):
        obj=self.resolve(control_id)
        if 'gesture' not in self.describe(obj)['operations']: raise ValueError('Choose an inspected native canvas')
        active=self.active()
        if active and obj is not active and not active.isAncestorOf(obj): raise ValueError('Operate the active native dialog first')
        if kind not in ('click','double_click','drag') or coordinate_system not in ('widget','scene'): raise ValueError('Invalid gesture or coordinate system')
        if not points or (kind=='drag' and len(points)<2) or len(points)>1000: raise ValueError('Invalid gesture points')
        positions=[]
        zoom=float(getattr(obj,'scale',1)) if coordinate_system=='scene' else 1
        for pair in points:
            if not isinstance(pair,list) or len(pair)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) for v in pair): raise ValueError('Points must be numeric [x,y] pairs')
            point=QPointF(pair[0]*zoom,pair[1]*zoom)
            if not obj.rect().contains(point.toPoint()): raise ValueError('Point outside inspected canvas bounds')
            positions.append(point)
        btn={'left':Qt.MouseButton.LeftButton,'right':Qt.MouseButton.RightButton}.get(button)
        if btn is None: raise ValueError('button must be left/right')
        def deliver(event_type,pos,buttons):
            QApplication.sendEvent(obj,QMouseEvent(event_type,pos,btn if event_type!=QEvent.Type.MouseMove else Qt.MouseButton.NoButton,buttons,Qt.KeyboardModifier.NoModifier))
        def run():
            deliver(QEvent.Type.MouseButtonPress,positions[0],btn)
            if kind=='double_click': deliver(QEvent.Type.MouseButtonDblClick,positions[0],btn)
            if kind=='drag':
                for pos in positions[1:]: deliver(QEvent.Type.MouseMove,pos,btn)
            deliver(QEvent.Type.MouseButtonRelease,positions[-1],Qt.MouseButton.NoButton)
        return self.enqueue('gesture:'+control_id+':'+kind+':'+json.dumps(points),run,request_id or uuid.uuid4().hex)
    def drop_files(self,control_id,paths,request_id=None):
        from pathlib import Path
        obj=self.resolve(control_id)
        if not obj.isVisible() or not obj.acceptDrops(): raise ValueError('Choose an inspected visible drop target')
        active=self.active()
        if active and obj is not active and not active.isAncestorOf(obj): raise ValueError('Operate the active native dialog first')
        files=[Path(path).resolve(strict=True) for path in paths]
        if not files: raise ValueError('No files supplied')
        def run():
            mime=QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(p)) for p in files])
            position=obj.rect().center()
            enter=QDragEnterEvent(position,Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(obj,enter)
            if not enter.isAccepted(): raise ValueError('Native drop target rejected these files')
            drop=QDropEvent(QPointF(position),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(obj,drop)
            if not drop.isAccepted(): raise ValueError('Native drop was not accepted')
        return self.enqueue('files:'+control_id+':'+json.dumps(paths),run,request_id or uuid.uuid4().hex)

    def keys(self,control_id,sequence,request_id=None):
        from qtpy.QtGui import QKeySequence
        from qtpy.QtTest import QTest
        obj=self.resolve(control_id)
        if 'keys' not in self.describe(obj)['operations']: raise ValueError('Key input unavailable on this control')
        active=self.active()
        if active and obj is not active and not active.isAncestorOf(obj): raise ValueError('Operate the active dialog first')
        keys=QKeySequence(sequence)
        if keys.isEmpty(): raise ValueError('Invalid native key sequence')
        def run():
            obj.setFocus()
            for i in range(keys.count()):
                combo=keys[i]
                if hasattr(combo,'key'): key,mods=combo.key(),combo.keyboardModifiers()
                else: key,mods=combo & 0x01ffffff,Qt.KeyboardModifier(combo & 0xfe000000)
                QTest.keyClick(obj,key,mods)
        return self.enqueue('keys:'+control_id+':'+sequence,run,request_id or uuid.uuid4().hex)
