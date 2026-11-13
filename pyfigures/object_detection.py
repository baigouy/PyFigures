"""Find objects (cells, nuclei, embryos, spots) in one panel by thresholding.

A simple tool for simple images: smoothing, an automatic (Otsu) threshold, the
objects taken as the minority class (dark cells on a light background or bright
nuclei on a dark one), small and elongated pieces dropped. Touching objects stay
one object. A model drawing "ROIs over every cell" by eye placed two boxes in two
minutes, both off target (2026-11-13); this boxes them all at once.

Shared by the MCP tool detect_objects (the live chat reaches it too) and the GUI
action Annotations > Detect objects (ROIs)…
"""


def visible_region(crop, w, h):
    """(x0, y0, x1, y1) of the part a crop (left, top, right, bottom) keeps."""
    left, top, right, bottom = crop
    return left, top, w - right, h - bottom


def _split_touching(mask, labels, min_area):
    """Round objects touching each other split along the narrowest line (distance-
    transform watershed); one seed per object of the typical size."""
    import numpy as np
    from scipy import ndimage as ndi
    from skimage.feature import peak_local_max
    from skimage.measure import regionprops
    from skimage.segmentation import watershed
    areas = [p.area for p in regionprops(labels) if p.area >= min_area]
    if not areas:
        return labels
    radius = max(2, int(0.8 * np.sqrt(np.median(areas) / np.pi)))     # most of a typical radius
    distance = ndi.gaussian_filter(ndi.distance_transform_edt(mask), 1)
    # seeds only in the thick part of each object: an oval blob keeps one seed
    peaks = peak_local_max(distance, min_distance=radius, labels=labels, exclude_border=False,
                           threshold_abs=0.6 * radius)
    markers = np.zeros(mask.shape, dtype=np.int32)
    markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    split = watershed(-distance, markers, mask=mask)
    # an object without a seed (too small for one) keeps its own label
    lost = (split == 0) & mask
    if lost.any():
        extra = labels.copy()
        extra[~lost] = 0
        split[lost] = extra[lost] + split.max()
    return split


CHANNELS = {'red': 0, 'green': 1, 'blue': 2}


def channel_plane(rgb, channel='all'):
    """The plane to threshold: the mean of the colours ('all'), or one colour as shown
    ('red', 'green', 'blue'): blue nuclei inside green/red cells (2026-11-13: the mean
    outlined whole cells)."""
    import numpy as np
    image = np.asarray(rgb, dtype=np.float32)
    if image.ndim == 2 or channel in (None, 'all'):
        return image.mean(axis=2) if image.ndim == 3 else image
    if channel not in CHANNELS:
        raise ValueError("channel is 'all', 'red', 'green' or 'blue'")
    return image[..., CHANNELS[channel]]


def detect(rgb, region=None, polarity='auto', min_area=None, max_area=None, smooth=1.5,
           exclude_border=True, max_elongation=5.0, split_touching=True, channel='all'):
    """Objects of *rgb* (h, w, 3 or h, w) inside *region* (x0, y0, x1, y1; None =
    whole image) as dicts x, y, width, height, area, in image pixels, top to
    bottom then left to right. *polarity*: 'auto', 'dark' (darker than the
    background) or 'bright'. *min_area* / *max_area* in pixels (None = 0.02 % /
    25 % of the region). Returns (objects, info) where info says what was used."""
    import numpy as np
    from scipy import ndimage as ndi
    from skimage.filters import threshold_otsu, gaussian
    from skimage.measure import label, regionprops
    from skimage.morphology import disk

    if polarity not in ('auto', 'dark', 'bright'):
        raise ValueError("polarity is 'auto', 'dark' or 'bright'")
    gray = channel_plane(rgb, channel)
    h, w = gray.shape
    x0, y0, x1, y1 = region if region is not None else (0, 0, w, h)
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise ValueError('the region to search is (almost) empty')
    part = gray[y0:y1, x0:x1]
    if smooth:
        part = gaussian(part, sigma=smooth, preserve_range=True)
    if float(part.max()) - float(part.min()) < 1e-6:
        return [], {'polarity': polarity, 'threshold': None, 'note': 'the image is uniform: nothing to find'}
    threshold = float(threshold_otsu(part))
    dark = part < threshold
    if polarity == 'auto':
        polarity = 'dark' if dark.mean() <= 0.5 else 'bright'     # the objects are the minority
    mask = dark if polarity == 'dark' else ~dark
    mask = ndi.binary_fill_holes(ndi.binary_opening(mask, structure=disk(1)))
    area = mask.size
    min_area = max(9, int(area * 0.0002)) if min_area is None else int(min_area)
    max_area = int(area * 0.25) if max_area is None else int(max_area)
    labels = label(mask)
    if split_touching:
        labels = _split_touching(mask, labels, min_area)
    objects, dropped = [], {'too small': 0, 'too large': 0, 'elongated': 0, 'touching the edge': 0}
    for prop in regionprops(labels):
        r0, c0, r1, c1 = prop.bbox
        if prop.area < min_area:
            dropped['too small'] += 1
            continue
        if prop.area > max_area:
            dropped['too large'] += 1
            continue
        major, minor = prop.axis_major_length, prop.axis_minor_length
        if minor <= 0 or major / minor > max_elongation:
            dropped['elongated'] += 1        # a burnt-in scale bar, a scratch, a border line
            continue
        if exclude_border and (r0 == 0 or c0 == 0 or r1 == mask.shape[0] or c1 == mask.shape[1]):
            dropped['touching the edge'] += 1
            continue
        objects.append({'x': c0 + x0, 'y': r0 + y0, 'width': c1 - c0, 'height': r1 - r0, 'area': int(prop.area)})
    objects.sort(key=lambda o: (o['y'], o['x']))
    return objects, {'channel': channel or 'all', 'polarity': polarity, 'threshold': round(threshold, 2), 'min_area': min_area,
                     'max_area': max_area, 'region': [x0, y0, x1, y1],
                     'dropped': {k: v for k, v in dropped.items() if v}}


def padded(obj, padding, w, h):
    """The box of *obj* grown by *padding* pixels on each side, inside the image."""
    x = max(0, obj['x'] - padding)
    y = max(0, obj['y'] - padding)
    return x, y, min(w, obj['x'] + obj['width'] + padding) - x, min(h, obj['y'] + obj['height'] + padding) - y
