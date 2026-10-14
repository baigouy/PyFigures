"""PyFigures MCP tools — Figure structure tools: describe/create figures, groups, images, annotations, sizes, journal presets, image properties, scripts.

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
    _warn,
    mcp,
)
from .core import (
    _JOURNAL_ALIASES,
    _JOURNAL_PRESETS,
    _ROI_PROTECTED,
    _append_image,
    _atomic_write_text,
    _clear_derived_sidecars,
    _auto_recompute,
    _child_text,
    _decode,
    _describe_roi,
    _encode_str,
    _encode_value,
    _get_container,
    _group_summary,
    _image_summary,
    _is_template,
    _load,
    _navigate_group,
    _new_group_elem,
    _new_image2d,
    _new_tatext2d,
    _next_group_id,
    _roi_children,
    _save,
    _set_child_text,
    _template_size,
    _top_groups,
    _width_mm_for_journal,
)

# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def describe_figure(pyf_path: str) -> str:
    """Return a human-readable tree summary of a .pyf figure's layout.

    Shows groups (orientation, spacing, child count) and images (filename,
    size, annotations). Use this first to understand a figure before editing.

    Two layout modes are reported:
    - Free-canvas: Image2D elements sit directly under <list> (group_path=[]).
    - Group-based: Image2D elements are nested inside Group / content elements.
    """
    _, root = _load(pyf_path)
    canvas_imgs = [c for c in root if c.tag == "Image2D"]
    groups = _top_groups(root)
    lines = [f"Figure: {pyf_path}"]

    if canvas_imgs:
        lines.append(f"\nFree-canvas mode - {len(canvas_imgs)} image(s) (use group_path=[] to address them):")
        for i, img in enumerate(canvas_imgs):
            lines.append(_image_summary(img, i, "  "))
        lines.append("")

    if groups:
        lines.append(f"{len(groups)} top-level group(s):\n")
        for i, grp in enumerate(groups):
            lines.extend(_group_summary(grp, f"Group {i}"))
            lines.append("")

    if not canvas_imgs and not groups:
        lines.append("(empty figure — no images or groups yet)")

    return "\n".join(lines)


@mcp.tool()
def get_xml(pyf_path: str) -> str:
    """Return the raw XML content of a .pyf file.

    Use this to inspect the full serialized structure or to prepare a complex
    edit that will be written back with write_xml().
    """
    return Path(pyf_path).read_text(encoding="utf-8")


@mcp.tool()
def write_xml(pyf_path: str, xml_content: str) -> str:
    """Write *xml_content* back to *pyf_path*, replacing the existing file.

    Always validate that the XML is well-formed before calling this.
    Returns a confirmation message or an error string.
    """
    try:
        ET.fromstring(xml_content)           # validate
    except ET.ParseError as e:
        return f"ERROR: XML is not well-formed — {e}.  File not written."
    _atomic_write_text(pyf_path, xml_content)
    return f"Written {len(xml_content)} bytes to {pyf_path}."


@mcp.tool()
def inspect_ome_zarr(path_or_url: str) -> str:
    """Describe an **OME-Zarr** image (local ``.zarr`` folder or http(s) URL,
    e.g. from the IDR or an institutional OME-Zarr server) without reading its
    pixels: axes, pyramid levels (shape, data type, pixel size in µm), channel
    names / colours / display windows, and the level PyFigures reads by default.

    Use it before add_image to pick a level: append ``#level=N`` to the URL to
    read level N instead of the default (the largest within 512 MB / 8192 px).
    Needs the ``zarr`` package (``pip install pyfigures[zarr]``).
    """
    try:
        from batoolset import ome_zarr as Z
    except ImportError as e:
        return f"ERROR: OME-Zarr support is not available ({e})."
    try:
        info = Z.describe(path_or_url)
        level, w, h = Z.level_size(path_or_url)
    except ImportError:
        return "ERROR: OME-Zarr needs the 'zarr' package: pip install zarr"
    except Exception as e:
        return f"ERROR: cannot read {path_or_url}: {type(e).__name__}: {e}"
    names = [str(n).lower() for n in info["axes"]]
    for lv in info["levels"]:
        for ax in ("x", "y", "z"):
            if ax in names:
                i = names.index(ax)
                unit = (info["units"][i] or "micrometer").lower()
                lv[f"pixel_size_{ax}_um"] = round(lv["scale"][i] * Z._UNIT_TO_UM.get(unit, 1.0), 6)
    info["default_level"] = level
    info["default_level_size_px"] = [w, h]
    return json.dumps(info, ensure_ascii=False, indent=2)


@mcp.tool()
def inspect_omero_image(image_url: str) -> str:
    """Describe an image on an **OMERO** server without reading its pixels: name,
    size (X, Y, Z, T, C), pixel size in µm, channel names / colours / windows,
    and the planes add_image would read.

    *image_url*: the image's OMERO.web link, as shown by the browser — e.g.
    ``https://omero.example.org/webclient/img_detail/1234/``,
    ``…/webclient/?show=image-1234`` or ``…/iviewer/?images=1234``. Append
    ``#z=0-9&t=0&c=0,2`` to choose planes / channels. Give the same link to
    add_image (or a recipe) to add the image. Pixels come from OMERO.web's
    renderer: 256 levels per channel over the channel's data range (exact for
    8-bit data). Private data needs a login: set OMERO_USERNAME and
    OMERO_PASSWORD in the MCP server's environment (never stored in figures).
    """
    from batoolset import omero_web as O
    if not O.is_omero_url(image_url):
        return ("ERROR: not an OMERO image link (expected …/webclient/img_detail/ID/, "
                "…/webclient/?show=image-ID or …/iviewer/?images=ID)")
    try:
        info = O.describe(image_url)
    except O.OmeroLoginRequired as e:
        return (f"ERROR: {e}. Set OMERO_USERNAME and OMERO_PASSWORD in the environment of the "
                "MCP server, or open the image once in the PyFigures GUI to log in.")
    except Exception as e:
        return f"ERROR: cannot read {image_url}: {type(e).__name__}: {e}"
    return json.dumps(info, ensure_ascii=False, indent=2)


@mcp.tool()
def list_images(pyf_path: str) -> str:
    """List all image file paths referenced in the figure, as JSON.

    Returns a JSON array of objects: [{group_path, image_index, path}].
    - group_path=[] → free-canvas image (direct child of <list>).
    - group_path=[i] → image inside top-level group i.
    Entries with path=null are template placeholders (no image loaded yet).
    """
    _, root = _load(pyf_path)
    results = []

    def _img_entry(img: ET.Element, path: list[int], ii: int) -> dict:
        script = _child_text(img, "custom_loading_script")
        tmpl = _is_template(img)
        return {
            "group_path": path,
            "image_index": ii,
            "path": None if tmpl else _child_text(img, "filename"),
            "is_template": tmpl,
            "has_script": script is not None,
            "template_size": _template_size(img) if tmpl else None,
        }

    # Free-canvas images (direct children of <list>)
    for ii, img in enumerate(c for c in root if c.tag == "Image2D"):
        results.append(_img_entry(img, [], ii))

    # Group-based images — recursive so grid sub-groups are included.
    # Label-row Groups (isText != "False") are skipped — they only contain
    # text cells and are never addressed by image-level tools.
    # Side-label Image2D cells (isText=="True") ARE included in the index so
    # that image_index here matches the index expected by set_scale_bar etc.,
    # but they are flagged with is_side_label=True so callers can identify them.
    def _walk_group(grp: ET.Element, path: list[int]):
        content = grp.find("content")
        if content is None:
            return
        sub_grp_idx = 0
        img_idx = 0
        for child in content:
            if child.tag == "Image2D":
                entry = _img_entry(child, path, img_idx)
                if child.findtext("isText", "False") == "True":
                    entry["is_side_label"] = True
                results.append(entry)
                img_idx += 1
            elif child.tag == "Group":
                if child.findtext("isText", "False") not in ("False", ""):
                    pass  # nested label-row group — skip
                else:
                    _walk_group(child, path + [sub_grp_idx])
                sub_grp_idx += 1

    for gi, grp in enumerate(_top_groups(root)):
        if grp.findtext("isText", "False") not in ("False", ""):
            continue  # top-level label-row group — skip entirely
        _walk_group(grp, [gi])

    return json.dumps(results, indent=2)


@mcp.tool()
def set_spacing(pyf_path: str, group_path: list[int], spacing: int) -> str:
    """Set the spacing (pixels) between children of a group.

    *group_path*: [0] for top-level group 0, [0,1] for a sub-group.
    (Free-canvas mode has no groups, so group_path=[] is not valid here.)
    Use describe_figure() to find the right path.
    """
    tree, root = _load(pyf_path)
    if not group_path:
        return "ERROR: set_spacing requires a group (group_path cannot be [])."
    grp, err = _navigate_group(root, group_path)
    if err:
        return f"ERROR: {err}"
    _set_child_text(grp, "space", str(int(spacing)))
    _save(tree, pyf_path, recompute=True)
    return f"Group {group_path} spacing set to {spacing}."


@mcp.tool()
def set_orientation(pyf_path: str, group_path: list[int], orientation: str) -> str:
    """Set the layout orientation of a group to 'X' (horizontal) or 'Y' (vertical).

    *group_path*: [0] for top-level group 0, [0,1] for a sub-group.
    """
    orientation = orientation.upper().strip()
    if orientation not in ("X", "Y"):
        return "ERROR: orientation must be 'X' or 'Y'."
    tree, root = _load(pyf_path)
    if not group_path:
        return "ERROR: set_orientation requires a group (group_path cannot be [])."
    grp, err = _navigate_group(root, group_path)
    if err:
        return f"ERROR: {err}"
    _set_child_text(grp, "orientation", _encode_str(orientation))
    _save(tree, pyf_path, recompute=True)
    return f"Group {group_path} orientation set to {orientation}."


@mcp.tool()
def reorder_children(pyf_path: str, group_path: list[int], new_order: list[int]) -> str:
    """Reorder the children inside a group or the free-canvas.

    *group_path*: [] for free-canvas (reorders Image2D children of <list>),
    [0] for top-level group 0's content, etc.
    *new_order*: permutation of [0, 1, …, n-1]. Example: [2, 0, 1] puts the
    third child first.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    if not group_path:
        # Free-canvas: reorder only Image2D children, leaving metadata in place
        imgs = [c for c in root if c.tag == "Image2D"]
        if sorted(new_order) != list(range(len(imgs))):
            return f"ERROR: new_order must be a permutation of 0..{len(imgs)-1}."
        for img in imgs:
            root.remove(img)
        # Re-insert in new order before metadata
        for i in new_order:
            _append_image(root, imgs[i], is_root=True)
        _save(tree, pyf_path, recompute=True)
        return f"Canvas images reordered to {new_order}."
    else:
        content = container    # _get_container already returned content element
        children = list(content)
        if sorted(new_order) != list(range(len(children))):
            return f"ERROR: new_order must be a permutation of 0..{len(children)-1}."
        for child in children:
            content.remove(child)
        for i in new_order:
            content.append(children[i])
        _save(tree, pyf_path, recompute=True)
        return f"Group {group_path} children reordered to {new_order}."


@mcp.tool()
def set_annotation_text(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    annotation_index: int,
    html_text: str,
) -> str:
    """Replace the text of a specific annotation on an image.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.
    *annotation_index*: 0-based index among TAText2D elements on that image.
    *html_text*: new label text — plain text or Qt HTML.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    images = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(images):
        return f"ERROR: image_index {image_index} out of range ({len(images)} images)."
    annotations = images[image_index].find("annotations")
    if annotations is None:
        return "ERROR: image has no <annotations>."
    ta_list = list(annotations.findall("TAText2D"))
    if annotation_index >= len(ta_list):
        return f"ERROR: annotation_index {annotation_index} out of range ({len(ta_list)} annotations)."
    _set_child_text(ta_list[annotation_index], "text", _encode_str(html_text))
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else str(group_path)
    return f"Annotation {loc}[{image_index}][{annotation_index}] updated."


@mcp.tool()
def tidy_text(pyf_path: str) -> str:
    """Apply conservative typography fixes to every text label in the figure.

    Safe, objective clean-ups only (tags/HTML markup are left untouched):
      - number × number:  2*3 -> 2×3
      - temperatures:      37 degrees C -> 37 °C
      - angles:            45 degrees -> 45°  (skips 'degrees of freedom')
      - number ↔ unit gap: 10µm -> 10 µm  (curated unit whitelist; leaves 2D/H2O/10K)
      - numeric ranges:    10-20 -> 10–20  (ISO dates protected)
      - negative sign:     -5 -> −5
      - collapses runs of spaces

    Deliberately does NOT touch italics, superscripts, %-placement or
    capitalisation — those are context-dependent and better done by hand.
    Returns how many labels changed.
    """
    from batoolset.strings.typography import tidy_html
    tree, root = _load(pyf_path)
    changed, scanned = 0, 0
    for ta in root.iter("TAText2D"):
        raw = _child_text(ta, "text")
        if not raw or not isinstance(raw, str):
            continue
        scanned += 1
        new = tidy_html(raw)
        if new != raw:
            _set_child_text(ta, "text", _encode_str(new))
            changed += 1
    if changed:
        _save(tree, pyf_path)
    return f"Tidied typography: {changed} of {scanned} text label(s) changed."


@mcp.tool()
def get_annotations(pyf_path: str) -> str:
    """Return ALL annotations and ROIs in the figure as JSON, including nested groups.

    Each entry includes *annotation_index* (0-based within that image's list),
    *type* (TAText2D / Rectangle2D / Ellipse2D / Line2D / Polygon2D / …),
    and shape-specific fields (x/y/width/height, text/placement, points, arrow, …).
    ScaleBars and insets are listed as protected and cannot be removed via remove_annotation.

    group_path=[] → free-canvas image; [0] → top-level group 0; [0,1] → sub-group.
    """
    _, root = _load(pyf_path)

    def _collect_imgs(container: ET.Element, path: list[int], out: list):
        for ii, img in enumerate(c for c in container if c.tag == "Image2D"):
            annots = img.find("annotations")
            if annots is None:
                continue
            removable = _roi_children(annots)
            for ai, child in enumerate(annots):
                desc = _describe_roi(child, ai)
                desc["group_path"] = path
                desc["image_index"] = ii
                out.append(desc)

    def _walk_group(grp: ET.Element, path: list[int], out: list):
        content = grp.find("content")
        if content is None:
            return
        _collect_imgs(content, path, out)
        for si, sub in enumerate(c for c in content if c.tag == "Group"):
            _walk_group(sub, path + [si], out)

    result: list[dict] = []
    _collect_imgs(root, [], result)
    for gi, grp in enumerate(_top_groups(root)):
        _walk_group(grp, [gi], result)
    return json.dumps(result, indent=2)


@mcp.tool()
def create_figure(
    pyf_path: str,
    orientation: str = "X",
    spacing: int = 3,
    num_groups: int = 0,
    mode: str | None = None,
) -> str:
    """Create a new empty .pyf figure file.

    *pyf_path*: save location (should end in .pyf).
    *mode*:
      - "canvas" — free-canvas figure with no groups.  Add images
        with add_image(..., group_path=[]).  This is the format real PyFigures
        produces when you drag images without creating explicit group panels.
      - "groups" — create *num_groups* empty layout groups instead.
        Add images with add_image(..., group_path=[i]).
      - omitted: "groups" when *num_groups* > 0, otherwise "canvas".
    *orientation*: 'X' = side-by-side, 'Y' = stacked (only relevant for groups mode).
    *spacing*: pixels between children.
    *num_groups*: number of empty groups to create (1–20, groups mode only).
    """
    if mode is None:
        mode = "groups" if num_groups and num_groups > 0 else "canvas"
    mode = mode.lower().strip()
    if mode not in ("canvas", "groups"):
        return "ERROR: mode must be 'canvas' or 'groups'."
    if mode == "canvas" and num_groups and num_groups > 0:
        return ("ERROR: num_groups only applies to mode='groups' "
                "(omit mode, or pass mode='groups').")
    orientation = orientation.upper().strip()
    if orientation not in ("X", "Y"):
        return "ERROR: orientation must be 'X' or 'Y'."

    root = ET.Element("list")

    if mode == "groups":
        if num_groups < 1:
            num_groups = 1
        if num_groups > 20:
            return "ERROR: num_groups must be between 1 and 20."
        for gid in range(1, num_groups + 1):
            root.append(_new_group_elem(orientation, spacing, group_id=gid))

    font = ET.SubElement(root, "SerializableQFont")
    for tag, val in [
        ("family",     _encode_str("Arial")),
        ("size",       "12"),
        ("style",      "400"),
        ("italic",     "False"),
        ("background", "None"),
        ("foreground", "4294967295"),
        ("placement",  _encode_str("top left")),
    ]:
        ET.SubElement(font, tag).text = val

    gui = ET.SubElement(root, "SerializableGUIparameters")
    ET.SubElement(gui, "space").text = str(spacing)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    buf = io.StringIO()
    tree.write(buf, encoding="unicode", xml_declaration=True)
    _atomic_write_text(pyf_path, buf.getvalue())
    # a new figure: drop the statistics record / alt text of any previous one
    stale = _clear_derived_sidecars(pyf_path)
    note = (f" Removed the previous figure's {', '.join(os.path.basename(p) for p in stale)}."
            if stale else "")

    if mode == "canvas":
        return (
            f"Created {pyf_path} in free-canvas mode (spacing={spacing}). "
            "Use add_image(..., group_path=[]) to add images." + note
        )
    return (
        f"Created {pyf_path} with {num_groups} group(s), "
        f"orientation={orientation}, spacing={spacing}." + note
    )


@mcp.tool()
def add_image(
    pyf_path: str,
    group_path: list[int],
    filename: str,
    label: str = "",
    label_placement: str = "top left",
    page: int | None = None,
) -> str:
    """Add an image to the figure.

    *group_path*: list of ints.
      - [] → free-canvas (image added directly under <list>; matches real PyFigures default).
      - [0] → top-level group 0; [0, 1] → first sub-group inside group 0.
    *filename*: absolute path to the image file (PNG, TIFF, JPG, …), an
      http(s) URL to an image, or an **OME-Zarr** image — a local ``.zarr``
      folder or a URL such as ``https://…/image.zarr``. For OME-Zarr the largest
      pyramid level within 512 MB / 8192 px is read; append ``#level=N`` to the
      URL to choose one (see inspect_ome_zarr). Pixel size and channel colours
      come from the OME metadata. An **OMERO** image's OMERO.web link
      (``…/webclient/img_detail/ID/``; see inspect_omero_image) works too.
    *label*: optional panel label (plain text or Qt HTML, e.g. "<b>A</b>").
    *label_placement*: "top left" | "top right" | "bottom left" | "bottom right".
    *page*: for a multi-page **PDF**, the page to show (1 = first page; the
      default). Stored as the panel's series (configure_image serie_to_open is
      the same, 0-based).
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d(filename)
    if page is not None:
        if not str(filename).lower().endswith(".pdf"):
            return "ERROR: page applies to PDF files only"
        try:
            from batoolset.img import pdf_page_count
            n_pages = pdf_page_count(filename)
        except Exception as e:
            return f"ERROR: cannot read {filename}: {e}"
        if not 1 <= int(page) <= n_pages:
            return f"ERROR: page must be between 1 and {n_pages}"
        from .core import _set_child_text
        _set_child_text(img, "serie_to_open", str(int(page) - 1))
    if label:
        img.find("annotations").append(_new_tatext2d(label, label_placement))
    _append_image(container, img, is_root=(not group_path))
    _save(tree, pyf_path, recompute=True)
    n = len([c for c in container if c.tag == "Image2D"]) - 1
    suffix = f' with label "{label}" ({label_placement})' if label else ""
    if page is not None:
        suffix += f" (page {int(page)})"
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Added {Path(filename).name} as image {n} in {loc}{suffix}."


@mcp.tool()
def add_equation(
    pyf_path: str,
    group_path: list[int],
    latex: str,
    font_size: float = 12.0,
    color: str = "black",
    fontset: str = "cm",
    label: str = "",
    label_placement: str = "top left",
) -> str:
    """Add a typeset equation as a vector panel.

    *latex*: LaTeX mathematics, e.g. ``\\Delta F/F_0 = \\frac{F-F_0}{F_0}`` (with or
      without surrounding $…$; text outside $…$ is set as plain text). Typeset by
      Matplotlib's mathtext — a LaTeX maths subset, no TeX installation needed.
    *font_size*: in points; *color*: a colour name or #rrggbb.
    *fontset*: "cm" (Computer Modern, the LaTeX look; default), "stix",
      "stixsans", "dejavusans" or "dejavuserif".
    The equation is written as an SVG (glyphs as outlines) in an ``equations``
    folder next to the figure and added like an image: it stays vector in PDF/SVG
    exports and is scaled with the layout like any panel.
    *group_path* / *label* / *label_placement*: as for add_image.
    """
    from pyfigures import equations as E
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such figure: {pyf_path}"
    try:
        svg = E.make_equation(pyf_path, latex, font_size, color, fontset)
    except ValueError as e:
        return f"ERROR: {e}"
    res = add_image(pyf_path, group_path, svg, label=label, label_placement=label_placement)
    if res.startswith("ERROR"):
        return res
    return res.replace(Path(svg).name, f"equation {E.normalize(latex)}") + f" (file: {svg})"


@mcp.tool()
def remove_image(pyf_path: str, group_path: list[int], image_index: int) -> str:
    """Remove an image from the figure.

    *group_path*: [] for free-canvas, [0] for top-level group 0, etc.
    *image_index*: 0-based index among the Image2D children at that location.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    container.remove(imgs[image_index])
    _save(tree, pyf_path, recompute=True)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Removed image {image_index} from {loc}."


@mcp.tool()
def add_annotation(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    text: str,
    placement: str = "top left",
) -> str:
    """Add a text label to a specific image.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] for sub-group.
    *image_index*: 0-based index among Image2D elements at that location.
    *text*: label text — plain or Qt HTML (e.g. "<b>A</b>", "DAPI").
    *placement*: "top left" | "top right" | "bottom left" | "bottom right" | "center".
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
        annots = ET.SubElement(imgs[image_index], "annotations")
    annots.append(_new_tatext2d(text, placement))
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Added annotation '{text}' ({placement}) to image {image_index} in {loc}."


@mcp.tool()
def add_corner_labels(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    top_left: list[str] | None = None,
    top_right: list[str] | None = None,
    bottom_left: list[str] | None = None,
    bottom_right: list[str] | None = None,
) -> str:
    """Add one or more text labels to any corner of an image in a single call.

    Each corner accepts a list of strings — they are stacked from the corner
    inward (top corners stack downward, bottom corners stack upward).
    Omit or pass ``null`` for corners you do not want to label.

    Labels support plain text or Qt HTML (bold, colour, superscript …).

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Examples::

        # Single letter label "A" top-left + scale info bottom-right
        add_corner_labels("fig.pyf", [0], 0,
                          top_left=["A"],
                          bottom_right=["10 µm"])

        # Two stacked labels at top-left (A over WT), asterisks at top-right
        add_corner_labels("fig.pyf", [0], 0,
                          top_left=["A", "WT"],
                          top_right=["*"])

        # Four corners at once
        add_corner_labels("fig.pyf", [0], 2,
                          top_left=["C", "Merge"],
                          top_right=["n=12"],
                          bottom_left=["DAPI"],
                          bottom_right=["<b>p&lt;0.01</b>"])
    """
    placement_map = {
        "top left":     top_left,
        "top right":    top_right,
        "bottom left":  bottom_left,
        "bottom right": bottom_right,
    }
    # Validate: at least one corner must be provided
    if not any(v for v in placement_map.values()):
        return "ERROR: at least one corner argument (top_left, top_right, bottom_left, bottom_right) must be provided."

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    annots = img.find("annotations")
    if annots is None:
        annots = ET.SubElement(img, "annotations")

    added: list[str] = []
    for placement, texts in placement_map.items():
        if not texts:
            continue
        for text in texts:
            annots.append(_new_tatext2d(text, placement))
            added.append(f"'{text}' @ {placement}")

    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Added {len(added)} label(s) to image {image_index} in {loc}: {'; '.join(added)}."


@mcp.tool()
def remove_annotation(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    annotation_index: int,
) -> str:
    """Remove an annotation or ROI from an image by its index.

    *annotation_index* is the 0-based position among ALL children of the
    image's <annotations> element (text labels, rect/ellipse/line/polygon ROIs).
    Use ``get_annotations()`` to see the current index of each item.
    ScaleBars and insets are protected and cannot be removed here.

    *group_path*: [] for free-canvas, [0] for top-level group 0, etc.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range."
    annots = imgs[image_index].find("annotations")
    if annots is None:
        return "ERROR: no annotations on this image."
    children = list(annots)
    if annotation_index >= len(children):
        return f"ERROR: annotation_index {annotation_index} out of range ({len(children)} items)."
    target = children[annotation_index]
    if target.tag in _ROI_PROTECTED:
        return (
            f"ERROR: element at index {annotation_index} is a {target.tag} "
            "which is protected. Use the dedicated remove_scale_bar or "
            "remove_inset tool instead."
        )
    annots.remove(target)
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Removed {target.tag} (index {annotation_index}) from image {image_index} in {loc}."


@mcp.tool()
def add_group(
    pyf_path: str,
    orientation: str = "X",
    spacing: int = 3,
    parent_group_path: list[int] | None = None,
) -> str:
    """Append a new empty group to the figure.

    *orientation*: 'X' (images side-by-side / columns) or 'Y' (images stacked / rows).
    *spacing*: pixels between children.
    *parent_group_path*: if None (default) the group is added as a new top-level group.
      Pass a path like [0] to nest it *inside* an existing group — this is how you
      build row-of-columns or column-of-rows (grid) layouts:

        # 2-row × 3-column grid
        create_figure(f, mode="groups", num_groups=1, orientation="Y")   # outer col
        add_group(f, orientation="X", parent_group_path=[0])  # row 0 → [0,0]
        add_group(f, orientation="X", parent_group_path=[0])  # row 1 → [0,1]
        add_image(f, [0,0], "a.tif") ...

    Returns the new group's path and ID.
    """
    orientation = orientation.upper().strip()
    if orientation not in ("X", "Y"):
        return "ERROR: orientation must be 'X' or 'Y'."
    tree, root = _load(pyf_path)
    new_id = _next_group_id(root)
    grp = _new_group_elem(orientation, spacing, group_id=new_id)

    if parent_group_path is None:
        # Top-level: insert after the last existing Group, before metadata
        existing = _top_groups(root)
        last_pos = -1
        for i, child in enumerate(root):
            if child.tag == "Group":
                last_pos = i
        root.insert(last_pos + 1, grp)
        new_index = len(existing)
        new_path = [new_index]
    else:
        # Nested: append to parent's <content>
        parent, err = _navigate_group(root, parent_group_path)
        if err:
            return f"ERROR: {err}"
        content = parent.find("content")
        if content is None:
            content = ET.SubElement(parent, "content")
        sub_idx = len([c for c in content if c.tag == "Group"])
        content.append(grp)
        new_path = list(parent_group_path) + [sub_idx]

    _save(tree, pyf_path, recompute=True)
    return (
        f"Added group at path {new_path} "
        f"(ID={new_id}, orientation={orientation}, spacing={spacing})."
    )


@mcp.tool()
def set_size(
    pyf_path: str,
    width_px: int,
    group_path: list[int] | None = None,
) -> str:
    """Set the layout width (in pixels) of one or all groups and write fully-computed
    geometry back to the file — identical to typing a value in the GUI size spinner.

    Uses PyFigures' own layout engine (set_to_width) so the saved XML contains correct
    x/y/width/height/scale values for every child, exactly as the GUI would produce.

    *width_px*: desired width in pixels.
      Tip — to convert cm to px:  round(cm * DPI / 2.54)
      e.g. 17 cm at 300 DPI = round(17 * 300 / 2.54) = 2008 px
    *group_path*:
      - None (default) → resize ALL top-level groups to *width_px*.
      - [0] → resize only top-level group 0.
      - [0, 1] → resize a specific sub-group.
      - [] → error (free-canvas has no groups; use layout_canvas() instead).
    """
    if width_px <= 0:
        return "ERROR: width_px must be a positive integer."
    if group_path is not None and not group_path:
        return "ERROR: group_path=[] means free-canvas (no groups). Use layout_canvas()."

    # ── Use PyFigures' own pipeline so geometry is fully computed ──────────────
    try:
        from batoolset.settings.global_settings import set_UI as _set_UI
        _set_UI()
        from qtpy.QtWidgets import QApplication as _QApp
        import sys as _sys
        _app = _QApp.instance() or _QApp(_sys.argv[:1])
        from batoolset.drawings.shapes.image2d import Image2D as _Image2D
        from batoolset.serializations.tools import (
            deserialize_to_dict as _d2d,
            create_object as _co,
            object_to_xml as _to_xml,
        )
        from batoolset.drawings.shapes.group import Group as _Group, set_to_width as _stw
    except ImportError as e:
        return f"ERROR: could not import PyFigures layout engine — {e}"

    xml_content = Path(pyf_path).read_text(encoding="utf-8")

    # Lazy mode: Image2D objects use stored (or default 512×512) dimensions
    # without loading pixel data — safe for headless use.
    _Image2D._lazy_mode = True
    _Image2D._skip_sized_scripts = True     # sizing must not run panel code
    try:
        props = _d2d(xml_content)
        objects = _co(list.__name__, props)
    finally:
        _Image2D._lazy_mode = False
        _Image2D._skip_sized_scripts = False

    # Collect target groups
    top_groups = [o for o in objects if isinstance(o, _Group)]
    if not top_groups:
        return "ERROR: figure has no groups. Use layout_canvas() for free-canvas figures."

    if group_path is None:
        targets = top_groups
    else:
        # Navigate to the specific group
        # (objects list mirrors top-level structure, so group_path[0] selects the group)
        if group_path[0] >= len(top_groups):
            return f"ERROR: group_path[0]={group_path[0]} out of range ({len(top_groups)} top-level groups)."
        grp = top_groups[group_path[0]]
        for sub_idx in group_path[1:]:
            sub_grps = [c for c in grp.content if isinstance(c, _Group)]
            if sub_idx >= len(sub_grps):
                return f"ERROR: sub-group index {sub_idx} out of range."
            grp = sub_grps[sub_idx]
        targets = [grp]

    # Apply set_to_width — this computes all x/y/w/h/scale values in place
    for grp in targets:
        _stw(grp, width_px)

    # Re-serialise back to .pyf XML using PyFigures' own serialiser
    new_xml = _to_xml(objects, is_list=True)
    _atomic_write_text(pyf_path, new_xml)
    # then re-stack the rows at their new heights (set_to_width only lays out
    # each group internally: rows kept their old y and overlapped when the
    # figure got taller) — the same pass every structural edit runs
    err = _auto_recompute(pyf_path)
    if err:
        _warn(f"widths applied, but re-stacking the rows failed ({err}).")

    n = len(targets)
    loc = f"group {group_path}" if group_path is not None else f"{n} top-level group(s)"
    return f"Laid out {loc} at {width_px}px wide and saved computed geometry."


@mcp.tool()
def list_journal_presets() -> str:
    """List the built-in journal size presets (single / 1.5 / double column
    widths in mm) usable as ``journal=`` in resize_figure, check_resolution and
    check_journal_compliance, plus their accepted name aliases.

    Use this to discover exact target widths before formatting a figure for
    submission. Returns JSON: each journal's three column widths and the
    recommended minimum print resolution (300 DPI for line/photographic art).
    """
    out = {}
    aliases_by_key: dict[str, list[str]] = {}
    for alias, key in _JOURNAL_ALIASES.items():
        aliases_by_key.setdefault(key, []).append(alias)
    for key, widths in sorted(_JOURNAL_PRESETS.items()):
        out[key] = {
            "widths_mm": widths,
            "aliases": sorted(aliases_by_key.get(key, [])),
            "recommended_min_dpi": 300,
        }
    return json.dumps({
        "columns": ["single", "1.5", "double"],
        "note": "Widths are journal column widths in millimetres. Pass any listed "
                "name or alias as journal=, and column='single'|'1.5'|'double'. "
                "300 DPI is the usual minimum for print; some journals want 600 "
                "DPI for line art — check the specific author guidelines.",
        "journals": out,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def resize_figure(
    pyf_path: str,
    width_mm: float | None = None,
    width_cm: float | None = None,
    width_in: float | None = None,
    width_px: int | None = None,
    dpi: int = 300,
    journal: str | None = None,
    column: str = "single",
    group_path: list[int] | None = None,
) -> str:
    """Resize all (or one) group(s) of a figure to a target physical width.

    This is the main tool for conforming a figure to journal submission
    guidelines.  Specify the target width in one of four ways —
    only one should be given (journal preset > mm > cm > in > px):

    **journal** + **column**
      Use a named journal preset.  Supported names (case-insensitive):
        ``nature``, ``science``, ``cell``, ``plos``, ``elife``, ``embo``,
        ``elsevier``, ``springer``, ``wiley``, ``jcb``, ``pnas``.
      Also accepted: ``"nature methods"``, ``"plos one"``, ``"cell reports"``, etc.
      *column*: ``"single"`` (default), ``"1.5"``, or ``"double"``.

    **width_mm** / **width_cm** / **width_in**
      Physical width with explicit units.  Combined with *dpi* to give pixels.

    **width_px**
      Pixel width directly (skip unit conversion).

    **dpi**
      Resolution used to convert physical units to pixels (default 300).
      Common values: 300 (print), 600 (high-res print), 72 or 96 (screen).

    **group_path**
      Which group to resize.  ``null`` (default) → all top-level groups.
      ``[0]`` → only group 0. ``[0,1]`` → a sub-group.

    The underlying PyFigures layout engine (``set_to_width``) recomputes
    all child x/y/width/height/scale values, so the result is identical to
    manually setting the size in the GUI.

    Common journal single-column widths at 300 DPI:

    | Journal  | Single (mm) | Double (mm) | Single px@300 |
    |----------|-------------|-------------|---------------|
    | Nature   | 89          | 183         | 1051          |
    | Science  | 55          | 168         | 650           |
    | Cell     | 85          | 170         | 1004          |
    | PLOS ONE | 83          | 174         | 980           |
    | eLife    | 85          | 178         | 1004          |
    | EMBO     | 82          | 172         | 969           |

    Examples::

        # Nature single-column figure at 300 DPI
        resize_figure("fig.pyf", journal="nature", column="single")

        # Nature double-column at 600 DPI (higher resolution export)
        resize_figure("fig.pyf", journal="nature", column="double", dpi=600)

        # Custom width in mm
        resize_figure("fig.pyf", width_mm=89, dpi=300)

        # Custom width in inches
        resize_figure("fig.pyf", width_in=3.5, dpi=300)

        # Resize only one group
        resize_figure("fig.pyf", journal="cell", column="single", group_path=[1])
    """
    # ── Resolve the target physical width ───────────────────────────────────
    # PyFigures' canvas unit is the point (1/72 in): fonts are in pt on the
    # canvas, and export scales canvas units by dpi/72 (72 dpi = 1:1). So a
    # physical width W maps to W_in * 72 canvas units whatever the export dpi;
    # *dpi* only decides how many pixels an export at that resolution will have.
    # (This used to set W_in * dpi canvas units — at 300 dpi figures came out
    # 4.17x too large and every pt font 4.17x too small once printed.)
    if journal is not None:
        try:
            target_mm = _width_mm_for_journal(journal, column)
        except ValueError as e:
            return f"ERROR: {e}"
        target_in = target_mm / 25.4
        source = f"{journal!r} {column}-column = {target_mm:.0f}mm"
    elif width_mm is not None:
        target_in = width_mm / 25.4
        source = f"{width_mm}mm"
    elif width_cm is not None:
        target_in = width_cm / 2.54
        source = f"{width_cm}cm"
    elif width_in is not None:
        target_in = float(width_in)
        source = f"{width_in}in"
    elif width_px is not None:
        target_in = int(width_px) / float(dpi) if dpi else 0
        source = f"{width_px}px at {dpi} DPI"
    else:
        return (
            "ERROR: specify a target width — one of: journal, width_mm, "
            "width_cm, width_in, or width_px."
        )
    if not dpi or dpi <= 0:
        return f"ERROR: dpi must be positive (got {dpi})."
    target_px = round(target_in * dpi)           # pixels of an export at *dpi*
    canvas_units = target_in * 72.0              # PyFigures canvas width (pt)
    if target_px <= 0 or canvas_units <= 0:
        return f"ERROR: computed width {target_px}px is invalid."

    # ── Delegate to set_size which uses the PyFigures layout engine ─────────
    result = set_size(pyf_path, canvas_units, group_path)   # also re-stacks the rows
    if result.startswith("ERROR"):
        return result

    return (
        f"Figure resized to {target_in * 25.4:.1f}mm wide = {canvas_units:.1f} canvas pt; "
        f"an export at {dpi} DPI is {target_px}px wide  [{source}].  {result}"
    )


@mcp.tool()
def layout_canvas(
    pyf_path: str,
    width_px: int = 512,
    spacing_px: int = 3,
    direction: str = "Y",
) -> str:
    """Compute and store the layout for a free-canvas figure (Image2D under <list>).

    Free-canvas images have no group to auto-position them.  This tool reads the
    actual image dimensions from disk, scales each image so its width matches
    *width_px*, then positions them in a column (direction='Y') or row (direction='X').

    After calling this, the figure will open in PyFigures with correct positions and
    sizes — equivalent to what the GUI shows after the first load.

    *width_px*: target width in pixels for each image.
    *spacing_px*: gap between images (pixels).
    *direction*: 'Y' = stack images top-to-bottom (default), 'X' = side by side.
    """
    direction = direction.upper().strip()
    if direction not in ("X", "Y"):
        return "ERROR: direction must be 'X' or 'Y'."

    # Lazy import — uses PyFigures' own image reader so format support is identical.
    try:
        from batoolset.settings.global_settings import set_UI as _set_UI
        _set_UI()
        from batoolset.drawings.shapes.image2d import Image2D as _Image2D
    except ImportError as e:
        return f"ERROR: could not import PyFigures image reader — {e}"

    tree, root = _load(pyf_path)
    canvas_imgs = [c for c in root if c.tag == "Image2D"]
    if not canvas_imgs:
        return "ERROR: figure has no free-canvas images. Use set_size() for group-based figures."

    updated = 0
    cursor = 0  # running position along the packing axis
    for img_el in canvas_imgs:
        fname = _child_text(img_el, "filename") or ""
        # Try to get actual dimensions via PyFigures Image2D (handles TIF, PNG, etc.)
        raw_w, raw_h = None, None
        if fname and Path(fname).exists():
            try:
                obj = _Image2D(fname)
                raw_w, raw_h = obj.get_raw_size()
            except Exception:
                pass
        if raw_w is None or raw_h is None or raw_w == 0:
            # Fall back to stored width/height, or a safe default
            raw_w = _child_text(img_el, "width") or width_px
            raw_h = _child_text(img_el, "height") or width_px
            raw_w = float(raw_w) if raw_w else width_px
            raw_h = float(raw_h) if raw_h else width_px

        scale = width_px / raw_w
        scaled_w = width_px
        scaled_h = raw_h * scale

        if direction == "Y":
            _set_child_text(img_el, "x", "0.0")
            _set_child_text(img_el, "y", str(float(cursor)))
            _set_child_text(img_el, "width",  str(float(scaled_w)))
            _set_child_text(img_el, "height", str(float(scaled_h)))
            cursor += scaled_h + spacing_px
        else:  # X
            _set_child_text(img_el, "x", str(float(cursor)))
            _set_child_text(img_el, "y", "0.0")
            _set_child_text(img_el, "width",  str(float(scaled_w)))
            _set_child_text(img_el, "height", str(float(scaled_h)))
            cursor += scaled_w + spacing_px

        updated += 1

    _save(tree, pyf_path)
    axis_label = "top-to-bottom" if direction == "Y" else "left-to-right"
    return (
        f"Laid out {updated} free-canvas image(s) {axis_label} "
        f"at {width_px}px wide, {spacing_px}px gap."
    )


@mcp.tool()
def recompute_layout(pyf_path: str) -> str:
    """Re-run the PyFigures layout engine on all top-level groups in a figure.

    Every structural editing tool (add_image, remove_image, add_group,
    set_spacing, set_orientation, reorder_children, move_image, clone_image,
    fill_template, batch_fill_templates, add_scripted_image, remove_group)
    already triggers this automatically after each edit.

    Call this tool explicitly when:
    - You have just written raw XML with write_xml() and want positions recomputed.
    - A figure was edited externally (outside MCP) and the stored positions may
      be stale.
    - You want to force a clean layout pass as a final step after a sequence of
      edits that may have left positions inconsistent.

    Uses ``set_to_width`` from the PyFigures layout engine for every top-level
    group at its current stored width — identical to what the GUI does on load.

    Free-canvas figures (no groups) are left unchanged (use layout_canvas() instead).
    Returns a confirmation message or a description of any error.
    """
    err = _auto_recompute(pyf_path)
    if err:
        return f"Layout recompute warning: {err}"
    return f"Layout recomputed for all groups in {pyf_path}."


@mcp.tool()
def set_image_filename(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    new_filename: str,
) -> str:
    """Update the source file path of an existing image slot.

    Use this to redirect an image to a different file (e.g. after re-exporting).
    *group_path*: [] for free-canvas, [0] for top-level group 0, [0, 1] for sub-group.
    *image_index*: 0-based index among Image2D elements at that location.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    _set_child_text(imgs[image_index], "filename", _encode_str(new_filename))
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc} → {new_filename}."


@mcp.tool()
def move_image(
    pyf_path: str,
    src_group_path: list[int],
    src_image_index: int,
    dst_group_path: list[int],
    dst_image_index: int = -1,
) -> str:
    """Move an image from one location to another (or reposition within the same location).

    Both *src_group_path* and *dst_group_path* follow the group_path convention:
    [] = free-canvas, [0] = top-level group 0, etc.
    *dst_image_index*=-1 (default) appends at the end of the destination.
    """
    tree, root = _load(pyf_path)
    src_container, err = _get_container(root, src_group_path)
    if err:
        return f"ERROR (source): {err}"
    src_imgs = [c for c in src_container if c.tag == "Image2D"]
    if src_image_index >= len(src_imgs):
        return f"ERROR: src_image_index {src_image_index} out of range ({len(src_imgs)} images)."

    dst_container, err = _get_container(root, dst_group_path)
    if err:
        return f"ERROR (destination): {err}"

    img = src_imgs[src_image_index]
    src_container.remove(img)

    if dst_image_index < 0:
        _append_image(dst_container, img, is_root=(not dst_group_path))
    else:
        children = list(dst_container)
        if dst_image_index >= len(children):
            dst_container.append(img)
        else:
            dst_container.insert(dst_image_index, img)

    _save(tree, pyf_path, recompute=True)
    src_loc = "canvas" if not src_group_path else str(src_group_path)
    dst_loc = "canvas" if not dst_group_path else str(dst_group_path)
    dst_label = dst_image_index if dst_image_index >= 0 else "end"
    return f"Moved image from {src_loc}[{src_image_index}] to {dst_loc}[{dst_label}]."


@mcp.tool()
def fill_template(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    filename: str,
) -> str:
    """Fill an unfilled template slot with a real image file.

    A template slot is an Image2D whose filename is ``@template@`` — a placeholder
    that PyFigures shows as a grey box with the expected aspect ratio.  All other
    settings on the slot (annotations/labels, LUTs, crop, projection, border, …)
    are preserved; only the filename is replaced.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] for sub-group.
    *image_index*: 0-based index.  Use describe_figure() to find template slots
                   (they are reported as ``<template slot>``).
    *filename*: absolute path to the real image file.

    After calling this, reopen the figure in PyFigures — it will load and render the
    new file while keeping the layout and all annotations intact.

    To batch-fill multiple slots in a loop::

        slots = [i for i in json.loads(list_images(f))
                 if i["is_template"] and i["group_path"] == [0]]
        for slot, path in zip(slots, my_file_list):
            fill_template(f, slot["group_path"], slot["image_index"], path)
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    if not _is_template(img):
        fn = _child_text(img, "filename") or "<no file>"
        return (
            f"ERROR: image {image_index} is not a template slot "
            f"(current filename: {fn!r}). "
            "Use set_image_filename() to replace a non-template image."
        )
    _set_child_text(img, "filename", _encode_str(filename))
    _save(tree, pyf_path, recompute=True)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Template slot {image_index} in {loc} filled with {Path(filename).name}."


@mcp.tool()
def list_image_properties(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
) -> str:
    """Return every property of an Image2D element as a JSON object.

    This gives a complete view of ALL settings stored on one image — including
    properties that have no dedicated tool (LUTs, normalization, channels,
    projection, crop, border, opacity, rotation, publication settings, etc.).
    Use it to discover what is set before calling get_image_property /
    set_image_property.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] for sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Returns JSON — values are already decoded (numbers as numbers, None as null,
    booleans as booleans, strings as strings, lists/dicts as their Python repr).
    The special fields ``annotations`` and ``extra_user_translation`` are
    summarised rather than fully expanded.
    """
    _SKIP = {"annotations", "extra_user_translation", "translation", "clip_rect",
             "template_rect", "__init_called__", "__version__", "_TAText2D__version"}
    _, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    result = {}
    for child in img:
        if child.tag in _SKIP:
            continue
        result[child.tag] = _decode(child.text)
    # Summarise annotations count
    annots = img.find("annotations")
    result["annotations_count"] = len(list(annots)) if annots is not None else 0
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_image_property(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    property_name: str,
) -> str:
    """Return the current value of any named property on an Image2D element.

    Covers every field that PyFigures stores — use list_image_properties() to
    discover the full list.  Common property names:

      LUTs, normalization, channels, dimensions, projection, projection_z_start,
      projection_z_end, crop_left, crop_right, crop_top, crop_bottom,
      border_size, border_color, opacity, theta, scale, color, fill_color,
      stroke, publication_style, publication_font_size, publication_font,
      publication_line_width, px_to_unit_conversion_factor, user_comments,
      placement, serie_to_open, isText

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] for sub-group.
    *image_index*: 0-based index.
    *property_name*: exact XML tag name (case-sensitive).
    """
    _, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    val = _child_text(imgs[image_index], property_name)
    if val is None:
        child = imgs[image_index].find(property_name)
        if child is None:
            return f"Property '{property_name}' not found on this image."
        return "None"
    return repr(val)


@mcp.tool()
def set_image_property(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    property_name: str,
    value: str,
) -> str:
    """Set any named property on an Image2D element.

    This is the universal setter — it covers every field that PyFigures stores
    without requiring a dedicated tool for each one.

    *property_name*: exact XML tag name.  See list_image_properties() for names.
    *value*: the new value as a string.  Encoding is automatic:

      ┌─────────────────────────────────┬────────────────────────────────────┐
      │ You pass                        │ Use for                            │
      ├─────────────────────────────────┼────────────────────────────────────┤
      │ "None"                          │ clear / unset any field            │
      │ "True" / "False"                │ boolean fields (isText, …)         │
      │ "3" / "0.5"                     │ numeric fields (opacity, theta, …) │
      │ "['GREEN', 'RED', None]"        │ LUTs (channel colour maps)         │
      │ "max" / "min" / "mean"          │ projection type                    │
      │ "Arial"                         │ font name                          │
      │ "/path/to/data.csv"             │ filename / serie_to_open           │
      │ "{'min_value':0,'max_value':1}" │ normalization dict                 │
      └─────────────────────────────────┴────────────────────────────────────┘

    Examples::

      # Colour-map: channel 0 green, channel 1 red
      set_image_property(f, [0], 2, "LUTs", "['GREEN', 'RED', None]")

      # Crop 10 px from left and right
      set_image_property(f, [0], 2, "crop_left",  "10")
      set_image_property(f, [0], 2, "crop_right", "10")

      # Max-intensity projection of Z-stack, slices 2–8
      set_image_property(f, [0], 2, "projection",       "max")
      set_image_property(f, [0], 2, "projection_z_start", "2")
      set_image_property(f, [0], 2, "projection_z_end",   "8")

      # Add a 3-pixel white border
      set_image_property(f, [0], 2, "border_size",  "3")
      set_image_property(f, [0], 2, "border_color", "16777215")

      # Semi-transparent (50 %)
      set_image_property(f, [0], 2, "opacity", "0.5")

      # Rotate 45 degrees
      set_image_property(f, [0], 2, "theta", "45")

    The change is saved immediately; reopen in PyFigures to see the result.
    """
    _READONLY = {"x", "y", "width", "height", "scale",
                 "__init_called__", "__version__", "extra_user_translation"}
    if property_name in _READONLY:
        return (
            f"ERROR: '{property_name}' is a layout/internal field managed by "
            "set_size() / layout_canvas() — do not set it directly."
        )
    if property_name == "custom_loading_script":
        return "Use set_script() to change the custom loading script."
    if property_name == "filename":
        return "Use set_image_filename() to change the filename."
    if property_name == "annotations":
        return "Use add_annotation() / remove_annotation() / set_annotation_text() for annotations."

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    # placement is a Position object — serialised as plain text by PyFigures,
    # no ""..."" wrapping.  Everything else uses the smart encoder.
    if property_name == "placement":
        raw = value.strip()
    else:
        raw = _encode_value(value)
    _set_child_text(imgs[image_index], property_name, raw)
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc}: {property_name} = {raw}"


@mcp.tool()
def get_script(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
) -> str:
    """Return the Python custom-loading script embedded in an Image2D slot.

    Scripted images have no raster file — instead they carry a Python snippet
    that runs at load time inside PyFigures.  The script receives a pre-imported
    ``plt`` (matplotlib.pyplot) and ``np`` (numpy), plus ``self`` pointing to the
    Image2D object.  It must assign a matplotlib figure to ``self.img`` at the end,
    e.g. ``self.img = fig``.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] for sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Returns the raw script text, or a message if no script is present.
    Use set_script() to modify it.
    """
    _, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    script = _child_text(imgs[image_index], "custom_loading_script")
    if script is None:
        return "No script — this image loads from a file (use set_image_filename to change the file)."
    return script


@mcp.tool()
def set_script(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    script: str,
) -> str:
    """Replace (or add) the Python custom-loading script on an Image2D slot.

    The script runs inside PyFigures at load time. It has access to:
      - ``plt``   — matplotlib.pyplot (already imported)
      - ``np``    — numpy (already imported)
      - ``self``  — the Image2D object; assign the finished figure to ``self.img``
      - ``file_path`` — value of the image's <filename> field, if set (useful for
                        data-driven plots that read a CSV/TXT)

    Example — replace a line plot with a scatter plot::

        fig, ax = plt.subplots()
        ax.scatter([1, 2, 3], [4, 5, 6])
        ax.set_title('Scatter')
        self.img = fig

    Example — load data from the linked file and bar-plot it::

        import pandas as pd
        df = pd.read_csv(file_path, sep='\\t')
        fig, ax = plt.subplots()
        ax.bar(df['x'], df['y'])
        self.img = fig

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] for sub-group.
    *image_index*: 0-based index among Image2D elements at that location.
    *script*: new Python script text. Must assign ``self.img = <matplotlib figure>``.

    The change is saved immediately; reopen the figure in PyFigures to see the update.
    To remove a script entirely pass script="" and PyFigures will fall back to loading
    from the filename field.
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    if script.strip() == "":
        _set_child_text(img, "custom_loading_script", "None")
        _save(tree, pyf_path)
        loc = "canvas" if not group_path else f"group {group_path}"
        return f"Script cleared from image {image_index} in {loc}."
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    _save(tree, pyf_path)
    n_lines = script.count("\n") + 1
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Script ({n_lines} line(s)) saved to image {image_index} in {loc}."


@mcp.tool()
def add_scripted_image(
    pyf_path: str,
    group_path: list[int],
    script: str,
    label: str = "",
    label_placement: str = "top left",
) -> str:
    """Add a new script-generated image panel in one step (no raster file needed).

    This is the single-call alternative to add_image() + set_script().  Use it
    whenever you want to embed a matplotlib plot, a generated chart, or any
    Python-computed graphic directly into the figure.

    The script runs inside PyFigures at load time with these pre-bound names:

    =========  ==============================================
    ``plt``    matplotlib.pyplot (already imported)
    ``np``     numpy (already imported)
    ``self``   the Image2D object — assign the finished
               matplotlib figure to ``self.img``
    ``file_path`` value of <filename> field (None here unless
               you later call set_image_filename to link data)
    =========  ==============================================

    The script **must** end with ``self.img = fig`` (or equivalent).

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *script*: complete Python script text.
    *label*: optional corner annotation (e.g. ``"D"`` or ``"<b>D</b>"``).
    *label_placement*: ``"top left"`` | ``"top right"`` | ``"bottom left"`` |
                       ``"bottom right"`` (default ``"top left"``).

    Returns the image index so you can address it immediately with other tools.

    Example — sinusoid plot::

        add_scripted_image(
            "fig.pyf", [0],
            script=\"\"\"
        x = np.linspace(0, 2 * np.pi, 300)
        fig, ax = plt.subplots()
        ax.plot(x, np.sin(x), color='steelblue')
        ax.set_title('sin(x)')
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        self.img = fig
        \"\"\",
            label="D",
        )
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"

    # Build the Image2D — filename must be bare "None" (not ""None"") so
    # PyFigures treats it as an unlinked scripted panel, not a missing file.
    img = _new_image2d("__scripted__")          # temporary placeholder
    img.find("filename").text = "None"          # override to bare sentinel
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    if label:
        img.find("annotations").append(_new_tatext2d(label, label_placement))

    _append_image(container, img, is_root=(not group_path))
    _save(tree, pyf_path, recompute=True)

    idx = len([c for c in container if c.tag == "Image2D"]) - 1
    loc = "canvas" if not group_path else f"group {group_path}"
    suffix = f' with label "{label}"' if label else ""
    n_lines = script.count("\n") + 1
    return (
        f"Scripted image added as index {idx} in {loc}{suffix}. "
        f"Script: {n_lines} line(s). "
        "Reopen the figure in PyFigures to render it."
    )
