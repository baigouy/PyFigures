"""What is inside an image stack: dimension order, sizes, voxel size, frame
interval. Shared by the stack tools (montage, channel split, kymograph,
orthogonal views) of the MCP server and the GUI.

Reads through batoolset's ``Img`` — the reader PyFigures panels use — so the
dimension order ('tdhwc', 'dhwc', 'hwc', …) is exactly what an Image2D panel
will see. Timing comes from the file's own metadata when present (ImageJ
``finterval``/``tunit``, Zeiss LSM ``TimeIntervall``, OME ``TimeIncrement``).
"""
from __future__ import annotations

import os
import re

__all__ = ["stack_info", "StackInfoError", "parse_frames", "format_stamp"]

_TIME_UNITS = {"sec": "s", "second": "s", "seconds": "s", "s": "s",
               "min": "min", "minute": "min", "minutes": "min",
               "h": "h", "hr": "h", "hour": "h", "hours": "h",
               "ms": "ms", "msec": "ms"}


class StackInfoError(ValueError):
    """The file cannot be read as an image stack."""


_MICRO_UNITS = {"micron", "microns", "micrometer", "micrometers", "micrometre",
                "micrometres", "um", "µm", "μm", "mum"}


def _norm_unit(u):
    """Spatial unit as written in the file, with the micrometre spellings
    ('micron', 'microns', 'um', '\\u00B5m', Greek mu…) unified to 'µm'."""
    if not u:
        return None
    u = str(u).strip().replace("\\u00B5", "µ").replace("\\u03BC", "µ")
    return "µm" if u.lower() in _MICRO_UNITS else u


def _tiff_timing(path):
    """(interval, unit, space_unit) from TIFF metadata, any may be None."""
    try:
        import tifffile
    except ImportError:
        return None, None, None
    try:
        with tifffile.TiffFile(path) as t:
            ij = t.imagej_metadata or {}
            fi = ij.get("finterval")
            tunit = ij.get("tunit")
            sunit = _norm_unit(ij.get("unit"))
            if fi:
                return float(fi), _TIME_UNITS.get(str(tunit or "sec").lower(), tunit or "s"), sunit
            if t.is_lsm:
                lsm = t.lsm_metadata or {}
                ti = lsm.get("TimeIntervall")
                if ti:
                    return float(ti), "s", sunit or "µm"
            if t.is_ome:
                import re
                m = re.search(r'TimeIncrement="([0-9.eE+-]+)"(?:\s+TimeIncrementUnit="([^"]+)")?',
                              t.ome_metadata or "")
                if m:
                    return float(m.group(1)), _TIME_UNITS.get((m.group(2) or "s").lower(), m.group(2) or "s"), sunit
            return None, None, sunit
    except Exception:
        return None, None, None


def stack_info(path: str, series: int | None = None) -> dict:
    """Describe the stack at *path*::

        {"order": "tdhwc", "shape": (19, 21, 300, 400, 2),
         "sizes": {"t": 19, "d": 21, "h": 300, "w": 400, "c": 2},
         "vx": 0.38, "vz": 0.75, "space_unit": "µm",
         "interval": 2.0, "time_unit": "min"}

    'd' is the Z axis. Raises StackInfoError if the file can't be read."""
    from pyfigures.path_resolution import source_exists
    if not path or not source_exists(path):
        raise StackInfoError(f"no such file: {path}")
    try:
        from batoolset.img import Img, guess_dimensions
        img = Img(path, serie_to_open=series) if series is not None else Img(path)
    except Exception as e:
        raise StackInfoError(f"cannot read {os.path.basename(path)}: {type(e).__name__}: {e}") from None
    order = guess_dimensions(img) or ""
    shape = tuple(int(s) for s in img.shape)
    if len(order) != len(shape):
        raise StackInfoError(f"unexpected dimensions {order!r} for shape {shape}")
    md = getattr(img, "metadata", None) or {}
    interval, tunit, sunit = (None, None, None)
    if path.lower().endswith((".tif", ".tiff", ".lsm")):
        interval, tunit, sunit = _tiff_timing(path)
    times = md.get("times")
    if interval is None and times is not None:
        try:
            ts = [float(v) for v in list(times)]
            if len(ts) > 1 and ts[1] > ts[0]:
                interval, tunit = ts[1] - ts[0], "s"
        except Exception:
            pass

    def _pos(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if v > 0 else None

    vx = _pos(md.get("vx"))
    return {
        "path": os.path.abspath(path),
        "order": order,
        "shape": shape,
        "sizes": {k: shape[i] for i, k in enumerate(order)},
        "dtype": str(img.dtype),
        "vx": vx,
        "vy": _pos(md.get("vy")) or vx,
        "vz": _pos(md.get("vz")),
        "space_unit": sunit or ("µm" if vx else None),
        "interval": interval,
        "time_unit": tunit,
    }


def parse_frames(spec, n: int, default_count: int = 6) -> list[int]:
    """Frame indices from a spec, validated against *n* frames.

    None -> *default_count* evenly spaced frames including the first and last;
    an int N -> N evenly spaced frames (first and last included); "all";
    "start:stop:step" (Python slice, stop exclusive, e.g. "::5" = every 5th);
    "first-last" or "first-last:step" (inclusive, e.g. "0-11:3");
    or an explicit list [0, 5, 10]."""
    if n < 1:
        raise ValueError("the stack has no frames along that axis")
    if spec is None:
        spec = default_count
    if isinstance(spec, int) and not isinstance(spec, bool):
        if spec < 1:
            raise ValueError("the number of frames must be >= 1")
        k = min(spec, n)
        if k == 1:
            return [0]
        return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    if isinstance(spec, str):
        s = spec.strip().lower()
        if s == "all":
            return list(range(n))
        # "0-11" or "0-11:3": an inclusive range, as Fiji's Make Substack writes it
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)(?:\s*:\s*(\d+))?", s)
        if m:
            a, b, step = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
            if step < 1 or b < a:
                raise ValueError(f"bad frame range {spec!r}: write first-last, e.g. '0-11' or '0-11:3'")
            return parse_frames(list(range(a, b + 1, step)), n)
        if not re.fullmatch(r"[\d\s,:-]+", s):
            raise ValueError(f"bad frames {spec!r}: use a list [0, 5, 10], a count, 'all', "
                             "'first-last' (e.g. '0-11', '0-11:3') or 'start:stop:step'")
        if ":" in s:
            parts = [p.strip() for p in s.split(":")]
            if len(parts) > 3:
                raise ValueError(f"bad frame range {spec!r}")
            vals = [int(p) if p else None for p in parts] + [None] * (3 - len(parts))
            out = list(range(n))[slice(*vals)]
            if not out:
                raise ValueError(f"frame range {spec!r} selects nothing (stack has {n})")
            return out
        if "," in s:
            spec = [int(v) for v in s.split(",") if v.strip()]
        else:
            return parse_frames(int(s), n)
    out = [int(v) for v in spec]
    bad = [v for v in out if not 0 <= v < n]
    if bad:
        raise ValueError(f"frame(s) {bad} out of range (0..{n - 1})")
    if not out:
        raise ValueError("no frames given")
    return out


def format_stamp(value: float, unit: str | None, fmt: str | None = None) -> str:
    """'0 min', '2.5 s', '12 µm' — *fmt* may use {value} and {unit}."""
    if fmt:
        return fmt.format(value=value, unit=unit or "")
    if abs(value - round(value)) < 1e-9:
        txt = str(int(round(value)))
    else:
        txt = f"{value:.3g}"
    return f"{txt} {unit}".strip() if unit else txt
