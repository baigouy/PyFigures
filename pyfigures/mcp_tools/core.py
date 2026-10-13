"""PyFigures MCP tools — Shared helpers: .pyf XML encoding, atomic save + layout recompute, element builders, colours, scale bars, sidecars, panel iteration.

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
)

# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _decode(text: str | None):
    """Decode a serialized PyFigures XML value to a Python value."""
    if text is None:
        return None
    t = text.strip()
    if t == "None":
        return None
    if t == "True":
        return True
    if t == "False":
        return False
    # Double-quoted string:  ""value""
    if t.startswith('""') and t.endswith('""') and len(t) >= 4:
        return t[2:-2]
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _encode_str(value: str) -> str:
    """Encode a string for PyFigures XML (wrap in double-quotes)."""
    return f'""{ value }""'


def _strip_tags(s: str) -> str:
    """Best-effort plain text from a possibly-HTML string (for length/logging)."""
    import re as _re
    # Qt rich text carries a <head><style>…</style></head> block: drop its CSS
    s = _re.sub(r"<(style|head|script)[^>]*>.*?</\1>", "", s or "", flags=_re.DOTALL | _re.IGNORECASE)
    return _re.sub(r"<[^>]+>", "", s)


def _escape_if_plain(s: str) -> str:
    """Escape XML/HTML specials in *s* only if it looks like plain text (no tag).
    Lets callers pass either plain labels ("p<0.001") or ready HTML ("<b>*</b>")."""
    if s and "<" in s and ">" in s and _strip_tags(s) != s:
        return s  # already contains markup — leave verbatim
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _encode_value(value: str) -> str:
    """Encode a user-supplied value string for storage in PyFigures XML.

    Applies the correct encoding automatically so callers do not need to know
    the internal ``""…""`` convention:

    ===========================  ============================================
    User passes                  Stored as
    ===========================  ============================================
    ``"None"``                   ``None``
    ``"True"`` / ``"False"``     ``True`` / ``False``
    Numeric string (``"3.14"``)  ``3.14``
    List / dict literal          stored as-is (Python repr)
    ``"PyQt6…"`` object string   stored as-is
    Anything else                ``""value""``  (PyFigures string encoding)
    ===========================  ============================================
    """
    v = value.strip()
    # Keywords / sentinels
    if v in ("None", "True", "False"):
        return v
    # Numeric
    try:
        int(v)
        return v
    except ValueError:
        pass
    try:
        float(v)
        return v
    except ValueError:
        pass
    # Python collection literal or Qt object string → store verbatim
    if (v.startswith("[") and v.endswith("]")) or \
       (v.startswith("{") and v.endswith("}")) or \
       v.startswith("PyQt"):
        return v
    # Plain text string → PyFigures encoding
    return _encode_str(v)


def _child_text(elem: ET.Element, tag: str):
    child = elem.find(tag)
    return _decode(child.text) if child is not None else None


def _set_child_text(elem: ET.Element, tag: str, raw_text: str):
    child = elem.find(tag)
    if child is None:
        child = ET.SubElement(elem, tag)
    child.text = raw_text


def _load(pyf_path: str, resolve: bool = True) -> tuple[ET.ElementTree, ET.Element]:
    """Parse a .pyf. With *resolve* (default), source paths that no longer exist
    are looked up relative to the .pyf's current location (figure moved to
    another folder / disk / OS) — see pyfigures.path_resolution. A later
    _save() then stores the found locations."""
    tree = ET.parse(pyf_path)
    root = tree.getroot()
    if resolve:
        from ..path_resolution import resolve_moved_paths_in_tree
        resolve_moved_paths_in_tree(root, pyf_path)
    return tree, root


def _atomic_write_text(path: str, text: str) -> None:
    """Write *text* to *path* atomically (temp file in the same folder, then
    os.replace), so a crash mid-write can never leave a truncated .pyf. Retries
    the replace briefly: OneDrive / antivirus can hold the target for a moment."""
    import tempfile
    import time
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".~pyf_", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _raw_size_from_file(filename) -> tuple[int, int] | None:
    """(width, height) of an image in source pixels, read from the file header
    without decoding pixels. None for non-files, SVGs, videos, multi-series
    containers or anything unreadable (those keep their stored size)."""
    if not filename or not isinstance(filename, str):
        return None
    if filename.split("#", 1)[0].rstrip("/\\").lower().endswith(".zarr"):
        try:                       # OME-Zarr (local or URL): the level that is read
            from batoolset.ome_zarr import level_size
            _, w, h = level_size(filename)
            return w, h
        except Exception:
            return None
    if not os.path.isfile(filename):
        return None
    low = filename.lower()
    if low.endswith(".svg"):
        return None
    if low.endswith((".tif", ".tiff")):
        try:
            import tifffile as _tf
            with _tf.TiffFile(filename) as t:
                p = t.pages[0]
                # imagewidth/imagelength are right even for planar (C,H,W) pages,
                # where p.shape[1] would be the height
                return int(p.imagewidth), int(p.imagelength)
        except Exception:
            pass
    try:
        from PIL import Image as _PI
        with _PI.open(filename) as im:
            return int(im.size[0]), int(im.size[1])
    except Exception:
        return None


def _first_filename(img: ET.Element) -> str | None:
    """The (first) source file of an Image2D element, or None."""
    import ast
    fn = _child_text(img, "filename")
    if not isinstance(fn, str) or fn in ("None", "", _TEMPLATE_SENTINEL):
        return None
    if fn.startswith("[") and fn.endswith("]"):
        try:
            lst = ast.literal_eval(fn)
        except Exception:
            return None
        return lst[0] if lst and isinstance(lst[0], str) else None
    return fn


def _sync_raw_sizes(root: ET.Element) -> int:
    """Make every file-backed Image2D store its TRUE source size.

    New panels created by this server carry no size, and the layout engine then
    assumes a 512x512 placeholder, so every image was laid out as a square until
    the GUI reopened the file. Stale sizes (source replaced by a different-sized
    file) have the same effect. Returns the number of panels updated."""
    n = 0
    for img in root.iter("Image2D"):
        sc = _child_text(img, "custom_loading_script")
        if isinstance(sc, str) and sc not in ("", "None"):
            continue  # scripted panel: size comes from the script's output
        wh = _raw_size_from_file(_first_filename(img))
        if wh is None:
            continue
        cur_w, cur_h = _child_text(img, "width"), _child_text(img, "height")
        try:
            same = abs(float(cur_w) - wh[0]) < 0.5 and abs(float(cur_h) - wh[1]) < 0.5
        except (TypeError, ValueError):
            same = False
        if not same:
            _set_child_text(img, "width", f"{float(wh[0])}")
            _set_child_text(img, "height", f"{float(wh[1])}")
            n += 1
    return n


def _save(tree: ET.ElementTree, pyf_path: str, recompute: bool = False):
    _sync_raw_sizes(tree.getroot())
    ET.indent(tree, space="  ")
    buf = io.StringIO()
    tree.write(buf, encoding="unicode", xml_declaration=True)
    _atomic_write_text(pyf_path, buf.getvalue())
    # source snapshot (<figure>.sources.json): report files that changed since
    # the previous save, then make the current files the reference
    try:
        from pyfigures.source_snapshot import compare_and_record, describe
        changed = describe(compare_and_record(pyf_path, tree.getroot()))
        if changed:
            _warn(changed.replace("\n", " "))
    except Exception as e:           # never block a save on the snapshot
        print(f"pyfigures-mcp: source snapshot skipped ({type(e).__name__}: {e})",
              file=sys.stderr)
    if recompute:
        err = _auto_recompute(pyf_path)
        if err:
            _warn(f"figure saved, but the automatic layout update failed ({err}); "
                  "positions may be stale until the figure is reopened in PyFigures.")


def _auto_recompute(pyf_path: str) -> str:
    """Re-run PyFigures' layout engine on all top-level groups at their current size.

    After structural edits (add/remove images, change orientation/spacing, …)
    the stored x/y positions can be stale.  This function re-deserialises the
    file with the PyFigures engine, calls ``set_to_width`` for every top-level
    group using its stored ``size`` attribute, then re-serialises.

    Then stacks the top-level rows vertically exactly like the GUI's default
    ("auto") layout does on paint, so stored y positions are consistent too.

    Panel scripts (data plots, channel merges, ...) are NOT executed for panels
    that already have a stored size — laying out a figure must not run panel
    code, and re-running every plot's statistics on each edit was slow. Only a
    brand-new scripted panel with no size yet is run once to measure it.

    Returns an empty string on success or a short error description on failure
    (the caller reports it as a warning — layout recompute is best-effort).
    """
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
        from batoolset.figure.alignment import pack2 as _pack2, align2 as _align2, \
            align_positions as _align_positions
    except Exception as exc:
        return f"layout engine unavailable: {exc}"

    try:
        xml_content = Path(pyf_path).read_text(encoding="utf-8")
        space = 3.0
        try:
            sp = ET.fromstring(xml_content).find("SerializableGUIparameters/space")
            if sp is not None and sp.text:
                space = float(sp.text)
        except (ET.ParseError, ValueError):
            pass
        _Image2D._lazy_mode = True
        _Image2D._skip_sized_scripts = True
        try:
            props = _d2d(xml_content)
            objects = _co(list.__name__, props)
        finally:
            _Image2D._lazy_mode = False
            _Image2D._skip_sized_scripts = False

        top_groups = [o for o in objects if isinstance(o, _Group)]
        if not top_groups:
            return ""  # free-canvas figure — nothing to recompute

        for grp in top_groups:
            try:
                w = float(getattr(grp, "size", 0) or 0)
            except (TypeError, ValueError):
                w = 0.0
            if not (math.isfinite(w) and w > 0):
                # no intended width stored: keep the group's current width;
                # a never-packed group has an empty (±inf) rect -> GUI default 512
                cur = float(grp.getRect(all=True).width())
                w = cur if (math.isfinite(cur) and cur > 0) else 512.0
            if len(getattr(grp, "content", [])) > 0:
                _stw(grp, w)

        # vertical stacking, as MyWidget.repack_all() does in auto mode
        drawables = [o for o in objects
                     if hasattr(o, "setTopLeft") and hasattr(o, "getRect")
                     and not (hasattr(o, "content") and len(o.content) == 0)]
        if drawables:
            drawables[0].setTopLeft(50, 50)
            _align2(_align_positions[2], *drawables)
            _pack2(space, "Y", False, *drawables)

        new_xml = _sanitize_recomputed_xml(_to_xml(objects, is_list=True))
        if new_xml is None:
            return ("layout engine produced non-finite geometry; kept the "
                    "positions as saved")
        _atomic_write_text(pyf_path, new_xml)
        return ""
    except Exception as exc:
        return f"layout recompute failed: {type(exc).__name__}: {exc}"


_GEOM_TAGS = ("x", "y", "width", "height")


def _sanitize_recomputed_xml(xml_text: str) -> str | None:
    """Post-process the engine's re-serialised figure.

    An empty group has no extent: the engine reports an infinite/empty rect for
    it, which must not be written (a Group with x=inf / size=-inf fails to load
    and drops its content). Empty groups are therefore written back the way a
    fresh group looks (no geometry, size 512). If any other element still has
    non-finite geometry, returns None so the caller keeps the file unchanged."""
    root = ET.fromstring(xml_text)

    def _finite(el, tag):
        t = el.findtext(tag)
        if t is None:
            return True
        try:
            return math.isfinite(float(t))
        except ValueError:
            return True  # non-numeric field: not geometry we produced

    for grp in root.iter("Group"):
        content = grp.find("content")
        if content is None or len(content) == 0:
            for tag in _GEOM_TAGS:
                el = grp.find(tag)
                if el is not None:
                    grp.remove(el)
            if not _finite(grp, "size"):
                grp.find("size").text = "512.0"
    for el in root.iter():
        if el.tag in ("Group", "Image2D") and not all(
                _finite(el, t) for t in _GEOM_TAGS + ("size", "scale")):
            return None
    # Group IDs come from a process-wide instance counter in the engine (they
    # are reassigned on every load and never read back). Renumber them in
    # document order so the same figure always serialises identically —
    # reproducible, diffable files (e.g. figures rebuilt from a recipe).
    for n, grp in enumerate(root.iter("Group"), start=1):
        id_el = grp.find("ID")
        if id_el is not None:
            id_el.text = str(n)
    out = io.StringIO()
    ET.ElementTree(root).write(out, encoding="unicode", xml_declaration=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Figure-level helpers
# ---------------------------------------------------------------------------

def _top_groups(root: ET.Element) -> list[ET.Element]:
    """Return top-level <Group> elements (direct children of <list>)."""
    return [c for c in root if c.tag == "Group"]


def _all_groups(root: ET.Element) -> list[ET.Element]:
    """BFS over all <Group> elements in the document."""
    result, queue = [], list(root)
    while queue:
        elem = queue.pop(0)
        if elem.tag == "Group":
            result.append(elem)
        queue.extend(list(elem))
    return result


def _html_to_plain(html: str) -> str:
    """Strip Qt HTML to plain text, removing style/head/script blocks first."""
    # Remove block-level noise that carries non-label text (CSS etc.)
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Normalise whitespace
    return " ".join(text.split()).strip()


_TEMPLATE_SENTINEL = "@template@"


def _is_template(img: ET.Element) -> bool:
    """Return True if this Image2D is an unfilled template slot."""
    fn = _child_text(img, "filename")
    return fn == _TEMPLATE_SENTINEL or (fn is None and img.find("template_rect") is not None)


def _template_size(img: ET.Element) -> str:
    """Return 'WxH' from template_rect, or '?' if absent."""
    tr = img.find("template_rect")
    if tr is None or not tr.text:
        return "?"
    # 'PyQt6.QtCore.QRectF(x, y, w, h)'
    m = re.search(r"QRectF\([\d.]+,\s*[\d.]+,\s*([\d.]+),\s*([\d.]+)\)", tr.text)
    if m:
        return f"{int(float(m.group(1)))}x{int(float(m.group(2)))}"
    return "?"


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_NAMED_COLORS: dict[str, int] = {
    "white": 0xFFFFFF, "black": 0, "red": 0xFF0000, "green": 0x00FF00,
    "blue": 0x0000FF, "yellow": 0xFFFF00, "cyan": 0x00FFFF,
    "magenta": 0xFF00FF, "gray": 0x808080, "grey": 0x808080,
    "orange": 0xFF8000, "pink": 0xFF69B4, "purple": 0x800080,
    "lime": 0x00FF00,
}


def _color_to_int(color_spec) -> int:
    """Convert a color specification (name, #rrggbb, or integer) to int."""
    if isinstance(color_spec, (int, float)):
        return int(color_spec)
    s = str(color_spec).strip()
    if s.lower() in _NAMED_COLORS:
        return _NAMED_COLORS[s.lower()]
    # Hex string (#rrggbb, rrggbb, or #rgb)
    s_hex = s.lstrip("#")
    if len(s_hex) == 3 and all(c in "0123456789abcdefABCDEF" for c in s_hex):
        s_hex = s_hex[0] * 2 + s_hex[1] * 2 + s_hex[2] * 2
    if len(s_hex) in (6, 8) and all(c in "0123456789abcdefABCDEF" for c in s_hex):
        return int(s_hex[-6:], 16)
    raise ValueError(
        f"Cannot parse color {color_spec!r}. "
        "Use a name (white, yellow, …), #rrggbb hex, or an integer."
    )


def _label_background_text(spec) -> str:
    """XML value of a TAText2D ``fill_color`` (the box drawn behind a label):
    "none" / "" / False -> "None" (no box), else the colour as an int."""
    if spec is None or spec is False or str(spec).strip().lower() in ("", "none", "transparent"):
        return "None"
    return str(_color_to_int(spec))


def _color_to_hex(color_int: int) -> str:
    return f"#{color_int & 0xFFFFFF:06x}"


# ---------------------------------------------------------------------------
# Scale bar helpers
# ---------------------------------------------------------------------------

def _scale_bar_legend_html(text: str, text_color: str | int = "white") -> str:
    """Return minimal Qt HTML for a scale bar legend label."""
    if isinstance(text_color, int):
        hex_col = _color_to_hex(text_color)
    else:
        s = str(text_color).strip()
        hex_col = _color_to_hex(_color_to_int(s)) if not s.startswith("#") else s
    return f'<font color="{hex_col}">{text}</font>'


def _find_scale_bar(img: ET.Element) -> ET.Element | None:
    """Return the first <ScaleBar> child of <annotations>, or None."""
    annots = img.find("annotations")
    if annots is None:
        return None
    return annots.find("ScaleBar")


def _scalebar_info(sb: ET.Element) -> dict:
    """Extract the key scale bar fields as a plain dict."""
    legend_el = sb.find("legend")
    legend_html = legend_el.text or "" if legend_el is not None else ""
    plain_label = _html_to_plain(legend_html) if legend_html else ""
    return {
        "bar_width_in_units":          _decode(sb.findtext("bar_width_in_units")),
        "unit_to_pixel_conversion_factor": _decode(sb.findtext("unit_to_pixel_conversion_factor")),
        "placement":                   sb.findtext("placement") or "",
        # the drawn colour; files without bar_color draw white whatever `color` says
        "bar_color":                   _decode(sb.findtext("bar_color")) if sb.find("bar_color") is not None
                                       and sb.findtext("bar_color") not in (None, "None") else 0xFFFFFF,
        "isSet":                       _decode(sb.findtext("isSet")),
        "label_plain":                 plain_label,
        "label_html":                  legend_html,
    }


def _new_scalebar_elem(
    bar_width_in_units: float,
    legend_html: str,
    placement: str = "bottom right",
    bar_color: int = 0xFFFFFF,
    px_to_unit: float = 1.0,
) -> ET.Element:
    """Build a complete <ScaleBar> XML element."""
    sb = ET.Element("ScaleBar")
    # Geometry fields are placeholders — PyFigures recomputes on render.
    for tag, val in [
        ("x",                   "0.0"),
        ("y",                   "0.0"),
        ("width",               "50.0"),
        ("height",              "20.0"),
        ("color",               str(int(bar_color))),
        ("fill_color",          "None"),
        ("stroke",              "0.65"),
        ("opacity",             "1.0"),
        ("isSet",               "True"),
        ("scale",               "1"),
        ("line_style",          "None"),
        ("theta",               "0"),
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",           "False"),
        ("__init_called__",     "True"),
        ("__version__",         "1.0"),
        # 'bar' is a Rectangle2D child re-created by ScaleBar.__init__; the
        # reference is passed as **kwargs and ignored during deserialization.
        ("bar",                 "Rectangle2D-placeholder"),
    ]:
        ET.SubElement(sb, tag).text = val
    # legend is TAText2D serialized as raw HTML (no ""..."" double-quote wrap)
    ET.SubElement(sb, "legend").text = legend_html
    ET.SubElement(sb, "bar_width_in_units").text = str(float(bar_width_in_units))
    ET.SubElement(sb, "unit_to_pixel_conversion_factor").text = str(float(px_to_unit))
    ET.SubElement(sb, "placement").text = placement
    # the bar's drawn colour (ScaleBar.bar_color); `color` above is legacy
    ET.SubElement(sb, "bar_color").text = str(int(bar_color))
    return sb


def _apply_scalebar_to_img(
    img: ET.Element,
    bar_width_in_units: float,
    legend_html: str,
    placement: str,
    bar_color: int,
    px_to_unit: float | None,
) -> str:
    """Add or update a ScaleBar on *img*. Returns 'added' or 'updated'."""
    # Optionally update the image-level pixel-size field so PyFigures uses the
    # correct conversion factor when rendering (it overrides the ScaleBar's own
    # unit_to_pixel_conversion_factor at render time from this value).
    if px_to_unit is not None:
        _set_child_text(img, "px_to_unit_conversion_factor", str(float(px_to_unit)))

    annots = img.find("annotations")
    if annots is None:
        annots = ET.SubElement(img, "annotations")

    sb = annots.find("ScaleBar")
    if sb is not None:
        # Update existing fields in-place
        _set_child_text(sb, "bar_width_in_units", str(float(bar_width_in_units)))
        legend_el = sb.find("legend")
        if legend_el is None:
            legend_el = ET.SubElement(sb, "legend")
        legend_el.text = legend_html
        _set_child_text(sb, "placement", placement)
        _set_child_text(sb, "color", str(int(bar_color)))
        _set_child_text(sb, "bar_color", str(int(bar_color)))   # what is drawn
        _set_child_text(sb, "isSet", "True")
        if px_to_unit is not None:
            _set_child_text(sb, "unit_to_pixel_conversion_factor", str(float(px_to_unit)))
        return "updated"
    else:
        eff_px = px_to_unit if px_to_unit is not None else 1.0
        annots.append(_new_scalebar_elem(bar_width_in_units, legend_html, placement, bar_color, eff_px))
        return "added"


def _image_summary(img: ET.Element, idx: int, prefix: str = "") -> str:
    if _is_template(img):
        ts = _template_size(img)
        script = _child_text(img, "custom_loading_script")
        script_tag = "  [has script]" if script is not None else ""
        return f"{prefix}Image {idx}: <template slot>  [{ts}]{script_tag}  (use fill_template() to assign a file)"
    filename = _child_text(img, "filename") or ""
    filename = Path(filename).name if filename else "<no file>"
    annotations = img.find("annotations")
    annot_parts = []
    if annotations is not None:
        for ta in annotations.findall("TAText2D"):
            raw = _child_text(ta, "text") or ""
            plain = _html_to_plain(raw)[:40]
            placement = _child_text(ta, "placement") or ""
            annot_parts.append(f'"{plain}" ({placement})')
    annot_str = ", ".join(annot_parts) if annot_parts else "—"
    w = _child_text(img, "width")
    h = _child_text(img, "height")
    size_str = f"{int(w)}x{int(h)}" if isinstance(w, (int, float)) and isinstance(h, (int, float)) else "?"
    script = _child_text(img, "custom_loading_script")
    script_tag = "  [has script]" if script is not None else ""
    # Scale bar summary
    sb = _find_scale_bar(img)
    if sb is not None:
        bw = sb.findtext("bar_width_in_units") or "?"
        pl = sb.findtext("placement") or ""
        legend_el = sb.find("legend")
        lbl = _html_to_plain(legend_el.text or "") if legend_el is not None else ""
        sb_tag = f"  [scale bar: {lbl or bw} {pl}]"
    else:
        sb_tag = ""
    # Inset summary
    annots_el = img.find("annotations")
    n_insets = len([c for c in annots_el if c.tag == "Image2D"]) if annots_el is not None else 0
    inset_tag = f"  [{n_insets} inset(s)]" if n_insets else ""
    return f"{prefix}Image {idx}: {filename}  [{size_str}]  annotations: {annot_str}{script_tag}{sb_tag}{inset_tag}"


def _is_label_row_group(grp: ET.Element) -> bool:
    """Return True if this Group is a text-row/label-row (isText != False)."""
    ist = grp.findtext("isText", "False")
    return ist not in ("False", "")


def _label_row_summary(grp: ET.Element, label: str, depth: int = 0) -> list[str]:
    """One-line summary for a text-row Group."""
    pad = "  " * depth
    ist = _decode(grp.findtext("isText", "False")) or "?"
    content = grp.find("content")
    texts = []
    if content is not None:
        for img in content:
            if img.tag == "Image2D":
                ann = img.find("annotations")
                if ann is not None:
                    for ta in ann.findall("TAText2D"):
                        raw = _child_text(ta, "text") or ""
                        plain = _html_to_plain(raw)[:30]
                        texts.append(f'"{plain}"')
    texts_str = ", ".join(texts) if texts else "(empty)"
    return [f"{pad}{label} [LABEL ROW, position={ist!r}]: {texts_str}"]


def _group_summary(grp: ET.Element, label: str, depth: int = 0) -> list[str]:
    pad = "  " * depth
    if _is_label_row_group(grp):
        return _label_row_summary(grp, label, depth)
    orientation = _child_text(grp, "orientation") or "?"
    space = _child_text(grp, "space")
    content = grp.find("content")
    children = list(content) if content is not None else []
    lines = [f"{pad}{label} [orientation={orientation}, spacing={space}, {len(children)} children]"]
    for i, child in enumerate(children):
        if child.tag == "Group":
            lines.extend(_group_summary(child, f"Group {label}.{i}", depth + 1))
        elif child.tag == "Image2D":
            ist = child.findtext("isText", "False")
            if ist == "True":
                # inline side label — show its text
                ann = child.find("annotations")
                texts = []
                if ann is not None:
                    for ta in ann.findall("TAText2D"):
                        plain = _html_to_plain(_child_text(ta, "text") or "")[:30]
                        texts.append(f'"{plain}"')
                lines.append(f"{pad}  Side-label {i}: {', '.join(texts) or '(empty)'}")
            else:
                lines.append(_image_summary(child, i, pad + "  "))
    return lines


# ---------------------------------------------------------------------------
# Element factories (used by the creation/mutation tools below)
# ---------------------------------------------------------------------------

def _new_image2d(filename: str) -> ET.Element:
    """Create an Image2D element matching the current PyFigures schema.

    Field set is derived from real GUI-saved .pyf files to ensure
    round-trip compatibility.  All positioning fields (x, y, width, height,
    scale) are left at 0 / 1.0 — PyFigures recomputes them on first render.
    """
    img = ET.Element("Image2D")
    for tag, val in [
        # ── identity / positioning ────────────────────────────────────────
        ("filename",        _encode_str(filename)),
        # ── image options ─────────────────────────────────────────────────
        ("projection",              "None"),
        ("projection_z_start",      "None"),   # Z-stack range (new field)
        ("projection_z_end",        "None"),
        ("normalization",           "None"),
        ("isText",                  "False"),
        ("channels",                _encode_str("None")),
        ("LUTs",                    "None"),
        ("dimensions",              "None"),
        # ── publication settings (new fields) ────────────────────────────
        ("publication_style",           "True"),
        ("publication_font_size",       "12"),
        ("publication_line_width",      "0.65"),
        ("publication_font",            _encode_str("Arial")),
        ("publication_svg_stroke_width","0.65"),
        ("_raw_svg_bytes",              "None"),
        # ── misc ──────────────────────────────────────────────────────────
        ("px_to_unit_conversion_factor", "0"),
        ("user_comments",   _encode_str("")),
        ("custom_loading_script", "None"),
        ("serie_to_open",   "None"),           # multi-series (LIF, CZI)
        ("crop_left",       "0"),
        ("crop_right",      "0"),
        ("crop_top",        "0"),
        ("crop_bottom",     "0"),
        ("line_style",      "None"),
        ("placement",       "top right"),
        ("fraction_of_parent_image_width_if_image_is_inset", "0.25"),
        ("border_size",     "None"),
        ("border_color",    "16777215"),
        ("lower_indices",   "None"),
        ("lower_values",    "None"),
        ("upper_indices",   "None"),
        ("upper_values",    "None"),
        ("color",           "16777215"),
        ("fill_color",      "None"),
        ("stroke",          "0.65"),
        ("opacity",         "1"),
        ("isSet",           "False"),
        ("scale",           "1.0"),
        ("theta",           "None"),           # must be None, not 0
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",       "False"),
        ("__init_called__", "True"),
        ("__version__",     "1.0"),
        # QPointF translation — required by newer batoolset deserialization
        ("translation",     "PyQt6.QtCore.QPointF()"),
    ]:
        ET.SubElement(img, tag).text = val
    # extra_user_translation: two empty <int/> elements (x, y offsets).
    # Older batoolset used <str>str</str> — that format causes load errors
    # in current versions.
    etu = ET.SubElement(img, "extra_user_translation")
    ET.SubElement(etu, "int")
    ET.SubElement(etu, "int")
    ET.SubElement(img, "annotations")
    return img


_PANEL_LETTER_RE = re.compile(r"^\(?[A-Za-z]{1,2}\)?\.?$")


def _looks_like_panel_letter(text: str) -> bool:
    """'A', 'b', '(c)', 'AA', 'D.' are panel letters; 'Merge', 'WT', 'GFP' are
    descriptive labels. (Two-letter all-caps like 'WT' are treated as letters
    only when they are a doubled letter such as 'AA'.)"""
    t = _strip_tags(text or "").strip()
    if not _PANEL_LETTER_RE.match(t):
        return False
    core = t.strip("().")
    return len(core) == 1 or (len(core) == 2 and core[0].lower() == core[1].lower())


def _new_tatext2d(text: str, placement: str = "top left",
                  is_letter: bool | None = None,
                  color: int | None = None) -> ET.Element:
    """Create a TAText2D annotation element.

    *is_letter*: None = decide from the text. Only real panel letters may be
    flagged: the GUI's auto-lettering renames every is_letter annotation to
    A, B, C…, which silently replaced descriptive labels such as "Merge".
    *color*: 0xRRGGBB text colour, None = PyFigures default (black). Applied
    through the label's rich text — TAText2D's ``color`` field is not the
    glyph colour."""
    if is_letter is None:
        is_letter = _looks_like_panel_letter(text)
    if color is not None:
        text = f'<font color=#{int(color) & 0xFFFFFF:06x}>{text}</font>'
    ta = ET.Element("TAText2D")
    for tag, val in [
        ("text",            _encode_str(text)),
        ("color",           "None"),
        ("fill_color",      "None"),
        ("stroke",          "0.65"),
        ("opacity",         "1.0"),
        ("isSet",           "False"),
        ("scale",           "1"),
        ("line_style",      "None"),
        ("theta",           "0"),
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",       "True"),
        ("__init_called__", "True"),
        ("__version__",     "1.0"),
        ("placement",       placement),
        ("text_orientation", _encode_str("X")),
        ("range",           "None"),
        ("_TAText2D__version", "1.0"),
        ("is_letter",       "True" if is_letter else "False"),
    ]:
        ET.SubElement(ta, tag).text = val
    return ta


def _new_group_elem(orientation: str = "X", space: int = 3, group_id: int = 1) -> ET.Element:
    """Create a new empty Group element."""
    grp = ET.Element("Group")
    ET.SubElement(grp, "content")
    for tag, val in [
        ("space",       str(space)),
        ("orientation", _encode_str(orientation)),
        ("size",        "512.0"),
        ("ID",          str(group_id)),
        ("fill_color",  "None"),
        ("immutable",   "False"),
        ("isText",      "False"),
    ]:
        ET.SubElement(grp, tag).text = val
    return grp


def _next_group_id(root: ET.Element) -> int:
    """Return one more than the highest existing group ID (or 1 if none)."""
    ids: set[int] = set()
    for grp in _all_groups(root):
        id_el = grp.find("ID")
        if id_el is not None and id_el.text:
            try:
                ids.add(int(id_el.text))
            except ValueError:
                pass
    return max(ids, default=0) + 1


def _navigate_group(root: ET.Element, group_path: list[int]) -> tuple[ET.Element | None, str]:
    """Navigate to a Group element by path.

    [0]    → first top-level Group.
    [0, 1] → second sub-Group inside first top-level Group.
    Returns (element, ""). On failure returns (None, error_message).
    """
    if not group_path:
        return None, "group_path must not be empty"
    tops = _top_groups(root)
    if group_path[0] >= len(tops):
        return None, f"top-level group index {group_path[0]} out of range ({len(tops)} groups)"
    current = tops[group_path[0]]
    for depth, sub_idx in enumerate(group_path[1:], start=1):
        content = current.find("content")
        if content is None:
            return None, f"group at depth {depth - 1} has no <content>"
        sub_groups = [c for c in content if c.tag == "Group"]
        if sub_idx >= len(sub_groups):
            return None, (
                f"sub-group index {sub_idx} out of range at depth {depth} "
                f"({len(sub_groups)} sub-groups)"
            )
        current = sub_groups[sub_idx]
    return current, ""


def _get_container(
    root: ET.Element,
    group_path: list[int],
    refuse_label_rows: bool = False,
) -> tuple[ET.Element | None, str]:
    """Return the direct parent element of Image2D items.

    []     → root itself (free-canvas mode: images are direct children of <list>).
    [i]    → <content> element of top-level group i.
    [i, j] → <content> element of sub-group j inside group i.

    When *refuse_label_rows* is True (used by all image-writing tools) an error
    is returned if the resolved group is a label-row group (isText != False).
    Label-row groups only hold text cells; adding image panels to them is illegal
    and will crash PyFigures.

    Returns (element, ""). On failure returns (None, error_message).
    """
    if not group_path:
        return root, ""          # free-canvas: images live directly under <list>
    grp, err = _navigate_group(root, group_path)
    if err:
        return None, err
    if refuse_label_rows and _is_label_row_group(grp):
        tops = _top_groups(root)
        content_paths = [
            f"[{i}]" for i, g in enumerate(tops)
            if not _is_label_row_group(g)
        ]
        return None, (
            f"group {group_path} is a label-row group (isText != False) — "
            "it only holds text cells and cannot contain image panels. "
            f"Content groups in this figure: {', '.join(content_paths) or 'none'}. "
            "Call describe_figure() to identify the correct group_path."
        )
    content = grp.find("content")
    if content is None:
        content = ET.SubElement(grp, "content")
    return content, ""


def _append_image(container: ET.Element, img: ET.Element, is_root: bool = False):
    """Append *img* to *container*.

    When *container* is the root <list> element (free-canvas mode), the image
    is inserted before the metadata trailer elements so the order stays clean:
    Image2D* → SerializableQFont → SerializableGUIparameters.
    """
    if is_root:
        _METADATA_TAGS = {"SerializableQFont", "SerializableGUIparameters"}
        insert_pos = len(list(container))
        for i, child in enumerate(container):
            if child.tag in _METADATA_TAGS:
                insert_pos = i
                break
        container.insert(insert_pos, img)
    else:
        container.append(img)


# ---------------------------------------------------------------------------
# Additional MCP Tools
# ---------------------------------------------------------------------------

_ROI_PROTECTED = {"ScaleBar", "Image2D"}  # never removed by remove_annotation


def _roi_children(annots: ET.Element) -> list[ET.Element]:
    """All annotation children that can be listed/removed (excludes ScaleBar + insets)."""
    return [c for c in annots if c.tag not in _ROI_PROTECTED]


def _describe_roi(el: ET.Element, idx: int) -> dict:
    """Return a concise dict description of any annotation element."""
    t = el.tag
    base = {"annotation_index": idx, "type": t}
    if t == "TAText2D":
        raw = _child_text(el, "text") or ""
        base["text"] = _html_to_plain(raw)
        base["placement"] = _child_text(el, "placement") or ""
    elif t in ("Rectangle2D", "Ellipse2D"):
        for k in ("x", "y", "width", "height"):
            v = _child_text(el, k)
            base[k] = float(v) if v is not None else None
        base["color"] = _child_text(el, "color")
        base["fill_color"] = _child_text(el, "fill_color")
    elif t == "Line2D":
        for k in ("x1", "y1", "x2", "y2"):
            v = _child_text(el, k)
            base[k] = float(v) if v is not None else None
        base["arrow"] = _child_text(el, "arrow")
        base["color"] = _child_text(el, "color")
    elif t in ("Polygon2D", "PolyLine2D", "Freehand2D"):
        raw = _child_text(el, "coords_as_list") or "[]"
        try:
            import ast as _ast
            flat = _ast.literal_eval(raw)
            pts = [[flat[i], flat[i + 1]] for i in range(0, len(flat) - 1, 2)]
        except Exception:
            pts = []
        base["points"] = pts
        base["color"] = _child_text(el, "color")
    elif t == "ScaleBar":
        base["type"] = "scale_bar (protected)"
    elif t == "Image2D":
        base["type"] = "inset (protected)"
    return base


# ---------------------------------------------------------------------------
# Journal presets  (width in mm: single / 1.5-column / double)
# ---------------------------------------------------------------------------
_JOURNAL_PRESETS: dict[str, dict[str, float]] = {
    # key        single   1.5-col   double
    "nature":    {"single": 89,  "1.5": 136, "double": 183},
    "science":   {"single": 55,  "1.5": 114, "double": 168},
    "cell":      {"single": 85,  "1.5": 128, "double": 170},
    "plos":      {"single": 83,  "1.5": 129, "double": 174},
    "elife":     {"single": 85,  "1.5": 132, "double": 178},
    "embo":      {"single": 82,  "1.5": 127, "double": 172},
    "elsevier":  {"single": 90,  "1.5": 140, "double": 190},
    "springer":  {"single": 84,  "1.5": 129, "double": 174},
    "wiley":     {"single": 86,  "1.5": 132, "double": 178},
    "jcb":       {"single": 85,  "1.5": 128, "double": 170},   # Journal of Cell Biology
    "pnas":      {"single": 87,  "1.5": 131, "double": 178},
}

# Normalise aliases
_JOURNAL_ALIASES = {
    "nature communications": "nature",
    "nature methods": "nature",
    "nature cell biology": "nature",
    "nature medicine": "nature",
    "science advances": "science",
    "cell reports": "cell",
    "current biology": "cell",
    "developmental cell": "cell",
    "plos biology": "plos",
    "plos genetics": "plos",
    "plos one": "plos",
    "journal of cell biology": "jcb",
}


def _width_mm_for_journal(journal: str, column: str) -> float:
    """Return the target width in mm for a journal + column-count combination."""
    j = journal.lower().strip()
    j = _JOURNAL_ALIASES.get(j, j)
    presets = _JOURNAL_PRESETS.get(j)
    if presets is None:
        raise ValueError(
            f"Unknown journal {journal!r}. "
            f"Known journals: {', '.join(sorted(_JOURNAL_PRESETS))}."
        )
    col = column.lower().strip().rstrip("s")  # "columns" → "column", "singles" → "single"
    col_map = {"single": "single", "1": "single", "one": "single",
               "1.5": "1.5", "half": "1.5",
               "double": "double", "2": "double", "two": "double", "full": "double"}
    col_key = col_map.get(col)
    if col_key is None:
        raise ValueError(f"Unknown column {column!r}. Use 'single', '1.5', or 'double'.")
    return presets[col_key]


# ---------------------------------------------------------------------------
# ROI helpers
# ---------------------------------------------------------------------------

def _flatten_points(points) -> list[float]:
    """Accept [[x,y],...] or [x,y,x,y,...] — return flat float list."""
    if not points:
        return []
    if isinstance(points[0], (list, tuple)):
        flat = []
        for p in points:
            flat.extend([float(p[0]), float(p[1])])
        return flat
    return [float(v) for v in points]


def _roi_fill_color_str(fill_color) -> str:
    if fill_color is None:
        return "None"
    return str(_color_to_int(fill_color))


def _new_roi_rect(
    x: float, y: float, w: float, h: float,
    color: int, fill_color, stroke: float, opacity: float,
) -> ET.Element:
    el = ET.Element("Rectangle2D")
    for tag, val in [
        ("x", str(float(x))), ("y", str(float(y))),
        ("width", str(float(w))), ("height", str(float(h))),
        ("color", str(color)), ("fill_color", _roi_fill_color_str(fill_color)),
        ("stroke", str(float(stroke))), ("opacity", str(float(opacity))),
        ("isSet", "False"), ("scale", "1"), ("line_style", "None"),
        ("theta", "0"), ("incompressible_width", "0"), ("incompressible_height", "0"),
        ("immutable", "False"), ("__init_called__", "True"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_roi_ellipse(
    x: float, y: float, w: float, h: float,
    color: int, fill_color, stroke: float, opacity: float,
) -> ET.Element:
    el = ET.Element("Ellipse2D")
    for tag, val in [
        ("x", str(float(x))), ("y", str(float(y))),
        ("width", str(float(w))), ("height", str(float(h))),
        ("color", str(color)), ("fill_color", _roi_fill_color_str(fill_color)),
        ("stroke", str(float(stroke))), ("opacity", str(float(opacity))),
        ("scale", "1"), ("line_style", "None"),
        ("theta", "0"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_roi_line(
    x1: float, y1: float, x2: float, y2: float,
    color: int, stroke: float, opacity: float,
    arrow: bool, arrow_at_both_ends: bool,
    head_width_scaler: float = 4, head_length_scaler: float = 12,
) -> ET.Element:
    """Line2D ROI. With *arrow* the head's point is exactly (x2, y2) (and
    (x1, y1) for a double arrow); its half-width / length are the stroke times
    *head_width_scaler* / *head_length_scaler*."""
    el = ET.Element("Line2D")
    for tag, val in [
        ("x1", str(float(x1))), ("y1", str(float(y1))),
        ("x2", str(float(x2))), ("y2", str(float(y2))),
        ("color", str(color)), ("stroke", str(float(stroke))),
        ("opacity", str(float(opacity))), ("scale", "1"),
        ("line_style", "None"), ("theta", "0"),
        ("arrow", str(arrow)), ("arrow_at_both_ends", str(arrow_at_both_ends)),
        ("arrowhead_width_scaler", repr(head_width_scaler)),
        ("arrowhead_height_scaler", repr(head_length_scaler)),
        ("fill_color", "None"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_roi_polygon(
    flat_coords: list[float],
    shape_tag: str,  # "Polygon2D" | "PolyLine2D" | "Freehand2D"
    color: int, fill_color, stroke: float, opacity: float,
) -> ET.Element:
    el = ET.Element(shape_tag)
    ET.SubElement(el, "coords_as_list").text = str(flat_coords)
    for tag, val in [
        ("isSet", "False"),
        ("color", str(color)), ("fill_color", _roi_fill_color_str(fill_color)),
        ("stroke", str(float(stroke))), ("opacity", str(float(opacity))),
        ("scale", "1"), ("line_style", "None"), ("theta", "0"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_free_text(html: str, x: float, y: float) -> ET.Element:
    """A TAText2D placed at an absolute image-pixel (x, y) rather than snapped to
    a corner. placement='None' makes it 'free/relative' so it draws at its own
    coordinates (like a ROI line), which is what significance labels need."""
    ta = ET.Element("TAText2D")
    for tag, val in [
        ("x",               str(float(x))),
        ("y",               str(float(y))),
        ("text",            _encode_str(html)),
        ("color",           "None"),
        ("fill_color",      "None"),
        ("stroke",          "0.65"),
        ("opacity",         "1.0"),
        ("isSet",           "False"),
        ("scale",           "1"),
        ("line_style",      "None"),
        ("theta",           "0"),
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",       "True"),
        ("__init_called__", "True"),
        ("__version__",     "1.0"),
        ("placement",       "None"),
        ("text_orientation", _encode_str("X")),
        ("range",           "None"),
        ("_TAText2D__version", "1.0"),
        ("is_letter",       "False"),
    ]:
        ET.SubElement(ta, tag).text = val
    return ta


def _get_annots_for_roi(root, group_path, image_index):
    """Return (tree, annots_el, err) for a ROI-add operation."""
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return None, None, err
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return None, None, f"image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    annots = img.find("annotations")
    if annots is None:
        annots = ET.SubElement(img, "annotations")
    return img, annots, ""


# ---------------------------------------------------------------------------
# Figure caption / legend
# ---------------------------------------------------------------------------

def _caption_sidecar_path(pyf_path: str) -> str:
    """Caption store: a JSON sidecar beside the .pyf (same stem). Kept OUT of the
    .pyf XML on purpose — unknown fields break SerializableGUIparameters
    deserialization (resets the figure's real font/spacing on GUI load)."""
    return os.path.splitext(pyf_path)[0] + ".caption.json"


def _read_caption(pyf_path: str):
    p = _caption_sidecar_path(pyf_path)
    if not os.path.isfile(p):
        return None, None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("title"), d.get("caption")
    except Exception:
        return None, None


def _stats_sidecar_path(pyf_path: str) -> str:
    """Statistics-provenance store: a JSON sidecar beside the .pyf (same stem),
    kept OUT of the figure XML for the same reason as the caption sidecar. Holds
    one entry per data-driven test (data plots + significance brackets) so the
    adjustment ledger can report the exact tests and p-values used."""
    return os.path.splitext(pyf_path)[0] + ".stats.json"


def _read_stats(pyf_path: str) -> list:
    p = _stats_sidecar_path(pyf_path)
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _append_stats_entry(pyf_path: str, entry: dict):
    entries = _read_stats(pyf_path)
    entries.append(entry)
    _atomic_write_text(_stats_sidecar_path(pyf_path),
                       json.dumps(entries, ensure_ascii=False, indent=2))


def _clear_derived_sidecars(pyf_path: str) -> list[str]:
    """Remove the sidecars that describe a figure's CONTENT (statistics record,
    alt text) — used when a new figure replaces the file, so the Methods text
    and alt text never report panels of the previous figure. The caption
    (author prose) is kept. Returns the removed paths."""
    removed = []
    stem = os.path.splitext(pyf_path)[0]
    for p in (_stats_sidecar_path(pyf_path), stem + ".alttext.json"):
        if os.path.isfile(p):
            os.remove(p)
            removed.append(p)
    return removed


def _auto_test_via_staplot(columns: dict):
    """Run staplot's auto_test on ``{group: [values]}`` and return its record,
    or None if staplot is unavailable. Soft dependency — never raises on import."""
    try:
        from staplot import api as _api
    except Exception:
        return None
    try:
        tbl = _api.table_from_columns(columns)
        return _api.auto_test(tbl)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# Journal-guidelines compliance: resolution, font size, and one-shot reformat
# ---------------------------------------------------------------------------

_MCP_QAPP = None  # module-level hold for the QApplication (must not be GC'd)


def _resolve_target_mm(
    journal: str | None, column: str,
    width_mm: float | None, width_cm: float | None, width_in: float | None,
) -> tuple[float, str]:
    """Resolve a target physical figure width (mm) from journal preset or explicit
    units. Raises ValueError if nothing usable is given."""
    if journal is not None:
        mm = _width_mm_for_journal(journal, column)
        return mm, f"{journal!r} {column}-column = {mm:.0f}mm"
    if width_mm is not None:
        return float(width_mm), f"{width_mm}mm"
    if width_cm is not None:
        return float(width_cm) * 10.0, f"{width_cm}cm"
    if width_in is not None:
        return float(width_in) * 25.4, f"{width_in}in"
    raise ValueError("specify a target width — one of: journal, width_mm, width_cm, width_in.")


def _load_objects_lazy(pyf_path: str):
    """Deserialize a .pyf into PyFigures objects without loading pixel data.
    Returns (objects_list, Group_cls, Image2D_cls). Raises on import/parse error."""
    from batoolset.settings.global_settings import set_UI as _set_UI
    _set_UI()
    from qtpy.QtWidgets import QApplication as _QApp
    import sys as _sys
    # keep a reference — a QApplication that is garbage-collected crashes (0xC0000409)
    global _MCP_QAPP
    if _QApp.instance() is None:
        from pyfigures.offscreen import ensure_offscreen_fonts
        ensure_offscreen_fonts()     # offscreen on Windows has no fonts otherwise
    _MCP_QAPP = _QApp.instance() or _QApp(_sys.argv[:1])
    from batoolset.drawings.shapes.image2d import Image2D as _Image2D
    from batoolset.drawings.shapes.group import Group as _Group
    from batoolset.serializations.tools import (
        deserialize_to_dict as _d2d, create_object as _co,
    )
    from ..path_resolution import resolve_moved_paths
    xml_content, _ = resolve_moved_paths(Path(pyf_path).read_text(encoding="utf-8"), pyf_path)
    _Image2D._lazy_mode = True
    try:
        objects = _co(list.__name__, _d2d(xml_content))
    finally:
        _Image2D._lazy_mode = False
    return objects, _Group, _Image2D


# ---------------------------------------------------------------------------
# heavy GUI ops exposed via a headless subprocess (video / consolidate)
# ---------------------------------------------------------------------------
def _run_headless_op(args: list[str], timeout: int = 600):
    """Run pyfigures.gui.headless_ops in a subprocess. Returns (ok, message)."""
    cmd = [sys.executable, "-m", "pyfigures.gui.headless_ops", *args]
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_API", "pyqt6")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"operation timed out after {timeout}s"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "operation failed").strip()
    return True, (proc.stdout or "").strip()


def _iter_panel_elements(root: ET.Element):
    """Yield Image2D elements that are real layout panels — not the ones nested
    inside a panel's annotations / insets / ScaleBar."""
    parent = {c: p for p in root.iter() for c in p}
    for img in root.iter("Image2D"):
        node, skip = img, False
        while node in parent:
            node = parent[node]
            if node.tag in ("annotations", "insets", "ScaleBar"):
                skip = True
                break
        if not skip:
            yield img
