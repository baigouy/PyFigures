"""The statistics of a figure's data plots, written for its legend.

User, 2026-11-19: the two-way ANOVA printed under a grouped plot "is really not
elegant"; it belongs in the text that goes with the figure, which the user can edit.
So a figure shows stars, and this writes the paragraph that explains them: for each
data plot (by its panel letter) the test, its result, n, and once the meaning of the
stars. It is inserted into the caption only when asked (caption dialog button, MCP
add_statistics_to_caption); the text inserted is remembered beside the caption, so
an update replaces it only while the user has not edited it, and a caption whose
statistics no longer match the plots is reported, never rewritten behind the user's
back.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

STAR_KEY = "*p < 0.05, **p < 0.01, ***p < 0.001, ****p < 0.0001"
HEAD = "Statistics: "


def _p(p) -> str:
    if p is None or p != p:
        return "p = n/a"
    if p < 0.0001:
        return "p < 0.0001"
    return f"p = {p:.2g}" if p < 0.01 else f"p = {p:.2f}".rstrip("0").rstrip(".")


def _test_name(test: str) -> str:
    """'One-way ANOVA + Tukey HSD' -> 'one-way ANOVA followed by Tukey's HSD test'."""
    t = str(test or "")
    t = t.replace(" + ", " followed by ").replace("Tukey HSD", "Tukey's HSD test")
    t = t.replace("Dunn's test", "Dunn's test (Bonferroni)") if "Bonferroni" not in t else t
    proper = ("Mann", "Welch", "Kruskal", "Pearson", "Spearman", "Wilcoxon", "Friedman", "Dunnett", "Student")
    return t if t.startswith(proper) else t[:1].lower() + t[1:]


def _omnibus(rec: dict) -> str:
    o = rec.get("omnibus") or {}
    if o.get("p") is None:
        return ""
    name = {"chi2": "χ²"}.get(o.get("stat_name"), o.get("stat_name") or "")
    return f" ({name} = {o['stat']:.3g}, {_p(o['p'])})" if o.get("stat") is not None else f" ({_p(o['p'])})"


def _n_text(groups: dict | None) -> str:
    if not groups:
        return ""
    ns = sorted(set(groups.values()))
    if len(ns) == 1:
        return f"n = {ns[0]} per group"
    return "n = " + ", ".join(f"{n} ({g})" for g, n in groups.items())


def _factor_names(spec: dict):
    try:
        from staplot import api
        from pyfigures.assistant.plot_info import _sel
        gt = api.grouped_table_from_csv(spec["csv"], **_sel(spec))
        names = getattr(gt, "factor_names", None)
        if names:
            return str(names[0]), str(names[1])
    except Exception:
        pass
    return "factor A", "factor B"


def _levels(spec: dict, factor: str) -> set:
    """The levels of factor A (the colours) of a two-factor plot, as text."""
    try:
        from staplot import api
        from pyfigures.assistant.plot_info import _sel
        return {str(g) for g in api.grouped_table_from_csv(spec["csv"], **_sel(spec)).col_groups}
    except Exception:
        return set()


def _effects(rec: dict, a: str, b: str) -> str:
    shown = {"factor A": a, "factor B": b, "A x B": f"{a} × {b}"}
    parts = [f"{shown.get(e['effect'], e['effect'])} {_p(e['p'])}" for e in rec.get("effects") or []
             if e.get("p") is not None]
    return "two-way ANOVA (" + "; ".join(parts) + ")" if parts else "two-way ANOVA"


def panel_sentence(letter: str, spec: dict) -> tuple[str, bool]:
    """(the sentence of one data plot, whether it shows stars)."""
    from pyfigures.assistant.plot_info import plot_statistics, _groups
    if not spec.get("annotate_stats", True):
        return "", False
    rec = plot_statistics(spec) or {}
    if rec.get("error"):
        return "", False
    kind = spec["kind"]
    lead = f"({letter}) " if letter else ""
    bars = {"sd": "mean ± SD", "sem": "mean ± SEM", "ci95": "mean ± 95% CI"}.get(spec.get("error") or "sd")
    if rec.get("facets"):
        tests = sorted({_test_name(r.get("test")) for r in rec["facets"].values() if r.get("test")})
        return (f"{lead}one plot per {spec['facet']}" + (f" and {spec['facet_row']}" if spec.get("facet_row") else "")
                + (f", each tested separately ({'; '.join(tests)})" if tests else "") + ".", True)
    if kind in ("bar", "box", "violin"):
        bits = []
        if kind == "bar" and bars:
            bits.append(bars)
        n = _n_text(_groups(spec))
        if n:
            bits.append(n)
        test = _test_name(rec.get("test")) + _omnibus(rec)
        if len(rec.get("comparisons") or []) == 1:
            test += f", {_p(rec['comparisons'][0]['p'])}"
        bits.append(test)
        if spec.get("control") and " vs " not in str(rec.get("test")):
            bits.append(f"each group compared with {spec['control']}")
        return lead + "; ".join(b for b in bits if b) + ".", True
    if kind == "paired":
        test = _test_name(rec.get("test")) + _omnibus(rec)
        if len(rec.get("comparisons") or []) == 1:
            test += f", {_p(rec['comparisons'][0]['p'])}"
        n = rec.get("n_subjects")
        return f"{lead}{test}" + (f"; n = {n} subjects" if n else "") + ".", True
    if kind == "scatter":
        r = rec.get("r")
        if r is None:
            return "", False
        return f"{lead}{rec.get('test') or 'Pearson correlation'}: r = {r:.2f}, {_p(rec.get('p'))}, n = {rec.get('n')}.", False
    if kind in ("grouped", "line", "split_violin"):
        a, b = _factor_names(spec)
        text = lead + (bars + "; " if kind in ("grouped", "line") and bars else "") + _effects(rec, a, b)
        if kind == "split_violin" and rec.get("split_comparisons"):
            tests = sorted({c["test"] for c in rec["split_comparisons"] if c.get("test")})
            first = rec["split_comparisons"][0]
            halves = {str(first.get("a")), str(first.get("b"))}
            # the halves are the two-level factor: name the other one as the x axis
            x_name = b if halves <= _levels(spec, a) else a
            text += (f"; at each {x_name}, {first.get('a')} vs {first.get('b')} compared "
                     f"({', '.join(tests)})")
        elif rec.get("within_x"):
            tests = sorted({_test_name(w["test"]) for w in rec["within_x"] if w.get("test")})
            text += f"; stars: the {a} groups compared within each {b} level ({', '.join(tests)})"
        return text + ".", True
    return "", False


def _panels(pyf_path: str):
    """(letter, data-plot spec) of each data plot of the figure, in figure order."""
    from pyfigures.assistant.plot_info import parse_data_plot
    from pyfigures.mcp_tools.core import _decode
    from pyfigures.mcp_tools.export import _panel_letter_label, _row_letter_map
    root = ET.parse(pyf_path).getroot()
    rows = _row_letter_map(root)
    folder = os.path.dirname(os.path.abspath(pyf_path))
    for img in root.iter("Image2D"):
        spec = parse_data_plot(_decode(img.findtext("custom_loading_script")) or "")
        if not spec:
            continue
        csv = spec["csv"]
        file = csv.split("::")[0] if isinstance(csv, str) else csv
        if isinstance(file, str) and not os.path.isabs(file):
            spec["csv"] = os.path.join(folder, csv)
        yield (_panel_letter_label(img) or rows.get(img) or ""), spec


def statistics_text(pyf_path: str) -> str:
    """The Statistics paragraph of the figure's data plots ('' when none is tested)."""
    sentences, stars = [], False
    for letter, spec in _panels(pyf_path):
        text, has_stars = panel_sentence(letter, spec)
        if text:
            sentences.append(text)
            stars = stars or has_stars
    if not sentences:
        return ""
    return HEAD + " ".join(sentences) + (f" {STAR_KEY}." if stars else "")


def merged_caption(caption: str, stored: str | None, fresh: str, force: bool = False):
    """(new caption, status): the statistics paragraph added or brought up to date.
    status: 'added', 'updated', 'unchanged', or 'edited' (the user changed the text
    inserted before: left alone unless *force*, which adds the new one at the end)."""
    caption = caption or ""
    if stored and stored in caption:
        if stored == fresh:
            return caption, "unchanged"
        return caption.replace(stored, fresh), "updated"
    if stored and HEAD.strip() in caption and not force:
        return caption, "edited"
    if fresh in caption:
        return caption, "unchanged"
    return (caption.rstrip() + ("\n\n" if caption.strip() else "") + fresh), "added"
