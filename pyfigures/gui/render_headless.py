#!/usr/bin/env python3
"""Headless rendering of a PyFigures .pyf figure to an image file.

This reuses the exact same load + paint path as the interactive GUI (so the
output matches what File -> Export produces), but runs without a visible
window (the Qt "offscreen" platform) and without any interactive dialogs
(the DPI prompt and the "unsaved changes" warning are stubbed out).

Use it two ways:

  * as a function, from a fresh process::

        from pyfigures.gui.render_headless import render_pyf
        render_pyf("fig.pyf", "fig.png", dpi=300)

  * as a CLI (this is how the MCP server calls it, in a subprocess so a Qt
    crash can never take the server down)::

        python -m pyfigures.gui.render_headless fig.pyf fig.png --dpi 300

Supported output extensions: .png .tif/.tiff .jpg/.jpeg .svg .pdf
(dpi only affects raster formats; svg/pdf are vector).
"""
from __future__ import annotations

# The Qt platform MUST be selected before any Qt module is imported, so do it
# here at the very top before anything pulls in QtWidgets. We only force it when
# the caller has not asked for a specific platform (e.g. a real display).
import os as _os
from pyfigures.offscreen import use_offscreen as _use_offscreen
_use_offscreen()   # offscreen + the system fonts (none at all on Windows otherwise)
_os.environ.setdefault("QT_API", "pyqt6")

import argparse
import sys

_RASTER_EXTS = {".png", ".tif", ".tiff", ".jpg", ".jpeg"}
_VECTOR_EXTS = {".svg", ".pdf", ".qpic"}     # .qpic: Qt paint commands (poster PDF export)
SUPPORTED_EXTS = _RASTER_EXTS | _VECTOR_EXTS


def _make_app():
    """Return a QApplication instance, creating one if necessary."""
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    try:
        from pyfigures.gui.portable_fonts import register_portable_fonts
        register_portable_fonts(app)
    except Exception:
        pass
    return app


def render_pyf(pyf_path: str, out_path: str, dpi: int = 300, _keep_alive=None, crop=None) -> str:
    """Render *pyf_path* to *out_path*, returning the absolute output path.

    Raises FileNotFoundError if the .pyf does not exist, ValueError for an
    unsupported output extension, and RuntimeError if nothing was written.
    """
    pyf_path = _os.path.abspath(pyf_path)
    out_path = _os.path.abspath(out_path)
    if not _os.path.isfile(pyf_path):
        raise FileNotFoundError(f"no such .pyf file: {pyf_path}")
    ext = _os.path.splitext(out_path)[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(
            f"unsupported output extension {ext!r}; use one of "
            + ", ".join(sorted(SUPPORTED_EXTS)))

    out_dir = _os.path.dirname(out_path)
    if out_dir:
        _os.makedirs(out_dir, exist_ok=True)

    # Keep a live reference to the QApplication for the whole render: if the
    # only Python handle is dropped, PyQt6 can garbage-collect the wrapper and
    # crash the interpreter natively.
    app = _make_app()  # noqa: F841  (must stay referenced)

    # Import the GUI only after the QApplication exists.
    from qtpy.QtWidgets import QInputDialog, QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI

    # Silence the three interactive touch-points the load + save path would hit:
    #   - the first-run tips popup
    #   - the "unsaved changes" warning on reload
    #   - the "choose a DPI" dialog inside the raster save branch
    EZFIG_GUI.show_tips = lambda self: None
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Yes)

    gui = EZFIG_GUI()
    try:
        # Synchronous load (a real path takes the non-dialog branch of
        # reload_state, which also runs arrange_text_rows so label rows and
        # side labels are positioned exactly as in the GUI).
        gui.reload_state(pyf_path, append=False)

        panel = gui.paint.EZFIG_panel
        if not panel.shapes_to_draw:
            raise RuntimeError(
                f"the figure loaded from {pyf_path} contains no panels to render")

        # Pin the output DPI so save() never opens the QInputDialog.
        panel.get_dpi = (lambda _dpi=int(dpi): _dpi)

        panel.update_size()
        try:
            b = panel.updateBounds()
            bw, bh = float(b.width()), float(b.height())
        except Exception:
            bw = bh = 1.0
        if bw < 1 or bh < 1:
            raise RuntimeError(f"the figure is {bw:.1f} x {bh:.1f} px: its panels have no room "
                               f"(too narrow for its panels and the gaps between them) — widen "
                               f"the figure, wrap the rows or reduce the spacing")
        if crop is not None:
            panel.save(out_path, crop=crop)
        else:
            panel.save(out_path)
    finally:
        # Mark clean and hide (do NOT deleteLater / close: closeEvent runs the
        # save-prompt + os._exit path, and an explicit delete without a running
        # event loop can crash PyQt6 natively). The process exits right after.
        gui._dirty = False
        gui.hide()
        if _keep_alive is not None:
            _keep_alive.append(gui)

    if not _os.path.isfile(out_path) or _os.path.getsize(out_path) == 0:
        raise RuntimeError(
            f"rendering produced no output at {out_path} (check that the "
            "figure's image files exist and are readable)")
    return out_path


_KEEP_ALIVE = []


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Render a PyFigures .pyf figure to an image (headless).")
    ap.add_argument("pyf_path", help="input .pyf figure file")
    ap.add_argument("out_path", help="output image (.png/.tif/.jpg/.svg/.pdf)")
    ap.add_argument("--dpi", type=int, default=300,
                    help="output DPI for raster formats (default 300)")
    ap.add_argument("--crop", default=None,
                    help=".qpic only: left,top,right,bottom fractions of the figure to clip away "
                         "(the poster designer's crop, recorded in the picture)")
    args = ap.parse_args(argv)
    # nothing is ever freed: Python freeing Qt objects (the window, its image
    # loaders) without an event loop crashed the process natively (access
    # violation) in about 1 run out of 20, after the output was written. This
    # process is short-lived: no cyclic GC, and it ends with os._exit.
    import gc
    gc.disable()
    try:
        crop = tuple(float(v) for v in args.crop.split(",")) if args.crop else None
        out = render_pyf(args.pyf_path, args.out_path, dpi=args.dpi, _keep_alive=_KEEP_ALIVE, crop=crop)
    except Exception as e:
        sys.stderr.write(f"ERROR: {type(e).__name__}: {e}\n")
        return 1
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    code = _main()
    sys.stdout.flush()
    sys.stderr.flush()
    _os._exit(code)
