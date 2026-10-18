"""Shape primitives for the poster/collage canvas.

These are intentionally independent from batoolset.drawings.shapes.image2d.Image2D:
Image2D's rotation support crops the image back to its pre-rotation rectangle,
which is exactly the behaviour posters must NOT have (the box must grow to
contain the whole rotated image, nothing clipped). Rather than bending Image2D's
crop-coupled paint/rotation code to do the opposite of what it was built for, the
poster module defines its own small, easy-to-verify image shape with no shared
state or classes with the scientific figure editor.
"""
from batoolset.settings.global_settings import set_UI
set_UI()

import math

from qtpy.QtCore import QRectF, QPointF, Qt
from qtpy.QtGui import QPixmap, QTransform, QPolygonF, QPainter, QColor, QPen, QTextDocument, QFontMetricsF

TEMPLATE_SENTINEL = '@template@'
# Same sentinel string/idea as the main editor's Image2D template slots
# (pyfigures/gui/pfgui.py templatify_figure / mcp_server.py fill_template):
# a placeholder shape with no real file, shown as an empty box, that can be
# sketched out as a layout first and filled with real photos one at a time
# later — here via PosterCanvas.sketch_layout()/fill_template_at() or by
# dragging an image onto it.

FRAME_STYLES = ('none', 'simple', 'polaroid')
# (left, top, right, bottom) mm padding around the image content, per frame style.
# Polaroid's fat bottom strip is where the caption goes, matching the real thing.
_FRAME_PADDING_MM = {
    'none': (0.0, 0.0, 0.0, 0.0),
    'simple': (3.0, 3.0, 3.0, 3.0),
    'polaroid': (6.0, 6.0, 6.0, 22.0),
}

# Markdown-style heading presets for PosterText — each is a target box
# *height* expressed as a fraction of the page height rather than a fixed
# point size, so "Heading 1" on an A0 poster comes out proportionally as
# big as "Heading 1" on an A4 page, adapted to the document instead of
# needing to be picked by hand each time (PosterText.paint already scales
# its document's font uniformly to fill the box — see poster_shapes.py's
# PosterText docstring — so the box height alone determines the rendered
# size regardless of the point size written into the HTML).
TEXT_STYLE_PRESETS = {
    'h1': {'label': 'Heading 1 (Title)', 'height_frac': 0.050, 'default_html': '<b>Heading 1</b>'},
    'h2': {'label': 'Heading 2', 'height_frac': 0.035, 'default_html': '<b>Heading 2</b>'},
    'h3': {'label': 'Heading 3', 'height_frac': 0.025, 'default_html': '<b>Heading 3</b>'},
    'body': {'label': 'Body text', 'height_frac': 0.015, 'default_html': 'Body text'},
    'caption': {'label': 'Caption', 'height_frac': 0.011, 'default_html': '<i>Caption</i>'},
}
TEXT_STYLE_ORDER = ('h1', 'h2', 'h3', 'body', 'caption')

# A multi-page document (see PosterCanvas.pages) mixes these freely:
# 'single' — a plain one-off poster page (the only kind that ever exists in
#   a document with just one page);
# 'spread' — two physical pages designed as one continuous canvas (width_mm
#   is conventionally double a single page's width) so a photo or text box
#   can freely cross the gutter, same idea as a real photobook double-page
#   spread;
# 'cover_front' / 'cover_back' — single physical pages, same tooling as any
#   other page (no separate cover editor), just conventionally first/last.
PAGE_KINDS = ('single', 'spread', 'cover_front', 'cover_back')
PAGE_KIND_LABELS = {
    'single': 'Page',
    'spread': 'Spread',
    'cover_front': 'Front cover',
    'cover_back': 'Back cover',
}


class PosterPage:
    """One page (or two-page spread) of a poster/photo-album document.

    A plain data holder — all the actual editing/painting logic stays in
    PosterCanvas, which always edits exactly one PosterPage at a time
    (`self.current_page`) via properties that proxy to it
    (page_width_mm/page_height_mm/shapes_to_draw/background), so nothing
    elsewhere needs to know a document can have more than one page.
    """

    def __init__(self, width_mm, height_mm, kind='single'):
        self.kind = kind if kind in PAGE_KINDS else 'single'
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.shapes_to_draw = []
        self.background = None


class PosterImage:
    """A freely positioned, freely rotated, never-cropped image on the poster canvas.

    (x_mm, y_mm, width_mm, height_mm) describe the *unrotated image content*
    rectangle (excluding any frame); rotation (theta, degrees, clockwise) is
    applied around the *framed card's* center, so a polaroid rotates the way a
    physical print would. The rendered/selectable bounding box grows with
    rotation instead of clipping the image, see bounding_rect_mm().
    """

    def __init__(self, path, x_mm=0.0, y_mm=0.0, width_mm=80.0, height_mm=60.0, theta=0.0,
                 frame='none', caption=None, group_id=None,
                 crop_left=0.0, crop_top=0.0, crop_right=0.0, crop_bottom=0.0, source_pyf=None):
        self.path = path
        # The original .pyf this image was flattened from (see
        # poster_canvas._render_pyf_to_png), if any — `path` itself is
        # always the rendered PNG actually shown on the page; this is only
        # ever used so consolidation (poster_headless.op_export_source_data)
        # can additionally bundle that .pyf's own source data alongside it,
        # nested inside the poster's bundle. None for a plain photo.
        self.source_pyf = source_pyf
        self.x_mm = x_mm
        self.y_mm = y_mm
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.theta = theta  # degrees
        self.locked = False
        self.frame = frame if frame in FRAME_STYLES else 'none'
        self.caption = caption
        # Shapes placed together by one apply_layout/sketch_layout call share
        # a group_id so they can be dragged as a block afterwards — no other
        # coupling (rotation/resizing stay per-image, and there is no
        # auto-alignment/repacking; free rotation doesn't fit that model).
        self.group_id = group_id
        # Fraction (0..1) of the *original* image cropped away from each
        # side — dragging a corner handle with Ctrl held trims content in
        # instead of rescaling it; see PosterCanvas's corner-handle dragging.
        self.crop_left = crop_left
        self.crop_top = crop_top
        self.crop_right = crop_right
        self.crop_bottom = crop_bottom
        self._pixmap = None
        self._pixmap_path = None
        # Set only during a vector (PDF/SVG) export: a QSvgRenderer of the
        # source .pyf rendered as vectors, drawn instead of the PNG flatten so
        # text and plots stay vector and images keep their native resolution.
        self._vector = None

    @property
    def is_template(self):
        """True for an unfilled slot sketched by sketch_layout() — a
        placeholder shown as an empty box until fill_template() gives it a
        real file, mirroring the main editor's @template@ Image2D slots."""
        return self.path in (None, TEMPLATE_SENTINEL)

    def pixmap(self):
        if self.is_template:
            return QPixmap()
        if self._pixmap is None or self._pixmap_path != self.path:
            self._pixmap = QPixmap(self.path)
            self._pixmap_path = self.path
        return self._pixmap

    def fill_template(self, image_path, source_pyf=None):
        """Turn this placeholder into a real photo. The image is fit inside
        the slot's existing box (aspect preserved, centered, never
        stretched — the same rule poster_templates.apply_layout uses per
        slot) instead of keeping whatever size the slot happened to have,
        so filling out of aspect-ratio order still looks right."""
        self.source_pyf = source_pyf
        pm = QPixmap(image_path)
        if not pm.isNull() and pm.height():
            aspect = pm.width() / pm.height()
            if self.width_mm / self.height_mm > aspect:
                new_h = self.height_mm
                new_w = new_h * aspect
            else:
                new_w = self.width_mm
                new_h = new_w / aspect
            center = self.center_mm()
            self.width_mm, self.height_mm = new_w, new_h
            self.set_center_mm(center.x(), center.y())
        self.path = image_path
        self._pixmap = None
        self._pixmap_path = None

    def frame_padding_mm(self):
        return _FRAME_PADDING_MM.get(self.frame, _FRAME_PADDING_MM['none'])

    def unrotated_rect_mm(self):
        return QRectF(self.x_mm, self.y_mm, self.width_mm, self.height_mm)

    def outer_rect_mm(self):
        """Unrotated rect of the image *plus* its frame (identical to
        unrotated_rect_mm() when frame == 'none')."""
        l, t, r, b = self.frame_padding_mm()
        return QRectF(self.x_mm - l, self.y_mm - t, self.width_mm + l + r, self.height_mm + t + b)

    def center_mm(self):
        rect = self.outer_rect_mm()
        return QPointF(rect.left() + rect.width() / 2.0, rect.top() + rect.height() / 2.0)

    def bounding_rect_mm(self):
        """Axis-aligned rect (in mm) that fully contains the rotated, framed image
        — grow, not crop."""
        rect = self.outer_rect_mm()
        if not self.theta:
            return rect
        center = self.center_mm()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(self.theta)
        transform.translate(-center.x(), -center.y())
        polygon = transform.map(QPolygonF(rect))
        return polygon.boundingRect()

    def set_center_mm(self, cx, cy):
        l, t, r, b = self.frame_padding_mm()
        self.x_mm = cx - (self.width_mm + r - l) / 2.0
        self.y_mm = cy - (self.height_mm + b - t) / 2.0

    def move_by_mm(self, dx, dy):
        self.x_mm += dx
        self.y_mm += dy

    def rotate_handle_pos_mm(self, handle_offset_mm=15.0):
        """Position of the rotate handle: above the (rotated) top-center of the
        framed card."""
        center = self.center_mm()
        outer = self.outer_rect_mm()
        local = QPointF(0.0, -outer.height() / 2.0 - handle_offset_mm)
        transform = QTransform()
        transform.rotate(self.theta)
        p = transform.map(local)
        return QPointF(center.x() + p.x(), center.y() + p.y())

    def corner_handles_mm(self):
        """World-space (rotated) positions of the four resize/crop handles,
        keyed 'tl'/'tr'/'bl'/'br' — the outer (framed) rect's own corners."""
        outer = self.outer_rect_mm()
        center = self.center_mm()
        local = {
            'tl': QPointF(outer.left() - center.x(), outer.top() - center.y()),
            'tr': QPointF(outer.right() - center.x(), outer.top() - center.y()),
            'bl': QPointF(outer.left() - center.x(), outer.bottom() - center.y()),
            'br': QPointF(outer.right() - center.x(), outer.bottom() - center.y()),
        }
        transform = QTransform()
        transform.rotate(self.theta)
        return {key: center + transform.map(pt) for key, pt in local.items()}

    def source_rect_px(self, pm):
        """The sub-rect of the original pixmap *pm* that crop_left/top/right/
        bottom leaves visible, in source pixel coordinates."""
        w, h = pm.width(), pm.height()
        sx = self.crop_left * w
        sy = self.crop_top * h
        sw = max(w * (1.0 - self.crop_left - self.crop_right), 1.0)
        sh = max(h * (1.0 - self.crop_top - self.crop_bottom), 1.0)
        return QRectF(sx, sy, sw, sh)

    def paint(self, painter: QPainter, mm_to_px):
        scale = mm_to_px.scale
        center = self.center_mm()
        cx_px, cy_px = mm_to_px(center.x(), center.y())
        painter.save()
        painter.translate(cx_px, cy_px)
        if self.theta:
            painter.rotate(self.theta)

        def _local(rect_mm):
            return QRectF((rect_mm.left() - center.x()) * scale, (rect_mm.top() - center.y()) * scale,
                          rect_mm.width() * scale, rect_mm.height() * scale)

        outer_local = _local(self.outer_rect_mm())
        img_local = _local(self.unrotated_rect_mm())

        if self.frame != 'none':
            shadow_offset = 2.5
            painter.fillRect(outer_local.translated(shadow_offset, shadow_offset), QColor(0, 0, 0, 70))
            painter.fillRect(outer_local, Qt.white)
            painter.setPen(QPen(QColor(180, 180, 180), 0.75))
            painter.drawRect(outer_local)

        if self.is_template:
            painter.fillRect(img_local, QColor(235, 235, 235))
            painter.setPen(QPen(QColor(150, 150, 150), 1, Qt.DashLine))
            painter.drawRect(img_local)
            r = min(img_local.width(), img_local.height()) * 0.12
            cx, cy = img_local.center().x(), img_local.center().y()
            painter.setPen(QPen(QColor(170, 170, 170), 2))
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
            painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
        elif self._vector is not None:
            # the whole (uncropped) figure, clipped to the visible part
            vis_w = max(1e-6, 1.0 - self.crop_left - self.crop_right)
            vis_h = max(1e-6, 1.0 - self.crop_top - self.crop_bottom)
            full_w = img_local.width() / vis_w
            full_h = img_local.height() / vis_h
            full = QRectF(img_local.left() - self.crop_left * full_w,
                          img_local.top() - self.crop_top * full_h, full_w, full_h)
            painter.save()
            painter.setClipRect(img_local, Qt.IntersectClip)
            self._vector.render(painter, full, img_local)
            painter.restore()
        else:
            pm = self.pixmap()
            if not pm.isNull():
                painter.drawPixmap(img_local, pm, self.source_rect_px(pm))
            else:
                painter.fillRect(img_local, Qt.lightGray)
                painter.drawRect(img_local)

        if self.frame == 'polaroid' and self.caption:
            font = painter.font()
            # sized in this card's own units: a point size is converted with the
            # DEVICE's dpi, so the same caption was ~12x larger in a 1200 dpi
            # PDF than on screen / in a PNG (96 dpi) and was cut off
            device = painter.device()
            dpi = device.logicalDpiY() if device is not None and device.logicalDpiY() > 0 else 96
            size_local = max(6.0, outer_local.height() * 0.09) * 96.0 / 72.0
            caption_rect = QRectF(outer_local.left(), img_local.bottom(),
                                  outer_local.width(), outer_local.bottom() - img_local.bottom())
            font.setPointSizeF(size_local * 72.0 / dpi)
            # a long caption shrinks to fit the strip instead of being cut
            width = QFontMetricsF(font, device).horizontalAdvance(self.caption)
            avail = caption_rect.width() * 0.92
            if width > avail > 0:
                font.setPointSizeF(font.pointSizeF() * avail / width)
            painter.setFont(font)
            painter.setPen(QColor(60, 60, 60))
            painter.drawText(caption_rect, Qt.AlignCenter, self.caption)

        painter.restore()


class PosterBackground:
    """An image filling the whole page: always covers it edge-to-edge (no
    gaps), and is never rotated — distinct from PosterImage's free placement
    — but is draggable (pan/crop) and wheel-zoomable (crop tighter), like a
    draggable/zoomable version of CSS `background-size: cover`.

    *zoom* >= 1.0 (1.0 = the tightest fit that still covers the page, i.e.
    no extra cropping). *pan_x_frac*/*pan_y_frac* are 0..1 fractions of the
    available "slack" (the part of the oversized image that overflows the
    page at the current zoom): 0.5 is centered, 0/1 are the two extremes.
    Storing pan as a fraction (rather than mm/px) keeps it valid across
    zoom changes and page-size changes with no extra bookkeeping.
    """

    MIN_ZOOM = 1.0
    MAX_ZOOM = 6.0

    def __init__(self, path, zoom=1.0, pan_x_frac=0.5, pan_y_frac=0.5):
        self.path = path
        self.zoom = min(max(zoom, self.MIN_ZOOM), self.MAX_ZOOM)
        self.pan_x_frac = min(max(pan_x_frac, 0.0), 1.0)
        self.pan_y_frac = min(max(pan_y_frac, 0.0), 1.0)
        self._pixmap = None
        self._pixmap_path = None

    def pixmap(self):
        if self._pixmap is None or self._pixmap_path != self.path:
            self._pixmap = QPixmap(self.path)
            self._pixmap_path = self.path
        return self._pixmap

    def _cover_size_px(self, page_rect_px):
        """The image size (px) at the current zoom, once scaled to cover
        *page_rect_px* while preserving aspect ratio."""
        pm = self.pixmap()
        base = pm.size()
        base.scale(page_rect_px.size().toSize(), Qt.KeepAspectRatioByExpanding)
        return base.width() * self.zoom, base.height() * self.zoom

    def content_rect_px(self, page_rect_px):
        """Where the (possibly page-overflowing) image sits at the current
        zoom/pan — always fully covering *page_rect_px*."""
        pm = self.pixmap()
        if pm.isNull():
            return QRectF(page_rect_px)
        w, h = self._cover_size_px(page_rect_px)
        slack_w = max(w - page_rect_px.width(), 0.0)
        slack_h = max(h - page_rect_px.height(), 0.0)
        x = page_rect_px.left() - slack_w * self.pan_x_frac
        y = page_rect_px.top() - slack_h * self.pan_y_frac
        return QRectF(x, y, w, h)

    def set_zoom(self, zoom):
        self.zoom = min(max(zoom, self.MIN_ZOOM), self.MAX_ZOOM)

    def pan_by_px(self, dx_px, dy_px, page_rect_px):
        """Shift the image by a mouse-drag delta (canvas px), clamped so it
        keeps covering the page. No-op along an axis with no slack to move in."""
        pm = self.pixmap()
        if pm.isNull():
            return
        w, h = self._cover_size_px(page_rect_px)
        slack_w = max(w - page_rect_px.width(), 0.0)
        slack_h = max(h - page_rect_px.height(), 0.0)
        if slack_w > 0:
            self.pan_x_frac = min(max(self.pan_x_frac - dx_px / slack_w, 0.0), 1.0)
        if slack_h > 0:
            self.pan_y_frac = min(max(self.pan_y_frac - dy_px / slack_h, 0.0), 1.0)

    def reset_view(self):
        self.zoom = 1.0
        self.pan_x_frac = 0.5
        self.pan_y_frac = 0.5

    def paint(self, painter: QPainter, page_rect_px):
        pm = self.pixmap()
        if pm.isNull():
            return
        painter.save()
        painter.setClipRect(page_rect_px)
        painter.drawPixmap(self.content_rect_px(page_rect_px), pm, QRectF(pm.rect()))
        painter.restore()


class PosterText:
    """Freely positioned, freely rotated rich-text box — titles, captions,
    labels floating on the page, same free placement as PosterImage but
    with no photo/frame/crop concept.

    The box (x_mm, y_mm, width_mm, height_mm) always matches the aspect
    ratio the text naturally lays out at (set once, on creation/edit); a
    corner-handle drag scales the *whole block* — font included — rather
    than reflowing/wrapping the text, which keeps it reusing exactly
    PosterCanvas's existing aspect-locked resize-drag code (see
    PosterCanvas._apply_resize_drag) with no per-shape-type branching
    needed there. Editing the words themselves happens in a separate
    dialog (pyfigures.poster.poster_text_dialog), not via the canvas.
    """

    # No frame/crop/pixmap concept — PosterCanvas code that is genuinely
    # PosterImage-only (corner-crop, Ctrl+drag pan-crop, template slots)
    # checks isinstance(shape, PosterImage) rather than relying on these,
    # but a couple of shared code paths (template-slot drop-target scan,
    # the crop-hint text under a selection) just read this flag instead.
    is_template = False

    def __init__(self, html=None, x_mm=20.0, y_mm=20.0, width_mm=None, height_mm=None,
                 theta=0.0, group_id=None, style=None):
        self.doc = QTextDocument()
        self.doc.setDocumentMargin(2.0)
        self.doc.setHtml(html if html is not None else '<span style="font-size:24pt"><b>Title</b></span>')
        self.x_mm = x_mm
        self.y_mm = y_mm
        self.theta = theta
        self.locked = False
        self.group_id = group_id
        # Which size preset (h1/h2/.../caption, or None if never one — e.g.
        # loaded from an old file, or a bespoke width_mm/height_mm) this box
        # currently represents. Purely so the edit dialog's "Size preset"
        # combo can show what's *actually* applied instead of a neutral
        # placeholder — see PosterTextDialog. Manually corner-resizing the
        # box does not clear this; the label is just stale until the combo
        # is touched again.
        self.style = style
        nat_w, nat_h = self._natural_size_px()
        aspect = nat_w / nat_h
        if height_mm is None and width_mm is None:
            height_mm = 20.0
            width_mm = height_mm * aspect
        elif height_mm is None:
            height_mm = width_mm / aspect
        elif width_mm is None:
            width_mm = height_mm * aspect
        self.width_mm = width_mm
        self.height_mm = height_mm

    @property
    def html(self):
        return self.doc.toHtml()

    def set_html(self, html):
        """Replace the text content, then re-fit the box (see refit_box)."""
        self.doc.setHtml(html)
        self.refit_box()

    def refit_box(self):
        """Re-derive width_mm from the current height_mm and the document's
        (possibly just-changed) natural aspect ratio, centered on the old
        position — call after the text content changes (set_html, or the
        rich-text dialog editing self.doc directly) so retyping a short
        title into a long sentence doesn't leave the box squashed/stretched."""
        center = self.center_mm()
        nat_w, nat_h = self._natural_size_px()
        self.width_mm = self.height_mm * (nat_w / nat_h)
        self.set_center_mm(center.x(), center.y())

    def _layout_doc(self):
        """self.doc with its $…$ typeset as maths (batoolset.drawings.math_text),
        or self.doc itself; self.doc keeps the raw text (saved and edited)."""
        # (cached in math_text, never on self: self is saved and copied)
        try:
            from batoolset.drawings.math_text import typeset_for
            doc = typeset_for(self, self.doc)
        except Exception:
            doc = self.doc
        doc.setTextWidth(-1)
        return doc

    def _natural_size_px(self):
        self.doc.setTextWidth(-1)  # no wrapping — natural single-flow size
        sz = self._layout_doc().size()
        return max(sz.width(), 1.0), max(sz.height(), 1.0)

    def unrotated_rect_mm(self):
        return QRectF(self.x_mm, self.y_mm, self.width_mm, self.height_mm)

    # No frame padding for text — outer rect is just the box itself.
    outer_rect_mm = unrotated_rect_mm

    def center_mm(self):
        rect = self.outer_rect_mm()
        return QPointF(rect.left() + rect.width() / 2.0, rect.top() + rect.height() / 2.0)

    def bounding_rect_mm(self):
        rect = self.outer_rect_mm()
        if not self.theta:
            return rect
        center = self.center_mm()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(self.theta)
        transform.translate(-center.x(), -center.y())
        polygon = transform.map(QPolygonF(rect))
        return polygon.boundingRect()

    def set_center_mm(self, cx, cy):
        self.x_mm = cx - self.width_mm / 2.0
        self.y_mm = cy - self.height_mm / 2.0

    def move_by_mm(self, dx, dy):
        self.x_mm += dx
        self.y_mm += dy

    def rotate_handle_pos_mm(self, handle_offset_mm=15.0):
        center = self.center_mm()
        outer = self.outer_rect_mm()
        local = QPointF(0.0, -outer.height() / 2.0 - handle_offset_mm)
        transform = QTransform()
        transform.rotate(self.theta)
        p = transform.map(local)
        return QPointF(center.x() + p.x(), center.y() + p.y())

    def corner_handles_mm(self):
        outer = self.outer_rect_mm()
        center = self.center_mm()
        local = {
            'tl': QPointF(outer.left() - center.x(), outer.top() - center.y()),
            'tr': QPointF(outer.right() - center.x(), outer.top() - center.y()),
            'bl': QPointF(outer.left() - center.x(), outer.bottom() - center.y()),
            'br': QPointF(outer.right() - center.x(), outer.bottom() - center.y()),
        }
        transform = QTransform()
        transform.rotate(self.theta)
        return {key: center + transform.map(pt) for key, pt in local.items()}

    def paint(self, painter: QPainter, mm_to_px):
        scale = mm_to_px.scale
        center = self.center_mm()
        cx_px, cy_px = mm_to_px(center.x(), center.y())
        painter.save()
        painter.translate(cx_px, cy_px)
        if self.theta:
            painter.rotate(self.theta)

        box_w_px = self.width_mm * scale
        box_h_px = self.height_mm * scale
        nat_w_px, nat_h_px = self._natural_size_px()
        # Uniform font-scale so the box's aspect-locked resize (shared code
        # with PosterImage) directly controls text size — no reflow/wrap.
        font_scale = min(box_w_px / nat_w_px, box_h_px / nat_h_px)
        painter.translate(-box_w_px / 2.0, -box_h_px / 2.0)
        painter.scale(font_scale, font_scale)
        self._layout_doc().drawContents(painter)
        painter.restore()
