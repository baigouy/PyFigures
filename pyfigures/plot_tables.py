"""The data tables of plot panels (data plots, seaborn plots) and their consolidation.

A plot panel has no image file: its table (CSV, TXT, Excel...) is named inside its
script, so Save & Consolidate gathered the images and left the tables behind (user,
2026-11-18: "staplot should also handle the consolidation, which is just the excel
file in this case"). Here the tables are copied into the figure's ``.files`` folder
and the scripts are pointed at the copies.

A table path may carry an Excel sheet: ``book.xlsx::counts``.
"""
from __future__ import annotations

import ast
import io
import json
import os
import shutil
import tokenize
import xml.etree.ElementTree as ET

SHEET_SEP = "::"
SEABORN_MARKER = "# pyfigures-seaborn: "
_DATA_PLOT_HINT = "_api.plot("


def is_sqlite_file(path: str) -> bool:
    """An SQLite database, by its magic header (any name: .db, .sqlite, .sqlite3, or
    none; a Windows Thumbs.db is not one)."""
    try:
        with open(path, "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except (OSError, ValueError, TypeError):
        return False


def split_sheet(path: str) -> tuple[str, str]:
    """("book.xlsx", "::counts") for "book.xlsx::counts"; (path, "") otherwise. An
    SQLite database keeps its table or query: ("cells.db", "::SELECT ...")."""
    if isinstance(path, str) and SHEET_SEP in path:
        file, sheet = path.split(SHEET_SEP, 1)
        if file.lower().endswith((".xlsx", ".xlsm", ".xls") + SQLITE_EXTENSIONS) or is_sqlite_file(file):
            return file, SHEET_SEP + sheet
    return path, ""


TABLE_EXTENSIONS = (".csv", ".tsv", ".xlsx", ".xlsm", ".xls")
SQLITE_EXTENSIONS = (".sqlite", ".sqlite3", ".db", ".db3")


def is_plot_table(path: str) -> bool:
    """A file a plot can be made from: CSV, TSV, Excel, or a .txt / .dat holding a table
    of numbers (a .txt of notes is not one)."""
    low = str(path).lower()
    if os.path.basename(low).startswith("~$"):      # Excel's lock file of an open workbook
        return False
    if low.endswith(TABLE_EXTENSIONS):
        return True
    # an SQLite database, whatever its name (user, 2026-11-18: "I very often use SQLite
    # DBs"; "the magic sign at the beginning of the file should be checked")
    if is_sqlite_file(path):
        return True
    if not low.endswith((".txt", ".dat")):
        return False
    try:
        from staplot.api import read_table
        import pandas as pd
        df = read_table(path)
    except Exception:
        return False
    if df.shape[1] < 2 and not (df.shape[1] == 1 and len(df) > 2):
        return False
    numbers = sum(int(pd.to_numeric(df[c], errors="coerce").notna().sum()) for c in df.columns)
    return numbers >= 3


def is_drawn_by_script(panel) -> bool:
    """A panel drawn by its script with no image file (a data plot, a seaborn plot, a
    matplotlib or LaTeX code panel): a double click opens its editor on the Script tab
    (user, 2026-11-18: "this is what most users would want"). A file panel with a
    script that only adjusts the file keeps the usual tab."""
    script = getattr(panel, "custom_loading_script", None)
    if not isinstance(script, str) or not script.strip() or script.strip() == "None":
        return False
    filename = getattr(panel, "filename", None)
    return filename in (None, "", "None") or (isinstance(filename, str) and filename.startswith("__"))


def is_plot_script(script: str) -> bool:
    return isinstance(script, str) and (script.startswith(SEABORN_MARKER) or _DATA_PLOT_HINT in script)


def _string_literals(script: str):
    """(start, end, value) of every string literal of *script*, by character offsets."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(script).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    offsets = [0]
    for line in script.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    out = []
    for t in toks:
        if t.type != tokenize.STRING:
            continue
        try:
            value = ast.literal_eval(t.string)
        except Exception:
            continue
        if isinstance(value, str):
            out.append((offsets[t.start[0] - 1] + t.start[1], offsets[t.end[0] - 1] + t.end[1], value))
    return out


def table_paths(script: str) -> list[str]:
    """The table files a plot script reads (without their sheet), in order, once each."""
    if not is_plot_script(script):
        return []
    out = []
    for _a, _b, value in _string_literals(script):
        file, _sheet = split_sheet(value)
        if os.path.isabs(file) and os.path.isfile(file) and file not in out:
            out.append(file)
    return out


def rewrite_table_paths(script: str, mapping: dict[str, str]) -> str:
    """*script* with every table path of *mapping* (old file -> new file) replaced, the
    sheet kept; the seaborn header (its settings as JSON) follows too."""
    if not mapping:
        return script
    edits = []
    for a, b, value in _string_literals(script):
        file, sheet = split_sheet(value)
        if file in mapping:
            edits.append((a, b, repr(mapping[file] + sheet)))
    for a, b, rep in reversed(edits):
        script = script[:a] + rep + script[b:]
    if script.startswith(SEABORN_MARKER):
        head, _, rest = script.partition("\n")
        try:
            spec = json.loads(head[len(SEABORN_MARKER):])
        except ValueError:
            return script
        file, sheet = split_sheet(spec.get("csv", ""))
        if file in mapping:
            spec["csv"] = mapping[file] + sheet
            head = SEABORN_MARKER + json.dumps(spec, ensure_ascii=False, sort_keys=True)
        script = head + "\n" + rest
    return script


def _decode(text):
    if text is None:
        return "", False
    raw = text
    wrapped = raw.startswith('""') and raw.endswith('""') and len(raw) >= 4
    return raw[2:-2] if wrapped else raw, wrapped


def consolidate_plot_tables(pyf_path: str, files_dir: str | None = None) -> list[tuple[str, str]]:
    """Copy the tables of every plot panel of *pyf_path* into *files_dir* (default:
    the figure's ``.files`` folder) and point the scripts at the copies. Two different
    tables with one name get distinct names. Returns [(source, copy), ...]."""
    pyf_path = os.path.abspath(pyf_path)
    # one separator style (the GUI's ".files" path mixes / and \)
    files_dir = os.path.abspath(files_dir or os.path.splitext(pyf_path)[0] + ".files")
    tree = ET.parse(pyf_path)
    root = tree.getroot()
    copied: dict[str, str] = {}
    used: set[str] = set()
    changed = False
    for img in root.iter("Image2D"):
        el = img.find("custom_loading_script")
        if el is None or not el.text or el.text.strip() in ("None", ""):
            continue
        script, wrapped = _decode(el.text)
        tables = table_paths(script)
        if not tables:
            continue
        mapping = {}
        for src in tables:
            if os.path.normcase(os.path.dirname(src)) == os.path.normcase(os.path.abspath(files_dir)):
                continue                                   # already in the bundle
            if src not in copied:
                os.makedirs(files_dir, exist_ok=True)
                stem, ext = os.path.splitext(os.path.basename(src))
                name, n = stem + ext, 1
                while name.lower() in used or (os.path.exists(os.path.join(files_dir, name))
                                               and not _same_file(src, os.path.join(files_dir, name))):
                    n += 1
                    name = f"{stem}_{n}{ext}"
                used.add(name.lower())
                dst = os.path.join(files_dir, name)
                shutil.copy2(src, dst)
                copied[src] = dst
            mapping[src] = copied[src]
        new = rewrite_table_paths(script, mapping)
        if new != script:
            el.text = f'""{new}""' if wrapped else new
            changed = True
    if changed:
        tree.write(pyf_path, encoding="utf-8", xml_declaration=False)
    return list(copied.items())


def _same_file(a: str, b: str) -> bool:
    try:
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False
