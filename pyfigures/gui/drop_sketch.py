"""Sketches for the menus shown when files are dropped (from the file
browser) on the figure or on a poster page: what each choice gives, before
it is picked.

Figure editor: the dropped files become pixel-free panels of their real
proportions (read from the file header only) and the canvas's own layout
code runs on them in the drag-and-drop sandbox (see drag_sketch). The new
panels are blue, the panel or row dropped on orange.

Poster: the page is drawn white with what is already on it in grey; the
dropped images in blue, placed by the same layout functions (scatter uses
the seed the drop will use, so the sketch is the real throw).

Anything that cannot be told leaves the entry without a sketch.
"""
from __future__ import annotations

import math
import os
import traceback

from qtpy.QtCore import QEvent, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QIcon, QImageReader, QPen, QPolygonF, QTransform
from qtpy.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout

from batoolset.drawings.shapes.group import Group
from batoolset.drawings.shapes.image2d import Image2D
from pyfigures.gui.drag_sketch import (PREVIEW_H, PREVIEW_W, SKETCH_H, SKETCH_W, SketchMenuStyle, _MOVED,
                                       _OTHER, _Sandbox, _clone, _leaves, _top, attach_preview,
                                       preview_pixmap, sketch, sketch_canvas)

_PAGE = QColor(255, 255, 255)
_PAGE_EDGE = QColor(120, 120, 120)
_MAX_BOXES = 400             # a montage of a long movie: boxes past this are not drawn


def _dpr():
    try:
        return QApplication.primaryScreen().devicePixelRatio()
    except Exception:
        return 1.0


def file_size(path):
    """(width, height) in pixels of an image file, from its header only;
    None when it cannot be told cheaply (never starts Fiji)."""
    if isinstance(path, (tuple, list)):
        path = path[0] if path else None
    if not isinstance(path, str) or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tif", ".tiff"):
        try:
            import tifffile
            with tifffile.TiffFile(path) as tf:
                s = tf.series[0]
                axes = s.axes.upper()
                shape = s.shape
                if "Y" in axes and "X" in axes:
                    return int(shape[axes.index("X")]), int(shape[axes.index("Y")])
        except Exception:
            pass
    try:
        size = QImageReader(path).size()
        if size.isValid() and size.width() > 0 and size.height() > 0:
            return size.width(), size.height()
    except Exception:
        pass
    return None


def _new_panel(path, size=None):
    w, h = size or file_size(path) or (100, 100)
    img = Image2D(width=w, height=h)
    img._sketch_new = True
    return img


def _figure_width(canvas):
    widths = [s.width() for s in canvas.shapes_to_draw if isinstance(s, (Group, Image2D))]
    return max(widths, default=0) or 512


def _grid(panels, cols, pad_size):
    """A column of rows of *cols* panels, the last row padded with empty
    panels so every panel keeps its size (the montage and panel dialogs)."""
    rows = []
    for i in range(0, len(panels), cols):
        row = list(panels[i:i + cols])
        if len(panels) > cols:
            while len(row) < cols:
                row.append(Image2D(width=pad_size[0], height=pad_size[1]))
        rows.append(row)
    if len(rows) == 1:
        return Group(*rows[0], orientation="X")
    return Group(*[Group(*r, orientation="X") for r in rows], orientation="Y")


def _canvas_result(canvas, op, files, target, montage):
    """Top-level shapes after the drop choice *op*, on copies; plus the ids
    of the new and of the target panels."""
    # only the row dropped on is shown with the new panels: the rest of the
    # figure (a full-width row above) dwarfed them
    context = [_top(canvas, target)] if target is not None else []
    mapping = {}
    clones = [_clone(t, mapping) for t in context]
    if any(c is None for c in clones):
        return None
    box = _Sandbox(canvas, clones, _figure_width(canvas))
    for c in clones:
        box.force_update_size_of_parent.emit(c)
    # sketch() colours by the original panels (a copy's _sketch_src)
    target_ids = {id(x) for x in _leaves(_top(canvas, target))} if target is not None else set()
    new = []
    if op == "template":
        if id(target) not in mapping:
            return None
        return box.shapes_to_draw, {id(target)}, set()
    if op == "montage":
        n, size = montage
        new = [_new_panel(None, size) for _ in range(min(n, _MAX_BOXES))]
        from pyfigures.mcp_tools.stacks import auto_columns
        grp = _grid(new, auto_columns(len(new)), size)
        box.shapes_to_draw.append(grp)
        box.force_update_size_of_parent.emit(grp)
    else:
        new = [_new_panel(f) for f in files]
        if op in ("row", "col"):
            box._add_as_new_group(new, orientation="X" if op == "row" else "Y", remove_from_parents=False)
        elif op in ("with_row", "with_col"):
            tc = mapping.get(id(_top(canvas, target)))
            if tc is None:
                return None
            box._add_as_new_group([tc] + new, orientation="X" if op == "with_row" else "Y",
                                  remove_from_parents=True)
        elif op == "panel":
            # the panel dialog opens on 2 rows, left to right, empty panels added
            rows = min(2, len(new))
            size = (new[0].width(), new[0].height())
            grp = _grid(new, math.ceil(len(new) / rows), size)
            box.shapes_to_draw.append(grp)
            box.force_update_size_of_parent.emit(grp)
        else:                                # single images / max projections
            for img in new:
                box.shapes_to_draw.append(img)
                box.force_update_size_of_parent.emit(img)
    result = [s for s in box.shapes_to_draw if not (isinstance(s, Group) and not s.content)]
    for s in result:
        box.force_update_size_of_parent.emit(s)
    return result, {id(x) for x in new}, target_ids


def finish_file_drop_menu(canvas, menu, entries):
    """Give each entry [(action, op, files, target, montage)] of the
    file-drop menu its sketch. *op*: row, col, panel, with_row, with_col,
    single, montage (montage = (frame count, (w, h))), template."""
    dpr = _dpr()
    drawn = False
    for act, op, files, target, montage in entries:
        try:
            res = _canvas_result(canvas, op, files, target, montage)
        except Exception:
            if os.environ.get("PYF_DEBUG_SKETCH"):
                traceback.print_exc()
            res = None
        if not res or not res[0]:
            continue
        shapes, new_ids, target_ids = res
        icon = sketch(shapes, new_ids, target_ids, dpr)
        if icon is not None:
            act.setIcon(icon)
            drawn = True
    if drawn:
        style = SketchMenuStyle()             # no base style: see drag_sketch
        menu.setStyle(style)
        menu._sketch_style = style
        menu.setToolTipsVisible(True)


# ---------------------------------------------------------------------------
# poster page
# ---------------------------------------------------------------------------

def _outline(shape):
    """The shape's rotated outline on the page, in mm."""
    try:
        rect = shape.outer_rect_mm()
    except Exception:
        try:
            return QPolygonF(shape.bounding_rect_mm())
        except Exception:
            return None
    theta = getattr(shape, "theta", 0) or 0
    if not theta:
        return QPolygonF(rect)
    c = rect.center()
    t = QTransform()
    t.translate(c.x(), c.y())
    t.rotate(theta)
    t.translate(-c.x(), -c.y())
    return t.map(QPolygonF(rect))


def page_sketch(page_w, page_h, grey, blue, background=False, dpr=1.0):
    """QIcon of a page (mm sizes) with *grey* and *blue* shapes drawn as
    their rotated outlines; *background* fills the page in blue."""
    if page_w <= 0 or page_h <= 0:
        return None
    pm, p = sketch_canvas(dpr)
    k = min((SKETCH_W - 2) / page_w, (SKETCH_H - 2) / page_h)
    ox = (SKETCH_W - page_w * k) / 2
    oy = (SKETCH_H - page_h * k) / 2
    page = QRectF(ox, oy, page_w * k, page_h * k)
    p.setPen(QPen(_PAGE_EDGE, 1))
    p.setBrush(_MOVED.lighter(150) if background else _PAGE)
    p.drawRect(page.adjusted(0.5, 0.5, -0.5, -0.5))
    p.setClipRect(page)
    to_px = QTransform()
    to_px.translate(ox, oy)
    to_px.scale(k, k)
    for shapes, colour in ((grey, _OTHER), (blue, _MOVED)):
        for s in shapes:
            poly = _outline(s)
            if poly is None:
                continue
            p.setPen(QPen(colour.darker(140), 1))
            p.setBrush(colour)
            p.drawPolygon(to_px.map(poly))
    p.end()
    return QIcon(pm)


def _poster_new(canvas, paths):
    """Stand-ins for the images add_image() would add: same size rule, page
    centre, no pixels read."""
    from pyfigures.poster.poster_shapes import PosterImage
    out = []
    for path in paths:
        w, h = file_size(path) or (400, 300)
        nat_w = w / canvas._mm_to_px.scale
        nat_h = h / canvas._mm_to_px.scale
        scale = min(1.0, min(canvas.page_width_mm, canvas.page_height_mm) * 0.4 / max(nat_w, nat_h, 1.0))
        img = PosterImage(path, x_mm=0, y_mm=0, width_mm=nat_w * scale, height_mm=nat_h * scale)
        img.set_center_mm(canvas.page_width_mm / 2.0, canvas.page_height_mm / 2.0)
        out.append(img)
    return out


def poster_arrangement(canvas, paths, key, seed=None, empty_slots=None):
    """(grey shapes, blue shapes) of the page once *paths* are arranged as
    *key* (the keys of PosterCanvas.apply_drop_arrangement)."""
    from pyfigures.poster import poster_layouts as L
    w, h = canvas.page_width_mm, canvas.page_height_mm
    empty_slots = empty_slots or []
    if key == "fill_slots":
        slots = [s for s in empty_slots][:len(paths)]
        others = [s for s in canvas.shapes_to_draw if all(s is not x for x in slots)]
        return others, slots + _poster_new(canvas, paths[len(slots):])
    new = _poster_new(canvas, paths)
    idx = list(range(len(new)))
    if key == "scatter":
        L.scatter_layout(new, w, h, indices=idx, seed=seed)
    elif key == "fan":
        L.arc_layout(new, indices=idx, page_width_mm=w, page_height_mm=h, **L.fan_defaults(w, h))
    elif key == "grid":
        L.grid_layout(new, w, h, indices=idx)
    elif key == "layout":
        return None                        # chosen in the gallery next
    return list(canvas.shapes_to_draw), new


def finish_poster_drop_menu(canvas, menu, action_for_key, paths, seed=None, empty_slots=None,
                            single=None):
    """Sketch each poster drop entry. *action_for_key* {action: key}; for a
    single image, *single* {action: 'add' | 'background'}."""
    dpr = _dpr()
    drawn = False
    w, h = canvas.page_width_mm, canvas.page_height_mm
    for act, key in list((single or {}).items()) + list((action_for_key or {}).items()):
        try:
            if key == "background":
                icon = page_sketch(w, h, canvas.shapes_to_draw, [], background=True, dpr=dpr)
            elif key == "add":
                icon = page_sketch(w, h, canvas.shapes_to_draw, _poster_new(canvas, paths), dpr=dpr)
            else:
                res = poster_arrangement(canvas, paths, key, seed=seed, empty_slots=empty_slots)
                icon = page_sketch(w, h, res[0], res[1], dpr=dpr) if res else None
        except Exception:
            if os.environ.get("PYF_DEBUG_SKETCH"):
                traceback.print_exc()
            icon = None
        if icon is not None:
            act.setIcon(icon)
            drawn = True
    if drawn:
        style = SketchMenuStyle()
        menu.setStyle(style)
        menu._sketch_style = style
        menu.setToolTipsVisible(True)
        attach_preview(menu)


def icon_size():
    return QSize(SKETCH_W, SKETCH_H)


class SketchPreviewPane(QFrame):
    """Right-hand pane of the figure's file-drop menu (a frame of buttons,
    not a QMenu): the hovered choice's sketch, large, and what it does."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sketchPreviewPane")
        self.setStyleSheet("QFrame#sketchPreviewPane { border: none; border-left: 1px solid palette(mid); }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 6, 6)
        self.picture = QLabel(self)
        self.picture.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption = QLabel(self)
        self.caption.setWordWrap(True)
        self.caption.setFixedWidth(PREVIEW_W)
        self.caption.setStyleSheet("border: none;")
        self.picture.setStyleSheet("border: none;")
        lay.addWidget(self.picture)
        lay.addWidget(self.caption)
        lay.addStretch(1)
        self._actions = {}
        self.hide()

    @staticmethod
    def icon_size():
        return QSize(SKETCH_W, SKETCH_H)

    def has_entries(self):
        return bool(self._actions)

    def watch(self, button, action):
        if not self._actions:
            self.show_action(action)        # the first choice until one is hovered
            self.show()
        self._actions[button] = action
        button.installEventFilter(self)

    def show_action(self, action):
        self.picture.setPixmap(preview_pixmap(action.icon()))
        tip = action.toolTip()
        name = action.text().replace("&", "").strip()
        self.caption.setText(f"<b>{name}</b><br>{tip}" if tip and tip != name else f"<b>{name}</b>")

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn) and obj in self._actions:
            self.show_action(self._actions[obj])
        return False
