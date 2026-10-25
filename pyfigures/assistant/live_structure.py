"""Live document structure invariants and explicit intermediate containers."""
import json,os,math
import xml.etree.ElementTree as ET
from types import MethodType
from pyfigures.mcp_tools.core import _decode
from batoolset.drawings.shapes.group import Group
from batoolset.drawings.shapes.image2d import Image2D

PENDING='live_pending_container'
SPEC='live_pending_container_spec'

def populated(obj):
    return any(not isinstance(c,Group) or populated(c) for c in obj.content)

def xml_populated(node):
    return any(c.tag!='Group' or xml_populated(c) for c in list(node.find('content') or []))

def protect_empty_groups(data):
    root=ET.fromstring(data)
    for node in root.iter('Group'):
        content=node.find('content')
        if not xml_populated(node):
            marker=node.find(PENDING)
            if marker is None:marker=ET.SubElement(node,PENDING)
            marker.text='True'
            spec=node.find(SPEC)
            if spec is None:
                spec=ET.SubElement(node,SPEC)
                spec.text=json.dumps({c.tag:c.text for c in node if c.tag not in ('content',PENDING,SPEC)})
        else:
            marker=node.find(PENDING)
            if marker is not None:node.remove(marker)
            spec=node.find(SPEC)
            if spec is not None:node.remove(spec)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def restore_group_marker(node,obj):
    if node.findtext(PENDING)=='True' and not populated(obj):
        setattr(obj,PENDING,True)
        setattr(obj,SPEC,_decode(node.findtext(SPEC)) or '{}')
        values=json.loads(getattr(obj,SPEC))
        if 'size' in values:
            value=float(values['size'])
            if not math.isfinite(value) or value<=0:raise ValueError('Invalid declared intermediate-container size')
            obj.size=value
        obj.setRect(0,0,0,0)
    elif hasattr(obj,PENDING):
        delattr(obj,PENDING)
        if hasattr(obj,SPEC):delattr(obj,SPEC)

def install_canvas(canvas):
    if getattr(canvas,'_live_structural_repack',False):return
    native=canvas.repack_all
    def repack(this):
        original=list(this.shapes_to_draw)
        protected=[s for s in original if isinstance(s,Group) and not populated(s) and getattr(s,PENDING,False)]
        for s in original:
            if isinstance(s,Group) and populated(s) and hasattr(s,PENDING):delattr(s,PENDING)
        if not protected:return native()
        keep={id(s) for s in protected}
        this.shapes_to_draw=[s for s in original if id(s) not in keep]
        try:
            return native()
        finally:
            survivors={id(s) for s in this.shapes_to_draw}|keep
            this.shapes_to_draw=[s for s in original if id(s) in survivors]
            this.update_size()
    native_bounds=canvas.updateBounds
    def bounds(this):
        original=this.shapes_to_draw
        this.shapes_to_draw=[s for s in original if not (isinstance(s,Group) and not populated(s) and getattr(s,PENDING,False))]
        try:return native_bounds()
        finally:this.shapes_to_draw=original
    canvas.updateBounds=MethodType(bounds,canvas)
    canvas.repack_all=MethodType(repack,canvas)
    canvas._live_structural_repack=True

def source(value):
    if value is None or str(value).strip() in ('','None'):return None
    text=str(value)
    if os.path.isabs(text):return os.path.normcase(os.path.normpath(text))
    return text

def script(value):
    return '' if value is None or str(value).strip() in ('','None') else str(value).strip()

def xml_structure(data):
    def node(n):
        if n.tag=='Group':
            return ['Group',str(_decode(n.findtext('orientation')) or 'X').strip('\'"'),[node(c) for c in list(n.find('content') or []) if c.tag in ('Group','Image2D')]]
        return ['Image2D',source(_decode(n.findtext('filename'))),script(_decode(n.findtext('custom_loading_script'))),
                [node(c) for c in list(n.find('annotations') or []) if c.tag=='Image2D']]
    return [node(n) for n in ET.fromstring(data) if n.tag in ('Group','Image2D')]

def live_structure(objects):
    def node(obj):
        if isinstance(obj,Group):return ['Group',str(obj.orientation).strip('\'"'),[node(c) for c in obj.content if isinstance(c,(Group,Image2D))]]
        return ['Image2D',source(getattr(obj,'filename',None)),script(getattr(obj,'custom_loading_script',None)),
                [node(c) for c in (obj.annotations or []) if isinstance(c,Image2D)]]
    return [node(o) for o in objects if isinstance(o,(Group,Image2D))]

def verify_adoption(data,objects):
    expected=xml_structure(data);actual=live_structure(objects)
    if actual!=expected:
        raise ValueError('VERIFICATION_FAILED: native GUI adoption changed container hierarchy, panel order, sources or scripted panels; edit rolled back. Expected '+json.dumps(expected)[:1800]+'; actual '+json.dumps(actual)[:1800])
    def validate(items):
        for obj in items:
            if isinstance(obj,Group):validate(obj.content)
            elif isinstance(obj,Image2D):
                scale=float(getattr(obj,'scale',1))
                if not math.isfinite(scale) or scale<=0:
                    raise ValueError('VERIFICATION_FAILED: invalid/nonpositive image scale after adoption; edit rolled back')
                rect=obj.getRect(all=True)
                if any(not math.isfinite(v) for v in (rect.x(),rect.y(),rect.width(),rect.height())):
                    raise ValueError('VERIFICATION_FAILED: non-finite image geometry after adoption; edit rolled back')
                validate([a for a in obj.annotations or [] if isinstance(a,Image2D)])
    validate(objects)
    return {'container_and_source_structure_verified':True}

def sanitize_saved_structure(data):
    root=ET.fromstring(data);changed=False
    for node in root.iter('Group'):
        if node.findtext(PENDING)!='True' or xml_populated(node):continue
        values=json.loads(_decode(node.findtext(SPEC)) or '{}')
        for key in ('size','space','orientation','x','y','width','height'):
            field=node.find(key);value=values.get(key)
            if value is None:
                if field is not None:node.remove(field);changed=True
            elif field is None:
                ET.SubElement(node,key).text=value;changed=True
            elif field.text!=value:field.text=value;changed=True
    return ET.tostring(root,encoding='utf-8',xml_declaration=True) if changed else data

def reflow_intermediate_parent(node,obj):
    from batoolset.drawings.shapes.group import set_to_width
    full=list(obj.content)
    drawable=[c for c in full if not (isinstance(c,Group) and not populated(c))]
    if not drawable:return
    rect=obj.getRect(all=True)
    invalid=not math.isfinite(float(obj.size)) or any(not math.isfinite(v) for v in (rect.x(),rect.y(),rect.width(),rect.height()))
    if len(drawable)==len(full) and not invalid:return
    declared=_decode(node.findtext('size'));extent=_decode(node.findtext('width'))
    value=float(512 if declared is None else declared)
    width=float(value if extent is None else extent)
    if not math.isfinite(value) or value<=0 or not math.isfinite(width) or width<=0:
        raise ValueError('Invalid declared construction group size')
    obj.content=drawable;obj.size=value
    try:
        obj.set_to_size(value)
        set_to_width(obj,width)
    finally:obj.content=full
    for child in full:
        if isinstance(child,Group) and not populated(child):child.setRect(obj.x(),obj.y(),0,0)

def uninstall_canvas(canvas):
    if not getattr(canvas,'_live_structural_repack',False):return
    # Break instance-method/Qt-wrapper cycles before native widget destruction.
    for name in ('repack_all','updateBounds','_live_structural_repack'):
        if name in vars(canvas):delattr(canvas,name)

def adopt_letter_deltas(before,after,window,operation=None):
    """Honor actual native-letter deltas without freezing letters on moved media."""
    from .categorized_mcp import category_for
    if operation and category_for(operation)=="layout":return
    if operation in ('add_image','remove_image','add_group','remove_group'):return
    from .partner_gui import panels,letters,letter_info,POLICY,TAText2D
    from pyfigures.mcp_tools.core import _html_to_plain
    def indexed(data):
        out={}
        def walk(nodes,path=()):
            gi=ii=0
            for n in nodes:
                if n.tag=='Group':
                    walk(list(n.find('content') or []),path+(gi,));gi+=1
                elif n.tag=='Image2D':
                    if n.findtext('isText')!='True':out[path+(ii,)]=n
                    ii+=1
        walk(list(ET.fromstring(data)));return out
    old=indexed(before);new=indexed(after)
    targets={gp+(ix,):p for gp,ix,p in panels(window.paint.EZFIG_panel.shapes_to_draw)}
    def identity(n):
        return source(_decode(n.findtext('filename'))),script(_decode(n.findtext('custom_loading_script')))
    def signature(n):
        return tuple(n.findtext(k) for k in ('text','placement','fill_color','opacity'))
    changed=False
    for address,node in new.items():
        previous=old.get(address)
        if previous is not None and identity(previous)!=identity(node):continue
        prior=[a for a in list(previous.find('annotations') or []) if a.tag=='TAText2D' and a.findtext('is_letter')=='True'] if previous is not None else []
        incoming=[a for a in list(node.find('annotations') or []) if a.tag=='TAText2D' and a.findtext('is_letter')=='True']
        deltas=[a for a in incoming if signature(a) not in {signature(v) for v in prior}]
        if not deltas:continue
        if len(deltas)!=1:raise ValueError('Ambiguous native letter changes; edit rolled back')
        annotation=deltas[0];panel=targets[address]
        text=_decode(annotation.findtext('text')) or ''
        preview=TAText2D(text,is_letter=True,placement=_decode(annotation.findtext('placement')) or 'top left')
        fill=_decode(annotation.findtext('fill_color'))
        preview.fill_color=fill
        preview.opacity=float(annotation.findtext('opacity') or 1)
        info=letter_info(preview)
        policy=json.loads(getattr(panel,POLICY,'{}'))
        policy.update(visible=True,base=info)
        prior_text=_html_to_plain(_decode(prior[0].findtext('text')) or '') if len(prior)==1 else None
        if prior_text!=_html_to_plain(text):
            policy.update(automatic_text=False,text=_html_to_plain(text))
        for key in ('placement','font_family','font_size','color','background'):
            policy[key]=info[key]
        setattr(panel,POLICY,json.dumps(policy));changed=True
    if changed:window.update_letters()
