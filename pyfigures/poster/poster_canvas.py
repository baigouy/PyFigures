"""The poster/collage canvas: a plain QWidget with its own paint/mouse handling.

Deliberately not built on batoolset.GUI.paint2.Createpaintwidget /
pyfigures.gui.annotation_editor_former_000_TOP_vectorial2.VectorialDrawPane2 (the
scientific-figure canvas): those are tightly bound to axis-aligned trimming and
tight packing, neither of which applies here. Nothing in this file is imported by,
or imports from, ezfig.py / pfgui.py / annotation_editor_former_000_TOP_vectorial2.py.
"""
from batoolset.settings.global_settings import set_UI
set_UI()

import base64
import contextlib
import hashlib
import math
import os
import re
import subprocess
import sys
import tempfile

from qtpy.QtCore import Qt, QRectF, QPointF, QSize, QSizeF, Signal, QBuffer, QIODevice, QMarginsF
from qtpy.QtGui import QPainter, QColor, QPen, QBrush, QImage, QPdfWriter, QPageSize, QPageLayout, QTransform, QPalette
from qtpy.QtSvg import QSvgGenerator
from qtpy.QtWidgets import QWidget, QInputDialog, QFileDialog, QMessageBox, QApplication, QProgressDialog

from pyfigures.poster.poster_shapes import (
    PosterImage, PosterBackground, PosterText, PosterPage, PAGE_KIND_LABELS, PAGE_KINDS,
)
from pyfigures.poster.poster_align import compute_snaps

ROTATE_HANDLE_RADIUS_PX = 6
RESIZE_HANDLE_SIZE_PX = 7
SNAP_THRESHOLD_MM = 1.2  # relaxed from 3.0 — that felt too sticky when moving images
ROTATE_SNAP_DEGREES = 15.0
DEFAULT_ZOOM_SCALE = 3.0  # px/mm
MIN_IMAGE_SIZE_MM = 10.0
MIN_CROP_VISIBLE_FRAC = 0.15  # a crop drag can never hide more than 85% of an axis
_OPPOSITE_CORNER = {'tl': 'br', 'tr': 'bl', 'bl': 'tr', 'br': 'tl'}

# Standard photo formats only (see docs/poster.md) — deliberately narrower than
# the main editor's scientific-format list (.lif/.czi/...), which PosterImage's
# plain QPixmap loader can't read anyway.
DROP_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}
# A dropped/browsed .pyf scientific figure is flattened to a plain raster
# (see _render_pyf_to_png) and from then on IS one of the plain photo formats
# above — the poster canvas otherwise never opens or holds a live .pyf.
DROP_PYF_EXTS = {'.pyf'}
DROP_ARRANGEMENTS = ('none', 'scatter', 'fan', 'grid')
PYF_RENDER_DPI = 300
# Print-ready export re-renders a source_pyf-backed image fresh at whatever
# dpi its on-page size actually needs (see PosterCanvas._high_res_pyf_images)
# instead of compositing the fixed-300-dpi flatten — capped here so a tiny
# cropped sliver blown up huge on the page can't demand an absurd render.
MAX_PYF_REEXPORT_DPI = 1200
# A dedicated cache folder (not next to the source .pyf — that would litter
# whatever folder the user dragged it from, e.g. their Desktop) that
# survives across sessions (unlike the OS temp dir, which can be swept on
# reboot) so a saved .pyfposter can still find the render after a restart.
PYF_RENDER_CACHE_DIR = os.path.join(os.path.expanduser('~'), '.pyfigures', 'poster_pyf_renders')


def _pyf_render_path(pyf_path):
    """Deterministic cache path for *pyf_path*'s render: same .pyf always
    maps to the same output file (so re-dropping it refreshes in place
    instead of piling up copies), while two different .pyf files that
    happen to share a basename don't collide (the hash covers the full
    absolute path, the basename is just for readability)."""
    abs_path = os.path.abspath(pyf_path)
    digest = hashlib.sha1(abs_path.encode('utf-8')).hexdigest()[:10]
    base = os.path.splitext(os.path.basename(abs_path))[0]
    return os.path.join(PYF_RENDER_CACHE_DIR, f'{base}__{digest}.png')


def _render_pyf_subprocess(pyf_path, out_path, dpi, timeout=120, crop=None):
    """The actual offscreen-Qt-subprocess render call (pyfigures.gui.
    render_headless), shared by _render_pyf_to_png (drop/Add-image flatten,
    cached, with a progress dialog) and _render_pyf_for_print (print-ready
    export's on-the-fly high-res re-render, no cache, no dialog). *crop*
    (.qpic only): left, top, right, bottom fractions clipped away."""
    cmd = [sys.executable, '-m', 'pyfigures.gui.render_headless', pyf_path, out_path, '--dpi', str(dpi)]
    if crop is not None:
        cmd += ['--crop', ','.join(f'{float(v):.6f}' for v in crop)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 or not os.path.isfile(out_path):
        raise RuntimeError((result.stderr or result.stdout or 'unknown error').strip())
    return out_path


class PictureFigure:
    """A figure's paint commands (QPicture written by render_headless to a
    .qpic file), drawn like a QSvgRenderer: render(painter, rect) scales the
    whole figure into *rect*. Replaying the commands keeps text as text."""

    def __init__(self, path):
        import json
        from qtpy.QtGui import QPicture
        self._picture = QPicture()
        self._ok = self._picture.load(path)
        # the figure's size in points and the dpi it was recorded at (the
        # .json written beside it by the figure's save())
        try:
            with open(path + '.json', encoding='utf-8') as f:
                info = json.load(f)
            self._w = float(info['width_pt'])
            self._h = float(info['height_pt'])
            self._dpi = float(info.get('picture_dpi') or self._picture.logicalDpiX())
        except Exception:
            self._ok = False
            self._w = self._h = 0.0
            self._dpi = 96.0

    def isValid(self):
        return self._ok and self._w > 0 and self._h > 0

    def defaultSize(self):
        from qtpy.QtCore import QSize
        return QSize(int(round(self._w)), int(round(self._h)))

    def render(self, painter, rect, clip=None):
        # *clip* is not needed: the poster crop is recorded in the picture
        # drawPicture scales by (device dpi / picture dpi) on its own: undo it
        device_dpi = painter.device().logicalDpiX() or self._dpi
        undo = self._dpi / device_dpi
        painter.save()
        painter.translate(rect.left(), rect.top())
        painter.scale(rect.width() / self._w * undo, rect.height() / self._h * undo)
        painter.drawPicture(0, 0, self._picture)
        painter.restore()


class SvgFigureEmbed:
    """Poster SVG export: a figure is not drawn through Qt (its SVG renderer
    turns text into outlines, its SVG writer drops clips); a placeholder
    rectangle in a unique colour is drawn instead, and embed_svg_figures()
    then replaces it, in the written file, with the figure's own SVG: real
    <text>, under the placeholder's transform, clipped by an SVG clipPath to
    the poster crop."""

    def __init__(self, svg_path, index):
        self.svg_path = svg_path
        self.marker = '#fe%02x%02x' % (1 + index // 250, 1 + index % 250)
        self.placements = []         # (figure rect, clip rect, opacity), in drawing order

    def isValid(self):
        return os.path.isfile(self.svg_path)

    def render(self, painter, rect, clip=None):
        # *clip*: the visible (cropped) part, in the same coordinates as *rect*
        # (Qt's SVG painter does not report its clip back)
        self.placements.append((QRectF(rect), QRectF(clip) if clip is not None else QRectF(rect),
                                painter.opacity()))
        painter.save()
        painter.setOpacity(1.0)
        painter.fillRect(rect, QColor(self.marker))
        painter.restore()


def _svg_inner(svg_text, prefix):
    """The figure SVG's content (root children, minus title/desc), its
    viewBox, with every id prefixed so it cannot clash with the poster's."""
    root = re.search(r'<svg\b[^>]*>', svg_text)
    vb = re.search(r'viewBox="([^"]+)"', root.group(0))
    x, y, w, h = (float(v) for v in vb.group(1).replace(',', ' ').split())
    body = svg_text[root.end():svg_text.rfind('</svg>')]
    body = re.sub(r'<title>.*?</title>|<desc>.*?</desc>', '', body, flags=re.S)
    body = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{prefix}{m.group(1)}"', body)
    body = re.sub(r'url\(#([^)]+)\)', lambda m: f'url(#{prefix}{m.group(1)})', body)
    body = re.sub(r'(xlink:href|href)="#([^"]+)"', lambda m: f'{m.group(1)}="#{prefix}{m.group(2)}"', body)
    return body, (x, y, w, h)


def embed_svg_figures(text, embeds):
    """Replace each SvgFigureEmbed placeholder in the poster SVG *text* by its
    figure (see SvgFigureEmbed); returns the new text. Placements are consumed."""
    n_clip = 0
    for k, emb in enumerate(embeds):
        if not emb.placements:
            continue
        with open(emb.svg_path, encoding='utf-8') as f:
            inner, (vx, vy, vw, vh) = _svg_inner(f.read(), f'pyffig{k}_')
        pattern = re.compile(r'(<g fill="' + re.escape(emb.marker) + r'"[^>]*>\s*)<rect [^>]*/>', re.I)

        def swap(m):
            nonlocal n_clip
            if not emb.placements:
                return m.group(0)
            rect, clip, opacity = emb.placements.pop(0)
            n_clip += 1
            cid = f'pyfcrop{n_clip}'
            sx = rect.width() / vw
            sy = rect.height() / vh
            op = f' opacity="{opacity:g}"' if opacity < 1 else ''
            group = re.sub(r'fill="' + re.escape(emb.marker) + '"', 'fill="none"', m.group(1), flags=re.I)
            return (group
                    + f'<defs><clipPath id="{cid}"><rect x="{clip.x():g}" y="{clip.y():g}" '
                      f'width="{clip.width():g}" height="{clip.height():g}"/></clipPath></defs>'
                    + f'<g clip-path="url(#{cid})"{op}><g fill="#000000" stroke="none" '
                      f'transform="matrix({sx:g},0,0,{sy:g},{rect.x() - vx * sx:g},{rect.y() - vy * sy:g})">'
                    + inner + '</g></g>')

        text = pattern.sub(swap, text)
    return text


def _render_pyf_to_png(pyf_path, dpi=PYF_RENDER_DPI, parent=None):
    """Flatten a .pyf scientific figure to a plain PNG so the poster canvas
    can treat it exactly like any other photo from then on — freely
    positioned/rotated/resized/cropped, with no ongoing link back to the
    source figure (re-drop the .pyf to refresh it if the figure changes).

    Rendered via the same offscreen-Qt-subprocess pattern as everything else
    that touches .pyf rendering (pyfigures.gui.render_headless), so this
    module still never imports pfgui/ezfig.py in-process — into
    PYF_RENDER_CACHE_DIR, never next to the source file.

    This blocks the GUI thread for as long as the subprocess takes (there's
    no way to show real progress for a single subprocess call), so a modal
    "Rendering..." dialog is shown first and pumped once via processEvents()
    to make sure it actually paints before the block starts — otherwise a
    multi-second render looks exactly like a frozen window."""
    os.makedirs(PYF_RENDER_CACHE_DIR, exist_ok=True)
    out_path = _pyf_render_path(pyf_path)

    progress = QProgressDialog(f'Rendering {os.path.basename(pyf_path)}…', None, 0, 0, parent)
    progress.setWindowTitle('Please wait')
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)
    progress.setCancelButton(None)
    progress.show()
    QApplication.processEvents()
    try:
        _render_pyf_subprocess(pyf_path, out_path, dpi)
    finally:
        progress.close()
    return out_path


def _clone_shape(shape):
    """An independent copy of a PosterImage/PosterText — used by
    duplicate_page(). Rebuilt via each class's own constructor (not
    copy.deepcopy) since both hold a lazily-created Qt object (QPixmap/
    QTextDocument) that deepcopy can't safely duplicate."""
    if isinstance(shape, PosterText):
        return PosterText(html=shape.html, x_mm=shape.x_mm, y_mm=shape.y_mm,
                          width_mm=shape.width_mm, height_mm=shape.height_mm,
                          theta=shape.theta, group_id=shape.group_id, style=shape.style)
    return PosterImage(path=shape.path, x_mm=shape.x_mm, y_mm=shape.y_mm,
                       width_mm=shape.width_mm, height_mm=shape.height_mm, theta=shape.theta,
                       frame=shape.frame, caption=shape.caption, group_id=shape.group_id,
                       crop_left=shape.crop_left, crop_top=shape.crop_top,
                       crop_right=shape.crop_right, crop_bottom=shape.crop_bottom,
                       source_pyf=shape.source_pyf)


def _rect_corner(rect, corner):
    if corner == 'tl':
        return QPointF(rect.left(), rect.top())
    if corner == 'tr':
        return QPointF(rect.right(), rect.top())
    if corner == 'bl':
        return QPointF(rect.left(), rect.bottom())
    return QPointF(rect.right(), rect.bottom())  # 'br'


def _unrotate_point_mm(point_mm, pivot_mm, theta_deg):
    """Where *point_mm* would sit if the shape at *pivot_mm* were rotated
    back to theta=0 — i.e. the equivalent point in the shape's own
    (unrotated) coordinate frame, still expressed in world mm."""
    theta = math.radians(theta_deg)
    dx = point_mm.x() - pivot_mm.x()
    dy = point_mm.y() - pivot_mm.y()
    local_dx = dx * math.cos(theta) + dy * math.sin(theta)
    local_dy = -dx * math.sin(theta) + dy * math.cos(theta)
    return QPointF(pivot_mm.x() + local_dx, pivot_mm.y() + local_dy)


def _collect_dropped_image_paths(urls):
    """Local file paths from a drop's mimeData().urls(): files kept as-is
    (filtered to DROP_IMAGE_EXTS plus DROP_PYF_EXTS — a dropped .pyf is
    resolved to a rendered PNG by the caller, see dropEvent), folders walked
    recursively."""
    accepted_exts = DROP_IMAGE_EXTS | DROP_PYF_EXTS
    paths = []
    for url in urls:
        local = url.toLocalFile()
        if not local:
            continue
        local = os.path.normpath(local)   # QUrl gives '/' separators, even on Windows
        if os.path.isdir(local):
            for root, _dirs, files in os.walk(local):
                for name in sorted(files):
                    if os.path.splitext(name)[1].lower() in accepted_exts:
                        paths.append(os.path.join(root, name))
        elif os.path.isfile(local) and os.path.splitext(local)[1].lower() in accepted_exts:
            paths.append(local)
    return paths


class _MmToPx:
    """Callable coordinate mapper; keeps a `.scale` attribute so shapes can size
    themselves without each one re-deriving it from the canvas."""

    def __init__(self, scale=3.0, origin=QPointF(0.0, 0.0)):
        self.scale = scale
        self.origin = origin

    def __call__(self, x_mm, y_mm):
        return (self.origin.x() + x_mm * self.scale, self.origin.y() + y_mm * self.scale)

    def inverse(self, x_px, y_px):
        return ((x_px - self.origin.x()) / self.scale, (y_px - self.origin.y()) / self.scale)


class PosterCanvas(QWidget):
    """Public surface intentionally mirrors pyfigures.gui.ezfig.MyWidget (EZFIG_panel)
    just enough to let render_headless-style export code work unchanged elsewhere:
    `shapes_to_draw`, `get_dpi()`, `save(path, filetype=None, ...)`, `update_size()`.
    Nothing else about MyWidget/EZFIG_panel is shared or reused.
    """

    # Emitted after every checkpoint push/undo/redo — a window connects this
    # to refresh its Undo/Redo button enabled-state (see can_undo/can_redo).
    undo_redo_changed = Signal()

    def __init__(self, page_width_mm=210.0, page_height_mm=297.0, parent=None):
        super().__init__(parent)
        # A document is an ordered list of PosterPage objects — almost always
        # just one (a plain poster), but a photo album adds more via
        # add_page() (spreads/covers, see poster_shapes.PAGE_KINDS). Only
        # `current_page` is ever edited/painted; page_width_mm/page_height_mm/
        # shapes_to_draw/background below are properties that proxy to it, so
        # the rest of this class (and poster_headless.py/serialization.py)
        # never needs to know how many pages the document actually has.
        self.pages = [PosterPage(page_width_mm, page_height_mm, kind='single')]
        self.current_page_index = 0
        # The document's own "one physical page" size, independent of
        # whatever kind/width the *current* page happens to be — add_page()
        # sizes a new spread/cover off this, not off current_page, so adding
        # a spread right after another spread doesn't double an already-
        # doubled width. Kept in sync with page 0's size by set_page_size_mm
        # for as long as the document is still a single plain page.
        self.base_page_width_mm = page_width_mm
        self.base_page_height_mm = page_height_mm
        # Photo-album mode: front/back covers are pinned at the two ends
        # (single pages) and every interior page is enforced to be a
        # 'spread' (one continuous two-page canvas, so a photo/text can
        # freely cross the middle) — see new_document(album=True). False is a plain
        # poster: any single page, no enforcement at all.
        self.album_mode = False
        self.selected = None
        # An ad hoc multi-shape selection for the Align/Distribute toolbar
        # actions (Shift+click to add/remove a shape) — distinct from a
        # layout group_id: this is just "these happen to be selected right
        # now", not a persistent block that always moves together. Dragging
        # any member with Shift not held moves the whole set (like a group
        # drag); a plain click elsewhere clears it. Always a subset of
        # shapes_to_draw — never the background.
        self.multi_selected = []
        self.file_path = None

        self._mm_to_px = _MmToPx(scale=DEFAULT_ZOOM_SCALE, origin=QPointF(20.0, 20.0))
        self._drag_mode = None  # None | 'move' | 'rotate' | 'move_bg' | 'pan_crop'
        self._drag_last_mouse_mm = None
        self._drag_last_mouse_px = None
        self._drag_start_theta = None
        self._drag_group = None  # shapes moving together with the current drag
        self._resize_state = None  # dict captured at the start of a corner resize/crop drag
        self._crop_pan_state = None  # dict captured at the start of a Ctrl+drag crop-pan
        self._guides = []

        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._resize_to_page()

        self._undo_redo_init()
        self._push_undo_checkpoint()  # baseline: an empty/blank document is itself undoable-to

    # ---- undo/redo (whole-document snapshots) --------------------------------

    def _undo_redo_init(self):
        """(Re)start undo/redo history from scratch — called once from
        __init__ and again from new_document()/load(), so a freshly created
        or opened document never inherits the previous document's history.
        Each checkpoint is a full .pyfalbum snapshot written to a private
        temp dir (mirrors pyfigures.gui.pfgui.py's own undo/redo: a whole-
        state snapshot stack, not a per-action command/diff stack) — this
        trivially covers every kind of edit (shape move/resize/crop, text,
        page add/remove/reorder, album-mode toggle, ...) with no per-action
        undo logic to keep in sync as new edit kinds get added."""
        old = getattr(self, '_undo_temp_dir', None)
        if old is not None:
            try:
                old.cleanup()
            except Exception:
                pass
        self._undo_temp_dir = tempfile.TemporaryDirectory(prefix='pyfigures_poster_undo_')
        self._undo_stack = []  # ordered list of snapshot file paths
        self._undo_pos = -1  # index into _undo_stack of the currently-live state
        self._undo_counter = 0
        self._undo_suspended = False
        # Undo position that matches the file on disk (or the blank document):
        # the document is "modified" whenever the live state is any other
        # snapshot — so undoing back to the saved state makes it clean again.
        self._saved_undo_pos = 0

    def is_modified(self):
        return self._undo_pos != self._saved_undo_pos

    def mark_saved(self):
        self._saved_undo_pos = self._undo_pos
        self.undo_redo_changed.emit()

    def can_undo(self):
        return self._undo_pos > 0

    def can_redo(self):
        return self._undo_pos < len(self._undo_stack) - 1

    @contextlib.contextmanager
    def _batch_edit(self):
        """Wrap several primitive edits (each of which would otherwise push
        its own checkpoint, e.g. add_image() called once per dropped photo
        plus an auto-arrange) so the whole gesture undoes/redoes as one step
        instead of several. Safe to nest — only the outermost call actually
        pushes a checkpoint."""
        was_suspended = self._undo_suspended
        self._undo_suspended = True
        try:
            yield
        finally:
            self._undo_suspended = was_suspended
        self._push_undo_checkpoint()

    def _push_undo_checkpoint(self):
        """Call after any user-visible edit completes. A no-op while
        _undo_suspended (mid-batch-edit, or mid-undo/redo restore)."""
        if self._undo_suspended:
            return
        try:
            from pyfigures.poster.serialization import save_album
            path = os.path.join(self._undo_temp_dir.name, f'state_{self._undo_counter}.pyfalbum')
            self._undo_counter += 1
            save_album(self, path)
            if self._undo_pos < self._saved_undo_pos < len(self._undo_stack):
                # the saved state was on the redo branch being discarded:
                # nothing reachable matches the file any more
                self._saved_undo_pos = -2
            del self._undo_stack[self._undo_pos + 1:]
            self._undo_stack.append(path)
            self._undo_pos = len(self._undo_stack) - 1
        except Exception:
            pass
        self.undo_redo_changed.emit()

    def _restore_snapshot(self, path):
        from pyfigures.poster.serialization import load_album
        self._undo_suspended = True
        try:
            load_album(self, path)
        finally:
            self._undo_suspended = False
        self.selected = None
        self.multi_selected = []
        self._resize_to_page()
        self.update()
        self.undo_redo_changed.emit()

    def undo(self):
        if not self.can_undo():
            return
        self._undo_pos -= 1
        self._restore_snapshot(self._undo_stack[self._undo_pos])

    def redo(self):
        if not self.can_redo():
            return
        self._undo_pos += 1
        self._restore_snapshot(self._undo_stack[self._undo_pos])

    # ---- multi-page document -------------------------------------------------

    @property
    def current_page(self):
        return self.pages[self.current_page_index]

    @property
    def page_width_mm(self):
        return self.current_page.width_mm

    @page_width_mm.setter
    def page_width_mm(self, value):
        self.current_page.width_mm = value

    @property
    def page_height_mm(self):
        return self.current_page.height_mm

    @page_height_mm.setter
    def page_height_mm(self, value):
        self.current_page.height_mm = value

    @property
    def shapes_to_draw(self):
        return self.current_page.shapes_to_draw

    @shapes_to_draw.setter
    def shapes_to_draw(self, value):
        self.current_page.shapes_to_draw = value

    @property
    def background(self):
        return self.current_page.background

    @background.setter
    def background(self, value):
        self.current_page.background = value

    def suggested_filetype(self):
        """'pyfalbum' once the document is more than a single plain page
        (multiple pages, or the one page is a cover/spread), else the
        original single-page 'pyfposter' — used by save()/save_as() so a
        document only ever "graduates" to the album format once it actually
        needs it."""
        if self.album_mode or len(self.pages) > 1 or self.pages[0].kind != 'single':
            return 'pyfalbum'
        return 'pyfposter'

    def new_document(self, width_mm=210.0, height_mm=297.0, album=False):
        """Reset to one fresh blank single page — used for File > New, so a
        previously multi-page album doesn't leave stray pages behind. With
        *album* the fresh document is a blank photo album instead (front
        cover, one spread, back cover; add/remove/move_page keep it so), as the photo
        album designer starts — not an undoable edit, a new document."""
        if album:
            self.pages = [PosterPage(width_mm, height_mm, kind='cover_front'),
                          PosterPage(width_mm * 2.0, height_mm, kind='spread'),
                          PosterPage(width_mm, height_mm, kind='cover_back')]
        else:
            self.pages = [PosterPage(width_mm, height_mm, kind='single')]
        self.current_page_index = 0
        self.base_page_width_mm = width_mm
        self.base_page_height_mm = height_mm
        self.album_mode = bool(album)
        self.selected = None
        self.multi_selected = []
        self.file_path = None
        self._resize_to_page()
        self.update()
        self._undo_redo_init()
        self._push_undo_checkpoint()

    def page_count(self):
        return len(self.pages)

    def page_label(self, index):
        page = self.pages[index]
        kind_label = PAGE_KIND_LABELS.get(page.kind, page.kind)
        return f'{index + 1}. {kind_label} ({page.width_mm:.0f}×{page.height_mm:.0f}mm)'

    def goto_page(self, index):
        if not (0 <= index < len(self.pages)) or index == self.current_page_index:
            return
        self.current_page_index = index
        self.selected = None
        self.multi_selected = []
        self._resize_to_page()
        self.update()

    def add_page(self, kind='spread', width_mm=None, height_mm=None, index=None):
        """Insert a new page of *kind* right after the current page (or at
        *index* if given) and switch to it. A 'spread' defaults to twice
        base_page_width_mm at base_page_height_mm (one continuous canvas for
        a two-page layout — content can freely cross the gutter, drawn as a
        light guide line, see _paint_content); a cover/plain page defaults to
        one base page's size.

        In album_mode, *kind* is forced to 'spread' (covers are pinned and
        made by new_document(album=True), not added by hand) and the insertion point
        is clamped to strictly between the front and back cover."""
        if self.album_mode:
            kind = 'spread'
        if width_mm is None:
            width_mm = self.base_page_width_mm * (2.0 if kind == 'spread' else 1.0)
        if height_mm is None:
            height_mm = self.base_page_height_mm
        page = PosterPage(width_mm, height_mm, kind=kind)
        insert_at = index if index is not None else self.current_page_index + 1
        if self.album_mode:
            insert_at = max(1, min(insert_at, len(self.pages) - 1))
        self.pages.insert(insert_at, page)
        self.goto_page(insert_at)
        self._push_undo_checkpoint()
        return page

    def remove_page(self, index=None):
        """Delete a page (default: the current one). No-op on the last
        remaining page — a document always has at least one page — and, in
        album_mode, no-op on the front/back cover (they're pinned; turn off
        album_mode first if a document really needs to lose its covers)."""
        if index is None:
            index = self.current_page_index
        if not (0 <= index < len(self.pages)) or len(self.pages) <= 1:
            return False
        if self.album_mode and self._is_cover_slot(index):
            return False
        del self.pages[index]
        self.current_page_index = min(index, len(self.pages) - 1)
        self.selected = None
        self.multi_selected = []
        self._resize_to_page()
        self.update()
        self._push_undo_checkpoint()
        return True

    def _is_cover_slot(self, index):
        return index in (0, len(self.pages) - 1)

    def duplicate_page(self, index=None):
        """Copy a page's content (background + every shape, independently
        re-created — not a live/shared reference) into a new page right
        after it, and switch to the copy. In album mode the covers can't be
        duplicated (a second front cover would land inside the book, a copy
        of the back cover after it) — returns None then."""
        if index is None:
            index = self.current_page_index
        if not (0 <= index < len(self.pages)):
            return None
        if self.album_mode and self._is_cover_slot(index):
            return None
        src = self.pages[index]
        new_page = PosterPage(src.width_mm, src.height_mm, kind=src.kind)
        if src.background is not None:
            new_page.background = PosterBackground(
                src.background.path, zoom=src.background.zoom,
                pan_x_frac=src.background.pan_x_frac, pan_y_frac=src.background.pan_y_frac)
        new_page.shapes_to_draw = [_clone_shape(s) for s in src.shapes_to_draw]
        self.pages.insert(index + 1, new_page)
        self.goto_page(index + 1)
        self._push_undo_checkpoint()
        return new_page

    def move_page(self, from_index, to_index):
        """Reorder a page. In album_mode, the front/back cover slots (index
        0 and the last index) can't be moved into or out of — only interior
        pages reorder among themselves."""
        if not (0 <= from_index < len(self.pages)) or not (0 <= to_index < len(self.pages)):
            return False
        last = len(self.pages) - 1
        if self.album_mode and (from_index in (0, last) or to_index in (0, last)):
            return False
        if from_index == to_index:
            return True
        page = self.pages.pop(from_index)
        self.pages.insert(to_index, page)
        # goto_page is a no-op when the index doesn't change, but a different
        # page now sits there: always re-point at it
        self.current_page_index = to_index
        self.selected = None
        self.multi_selected = []
        self._resize_to_page()
        self.update()
        self._push_undo_checkpoint()
        return True

    def set_page_kind(self, kind, index=None):
        """Change a page's kind. Refused (returns False) for an unknown kind
        and, in album mode, for anything that would break the book's
        structure: the covers stay covers and interior pages stay spreads."""
        if index is None:
            index = self.current_page_index
        if kind not in PAGE_KINDS or not (0 <= index < len(self.pages)):
            return False
        if self.album_mode:
            last = len(self.pages) - 1
            required = 'cover_front' if index == 0 else 'cover_back' if index == last else 'spread'
            if kind != required:
                return False
        if self.pages[index].kind == kind:
            return True
        self.pages[index].kind = kind
        self.update()
        self._push_undo_checkpoint()
        return True

    def export_album_pdf(self, path, dpi=300):
        """Render every page as one page of a multi-page PDF, each sized to
        its own width_mm/height_mm (a 'spread' page becomes one double-width
        PDF page — the print convention for a photobook spread) — the
        whole-document equivalent of save(path, filetype='pdf'), which only
        ever renders the current page."""
        px_per_mm = dpi / 25.4
        writer = QPdfWriter(str(path))
        writer.setResolution(dpi)
        # Qt's default margins shift the page content and clip its far edges
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
        saved_index = self.current_page_index
        painter = QPainter()
        try:
            with self._vector_pyf_images(self.pages):
                for i, page in enumerate(self.pages):
                    writer.setPageSize(QPageSize(QSizeF(page.width_mm, page.height_mm), QPageSize.Millimeter))
                    if i == 0:
                        painter.begin(writer)
                    else:
                        writer.newPage()
                    self.current_page_index = i
                    painter.setRenderHint(QPainter.Antialiasing, True)
                    mm_to_px = _MmToPx(scale=px_per_mm, origin=QPointF(0.0, 0.0))
                    self._paint_content(painter, mm_to_px)
                painter.end()
        finally:
            self.current_page_index = saved_index
            self.update()

    def export_album_web(self, out_path, dpi=150, quality=85):
        """A self-contained HTML "photo book" — one file, no PyFigures/Qt
        needed to view it, just a browser: every page rendered to a JPEG and
        embedded as a base64 data URI (so there's nothing else to attach —
        drop it in an email, on a USB stick, or on any plain web host and it
        just works), with a page-flip animation (click either side of the
        page, arrow keys, swipe on touch, or the thumbnail dots) — the whole
        point being an easy, good-looking way to share personal photos
        without asking anyone to install anything. Works for a plain
        one-page poster too (a one-page "book").

        *dpi* controls the embedded image resolution (150 is plenty for any
        screen — this isn't a print export, see export_album_print_ready for
        that); *quality* is the JPEG quality (0-100)."""
        from pyfigures.poster.poster_web_export import build_album_html
        px_per_mm = dpi / 25.4
        saved_index = self.current_page_index
        pages_data = []
        try:
            for i, page in enumerate(self.pages):
                self.current_page_index = i
                w_px = max(1, int(round(page.width_mm * px_per_mm)))
                h_px = max(1, int(round(page.height_mm * px_per_mm)))
                image = QImage(w_px, h_px, QImage.Format_ARGB32)
                image.fill(Qt.white)
                painter = QPainter(image)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                mm_to_px = _MmToPx(scale=px_per_mm, origin=QPointF(0.0, 0.0))
                self._paint_content(painter, mm_to_px)
                painter.end()

                buf = QBuffer()
                buf.open(QIODevice.WriteOnly)
                image.save(buf, 'JPG', quality)
                b64 = base64.b64encode(bytes(buf.data())).decode('ascii')
                pages_data.append({'src': f'data:image/jpeg;base64,{b64}'})
        finally:
            self.current_page_index = saved_index
            self.update()

        title = os.path.splitext(os.path.basename(str(out_path)))[0]
        html = build_album_html(pages_data, title)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return {'path': str(out_path), 'page_count': len(pages_data)}

    PRINT_FILETYPES = ('tiff', 'tif', 'eps', 'pdf', 'svg')

    def _pyf_sourced_images(self, pages):
        for page in pages:
            for shape in page.shapes_to_draw:
                if isinstance(shape, PosterImage) and shape.source_pyf and os.path.isfile(shape.source_pyf):
                    yield shape

    @contextlib.contextmanager
    def _vector_pyf_images(self, pages, kind='pdf'):
        """Vector (PDF/SVG) export only: every image flattened from a .pyf
        (PosterImage.source_pyf) is drawn from that figure re-rendered instead
        of from its PNG flatten. Plots and drawings stay vectors and the
        micrographs keep their native resolution, exactly as when the figure
        is exported on its own.

        *kind* 'pdf': the figure's paint commands (a QPicture) are replayed,
        so its text stays real, selectable text in the figure's fonts.
        *kind* 'svg': the figure's own SVG export is embedded in the written
        poster SVG (SvgFigureEmbed / embed_svg_figures, run by save()): real
        <text>, the poster crop as an SVG clipPath.

        Each figure is rendered once per export (in a subprocess, like every
        other .pyf render here); an image whose render fails keeps its PNG
        flatten. Nested calls reuse the outer one."""
        if getattr(self, '_vector_export_active', False):
            yield
            return
        self._vector_export_active = True
        self._svg_embeds = []
        tmp_dir = tempfile.mkdtemp(prefix='pyf_poster_vec_')
        rendered = {}
        touched = []
        try:
            for shape in self._pyf_sourced_images(pages):
                key = os.path.abspath(shape.source_pyf)
                crop = None
                if kind == 'pdf':
                    # the crop is recorded in the picture (see ezfig save):
                    # one render per figure and crop
                    crop = (shape.crop_left, shape.crop_top, shape.crop_right, shape.crop_bottom)
                    if not any(crop):
                        crop = None
                    key = (key, crop)
                if key not in rendered:
                    out = os.path.join(tmp_dir, f'fig_{len(rendered)}.' + ('qpic' if kind == 'pdf' else 'svg'))
                    try:
                        _render_pyf_subprocess(os.path.abspath(shape.source_pyf), out, PYF_RENDER_DPI, crop=crop)
                        if kind == 'pdf':
                            renderer = PictureFigure(out)
                        else:
                            renderer = SvgFigureEmbed(out, len(self._svg_embeds))
                            self._svg_embeds.append(renderer)
                        rendered[key] = renderer if renderer.isValid() else None
                    except Exception:
                        rendered[key] = None
                if rendered[key] is not None:
                    shape._vector = rendered[key]
                    touched.append(shape)
            yield
        finally:
            for shape in touched:
                shape._vector = None
            self._vector_export_active = False
            self._svg_embeds = []
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @contextlib.contextmanager
    def _high_res_pyf_images(self, pages, dpi):
        """Print-ready export only: every image flattened from a .pyf (see
        PosterImage.source_pyf) was cached at a fixed PYF_RENDER_DPI when
        dropped in — fine on screen, but if it's since been enlarged on the
        page, or the export dpi is higher than that flatten's own effective
        resolution, the cached copy is now the bottleneck, not the export
        settings. This re-renders each such image fresh, from its original
        .pyf, at whatever dpi its *actual on-page size* needs to match
        *dpi* — then temporarily swaps it in for the duration of the
        `with` block (restored after, live canvas or a throwaway export
        canvas alike). Skipped per-image when the cached flatten is already
        sharp enough (no needless re-render), and any image whose re-render
        fails just falls back to the cached copy rather than aborting the
        whole export."""
        target_px_per_mm = dpi / 25.4
        saved, tmp_files = [], []
        try:
            for shape in self._pyf_sourced_images(pages):
                pm = shape.pixmap()
                if pm.isNull() or not pm.width() or not pm.height():
                    continue
                visible_w = pm.width() * max(1e-6, 1.0 - shape.crop_left - shape.crop_right)
                visible_h = pm.height() * max(1e-6, 1.0 - shape.crop_top - shape.crop_bottom)
                needed_w = shape.width_mm * target_px_per_mm
                needed_h = shape.height_mm * target_px_per_mm
                scale = max(needed_w / visible_w, needed_h / visible_h)
                if scale <= 1.02:
                    continue  # cached flatten already meets or exceeds the target resolution
                new_dpi = min(round(PYF_RENDER_DPI * scale), MAX_PYF_REEXPORT_DPI)
                fd, tmp_png = tempfile.mkstemp(suffix='.png')
                os.close(fd)
                try:
                    _render_pyf_subprocess(shape.source_pyf, tmp_png, new_dpi)
                except Exception:
                    if os.path.isfile(tmp_png):
                        os.remove(tmp_png)
                    continue  # fall back to the cached flatten rather than fail the export
                saved.append((shape, shape.path))
                shape.path = tmp_png
                shape._pixmap = None
                shape._pixmap_path = None
                tmp_files.append(tmp_png)
            yield
        finally:
            for shape, old_path in saved:
                shape.path = old_path
                shape._pixmap = None
                shape._pixmap_path = None
            for f in tmp_files:
                if os.path.isfile(f):
                    os.remove(f)

    def export_print_ready(self, out_path, filetype='tiff', color_mode='cmyk', dpi=300):
        """Print-ready export of the *current* page only.

        'tiff'/'eps' go through a high-DPI RGB render converted with Pillow
        (naive, non-colour-managed RGB->CMYK — no ICC profile — same
        caveat as the main editor's export_print_ready; fine for layout/
        proofing, not colour-critical print). 'pdf'/'svg' are vector, always
        RGB (Qt has no CMYK writer for either), so *color_mode* is ignored
        for those two. Images flattened from a .pyf are drawn as vectors in
        pdf/svg (_vector_pyf_images) and, in tiff/eps, re-rendered at a
        matching resolution if the cached flatten would otherwise be the
        bottleneck (_high_res_pyf_images)."""
        filetype = filetype.lower().lstrip('.')
        if filetype not in self.PRINT_FILETYPES:
            raise ValueError(f'unsupported print filetype {filetype!r}; use one of {self.PRINT_FILETYPES}')
        if filetype in ('pdf', 'svg'):
            self.save(out_path, filetype=filetype, dpi=dpi)
            return
        with self._high_res_pyf_images([self.current_page], dpi):
            self._export_raster_print_page(out_path, filetype, color_mode=color_mode, dpi=dpi)

    def _export_raster_print_page(self, out_path, filetype, color_mode='cmyk', dpi=300):
        from PIL import Image as PILImage
        fd, tmp_png = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        try:
            self.save(tmp_png, filetype='png', dpi=dpi)
            im = PILImage.open(tmp_png)
            if im.mode in ('RGBA', 'P', 'LA'):
                bg = PILImage.new('RGB', im.size, (255, 255, 255))
                im = im.convert('RGBA')
                bg.paste(im, mask=im.split()[-1])
                im = bg
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            if color_mode == 'cmyk':
                im = im.convert('CMYK')
            out_dir = os.path.dirname(os.path.abspath(str(out_path)))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            if filetype in ('tiff', 'tif'):
                im.save(out_path, format='TIFF', dpi=(dpi, dpi), compression='tiff_lzw')
            else:  # eps — Pillow writes a plain raster-wrapped-in-PostScript
                # file; no Ghostscript needed for *writing* (only for reading
                # an EPS back), so this works with no extra dependency.
                im.save(out_path, format='EPS', dpi=(dpi, dpi))
        finally:
            if os.path.isfile(tmp_png):
                os.remove(tmp_png)

    def export_album_print_ready(self, out_path, filetype='tiff', color_mode='cmyk', dpi=300):
        """Print-ready export of the WHOLE document (every page, front cover
        through back cover).

        'pdf' is a single multi-page vector file (like export_album_pdf) —
        Qt's PDF writer is RGB-only, so *color_mode* is ignored for pdf.
        'tiff'/'eps'/'svg' have no standard multi-page container print
        software reliably accepts, so *out_path* is instead treated as a
        folder: one numbered file per page (page_01_<kind>.<ext>) plus a
        manifest.json. Returns a dict describing what was written."""
        filetype = filetype.lower().lstrip('.')
        if filetype not in self.PRINT_FILETYPES:
            raise ValueError(f'unsupported print filetype {filetype!r}; use one of {self.PRINT_FILETYPES}')

        resolution = contextlib.nullcontext() if filetype in ('pdf', 'svg') \
            else self._high_res_pyf_images(self.pages, dpi)
        with resolution, self._vector_pyf_images(self.pages if filetype in ('pdf', 'svg') else [],
                                                 kind='svg' if filetype == 'svg' else 'pdf'):
            if filetype == 'pdf':
                self.export_album_pdf(out_path, dpi=dpi)
                return {'mode': 'single_file', 'path': str(out_path), 'page_count': len(self.pages)}

            out_dir = str(out_path)
            os.makedirs(out_dir, exist_ok=True)
            ext = 'tif' if filetype in ('tiff', 'tif') else filetype
            saved_index = self.current_page_index
            manifest = []
            try:
                for i, page in enumerate(self.pages):
                    self.current_page_index = i
                    fname = f'page_{i + 1:02d}_{page.kind}.{ext}'
                    fpath = os.path.join(out_dir, fname)
                    if filetype == 'svg':
                        self.save(fpath, filetype='svg', dpi=dpi)
                    else:
                        self._export_raster_print_page(fpath, filetype, color_mode=color_mode, dpi=dpi)
                    manifest.append({'index': i, 'kind': page.kind, 'file': fname})
            finally:
                self.current_page_index = saved_index
                self.update()

        manifest_doc = {
            'color_mode': color_mode.upper() if filetype in ('tiff', 'tif', 'eps') else None,
            'dpi': dpi, 'pages': manifest,
        }
        import json
        with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(manifest_doc, f, ensure_ascii=False, indent=2)
        return {'mode': 'folder', 'path': out_dir, 'page_count': len(self.pages), 'files': manifest}

    # ---- geometry helpers -------------------------------------------------

    def _resize_to_page(self):
        margin = self._mm_to_px.origin
        w = int(self.page_width_mm * self._mm_to_px.scale + 2 * margin.x())
        h = int(self.page_height_mm * self._mm_to_px.scale + 2 * margin.y())
        self.setMinimumSize(QSize(w, h))
        self.resize(w, h)

    def page_rect_mm(self):
        return QRectF(0.0, 0.0, self.page_width_mm, self.page_height_mm)

    def page_rect_px(self):
        x0, y0 = self._mm_to_px(0.0, 0.0)
        x1, y1 = self._mm_to_px(self.page_width_mm, self.page_height_mm)
        return QRectF(x0, y0, x1 - x0, y1 - y0)

    def set_zoom(self, scale):
        self._mm_to_px.scale = max(0.2, scale)
        self._resize_to_page()
        self.update()

    def zoom_in(self):
        """+10%, mirroring the main editor's scrollableEZFIG.zoomIn()."""
        self.set_zoom(self._mm_to_px.scale * 1.1)

    def zoom_out(self):
        """-10%, mirroring the main editor's scrollableEZFIG.zoomOut()."""
        self.set_zoom(self._mm_to_px.scale * 0.9)

    def zoom_reset(self):
        self.set_zoom(DEFAULT_ZOOM_SCALE)

    def set_page_size_mm(self, width_mm, height_mm):
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError('page width and height must be positive')
        if abs(width_mm - self.page_width_mm) < 1e-9 and abs(height_mm - self.page_height_mm) < 1e-9:
            return
        self.page_width_mm = width_mm
        self.page_height_mm = height_mm
        if len(self.pages) == 1 and self.pages[0].kind == 'single':
            # Still a plain single-page document — keep the "one physical
            # page" reference size (used to size a future spread/cover) in
            # step with the page-size picker instead of freezing it at
            # whatever size the document started at.
            self.base_page_width_mm = width_mm
            self.base_page_height_mm = height_mm
        self._resize_to_page()
        self.update()
        self._push_undo_checkpoint()

    # ---- content management -------------------------------------------------

    def add_image(self, path, x_mm=None, y_mm=None, width_mm=None, height_mm=None, theta=0.0,
                  source_pyf=None):
        img = PosterImage(path, x_mm=0, y_mm=0, width_mm=80.0, height_mm=60.0, theta=theta,
                          source_pyf=source_pyf)
        pm = img.pixmap()
        if pm.isNull():
            # used to add a grey placeholder box silently; say why instead
            if not os.path.isfile(path):
                raise FileNotFoundError(f'no such image file: {path}')
            raise ValueError(f'cannot read {os.path.basename(path)} as an image '
                             f'(unsupported or corrupt file)')
        natural_w_mm = pm.width() / self._mm_to_px.scale
        natural_h_mm = pm.height() / self._mm_to_px.scale
        max_dim_mm = min(self.page_width_mm, self.page_height_mm) * 0.4
        longest = max(natural_w_mm, natural_h_mm, 1.0)
        scale = min(1.0, max_dim_mm / longest)
        img.width_mm = natural_w_mm * scale
        img.height_mm = natural_h_mm * scale
        aspect = pm.width() / pm.height()
        if width_mm is not None and height_mm is not None:
            img.width_mm, img.height_mm = width_mm, height_mm
        elif width_mm is not None:
            # one side given: keep the photo's own aspect ratio
            img.width_mm, img.height_mm = width_mm, width_mm / aspect
        elif height_mm is not None:
            img.width_mm, img.height_mm = height_mm * aspect, height_mm
        if x_mm is not None and y_mm is not None:
            img.x_mm, img.y_mm = x_mm, y_mm
        else:
            img.set_center_mm(self.page_width_mm / 2.0, self.page_height_mm / 2.0)
        self.shapes_to_draw.append(img)
        self.selected = img
        self.update()
        self._push_undo_checkpoint()
        return img

    def render_figure(self, pyf_path, dpi=PYF_RENDER_DPI):
        """Flatten a .pyf to its cached PNG (no progress dialog — the headless
        / recipe counterpart of the GUI's drop/Add-image render). Returns the
        PNG path."""
        if not os.path.isfile(pyf_path):
            raise FileNotFoundError(f'no such figure: {pyf_path}')
        os.makedirs(PYF_RENDER_CACHE_DIR, exist_ok=True)
        out = _pyf_render_path(pyf_path)
        _render_pyf_subprocess(os.path.abspath(pyf_path), out, dpi)
        return out

    def add_figure(self, pyf_path, **kwargs):
        """Add a .pyf scientific figure as a photo (flattened, remembering the
        .pyf for the source-data bundle) — same as dropping it in the GUI."""
        png = self.render_figure(pyf_path)
        return self.add_image(png, source_pyf=os.path.abspath(pyf_path), **kwargs)

    def add_text(self, html=None, x_mm=None, y_mm=None, theta=0.0, style='body'):
        from pyfigures.poster.poster_shapes import TEXT_STYLE_PRESETS
        resolved_style = style if style in TEXT_STYLE_PRESETS else 'body'
        preset = TEXT_STYLE_PRESETS[resolved_style]
        if html is None:
            html = preset['default_html']
        height_mm = self.page_height_mm * preset['height_frac']
        text = PosterText(html=html, theta=theta, height_mm=height_mm, style=resolved_style)
        if x_mm is not None and y_mm is not None:
            text.x_mm, text.y_mm = x_mm, y_mm
        else:
            text.set_center_mm(self.page_width_mm / 2.0, self.page_height_mm / 2.0)
        self.shapes_to_draw.append(text)
        self.selected = text
        self.update()
        self._push_undo_checkpoint()
        return text

    def edit_text(self, shape):
        """Open the rich-text dialog for *shape* (a PosterText); re-fits the
        box to the edited content's aspect ratio once the dialog closes —
        not on every keystroke, so the box doesn't visibly jump around
        while the user is still typing."""
        from pyfigures.poster.poster_text_dialog import PosterTextDialog
        before = (shape.html, shape.width_mm, shape.height_mm, shape.style)
        dlg = PosterTextDialog(shape, parent=self, on_change=self.update,
                               page_height_mm=self.page_height_mm)
        dlg.exec()
        shape.refit_box()
        self.update()
        if (shape.html, shape.width_mm, shape.height_mm, shape.style) != before:
            self._push_undo_checkpoint()

    def set_background(self, path):
        self.background = PosterBackground(path)
        self.selected = None
        self.update()
        self._push_undo_checkpoint()

    def clear_background(self):
        self.background = None
        if self.selected is not None and self.selected not in self.shapes_to_draw:
            self.selected = None
        self.update()
        self._push_undo_checkpoint()

    def reset_background_view(self):
        if self.background is not None:
            self.background.reset_view()
            self.update()
            self._push_undo_checkpoint()

    def delete_selected(self):
        removed = self.selected in self.shapes_to_draw
        if removed:
            self.shapes_to_draw.remove(self.selected)
        if self.selected in self.multi_selected:
            self.multi_selected.remove(self.selected)
        self.selected = None
        self.update()
        if removed:
            self._push_undo_checkpoint()

    def raise_selected(self):
        if self.selected in self.shapes_to_draw:
            self.shapes_to_draw.remove(self.selected)
            self.shapes_to_draw.append(self.selected)
            self.update()
            self._push_undo_checkpoint()

    def lower_selected(self):
        if self.selected in self.shapes_to_draw:
            self.shapes_to_draw.remove(self.selected)
            self.shapes_to_draw.insert(0, self.selected)
            self.update()
            self._push_undo_checkpoint()

    def _group_members(self, shape):
        """Every shape sharing *shape*'s group_id (including itself), or just
        [*shape*] if it isn't grouped."""
        if shape is None or shape.group_id is None:
            return [shape] if shape is not None else []
        return [s for s in self.shapes_to_draw if s.group_id == shape.group_id]

    def ungroup_selected(self):
        """Break the selected shape's group apart — its members go back to
        moving independently. No-op if nothing selected or not grouped."""
        if self.selected is None or self.selected.group_id is None:
            return
        gid = self.selected.group_id
        for s in self.shapes_to_draw:
            if s.group_id == gid:
                s.group_id = None
        self.update()
        self._push_undo_checkpoint()

    def _align_distribute_targets(self):
        """The shapes an Align/Distribute action should act on: the ad hoc
        Shift+click multi-selection if 2+ shapes are in it, else just the
        single selected shape (which is enough to no-op align, but lets a
        caller not special-case "nothing selected yet")."""
        if len(self.multi_selected) > 1:
            return list(self.multi_selected)
        return [self.selected] if self.selected is not None else []

    def align_selected(self, mode):
        """Align the current selection (see _align_distribute_targets) —
        mode is one of poster_align.ALIGN_MODES. No-op with fewer than 2
        shapes selected (nothing to align to)."""
        from pyfigures.poster.poster_align import align_shapes
        align_shapes(self._align_distribute_targets(), mode)
        self.update()
        self._push_undo_checkpoint()

    def distribute_selected(self, axis):
        """Evenly space the current selection (see _align_distribute_targets)
        along *axis* ('x' or 'y'). No-op with fewer than 3 shapes selected."""
        from pyfigures.poster.poster_align import distribute_shapes
        distribute_shapes(self._align_distribute_targets(), axis)
        self.update()
        self._push_undo_checkpoint()

    def arrange(self, kind, layout_name=None, **kwargs):
        """One-click arrangement of the current page's photos — 'scatter',
        'fan', 'grid' or 'layout' (with *layout_name*) — as one undo step.
        Text boxes are never moved (see poster_layouts.default_targets).
        Returns the number of shapes arranged."""
        from pyfigures.poster import poster_layouts
        w, h = self.page_width_mm, self.page_height_mm
        if kind == 'layout':
            from pyfigures.poster.poster_templates import apply_layout, layout_targets
            n = len(layout_targets(self.shapes_to_draw))
            if n:
                apply_layout(self.shapes_to_draw, w, h, layout_name, **kwargs)
        else:
            n = len(poster_layouts.default_targets(self.shapes_to_draw))
            if n:
                if kind == 'scatter':
                    poster_layouts.scatter_layout(self.shapes_to_draw, w, h, **kwargs)
                elif kind == 'fan':
                    params = poster_layouts.fan_defaults(w, h)
                    params.update(kwargs)
                    poster_layouts.arc_layout(self.shapes_to_draw, page_width_mm=w, page_height_mm=h,
                                              **params)
                elif kind == 'grid':
                    poster_layouts.grid_layout(self.shapes_to_draw, w, h, **kwargs)
                else:
                    raise ValueError(f'unknown arrangement {kind!r}')
        self.selected = None
        self.multi_selected = []
        self.update()
        if n:
            self._push_undo_checkpoint()
        return n

    def sketch_layout(self, layout_name, margin_mm=15.0, group=True):
        """Add empty template-slot placeholders for *layout_name* — sketch
        the page out before any photo exists, then drag images onto the
        slots (or fill_template_slot()) to fill them one at a time. By
        default (*group*) the slots share one group_id so they can be
        dragged around the page together."""
        from pyfigures.poster.poster_templates import sketch_layout as _sketch
        new_shapes = _sketch(self.page_width_mm, self.page_height_mm, layout_name,
                             margin_mm=margin_mm, group=group)
        self.shapes_to_draw.extend(new_shapes)
        self.selected = new_shapes[-1] if new_shapes else None
        self.update()
        self._push_undo_checkpoint()
        return new_shapes

    @staticmethod
    def check_image_readable(path):
        """Raise FileNotFoundError/ValueError unless *path* loads as an image."""
        if not os.path.isfile(path):
            raise FileNotFoundError(f'no such image file: {path}')
        if QImage(path).isNull():
            raise ValueError(f'cannot read {os.path.basename(path)} as an image '
                             f'(unsupported or corrupt file)')

    def fill_template_slot(self, shape, image_path, source_pyf=None):
        """Fill one existing template-slot placeholder with a real photo."""
        self.check_image_readable(image_path)
        shape.fill_template(image_path, source_pyf=source_pyf)
        self.update()
        self._push_undo_checkpoint()

    def _template_slot_at(self, pos_px):
        """Topmost unfilled template-slot placeholder under *pos_px*, if any."""
        for shape in reversed(self.shapes_to_draw):
            if not shape.is_template:
                continue
            rect_mm = shape.bounding_rect_mm()
            x0, y0 = self._mm_to_px(rect_mm.left(), rect_mm.top())
            x1, y1 = self._mm_to_px(rect_mm.right(), rect_mm.bottom())
            if QRectF(x0, y0, x1 - x0, y1 - y0).contains(pos_px):
                return shape
        return None

    # ---- mouse interaction -------------------------------------------------

    def _hit_test(self, pos_px):
        # Rotate/resize handles of the currently selected shape take priority.
        if self.selected is not None and self.selected in self.shapes_to_draw:
            hx_mm, hy_mm = self.selected.rotate_handle_pos_mm().x(), self.selected.rotate_handle_pos_mm().y()
            hx_px, hy_px = self._mm_to_px(hx_mm, hy_mm)
            if (QPointF(hx_px, hy_px) - pos_px).manhattanLength() <= ROTATE_HANDLE_RADIUS_PX * 2:
                return 'rotate', self.selected
            for corner, pt_mm in self.selected.corner_handles_mm().items():
                cx_px, cy_px = self._mm_to_px(pt_mm.x(), pt_mm.y())
                if (QPointF(cx_px, cy_px) - pos_px).manhattanLength() <= RESIZE_HANDLE_SIZE_PX * 2:
                    return f'resize_{corner}', self.selected
        for shape in reversed(self.shapes_to_draw):
            rect_mm = shape.bounding_rect_mm()
            x0, y0 = self._mm_to_px(rect_mm.left(), rect_mm.top())
            x1, y1 = self._mm_to_px(rect_mm.right(), rect_mm.bottom())
            if QRectF(x0, y0, x1 - x0, y1 - y0).contains(pos_px):
                return 'move', shape
        if self.background is not None and self.page_rect_px().contains(pos_px):
            return 'move_bg', self.background
        return None, None

    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, 'position') else event.localPos()
        mode, shape = self._hit_test(pos)
        self._press_signature = self._geometry_signature()

        if bool(event.modifiers() & Qt.ShiftModifier) and mode == 'move' and shape is not None:
            # Shift+click toggles *shape* in/out of the ad hoc multi-selection
            # used by Align/Distribute — it's a selection change, not the
            # start of a drag, so stop here rather than falling through.
            if shape in self.multi_selected:
                self.multi_selected.remove(shape)
            else:
                self.multi_selected.append(shape)
            self.selected = shape if self.multi_selected else None
            self._drag_mode = None
            self.update()
            return

        if mode != 'move' or shape not in self.multi_selected:
            # Anything other than clicking (without Shift) on a shape that's
            # already part of the multi-selection collapses it back down to
            # a plain single selection — same as most design tools.
            self.multi_selected = []

        if (mode == 'move' and isinstance(shape, PosterImage) and bool(event.modifiers() & Qt.ControlModifier)
                and not shape.is_template and not shape.pixmap().isNull()):
            # Ctrl+drag on an image's body repositions the crop window
            # within the photo — same idea as PosterBackground's pan, but
            # per image, and only meaningful once something is cropped
            # (an axis with no crop yet has nowhere to pan to).
            mode = 'pan_crop'
        self.selected = shape
        self._drag_mode = mode
        if mode == 'move_bg':
            self._drag_last_mouse_px = QPointF(pos.x(), pos.y())
        elif mode == 'move':
            mx_mm, my_mm = self._mm_to_px.inverse(pos.x(), pos.y())
            self._drag_last_mouse_mm = QPointF(mx_mm, my_mm)
            if len(self.multi_selected) > 1 and shape in self.multi_selected:
                # Drag the whole multi-selection together, like a one-off group.
                self._drag_group = list(self.multi_selected)
            else:
                self._drag_group = self._group_members(shape)
        elif mode == 'pan_crop':
            pm = shape.pixmap()
            mx_mm, my_mm = self._mm_to_px.inverse(pos.x(), pos.y())
            pivot, theta0 = shape.center_mm(), shape.theta
            self._crop_pan_state = {
                'pivot': pivot,
                'theta0': theta0,
                'last_local': _unrotate_point_mm(QPointF(mx_mm, my_mm), pivot, theta0),
                'pm_size': (pm.width(), pm.height()),
            }
        elif mode and mode.startswith('resize_'):
            corner = mode[len('resize_'):]
            is_crop = bool(event.modifiers() & Qt.ControlModifier) and isinstance(shape, PosterImage)
            if is_crop:
                pm = shape.pixmap()
                if shape.is_template or pm.isNull():
                    is_crop = False  # nothing to crop into — fall back to a plain resize
            state = {
                'corner': corner,
                'pivot': shape.center_mm(),
                'theta0': shape.theta,
                'anchor': _rect_corner(shape.unrotated_rect_mm(), _OPPOSITE_CORNER[corner]),
                'aspect0': (shape.width_mm / shape.height_mm) if shape.height_mm else 1.0,
                'w0': shape.width_mm,
                'h0': shape.height_mm,
                'is_crop': is_crop,
            }
            if is_crop:
                state['pm_size'] = (pm.width(), pm.height())
                state['crop0'] = (shape.crop_left, shape.crop_top, shape.crop_right, shape.crop_bottom)
            self._resize_state = state
        elif mode:
            mx_mm, my_mm = self._mm_to_px.inverse(pos.x(), pos.y())
            self._drag_last_mouse_mm = QPointF(mx_mm, my_mm)
            self._drag_start_theta = shape.theta
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, 'position') else event.localPos()
        if self._drag_mode is None or self.selected is None:
            return

        if self._drag_mode == 'move_bg':
            dx = pos.x() - self._drag_last_mouse_px.x()
            dy = pos.y() - self._drag_last_mouse_px.y()
            self.background.pan_by_px(dx, dy, self.page_rect_px())
            self._drag_last_mouse_px = QPointF(pos.x(), pos.y())
            self.update()
            return

        if self._drag_mode.startswith('resize_'):
            mx_mm, my_mm = self._mm_to_px.inverse(pos.x(), pos.y())
            self._apply_resize_drag(QPointF(mx_mm, my_mm), event.modifiers())
            self.update()
            return

        if self._drag_mode == 'pan_crop':
            mx_mm, my_mm = self._mm_to_px.inverse(pos.x(), pos.y())
            self._apply_crop_pan_drag(QPointF(mx_mm, my_mm))
            self.update()
            return

        mx_mm, my_mm = self._mm_to_px.inverse(pos.x(), pos.y())

        if self._drag_mode == 'move':
            dx = mx_mm - self._drag_last_mouse_mm.x()
            dy = my_mm - self._drag_last_mouse_mm.y()
            for member in self._drag_group:
                member.move_by_mm(dx, dy)
            self._drag_last_mouse_mm = QPointF(mx_mm, my_mm)

            # Snapping stays on by default (guides are only useful if you see
            # them without holding a key first) but the pull itself is eased
            # — see poster_align._eased_pull — so it's a gentle heads-up
            # near a candidate line rather than a hard grab; hold Alt to
            # switch it off entirely for a drag. Also skipped for a
            # multi-shape group drag, which has no single edge/center to
            # align (and there's no auto-alignment/repacking for groups).
            is_group_drag = len(self._drag_group) > 1
            disable_snap = is_group_drag or bool(event.modifiers() & Qt.AltModifier)
            self._guides = []
            if not disable_snap:
                others = [s.bounding_rect_mm() for s in self.shapes_to_draw if s is not self.selected]
                sdx, sdy, guides = compute_snaps(
                    self.selected.bounding_rect_mm(), others, self.page_rect_mm(),
                    threshold_mm=SNAP_THRESHOLD_MM)
                self.selected.move_by_mm(sdx, sdy)
                self._guides = guides

        elif self._drag_mode == 'rotate':
            center = self.selected.center_mm()
            angle = math.degrees(math.atan2(my_mm - center.y(), mx_mm - center.x())) + 90.0
            if event.modifiers() & Qt.ShiftModifier:
                angle = round(angle / ROTATE_SNAP_DEGREES) * ROTATE_SNAP_DEGREES
            self.selected.theta = angle

        self.update()

    def _apply_resize_drag(self, mouse_mm, modifiers):
        """Corner-handle drag: resize the selected image's box, or — if Ctrl
        was held when the drag started — crop into it instead (the box
        shrinks and shows less of the image, keeping the remaining content's
        on-page scale fixed, rather than shrinking the whole image to fit a
        smaller box). Either way the box's aspect ratio never changes (same
        rule the main editor applies to its panels — free/non-uniform
        stretching is never allowed); cropping is the one thing allowed to
        reveal less of the *photo* than before, not to distort its box."""
        state = self._resize_state
        shape = self.selected
        corner = state['corner']
        point = _unrotate_point_mm(mouse_mm, state['pivot'], state['theta0'])
        anchor = state['anchor']

        # The anchor (opposite corner) never moves; the dragged corner is
        # clamped to stay at least MIN_IMAGE_SIZE_MM past it on each axis —
        # keyed off the anchor's own coordinate (not a sorted min/max, which
        # would silently invert the box if the drag crosses over the anchor).
        if corner[1] == 'l':  # dragging the left side; right edge is anchored
            new_right = anchor.x()
            new_left = min(point.x(), new_right - MIN_IMAGE_SIZE_MM)
        else:  # dragging the right side; left edge is anchored
            new_left = anchor.x()
            new_right = max(point.x(), new_left + MIN_IMAGE_SIZE_MM)
        if corner[0] == 't':  # dragging the top side; bottom edge is anchored
            new_bottom = anchor.y()
            new_top = min(point.y(), new_bottom - MIN_IMAGE_SIZE_MM)
        else:  # dragging the bottom side; top edge is anchored
            new_top = anchor.y()
            new_bottom = max(point.y(), new_top + MIN_IMAGE_SIZE_MM)

        # Always keep the original aspect ratio — scale uniformly by
        # whichever axis the drag moved further, so the box follows the
        # dominant drag direction instead of always favoring one axis.
        scale = max((new_right - new_left) / state['w0'], (new_bottom - new_top) / state['h0'])
        new_w, new_h = state['w0'] * scale, state['h0'] * scale
        if corner[1] == 'l':
            new_left = new_right - new_w
        else:
            new_right = new_left + new_w
        if corner[0] == 't':
            new_top = new_bottom - new_h
        else:
            new_bottom = new_top + new_h

        if state['is_crop']:
            pm_w, pm_h = state['pm_size']
            crop_l0, crop_t0, crop_r0, crop_b0 = state['crop0']
            scale_x0 = pm_w * (1.0 - crop_l0 - crop_r0) / state['w0']
            scale_y0 = pm_h * (1.0 - crop_t0 - crop_b0) / state['h0']
            max_crop_sum = 1.0 - MIN_CROP_VISIBLE_FRAC
            if corner[1] == 'l':
                shape.crop_left = min(max(1.0 - crop_r0 - scale_x0 * new_w / pm_w, 0.0), max_crop_sum - crop_r0)
                shape.crop_right = crop_r0
            else:
                shape.crop_right = min(max(1.0 - crop_l0 - scale_x0 * new_w / pm_w, 0.0), max_crop_sum - crop_l0)
                shape.crop_left = crop_l0
            if corner[0] == 't':
                shape.crop_top = min(max(1.0 - crop_b0 - scale_y0 * new_h / pm_h, 0.0), max_crop_sum - crop_b0)
                shape.crop_bottom = crop_b0
            else:
                shape.crop_bottom = min(max(1.0 - crop_t0 - scale_y0 * new_h / pm_h, 0.0), max_crop_sum - crop_t0)
                shape.crop_top = crop_t0

        shape.x_mm, shape.y_mm = new_left, new_top
        shape.width_mm, shape.height_mm = new_right - new_left, new_bottom - new_top

    def _apply_crop_pan_drag(self, mouse_mm):
        """Ctrl+drag on an already-cropped image's body: slide the crop
        window over the photo (box size and crop *amount* per axis both stay
        fixed — only which part of the photo is currently visible changes),
        the same idea as PosterBackground.pan_by_px but per image and
        expressed in the image's own (possibly rotated) local frame."""
        state = self._crop_pan_state
        shape = self.selected
        local = _unrotate_point_mm(mouse_mm, state['pivot'], state['theta0'])
        last_local = state['last_local']
        dx, dy = local.x() - last_local.x(), local.y() - last_local.y()
        state['last_local'] = local

        pm_w, pm_h = state['pm_size']
        total_crop_x = shape.crop_left + shape.crop_right
        if total_crop_x > 0 and pm_w and shape.width_mm:
            scale_x = pm_w * (1.0 - total_crop_x) / shape.width_mm
            shape.crop_left = min(max(shape.crop_left - dx * scale_x / pm_w, 0.0), total_crop_x)
            shape.crop_right = total_crop_x - shape.crop_left
        total_crop_y = shape.crop_top + shape.crop_bottom
        if total_crop_y > 0 and pm_h and shape.height_mm:
            scale_y = pm_h * (1.0 - total_crop_y) / shape.height_mm
            shape.crop_top = min(max(shape.crop_top - dy * scale_y / pm_h, 0.0), total_crop_y)
            shape.crop_bottom = total_crop_y - shape.crop_top

    def mouseDoubleClickEvent(self, event):
        pos = event.position() if hasattr(event, 'position') else event.localPos()
        mode, shape = self._hit_test(pos)
        if mode == 'move' and isinstance(shape, PosterText):
            self.selected = shape
            self.update()
            self.edit_text(shape)

    def _geometry_signature(self):
        """Everything a mouse drag can change on the current page — compared
        before/after so a plain click (select only) is not an undo step and
        doesn't mark the document modified."""
        sig = []
        for s in self.shapes_to_draw:
            sig.append((id(s), s.x_mm, s.y_mm, s.width_mm, s.height_mm, s.theta,
                        getattr(s, 'crop_left', 0.0), getattr(s, 'crop_top', 0.0),
                        getattr(s, 'crop_right', 0.0), getattr(s, 'crop_bottom', 0.0)))
        bg = self.background
        if bg is not None:
            sig.append((bg.zoom, bg.pan_x_frac, bg.pan_y_frac))
        return tuple(sig)

    def mouseReleaseEvent(self, event):
        had_drag = self._drag_mode is not None
        changed = had_drag and self._geometry_signature() != getattr(self, '_press_signature', None)
        self._drag_mode = None
        self._drag_last_mouse_mm = None
        self._drag_last_mouse_px = None
        self._drag_group = None
        self._resize_state = None
        self._crop_pan_state = None
        self._guides = []
        self.update()
        if changed:
            self._push_undo_checkpoint()

    def wheelEvent(self, event):
        pos = event.position() if hasattr(event, 'position') else event.posF()
        mode, shape = self._hit_test(pos)
        if mode != 'move_bg':
            event.ignore()
            return
        steps = event.angleDelta().y() / 120.0
        old_zoom = shape.zoom
        shape.set_zoom(shape.zoom * (1.1 ** steps))
        self.update()
        event.accept()
        if shape.zoom != old_zoom:
            self._push_undo_checkpoint()

    # ---- drag-and-drop from the OS file browser -------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _resolve_pyf_paths(self, paths):
        """Replace any .pyf path with its rendered PNG (_render_pyf_to_png);
        plain image paths pass through unchanged. A .pyf that fails to
        render is dropped from the list (with an error message collected)
        rather than aborting the whole drop. Also returns a {rendered_png:
        original_pyf} map so the caller can tag the resulting PosterImage
        with source_pyf — used later to bundle the .pyf's own source data
        alongside the poster's, see poster_headless.op_export_source_data."""
        resolved, origins, errors = [], {}, []
        for path in paths:
            if os.path.splitext(path)[1].lower() in DROP_PYF_EXTS:
                try:
                    rendered = _render_pyf_to_png(path, parent=self)
                    resolved.append(rendered)
                    origins[rendered] = path
                except Exception as exc:
                    errors.append(f'{os.path.basename(path)}: {exc}')
            else:
                resolved.append(path)
        return resolved, origins, errors

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        event.acceptProposedAction()
        paths = _collect_dropped_image_paths(event.mimeData().urls())
        if not paths:
            return
        single_was_pyf = (len(paths) == 1
                          and os.path.splitext(paths[0])[1].lower() in DROP_PYF_EXTS)
        paths, pyf_origins, pyf_errors = self._resolve_pyf_paths(paths)
        if pyf_errors:
            QMessageBox.warning(self, 'Could not render figure(s)', '\n'.join(pyf_errors))
        if not paths:
            return

        try:
            drop_pos_f = event.position()
        except AttributeError:
            drop_pos_f = QPointF(event.pos())
        try:
            drop_pos = drop_pos_f.toPoint()
        except AttributeError:
            drop_pos = event.pos()

        if len(paths) == 1:
            # Dropping directly onto a sketched-but-empty template slot fills
            # it in place — unambiguous, no popup needed (mirrors the main
            # editor's fill_template: only the file changes, the slot's own
            # box/rotation stays put).
            slot = self._template_slot_at(drop_pos_f)
            if slot is not None:
                try:
                    self.fill_template_slot(slot, paths[0], source_pyf=pyf_origins.get(paths[0]))
                except (OSError, ValueError) as exc:
                    QMessageBox.warning(self, 'Could not add image', str(exc))
                    return
                self.selected = slot
                self.update()
                return
            if single_was_pyf:
                # A rendered .pyf is unambiguously page content, never a
                # background — skip the add/background prompt entirely so
                # there's no easy-to-miss decision sitting there right after
                # the render (which can take a few seconds) finishes.
                try:
                    img = self.add_image(paths[0], source_pyf=pyf_origins.get(paths[0]))
                except (OSError, ValueError) as exc:
                    QMessageBox.warning(self, 'Could not add image', str(exc))
                    return
                self.selected = img
                self.update()
                return
            # Otherwise a single image could be meant as page content or as
            # the page background — ask, rather than silently guessing.
            self._offer_single_drop(paths[0], self.mapToGlobal(drop_pos))
            return

        # Multiple images: nothing is added until the user picks a layout from a
        # popup menu at the drop position (mirrors the main editor's DND menu in
        # pyfigures/gui/pfgui.py — a drop never silently decides a layout for you).
        empty_slots = [s for s in self.shapes_to_draw if s.is_template]
        self._offer_drop_layout(paths, self.mapToGlobal(drop_pos), empty_slots=empty_slots,
                                origins=pyf_origins)

    def _offer_single_drop(self, path, global_pos):
        from qtpy.QtWidgets import QMenu
        menu = QMenu(self)
        add_action = menu.addAction('Add to page')
        bg_action = menu.addAction('Set as background')
        chosen = menu.exec(global_pos)
        if chosen is None:
            return  # dismissed: nothing added, page unchanged
        try:
            if chosen is bg_action:
                self.check_image_readable(path)
                self.set_background(path)
            else:
                img = self.add_image(path)
                self.selected = img
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Could not add image', str(exc))
        self.update()

    def _offer_drop_layout(self, paths, global_pos, empty_slots=None, origins=None):
        from qtpy.QtWidgets import QMenu
        menu = QMenu(self)
        header = menu.addAction(f'Arrange {len(paths)} dropped images as...')
        header.setEnabled(False)
        menu.addSeparator()
        choices = []
        if empty_slots:
            n = min(len(paths), len(empty_slots))
            plural = '' if n == 1 else 's'
            choices.append((f'Fill {n} empty template slot{plural} in order', 'fill_slots'))
        choices += [
            ('Scatter — thrown on a table', 'scatter'),
            ('Fan — spread like cards', 'fan'),
            ('Grid — tidy rows/columns', 'grid'),
            ('Choose a layout… (gallery)', 'layout'),
            ('Just add them, centered', 'none'),
        ]
        action_for_key = {}
        for label, key in choices:
            action_for_key[menu.addAction(label)] = key

        chosen = menu.exec(global_pos)
        if chosen is None:
            return  # dismissed: nothing added, page unchanged
        key = action_for_key[chosen]

        origins = origins or {}
        # Unreadable files are skipped (and reported once) instead of
        # aborting the whole drop or adding grey placeholder boxes.
        errors = []
        readable = []
        for p in paths:
            try:
                self.check_image_readable(p)
                readable.append(p)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        if errors:
            QMessageBox.warning(self, 'Some files were skipped', '\n'.join(errors))
        paths = readable
        if not paths:
            return
        self.apply_drop_arrangement(paths, key, empty_slots=empty_slots, origins=origins)

    def apply_drop_arrangement(self, paths, key, empty_slots=None, origins=None):
        """Add *paths* to the current page and arrange them as *key* (one of
        'fill_slots', 'scatter', 'fan', 'grid', 'layout', 'none') — what the
        multi-file drop menu does once a choice is made, as one undo step."""
        origins = origins or {}
        empty_slots = empty_slots or []
        # One undo/redo step for the whole drop-and-arrange gesture, not one
        # per image added (each add_image()/fill_template_slot() call below
        # would otherwise push its own checkpoint).
        with self._batch_edit():
            if key == 'fill_slots':
                for shape, path in zip(empty_slots, paths):
                    shape.fill_template(path, source_pyf=origins.get(path))
                for leftover in paths[len(empty_slots):]:
                    self.add_image(leftover, source_pyf=origins.get(leftover))
                self.selected = empty_slots[0] if empty_slots else None
                self.update()
                return

            new_shapes = [self.add_image(p, source_pyf=origins.get(p)) for p in paths]
            self.selected = new_shapes[-1]
            indices = [self.shapes_to_draw.index(s) for s in new_shapes]
            if key == 'scatter':
                from pyfigures.poster.poster_layouts import scatter_layout
                scatter_layout(self.shapes_to_draw, self.page_width_mm, self.page_height_mm,
                               indices=indices)
            elif key == 'fan':
                from pyfigures.poster.poster_layouts import arc_layout, fan_defaults
                arc_layout(self.shapes_to_draw, indices=indices,
                          page_width_mm=self.page_width_mm, page_height_mm=self.page_height_mm,
                          **fan_defaults(self.page_width_mm, self.page_height_mm))
            elif key == 'grid':
                from pyfigures.poster.poster_layouts import grid_layout
                grid_layout(self.shapes_to_draw, self.page_width_mm, self.page_height_mm,
                           indices=indices)
            elif key == 'layout':
                from pyfigures.poster.poster_layout_dialog import LayoutGalleryDialog
                dlg = LayoutGalleryDialog(self, image_count=len(new_shapes))
                if dlg.exec() and dlg.selected_layout:
                    from pyfigures.poster.poster_templates import apply_layout
                    apply_layout(self.shapes_to_draw, self.page_width_mm, self.page_height_mm,
                                dlg.selected_layout, indices=indices)
            self.update()

    # ---- painting -------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Same "dark mat around the page" role the main editor's canvas surround
        # uses (QScrollArea.setBackgroundRole(QPalette.Dark) in scrollableEZFIG.py),
        # so both tools look the same in light and dark theme.
        painter.fillRect(self.rect(), self.palette().color(QPalette.Dark))
        self._paint_content(painter, self._mm_to_px, editor_overlays=True)
        painter.end()

    def _paint_content(self, painter, mm_to_px, editor_overlays=False):
        """Paint the current page. *editor_overlays* (on-screen only) adds the
        selection outlines, handles, hints and snap guides, which must never
        end up in an export or a thumbnail."""
        page_rect_px = self._page_rect_px_for(mm_to_px)

        painter.fillRect(page_rect_px, QColor(255, 255, 255))
        if self.background is not None:
            self.background.paint(painter, page_rect_px)

        for shape in self.shapes_to_draw:
            shape.paint(painter, mm_to_px)

        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawRect(page_rect_px)

        if self.current_page.kind == 'spread':
            # Purely a visual heads-up for where the physical fold falls —
            # content is free to cross it (or not); it never constrains
            # placement or gets exported (see _paint_content callers: this
            # runs for on-screen paint and for save()/export_album_pdf alike,
            # same as the page border above, since a printed spread's own
            # fold line is a real, physical reference too).
            mid_x_mm = self.page_width_mm / 2.0
            gx, gy0 = mm_to_px(mid_x_mm, 0.0)
            _, gy1 = mm_to_px(mid_x_mm, self.page_height_mm)
            painter.setPen(QPen(QColor(150, 150, 150), 1, Qt.DashLine))
            painter.drawLine(QPointF(gx, gy0), QPointF(gx, gy1))

        if not editor_overlays:
            return

        if self.multi_selected:
            self._paint_multi_selection(painter, mm_to_px)

        if self.selected is not None and self.selected in self.shapes_to_draw:
            if self.selected.group_id is not None:
                self._paint_group_outline(painter, mm_to_px, self.selected)
            self._paint_selection(painter, mm_to_px, self.selected)
        elif self.selected is not None and self.selected is self.background:
            painter.setPen(QPen(QColor(30, 120, 255), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(page_rect_px)

        if self._guides:
            pen = QPen(QColor(255, 0, 200), 1, Qt.DashLine)
            painter.setPen(pen)
            for line in self._guides:
                p1x, p1y = mm_to_px(line.x1(), line.y1())
                p2x, p2y = mm_to_px(line.x2(), line.y2())
                painter.drawLine(QPointF(p1x, p1y), QPointF(p2x, p2y))

    def _page_rect_px_for(self, mm_to_px):
        x0, y0 = mm_to_px(0.0, 0.0)
        x1, y1 = mm_to_px(self.page_width_mm, self.page_height_mm)
        return QRectF(x0, y0, x1 - x0, y1 - y0)

    def _paint_multi_selection(self, painter, mm_to_px):
        """A solid green rect around every shape in the ad hoc Align/
        Distribute selection (Shift+click) — distinct from the single
        "active" shape's dashed blue outline (_paint_selection) and from a
        layout group's loose dash-dot outline (_paint_group_outline), so the
        three concepts read as visually different even though only one
        shape at a time can show resize/rotate handles."""
        painter.setPen(QPen(QColor(40, 180, 90), 2, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        for shape in self.multi_selected:
            if shape not in self.shapes_to_draw:
                continue
            rect_mm = shape.bounding_rect_mm()
            x0, y0 = mm_to_px(rect_mm.left(), rect_mm.top())
            x1, y1 = mm_to_px(rect_mm.right(), rect_mm.bottom())
            margin_px = 2
            painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0).adjusted(-margin_px, -margin_px, margin_px, margin_px))

    def _paint_group_outline(self, painter, mm_to_px, shape):
        """A loose dash-dot rect around every shape sharing *shape*'s
        group_id — signals "these move together as one block", distinct
        from the tighter per-shape selection outline drawn on top of it."""
        members = self._group_members(shape)
        union_mm = None
        for member in members:
            r = member.bounding_rect_mm()
            union_mm = r if union_mm is None else union_mm.united(r)
        if union_mm is None:
            return
        x0, y0 = mm_to_px(union_mm.left(), union_mm.top())
        x1, y1 = mm_to_px(union_mm.right(), union_mm.bottom())
        painter.setPen(QPen(QColor(255, 150, 0), 1.5, Qt.DashDotLine))
        painter.setBrush(Qt.NoBrush)
        margin_px = 4
        painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0).adjusted(-margin_px, -margin_px, margin_px, margin_px))

    def _paint_selection(self, painter, mm_to_px, shape):
        rect_mm = shape.bounding_rect_mm()
        x0, y0 = mm_to_px(rect_mm.left(), rect_mm.top())
        x1, y1 = mm_to_px(rect_mm.right(), rect_mm.bottom())
        painter.setPen(QPen(QColor(30, 120, 255), 1, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(x0, y0, x1 - x0, y1 - y0))

        handle = shape.rotate_handle_pos_mm()
        hx, hy = mm_to_px(handle.x(), handle.y())

        # affordance line from the (rotated) top-center of the image to the handle
        t = QTransform()
        t.rotate(shape.theta)
        top_local = t.map(QPointF(0, -shape.height_mm / 2.0))
        top_mm = shape.center_mm() + top_local
        tx, ty = mm_to_px(top_mm.x(), top_mm.y())
        painter.drawLine(QPointF(tx, ty), QPointF(hx, hy))
        painter.setBrush(QBrush(QColor(30, 120, 255)))
        painter.drawEllipse(QPointF(hx, hy), ROTATE_HANDLE_RADIUS_PX, ROTATE_HANDLE_RADIUS_PX)

        # Corner resize/crop handles — small squares so they read as distinct
        # from the round rotate handle.
        painter.setPen(QPen(QColor(30, 120, 255), 1))
        painter.setBrush(QBrush(Qt.white))
        half = RESIZE_HANDLE_SIZE_PX / 2.0
        for pt_mm in shape.corner_handles_mm().values():
            px, py = mm_to_px(pt_mm.x(), pt_mm.y())
            painter.drawRect(QRectF(px - half, py - half, RESIZE_HANDLE_SIZE_PX, RESIZE_HANDLE_SIZE_PX))

        # Ctrl's two roles here (crop a corner, reposition an existing crop)
        # aren't discoverable from the handles alone — spell them out right
        # under the selection as soon as it's picked. Text boxes have no
        # crop concept (they resize the whole block, font included, on a
        # plain drag) so they get their own one-line hint instead.
        if isinstance(shape, PosterText):
            font = painter.font()
            font.setPointSizeF(8.0)
            painter.setFont(font)
            painter.setPen(QColor(90, 90, 90))
            painter.drawText(QPointF(x0, y1 + 14), 'Drag a corner to resize (double-click to edit text)')
        elif not shape.is_template:
            font = painter.font()
            font.setPointSizeF(8.0)
            painter.setFont(font)
            painter.setPen(QColor(90, 90, 90))
            painter.drawText(QPointF(x0, y1 + 14), 'Ctrl+drag a corner to crop')
            has_crop = (shape.crop_left or shape.crop_top
                       or shape.crop_right or shape.crop_bottom)
            if has_crop:
                painter.drawText(QPointF(x0, y1 + 28), 'Ctrl+drag the image to reposition the crop')

    # ---- export / interface expected by render-style code -------------------------------------------------

    def get_dpi(self):
        dpi, ok = QInputDialog.getItem(self, 'Export DPI', 'Choose a resolution (DPI):',
                                        ['72', '150', '300', '600'], 2, False)
        if not ok:
            return None          # cancelled: save() writes nothing
        return int(dpi)

    def update_size(self, mouse_pos=None):
        # Fixed page size by design (posters are not auto-trimmed to content).
        self._resize_to_page()

    def save(self, path, filetype=None, title=None, description=None, dpi=None):
        if filetype is None:
            filetype = str(path).rsplit('.', 1)[-1].lower() if '.' in str(path) else 'png'
        filetype = filetype.lower().lstrip('.')

        if filetype == 'pyfposter':
            if len(self.pages) > 1 or self.pages[0].kind != 'single':
                raise ValueError('this document has more than one page (or a cover/spread) — '
                                 'save it as .pyfalbum instead, not .pyfposter')
            from pyfigures.poster.serialization import save_poster
            save_poster(self, path)
            self.file_path = str(path)
            self.mark_saved()
            return

        if filetype == 'pyfalbum':
            from pyfigures.poster.serialization import save_album
            save_album(self, path)
            self.file_path = str(path)
            self.mark_saved()
            return

        if filetype not in self.EXPORT_FILETYPES:
            raise ValueError(f'unsupported export format {filetype!r}; use one of '
                             f'{", ".join(self.EXPORT_FILETYPES)}')

        if dpi is None:
            dpi = self.get_dpi()
            if dpi is None:
                return False
        px_per_mm = dpi / 25.4
        mm_to_px = _MmToPx(scale=px_per_mm, origin=QPointF(0.0, 0.0))
        page_w_px = int(round(self.page_width_mm * px_per_mm))
        page_h_px = int(round(self.page_height_mm * px_per_mm))

        if filetype == 'svg':
            generator = QSvgGenerator()
            # written to memory: the figures are put in before the file is
            # written (and QSvgGenerator keeps a file open until it is deleted)
            svg_buffer = QBuffer()
            svg_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            generator.setOutputDevice(svg_buffer)
            # the page's real size in mm (Qt's default 72 dpi wrote a 210 mm
            # page as 437 mm at 150 dpi)
            generator.setResolution(int(round(dpi)))
            generator.setSize(QSize(page_w_px, page_h_px))
            generator.setViewBox(QRectF(0, 0, page_w_px, page_h_px))
            if title:
                generator.setTitle(title)
            if description:
                generator.setDescription(description)
            with self._vector_pyf_images([self.current_page], kind='svg'):
                # Qt's SVG engine ignores drawPixmap source rects (crops)
                from pyfigures.gui.svg_painter import CroppingPainter
                painter = CroppingPainter(generator)
                painter.setRenderHint(QPainter.Antialiasing, True)
                self._paint_content(painter, mm_to_px)
                painter.end()
                svg_text = bytes(svg_buffer.data()).decode('utf-8')
                svg_buffer.close()
                # figures drawn as placeholders: put their own SVG in (real text)
                if getattr(self, '_svg_embeds', None):
                    svg_text = embed_svg_figures(svg_text, self._svg_embeds)
                from pyfigures.gui.svg_painter import real_font_families
                svg_text = real_font_families(svg_text)
                with open(str(path), 'w', encoding='utf-8') as f:
                    f.write(svg_text)
        elif filetype == 'pdf':
            writer = QPdfWriter(str(path))
            writer.setPageSize(QPageSize(QSizeF(self.page_width_mm, self.page_height_mm), QPageSize.Millimeter))
            # Qt's default margins shift the page content and clip its far edges
            writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
            writer.setResolution(dpi)
            with self._vector_pyf_images([self.current_page]):
                painter = QPainter(writer)
                painter.setRenderHint(QPainter.Antialiasing, True)
                self._paint_content(painter, mm_to_px)
                painter.end()
        else:
            image = QImage(page_w_px, page_h_px, QImage.Format_ARGB32)
            image.fill(Qt.white)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            self._paint_content(painter, mm_to_px)
            painter.end()
            if filetype in ('jpg', 'jpeg'):
                # JPEG has no alpha: flatten on white, not on black
                image = image.convertToFormat(QImage.Format_RGB32)
            if not image.save(str(path)):
                raise OSError(f'could not write {path}')

    # Formats save() can render a page to (besides the document formats).
    EXPORT_FILETYPES = ('png', 'jpg', 'jpeg', 'bmp', 'tif', 'tiff', 'svg', 'pdf')

    def missing_files(self):
        """[(page_index, role, path)] for every referenced image or background
        that can't be found on disk (moved/renamed/deleted since it was
        placed). Empty template slots are not files and never count."""
        out = []
        for pi, page in enumerate(self.pages):
            bg = page.background
            if bg is not None and bg.path and not os.path.isfile(bg.path):
                out.append((pi, 'background', bg.path))
            for shape in page.shapes_to_draw:
                if isinstance(shape, PosterImage) and not shape.is_template \
                        and not os.path.isfile(shape.path):
                    out.append((pi, 'image', shape.path))
        return out

    def load(self, path):
        from pyfigures.poster.serialization import load_poster, load_album, sniff_root_tag
        if sniff_root_tag(path) == 'PosterAlbum':
            load_album(self, path)
        else:
            # Reset to one fresh single page first: load_poster only ever
            # populates canvas.page_width_mm/height_mm/background/
            # shapes_to_draw (i.e. whatever "current page" already is), so
            # without this a plain .pyfposter loaded on top of a multi-page
            # album would silently keep the album's other pages around.
            self.pages = [PosterPage(210.0, 297.0, kind='single')]
            self.current_page_index = 0
            self.album_mode = False
            load_poster(self, path)
            self.base_page_width_mm = self.pages[0].width_mm
            self.base_page_height_mm = self.pages[0].height_mm
        self.file_path = str(path)
        self._undo_redo_init()
        self._push_undo_checkpoint()
        self.selected = None
        self.multi_selected = []
        self._resize_to_page()
        self.update()
