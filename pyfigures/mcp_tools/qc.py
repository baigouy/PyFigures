"""PyFigures MCP tools — Journal QC: resolution, scale consistency, minimum font size, journal compliance and guidelines.

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
    _child_text,
    _decode,
    _encode_str,
    _figure_height_mm,
    _find_scale_bar,
    _journal_max_height,
    _stored_target,
    _load,
    _load_objects_lazy,
    _resolve_target_mm,
    _resolve_target_for,
    _save,
    _set_child_text,
    _top_groups,
)
from .structure import (
    add_corner_labels,
    resize_figure,
)
from .annotations import (
    set_figure_properties,
)
from .overlays import (
    set_scale_bar_all,
)

def _is_raster_panel(img) -> bool:
    """A panel made of pixels (it has a print resolution and a pixel scale):
    not text, not an SVG/PDF, and not a data plot / colour bar, which are drawn
    as vectors (a box plot was rated at ~70 DPI and models then blamed the plot).
    Image-like script panels (channel merges) mark themselves as images."""
    if getattr(img, "isText", False):
        return False
    fn = img.filename
    if isinstance(fn, str) and fn.lower().endswith((".svg", ".pdf")):
        return False
    script = getattr(img, "custom_loading_script", None)
    if not fn and not script and getattr(img, "img", None) is None:
        return False                    # empty placeholder (pads a grid / montage row)
    if isinstance(script, str) and ("staplot" in script or "ColorbarBase(" in script) \
            and "_pyfigures_image_panel" not in script:
        return False
    return True


def _where(img, loc):
    """'panel B (group 0, img 1)': the letter the reader sees, then where
    the MCP tools find it; just *loc* for a panel without a letter."""
    for a in getattr(img, "annotations", None) or []:
        if getattr(a, "is_letter", False):
            try:
                letter = a.getPlainText().strip()
            except Exception:
                letter = ""
            if letter:
                return f"panel {letter} ({loc})"
    return loc


def _panel_resolutions(pyf_path: str, target_mm: float) -> list[dict]:
    """Return one dict per raster panel describing its effective print resolution
    if the figure were printed *target_mm* wide. Vector (svg) and text panels are
    skipped. Fields: label, filename, raw_w, raw_h, display_w, physical_mm, dpi."""
    objects, Group, Image2D = _load_objects_lazy(pyf_path)

    def _imgs_in(group):
        out = []
        for c in getattr(group, "content", []):
            if isinstance(c, Image2D):
                out.append(c)
            elif isinstance(c, Group):
                out.extend(_imgs_in(c))
        return out

    _is_real_raster = _is_raster_panel

    def _one(img, denom_w, letter):
        try:
            raw_w, raw_h = img.get_raw_size()
        except Exception:
            raw_w, raw_h = None, None
        disp = img.width(all=True)
        frac = (disp / denom_w) if denom_w else 0.0
        phys_mm = frac * target_mm
        dpi = (raw_w / (phys_mm / 25.4)) if (raw_w and phys_mm > 0) else None
        return {
            "label": letter,
            "filename": os.path.basename(str(img.filename)) if img.filename else "(in-memory)",
            "raw_w": raw_w, "raw_h": raw_h,
            "display_w": round(disp, 1),
            "physical_mm": round(phys_mm, 2),
            "dpi": round(dpi) if dpi else None,
        }

    results: list[dict] = []
    top_groups = [o for o in objects if isinstance(o, Group)]
    free_imgs = [o for o in objects if isinstance(o, Image2D)]

    for gi, grp in enumerate(top_groups):
        denom = grp.width(all=True)
        for ii, img in enumerate(_imgs_in(grp)):
            if not _is_real_raster(img):
                continue
            results.append(_one(img, denom, _where(img, f"group {gi}, img {ii}")))

    if free_imgs:
        canvas_w = max((im.x() + im.width(all=True)) for im in free_imgs)
        for ii, img in enumerate(free_imgs):
            if not _is_real_raster(img):
                continue
            results.append(_one(img, canvas_w, _where(img, f"canvas img {ii}")))

    return results


def _micrographs_without_bar(root) -> tuple[list, int]:
    """(panel elements still needing a scale bar, number of micrographs).

    Micrographs are real image panels: not text labels, not inset images, not
    scripted panels (data plots, colour bars, equations). The panels of one
    montage / channel split are ONE micrograph — the usual convention is one bar
    per series (on its last panel), which the recipes and tools follow; counting
    each panel reported such figures as missing most of their bars. A series
    without any bar is reported by its last panel."""
    from .stacks import SERIES_MARK
    from .core import _iter_panel_elements
    parent = {c: p for p in root.iter() for c in p}
    units: dict = {}
    from .core import _is_empty_placeholder
    for img in _iter_panel_elements(root):
        if _child_text(img, "isText") is not False or _is_empty_placeholder(img):
            continue
        script = _child_text(img, "custom_loading_script")
        if isinstance(script, str) and script not in ("", "None"):
            continue
        comment = str(_decode(img.findtext("user_comments")) or "")
        key = parent.get(img) if comment.startswith(SERIES_MARK) else img
        has_bar, _ = units.get(key, (False, None))
        units[key] = (has_bar or _find_scale_bar(img) is not None, img)
    return [img for has_bar, img in units.values() if not has_bar], len(units)


def _scale_bar_coverage(root) -> tuple[int, int]:
    """(micrographs with a scale bar, micrographs) for the scale-bar rule."""
    missing, n = _micrographs_without_bar(root)
    return n - len(missing), n


@mcp.tool()
def check_resolution(
    pyf_path: str,
    min_dpi: int = 300,
    journal: str | None = None,
    column: str = "single",
    width_mm: float | None = None,
    width_cm: float | None = None,
    width_in: float | None = None,
) -> str:
    """Report the effective print resolution of every raster panel *if the figure
    were printed at the target physical width*, and flag panels below *min_dpi*.

    A panel's effective DPI = (its source pixels) / (its printed width in inches).
    Panels scaled up to fill space lose resolution; this catches the ones that
    would look soft or pixelated at the journal's column width. Vector (SVG) and
    text-label panels are ignored (resolution-independent).

    Specify the target width via *journal*+*column* (e.g. journal="nature",
    column="double") or explicit *width_mm* / *width_cm* / *width_in*.
    Typical requirements: 300 DPI (photographic/halftone), 600 DPI (line art).

    Example::

        check_resolution("fig.pyf", min_dpi=300, journal="nature", column="single")
    """
    try:
        target_mm, src = _resolve_target_for(pyf_path, journal, column, width_mm, width_cm, width_in)
    except ValueError as e:
        return f"ERROR: {e}"
    try:
        panels = _panel_resolutions(pyf_path, target_mm)
    except Exception as e:
        return f"ERROR: could not analyse resolution — {e}"
    if not panels:
        return f"No raster panels found to check (target {src})."

    lines = [f"Resolution check at {src} (min {min_dpi} DPI):"]
    n_bad = 0
    for p in panels:
        if p["dpi"] is None:
            flag, note = "?", "unknown source size"
        elif p["dpi"] < min_dpi:
            flag, note = "FAIL", f"{p['dpi']} DPI — needs a smaller display size or a higher-res source"
            n_bad += 1
        else:
            flag, note = "ok", f"{p['dpi']} DPI"
        lines.append(
            f"  [{flag}] {p['label']} ({p['filename']}): "
            f"{p['raw_w']}x{p['raw_h']} px -> {p['physical_mm']}mm wide -> {note}"
        )
    lines.append("")
    lines.append(
        f"Summary: {len(panels) - n_bad}/{len(panels)} panel(s) meet {min_dpi} DPI."
        if n_bad == 0 else
        f"Summary: {n_bad}/{len(panels)} panel(s) BELOW {min_dpi} DPI — show them "
        f"smaller (e.g. more panels per row or a narrower figure) or use a "
        f"higher-resolution source. Do not upsample the image: it adds no detail."
    )
    return "\n".join(lines)


def _raw_width_from_file(filename) -> int | None:
    """Read an image's source-pixel width from its file header without decoding
    the pixels. Returns None for non-file / unreadable / multi-series formats."""
    if not filename or not isinstance(filename, str):
        return None
    if filename.split("#", 1)[0].rstrip("/\\").lower().endswith(".zarr"):
        try:                       # OME-Zarr (local or URL): the level that is read
            from batoolset.ome_zarr import level_size
            return level_size(filename)[1]
        except Exception:
            return None
    from batoolset.omero_web import is_omero_url
    if is_omero_url(filename):
        try:                       # OMERO image: its size from OMERO.web
            from batoolset.omero_web import size_of
            return size_of(filename)[0]
        except Exception:
            return None
    if not os.path.isfile(filename):
        return None
    low = filename.lower()
    if low.endswith((".tif", ".tiff")):
        try:
            import tifffile as _tf
            with _tf.TiffFile(filename) as t:
                shp = t.pages[0].shape          # (H, W) or (H, W, C)
                if len(shp) >= 2:
                    return int(shp[1])
        except Exception:
            pass
    try:
        from PIL import Image as _PI
        with _PI.open(filename) as im:
            return int(im.size[0])              # (W, H)
    except Exception:
        return None


def _scale_consistency_panels(pyf_path: str) -> list[dict]:
    """One dict per raster panel describing its *displayed* physical scale — the
    physical length one on-figure pixel represents. Two panels are visually
    comparable (a 10 µm feature looks the same size in both) only when this
    matches. Fields: label, filename, px_to_unit (µm per source px), raw_w,
    display_w, displayed_scale (µm per figure px, or None if px_to_unit unset)."""
    objects, Group, Image2D = _load_objects_lazy(pyf_path)

    def _imgs_in(group):
        out = []
        for c in getattr(group, "content", []):
            if isinstance(c, Image2D):
                out.append(c)
            elif isinstance(c, Group):
                out.extend(_imgs_in(c))
        return out

    _is_real_raster = _is_raster_panel

    def _one(img, letter):
        # True source-pixel width from the file header (cheap, and correct even in
        # lazy mode where get_raw_size() returns a 512 placeholder).
        raw_w = _raw_width_from_file(img.filename)
        if raw_w is None:
            try:
                raw_w, _ = img.get_raw_size()
            except Exception:
                raw_w = None
        disp = img.width(all=True)
        try:
            px_to_unit = float(getattr(img, "px_to_unit_conversion_factor", 0) or 0)
        except (TypeError, ValueError):
            px_to_unit = 0.0
        scale = None
        if px_to_unit > 0 and raw_w and disp:
            scale = px_to_unit * raw_w / disp     # µm per on-figure pixel
        return {
            "label": letter,
            "filename": os.path.basename(str(img.filename)) if img.filename else "(in-memory)",
            "px_to_unit": px_to_unit or None,
            "raw_w": raw_w,
            "display_w": round(disp, 1) if disp else None,
            "displayed_scale": scale,
        }

    results: list[dict] = []
    top_groups = [o for o in objects if isinstance(o, Group)]
    free_imgs = [o for o in objects if isinstance(o, Image2D)]
    for gi, grp in enumerate(top_groups):
        for ii, img in enumerate(_imgs_in(grp)):
            if _is_real_raster(img):
                results.append(_one(img, _where(img, f"group {gi}, img {ii}")))
    for ii, img in enumerate(free_imgs):
        if _is_real_raster(img):
            results.append(_one(img, _where(img, f"canvas img {ii}")))
    return results


@mcp.tool()
def check_scale_consistency(pyf_path: str, tolerance: float = 0.05) -> str:
    """Flag panels whose **displayed physical scale is inconsistent** — a subtle
    integrity issue where micrographs placed side by side can't honestly be
    compared by eye because a given physical length occupies a different number
    of on-figure pixels in each.

    For every raster panel with a pixel size set
    (``px_to_unit_conversion_factor``) this computes the displayed scale =
    ``px_to_unit x source_pixels / on-figure_width`` (physical units per on-figure
    pixel), takes the median as the reference, and flags any panel deviating by
    more than *tolerance* (fractional, default 0.05 = 5 %). For each flagged panel
    it reports the on-figure width it *would* need to match the reference.

    Also lists panels with **no pixel size set** (can't be checked — set one with
    set_scale_bar's px_to_unit or configure_image). Assumes all panels use the
    same physical unit (e.g. µm). This reports; it does not modify the figure.

    Example::

        check_scale_consistency("fig.pyf", tolerance=0.05)
    """
    if tolerance < 0:
        return "ERROR: tolerance must be >= 0."
    try:
        panels = _scale_consistency_panels(pyf_path)
    except Exception as e:
        return f"ERROR: could not analyse scale consistency — {e}"
    if not panels:
        return "No raster panels found to check."

    scaled = [p for p in panels if p["displayed_scale"]]
    missing = [p for p in panels if not p["displayed_scale"]]

    result: dict = {
        "panels_total": len(panels),
        "panels_with_scale": len(scaled),
        "panels_without_scale": len(missing),
        "tolerance": tolerance,
    }
    if not scaled:
        result["reference_scale"] = None
        result["note"] = ("No panel has a pixel size set, so scale consistency "
                          "cannot be checked. Set px_to_unit via set_scale_bar or "
                          "configure_image.")
        result["missing_scale"] = [p["label"] for p in missing]
        return json.dumps(result, ensure_ascii=False, indent=2)

    values = sorted(p["displayed_scale"] for p in scaled)
    n = len(values)
    ref = values[n // 2] if n % 2 else 0.5 * (values[n // 2 - 1] + values[n // 2])
    result["reference_scale"] = ref
    result["reference_scale_note"] = "median physical units per on-figure pixel"

    reports = []
    n_bad = 0
    for p in scaled:
        dev = abs(p["displayed_scale"] / ref - 1.0) if ref else 0.0
        consistent = dev <= tolerance
        if not consistent:
            n_bad += 1
        entry = {
            "label": p["label"],
            "filename": p["filename"],
            "px_to_unit": round(p["px_to_unit"], 6),
            "displayed_scale": round(p["displayed_scale"], 6),
            "deviation_pct": round(dev * 100, 1),
            "consistent": consistent,
        }
        if not consistent and p["raw_w"]:
            entry["recommended_display_w"] = round(p["px_to_unit"] * p["raw_w"] / ref, 1)
        reports.append(entry)

    result["panels"] = reports
    result["missing_scale"] = [{"label": p["label"], "filename": p["filename"]}
                               for p in missing]
    result["inconsistent_count"] = n_bad
    if n_bad:
        result["summary"] = (f"{n_bad}/{len(scaled)} panel(s) deviate from the reference "
                             f"displayed scale by more than {tolerance*100:g}% — features "
                             f"cannot be compared by eye across panels. Resize each flagged "
                             f"panel to its recommended on-figure width, or note the "
                             f"different magnifications explicitly.")
    else:
        result["summary"] = (f"All {len(scaled)} scaled panel(s) share a consistent "
                             f"displayed scale (within {tolerance*100:g}%).")
    if missing:
        result["summary"] += (f" {len(missing)} panel(s) have no pixel size set and "
                              f"were not checked.")
    return json.dumps(result, ensure_ascii=False, indent=2)


def _bump_font_size_in_html(html: str, min_pt: float) -> tuple[str, int]:
    """Raise every 'font-size:Npt' below *min_pt* in a Qt rich-text string to
    *min_pt*. Returns (new_html, number_bumped)."""
    n = 0

    def _repl(m):
        nonlocal n
        val = float(m.group(1))
        if val < min_pt:
            n += 1
            return f"font-size:{int(min_pt) if float(min_pt).is_integer() else min_pt}pt"
        return m.group(0)

    return re.sub(r"font-size:\s*([\d.]+)pt", _repl, html), n


@mcp.tool()
def enforce_min_font_size(
    pyf_path: str,
    min_pt: float = 7.0,
    font_family: str | None = None,
) -> str:
    """Raise every font below *min_pt* points up to the minimum, across the whole
    figure. PyFigures measures text in points and does not shrink text with panels,
    so the stored point size is the on-page size — this makes the figure satisfy a
    journal's minimum-font-size rule (commonly 5–8 pt).

    Bumps three things: the figure-level font (auto-lettering / labels), the
    embedded font-size in any rich-text annotation, and each panel's
    publication_font_size (matplotlib / scripted plot panels). Optionally also sets
    *font_family* (e.g. "Arial" / "Helvetica") on the figure-level font.

    Example::

        enforce_min_font_size("fig.pyf", min_pt=7, font_family="Arial")
    """
    tree, root = _load(pyf_path)
    changed: list[str] = []

    # 1. figure-level SerializableQFont
    font_el = root.find("SerializableQFont")
    if font_el is None:
        font_el = ET.SubElement(root, "SerializableQFont")
    cur = _child_text(font_el, "size")
    try:
        cur_val = float(cur) if cur is not None else None
    except ValueError:
        cur_val = None
    if cur_val is None or cur_val < min_pt:
        _set_child_text(font_el, "size", str(int(min_pt)))
        changed.append(f"figure font size {cur_val or '?'} -> {int(min_pt)}pt")
    if font_family is not None:
        _set_child_text(font_el, "family", _encode_str(font_family))
        changed.append(f"figure font family -> {font_family!r}")

    # 2. embedded font-size in every rich-text annotation
    ann_bumped = 0
    for ta in root.iter("TAText2D"):
        text_el = ta.find("text")
        if text_el is None or not text_el.text:
            continue
        raw = _decode(text_el.text)
        new, n = _bump_font_size_in_html(raw, min_pt)
        if n:
            text_el.text = _encode_str(new)
            ann_bumped += n
    if ann_bumped:
        changed.append(f"{ann_bumped} annotation font-size(s) raised to {int(min_pt)}pt")

    # 3. per-image publication_font_size (scripted / plot panels)
    pub_bumped = 0
    for img in root.iter("Image2D"):
        pf = img.find("publication_font_size")
        if pf is None:
            continue
        try:
            v = float(pf.text) if pf.text is not None else None
        except (ValueError, TypeError):
            v = None
        if v is not None and v < min_pt:
            pf.text = str(int(min_pt))
            pub_bumped += 1
    if pub_bumped:
        changed.append(f"{pub_bumped} scripted-panel publication_font_size(s) -> {int(min_pt)}pt")

    if not changed:
        return f"All fonts already ≥ {min_pt}pt — nothing changed."
    _save(tree, pyf_path)
    return f"Enforced ≥{min_pt}pt: " + "; ".join(changed) + "."


@mcp.tool()
def check_journal_compliance(
    pyf_path: str,
    journal: str | None = None,
    column: str = "single",
    width_mm: float | None = None,
    width_cm: float | None = None,
    width_in: float | None = None,
    dpi: int = 300,
    min_font_pt: float = 7.0,
    min_dpi: int = 300,
    require_scale_bars: bool = False,
    require_panel_labels: bool = False,
    require_sans_serif: bool = True,
    max_height_mm: float | None = None,
) -> str:
    """Read-only compliance report: check the current figure against a journal's
    formatting rules and list what passes and what needs fixing. Nothing is
    modified — use apply_journal_guidelines() to fix issues.

    Checks: figure width vs the target column width, figure height vs the
    journal's maximum height (*max_height_mm* when given, else the journal's
    own; without either the height is only reported), minimum font size
    (figure font + scripted-panel fonts), sans-serif font family, per-panel
    print resolution, and (optionally) presence of scale bars and panel labels.

    Paste the journal's guidelines, extract the numbers, then call this with the
    matching parameters (journal preset or explicit width, dpi, min_font_pt, …).
    """
    try:
        target_mm, wsrc = _resolve_target_for(pyf_path, journal, column, width_mm, width_cm, width_in)
    except ValueError as e:
        return f"ERROR: {e}"

    # a journal style imported from the journal's guidelines: its minimum font
    # size and photograph DPI replace the defaults (not values the caller gave)
    from ..journal_styles import user_style_for
    style = user_style_for(journal)
    style_notes = []
    if style is not None:
        from ..journal_styles import min_value
        fmin = min_value(style, "font_size")
        if fmin and min_font_pt == 7.0:
            min_font_pt = fmin[0]
            style_notes.append(f"minimum font {min_font_pt:g} pt from rule '{fmin[1]['label']}'")
        dmin = min_value(style, "resolution", r"photo|halftone|colou?r|gr[ae]y|image|raster|combination")
        if dmin and min_dpi == 300:
            min_dpi = int(round(dmin[0]))
            style_notes.append(f"minimum {min_dpi} DPI from rule '{dmin[1]['label']}' "
                               f"({dmin[1]['applies_to']})")

    # canvas units are points (1/72 in) — see resize_figure; *dpi* only sets the
    # pixel count of a raster export
    target_px = round(target_mm / 25.4 * 72.0)
    _, root = _load(pyf_path)
    results: list[tuple[str, bool, str]] = []  # (criterion, ok, detail)

    # ── width ────────────────────────────────────────────────────────────────
    groups = _top_groups(root)
    cur_sizes = []
    for g in groups:
        s = g.get("size") or _child_text(g, "size")
        try:
            cur_sizes.append(float(s))
        except (TypeError, ValueError):
            pass
    # the journal's maximum height (or the one the figure was narrowed to fit)
    stored = _stored_target(pyf_path) or {}
    height_journal = journal if journal is not None else (
        stored.get("journal") if width_mm is None and width_cm is None and width_in is None
        else None)
    max_h = _journal_max_height(height_journal)
    if stored.get("max_height_mm") and (journal is None or journal == stored.get("journal")):
        if max_h is None or stored["max_height_mm"] < max_h[0]:
            max_h = (float(stored["max_height_mm"]), "the height the figure was fitted to")
    if max_height_mm is not None:
        try:
            if float(max_height_mm) <= 0:
                raise ValueError
            max_h = (float(max_height_mm), "the maximum height you gave")
        except (TypeError, ValueError):
            return f"ERROR: max_height_mm must be a positive number of mm, not {max_height_mm!r}."
    height_mm = _figure_height_mm(pyf_path)
    if cur_sizes:
        cur_px = max(cur_sizes)
        ok_w = abs(cur_px - target_px) <= max(2, target_px * 0.01)
        detail = f"figure {cur_px / 72.0 * 25.4:.1f}mm vs target {target_mm:.1f}mm ({wsrc})"
        if not ok_w and cur_px < target_px and height_mm is not None \
                and height_mm >= max_h[0] * 0.98 and height_mm <= max_h[0] * 1.01:
            ok_w = True              # narrowed on purpose: at the maximum height
            detail += f"; narrower so that its height fits the maximum {max_h[0]:g}mm"
        results.append(("width", ok_w, detail))
    else:
        results.append(("width", False, "no group size found (free-canvas?)"))
    if max_h is not None:
        if height_mm is None:
            results.append(("height", False, f"could not measure the figure height "
                                             f"(maximum {max_h[0]:g}mm: {max_h[1]})"))
        else:
            results.append(("height", height_mm <= max_h[0] * 1.01,
                            f"figure {height_mm:.1f}mm tall vs maximum {max_h[0]:g}mm "
                            f"({max_h[1]})"
                            + ("" if height_mm <= max_h[0] * 1.01 else
                               " — resize_figure with the journal narrows it to fit, or "
                               "choose a smaller column (fit_height='column')")))
    elif height_mm is not None:
        # nothing to compare with: say how tall it is (the check was invisible)
        results.append(("height", True, f"figure {height_mm:.1f}mm tall; the journal gives no "
                                        f"maximum height (give max_height_mm to check one)"))

    # ── font size ──────────────────────────────────────────────────────────────
    font_el = root.find("SerializableQFont")
    fig_size = None
    family = None
    if font_el is not None:
        try:
            fig_size = float(_child_text(font_el, "size"))
        except (TypeError, ValueError):
            pass
        family = _decode(_child_text(font_el, "family"))
    ann_min = None
    for ta in root.iter("TAText2D"):
        raw = _decode((ta.find("text").text if ta.find("text") is not None else "") or "")
        for m in re.finditer(r"font-size:\s*([\d.]+)pt", raw):
            v = float(m.group(1))
            ann_min = v if ann_min is None else min(ann_min, v)
    pub_min = None
    for img in root.iter("Image2D"):
        pf = img.find("publication_font_size")
        if pf is not None and pf.text:
            try:
                v = float(pf.text)
                pub_min = v if pub_min is None else min(pub_min, v)
            except ValueError:
                pass
    smallest = min([v for v in (fig_size, ann_min, pub_min) if v is not None] or [None])
    if smallest is None:
        results.append(("font size", True, "no font info found (assumed ok)"))
    else:
        results.append(("font size", smallest >= min_font_pt,
                        f"smallest font {smallest:g}pt vs min {min_font_pt:g}pt"))

    # ── sans-serif ─────────────────────────────────────────────────────────────
    if require_sans_serif:
        # judged on the family each text is really drawn and exported in: a
        # requested font that is not installed is replaced by another one
        from .core import _font_report, _text_families
        serif_fonts = {"times", "georgia", "garamond", "cambria", "serif", "roman", "minion", "palatino"}
        requested = _text_families(root)
        rep = _font_report(requested) if requested else {}
        drawn = rep.get("drawn_as", {}) if isinstance(rep, dict) else {}
        parts, is_sans = [], bool(requested)
        for fam in requested:
            real = drawn.get(fam, fam)
            # "sans" in a name (e.g. "Noto Serif Sans" never, "DejaVu Sans") wins over a serif hint
            if "sans" not in real.lower() and any(s in real.lower() for s in serif_fonts):
                is_sans = False
            parts.append(f"{fam!r}" if real == fam else f"{fam!r} (not installed here: drawn and exported as {real!r})")
        if not isinstance(rep, dict):
            parts.append(f"(could not check which fonts are installed: {rep})")
        results.append(("sans-serif font", is_sans,
                        "font family " + ", ".join(parts) if requested else "no font family set"))

    # ── resolution ─────────────────────────────────────────────────────────────
    try:
        panels = _panel_resolutions(pyf_path, target_mm)
        bad = [p for p in panels if p["dpi"] is not None and p["dpi"] < min_dpi]
        if not panels:
            results.append(("resolution", True, "no raster panels"))
        else:
            worst = min((p["dpi"] for p in panels if p["dpi"]), default=None)
            results.append(("resolution", not bad,
                            f"{len(bad)}/{len(panels)} panel(s) below {min_dpi} DPI"
                            + (f" (worst {worst} DPI)" if worst else "")
                            + (f" — to reach {min_dpi} DPI that panel must be printed "
                               f"{min_dpi / worst:.2f}x smaller, or come from a source with "
                               f"{min_dpi / worst:.2f}x more pixels per side"
                               if bad and worst else "")))
    except Exception as e:
        results.append(("resolution", False, f"could not analyse: {e}"))

    # ── scale bars ─────────────────────────────────────────────────────────────
    if require_scale_bars:
        n_ok, n_units = _scale_bar_coverage(root)
        results.append(("scale bars", n_units > 0 and n_ok == n_units,
                        f"{n_ok}/{n_units} micrograph(s) have a scale bar (a montage or "
                        "channel split counts once; plots are not counted)"))

    # ── panel labels ───────────────────────────────────────────────────────────
    if require_panel_labels:
        n_labels = sum(1 for ta in root.iter("TAText2D")
                       if _child_text(ta, "is_letter") is True)
        results.append(("panel labels", n_labels >= len(groups) and n_labels > 0,
                        f"{n_labels} panel label(s) for {len(groups)} group(s)"))

    n_fail = sum(1 for _, ok, _ in results if not ok)
    header = ("COMPLIANT" if n_fail == 0
              else f"{n_fail} issue(s) to fix")
    lines = [f"Journal compliance [{wsrc}]: {header}"]
    for crit, ok, detail in results:
        lines.append(f"  [{'ok' if ok else 'FAIL'}] {crit}: {detail}")
    # a 9B model read COMPLIANT as "the figure is ready" with a wrong row layout
    lines.append("  (These are the journal's mechanical rules only — not whether the "
                 "arrangement matches what was asked, nor a visual review; describe_figure "
                 "shows the actual layout.)")
    # two models answered "ready for submission" right after a [FAIL] resolution
    failed = [crit for crit, ok, _ in results if not ok]
    if failed:
        lines.append(f"VERDICT: NOT READY — {len(failed)} check(s) FAIL ({', '.join(failed)}). "
                     "Fix them, or tell the user plainly that they remain unresolved; do not "
                     "call the figure ready for submission.")
    else:
        lines.append("VERDICT: the mechanical checks pass. Readiness for submission also needs "
                     "the requested content and layout checked and the user's own review.")
    if style is not None:
        from ..journal_styles import describe_rules
        lines.append(f"Journal style {style['journal']!r} ({style['status']}, stage "
                     f"{style['stage']}): " + ("; ".join(style_notes) or "widths only")
                     + ". All its rules — the ones above are checked, check the others yourself:")
        lines.extend(f"  - {d}" for d in describe_rules(style))
        if style["status"] != "reviewed":
            lines.append("  (draft style: its rules were extracted automatically and not yet "
                         "reviewed by a person — QC → Journal styles…)")
    return "\n".join(lines)


@mcp.tool()
def apply_journal_guidelines(
    pyf_path: str,
    journal: str | None = None,
    column: str = "single",
    width_mm: float | None = None,
    width_cm: float | None = None,
    width_in: float | None = None,
    dpi: int = 300,
    font_family: str | None = "Arial",
    min_font_pt: float = 7.0,
    add_panel_labels: bool = False,
    panel_label_start: str = "a",
    scale_bar_units: float | None = None,
    scale_bar_unit: str = "µm",
    scale_bar_px_to_unit: float | None = None,
    fit_height: bool | str = True,
) -> str:
    """One-shot reformat of a figure to a journal's guidelines, then report
    compliance. Bundles the individual tools so a pasted set of guidelines can be
    applied in a single call.

    Steps (each optional depending on arguments):
      1. resize the figure to the target column width (journal preset or explicit);
         a figure then taller than the journal's maximum height is narrowed
         (*fit_height* True/'shrink'), put in the widest column it fits in
         ('column') or left too tall (False) — see resize_figure.
      2. set the figure font family (default Arial) and raise every font to
         *min_font_pt* (enforce_min_font_size).
      3. if *add_panel_labels*: add a bold lowercase letter (a, b, c, …) to the top-
         left of the first image of each top-level group, starting at
         *panel_label_start*.
      4. if *scale_bar_units*: add/update a scale bar on every image
         (*scale_bar_px_to_unit* = µm-per-pixel, if the images lack that metadata).

    Then returns the check_journal_compliance() report so you can see what still
    needs manual attention (e.g. under-resolution panels, which this cannot fix).

    Example — Nature single-column, Arial ≥7pt, panel labels, 10µm bars::

        apply_journal_guidelines("fig.pyf", journal="nature", column="single",
                                 add_panel_labels=True,
                                 scale_bar_units=10, scale_bar_px_to_unit=0.1)
    """
    try:
        target_mm, wsrc = _resolve_target_mm(journal, column, width_mm, width_cm, width_in)
    except ValueError as e:
        return f"ERROR: {e}"

    steps: list[str] = []

    # 1. resize
    r = resize_figure(pyf_path, journal=journal, column=column, dpi=dpi,
                      width_mm=width_mm, width_cm=width_cm, width_in=width_in,
                      fit_height=fit_height)
    if r.startswith("ERROR"):
        return "ERROR during resize: " + r
    steps.append("resize: " + (r.split(".")[0] if r else "done"))
    m = re.search(r"At [\d.]+mm wide the figure is .*?Choices: [^\n]*?\.(?=  |$)", r)
    if m:
        steps.append("height: " + m.group(0))
    stored = _stored_target(pyf_path) or {}
    if journal is not None and stored.get("column") and stored.get("column") != column:
        column = stored["column"]            # fit_height='column' moved it to another column

    # 2. font family + min size
    if font_family is not None:
        set_figure_properties(pyf_path, font_family=font_family)
    steps.append(enforce_min_font_size(pyf_path, min_pt=min_font_pt, font_family=font_family))

    # 3. panel labels
    if add_panel_labels:
        _, root = _load(pyf_path)
        n_groups = len(_top_groups(root))
        letter = panel_label_start
        added = 0
        for gi in range(n_groups):
            res = add_corner_labels(pyf_path, [gi], 0, top_left=[f"<b>{letter}</b>"])
            if not res.startswith("ERROR"):
                added += 1
            letter = _increment_label_letter(letter)
        steps.append(f"panel labels: added {added} bold letter(s) starting '{panel_label_start}'")

    # 4. scale bars
    if scale_bar_units is not None:
        sb = set_scale_bar_all(pyf_path, scale_bar_units, unit=scale_bar_unit,
                               px_to_unit=scale_bar_px_to_unit)
        steps.append("scale bars: " + (sb.split(".")[0] if sb else "done"))

    report = check_journal_compliance(
        pyf_path, journal=journal, column=column, width_mm=width_mm,
        width_cm=width_cm, width_in=width_in, dpi=dpi, min_font_pt=min_font_pt,
        min_dpi=min_dpi_default(dpi),
        require_scale_bars=scale_bar_units is not None,
        require_panel_labels=add_panel_labels,
        require_sans_serif=font_family is not None,
    )
    return (f"Applied journal guidelines [{wsrc}]:\n  - "
            + "\n  - ".join(steps) + "\n\n" + report)


def min_dpi_default(export_dpi: int) -> int:
    """Reasonable default minimum acceptable DPI given the intended export DPI."""
    return 300 if export_dpi >= 300 else export_dpi


def _increment_label_letter(letter: str) -> str:
    """a→b, z→aa, az→ba (spreadsheet-style), for sequential panel labels."""
    try:
        from batoolset.strings.tools import find_letter_before_h  # noqa: F401
    except Exception:
        pass
    if not letter:
        return "a"
    chars = list(letter)
    i = len(chars) - 1
    while i >= 0:
        if chars[i] == "z":
            chars[i] = "a"
            i -= 1
        else:
            chars[i] = chr(ord(chars[i]) + 1)
            return "".join(chars)
    return "a" + "".join(chars)
