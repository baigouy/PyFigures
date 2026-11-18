"""Table panels (user, 2026-11-18: "plots and tables become really easy to do"): a data
table, or a summary of it (n, mean ± SD... per group), drawn as a figure panel.

Like a seaborn plot panel, the panel stores a short script that reads the table and
draws it, so it re-renders when the table changes; its settings are kept as JSON in the
script's first line (``# pyfigures-table: {...}``), read back by edit_table_panel and by
the consolidation (the table file is copied with the figure).
"""
from __future__ import annotations

import json

MARKER = '# pyfigures-table: '
STATS = ('n', 'mean', 'sd', 'sem', 'median', 'min', 'max', 'mean±sd', 'mean±sem', 'median [iqr]')
MAX_ROWS = 60


def make_script(spec: dict) -> str:
    """The panel's script for *spec*: csv (a table path), columns, where, skip_rows; a
    summary: by (columns to group by), value (the numbers), stats; decimals, max_rows,
    title, rename."""
    head = MARKER + json.dumps(spec, ensure_ascii=False, sort_keys=True)
    # no comprehension, no def: PyFigures runs panel scripts with separate globals and
    # locals, and a comprehension cannot see the script's own names (Python < 3.12)
    return head + '\n' + f'''import numpy as _np
import pandas as _pd
import matplotlib.pyplot as _plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as _Agg
from pyfigures.table_panel import table_cells as _cells, cell_widths as _cell_widths
_spec = {spec!r}
_header, _rows, _note = _cells(_spec)
# drawn as text and rules (booktabs: a rule above, under the header and below; no vertical
# lines), so the text takes the figure's size like any plot text
_widths = _np.array(_cell_widths(_header, _rows), float)
_n = len(_rows) + 1
_fig_w = max(1.5, min(9.0, 0.075 * _widths.sum() + 0.3))
_fig_h = max(0.6, 0.2 * _n + (0.3 if _spec.get('title') else 0.08) + (0.2 if _note else 0))
fig, _ax = _plt.subplots(figsize=(_fig_w, _fig_h))
_ax.axis('off')
_ax.set_xlim(0, 1)
_ax.set_ylim(_n, 0)
_edges = _np.concatenate([[0.0], _np.cumsum(_widths) / _widths.sum()])
for _c, _h in enumerate(_header):
    _ax.text((_edges[_c] + _edges[_c + 1]) / 2, 0.5, _h, ha='center', va='center', fontsize=8,
             fontweight='bold')
for _r, _row in enumerate(_rows):
    for _c, _v in enumerate(_row):
        _ax.text((_edges[_c] + _edges[_c + 1]) / 2, _r + 1.5, _v, ha='center', va='center', fontsize=8)
for _y, _lw in ((0.0, 1.0), (1.0, 0.6), (_n, 1.0)):
    _ax.plot([0, 1], [_y, _y], color='#222222', linewidth=_lw, clip_on=False)
if not _rows:
    _ax.text(0.5, 1.5, 'no rows', ha='center', va='center', fontsize=8)
if _spec.get('title'):
    _ax.set_title(_spec['title'], fontsize=9)
if _note:
    fig.text(0.5, 0.01, _note, ha='center', va='bottom', fontsize=6, color='#666666')
fig.tight_layout()
_Agg(fig)
_plt.close(fig)
fig._pyfigures_no_relayout = True
self.img = fig
'''


def read_table(spec: dict):
    """The rows of the table the panel shows (before a summary)."""
    try:
        from staplot.api import read_table as staplot_read, select_columns
    except ImportError:
        import pandas as pd
        df = pd.read_csv(spec['csv'], sep=None, engine='python', encoding='utf-8-sig',
                         skiprows=int(spec.get('skip_rows') or 0))
        if spec.get('where'):
            df = df.query(spec['where'], engine='python')
        return df[spec['columns']] if spec.get('columns') else df
    df = staplot_read(spec['csv'], spec.get('skip_rows'))
    return select_columns(df, None, spec.get('where'))


def cell_widths(header, rows) -> list[float]:
    """Each column's width, in characters (its longest text, plus a margin)."""
    widths = []
    for c, h in enumerate(header):
        longest = max([len(str(h))] + [len(str(r[c])) for r in rows if c < len(r)])
        widths.append(longest + 2.5)
    return widths or [10.0]


def _fmt(v, decimals, trim=False):
    """A cell's text: *decimals* digits; *trim* (the raw rows) drops trailing zeros, so a
    table's 56.9 stays 56.9 and 12.0 shows 12."""
    import numpy as np
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ''
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        text = f'{float(v):.{decimals}f}'
        if trim and '.' in text:
            text = text.rstrip('0').rstrip('.')
        return text
    return str(v)


def table_cells(spec: dict) -> tuple[list, list, str]:
    """(header, rows of text, a note) of the panel: the table's rows (some columns, some
    rows), or a summary per group."""
    import numpy as np
    import pandas as pd
    decimals = int(spec.get('decimals', 2))
    ren = spec.get('rename') or {}
    df = read_table(spec)
    low = {str(c).strip().lower(): c for c in df.columns}
    by = spec.get('by') or []
    by = [low.get(str(b).strip().lower(), b) for b in ([by] if isinstance(by, str) else list(by))]
    if by or spec.get('stats'):
        value = spec.get('value')
        values = [low.get(str(v).strip().lower(), v) for v in ([value] if isinstance(value, str) else list(value or []))]
        if not values:
            values = [str(c) for c in df.columns if str(c) not in by
                      and pd.to_numeric(df[c], errors='coerce').notna().sum() >= max(1, df[c].notna().sum() * 0.8)]
        stats = spec.get('stats') or ['n', 'mean±sd']
        header = [str(ren.get(b, b)) for b in by]
        multi = len(values) > 1
        for v in values:
            for st in stats:
                header.append((f'{ren.get(v, v)} ' if multi else '') + st.replace('±', ' ± '))
        groups = df.groupby(by, sort=False, dropna=False) if by else [((), df)]
        rows = []
        for key, sub in groups:
            key = key if isinstance(key, tuple) else (key,)
            row = [str(ren.get(str(k), k)) for k in key]
            for v in values:
                x = pd.to_numeric(sub[v], errors='coerce').dropna().to_numpy(float)
                n = len(x)
                mean = x.mean() if n else np.nan
                sd = x.std(ddof=1) if n > 1 else np.nan
                sem = sd / np.sqrt(n) if n > 1 else np.nan
                q1, med, q3 = (np.percentile(x, [25, 50, 75]) if n else (np.nan,) * 3)
                cell = {'n': str(n), 'mean': _fmt(mean, decimals), 'sd': _fmt(sd, decimals),
                        'sem': _fmt(sem, decimals), 'median': _fmt(med, decimals),
                        'min': _fmt(x.min() if n else np.nan, decimals), 'max': _fmt(x.max() if n else np.nan, decimals),
                        'mean±sd': f'{_fmt(mean, decimals)} ± {_fmt(sd, decimals)}' if n > 1 else _fmt(mean, decimals),
                        'mean±sem': f'{_fmt(mean, decimals)} ± {_fmt(sem, decimals)}' if n > 1 else _fmt(mean, decimals),
                        'median [iqr]': f'{_fmt(med, decimals)} [{_fmt(q1, decimals)}-{_fmt(q3, decimals)}]' if n else ''}
                row += [cell[st] for st in stats]
            rows.append(row)
        return header, rows, ''
    if spec.get('columns'):
        low = {str(c).lower(): c for c in df.columns}
        df = df[[low[str(c).lower()] for c in spec['columns'] if str(c).lower() in low]]
    max_rows = int(spec.get('max_rows') or MAX_ROWS)
    note = f'{len(df) - max_rows} more row(s) not shown' if len(df) > max_rows else ''
    df = df.head(max_rows)
    header = [str(ren.get(str(c), c)) for c in df.columns]
    rows = [[_fmt(ren.get(v, v) if isinstance(v, str) else v, int(spec.get('decimals', 4)), trim=True) for v in r]
            for r in df.itertuples(index=False)]
    return header, rows, note


def parse(script: str) -> dict | None:
    if not isinstance(script, str) or not script.startswith(MARKER):
        return None
    try:
        return json.loads(script.splitlines()[0][len(MARKER):])
    except ValueError:
        return None


def check(spec: dict) -> str | None:
    """Why *spec* cannot be drawn, or None."""
    import os
    try:
        from staplot.api import split_sheet
        file = split_sheet(str(spec.get('csv')))[0]
    except ImportError:
        file = str(spec.get('csv'))
    if not os.path.isfile(file):
        return f'no such table file: {spec.get("csv")}'
    bad = [s for s in spec.get('stats') or [] if s not in STATS]
    if bad:
        return f'unknown statistic {bad}; one of {", ".join(STATS)}'
    try:
        df = read_table(spec)
    except Exception as e:
        return f'could not read the table ({type(e).__name__}: {e})'
    low = {str(c).lower() for c in df.columns}
    by = spec.get('by') or []
    value = spec.get('value') or []
    wanted = ([by] if isinstance(by, str) else list(by)) + ([value] if isinstance(value, str) else list(value)) \
        + list(spec.get('columns') or [])
    missing = [c for c in wanted if str(c).lower() not in low]
    if missing:
        return f'no column {missing}; the columns are {", ".join(map(str, df.columns))}'
    try:
        table_cells(spec)
    except Exception as e:
        return f'could not summarise the table ({type(e).__name__}: {e})'
    return None
