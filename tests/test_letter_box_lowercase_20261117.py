"""A panel letter on a box stays where it was without the box, lowercase included.

User, 2026-11-17: after a black background was added to the letters "all the letters
went slightly down", then: "the bug was due to the fact that small letters are not
really up eg a compared to big ones like l". Without a box a top letter is lifted so
its ink touches the top (TAText2D._letter_ink_shift); with a box the lift was off and
the box was the whole line box, so an "a" (lots of empty line above it) sat much lower
than an "l". The box now hugs the letter's own ink with an even padding.
"""
from __future__ import annotations

import numpy as np
import pytest

LETTERS = ("a", "l", "g", "x", "b", "e")
_APP = []          # the QApplication must stay referenced, or drawing text crashes


def _draw(letter, boxed, mode="hug", size=40):
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication
    if not _APP:
        _APP.append(QApplication.instance() or QApplication([]))
    from qtpy.QtGui import QImage, QPainter, QColor
    from batoolset.drawings.shapes.txt2d import TAText2D
    from batoolset.drawings.shapes.Position import Position
    TAText2D.LETTER_BOX = mode
    TAText2D._ink_shift_cache.clear()
    try:
        t = TAText2D(f'<font style="font-family:Segoe UI;font-size:{size}pt" color="#ffffff">{letter}</font>',
                     is_letter=True, placement=Position("top left"))
        t.fill_color = 0 if boxed else None
        t.setTopLeft(0, 10)
        img = QImage(200, 200, QImage.Format.Format_RGB32)
        img.fill(QColor(128, 128, 128))
        p = QPainter(img)
        t.draw(p)
        p.end()
    finally:
        TAText2D.LETTER_BOX = "hug"
        TAText2D._ink_shift_cache.clear()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    rgb = np.frombuffer(ptr, np.uint8).reshape(200, 200, 4)[..., :3].astype(int)
    ink = np.nonzero((rgb.min(-1) > 200).any(1))[0]          # white letter
    box = np.nonzero((rgb.max(-1) < 30).any(1))[0]           # black box
    return (ink[0], ink[-1]), ((box[0], box[-1]) if len(box) else None)


def _ink_rows_of(texts, size=40):
    """Draw stacked texts (white on grey), return each one's (top, bottom) ink rows."""
    from qtpy.QtGui import QImage, QPainter, QColor
    out = []
    for t in texts:
        img = QImage(400, 400, QImage.Format.Format_RGB32)
        img.fill(QColor(128, 128, 128))
        p = QPainter(img)
        t.draw(p)
        p.end()
        ptr = img.constBits()
        ptr.setsize(img.sizeInBytes())
        rgb = np.frombuffer(ptr, np.uint8).reshape(400, 400, 4)[..., :3].astype(int)
        rows = np.nonzero((rgb.min(-1) > 200).any(1))[0]
        out.append((rows[0], rows[-1]))
    return out


@pytest.mark.parametrize("corner", ["top left", "bottom left"])
@pytest.mark.parametrize("first", ["a", "g", "B"])
def test_corner_texts_stack_by_their_ink(corner, first):
    # user, 2026-11-17: the space between a panel letter and the text under it was
    # "way too big" (~65 % of the letter): texts were stacked by their line boxes
    _draw("a", boxed=False)                     # Qt application + UI
    from batoolset.drawings.shapes.txt2d import TAText2D
    from batoolset.drawings.shapes.Position import Position
    from batoolset.drawings.shapes.image2d import stack_texts_by_ink, TEXT_STACK_GAP
    from batoolset.figure.alignment import pack2

    def text(s, letter):
        return TAText2D(f'<font style="font-family:Segoe UI;font-size:40pt" color="#ffffff">{s}</font>',
                        is_letter=letter, placement=Position(corner))
    letter, label = text(first, True), text("control", False)
    letter.setTopLeft(5, 5 if corner.startswith("top") else 330)
    label.setTopLeft(5, 0)
    pack2(1, letter.placement, True, letter, label)
    old_rows = _ink_rows_of([letter, label])
    stack_texts_by_ink([letter, label])
    rows = _ink_rows_of([letter, label])
    if corner.startswith("top"):
        gap, old_gap = rows[1][0] - rows[0][1], old_rows[1][0] - old_rows[0][1]
    else:
        gap, old_gap = rows[0][0] - rows[1][1], old_rows[0][0] - old_rows[1][1]
    assert abs(gap - TEXT_STACK_GAP * label.height()) <= 3, (gap, label.height())
    assert gap < old_gap


@pytest.mark.parametrize("letter", LETTERS)
def test_the_letter_stays_where_it_was_without_a_box(letter):
    (top0, _), _ = _draw(letter, boxed=False)
    (top1, bottom1), (box_top, box_bottom) = _draw(letter, boxed=True)
    assert box_top == 10                                  # the box sits in the corner
    pad_above, pad_below = top1 - box_top, box_bottom - bottom1
    assert 1 <= pad_above <= 12 and abs(pad_above - pad_below) <= 2    # even padding around the ink
    assert abs(top1 - (top0 + pad_above)) <= 2            # moved by the padding only


def test_without_a_box_every_letter_top_is_at_the_same_height():
    # the font-metrics lift left "l" and "b" lower than "a" (seen on the same render)
    tops = {c: _draw(c, boxed=False)[0][0] for c in LETTERS}
    assert max(tops.values()) - min(tops.values()) <= 1, tops


def test_a_sits_as_high_as_l_on_a_box():
    tops = {c: _draw(c, boxed=True)[0][0] for c in ("a", "l")}
    assert abs(tops["a"] - tops["l"]) <= 2
    # the old full-line box: the bug the user saw, "a" far lower than "l"
    old = {c: _draw(c, boxed=True, mode="line")[0][0] for c in ("a", "l")}
    assert old["a"] - old["l"] > 6
