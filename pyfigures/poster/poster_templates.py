"""A gallery of pre-designed page layouts — PowerPoint-slide-layout style:
pick a named layout and fill its slots with real photos in one call.

This is the poster module's analogue of the main editor's Template menu
(EZFIG_GUI.templatify_figure + MCP fill_template): there, a real figure is
stripped down to reusable "@template@" slots and refilled one image at a
time; here the slots are hand-designed shapes (a big photo + three small
ones, a fan of five, a 2x2 grid...) and you fill all of them with one call
instead of positioning each image by hand.

Pure data + pure functions, no Qt — usable from the GUI (poster_window.py /
poster_layout_dialog.py) and from the headless MCP tools (poster_headless.py)
alike, same as poster_layouts.py.
"""
import math
import uuid

from pyfigures.poster.poster_shapes import PosterImage, TEMPLATE_SENTINEL

# Each layout is a fixed list of slots — fractional rects (0..1) within the
# page's margin-inset content area, in fill order (first slot is usually the
# most prominent one). An optional 'theta' (degrees) gives a couple of the
# fancier layouts a magazine-collage tilt.
LAYOUTS = {
    'single': {
        'label': 'Single photo',
        'description': 'One photo filling the page.',
        'slots': [
            {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 1.0},
        ],
    },
    'diptych': {
        'label': 'Diptych - side by side',
        'description': 'Two photos side by side.',
        'slots': [
            {'x': 0.0, 'y': 0.0, 'w': 0.48, 'h': 1.0},
            {'x': 0.52, 'y': 0.0, 'w': 0.48, 'h': 1.0},
        ],
    },
    'diptych_stacked': {
        'label': 'Diptych - stacked',
        'description': 'Two photos, one above the other.',
        'slots': [
            {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 0.48},
            {'x': 0.0, 'y': 0.52, 'w': 1.0, 'h': 0.48},
        ],
    },
    'triptych': {
        'label': 'Triptych',
        'description': 'Three photos side by side.',
        'slots': [
            {'x': 0.0, 'y': 0.0, 'w': 0.313, 'h': 1.0},
            {'x': 0.343, 'y': 0.0, 'w': 0.313, 'h': 1.0},
            {'x': 0.687, 'y': 0.0, 'w': 0.313, 'h': 1.0},
        ],
    },
    'hero_with_strip': {
        'label': 'Hero + filmstrip',
        'description': 'One large photo on top, three small ones in a row below.',
        'slots': [
            {'x': 0.0, 'y': 0.0, 'w': 1.0, 'h': 0.68},
            {'x': 0.0, 'y': 0.72, 'w': 0.313, 'h': 0.28},
            {'x': 0.343, 'y': 0.72, 'w': 0.313, 'h': 0.28},
            {'x': 0.687, 'y': 0.72, 'w': 0.313, 'h': 0.28},
        ],
    },
    'big_plus_three_side': {
        'label': 'Big photo + 3 side',
        'description': 'One large photo on the left, three stacked small ones on the right.',
        'slots': [
            {'x': 0.0, 'y': 0.0, 'w': 0.62, 'h': 1.0},
            {'x': 0.66, 'y': 0.0, 'w': 0.34, 'h': 0.313},
            {'x': 0.66, 'y': 0.343, 'w': 0.34, 'h': 0.313},
            {'x': 0.66, 'y': 0.687, 'w': 0.34, 'h': 0.313},
        ],
    },
    'grid_2x2': {
        'label': '2x2 grid',
        'description': 'Four photos in an even grid.',
        'slots': [
            {'x': 0.0, 'y': 0.0, 'w': 0.48, 'h': 0.48},
            {'x': 0.52, 'y': 0.0, 'w': 0.48, 'h': 0.48},
            {'x': 0.0, 'y': 0.52, 'w': 0.48, 'h': 0.48},
            {'x': 0.52, 'y': 0.52, 'w': 0.48, 'h': 0.48},
        ],
    },
    'grid_3x3': {
        'label': '3x3 grid',
        'description': 'Nine photos in an even grid.',
        'slots': [
            {'x': col * 0.343, 'y': row * 0.343, 'w': 0.313, 'h': 0.313}
            for row in range(3) for col in range(3)
        ],
    },
    'center_plus_corners': {
        'label': 'Center + 4 corners',
        'description': 'One large centered photo with four small ones in the corners.',
        'slots': [
            {'x': 0.22, 'y': 0.22, 'w': 0.56, 'h': 0.56},
            {'x': 0.0, 'y': 0.0, 'w': 0.2, 'h': 0.2},
            {'x': 0.8, 'y': 0.0, 'w': 0.2, 'h': 0.2},
            {'x': 0.0, 'y': 0.8, 'w': 0.2, 'h': 0.2},
            {'x': 0.8, 'y': 0.8, 'w': 0.2, 'h': 0.2},
        ],
    },
    'magazine_collage': {
        'label': 'Magazine collage',
        'description': 'Five photos at varied sizes with a slight tilt, for a scrapbook/magazine feel.',
        'slots': [
            {'x': 0.03, 'y': 0.05, 'w': 0.55, 'h': 0.55, 'theta': -3.0},
            {'x': 0.58, 'y': 0.02, 'w': 0.4, 'h': 0.32, 'theta': 2.0},
            {'x': 0.58, 'y': 0.36, 'w': 0.4, 'h': 0.32, 'theta': -2.0},
            {'x': 0.05, 'y': 0.62, 'w': 0.4, 'h': 0.34, 'theta': 3.0},
            {'x': 0.48, 'y': 0.70, 'w': 0.5, 'h': 0.26, 'theta': -1.5},
        ],
    },
}


def layout_targets(shapes):
    """What apply_layout fills when no *indices* are given: the real photos
    on the page, in z-order — not text boxes, and not empty template slots
    (those are already a layout, waiting to be filled)."""
    from pyfigures.poster.poster_shapes import PosterText
    return [s for s in shapes if not isinstance(s, PosterText) and not s.is_template]


def _select(shapes, indices):
    if indices is None:
        return layout_targets(shapes)
    return [shapes[i] for i in indices]


def list_layouts(min_images=None, max_images=None):
    """Return [{'name', 'label', 'description', 'slot_count'}, ...], optionally
    filtered to layouts whose slot count falls in [min_images, max_images]."""
    out = []
    for name, spec in LAYOUTS.items():
        n = len(spec['slots'])
        if min_images is not None and n < min_images:
            continue
        if max_images is not None and n > max_images:
            continue
        out.append({'name': name, 'label': spec['label'],
                    'description': spec['description'], 'slot_count': n})
    out.sort(key=lambda d: d['slot_count'])
    return out


def layouts_for_count(n):
    """Layout names whose slot count exactly matches *n* images."""
    return [name for name, spec in LAYOUTS.items() if len(spec['slots']) == n]


def _place_in_rect(shape, slot, rect_left, rect_top, rect_w, rect_h):
    """Position/size one shape into *slot* (fractional x/y/w/h/theta, 0..1)
    mapped onto the given mm rect: fit inside (aspect preserved, never
    stretched), centered."""
    slot_w_mm = slot['w'] * rect_w
    slot_h_mm = slot['h'] * rect_h
    slot_cx = rect_left + slot['x'] * rect_w + slot_w_mm / 2.0
    slot_cy = rect_top + slot['y'] * rect_h + slot_h_mm / 2.0
    l, t, r, b = shape.frame_padding_mm()
    max_w = max(slot_w_mm - l - r, 5.0)
    max_h = max(slot_h_mm - t - b, 5.0)
    aspect = (shape.width_mm / shape.height_mm) if shape.height_mm else 1.0
    if max_w / max_h > aspect:
        shape.height_mm = max_h
        shape.width_mm = max_h * aspect
    else:
        shape.width_mm = max_w
        shape.height_mm = max_w / aspect
    shape.theta = slot.get('theta', 0.0)
    shape.set_center_mm(slot_cx, slot_cy)


def sketch_layout(page_width_mm, page_height_mm, layout_name, margin_mm=15.0, group=True):
    """Build empty template-slot placeholders (PosterImage shapes with
    path=TEMPLATE_SENTINEL) at every slot of the named layout — the page can
    be sketched out before a single photo exists, and filled in one slot at
    a time afterwards (drag-and-drop, or PosterImage.fill_template()/the
    fill_poster_template_slot MCP tool), mirroring the main editor's
    templatify_figure/fill_template workflow but built forwards instead of
    stripped down from a filled-in figure.

    By default (*group*) every placeholder gets the same new group_id, so
    dragging one moves the whole sketched layout together — no auto-alignment
    or repacking, just shared translation; each slot keeps its own
    size/rotation/fill independently. Filling a slot (fill_template) keeps
    its group_id. Set group=False for independent, ungrouped placeholders.

    Returns the new list[PosterImage] placeholders, in slot order (append
    these to the canvas's shapes_to_draw).
    """
    if layout_name not in LAYOUTS:
        raise ValueError(f'unknown layout {layout_name!r}; see list_layouts()')
    slots = LAYOUTS[layout_name]['slots']
    avail_w = max(page_width_mm - 2 * margin_mm, 1.0)
    avail_h = max(page_height_mm - 2 * margin_mm, 1.0)
    group_id = uuid.uuid4().hex[:8] if group else None
    shapes = []
    for slot in slots:
        w = slot['w'] * avail_w
        h = slot['h'] * avail_h
        x = margin_mm + slot['x'] * avail_w
        y = margin_mm + slot['y'] * avail_h
        shapes.append(PosterImage(TEMPLATE_SENTINEL, x_mm=x, y_mm=y, width_mm=w, height_mm=h,
                                  theta=slot.get('theta', 0.0), group_id=group_id))
    return shapes


def apply_layout(shapes, page_width_mm, page_height_mm, layout_name, indices=None,
                 margin_mm=15.0, band_gap_mm=10.0, repeat=True, group=True):
    """Position/size *shapes* (in fill order — page z-order, or *indices* if
    given) into the named layout's slots. Each image is scaled (aspect ratio
    preserved, never stretched) to fit inside its slot and centered there —
    the same "fit inside a cell" rule poster_layouts.grid_layout uses per cell.

    If there are more images than the layout has slots: by default (*repeat*)
    the layout repeats in horizontal bands stacked down the page — enough
    bands to place every image, each band a shrunk copy of the same slot
    pattern — so e.g. a 4-slot layout with 9 photos gives three bands of
    (up to) four, the pattern continuing rather than leaving the rest
    wherever they were. The last band is partially filled if the count isn't
    an exact multiple; with too few images for even one full slot set,
    trailing slots in that single band are simply left empty. Set
    repeat=False for the old behaviour: only the first len(slots) images are
    placed, any extras left untouched.

    By default (*group*) every placed image gets the same new group_id, so
    the whole composition can be dragged as one block afterwards — no
    auto-alignment/repacking, just shared translation; each image keeps its
    own size/rotation independently. Set group=False to leave images
    ungrouped (each moves independently, as before).
    """
    if layout_name not in LAYOUTS:
        raise ValueError(f'unknown layout {layout_name!r}; see list_layouts()')
    targets = _select(shapes, indices)
    slots = LAYOUTS[layout_name]['slots']
    slot_count = len(slots)
    if not targets or slot_count == 0:
        return

    avail_w = max(page_width_mm - 2 * margin_mm, 1.0)
    avail_h_total = max(page_height_mm - 2 * margin_mm, 1.0)
    n_bands = math.ceil(len(targets) / slot_count) if repeat else 1
    gap = band_gap_mm if n_bands > 1 else 0.0
    band_h = max((avail_h_total - gap * (n_bands - 1)) / n_bands, 5.0)
    group_id = uuid.uuid4().hex[:8] if group else None

    for band_idx in range(n_bands):
        band_top = margin_mm + band_idx * (band_h + gap)
        band_targets = targets[band_idx * slot_count: (band_idx + 1) * slot_count]
        for shape, slot in zip(band_targets, slots):
            _place_in_rect(shape, slot, margin_mm, band_top, avail_w, band_h)
            if group:
                shape.group_id = group_id
