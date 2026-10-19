"""Page sizes offered by the poster / album designer (window, recipes, MCP).
No Qt import, so the command-line parser can use it."""

# name -> (width mm, height mm), portrait
PAGE_PRESETS = {
    'A6': (105.0, 148.0),
    'A5': (148.0, 210.0),
    'A4': (210.0, 297.0),
    'A3': (297.0, 420.0),
    'A2': (420.0, 594.0),
    'A1': (594.0, 841.0),
    'A0': (841.0, 1189.0),
    'Letter': (215.9, 279.4),
    'Legal': (215.9, 355.6),
    'Tabloid': (279.4, 431.8),
}


def preset_size(name):
    """(width, height) mm of a page preset, any case ("a4", "letter");
    ValueError for an unknown name."""
    for key, size in PAGE_PRESETS.items():
        if key.lower() == str(name).strip().lower():
            return size
    raise ValueError(f'unknown page preset {name!r}; use one of {", ".join(PAGE_PRESETS)}')
