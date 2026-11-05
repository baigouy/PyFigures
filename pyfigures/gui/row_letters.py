"""Row letters: ONE panel letter per figure row, drawn OUTSIDE the row in a
left margin (as in many journal figures), instead of one letter inside each
panel.

The figure setting is ``letter_layout``: 'panel' (default, a letter in a
corner of every panel) or 'row'. With 'row', ``row_letter_align`` says where
the letter sits next to its row: 'top' (default, level with the top of the
row and of the label rows above it) or 'center'.

Both are saved with the figure in ``<SerializableGUIparameters>``. The canvas
(ezfig.MyWidget) keeps the margin free when it lays the rows out (the figure
keeps its width: the rows are narrowed by the margin) and draws the letters
itself, so every export (PNG/TIFF/SVG/PDF, the editable PPTX/Illustrator
capture, the headless render) shows them uncut. They follow the row order:
nothing is stored per row.
"""
from __future__ import annotations

LAYOUTS = ('panel', 'row')
ALIGNS = ('top', 'center')
DEFAULT_LAYOUT = 'panel'
DEFAULT_ALIGN = 'top'


def normalise_layout(value) -> str:
    """'row' or 'panel' (None, '' and unknown values: 'panel')."""
    v = str(value or '').strip().strip('"').lower()
    if v in ('row', 'rows', 'per row', 'per_row', 'outside', 'outside left', 'row left'):
        return 'row'
    return 'panel'


def normalise_align(value) -> str:
    v = str(value or '').strip().strip('"').lower()
    if v in ('center', 'centre', 'middle', 'center_v', 'centre_v'):
        return 'center'
    return 'top'


def layout_error(value) -> str | None:
    v = str(value or '').strip().strip('"').lower()
    if v in ('row', 'panel', 'rows', 'per row', 'per_row', 'outside', 'outside left', 'row left', 'panels',
             'per panel', 'per_panel', 'inside'):
        return None
    return f"letter_layout must be 'panel' (a letter in each panel) or 'row' (one letter per row, " \
           f"outside it on the left), not {value!r}"


def align_error(value) -> str | None:
    v = str(value or '').strip().strip('"').lower()
    if v in ('top', 'center', 'centre', 'middle'):
        return None
    return f"row_letter_align must be 'top' or 'center', not {value!r}"


def install_gui_params_fields():
    """Let SerializableGUIparameters (batoolset-gui) keep the two fields on
    load: its constructor drops unknown keywords, so the setting was lost on
    reopen and undo. Only set when given, so figures without it are saved
    exactly as before. Harmless once batoolset-gui keeps them itself."""
    from batoolset.drawings.shapes.serializableguiparams import SerializableGUIparameters as cls
    if getattr(cls, '_pyfigures_row_letters', False):
        return
    original = cls.__init__

    def __init__(self, *args, letter_layout=None, row_letter_align=None, **kwargs):
        original(self, *args, **kwargs)
        if letter_layout is not None and not hasattr(self, 'letter_layout'):
            self.letter_layout = normalise_layout(letter_layout)
        if row_letter_align is not None and not hasattr(self, 'row_letter_align'):
            self.row_letter_align = normalise_align(row_letter_align)

    cls.__init__ = __init__
    cls._pyfigures_row_letters = True


def lettered_rows(shapes) -> list:
    """The top-level shapes that get a row letter, in order: every image row
    / column / single panel; label rows (text rows) are not rows."""
    return [s for s in shapes if not getattr(s, 'isText', False)]


def block_top(shapes, row):
    """Top of *row* together with the label rows above it that label it (a
    letter goes level with the column titles, as in journals)."""
    from pyfigures.gui.label_rows import labelled_row
    top = row.getRect(all=True).top()
    i = next((k for k, s in enumerate(shapes) if s is row), None)
    if i is None:
        return top
    j = i - 1
    while j >= 0 and getattr(shapes[j], 'isText', False):
        if labelled_row(shapes, j) is row:
            top = min(top, shapes[j].getRect(all=True).top())
        j -= 1
    return top


def letter_colour(font, page_background):
    """The letter colour: the figure's letter colour, unless it would vanish
    on the page around the rows (white letters for dark micrographs on a
    white/transparent page) — then black, or white on a dark page."""
    fg = getattr(font, 'foreground', None)
    if fg is None or getattr(font, 'background', None) is not None:
        return fg                      # its own box: the colour chosen for the box

    def lum(c):
        c = int(c) & 0xFFFFFF
        return 0.299 * ((c >> 16) & 0xFF) + 0.587 * ((c >> 8) & 0xFF) + 0.114 * (c & 0xFF)

    page = 0xFFFFFF if page_background is None else int(page_background) & 0xFFFFFF
    if abs(lum(fg) - lum(page)) >= 90:
        return int(fg) & 0xFFFFFF
    return 0x000000 if lum(page) >= 128 else 0xFFFFFF


def make_letter(font, text, colour):
    """A free TAText2D (no corner placement: drawn where it is put)."""
    from batoolset.drawings.shapes.txt2d import TAText2D
    html = font.get_letter_html(text, foreground=colour)
    t = TAText2D(html, placement=None, fill_color=getattr(font, 'background', None), is_letter=True)
    t._row_letter = True
    return t


def edge_pad(letter_width):
    """Room left of a letter: its ink starts at its box edge, and the figure
    edge cut its anti-aliasing."""
    return max(0.5, 0.08 * float(letter_width))


def gap(letter_width):
    """Space between a letter and its row: about a third of a letter."""
    return max(2.0, 0.35 * float(letter_width))
