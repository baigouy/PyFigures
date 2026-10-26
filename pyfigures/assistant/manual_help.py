"""Source-reviewed manual help; does not execute GUI actions."""
import ast,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
NAMES=('left_pressed','right_pressed','up_pressed','down_pressed','_drag_entry','internal_DND_context_menu','mouseReleaseEvent','extend')
def fingerprints():
    source=(ROOT.parent/'gui'/'ezfig.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    return {node.name:hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest()
            for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in NAMES}
def current_feature_help(topic):
    words=set(re.findall(r'[a-z]+',topic.lower()))
    native=Path(__file__).resolve().parents[2]/'pyfigures'
    if words.intersection({'sample','samples'}) and words.intersection({'file','files','tutorial','tutorials','inputs'}):
        files={'gui/tutorial.py':['Give me sample files','def _make_samples'],'gui/pfgui.py':['Beginner Tutorial']}
        title='Tutorial sample files'
        steps=['Open a tutorial from Help, for example Beginner Tutorial.',
               'On a step that needs input files, click Give me sample files. It creates the sample inputs and shows information for that step. The button is offered only on steps that provide samples.',
               'Use those files in the dialog described by the tutorial. The tutorial still guides your own clicks.']
    elif 'poster' in words and words.intersection({'send','transfer'}):
        files={'gui/pfgui.py':['Send this figure to the poster designer','add_figure_file(self.current_file)']}
        title='Send the current figure to a poster'
        steps=['Choose Tools > Send this figure to the poster designer.',
               'If the figure is new or has unsaved changes, choose Save and complete saving; Cancel stops the transfer.',
               'The poster designer opens and links the saved .pyf figure. Its PDF/SVG exports draw that figure as vectors.']
    elif ('^' in topic and words.intersection({'layout','formula','inset','notation'})) or 'a^b' in topic or 'a^a' in topic or ('inset' in words and words.intersection({'formula','notation','expression'})):
        files={'layout_formula.py':['a^b','a^a'],'recipe.py':['centre quarter']}
        title='Inset layout notation'
        steps=['In a layout formula, a^b means image b is an inset in a corner of image a; the inset has no letter of its own.',
               'a^a means a zoom callout of a itself. Its initial box is the centre quarter, which you can refine in the GUI.',
               'For the mouse workflow, select the panel and use Annotations > Add zoom callout to selected panel, or open its annotation editor and convert a rectangle ROI to an inset.']
    else:return None
    hashes={}
    for relative,anchors in files.items():
        path=native/relative
        try:source=path.read_text(encoding='utf-8')
        except OSError:return dict(status='needs_review',operation_executed=False,message='Current source for this help is unavailable.')
        if not all(anchor in source for anchor in anchors):
            return dict(status='needs_review',operation_executed=False,message='The source changed; verify this feature in the current GUI before giving exact steps.')
        hashes[relative]=hashlib.sha256(source.encode()).hexdigest()
    return dict(status='source_reviewed',operation_executed=False,guides=[dict(title=title,steps=steps)],
                source_sha256=hashes,answer_style='Human GUI steps. No Python or tool commands unless explicitly requested.')

def tutorial_feature_help(topic):
    """Read authored tutorial text without importing or constructing Qt widgets."""
    import html
    words=set(re.findall(r'[a-z]+',topic.lower()))
    concepts=None
    if 'projection' in words:concepts=('projection',)
    elif 'montage' in words:concepts=('montage',)
    elif 'orthogonal' in words:concepts=('orthogonal',)
    elif words.intersection({'consolidate','portable','archive'}):concepts=('consolidat',)
    elif words.intersection({'reconnect','relink','remap'}) or ('missing' in words and 'image' in words):concepts=('remap','moved file')
    elif 'replace' in words and words.intersection({'picture','image','panel'}):concepts=('replac',)
    if concepts is None:return None
    source=Path(__file__).resolve().parents[2]/'pyfigures/gui/tutorial.py'
    try:text=source.read_text(encoding='utf-8')
    except OSError:return dict(status='needs_review',operation_executed=False,message='Current tutorial source unavailable.')
    choices=[]
    for function in ast.parse(text).body:
        if not isinstance(function,ast.FunctionDef) or not function.name.endswith('_steps'):continue
        for node in ast.walk(function):
            if not isinstance(node,ast.Call) or getattr(node.func,'id','')!='TutorialStep':continue
            data={item.arg:item.value for item in node.keywords}
            try:
                title=ast.literal_eval(data.get('title',node.args[0] if node.args else None))
                message=ast.literal_eval(data.get('message',node.args[1] if len(node.args)>1 else None))
            except (ValueError,TypeError):continue
            if not isinstance(title,str) or not isinstance(message,str):continue
            score=sum(10*(term in title.lower())+(term in message.lower()) for term in concepts)
            if score:choices.append((score,title,message,node.lineno,function.name))
    if not choices:return dict(status='needs_review',operation_executed=False,message='No current authored tutorial step for this topic; inspect current native menus instead of inventing instructions.')
    _,title,message,line,function=max(choices,key=lambda row:row[0])
    clean=html.unescape(re.sub('<[^>]+>',' ',message.replace('<br>','\n').replace('<br/>','\n')))
    clean=re.sub(r'[ \t]+',' ',clean).strip()
    return dict(status='source_reviewed',operation_executed=False,guides=[dict(title=title,steps=[clean])],
                tutorial_source=dict(function=function,line=line,sha256=hashlib.sha256(text.encode()).hexdigest()),
                answer_style='Human GUI steps from the current authored tutorial. No API commands or Python.')

def explain(topic='overview'):
    feature=current_feature_help(topic)
    if feature is not None:return feature
    from pyfigures.guides import find_guide, explain as native_explain
    # Task guides answer these exactly; the word routes below would send "draw a
    # rectangle" to edit_roi, "editable text" slides to edit_text, a projection or
    # a moved image to an unrelated tutorial step.
    task,_=find_guide(topic)
    if task in ('draw_roi','remove_inset','scale_bar_units','max_projection','remap_images','export_pptx','reorder_panels','flip_image'):
        result=native_explain(task)
        result['answer_style']='Human GUI steps; code only when explicitly requested.'
        return result
    tutorial=tutorial_feature_help(topic)
    if tutorial is not None:return tutorial
    from pyfigures.guides import explain as native_explain, GUIDES
    # Prefer the current authored native guides to prototype-era supplements.
    words=set(re.findall(r'[a-z]+',topic.lower()))
    target=None
    if words.intersection({'rectangle','ellipse','polygon'}) or ('line' in words and words.intersection({'plain','no','without'})):
        target='edit_roi'
    elif words.intersection({'text','note','wording','word','phrase'}) and not words.intersection({'caption','scale','bar','bars'}):
        target='edit_text'
    elif words.intersection({'scale','bar','bars'}) and words.intersection({'restyle','font','style','numbers'}):
        target='text_style'

    if 'inset' in words and words.intersection({'move','resize','border','existing','edit','remove'}):
        target='edit_inset'
    elif words.intersection({'subscript','superscript','greek'}) or ('text' in words and words.intersection({'part','word','portion','edit'})):
        target='edit_text'
    if target in GUIDES:
        result=native_explain(target)
        result['answer_style']='Human GUI steps; code only when explicitly requested.'
        return result
    current=native_explain(topic)
    if current.get('guide')=='split_channels':
        current['steps'].append('With automatic lettering enabled, each channel panel and the merge have their own panel letter; montage frames may share one letter.')
        return current
    if current.get('guide') in ('edit_roi','edit_text','edit_inset','stack_in_row','arrowheads','text_style','review_comments','figure_caption'):
        return current
    normalized=topic.lower().replace('-', '_').replace(' ', '_')
    if normalized in ('shortcuts','keyboard','rearrange','arrows'):
        from pyfigures.guides import explain as native_explain
        return native_explain('reorder_panels')
    if normalized not in ('overview','shortcuts','keyboard','rearrange','arrows','drag_and_drop','drag','drop','dnd'):
        from pyfigures.guides import explain as native_explain
        result=native_explain(topic)
        result['operation_executed']=False
        result['answer_style']='Human GUI steps; code only when explicitly requested.'
        return result
    baseline=json.loads((ROOT/'manual_help_verified.json').read_text(encoding='utf-8'))
    if fingerprints()!=baseline:
        return dict(status='needs_review',operation_executed=False,
                    message='The native interaction implementation changed since this help was reviewed. Do not invent exact shortcut or drop-menu instructions; review current GUI help.',
                    topics=['shortcuts','drag_and_drop'])
    topic=topic.lower().replace('-','_').replace(' ','_')
    keyboard=dict(title='Rearrange using arrow keys',steps=[
        'Click in the figure and check the selection outline. To reach an image within a selected group, click again on that image until it is the selected object.',
        'With focus on the figure, press Left (or Up) to move the selection earlier in its layout; Right (or Down) moves it later. Up is exactly the SAME operation as Left; Down is exactly the SAME operation as Right. They are not independent horizontal/vertical movement axes. Never say Up/Down transfers an image between rows. These reorder objects rather than nudge them by a pixel.',
        'A selected top-level row moves among top-level rows. An individual image inside a group moves within its parent layout. The selection level matters.',
        'Automatic lettering follows the new panel positions when enabled.',
        'Use the native Undo command to reverse the move. Keep focus out of the chat text editor when using figure shortcuts.'])
    drag=dict(title='Internal drag-and-drop choices',steps=[
        'Select one panel or one whole group, then drag it onto the intended target and release. Confirm the selection outline so you know whether you are moving an image or its row.',
        'A context menu offers the operations valid for that source, destination and nesting. Choose an operation to commit it; To cancel, release the mouse and choose Ignore or dismiss the opened context menu (Escape while that menu is open). Do not promise Escape during an active drag, clicking empty canvas before release, or a Cancel-labelled menu item.',
        'Swap exchanges the dragged object and target. To row creates a new row, with the target first and the dragged item after it. To column places the target above the dragged item.',
        'Join this row/column inserts into the existing group. A dragged group offered as one block retains its internal layout; panel by panel inserts its contents individually IN ONE operation, retaining their order but removing the source group as a nested block. Do not describe multiple drops or scattered placement. Neither option is a universal default.',
        'Example: drag row [A,B,C] onto [D,E]. As a block gives [D,E,group(A,B,C)]; panel by panel gives [D,E,A,B,C]. You choose a menu option for one drop.',
        'Take [target] into the dragged row/column puts the target into the dragged group, as its last panel.',
        'Extrude takes the selected image out of its group into a row of its own.',
        'The preview sketches and tooltips describe the available outcomes. Some equivalent choices may be removed, so do not promise every choice for every drop.',
        'This native internal drag path handles a single selected object, which may itself be a whole group. Do not promise dragging a multi-selection as one operation; this is different from importing multiple files.',
        'External file drops and modifier-dependent alternatives require their own verified guide; do not invent file replacement or copy modifiers from these internal-drop rules.'])
    split=dict(title='Split image channels using the native GUI',steps=[
        'Select the image panel, then RIGHT-CLICK that image to open its context menu.',
        'Choose Split > Channel split (Gray mode) for grayscale channel panels. Channel split (Magenta/Green mode) is a separate option in that Split submenu.',
        'The channel choices appear only when the selected image has multiple channels. Split by a dimension is offered for images with extra dimensions.',
        'This is a manual how-to request: do not edit the figure. Do not substitute API parameters or recipes for the menu path. Offer to perform the split if the user asks.'])
    if 'split' in topic or 'channel' in topic: guides=[split]
    elif topic in ('shortcuts','keyboard','rearrange','arrows'): guides=[keyboard]
    elif topic in ('drag_and_drop','drag','drop','dnd'): guides=[drag]
    else: guides=[keyboard,drag]
    return dict(status='source_reviewed',operation_executed=False,
                verification='Checked against native source; end-to-end gesture tests remain separate.',
                guides=guides,answer_style='Give concise human steps and relevant shortcuts. No tool commands or Python unless explicitly requested.')
