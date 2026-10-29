"""Automatic arrangement helpers for the poster canvas.

Plain functions that reposition/rotate a list of PosterImage shapes in place
(no Qt widgets, no PosterCanvas dependency), so both the interactive GUI
toolbar (poster_window.py) and the headless MCP tools (poster_headless.py)
can call the exact same code. Nothing here is auto-applied — a caller always
has to invoke a layout explicitly, and can target a subset of images via
`indices`.
"""
import math
import random


def default_targets(shapes):
    """What an arrangement moves when no *indices* are given: the photos
    (and empty photo slots) — never the text boxes, so scattering or
    fanning the pictures doesn't also tilt and shrink the poster's title."""
    from pyfigures.poster.poster_shapes import PosterText
    return [s for s in shapes if not isinstance(s, PosterText)]


def _select(shapes, indices):
    if indices is None:
        return default_targets(shapes)
    return [shapes[i] for i in indices]


def scatter_layout(shapes, page_width_mm, page_height_mm, indices=None,
                    seed=None, margin_mm=15.0, max_rotation_deg=25.0, fit_to_page=True):
    """'Photos thrown on a table': each targeted image gets a random center
    within the page margins and a random rotation in [-max_rotation_deg,
    +max_rotation_deg]. Overlap is expected and part of the look.

    By default (*fit_to_page*) a corner that ends up poking past the page
    edge once rotation grows its bounding box triggers a group-wide shrink
    (see _fit_group_to_page()) so nothing hangs off the page; a throw that
    already lands cleanly within the page is left untouched. Set
    fit_to_page=False to allow images to bleed past the edge.
    """
    rng = random.Random(seed)
    targets = _select(shapes, indices)
    if not targets:
        return
    lo_x, hi_x = margin_mm, max(margin_mm, page_width_mm - margin_mm)
    band = _free_band(shapes, targets, page_height_mm, margin_mm)
    lo_y, hi_y = band
    # centres far enough from the band's edges for an untilted photo to stay in it
    half_h = min(max(s.height_mm for s in targets) / 2.0, (hi_y - lo_y) / 2.0)
    lo_y, hi_y = lo_y + half_h, hi_y - half_h
    for shape in targets:
        shape.set_center_mm(rng.uniform(lo_x, hi_x), rng.uniform(lo_y, hi_y))
        shape.theta = rng.uniform(-max_rotation_deg, max_rotation_deg)
    if fit_to_page:
        _fit_group_to_page(targets, page_width_mm, page_height_mm, margin_mm=margin_mm, band=band)


def _free_band(shapes, targets, page_height_mm, margin_mm, gap_mm=6.0):
    """(top, bottom) in mm of the page height left for photos once the text
    boxes in its top and bottom thirds (a title, a footer) are kept clear:
    a grid laid over the whole page hid the poster's title under its first
    row. Falls back to the margins when the texts leave less than a third."""
    from pyfigures.poster.poster_shapes import PosterText
    top, bottom = margin_mm, page_height_mm - margin_mm
    chosen = {id(s) for s in targets}
    for s in shapes:
        if id(s) in chosen or not isinstance(s, PosterText):
            continue
        r = s.bounding_rect_mm()
        if r.bottom() <= page_height_mm / 3.0:
            top = max(top, r.bottom() + gap_mm)
        elif r.top() >= page_height_mm * 2.0 / 3.0:
            bottom = min(bottom, r.top() - gap_mm)
    if bottom - top < page_height_mm / 3.0:
        return margin_mm, page_height_mm - margin_mm
    return top, bottom


def _fit_group_to_page(shapes, page_width_mm, page_height_mm, margin_mm=10.0, band=None):
    """If *shapes*' combined bounding box (frame included) doesn't already fit
    inside the page with margin_mm to spare, uniformly shrink and recenter the
    whole group (never enlarge) so it does — relative position/spacing/tilt is
    preserved, just at a size that fits. No-op if it already fits or if
    *shapes* is empty, so a caller that already lands cleanly on the page is
    left untouched.

    *band*: (top, bottom) in mm the group must stay within vertically (the
    room left under a title / above a footer, see _free_band); the margins
    otherwise. Recentring on the whole page pulled thrown photos up over the
    poster's title."""
    if not shapes:
        return
    band_top, band_bottom = band if band else (margin_mm, page_height_mm - margin_mm)
    rects = [s.bounding_rect_mm() for s in shapes]
    left = min(r.left() for r in rects)
    right = max(r.right() for r in rects)
    top = min(r.top() for r in rects)
    bottom = max(r.bottom() for r in rects)
    if (left >= margin_mm and top >= band_top and
            right <= page_width_mm - margin_mm and bottom <= band_bottom):
        return  # already fits — don't touch it
    bbox_w = max(right - left, 1e-6)
    bbox_h = max(bottom - top, 1e-6)
    avail_w = max(page_width_mm - 2 * margin_mm, 1.0)
    avail_h = max(band_bottom - band_top, 1.0)
    scale = min(avail_w / bbox_w, avail_h / bbox_h, 1.0)
    if scale <= 0:
        return
    bbox_cx, bbox_cy = (left + right) / 2.0, (top + bottom) / 2.0
    page_cx, page_cy = page_width_mm / 2.0, (band_top + band_bottom) / 2.0
    for shape in shapes:
        c = shape.center_mm()
        shape.width_mm *= scale
        shape.height_mm *= scale
        shape.set_center_mm(page_cx + (c.x() - bbox_cx) * scale,
                            page_cy + (c.y() - bbox_cy) * scale)


def fan_defaults(page_width_mm, page_height_mm):
    """Sensible arc_layout() kwargs for a one-click 'fan out' of images already
    on a page of this size: arc center below the page, radius reaching back up
    into it. Shared by the GUI's Fan button, drag-and-drop-with-fan, and
    anything else that wants a fan without picking geometry by hand."""
    return {
        'center_x_mm': page_width_mm / 2.0,
        'center_y_mm': page_height_mm * 1.15,
        'radius_mm': page_height_mm * 0.9,
        'start_angle_deg': -50.0,
        'end_angle_deg': 50.0,
        'face': 'outward',
    }


def arc_layout(shapes, center_x_mm, center_y_mm, radius_mm, indices=None,
              start_angle_deg=-60.0, end_angle_deg=60.0, face='outward',
              page_width_mm=None, page_height_mm=None, margin_mm=10.0, fit_to_page=True):
    """Fan the images out along a circular arc — a spread hand of photographs
    or playing cards. Angle 0 points straight up from the center; the fan
    sweeps clockwise from start_angle_deg to end_angle_deg. A single image is
    placed at start_angle_deg.

    face:
      'outward' (default) - each image's own "up" points away from the
                 center, like a classic card fan.
      'inward'  - each image's "up" points toward the center.
      'none'    - images keep theta == 0; only position moves along the arc.

    If page_width_mm and page_height_mm are given and *fit_to_page* is true
    (both default), the whole fan is rescaled and recentered afterwards (see
    _fit_group_to_page()) so it always lands fully on the page, whatever
    center/radius/angles were asked for — a fan is meant to be looked at as a
    whole, not clipped at the page edge. Pass fit_to_page=False (or omit the
    page size) to get the raw geometry instead.
    """
    targets = _select(shapes, indices)
    n = len(targets)
    if n == 0:
        return
    angles = [start_angle_deg] if n == 1 else [
        start_angle_deg + (end_angle_deg - start_angle_deg) * i / (n - 1) for i in range(n)]
    for shape, angle_deg in zip(targets, angles):
        angle_rad = math.radians(angle_deg)
        cx = center_x_mm + radius_mm * math.sin(angle_rad)
        cy = center_y_mm - radius_mm * math.cos(angle_rad)
        shape.set_center_mm(cx, cy)
        if face == 'outward':
            shape.theta = angle_deg
        elif face == 'inward':
            shape.theta = angle_deg + 180.0
        else:
            shape.theta = 0.0

    if fit_to_page and page_width_mm is not None and page_height_mm is not None:
        _fit_group_to_page(targets, page_width_mm, page_height_mm, margin_mm=margin_mm)


def grid_layout(shapes, page_width_mm, page_height_mm, indices=None,
               columns=None, margin_mm=15.0, gap_mm=6.0, fit_to_page=True):
    """Even rows/columns, theta reset to 0, each image scaled (aspect
    preserved) to fill its cell — the tidy baseline layout to fall back on
    after a scatter/arc arrangement looks too chaotic. Cells are sized to fit
    the page by construction, so *fit_to_page* is mostly a safety net (kept
    for the same signature as scatter_layout/arc_layout); set it False only
    if you want to skip that final check entirely."""
    targets = _select(shapes, indices)
    n = len(targets)
    if n == 0:
        return
    if columns is None:
        columns = max(1, round(math.sqrt(n * page_width_mm / max(page_height_mm, 1.0))))
    columns = max(1, min(columns, n))
    rows = math.ceil(n / columns)
    band_top, band_bottom = _free_band(shapes, targets, page_height_mm, margin_mm, gap_mm)
    avail_w = max(page_width_mm - 2 * margin_mm - gap_mm * (columns - 1), columns * 5.0)
    avail_h = max(band_bottom - band_top - gap_mm * (rows - 1), rows * 5.0)
    cell_w = avail_w / columns
    cell_h = avail_h / rows
    for idx, shape in enumerate(targets):
        row, col = divmod(idx, columns)
        cell_cx = margin_mm + col * (cell_w + gap_mm) + cell_w / 2.0
        cell_cy = band_top + row * (cell_h + gap_mm) + cell_h / 2.0
        l, t, r, b = shape.frame_padding_mm()
        max_w = max(cell_w - l - r, 5.0)
        max_h = max(cell_h - t - b, 5.0)
        aspect = (shape.width_mm / shape.height_mm) if shape.height_mm else 1.0
        if max_w / max_h > aspect:
            shape.height_mm = max_h
            shape.width_mm = max_h * aspect
        else:
            shape.width_mm = max_w
            shape.height_mm = max_w / aspect
        shape.theta = 0.0
        shape.set_center_mm(cell_cx, cell_cy)

    if fit_to_page:
        _fit_group_to_page(targets, page_width_mm, page_height_mm, margin_mm=margin_mm,
                           band=(band_top, band_bottom))
