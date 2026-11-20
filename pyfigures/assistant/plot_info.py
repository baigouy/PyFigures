"""What a code panel is, for the model (user, 2026-11-18: "the model should see both code
and image together, they are complementary; with no vision it should see the code").

A data plot (add_data_plot: a CSV drawn by staplot) was only "a code panel" to the model:
it could not find the p-values, said a box plot with brackets had "no comparisons", and
hand-edited the generated script into an error. Now a data plot is described by its
settings (CSV, kind, groups, error bars, which brackets) and its statistics, computed from
the CSV with the same settings as the drawing; any other script panel by its code.
"""
from __future__ import annotations

import ast
import os

# the data-plot kinds (mcp_tools.content._DATA_PLOT_KINDS), with what each is for
PLOT_KINDS = {
    'bar': 'group means with error bars (sem, sd or ci95); group comparisons',
    'box': 'median, quartiles and whiskers per group; group comparisons',
    'violin': 'the shape of each group\'s distribution; group comparisons',
    'scatter': 'one numeric column against another, with a regression line and correlation test',
    'grouped': 'bars by two factors (e.g. genotype x treatment); two-way ANOVA (needs a two-factor CSV)',
    'line': 'a time course / dose response: mean ± error of each group across x (day, dose, time); '
            'two-way ANOVA (a table: group, x, value)',
    'paired': 'repeated measures (before / after on the same subjects): a line per subject; paired '
              't-test / Wilcoxon, repeated-measures ANOVA / Friedman',
    'split_violin': 'two conditions (e.g. sex) as the two halves of each violin, a legend naming them; '
                    'each pair tested, two-way ANOVA (needs a two-factor table with a two-level factor)',
}
_LAYOUT_KEYS = ('aspect', 'width', 'height', 'font_scale', 'order', 'ylim', 'log_y', 'xtick_rotation', 'legend',
                'rename', 'violin_inner', 'violin_side', 'element_colors', 'show_n', 'show_mean', 'p_format',
                'hlines', 'control', 'point_style', 'normalize', 'pairs', 'stats_text')
SCRIPT_CHARS = 2500           # the code shown for a script panel (the rest: get_script)
_STATS_CACHE: dict = {}        # (csv, mtime, size, kind, only_significant, stats_mode) -> record


def panel_script(panel) -> str:
    script = getattr(panel, 'custom_loading_script', None)
    return script if isinstance(script, str) and script.strip() not in ('', 'None') else ''


def _table_file(path):
    """The file of a table path: "book.xlsx::counts" -> "book.xlsx" (os.stat of the
    whole string failed, and Excel plots lost their description and statistics)."""
    from ..plot_tables import split_sheet
    return split_sheet(path)[0] if isinstance(path, str) else path


def _sel(spec: dict) -> dict:
    """How the plot reads its table: columns, where, skip_rows (those set)."""
    return {k: spec[k] for k in ('columns', 'where', 'skip_rows')
            if spec.get(k) is not None and spec.get(k) not in ('', [])}


def parse_data_plot(script: str) -> dict | None:
    """The settings of a data-plot script (mcp_tools.content._make_data_plot_script),
    else None."""
    if not script or ('_api.plot(' not in script and '_api.plot_facets(' not in script):
        return None
    try:
        tree = ast.parse(script)
    except SyntaxError:
        return None
    spec: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_csv' for t in node.targets):
            try:
                spec['csv'] = ast.literal_eval(node.value)
            except ValueError:
                pass
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ('table_from_csv', 'grouped_table_from_csv'):
                spec['grouped_table'] = node.func.attr == 'grouped_table_from_csv'
                for kw in node.keywords:
                    if kw.arg in ('columns', 'where', 'skip_rows'):
                        try:
                            spec[kw.arg] = ast.literal_eval(kw.value)
                        except ValueError:
                            pass
            elif node.func.attr in ('plot', 'plot_facets'):
                for kw in node.keywords:
                    try:
                        spec[{'ncols': 'facet_ncols'}.get(kw.arg, kw.arg)] = ast.literal_eval(kw.value)
                    except ValueError:
                        pass
        elif isinstance(node, ast.If) and isinstance(node.test, ast.Constant) and 'latex' not in spec:
            spec['latex'] = bool(node.test.value)
    if 'csv' not in spec or 'kind' not in spec:
        return None
    return {'csv': spec['csv'], 'kind': spec['kind'], 'error': spec.get('error', 'sem'),
            'annotate_stats': bool(spec.get('annotate', True)),
            'only_significant': bool(spec.get('only_significant', False)),
            'stats_mode': spec.get('stats_mode', 'auto'), 'colors': spec.get('colors'),
            'title': spec.get('title', ''), 'ylabel': spec.get('ylabel', ''), 'xlabel': spec.get('xlabel', ''),
            'latex': bool(spec.get('latex', False)),
            # layout and size (mcp_tools.content.PLOT_LAYOUT_KEYS): None = staplot's default
            **{k: spec.get(k) for k in _LAYOUT_KEYS},
            # False: that axis has no label at all
            'show_ylabel': spec.get('show_ylabel', True), 'show_xlabel': spec.get('show_xlabel', True),
            'show_points': spec.get('show_points', True),
            # the columns of a wider table the plot uses (None: the whole table)
            'columns': spec.get('columns'),
            # the rows it uses (a pandas query; None: every row)
            'where': spec.get('where'),
            # lines skipped above the table by hand (None: found automatically)
            'skip_rows': spec.get('skip_rows'),
            # facets: one plot per value of a column (staplot.api.plot_facets)
            'facet': spec.get('facet'), 'facet_row': spec.get('facet_row'),
            'facet_ncols': spec.get('facet_ncols')}


def data_plot_code(spec: dict) -> str | None:
    """The full code of a data plot (staplot.api.plot_code): part 1 redraws it with
    staplot, part 2 reads the table with pandas and runs the test with scipy alone."""
    try:
        from staplot import api
        maker = getattr(api, 'plot_code', None)
        if maker is None:
            return None
        return maker(spec['csv'], spec['kind'], error=spec.get('error', 'sd'),
                     annotate=bool(spec.get('annotate_stats', True)),
                     only_significant=bool(spec.get('only_significant', True)),
                     stats_mode=spec.get('stats_mode', 'auto'), title=spec.get('title', ''),
                     ylabel=spec.get('ylabel', ''), xlabel=spec.get('xlabel', ''),
                     colors=spec.get('colors'), show_title=bool(spec.get('title')),
                     **{k: spec[k] for k in _LAYOUT_KEYS if spec.get(k) not in (None, False, [], '')},
                     **{k: False for k in ('show_ylabel', 'show_xlabel', 'show_points') if spec.get(k) is False},
                     **_sel(spec),
                     **{k: spec[k] for k in ('facet', 'facet_row') if spec.get(k)},
                     **({'ncols': spec['facet_ncols']} if spec.get('facet_ncols') else {}))
    except Exception:
        return None


def staplot_call(spec: dict) -> str | None:
    """Part 1 of data_plot_code: the lines that draw the plot (short, for the chat)."""
    code = data_plot_code(spec)
    if not code:
        return None
    lines = code.splitlines()
    keep = [ln for ln in lines if ln.startswith(('table = api.', 'fig, stats_record = api.plot('))]
    return '\n'.join(['from staplot import api'] + keep) if keep else None


def plot_statistics(spec: dict) -> dict | None:
    """The test the plot draws, recomputed from its CSV with its settings (cached until
    the CSV changes): test, omnibus, each comparison with its p-value and stars."""
    csv = spec.get('csv')
    try:
        st = os.stat(_table_file(csv))
    except (OSError, TypeError):
        return {'error': f'table not found: {csv}'}
    cols = spec.get('columns') or None
    ckw = _sel(spec)
    key = (csv, st.st_mtime_ns, st.st_size, spec['kind'], spec['only_significant'], spec['stats_mode'],
           tuple(cols or ()), spec.get('where'), spec.get('skip_rows'), spec.get('facet'), spec.get('facet_row'), spec.get('control'))
    if key in _STATS_CACHE:
        return _STATS_CACHE[key]
    try:
        from staplot import api
        mode = {'auto': None, 'parametric': True, 'nonparametric': False}.get(spec['stats_mode'])
        if spec.get('facet') and hasattr(api, 'facet_stats'):
            recs = api.facet_stats(csv, spec['kind'], spec['facet'], spec.get('facet_row'),
                                   only_significant=spec['only_significant'], stats_mode=spec['stats_mode'], **ckw,
                                   **({'control': spec['control']} if spec.get('control') else {}))
            out = {'facets': {k: {f: r.get(f) for f in ('test', 'omnibus', 'effects', 'split_comparisons', 'r',
                                                       'p', 'error') if f in r}
                              | {'comparisons': [{c: x.get(c) for c in ('a', 'b', 'p', 'p_text', 'stars')}
                                                 for x in r.get('comparisons') or []]}
                              for k, r in recs.items()}}
        elif spec['kind'] == 'paired' and hasattr(api, 'paired_test'):
            rec = api.paired_test(api.table_from_csv(csv, **ckw), only_significant=spec['only_significant'],
                                  parametric=mode)
            out = {k: rec.get(k) for k in ('test', 'omnibus', 'normality', 'n_subjects', 'error')}
            out['comparisons'] = [{k: c.get(k) for k in ('a', 'b', 'p', 'p_text', 'stars')}
                                  for c in rec.get('comparisons') or []]
        elif spec['kind'] in ('bar', 'box', 'violin'):
            table = api.table_from_csv(csv, **ckw)
            rec = api.auto_test(table, only_significant=spec['only_significant'], parametric=mode,
                                **({'control': spec['control']} if spec.get('control') else {}))
            out = {'test': rec.get('test'), 'omnibus': rec.get('omnibus'), 'correction': rec.get('correction'),
                   'normality': rec.get('normality'),
                   'comparisons': [{k: c.get(k) for k in ('a', 'b', 'p', 'p_text', 'stars')}
                                   for c in rec.get('comparisons') or []],
                   # the pairs drawn as brackets (all tested pairs, or only the significant ones)
                   'bracketed_pairs': [[p[0], p[1]] for p in rec.get('sig_pairs') or []]}
            if rec.get('warnings'):
                out['warnings'] = rec['warnings']
        elif spec['kind'] == 'scatter':
            rec = api.correlation_test(api.table_from_csv(csv, **ckw))
            out = {k: rec.get(k) for k in ('test', 'r', 'r2', 'p', 'n', 'x', 'y')}
        elif spec['kind'] in ('grouped', 'split_violin', 'line'):
            gt = api.grouped_table_from_csv(csv, **ckw)
            rec = api.two_way_test(gt)
            out = {'test': rec.get('test'), 'effects': rec.get('effects')}
            if spec['kind'] == 'split_violin' and hasattr(api, 'split_pair_tests'):
                out['split_comparisons'] = api.split_pair_tests(*api.split_parts(gt))
            elif hasattr(api, 'within_x_tests'):
                out['within_x'] = [{k: r.get(k) for k in ('x', 'test', 'omnibus', 'sig_pairs')}
                                   for r in api.within_x_tests(gt)]
        else:
            out = None
    except Exception as e:                      # soft dependency, odd CSVs: say so, never fail the description
        out = {'error': f'{type(e).__name__}: {e}'[:300]}
    if len(_STATS_CACHE) > 64:
        _STATS_CACHE.clear()
    _STATS_CACHE[key] = out
    return out


def _groups(spec: dict) -> dict | None:
    """{group: n} from the CSV (the plot's own reader), for "I have 3 groups"."""
    try:
        from staplot import api
        if spec.get('grouped_table') or spec['kind'] == 'scatter' or spec.get('facet'):
            return None
        groups = api.table_from_csv(spec['csv'], **_sel(spec)).group_arrays()
        if isinstance(groups, dict):
            return {str(k): int(sum(1 for v in vals if v == v)) for k, vals in groups.items()}
    except Exception:
        pass
    return None


def data_cleaning(spec: dict) -> str | None:
    """staplot's account of the CSV's left-out cells (staplot >= 0.1.1), cached with the
    statistics; None with an older staplot or for a grouped (two-factor) table."""
    if spec.get('grouped_table') or spec.get('kind') in ('grouped', 'split_violin', 'line'):
        return None
    csv = spec.get('csv')
    try:
        st = os.stat(_table_file(csv))
    except (OSError, TypeError):
        return None
    cols = spec.get('columns') or None
    sel = _sel(spec)
    key = ('cleaning', csv, st.st_mtime_ns, st.st_size, tuple(cols or ()), spec.get('where'),
           spec.get('skip_rows'))
    if key not in _STATS_CACHE:
        try:
            from staplot import api
            report = getattr(api, 'csv_cleaning_report', None)
            _STATS_CACHE[key] = report(csv, **sel)['summary'] if report else None
        except Exception:
            _STATS_CACHE[key] = None
    return _STATS_CACHE[key]


def _plot_text_sizes(panel) -> dict | None:
    """{'pt': whole plot's size on the page, 'font', 'parts': {part: {pt, font}}} of a
    plot panel (a live Image2D); None when it cannot be told."""
    try:
        if not getattr(panel, 'publication_font_on_page', False):
            return None
        out = {'pt': float(panel._page_font_pt()) if hasattr(panel, '_page_font_pt')
               else float(getattr(panel, 'publication_font_size', 0))}
        family = panel._publication_family() if hasattr(panel, '_publication_family') else None
        if family:
            out['font'] = family
        from batoolset.drawings.shapes.image2d import parse_text_parts
        parts = parse_text_parts(getattr(panel, 'publication_text_parts', None))
        if parts:
            out['parts'] = parts
        return out
    except Exception:
        return None


def describe_code_panel(panel, statistics: bool = True) -> dict:
    """The part of panel_references that says what a code panel draws."""
    script = panel_script(panel)
    from ..seaborn_plot import parse as parse_seaborn, dropped_rows
    seaborn = parse_seaborn(script)
    if seaborn:
        out = {'type': 'seaborn_plot', **seaborn}
        rows = dropped_rows(seaborn)
        if rows:
            out['data_cleaning'] = rows
        out['change_it_with'] = ('edit_seaborn_plot (function, kind, x/y/hue, facets col/row/col_wrap, palette, '
                                 'labels, options) — never set_script on a seaborn plot')
        return out
    from ..table_panel import parse as parse_table
    table = parse_table(script)
    if table:
        return {'type': 'table_panel', **table,
                'change_it_with': ('edit_table_panel (columns, where, by / value / stats for a summary, decimals, '
                                   'title, rename) — never set_script on a table panel')}
    spec = parse_data_plot(script)
    if spec:
        out = {'type': 'data_plot', **{k: v for k, v in spec.items() if v not in (None, '', False) or
                                       k in ('annotate_stats', 'only_significant') or
                                       (k in ('show_ylabel', 'show_xlabel', 'show_points') and v is False)}}
        groups = _groups(spec)
        if groups:
            out['groups_n'] = groups
        cleaning = data_cleaning(spec)
        if cleaning:
            # what was left out of the CSV (empty / NA / text cells, rows without a group):
            # "what did you do with the missing values?" (user, 2026-11-18)
            out['data_cleaning'] = cleaning
        if statistics and spec['annotate_stats'] or spec['kind'] == 'scatter':
            out['statistics'] = plot_statistics(spec)
        out['kinds_available'] = list(PLOT_KINDS)
        # its text as drawn: "make the title bigger" needs the size it has now
        text = _plot_text_sizes(panel)
        if text:
            out['text'] = text
        # the staplot call that draws it: every setting at a glance, in the words the
        # parameters have (user: "that could also be sent to the model and help it
        # modify the parameters"); the whole script (with the test redone in scipy)
        # comes from data_plot_code
        call = staplot_call(spec)
        if call:
            out['code'] = call
            out['full_code_with'] = 'data_plot_code'
        out['change_it_with'] = ('edit_data_plot (kind, error bars, only_significant, stats on/off, stats_mode, '
                                 'labels, colours, csv_path, sheet; text size font_pt, font font_family (whole plot), '
                                 'text_pt / text_font {title, axis_labels, ticks, legend} (one part); layout and size: aspect, width, height, '
                                 'order, rename (group names shown), show_points, violin_inner, violin_side (half violins), ylim (its "scale" / "range": a plot has no scale bar), '
                                 'log_y, xtick_rotation (anticlockwise: left = +), legend) — never set_script on a data plot')
        return out
    if not script:
        return {'type': 'figure', 'note': 'drawn by a matplotlib figure without a stored script'}
    out = {'type': 'script', 'lines': script.count('\n') + 1, 'code': script[:SCRIPT_CHARS]}
    if len(script) > SCRIPT_CHARS:
        out['code_truncated'] = True
        out['full_code_with'] = 'get_script'
    return out


def preview_text(panel) -> str:
    """Appended to a preview of a code panel: the picture and what makes it, together."""
    info = describe_code_panel(panel)
    if info.get('type') == 'seaborn_plot':
        mapping = ', '.join(f"{k}={info[k]}" for k in ('x', 'y', 'hue', 'col', 'row', 'col_wrap', 'kind') if info.get(k))
        return (f"This panel is a SEABORN {info['function']} of {os.path.basename(info['csv'])} ({mapping})."
                + (f"\nData: {info['data_cleaning']}." if info.get('data_cleaning') else '')
                + '\nChange it with edit_seaborn_plot, not set_script.')
    if info.get('type') == 'data_plot':
        lines = [f"This panel is a DATA PLOT ({info['kind']}) of {os.path.basename(info['csv'])}"
                 f" (error bars: {info.get('error')}; brackets: "
                 f"{'only significant pairs' if info.get('only_significant') else 'all tested pairs'}"
                 f"{'' if info.get('annotate_stats') else ' — statistics off'})."]
        if info.get('data_cleaning'):
            lines.append('Data: ' + info['data_cleaning'])
        stats = info.get('statistics') or {}
        if stats.get('test'):
            lines.append('Test: ' + str(stats['test']))
        for c in stats.get('comparisons') or []:
            lines.append(f"  {c.get('a')} vs {c.get('b')}: {c.get('p_text') or c.get('p')} ({c.get('stars')})")
        lines.append('Change it with edit_data_plot, not set_script.')
        return '\n'.join(lines)
    if info.get('type') == 'script':
        return ('This panel is drawn by this Python script (the picture above is its output):\n'
                + info['code'] + ('\n… (truncated; get_script gives the rest)' if info.get('code_truncated') else ''))
    return ''
