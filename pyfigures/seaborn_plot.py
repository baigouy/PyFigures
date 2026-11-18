"""Seaborn plot panels (user, 2026-11-18: "faceted plots as in R... seaborn is the real
replacement for R... make sure it can do any plot supported").

A panel stores a short script that reads the CSV and draws one seaborn plot, so it
re-renders when the CSV changes, like the data plots. The settings are kept as JSON in
the script's first line (``# pyfigures-seaborn: {...}``): describe_code_panel and
edit_seaborn_plot read them back, and the script is regenerated from them, never edited
by hand. Faceting, as ggplot2's facet_wrap / facet_grid: *col* / *row* (and *col_wrap*)
on the figure-level functions (relplot, displot, catplot, lmplot).
"""
from __future__ import annotations

import json

MARKER = '# pyfigures-seaborn: '

# figure-level functions draw their own figure and can facet (col / row)
FIGURE_LEVEL = {
    'relplot': 'relationships: scatter or line (kind="scatter"|"line"), facets by col / row',
    'displot': 'distributions: histogram, KDE or ECDF (kind="hist"|"kde"|"ecdf"), facets by col / row',
    'catplot': 'categories: strip, swarm, box, violin, boxen, point, bar or count (kind=...), facets by col / row',
    'lmplot': 'scatter with a regression line per group, facets by col / row',
    'pairplot': 'every numeric column against every other (hue colours groups)',
    'jointplot': 'two variables with their marginal distributions (kind="scatter"|"kde"|"hist"|"hex"|"reg")',
}
# axes-level functions draw one plot
AXES_LEVEL = {
    'scatterplot': 'x against y, points', 'lineplot': 'x against y, lines with a confidence band',
    'histplot': 'histogram', 'kdeplot': 'density curve', 'ecdfplot': 'cumulative distribution',
    'rugplot': 'tick per value', 'stripplot': 'points per category', 'swarmplot': 'non-overlapping points per category',
    'boxplot': 'box per category', 'violinplot': 'violin per category', 'boxenplot': 'letter-value box per category',
    'pointplot': 'means with confidence intervals per category', 'barplot': 'bars of means with confidence intervals',
    'countplot': 'counts per category', 'regplot': 'scatter with a regression line', 'residplot': 'regression residuals',
    'heatmap': 'a matrix of values (index=, columns=, values= pivot the table; else the numeric columns)',
    'clustermap': 'a clustered heatmap (same pivot options as heatmap)',
}
FUNCTIONS = {**FIGURE_LEVEL, **AXES_LEVEL}
CATEGORY_KINDS = ('strip', 'swarm', 'box', 'violin', 'boxen', 'point', 'bar', 'count')
# the mapping arguments a function takes from the table's columns
MAPPINGS = ('x', 'y', 'hue', 'col', 'row', 'style', 'size', 'units')


def describe_functions() -> str:
    return ('Seaborn plots (add_seaborn_plot; edit_seaborn_plot changes one; facets like ggplot2 with col= / row= '
            'on the figure-level ones):\n'
            + '\n'.join(f'- {k} (faceting): {v}' for k, v in FIGURE_LEVEL.items())
            + '\n' + '\n'.join(f'- {k}: {v}' for k, v in AXES_LEVEL.items()))


def table_file(path) -> str:
    """The file of a table path ("book.xlsx::Sheet2" -> "book.xlsx")."""
    try:
        from staplot.api import split_sheet
        return split_sheet(str(path))[0]
    except ImportError:
        return str(path)


def read_table(path):
    """The table the panel plots: CSV / TXT / TSV, or an Excel sheet (staplot)."""
    try:
        from staplot.api import read_table as staplot_read
    except ImportError:
        import pandas as pd
        return pd.read_csv(path, sep=None, engine='python', encoding='utf-8-sig')
    return staplot_read(path)


def make_script(spec: dict) -> str:
    """The panel's script for *spec* (function, csv, x/y/hue/col/row..., kind, col_wrap,
    options, palette, height, aspect, title, xlabel, ylabel, index/columns/values)."""
    head = MARKER + json.dumps(spec, ensure_ascii=False, sort_keys=True)
    # no comprehension, no def: PyFigures runs panel scripts with separate globals and
    # locals, and a comprehension cannot see the script's own names (Python < 3.12)
    return head + '\n' + f'''import pandas as _pd
import seaborn as _sns
import matplotlib.pyplot as _plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as _Agg
_spec = {spec!r}
try:
    from staplot.api import read_table as _read_table     # CSV, TXT, Excel (book.xlsx::Sheet)
    _df = _read_table(_spec['csv'])
except ImportError:
    _df = _pd.read_csv(_spec['csv'], sep=None, engine='python', encoding='utf-8-sig')
if _spec.get('where'):
    _df = _df.query(_spec['where'], engine='python')     # only these rows ("only day 14")
_kw = {{}}
for _k in {MAPPINGS!r}:
    if _spec.get(_k):
        _kw[_k] = _spec[_k]
_used = []
for _c in _kw.values():
    if _c in _df.columns:
        _used.append(_c)
_df = _df.dropna(subset=_used)
# colour-blind safe colours unless a palette is asked for (user, 2026-11-18)
_sns.set_theme(style=_spec.get('style_theme') or 'ticks', context='paper', palette=_spec.get('palette') or 'colorblind')
_fn = getattr(_sns, _spec['function'])
# points and lines of each hue also get their own shape: told apart without colour
if _kw.get('hue') and not _kw.get('style') and (_spec['function'] in ('scatterplot', 'lineplot') or (_spec['function'] == 'relplot')):
    _kw['style'] = _kw['hue']
    if _spec['function'] == 'lineplot' or (_spec['function'] == 'relplot' and _spec.get('kind') == 'line'):
        _kw['markers'] = True
        _kw['dashes'] = False
_kw.update(_spec.get('options') or {{}})
if _spec['function'] in ('heatmap', 'clustermap'):
    _kw = dict(_spec.get('options') or {{}})
    if _spec.get('index') and _spec.get('columns') and _spec.get('values'):
        _m = _df.pivot_table(index=_spec['index'], columns=_spec['columns'], values=_spec['values'])
    else:
        _m = _df.select_dtypes('number')
    _out = _fn(_m, **_kw) if _spec['function'] == 'clustermap' else None
    if _out is None:
        fig, _ax = _plt.subplots(figsize=(_spec.get('height', 3) * _spec.get('aspect', 1.3), _spec.get('height', 3)))
        _fn(_m, ax=_ax, **_kw)
    else:
        fig = _out.figure
elif _spec['function'] in {tuple(FIGURE_LEVEL)!r}:
    if _spec.get('kind'):
        _kw['kind'] = _spec['kind']
    if _spec.get('col_wrap') and _spec.get('col'):
        _kw['col_wrap'] = _spec['col_wrap']
    if _spec['function'] in ('pairplot', 'jointplot'):
        for _k in ('col', 'row', 'col_wrap', 'style', 'size', 'units'):
            _kw.pop(_k, None)
        if _spec['function'] == 'pairplot':
            _kw.pop('x', None)
            _kw.pop('y', None)
        _kw['height'] = _spec.get('height', 2.0 if _spec['function'] == 'pairplot' else 3.0)
    else:
        _kw['height'] = _spec.get('height', 2.5)
        _kw['aspect'] = _spec.get('aspect', 1.2)
    _grid = _fn(data=_df, **_kw)
    fig = _grid.figure
    if _spec.get('title'):
        fig.suptitle(_spec['title'])
    if _spec.get('xlabel') or _spec.get('ylabel'):
        if hasattr(_grid, 'set_axis_labels'):
            _grid.set_axis_labels(_spec.get('xlabel') or None, _spec.get('ylabel') or None)
else:
    fig, _ax = _plt.subplots(figsize=(_spec.get('height', 2.5) * _spec.get('aspect', 1.3), _spec.get('height', 2.5)))
    _fn(data=_df, ax=_ax, **_kw)
    if _spec.get('title'):
        _ax.set_title(_spec['title'])
    if _spec.get('xlabel'):
        _ax.set_xlabel(_spec['xlabel'])
    if _spec.get('ylabel'):
        _ax.set_ylabel(_spec['ylabel'])
_sns.despine(fig=fig)
if _spec['function'] in {tuple(FIGURE_LEVEL)!r} and _spec['function'] not in ('heatmap', 'clustermap') and hasattr(_grid, 'tight_layout'):
    _grid.tight_layout()             # keeps room for the grid's legend (fig.tight_layout put a facet under it)
else:
    fig.tight_layout()
_Agg(fig)
_plt.close(fig)
self.img = fig
'''


def parse(script: str) -> dict | None:
    if not isinstance(script, str) or not script.startswith(MARKER):
        return None
    try:
        return json.loads(script.splitlines()[0][len(MARKER):])
    except ValueError:
        return None


def check(spec: dict) -> str | None:
    """Why *spec* cannot be drawn (unknown function, missing column...), or None."""
    import os
    function = spec.get('function')
    if function not in FUNCTIONS:
        return f'unknown seaborn function {function!r}; one of: {", ".join(FUNCTIONS)}'
    if not os.path.isfile(table_file(spec.get('csv'))):
        return f'no such table file: {spec.get("csv")}'
    if spec.get('kind') and function == 'catplot' and spec['kind'] not in CATEGORY_KINDS:
        return f'catplot kind must be one of {CATEGORY_KINDS}'
    try:
        df = read_table(spec['csv'])
        columns = list(df.columns)
    except Exception as e:
        return f'could not read the table ({type(e).__name__}: {e})'
    if spec.get('where'):
        try:
            if df.query(str(spec['where']), engine='python').empty:
                return f'no row where {spec["where"]}'
        except Exception as e:
            return f'cannot keep the rows where {spec["where"]!r} ({type(e).__name__}: {e}); its columns are {columns}'
    wanted = [spec[k] for k in MAPPINGS + ('index', 'columns', 'values') if spec.get(k)]
    missing = [c for c in wanted if c not in columns]
    if missing:
        return f'no column {missing} in the CSV; its columns are {columns}'
    if (spec.get('col') or spec.get('row')) and function not in ('relplot', 'displot', 'catplot', 'lmplot'):
        return (f'{function} cannot facet: col / row facets need relplot, displot, catplot or lmplot '
                f'(e.g. catplot(kind="box") for box plots per facet)')
    return None


def dropped_rows(spec: dict) -> str | None:
    """How many rows the plot leaves out (a missing value in a column it uses)."""
    try:
        df = read_table(spec['csv'])
        if spec.get('where'):
            df = df.query(str(spec['where']), engine='python')
        used =[spec[k] for k in MAPPINGS if spec.get(k) and spec[k] in df.columns]
        if not used:
            return None
        n = int(df[used].isna().any(axis=1).sum())
        return (f'{n} of {len(df)} row(s) left out (a missing value in {", ".join(used)}); never filled in'
                if n else f'all {len(df)} rows used')
    except Exception:
        return None
