"""PyFigures MCP tools — Poster designer tools.

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

# ---------------------------------------------------------------------------
# poster / collage designer (.pyfposter) — separate tool, separate file format
# ---------------------------------------------------------------------------
# The poster designer (pyfigures/poster/) is a distinct tool from the scientific
# figure editor above: free rotation/positioning for posters and photo-album
# pages, not tight scientific packing. It has its own file format (.pyfposter)
# and shares no state with .pyf. Like figure rendering, every edit needs Qt, so
# it runs in a short subprocess via pyfigures/poster/poster_headless.py
# (mirrors _run_render / _run_headless_ops above) — keeps this server Qt-free
# and isolates any Qt crash to the child process.
_POSTER_FRAME_STYLES = ("none", "simple", "polaroid")


def _run_poster_op(op_args: list[str], timeout: int = 120):
    """Run one poster_headless.py subcommand. Returns (ok, parsed_json_or_message)."""
    cmd = [sys.executable, "-m", "pyfigures.poster.poster_headless", *op_args]
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_API", "pyqt6")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"poster operation timed out after {timeout}s"
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or \
            f"poster_headless exited with code {proc.returncode}"
        return False, msg
    try:
        return True, json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return False, f"poster_headless produced unparsable output: {proc.stdout!r}"


def _poster_result(ok, payload):
    if not ok:
        return f"ERROR: {payload}"
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
def create_poster(poster_path: str, page_preset: str | None = "A4",
                  page_width_mm: float | None = None, page_height_mm: float | None = None,
                  album: bool = False) -> str:
    """Create a new, empty poster/collage page (.pyfposter) — the poster
    designer's own free-placement canvas, unrelated to .pyf scientific figures —
    or, with album=True, a new photo album (.pyfalbum).

    Use this to start a poster or decorative collage: images added afterwards
    (add_poster_image) can be freely positioned and rotated without
    cropping, unlike panels in the scientific figure editor.

    *album*: True makes a photo album instead — the photo album designer's
    document: a pinned front cover (page 0), one two-page spread (page 1)
    and a pinned back cover (page 2). add_poster_page then only adds spreads
    between the covers, and the covers can't be removed, moved, duplicated
    or re-kinded. *poster_path* must end in .pyfalbum and must not exist yet:
    a photo album is only ever created as one, an existing poster is never
    converted (build_poster_from_recipe with `album: true` also makes one).

    *page_preset* is one of A4 (default)/A3/A2/A1/A0 (portrait, ISO mm sizes);
    pass explicit page_width_mm/page_height_mm instead for a custom size (a
    spread is twice that width).
    Returns the new document's page size and (empty) image list as JSON.
    """
    args = ["create", poster_path]
    if album:
        args.append("--album")
    if page_width_mm is not None and page_height_mm is not None:
        args += ["--page-width", str(page_width_mm), "--page-height", str(page_height_mm)]
    elif page_preset:
        args += ["--preset", page_preset]
    return _poster_result(*_run_poster_op(args))


_POSTER_PAGE_KINDS = ("single", "spread", "cover_front", "cover_back")


@mcp.tool()
def add_poster_page(poster_path: str, kind: str = "spread",
                    width_mm: float | None = None, height_mm: float | None = None,
                    index: int | None = None) -> str:
    """Add a page to a poster document, turning it into a multi-page photo
    album (see docs/poster.md) the moment it has more than one page — a
    document starts as one plain page (.pyfposter) and is automatically
    saved as .pyfalbum from then on, same tool calls either way.

    *kind*: "spread" (default — two physical pages designed as one
    continuous canvas, so a photo/text box can freely cross the gutter,
    shown as a light guide line; defaults to double the document's own page
    width), "cover_front"/"cover_back" (a single physical page, same tooling
    as any other page — just conventionally first/last), or "single" (a
    plain extra page). Pass width_mm/height_mm to override the default size.

    *index* inserts at that position (0-based); omit it to insert right
    after the current last page. Returns the whole updated page list
    (see list_poster_pages) as JSON.
    """
    if kind not in _POSTER_PAGE_KINDS:
        return f"ERROR: unknown kind {kind!r}; use one of {_POSTER_PAGE_KINDS}"
    args = ["add-page", poster_path, "--kind", kind]
    if width_mm is not None:
        args += ["--width", str(width_mm)]
    if height_mm is not None:
        args += ["--height", str(height_mm)]
    if index is not None:
        args += ["--index", str(index)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def list_poster_pages(poster_path: str) -> str:
    """List every page of a poster document — index, kind ("single"/
    "spread"/"cover_front"/"cover_back"), width_mm/height_mm, shape_count,
    has_background — as JSON. Use this to see a photo album's whole
    structure at once; list_poster_images gives the full shape detail for
    just one page.
    """
    return _poster_result(*_run_poster_op(["list-pages", poster_path]))


@mcp.tool()
def remove_poster_page(poster_path: str, page: int) -> str:
    """Delete page *page* (0-based, see list_poster_pages) from a poster
    document. Errors if it's the last remaining page — a document always
    keeps at least one. Returns the updated page list as JSON."""
    return _poster_result(*_run_poster_op(["remove-page", poster_path, str(page)]))


@mcp.tool()
def duplicate_poster_page(poster_path: str, page: int) -> str:
    """Copy page *page* (0-based, see list_poster_pages) — background and
    every shape independently re-created, not a live/shared reference — into
    a new page right after it. Handy as a starting template for the next
    spread in an album. Returns the updated page list as JSON."""
    return _poster_result(*_run_poster_op(["duplicate-page", poster_path, str(page)]))


@mcp.tool()
def move_poster_page(poster_path: str, from_index: int, to_index: int) -> str:
    """Reorder a poster document's pages — move the page at *from_index* to
    *to_index* (both 0-based, see list_poster_pages). Returns the updated
    page list as JSON."""
    return _poster_result(*_run_poster_op(["move-page", poster_path, str(from_index), str(to_index)]))


@mcp.tool()
def set_poster_page_kind(poster_path: str, page: int, kind: str) -> str:
    """Change page *page*'s (0-based, see list_poster_pages) kind after the
    fact — e.g. turn a plain page into a "cover_front"/"cover_back", or a
    "spread"/"single". Only the kind changes; width_mm/height_mm and its
    content are untouched (resize with add_poster_page's width_mm/height_mm
    at creation time, or move/duplicate/remove and re-add if you need a
    different size). Returns the updated page list as JSON."""
    if kind not in _POSTER_PAGE_KINDS:
        return f"ERROR: unknown kind {kind!r}; use one of {_POSTER_PAGE_KINDS}"
    return _poster_result(*_run_poster_op(["set-page-kind", poster_path, str(page), kind]))


@mcp.tool()
def add_poster_image(poster_path: str, image_path: str,
                     x_mm: float | None = None, y_mm: float | None = None,
                     width_mm: float | None = None, height_mm: float | None = None,
                     theta: float = 0.0, frame: str = "none", caption: str | None = None,
                     page: int | None = None) -> str:
    """Add one photo to a poster page, freely positioned and rotated.

    *image_path* may also be a .pyf scientific figure: it is flattened to an
    image (exactly like dropping it in the poster GUI) and remembered, so
    export_poster_source_data nests that figure's own source-data bundle.

    Rotation (theta, degrees) grows the image's bounding box instead of
    cropping it — the whole photo stays visible, tilted, which is the opposite
    of how the scientific figure editor rotates panels. Leave x_mm/y_mm to
    center it on the page, and width_mm/height_mm to keep its natural aspect
    ratio scaled to fit.

    *frame* is "none" (default), "simple" (thin white border) or "polaroid"
    (thick border with a caption strip below — old-photo look); *caption* is
    the text shown in a polaroid's strip (ignored for other frames).

    *page* picks which page of a multi-page album to add to (0-based, see
    list_poster_pages); omit it for a plain single-page poster, or to target
    page 0 of an album.

    Returns the new image's index (0-based, in front-to-back paint order —
    later additions draw on top) plus its geometry, as JSON. Use that index
    with remove_poster_image / set_poster_image_frame / the arrange_poster_*
    tools' `indices` argument.
    """
    if frame not in _POSTER_FRAME_STYLES:
        return f"ERROR: unknown frame {frame!r}; use one of {_POSTER_FRAME_STYLES}"
    args = ["add-image", poster_path, image_path, "--theta", str(theta), "--frame", frame]
    if x_mm is not None:
        args += ["--x", str(x_mm)]
    if y_mm is not None:
        args += ["--y", str(y_mm)]
    if width_mm is not None:
        args += ["--width", str(width_mm)]
    if height_mm is not None:
        args += ["--height", str(height_mm)]
    if caption:
        args += ["--caption", caption]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


_POSTER_TEXT_STYLES = ("h1", "h2", "h3", "body", "caption")


@mcp.tool()
def add_poster_text(poster_path: str, html: str | None = None, style: str = "body",
                    x_mm: float | None = None, y_mm: float | None = None,
                    width_mm: float | None = None, height_mm: float | None = None,
                    theta: float = 0.0, page: int | None = None) -> str:
    """Add a freely positioned/rotated text box to a poster page — titles,
    captions, labels floating on the page (as opposed to add_poster_image's
    photos).

    *html* is the text content, either plain ('Poster Title') or simple HTML
    for formatting, e.g. '<span style="font-size:36pt"><b>My Poster</b></span>'
    or '<i>subtitle</i>'; leave it out to use the chosen *style*'s own
    placeholder wording (e.g. "Heading 1"). Leave x_mm/y_mm to center it on
    the page.

    *style* is one of "h1" (biggest, a poster title), "h2", "h3", "body"
    (default) or "caption" (smallest) — like a Markdown heading level, it
    sets the box's default size as a *fraction of the page height* rather
    than a fixed point size, so "h1" comes out proportionally just as big on
    an A0 poster as on an A4 page. Overridden by width_mm/height_mm if given.

    Unlike an image, the box has no crop; the box's aspect ratio always
    matches what the text naturally lays out at (font scales with the box),
    same as resizing it by a corner handle in the GUI.

    To change the wording afterwards, use remove_poster_image (it deletes by
    index regardless of shape kind, despite the name) and add a new text box
    in its place — there is no in-place text edit from the MCP side (the
    rich-text editor is GUI-only, see docs/poster.md).

    *page* picks which page of a multi-page album to add to (0-based, see
    list_poster_pages); omit it for a plain single-page poster, or to target
    page 0 of an album.

    Returns the new text box's index (0-based) plus its geometry as JSON —
    same indices as images, shared with remove_poster_image (works for any
    shape) and the arrange_poster_*/apply_poster_layout `indices` argument.
    """
    if style not in _POSTER_TEXT_STYLES:
        return f"ERROR: unknown style {style!r}; use one of {_POSTER_TEXT_STYLES}"
    args = ["add-text", poster_path, "--style", style, "--theta", str(theta)]
    if html is not None:
        args.insert(2, html)
    if x_mm is not None:
        args += ["--x", str(x_mm)]
    if y_mm is not None:
        args += ["--y", str(y_mm)]
    if width_mm is not None:
        args += ["--width", str(width_mm)]
    if height_mm is not None:
        args += ["--height", str(height_mm)]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def set_poster_background(poster_path: str, image_path: str,
                          zoom: float | None = None,
                          pan_x: float | None = None, pan_y: float | None = None,
                          page: int | None = None) -> str:
    """Fill the whole poster page with a background image (cropped to cover,
    never rotated) — e.g. a texture or backdrop behind the arranged photos.
    Replaces any existing background. Use clear_poster_background to remove it.

    In the GUI the background can also be dragged to reposition (crop) it and
    scroll-wheeled to zoom in tighter; *zoom* (>=1.0, default 1.0 = the
    tightest crop-free fit) and *pan_x*/*pan_y* (0..1, default 0.5 = centered)
    let you set the same crop/position from here. Use adjust_poster_background
    to change these later without replacing the image.

    *page* picks which page of a multi-page album to set (0-based, see
    list_poster_pages); omit it for a plain single-page poster."""
    args = ["set-background", poster_path, image_path]
    if zoom is not None:
        args += ["--zoom", str(zoom)]
    if pan_x is not None:
        args += ["--pan-x", str(pan_x)]
    if pan_y is not None:
        args += ["--pan-y", str(pan_y)]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def adjust_poster_background(poster_path: str, zoom: float | None = None,
                             pan_x: float | None = None, pan_y: float | None = None,
                             reset: bool = False, page: int | None = None) -> str:
    """Change the crop/position of the poster's existing background image
    (zoom >= 1.0, pan_x/pan_y 0..1 fractions, 0.5 = centered) without
    replacing it. Set reset=True to put it back to centered/no-zoom.
    *page* targets one page of a multi-page album (0-based)."""
    args = ["adjust-background", poster_path]
    if zoom is not None:
        args += ["--zoom", str(zoom)]
    if pan_x is not None:
        args += ["--pan-x", str(pan_x)]
    if pan_y is not None:
        args += ["--pan-y", str(pan_y)]
    if reset:
        args += ["--reset"]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def clear_poster_background(poster_path: str, page: int | None = None) -> str:
    """Remove the poster page's background image, if any. *page* targets one
    page of a multi-page album (0-based)."""
    args = ["clear-background", poster_path]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def remove_poster_image(poster_path: str, index: int, page: int | None = None) -> str:
    """Delete one image from a poster page by its index (see list_poster_images).
    *page* targets one page of a multi-page album (0-based). Returns the
    updated document (images re-indexed from 0) as JSON."""
    args = ["remove-image", poster_path, str(index)]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def set_poster_image_frame(poster_path: str, index: int,
                           frame: str | None = None, caption: str | None = None,
                           page: int | None = None) -> str:
    """Change one poster image's frame style and/or caption after the fact.

    *frame*: "none", "simple", or "polaroid" (leave unset to keep the current
    frame). *caption* sets the text in a polaroid's caption strip; pass an
    empty string to clear it (leave unset to keep the current caption).
    *page* targets one page of a multi-page album (0-based).
    """
    if frame is not None and frame not in _POSTER_FRAME_STYLES:
        return f"ERROR: unknown frame {frame!r}; use one of {_POSTER_FRAME_STYLES}"
    args = ["set-frame", poster_path, str(index)]
    if frame is not None:
        args += ["--frame", frame]
    if caption is not None:
        args += ["--caption", caption]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def list_poster_images(poster_path: str, page: int | None = None) -> str:
    """Inventory a poster page: page size, background (if any), and every
    shape's index/position/size/rotation/group_id, as JSON — one entry per
    photo (add_poster_image) or text box (add_poster_text), distinguished by
    `kind` ("image" has path/frame/caption/is_template/crop_*, "text" has
    html instead). Also reports page_index/page_count/page_kind — see
    list_poster_pages for the whole document's page list at once.

    *page* picks which page of a multi-page album to inspect (0-based);
    omit it for a plain single-page poster, or to inspect page 0 of an album.

    Use this before arrange_poster_scatter/arc/grid to know how many shapes
    there are and pick which `indices` to target, or after arranging to see
    the resulting geometry. `is_template` (true/false, images only) marks an
    empty slot from sketch_poster_layout still waiting for a real photo — see
    fill_poster_template_slot. `group_id` is shared by images placed together
    by one apply_poster_layout/sketch_poster_layout call (null if ungrouped)
    — see ungroup_poster_images.
    """
    args = ["list", poster_path]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def arrange_poster_scatter(poster_path: str, indices: str | None = None,
                           seed: int | None = None, margin_mm: float = 15.0,
                           max_rotation_deg: float = 25.0, fit_to_page: bool = True,
                           page: int | None = None) -> str:
    """Scatter images across the page like photos thrown on a table: each
    targeted image gets a random position (within margin_mm of the page edge)
    and a random tilt in [-max_rotation_deg, +max_rotation_deg]. Overlap is
    expected — that's the look. Re-run with a different seed for a different
    throw, or the same seed to reproduce one.

    *indices* is a comma-separated list like "0,2,3" to scatter only those
    images (see list_poster_images); omit it to scatter every image on the page.

    By default (*fit_to_page*) a throw where rotation pushes a corner past the
    page edge is shrunk back to fit as a whole group — a throw that already
    lands cleanly is left untouched, so this never changes a "good" throw.
    Set fit_to_page=False to allow images to bleed past the edge.
    """
    args = ["arrange-scatter", poster_path, "--margin", str(margin_mm),
            "--max-rotation", str(max_rotation_deg)]
    if seed is not None:
        args += ["--seed", str(seed)]
    if indices:
        args += ["--indices", indices]
    if not fit_to_page:
        args += ["--no-fit"]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def arrange_poster_arc(poster_path: str, center_x_mm: float, center_y_mm: float, radius_mm: float,
                       indices: str | None = None, start_angle_deg: float = -60.0,
                       end_angle_deg: float = 60.0, face: str = "outward",
                       fit_to_page: bool = True, page: int | None = None) -> str:
    """Fan images out along a circular arc — a spread hand of photographs or
    playing cards. Angle 0 points straight up from (center_x_mm, center_y_mm);
    the fan sweeps clockwise from start_angle_deg to end_angle_deg, images
    evenly spaced across that sweep.

    *face* controls each image's own rotation: "outward" (default, classic fan
    — each image's top points away from the arc's center), "inward" (top points
    toward the center), or "none" (images stay upright, only position moves).
    *indices* is a comma-separated list like "0,2,3" to arrange a subset (see
    list_poster_images); omit it to arrange every image on the page.

    By default (*fit_to_page*) the whole fan is rescaled and recentered
    afterwards so every image ends up fully on the page, whatever
    center/radius/angles you passed — you don't need to hand-tune the geometry
    to avoid images hanging off the edge. Set fit_to_page=False to get the
    fan exactly as geometrically specified (useful for a deliberate bleed).
    """
    if face not in ("outward", "inward", "none"):
        return "ERROR: face must be one of 'outward', 'inward', 'none'"
    args = ["arrange-arc", poster_path, "--center-x", str(center_x_mm),
            "--center-y", str(center_y_mm), "--radius", str(radius_mm),
            "--start-angle", str(start_angle_deg), "--end-angle", str(end_angle_deg),
            "--face", face]
    if indices:
        args += ["--indices", indices]
    if not fit_to_page:
        args += ["--no-fit"]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def arrange_poster_grid(poster_path: str, indices: str | None = None, columns: int | None = None,
                        margin_mm: float = 15.0, gap_mm: float = 6.0, fit_to_page: bool = True,
                        page: int | None = None) -> str:
    """Lay images out in a tidy grid: rotation reset to 0, each image resized
    (aspect ratio preserved) to fill its cell. The sane, orderly baseline —
    good as a starting point, or to recover from an arrangement that scattered
    or fanned too chaotically.

    *columns* picks the column count (default: roughly page-aspect-matched).
    *indices* is a comma-separated list like "0,2,3" to arrange a subset (see
    list_poster_images); omit it to arrange every image on the page.

    Grid cells are already sized to fit the page, so *fit_to_page* (default
    on) is mostly a safety net; set it False to skip that final check.
    """
    args = ["arrange-grid", poster_path, "--margin", str(margin_mm), "--gap", str(gap_mm)]
    if columns is not None:
        args += ["--columns", str(columns)]
    if indices:
        args += ["--indices", indices]
    if not fit_to_page:
        args += ["--no-fit"]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


_POSTER_ALIGN_MODES = ("left", "right", "top", "bottom", "center_h", "center_v")


@mcp.tool()
def align_poster_shapes(poster_path: str, mode: str, indices: str | None = None,
                        page: int | None = None) -> str:
    """Align shapes on a poster page to each other — same idea as PowerPoint/
    Illustrator's align tools, and the GUI's Align toolbar button.

    *mode* is one of "left"/"right"/"top"/"bottom" (every targeted shape's
    matching edge moves onto the group's own extreme edge) or "center_h"/
    "center_v" (every shape's center moves onto the horizontal/vertical
    center of the group's overall bounding box).

    *indices* is a comma-separated list like "0,2,3" (see list_poster_images)
    to align a subset; omit it to align every shape on the page. Needs at
    least 2 targeted shapes.
    """
    if mode not in _POSTER_ALIGN_MODES:
        return f"ERROR: unknown mode {mode!r}; use one of {_POSTER_ALIGN_MODES}"
    args = ["align-shapes", poster_path, "--mode", mode]
    if indices:
        args += ["--indices", indices]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def distribute_poster_shapes(poster_path: str, axis: str, indices: str | None = None,
                             page: int | None = None) -> str:
    """Evenly space shapes on a poster page — same idea as PowerPoint/
    Illustrator's distribute tools, and the GUI's Distribute toolbar button.

    Sorts the targeted shapes along *axis* ("x" or "y") and spaces their
    centers evenly between the two extreme ones, which stay put — sensible
    even when the shapes are different sizes.

    *indices* is a comma-separated list like "0,2,3" (see list_poster_images)
    to distribute a subset; omit it to distribute every shape on the page.
    Needs at least 3 targeted shapes (nothing to redistribute with only 2).
    """
    if axis not in ("x", "y"):
        return "ERROR: axis must be 'x' or 'y'"
    args = ["distribute-shapes", poster_path, "--axis", axis]
    if indices:
        args += ["--indices", indices]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def list_poster_layouts() -> str:
    """List the pre-designed page layouts ("templates") available for
    apply_poster_layout — the poster module's answer to picking a slide
    layout in PowerPoint, or the main editor's Template feature, but as a
    ready-made gallery instead of a save/fill round-trip.

    Each entry has: name (pass to apply_poster_layout), label, description,
    and slot_count (how many photos it expects — e.g. "big_plus_three_side"
    has slot_count 4: one large photo + three small ones). Use slot_count to
    pick a layout that matches how many images you have.
    """
    return _poster_result(*_run_poster_op(["list-layouts"]))


@mcp.tool()
def apply_poster_layout(poster_path: str, layout_name: str, indices: str | None = None,
                        margin_mm: float = 15.0, repeat: bool = True, group: bool = True,
                        page: int | None = None) -> str:
    """Fill a pre-designed layout with the photos already on a poster page —
    pick a layout (see list_poster_layouts), and every targeted image is
    dropped into one of its slots in one call, instead of positioning each
    image by hand.

    Images fill slots in order — page z-order, or the given *indices* subset
    (comma-separated like "0,2,3") — each resized (aspect ratio preserved,
    never stretched) to fit inside its slot and centered there. A couple of
    layouts (e.g. "magazine_collage") give slots a slight tilt for a
    scrapbook feel — that's part of the layout, not something you control
    per call.

    If you have more images than the layout has slots: by default (*repeat*)
    the layout repeats in horizontal bands stacked down the page — enough
    bands to place every image, the pattern continuing rather than leaving
    the rest wherever they were. The last band may be partially filled if the
    count isn't an exact multiple of the slot count. Set repeat=False to only
    fill the first slots and leave any extra images untouched instead. With
    fewer images than slots, only the first slots get filled either way.

    By default (*group*) every placed image is grouped, so in the GUI
    dragging any one of them moves the whole composition together (no
    auto-alignment — each image keeps its own size/rotation, only their
    shared position moves). Set group=False to leave them ungrouped. See
    also ungroup_poster_images.
    """
    args = ["apply-layout", poster_path, layout_name, "--margin", str(margin_mm)]
    if indices:
        args += ["--indices", indices]
    if not repeat:
        args += ["--no-repeat"]
    if not group:
        args += ["--no-group"]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def sketch_poster_layout(poster_path: str, layout_name: str, margin_mm: float = 15.0,
                         group: bool = True, page: int | None = None) -> str:
    """Sketch a pre-designed layout (see list_poster_layouts) as empty
    placeholder slots — no photos needed yet. Each slot is shown (in the GUI)
    as a dashed grey box until filled. This is the poster module's version of
    the main editor's templatify_figure/fill_template workflow, but built
    forwards: lay the page out first, decide which photo goes where later.

    Fill slots afterwards one at a time with fill_poster_template_slot, or in
    the GUI by dragging an image onto a slot. By default (*group*) all
    sketched slots share one group, so in the GUI dragging any slot (filled
    or not) moves the whole sketch together; set group=False to leave them
    ungrouped. Returns the updated document (list_poster_images) as JSON —
    filled/unfilled slots are distinguished by each image's `is_template` field.
    """
    args = ["sketch-layout", poster_path, layout_name, "--margin", str(margin_mm)]
    if not group:
        args += ["--no-group"]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def fill_poster_template_slot(poster_path: str, index: int, image_path: str,
                              page: int | None = None) -> str:
    """Fill one empty template slot (see sketch_poster_layout / the
    `is_template` field from list_poster_images) with a real photo.

    The image is fit inside the slot's existing box — aspect ratio preserved,
    centered, never stretched — so its rectangle may shrink slightly from the
    sketched size if the photo's aspect ratio differs. Errors if *index* isn't
    currently an empty template slot (use set_poster_image_frame or
    remove_poster_image/add_poster_image for an already-filled image instead).
    *page* targets one page of a multi-page album (0-based).
    """
    args = ["fill-slot", poster_path, str(index), image_path]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def ungroup_poster_images(poster_path: str, index: int, page: int | None = None) -> str:
    """Break apart the group that image *index* belongs to (from
    apply_poster_layout/sketch_poster_layout with group=True) so its members
    go back to moving independently in the GUI. No-op if that image isn't
    grouped. Sizes/positions/rotations are unchanged — only the shared-drag
    link is removed. *page* targets one page of a multi-page album (0-based)."""
    args = ["ungroup", poster_path, str(index)]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def render_poster(poster_path: str, out_path: str, dpi: int = 300, page: int | None = None) -> str:
    """Render one page of a poster/album to a final image file — the
    shippable deliverable for that page. For a multi-page photo album's
    whole book as one multi-page PDF, use render_poster_album instead.

    *out_path* extension selects the format: raster (.png/.tif/.tiff/.jpg) at
    *dpi* resolution, or vector (.svg/.pdf, dpi ignored). *page* picks which
    page to render (0-based, see list_poster_pages); omit it for a plain
    single-page poster, or to render page 0 of an album. Returns the absolute
    output path as JSON. To preview without writing a permanent file, use
    preview_poster.
    """
    args = ["render", poster_path, out_path, "--dpi", str(int(dpi))]
    if page is not None:
        args += ["--page", str(page)]
    ok, payload = _run_poster_op(args)
    return _poster_result(ok, payload)


@mcp.tool()
def render_poster_album(poster_path: str, out_path: str, dpi: int = 300) -> str:
    """Render every page of a multi-page photo-album document as one
    multi-page PDF — front cover, every interior spread, back cover, each
    sized to its own page (a spread becomes one double-width PDF page, the
    print convention for a photobook spread). For a single page instead
    (including a plain one-page poster), use render_poster.

    Returns the absolute output path and page_count as JSON.
    """
    ok, payload = _run_poster_op(["render-album", poster_path, out_path, "--dpi", str(int(dpi))])
    return _poster_result(ok, payload)


@mcp.tool()
def preview_poster(poster_path: str, dpi: int = 100, max_dimension: int = 1400,
                   page: int | None = None) -> Image:
    """Render one page of a poster/album to a PNG and return it as an image
    you can see — for checking layout/arrangement while composing, without
    writing a permanent file. *page* picks which page (0-based, see
    list_poster_pages); omit it for a plain single-page poster, or page 0 of
    an album. For the final deliverable use render_poster / render_poster_album.
    """
    if not os.path.isfile(poster_path):
        raise ValueError(f"no such poster file: {poster_path}")
    tmp = os.path.join(tempfile.mkdtemp(prefix="poster_preview_"), "preview.png")
    render_args = ["render", poster_path, tmp, "--dpi", str(int(dpi))]
    if page is not None:
        render_args += ["--page", str(page)]
    ok, payload = _run_poster_op(render_args)
    if not ok:
        raise RuntimeError(f"could not render poster preview: {payload}")

    from PIL import Image as PILImage
    im = PILImage.open(tmp)
    im.load()
    if max(im.size) > max_dimension:
        im.thumbnail((max_dimension, max_dimension), PILImage.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGBA").save(buf, format="PNG")
    return Image(data=buf.getvalue(), format="png")


@mcp.tool()
def export_poster_print_ready(poster_path: str, out_path: str, format: str = "tiff",
                              color_mode: str = "cmyk", dpi: int = 300,
                              page: int | None = None) -> str:
    """Print-ready export of one page of a poster/album — for a whole
    multi-page document at once, use export_poster_album_print_ready
    instead.

    *format* is "tiff"/"eps" (raster, naive non-colour-managed RGB->CMYK
    conversion when *color_mode*="cmyk" — no ICC profile, fine for
    layout/proofing, not colour-critical print) or "pdf"/"svg" (vector,
    always RGB — Qt has no CMYK writer for either, *color_mode* is ignored).
    *page* picks which page (0-based, see list_poster_pages); omit it for a
    plain single-page poster. Returns the output path/format/dpi as JSON.
    """
    format = format.lower()
    if format not in ("tiff", "eps", "pdf", "svg"):
        return "ERROR: format must be one of tiff/eps/pdf/svg"
    if color_mode.lower() not in ("cmyk", "rgb"):
        return "ERROR: color_mode must be 'cmyk' or 'rgb'"
    args = ["print-current-page", poster_path, out_path, "--format", format,
            "--color-mode", color_mode.lower(), "--dpi", str(int(dpi))]
    if page is not None:
        args += ["--page", str(page)]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def export_poster_album_print_ready(poster_path: str, out_path: str, format: str = "tiff",
                                    color_mode: str = "cmyk", dpi: int = 300) -> str:
    """Print-ready export of the WHOLE poster/album document (every page,
    front cover through back cover) — for one page only, use
    export_poster_print_ready instead.

    *format*="pdf" writes a single multi-page vector file at *out_path*
    (color_mode ignored, Qt's PDF writer is RGB-only). *format* "tiff"/"eps"/
    "svg" have no standard multi-page container print software reliably
    accepts, so *out_path* is instead treated as a folder: one numbered file
    per page (page_01_<kind>.<ext>, cmyk for tiff/eps if requested) plus a
    manifest.json. Returns JSON describing what was written.
    """
    format = format.lower()
    if format not in ("tiff", "eps", "pdf", "svg"):
        return "ERROR: format must be one of tiff/eps/pdf/svg"
    if color_mode.lower() not in ("cmyk", "rgb"):
        return "ERROR: color_mode must be 'cmyk' or 'rgb'"
    args = ["print-album", poster_path, out_path, "--format", format,
            "--color-mode", color_mode.lower(), "--dpi", str(int(dpi))]
    return _poster_result(*_run_poster_op(args))


@mcp.tool()
def export_poster_source_data(poster_path: str, out_dir: str, dpi: int = 300) -> str:
    """Assemble a **Source Data bundle** for a poster/album — the consolidation
    equivalent of export_source_data, but for a whole poster/photo-album
    document instead of one .pyf figure.

    Writes *out_dir* containing:
      * ``<name>.pyfposter``/``.pyfalbum`` — a portable copy of the document
        whose image/background paths point at the copies below, so the
        bundle reopens standalone;
      * ``images/`` — every page's background/image files, copied and
        renamed by page + shape index (``p01_s00__photo.jpg``, ...);
      * ``manifest.json`` / ``MANIFEST.txt`` — per-file index (page, kind,
        shape index) tying each copy back to where it sits in the document.

    If a photo was flattened from a .pyf (dropped in as a figure — see the
    poster GUI's drag-and-drop / "Add image…"), that .pyf's own Source Data
    bundle is additionally nested inside its images/ entry (as
    ``images/<name>_pyf_bundle/``) via export_source_data — a bundle inside
    a bundle, so the figure behind a photo stays traceable to its own
    panels/scripts/CSVs, not just the flattened image actually on the page.

    Returns JSON summarising what was bundled (including nested_pyf_bundles,
    the count of figures consolidated this way).
    """
    # Longer timeout than the other poster ops: each nested .pyf bundle
    # (see above) re-renders that figure through the normal export path,
    # which can add up across an album with several flattened figures.
    return _poster_result(*_run_poster_op(
        ["export-source-data", poster_path, out_dir, "--dpi", str(int(dpi))], timeout=600))


@mcp.tool()
def build_poster_from_recipe(recipe_path: str) -> str:
    """Build a whole poster or photo album from a declarative **recipe** file
    (YAML or JSON) in one call — pages, backgrounds, photos (files or glob
    patterns), how each page's photos are arranged, and text boxes; optionally
    also renders it (PDF of every page, or an image of page 1) and/or writes
    the HTML photo book. Re-running after adding photos rebuilds it.

    Paths are relative to the recipe file. Minimal album::

        output: iceland.pyfalbum
        page: A4
        album: true
        render: iceland.pdf
        front_cover:
          background: cover.jpg
          text: [{html: "<b>Iceland 2026</b>", style: h1}]
        spreads:
          - {images: ["day1/*.jpg"], arrange: grid}
          - {images: [lagoon.jpg, geyser.jpg], arrange: {layout: diptych}}

    A one-page poster puts ``background`` / ``images`` / ``arrange`` / ``text``
    at the top level (output ``.pyfposter``); a plain multi-page document uses
    ``pages: [...]``. ``arrange`` is grid / scatter / fan / none,
    ``{grid: {columns: 3}}``-style options, or ``{layout: <name>}`` (see
    list_poster_layouts). Images may be ``{image, frame, caption, x_mm, y_mm,
    width_mm, height_mm, theta}``; text ``{html, style (h1..caption), x_mm,
    y_mm, theta, width_mm}``. Unknown keys, missing files and empty globs are
    errors reported before anything is written. Full reference:
    pyfigures/poster/poster_recipe.py and docs/poster.md.
    """
    return _poster_result(*_run_poster_op(["build", recipe_path], timeout=600))


@mcp.tool()
def export_poster_web(poster_path: str, out_path: str, dpi: int = 150, quality: int = 85) -> str:
    """Export a poster/album as a self-contained HTML "photo book" — a nice
    way to share personal photos with anyone, no app/install needed on
    their end, just a browser.

    Renders every page to a JPEG and writes ONE .html file at *out_path*
    with the images embedded as base64 data URIs (nothing else to attach —
    email it, drop it on a USB stick, or upload it to any plain static web
    host) plus a page-flip viewer: click either side of the page, arrow
    keys, swipe on touch, or the thumbnail dots at the bottom; a page
    counter and full-screen button are included. Works for a plain
    one-page poster too (a one-page "book").

    *dpi* controls the embedded image resolution (150 is plenty for any
    screen — this is a viewing export, not print; see
    export_poster_album_print_ready for that). *quality* is the JPEG
    quality, 0-100. Returns JSON with the output path and page count.
    """
    return _poster_result(*_run_poster_op(
        ["export-web", poster_path, out_path, "--dpi", str(int(dpi)), "--quality", str(int(quality))]))
