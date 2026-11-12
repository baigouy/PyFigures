"""Small verified figure memory and strict property-preservation checks."""
FIELDS = ('text', 'placement', 'font_family', 'font_size', 'color', 'background', 'opacity', 'bold', 'italic', 'underline')
MOVE_HINT = 'To regroup images into rows (equal or uneven, e.g. 3-2-2-2) use arrange_live_images with columns or row_counts in ONE call; it keeps reading order and letters. To move single images, move them so the reading order stays the same.'
REQUEST_FIELDS = {'placement': 'placement', 'font_family': 'font_family', 'font_size': 'font_size',
                  'color_value': 'color', 'background': 'background',
                  # "rename g to G'": the requested text of one panel's letter (it was rolled back
                  # as an unrequested change, 2026-11-12)
                  'text': 'text',
                  # "the letter bold on every rotated panel" (2026-11-12)
                  'bold': 'bold', 'italic': 'italic', 'underline': 'underline'}


def specification(state):
    letters = [a for panel in state['panels'] for a in panel['letters']]
    uniform = {}
    for field in FIELDS[1:]:
        values = [a.get(field) for a in letters]
        uniform[field] = values[0] if values and all(v == values[0] for v in values) else 'mixed' if values else None
    spec = {'image_panels': len(state['panels']), 'visible_letters': len(letters),
            'duplicate_letter_references':state.get('duplicate_letter_references',{}),
            'uniform_letter_style': uniform, 'unlettered_panel_ids': state['unlettered_panel_ids'],
            'letter_layout': state.get('letter_layout', 'panel'),
            'source': 'Actual GUI readback; preserve unspecified properties on follow-up edits.'}
    if spec['letter_layout'] == 'row':
        # one letter per ROW, outside the rows on the left (drawn by the canvas):
        # the panels carry none on purpose
        row_letters = state.get('row_letters') or []
        spec.update(visible_letters=len(row_letters),
                    row_letters=[r['text'] for r in row_letters],
                    row_letter_align=state.get('row_letter_align', 'top'),
                    letter_layout_note='One letter per row, outside the rows on the left; change it '
                                       'with set_panel_letter_layout (letter_layout="panel" puts a '
                                       'letter back in each panel).')
    return spec


def changes(before, after):
    old = {p['panel_id']: p for p in before['panels']}
    result = []
    for panel in after['panels']:
        previous = old.get(panel['panel_id'], {}).get('letters', [])
        current = panel['letters']
        if len(previous) != len(current):
            result.append({'panel_id': panel['panel_id'], 'property': 'letter_count', 'before': len(previous), 'after': len(current)})
        for index, (a, b) in enumerate(zip(previous, current)):
            for field in FIELDS:
                if a.get(field) != b.get(field):
                    result.append({'panel_id': panel['panel_id'], 'letter_index': index,
                                   'property': field, 'before': a.get(field), 'after': b.get(field)})
    return result


def movement_changes(before, after):
    """Container indices change on moves; match images before comparing labels."""
    known = {}
    for panel in before['panels']:
        known.setdefault(panel['filename'], []).append(panel)
    aligned = []
    for panel in after['panels']:
        candidates = known.get(panel['filename'], [])
        if len(candidates) > 1:
            texts = [a['text'] for a in panel['letters']]
            candidates = [p for p in candidates if [a['text'] for a in p['letters']] == texts]
        if len(candidates) != 1:
            raise ValueError('MOVE_VERIFICATION_FAILED: Cannot uniquely match image identity; edit rolled back. ' + MOVE_HINT)
        matched = candidates[0]
        known[panel['filename']].remove(matched)
        aligned.append({**matched, 'panel_id': panel['panel_id']})
    if any(known.values()):
        raise ValueError('MOVE_VERIFICATION_FAILED: Image count changed; edit rolled back.')
    deltas = changes({**before, 'panels': aligned}, after)
    if deltas:
        raise ValueError('MOVE_VERIFICATION_FAILED: this move changes the panel letters (their reading order); edit rolled back. ' + MOVE_HINT)
    return deltas


def describe(deltas, spec):
    import json
    grouped = {}
    for delta in deltas:
        key = (delta['property'], json.dumps(delta['before']), json.dumps(delta['after']))
        grouped.setdefault(key, set()).add(delta['panel_id'])
    def value(raw):
        decoded = json.loads(raw)
        names = {'#ffffff': 'white', '#000000': 'black', '#d3d3d3': 'light gray', 'center_h center_v': 'center'}
        return 'none' if decoded is None else names.get(str(decoded), str(decoded))
    lines = [f"{len(ids)} panel(s): {field}: {value(old)} → {value(new)}" for (field, old, new), ids in grouped.items()]
    if not lines:
        lines = ['No visible letter-property changes.']
    style = spec.get('uniform_letter_style', {})
    lines.append('Verified now: ' + ', '.join(f'{k}={value(json.dumps(style.get(k)))}'
                 for k in ('color', 'background', 'placement')))
    return '\n'.join(lines)


def verify_style(before, after, arguments, matched_ids):
    requested = {field for arg, field in REQUEST_FIELDS.items() if arguments.get(arg) is not None}
    deltas = changes(before, after)
    for delta in deltas:
        if delta['panel_id'] not in matched_ids or delta['property'] not in requested:
            raise ValueError('STYLE_PRESERVATION_FAILED: Unrequested change to ' + delta['panel_id'] + '.' + delta['property'] + '; edit rolled back.')
    for panel in after['panels']:
        if panel['panel_id'] not in matched_ids:
            continue
        policy = panel.get('override', {})
        for letter in panel['letters']:
            for field in requested:
                expected = policy.get(field, policy.get('base', {}).get(field, letter.get(field)))
                if letter.get(field) != expected:
                    raise ValueError('STYLE_VERIFICATION_FAILED: Actual ' + field + ' differs from the effective saved policy; edit rolled back.')
    return deltas
