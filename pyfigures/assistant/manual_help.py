"""Source-reviewed manual help; does not execute GUI actions."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
NAMES=('left_pressed','right_pressed','up_pressed','down_pressed','_drag_entry','internal_DND_context_menu','mouseReleaseEvent','extend')
def fingerprints():
    source=(ROOT.parent/'gui'/'ezfig.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    return {node.name:hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest()
            for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in NAMES}
def explain(topic='overview'):
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
