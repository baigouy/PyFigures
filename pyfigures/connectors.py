"""Sticky connectors and insets that follow their ROI.

A connector is an ordinary line (Line2D) whose two ends are attached to other
annotations of the same panel: rectangle / ellipse / polygon ROIs, texts, or
insets. Before a panel draws its annotations, every connector is re-snapped, so
it stays on its shapes when they move, as connectors do in PowerPoint (user
request 2026-11-12). An end is attached to a site of the shape's box:
"top left", "top", "top right", "right", "bottom right", "bottom",
"bottom left", "left", "center", or "auto" (the nearest pair of sites).

An inset made from an ROI remembers it (``follows_roi``) and is re-cropped to
the ROI whenever the ROI moves: an ROI moved by hand in the panel editor left
its inset showing the old region (user chat 2026-11-12).

Connectors are opt-in: nothing is connected by default.
"""
from __future__ import annotations

import math
import traceback
import uuid

# attributes the shapes keep through save / open / undo (the loader drops
# unknown constructor arguments, see install)
KEYS = ('link_id', 'connect_start', 'connect_end', 'follows_roi')
SITES = ('top left', 'top', 'top right', 'right', 'bottom right', 'bottom', 'bottom left', 'left', 'center')


def link_id(shape) -> str:
    """The shape's stable id, given on first use."""
    ident = getattr(shape, 'link_id', None)
    if not ident:
        ident = _new_id()
        shape.link_id = ident
    return str(ident)


def _new_id() -> str:
    # a letter first: an id of digits (or "1e5…") would be read back as a number
    return 'k' + uuid.uuid4().hex[:10]


def normalise_site(site) -> str:
    text = ' '.join(str(site or 'auto').lower().replace('-', ' ').replace('_', ' ').split())
    text = text.replace('upper', 'top').replace('lower', 'bottom').replace('centre', 'center')
    if text in ('middle', 'centre', 'center center'):
        text = 'center'
    if text in ('auto', 'nearest', 'closest', ''):
        return 'auto'
    if text not in SITES:
        raise ValueError(f'unknown connector site {site!r}: use auto or one of {", ".join(SITES)}')
    return text


def make_connector(first, second, first_site='auto', second_site='auto', color=None, stroke=None,
                   arrow=False):
    """A line from *first* to *second* that stays attached to both."""
    from batoolset.drawings.shapes.line2d import Line2D
    colour = color if color is not None else getattr(first, 'color', None)
    line = Line2D(0, 0, 0, 0, color=0xFFFF00 if colour is None else colour,
                  stroke=stroke if stroke is not None else (getattr(first, 'stroke', None) or 1.5),
                  arrow=arrow)
    line.connect_start = f'{link_id(first)}:{normalise_site(first_site)}'
    line.connect_end = f'{link_id(second)}:{normalise_site(second_site)}'
    return line


def is_connector(shape) -> bool:
    return bool(getattr(shape, 'connect_start', None) and getattr(shape, 'connect_end', None))


def follow_roi(inset, roi) -> None:
    """*inset* (made from *roi*) is re-cropped to *roi* whenever it moves."""
    inset.follows_roi = link_id(roi)


def site_of(box, point) -> str:
    """The site of *box* nearest to *point* (to attach a line drawn there)."""
    return min(_box_sites(box).items(), key=lambda item: math.dist(item[1], point))[0]


def attach(line, first, second, first_box, second_box, parent=None) -> None:
    """Make an existing *line* (drawn from *first* to *second*) a connector, each
    end on the site of its shape it is drawn at. With *parent*, an end that does not
    sit exactly where snap() would put it (the editor draws a cropped panel's inset
    where the figure has it) keeps that offset, so snapping does not move it."""
    specs = []
    for shape, box, point in ((first, first_box, (line.x1(), line.y1())), (second, second_box, (line.x2(), line.y2()))):
        site = site_of(box, point)
        computed = (shape_box(shape, parent) if parent is not None else None) or box
        specs.append(f'{link_id(shape)}:{site}' + _offset(computed, site, point))
    line.connect_start, line.connect_end = specs


def _offset(box, site, point) -> str:
    """':dx:dy' from *site* of *box* to *point* ('' when it is the site itself): an end
    on a rotated panel's inset sits on its tilted corner, inside its upright box."""
    sx, sy = _box_sites(box)[site]
    dx, dy = point[0] - sx, point[1] - sy
    return f':{dx:.6f}:{dy:.6f}' if abs(dx) > 1e-6 or abs(dy) > 1e-6 else ''


def xml_link_id(element) -> str:
    """link_id of a shape stored in a .pyf (file tools), given on first use."""
    from .mcp_tools.core import _child_text, _encode_str, _set_child_text
    ident = _child_text(element, 'link_id')
    if not ident or str(ident) == 'None':
        ident = _new_id()
        _set_child_text(element, 'link_id', _encode_str(ident))
    return str(ident)


def xml_attach(line, first, second, first_box, second_box, first_site=None, second_site=None) -> None:
    """The file-tool form of attach(): *line*, *first*, *second* are XML elements."""
    from .mcp_tools.core import _child_text, _encode_str, _set_child_text

    def point(a, b):
        return float(_child_text(line, a) or 0), float(_child_text(line, b) or 0)
    start, end = point('x1', 'y1'), point('x2', 'y2')
    site_a = first_site or site_of(first_box, start)
    site_b = second_site or site_of(second_box, end)
    off_a = _offset(first_box, site_a, start) if site_a != 'auto' else ''
    off_b = _offset(second_box, site_b, end) if site_b != 'auto' else ''
    _set_child_text(line, 'connect_start', _encode_str(f'{xml_link_id(first)}:{site_a}{off_a}'))
    _set_child_text(line, 'connect_end', _encode_str(f'{xml_link_id(second)}:{site_b}{off_b}'))


def _box_sites(box):
    x, y, w, h = box
    return {'top left': (x, y), 'top': (x + w / 2, y), 'top right': (x + w, y), 'right': (x + w, y + h / 2),
            'bottom right': (x + w, y + h), 'bottom': (x + w / 2, y + h), 'bottom left': (x, y + h),
            'left': (x, y + h / 2), 'center': (x + w / 2, y + h / 2)}


_measuring = False
_box_cache = None      # inset boxes measured once per snap()


def shape_box(shape, parent):
    """(x, y, w, h) of *shape* in *parent*'s image pixels, where it is drawn."""
    from batoolset.drawings.shapes.image2d import Image2D
    if isinstance(shape, Image2D):
        global _measuring
        key = (id(parent), id(shape))
        if _box_cache is not None and key in _box_cache:
            return _box_cache[key]
        if parent is not None and not _measuring:
            # measured where it is drawn: an inset in a corner stacks under the panel
            # letter, whose size in image pixels depends on the panel's size, so the
            # inset sits elsewhere in the editor and in the figure (a leader line fine
            # in the editor missed the inset in the figure, user chat 2026-11-12); on a
            # rotated panel the inset stays upright while ROIs turn with the image
            from .zoom_geometry import measured_inset_corners
            _measuring = True
            try:
                corners = measured_inset_corners(parent, shape)
            except Exception:
                corners = None
            finally:
                _measuring = False
            if corners:
                xs, ys = [c.x() if hasattr(c, 'x') else c[0] for c in corners], [c.y() if hasattr(c, 'y') else c[1] for c in corners]
                box = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
                if _box_cache is not None:
                    _box_cache[key] = box
                return box
        from .zoom_geometry import inset_rect
        parent_size, inset_size = parent.get_raw_size(), shape.get_raw_size()
        if not parent_size or not inset_size:
            return None
        crops = lambda im: (im.crop_left or 0, im.crop_right or 0, im.crop_top or 0, im.crop_bottom or 0)
        return inset_rect(parent_size, crops(parent), inset_size, crops(shape),
                          shape.fraction_of_parent_image_width_if_image_is_inset or 0.25, shape.placement)
    try:
        rect = shape.boundingRect()
    except TypeError:
        rect = shape.getRect()
    except Exception:
        return None
    return rect.x(), rect.y(), rect.width(), rect.height()


def _end(spec):
    """'id:site' or 'id:site:dx:dy' -> (id, site, (dx, dy))."""
    parts = str(spec).split(':')
    offset = (0.0, 0.0)
    if len(parts) >= 4:
        try:
            offset = (float(parts[2]), float(parts[3]))
        except ValueError:
            pass
    return parts[0], (parts[1] if len(parts) > 1 and parts[1] else 'auto'), offset


def _near_border(point, box, tol):
    x, y, w, h = box
    px, py = point
    inside_outer = x - tol <= px <= x + w + tol and y - tol <= py <= y + h + tol
    inside_inner = x + tol < px < x + w - tol and y + tol < py < y + h - tol
    return inside_outer and not inside_inner


def adopt_legacy(parent, shapes) -> int:
    """Figures made before connectors (2026-11-12): an inset showing exactly an ROI's
    region follows that ROI, and a line from the ROI's border to the inset's border is
    attached to both, where it is drawn (a leader line whose end was a few pixels off
    the ROI corner stayed behind when the ROI was moved). Returns how many were adopted."""
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.line2d import Line2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    insets = [s for s in shapes if isinstance(s, Image2D) and not getattr(s, 'isText', False)
              and any((getattr(s, c, 0) or 0) for c in ('crop_left', 'crop_right', 'crop_top', 'crop_bottom'))]
    loose = [s for s in shapes if isinstance(s, Line2D) and not is_connector(s)]
    if not insets or (all(getattr(i, 'follows_roi', None) for i in insets) and not loose):
        return 0
    rois = [s for s in shapes if type(s) is Rectangle2D]
    by_id = {getattr(s, 'link_id', None): s for s in shapes if getattr(s, 'link_id', None)}
    adopted = 0
    pairs = []
    try:
        size = parent.get_raw_size() if parent is not None else None
    except Exception:
        size = None
    for inset in insets:
        roi = by_id.get(getattr(inset, 'follows_roi', None))
        if roi is None and size:
            from qtpy.QtCore import QRectF
            from batoolset.pyqts.tools import get_original_shape_from_rect_and_angle
            crop = (inset.crop_left, inset.crop_right, inset.crop_top, inset.crop_bottom)
            for r in rois:
                try:
                    found = get_original_shape_from_rect_and_angle(QRectF(0, 0, size[0], size[1]), r.getRect(),
                                                                   getattr(r, 'theta', 0) or 0)[1:]
                except Exception:
                    continue
                if all(abs(a - b) <= 2 for a, b in zip(found, crop)):
                    follow_roi(inset, r)
                    roi = r
                    adopted += 1
                    break
        if roi is not None:
            pairs.append((roi, inset))
    if getattr(parent, 'theta', 0):
        return adopted                      # inset corners need a full paint there: lines left as drawn
    from .zoom_geometry import leader_lines
    for roi, inset in pairs:
        box_r, box_i = shape_box(roi, parent), shape_box(inset, parent)
        if not box_r or not box_i:
            continue
        tol = max(3.0, 0.1 * min(box_r[2], box_r[3]))
        # the inset end was drawn where the inset sat at the size the panel had then:
        # the inset moves with the panel's letter, so it may be well off now
        reach = 0.3 * max(box_i[2], box_i[3])
        canonical = list(leader_lines(box_r, box_i, connectors=2))
        for line in loose:
            if is_connector(line) or not canonical:
                continue
            p, q = (line.x1(), line.y1()), (line.x2(), line.y2())
            if _near_border(q, box_r, tol) and not _near_border(p, box_r, tol):
                p, q = q, p
            if not _near_border(p, box_r, tol) or not _near_border(q, box_i, reach):
                continue
            # the usual funnel between the two boxes, the pair nearest this line
            best = min(canonical, key=lambda c: math.dist(c[0], p) + math.dist(c[1], q))
            canonical.remove(best)
            (x1, y1), (x2, y2) = best
            line.setLine(x1, y1, x2, y2)
            line.connect_start = f'{link_id(roi)}:{site_of(box_r, best[0])}'
            line.connect_end = f'{link_id(inset)}:{site_of(box_i, best[1])}'
            adopted += 1
    return adopted


def snap(parent, annotations=None) -> int:
    """Re-attach every connector of *parent* and re-crop the insets that follow an
    ROI. Returns how many connectors were placed."""
    global _box_cache
    if _measuring:
        return 0                            # the measuring paint of shape_box()
    if _box_cache is not None:
        return _snap(parent, annotations)
    _box_cache = {}
    try:
        return _snap(parent, annotations)
    finally:
        _box_cache = None


def _snap(parent, annotations=None) -> int:
    from batoolset.drawings.shapes.image2d import Image2D
    shapes = list(annotations if annotations is not None else (getattr(parent, 'annotations', None) or []))
    if not shapes:
        return 0
    try:
        adopt_legacy(parent, shapes)
    except Exception:
        traceback.print_exc()
    by_id = {getattr(s, 'link_id', None): s for s in shapes if getattr(s, 'link_id', None)}
    if not by_id:
        return 0
    for inset in shapes:
        roi = by_id.get(getattr(inset, 'follows_roi', None)) if isinstance(inset, Image2D) else None
        if roi is not None:
            _follow(parent, inset, roi)
    placed = 0
    for line in shapes:
        if not is_connector(line):
            continue
        (a_id, a_site, a_off), (b_id, b_site, b_off) = _end(line.connect_start), _end(line.connect_end)
        a, b = by_id.get(a_id), by_id.get(b_id)
        if a is None or b is None or a is line or b is line:
            continue
        if getattr(parent, 'theta', 0) and (isinstance(a, Image2D) or isinstance(b, Image2D)):
            # a rotated panel: the inset stays upright and its tilted corners can only be
            # measured on a full paint; the inset end stays, the ROI end follows its ROI
            _follow_one_end(line, a, b, parent, a_site, b_site, a_off, b_off)
            placed += 1
            continue
        box_a, box_b = shape_box(a, parent), shape_box(b, parent)
        if not box_a or not box_b:
            continue
        sites_a, sites_b = _box_sites(box_a), _box_sites(box_b)
        if a_site != 'auto' and b_site != 'auto':
            p, q = sites_a.get(a_site), sites_b.get(b_site)
        else:
            choices_a = [sites_a[a_site]] if a_site != 'auto' else [v for k, v in sites_a.items() if k != 'center']
            choices_b = [sites_b[b_site]] if b_site != 'auto' else [v for k, v in sites_b.items() if k != 'center']
            p, q = min(((pa, pb) for pa in choices_a for pb in choices_b),
                       key=lambda pair: math.dist(*pair))
        if p is None or q is None:
            continue
        if a_site != 'auto':
            p = (p[0] + a_off[0], p[1] + a_off[1])
        if b_site != 'auto':
            q = (q[0] + b_off[0], q[1] + b_off[1])
        line.setLine(p[0], p[1], q[0], q[1])
        placed += 1
    return placed


def _follow_one_end(line, a, b, parent, a_site, b_site, a_off, b_off):
    """Move only the end(s) of *line* attached to a non-inset shape."""
    from batoolset.drawings.shapes.image2d import Image2D
    p, q = (line.x1(), line.y1()), (line.x2(), line.y2())
    for shape, site, off, is_start in ((a, a_site, a_off, True), (b, b_site, b_off, False)):
        if isinstance(shape, Image2D) or site == 'auto':
            continue
        box = shape_box(shape, parent)
        if not box:
            continue
        sx, sy = _box_sites(box)[site]
        if is_start:
            p = (sx + off[0], sy + off[1])
        else:
            q = (sx + off[0], sy + off[1])
    line.setLine(p[0], p[1], q[0], q[1])


def _follow(parent, inset, roi):
    """Crop *inset* to *roi*'s region of *parent* (only when it changed)."""
    try:
        from qtpy.QtCore import QRectF
        from batoolset.pyqts.tools import get_original_shape_from_rect_and_angle
        size = parent.get_raw_size()
        if not size:
            return
        angle, left, right, top, bottom = get_original_shape_from_rect_and_angle(
            QRectF(0, 0, size[0], size[1]), roi.getRect(), getattr(roi, 'theta', 0) or 0)
        if (inset.crop_left, inset.crop_right, inset.crop_top, inset.crop_bottom) != (left, right, top, bottom):
            inset.crop(left, right, top, bottom)
            inset.theta = angle
    except Exception:
        traceback.print_exc()


_installed = False


def install() -> None:
    """Keep the connector attributes through save / open / undo, and snap the
    connectors before a panel draws its annotations (figure, editor, export)."""
    global _installed
    if _installed:
        return
    _installed = True
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.line2d import Line2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.ellipse2d import Ellipse2D
    from batoolset.drawings.shapes.circle2d import Circle2D
    from batoolset.drawings.shapes.polygon2d import Polygon2D
    from batoolset.drawings.shapes.polyline2d import PolyLine2D
    from batoolset.drawings.shapes.freehand2d import Freehand2D
    from batoolset.drawings.shapes.square2d import Square2D
    from batoolset.drawings.shapes.point2d import Point2D
    from batoolset.drawings.shapes.txt2d import TAText2D

    # the shapes take unknown keyword arguments and drop them: these are kept
    def keeping(init):
        def __init__(self, *args, **kwargs):
            kept = {k: kwargs.pop(k) for k in KEYS if k in kwargs}
            init(self, *args, **kwargs)
            for key, value in kept.items():
                if value not in (None, '', 'None'):
                    setattr(self, key, value)
        __init__.__wrapped__ = init
        return __init__
    for cls in (Image2D, Line2D, Rectangle2D, Ellipse2D, Circle2D, Polygon2D, PolyLine2D, Freehand2D,
                Square2D, Point2D, TAText2D):
        if '__init__' in cls.__dict__:
            cls.__init__ = keeping(cls.__dict__['__init__'])

    draw_annotations = Image2D.draw_annotations

    def drawing(self, *args, **kwargs):
        try:
            snap(self)
        except Exception:
            traceback.print_exc()
        return draw_annotations(self, *args, **kwargs)
    Image2D.draw_annotations = drawing
