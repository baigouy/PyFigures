"""Marks drawn on the canvas panels, on screen only (never in an export).

Selected panels show, in their centre (the corners hold letters, insets and
scale bars):

- their number in reading order (#1, #2…), the numbers the chat assistant
  accepts ("#3" is a panel reference), for figures without letters or with one
  letter per row;
- what the panel is (image, code, vector) and what differs from the file: stack
  size and what is shown ("▤ 21z 19t (max)"), hidden or recoloured channels
  ("◐ ch"), crop, rotation, flip, contrast, series of a multi-series file;
- warnings, in orange: low resolution at the current figure width, the same
  image shown twice (image reuse), a missing file.

Nothing is drawn without a selection (orange dots on unselected panels were
tried and found a nuisance by the user).

Suggested by the user while the chat could not tell which images were stacks
(2026-11-12).
"""
from __future__ import annotations

import os
import time

from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPen

from batoolset.drawings.shapes.group import Group
from batoolset.drawings.shapes.image2d import Image2D

MIN_DPI = 300
UNITS_PER_INCH = 72.0          # the canvas works in points: the figure-width box converts at 72 per inch
INFO, WARNING = "info", "warning"
_EXISTS = {}                   # filename -> (checked at, exists): paint runs at every hover


def numbered_panels(items):
    """(number, panel) in reading order, the order of the chat's panel_references:
    groups depth first, text images skipped."""
    out = []

    def walk(objects):
        for obj in objects:
            if isinstance(obj, Group):
                if not obj.isText:
                    walk(obj.content)
            elif isinstance(obj, Image2D) and not obj.isText:
                out.append(obj)
    walk(items)
    return list(enumerate(out, 1))


def selected_panels(selection):
    """The image panels inside a selection (one panel, a group, a list of them)."""
    if selection is None:
        return []
    items = selection if isinstance(selection, list) else [selection]
    return [p for _, p in numbered_panels(items)]


def channels_changed(panel) -> bool:
    """True when a channel is hidden or has its own colour table: what the panel
    shows is not what the file shows."""
    channels = getattr(panel, "channels", None)
    if isinstance(channels, (list, tuple)) and any(c is False for c in channels):
        return True
    luts = getattr(panel, "LUTs", None)
    return isinstance(luts, (list, tuple)) and any(l is not None for l in luts)


def _crop(panel):
    return tuple(int(getattr(panel, f"crop_{side}", 0) or 0) for side in ("left", "top", "right", "bottom"))


def stack_text(panel) -> str | None:
    """'21z 19t (max)', '48z (z 5)', '19t', or None for a single image."""
    from pyfigures.stack_info import header_sizes
    sizes = header_sizes(getattr(panel, "filename", None), getattr(panel, "serie_to_open", None))
    if not isinstance(sizes, dict):
        return None
    z, t = sizes.get("d", 1), sizes.get("t", 1)
    parts = [f"{z}z" if z > 1 else "", f"{t}t" if t > 1 else ""]
    text = " ".join(p for p in parts if p)
    if not text:
        return None
    if z > 1:
        projection = getattr(panel, "projection", None)
        start, end = getattr(panel, "projection_z_start", None), getattr(panel, "projection_z_end", None)
        if projection and start is not None and end is not None and end - start == 1:
            text += f" (z {start})"
        elif projection:
            text += f" ({projection})" if start is None and end is None else f" ({projection} z {start or 0}-{end if end is not None else z})"
    return text


def effective_dpi(panel):
    """Pixels per inch of the panel at the figure's current printed size, None when
    unknown (image not loaded yet, plot, vector)."""
    img = getattr(panel, "img", None)
    if img is None or not hasattr(img, "ndim"):
        return None
    try:
        raw_w, _ = panel.get_raw_size()
        left, _, right, _ = _crop(panel)
        shown = float(raw_w) - left - right
        width = float(panel.width(all=True))
    except Exception:
        return None
    if shown <= 0 or width <= 0:
        return None
    return shown / (width / UNITS_PER_INCH)


def _missing(panel) -> bool:
    name = getattr(panel, "filename", None)
    if not name or not isinstance(name, str):
        return False
    now = time.monotonic()
    seen = _EXISTS.get(name)
    if seen is None or now - seen[0] > 5:
        seen = (now, os.path.exists(name))
        _EXISTS[name] = seen
    return not seen[1]


def _view_key(panel):
    """What the panel shows: the same file, series, crop, channels and Z range
    shown twice is the same image (channel splits and montage frames differ)."""
    name = getattr(panel, "filename", None)
    if not name or not isinstance(name, str):
        return None
    channels = getattr(panel, "channels", None)
    return (os.path.normcase(name), getattr(panel, "serie_to_open", None), _crop(panel),
            tuple(channels) if isinstance(channels, (list, tuple)) else channels,
            getattr(panel, "projection", None), getattr(panel, "projection_z_start", None),
            getattr(panel, "projection_z_end", None), bool(getattr(panel, "flip_h", False)),
            bool(getattr(panel, "flip_v", False)), getattr(panel, "theta", 0) or 0)


def panel_kind(panel) -> str:
    """'vector' (SVG / PDF drawing), 'code' (made by a script or a plot) or 'image'
    (pixels from a file): what can be done to it differs (the user's idea, 2026-11-12)."""
    renderer = getattr(panel, "renderer", None)
    name = str(getattr(panel, "filename", "") or "").lower()
    if renderer is not None and type(renderer).__name__ == "QSvgRenderer" or name.endswith((".svg", ".pdf", ".eps")):
        return "vector"
    img = getattr(panel, "img", None)
    if str(getattr(panel, "custom_loading_script", "") or "").strip() or type(img).__name__ == "Figure":
        return "code"
    return "image"


_KIND_MARK = {"image": "▦ image", "code": "ƒ code", "vector": "◇ vector"}   # ▦ ƒ ◇


_PANEL_CACHE = {}       # id(panel) -> (signature, record): repaints run at every hover


def _signature(panel):
    """Cheap attribute reads (no geometry computation): when none changed, the
    panel's marks and drawn rectangle are the same as at the last repaint."""
    g = panel.__dict__
    normalization = g.get("normalization")
    channels, luts = g.get("channels"), g.get("LUTs")
    return (QRectF.x(panel), QRectF.y(panel), QRectF.width(panel), QRectF.height(panel), g.get("scale"),
            g.get("filename"), g.get("crop_left"), g.get("crop_top"), g.get("crop_right"), g.get("crop_bottom"),
            g.get("theta"), g.get("flip_h"), g.get("flip_v"), id(normalization), bool(normalization),
            tuple(channels) if isinstance(channels, list) else channels,
            tuple(luts) if isinstance(luts, list) else luts, g.get("serie_to_open"), g.get("projection"),
            g.get("projection_z_start"), g.get("projection_z_end"), id(g.get("img")), id(g.get("renderer")),
            g.get("custom_loading_script"))


def _record(panel):
    """{'rect', 'info', 'low_dpi', 'view'} of a panel, recomputed only when it changed."""
    try:
        signature = _signature(panel)
    except Exception:
        signature = None
    hit = _PANEL_CACHE.get(id(panel))
    if signature is not None and hit is not None and hit[0] == signature and hit[2] is panel:
        return hit[1]
    dpi = effective_dpi(panel)
    record = {"rect": _rect(panel), "info": changes(panel), "view": _view_key(panel),
              "low_dpi": [(f"⚠ {dpi:.0f} dpi", WARNING)] if dpi is not None and dpi < MIN_DPI else []}
    _PANEL_CACHE[id(panel)] = (signature, record, panel)
    return record


def context(shapes):
    """Computed once per paint: numbers, cached records, which panels repeat another one."""
    numbered = numbered_panels(shapes)
    records, first, repeats = {}, {}, {}
    for number, panel in numbered:
        record = records[id(panel)] = _record(panel)
        key = record["view"]
        if key is None:
            continue
        if key in first:
            repeats[id(panel)] = first[key]
        else:
            first[key] = number
    if len(_PANEL_CACHE) > 2 * len(numbered) + 50:          # panels deleted since
        alive = set(records)
        for key in [k for k in _PANEL_CACHE if k not in alive]:
            del _PANEL_CACHE[key]
    return {"numbered": numbered, "repeats": repeats, "records": records}


def badges(panel, number, ctx=None):
    """(text, kind) drawn on one selected panel, in reading order."""
    return [(f"#{number}", INFO)] + changes(panel) + warnings(panel, ctx)


def changes(panel):
    """(text, INFO): what the panel is, and what differs from its file."""
    out = [(_KIND_MARK[panel_kind(panel)], INFO)]
    try:
        stack = stack_text(panel)
    except Exception:
        stack = None
    if stack:
        out.append(("▤ " + stack, INFO))              # ▤ a pile of planes
    series = getattr(panel, "serie_to_open", None)
    if isinstance(series, int) and series > 0:
        out.append((f"series {series + 1}", INFO))         # counted from 1 for people
    if channels_changed(panel):
        out.append(("◐ ch", INFO))                    # ◐ colours changed
    if any(_crop(panel)):
        out.append(("⌗ crop", INFO))                  # ⌗
    theta = getattr(panel, "theta", 0) or 0
    if theta:
        out.append((f"↻ {theta:g}°", INFO))      # ↻ 30°
    flips = ("⇋" if getattr(panel, "flip_h", False) else "") + ("⇵" if getattr(panel, "flip_v", False) else "")
    if flips:
        out.append((flips + " flip", INFO))                # ⇋ ⇵
    if getattr(panel, "normalization", None):
        out.append(("◑ contrast", INFO))              # ◑ display range changed
    return out


def warnings(panel, ctx=None):
    """(text, WARNING): what would be a problem in the figure as it stands."""
    out = []
    if _missing(panel):
        out.append(("⚠ missing", WARNING))
        return out
    record = ctx["records"].get(id(panel)) if ctx and "records" in ctx else None
    if record is not None:
        out.extend(record["low_dpi"])
    else:
        dpi = effective_dpi(panel)
        if dpi is not None and dpi < MIN_DPI:
            out.append((f"⚠ {dpi:.0f} dpi", WARNING))
    if ctx and id(panel) in ctx["repeats"]:
        out.append((f"⚠ same as #{ctx['repeats'][id(panel)]}", WARNING))
    return out


def _rect(panel):
    try:
        return panel.getRect(all=True)              # where the panel is drawn on the canvas
    except Exception:
        return QRectF(panel.x(), panel.y(), panel.width(), panel.height())


def fit(items, width_of, max_width, max_height, line_height, gap):
    """Lines of ((text, kind), width) that stay inside the panel: marks flow onto as
    few lines as fit its width; when they are too many for its height, the number and
    the warnings are kept first and the rest becomes "+N" (short rows spilled over
    the next row)."""
    def flow(chosen):
        lines, line, used = [], [], 0.0
        for item in chosen:
            w = width_of(item[0])
            if line and used + gap + w > max_width:
                lines.append(line)
                line, used = [], 0.0
            line.append((item, w))
            used += (gap if len(line) > 1 else 0) + w
        if line:
            lines.append(line)
        return lines

    def height(lines):
        return len(lines) * line_height + (len(lines) - 1) * gap

    lines = flow(items)
    if height(lines) <= max_height or len(items) <= 1:
        return lines
    ranked = [items[0]] + [i for i in items[1:] if i[1] == WARNING] + [i for i in items[1:] if i[1] != WARNING]
    for keep in range(len(ranked) - 1, 0, -1):
        kept = ranked[:keep]
        chosen = [i for i in items if i in kept] + [(f"+{len(items) - keep}", INFO)]
        lines = flow(chosen)
        if height(lines) <= max_height:
            return lines
    return flow([items[0], (f"+{len(items) - 1}", INFO)])[:1]


def place_block(rect, block_width, block_height, avoid=None, gap=2.0):
    """Top y of the marks block: centred in the panel, moved below (or, without room,
    above) *avoid*, the selection's name drawn at the selection's centre."""
    y = rect.center().y() - block_height / 2
    if avoid is None:
        return y
    block = QRectF(rect.center().x() - block_width / 2, y, block_width, block_height)
    if not block.intersects(avoid):
        return y
    below = avoid.bottom() + gap
    if below + block_height <= rect.bottom() or avoid.top() - gap - block_height < rect.top():
        return below
    return avoid.top() - gap - block_height


def draw_badges(painter, shapes, selection, scale=1.0, limit=60, avoid=None):
    """Draw the marks of every selected panel in its centre, at a constant size on
    screen whatever the zoom."""
    scale = scale if scale and scale > 0 else 1.0
    chosen = {id(p) for p in selected_panels(selection)}
    if not chosen:
        return            # nothing selected, nothing drawn: warnings without a selection were a nuisance
    ctx = context(shapes)       # the whole figure: numbers and "same as #1" need every panel
    painter.save()
    try:
        font = QFont(painter.font())
        font.setPointSizeF(8.0 / scale)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        pad, gap = 2.0 / scale, 3.0 / scale
        shown = 0
        for number, panel in ctx["numbered"]:
            record = ctx["records"][id(panel)]
            rect = record["rect"]
            if id(panel) not in chosen:
                continue
            if shown >= limit:
                continue
            shown += 1
            try:
                items = [(f"#{number}", INFO)] + record["info"] + warnings(panel, ctx)
            except Exception:
                items = [(f"#{number}", INFO)]
            h = metrics.height() + pad
            lines = fit(items, lambda t: metrics.horizontalAdvance(t) + 2 * pad, rect.width() - 2 * gap,
                        rect.height() - 2 * gap, h, gap)
            block_width = max(sum(w for _, w in line) + gap * (len(line) - 1) for line in lines)
            y = place_block(rect, block_width, len(lines) * h + (len(lines) - 1) * gap, avoid, gap)
            for line in lines:
                x = rect.center().x() - (sum(w for _, w in line) + gap * (len(line) - 1)) / 2
                for (text, kind), w in line:
                    box = QRectF(x, y, w, h)
                    painter.setPen(Qt.NoPen)
                    if kind == WARNING:
                        painter.setBrush(QBrush(QColor(255, 140, 0, 235)))
                        colour = QColor(20, 20, 20)
                    else:
                        painter.setBrush(QBrush(QColor(20, 20, 20, 200)))
                        colour = QColor(255, 235, 59)
                    painter.drawRoundedRect(box, 2.5 / scale, 2.5 / scale)
                    painter.setPen(QPen(colour))
                    painter.drawText(box, int(Qt.AlignCenter), text)
                    x += w + gap
                y += h + gap
    finally:
        painter.restore()
