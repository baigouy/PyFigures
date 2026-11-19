"""2026-11-19 (user): a scale bar put top left sat a whole letter height under the
panel letter; it is now stacked by its ink, as two corner texts are."""


def test_a_scale_bar_sits_just_under_the_letter(qtbot):
    from batoolset.drawings.shapes.txt2d import TAText2D
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.image2d import stack_texts_by_ink, _stack_ink, TEXT_STACK_GAP
    letter = TAText2D("<font size=5>a</font>", placement="top-left", is_letter=True)
    bar = ScaleBar(30, "30 px", placement="top-left")
    bar.update_bar_at_scale(1)
    letter.setTopLeft(0, 0)
    bar.setTopLeft(0, letter.height() + 3)               # where pack2 leaves it
    before = bar.y() + _stack_ink(bar)[0] - (letter.y() + letter.ink_extent()[1])
    stack_texts_by_ink([letter, bar])
    gap = bar.y() + _stack_ink(bar)[0] - (letter.y() + letter.ink_extent()[1])
    assert 0 < gap < before
    assert abs(gap - TEXT_STACK_GAP * bar.legend.height()) < 0.5
