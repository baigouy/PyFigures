"""Reads and writes .pyfposter (single-page) and .pyfalbum (multi-page) files.

A small, self-contained XML format (via the stdlib xml.etree, not batoolset's
reflective object_to_xml/create_object serializer used by .pyf) with distinct
root tags per format. Kept independent on purpose: neither must ever be
mistaken for, or opened as, a scientific-figure .pyf file, and vice versa.

.pyfposter (root <PosterDocument>) is exactly one page — the original format,
untouched for backward compatibility. .pyfalbum (root <PosterAlbum>) is an
ordered list of <Page> elements (a photo album: front cover, interior
spreads, back cover, ...), each holding the same <Background>/<Image>/<Text>
children a .pyfposter's root does — see PosterCanvas.suggested_filetype(),
which picks .pyfalbum the moment a document has more than one plain page.
"""
import io
import os
import xml.etree.ElementTree as ET

from pyfigures.poster.poster_shapes import (
    PosterImage, PosterBackground, PosterText, PosterPage, TEMPLATE_SENTINEL,
)

ROOT_TAG = 'PosterDocument'
ALBUM_ROOT_TAG = 'PosterAlbum'
FORMAT_VERSION = '1'

# Every file reference (image, background, source .pyf) is written twice:
# `path` (absolute, as before) and `rel_path` (relative to the document's own
# folder). On load the absolute path wins while it exists; when it doesn't —
# the folder was moved, copied to another computer, or it is a source-data
# bundle unzipped elsewhere — the relative one is tried. Older files without
# rel_path load exactly as before.


def _rel(path, doc_dir):
    if not path or not doc_dir:
        return None
    try:
        return os.path.relpath(os.path.abspath(path), doc_dir)
    except ValueError:  # different drive on Windows: no relative form
        return None


def _resolve(path, rel_path, doc_dir):
    """The usable location of a referenced file: *path* if it exists, else
    *rel_path* under *doc_dir* if that exists, else *path* unchanged (the
    caller reports it as missing)."""
    if not path or os.path.isfile(path):
        return path
    if rel_path and doc_dir:
        candidate = os.path.normpath(os.path.join(doc_dir, rel_path))
        if os.path.isfile(candidate):
            return candidate
    return path


def _write_atomic(tree, path):
    """Write next to the target, then rename over it: an interrupted save
    (crash, full disk, killed process) leaves the previous file intact
    instead of a truncated one."""
    from pyfigures.atomic_io import write_atomic
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    write_atomic(path, buf.getvalue(), fsync=True)


def sniff_root_tag(path):
    """The root element's tag without parsing the whole file — just enough
    for PosterCanvas.load() to tell a .pyfposter from a .pyfalbum regardless
    of the file's actual extension. None if the file can't be parsed at all
    (the caller's own full parse will raise a proper error for that)."""
    root = _root_element(path)
    return None if root is None else root.tag


def _root_element(path):
    """The root element (tag + attributes only), or None. The file is opened
    here and closed on return: ET.iterparse(path) left early kept the file
    open until garbage collection (Python 3.10), and saving over the poster
    then failed on Windows (PermissionError in os.replace)."""
    try:
        with open(path, 'rb') as fh:
            for _event, elem in ET.iterparse(fh, events=('start',)):
                return elem
    except Exception:
        return None
    return None


def is_photo_album(path):
    """True for a .pyfalbum saved in photo album mode (pinned covers) — those
    open in the photo album designer, everything else in the poster
    designer. Reads only the root element, like sniff_root_tag."""
    root = _root_element(path)
    return root is not None and root.tag == ALBUM_ROOT_TAG and root.get('album_mode', '0') == '1'


def _write_page_shapes(parent_elem, background, shapes_to_draw, doc_dir=None):
    if background is not None:
        bg_attrs = {
            'path': background.path,
            'zoom': repr(background.zoom),
            'pan_x_frac': repr(background.pan_x_frac),
            'pan_y_frac': repr(background.pan_y_frac),
        }
        rel = _rel(background.path, doc_dir)
        if rel:
            bg_attrs['rel_path'] = rel
        ET.SubElement(parent_elem, 'Background', bg_attrs)

    for shape in shapes_to_draw:
        if isinstance(shape, PosterText):
            text_attrs = {
                'x_mm': repr(shape.x_mm),
                'y_mm': repr(shape.y_mm),
                'width_mm': repr(shape.width_mm),
                'height_mm': repr(shape.height_mm),
                'theta': repr(shape.theta),
            }
            if shape.group_id:
                text_attrs['group_id'] = shape.group_id
            if getattr(shape, 'style', None):
                text_attrs['style'] = shape.style
            ET.SubElement(parent_elem, 'Text', text_attrs).text = shape.html
            continue
        attrs = {
            'path': shape.path,
            'x_mm': repr(shape.x_mm),
            'y_mm': repr(shape.y_mm),
            'width_mm': repr(shape.width_mm),
            'height_mm': repr(shape.height_mm),
            'theta': repr(shape.theta),
            'frame': getattr(shape, 'frame', 'none'),
        }
        if not shape.is_template:
            rel = _rel(shape.path, doc_dir)
            if rel:
                attrs['rel_path'] = rel
        caption = getattr(shape, 'caption', None)
        if caption:
            attrs['caption'] = caption
        group_id = getattr(shape, 'group_id', None)
        if group_id:
            attrs['group_id'] = group_id
        source_pyf = getattr(shape, 'source_pyf', None)
        if source_pyf:
            attrs['source_pyf'] = source_pyf
            rel = _rel(source_pyf, doc_dir)
            if rel:
                attrs['source_pyf_rel'] = rel
        for side in ('crop_left', 'crop_top', 'crop_right', 'crop_bottom'):
            value = getattr(shape, side, 0.0)
            if value:
                attrs[side] = repr(value)
        ET.SubElement(parent_elem, 'Image', attrs)


def _read_page_shapes(parent_elem, doc_dir=None):
    background = None
    shapes_to_draw = []
    for child in parent_elem:
        if child.tag == 'Background':
            background = PosterBackground(
                _resolve(child.get('path'), child.get('rel_path'), doc_dir),
                zoom=float(child.get('zoom', 1.0)),
                pan_x_frac=float(child.get('pan_x_frac', 0.5)),
                pan_y_frac=float(child.get('pan_y_frac', 0.5)),
            )
        elif child.tag == 'Text':
            shapes_to_draw.append(PosterText(
                html=child.text or '',
                x_mm=float(child.get('x_mm', 20.0)),
                y_mm=float(child.get('y_mm', 20.0)),
                width_mm=float(child.get('width_mm')) if child.get('width_mm') else None,
                height_mm=float(child.get('height_mm')) if child.get('height_mm') else None,
                theta=float(child.get('theta', 0.0)),
                group_id=child.get('group_id'),
                style=child.get('style'),
            ))
        elif child.tag == 'Image':
            path = child.get('path')
            if path not in (None, TEMPLATE_SENTINEL):
                path = _resolve(path, child.get('rel_path'), doc_dir)
            shapes_to_draw.append(PosterImage(
                path=path,
                x_mm=float(child.get('x_mm', 0.0)),
                y_mm=float(child.get('y_mm', 0.0)),
                width_mm=float(child.get('width_mm', 80.0)),
                height_mm=float(child.get('height_mm', 60.0)),
                theta=float(child.get('theta', 0.0)),
                frame=child.get('frame', 'none'),
                caption=child.get('caption'),
                group_id=child.get('group_id'),
                crop_left=float(child.get('crop_left', 0.0)),
                crop_top=float(child.get('crop_top', 0.0)),
                crop_right=float(child.get('crop_right', 0.0)),
                crop_bottom=float(child.get('crop_bottom', 0.0)),
                source_pyf=_resolve(child.get('source_pyf'), child.get('source_pyf_rel'), doc_dir),
            ))
    return background, shapes_to_draw


def _doc_dir(path):
    return os.path.dirname(os.path.abspath(os.fspath(path)))


def save_poster(canvas, path):
    root = ET.Element(ROOT_TAG, {
        'version': FORMAT_VERSION,
        'page_width_mm': repr(canvas.page_width_mm),
        'page_height_mm': repr(canvas.page_height_mm),
    })
    _write_page_shapes(root, canvas.background, canvas.shapes_to_draw, _doc_dir(path))

    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    _write_atomic(tree, path)


def load_poster(canvas, path):
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != ROOT_TAG:
        raise ValueError(f'{path} is not a poster file (expected <{ROOT_TAG}>, found <{root.tag}>)')

    canvas.page_width_mm = float(root.get('page_width_mm', canvas.page_width_mm))
    canvas.page_height_mm = float(root.get('page_height_mm', canvas.page_height_mm))
    canvas.background, canvas.shapes_to_draw = _read_page_shapes(root, _doc_dir(path))


def save_album(canvas, path):
    root = ET.Element(ALBUM_ROOT_TAG, {
        'version': FORMAT_VERSION,
        'album_mode': '1' if getattr(canvas, 'album_mode', False) else '0',
        'current_page_index': str(getattr(canvas, 'current_page_index', 0)),
    })
    for page in canvas.pages:
        page_elem = ET.SubElement(root, 'Page', {
            'kind': page.kind,
            'width_mm': repr(page.width_mm),
            'height_mm': repr(page.height_mm),
        })
        _write_page_shapes(page_elem, page.background, page.shapes_to_draw, _doc_dir(path))

    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    _write_atomic(tree, path)


def load_album(canvas, path):
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != ALBUM_ROOT_TAG:
        raise ValueError(f'{path} is not a poster album file '
                         f'(expected <{ALBUM_ROOT_TAG}>, found <{root.tag}>)')

    pages = []
    for child in root:
        if child.tag != 'Page':
            continue
        page = PosterPage(
            width_mm=float(child.get('width_mm', 210.0)),
            height_mm=float(child.get('height_mm', 297.0)),
            kind=child.get('kind', 'single'),
        )
        page.background, page.shapes_to_draw = _read_page_shapes(child, _doc_dir(path))
        pages.append(page)
    if not pages:
        raise ValueError(f'{path} has no <Page> elements')

    canvas.pages = pages
    canvas.current_page_index = min(max(int(root.get('current_page_index', 0)), 0), len(pages) - 1)
    canvas.album_mode = root.get('album_mode', '0') == '1'
    single_or_cover = next((p for p in pages if p.kind != 'spread'), pages[0])
    canvas.base_page_width_mm = (single_or_cover.width_mm if single_or_cover.kind != 'spread'
                                 else single_or_cover.width_mm / 2.0)
    canvas.base_page_height_mm = single_or_cover.height_mm
