#!/usr/bin/env python3
"""Restyle a PyFigures annotation's rich text without losing its formatting.

Annotation text is a Qt rich-text document (HTML) that may contain per-run
colour, super/subscript, bold spans, etc. Naively rewriting the HTML would
destroy that. Instead we load it into a QTextDocument and *merge* a character
format across the whole document: only the attributes you actually specify are
changed; everything else (per-span colour when you don't set colour, super /
subscript, existing bold) is preserved.

This needs Qt, so the PyFigures MCP server runs it in a subprocess (which also
isolates any Qt crash). It is a pure function of its input:

    python -m pyfigures.gui.style_text_headless <params.json> <out.html>

where params.json is UTF-8 JSON with keys:
    html        (str)   the current annotation HTML
    font_family (str|None)
    font_size   (number|None)   point size
    bold        (bool|None)
    italic      (bool|None)
    underline   (bool|None)
    color       (str|None)      any Qt colour string, e.g. "#ff0000" / "red"

The restyled HTML is written (UTF-8) to <out.html>. With ``htmls`` (a list)
instead of ``html``, every text gets the same attributes and <out.html> holds
JSON: {"htmls": [the results], "font_installed": true/false/null}.
"""
from __future__ import annotations

import os as _os
from pyfigures.offscreen import use_offscreen as _use_offscreen
_use_offscreen()   # offscreen + the system fonts (none at all on Windows otherwise)
_os.environ.setdefault("QT_API", "pyqt6")

import json
import sys


def restyle_html(html: str, *, font_family=None, font_size=None, bold=None,
                 italic=None, underline=None, color=None) -> str:
    """Return *html* with the given character attributes merged over every run.

    Only non-None attributes are applied; the rest of the formatting is kept.
    Requires a QApplication to exist (QTextDocument needs font metrics).
    """
    from qtpy.QtGui import (QTextDocument, QTextCursor, QTextCharFormat,
                            QFont, QColor)

    doc = QTextDocument()
    doc.setHtml(html or "")
    cursor = QTextCursor(doc)
    cursor.select(QTextCursor.Document)

    fmt = QTextCharFormat()
    if font_family is not None:
        fmt.setFontFamily(str(font_family))
    if font_size is not None:
        fmt.setFontPointSize(float(font_size))
    if bold is not None:
        fmt.setFontWeight(QFont.Bold if bold else QFont.Normal)
    if italic is not None:
        fmt.setFontItalic(bool(italic))
    if underline is not None:
        fmt.setFontUnderline(bool(underline))
    if color is not None:
        fmt.setForeground(QColor(str(color)))

    cursor.mergeCharFormat(fmt)
    return doc.toHtml()


def _main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        sys.stderr.write("usage: style_text_headless <params.json> <out.html>\n")
        return 2
    params_path, out_path = argv

    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841

    try:
        with open(params_path, "r", encoding="utf-8") as f:
            p = json.load(f)
        attrs = {k: p.get(k) for k in ("font_family", "font_size", "bold", "italic",
                                        "underline", "color")}
        if "htmls" in p:            # several texts at once: JSON out
            from qtpy.QtGui import QFontDatabase
            fam = attrs.get("font_family")
            out = json.dumps({"htmls": [restyle_html(h, **attrs) for h in p["htmls"]],
                              "font_installed": (None if not fam else
                                                 fam in QFontDatabase.families())})
        else:
            out = restyle_html(p.get("html", ""), **attrs)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
    except Exception as e:
        sys.stderr.write(f"ERROR: {type(e).__name__}: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
