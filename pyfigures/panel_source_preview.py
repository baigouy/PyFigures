"""The whole source image of one panel, uncropped, with pixel rulers and the
current crop outlined: what an MCP client needs to choose crop values.

A figure preview shows each panel small and already cropped, so a model asked
to "crop g so the nuclei fill the frame" cropped, previewed, uncropped and
cropped again until it ran out of steps (2026-11-03). Shared by the live chat
tool preview_panel and the headless MCP tool preview_panel_source.
"""
import math


def _step(size):
    """A round ruler step giving about 8 ticks over *size* pixels."""
    raw = max(size / 8, 1)
    power = 10 ** math.floor(math.log10(raw))
    for f in (1, 2, 5, 10):
        if raw <= f * power:
            return int(f * power)
    return int(10 * power)


def qimage_to_rgb(qimage):
    """A QImage as an (h, w, 3) uint8 array."""
    import numpy as np
    from qtpy.QtGui import QImage
    image = qimage.convertToFormat(QImage.Format.Format_RGB888)
    w, h = image.width(), image.height()
    ptr = image.constBits()
    ptr.setsize(image.bytesPerLine() * h)
    rows = np.frombuffer(ptr, np.uint8).reshape(h, image.bytesPerLine())
    return rows[:, :w * 3].reshape(h, w, 3).copy()


def panel_crop(panel):
    """(left, top, right, bottom) crop of an Image2D, in source pixels."""
    return tuple(int(round(float(getattr(panel, 'crop_' + side, 0) or 0)))
                 for side in ('left', 'top', 'right', 'bottom'))


def border_colour(panel, width=4):
    """The colour of the image's own background, as shown: the median of the pixels
    along the edges of its visible (cropped) part. An int 0xRRGGBB. ("fit the panel's
    background to the image's background", 2026-11-13: the chat had no way to read it.)"""
    import numpy as np
    rgb = panel_rgb(panel)
    h, w = rgb.shape[:2]
    left, top, right, bottom = panel_crop(panel)
    view = rgb[top:max(top + 1, h - bottom), left:max(left + 1, w - right)]
    k = max(1, min(width, view.shape[0] // 4, view.shape[1] // 4))
    edges = np.concatenate([view[:k].reshape(-1, 3), view[-k:].reshape(-1, 3),
                            view[:, :k].reshape(-1, 3), view[:, -k:].reshape(-1, 3)])
    r, g, b = (int(v) for v in np.median(edges, axis=0))
    return (r << 16) | (g << 8) | b


def stretch(rgb):
    """*rgb* with its 0.5-99.8 percentile range spread over 0-255: dim
    fluorescence (nuclei barely above black) becomes visible. Display only."""
    import numpy as np
    low, high = np.percentile(rgb, (0.5, 99.8))
    if high <= low:
        return rgb
    return (np.clip((rgb.astype(np.float32) - low) / (high - low), 0, 1) * 255).astype(np.uint8)


def _region(region, w, h):
    """(x0, y0, x1, y1) clipped to the image, or the whole image for None."""
    if region is None:
        return 0, 0, w, h
    if len(region) != 4:
        raise ValueError('region is [x0, y0, x1, y1] in source pixels')
    x0, y0, x1, y1 = (int(round(float(v))) for v in region)
    x0, x1 = sorted((max(0, min(w, x0)), max(0, min(w, x1))))
    y0, y1 = sorted((max(0, min(h, y0)), max(0, min(h, y1))))
    if x1 - x0 < 4 or y1 - y0 < 4:
        raise ValueError(f'region {list(region)} is (almost) empty inside the {w}x{h} px source')
    return x0, y0, x1, y1


def render(rgb, crop, out_path, title='', brighten=True, region=None, rois=()):
    """Save *rgb* with pixel rulers, a light grid and *crop* outlined; *region*
    (x0, y0, x1, y1) shows only that part, magnified; *rois* are (index, kind,
    geometry) drawn in magenta. Returns a one-line description of the picture."""
    if brighten:
        rgb = stretch(rgb)
    import matplotlib
    matplotlib.use('Agg', force=False)
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Ellipse, Polygon
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = _region(region, w, h)
    rw, rh = x1 - x0, y1 - y0
    left, top, right, bottom = crop
    inch = 8.0
    fig, ax = plt.subplots(figsize=(inch, inch * rh / rw if rw else inch), dpi=110)
    ax.imshow(rgb[y0:y1, x0:x1], interpolation='nearest', extent=(x0, x1, y1, y0))
    step = _step(max(rw, rh))
    ax.set_xticks(range(x0 - x0 % step, x1 + 1, step))
    ax.set_yticks(range(y0 - y0 % step, y1 + 1, step))
    ax.tick_params(labelsize=8, top=True, labeltop=True, right=True, labelright=True)
    ax.grid(color='#00e5ff', alpha=0.35, linewidth=0.6)
    if any(crop):
        ax.add_patch(Rectangle((left, top), w - left - right, h - top - bottom, fill=False,
                               edgecolor='yellow', linewidth=1.8, linestyle='--'))
    for index, kind, geometry in rois:
        style = dict(fill=False, edgecolor='#ff00ff', linewidth=1.4)
        if kind == 'polygon':
            ax.add_patch(Polygon(geometry, closed=True, **style))
            lx, ly = geometry[0]
        elif kind == 'line':
            ax.plot([geometry[0], geometry[2]], [geometry[1], geometry[3]], color='#ff00ff', linewidth=1.4)
            lx, ly = geometry[0], geometry[1]
        else:
            gx, gy, gw, gh = geometry
            patch = Ellipse((gx + gw / 2, gy + gh / 2), gw, gh, **style) if kind == 'ellipse' else Rectangle((gx, gy), gw, gh, **style)
            ax.add_patch(patch)
            lx, ly = gx, gy
        if x0 <= lx <= x1 and y0 <= ly <= y1:
            ax.annotate(str(index), (lx, ly), color='#ff00ff', fontsize=7, xytext=(1, -1), textcoords='offset points')
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    kept = f'kept x {left}-{w - right}, y {top}-{h - bottom}' if any(crop) else 'no crop'
    zoom = f'region x {x0}-{x1}, y {y0}-{y1} of ' if region is not None else ''
    ax.set_title((title + '\n' if title else '') + f'{zoom}source {w}x{h} px; current crop left={left} top={top} '
                 f'right={right} bottom={bottom} ({kept}, yellow box)', fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    shown = ' Contrast stretched for this preview only; the figure is unchanged.' if brighten else ''
    what = (f'Region x {x0}-{x1}, y {y0}-{y1} of the panel source ({w}x{h} px), magnified,' if region is not None
            else f'Whole source of the panel, {w}x{h} px,')
    drawn = (f' Its {len(rois)} existing ROI(s) are drawn in magenta, labelled with their annotation_index.'
             if rois else '')
    return (f'{what} with pixel rulers (x left to right, y top to bottom; ROIs, arrows and crops use these '
            f'source pixels).{shown}{drawn} '
            f'Current crop: left={left}, top={top}, right={right}, bottom={bottom} ({kept}, dashed yellow box). '
            f'To keep the region x0-x1, y0-y1 set crop_left=x0, crop_top=y0, crop_right={w}-x1, crop_bottom={h}-y1. '
            f'To look closer, call again with region=[x0, y0, x1, y1].')


def panel_rois(panel):
    """The panel's ROIs as (annotation_index, kind, geometry) in source pixels."""
    out = []
    for index, a in enumerate(getattr(panel, 'annotations', None) or []):
        name = type(a).__name__
        try:
            if name in ('Rectangle2D', 'Rect2D', 'Square2D', 'Ellipse2D', 'Circle2D'):
                kind = 'ellipse' if name in ('Ellipse2D', 'Circle2D') else 'rect'
                out.append((index, kind, (a.x(), a.y(), a.width(), a.height())))
            elif name == 'Line2D':
                out.append((index, 'line', (a.x1(), a.y1(), a.x2(), a.y2())))
            elif name in ('Polygon2D', 'PolyLine2D', 'Freehand2D'):
                points = [(p.x(), p.y()) for p in a]
                if len(points) >= 2:
                    out.append((index, 'polygon', points))
        except (AttributeError, TypeError):
            continue
    return out


def panel_rgb(panel):
    """The panel's displayed pixels (LUTs, channels, projection, flips), uncropped."""
    if getattr(panel, 'qimage', None) is None:
        if getattr(panel, 'img', None) is None and hasattr(panel, 'load_img'):
            panel.load_img()
        if getattr(panel, 'qimage', None) is None and hasattr(panel, 'update_qimage'):
            panel.update_qimage()
    if getattr(panel, 'qimage', None) is None:
        raise ValueError('This panel has no pixel image (a template, a plot script or a missing file); '
                         'there is nothing to crop by pixels.')
    return qimage_to_rgb(panel.qimage)


def panel_channels(panel):
    """The panel's real channels: a list, one entry per channel, of the colour it is
    shown in (its LUT, else the file's own colour; None when unknown), or [] for a
    single-channel image. An RGB file without channel colours gives RED/GREEN/BLUE."""
    import numpy as np
    from batoolset.img import guess_dimensions
    img = getattr(panel, 'img', None)
    if img is None and hasattr(panel, 'load_img'):
        panel.load_img()
        img = getattr(panel, 'img', None)
    if not isinstance(img, np.ndarray):
        return []
    try:
        dims = guess_dimensions(img) or ''
    except Exception:
        dims = ''
    if 'c' not in dims:
        return []
    n = img.shape[dims.index('c')] if len(dims) == img.ndim else img.shape[-1]
    if n < 2:
        return []
    try:
        from pyfigures.assistant.session import channel_colours
        colours = list(channel_colours(panel) or [])
    except Exception:
        colours = []
    colours = (colours + [None] * n)[:n]
    if not any(colours) and n == 3:
        colours = ['RED', 'GREEN', 'BLUE']
    return [str(c).upper() if c else None for c in colours]


def panel_channel_plane(panel, index):
    """Channel *index* (0-based) of *panel* as it is shown (same z, time point,
    projection and display range), as a 2-D float array: the panel is drawn once
    with only that channel on, in gray, then put back as it was."""
    import numpy as np
    n = len(panel_channels(panel))
    if not 0 <= index < n:
        raise ValueError(f'channel {index + 1} does not exist: the image has {n or 1} channel(s)')
    saved = (getattr(panel, 'channels', None), getattr(panel, 'LUTs', None))
    try:
        panel.channels = [i == index for i in range(n)]
        luts = list(saved[1] or [None] * n)
        luts = (luts + [None] * n)[:n]
        luts[index] = 'GRAY'
        panel.LUTs = luts
        panel.update_qimage()
        plane = qimage_to_rgb(panel.qimage).astype(np.float32).mean(axis=2)
    finally:
        panel.channels, panel.LUTs = saved
        try:
            panel.update_qimage()
        except Exception:
            pass
    return plane


def detection_plane(panel, channel='all'):
    """(plane, rgb, what) for object detection: *channel* 'all' (the colours as shown,
    averaged), a channel number ('2', 1-based as people count) or a colour ('blue'):
    the image's own channel shown in that colour when it has real channels (from the
    file's metadata or its LUTs), else that colour of the picture as shown. *rgb* is
    the picture as shown (its size is the image's)."""
    rgb = panel_rgb(panel)
    if channel in (None, '', 'all'):
        return None, rgb, 'all channels'
    text = str(channel).strip().lower()
    colours = panel_channels(panel)
    if text.isdigit():
        index = int(text) - 1
        if not colours:
            if index == 0:
                return None, rgb, 'channel 1 (the only one)'
            raise ValueError(f'channel {text} does not exist: the image has a single channel')
        return panel_channel_plane(panel, index), rgb, f'channel {text}' + (
            f' ({colours[index].lower()})' if 0 <= index < len(colours) and colours[index] else '')
    matches = [i for i, c in enumerate(colours) if c and c.lower() == text]
    if len(matches) == 1:
        return panel_channel_plane(panel, matches[0]), rgb, f'channel {matches[0] + 1} ({text})'
    if text in ('red', 'green', 'blue'):
        from .object_detection import channel_plane
        return channel_plane(rgb, text), rgb, f'the {text} of the picture as shown'
    names = ', '.join(f'{i + 1}' + (f' ({c.lower()})' if c else '') for i, c in enumerate(colours)) or '1'
    raise ValueError(f'no channel is shown in {text!r}; channels: {names}. Use a channel number or "all".')


def preview_panel(panel, out_path, title='', brighten=True, region=None):
    """Render *panel*'s whole source (or *region* of it) with rulers and its ROIs to
    *out_path*; returns its description."""
    return render(panel_rgb(panel), panel_crop(panel), out_path, title, brighten, region, panel_rois(panel))
