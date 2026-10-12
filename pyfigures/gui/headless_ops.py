#!/usr/bin/env python3
"""Headless (no-window) figure operations that need the live PyFigures panel:
video export and file consolidation.

Both reuse the exact GUI code paths — they just run off-screen with the
interactive dialogs bypassed — so the MCP server can offer them by shelling out
to this module in a subprocess (keeping the server Qt-free and crash-isolated),
mirroring pyfigures/gui/render_headless.py.

    python -m pyfigures.gui.headless_ops video       <pyf> <out.mp4> [--frame-mode freeze|blank] [--bg R,G,B]
    python -m pyfigures.gui.headless_ops consolidate <pyf> <out.pyf>
"""
from __future__ import annotations

import os as _os
from pyfigures.offscreen import use_offscreen as _use_offscreen
_use_offscreen()   # offscreen + the system fonts (none at all on Windows otherwise)
_os.environ.setdefault("QT_API", "pyqt6")

import argparse
import sys


def _build_gui(pyf_path: str):
    """Return (app, gui) with the figure loaded off-screen and interactive
    dialogs silenced. Keep the returned app referenced for the whole op."""
    pyf_path = _os.path.abspath(pyf_path)
    if not _os.path.isfile(pyf_path):
        raise FileNotFoundError(f"no such .pyf file: {pyf_path}")

    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication(sys.argv[:1])
    try:
        from pyfigures.gui.portable_fonts import register_portable_fonts
        register_portable_fonts(app)
    except Exception:
        pass

    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Yes)

    gui = EZFIG_GUI()
    gui.reload_state(pyf_path, append=False)
    return app, gui


def export_video(pyf_path: str, out_path: str, frame_mode: str = "freeze",
                 bg_color=(0, 0, 0)) -> str:
    """Render the figure's time-stack/video panels to *out_path*
    (.mp4/.mov/.mkv/.webm/.avi)."""
    out_path = _os.path.abspath(out_path)
    if not out_path.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
        raise ValueError("video output must end in .mp4, .mov, .mkv, .webm or .avi")
    app, gui = _build_gui(pyf_path)  # noqa: F841 (keep app alive)
    try:
        panel = gui.paint.EZFIG_panel
        if not panel._collect_time_stacks():
            raise RuntimeError("this figure has no video / time-stack panel to animate")
        out_dir = _os.path.dirname(out_path)
        if out_dir:
            _os.makedirs(out_dir, exist_ok=True)
        panel.save_video(out_path, frame_mode=frame_mode, bg_color=tuple(bg_color))
    finally:
        gui._dirty = False
        gui.hide()
        # a loader thread still running when the window is freed kills the process
        gui._stop_all_img_loaders()
    if not _os.path.isfile(out_path) or _os.path.getsize(out_path) == 0:
        raise RuntimeError("video rendering produced no output")
    return out_path


def export_latex(pyf_path: str, out_path: str, image_format: str = "pdf",
                 with_caption: bool = False):
    """Export 'PDF + LaTeX': a text-free graphics file plus an \\input-able LaTeX
    overlay (GUI: Export As → PDF + LaTeX). Returns (graphics_path, tex_path).

    If *with_caption* is set, the figure's ``<stem>.caption.json`` sidecar (if
    present) is wrapped in a ``figure`` float with a ``\\caption{...}``."""
    out_path = _os.path.abspath(out_path)
    app, gui = _build_gui(pyf_path)  # noqa: F841 (keep app alive)
    caption = caption_title = None
    if with_caption:
        import json as _json
        sidecar = _os.path.splitext(_os.path.abspath(pyf_path))[0] + ".caption.json"
        if _os.path.isfile(sidecar):
            try:
                with open(sidecar, encoding="utf-8") as _f:
                    _d = _json.load(_f)
                caption = _d.get("caption") or None
                caption_title = _d.get("title") or None
            except Exception:
                pass
    try:
        panel = gui.paint.EZFIG_panel
        if not panel.shapes_to_draw:
            raise RuntimeError("the figure contains no panels to export")
        panel.get_dpi = (lambda _d=300: _d)  # avoid the DPI dialog for png/raster format
        out_dir = _os.path.dirname(out_path)
        if out_dir:
            _os.makedirs(out_dir, exist_ok=True)
        img_path, tex_path = panel.save_latex(
            out_path, image_format=image_format,
            caption=caption, caption_title=caption_title)
    finally:
        gui._dirty = False
        gui.hide()
        # a loader thread still running when the window is freed kills the process
        gui._stop_all_img_loaders()
    if not (_os.path.isfile(img_path) and _os.path.isfile(tex_path)):
        raise RuntimeError("LaTeX export produced no output")
    return img_path, tex_path


def fonts_report(out_json: str) -> str:
    """Write the portable-font report (bundled + available families) to *out_json*.
    Needs a QApplication for QFontDatabase, so it runs here off-screen."""
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841
    from pyfigures.gui.portable_fonts import register_portable_fonts, font_report
    register_portable_fonts(app)
    import json as _json
    rep = font_report()
    with open(out_json, "w", encoding="utf-8") as f:
        _json.dump(rep, f, ensure_ascii=False, indent=2)
    return out_json


def consolidate(pyf_path: str, out_pyf: str) -> str:
    """Copy every referenced image next to *out_pyf* (in a .files folder) and
    save a self-contained figure — the GUI's Save & Consolidate, headless."""
    out_pyf = _os.path.abspath(out_pyf)
    if not out_pyf.lower().endswith(".pyf"):
        raise ValueError("consolidation output must end in .pyf")
    app, gui = _build_gui(pyf_path)  # noqa: F841 (keep app alive)
    try:
        from batoolset.files.tools import (
            smartly_consolidate_files_to_reduce_dupes, consolidate_files2)
        from batoolset.files.tools import smart_name_parser

        panel = gui.paint.EZFIG_panel
        names, _imgs = panel.get_full_list_ofimages2D_for_consolidation()
        files_dir = smart_name_parser(out_pyf, "TA") + ".files"
        names, consolidated = smartly_consolidate_files_to_reduce_dupes(names, files_dir)
        consolidate_files2(files_dir, names, consolidated)
        gui._save_state_to_file(out_pyf)
        gui.reload_state(out_pyf, append=False, skip_add_to_stack=True)
        # point every panel at its copy (as the GUI's Save & Consolidate does);
        # without this the "self-contained" figure still linked the originals
        _, imgs = gui.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation()
        for img in imgs:
            img.consolidate_names(names, consolidated)
        gui._save_state_to_file(out_pyf)
        src_base = _os.path.splitext(_os.path.abspath(pyf_path))[0]
        dst_base = _os.path.splitext(out_pyf)[0]
        if src_base != dst_base:
            gui._copy_sidecars(src_base, dst_base)
    finally:
        gui._dirty = False
        gui.hide()
        # a loader thread still running when the window is freed kills the process
        gui._stop_all_img_loaders()
    if not _os.path.isfile(out_pyf):
        raise RuntimeError("consolidation produced no .pyf output")
    return out_pyf


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Headless PyFigures operations.")
    sub = ap.add_subparsers(dest="op", required=True)

    v = sub.add_parser("video")
    v.add_argument("pyf_path")
    v.add_argument("out_path")
    v.add_argument("--frame-mode", choices=["freeze", "blank"], default="freeze")
    v.add_argument("--bg", default="0,0,0", help="blank-frame background R,G,B")

    c = sub.add_parser("consolidate")
    c.add_argument("pyf_path")
    c.add_argument("out_path")

    lx = sub.add_parser("latex")
    lx.add_argument("pyf_path")
    lx.add_argument("out_path")
    lx.add_argument("--format", default="pdf", choices=["pdf", "png", "svg"])
    lx.add_argument("--with-caption", action="store_true",
                    help="wrap in a figure float with the .caption.json sidecar caption")

    fo = sub.add_parser("fonts")
    fo.add_argument("out_json")

    args = ap.parse_args(argv)
    try:
        if args.op == "fonts":
            out = fonts_report(args.out_json)
        elif args.op == "video":
            bg = tuple(int(x) for x in args.bg.split(","))
            out = export_video(args.pyf_path, args.out_path,
                               frame_mode=args.frame_mode, bg_color=bg)
        elif args.op == "latex":
            img, tex = export_latex(args.pyf_path, args.out_path,
                                    image_format=args.format,
                                    with_caption=args.with_caption)
            out = img + "\n" + tex
        else:
            out = consolidate(args.pyf_path, args.out_path)
    except Exception as e:
        sys.stderr.write(f"ERROR: {type(e).__name__}: {e}\n")
        return 1
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
