"""2026-11-19 (live Mistral replay, trimmed instructions): the topic rules reached the
model only through a search, and in six requests it never searched (it previewed a
panel seven times for "draw ROIs over every cell in e", then gave up). The chat now
asks for the rules of the request's own words and sends them WITH it: only the
topics those words call for, so the first message stays small. Checked here without
any model: each request of that replay gets the rule it lacked, and a sentence that
is not about a topic gets none."""
import re

import pytest

from pyfigures.assistant.categorized_mcp import REQUEST_KEYS, TOPIC_RULES, request_rules

# (the request, the request before it, a phrase its rules must hold)
NEEDED = [
    ('cna you draw ROIs over every cell in e', '', 'detect_objects(panel_ref) in one call'),
    ('you did not finish', 'cna you draw ROIs over every cell in e', 'detect_objects(panel_ref) in one call'),
    ('put in fcat two arrowheads close to the teeth/white in left and right side of the mouth', '',
     'style="arrowhead"'),
    ('can you make a figure to illustrate that ?', '', 'add_scripted_image(group_path, script)'),
    ('Two horizontal bars side by side (or stacked) representing the paired homologous chromosomes',
     'can you make a figure to illustrate that ?', 'add_scripted_image(group_path, script)'),
    ('add a black bg to g', '', 'it is the PANEL background'),
    ("I can't see well the letter of panel b, can you imporve taht", '', 'edit_panel_letters once'),
    ('make an inset in the central part of the second image of the first row', '', 'An INSET sits in a corner'),
    ('swap b and c', '', 'swaps the image PANELS'),
    ('add scale bars to all', '', 'set_scale_bar_all'),
    ('reset all LUTs in e', '', 'set_lut with "NONE"'),
    ('I want a,c and e in one row, the rest in another tow', '', 'arrange_live_images once'),
    ('save this fig as a ppt in my folder', '', 'FILES:'),
    # user 2026-11-19 ("I love this feature, it cannot be lost"): the editor opens on the named panel's tab
    ('let me edit the b crop', '', 'open_annotation_editor(panel_ref, tab="crop"'),
    ('I said b, you opened g', 'let me edit the b crop', 'never the selected one instead'),
]


@pytest.mark.parametrize('text, earlier, phrase', NEEDED)
def test_a_request_gets_the_rule_it_needs(text, earlier, phrase):
    assert phrase in request_rules(text, earlier)


@pytest.mark.parametrize('text', ['not bad', 'thanks', 'Two horizontal bars side by side (or stacked)',
                                  'same of the second image of the third one', 'perfect', 'yes go on'])
def test_a_sentence_about_no_topic_gets_no_rule(text):
    rules = request_rules(text)
    # "not bad" is no NOTE, "bars side by side" no scale bar, "same" no lettering rule
    assert 'SCALE BARS' not in rules and 'LETTERS' not in rules and 'TEXT / EDITOR' not in rules
    assert rules == '' or text.startswith('same')


def test_the_rules_stay_small():
    for text, earlier, _ in NEEDED:
        assert len(request_rules(text, earlier)) < 3000, text


def test_every_topic_can_be_called_by_a_request():
    topics = {rule.split(':', 1)[0] for _keys, rule in TOPIC_RULES}
    assert topics == set(REQUEST_KEYS)


def test_the_bridge_answers_without_a_figure():
    from types import SimpleNamespace
    from pyfigures.assistant import session as S
    fake = SimpleNamespace(window=None)
    import pyfigures.assistant.gui_selection as G
    original = G.sync_editor
    G.sync_editor = lambda session: None
    try:
        out = S.Session.execute(fake, {'operation': 'request_rules', 'request_id': 'x',
                                       'arguments': {'text': 'add scale bars to all', 'earlier': ''}})
    finally:
        G.sync_editor = original
    assert re.match(r'SCALE BARS:', out['rules'])


def test_the_web_chat_sends_them_with_the_first_request():
    from pyfigures.assistant.web_chat import instructions_prompt
    text = instructions_prompt([], 'Guidance.', None, 'draw ROIs over every cell in e')
    assert 'Rules for this request: ROIs:' in text and text.index('Rules for this request') < text.index('My request:')
    assert 'Rules for this request' not in instructions_prompt([], 'Guidance.', None, 'thanks')


def test_investigating_two_panels_runs_the_duplicate_check():
    """User 2026-11-19: "can you investigate n and o images?" got eight previews and no
    word that o is n inverted; check_image_integrity reports it (transform "invert")."""
    assert 'check_image_integrity once' in request_rules('can you investigate n and o images ?')
    assert 'INTEGRITY' not in request_rules('compare everything to WT')
