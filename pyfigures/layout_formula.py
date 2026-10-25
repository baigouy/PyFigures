"""Layout formulas: a whole figure layout in one short line.

    (a,b,c)/(d,e,f)            two rows of three panels
    (a,(b/c))/d                b over c, the pair beside a (a spans both)
    ((a/d),((b,c)/e/f))/(h,g)  any depth of nesting
    [a,b,c/d,e,f]              a GRID: two rows of three cells of equal size

* ``,`` (or ``|``) puts panels side by side, ``/`` stacks them; ``,`` binds
  tighter than ``/``, so ``a,b/c,d`` (``a|b/c|d``) is the row ``a,b`` over the
  row ``c,d``.
* ``( )`` groups: a group spans the rows / columns of what it holds, so
  ``(a,(b/c))`` gives a panel a beside a column of two (a multi-row panel).
  Brackets around a single side-by-side or stacked list are optional at the top.
* ``[ ]`` is a grid: every cell is centre-cropped to the same aspect ratio
  (the most common one in the grid), so rows have equal heights and columns
  line up. Plain groups keep each panel's own aspect ratio (no crop), which
  is why their columns do not line up when the aspect ratios differ.
* A name is a panel id defined in the recipe's ``panels:`` (any recipe panel:
  an image with its crop / LUT / scale bar, a channel split, a plot…), or
  directly an image file name when it contains no ``, / ( ) [ ]`` or spaces.
  Ids are stable names, not positions: panel letters (A, B, C…) follow the
  reading order of the formula and are regenerated, the mapping id → source
  never changes.
* ``^`` adds insets (no letter of their own): ``a^b`` shows image ``b`` in a
  corner of ``a``; ``a^a`` is a zoom callout of ``a`` itself (a box on the
  centre, to refine afterwards in the GUI); ``a^b^c`` two insets.

The parenthesised comma/slash notation is inspired by Griphus (Systaxon,
UFES; https://www.systaxon.ufes.br/gri/), which builds figure plates from
formulas such as ``((1/5),(2/(3,4)/6))``. ``|`` for side by side comes from
an earlier PyFigures sketch of the same idea; the ``[ ]`` grid, the named
panels and the mapping to recipe panels are PyFigures'.

Used by recipes (``layout:``), the MCP tool build_figure_from_recipe, the
command line ``python -m pyfigures.layout_formula "(a,b)/c"`` (prints the
parsed tree) and the GUI (File → Build figure from recipe…).
"""
from __future__ import annotations

import json
import re
import sys

_TOKEN = re.compile(r"\s*(?:(?P<sym>[(),|/\[\]])|(?P<name>[^\s(),|/\[\]]+))")


class FormulaError(ValueError):
    """A formula that cannot be parsed; the message points at the place."""


def _err(text, pos, msg):
    caret = " " * pos + "^"
    return FormulaError(f"{msg} at character {pos + 1}:\n  {text}\n  {caret}")


def tokenize(text: str):
    pos = 0
    out = []
    text = str(text)
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = _TOKEN.match(text, pos)
        if not m:
            raise _err(text, pos, "unexpected character")
        start = m.start("sym") if m.group("sym") else m.start("name")
        sym = "," if m.group("sym") == "|" else m.group("sym")      # | = , (side by side)
        out.append((sym or m.group("name"), start, bool(m.group("name"))))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, text):
        self.text = str(text)
        self.toks = tokenize(self.text)
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, len(self.text), False)

    def take(self, sym=None):
        tok = self.peek()
        if sym is not None and tok[0] != sym:
            what = "the end" if tok[0] is None else repr(tok[0])
            raise _err(self.text, tok[1], f"expected {sym!r}, found {what}")
        self.i += 1
        return tok

    def parse(self):
        if not self.toks:
            raise FormulaError("the layout formula is empty")
        node = self.stack()
        tok = self.peek()
        if tok[0] is not None:
            raise _err(self.text, tok[1], f"unexpected {tok[0]!r}"
                       + (" (more ')' than '('?)" if tok[0] in ")]" else ""))
        return node

    def stack(self):
        items = [self.row()]
        while self.peek()[0] == "/":
            self.take("/")
            items.append(self.row())
        return items[0] if len(items) == 1 else {"type": "col", "children": items}

    def row(self):
        items = [self.atom()]
        while self.peek()[0] == ",":
            self.take(",")
            items.append(self.atom())
        return items[0] if len(items) == 1 else {"type": "row", "children": items}

    def atom(self):
        tok = self.peek()
        if tok[0] is None:
            raise _err(self.text, tok[1], "a panel or '(' is missing")
        if tok[2]:
            self.take()
            if "^" not in tok[0]:
                return {"type": "panel", "id": tok[0]}
            # a^b: panel a with b as an inset; a^a: a zoom callout of a itself
            host, *insets = tok[0].split("^")
            if not host or not all(insets):
                if not host:
                    where = tok[1]
                elif "^^" in tok[0]:
                    where = tok[1] + tok[0].index("^^") + 1
                else:
                    where = tok[1] + len(tok[0]) - 1
                raise _err(self.text, where, "'^' needs a panel on each side (a^b: b as an "
                                             "inset of a; a^a: a zoom of a)")
            return {"type": "panel", "id": host, "insets": insets}
        if tok[0] == "(":
            self.take("(")
            if self.peek()[0] == ")":
                raise _err(self.text, self.peek()[1], "empty ( )")
            node = self.stack()
            self.take(")")
            return node
        if tok[0] == "[":
            start = tok[1]
            self.take("[")
            if self.peek()[0] == "]":
                raise _err(self.text, self.peek()[1], "empty [ ]")
            inner = self.stack()
            self.take("]")
            if inner["type"] == "panel":
                raise _err(self.text, start, "a grid [ ] needs at least two cells")
            return {"type": "grid", "children": [inner]}
        raise _err(self.text, tok[1], f"unexpected {tok[0]!r}")


def _flatten(node):
    """(a,(b,c)) is (a,b,c): a group of the same direction inside another
    adds nothing. Grids are kept."""
    if node["type"] == "panel":
        return node
    kids = [_flatten(k) for k in node["children"]]
    if node["type"] in ("row", "col"):
        flat = []
        for k in kids:
            flat.extend(k["children"] if k["type"] == node["type"] else [k])
        kids = flat
    return {"type": node["type"], "children": kids}


def parse(text: str) -> dict:
    """The layout tree of *text*: {'type': 'row'|'col'|'grid'|'panel', ...}."""
    return _flatten(_Parser(text).parse())


def panel_ids(tree) -> list[str]:
    """Panel ids in reading order (the order of the panel letters)."""
    if tree["type"] == "panel":
        return [tree["id"]]
    out = []
    for k in tree["children"]:
        out.extend(panel_ids(k))
    return out


def panel_insets(tree) -> dict:
    """{panel id: [inset ids]} for the panels written a^b (insets carry no
    letter; a^a is a zoom callout of a)."""
    if tree["type"] == "panel":
        return {tree["id"]: list(tree["insets"])} if tree.get("insets") else {}
    out = {}
    for k in tree["children"]:
        out.update(panel_insets(k))
    return out


def grid_cells(tree) -> list[list[str]]:
    """The rows of panel ids of a grid node (its inner stack of rows)."""
    inner = tree["children"][0]
    rows = inner["children"] if inner["type"] == "col" else [inner]
    return [panel_ids(r) for r in rows]


def to_text(tree) -> str:
    """The formula of a tree (normalised: minimal brackets)."""
    t = tree["type"]
    if t == "panel":
        return "^".join([tree["id"]] + list(tree.get("insets") or []))
    if t == "grid":
        return "[" + to_text(tree["children"][0]) + "]"
    sep = "," if t == "row" else "/"
    parts = []
    for k in tree["children"]:
        s = to_text(k)
        if k["type"] in ("row", "col"):
            s = "(" + s + ")"
        parts.append(s)
    return sep.join(parts)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 0
    try:
        tree = parse(" ".join(argv))
    except FormulaError as e:
        print(f"ERROR: {e}")
        return 1
    print(json.dumps({"normalised": to_text(tree), "panels_in_reading_order": panel_ids(tree),
                      "tree": tree}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
