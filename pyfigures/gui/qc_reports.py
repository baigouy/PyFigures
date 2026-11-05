"""QC reports for people: the QC menu runs the MCP tools, whose results are
written for the MCP server (JSON, panels as "group 0, img 1", advice naming
MCP tools). These turn them into plain text that names panels by their letter
and file, says what is wrong and what to do in the GUI.
"""
from __future__ import annotations

import json
import os
import re

_HOW_SCALE_BAR = ("To add one: Annotations → Add scale bar to all panels…, or double-click a panel "
                  "and add a scale bar in its editor (the pixel size is set there too).")
_HOW_LABEL = ("To add letters: Annotations → Panel letters (A, B, C…)…, or double-click the panel "
              "and add a text.")

# advice written for the MCP server → what to do in the GUI
_MCP_SPEAK = [
    (re.compile(r"\s*\(?These are the journal's mechanical rules only[^\n]*"),
     "\nThese are the journal's mechanical rules only: the arrangement and the look "
     "of the figure are for you to judge."),
    (re.compile(r"Fix them, or tell the user plainly[^\n]*"), "Fix them before submitting."),
    (re.compile(r"Set px_to_unit via set_scale_bar or configure_image\.?"),
     "Set the pixel size of the panels: double-click a panel, or Annotations → "
     "Add scale bar to all panels…"),
    (re.compile(r"\bVERDICT:\s*"), "Verdict: "),
    (re.compile(r"\(give max_height_mm to check one\)"), "(enter a Max height to check one)"),
    (re.compile(r"resize_figure with the journal narrows it to fit, or choose a smaller column "
                r"\(fit_height='column'\)"),
     "QC → Apply journal guidelines… narrows it to fit (If too tall), or choose a smaller column"),
]


def _name(panel):
    """'A (cells.png)' from an audit entry (letter + file name)."""
    letters = [x for x in panel.get("labels") or [] if 0 < len(x) <= 3]
    fn = panel.get("filename")
    base = os.path.basename(str(fn)) if fn and str(fn) != "None" else ""
    if letters:
        return f"{letters[0]} ({base})" if base else letters[0]
    return base or "a panel without a file"


def _names_by_place(audit):
    return {(tuple(p["group_path"]), p["image_index"]): _name(p) for p in audit.get("panels", [])}


def humanize(text):
    """Panels named by their letter, MCP advice turned into GUI steps."""
    # 'panel B (group 0, img 1)' → 'panel B'; what is left: row / loose panel numbers
    text = re.sub(r"panel (\S+) \((?:group \d+, img \d+|canvas img \d+)\)", r"panel \1", text)
    text = re.sub(r"group (\d+), img (\d+)",
                  lambda m: f"row {int(m.group(1)) + 1}, panel {int(m.group(2)) + 1}", text)
    text = re.sub(r"canvas img (\d+)", lambda m: f"loose panel {int(m.group(1)) + 1}", text)
    for pattern, repl in _MCP_SPEAK:
        text = pattern.sub(repl, text)
    return text


def audit_report(raw):
    """QC → Audit figure."""
    try:
        d = json.loads(raw)
    except (TypeError, ValueError):
        return humanize(str(raw))
    names = _names_by_place(d)

    def who(entries):
        return ", ".join(names.get((tuple(e["group_path"]), e["image_index"]),
                                   os.path.basename(str(e.get("filename")))) for e in entries)
    n = d.get("n_panels", 0)
    lines = [f"Figure audit: {n} panel{'s' if n != 1 else ''}", ""]
    bars = d.get("panels_missing_scale_bar") or []
    if bars:
        lines += [f"✗ {len(bars)} micrograph{'s have' if len(bars) > 1 else ' has'} no scale bar: {who(bars)}",
                  "   " + _HOW_SCALE_BAR,
                  "   (Plots and text panels need none; a montage or channel split needs one, on its "
                  "last panel.)", ""]
    else:
        lines += ["✓ Every micrograph has a scale bar.", ""]
    # a bar is not a calibration
    uncal = d.get("scale_bars_not_calibrated") or []
    if uncal:
        lines += [f"✗ {len(uncal)} scale bar{'s are' if len(uncal) > 1 else ' is'} NOT calibrated "
                  f"(the image has no pixel size, the bar is a length in pixels): {who(uncal)}",
                  "   Set the pixel size: double-click the panel (px to unit), or Annotations → "
                  "Add scale bar to all panels… with a pixel size.", ""]
    by_hand = d.get("scale_bars_calibrated_by_hand") or []
    if by_hand:
        lines += [f"! {len(by_hand)} scale bar{'s use' if len(by_hand) > 1 else ' uses'} a pixel size "
                  f"set in the figure, not read from the image file: "
                  + ", ".join(f"{names.get((tuple(e['group_path']), e['image_index']), '?')} "
                              f"({e.get('pixel_size'):g} per pixel)" for e in by_hand),
                  "   Check it is the microscope's real pixel size.", ""]
    unlabelled = d.get("panels_missing_label") or []
    if unlabelled:
        lines += [f"✗ {len(unlabelled)} panel{'s have' if len(unlabelled) > 1 else ' has'} no letter or "
                  f"text: {who(unlabelled)}", "   " + _HOW_LABEL, ""]
    else:
        lines += ["✓ Every panel has a letter or a text.", ""]
    constant = d.get("panels_constant") or []
    if constant:
        lines += [f"✗ {len(constant)} panel{'s show' if len(constant) > 1 else ' shows'} a single value "
                  f"everywhere (nothing to see, e.g. an empty channel): {who(constant)}",
                  "   Remove it (select it, Delete) unless the empty image is the point.", ""]
    for s in d.get("panels_channels_share_a_lut") or []:
        place = names.get((tuple(s["group_path"]), s["image_index"]), os.path.basename(str(s.get("filename"))))
        chans = ", ".join(str(c) for c in s.get("channels", []))
        lines += [f"✗ {place}: channels {chans} all use the {s.get('lut')} LUT, so they add up in one colour "
                  f"and cannot be told apart.",
                  "   Give each channel its own LUT, show only one channel (double-click the panel), "
                  "or split the channels (Insert → Stack views → Channel split).", ""]
    for b in d.get("panels_with_burned_in_text") or []:
        place = names.get((tuple(b["group_path"]), b["image_index"]), os.path.basename(str(b.get("filename"))))
        lines += [f"! {place}: {b.get('warning')}", ""]
    if d.get("panels"):
        lines.append("Panels:")
        for p in d["panels"]:
            texts = ", ".join(p.get("labels") or []) or "none"
            bar = "no"
            if p.get("scale_bar"):
                bar = {"metadata": "yes (pixel size from the file)",
                       "figure": "yes (pixel size set by hand)",
                       "none": "yes, NOT calibrated (pixels)"}.get(p.get("pixel_size_source"), "yes")
            lines.append(f"   {_name(p)} — scale bar: {bar}; texts: {texts}")
    return "\n".join(lines).rstrip()


def integrity_report(raw):
    """QC → Check image integrity."""
    try:
        d = json.loads(raw)
    except (TypeError, ValueError):
        return humanize(str(raw))
    lines = [d.get("summary") or "", ""]

    def side(label, fn):
        fn = os.path.basename(str(fn or ""))
        return f"{label} ({fn})" if label and fn else (label or fn or "?")
    for it in d.get("exact_file_duplicates") or []:
        lines.append(f"✗ The same file in two panels: {side(it.get('a_label'), it.get('a_file'))} and "
                     f"{side(it.get('b_label'), it.get('b_file'))} ({it.get('reason')})")
    for it in d.get("cross_panel_duplicates") or []:
        lines.append(f"✗ Look like the same image: {side(it.get('a_label'), it.get('a_file'))} and "
                     f"{side(it.get('b_label'), it.get('b_file'))} ({it.get('transform')}, "
                     f"{round(100 * float(it.get('similarity') or 0))} % similar)")
    for it in d.get("within_panel_clones") or []:
        lines.append(f"✗ Repeated regions inside {side(it.get('label'), it.get('file'))} "
                     f"({it.get('clone_block_pairs')} matching block pairs): possible copy-paste")
        for r in (it.get("regions") or [])[:2]:
            (ax, ay, aw, ah), (bx, by, _bw, _bh) = r["a"], r["b"]
            lines.append(f"   the {aw}×{ah} px area at x={ax}, y={ay} matches the one at "
                         f"x={bx}, y={by} (image pixels)")
    if len(lines) > 2:
        lines.append("")
    errors = d.get("load_errors") or []
    if errors:
        lines.append("Not checked (could not be read):")
        for e in errors:
            lines.append(f"   {os.path.basename(str(e.get('file')))}: {e.get('error')}")
        lines.append("")
    lines.append(f"{d.get('panels_analyzed', 0)} of {d.get('panels_total', 0)} panels checked. "
                 "A flag is a lead to look at, not a proof: judge each pair yourself.")
    return "\n".join(x for x in lines).strip()


def _adjustment(a):
    """'crop (left 10, top 4)' from a ledger entry {type, detail}."""
    if isinstance(a, str):
        return a
    kind = str(a.get("type", "adjustment")).replace("_", " ")
    detail = a.get("detail")
    if isinstance(detail, dict):
        bits = [f"{k.replace('_', ' ')} {v}" for k, v in detail.items() if v not in (None, "", [], {})]
        return f"{kind} ({', '.join(bits)})" if bits else kind
    return f"{kind} ({detail})" if detail not in (None, "") else kind


def ledger_report(raw):
    """QC → Adjustment provenance ledger."""
    try:
        d = json.loads(raw)
    except (TypeError, ValueError):
        return humanize(str(raw))
    lines = [f"{d.get('panels_adjusted', 0)} of {d.get('panels_total', 0)} panels adjusted"
             + (f", {d['panels_with_custom_script']} with a custom script" if d.get("panels_with_custom_script")
                else ""), ""]
    for p in d.get("panels", []):
        adj = p.get("adjustments") or []
        what = "; ".join(_adjustment(a) for a in adj) or "no adjustment"
        flag = "" if p.get("all_linear", True) else "  ⚠ not linear"
        lines.append(f"   {p.get('label') or '?'} ({p.get('file')}): {what}{flag}")
    for f in d.get("flags") or []:
        lines.append(f"⚠ {f if isinstance(f, str) else f.get('message') or f}")
    if d.get("methods_paragraph"):
        lines += ["", "Methods (ready to paste):", d["methods_paragraph"]]
    if d.get("statistics_methods_paragraph"):
        lines += ["", "Statistics (ready to paste):", d["statistics_methods_paragraph"]]
    for s in d.get("statistics") or []:
        for c in s.get("comparisons") or []:
            lines.append(f"   {s.get('panel_label') or 'plot'}: {c.get('a')} vs {c.get('b')}: "
                         f"{c.get('p_text')} ({s.get('test')})")
    if d.get("note"):
        lines += ["", humanize(d["note"])]
    return "\n".join(lines).strip()


def fonts_report(d):
    """QC → Fonts (a dict from portable_fonts.font_report)."""
    bundled = d.get("bundled_families") or []
    clones = d.get("portable_clones_available") or []
    lines = [
        f"Helvetica is drawn with: {d.get('helvetica_resolves_to')}"
        + ("" if d.get("has_true_helvetica") else " (no real Helvetica on this computer)"),
        f"Arial is drawn with: {d.get('arial_resolves_to')}"
        + ("" if d.get("has_arial") else " (Arial is not installed)"),
        "",
        "Fonts bundled with PyFigures: " + (", ".join(bundled) if bundled else "none found"),
        "Portable Helvetica/Arial look-alikes: " + (", ".join(clones) if clones else "none found"),
        f"(folder: {d.get('fonts_dir')})",
    ]
    if not clones:
        lines += ["", "Without a look-alike, the figure may look different on another computer: "
                      "use a font installed everywhere, or add the fonts to that folder."]
    status = d.get("status") or {}
    if status:
        lines += ["", "Fonts used in this figure:"]
        for fam, st in status.items():
            if st.get("installed"):
                lines.append(f"  {fam}: installed")
            else:
                alts = ", ".join(st.get("alternatives") or []) or "none found"
                lines.append(f"  {fam}: NOT installed, drawn and exported as {st.get('drawn_as')} "
                             f"(installed alternatives: {alts})")
    return "\n".join(lines)
