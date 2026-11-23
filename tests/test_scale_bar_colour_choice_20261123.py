"""User chat 2026-11-23: "change scale bar color in b and k because they don't read well" got a
question ("which colour?"), then "white, yellow, red" got another ("which goes where?"): the
model must choose a readable colour itself, and pick per panel from a list the user gives."""


def test_the_scale_bar_rule_says_choose_never_ask():
    from pyfigures.assistant.categorized_mcp import request_rules
    rules = request_rules("change scale bar color in b and k because they don't read well")
    assert "choose it yourself, never ask" in rules and "black <-> white" in rules
    assert "the one reading best on each" in rules
