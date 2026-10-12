"""Build a poster or photo album from a declarative recipe (YAML or JSON) —
the poster designer's counterpart of pyfigures.recipe for .pyf figures.

    output: trip/iceland.pyfalbum        # .pyfposter for one plain page
    page: A4                             # A4..A0, or {width_mm: 300, height_mm: 300}
    album: true                          # front cover + spreads + back cover
    render: trip/iceland.pdf             # optional: .pdf = every page; .png/.jpg/.tif/.svg = page 1
    web: trip/iceland.html               # optional: self-contained HTML photo book
    front_cover:
      background: cover.jpg
      text: [{html: "<b>Iceland 2026</b>", style: h1, x_mm: 20, y_mm: 30}]
    spreads:
      - images: [day1/*.jpg]             # files or glob patterns, in order
        arrange: grid                    # grid | scatter | fan | none
      - images: [{image: lagoon.jpg, frame: polaroid, caption: Blue Lagoon}, geyser.jpg]
        arrange: {layout: diptych}       # any list_poster_layouts() name
    back_cover:
      text: [{html: "<i>the end</i>", style: caption}]

Without ``album: true`` use ``pages:`` (a list of page specs, each with an
optional ``kind``: single / spread / cover_front / cover_back), or a single
page's keys at the top level for a one-page poster.

Every path is relative to the recipe file. Unknown keys, missing files,
unreadable images and empty globs are errors, reported before anything is
written, so a script never ships a half-built album.

    python -m pyfigures.poster.poster_headless build recipe.yaml
    build_poster_from_recipe("recipe.yaml")          (MCP)
    Poster designer: "Build from recipe…"            (GUI)
"""
from __future__ import annotations

import glob as _glob
import json
import os

PAGE_PRESETS = {
    'A4': (210.0, 297.0),
    'A3': (297.0, 420.0),
    'A2': (420.0, 594.0),
    'A1': (594.0, 841.0),
    'A0': (841.0, 1189.0),
}
_TOP_KEYS = {'output', 'page', 'album', 'render', 'render_dpi', 'web', 'pages', 'front_cover',
             'spreads', 'back_cover'}
_PAGE_KEYS = {'kind', 'background', 'images', 'arrange', 'text', 'width_mm', 'height_mm'}
_IMAGE_KEYS = {'image', 'frame', 'caption', 'x_mm', 'y_mm', 'width_mm', 'height_mm', 'theta'}
_TEXT_KEYS = {'html', 'style', 'x_mm', 'y_mm', 'theta', 'width_mm'}
_BG_KEYS = {'image', 'zoom', 'pan_x', 'pan_y'}
_ARRANGE_KINDS = ('grid', 'scatter', 'fan', 'none')
_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.pyf'}   # .pyf: flattened figure


class PosterRecipeError(ValueError):
    pass


def load_recipe(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    if path.lower().endswith('.json'):
        data = json.loads(text)
    else:
        import yaml
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise PosterRecipeError(f'{path}: a recipe must be a mapping of keys')
    return data


def _unknown(d, allowed, where):
    extra = sorted(set(d) - allowed)
    if extra:
        raise PosterRecipeError(f'{where}: unknown key(s) {", ".join(extra)}; allowed: {", ".join(sorted(allowed))}')


def _num(v, where, positive=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise PosterRecipeError(f'{where}: expected a number, got {v!r}')
    if positive and v <= 0:
        raise PosterRecipeError(f'{where}: must be positive')
    return float(v)


def _expand_images(entries, base, where):
    """Recipe image entries -> [(abs_path, options)], globs expanded and sorted."""
    if isinstance(entries, (str, dict)):
        entries = [entries]
    if not isinstance(entries, list):
        raise PosterRecipeError(f'{where}: images must be a list')
    out = []
    for i, e in enumerate(entries):
        w = f'{where}[{i}]'
        opts = {}
        if isinstance(e, dict):
            _unknown(e, _IMAGE_KEYS, w)
            if 'image' not in e:
                raise PosterRecipeError(f'{w}: needs an "image" key')
            opts = {k: v for k, v in e.items() if k != 'image'}
            e = e['image']
        if not isinstance(e, str):
            raise PosterRecipeError(f'{w}: expected a file name or pattern, got {e!r}')
        pattern = os.path.join(base, e)
        if any(ch in e for ch in '*?['):
            matches = sorted(p for p in _glob.glob(pattern, recursive=True)
                             if os.path.splitext(p)[1].lower() in _IMAGE_EXTS)
            if not matches:
                raise PosterRecipeError(f'{w}: no image matches {e!r}')
            out += [(os.path.normpath(m), dict(opts)) for m in matches]
        else:
            p = os.path.normpath(pattern)
            if not os.path.isfile(p):
                raise PosterRecipeError(f'{w}: no such file {e!r}')
            out.append((p, opts))
    for p, opts in out:
        if 'frame' in opts and opts['frame'] not in ('none', 'simple', 'polaroid'):
            raise PosterRecipeError(f'{where}: unknown frame {opts["frame"]!r} for {os.path.basename(p)}')
        for k in ('x_mm', 'y_mm', 'theta'):
            if k in opts:
                _num(opts[k], f'{where}: {k}')
        for k in ('width_mm', 'height_mm'):
            if k in opts:
                _num(opts[k], f'{where}: {k}', positive=True)
        if ('x_mm' in opts) != ('y_mm' in opts):
            raise PosterRecipeError(f'{where}: give both x_mm and y_mm for {os.path.basename(p)}')
    return out


def _plan_arrange(spec, where):
    if spec is None:
        return None
    if isinstance(spec, str):
        if spec not in _ARRANGE_KINDS:
            raise PosterRecipeError(f'{where}: arrange must be one of {_ARRANGE_KINDS} or {{layout: name}}')
        return (spec, None, {})
    if isinstance(spec, dict) and len(spec) == 1:
        (kind, params), = spec.items()
        if kind == 'layout':
            from pyfigures.poster.poster_templates import LAYOUTS
            if params not in LAYOUTS:
                raise PosterRecipeError(f'{where}: unknown layout {params!r}; use one of {sorted(LAYOUTS)}')
            return ('layout', params, {})
        if kind in ('grid', 'scatter', 'fan'):
            params = params or {}
            allowed = {'grid': {'columns', 'margin_mm', 'gap_mm'},
                       'scatter': {'seed', 'margin_mm', 'max_rotation_deg'},
                       'fan': {'start_angle_deg', 'end_angle_deg', 'face'}}[kind]
            if not isinstance(params, dict):
                raise PosterRecipeError(f'{where}: {kind} options must be a mapping')
            _unknown(params, allowed, f'{where}.{kind}')
            return (kind, None, dict(params))
    raise PosterRecipeError(f'{where}: arrange must be one of {_ARRANGE_KINDS}, '
                            f'{{grid: {{columns: 3}}}}-style options, or {{layout: name}}')


def _plan_page(spec, base, where, default_kind='single'):
    if spec is None:
        spec = {}
    if not isinstance(spec, dict):
        raise PosterRecipeError(f'{where}: a page must be a mapping')
    _unknown(spec, _PAGE_KEYS, where)
    kind = spec.get('kind', default_kind)
    from pyfigures.poster.poster_shapes import PAGE_KINDS, TEXT_STYLE_PRESETS
    if kind not in PAGE_KINDS:
        raise PosterRecipeError(f'{where}: unknown kind {kind!r}; use one of {PAGE_KINDS}')
    page = {'kind': kind, 'images': [], 'text': [], 'background': None, 'arrange': None,
            'width_mm': None, 'height_mm': None}
    for k in ('width_mm', 'height_mm'):
        if k in spec:
            page[k] = _num(spec[k], f'{where}.{k}', positive=True)
    bg = spec.get('background')
    if bg is not None:
        if isinstance(bg, str):
            bg = {'image': bg}
        if not isinstance(bg, dict) or 'image' not in bg:
            raise PosterRecipeError(f'{where}.background: a file name or {{image: ..., zoom: ...}}')
        _unknown(bg, _BG_KEYS, f'{where}.background')
        path = os.path.normpath(os.path.join(base, bg['image']))
        if not os.path.isfile(path):
            raise PosterRecipeError(f'{where}.background: no such file {bg["image"]!r}')
        page['background'] = {'path': path,
                              'zoom': _num(bg.get('zoom', 1.0), f'{where}.background.zoom', positive=True),
                              'pan_x': _num(bg.get('pan_x', 0.5), f'{where}.background.pan_x'),
                              'pan_y': _num(bg.get('pan_y', 0.5), f'{where}.background.pan_y')}
    if 'images' in spec:
        page['images'] = _expand_images(spec['images'], base, f'{where}.images')
    page['arrange'] = _plan_arrange(spec.get('arrange'), f'{where}.arrange')
    texts = spec.get('text', [])
    if isinstance(texts, (str, dict)):
        texts = [texts]
    for i, t in enumerate(texts):
        w = f'{where}.text[{i}]'
        if isinstance(t, str):
            t = {'html': t}
        if not isinstance(t, dict):
            raise PosterRecipeError(f'{w}: a string or a mapping')
        _unknown(t, _TEXT_KEYS, w)
        style = t.get('style', 'body')
        if style not in TEXT_STYLE_PRESETS:
            raise PosterRecipeError(f'{w}: unknown style {style!r}; use one of {sorted(TEXT_STYLE_PRESETS)}')
        if ('x_mm' in t) != ('y_mm' in t):
            raise PosterRecipeError(f'{w}: give both x_mm and y_mm')
        for k in ('x_mm', 'y_mm', 'theta'):
            if k in t:
                _num(t[k], f'{w}.{k}')
        if 'width_mm' in t:
            _num(t['width_mm'], f'{w}.width_mm', positive=True)
        page['text'].append(dict(t, style=style))
    return page


def plan_recipe(recipe, recipe_path):
    """Validate a recipe and resolve every path — no Qt, nothing written."""
    if not isinstance(recipe, dict):
        raise PosterRecipeError('a recipe must be a mapping of keys')
    base = os.path.dirname(os.path.abspath(recipe_path))
    album = recipe.get('album', False)
    if not isinstance(album, bool):
        raise PosterRecipeError('album: must be true or false')
    single_page_keys = _PAGE_KEYS & set(recipe)
    _unknown(recipe, _TOP_KEYS | (_PAGE_KEYS if not album and 'pages' not in recipe else set()), 'recipe')
    if 'output' not in recipe or not isinstance(recipe['output'], str):
        raise PosterRecipeError('recipe: "output" (the .pyfposter/.pyfalbum to write) is required')
    output = os.path.normpath(os.path.join(base, recipe['output']))
    ext = os.path.splitext(output)[1].lower()
    if ext not in ('.pyfposter', '.pyfalbum'):
        raise PosterRecipeError('output: must end in .pyfposter or .pyfalbum')

    page = recipe.get('page', 'A4')
    if isinstance(page, str):
        if page not in PAGE_PRESETS:
            raise PosterRecipeError(f'page: unknown preset {page!r}; use one of {sorted(PAGE_PRESETS)} '
                                    f'or {{width_mm: ..., height_mm: ...}}')
        size = PAGE_PRESETS[page]
    elif isinstance(page, dict):
        _unknown(page, {'width_mm', 'height_mm'}, 'page')
        size = (_num(page.get('width_mm'), 'page.width_mm', positive=True),
                _num(page.get('height_mm'), 'page.height_mm', positive=True))
    else:
        raise PosterRecipeError('page: a preset name (A4..A0) or {width_mm, height_mm}')

    if album:
        for k in ('pages',):
            if k in recipe:
                raise PosterRecipeError('album: true uses front_cover / spreads / back_cover, not pages')
        spreads = recipe.get('spreads') or []
        if not isinstance(spreads, list) or not spreads:
            raise PosterRecipeError('album: needs at least one entry under "spreads"')
        pages = [_plan_page(recipe.get('front_cover'), base, 'front_cover', 'cover_front')]
        pages += [_plan_page(s, base, f'spreads[{i}]', 'spread') for i, s in enumerate(spreads)]
        pages.append(_plan_page(recipe.get('back_cover'), base, 'back_cover', 'cover_back'))
        for p, required in zip(pages, ['cover_front'] + ['spread'] * len(spreads) + ['cover_back']):
            if p['kind'] != required:
                raise PosterRecipeError(f'album: page kinds are fixed (covers and spreads); got {p["kind"]!r}')
    else:
        for k in ('front_cover', 'spreads', 'back_cover'):
            if k in recipe:
                raise PosterRecipeError(f'{k}: only with album: true')
        if 'pages' in recipe:
            if single_page_keys:
                raise PosterRecipeError(f'recipe: put {", ".join(sorted(single_page_keys))} inside a page '
                                        f'when "pages" is used')
            if not isinstance(recipe['pages'], list) or not recipe['pages']:
                raise PosterRecipeError('pages: a non-empty list')
            pages = [_plan_page(p, base, f'pages[{i}]') for i, p in enumerate(recipe['pages'])]
        else:
            pages = [_plan_page({k: recipe[k] for k in single_page_keys}, base, 'recipe')]
    if ext == '.pyfposter' and (album or len(pages) > 1 or pages[0]['kind'] != 'single'):
        raise PosterRecipeError('output: a multi-page document or album must be saved as .pyfalbum')

    extras = {}
    for k in ('render', 'web'):
        if k in recipe:
            if not isinstance(recipe[k], str):
                raise PosterRecipeError(f'{k}: an output file name')
            extras[k] = os.path.normpath(os.path.join(base, recipe[k]))
    if 'render' in extras:
        from pyfigures.poster.poster_canvas import PosterCanvas
        r_ext = os.path.splitext(extras['render'])[1].lower().lstrip('.')
        if r_ext not in PosterCanvas.EXPORT_FILETYPES:
            raise PosterRecipeError(f'render: unsupported format {r_ext!r}')
    if 'web' in extras and not extras['web'].lower().endswith('.html'):
        raise PosterRecipeError('web: must end in .html')
    dpi = recipe.get('render_dpi', 300)
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not (1 <= dpi <= 2400):
        raise PosterRecipeError('render_dpi: an integer between 1 and 2400')
    return {'output': output, 'size': size, 'album': album, 'pages': pages, 'dpi': dpi, **extras}


def build_from_plan(plan, canvas=None):
    """Create the document described by *plan* (see plan_recipe) on a fresh or
    given PosterCanvas, save it, and write the optional render/web outputs.
    Needs a QApplication."""
    from pyfigures.poster.poster_canvas import PosterCanvas
    from pyfigures.poster.poster_shapes import PosterPage, PosterBackground
    w0, h0 = plan['size']
    # every file must load before the (possibly open, GUI) canvas is touched
    for p in plan['pages']:
        for path, _o in p['images']:
            if path.lower().endswith('.pyf'):
                continue                   # rendered while building (and checked there)
            try:
                PosterCanvas.check_image_readable(path)
            except (OSError, ValueError) as exc:
                raise PosterRecipeError(str(exc)) from exc
        if p['background']:
            try:
                PosterCanvas.check_image_readable(p['background']['path'])
            except (OSError, ValueError) as exc:
                raise PosterRecipeError(f'background: {exc}') from exc
    if canvas is None:
        canvas = PosterCanvas(page_width_mm=w0, page_height_mm=h0)
    canvas.new_document(w0, h0)
    with canvas._batch_edit():
        pages = []
        for spec in plan['pages']:
            width = spec['width_mm'] or (w0 * 2.0 if spec['kind'] == 'spread' else w0)
            pages.append(PosterPage(width, spec['height_mm'] or h0, kind=spec['kind']))
        canvas.pages = pages
        canvas.album_mode = plan['album']
        n_images = 0
        for i, spec in enumerate(plan['pages']):
            canvas.current_page_index = i
            if spec['background']:
                bg = spec['background']
                canvas.background = PosterBackground(bg['path'], zoom=bg['zoom'],
                                                     pan_x_frac=bg['pan_x'], pan_y_frac=bg['pan_y'])
            for path, o in spec['images']:
                place = dict(x_mm=o.get('x_mm'), y_mm=o.get('y_mm'), width_mm=o.get('width_mm'),
                             height_mm=o.get('height_mm'), theta=o.get('theta', 0.0))
                if path.lower().endswith('.pyf'):
                    try:
                        img = canvas.add_figure(path, **place)
                    except (OSError, RuntimeError, ValueError) as exc:
                        raise PosterRecipeError(f'{os.path.basename(path)}: could not render '
                                                f'the figure ({exc})') from exc
                else:
                    img = canvas.add_image(path, **place)
                img.frame = o.get('frame', 'none')
                img.caption = o.get('caption')
                n_images += 1
            if spec['arrange'] and spec['arrange'][0] != 'none' and spec['images']:
                kind, layout, params = spec['arrange']
                canvas.arrange(kind, layout_name=layout, **params)
            for t in spec['text']:
                shape = canvas.add_text(t.get('html'), x_mm=t.get('x_mm'), y_mm=t.get('y_mm'),
                                        theta=t.get('theta', 0.0), style=t['style'])
                if 'width_mm' in t:
                    aspect = shape.width_mm / shape.height_mm
                    c = shape.center_mm()
                    shape.width_mm, shape.height_mm = t['width_mm'], t['width_mm'] / aspect
                    if 'x_mm' not in t:
                        shape.set_center_mm(c.x(), c.y())
        canvas.current_page_index = 0
        canvas.selected = None
    out = plan['output']
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    canvas.save(out, filetype=os.path.splitext(out)[1].lstrip('.').lower())
    result = {'output': out, 'page_count': len(canvas.pages), 'image_count': n_images,
              'album_mode': canvas.album_mode}
    if 'render' in plan:
        r = plan['render']
        os.makedirs(os.path.dirname(r) or '.', exist_ok=True)
        if r.lower().endswith('.pdf'):
            canvas.export_album_pdf(r, dpi=plan['dpi'])
        else:
            canvas.save(r, dpi=plan['dpi'])
        result['render'] = r
    if 'web' in plan:
        os.makedirs(os.path.dirname(plan['web']) or '.', exist_ok=True)
        canvas.export_album_web(plan['web'])
        result['web'] = plan['web']
    return result


def build_poster_from_recipe(recipe_path, canvas=None):
    """Validate then build. Raises PosterRecipeError for recipe mistakes."""
    recipe_path = os.path.abspath(recipe_path)
    if not os.path.isfile(recipe_path):
        raise PosterRecipeError(f'no such recipe file: {recipe_path}')
    try:
        recipe = load_recipe(recipe_path)
    except PosterRecipeError:
        raise
    except Exception as exc:
        raise PosterRecipeError(f'{os.path.basename(recipe_path)}: cannot parse ({exc})') from exc
    plan = plan_recipe(recipe, recipe_path)
    return build_from_plan(plan, canvas=canvas)
