"""Image flips: the Image2D properties ``flip_h`` / ``flip_v``.

A flip is part of how a panel is drawn (like its rotation): the loaded pixels
stay the original and only the displayed image is mirrored. The image editor
(Rotate + Crop tab), the recipe key ``flip`` and the MCP tool
``transform_image`` all set these two properties.

Older versions stored a flip as a loading script that re-read the file through
matplotlib; :func:`legacy_state` recognises those so they can be converted.
"""
from __future__ import annotations


def legacy_state(script) -> tuple[bool, bool] | None:
    """(flip_h, flip_v) when *script* is an old flip-only loading script, else None."""
    text = str(script or "")
    if "# flip" in text and "self.img = fig" in text and "tifffile" in text:
        return "arr[:, ::-1]" in text, "arr[::-1, :]" in text
    return None
