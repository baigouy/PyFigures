"""Editable exports: PowerPoint (.pptx) and an Adobe Illustrator script (.jsx).

Both rebuild the figure out of *native* objects of the target application —
pictures for the image data, editable text boxes for every label, and vector
shapes for scale bars, ROIs, arrows, brackets and vector plots — so the figure
can still be edited there (QuickFigures-style), instead of being one flat image.

How it works: the figure is painted by the normal PyFigures renderer into an
in-memory SVG (Qt's QSvgGenerator records every image, path and text run with
its exact transform). That SVG is parsed into a flat *scene* of primitives in
figure points (1/72 inch), each primitive is assigned to the panel it lies on,
and the scene is written out:

* ``write_pptx``  — one slide the size of the figure, one group per panel
  (python-pptx);
* ``write_jsx``   — an ExtendScript file plus an ``<name>_assets`` folder of
  PNGs; File > Scripts > Other Script… in Illustrator builds the figure as one
  group per panel, with live text and vector paths.

Only ``capture_scene`` needs Qt; parsing and both writers are pure Python.

Text *inside* Matplotlib data plots (tick labels, axis titles, stars) is real
text as well: during the capture plots are rendered with svg.fonttype 'none'
and their text drawn with drawText (batoolset.drawings.svg_text_renderer) —
Qt alone would draw it as glyph outlines. Text inside imported SVG/PDF
graphics and LaTeX-typeset plots stays outlines. Every PyFigures label
(letters, channel names, scale-bar text, annotations) is real, editable text. ``$…$`` maths in labels is recorded as
its TeX source (batoolset math_text markers) and becomes a native PowerPoint
equation (OMML) inside the label's text box, and Unicode text in Illustrator.

Video / time-stack panels play in PowerPoint: their picture becomes a movie
(H.264 mp4 of the panel's frames, as displayed) with the shown frame as its
poster image. Illustrator has no movies: it gets the shown frame.
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
EMU_PER_PT = 12700
_CURVE_STEPS = 12          # line segments per Bezier when flattening a curve
_ASCENT = 0.905            # Arial / Helvetica ascent, in em
_GENERIC_SANS = {"sans serif", "sans-serif", "sansserif", "helvetica", "helvetica neue",
                 "tex gyre heros", "nimbus sans", "arimo", "liberation sans", "ms shell dlg 2",
                 "segoe ui", ""}


# ---------------------------------------------------------------------------
# scene capture (needs Qt)
# ---------------------------------------------------------------------------
def capture_scene(panel, movies=False) -> dict:
    """Render the PyFigures canvas *panel* (an EZFIG panel) into a scene dict:
    {'width', 'height', 'items': [...], 'panels': [(x, y, w, h), ...]} in points.
    With *movies*, the picture of each video / time-stack panel also carries its
    frames as an mp4 (item['movie'], see attach_movies)."""
    from qtpy.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize
    from qtpy.QtGui import QPainter
    from qtpy.QtSvg import QSvgGenerator
    from batoolset.lists.tools import flatten_iterable

    if hasattr(panel, "wait_for_pending_images"):
        panel.wait_for_pending_images()
    bounds = panel.updateBounds()
    width = float(bounds.width())
    height = float(bounds.height())
    if width < 1 or height < 1:
        if getattr(panel, "shapes_to_draw", None):
            raise RuntimeError(f"the figure is {width:.1f} x {height:.1f} pt: its panels have no "
                               f"room (too narrow for its panels and the gaps between them) — "
                               f"widen the figure, wrap the rows or reduce the spacing")
        raise RuntimeError("the figure contains no panels to export")
    # the figure's own top-left corner (not a fixed margin: free-canvas
    # figures can start anywhere)
    pad_x = float(bounds.x())
    pad_y = float(bounds.y())

    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    gen = QSvgGenerator()
    gen.setOutputDevice(buf)
    gen.setSize(QSize(int(math.ceil(width)), int(math.ceil(height))))
    gen.setViewBox(QRectF(0, 0, width, height))
    # 1 SVG unit = 1 point = 1 canvas unit; the resolution only sets how point-size
    # fonts become units: as on the images the other exports draw on (QImage,
    # 96 dpi), or labels and letters came out at 72/96 of their size, off-centre
    from qtpy.QtGui import QImage
    gen.setResolution(QImage(1, 1, QImage.Format.Format_ARGB32).logicalDpiY())
    from pyfigures.gui.svg_painter import CroppingPainter
    painter = CroppingPainter(gen)
    painter.translate(-pad_x, -pad_y)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    shapes = flatten_iterable(panel.shapes_to_draw)
    fig_images = [s for s in shapes if hasattr(s, "enter_export_mode")]
    try:
        from batoolset.drawings import math_text
    except ImportError:
        math_text = None
    from batoolset.drawings.shapes.image2d import Image2D
    try:
        Image2D._export_editable_text = True       # plot text as text, not outlines
        for img in fig_images:
            img.enter_export_mode()
        if math_text is not None:
            math_text.SOURCE_MARKERS = True        # $…$ recorded as TeX, not outlines
        panel.paint(painter)
    finally:
        if math_text is not None:
            math_text.SOURCE_MARKERS = False
        painter.end()
        for img in fig_images:
            img.exit_export_mode()
        Image2D._export_editable_text = False
        buf.close()

    rects = []
    rect_of = {}
    for s in fig_images:
        try:
            r = s.getRect(all=True)
            rect_of[id(s)] = (float(r.x()) - pad_x, float(r.y()) - pad_y, float(r.width()), float(r.height()))
            rects.append(rect_of[id(s)])
        except Exception:
            pass
    scene = parse_svg(bytes(data))
    scene["width"] = width
    scene["height"] = height
    assign_groups(scene, rects)
    if movies:
        attach_movies(panel, scene, rect_of)
    return scene


def _qimage_to_rgb(qimg):
    """(H, W, 3) uint8 copy of a QImage."""
    import numpy as np
    from qtpy.QtGui import QImage
    img = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)
    return np.ascontiguousarray(arr[:, :img.width(), :3])


def _grab_drawn_image(shape):
    """The picture *shape* draws (its displayed, cropped image, without labels),
    as an (H, W, 3) array, or None."""
    from qtpy.QtGui import QImage, QPixmap
    from pyfigures.gui.svg_painter import CroppingPainter

    class Grabber(CroppingPainter):
        grabbed = None

        def _keep(self, *args):
            if self.grabbed is None:
                for a in args[1:]:
                    if isinstance(a, QPixmap):
                        a = a.toImage()
                    if isinstance(a, QImage):
                        self.grabbed = a.copy()
                        break

        def drawImage(self, *args, **kwargs):
            return self._crop_call(Grabber._keep, QImage, args, kwargs)

        def drawPixmap(self, *args, **kwargs):
            return self._crop_call(Grabber._keep, QPixmap, args, kwargs)

    device = QImage(1, 1, QImage.Format.Format_ARGB32)
    painter = Grabber(device)
    try:
        shape.enter_export_mode()
        try:
            shape.draw_bg(painter, draw=True, restore_painter_in_the_end=True)
        finally:
            shape.exit_export_mode()
    finally:
        painter.end()
    if painter.grabbed is None:
        return None
    return _qimage_to_rgb(painter.grabbed)


_MOVIE_MIN_SIDE = 512       # small stacks are enlarged (nearest neighbour): PowerPoint blurs them less
_MOVIE_MAX_WIDTH = 3840     # mp4 decoder limit


def movie_frames_to_mp4(frames, fps):
    """H.264 mp4 bytes of a list of equal (H, W, 3) uint8 frames; small frames are
    enlarged by a whole factor (sharp pixels) and the size made even."""
    import tempfile
    import numpy as np
    from batoolset.img import write_video
    stack = np.stack(frames, axis=0)
    h, w = stack.shape[1:3]
    factor = max(1, int(math.ceil(_MOVIE_MIN_SIDE / max(h, w))))
    factor = max(1, min(factor, _MOVIE_MAX_WIDTH // max(w, 1)))
    if factor > 1:
        stack = np.repeat(np.repeat(stack, factor, axis=1), factor, axis=2)
    pad_h = stack.shape[1] % 2
    pad_w = stack.shape[2] % 2
    if pad_h or pad_w:
        stack = np.pad(stack, ((0, 0), (0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    tmp_dir = tempfile.mkdtemp(prefix="pyf_movie_")
    path = os.path.join(tmp_dir, "panel.mp4")
    try:
        write_video(stack, path, fps=fps, dimensions="thwc")
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


def attach_movies(panel, scene, rect_of):
    """Give the picture of every video / time-stack panel its movie: the panel's
    frames (as displayed, cropped, without labels) as mp4 bytes in item['movie'].
    PowerPoint plays it in place; the picture stays its poster frame."""
    stacks = panel._collect_time_stacks() if hasattr(panel, "_collect_time_stacks") else []
    for s, dims, n_frames in stacks:
        rect = rect_of.get(id(s))
        if rect is None or n_frames < 2:
            continue
        x, y, w, h = rect
        best = None
        for it in scene["items"]:
            if it["kind"] != "image" or "movie" in it:
                continue
            x0, y0, x1, y1 = _bbox(it)
            if x0 >= x - 1 and y0 >= y - 1 and x1 <= x + w + 1 and y1 <= y + h + 1:
                if best is None or it["w"] * it["h"] > best["w"] * best["h"]:
                    best = it
        if best is None:
            continue
        originals = (getattr(s, "dimensions", None), getattr(s, "projection", None))
        frames = []
        try:
            for i in range(n_frames):
                panel._show_stack_frame(s, dims, i)
                frame = _grab_drawn_image(s)
                if frame is None or (frames and frame.shape != frames[0].shape):
                    frames = []
                    break
                frames.append(frame)
        finally:
            s.dimensions, s.projection = originals
            s.update_qimage()
        if frames:
            best["movie"] = movie_frames_to_mp4(frames, panel._video_fps([s]))
            best["movie_frames"] = len(frames)


# ---------------------------------------------------------------------------
# SVG -> scene (pure Python)
# ---------------------------------------------------------------------------
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _mul(m, n):
    """Compose affine matrices (a, b, c, d, e, f): apply n first, then m."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + c * b2, b * a2 + d * b2,
            a * c2 + c * d2, b * c2 + d * d2,
            a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _parse_transform(s):
    m = _IDENTITY
    if not s:
        return m
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s):
        v = [float(t) for t in re.split(r"[\s,]+", args.strip()) if t]
        if name == "matrix" and len(v) == 6:
            n = tuple(v)
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            t = math.radians(v[0])
            n = (math.cos(t), math.sin(t), -math.sin(t), math.cos(t), 0, 0)
            if len(v) == 3:
                n = _mul(_mul((1, 0, 0, 1, v[1], v[2]), n), (1, 0, 0, 1, -v[1], -v[2]))
        else:
            continue
        m = _mul(m, n)
    return m


def _scale_of(m):
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0


def _angle_of(m):
    """Clockwise rotation (degrees) of the matrix in a y-down space."""
    return math.degrees(math.atan2(m[1], m[0]))


def _color(v):
    """'#rrggbb' / 'rgb(r,g,b)' / named -> (r, g, b) or None for none."""
    if v is None:
        return None
    v = v.strip()
    if not v or v == "none" or v.startswith("url("):
        return None
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            return None
    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v)
    if m:
        return tuple(int(x) for x in m.groups())
    named = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
             "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0)}
    return named.get(v.lower())


def _float(v, default=0.0):
    try:
        return float(re.sub(r"[a-z%]+$", "", str(v).strip()))
    except (TypeError, ValueError):
        return default


_STYLE_KEYS = ("fill", "fill-opacity", "stroke", "stroke-opacity", "stroke-width", "opacity",
               "vector-effect", "font-family", "font-size", "font-weight", "font-style", "fill-rule")


def _style(el, inherited):
    st = dict(inherited)
    for k in _STYLE_KEYS:
        if k in el.attrib:
            st[k] = el.attrib[k]
    if "style" in el.attrib:
        for part in el.attrib["style"].split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                st[k.strip()] = v.strip()
    return st


def _cubic(p0, p1, p2, p3):
    out = []
    for i in range(1, _CURVE_STEPS + 1):
        t = i / _CURVE_STEPS
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def _quad(p0, p1, p2):
    out = []
    for i in range(1, _CURVE_STEPS + 1):
        t = i / _CURVE_STEPS
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def parse_path_d(d):
    """SVG path data -> [(points, closed)], curves flattened to line segments."""
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtZzAa]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d or "")
    subpaths = []
    pts = []
    closed = False
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    last_ctrl = None
    cmd = None
    i = 0

    def nums(k):
        nonlocal i
        vals = [float(t) for t in tokens[i:i + k]]
        i += k
        return vals

    def flush():
        nonlocal pts, closed
        if len(pts) >= 2:
            subpaths.append((pts, closed))
        pts = []
        closed = False

    while i < len(tokens):
        t = tokens[i]
        if re.match(r"[A-Za-z]", t):
            cmd = t
            i += 1
            if cmd in "Zz":
                closed = True
                cur = start
                flush()
                cmd = None
                continue
        if cmd is None:
            i += 1
            continue
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if c == "M":
            x, y = nums(2)
            flush()
            cur = (x + ox, y + oy)
            start = cur
            pts = [cur]
            cmd = "l" if rel else "L"      # following pairs are line-tos
        elif c == "L":
            x, y = nums(2)
            cur = (x + ox, y + oy)
            pts.append(cur)
        elif c == "H":
            (x,) = nums(1)
            cur = (x + ox, cur[1])
            pts.append(cur)
        elif c == "V":
            (y,) = nums(1)
            cur = (cur[0], y + (cur[1] if rel else 0.0))
            pts.append(cur)
        elif c == "C":
            x1, y1, x2, y2, x, y = nums(6)
            p1 = (x1 + ox, y1 + oy)
            p2 = (x2 + ox, y2 + oy)
            p3 = (x + ox, y + oy)
            pts.extend(_cubic(cur, p1, p2, p3))
            last_ctrl = p2
            cur = p3
        elif c == "S":
            x2, y2, x, y = nums(4)
            p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
            p2 = (x2 + ox, y2 + oy)
            p3 = (x + ox, y + oy)
            pts.extend(_cubic(cur, p1, p2, p3))
            last_ctrl = p2
            cur = p3
        elif c == "Q":
            x1, y1, x, y = nums(4)
            p1 = (x1 + ox, y1 + oy)
            p2 = (x + ox, y + oy)
            pts.extend(_quad(cur, p1, p2))
            last_ctrl = p1
            cur = p2
        elif c == "T":
            x, y = nums(2)
            p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
            p2 = (x + ox, y + oy)
            pts.extend(_quad(cur, p1, p2))
            last_ctrl = p1
            cur = p2
        elif c == "A":                      # arcs: straight line to the end point
            vals = nums(7)
            cur = (vals[5] + ox, vals[6] + oy)
            pts.append(cur)
        else:
            i += 1
        if c not in "CSQT":
            last_ctrl = None
    flush()
    return subpaths


def _ellipse_points(cx, cy, rx, ry, n=48):
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n))
            for k in range(n)]


def _shape_item(st, m, subpaths):
    fill = _color(st.get("fill", "black"))
    stroke = _color(st.get("stroke", "none"))
    if fill is None and stroke is None:
        return None
    opacity = _float(st.get("opacity", 1), 1.0)
    width = _float(st.get("stroke-width", 1), 1.0)
    if st.get("vector-effect") != "non-scaling-stroke":
        width *= _scale_of(m)
    paths = []
    for pts, closed in subpaths:
        tp = [_apply(m, x, y) for x, y in pts]
        if len(tp) >= 2:
            paths.append((tp, closed))
    if not paths:
        return None
    return {"kind": "path", "subpaths": paths,
            "fill": fill, "fill_opacity": _float(st.get("fill-opacity", 1), 1.0) * opacity,
            "stroke": stroke, "stroke_opacity": _float(st.get("stroke-opacity", 1), 1.0) * opacity,
            "stroke_width": width}


def parse_svg(svg_bytes) -> dict:
    """Parse a Qt-generated SVG into {'items': [...]} (absolute coordinates)."""
    root = ET.fromstring(svg_bytes)
    items = []
    vb = root.attrib.get("viewBox")
    scene = {"items": items}
    if vb:
        v = [float(t) for t in re.split(r"[\s,]+", vb.strip())]
        scene["width"] = v[2]
        scene["height"] = v[3]

    def walk(el, m, st):
        tag = el.tag.replace(SVG_NS, "")
        m = _mul(m, _parse_transform(el.attrib.get("transform")))
        st = _style(el, st)
        if tag in ("svg", "g"):
            for ch in el:
                walk(ch, m, st)
            return
        if tag == "path":
            it = _shape_item(st, m, parse_path_d(el.attrib.get("d")))
        elif tag == "rect":
            x = _float(el.attrib.get("x"))
            y = _float(el.attrib.get("y"))
            w = _float(el.attrib.get("width"))
            h = _float(el.attrib.get("height"))
            it = _shape_item(st, m, [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)])
        elif tag in ("polyline", "polygon"):
            v = [float(t) for t in re.split(r"[\s,]+", el.attrib.get("points", "").strip()) if t]
            pts = list(zip(v[0::2], v[1::2]))
            it = _shape_item(st, m, [(pts, tag == "polygon")])
        elif tag == "line":
            pts = [(_float(el.attrib.get("x1")), _float(el.attrib.get("y1"))),
                   (_float(el.attrib.get("x2")), _float(el.attrib.get("y2")))]
            it = _shape_item(st, m, [(pts, False)])
        elif tag in ("ellipse", "circle"):
            cx = _float(el.attrib.get("cx"))
            cy = _float(el.attrib.get("cy"))
            rx = _float(el.attrib.get("rx", el.attrib.get("r")))
            ry = _float(el.attrib.get("ry", el.attrib.get("r")))
            it = _shape_item(st, m, [(_ellipse_points(cx, cy, rx, ry), True)])
        elif tag == "image":
            it = _image_item(el, m, st)
        elif tag == "text":
            it = _text_item(el, m, st)
        else:
            it = None
        if it is not None:
            items.append(it)

    walk(root, _IDENTITY, {})
    scene["items"] = merge_math_runs(items)
    return scene


def _image_item(el, m, st):
    href = el.attrib.get(XLINK_HREF) or el.attrib.get("href") or ""
    mt = re.match(r"data:image/(\w+);base64,(.*)", href, re.S)
    if not mt:
        return None
    data = base64.b64decode(mt.group(2))
    fmt = mt.group(1).lower()
    if fmt != "png":                         # keep everything as PNG
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            out = io.BytesIO()
            im.save(out, format="PNG")
            data = out.getvalue()
        except Exception:
            return None
    x = _float(el.attrib.get("x"))
    y = _float(el.attrib.get("y"))
    w = _float(el.attrib.get("width"))
    h = _float(el.attrib.get("height"))
    if w <= 0 or h <= 0:
        return None
    cx, cy = _apply(m, x + w / 2, y + h / 2)
    sx = math.hypot(m[0], m[1])
    sy = math.hypot(m[2], m[3])
    return {"kind": "image", "png": data, "cx": cx, "cy": cy, "w": w * sx, "h": h * sy,
            "rotation": _angle_of(m), "opacity": _float(st.get("opacity", 1), 1.0)}


def _text_item(el, m, st):
    text = "".join(el.itertext())
    if not text.strip():
        return None
    x = _float(el.attrib.get("x"))
    y = _float(el.attrib.get("y"))
    ax, ay = _apply(m, x, y)
    weight = str(st.get("font-weight", "400")).lower()
    try:
        bold = weight == "bold" or int(weight) >= 600
    except ValueError:
        bold = False
    color = _color(st.get("fill", "black")) or (0, 0, 0)
    it = {"kind": "text", "text": text, "x": ax, "y": ay,
          "size": _float(st.get("font-size", 12), 12.0) * _scale_of(m),
          "family": portable_family(st.get("font-family", "")),
          "bold": bold, "italic": str(st.get("font-style", "")).lower() in ("italic", "oblique"),
          "color": color, "rotation": _angle_of(m)}
    marker = _parse_math_marker(text.strip())
    if marker is not None:
        from pyfigures.office_math import latex_to_unicode
        tex, width = marker
        it["math"] = tex
        it["text"] = latex_to_unicode(tex)
        it["width"] = width * _scale_of(m)
    return it


def _parse_math_marker(text):
    """(tex, width) of a $…$ formula recorded by batoolset's math_text, or None."""
    if not text.startswith("PYFMATH:"):
        return None
    try:
        width, hexed = text[len("PYFMATH:"):].split(":", 1)
        return bytes.fromhex(hexed.strip()).decode("utf-8"), float(width)
    except ValueError:
        return None


_RUN_KEYS = ("text", "math", "size", "family", "bold", "italic", "color")


def _runs(it):
    if "runs" in it:
        return it["runs"]
    run = {k: it.get(k) for k in _RUN_KEYS}
    run["width"] = text_width(it)
    return [run]


def _same_line(a, b):
    """b starts on a's baseline, right after a (allowing for estimated widths)."""
    if abs(((a["rotation"] - b["rotation"]) + 180) % 360 - 180) > 0.5:
        return False
    t = math.radians(a["rotation"])
    dx = b["x"] - a["x"]
    dy = b["y"] - a["y"]
    along = dx * math.cos(t) + dy * math.sin(t)
    across = -dx * math.sin(t) + dy * math.cos(t)
    size = max(a["size"], b["size"])
    return abs(across) < 0.35 * size and -0.5 * size <= along <= 1.5 * text_width(a) + size


def merge_math_runs(items):
    """Join each $…$ formula with the label text around it on the same line into
    one text item whose 'runs' alternate text and maths (in paint order)."""
    out = []
    for it in items:
        prev = out[-1] if out else None
        if (it["kind"] == "text" and prev is not None and prev["kind"] == "text"
                and ("math" in it or any(r.get("math") for r in _runs(prev)))
                and _same_line(prev, it)):
            runs = _runs(prev) + _runs(it)
            merged = dict(prev)
            merged.pop("math", None)
            merged["runs"] = runs
            merged["text"] = "".join(r["text"] for r in runs)
            merged["width"] = sum(r["width"] for r in runs)
            out[-1] = merged
            continue
        if it["kind"] == "text" and "math" in it:
            it = dict(it)
            it["runs"] = _runs(it)
        out.append(it)
    return out


def portable_family(family):
    """Map Qt's generic names and the bundled Helvetica/Arial clones to Arial,
    which PowerPoint and Illustrator always have."""
    f = (family or "").strip().strip("'\"").split(",")[0].strip()
    if f.lower() in _GENERIC_SANS or f.lower() == "arial":
        return "Arial"
    return f


# ---------------------------------------------------------------------------
# grouping by panel
# ---------------------------------------------------------------------------
def _bbox(item):
    if item["kind"] == "path":
        xs = [p[0] for pts, _ in item["subpaths"] for p in pts]
        ys = [p[1] for pts, _ in item["subpaths"] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    if item["kind"] == "image":
        return (item["cx"] - item["w"] / 2, item["cy"] - item["h"] / 2,
                item["cx"] + item["w"] / 2, item["cy"] + item["h"] / 2)
    w = text_width(item)
    return item["x"], item["y"] - item["size"] * _ASCENT, item["x"] + w, item["y"]


def assign_groups(scene, rects):
    """Give each item the index of the panel (x, y, w, h) containing its centre,
    the smallest one when panels overlap (insets); None outside every panel."""
    scene["panels"] = list(rects)
    for it in scene["items"]:
        x0, y0, x1, y1 = _bbox(it)
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        best = None
        best_area = None
        for k, (x, y, w, h) in enumerate(rects):
            if x - 0.5 <= cx <= x + w + 0.5 and y - 0.5 <= cy <= y + h + 0.5:
                if best_area is None or w * h < best_area:
                    best = k
                    best_area = w * h
        it["group"] = best
    # an inset panel inside a bigger panel belongs to that bigger panel's group
    for k, (x, y, w, h) in enumerate(rects):
        for j, (X, Y, W, H) in enumerate(rects):
            if j != k and W * H > w * h and X <= x and Y <= y and x + w <= X + W and y + h <= Y + H:
                for it in scene["items"]:
                    if it["group"] == k:
                        it["group"] = j


def text_width(item):
    """Advance width of a text run: exact for formulas and joined runs, else
    approximated (Arial-like average 0.56 em)."""
    if "width" in item:
        return max(1.0, item["width"])
    return max(1.0, 0.56 * item["size"] * len(item["text"]))


def _grouped(scene):
    """[(group_index or None, [items])] in paint order of each group's first item."""
    order = []
    groups = {}
    for it in scene["items"]:
        g = it.get("group")
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(it)
    return [(g, groups[g]) for g in order]


# ---------------------------------------------------------------------------
# PowerPoint
# ---------------------------------------------------------------------------
def _set_alpha(fill_or_line_fill, alpha):
    """python-pptx has no transparency API: add <a:alpha> to the solid fill."""
    if alpha >= 0.999:
        return
    from pptx.oxml.ns import qn
    try:
        solid = fill_or_line_fill._xPr.find(qn("a:solidFill"))
        clr = solid[0]
        a = clr.makeelement(qn("a:alpha"), {"val": str(int(max(0.0, alpha) * 100000))})
        clr.append(a)
    except Exception:
        pass


def write_pptx(scene, out_path):
    """Write *scene* as a one-slide .pptx with native, editable objects."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import MSO_AUTO_SIZE
    from pptx.util import Emu, Pt

    def emu(v):
        return Emu(int(round(v * EMU_PER_PT)))

    # PowerPoint slides are 1 to 56 inches on a side: a smaller figure sits
    # at the top left of a 1-inch slide; a larger one cannot be a slide
    longest = max(scene["width"], scene["height"])
    if longest > 56 * 72:
        raise RuntimeError(f"the figure is {longest / 72:.0f} inches on its longest side; "
                           f"PowerPoint slides are at most 56 inches: resize the figure first")
    prs = Presentation()
    prs.slide_width = emu(max(scene["width"], 72))
    prs.slide_height = emu(max(scene["height"], 72))
    slide = prs.slides.add_slide(prs.slide_layouts[6])        # blank layout
    for g, items in _grouped(scene):
        target = slide.shapes
        if g is not None and len(items) > 1:
            grp = slide.shapes.add_group_shape()
            grp.name = f"Panel {g + 1}"
            target = grp.shapes
        for it in items:
            if it["kind"] == "image" and it.get("movie"):
                _pptx_movie(slide.shapes, target, it, emu)
            elif it["kind"] == "image":
                _pptx_image(target, it, emu)
            elif it["kind"] == "path":
                _pptx_path(target, it, emu, RGBColor, Pt)
            else:
                _pptx_text(target, it, emu, RGBColor, Pt, MSO_AUTO_SIZE)
    prs.save(out_path)
    return out_path


def _pptx_image(shapes, it, emu):
    pic = shapes.add_picture(io.BytesIO(it["png"]), emu(it["cx"] - it["w"] / 2),
                             emu(it["cy"] - it["h"] / 2), emu(it["w"]), emu(it["h"]))
    if abs(it["rotation"]) > 0.01:
        pic.rotation = it["rotation"] % 360


def _pptx_movie(slide_shapes, shapes, it, emu):
    """A playable movie where the picture was, the picture as its poster frame.
    python-pptx adds movies to the slide only: it is then moved into the group."""
    movie = slide_shapes.add_movie(io.BytesIO(it["movie"]), emu(it["cx"] - it["w"] / 2),
                                   emu(it["cy"] - it["h"] / 2), emu(it["w"]), emu(it["h"]),
                                   poster_frame_image=io.BytesIO(it["png"]), mime_type="video/mp4")
    movie.name = "Movie"
    if abs(it["rotation"]) > 0.01:
        movie.rotation = it["rotation"] % 360
    if shapes is not slide_shapes:
        shapes._spTree.append(movie._element)
        shapes._recalculate_extents()


def _pptx_path(shapes, it, emu, RGBColor, Pt):
    subpaths = it["subpaths"]
    x0 = min(p[0] for pts, _ in subpaths for p in pts)
    y0 = min(p[1] for pts, _ in subpaths for p in pts)
    first = subpaths[0][0][0]
    builder = shapes.build_freeform(first[0] - x0, first[1] - y0, scale=EMU_PER_PT)
    filled = it["fill"] is not None          # SVG fills open subpaths too
    for k, (pts, closed) in enumerate(subpaths):
        if k:
            builder.move_to(pts[0][0] - x0, pts[0][1] - y0)
        builder.add_line_segments([(px - x0, py - y0) for px, py in pts[1:]], close=closed or filled)
    shp = builder.convert_to_shape(emu(x0), emu(y0))
    if filled:
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor(*it["fill"])
        _set_alpha(shp.fill, it["fill_opacity"])
    else:
        shp.fill.background()
    if it["stroke"] is not None:
        shp.line.color.rgb = RGBColor(*it["stroke"])
        shp.line.width = Pt(max(0.25, it["stroke_width"]))
        _set_alpha(shp.line.fill, it["stroke_opacity"])
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False


def _rotated_box(it, w, h):
    """Top-left of an unrotated box whose rotated copy keeps the text anchor
    (baseline start) where it belongs; the box rotates about its centre."""
    t = math.radians(it["rotation"])
    asc = it["size"] * _ASCENT
    lcx = w / 2
    lcy = -asc + h / 2
    cx = it["x"] + lcx * math.cos(t) - lcy * math.sin(t)
    cy = it["y"] + lcx * math.sin(t) + lcy * math.cos(t)
    return cx - w / 2, cy - h / 2


def _pptx_text(shapes, it, emu, RGBColor, Pt, MSO_AUTO_SIZE):
    w = text_width(it) * 1.15 + 2
    h = it["size"] * 1.2
    left, top = _rotated_box(it, w, h)
    tb = shapes.add_textbox(emu(left), emu(top), emu(w), emu(h))
    tf = tb.text_frame
    tf.word_wrap = False
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    para = tf.paragraphs[0]
    for r in _runs(it):
        if r.get("math") and _pptx_equation(para, r):
            continue
        run = para.add_run()
        run.text = r["text"]
        f = run.font
        f.name = r["family"]
        f.size = Pt(round(r["size"] * 2) / 2)
        f.bold = r["bold"]
        f.italic = r["italic"]
        f.color.rgb = RGBColor(*r["color"])
    if abs(it["rotation"]) > 0.01:
        tb.rotation = it["rotation"] % 360


_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _pptx_equation(para, run):
    """Append *run*'s formula to the paragraph as a native PowerPoint equation
    (OMML in an a14:m block, with a plain-text fallback for old readers).
    False when the formula cannot be converted."""
    from lxml import etree
    from pyfigures.office_math import OMML_NS, latex_to_omml
    omml = latex_to_omml(run["math"])
    if omml is None:
        return False
    sz = str(int(round(run["size"] * 100)))
    color = "%02X%02X%02X" % tuple(run["color"])
    a_rpr = ('<a:rPr xmlns:a="%s" lang="en-US" sz="%s" i="1">'
             '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>'
             '<a:latin typeface="Cambria Math" panose="02040503050406030204" pitchFamily="18" charset="0"/>'
             '</a:rPr>') % (_A_NS, sz, color)
    math_el = etree.fromstring(omml)
    for r in math_el.iter("{%s}r" % OMML_NS):
        t = r.find("{%s}t" % OMML_NS)
        if t is not None:
            t.addprevious(etree.fromstring(a_rpr))
    alt = etree.fromstring(
        '<mc:AlternateContent xmlns:mc="%s" xmlns:a="%s">'
        '<mc:Choice xmlns:a14="%s" Requires="a14"><a14:m/></mc:Choice>'
        '<mc:Fallback><a:r>%s<a:t/></a:r></mc:Fallback>'
        '</mc:AlternateContent>' % (_MC_NS, _A_NS, _A14_NS, a_rpr.replace(' xmlns:a="%s"' % _A_NS, "")))
    alt.find(".//{%s}m" % _A14_NS).append(math_el)
    alt.find(".//{%s}t" % _A_NS).text = run["text"]
    p = para._p
    end = p.find("{%s}endParaRPr" % _A_NS)
    if end is not None:
        end.addprevious(alt)
    else:
        p.append(alt)
    return True


# ---------------------------------------------------------------------------
# Adobe Illustrator (ExtendScript)
# ---------------------------------------------------------------------------
_PS_FONTS = {("Arial", False, False): "ArialMT", ("Arial", True, False): "Arial-BoldMT",
             ("Arial", False, True): "Arial-ItalicMT", ("Arial", True, True): "Arial-BoldItalicMT"}


def _ps_names(it):
    """PostScript names to try, most specific first."""
    key = (it["family"], it["bold"], it["italic"])
    names = []
    if key in _PS_FONTS:
        names.append(_PS_FONTS[key])
    base = it["family"].replace(" ", "")
    style = ("Bold" if it["bold"] else "") + ("Italic" if it["italic"] else "")
    names.append(base + ("-" + style if style else ""))
    if not style:
        names.append(base + "-Regular")
    names.append(_PS_FONTS[("Arial", it["bold"], it["italic"])])
    return names


def _r(v):
    return round(float(v), 3)


def write_jsx(scene, out_path):
    """Write an ExtendScript (.jsx) that rebuilds *scene* in Adobe Illustrator,
    plus an ``<stem>_assets`` folder holding the panel images as PNG.
    Returns (jsx_path, assets_dir)."""
    stem = os.path.splitext(os.path.basename(out_path))[0]
    assets_name = stem + "_assets"
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(out_path)), assets_name)
    os.makedirs(assets_dir, exist_ok=True)
    W = scene["width"]
    H = scene["height"]
    lines = [
        "// PyFigures -> Adobe Illustrator. Run it in Illustrator with",
        "// File > Scripts > Other Script... ; keep the '" + assets_name + "' folder next to it.",
        "#target illustrator",
        "(function () {",
        "var here = File($.fileName).parent;",
        "var assets = here.fsName + '/" + assets_name + "/';",
        "var doc = app.documents.add(DocumentColorSpace.RGB, %s, %s);" % (_r(W), _r(H)),
        "doc.artboards[0].artboardRect = [0, 0, %s, %s];" % (_r(W), _r(-H)),
        "var layer = doc.layers[0]; layer.name = 'PyFigures';",
        "function rgb(r, g, b) { var c = new RGBColor(); c.red = r; c.green = g; c.blue = b; return c; }",
        "function font(names) { for (var i = 0; i < names.length; i++) {"
        " try { return app.textFonts.getByName(names[i]); } catch (e) {} } return null; }",
        "function img(parent, name, cx, cy, w, h, rot, op) {",
        "  var p = parent.placedItems.add(); p.file = new File(assets + name);",
        "  p.width = w; p.height = h; p.position = [cx - w / 2, -(cy - h / 2)];",
        "  if (rot) { p.rotate(-rot); }",
        "  if (op < 1) { p.opacity = op * 100; }",
        "  try { p.embed(); } catch (e) {} }",
        "function shape(parent, subs, fill, fop, stroke, sop, sw) {",
        "  var host = parent; var items = [];",
        "  if (subs.length > 1) { host = parent.compoundPathItems.add(); }",
        "  for (var i = 0; i < subs.length; i++) {",
        "    var p = host.pathItems.add(); p.setEntirePath(subs[i][0]); p.closed = subs[i][1];",
        "    items.push(p); }",
        "  for (var j = 0; j < items.length; j++) { var q = items[j];",
        "    if (fill) { q.filled = true; q.fillColor = rgb(fill[0], fill[1], fill[2]); } else { q.filled = false; }",
        "    if (stroke) { q.stroked = true; q.strokeColor = rgb(stroke[0], stroke[1], stroke[2]); q.strokeWidth = sw; }",
        "    else { q.stroked = false; } }",
        "  var op = Math.max(fill ? fop : 0, stroke ? sop : 0);",
        "  if (op < 1) { (subs.length > 1 ? host : items[0]).opacity = op * 100; } }",
        "function txt(parent, s, x, y, size, color, names, rot) {",
        "  var t = parent.textFrames.pointText([0, 0]); t.contents = s;",
        "  var a = t.textRange.characterAttributes; a.size = size;",
        "  a.fillColor = rgb(color[0], color[1], color[2]);",
        "  var f = font(names); if (f) { a.textFont = f; }",
        "  if (rot) { t.rotate(-rot); }",
        "  var an = t.anchor; t.translate(x - an[0], -y - an[1]); }",
    ]
    n_img = 0
    for g, items in _grouped(scene):
        if g is not None and len(items) > 1:
            lines.append("var grp = layer.groupItems.add(); grp.name = 'Panel %d';" % (g + 1))
            parent = "grp"
        else:
            parent = "layer"
        for it in items:
            if it["kind"] == "image":
                name = "img_%03d.png" % n_img
                n_img += 1
                with open(os.path.join(assets_dir, name), "wb") as f:
                    f.write(it["png"])
                lines.append("img(%s, %s, %s, %s, %s, %s, %s, %s);" % (
                    parent, json.dumps(name), _r(it["cx"]), _r(it["cy"]), _r(it["w"]), _r(it["h"]),
                    _r(it["rotation"]) if abs(it["rotation"]) > 0.01 else 0, _r(it["opacity"])))
            elif it["kind"] == "path":
                fill = list(it["fill"]) if it["fill"] is not None else None
                subs = [[[[_r(x), _r(-y)] for x, y in pts], bool(closed or fill)]
                        for pts, closed in it["subpaths"]]
                stroke = list(it["stroke"]) if it["stroke"] is not None else None
                lines.append("shape(%s, %s, %s, %s, %s, %s, %s);" % (
                    parent, json.dumps(subs), json.dumps(fill), _r(it["fill_opacity"]),
                    json.dumps(stroke), _r(it["stroke_opacity"]), _r(max(0.25, it["stroke_width"]))))
            else:
                lines.append("txt(%s, %s, %s, %s, %s, %s, %s, %s);" % (
                    parent, json.dumps(it["text"], ensure_ascii=False), _r(it["x"]), _r(it["y"]),
                    _r(it["size"]), json.dumps(list(it["color"])), json.dumps(_ps_names(it)),
                    _r(it["rotation"]) if abs(it["rotation"]) > 0.01 else 0))
    lines.append("})();")
    # a BOM makes ExtendScript read the file as UTF-8 (µ, ±, Greek letters)
    with open(out_path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return out_path, assets_dir


def scene_summary(scene):
    kinds = {"image": 0, "path": 0, "text": 0}
    for it in scene["items"]:
        kinds[it["kind"]] += 1
    return {"width_pt": round(scene["width"], 2), "height_pt": round(scene["height"], 2),
            "images": kinds["image"], "shapes": kinds["path"], "texts": kinds["text"],
            "movies": sum(1 for it in scene["items"] if it.get("movie")),
            "panel_groups": len({it.get("group") for it in scene["items"] if it.get("group") is not None})}
