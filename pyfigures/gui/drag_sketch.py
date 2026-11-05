"""What each choice of the drag-and-drop menu would do, before it is picked.

For every entry (To row, To column, Swap, Join this row…) the real canvas
method runs on a light copy of the rows involved — same groups, same panel
sizes, no pixels — inside a stand-in for the canvas that ignores repaints and
signals. From the result:

* entries that give the same layout are shown once (dedupe),
* each entry gets a small sketch of the layout it gives: grey boxes in the
  panels' proportions, the dragged panel in blue, the drop target in orange,
  panel letters drawn in.

Cheap: no image is read or drawn, only the one or two rows touched by the
drop are copied. Anything the simulation cannot handle leaves the entry as it
was (no sketch, never removed).
"""
from __future__ import annotations

import inspect
import os
import traceback
import types

from qtpy.QtCore import QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from qtpy.QtWidgets import QApplication, QFrame, QLabel, QProxyStyle, QStyle, QVBoxLayout

from batoolset.drawings.shapes.group import Group, set_to_width
from batoolset.drawings.shapes.image2d import Image2D

SKETCH_W = 72
SKETCH_H = 48
PREVIEW_W = 240              # the enlarged sketch beside the menu
PREVIEW_H = 160
_MOVED = QColor(70, 130, 220)
_TARGET = QColor(235, 150, 50)
_OTHER = QColor(170, 170, 170)

# entries kept first when two give the same layout (familiar names win)
_PRIORITY = {"row": 0, "swap": 1, "col": 2, "join": 3, "join_each": 4, "extrude": 5}


class _Mute:
    """A signal nobody listens to."""

    def emit(self, *a, **k):
        pass

    def connect(self, *a, **k):
        pass


class _Resize:
    """force_update_size_of_parent: the GUI fits the shape to the figure
    width; here the same, so the sketch has the real proportions."""

    def __init__(self, width):
        self.width = width

    def emit(self, shape, *a):
        if shape is None or not self.width:
            return
        try:
            if isinstance(shape, Group):
                set_to_width(shape, self.width)
            elif isinstance(shape, Image2D):
                from batoolset.drawings.shapes.group import set_to_width_im2d
                set_to_width_im2d(shape, self.width)
        except Exception:
            pass


class _Sandbox:
    """Stands in for the canvas: the canvas's own Python methods (add,
    extend, To row…) run on it unchanged; Qt widget calls do nothing."""

    def __init__(self, canvas, shapes, width):
        self._canvas_cls = type(canvas)
        self.shapes_to_draw = shapes
        self.selected_shape = None
        self.space = getattr(canvas, "space", 3)
        self._EXTRA_PADDING = getattr(canvas, "_EXTRA_PADDING", 0)
        self.force_update_size_of_parent = _Resize(width)

    def set_current_selection(self, sel=None, *a, **k):
        self.selected_shape = sel

    def update_size(self, *a, **k):
        pass

    def update(self, *a, **k):
        pass

    def repaint(self, *a, **k):
        pass

    def reset_position(self, *a, **k):
        pass

    def __getattr__(self, name):
        attr = getattr(self._canvas_cls, name)
        if inspect.isfunction(attr):
            return types.MethodType(attr, self)
        if type(attr).__name__ in ("pyqtSignal", "Signal", "pyqtBoundSignal", "SignalInstance"):
            return _Mute()
        if callable(attr):
            return lambda *a, **k: None          # QWidget methods: update, repaint…
        return attr


def _clone(shape, mapping):
    """Copy of *shape* with the same layout and no pixels; *mapping*
    {id(original): clone}."""
    if isinstance(shape, Group):
        kids = [_clone(c, mapping) for c in shape.content]
        if any(k is None for k in kids):
            return None
        grp = Group(*kids, orientation=shape.orientation, space=shape.space)
        grp.isText = getattr(shape, "isText", False)
        grp._sketch_src = shape
        mapping[id(shape)] = grp
        return grp
    if isinstance(shape, Image2D):
        try:
            w, h = shape.get_raw_size()
        except Exception:
            w, h = shape.width(), shape.height()
        img = Image2D(width=w or 1, height=h or 1, crop_left=shape.crop_left,
                      crop_right=shape.crop_right, crop_top=shape.crop_top,
                      crop_bottom=shape.crop_bottom, theta=shape.theta)
        img.isText = getattr(shape, "isText", False)
        img._sketch_src = shape
        mapping[id(shape)] = img
        return img
    return None


def _map_arg(arg, mapping):
    if isinstance(arg, (list, tuple)):
        out = [_map_arg(a, mapping) for a in arg]
        return out if isinstance(arg, list) else tuple(out)
    if isinstance(arg, (Group, Image2D)):
        if id(arg) not in mapping:
            raise KeyError("shape not in the copied rows")
        return mapping[id(arg)]
    return arg


def _top(canvas, shape):
    try:
        return canvas.get_top_parent_of_shape(shape) or shape
    except Exception:
        return shape


def simulate(canvas, method, args, involved):
    """The canvas's top-level shapes after *method*(*args*) — run on copies
    of the rows holding *involved* shapes. None when it cannot be told."""
    tops = []
    for s in involved:
        t = _top(canvas, s)
        if t is not None and all(t is not x for x in tops):
            tops.append(t)
    order = list(canvas.shapes_to_draw)
    tops.sort(key=lambda t: next((i for i, s in enumerate(order) if s is t), len(order)))
    mapping = {}
    clones = [_clone(t, mapping) for t in tops]
    if not clones or any(c is None for c in clones):
        return None
    width = max((t.width() for t in tops), default=0)
    box = _Sandbox(canvas, clones, width)
    for t, c in zip(tops, clones):
        box.force_update_size_of_parent.emit(c)
        # where the original is: the canvas code partly tells parents by geometry
        try:
            c.setTopLeft(t.x(), t.y())
        except Exception:
            pass
    try:
        if method is not None:                # None: the layout as it is now
            getattr(box, method)(*_map_arg(list(args), mapping))
    except Exception:
        if os.environ.get("PYF_DEBUG_SKETCH"):
            traceback.print_exc()
        return None
    result = [s for s in box.shapes_to_draw if not (isinstance(s, Group) and not s.content)]
    for s in result:
        box.force_update_size_of_parent.emit(s)
    return result


def signature(shapes):
    """The layout as nested tuples of original panels: two entries giving the
    same signature look the same (a row nested in a row = one row)."""
    def sig(s):
        if isinstance(s, Group):
            kids = []
            for c in s.content:
                k = sig(c)
                if isinstance(k, tuple) and k and k[0] == s.orientation:
                    kids.extend(k[1:])
                else:
                    kids.append(k)
            if len(kids) == 1:
                return kids[0]
            return (s.orientation,) + tuple(kids)
        return id(getattr(s, "_sketch_src", s))
    return tuple(sig(s) for s in shapes)


def looks(shapes):
    """The layout as drawn: each panel's box, relative to the whole, rounded.
    A column of two rows looks like two rows: shown once."""
    _place(shapes, gap=0)
    boxes = [(id(getattr(x, "_sketch_src", x)), x.getRect(all=True)) for s in shapes for x in _leaves(s)]
    if not boxes:
        return ()
    bound = QRectF(boxes[0][1])
    for _i, r in boxes[1:]:
        bound = bound.united(r)
    w, h = max(bound.width(), 1e-9), max(bound.height(), 1e-9)
    return tuple(sorted((i, round((r.x() - bound.x()) / w * 40), round((r.y() - bound.y()) / h * 40),
                         round(r.width() / w * 40), round(r.height() / h * 40)) for i, r in boxes))


def letter_of(img):
    for a in getattr(img, "annotations", None) or []:
        if getattr(a, "is_letter", False):
            try:
                return a.getPlainText().strip().strip("().")
            except Exception:
                return ""
    return ""


def name_of(shape):
    """'d', 'cells.png', 'the row a–c' — how a label names a shape."""
    if isinstance(shape, Group):
        leaves = list(_leaves(shape))
        letters = [letter_of(x) for x in leaves]
        kind = "row" if shape.orientation == "X" else "column"
        if letters and all(letters):
            return f"{kind} {letters[0]}–{letters[-1]}" if len(letters) > 1 else f"{kind} {letters[0]}"
        return kind
    letter = letter_of(shape)
    if letter:
        return letter
    fn = getattr(shape, "filename", None)
    return os.path.basename(str(fn)) if fn else "panel"


def _leaves(shape):
    if isinstance(shape, Group):
        for c in shape.content:
            yield from _leaves(c)
    else:
        yield shape


def _place(shapes, gap):
    """Stack the rows top to bottom (what the canvas does when it repacks)."""
    y = 0.
    for s in shapes:
        r = s.getRect(all=True)
        s.translate(-r.x(), y - r.y())
        y += r.height() + gap


def row_letter_names(canvas):
    """{id(panel): its row letter} when the figure has one letter per row
    (outside the rows: the panels carry none), {} otherwise. The sketch then
    names each panel by its row's letter, as it names lettered panels."""
    if getattr(canvas, "letter_layout", "panel") != "row":
        return {}
    try:
        names = {}
        for row, text in canvas._row_letter_texts():
            letter = text.getPlainText().strip()
            for leaf in _leaves(row):
                names[id(leaf)] = letter
        return names
    except Exception:
        return {}


def sketch(shapes, moved, target, dpr=1.0, letters=None):
    """QIcon of *shapes* (sandbox result): grey boxes, *moved* panels blue,
    *target* panels orange, letters inside (*letters* {id(panel): letter}
    for panels whose letter is not on them: one letter per row)."""
    # getRect(all=True): the size drawn on the canvas (getRect() ignores the fit to width)
    _place(shapes, gap=max(s.getRect(all=True).height() for s in shapes) * 0.08 if shapes else 0)
    leaves = [x for s in shapes for x in _leaves(s)]
    rects = [x.getRect(all=True) for x in leaves]
    if not rects:
        return None
    bound = QRectF(rects[0])
    for r in rects[1:]:
        bound = bound.united(r)
    if bound.width() <= 0 or bound.height() <= 0:
        return None
    pm, p = sketch_canvas(dpr)
    k = min((SKETCH_W - 2) / bound.width(), (SKETCH_H - 2) / bound.height())
    ox = (SKETCH_W - bound.width() * k) / 2
    oy = (SKETCH_H - bound.height() * k) / 2
    font = QFont()
    font.setPixelSize(9)
    font.setBold(True)
    p.setFont(font)
    for leaf, r in zip(leaves, rects):
        src = getattr(leaf, "_sketch_src", leaf)
        colour = _MOVED if id(src) in moved else _TARGET if id(src) in target else _OTHER
        box = QRectF(ox + (r.x() - bound.x()) * k, oy + (r.y() - bound.y()) * k,
                     max(1., r.width() * k), max(1., r.height() * k)).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(colour.darker(140), 1))
        p.setBrush(colour)
        p.drawRect(box)
        letter = letter_of(src) or (letters or {}).get(id(src), "")
        if letter and box.width() >= 7 and box.height() >= 9:
            p.setPen(Qt.GlobalColor.white)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, letter[:2])
    p.end()
    return QIcon(pm)


def sketch_canvas(dpr=1.0):
    """(pixmap, painter) for a sketch: drawn in SKETCH_W x SKETCH_H units on
    a PREVIEW_W x PREVIEW_H pixmap, so the same icon reads in the menu and,
    enlarged, in the preview beside it."""
    pm = QPixmap(int(PREVIEW_W * dpr), int(PREVIEW_H * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.scale(PREVIEW_W / SKETCH_W, PREVIEW_H / SKETCH_H)
    return pm, p


class SketchMenuStyle(QProxyStyle):
    """Bigger menu icons, so the sketches can be read."""

    def pixelMetric(self, metric, option=None, widget=None):
        if metric == QStyle.PixelMetric.PM_SmallIconSize:
            return SKETCH_W
        return super().pixelMetric(metric, option, widget)


def preview_pixmap(icon):
    return icon.pixmap(QSize(PREVIEW_W, PREVIEW_H))


def attach_preview(menu):
    """The sketch of the hovered entry, large, beside *menu*, with what the
    entry does under it."""
    pop = QFrame(menu, Qt.WindowType.ToolTip)
    pop.setObjectName("sketchPreview")
    pop.setFrameShape(QFrame.Shape.Box)
    pop.setStyleSheet("QFrame#sketchPreview { background: palette(base); border: 1px solid palette(mid); }")
    lay = QVBoxLayout(pop)
    lay.setContentsMargins(6, 6, 6, 6)
    pic = QLabel(pop)
    text = QLabel(pop)
    text.setWordWrap(True)
    text.setMaximumWidth(PREVIEW_W)
    lay.addWidget(pic)
    lay.addWidget(text)

    def show(act):
        icon = act.icon()
        if icon.isNull() or not menu.isVisible():
            pop.hide()
            return
        pic.setPixmap(preview_pixmap(icon))
        tip = act.toolTip()
        text.setText(tip if tip and tip != act.text().replace("&", "") else act.text())
        pop.adjustSize()
        g = menu.geometry()
        x = g.right() + 4
        try:
            screen = menu.screen().availableGeometry()
            if x + pop.width() > screen.right():
                x = g.left() - pop.width() - 4
        except Exception:
            pass
        pop.move(x, g.top() + menu.actionGeometry(act).top())
        pop.show()
    menu.hovered.connect(show)
    menu.aboutToHide.connect(pop.hide)
    menu._sketch_preview = pop
    return pop


def finish_drag_menu(canvas, menu, entries):
    """Dedupe *entries* [(action, kind, method, args, moved, target)] by the
    layout they give, and give each kept one its sketch and a tooltip."""
    if not entries:
        return
    dpr = 1.0
    try:
        dpr = QApplication.primaryScreen().devicePixelRatio()
    except Exception:
        pass
    seen = {}
    row_names = row_letter_names(canvas)
    # an entry that would leave the layout as it is does nothing: not offered
    first = entries[0]
    now = simulate(canvas, None, (), [x for x in (first[4], first[5]) if x is not None])
    nothing = {("s", signature(now)), ("l", looks(now))} if now is not None else set()
    for act, kind, method, args, moved, target in sorted(
            entries, key=lambda e: _PRIORITY.get(e[1], 9)):
        involved = [x for x in (moved, target) if x is not None]
        result = simulate(canvas, method, args, involved)
        if result is None:
            continue
        keys = (("s", signature(result)), ("l", looks(result)))
        if ("s", signature(result)) in nothing:
            menu.removeAction(act)
            continue
        kept = next((seen[k] for k in keys if k in seen), None)
        if kept is not None:                  # same layout as an entry already kept
            menu.removeAction(act)
            kept.setToolTip(kept.toolTip() + f"<br>(same result as “{act.text()}”)")
            continue
        for k in keys:
            seen[k] = act
        moved_ids = {id(x) for x in _leaves(moved)} if moved is not None else set()
        target_ids = {id(x) for x in _leaves(target)} if target is not None else set()
        icon = sketch(result, moved_ids, target_ids, dpr, letters=row_names)
        if icon is not None:
            act.setIcon(icon)
    _drop_empty_separators(menu)
    if any(not a.icon().isNull() for a in menu.actions()):
        # no base style passed: QProxyStyle(style) takes ownership of it, and the
        # application's style was deleted with the menu (crash on the next paint)
        style = SketchMenuStyle()
        menu.setStyle(style)
        menu._sketch_style = style            # keep it alive with the menu
        menu.setToolTipsVisible(True)
        attach_preview(menu)


def _drop_empty_separators(menu):
    acts = menu.actions()
    prev_sep = True
    for i, a in enumerate(acts):
        if a.isSeparator():
            if prev_sep or i == len(acts) - 1:
                menu.removeAction(a)
                continue
            prev_sep = True
        else:
            prev_sep = False
    acts = menu.actions()
    if acts and acts[-1].isSeparator():
        menu.removeAction(acts[-1])
