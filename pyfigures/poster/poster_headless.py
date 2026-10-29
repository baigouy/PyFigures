#!/usr/bin/env python3
"""Headless (no-window) editing and rendering of .pyfposter poster/collage
files, so the MCP server can drive the poster designer by shelling out to
this module in a subprocess — keeping the server Qt-free and any Qt crash
isolated to a short-lived child process. Mirrors
pyfigures/gui/render_headless.py and pyfigures/gui/headless_ops.py.

Every subcommand loads (or creates) a PosterCanvas, applies one edit, saves
the .pyfposter back to disk, and prints a single JSON object to stdout. On
failure, "ERROR: ..." goes to stderr and the process exits 1.

    python -m pyfigures.poster.poster_headless create <poster.pyfposter> [--page-width MM] [--page-height MM] [--preset A4|A3|A2|A1|A0]
    python -m pyfigures.poster.poster_headless add-image <poster> <image> [--x MM] [--y MM] [--width MM] [--height MM] [--theta DEG] [--frame none|simple|polaroid] [--caption TEXT]
    python -m pyfigures.poster.poster_headless add-text <poster> [<html>] [--style h1|h2|h3|body|caption] [--x MM] [--y MM] [--width MM] [--height MM] [--theta DEG]
    python -m pyfigures.poster.poster_headless set-background <poster> <image> [--zoom N] [--pan-x 0..1] [--pan-y 0..1]
    python -m pyfigures.poster.poster_headless adjust-background <poster> [--zoom N] [--pan-x 0..1] [--pan-y 0..1] [--reset]
    python -m pyfigures.poster.poster_headless clear-background <poster>
    python -m pyfigures.poster.poster_headless remove-image <poster> <index>
    python -m pyfigures.poster.poster_headless set-frame <poster> <index> [--frame none|simple|polaroid] [--caption TEXT]
    python -m pyfigures.poster.poster_headless list <poster>
    python -m pyfigures.poster.poster_headless arrange-scatter <poster> [--seed N] [--margin MM] [--max-rotation DEG] [--indices 0,2,3] [--no-fit]
    python -m pyfigures.poster.poster_headless arrange-arc <poster> --center-x MM --center-y MM --radius MM [--start-angle DEG] [--end-angle DEG] [--face outward|inward|none] [--indices 0,2,3] [--no-fit]
    python -m pyfigures.poster.poster_headless arrange-grid <poster> [--columns N] [--margin MM] [--gap MM] [--indices 0,2,3] [--no-fit]
    python -m pyfigures.poster.poster_headless align-shapes <poster> --mode left|right|top|bottom|center_h|center_v [--indices 0,2,3]
    python -m pyfigures.poster.poster_headless distribute-shapes <poster> --axis x|y [--indices 0,2,3]
    python -m pyfigures.poster.poster_headless list-layouts
    python -m pyfigures.poster.poster_headless apply-layout <poster> <layout_name> [--indices 0,2,3] [--margin MM] [--no-repeat] [--no-group]
    python -m pyfigures.poster.poster_headless sketch-layout <poster> <layout_name> [--margin MM] [--no-group]
    python -m pyfigures.poster.poster_headless fill-slot <poster> <index> <image>
    python -m pyfigures.poster.poster_headless ungroup <poster> <index>
    python -m pyfigures.poster.poster_headless render <poster> <out_path> [--dpi N]

Multi-page documents (photo albums: front cover, interior spreads, back
cover — see poster_shapes.PAGE_KINDS): every op above that edits page
content also accepts [--page N] (0-based, default: page 0) to target a page
other than the document's first. A document starts as one plain page and is
saved as .pyfposter; the moment add-page adds a second page (or changes the
one page's kind), it's saved in the .pyfalbum format instead (under the same
file name) — same poster/image/text JSON shape either way.

    python -m pyfigures.poster.poster_headless list-pages <poster>
    python -m pyfigures.poster.poster_headless add-page <poster> [--kind spread|cover_front|cover_back|single] [--width MM] [--height MM] [--index N]
    python -m pyfigures.poster.poster_headless remove-page <poster> <page>
    python -m pyfigures.poster.poster_headless duplicate-page <poster> <page>
    python -m pyfigures.poster.poster_headless move-page <poster> <from_index> <to_index>
    python -m pyfigures.poster.poster_headless set-page-kind <poster> <page> <kind>
    python -m pyfigures.poster.poster_headless render-album <poster> <out_path.pdf> [--dpi N]

Photo albums: create-album makes a new photo album (a .pyfalbum with a
pinned front cover, one spread and a pinned back cover); every add-page on
it is a 'spread' inserted strictly between the two covers, and
remove-page/move-page/duplicate-page/set-page-kind refuse to touch the cover
slots. A photo album is only ever created as one (here, by a recipe with
`album: true`, or in the photo album designer) — an existing poster is never
converted into an album, nor an album back into a poster.

    python -m pyfigures.poster.poster_headless create-album <album.pyfalbum> [--preset A4] [--page-width MM --page-height MM]

Print-ready export (tiff/eps rasterised, optionally CMYK; pdf/svg vector,
always RGB — Qt has no CMYK writer for either): print-current-page exports
just the current page; print-album exports every page — a single multi-page
file for --format pdf, or a folder of one numbered file per page (plus
manifest.json) for tiff/eps/svg.

    python -m pyfigures.poster.poster_headless print-current-page <poster> <out_path> [--format tiff|eps|pdf|svg] [--color-mode cmyk|rgb] [--dpi N] [--page N]
    python -m pyfigures.poster.poster_headless print-album <poster> <out_path> [--format tiff|eps|pdf|svg] [--color-mode cmyk|rgb] [--dpi N]

Consolidation ("Source Data" bundle for a poster/album): export-source-data
copies every page's background/images into out_dir/images (renamed by page
and shape index) and writes a portable copy of the document
(out_dir/<name>.pyfposter or .pyfalbum) whose image paths point at those
copies — the bundle reopens standalone, without the original external image
files. If an image was flattened from a .pyf (dropped in as a figure — see
add-image / GUI drag-and-drop), that .pyf's own Source Data bundle
(pyfigures.mcp_server.export_source_data) is additionally nested inside
out_dir/images/<name>_pyf_bundle/ — a bundle nested inside a bundle, so the
figure behind a photo is traceable all the way to its own panels/scripts/CSVs.

    python -m pyfigures.poster.poster_headless export-source-data <poster> <out_dir> [--dpi N]

Web export: export-web renders every page to a JPEG and writes ONE
self-contained .html file (images embedded as base64 data URIs — no other
files to attach) with a page-flip viewer (click/arrow keys/swipe/thumbnail
dots) for sharing a photo album by email, link, or any static web host.

    python -m pyfigures.poster.poster_headless export-web <poster> <out.html> [--dpi N] [--quality N]

Recipe: build a whole poster/album from a YAML/JSON description (pages,
backgrounds, photos or globs, arrangement, text) — see poster_recipe.py.

    python -m pyfigures.poster.poster_headless build <recipe.yaml>
"""
from __future__ import annotations

import os as _os
from pyfigures.offscreen import use_offscreen as _use_offscreen
_use_offscreen()   # offscreen + the system fonts (none at all on Windows otherwise)
_os.environ.setdefault("QT_API", "pyqt6")

import argparse
import json
import sys

from pyfigures.poster.page_presets import PAGE_PRESETS, preset_size as _preset_size  # noqa: F401
FRAME_STYLES = ('none', 'simple', 'polaroid')
# Mirrors pyfigures.poster.poster_shapes.TEXT_STYLE_ORDER, duplicated as a
# plain tuple (like FRAME_STYLES above) so argparse setup for --help doesn't
# need to import poster_shapes (and its Qt dependencies) up front.
TEXT_STYLES = ('h1', 'h2', 'h3', 'body', 'caption')
# Mirrors pyfigures.poster.poster_shapes.PAGE_KINDS, duplicated for the same
# reason as TEXT_STYLES above.
PAGE_KINDS = ('single', 'spread', 'cover_front', 'cover_back')


def _make_app():
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    from pyfigures.qt_exit import skip_qt_teardown
    skip_qt_teardown()
    try:
        from pyfigures.gui.portable_fonts import register_portable_fonts
        register_portable_fonts(app)
    except Exception:
        pass
    return app


def _canvas_from(poster_path, page_width_mm=None, page_height_mm=None, page=None, create=False):
    """The document at *poster_path*; a new one only with *create* (a
    mistyped path used to start an empty poster silently)."""
    from pyfigures.poster.poster_canvas import PosterCanvas
    poster_path = _os.path.abspath(poster_path)
    if _os.path.isfile(poster_path):
        canvas = PosterCanvas()
        try:
            canvas.load(poster_path)
        except Exception as e:
            raise ValueError(f'cannot read {poster_path} as a poster or album ({e})') from None
    elif not create:
        raise FileNotFoundError(f'no such poster or album: {poster_path} '
                                '(create_poster / create_album make one)')
    else:
        canvas = PosterCanvas(page_width_mm=page_width_mm or 210.0,
                              page_height_mm=page_height_mm or 297.0)
        canvas.file_path = poster_path
    # No --page means page 0, as documented — not whichever page happened to
    # be current when the file was last saved (an add-page leaves the new
    # page current, so the next "add-image" without --page used to land there).
    if page is None:
        page = 0
    if not (0 <= page < len(canvas.pages)):
        raise IndexError(f'page {page} out of range (0..{len(canvas.pages) - 1})')
    canvas.current_page_index = page
    canvas.selected = None
    canvas.multi_selected = []
    return canvas


def _save(canvas, poster_path):
    poster_path = _os.path.abspath(poster_path)
    out_dir = _os.path.dirname(poster_path)
    if out_dir:
        _os.makedirs(out_dir, exist_ok=True)
    canvas.save(poster_path, filetype=canvas.suggested_filetype())


def _parse_indices(raw, canvas=None, photos_only=False):
    """"0,2,3" -> [0, 2, 3] and "1-3,5" -> [1, 2, 3, 5], checked against
    *canvas*'s shapes (in range; with *photos_only*, no text boxes:
    arrangements move photos)."""
    if not raw:
        return None
    indices = []
    try:
        for part in (x.strip() for x in raw.split(',')):
            if not part:
                continue
            first, dash, last = part.partition('-')
            if dash and first.strip():
                indices.extend(range(int(first), int(last) + 1))
            else:
                indices.append(int(part))
    except ValueError:
        raise ValueError(f'indices must be shape numbers separated by commas, e.g. "0,2,3" '
                         f'or "1-3" (got {raw!r})') from None
    if canvas is not None:
        n = len(canvas.shapes_to_draw)
        bad = [i for i in indices if not 0 <= i < n]
        if bad:
            raise ValueError(f'index {bad[0]} out of range: this page has {n} shape(s), 0..{n - 1}')
        if photos_only:
            from pyfigures.poster.poster_shapes import PosterText
            texts = [i for i in indices if isinstance(canvas.shapes_to_draw[i], PosterText)]
            if texts:
                raise ValueError(f'shape {texts[0]} is a text box; arrangements and layouts move '
                                 'photos only')
    return indices


def _shape_dict(idx, shape):
    from pyfigures.poster.poster_shapes import PosterText
    if isinstance(shape, PosterText):
        return {
            'index': idx,
            'kind': 'text',
            'html': shape.html,
            'x_mm': shape.x_mm,
            'y_mm': shape.y_mm,
            'width_mm': shape.width_mm,
            'height_mm': shape.height_mm,
            'theta': shape.theta,
            'group_id': shape.group_id,
            'style': shape.style,
        }
    return {
        'index': idx,
        'kind': 'image',
        'path': shape.path,
        'is_template': shape.is_template,
        'missing': (not shape.is_template) and not _os.path.isfile(shape.path),
        'x_mm': shape.x_mm,
        'y_mm': shape.y_mm,
        'width_mm': shape.width_mm,
        'height_mm': shape.height_mm,
        'theta': shape.theta,
        'frame': getattr(shape, 'frame', 'none'),
        'caption': getattr(shape, 'caption', None),
        'group_id': getattr(shape, 'group_id', None),
        'crop_left': getattr(shape, 'crop_left', 0.0),
        'crop_top': getattr(shape, 'crop_top', 0.0),
        'crop_right': getattr(shape, 'crop_right', 0.0),
        'crop_bottom': getattr(shape, 'crop_bottom', 0.0),
        'source_pyf': getattr(shape, 'source_pyf', None),
    }


def _doc_dict(canvas):
    return {
        'page_index': canvas.current_page_index,
        'page_count': len(canvas.pages),
        'page_kind': canvas.current_page.kind,
        'page_width_mm': canvas.page_width_mm,
        'page_height_mm': canvas.page_height_mm,
        'album_mode': canvas.album_mode,
        'background': _bg_dict(canvas.background) if canvas.background is not None else None,
        'images': [_shape_dict(i, s) for i, s in enumerate(canvas.shapes_to_draw)],
    }


def _page_dict(index, page):
    return {'index': index, 'kind': page.kind, 'width_mm': page.width_mm, 'height_mm': page.height_mm,
            'shape_count': len(page.shapes_to_draw), 'has_background': page.background is not None}


def op_create(args, album=False):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    w, h = args.page_width, args.page_height
    if args.preset:
        w, h = _preset_size(args.preset)
    if (w is not None and w <= 0) or (h is not None and h <= 0):
        raise ValueError('page width and height must be positive')
    if (w is None) != (h is None):
        raise ValueError('give both --page-width and --page-height, or neither')
    if album:
        # A photo album is made as one from the start (like the photo album
        # designer); an existing poster is never converted into one.
        if not _os.path.splitext(args.poster)[1]:
            args.poster += '.pyfalbum'
        if not args.poster.lower().endswith('.pyfalbum'):
            raise ValueError('a photo album is saved as .pyfalbum')
        if _os.path.exists(args.poster):
            raise FileExistsError(f'{_os.path.abspath(args.poster)} already exists; '
                                  'a photo album can only be created as a new file')
    else:
        if not _os.path.splitext(args.poster)[1]:
            args.poster += '.pyfposter'
        if not args.poster.lower().endswith(('.pyfposter', '.pyfalbum')):
            raise ValueError('a poster is saved as .pyfposter (or .pyfalbum once it has '
                             'several pages)')
    canvas = _canvas_from(args.poster, page_width_mm=w, page_height_mm=h, create=True)
    if album:
        canvas.new_document(w or 210.0, h or 297.0, album=True)
        canvas.file_path = _os.path.abspath(args.poster)
    _save(canvas, args.poster)
    return {'ok': True, 'path': _os.path.abspath(args.poster), **_doc_dict(canvas)}


def op_create_album(args):
    """A new photo album: pinned front cover, one spread, pinned back cover."""
    return op_create(args, album=True)


def op_add_image(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    image_path = _os.path.abspath(args.image)
    if not _os.path.isfile(image_path):
        raise FileNotFoundError(f'no such image file: {image_path}')
    if args.frame and args.frame not in FRAME_STYLES:
        raise ValueError(f'unknown frame {args.frame!r}; use one of {FRAME_STYLES}')
    for name in ('width', 'height'):
        value = getattr(args, name)
        if value is not None and value <= 0:
            raise ValueError(f'--{name} must be positive')
    place = dict(x_mm=args.x, y_mm=args.y, width_mm=args.width, height_mm=args.height,
                 theta=args.theta if args.theta is not None else 0.0)
    if image_path.lower().endswith('.pyf'):
        # a scientific figure: flattened like a GUI drop, linked for source data
        img = canvas.add_figure(image_path, **place)
    else:
        img = canvas.add_image(image_path, **place)
    if args.frame:
        img.frame = args.frame
    if args.caption:
        img.caption = args.caption
    _save(canvas, args.poster)
    idx = canvas.shapes_to_draw.index(img)
    return {'ok': True, **_shape_dict(idx, img)}


def op_add_text(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    for name in ('width', 'height'):
        value = getattr(args, name)
        if value is not None and value <= 0:
            raise ValueError(f'--{name} must be positive')
    if args.html is not None:
        import re
        if not re.sub(r'<[^>]*>|&nbsp;', '', args.html).strip():
            raise ValueError('the text is empty')
    text = canvas.add_text(html=args.html, x_mm=args.x, y_mm=args.y,
                           theta=args.theta if args.theta is not None else 0.0,
                           style=args.style or 'body')
    if args.width is not None or args.height is not None:
        # One side given: the other follows the text's own aspect ratio (the
        # font scales with the box, so a box of the wrong shape would only
        # add empty space around the text).
        aspect = text.width_mm / text.height_mm
        center = text.center_mm()
        if args.width is not None and args.height is not None:
            text.width_mm, text.height_mm = args.width, args.height
        elif args.width is not None:
            text.width_mm, text.height_mm = args.width, args.width / aspect
        else:
            text.width_mm, text.height_mm = args.height * aspect, args.height
        if args.x is None or args.y is None:
            text.set_center_mm(center.x(), center.y())
    _save(canvas, args.poster)
    idx = canvas.shapes_to_draw.index(text)
    return {'ok': True, **_shape_dict(idx, text)}


def _bg_dict(bg):
    return {'path': bg.path, 'zoom': bg.zoom, 'pan_x_frac': bg.pan_x_frac, 'pan_y_frac': bg.pan_y_frac}


def op_set_background(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    image_path = _os.path.abspath(args.image)
    canvas.check_image_readable(image_path)
    _check_zoom(args.zoom)
    canvas.set_background(image_path)
    if args.zoom is not None:
        canvas.background.set_zoom(args.zoom)
    if args.pan_x is not None:
        canvas.background.pan_x_frac = min(max(args.pan_x, 0.0), 1.0)
    if args.pan_y is not None:
        canvas.background.pan_y_frac = min(max(args.pan_y, 0.0), 1.0)
    _save(canvas, args.poster)
    return {'ok': True, 'background': _bg_dict(canvas.background)}


def op_adjust_background(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    if canvas.background is None:
        raise ValueError('this poster has no background to adjust; use set-background first')
    _check_zoom(args.zoom)
    if args.reset:
        canvas.background.reset_view()
    if args.zoom is not None:
        canvas.background.set_zoom(args.zoom)
    if args.pan_x is not None:
        canvas.background.pan_x_frac = min(max(args.pan_x, 0.0), 1.0)
    if args.pan_y is not None:
        canvas.background.pan_y_frac = min(max(args.pan_y, 0.0), 1.0)
    _save(canvas, args.poster)
    return {'ok': True, 'background': _bg_dict(canvas.background)}


def op_clear_background(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    canvas.clear_background()
    _save(canvas, args.poster)
    return {'ok': True, 'background': None}


def _image_index_message(index, canvas):
    n = len(canvas.shapes_to_draw)
    if not n:
        return f'image index {index} out of range: this page has no images or text boxes'
    return f'image index {index} out of range (0..{n - 1})'


def op_remove_image(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    if not (0 <= args.index < len(canvas.shapes_to_draw)):
        raise IndexError(_image_index_message(args.index, canvas))
    del canvas.shapes_to_draw[args.index]
    canvas.selected = None
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_set_frame(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    if not (0 <= args.index < len(canvas.shapes_to_draw)):
        raise IndexError(_image_index_message(args.index, canvas))
    shape = canvas.shapes_to_draw[args.index]
    from pyfigures.poster.poster_shapes import PosterText
    if isinstance(shape, PosterText):
        raise ValueError(f'shape {args.index} is a text box; frames and captions only apply to images')
    if args.frame:
        if args.frame not in FRAME_STYLES:
            raise ValueError(f'unknown frame {args.frame!r}; use one of {FRAME_STYLES}')
        shape.frame = args.frame
    if args.caption is not None:
        shape.caption = args.caption or None
    _save(canvas, args.poster)
    return {'ok': True, **_shape_dict(args.index, shape)}


def op_list(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    return {'ok': True, **_doc_dict(canvas)}


def _resolve_targets(canvas, indices_arg, min_count, verb):
    indices = _parse_indices(indices_arg, canvas)
    if indices is not None:
        targets = [canvas.shapes_to_draw[i] for i in indices]
    else:
        targets = list(canvas.shapes_to_draw)
    if len(targets) < min_count:
        raise ValueError(f'need at least {min_count} shapes to {verb} (use --indices to pick '
                         f'which, or add more shapes) — got {len(targets)}')
    return targets


def op_align(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    from pyfigures.poster.poster_align import align_shapes, ALIGN_MODES
    if args.mode not in ALIGN_MODES:
        raise ValueError(f'unknown align mode {args.mode!r}; use one of {ALIGN_MODES}')
    targets = _resolve_targets(canvas, args.indices, 2, 'align')
    align_shapes(targets, args.mode)
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_distribute(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    from pyfigures.poster.poster_align import distribute_shapes, DISTRIBUTE_AXES
    if args.axis not in DISTRIBUTE_AXES:
        raise ValueError(f'unknown axis {args.axis!r}; use one of {DISTRIBUTE_AXES}')
    targets = _resolve_targets(canvas, args.indices, 3, 'distribute')
    distribute_shapes(targets, args.axis)
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_arrange_scatter(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    from pyfigures.poster.poster_layouts import scatter_layout
    _check_margin(args.margin, canvas)
    if args.max_rotation < 0:
        raise ValueError(f'max_rotation must be 0 or more degrees (got {args.max_rotation})')
    scatter_layout(canvas.shapes_to_draw, canvas.page_width_mm, canvas.page_height_mm,
                   indices=_parse_indices(args.indices, canvas, photos_only=True), seed=args.seed,
                   margin_mm=args.margin, max_rotation_deg=args.max_rotation,
                   fit_to_page=not args.no_fit)
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_arrange_arc(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    from pyfigures.poster.poster_layouts import arc_layout
    if args.radius <= 0:
        raise ValueError(f'radius must be positive (got {args.radius} mm)')
    arc_layout(canvas.shapes_to_draw, args.center_x, args.center_y, args.radius,
              indices=_parse_indices(args.indices, canvas, photos_only=True),
              start_angle_deg=args.start_angle, end_angle_deg=args.end_angle,
              face=args.face,
              page_width_mm=canvas.page_width_mm, page_height_mm=canvas.page_height_mm,
              fit_to_page=not args.no_fit)
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_arrange_grid(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    from pyfigures.poster.poster_layouts import grid_layout
    if args.columns is not None and args.columns < 1:
        raise ValueError(f'columns must be 1 or more (got {args.columns})')
    if args.gap < 0:
        raise ValueError(f'gap must be 0 or more (got {args.gap} mm)')
    _check_margin(args.margin, canvas)
    grid_layout(canvas.shapes_to_draw, canvas.page_width_mm, canvas.page_height_mm,
               indices=_parse_indices(args.indices, canvas, photos_only=True), columns=args.columns,
               margin_mm=args.margin, gap_mm=args.gap, fit_to_page=not args.no_fit)
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_list_layouts(args):
    from pyfigures.poster.poster_templates import list_layouts
    return {'ok': True, 'layouts': list_layouts()}


def op_apply_layout(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    from pyfigures.poster.poster_templates import apply_layout
    _check_margin(args.margin)
    apply_layout(canvas.shapes_to_draw, canvas.page_width_mm, canvas.page_height_mm,
                args.layout, indices=_parse_indices(args.indices, canvas, photos_only=True),
                margin_mm=args.margin,
                repeat=not args.no_repeat, group=not args.no_group)
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_sketch_layout(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    canvas.sketch_layout(args.layout, margin_mm=args.margin, group=not args.no_group)
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_ungroup(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    if not (0 <= args.index < len(canvas.shapes_to_draw)):
        raise IndexError(_image_index_message(args.index, canvas))
    if canvas.shapes_to_draw[args.index].group_id is None:
        raise ValueError(f'shape {args.index} is not in a group (layouts group the photos they '
                         'place; see list_poster_images, group_id)')
    canvas.selected = canvas.shapes_to_draw[args.index]
    canvas.ungroup_selected()
    _save(canvas, args.poster)
    return {'ok': True, **_doc_dict(canvas)}


def op_fill_slot(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    if not (0 <= args.index < len(canvas.shapes_to_draw)):
        raise IndexError(_image_index_message(args.index, canvas))
    shape = canvas.shapes_to_draw[args.index]
    if not shape.is_template:
        raise ValueError(f'image {args.index} is not an empty template slot '
                         f'(current path: {shape.path!r}); use set-frame or add-image instead')
    image_path = _os.path.abspath(args.image)
    if not _os.path.isfile(image_path):
        raise FileNotFoundError(f'no such image file: {image_path}')
    if image_path.lower().endswith('.pyf'):
        canvas.fill_template_slot(shape, canvas.render_figure(image_path), source_pyf=image_path)
    else:
        canvas.fill_template_slot(shape, image_path)
    _save(canvas, args.poster)
    return {'ok': True, **_shape_dict(args.index, shape)}


def op_render(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    out_path = _os.path.abspath(args.out)
    ext = _os.path.splitext(out_path)[1].lower().lstrip('.')
    if ext not in canvas.EXPORT_FILETYPES:
        raise ValueError(f'unsupported output format {ext!r}; use one of '
                         f'{", ".join(canvas.EXPORT_FILETYPES)}')
    _check_dpi(args.dpi)
    out_dir = _os.path.dirname(out_path)
    if out_dir:
        _os.makedirs(out_dir, exist_ok=True)
    canvas.save(out_path, dpi=args.dpi)
    if not _os.path.isfile(out_path) or _os.path.getsize(out_path) == 0:
        raise RuntimeError(f'rendering produced no output at {out_path}')
    return {'ok': True, 'path': out_path, **_missing_warning(canvas)}


def _check_margin(margin, canvas=None):
    if margin is not None and margin < 0:
        raise ValueError(f'margin must be 0 or more (got {margin} mm)')
    if margin is not None and canvas is not None \
            and 2 * margin >= min(canvas.page_width_mm, canvas.page_height_mm):
        # a 200 mm margin on an A4 page was accepted: nothing left to lay out in
        raise ValueError(f'margin {margin:g} mm leaves no room on the '
                         f'{canvas.page_width_mm:g} x {canvas.page_height_mm:g} mm page')


def _check_zoom(zoom):
    if zoom is not None and zoom <= 0:
        raise ValueError(f'zoom must be positive (got {zoom}); 1 = the image just covers the page')


def _check_dpi(dpi):
    if dpi is None or dpi <= 0 or dpi > 2400:
        raise ValueError(f'dpi must be between 1 and 2400 (got {dpi})')


def _missing_warning(canvas):
    """Renders still succeed with a missing image (drawn as a grey box), but
    the caller is told which files were not found."""
    missing = canvas.missing_files()
    if not missing:
        return {}
    return {'missing_files': [{'page': pi, 'role': role, 'path': p} for pi, role, p in missing]}


def op_list_pages(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    return {'ok': True, 'album_mode': canvas.album_mode,
            'pages': [_page_dict(i, p) for i, p in enumerate(canvas.pages)]}


def op_add_page(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    for name in ('width', 'height'):
        value = getattr(args, name)
        if value is not None and value <= 0:
            raise ValueError(f'--{name} must be positive')
    if args.index is not None and not (0 <= args.index <= len(canvas.pages)):
        raise IndexError(f'insert index {args.index} out of range (0..{len(canvas.pages)})')
    if canvas.album_mode and args.kind != 'spread':
        raise ValueError(f'album mode: only spreads can be added (covers are pinned); '
                         f'got kind {args.kind!r} — turn album mode off first')
    # default: append at the end (in album mode add_page clamps it to just
    # before the back cover)
    index = args.index if args.index is not None else len(canvas.pages)
    canvas.add_page(kind=args.kind, width_mm=args.width, height_mm=args.height, index=index)
    _save(canvas, args.poster)
    return {'ok': True, 'pages': [_page_dict(i, p) for i, p in enumerate(canvas.pages)]}


def op_remove_page(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    if not (0 <= args.page < len(canvas.pages)):
        raise IndexError(f'page {args.page} out of range (0..{len(canvas.pages) - 1})')
    if len(canvas.pages) <= 1:
        raise ValueError('cannot remove the last remaining page')
    if not canvas.remove_page(args.page):
        raise ValueError(f'page {args.page} is a cover, pinned in album mode; '
                         f'turn album mode off first')
    _save(canvas, args.poster)
    return {'ok': True, 'pages': [_page_dict(i, p) for i, p in enumerate(canvas.pages)]}


def op_duplicate_page(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    if not (0 <= args.page < len(canvas.pages)):
        raise IndexError(f'page {args.page} out of range (0..{len(canvas.pages) - 1})')
    if canvas.duplicate_page(args.page) is None:
        raise ValueError(f'page {args.page} is a cover; covers cannot be duplicated in album mode')
    _save(canvas, args.poster)
    return {'ok': True, 'pages': [_page_dict(i, p) for i, p in enumerate(canvas.pages)]}


def op_move_page(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    n = len(canvas.pages)
    if not (0 <= args.from_index < n) or not (0 <= args.to_index < n):
        raise IndexError(f'page index out of range (0..{n - 1})')
    if not canvas.move_page(args.from_index, args.to_index):
        raise ValueError('album mode: the front and back covers stay first and last; '
                         'only interior spreads can be reordered')
    _save(canvas, args.poster)
    return {'ok': True, 'pages': [_page_dict(i, p) for i, p in enumerate(canvas.pages)]}


def op_set_page_kind(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    if not (0 <= args.page < len(canvas.pages)):
        raise IndexError(f'page {args.page} out of range (0..{len(canvas.pages) - 1})')
    from pyfigures.poster.poster_shapes import PAGE_KINDS
    if args.kind not in PAGE_KINDS:
        raise ValueError(f'unknown page kind {args.kind!r}; use one of {PAGE_KINDS}')
    if not canvas.set_page_kind(args.kind, index=args.page):
        raise ValueError(f'album mode: page {args.page} must stay a '
                         f'{"cover" if args.page in (0, len(canvas.pages) - 1) else "spread"}; '
                         f'turn album mode off first')
    _save(canvas, args.poster)
    return {'ok': True, 'pages': [_page_dict(i, p) for i, p in enumerate(canvas.pages)]}


def op_render_album(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    _check_dpi(args.dpi)
    out_path = _os.path.abspath(args.out)
    out_dir = _os.path.dirname(out_path)
    if out_dir:
        _os.makedirs(out_dir, exist_ok=True)
    canvas.export_album_pdf(out_path, dpi=args.dpi)
    if not _os.path.isfile(out_path) or _os.path.getsize(out_path) == 0:
        raise RuntimeError(f'rendering produced no output at {out_path}')
    return {'ok': True, 'path': out_path, 'page_count': len(canvas.pages), **_missing_warning(canvas)}


def op_print_current_page(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster, page=getattr(args, 'page', None))
    _check_dpi(args.dpi)
    out_path = _os.path.abspath(args.out)
    canvas.export_print_ready(out_path, filetype=args.format, color_mode=args.color_mode, dpi=args.dpi)
    if not _os.path.isfile(out_path) or _os.path.getsize(out_path) == 0:
        raise RuntimeError(f'print export produced no output at {out_path}')
    return {'ok': True, 'path': out_path, 'format': args.format, 'color_mode': args.color_mode, 'dpi': args.dpi,
            **_missing_warning(canvas)}


def op_print_album(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    _check_dpi(args.dpi)
    out_path = _os.path.abspath(args.out)
    result = canvas.export_album_print_ready(out_path, filetype=args.format,
                                             color_mode=args.color_mode, dpi=args.dpi)
    return {'ok': True, 'format': args.format, 'color_mode': args.color_mode, 'dpi': args.dpi, **result,
            **_missing_warning(canvas)}


def op_export_source_data(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    from pyfigures.poster.poster_source_data import export_poster_source_data
    _check_dpi(args.dpi)
    missing = _missing_warning(canvas)
    result = export_poster_source_data(canvas, _os.path.abspath(args.poster), _os.path.abspath(args.out_dir),
                                       dpi=args.dpi)
    return {'ok': True, **result, **missing}


def op_export_web(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    canvas = _canvas_from(args.poster)
    _check_dpi(args.dpi)
    if not (0 <= args.quality <= 100):
        raise ValueError(f'quality must be 0..100 (got {args.quality})')
    out_path = _os.path.abspath(args.out)
    _os.makedirs(_os.path.dirname(out_path), exist_ok=True)
    result = canvas.export_album_web(out_path, dpi=args.dpi, quality=args.quality)
    if not _os.path.isfile(out_path) or _os.path.getsize(out_path) == 0:
        raise RuntimeError(f'web export produced no output at {out_path}')
    return {'ok': True, **result, **_missing_warning(canvas)}


def op_build(args):
    _app = _make_app()  # noqa: F841 (must stay referenced)
    from pyfigures.poster.poster_recipe import build_poster_from_recipe
    return {'ok': True, **build_poster_from_recipe(args.recipe)}


def _finite(text):
    """argparse type: a finite number. 'nan' / 'inf' parsed as floats and were
    saved as positions, sizes, angles and pans (a photo at x=-Infinity)."""
    import math
    try:
        v = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{text!r} is not a number') from None
    if not math.isfinite(v):
        raise argparse.ArgumentTypeError(f'{text!r} is not a finite number')
    return v


class _Parser(argparse.ArgumentParser):
    """Bad arguments (an unknown --frame, --kind…) give one "ERROR:" line,
    not the usage text."""

    def error(self, message):
        self.exit(2, f'ERROR: {message}\n')


# the message alone for the errors a caller makes; the type too for the others
_PLAIN_ERRORS = (ValueError, IndexError, FileNotFoundError, FileExistsError, KeyError)


def _main(argv=None) -> int:
    ap = _Parser(description='Headless .pyfposter editing and rendering.')
    sub = ap.add_subparsers(dest='op', required=True, parser_class=_Parser)

    bd = sub.add_parser('build', help='build a poster/album from a YAML/JSON recipe '
                                      '(see pyfigures/poster/poster_recipe.py)')
    bd.add_argument('recipe')

    for name in ('create', 'create-album'):
        c = sub.add_parser(name)
        c.add_argument('poster')
        c.add_argument('--page-width', type=_finite, default=None)
        c.add_argument('--page-height', type=_finite, default=None)
        c.add_argument('--preset', default=None, help=', '.join(PAGE_PRESETS))

    _PAGE_HELP = 'which page to operate on (0-based; default: the document\'s only/first page)'

    a = sub.add_parser('add-image')
    a.add_argument('poster')
    a.add_argument('image')
    a.add_argument('--x', type=_finite, default=None)
    a.add_argument('--y', type=_finite, default=None)
    a.add_argument('--width', type=_finite, default=None)
    a.add_argument('--height', type=_finite, default=None)
    a.add_argument('--theta', type=_finite, default=None)
    a.add_argument('--frame', choices=list(FRAME_STYLES), default=None)
    a.add_argument('--caption', default=None)
    a.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    at = sub.add_parser('add-text')
    at.add_argument('poster')
    at.add_argument('html', nargs='?', default=None,
                    help="rich-text content, e.g. '<b>Title</b>' (plain text works too); "
                         "omit to use the --style preset's own placeholder wording")
    at.add_argument('--x', type=_finite, default=None)
    at.add_argument('--y', type=_finite, default=None)
    at.add_argument('--width', type=_finite, default=None)
    at.add_argument('--height', type=_finite, default=None)
    at.add_argument('--theta', type=_finite, default=None)
    at.add_argument('--style', choices=list(TEXT_STYLES), default='body',
                    help='target box size as a fraction of the page height (h1=title-sized down '
                         'to caption), overridden by --width/--height if given')
    at.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    sb = sub.add_parser('set-background')
    sb.add_argument('poster')
    sb.add_argument('image')
    sb.add_argument('--zoom', type=_finite, default=None)
    sb.add_argument('--pan-x', type=_finite, default=None)
    sb.add_argument('--pan-y', type=_finite, default=None)
    sb.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    ab = sub.add_parser('adjust-background')
    ab.add_argument('poster')
    ab.add_argument('--zoom', type=_finite, default=None)
    ab.add_argument('--pan-x', type=_finite, default=None)
    ab.add_argument('--pan-y', type=_finite, default=None)
    ab.add_argument('--reset', action='store_true')
    ab.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    cb = sub.add_parser('clear-background')
    cb.add_argument('poster')
    cb.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    ri = sub.add_parser('remove-image')
    ri.add_argument('poster')
    ri.add_argument('index', type=int)
    ri.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    sf = sub.add_parser('set-frame')
    sf.add_argument('poster')
    sf.add_argument('index', type=int)
    sf.add_argument('--frame', choices=list(FRAME_STYLES), default=None)
    sf.add_argument('--caption', default=None)
    sf.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    ls = sub.add_parser('list')
    ls.add_argument('poster')
    ls.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    asc = sub.add_parser('arrange-scatter')
    asc.add_argument('poster')
    asc.add_argument('--seed', type=int, default=None)
    asc.add_argument('--margin', type=_finite, default=15.0)
    asc.add_argument('--max-rotation', type=_finite, default=25.0)
    asc.add_argument('--indices', default=None)
    asc.add_argument('--no-fit', action='store_true',
                     help="don't shrink a throw to fit the page if a corner pokes past the edge")
    asc.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    aarc = sub.add_parser('arrange-arc')
    aarc.add_argument('poster')
    aarc.add_argument('--center-x', type=_finite, required=True)
    aarc.add_argument('--center-y', type=_finite, required=True)
    aarc.add_argument('--radius', type=_finite, required=True)
    aarc.add_argument('--start-angle', type=_finite, default=-60.0)
    aarc.add_argument('--end-angle', type=_finite, default=60.0)
    aarc.add_argument('--face', choices=['outward', 'inward', 'none'], default='outward')
    aarc.add_argument('--indices', default=None)
    aarc.add_argument('--no-fit', action='store_true',
                      help="don't rescale the fan to fit the page (may hang off the edge)")
    aarc.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    ag = sub.add_parser('arrange-grid')
    ag.add_argument('poster')
    ag.add_argument('--columns', type=int, default=None)
    ag.add_argument('--margin', type=_finite, default=15.0)
    ag.add_argument('--gap', type=_finite, default=6.0)
    ag.add_argument('--indices', default=None)
    ag.add_argument('--no-fit', action='store_true', help='skip the final fit-to-page safety check')
    ag.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    al_ = sub.add_parser('align-shapes')
    al_.add_argument('poster')
    al_.add_argument('--mode', required=True,
                     choices=['left', 'right', 'top', 'bottom', 'center_h', 'center_v'])
    al_.add_argument('--indices', default=None,
                     help='which shapes to align (omit for every shape on the page); need 2+')
    al_.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    ds = sub.add_parser('distribute-shapes')
    ds.add_argument('poster')
    ds.add_argument('--axis', required=True, choices=['x', 'y'])
    ds.add_argument('--indices', default=None,
                    help='which shapes to distribute (omit for every shape on the page); need 3+')
    ds.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    sub.add_parser('list-layouts')

    al = sub.add_parser('apply-layout')
    al.add_argument('poster')
    al.add_argument('layout')
    al.add_argument('--indices', default=None)
    al.add_argument('--margin', type=_finite, default=15.0)
    al.add_argument('--no-repeat', action='store_true',
                    help="don't tile the layout in bands for extra images; only fill the "
                         "first slots and leave the rest untouched")
    al.add_argument('--no-group', action='store_true',
                    help="don't group the placed images — each moves independently instead "
                         "of dragging as one block")
    al.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    sl = sub.add_parser('sketch-layout')
    sl.add_argument('poster')
    sl.add_argument('layout')
    sl.add_argument('--margin', type=_finite, default=15.0)
    sl.add_argument('--no-group', action='store_true',
                    help="don't group the sketched slots — each moves independently")
    sl.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    fs = sub.add_parser('fill-slot')
    fs.add_argument('poster')
    fs.add_argument('index', type=int)
    fs.add_argument('image')
    fs.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    ug = sub.add_parser('ungroup')
    ug.add_argument('poster')
    ug.add_argument('index', type=int)
    ug.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    r = sub.add_parser('render')
    r.add_argument('poster')
    r.add_argument('out')
    r.add_argument('--dpi', type=int, default=300)
    r.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    lp = sub.add_parser('list-pages')
    lp.add_argument('poster')

    ap_ = sub.add_parser('add-page')
    ap_.add_argument('poster')
    ap_.add_argument('--kind', default='spread', choices=list(PAGE_KINDS))
    ap_.add_argument('--width', type=_finite, default=None)
    ap_.add_argument('--height', type=_finite, default=None)
    ap_.add_argument('--index', type=int, default=None,
                     help='insert position (0-based); default: right after the last page')

    rp = sub.add_parser('remove-page')
    rp.add_argument('poster')
    rp.add_argument('page', type=int)

    dp = sub.add_parser('duplicate-page')
    dp.add_argument('poster')
    dp.add_argument('page', type=int)

    mp = sub.add_parser('move-page')
    mp.add_argument('poster')
    mp.add_argument('from_index', type=int)
    mp.add_argument('to_index', type=int)

    spk = sub.add_parser('set-page-kind')
    spk.add_argument('poster')
    spk.add_argument('page', type=int)
    spk.add_argument('kind')

    ra = sub.add_parser('render-album')
    ra.add_argument('poster')
    ra.add_argument('out')
    ra.add_argument('--dpi', type=int, default=300)

    PRINT_FORMATS = ('tiff', 'eps', 'pdf', 'svg')

    ppc = sub.add_parser('print-current-page')
    ppc.add_argument('poster')
    ppc.add_argument('out')
    ppc.add_argument('--format', choices=PRINT_FORMATS, default='tiff')
    ppc.add_argument('--color-mode', choices=('cmyk', 'rgb'), default='cmyk')
    ppc.add_argument('--dpi', type=int, default=300)
    ppc.add_argument('--page', type=int, default=None, help=_PAGE_HELP)

    pal = sub.add_parser('print-album')
    pal.add_argument('poster')
    pal.add_argument('out')
    pal.add_argument('--format', choices=PRINT_FORMATS, default='tiff')
    pal.add_argument('--color-mode', choices=('cmyk', 'rgb'), default='cmyk')
    pal.add_argument('--dpi', type=int, default=300)

    esd = sub.add_parser('export-source-data')
    esd.add_argument('poster')
    esd.add_argument('out_dir')
    esd.add_argument('--dpi', type=int, default=300)

    ewb = sub.add_parser('export-web')
    ewb.add_argument('poster')
    ewb.add_argument('out', help='output .html path')
    ewb.add_argument('--dpi', type=int, default=150)
    ewb.add_argument('--quality', type=int, default=85, help='JPEG quality, 0-100')

    args = ap.parse_args(argv)
    ops = {
        'create': op_create, 'create-album': op_create_album, 'add-image': op_add_image, 'add-text': op_add_text,
        'set-background': op_set_background, 'adjust-background': op_adjust_background,
        'clear-background': op_clear_background,
        'remove-image': op_remove_image, 'set-frame': op_set_frame, 'list': op_list,
        'arrange-scatter': op_arrange_scatter, 'arrange-arc': op_arrange_arc,
        'arrange-grid': op_arrange_grid, 'align-shapes': op_align,
        'distribute-shapes': op_distribute, 'list-layouts': op_list_layouts,
        'apply-layout': op_apply_layout, 'sketch-layout': op_sketch_layout,
        'fill-slot': op_fill_slot, 'ungroup': op_ungroup, 'render': op_render,
        'list-pages': op_list_pages, 'add-page': op_add_page, 'remove-page': op_remove_page,
        'duplicate-page': op_duplicate_page, 'move-page': op_move_page,
        'set-page-kind': op_set_page_kind, 'render-album': op_render_album,
        'print-current-page': op_print_current_page, 'print-album': op_print_album,
        'export-source-data': op_export_source_data, 'export-web': op_export_web,
        'build': op_build,
    }
    try:
        result = ops[args.op](args)
    except Exception as e:
        msg = str(e.args[0]) if isinstance(e, KeyError) and e.args else str(e)
        if not isinstance(e, _PLAIN_ERRORS):
            msg = f'{type(e).__name__}: {msg}'
        sys.stderr.write(f'ERROR: {msg}\n')
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
