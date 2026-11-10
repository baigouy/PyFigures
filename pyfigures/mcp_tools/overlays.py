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
    _corner_error,
    _apply_scalebar_to_img,
    _first_filename,
    _pixel_size,
    _scale_bar_length_error,
    _length_unit_factor,
    _atomic_write_text,
    _caption_sidecar_path,
    _check_property_value,
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
    _resolve_image_property,
    _save,
    _scale_bar_legend_html,
    _scalebar_info,
    _set_child_text,
    _stored_image_property,
    _top_groups,
)

def _stored_units_per(unit) -> float:
    """How many stored pixel-size units (µm) one *unit* is: 1000 for mm, so a
    "100 mm" bar is 100 mm long (it was 100 µm long with a "100 mm" label: on
    a CT scan, a label without a bar). 1 for µm, px and units not known as
    lengths."""
    return _length_unit_factor(unit) or 1.0


def _default_bar_label(units, unit) -> str:
    """'10 µm': the number without a trailing '.0' and a space before the unit
    (SI style; it read '10.0µm')."""
    try:
        number = f"{float(units):g}"
    except (TypeError, ValueError):
        number = str(units)
    unit = (unit or "").strip()
    # "um" is the ASCII stand-in for µm (and models type it): print the real unit
    unit = {"um": "µm", "micron": "µm", "microns": "µm", "μm": "µm"}.get(unit.lower(), unit)
    return f"{number} {unit}" if unit else number


@mcp.tool()
def set_figure_caption(pyf_path: str, caption: str, title: str | None = None,
                       caption_markdown: str | None = None) -> str:
    """Store the figure's caption/legend (and optional title) alongside the .pyf —
    the text that describes the panels in the paper.

    *caption*: the legend text (plain text; may include panel refs like "(a) …").
    *title*: optional short title, e.g. "Figure 1".
    *caption_markdown*: the same caption with formatting (**bold**, *italic*
      species names…), written by export_caption(fmt="md"). A new plain
      *caption* without it drops the old formatted version.

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
    entry = {"title": title if title is not None else old_title, "caption": caption}
    if caption_markdown:
        entry["caption_markdown"] = caption_markdown
    _atomic_write_text(p, json.dumps(entry, ensure_ascii=False, indent=2))
    return (f"Figure caption set ({len(caption)} chars)"
            + (f", title={title!r}" if title is not None else "")
            + f" → {os.path.basename(p)}.")


def _read_caption_markdown(pyf_path: str):
    """The formatted (Markdown) caption written by the GUI, or None."""
    try:
        with open(_caption_sidecar_path(pyf_path), encoding="utf-8") as f:
            return json.load(f).get("caption_markdown")
    except (OSError, ValueError):
        return None


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
        # the formatted caption (bold, italics) when one was written
        rich = _read_caption_markdown(pyf_path) or caption
        body = (f"## {title}\n\n" if title else "") + rich + "\n"
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
    if not 0 <= image_index < len(imgs):
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
             "10 µm" (combining bar_width_in_units and unit).
    *unit*: the unit of *bar_width_in_units* (and of *px_to_unit*), shown in
            the auto-label: "µm" (default), "nm", "mm", "cm", "m". Pixel sizes
            are kept in µm, so a bar in another unit is converted: 100 with
            unit="mm" is a 100 mm bar (large samples: CT, whole organs). A bar
            shorter than one pixel is refused, as is one wider than the image.
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
    if _corner_error(placement):
        return f"ERROR: {_corner_error(placement)}"

    text = label if label is not None else _default_bar_label(bar_width_in_units, unit)
    legend_html = _scale_bar_legend_html(text, label_color_int)

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    calibrated = px_to_unit is not None or _pixel_size(imgs[image_index])[0] is not None
    factor = _stored_units_per(unit) if calibrated else 1.0
    too_long = _scale_bar_length_error(imgs[image_index], bar_width_in_units, px_to_unit, unit, factor)
    if too_long:
        return f"ERROR: {too_long} Nothing was changed."

    uncal = []
    if not calibrated:
        # no pixel size anywhere: the bar is a length in pixels and says so
        uncal = [os.path.basename(str(_first_filename(imgs[image_index])))]
        text = _default_bar_label(bar_width_in_units, "px")
        legend_html = _scale_bar_legend_html(text, label_color_int)
    # the bar is stored in the pixel size's unit (µm): "100 mm" is 100000 of them, labelled 100 mm
    action = _apply_scalebar_to_img(
        imgs[image_index], bar_width_in_units * factor, legend_html,
        placement, bar_color_int, None if px_to_unit is None else px_to_unit * factor,
    )
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    px_note = f", px_to_unit={px_to_unit}" if px_to_unit is not None else ""
    return (
        f"Scale bar {action} on image {image_index} in {loc}: "
        f"{text}, {placement}{px_note}." + _uncalibrated_warning(uncal, unit)
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
    if not 0 <= image_index < len(imgs):
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
    px_to_unit_scope: str = "all",
) -> str:
    """Add or update the scale bar on EVERY image in the figure at once.

    When the user gives ONE pixel size for the figure, pass it as *px_to_unit*
    and leave *px_to_unit_scope* at "all" (the default): every image then uses
    it. "missing" leaves each image that already has a pixel size with its
    own, so the bars of those images do NOT use the value given.

    Applies the same scale bar settings to all Image2D elements, including
    images inside nested sub-groups (grids).  Existing scale bars are updated;
    images without one get a new scale bar added.

    Parameters are identical to set_scale_bar(), except *group_path* and
    *image_index* are omitted — this tool always targets all images.

    Pixel size: each image keeps its own (from its file's metadata or set
    before) unless *px_to_unit* is given. *px_to_unit_scope*: ``"all"``
    (default) — *px_to_unit* replaces the pixel size of every image;
    ``"missing"`` — it is used only for images that have none (a calibrated
    image keeps its own). An image left without any pixel size gets a bar
    drawn at 1 unit per pixel: the reply flags it as NOT calibrated — never
    present such a bar as a real scale (ask the user for the pixel size).

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

    if px_to_unit_scope not in ("all", "missing"):
        return "ERROR: px_to_unit_scope must be 'all' or 'missing'."
    if _corner_error(placement):
        return f"ERROR: {_corner_error(placement)}"
    text = label if label is not None else _default_bar_label(bar_width_in_units, unit)
    legend_html = _scale_bar_legend_html(text, label_color_int)
    px_legend_html = _scale_bar_legend_html(_default_bar_label(bar_width_in_units, "px"),
                                            label_color_int)

    tree, root = _load(pyf_path)

    added = 0
    updated = 0
    skipped = 0
    kept_own = 0
    too_long: list[str] = []
    uncalibrated: list[str] = []
    used: list[str] = []         # the pixel size each bar was drawn with

    def _process_img(img: ET.Element):
        nonlocal added, updated, skipped, kept_own
        # label-row cells and side labels are text: a bar drawn over them
        # crossed the words (it looked like clipped text)
        if (_decode(img.findtext("isText")) or "False") not in ("False", "None"):
            return
        # a chart or a LUT calibration bar has no pixel size: no scale bar,
        # nor an equation or another vector drawing
        script = _decode(img.findtext("custom_loading_script")) or ""
        fn = str(_decode(img.findtext("filename")) or "")
        if "from staplot import api" in script or "ColorbarBase(" in script \
                or fn.lower().endswith((".svg", ".pdf")):
            skipped += 1
            return
        px = px_to_unit
        own, _source = _pixel_size(img)
        if px is not None and px_to_unit_scope == "missing" and own is not None:
            px = None                    # a calibrated image keeps its own pixel size
            kept_own += 1
        factor = _stored_units_per(unit) if (px is not None or own is not None) else 1.0
        err = _scale_bar_length_error(img, bar_width_in_units, px, unit, factor)
        if err:
            too_long.append(f"{os.path.basename(str(_first_filename(img)))}: {err}")
            return
        legend = legend_html
        name = os.path.basename(str(_first_filename(img)))
        if px is None and own is None:
            uncalibrated.append(name)
            legend = px_legend_html          # no pixel size: the bar says pixels
        elif px is not None:
            used.append(f"{name} {px:g} (given)")
        else:
            used.append(f"{name} {own:g} (its own"
                        + (", kept: NOT the value given)" if px_to_unit is not None else ")"))
        action = _apply_scalebar_to_img(
            img, bar_width_in_units * factor, legend,
            placement, bar_color_int, None if px is None else px * factor,
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

    if too_long:
        return "ERROR: " + " | ".join(too_long[:3]) + " Nothing was changed."
    total = added + updated
    if total == 0:
        return "No images found in this figure."
    _save(tree, pyf_path)
    px_note = f", px_to_unit={px_to_unit}" if px_to_unit is not None else ""
    if px_to_unit is not None and kept_own:
        px_note += f" (only for images without a pixel size; {kept_own} kept their own)"
    skip_note = (f" Skipped {skipped} data-plot / colour-bar / vector panel(s)."
                 if skipped else "")
    return (
        f"Scale bar applied to {total} image(s): "
        f"{added} added, {updated} updated. "
        f"Settings: '{text}', {placement}{px_note}.{skip_note}"
        # per image: a 27B model chose "missing", then said every image used 1.24
        + (f"\nPixel size per image ({unit}/px): " + "; ".join(used[:12])
           + (f"; and {len(used) - 12} more" if len(used) > 12 else "") + "." if used else "")
        + (f"\nNOTE: {kept_own} image(s) kept their own pixel size instead of "
           f"px_to_unit={px_to_unit:g}. If the user gave one pixel size for the whole figure, "
           f"call again with px_to_unit_scope='all'." if px_to_unit is not None and kept_own else "")
        + _uncalibrated_warning(uncalibrated, unit)
    )


def _uncalibrated_warning(names: list, unit: str) -> str:
    """The bars drawn without any pixel size (1 unit per pixel): they look
    like real scales, so the reply says they are not."""
    if not names:
        return ""
    shown = ", ".join(names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")
    return (f"\nWARNING: NOT CALIBRATED — {len(names)} image(s) have no pixel size (none in the "
            f"file, none set): {shown}. Their bar is labelled in pixels (px), not {unit}. Give "
            f"their pixel size (px_to_unit, {unit} per pixel) for a {unit} scale bar.")


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
    if border_size is not None and border_size < 0:
        return f"ERROR: border_size must be 0 (no border) or more pixels (got {border_size})."
    from .core import _placement_error, _unreadable_image, _missing_image_note
    # an unknown placement ('middle-ish') was stored and drawn top right
    bad = _placement_error(placement) or _unreadable_image(inset_filename)
    if bad:
        return f"ERROR: {bad}"

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
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
        + _missing_image_note(inset_filename)
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
    # 'top_left', 'Top-Left' and 'TopLeft' mean 'top left'
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(inset_corner))
    inset_corner = " ".join(w for w in re.split(r"[\s\-_]+", spaced.strip().lower()) if w)
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
    if inset_filename is not None:
        # a missing file was taken: the callout's inset stayed empty
        from .core import _unreadable_image
        bad = _unreadable_image(inset_filename) or (
            None if os.path.isfile(inset_filename) else f"no such file: {inset_filename}")
        if bad:
            return f"ERROR: inset_filename: {bad}."
    if source_x < 0 or source_y < 0 or source_x + source_w > parent_width + 0.5 \
            or source_y + source_h > parent_height + 0.5:
        # a box beyond the image magnified a smear of edge pixels (a model gave
        # x1, y1, x2, y2 where x, y, width, height is expected)
        hint = ""
        if source_w > source_x and source_h > source_y and source_w <= parent_width \
                and source_h <= parent_height:
            hint = (f" If {source_w:g}, {source_h:g} are the opposite corner, the size is "
                    f"{source_w - source_x:g} x {source_h - source_y:g}.")
        return (f"ERROR: the zoom box (x={source_x:g}, y={source_y:g}, width={source_w:g}, "
                f"height={source_h:g}) goes outside the {parent_width:g} x {parent_height:g} px "
                f"image; the box is x, y, width, height in image pixels.{hint}")

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
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
    from ..zoom_geometry import leader_lines
    for (lx1, ly1), (lx2, ly2) in leader_lines((source_x, source_y, source_w, source_h),
                                               (ix, iy, iw, ih), connectors):
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
        + _zoom_overlap_warning(source_x, source_y, source_w, source_h,
                                parent_width, parent_height, inset_fraction, inset_corner)
    )


def _zoom_fraction_limit(box, parent_w, parent_h, corner) -> float:
    """Largest inset fraction (of the parent width) at *corner* that leaves the
    zoomed box visible: the inset must clear the box horizontally OR vertically,
    and stay inside the image."""
    bx1, by1, bx2, by2 = box
    aspect = (by2 - by1) / (bx2 - bx1)
    free_x = (parent_w - bx2) if "right" in corner else bx1
    free_y = by1 if "top" in corner else (parent_h - by2)
    fit_h = parent_h / (parent_w * aspect)            # inset taller than the image
    return max(0.0, min(1.0, fit_h, max(free_x / parent_w, free_y / (parent_w * aspect))))


def _zoom_overlap_warning(sx, sy, sw, sh, parent_w, parent_h, fraction, corner) -> str:
    """A warning (with the largest fraction / a better corner) when the inset
    covers the zoomed region: the box and leader lines disappear under it, and
    the reader no longer sees where the detail comes from."""
    box = (sx, sy, sx + sw, sy + sh)
    limit = _zoom_fraction_limit(box, parent_w, parent_h, corner)
    if fraction <= limit + 1e-9:
        return ""
    best = max(("top right", "top left", "bottom right", "bottom left"),
               key=lambda c: _zoom_fraction_limit(box, parent_w, parent_h, c))
    best_limit = _zoom_fraction_limit(box, parent_w, parent_h, best)
    hint = f"use inset_fraction <= {limit:.2f} at {corner}"
    if best != corner and best_limit > limit + 0.02:
        hint += f", or inset_corner='{best}' (up to {best_limit:.2f})"
    return (f"\nWARNING: the inset ({fraction:.2f} of the width) covers the zoomed region, so "
            f"the box and its leader lines are hidden — {hint}; or enlarge the whole panel instead.")


def _xml_crops(el) -> tuple[float, float, float, float]:
    def num(tag):
        try:
            return float(_decode(el.findtext(tag)) or 0)
        except (TypeError, ValueError):
            return 0.0
    return tuple(num(t) for t in ("crop_left", "crop_right", "crop_top", "crop_bottom"))


def _xml_raw_size(el) -> tuple[float, float] | None:
    from .core import _raw_size_from_file
    size = _raw_size_from_file(_decode(el.findtext("filename")) or None)
    if size:
        return size
    try:
        return float(_decode(el.findtext("width"))), float(_decode(el.findtext("height")))
    except (TypeError, ValueError):
        return None


def _measured_inset_corners(parent_el, annotation_index):
    """The drawn corners of annotation *annotation_index* (an inset) of the
    panel *parent_el*, in its image pixels, from a real paint; None on failure."""
    try:
        from batoolset.settings.global_settings import set_UI
        set_UI()
        from batoolset.serializations.tools import create_object, element_to_dict
        from .core import _ensure_qapp
        from ..zoom_geometry import measured_inset_corners
        _ensure_qapp()
        props = element_to_dict(parent_el)
        panel = create_object("Image2D", props.get("Image2D", props))
        corners = measured_inset_corners(panel, panel.annotations[annotation_index])
        return [(c.x(), c.y()) for c in corners] if corners else None
    except Exception:
        return None


@mcp.tool()
def connect_roi_to_inset(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    roi_index: int | None = None,
    inset_index: int | None = None,
    connectors: int = 2,
    line_color: str | int | None = None,
    stroke: float | None = None,
) -> str:
    """Join a rectangular ROI and an inset of the same panel with leader lines
    ("connect the ROI to the inset with 2 lines", "show they are the same
    region"). The lines go from the ROI corners facing the inset to the inset
    corners facing the ROI, computed from where the inset is really drawn —
    never compute the endpoints yourself and never draw them with add_roi_line.

    *roi_index*: annotation_index of the rectangle (get_annotations); omit when
    the panel has one rectangle. *inset_index*: index among the panel's insets
    (list_insets); omit when it has one. *connectors*: 1 or 2 lines.
    *line_color* / *stroke*: default to the ROI's own colour and line width.
    Leader lines already joining these two are replaced, not doubled.
    GUI: image editor → Annotations → Connect ROI ↔ inset.
    """
    from ..zoom_geometry import inset_rect, leader_lines, leader_lines_to_corners
    if connectors not in (1, 2):
        return "ERROR: connectors must be 1 or 2."
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    parent = imgs[image_index]
    annots = parent.find("annotations")
    items = list(annots) if annots is not None else []
    rects = [(i, a) for i, a in enumerate(items) if a.tag == "Rectangle2D"]
    insets = [a for a in items if a.tag == "Image2D"]
    if roi_index is not None:
        rects = [(i, a) for i, a in rects if i == roi_index]
        if not rects:
            return f"ERROR: annotation {roi_index} is not a rectangle ROI (see get_annotations)."
    if len(rects) != 1:
        return ("ERROR: " + ("this panel has no rectangle ROI." if not rects else
                f"the panel has {len(rects)} rectangle ROIs: give roi_index "
                f"(one of {[i for i, _ in rects]})."))
    if inset_index is not None:
        if not 0 <= inset_index < len(insets):
            return f"ERROR: inset_index {inset_index} out of range ({len(insets)} insets)."
        insets = [insets[inset_index]]
    if len(insets) != 1:
        return "ERROR: " + ("this panel has no inset." if not insets else
                            f"the panel has {len(insets)} insets: give inset_index (list_insets).")
    roi_i, roi = rects[0]
    inset = insets[0]

    def num(el, tag, default=0.0):
        try:
            return float(_decode(el.findtext(tag)))
        except (TypeError, ValueError):
            return default
    box = tuple(num(roi, t) for t in ("x", "y", "width", "height"))
    parent_size = _xml_raw_size(parent)
    inset_size = _xml_raw_size(inset)
    if not parent_size or not inset_size:
        return "ERROR: the image size is unknown (missing file?): the inset position cannot be computed."
    fraction = num(inset, "fraction_of_parent_image_width_if_image_is_inset", 0.25)
    where = inset_rect(parent_size, _xml_crops(parent), inset_size, _xml_crops(inset),
                       fraction, inset.findtext("placement") or "top right")
    lines = leader_lines(box, where, connectors)
    if num(parent, "theta", 0.0):
        # a rotated panel: ROIs turn with the image, the inset stays upright —
        # measured on a real paint of the panel
        corners = _measured_inset_corners(parent, items.index(inset))
        if corners:
            xs, ys = [c[0] for c in corners], [c[1] for c in corners]
            where = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
            lines = leader_lines_to_corners(box, corners, connectors)
    color = _color_to_int(line_color) if line_color is not None else int(num(roi, "color", 0xFFFF00))
    width = float(stroke) if stroke is not None else num(roi, "stroke", 1.5) or 1.5

    # earlier leaders between these two (one end on the ROI, the other on the inset) go
    def on_rect(x, y, r, tol=2.0):
        rx, ry, rw, rh = r
        inside = rx - tol <= x <= rx + rw + tol and ry - tol <= y <= ry + rh + tol
        return inside and min(abs(x - rx), abs(x - rx - rw), abs(y - ry), abs(y - ry - rh)) <= tol
    removed = 0
    for a in list(items):
        if a.tag != "Line2D":
            continue
        p1 = (num(a, "x1"), num(a, "y1"))
        p2 = (num(a, "x2"), num(a, "y2"))
        if (on_rect(*p1, box) and on_rect(*p2, where)) or (on_rect(*p2, box) and on_rect(*p1, where)):
            annots.remove(a)
            removed += 1
    # before the inset, so the inset is drawn over their ends
    pos = list(annots).index(inset)
    for k, ((x1, y1), (x2, y2)) in enumerate(lines):
        annots.insert(pos + k, _new_roi_line(x1, y1, x2, y2, color, width, 1.0, False, False))
    _save(tree, pyf_path)
    ends = "; ".join(f"({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f})" for (x1, y1), (x2, y2) in lines)
    return (f"{len(lines)} leader line(s) join ROI {roi_i} and the inset (drawn at x={where[0]:.0f}, "
            f"y={where[1]:.0f}, {where[2]:.0f}×{where[3]:.0f} px): {ends}."
            + (f" Replaced {removed} earlier line(s) between them." if removed else ""))


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
    if not 0 <= image_index < len(imgs):
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
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    insets = _get_insets(imgs[image_index])
    if not 0 <= inset_index < len(insets):
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
    value: str | int | float | bool | list | None,
) -> str:
    """Set any property on an inset Image2D.

    Insets share the same field schema as regular panels, so all the same
    property names apply.  Common use cases:

    ┌──────────────────────────────────────────────┬──────────────────────────┐
    │ property_name                                │ example value            │
    ├──────────────────────────────────────────────┼──────────────────────────┤
    │ size_fraction (inset width / parent width)   │ "0.3"  (0 < f <= 1)      │
    │ placement                                    │ "bottom left"            │
    │ border_size                                  │ "5"                      │
    │ border_color                                 │ "16776960"  (yellow)     │
    │ filename                                     │ "/new/path/detail.png"   │
    │ crop_left / crop_right / crop_top / crop_bottom │ "20" (px cut away    │
    │   from that EDGE, not a coordinate: x 275-375 of │  a 650 px image =   │
    │   a 650 px wide image is left 275, right 275)    │  left 275 right 275) │
    │ opacity                                      │ "0.8"                    │
    │ LUTs                                         │ "['GREEN', None, None]"  │
    │ theta                                        │ "45"                     │
    └──────────────────────────────────────────────┴──────────────────────────┘

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index of the parent panel.
    *inset_index*: 0-based index among the insets (from list_insets()).
    *property_name*: a field name as returned by list_insets() (e.g.
    size_fraction) or the exact XML tag name. An unknown name is rejected and
    nothing is changed.
    *value*: new value as a string — auto-encoded (see set_image_property docs).

    The change is saved immediately; the reply gives the value read back from
    the saved file.
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
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    insets = _get_insets(imgs[image_index])
    if not 0 <= inset_index < len(insets):
        return f"ERROR: inset_index {inset_index} out of range ({len(insets)} insets)."
    property_name, err = _resolve_image_property(insets[inset_index], property_name)
    if err:
        return err
    if property_name in _LAYOUT_FIELDS:
        return (
            f"ERROR: '{property_name}' is a layout field managed by PyFigures — "
            "do not set it directly on an inset."
        )

    # placement is a Position object — serialised by PyFigures as a plain string
    # (no ""..."" wrapping).  filename always needs the double-quote wrapping.
    # Everything else goes through the smart encoder.
    if property_name == "placement":
        raw = str(value).strip()
        from .core import _placement_error
        bad = _placement_error(raw)
        if bad:
            return f"ERROR: {bad}"
    elif property_name == "filename":
        raw = _encode_str(str(value))
    else:
        raw = _encode_value(value)
    err = _check_property_value(property_name, raw)
    if err:
        return err
    _set_child_text(insets[inset_index], property_name, raw)
    if property_name.startswith("crop_"):
        # crops are margins cut from each side, not coordinates: a model set
        # crop_right=375 meaning "up to x 375" next to crop_left=275 on a
        # 650 px image, and the inset became 0 px wide, invisible (2026-11-06).
        # The same check as set_image_property / transform_image.
        from .core import _crop_fit_error
        crop_err = _crop_fit_error(insets[inset_index])
        if crop_err:
            return (f"ERROR: {crop_err} For an inset made from an ROI: move/resize the ROI, then "
                    "remove_inset and roi_to_inset again. "
                    "Nothing was changed.")
    _save(tree, pyf_path)
    stored = _stored_image_property(pyf_path, group_path, image_index, property_name,
                                    inset_index=inset_index)
    loc = "canvas" if not group_path else f"group {group_path}"
    return (
        f"Inset {inset_index} on image {image_index} in {loc}: "
        f"{property_name} = {stored} (read back from the saved file)"
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

    grp_orient = (_child_text(grp, "orientation") or "X").upper()
    # Resolve labels list
    if isinstance(labels, str):
        labels_list = [labels]
    else:
        labels_list = list(labels)
        if grp_orient == "Y" and len(labels_list) != 1:
            # the GUI gives a column one header (associate_text_row)
            return ("ERROR: group is a column (vertical): a label row above or below it "
                    "holds one header — pass a single string.")
        if grp_orient != "Y" and len(labels_list) != non_label_count:
            return (
                f"ERROR: {non_label_count} non-label children in the group but "
                f"{len(labels_list)} label(s) supplied. "
                "Provide one label per child, or a single string for a spanning header."
            )

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
        # always a row, as the GUI builds it: a vertical label row's layout
        # divided by zero and sent every panel below it to y = 1e30
        ("orientation", _encode_str("X")),
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
    # the row is a top-level group of its own: every later group moved one index
    first_moved = group_path[0] + (0 if position == "above" else 1)
    target_now = group_path[0] + (1 if position == "above" else 0)
    return (
        f"Label row added {position} {loc} (new path {new_label_path}): "
        f"{texts_preview}. Top-level groups from [{first_moved}] on moved down one "
        f"index (the labelled group is now [{target_now}]); use the new paths."
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
    from .core import _html_to_plain
    # an empty label still takes a strip of the row (a blank gap)
    if not _html_to_plain(str(label or "")).strip():
        return "ERROR: label is empty: give the text to show beside the group."

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
    # a side label is a narrow strip beside the panels, not a 512 x 256 cell:
    # with that placeholder the label took the whole row width and, with no
    # spacing to absorb the rounding, the layout divided by zero
    across = "width" if resolved_orient.startswith("vertical") else "height"
    _set_child_text(label_img, across, "15.0")

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
