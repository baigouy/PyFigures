"""Write the sample videos that check_on_mac.py plays with Apple's own decoder.

Run on the development machine (Windows/Linux) after changing the video
writer, then commit tests/mac_check/samples/ and run the "Mac video check"
GitHub workflow (Actions tab -> Mac video check -> Run workflow). The files go
through the real code paths: batoolset.img.write_video and the PyFigures
video export (MCP export_video -> headless GUI).

    python tests/mac_check/make_samples.py
"""
import json
import os
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "samples")
FPS = 10
LEVELS = (30, 90, 150, 210)          # mean grey of each frame: catches dropped,
                                     # reordered or range-squeezed (16-235) frames


def _frames(h, w, grey=False):
    ramp = np.linspace(-20, 20, w).round().astype(np.int16)
    out = []
    for v in LEVELS:
        f = np.full((h, w, 3), v, np.int16)
        f = f + ramp[None, :, None]                       # a gradient, same mean
        f[: h // 4, : w // 4] = (v + 40, v - 20, v - 20)   # a coloured corner
        out.append(np.clip(f, 0, 255).astype(np.uint8))
    a = np.stack(out)
    if grey:
        a = a.mean(axis=3).round().astype(np.uint8)
    return a


def _expect(a):
    rgb = a if a.ndim == 4 else np.repeat(a[..., None], 3, axis=3)
    h, w = rgb.shape[1:3]
    return {"frames": int(len(rgb)), "fps": FPS,
            "width": w + (w % 2), "height": h + (h % 2),
            "means": [round(float(f.mean()), 2) for f in rgb]}


def main():
    from batoolset.img import write_video
    os.makedirs(OUT, exist_ok=True)
    for n in os.listdir(OUT):            # empty it, keep the folder (OneDrive locks it)
        os.remove(os.path.join(OUT, n))
    expected = {}
    for name, a in (("rgb_odd_size.mp4", _frames(241, 321)),
                    ("rgb_odd_size.mov", _frames(241, 321)),
                    ("grey.mp4", _frames(120, 160, grey=True)),
                    ("full_hd.mp4", _frames(1080, 1920))):
        write_video(a, os.path.join(OUT, name), fps=FPS,
                    dimensions="thwc" if a.ndim == 4 else "thw")
        expected[name] = _expect(a)

    # the whole PyFigures path: a figure whose panel is a movie, exported as a video
    from pyfigures.mcp_server import create_figure, add_image, export_video
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, "movie.tif")
        import tifffile
        tifffile.imwrite(src, _frames(90, 120), photometric="rgb")
        pyf = os.path.join(tmp, "fig.pyf")
        create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
        add_image(pyf, [0], src)
        out = os.path.join(OUT, "pyfigures_export.mp4")
        r = export_video(pyf, out)
        if r.startswith("ERROR"):
            print(r)
            sys.exit(1)
        # the figure adds margins and picks the frame rate: take them from the
        # file, decoded by ffmpeg (PyAV) as the reference the Mac must match
        import av
        with av.open(out) as c:
            s = c.streams.video[0]
            means = [round(float(f.to_ndarray(format="rgb24").mean()), 2) for f in c.decode(s)]
            expected["pyfigures_export.mp4"] = {
                "frames": len(means), "fps": float(s.average_rate),
                "width": s.codec_context.width, "height": s.codec_context.height,
                "means": means}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with open(os.path.join(OUT, "expected.json"), "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=1)
    for n in sorted(os.listdir(OUT)):
        print(n, os.path.getsize(os.path.join(OUT, n)), "bytes")


if __name__ == "__main__":
    main()
