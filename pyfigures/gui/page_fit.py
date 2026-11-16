"""Keep an automatically built figure within one printed page.

Images added one by one go one below the other at the full figure width: ten
of them made a figure several pages tall (chat, 2026-11-16). After an
automatic layout (images added in the GUI or by the chat, rows arranged by the
chat) a figure taller than the page is
  1. given rows: each run of two or more images lying alone one below the
     other becomes rows, with the fewest images per row that fit the page;
  2. then, if still too tall, narrowed (aspect kept) until its height fits.
A width or a layout the user sets by hand is never touched (the user has the
final word); View → Fit new layouts to the page turns this off.

Page = printable area: the paper minus 15 mm at each side, 25 mm top and
bottom (A4 180 × 247 mm, about a journal's full page; Letter 186 × 229 mm).
Canvas units are points (72 per inch).
"""
from __future__ import annotations

PAGES_MM = {'A4': (180.0, 247.0), 'Letter': (185.9, 229.4)}
MAX_PER_ROW = 5              # images per row chosen automatically (more only when asked)
MIN_WIDTH_MM = 30.0          # narrower: panels too small to read; say so instead
MM_PER_PT = 25.4 / 72.0


def page_mm(name=None):
    if name is None:
        try:
            from pyfigures.gui.user_prefs import load_page_size
            name = load_page_size()
        except Exception:
            name = 'A4'
    return name if name in PAGES_MM else 'A4', PAGES_MM.get(name, PAGES_MM['A4'])


def prefs_enabled():
    """View → Fit new layouts to the page (on by default)."""
    try:
        from pyfigures.gui.user_prefs import load_fit_to_page
        return bool(load_fit_to_page())
    except Exception:
        return True


enabled = prefs_enabled          # the switch fit_to_page reads (tests replace it)


def figure_size_pt(panel):
    """(width, height) of everything on the canvas, in points; None if empty."""
    from batoolset.figure.fig_tools import get_master_bounds2
    if not panel.shapes_to_draw:
        return None
    b = get_master_bounds2(panel.shapes_to_draw)
    return float(b.width()), float(b.height())


def _relayout(window):
    panel = window.paint.EZFIG_panel
    panel.repack_all()
    panel.update_size()
    panel.update()


def _is_lone_image(shape):
    from batoolset.drawings.shapes.image2d import Image2D
    return isinstance(shape, Image2D) and not getattr(shape, 'isText', False)


def _lone_runs(shapes):
    """[(start, end)] of runs of 2+ consecutive top-level images not in a row."""
    runs, start = [], None
    for i, s in enumerate(list(shapes) + [None]):
        if s is not None and _is_lone_image(s):
            start = i if start is None else start
        else:
            if start is not None and i - start >= 2:
                runs.append((start, i))
            start = None
    return runs


def _aspect(shape):
    r = shape.getRect(all=True)
    return float(r.width()) / float(r.height()) if r.height() > 0 else 1.0


def _height_with_columns(shapes, runs, columns, width, space):
    """Figure height (pt) at *width* when each run becomes rows of *columns*."""
    in_run = {i for a, b in runs for i in range(a, b)}
    heights = []
    for i, s in enumerate(shapes):
        if i in in_run:
            continue
        r = s.getRect(all=True)
        heights.append(float(r.height()) * width / float(r.width()) if r.width() > 0 else float(r.height()))
    for a, b in runs:
        ars = [_aspect(s) for s in shapes[a:b]]
        for k in range(0, len(ars), columns):
            row = ars[k:k + columns]
            heights.append(max(width - space * (len(row) - 1), 1.0) / sum(row))
    return sum(heights) + space * max(len(heights) - 1, 0)


def _make_rows(window, runs, columns, width, space):
    from batoolset.drawings.shapes.group import Group
    panel = window.paint.EZFIG_panel
    shapes = panel.shapes_to_draw
    for a, b in reversed(runs):
        imgs = shapes[a:b]
        rows = [Group(*imgs[k:k + columns], orientation='X', space=space, size=width)
                for k in range(0, len(imgs), columns)]
        shapes[a:b] = rows
        for row in rows:
            window.update_size_of_object(row, width)


def _set_width(window, width):
    from batoolset.drawings.shapes.group import Group
    for s in window.paint.EZFIG_panel.shapes_to_draw:
        if getattr(s, 'isText', False):
            continue
        if isinstance(s, Group):
            s.size = width               # the width repack_all lays the row out at
        window.update_size_of_object(s, width)
    _show_width(window, width)


def _show_width(window, width):
    spin = window.size_spinbox
    spin.blockSignals(True)          # the figure width shown, without a second resize
    try:
        spin.setValue(int(round(width)))
    finally:
        spin.blockSignals(False)
    try:
        window.update_size_in_unit()
    except Exception:
        pass


def fit_to_page(window, force=False):
    """Fit the figure of *window* to the page after an automatic layout.
    Returns a sentence saying what was done (for the status bar and the chat),
    or '' when nothing had to change."""
    if not (force or enabled()):
        return ''
    panel = window.paint.EZFIG_panel
    if getattr(window, 'fit_to_combo', None) is not None and 'idth' not in window.fit_to_combo.currentText():
        return ''                     # the figure is sized by height: the user's choice
    _relayout(window)                 # rows just added may not be stacked yet
    size = figure_size_pt(panel)
    name, (page_w, page_h) = page_mm()
    limit = page_h / MM_PER_PT
    # 1 % slack: the default width, 512 px = 180.6 mm, is the A4 page width
    max_width = page_w / MM_PER_PT * 1.01
    if size is None or (size[1] <= limit * 1.002 and size[0] <= max_width):
        return ''
    # the page bounds the width too: a figure reloaded after the chat added images
    # took the width of its widest image (2000 px = 705 mm, 2026-11-16)
    width = float(window.size_spinbox.value())
    if width > max_width:
        width = page_w / MM_PER_PT
    space = float(window.main_space_spinner.value()) if hasattr(window, 'main_space_spinner') else 3.0
    done = []
    shapes = panel.shapes_to_draw
    runs = _lone_runs(shapes)
    if runs:
        longest = max(b - a for a, b in runs)
        # at most 5 per row: a row of more is hard to read (the user, 2026-11-16);
        # still too tall with 5: narrowed below
        heights = {c: _height_with_columns(shapes, runs, c, width, space)
                   for c in range(1, min(longest, MAX_PER_ROW) + 1)}
        fitting = [c for c in sorted(heights) if heights[c] <= limit]
        # the fewest per row that fit; none fits: the shortest, then narrowed below
        columns = fitting[0] if fitting else min(heights, key=heights.get)
        if columns > 1:
            n = sum(b - a for a, b in runs)
            _make_rows(window, runs, columns, width, space)
            _relayout(window)
            done.append(f'put the {n} images lying one below the other in rows of {columns}')
    size = figure_size_pt(panel)
    if size is not None and size[0] > max_width:
        _set_width(window, width)
        _relayout(window)
        size = figure_size_pt(panel)
        done.append(f'set its width to the page width, {width * MM_PER_PT:.0f} mm')
    if size is not None and size[1] > limit * 1.002:
        first = width
        estimate = width * limit / size[1]
        if estimate * MM_PER_PT < MIN_WIDTH_MM:
            done.append(f'it is still {size[1] * MM_PER_PT:.0f} mm tall: to fit it would have to be '
                        f'about {estimate * MM_PER_PT:.0f} mm wide, too small to read — put more panels '
                        f'side by side or split it into several figures')
        else:
            best = (size[1], width)
            for _ in range(4):                 # gaps and labels do not shrink: not quite linear
                width = max(width * limit / size[1] * 0.999, MIN_WIDTH_MM / MM_PER_PT)
                _set_width(window, width)
                _relayout(window)
                size = figure_size_pt(panel)
                if size is None or size[1] >= best[0]:      # narrower and no shorter: back
                    width = best[1]
                    _set_width(window, width)
                    _relayout(window)
                    size = figure_size_pt(panel)
                    break
                best = (size[1], width)
                if size[1] <= limit * 1.002:
                    break
            if width < first:
                done.append(f'narrowed it to {width * MM_PER_PT:.0f} mm wide, aspect kept')
    if not done:
        return ''
    _show_width(window, width)        # the next layout (arrange, add) starts from it
    height = (size[1] if size else 0) * MM_PER_PT
    return (f'Fitted to the {name} page ({page_w:g} × {page_h:g} mm): ' + '; '.join(done)
            + f' — now {height:.0f} mm tall. View → Fit new layouts to the page turns this off.')
