"""PyFigures MCP tools — ROI shapes, significance brackets, path remapping, cloning, figure-level properties and fonts.

Split out of pyfigures/mcp_server.py (which re-exports every name and
remains the server entry point: ``python -m pyfigures.mcp_server``).
"""
from __future__ import annotations

import fnmatch
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from textwrap import indent
from mcp.server.fastmcp import FastMCP, Image
from .app import (
    mcp,
    _warn,
)
from .core import (
    _warn_missing_font,
    _restyle_html_batch,
    _roi_outside_error,
    _restyle_letters,
    _append_image,
    _append_stats_entry,
    _child_text,
    _color_to_int,
    _decode,
    _encode_str,
    _escape_if_plain,
    _first_filename,
    _flatten_points,
    _get_annots_for_roi,
    _get_container,
    _iter_panel_elements,
    _label_background_text,
    _is_template,
    _load,
    _navigate_group,
    _new_free_text,
    _new_roi_ellipse,
    _new_roi_line,
    _new_roi_polygon,
    _new_roi_rect,
    _run_headless_op,
    _save,
    _set_child_text,
    _strip_tags,
)

# ---------------------------------------------------------------------------
# ROI tools
# ---------------------------------------------------------------------------

def _roi_style_error(color, fill_color, stroke, opacity) -> str | None:
    """Why a ROI's colours / stroke / opacity cannot be drawn, or None (an
    opacity of 2 was stored; a bad colour raised a raw ValueError)."""
    try:
        _color_to_int(color)
        if fill_color is not None:
            _color_to_int(fill_color)
    except ValueError as e:
        return str(e)
    if not (isinstance(stroke, (int, float)) and math.isfinite(stroke) and stroke > 0):
        return f"stroke must be a positive width in pixels (got {stroke!r})."
    if not (isinstance(opacity, (int, float)) and 0 <= opacity <= 1):
        return f"opacity must be between 0 and 1 (got {opacity!r})."
    return None


@mcp.tool()
def add_roi_rect(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    x: float,
    y: float,
    width: float,
    height: float,
    color: str | int = "yellow",
    fill_color: str | int | None = None,
    stroke: float = 2.0,
    opacity: float = 1.0,
) -> str:
    """Overlay a rectangular ROI (highlight box) on an image.

    Coordinates are in *image pixels* relative to the top-left of the raw
    image (before any crop or rotation applied in PyFigures).

    *x*, *y*: top-left corner of the rectangle.
    *width*, *height*: size in pixels.
    *color*: outline colour — name (yellow, red, …), #rrggbb hex, or integer.
    *fill_color*: fill colour (``null`` = transparent / no fill).
    *stroke*: outline width in pixels.
    *opacity*: 0.0 (transparent) – 1.0 (opaque).

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Examples::

        # Yellow box around a feature
        add_roi_rect("fig.pyf", [0], 0, x=120, y=80, width=200, height=150)

        # Semi-transparent red filled rectangle
        add_roi_rect("fig.pyf", [0], 1, x=50, y=50, width=100, height=60,
                     color="red", fill_color="red", opacity=0.3)
    """
    if not (width > 0 and height > 0):
        return f"ERROR: width and height must be positive (got {width} × {height})."
    bad = _roi_style_error(color, fill_color, stroke, opacity)
    if bad:
        return f"ERROR: {bad}"
    tree, root = _load(pyf_path)
    img, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    c = _color_to_int(color)
    fc = _color_to_int(fill_color) if fill_color is not None else None
    outside = _roi_outside_error(img, [x, x + width], [y, y + height])
    if outside:
        return f"ERROR: {outside}"
    annots.append(_new_roi_rect(x, y, width, height, c, fc, stroke, opacity))
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return (
        f"Rectangle2D ROI added to image {image_index} in {loc}: "
        f"({x},{y}) {width}×{height} px, color={color}, stroke={stroke}."
    )


@mcp.tool()
def add_roi_ellipse(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    x: float,
    y: float,
    width: float,
    height: float,
    color: str | int = "yellow",
    fill_color: str | int | None = None,
    stroke: float = 2.0,
    opacity: float = 1.0,
) -> str:
    """Overlay an elliptical (or circular) ROI on an image.

    Coordinates are in *image pixels* relative to the top-left of the raw image.

    *x*, *y*: top-left of the bounding box.
    *width*, *height*: bounding-box size. Pass equal values for a circle.
    *color*: outline colour — name, #rrggbb, or integer.
    *fill_color*: fill colour (``null`` = transparent).
    *stroke*: outline width in pixels.
    *opacity*: 0.0 – 1.0.

    Examples::

        # Circle around a cell nucleus
        add_roi_ellipse("fig.pyf", [0], 0, x=200, y=180, width=90, height=90,
                        color="cyan", stroke=3)

        # Filled semi-transparent ellipse
        add_roi_ellipse("fig.pyf", [0], 0, x=50, y=50, width=120, height=80,
                        color="magenta", fill_color="magenta", opacity=0.25)
    """
    if not (width > 0 and height > 0):
        return f"ERROR: width and height must be positive (got {width} × {height})."
    bad = _roi_style_error(color, fill_color, stroke, opacity)
    if bad:
        return f"ERROR: {bad}"
    tree, root = _load(pyf_path)
    img, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    c = _color_to_int(color)
    fc = _color_to_int(fill_color) if fill_color is not None else None
    outside = _roi_outside_error(img, [x, x + width], [y, y + height])
    if outside:
        return f"ERROR: {outside}"
    annots.append(_new_roi_ellipse(x, y, width, height, c, fc, stroke, opacity))
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return (
        f"Ellipse2D ROI added to image {image_index} in {loc}: "
        f"bbox ({x},{y}) {width}×{height} px, color={color}, stroke={stroke}."
    )


@mcp.tool()
def add_roi_line(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str | int = "yellow",
    stroke: float = 2.0,
    opacity: float = 1.0,
    arrow: bool = False,
    arrow_at_both_ends: bool = False,
) -> str:
    """Overlay a straight line (or arrow) on an image.

    Coordinates are in *image pixels* relative to the top-left of the raw image.

    *x1*, *y1*: start point.
    *x2*, *y2*: end point.
    *color*: colour — name, #rrggbb, or integer.
    *stroke*: line width in pixels.
    *arrow*: if ``true``, draw an arrowhead at (*x2*, *y2*).
    *arrow_at_both_ends*: if ``true``, arrowheads at both ends.

    Examples::

        # Simple measurement line
        add_roi_line("fig.pyf", [0], 0, x1=100, y1=200, x2=300, y2=200,
                     color="white", stroke=1.5)

        # Arrow pointing to a feature
        add_roi_line("fig.pyf", [0], 0, x1=50, y1=50, x2=150, y2=150,
                     color="yellow", stroke=2.5, arrow=True)
    """
    if (x1, y1) == (x2, y2):
        return f"ERROR: the line has no length: both ends are at ({x1}, {y1})."
    bad = _roi_style_error(color, None, stroke, opacity)
    if bad:
        return f"ERROR: {bad}"
    tree, root = _load(pyf_path)
    img, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    c = _color_to_int(color)
    outside = _roi_outside_error(img, [x1, x2], [y1, y2])
    if outside:
        return f"ERROR: {outside}"
    annots.append(_new_roi_line(x1, y1, x2, y2, c, stroke, opacity, arrow, arrow_at_both_ends))
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    suffix = " (arrow)" if arrow else ""
    return (
        f"Line2D ROI{suffix} added to image {image_index} in {loc}: "
        f"({x1},{y1})→({x2},{y2}), color={color}, stroke={stroke}."
    )


_ARROW_DIRECTIONS = {
    # where the arrow comes FROM, as a unit vector tip -> tail (image y points down)
    "n": (0.0, -1.0), "s": (0.0, 1.0), "e": (1.0, 0.0), "w": (-1.0, 0.0),
    "ne": (0.7071067811865476, -0.7071067811865476),
    "nw": (-0.7071067811865476, -0.7071067811865476),
    "se": (0.7071067811865476, 0.7071067811865476),
    "sw": (-0.7071067811865476, 0.7071067811865476),
}
_ARROW_DIRECTION_ALIASES = {
    "top": "n", "bottom": "s", "right": "e", "left": "w",
    "top right": "ne", "top left": "nw", "bottom right": "se", "bottom left": "sw",
    "above": "n", "below": "s", "up": "n", "down": "s",
}
# (half-width, length) as multiples of the stroke. With the default 1 pt stroke a
# "normal" head is 8 pt (2.8 mm) long and 6 pt wide on the printed page.
_ARROW_HEADS = {"small": (2.5, 6.0), "normal": (3.0, 8.0), "large": (4.0, 11.0)}


def _panel_raw_size(img: ET.Element) -> tuple[float, float] | None:
    """Source-pixel (width, height) of a panel: file header, else stored size."""
    from .core import _raw_size_from_file
    wh = _raw_size_from_file(_first_filename(img))
    if wh:
        return float(wh[0]), float(wh[1])
    try:
        w, h = float(_child_text(img, "width")), float(_child_text(img, "height"))
    except (TypeError, ValueError):
        return None
    return (w, h) if w > 0 and h > 0 else None


def _arrow_tail(tip_x, tip_y, from_direction, length, size):
    """Tail point for an arrow whose point is (tip_x, tip_y), coming from
    *from_direction* (compass 'nw' / 'top left' / an angle in degrees, 0 = from
    the right, counter-clockwise), shortened if needed so the tail stays inside
    the image. Returns (tail_x, tail_y, used_length) or raises ValueError."""
    if isinstance(from_direction, (int, float)) and not isinstance(from_direction, bool):
        a = math.radians(float(from_direction))
        ux, uy = math.cos(a), -math.sin(a)
    else:
        key = str(from_direction).strip().lower().replace("-", " ").replace("_", " ")
        key = _ARROW_DIRECTION_ALIASES.get(key, key.replace(" ", ""))
        try:
            key_num = float(key)
        except ValueError:
            key_num = None
        if key_num is not None:
            return _arrow_tail(tip_x, tip_y, key_num, length, size)
        if key not in _ARROW_DIRECTIONS:
            raise ValueError(f"unknown direction {from_direction!r}; use n, ne, e, se, s, "
                             "sw, w, nw ('top left'…) or an angle in degrees")
        ux, uy = _ARROW_DIRECTIONS[key]
    if size is not None:
        w, h = size
        # longest length along (ux, uy) that keeps the tail inside [0,w]x[0,h]
        lim = []
        if ux > 1e-9:
            lim.append((w - tip_x) / ux)
        elif ux < -1e-9:
            lim.append(tip_x / -ux)
        if uy > 1e-9:
            lim.append((h - tip_y) / uy)
        elif uy < -1e-9:
            lim.append(tip_y / -uy)
        room = max(0.0, min(lim)) if lim else length
        length = min(length, room)
    if length < 4:
        raise ValueError("no room for the arrow on that side of the tip — "
                         "choose another direction")
    return tip_x + ux * length, tip_y + uy * length, length


@mcp.tool()
def add_arrow(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    tip_x: float,
    tip_y: float,
    from_direction: str | float = "top left",
    length: float | None = None,
    color: str | int = "white",
    stroke: float = 1.0,
    head: str = "normal",
    both_ends: bool = False,
    label: str | None = None,
    style: str = "arrow",
) -> str:
    """Point an arrow AT a feature: give where the tip must be, not the line.

    *style*: "arrow" (a line with a head, default) or "arrowhead" — the head
    alone, larger, as often seen in papers (no line; *length* and *both_ends*
    do not apply). get_annotations reports kind "arrow" / "arrowhead".

    The arrowhead's point is exactly (*tip_x*, *tip_y*) in image pixels
    (top-left of the raw image = 0,0) and stays on that pixel whatever the
    panel size, zoom or export resolution — the head keeps a constant size on
    the page and grows backwards from its point.

    *from_direction*: side the arrow comes from — "n", "ne", "e", "se", "s",
      "sw", "w", "nw", or "top left" / "bottom right" / "left"…, or an angle in
      degrees (0 = from the right, 90 = from above).
    *length*: shaft length in image pixels (default 20 % of the image's shorter
      side); shortened automatically so the tail stays inside the image.
    *stroke*: line width in points on the page (default 1 pt).
    *head*: "small", "normal" or "large" — a normal head is 8× the stroke long
      (8 pt ≈ 2.8 mm at 1 pt), whatever the panel size; the message warns when
      the panel is currently so small that the arrow would be mostly head.
    *both_ends*: arrowheads at both ends.
    *label*: optional text placed just beyond the tail (e.g. "nucleus").

    Example — arrow pointing at a cell at (412, 230), coming from its upper right::

        add_arrow("fig.pyf", [0], 1, tip_x=412, tip_y=230, from_direction="ne")
    """
    if head not in _ARROW_HEADS:
        return f"ERROR: head must be one of {sorted(_ARROW_HEADS)}."
    style = str(style).strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if style in ("head", "headonly", "arrowheadonly"):
        style = "arrowhead"
    if style not in ("arrow", "arrowhead"):
        return "ERROR: style must be 'arrow' (a line with a head) or 'arrowhead' (the head alone)."
    if style == "arrowhead":
        return _add_arrowhead(pyf_path, group_path, image_index, tip_x, tip_y, from_direction,
                              color, stroke, head, label)
    tree, root = _load(pyf_path)
    img, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    size = _panel_raw_size(img)
    if size is not None and not (0 <= tip_x <= size[0] and 0 <= tip_y <= size[1]):
        return (f"ERROR: tip ({tip_x}, {tip_y}) is outside the image "
                f"({size[0]:.0f} x {size[1]:.0f} px).")
    if length is None:
        length = 0.20 * min(size) if size else 60.0
    try:
        tx, ty, used = _arrow_tail(float(tip_x), float(tip_y), from_direction,
                                   float(length), size)
        c = _color_to_int(color)
    except ValueError as e:
        return f"ERROR: {e}"
    hw, hl = _ARROW_HEADS[head]
    annots.append(_new_roi_line(tx, ty, tip_x, tip_y, c, stroke, 1.0, True,
                                bool(both_ends), hw, hl))
    if label:
        hexcol = f"#{c & 0xFFFFFF:06x}"
        ux, uy = (tx - tip_x) / used, (ty - tip_y) / used
        gap = 0.04 * (min(size) if size else 100.0)
        annots.append(_new_free_text(
            f'<font color={hexcol}>{_escape_if_plain(label)}</font>',
            tx + ux * gap, ty + uy * gap))
    _save(tree, pyf_path)
    note = "" if abs(used - length) < 0.5 else f" (shortened to {used:.0f} px to stay inside the image)"
    # head size is fixed on the page, the shaft scales with the panel: check
    # the proportions at the panel's current size (scale = image px per page pt)
    try:
        sc = float(_child_text(img, "scale"))
    except (TypeError, ValueError):
        sc = 0.0
    if sc > 0:
        on_page = used / sc                       # arrow length in pt
        head_pt = stroke * hl
        if on_page < 1.8 * head_pt:
            note += (f". NOTE: at the panel's current size the arrow is {on_page:.0f} pt "
                     f"long with a {head_pt:.0f} pt head — mostly head; use a longer "
                     f"length, head='small' or a thinner stroke")
    return (f"Arrow added to image {image_index} in "
            f"{'canvas' if not group_path else f'group {group_path}'}: tip at "
            f"({tip_x:g}, {tip_y:g}), tail at ({tx:.0f}, {ty:.0f}){note}.")


def _add_arrowhead(pyf_path, group_path, image_index, tip_x, tip_y, from_direction,
                   color, stroke, head, label):
    """add_arrow(style='arrowhead'): the head alone, its point on (tip_x, tip_y)."""
    from ..arrowheads import ARROWHEAD_SIZES, HEAD_ONLY_LENGTH
    tree, root = _load(pyf_path)
    img, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    size = _panel_raw_size(img)
    if size is not None and not (0 <= tip_x <= size[0] and 0 <= tip_y <= size[1]):
        return (f"ERROR: tip ({tip_x}, {tip_y}) is outside the image "
                f"({size[0]:.0f} x {size[1]:.0f} px).")
    try:
        # the direction only: a line much shorter than the head never shows
        dx, dy, n = _arrow_tail(float(tip_x), float(tip_y), from_direction, 10.0, None)
        used = HEAD_ONLY_LENGTH
        tx = tip_x + (dx - tip_x) / n * used
        ty = tip_y + (dy - tip_y) / n * used
        c = _color_to_int(color)
    except ValueError as e:
        return f"ERROR: {e}"
    hw, hl = ARROWHEAD_SIZES[head]
    annots.append(_new_roi_line(tx, ty, tip_x, tip_y, c, stroke, 1.0, True, False, hw, hl))
    if label:
        hexcol = f"#{c & 0xFFFFFF:06x}"
        ux, uy = (tx - tip_x) / used, (ty - tip_y) / used
        gap = 0.08 * (min(size) if size else 100.0)        # beyond the head
        annots.append(_new_free_text(
            f'<font color={hexcol}>{_escape_if_plain(label)}</font>',
            tip_x + ux * gap, tip_y + uy * gap))
    _save(tree, pyf_path)
    return (f"Arrowhead added to image {image_index} in "
            f"{'canvas' if not group_path else f'group {group_path}'}: point at "
            f"({tip_x:g}, {tip_y:g}), coming from {from_direction}.")


def _append_bracket_shapes(annots, x1, x2, y, label, tick, color, stroke,
                           font_pt, label_gap, whiskers_point):
    """Append the 3 lines + centred free-text label of a significance bracket to
    *annots* (in panel pixels). Returns (x_lo, x_hi). Shared by the manual
    add_significance_bracket and the data-driven add_significance_bracket_from_data."""
    c = _color_to_int(color)
    hexcol = f"#{c & 0xFFFFFF:06x}"
    x_lo, x_hi = (x1, x2) if x1 <= x2 else (x2, x1)

    # horizontal bar
    annots.append(_new_roi_line(x_lo, y, x_hi, y, c, stroke, 1.0, False, False))
    # end whiskers (toward the compared groups)
    if tick:
        dy = tick if whiskers_point == "down" else -tick
        annots.append(_new_roi_line(x_lo, y, x_lo, y + dy, c, stroke, 1.0, False, False))
        annots.append(_new_roi_line(x_hi, y, x_hi, y + dy, c, stroke, 1.0, False, False))

    if label:
        # centred label (above the bar when whiskers point down, else below)
        html = (f'<span style="font-size:{font_pt:g}pt; color:{hexcol};">'
                f'{_escape_if_plain(label)}</span>')
        # approximate centring: mean glyph advance ~0.5*font_pt
        half_w = 0.25 * font_pt * max(1, len(_strip_tags(label)))
        lx = (x_lo + x_hi) / 2.0 - half_w
        if whiskers_point == "down":
            ly = y - label_gap - font_pt * 1.1
        else:
            ly = y + label_gap
        annots.append(_new_free_text(html, lx, ly))
    return x_lo, x_hi


def _bracket_style_error(color, stroke, font_pt, tick, label_gap) -> str | None:
    """Why a bracket's style values cannot be drawn, or None (font_pt=0 was
    stored as an invisible label)."""
    try:
        _color_to_int(color)
    except ValueError as e:
        return str(e)
    for name, v, lo in (("stroke", stroke, 0.0), ("font_pt", font_pt, 0.0)):
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v > lo):
            return f"{name} must be a positive number (got {v})."
    for name, v in (("tick", tick), ("label_gap", label_gap)):
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
            return f"{name} must be 0 or more pixels (got {v})."
    return None


@mcp.tool()
def add_significance_bracket(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    x1: float,
    x2: float,
    y: float,
    label: str = "*",
    tick: float = 8.0,
    color: str | int = "black",
    stroke: float = 1.5,
    font_pt: float = 14.0,
    label_gap: float = 2.0,
    whiskers_point: str = "down",
) -> str:
    """Add a statistical-significance bracket (a horizontal bar with end whiskers
    and a centred label like ``*`` / ``**`` / ``n.s.`` / ``p<0.001``) over a
    panel — the staple annotation of bar/box plots comparing two conditions.

    Composed of three lines plus a free-positioned text label, all in *image
    pixels* relative to the panel's top-left. The two compared items sit under
    *x1* and *x2*; the bar spans them at height *y*.

    *x1*, *x2*: x of the two ends of the bracket (the compared groups).
    *y*: y of the horizontal bar.
    *label*: text above the bar (plain or Qt HTML). Use "*"/"**"/"***" or "n.s.".
    *tick*: whisker length in px (0 = no whiskers, a plain bar).
    *color*: line + default text colour — name, #rrggbb or integer.
    *stroke*: line width in px.
    *font_pt*: label font size in points.
    *label_gap*: gap in px between the bar and the label.
    *whiskers_point*: "down" (bar above the groups, ticks toward them — usual) or
    "up".

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Example — three-star bracket spanning two bars of a plot panel::

        add_significance_bracket("fig.pyf", [0], 0, x1=60, y=40, x2=180,
                                 label="***")
    """
    if whiskers_point not in ("down", "up"):
        return "ERROR: whiskers_point must be 'down' or 'up'."
    bad = _bracket_style_error(color, stroke, font_pt, tick, label_gap)
    if bad:
        return f"ERROR: {bad}"
    if x1 == x2:
        return f"ERROR: the bracket has no width: x1 and x2 are both {x1}; give the two group positions."
    tree, root = _load(pyf_path)
    _, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    x_lo, x_hi = _append_bracket_shapes(annots, x1, x2, y, label, tick, color,
                                        stroke, font_pt, label_gap, whiskers_point)

    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return (
        f"Significance bracket '{_strip_tags(label)}' added to image {image_index} "
        f"in {loc}: span x=[{x_lo:g},{x_hi:g}] at y={y:g}, tick={tick:g}, "
        f"color={color}. Note: label centring is approximate — nudge it in the GUI "
        f"if needed."
    )


@mcp.tool()
def add_significance_bracket_from_data(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    x1: float,
    x2: float,
    y: float,
    values_a: list[float],
    values_b: list[float],
    group_a: str = "A",
    group_b: str = "B",
    test: str = "auto",
    tick: float = 8.0,
    color: str | int = "black",
    stroke: float = 1.5,
    font_pt: float = 14.0,
    label_gap: float = 2.0,
    whiskers_point: str = "down",
) -> str:
    """Like add_significance_bracket, but the label is **computed from the raw
    data**: it runs the appropriate two-group test on *values_a* vs *values_b*
    and draws the bracket with the correct significance stars (or "n.s."),
    recording the exact test + p-value in the figure's statistics sidecar so it
    flows into the Methods section (see export_adjustment_ledger).

    Needs the ``staplot`` package (soft dependency). If it isn't installed, use
    add_significance_bracket with a manual label instead.

    *values_a*, *values_b*: the raw measurements of the two compared groups.
    *group_a*, *group_b*: names used in the recorded provenance.
    *test*: "auto" (Welch t if both groups look normal, else Mann-Whitney),
    "ttest"/"welch", "mannwhitney"/"mwu", or "wilcoxon" (paired, equal n).
    *x1*, *x2*, *y*, *tick*, *color*, *stroke*, *font_pt*, *label_gap*,
    *whiskers_point*: geometry/style, identical to add_significance_bracket.

    Example::

        add_significance_bracket_from_data(
            "fig.pyf", [0], 0, x1=60, x2=180, y=40,
            values_a=[1.1, 0.9, 1.0, 1.2], values_b=[2.0, 2.3, 1.9, 2.1],
            group_a="WT", group_b="KO")
    """
    if whiskers_point not in ("down", "up"):
        return "ERROR: whiskers_point must be 'down' or 'up'."
    if len(values_a) < 2 or len(values_b) < 2:
        return "ERROR: each group needs at least 2 values."
    bad = _bracket_style_error(color, stroke, font_pt, tick, label_gap)
    if bad:
        return f"ERROR: {bad}"
    try:
        finite = all(math.isfinite(float(v)) for v in list(values_a) + list(values_b))
    except (TypeError, ValueError):
        finite = False
    if not finite:
        # NaN used to be dropped without a word, testing other n than given
        return "ERROR: values_a and values_b must be finite numbers (no NaN, inf or text)."
    try:
        from staplot import api as _api
        from staplot.stats.tests import run_ttest, run_mann_whitney, run_wilcoxon
        from staplot.stats.descriptive import significance_stars
    except Exception:
        return ("ERROR: computing significance from data needs the 'staplot' "
                "package (pip install staplot). Use add_significance_bracket to "
                "place a bracket with a manual label instead.")

    tbl = _api.table_from_columns({group_a: list(values_a), group_b: list(values_b)})
    t = test.lower()
    try:
        if t == "auto":
            rec = _api.auto_test(tbl, only_significant=False)
            comp = rec["comparisons"][0]
            p, test_name = comp["p"], rec["test"]
        elif t in ("ttest", "welch", "t"):
            r = run_ttest(tbl, group_a, group_b)
            p, test_name = float(r.details["p"]), "Welch's t-test"
        elif t in ("mannwhitney", "mwu", "mann-whitney"):
            r = run_mann_whitney(tbl, group_a, group_b)
            p, test_name = float(r.details["p"]), "Mann-Whitney U test"
        elif t in ("wilcoxon", "paired"):
            r = run_wilcoxon(tbl, group_a, group_b)
            p, test_name = float(r.details["p"]), "Wilcoxon signed-rank test"
        else:
            return f"ERROR: unknown test {test!r}."
    except Exception as e:
        return f"ERROR: statistics failed: {type(e).__name__}: {e}"

    if not math.isfinite(p):
        # e.g. two constant groups: an 'n/a' bracket with p=nan was drawn
        return (f"ERROR: {test_name} gives no p-value for these values (constant or "
                f"identical groups?); no bracket added.")
    stars = significance_stars(p)
    label = "n.s." if stars == "ns" else stars

    tree, root = _load(pyf_path)
    _, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    x_lo, x_hi = _append_bracket_shapes(annots, x1, x2, y, label, tick, color,
                                        stroke, font_pt, label_gap, whiskers_point)
    _save(tree, pyf_path)

    _append_stats_entry(pyf_path, {
        "source": "significance_bracket",
        "group_a": group_a, "group_b": group_b,
        "n_a": len(values_a), "n_b": len(values_b),
        "test": test_name, "p": p, "label": label,
    })
    loc = "canvas" if not group_path else f"group {group_path}"
    return (
        f"Significance bracket '{label}' ({test_name}, p={p:.4g}) added to image "
        f"{image_index} in {loc}: span x=[{x_lo:g},{x_hi:g}] at y={y:g}. Recorded "
        f"in the statistics sidecar for the Methods section."
    )


@mcp.tool()
def add_roi_polygon(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    points: list,
    color: str | int = "yellow",
    fill_color: str | int | None = None,
    stroke: float = 2.0,
    opacity: float = 1.0,
    style: str = "polygon",
) -> str:
    """Overlay a polygon, open polyline, or freehand shape on an image.

    Coordinates are in *image pixels* relative to the top-left of the raw image.

    *points*: vertex list — either a flat alternating list ``[x0,y0,x1,y1,…]``
       or a list of ``[x,y]`` pairs: ``[[x0,y0],[x1,y1],…]``.
    *color*: outline colour — name, #rrggbb, or integer.
    *fill_color*: fill colour (``null`` = transparent).
    *stroke*: outline width in pixels.
    *style*:
        - ``"polygon"``  — closed filled/outlined polygon  (default)
        - ``"polyline"`` — open connected line segments (not closed)
        - ``"freehand"`` — same rendering as polygon but intended for
          irregular hand-drawn outlines

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Examples::

        # Closed polygon around a region of interest
        add_roi_polygon("fig.pyf", [0], 0,
                        points=[[50,100],[150,50],[250,100],[200,200],[100,200]])

        # Open polyline (measurement path)
        add_roi_polygon("fig.pyf", [0], 0,
                        points=[[10,10],[100,50],[200,30],[300,80]],
                        style="polyline", color="cyan")

        # Freehand outline, semi-transparent yellow fill
        add_roi_polygon("fig.pyf", [0], 0,
                        points=[[30,80],[60,20],[120,10],[180,60],[150,130],[80,140]],
                        style="freehand", fill_color="yellow", opacity=0.3)
    """
    style = style.lower().strip()
    _style_map = {"polygon": "Polygon2D", "polyline": "PolyLine2D", "freehand": "Freehand2D"}
    if style not in _style_map:
        return f"ERROR: style must be 'polygon', 'polyline', or 'freehand'. Got {style!r}."

    try:
        flat = _flatten_points(points)
    except (TypeError, ValueError, IndexError):
        return f"ERROR: points must be [[x, y], ...] or [x, y, x, y, ...] numbers (got {points!r})."
    if len(flat) % 2 or not all(math.isfinite(v) for v in flat):
        return "ERROR: points must be finite x, y pairs."
    # a closed shape of two points is a line drawn twice
    min_pts = 2 if style == "polyline" else 3
    if len(flat) < 2 * min_pts:
        return f"ERROR: a {style} needs at least {min_pts} points ({len(flat) // 2} given)."
    bad = _roi_style_error(color, fill_color, stroke, opacity)
    if bad:
        return f"ERROR: {bad}"

    tree, root = _load(pyf_path)
    img, annots, err = _get_annots_for_roi(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    c = _color_to_int(color)
    fc = _color_to_int(fill_color) if fill_color is not None else None
    outside = _roi_outside_error(img, flat[0::2], flat[1::2])
    if outside:
        return f"ERROR: {outside}"
    annots.append(_new_roi_polygon(flat, _style_map[style], c, fc, stroke, opacity))
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    n_pts = len(flat) // 2
    return (
        f"{_style_map[style]} ROI added to image {image_index} in {loc}: "
        f"{n_pts} points, color={color}, stroke={stroke}."
    )


_LINE_STYLES = {"solid": "None", "dashed": "[4, 4]", "dotted": "[1, 3]", "dash-dot": "[6, 3, 1, 3]"}
_ROI_TAGS = ("Rectangle2D", "Ellipse2D", "Line2D", "Polygon2D", "PolyLine2D", "Freehand2D")


@mcp.tool()
def set_roi_properties(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    annotation_index: int,
    color: str | int | None = None,
    fill_color: str | int | None = None,
    stroke: float | None = None,
    opacity: float | None = None,
    line_style: str | None = None,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
    x1: float | None = None,
    y1: float | None = None,
    x2: float | None = None,
    y2: float | None = None,
    points: list | None = None,
    move_by: list[float] | None = None,
    arrow: bool | None = None,
    arrow_at_both_ends: bool | None = None,
) -> str:
    """Change an EXISTING ROI (rectangle, ellipse, line/arrow, polygon,
    polyline, freehand) — what its properties in the Edit Image dialog do.
    Only what you pass changes; geometry, colours and the rest stay as they are.

    Find the ROI with get_annotations: *annotation_index* is its index there
    (0-based among all the image's annotations). Several ROIs fit the user's
    words ("the box" with two rectangles)? Ask which one — do not edit the first.

    Style (any ROI): *color* outline; *fill_color* fill, "none" removes it;
    *stroke* outline width (px); *opacity* 0–1; *line_style* solid, dashed,
    dotted or dash-dot.
    Geometry, in RAW image pixels (top-left of the uncropped image, the same
    coordinates get_annotations reports — never canvas/screen positions):
      rectangle / ellipse: *x*, *y* (top-left), *width*, *height*
      line / arrow: *x1*, *y1*, *x2*, *y2* (an arrow points at x2, y2);
                    *arrow* / *arrow_at_both_ends* turn the heads on or off
      polygon / polyline / freehand: *points* [[x, y], …] (replaces them all)
      any ROI: *move_by* [dx, dy] shifts it without changing its size.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    annots = imgs[image_index].find("annotations")
    children = list(annots) if annots is not None else []
    if not 0 <= annotation_index < len(children):
        return (f"ERROR: annotation_index {annotation_index} out of range "
                f"({len(children)} annotations; see get_annotations).")
    el = children[annotation_index]
    tag = el.tag
    if tag not in _ROI_TAGS:
        hint = {"TAText2D": "a text — use style_annotation / set_annotation_text",
                "ScaleBar": "the scale bar — use set_scale_bar",
                "Image2D": "an inset — use set_inset_property"}.get(tag, tag)
        return f"ERROR: annotation {annotation_index} is {hint}, not a ROI."

    box = ("x", "y", "width", "height")
    ends = ("x1", "y1", "x2", "y2")
    given = {k: v for k, v in dict(x=x, y=y, width=width, height=height, x1=x1, y1=y1,
                                   x2=x2, y2=y2).items() if v is not None}
    kind = ("box" if tag in ("Rectangle2D", "Ellipse2D") else
            "line" if tag == "Line2D" else "points")
    wrong = [k for k in given if (k in box) != (kind == "box") or (k in ends) != (kind == "line")]
    if wrong or (points is not None and kind != "points"):
        return (f"ERROR: a {tag} has no {', '.join(wrong) or 'points'}: rectangles/ellipses take "
                "x, y, width, height; lines x1, y1, x2, y2; polygons points.")
    if (arrow is not None or arrow_at_both_ends is not None) and tag != "Line2D":
        return f"ERROR: only a line has arrowheads (this is a {tag})."
    if line_style is not None and line_style not in _LINE_STYLES:
        return f"ERROR: line_style must be one of {', '.join(_LINE_STYLES)}."
    if opacity is not None and not 0 <= opacity <= 1:
        return "ERROR: opacity must be between 0 and 1."
    if stroke is not None and stroke <= 0:
        return "ERROR: stroke must be positive."
    if (width is not None and width <= 0) or (height is not None and height <= 0):
        return "ERROR: width and height must be positive."
    if move_by is not None and len(move_by) != 2:
        return "ERROR: move_by is [dx, dy]."

    changed = []

    def put(name, text):
        if el.find(name) is None:
            ET.SubElement(el, name)
        _set_child_text(el, name, text)
        changed.append(name)

    if color is not None:
        put("color", str(_color_to_int(color)))
    if fill_color is not None:
        none = str(fill_color).strip().lower() in ("none", "null", "transparent", "")
        put("fill_color", "None" if none else str(_color_to_int(fill_color)))
    if stroke is not None:
        put("stroke", str(float(stroke)))
    if opacity is not None:
        put("opacity", str(float(opacity)))
    if line_style is not None:
        put("line_style", _LINE_STYLES[line_style])
    for k, v in given.items():
        put(k, str(float(v)))
    if points is not None:
        flat = _flatten_points(points)
        if len(flat) < 4:
            return "ERROR: need at least 2 points."
        put("coords_as_list", str(flat))
    if arrow is not None:
        put("arrow", str(bool(arrow)))
    if arrow_at_both_ends is not None:
        put("arrow_at_both_ends", str(bool(arrow_at_both_ends)))
    if move_by is not None:
        dx, dy = float(move_by[0]), float(move_by[1])
        if kind == "points":
            import ast as _ast
            flat = [float(v) for v in _ast.literal_eval(_child_text(el, "coords_as_list") or "[]")]
            put("coords_as_list", str([v + (dx if i % 2 == 0 else dy) for i, v in enumerate(flat)]))
        else:
            for k, d in ((("x", dx), ("y", dy)) if kind == "box" else
                         (("x1", dx), ("y1", dy), ("x2", dx), ("y2", dy))):
                put(k, str(float(_child_text(el, k) or 0) + d))
    if not changed:
        return "ERROR: nothing to change — pass at least one property."
    _save(tree, pyf_path)
    from .core import _describe_roi
    return json.dumps({"edited": {"group_path": group_path, "image_index": image_index,
                                  "annotation_index": annotation_index, "type": tag},
                       "changed": sorted(set(changed)),
                       "now": _describe_roi(el, annotation_index)}, ensure_ascii=False, indent=2)


@mcp.tool()
def remove_group(pyf_path: str, group_path: list[int]) -> str:
    """Remove a group and ALL of its contents (images, sub-groups, annotations).

    *group_path*: [0] removes the first top-level group.  [0, 1] removes
    sub-group 1 inside top-level group 0.
    Use describe_figure() first — this operation is irreversible.
    """
    if not group_path:
        return "ERROR: group_path cannot be [] — specify at least one index."
    tree, root = _load(pyf_path)
    grp, err = _navigate_group(root, group_path)
    if err:
        return f"ERROR: {err}"
    # Find parent container
    if len(group_path) == 1:
        parent = root
    else:
        parent_grp, err = _navigate_group(root, group_path[:-1])
        if err:
            return f"ERROR finding parent: {err}"
        parent = parent_grp.find("content")
        if parent is None:
            return "ERROR: parent group has no <content>."
    parent.remove(grp)
    _save(tree, pyf_path, recompute=True)
    return f"Removed group at path {group_path} and all its contents."


@mcp.tool()
def clone_image(
    pyf_path: str,
    src_group_path: list[int],
    src_image_index: int,
    dst_group_path: list[int],
    dst_image_index: int = -1,
) -> str:
    """Deep-copy an image slot (including all annotations and settings) to another location.

    Unlike move_image, the original is kept.  Useful for duplicating a panel
    that has complex LUT / crop / annotation settings you want to reuse.

    *src_group_path* / *src_image_index*: source location.
    *dst_group_path*: destination (can be the same group to insert a duplicate).
    *dst_image_index*: position in destination (-1 = append at end).
    """
    import copy
    tree, root = _load(pyf_path)
    src_cont, err = _get_container(root, src_group_path)
    if err:
        return f"ERROR (source): {err}"
    src_imgs = [c for c in src_cont if c.tag == "Image2D"]
    if not 0 <= src_image_index < len(src_imgs):
        return f"ERROR: src_image_index {src_image_index} out of range ({len(src_imgs)} images)."

    clone = copy.deepcopy(src_imgs[src_image_index])

    dst_cont, err = _get_container(root, dst_group_path)
    if err:
        return f"ERROR (destination): {err}"

    if dst_image_index < 0:
        _append_image(dst_cont, clone, is_root=(not dst_group_path))
    else:
        dst_cont.insert(dst_image_index, clone)

    _save(tree, pyf_path, recompute=True)
    src_loc = "canvas" if not src_group_path else str(src_group_path)
    dst_loc = "canvas" if not dst_group_path else str(dst_group_path)
    fn = _child_text(src_imgs[src_image_index], "filename") or "<no file>"
    return f"Cloned {Path(fn).name} from {src_loc}[{src_image_index}] to {dst_loc}."


def _swap_prefix(path: str, old_prefix: str, new_prefix: str) -> str | None:
    """*path* with *old_prefix* replaced by *new_prefix*, or None when it does
    not start with it. '\\' and '/' count as the same separator (figures store
    '/', Windows users type '\\'), and the prefix must end at a folder
    boundary, so 'C:/data' never matches 'C:/data2/x.tif'."""
    norm_p = path.replace("\\", "/")
    norm_old = old_prefix.replace("\\", "/").rstrip("/")
    if not norm_old or not norm_p.startswith(norm_old):
        return None
    rest = norm_p[len(norm_old):]
    if rest and not rest.startswith("/"):
        return None
    return new_prefix.rstrip("/\\") + rest if new_prefix else rest.lstrip("/")


def _remap_script_paths(script: str, old_prefix: str, new_prefix: str) -> tuple[str, int]:
    """Rewrite string literals in a panel script that start with *old_prefix*.

    Only whole string-literal tokens are touched (found with ``tokenize``), so
    code and comments are never altered. Returns (new_script, n_replaced)."""
    import ast
    import io as _io
    import tokenize
    try:
        toks = list(tokenize.generate_tokens(_io.StringIO(script).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return script, 0
    lines = script.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))
    edits = []
    for t in toks:
        if t.type != tokenize.STRING:
            continue
        try:
            val = ast.literal_eval(t.string)
        except Exception:
            continue
        new_val = _swap_prefix(val, old_prefix, new_prefix) if isinstance(val, str) else None
        if new_val is not None:
            a = offsets[t.start[0] - 1] + t.start[1]
            b = offsets[t.end[0] - 1] + t.end[1]
            edits.append((a, b, repr(new_val)))
    for a, b, rep in reversed(edits):
        script = script[:a] + rep + script[b:]
    return script, len(edits)


@mcp.tool()
def remap_paths(
    pyf_path: str,
    old_prefix: str,
    new_prefix: str,
    dry_run: bool = False,
) -> str:
    """Replace a path prefix in every image filename in the figure.

    Essential when a figure was created on a different machine or OS, or when
    files have been moved to a new directory.

    Examples::

        # Linux → Windows migration
        remap_paths(f, "/home/alice/data", r"C:\\Users\\alice\\data")

        # Files moved to a new folder
        remap_paths(f, "/old/path/project", "/new/path/project")

    *old_prefix*: path string to find at the start of each filename.
    *new_prefix*: replacement string.
    *dry_run*: if True, report what would change without saving.

    Paths baked into scripted panels (channel merges, data plots) are remapped
    too, so those panels keep working after the move.

    Returns a summary of all changed (or would-be-changed) paths.
    """
    import ast
    if not old_prefix.replace("\\", "/").strip("/ "):
        return "ERROR: old_prefix is empty: give the folder the paths currently start with."
    # remap the paths exactly as stored (automatic relocation would pre-empt it)
    tree, root = _load(pyf_path, resolve=False)
    changed = []
    unchanged = []

    for img in root.iter("Image2D"):
        # paths baked into scripted panels (channel merge, data plots, ...)
        sc_el = img.find("custom_loading_script")
        if sc_el is not None and sc_el.text:
            script = _decode(sc_el.text)
            if isinstance(script, str) and script not in ("None", ""):
                new_script, n_sub = _remap_script_paths(script, old_prefix, new_prefix)
                if n_sub:
                    changed.append(f"  script: {n_sub} path literal(s) remapped")
                    if not dry_run:
                        sc_el.text = _encode_str(new_script)

        fn_el = img.find("filename")
        if fn_el is None or not fn_el.text:
            continue
        raw = fn_el.text.strip()
        # Decode the ""…"" encoding
        wrapped = raw.startswith('""') and raw.endswith('""')
        decoded = raw[2:-2] if wrapped else raw
        if decoded in ("None", "@template@", ""):
            continue
        # Handle list-of-paths (multi-series filenames)
        if decoded.startswith("[") and decoded.endswith("]"):
            try:
                paths = ast.literal_eval(decoded)  # never executes file content
                new_paths = []
                any_changed = False
                for p in paths:
                    new_p = _swap_prefix(p, old_prefix, new_prefix) if isinstance(p, str) else None
                    if new_p is not None:
                        new_paths.append(new_p)
                        any_changed = True
                    else:
                        new_paths.append(p)
                if any_changed:
                    changed.append(f"  {decoded[:60]}... -> list remapped")
                    if not dry_run:
                        # keep the ""…"" wrapper exactly as the file had it
                        fn_el.text = _encode_str(repr(new_paths)) if wrapped else repr(new_paths)
                else:
                    unchanged.append(decoded[:80])
            except Exception:
                unchanged.append(decoded[:80])
        elif _swap_prefix(decoded, old_prefix, new_prefix) is not None:
            new_path = _swap_prefix(decoded, old_prefix, new_prefix)
            changed.append(f"  {decoded} -> {new_path}")
            if not dry_run:
                fn_el.text = _encode_str(new_path)
        else:
            unchanged.append(decoded[:80])

    if not dry_run and changed:
        _save(tree, pyf_path)

    lines = []
    verb = "Would change" if dry_run else "Changed"
    lines.append(f"{verb} {len(changed)} path(s), {len(unchanged)} path(s) unchanged:")
    lines.extend(changed if changed else ["  (none)"])
    if dry_run:
        lines.append("(dry_run=True — nothing saved)")
    return "\n".join(lines)


@mcp.tool()
def find_moved_files(pyf_path: str, apply: bool = False) -> str:
    """Locate a moved figure's source files relative to the .pyf's location.

    When a figure and its data were copied to another folder, disk or OS, the
    stored absolute paths no longer exist. PyFigures looks the files up
    automatically when opening/editing (longest matching trailing path under the
    .pyf's folder and its parents, e.g. ``/home/me/Bureau/exp/a.tif`` ->
    ``C:/Users/me/Desktop/exp/a.tif``). This tool reports what that finds and
    what is still missing.

    *apply*: also write the found locations into the .pyf (otherwise read-only;
    the figure resolves them on the fly anyway). Use remap_paths for a manual
    prefix swap when files moved somewhere unrelated to the .pyf.

    Returns JSON: {"relocated": {old: new}, "still_missing": [...]}.
    """
    from ..path_resolution import resolve_moved_paths_in_tree
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    tree, root = _load(pyf_path, resolve=False)
    moved = resolve_moved_paths_in_tree(root, pyf_path)
    missing = []
    for img in root.iter("Image2D"):
        fn = _first_filename(img)
        if fn and not os.path.exists(fn):
            missing.append(fn)
    if apply and moved:
        _save(tree, pyf_path)
    return json.dumps({"relocated": moved, "still_missing": sorted(set(missing)),
                       "written": bool(apply and moved)}, ensure_ascii=False, indent=2)


@mcp.tool()
def batch_fill_templates(
    pyf_path: str,
    group_path: list[int],
    filenames: list[str],
) -> str:
    """Fill multiple template slots in one call, assigning files in index order.

    Finds every template slot (``@template@``) at *group_path* and fills them
    in ascending image-index order using the supplied *filenames* list.
    Slots that have a script are skipped (they generate their own content).

    *group_path*: [] for free-canvas, [0] for top-level group 0, etc.
    *filenames*: list of absolute file paths; must have at least as many entries
                 as there are non-script template slots at that location.

    Returns a summary of which slot received which file.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"

    imgs = [c for c in container if c.tag == "Image2D"]
    slots = [
        (ii, img)
        for ii, img in enumerate(imgs)
        if _is_template(img) and _child_text(img, "custom_loading_script") is None
    ]

    if not slots:
        return "No fillable template slots found at this location (slots with scripts are skipped)."
    if len(filenames) < len(slots):
        return (
            f"ERROR: {len(slots)} template slot(s) but only {len(filenames)} filename(s) provided."
        )

    from .core import _unreadable_image, _missing_image_note, _reset_luts_for_new_file
    # fill_template refuses a broken file; the batch filled slots with anything
    for fname in filenames[:len(slots)]:
        bad = _unreadable_image(fname)
        if bad:
            return f"ERROR: {bad} — no slot filled."
    lines = []
    for (ii, img), fname in zip(slots, filenames):
        _set_child_text(img, "filename", _encode_str(fname))
        lines.append(f"  slot {ii} <- {Path(fname).name}" + _reset_luts_for_new_file(img, fname))

    _save(tree, pyf_path, recompute=True)
    loc = "canvas" if not group_path else f"group {group_path}"
    extra = filenames[len(slots):]
    return (f"Filled {len(slots)} template slot(s) in {loc}:\n" + "\n".join(lines)
            + (f"\nNOTE: {len(extra)} more filename(s) than slots were not used: "
               + ", ".join(Path(f).name for f in extra[:10]) if extra else "")
            + "".join(_missing_image_note(f) for f in filenames[:len(slots)]))


@mcp.tool()
def get_figure_properties(pyf_path: str) -> str:
    """Return the figure-level settings: global font and default spacing.

    These settings live in the ``<SerializableQFont>`` and
    ``<SerializableGUIparameters>`` elements at the root of the .pyf file.
    They control the default label font, background/foreground colours, and
    the default spacing between groups.

    Use set_figure_properties() to change them.
    """
    _, root = _load(pyf_path)
    result = {}

    font_el = root.find("SerializableQFont")
    if font_el is not None:
        result["font"] = {
            child.tag: _decode(child.text)
            for child in font_el
        }

    gui_el = root.find("SerializableGUIparameters")
    if gui_el is not None:
        result["gui"] = {
            child.tag: _decode(child.text)
            for child in gui_el
        }

    if not result:
        return "No figure-level properties found (empty or non-standard file)."
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def set_figure_properties(
    pyf_path: str,
    font_family: str | None = None,
    font_size: int | None = None,
    font_italic: bool | None = None,
    background_color: int | None = None,
    foreground_color: int | None = None,
    default_spacing: int | None = None,
    page_background: str | int | None = None,
) -> str:
    """Set figure-level properties: global font, default spacing and the
    figure background.

    Only the parameters you supply are changed; all others are left as-is.

    *font_family*: font name, e.g. ``"Arial"``, ``"Helvetica"``, ``"Times New Roman"``.
    *font_size*: point size, e.g. 10, 12.
    *font_italic*: True / False.
    *background_color*: box behind the auto panel LETTERS (integer RGB colour,
      0xRRGGBB). For other labels use set_label_background.
    *foreground_color*: integer RGB colour of the letters (0 black, 16777215 white).
    *default_spacing*: pixels between top-level groups (also used by create_figure).
    *page_background*: colour of the whole figure behind the panels — i.e. of
      the gaps between them (name, #rrggbb or int; "none" = transparent, the
      default, which PNG/TIFF keep and JPG shows as white). Use "white" so the
      separators stay white in any viewer, or "black" for dark figures.

    Colour integers: white = 16777215, black = 0, red = 16711680, green = 65280,
    blue = 255.  Or compute: (R << 16) | (G << 8) | B.
    """
    # all of these were stored as given (font size 0 or -4, spacing -2, ...)
    if font_size is not None and not (math.isfinite(font_size) and font_size > 0):
        return f"ERROR: font_size must be a positive number of points (got {font_size})."
    if default_spacing is not None and not default_spacing >= 0:
        return f"ERROR: default_spacing must be 0 or more pixels (got {default_spacing})."
    for name, c in (("background_color", background_color), ("foreground_color", foreground_color)):
        if c is not None and not (isinstance(c, int) and 0 <= c <= 0xFFFFFF):
            return f"ERROR: {name} must be an RGB integer 0..16777215 (0xRRGGBB), got {c}."
    tree, root = _load(pyf_path)
    changed = []

    font_el = root.find("SerializableQFont")
    if font_el is None:
        font_el = ET.SubElement(root, "SerializableQFont")

    if font_family is not None:
        _set_child_text(font_el, "family", _encode_str(font_family))
        changed.append(f"font.family={font_family!r}")
        _warn_missing_font(font_family)
    if font_size is not None:
        _set_child_text(font_el, "size", str(int(font_size)))
        changed.append(f"font.size={font_size}")
    if font_italic is not None:
        _set_child_text(font_el, "italic", str(bool(font_italic)))
        changed.append(f"font.italic={font_italic}")
    if background_color is not None:
        _set_child_text(font_el, "background", str(int(background_color)))
        changed.append(f"font.background={background_color}")
    if foreground_color is not None:
        _set_child_text(font_el, "foreground", str(int(foreground_color)))
        changed.append(f"font.foreground={foreground_color}")

    gui_el = root.find("SerializableGUIparameters")
    if gui_el is None:
        gui_el = ET.SubElement(root, "SerializableGUIparameters")
    if default_spacing is not None:
        _set_child_text(gui_el, "space", str(int(default_spacing)))
        changed.append(f"gui.space={default_spacing}")
    if page_background is not None:
        try:
            value = _label_background_text(page_background)
        except ValueError as e:
            return f"ERROR: {e}"
        if gui_el.find("space") is None:
            _set_child_text(gui_el, "space", "3")
        _set_child_text(gui_el, "background", value)
        changed.append(f"page background={page_background}")

    if not changed:
        return "Nothing changed — supply at least one parameter to modify."
    # the panel letters already in the figure take the new font (it used to
    # be stored only, so a figure font never showed on MCP-built letters)
    n_letters, err = _restyle_letters(root, font_family=font_family, font_size=font_size,
                                      italic=font_italic)
    if err:
        _warn(f"the panel letters kept their font ({err}).")
    elif n_letters:
        changed.append(f"{n_letters} panel letter(s) restyled")
    _save(tree, pyf_path)
    return "Updated: " + ", ".join(changed) + "."


def _panel_letters_of(root: ET.Element) -> list:
    """The A, B, C… letters the panels carry (is_letter texts)."""
    out = []
    for img in _iter_panel_elements(root):
        annots = img.find("annotations")
        if annots is None:
            continue
        out += [ta for ta in annots.findall("TAText2D")
                if (ta.findtext("is_letter") or "") in ("True", "b'True'")]
    return out


def _strip_panel_letters(root: ET.Element) -> int:
    """Remove the A, B, C… letters the panels carry (is_letter texts)."""
    parent = {c: p for p in root.iter() for c in p}
    letters = _panel_letters_of(root)
    for ta in letters:
        parent[ta].remove(ta)
    return len(letters)


def _lettered_row_elements(root: ET.Element) -> list:
    """The top-level rows that get a row letter (label rows excluded), in order
    (as the canvas: row_letters.lettered_rows)."""
    return [el for el in root if el.tag in ("Group", "Image2D")
            and _decode(el.findtext("isText")) in (None, False, "", "False")]


def row_letters_of(root: ET.Element) -> list:
    """[(letter, row element)] of a figure lettered per row, [] otherwise."""
    from batoolset.strings.tools import increment_letter
    if letter_layout_of(root)["letter_layout"] != "row":
        return []
    gui_el = root.find("SerializableGUIparameters")
    if gui_el is not None and _decode(gui_el.findtext("auto_lettering")) is False:
        return []
    letter = (_decode(gui_el.findtext("first_letter")) if gui_el is not None else None) or "A"
    letter = str(letter)[:1]
    out = []
    for el in _lettered_row_elements(root):
        out.append((letter, el))
        letter = increment_letter(letter)
    return out


def letter_layout_of(root: ET.Element) -> dict:
    """{'letter_layout': 'panel'|'row', 'row_letter_align': 'top'|'center'}
    as saved in <SerializableGUIparameters> ('panel' when not saved)."""
    from pyfigures.gui.row_letters import normalise_layout, normalise_align
    gui_el = root.find("SerializableGUIparameters")
    layout = _decode(gui_el.findtext("letter_layout")) if gui_el is not None else None
    align = _decode(gui_el.findtext("row_letter_align")) if gui_el is not None else None
    return {"letter_layout": normalise_layout(layout), "row_letter_align": normalise_align(align)}


@mcp.tool()
def set_panel_letter_layout(
    pyf_path: str,
    letter_layout: str = "row",
    row_letter_align: str | None = None,
) -> str:
    """Letter the figure per ROW or per PANEL.

    *letter_layout*:
      - ``"row"``: ONE letter per row of the figure (A for the first row, B
        for the second…), drawn OUTSIDE the row in a margin on its left, as in
        many journal figures. The rows are narrowed by that margin so the
        figure keeps its width; the panels carry no letter. The letters follow
        the row order (swapping rows re-letters them) and use the figure's
        letter font, size and colour (set_figure_properties).
      - ``"panel"`` (default of every figure): a letter in a corner of each
        panel (the corner: letter_placement / set_figure_properties).
    *row_letter_align*: ``"top"`` (default: level with the top of the row and
      of its column titles) or ``"center"`` (the middle of the row).

    Saved in the figure (``<SerializableGUIparameters>``): the GUI, the
    headless renders and every export show it. Turns lettering on.
    """
    from pyfigures.gui.row_letters import layout_error, align_error, normalise_layout, normalise_align
    bad = layout_error(letter_layout) or (align_error(row_letter_align) if row_letter_align is not None else None)
    if bad:
        return f"ERROR: {bad}."
    layout = normalise_layout(letter_layout)
    tree, root = _load(pyf_path)
    gui_el = root.find("SerializableGUIparameters")
    if gui_el is None:
        gui_el = ET.SubElement(root, "SerializableGUIparameters")
    if gui_el.find("space") is None:
        _set_child_text(gui_el, "space", "3")
    before = letter_layout_of(root)
    align = normalise_align(row_letter_align) if row_letter_align is not None else before["row_letter_align"]
    _set_child_text(gui_el, "auto_lettering", "True")
    if layout == "row":
        if not _decode(gui_el.findtext("first_letter")):
            # the first letter (and its case) is read from the panels' letters
            # when a figure is opened: they are about to go, so it is saved
            firsts = [_strip_tags(_decode(ta.findtext("text")) or "").strip() for ta in _panel_letters_of(root)]
            firsts = [f for f in firsts if len(f) == 1 and f.isalpha()]
            _set_child_text(gui_el, "first_letter", _encode_str(min(firsts) if firsts else "A"))
        _set_child_text(gui_el, "letter_layout", _encode_str("row"))
        _set_child_text(gui_el, "row_letter_align", _encode_str(align))
        removed = _strip_panel_letters(root)
        _save(tree, pyf_path)
        n_rows = len(_lettered_row_elements(root))
        return (f"Letters: one per row, outside the rows on the left, aligned to the "
                f"{'middle' if align == 'center' else 'top'} of each row"
                + (f" ({n_rows} row(s))" if n_rows else "")
                + (f"; {removed} letter(s) removed from the panels" if removed else "") + ".")
    for tag in ("letter_layout", "row_letter_align"):
        el = gui_el.find(tag)
        if el is not None:
            gui_el.remove(el)
    _save(tree, pyf_path)
    added = 0
    if before["letter_layout"] == "row":
        # the panels get their letters back (in the figure's corner and font)
        from pyfigures.mcp_tools.workflow import _finalize_draft
        font_el = root.find("SerializableQFont")
        corner = _decode(font_el.findtext("placement")) if font_el is not None else None
        corner = (corner or "top left").replace("-", " ").lower()
        if corner not in ("top left", "top right", "bottom left", "bottom right"):
            corner = "top left"
        added, _ = _finalize_draft(pyf_path, True, corner, None, None, "")
    return "Letters: one in each panel" + (f" ({added} panel(s) lettered)" if added else "") + "."


@mcp.tool()
def set_label_background(
    pyf_path: str,
    color: str | int = "black",
    group_path: list[int] | None = None,
    include_letters: bool = True,
) -> str:
    """Put a filled box behind panel labels so they read on any image —
    panel letters, labels ("WT"), time stamps, channel names.

    *color*: name, #rrggbb or int; "none" removes the boxes. Pick a colour
      that contrasts with the text (black behind the default white labels).
    *group_path*: only the panels inside this group (default: whole figure).
    *include_letters*: also the auto panel letters (A, B, C…). The GUI keeps
      the letters' box in the figure font (see set_figure_properties
      background_color), so this sets that too.

    Data-plot panels are skipped (their labels already sit on the white chart);
    scale-bar legends are not touched. GUI: right-click → Text & lettering →
    Change background; recipe: ``label_background:``.
    """
    try:
        value = _label_background_text(color)
    except ValueError as e:
        return f"ERROR: {e}"
    tree, root = _load(pyf_path)
    scope = root
    if group_path:
        scope, err = _get_container(root, group_path)
        if err:
            return f"ERROR: {err}"
    n = 0
    boxed = []
    for img in _iter_panel_elements(scope):
        if "from staplot import api" in (_decode(img.findtext("custom_loading_script")) or ""):
            continue
        # label rows and side labels sit on the page, not on an image
        if (_decode(img.findtext("isText")) or "False") not in ("False", "None"):
            continue
        annots = img.find("annotations")
        for ta in (annots.findall("TAText2D") if annots is not None else []):
            if not include_letters and ta.findtext("is_letter") == "True":
                continue
            _set_child_text(ta, "fill_color", value)
            boxed.append(ta)
            n += 1
    # a text the colour of its box vanished (black letters in black boxes):
    # those turn white on a dark box, black on a light one
    recoloured = 0
    if value != "None" and boxed:
        box = int(value)
        new_col = "#ffffff" if _luminance(box) < 0.5 else "#000000"
        poor = [ta for ta in boxed if any(_contrast(box, c) < 2.0
                                          for c in _text_colours(_decode(ta.findtext("text")) or ""))]
        if poor:
            new = _restyle_html_batch([_decode(ta.findtext("text")) or "" for ta in poor], color=new_col)
            if not isinstance(new, str):
                for ta, html in zip(poor, new):
                    _set_child_text(ta, "text", _encode_str(html))
                recoloured = len(poor)
    if include_letters and not group_path:
        # the GUI re-applies the figure font's background to every letter
        font_el = root.find("SerializableQFont")
        if font_el is None:
            font_el = ET.SubElement(root, "SerializableQFont")
        _set_child_text(font_el, "background", value)
        fg = font_el.findtext("foreground")
        if value != "None" and fg not in (None, "", "None") and _contrast(int(value), int(fg)) < 2.0:
            _set_child_text(font_el, "foreground", str(0xFFFFFFFF if _luminance(int(value)) < 0.5
                                                       else 0xFF000000))
    _save(tree, pyf_path)
    what = "removed from" if value == "None" else f"set to {color} on"
    note = (f" {recoloured} text(s) the colour of the box now {'white' if new_col == '#ffffff' else 'black'}."
            if recoloured else "")
    return f"Label background {what} {n} label(s).{note}"


def _luminance(rgb: int) -> float:
    """WCAG relative luminance of 0xRRGGBB."""
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch((rgb >> 16) & 255) + 0.7152 * ch((rgb >> 8) & 255) + 0.0722 * ch(rgb & 255)


def _contrast(a: int, b: int) -> float:
    la, lb = sorted((_luminance(a & 0xFFFFFF), _luminance(b & 0xFFFFFF)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _text_colours(html: str) -> list[int]:
    """The colours a rich text is drawn in (black when it names none: Qt's default)."""
    found = re.findall(r"colou?r\s*[:=]\s*[\"']?#([0-9a-fA-F]{6})", html)
    return [int(h, 16) for h in found] or [0x000000]


_TEXT_TARGETS = ("letters", "texts", "label_rows", "scale_bars", "all")


@mcp.tool()
def restyle_texts(
    pyf_path: str,
    target: str = "texts",
    font_family: str | None = None,
    font_size: float | None = None,
    color: str | int | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
) -> str:
    """Change the font / size / colour / bold / italic of a whole family of
    texts at once, keeping each text's words (Panel letters only had such
    controls).

    *target*: "letters" (the panel letters A, B, C…, also the letters drawn
      one per row outside the rows: set_panel_letter_layout), "texts" (texts on the
      panels that are not letters: labels, channel names, time stamps, arrow
      labels), "label_rows" (rows / columns of labels beside the panels),
      "scale_bars" (scale-bar legends) or "all".
    Only the attributes you give change. *color*: name, #rrggbb or int.
    GUI: Annotations → Text style (letters, labels, scale bars…)….
    """
    target = str(target).strip().lower().replace(" ", "_").replace("-", "_")
    target = {"letter": "letters", "text": "texts", "labels": "texts", "label_row": "label_rows",
              "scalebars": "scale_bars", "scale_bar": "scale_bars", "everything": "all"}.get(target, target)
    if target not in _TEXT_TARGETS:
        return f"ERROR: target must be one of {list(_TEXT_TARGETS)}."
    if font_size is not None and not (math.isfinite(font_size) and font_size > 0):
        return f"ERROR: font_size must be a positive number of points (got {font_size})."
    attrs = {"font_family": font_family, "font_size": font_size, "bold": bold, "italic": italic}
    if color is not None:
        try:
            attrs["color"] = f"#{_color_to_int(color) & 0xFFFFFF:06x}"
        except ValueError as e:
            return f"ERROR: {e}"
    attrs = {k: v for k, v in attrs.items() if v is not None}
    if not attrs:
        return "Nothing changed — give at least one of font_family, font_size, color, bold, italic."
    tree, root = _load(pyf_path)
    # (element, field) pairs holding rich text
    found = {t: [] for t in _TEXT_TARGETS[:-1]}
    for img in _iter_panel_elements(root):
        annots = img.find("annotations")
        is_text_panel = img.findtext("isText", "False") == "True"
        for ta in (annots.findall("TAText2D") if annots is not None else []):
            if is_text_panel:
                found["label_rows"].append((ta, "text"))
            elif (ta.findtext("is_letter") or "") in ("True", "b'True'"):
                found["letters"].append((ta, "text"))
            else:
                found["texts"].append((ta, "text"))
        for sb in (annots.findall("ScaleBar") if annots is not None else []):
            if sb.find("legend") is not None and (_decode(sb.findtext("legend")) or "").strip():
                found["scale_bars"].append((sb, "legend"))
    chosen = [p for t in (_TEXT_TARGETS[:-1] if target == "all" else (target,)) for p in found[t]]
    # one letter per row: drawn from the figure letter font, nothing to rewrite
    n_row = len(row_letters_of(root)) if target in ("letters", "all") else 0
    if not chosen and not n_row:
        return f"No {target.replace('_', ' ')} in this figure: nothing changed."
    new = _restyle_html_batch([_decode(el.findtext(field)) or "" for el, field in chosen], **attrs) if chosen else []
    if isinstance(new, str):
        return f"ERROR: {new}"
    for (el, field), html in zip(chosen, new):
        _set_child_text(el, field, _encode_str(html))
    if target in ("letters", "all"):
        # the GUI re-applies the figure font to the letters: keep it in step
        font_el = root.find("SerializableQFont")
        if font_el is None:
            font_el = ET.SubElement(root, "SerializableQFont")
        if font_family:
            _set_child_text(font_el, "family", _encode_str(font_family))
        if font_size:
            _set_child_text(font_el, "size", str(int(round(float(font_size)))))
        if italic is not None:
            _set_child_text(font_el, "italic", str(bool(italic)))
        if bold is not None:
            _set_child_text(font_el, "style", "700" if bold else "400")
        if "color" in attrs:
            _set_child_text(font_el, "foreground", str(_color_to_int(color)))
    _save(tree, pyf_path)
    what = {"letters": "panel letter(s)", "label_rows": "label-row text(s)",
            "scale_bars": "scale-bar legend(s)"}.get(target, "text(s)")
    msg = f"Restyled {len(chosen) + n_row} {what}"
    if n_row:
        msg += f" ({n_row} row letter(s), drawn with the figure letter font)"
    return msg + ": " + ", ".join(f"{k}={v}" for k, v in attrs.items()) + "."


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

@mcp.tool()
def list_fonts(query: str | None = None) -> str:
    """List the fonts available for figure text on this computer.

    *query*: optional part of a name (case-insensitive), e.g. "arial" or "sans",
    to list only matching families. Also answers "is Helvetica available?":
    list_fonts("Helvetica") → font_check.installed.

    Returns JSON with: installed_families (every font family that can be used,
    filtered by *query*) and their count; with a query, font_check: whether
    that exact font is installed, the font it is really drawn and exported in,
    and installed alternatives of the same style (sans/serif/mono, look-alikes
    first) — offer those when it is not installed; what "Helvetica" and "Arial" are
    really drawn in here and whether real Helvetica/Arial are present (a
    missing Helvetica is drawn and exported as a metric-compatible clone such
    as Arial); bundled_families / portable_clones_available (portable fonts
    PyFigures loads from fonts_dir, where more can be added). To use a font:
    set_figure_properties(font_family=...) or restyle_texts(font_family=...).
    """
    from .core import _font_report
    query = str(query).strip() if query else None
    rep = _font_report([query] if query else [])
    if isinstance(rep, str):
        return f"ERROR: {rep}"
    fams = rep.pop("installed_families", [])
    if query:
        fams = [f for f in fams if query.lower() in f.lower()]
    rep.pop("drawn_as", None)
    status = rep.pop("status", {})
    out = {"query": query, "count": len(fams), "installed_families": fams}
    if query:
        out["font_check"] = status.get(query)
    out.update(rep)
    return json.dumps(out, ensure_ascii=False, indent=2)
