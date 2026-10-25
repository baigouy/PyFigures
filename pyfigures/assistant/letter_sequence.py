"""Plan scoped lettering before mutating the scene."""
def plan_letters(entries, selected, action, start, default, increment):
    selected=set(selected)
    used={}
    for pid,texts in entries:
        if pid not in selected:
            for text in texts:
                used.setdefault(text.casefold(),pid)
    result={}
    sequence=start or default or 'a'
    positional=default or 'a'
    for pid,texts in entries:
        position=positional
        positional=increment(positional)
        if pid not in selected:
            continue
        if action=='restore' and start is None:
            proposed=texts[0] if texts else position
            if proposed.casefold() in used:
                proposed=position
                while proposed.casefold() in used:
                    proposed=increment(proposed)
        else:
            proposed=sequence
            sequence=increment(sequence)
            if proposed.casefold() in used:
                raise ValueError('LETTER_CONFLICT: '+proposed+' is already assigned to panel '+used[proposed.casefold()]+'. Use renumber with scope all for a complete sequence, or choose an unused starting letter. No edit performed.')
        used[proposed.casefold()]=pid
        result[pid]=proposed
    return result
