"""PyFigures MCP tools — Captions/legends, scale bars, insets and zoom callouts, row/column label rows.

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
)
from .core import (
    _apply_scalebar_to_img,
    _atomic_write_text,
    _caption_sidecar_path,
    _child_text,
    _color_to_int,
    _decode,
    _encode_str,
    _encode_value,
    _find_scale_bar,
    _get_container,
    _html_to_plain,
    _load,
    _navigate_group,
    _new_image2d,
    _new_roi_line,
    _new_roi_rect,
    _new_tatext2d,
    _next_group_id,
    _read_caption,
    _save,
    _scale_bar_legend_html,
    _scalebar_info,
    _set_child_text,
    _top_groups,
)

@mcp.tool()
def set_figure_caption(pyf_path: str, caption: str, title: str | None = None) -> str:
    """Store the figure's caption/legend (and optional title) alongside the .pyf —
    the text that describes the panels in the paper.

    *caption*: the legend text (plain text; may include panel refs like "(a) …").
    *title*: optional short title, e.g. "Figure 1".

    Saved to a ``<figure>.caption.json`` sidecar next to the .pyf (kept out of the
    figure XML so it can never corrupt the figure's own settings; consolidate/move
    the pair together). Use get_figure_caption() to read it and export_caption() to
    write it out for submission. Empty caption clears it.
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    p = _caption_sidecar_path(pyf_path)
    if not caption and title is None:
        if os.path.isfile(p):
            os.remove(p)
        return "Figure caption cleared."
    old_title, _ = _read_caption(pyf_path)
    _atomic_write_text(p, json.dumps({"title": title if title is not None else old_title,
                                      "caption": caption}, ensure_ascii=False, indent=2))
    return (f"Figure caption set ({len(caption)} chars)"
            + (f", title={title!r}" if title is not None else "")
            + f" → {os.path.basename(p)}.")


@mcp.tool()
def get_figure_caption(pyf_path: str) -> str:
    """Return the figure's stored caption/legend and title as JSON, or a note if
    none has been set. Pairs with set_figure_caption() / export_caption()."""
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    title, caption = _read_caption(pyf_path)
    if not caption and not title:
        return "No figure caption set. Use set_figure_caption() to add one."
    return json.dumps({"title": title, "caption": caption}, ensure_ascii=False, indent=2)


@mcp.tool()
def export_caption(pyf_path: str, out_path: str | None = None, fmt: str = "txt") -> str:
    """Write the figure's stored caption to a text file for manuscript submission.

    *out_path*: output file (default ``<pyf-stem>_caption.<fmt>`` next to the .pyf).
    *fmt*: "txt" (plain) or "md" (title as a Markdown heading).

    Returns the output path. Requires a caption set via set_figure_caption().
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    fmt = fmt.lower().lstrip(".")
    if fmt not in ("txt", "md"):
        return "ERROR: fmt must be 'txt' or 'md'."
    title, caption = _read_caption(pyf_path)
    if not caption:
        return "ERROR: no caption set — use set_figure_caption() first."
    if out_path is None:
        out_path = os.path.splitext(pyf_path)[0] + "_caption." + fmt
    out_path = os.path.abspath(out_path)
    if fmt == "md":
        body = (f"## {title}\n\n" if title else "") + caption + "\n"
    else:
        body = ((title + "\n\n") if title else "") + caption + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)
    return json.dumps({"output": out_path, "chars": len(caption),
                       "title": title}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Scale bar MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_scale_bar(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
) -> str:
    """Return the scale bar settings on a specific image as JSON.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] for sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Returns a JSON object with fields:
      bar_width_in_units, unit_to_pixel_conversion_factor, placement,
      bar_color (int), isSet (bool), label_plain, label_html.
    Returns a message if the image has no scale bar.

    The pixel conversion factor stored on the *image* (px_to_unit_conversion_factor)
    overrides the ScaleBar's own field at render time — check that too via
    get_image_property(..., "px_to_unit_conversion_factor").

    Use set_scale_bar() to add or update a scale bar,
    remove_scale_bar() to delete one.
    """
    _, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    sb = _find_scale_bar(imgs[image_index])
    if sb is None:
        return "No scale bar on this image. Use set_scale_bar() to add one."
    info = _scalebar_info(sb)
    # Also report the image-level px_to_unit so callers see the full picture
    info["image_px_to_unit"] = _child_text(imgs[image_index], "px_to_unit_conversion_factor")
    return json.dumps(info, indent=2, default=str)


@mcp.tool()
def set_scale_bar(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    bar_width_in_units: float,
    label: str | None = None,
    unit: str = "µm",
    placement: str = "bottom right",
    bar_color: str = "white",
    label_color: str = "white",
    px_to_unit: float | None = None,
) -> str:
    """Add or update the scale bar on a specific image.

    If the image already has a ScaleBar annotation it is updated; otherwise a new
    one is added.  Reopen the figure in PyFigures to see the change.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.
    *bar_width_in_units*: numeric width of the bar in physical units (e.g. 10).
    *label*: text shown next to the bar. If omitted, auto-generated as
             "10µm" (combining bar_width_in_units and unit).
    *unit*: physical unit appended to the auto-label (default "µm").
            Ignored if *label* is supplied explicitly.
    *placement*: "bottom right" | "bottom left" | "top right" | "top left"
                 (default "bottom right").
    *bar_color*: color of the bar itself — name ("white", "yellow", …), #rrggbb
                 hex string, or integer (e.g. 16777215 for white).
    *label_color*: color of the text label (same formats as bar_color).
    *px_to_unit*: pixel size in physical units — how many *unit*s per pixel
                  of the raw image (e.g. 0.1 means 1px = 0.1µm).
                  When supplied this is stored on the image's
                  ``px_to_unit_conversion_factor`` field, which PyFigures reads
                  when rendering to compute the bar length in pixels.
                  Example: bar_width_in_units=10, px_to_unit=0.1
                           → bar is 10/0.1 = 100px wide on the original image.
                  If omitted the existing value is left unchanged.

    Color quick reference: white=16777215, black=0, yellow=16776960,
    red=16711680, green=65280, blue=255, cyan=65535, magenta=16711935.
    """
    try:
        bar_color_int  = _color_to_int(bar_color)
        label_color_int = _color_to_int(label_color)
    except ValueError as e:
        return f"ERROR: {e}"

    text = label if label is not None else f"{bar_width_in_units}{unit}"
    legend_html = _scale_bar_legend_html(text, label_color_int)

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    action = _apply_scalebar_to_img(
        imgs[image_index], bar_width_in_units, legend_html,
        placement, bar_color_int, px_to_unit,
    )
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    px_note = f", px_to_unit={px_to_unit}" if px_to_unit is not None else ""
    return (
        f"Scale bar {action} on image {image_index} in {loc}: "
        f"{text}, {placement}{px_note}."
    )


@mcp.tool()
def remove_scale_bar(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
) -> str:
    """Remove the scale bar from a specific image.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Returns a confirmation or an error if no scale bar was found.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    annots = imgs[image_index].find("annotations")
    if annots is None:
        return "No annotations element — image has no scale bar."
    sb = annots.find("ScaleBar")
    if sb is None:
        return "Image has no scale bar to remove."
    annots.remove(sb)
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Scale bar removed from image {image_index} in {loc}."


@mcp.tool()
def set_scale_bar_all(
    pyf_path: str,
    bar_width_in_units: float,
    label: str | None = None,
    unit: str = "µm",
    placement: str = "bottom right",
    bar_color: str = "white",
    label_color: str = "white",
    px_to_unit: float | None = None,
) -> str:
    """Add or update the scale bar on EVERY image in the figure at once.

    Applies the same scale bar settings to all Image2D elements, including
    images inside nested sub-groups (grids).  Existing scale bars are updated;
    images without one get a new scale bar added.

    Parameters are identical to set_scale_bar(), except *group_path* and
    *image_index* are omitted — this tool always targets all images.

    Typical workflow::

        # All images share the same pixel size (0.1 µm/px).
        # Add a 10µm white scale bar at the bottom-right of every image:
        set_scale_bar_all("figure.pyf", 10, unit="µm", px_to_unit=0.1)

        # Custom label, yellow bar, white text:
        set_scale_bar_all("figure.pyf", 50, label="50 nm",
                          bar_color="yellow", label_color="white")

    Returns a summary: how many images were updated vs. how many got a new bar.
    """
    try:
        bar_color_int   = _color_to_int(bar_color)
        label_color_int = _color_to_int(label_color)
    except ValueError as e:
        return f"ERROR: {e}"

    text = label if label is not None else f"{bar_width_in_units}{unit}"
    legend_html = _scale_bar_legend_html(text, label_color_int)

    tree, root = _load(pyf_path)

    added = 0
    updated = 0
    skipped = 0

    def _process_img(img: ET.Element):
        nonlocal added, updated, skipped
        # a chart or a LUT calibration bar has no pixel size: no scale bar
        script = _decode(img.findtext("custom_loading_script")) or ""
        if "from staplot import api" in script or "ColorbarBase(" in script:
            skipped += 1
            return
        action = _apply_scalebar_to_img(
            img, bar_width_in_units, legend_html,
            placement, bar_color_int, px_to_unit,
        )
        if action == "added":
            added += 1
        else:
            updated += 1

    # Free-canvas images
    for img in (c for c in root if c.tag == "Image2D"):
        _process_img(img)

    # Group-based images — recursive walk
    def _walk(grp: ET.Element):
        content = grp.find("content")
        if content is None:
            return
        for child in content:
            if child.tag == "Image2D":
                _process_img(child)
            elif child.tag == "Group":
                _walk(child)

    for grp in _top_groups(root):
        _walk(grp)

    total = added + updated
    if total == 0:
        return "No images found in this figure."
    _save(tree, pyf_path)
    px_note = f", px_to_unit={px_to_unit}" if px_to_unit is not None else ""
    skip_note = f" Skipped {skipped} data-plot / colour-bar panel(s)." if skipped else ""
    return (
        f"Scale bar applied to {total} image(s): "
        f"{added} added, {updated} updated. "
        f"Settings: '{text}', {placement}{px_note}.{skip_note}"
    )


# ---------------------------------------------------------------------------
# Inset / picture-in-picture MCP tools
# ---------------------------------------------------------------------------

def _get_insets(img: ET.Element) -> list[ET.Element]:
    """Return all Image2D elements nested inside *img*'s <annotations> (insets)."""
    annots = img.find("annotations")
    if annots is None:
        return []
    return [c for c in annots if c.tag == "Image2D"]


@mcp.tool()
def add_inset(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    inset_filename: str,
    placement: str = "top right",
    size_fraction: float = 0.25,
    border_size: int | None = 3,
    border_color: str = "white",
) -> str:
    """Add a picture-in-picture (inset) image to an existing image panel.

    An inset is a second image overlaid on the parent panel — typically a
    magnified detail, a different channel, or a comparison crop.  PyFigures
    renders it as a fraction of the parent image's width and places it in the
    chosen corner.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index of the **parent** panel.
    *inset_filename*: absolute path to the inset image file.
    *placement*: corner — "top right" | "top left" | "bottom right" | "bottom left"
                 (default "top right").
    *size_fraction*: width of the inset as a fraction of the parent image width
                     (0.0–1.0, default 0.25 = 25%).  Height is set automatically
                     to preserve the inset image's aspect ratio.
    *border_size*: frame thickness in pixels (default 3).  Pass 0 or None for
                   no border.
    *border_color*: frame color — name ("white", "yellow", …), #rrggbb, or int
                    (default "white" = 16777215).

    The inset inherits the full Image2D field set, so you can later call
    set_inset_property() to change crop, LUTs, opacity, rotation, etc.
    Use list_insets() to discover inset indices and remove_inset() to delete.

    Example — add a 30 % magnified detail at the bottom-right with a yellow border::

        add_inset("fig.pyf", [0], 2, "/data/detail.png",
                  placement="bottom right", size_fraction=0.30,
                  border_color="yellow")
    """
    try:
        border_color_int = _color_to_int(border_color)
    except ValueError as e:
        return f"ERROR: {e}"
    if not (0.0 < size_fraction <= 1.0):
        return "ERROR: size_fraction must be between 0 (exclusive) and 1.0."

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    parent_img = imgs[image_index]
    annots = parent_img.find("annotations")
    if annots is None:
        annots = ET.SubElement(parent_img, "annotations")

    # Build the inset as a standard Image2D, then customise inset-specific fields
    inset = _new_image2d(inset_filename)
    _set_child_text(inset, "placement", placement)
    _set_child_text(inset, "fraction_of_parent_image_width_if_image_is_inset",
                    str(float(size_fraction)))
    _set_child_text(inset, "border_size",
                    str(int(border_size)) if border_size else "None")
    _set_child_text(inset, "border_color", str(border_color_int))

    annots.append(inset)
    _save(tree, pyf_path)

    inset_idx = len(_get_insets(parent_img)) - 1
    loc = "canvas" if not group_path else f"group {group_path}"
    border_note = f", border={border_size}px {border_color}" if border_size else ", no border"
    return (
        f"Inset {inset_idx} added to image {image_index} in {loc}: "
        f"{Path(inset_filename).name}, {placement}, "
        f"size={int(size_fraction * 100)}%{border_note}."
    )


@mcp.tool()
def add_zoom_callout(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    source_x: float,
    source_y: float,
    source_w: float,
    source_h: float,
    parent_width: float,
    parent_height: float,
    inset_corner: str = "top right",
    inset_fraction: float = 0.4,
    box_color: str | int = "yellow",
    line_color: str | int = "yellow",
    stroke: float = 1.5,
    connectors: int = 2,
    inset_border: int = 2,
    inset_filename: str | None = None,
) -> str:
    """Add a zoom / magnified-detail callout to a panel — the micrograph staple:
    a box around a region of interest, a magnified inset of that region in a
    corner, and leader lines connecting the box to the inset.

    Everything is placed in the parent panel's *image-pixel* space, so you must
    give the parent image's pixel size (*parent_width*, *parent_height*) — the
    geometry is then exact and needs no image loading. The magnified inset shows
    the parent's own *source* region (created by cropping a copy of the parent);
    pass *inset_filename* only if the magnified view is a different file.

    *source_x/y/w/h*: the region of interest, in parent pixels.
    *parent_width/height*: the parent image's pixel dimensions (see list_images /
    describe_figure, or the source file).
    *inset_corner*: where the magnified inset sits — "top right" (default),
    "top left", "bottom right", "bottom left".
    *inset_fraction*: inset width as a fraction of the parent width (0-1).
    *box_color* / *line_color*: ROI box and leader-line colour.
    *stroke*: line width in px.
    *connectors*: number of leader lines (0, 1 or 2; 2 = the usual funnel).
    *inset_border*: inset frame thickness in px (0 = none).

    Example — box a region and magnify it 40 % in the top-right, 2 leaders::

        add_zoom_callout("fig.pyf", [0], 0, source_x=300, source_y=220,
                         source_w=120, source_h=120,
                         parent_width=1024, parent_height=1024)

    The inset is drawn flush in its corner, so the leader lines end exactly on
    its corners (also in single-pass exports). GUI: Annotations -> Add zoom
    callout to selected panel.
    """
    corners = {"top right", "top left", "bottom right", "bottom left"}
    if inset_corner not in corners:
        return f"ERROR: inset_corner must be one of {sorted(corners)}."
    if not (0.0 < inset_fraction <= 1.0):
        return "ERROR: inset_fraction must be between 0 (exclusive) and 1.0."
    if source_w <= 0 or source_h <= 0:
        return "ERROR: source_w and source_h must be positive."
    if parent_width <= 0 or parent_height <= 0:
        return "ERROR: parent_width and parent_height must be positive."
    if connectors not in (0, 1, 2):
        return "ERROR: connectors must be 0, 1 or 2."

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    parent_img = imgs[image_index]
    annots = parent_img.find("annotations")
    if annots is None:
        annots = ET.SubElement(parent_img, "annotations")

    bc = _color_to_int(box_color)
    lc = _color_to_int(line_color)

    # 1) source ROI box (exact, parent px)
    annots.append(_new_roi_rect(source_x, source_y, source_w, source_h, bc, None, stroke, 1.0))

    # 2) inset rect in parent px (flush to the chosen corner)
    iw = inset_fraction * parent_width
    ih = iw * (source_h / source_w)
    ix = (parent_width - iw) if "right" in inset_corner else 0.0
    iy = (parent_height - ih) if "bottom" in inset_corner else 0.0
    ix2, iy2 = ix + iw, iy + ih

    # 3) leader lines from the box side facing the inset to the inset side facing the box
    if connectors:
        bx1, by1, bx2, by2 = source_x, source_y, source_x + source_w, source_y + source_h
        box_c = {"tl": (bx1, by1), "tr": (bx2, by1), "bl": (bx1, by2), "br": (bx2, by2)}
        ins_c = {"tl": (ix, iy), "tr": (ix2, iy), "bl": (ix, iy2), "br": (ix2, iy2)}
        bcx, bcy = (bx1 + bx2) / 2, (by1 + by2) / 2
        icx, icy = (ix + ix2) / 2, (iy + iy2) / 2
        if abs(icx - bcx) >= abs(icy - bcy):
            (bp, ip) = (("tr", "br"), ("tl", "bl")) if icx > bcx else (("tl", "bl"), ("tr", "br"))
        else:
            (bp, ip) = (("bl", "br"), ("tl", "tr")) if icy > bcy else (("tl", "tr"), ("bl", "br"))
        for bk, ik in list(zip(bp, ip))[:connectors]:
            (lx1, ly1), (lx2, ly2) = box_c[bk], ins_c[ik]
            annots.append(_new_roi_line(lx1, ly1, lx2, ly2, lc, stroke, 1.0, False, False))

    # 4) magnified inset (drawn last = on top of the leaders), corner-placed
    src_file = inset_filename or _decode(parent_img.findtext("filename")) or ""
    inset = _new_image2d(str(src_file))
    _set_child_text(inset, "placement", inset_corner)
    _set_child_text(inset, "fraction_of_parent_image_width_if_image_is_inset",
                    str(float(inset_fraction)))
    _set_child_text(inset, "border_size", str(int(inset_border)) if inset_border else "None")
    _set_child_text(inset, "border_color", str(bc))
    if inset_filename is None:   # magnify the parent's own source region via crop
        # shown like the parent (same LUTs, channels, series…), also after later
        # changes to the parent: follow_parent_display (it used to show grey)
        for tag in ("LUTs", "channels", "normalization", "projection", "projection_z_start",
                    "projection_z_end", "dimensions", "serie_to_open"):
            value = parent_img.findtext(tag)
            if value is not None:
                _set_child_text(inset, tag, value)
        _set_child_text(inset, "follow_parent_display", "True")
        _set_child_text(inset, "crop_left",   str(int(source_x)))
        _set_child_text(inset, "crop_top",    str(int(source_y)))
        _set_child_text(inset, "crop_right",  str(int(max(0, parent_width - (source_x + source_w)))))
        _set_child_text(inset, "crop_bottom", str(int(max(0, parent_height - (source_y + source_h)))))
    annots.append(inset)

    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return (
        f"Zoom callout added to image {image_index} in {loc}: source "
        f"({source_x:g},{source_y:g}) {source_w:g}×{source_h:g}px → {int(inset_fraction*100)}% "
        f"inset at {inset_corner}, {connectors} leader line(s), box/line color={box_color}."
    )


@mcp.tool()
def list_insets(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
) -> str:
    """List all inset images on a specific panel as JSON.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index of the parent panel.

    Each entry in the returned array:
      inset_index, filename, placement, size_fraction, border_size, border_color,
      crop_left/right/top/bottom, has_script.

    Use add_inset() to add a new inset, remove_inset() to delete one, and
    set_inset_property() to change any field.
    """
    _, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    insets = _get_insets(imgs[image_index])
    if not insets:
        return "No insets on this image. Use add_inset() to add one."

    result = []
    for ii, ins in enumerate(insets):
        fn = _child_text(ins, "filename")
        script = _child_text(ins, "custom_loading_script")
        result.append({
            "inset_index": ii,
            "filename": fn,
            # placement is a Position — stored as raw text, decode without ""..."" stripping
            "placement": ins.findtext("placement") or "",
            "size_fraction": _decode(ins.findtext("fraction_of_parent_image_width_if_image_is_inset")),
            "border_size":  _decode(ins.findtext("border_size")),
            "border_color": _decode(ins.findtext("border_color")),
            "crop_left":    _decode(ins.findtext("crop_left")),
            "crop_right":   _decode(ins.findtext("crop_right")),
            "crop_top":     _decode(ins.findtext("crop_top")),
            "crop_bottom":  _decode(ins.findtext("crop_bottom")),
            "has_script":   script is not None,
        })
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def remove_inset(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    inset_index: int,
) -> str:
    """Remove an inset image from a panel.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index of the parent panel.
    *inset_index*: 0-based index among the insets (from list_insets()).
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    insets = _get_insets(imgs[image_index])
    if inset_index >= len(insets):
        return f"ERROR: inset_index {inset_index} out of range ({len(insets)} insets)."

    annots = imgs[image_index].find("annotations")
    annots.remove(insets[inset_index])
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Inset {inset_index} removed from image {image_index} in {loc}."


@mcp.tool()
def set_inset_property(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    inset_index: int,
    property_name: str,
    value: str,
) -> str:
    """Set any property on an inset Image2D.

    Insets share the same field schema as regular panels, so all the same
    property names apply.  Common use cases:

    ┌──────────────────────────────────────────────┬──────────────────────────┐
    │ property_name                                │ example value            │
    ├──────────────────────────────────────────────┼──────────────────────────┤
    │ fraction_of_parent_image_width_if_image_is_inset │ "0.3"            │
    │ placement                                    │ "bottom left"            │
    │ border_size                                  │ "5"                      │
    │ border_color                                 │ "16776960"  (yellow)     │
    │ filename                                     │ "/new/path/detail.png"   │
    │ crop_left / crop_right / crop_top / crop_bottom │ "20"                 │
    │ opacity                                      │ "0.8"                    │
    │ LUTs                                         │ "['GREEN', None, None]"  │
    │ theta                                        │ "45"                     │
    └──────────────────────────────────────────────┴──────────────────────────┘

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index of the parent panel.
    *inset_index*: 0-based index among the insets (from list_insets()).
    *property_name*: exact XML tag name.
    *value*: new value as a string — auto-encoded (see set_image_property docs).

    The change is saved immediately; reopen in PyFigures to see the result.
    """
    _LAYOUT_FIELDS = {"x", "y", "width", "height", "scale",
                      "__init_called__", "__version__", "extra_user_translation"}
    if property_name in _LAYOUT_FIELDS:
        return (
            f"ERROR: '{property_name}' is a layout field managed by PyFigures — "
            "do not set it directly on an inset."
        )

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    insets = _get_insets(imgs[image_index])
    if inset_index >= len(insets):
        return f"ERROR: inset_index {inset_index} out of range ({len(insets)} insets)."

    # placement is a Position object — serialised by PyFigures as a plain string
    # (no ""..."" wrapping).  filename always needs the double-quote wrapping.
    # Everything else goes through the smart encoder.
    if property_name == "placement":
        raw = value.strip()
    elif property_name == "filename":
        raw = _encode_str(value)
    else:
        raw = _encode_value(value)
    _set_child_text(insets[inset_index], property_name, raw)
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return (
        f"Inset {inset_index} on image {image_index} in {loc}: "
        f"{property_name} = {raw}"
    )


# ---------------------------------------------------------------------------
# Row / column label MCP tools
# ---------------------------------------------------------------------------

# Map user-facing orientation names to internal TAText2D text_orientation values
_TEXT_ORIENT_MAP = {
    "horizontal":        "None",
    "vertical":          _encode_str("Y"),
    "vertical_flipped":  _encode_str("-Y"),
}


def _new_text_label_image2d(label_text: str, text_orientation: str = "horizontal") -> ET.Element:
    """Create an Image2D with isText=True used as a label cell in a text row."""
    img = ET.Element("Image2D")
    for tag, val in [
        ("x",           "0.0"),
        ("y",           "0.0"),
        ("width",       "512.0"),
        ("height",      "256.0"),
        ("filename",    "None"),
        ("custom_loading_script", "None"),
        ("crop_left",   "0"),
        ("crop_right",  "0"),
        ("crop_top",    "0"),
        ("crop_bottom", "0"),
        ("line_style",  "None"),
        ("placement",   "top right"),
        ("fraction_of_parent_image_width_if_image_is_inset", "0.25"),
        ("border_size", "None"),
        ("border_color","16777215"),
        ("color",       "16776960"),
        ("fill_color",  "None"),
        ("stroke",      "0.65"),
        ("opacity",     "1"),
        ("isSet",       "False"),
        ("scale",       "1"),
        ("theta",       "None"),
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",   "False"),
        ("__init_called__", "True"),
        ("__version__", "1.0"),
        ("translation", "PyQt6.QtCore.QPointF()"),
        ("isText",      "True"),
    ]:
        ET.SubElement(img, tag).text = val
    # extra_user_translation: two empty <int/> elements (x, y offsets)
    etu = ET.SubElement(img, "extra_user_translation")
    ET.SubElement(etu, "int")
    ET.SubElement(etu, "int")

    ann = ET.SubElement(img, "annotations")
    ta = _new_tatext2d(label_text, placement="center_h center_v")
    # Override text_orientation to the requested style
    to_el = ta.find("text_orientation")
    if to_el is not None:
        to_el.text = _TEXT_ORIENT_MAP.get(text_orientation, "None")
    ann.append(ta)
    return img


def _find_group_index_in_root(root: ET.Element, group_path: list[int]) -> int:
    """Return the index of the target Group inside root (among ALL children, not just Groups)."""
    target, err = _navigate_group(root, group_path)
    if err:
        return -1
    for i, child in enumerate(root):
        if child is target:
            return i
    return -1


@mcp.tool()
def add_label_row(
    pyf_path: str,
    group_path: list[int],
    labels: list[str] | str,
    position: str = "above",
    text_orientation: str = "horizontal",
) -> str:
    """Add a row of text labels above or below a group.

    This creates a separate label-row Group immediately adjacent to the target
    group — exactly what PyFigures does when you right-click a panel row and
    choose "Above / Below the row".

    *group_path*: must be a top-level group, i.e. [0], [1], …
    *labels*: the text(s) to display.

      - A **list** of strings assigns one label per column in the target group
        (e.g. ["WT", "KO", "Rescue"] for a 3-image row).  The list length must
        match the number of non-label children in that group.
      - A **single string** creates one label that spans the entire row (useful
        when you want one header above a multi-image panel).

    *position*: "above" (default) or "below".
    *text_orientation*: "horizontal" (default), "vertical", or "vertical_flipped".

    Example::

        # Add column headers "WT", "KO" above a 2-image row
        add_label_row("fig.pyf", [0], ["WT", "KO"], position="above")

        # Single centred header below the row
        add_label_row("fig.pyf", [0], "Figure 1", position="below")
    """
    position = position.strip().lower()
    if position not in ("above", "below"):
        return "ERROR: position must be 'above' or 'below'."
    if text_orientation not in _TEXT_ORIENT_MAP:
        return f"ERROR: text_orientation must be one of {list(_TEXT_ORIENT_MAP)}."
    if len(group_path) != 1:
        return "ERROR: add_label_row only supports top-level groups (group_path length must be 1)."

    tree, root = _load(pyf_path)
    grp, err = _navigate_group(root, group_path)
    if err:
        return f"ERROR: {err}"

    # Count non-label children to know how many label cells to create
    content = grp.find("content")
    content_children = list(content) if content is not None else []
    non_label_count = sum(
        1 for c in content_children
        if c.tag in ("Image2D", "Group") and c.findtext("isText", "False") not in ("True",)
    )

    # Resolve labels list
    if isinstance(labels, str):
        labels_list = [labels]
    else:
        labels_list = list(labels)
        if len(labels_list) != non_label_count:
            return (
                f"ERROR: {non_label_count} non-label children in the group but "
                f"{len(labels_list)} label(s) supplied. "
                "Provide one label per child, or a single string for a spanning header."
            )

    # Get group orientation to match the label row orientation
    grp_orient = (_child_text(grp, "orientation") or "X").upper()
    spacing = _child_text(grp, "space") or 3
    new_id = _next_group_id(root)

    # isText value on the label-row Group describes where the CONTENT is relative to it
    istext_val = _encode_str("above" if position == "below" else "below")

    # Build the label-row Group
    label_grp = ET.Element("Group")
    content_el = ET.SubElement(label_grp, "content")
    for lbl in labels_list:
        content_el.append(_new_text_label_image2d(lbl, text_orientation))
    for tag, val in [
        ("space",       str(spacing)),
        ("orientation", _encode_str(grp_orient)),
        ("size",        "512.0"),
        ("ID",          str(new_id)),
        ("fill_color",  "None"),
        ("immutable",   "False"),
        ("isText",      istext_val),
    ]:
        ET.SubElement(label_grp, tag).text = val

    # Find the index of the target group in root and insert accordingly
    root_idx = _find_group_index_in_root(root, group_path)
    if root_idx < 0:
        return "ERROR: could not locate group in root."
    if position == "above":
        root.insert(root_idx, label_grp)
        new_label_path = [group_path[0]]   # inserted before → same index
    else:
        root.insert(root_idx + 1, label_grp)
        new_label_path = [group_path[0] + 1]

    _save(tree, pyf_path, recompute=True)
    loc = f"group {group_path}"
    texts_preview = ", ".join(f'"{l}"' for l in labels_list[:4])
    if len(labels_list) > 4:
        texts_preview += f" … ({len(labels_list)} total)"
    return (
        f"Label row added {position} of {loc} (new path {new_label_path}): "
        f"{texts_preview}."
    )


@mcp.tool()
def add_side_label(
    pyf_path: str,
    group_path: list[int],
    label: str,
    position: str = "left",
    text_orientation: str = "auto",
) -> str:
    """Add a side text label to the left/right (or top/bottom) of a group.

    A side label is a special Image2D with isText=True inserted as the first or
    last element of the group's content — exactly what PyFigures produces when
    you choose "Left / top of row/col" or "Right / bottom of row/col".

    For a **horizontal row** (orientation=X):
      - position="left"  → label appears to the LEFT of all images.
      - position="right" → label appears to the RIGHT of all images.

    For a **vertical column** (orientation=Y):
      - position="top"   → label appears ABOVE all images.
      - position="bottom"→ label appears BELOW all images.

    Aliases: "left"="top", "right"="bottom" are both accepted for either orientation.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *label*: text string (plain or Qt HTML).
    *text_orientation*: "auto" (default, chooses based on group orientation),
                        "horizontal", "vertical", or "vertical_flipped".

    Example::

        # Add a vertical label to the left of a horizontal row of images
        add_side_label("fig.pyf", [0], "Condition A", position="left")

        # Add a horizontal label below a vertical column
        add_side_label("fig.pyf", [1], "n = 5", position="bottom")
    """
    position = position.strip().lower()
    if position not in ("left", "right", "top", "bottom"):
        return "ERROR: position must be 'left', 'right', 'top', or 'bottom'."

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"

    # Determine group orientation to auto-select text direction
    if group_path:
        grp, _ = _navigate_group(root, group_path)
        grp_orient = (_child_text(grp, "orientation") or "X").upper() if grp is not None else "X"
    else:
        grp_orient = "X"

    if text_orientation == "auto":
        # Match what ezfig.py does: -Y for X-group, X for Y-group
        resolved_orient = "vertical_flipped" if grp_orient == "X" else "horizontal"
    else:
        resolved_orient = text_orientation
    if resolved_orient not in _TEXT_ORIENT_MAP:
        return f"ERROR: text_orientation must be one of {list(_TEXT_ORIENT_MAP)} or 'auto'."

    label_img = _new_text_label_image2d(label, resolved_orient)

    if position in ("left", "top"):
        container.insert(0, label_img)
    else:
        container.append(label_img)

    _save(tree, pyf_path, recompute=True)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Side label '{label}' added to the {position} of {loc}."


@mcp.tool()
def list_label_rows(pyf_path: str) -> str:
    """List all text-row / label-row Groups in the figure as JSON.

    Returns every Group whose isText field is not False — these are the text
    rows that appear above, below, or beside content rows.  Each entry includes:

      group_index (position in top-level list), group_path, position_hint
      (decoded isText value, e.g. "above"/"below"), and labels (list of plain
      text strings for each label cell).

    Use add_label_row() to add new label rows and remove_label_row() to delete.
    """
    _, root = _load(pyf_path)
    result = []
    gi = 0
    for raw_idx, child in enumerate(root):
        if child.tag != "Group":
            continue
        ist = child.findtext("isText", "False")
        is_label = ist not in ("False", "")
        if is_label:
            content = child.find("content")
            labels = []
            if content is not None:
                for img in content:
                    if img.tag == "Image2D":
                        ann = img.find("annotations")
                        if ann is not None:
                            for ta in ann.findall("TAText2D"):
                                plain = _html_to_plain(_child_text(ta, "text") or "")
                                orient = _decode(ta.findtext("text_orientation"))
                                labels.append({"text": plain, "text_orientation": orient})
            result.append({
                "group_index": gi,
                "group_path": [gi],
                "position_hint": _decode(ist),
                "labels": labels,
            })
        gi += 1
    if not result:
        return "No label-row groups found. Use add_label_row() to add one."
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def remove_label_row(pyf_path: str, group_path: list[int]) -> str:
    """Remove a label-row Group from the figure.

    *group_path*: the path of the label-row group to remove, e.g. [1].
    Use list_label_rows() or describe_figure() to identify the correct path.

    Returns an error if the target group is not a label row (isText != False) —
    use remove_group() to delete regular content groups.
    """
    if len(group_path) != 1:
        return "ERROR: remove_label_row only operates on top-level groups."
    tree, root = _load(pyf_path)
    grp, err = _navigate_group(root, group_path)
    if err:
        return f"ERROR: {err}"
    ist = grp.findtext("isText", "False")
    if ist in ("False", ""):
        return (
            f"ERROR: group {group_path} is not a label row (isText={ist!r}). "
            "Use remove_group() to remove regular content groups."
        )
    root.remove(grp)
    _save(tree, pyf_path, recompute=True)
    return f"Label-row group {group_path} removed."
