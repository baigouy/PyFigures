"""A data plot edited in staplot's visual editor (staplot.ui.plot_editor): the table beside
the plot, a click on any part of the plot (a group, the points, a title, the tick labels,
the legend, the axes) to change its colour, text, size or font. Double-click a data plot
(or right-click -> Edit in staplot…) opens it; OK applies the changes with edit_data_plot,
as the chat and Plot settings… do (GUI = MCP)."""
from __future__ import annotations

import json

# the panel's settings (assistant.plot_info.parse_data_plot) that are staplot.api.plot
# arguments under another name
_SPEC_TO_PLOT = {"annotate_stats": "annotate"}
_PLOT_TO_EDIT = {v: k for k, v in _SPEC_TO_PLOT.items()}
_NOT_PLOT_ARGS = {"csv", "kind", "latex", "grouped_table", "columns", "where", "skip_rows", "subject",
                  "facet", "facet_row", "facet_ncols"}
# staplot's defaults: a setting at its default is not written
_DEFAULTS = {"error": "sd", "annotate": True, "only_significant": True, "stats_mode": "auto",
             "show_ylabel": True, "show_xlabel": True, "show_points": True, "title": "",
             "ylabel": "", "xlabel": "", "violin_inner": "lines", "violin_side": "both",
             "point_style": "jitter", "p_format": "stars", "log_y": False, "show_n": False,
             "show_mean": False, "stats_text": False, "error_side": "both", "percent": False, "log_x": True,
             "invert_y": False, "invert_x": False}


def staplot_editor_available() -> bool:
    try:
        from staplot.ui import plot_editor  # noqa: F401
        return True
    except Exception:
        return False


def text_parts_of_panel(panel) -> dict:
    """{part: {'pt', 'font'}} of a plot panel (Image2D.publication_text_parts)."""
    raw = getattr(panel, "publication_text_parts", None)
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError):
        return {}
    return {p: dict(s) for p, s in data.items() if isinstance(s, dict) and s}


def editor_arguments(spec: dict) -> dict:
    """PlotEditor's arguments for a data plot's settings (parse_data_plot)."""
    kwargs = {}
    for key, value in spec.items():
        if key in _NOT_PLOT_ARGS or value is None or value == [] or value == {}:
            continue
        key = _SPEC_TO_PLOT.get(key, key)
        if _DEFAULTS.get(key, object()) == value:
            continue
        kwargs[key] = value
    kwargs["show_title"] = bool(spec.get("title"))
    table = {k: spec[k] for k in ("columns", "where", "skip_rows", "subject") if spec.get(k) not in (None, "", [])}
    facet = {k: spec[k] for k in ("facet", "facet_row") if spec.get(k)}
    if facet and spec.get("facet_ncols"):
        facet["ncols"] = spec["facet_ncols"]
    return {"path": spec["csv"], "kind": spec["kind"], "kwargs": kwargs,
            "table_kwargs": table, "facet": facet or None}


def _cleared(old):
    """The value edit_data_plot reads as "back to the default" for a setting removed."""
    if isinstance(old, dict):
        return {}
    if isinstance(old, (list, tuple)):
        return []
    if isinstance(old, bool):
        return not old
    if isinstance(old, (int, float)):
        return 0
    return ""


def edit_arguments(editor, start_kwargs: dict, start_kind: str) -> dict:
    """edit_data_plot's arguments for what changed in the editor."""
    out = {}
    if editor.kind() != start_kind:
        out["kind"] = editor.kind()
    for key, value in editor.changed_kwargs().items():
        if key == "show_title":
            continue                            # follows the title
        name = _PLOT_TO_EDIT.get(key, key)
        if value is None:
            if key == "ylabel":
                value = "auto"
            elif key in _DEFAULTS:
                value = _DEFAULTS[key]
            else:
                value = _cleared(start_kwargs.get(key))
        elif isinstance(value, dict) and key in ("element_colors", "rename"):
            # a part set back to its default: "" (the tool merges the dict)
            value = {**{k: "" for k in (start_kwargs.get(key) or {}) if k not in value}, **value}
        out[name] = value
    parts = editor.changed_text_parts()
    if parts:
        out["text_pt"] = {p: s["pt"] for p, s in parts.items() if "pt" in s} or None
        out["text_font"] = {p: s["font"] for p, s in parts.items() if "font" in s} or None
        for k in ("text_pt", "text_font"):
            if out[k] is None:
                del out[k]
            else:
                out[k] = {p: (v if v not in (None, "") else "auto") for p, v in out[k].items()}
    return out


def open_editor(gui, panel, *, exec_dialog=True):
    """Edit *panel* (a data plot) in staplot's editor; OK applies the changes.
    Returns the edit_data_plot arguments applied, "annotations" when the user asked for
    the panel's annotations / script instead, or None."""
    from pyfigures.assistant.plot_info import parse_data_plot
    from staplot.ui.plot_editor import PlotEditor
    spec = parse_data_plot(getattr(panel, "custom_loading_script", None) or "")
    loc = gui._locate_panel(panel) if hasattr(gui, "_locate_panel") else None
    if spec is None or loc is None:
        return None
    args = editor_arguments(spec)
    ed = PlotEditor(args["path"], args["kind"], args["kwargs"], args["table_kwargs"], args["facet"],
                    parts=text_parts_of_panel(panel), parent=gui, title="Edit the plot (staplot)")
    wanted = {}

    def annotations():
        wanted["annotations"] = True
        ed.reject()
    ed.add_button("Annotations && script…", annotations, "fa5s.pen")
    gui._staplot_editor = ed                  # tests drive it before exec
    if not exec_dialog:
        return ed
    accepted = ed.exec()
    if wanted:
        return "annotations"
    changes = edit_arguments(ed, args["kwargs"], args["kind"]) if accepted else {}
    if not changes and not ed.data_saved:
        return None
    from pyfigures.mcp_server import edit_data_plot
    gui._run_mcp_mutation(edit_data_plot, "Plot changed.", group_path=loc[0], image_index=loc[1],
                          **(changes or {"csv_path": args["path"]}))
    return changes
