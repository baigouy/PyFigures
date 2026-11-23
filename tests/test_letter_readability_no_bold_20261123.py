"""User 2026-11-23, on "l is not well visible, fix it": the chat made the letters bold (and
then black everywhere). "ideally it should just have changed the bg first and make sure the
font color contrasts well on the bg rather than changing font or making text bold (unless the
user specifically asks for it)". Bold / italic / underline / font / size now need the user's
words (style_request); a box and a contrasting colour do not."""
import pytest

from pyfigures.assistant import live_mcp


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(live_mcp, "call_live", lambda op, args: out.append(args) or {})
    return out


ASKED = "l is not well visible, fix it"


def test_the_logged_call_is_refused_and_says_what_to_do(sent):
    with pytest.raises(ValueError, match="STYLE_NOT_ASKED") as e:
        live_mcp.edit_panel_letters(action="style", scope="panels", panel_ids=["2/2"], bold=True,
                                    background="white", background_request="the letter " + ASKED,
                                    color="black", color_request="the letter " + ASKED)
    assert "contrasts with that box" in str(e.value) and "No edit performed" in str(e.value)
    assert sent == []


def test_a_box_and_a_contrasting_colour_need_no_style_request(sent):
    live_mcp.edit_panel_letters(action="style", scope="panels", panel_ids=["2/2"],
                                background="white", background_request="the letter " + ASKED,
                                color="black", color_request="the letter " + ASKED)
    assert sent and "bold" not in sent[-1]


@pytest.mark.parametrize("kw, words", [
    (dict(bold=True), "make the letters bold"),
    (dict(italic=True), "letters in italic please"),
    (dict(font_size=14), "make the letters bigger"),
    (dict(font_family="Arial"), "use Arial for the letters"),
    (dict(font_size=12), "letters at 12 pt"),
])
def test_asked_type_changes_go_through(sent, kw, words):
    live_mcp.edit_panel_letters(action="style", scope="all", style_request=words, **kw)
    assert sent


def test_undoing_bold_and_other_actions_need_no_request(sent):
    live_mcp.edit_panel_letters(action="style", scope="all", bold=False)          # "don't make letters bold"
    live_mcp.edit_panel_letters(action="renumber", scope="all")
    assert len(sent) == 2
