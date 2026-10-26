#!/usr/bin/env python3
"""Headless (no-window) figure operations that need the live PyFigures panel:
video export and file consolidation.

Both reuse the exact GUI code paths — they just run off-screen with the
interactive dialogs bypassed — so the MCP server can offer them by shelling out
to this module in a subprocess (keeping the server Qt-free and crash-isolated),
mirroring pyfigures/gui/render_headless.py.

    python -m pyfigures.gui.headless_ops video       <pyf> <out.mp4> [--frame-mode freeze|blank] [--bg R,G,B]
    python -m pyfigures.gui.headless_ops consolidate <pyf> <out.pyf> [--download-remote]
    python -m pyfigures.gui.headless_ops editable    <pyf> <out.pptx|out.jsx|out.vectorcraft|out.deckcraft> --format pptx|jsx|vectorcraft|deckcraft
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
    # no prompt may block a headless call; Qt's own warning comes back in
    # _release(): it used to stay replaced for good, so in a process that
    # also runs the GUI (the tests, an MCP host) every later warning was
    # answered "Yes" without being shown
    getattr(QMessageBox, 'warning')                 # (sip fills the class dict lazily)
    real_warning = QMessageBox.__dict__.get('warning')
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Yes)

    try:
        gui = EZFIG_GUI()
        gui._headless_real_warning = real_warning
        gui.reload_state(pyf_path, append=False)
    except BaseException:
        _restore_warning(real_warning)
        raise
    return app, gui


def _restore_warning(real_warning):
    from qtpy.QtWidgets import QMessageBox
    if real_warning is not None:
        QMessageBox.warning = real_warning


def _release(gui):
    """End of a headless call: clean, hidden, loaders stopped, Qt's
    QMessageBox.warning back."""
    gui._dirty = False
    gui.hide()
    # a loader thread still running when the window is freed kills the process
    gui._stop_all_img_loaders()
    _restore_warning(getattr(gui, '_headless_real_warning', None))


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
        _release(gui)
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
        _release(gui)
    if not (_os.path.isfile(img_path) and _os.path.isfile(tex_path)):
        raise RuntimeError("LaTeX export produced no output")
    return img_path, tex_path


def export_editable(pyf_path: str, out_path: str, fmt: str) -> str:
    """Export an editable PowerPoint (*fmt* 'pptx') or Adobe Illustrator script
    (*fmt* 'jsx', plus its ``<stem>_assets`` image folder). Returns a JSON summary."""
    import json as _json
    from pyfigures.gui.editable_export import (capture_scene, write_pptx, write_jsx,
                                               write_vectorcraft, write_deckcraft, scene_summary)
    out_path = _os.path.abspath(out_path)
    app, gui = _build_gui(pyf_path)  # noqa: F841 (keep app alive)
    try:
        panel = gui.paint.EZFIG_panel
        if not panel.shapes_to_draw:
            raise RuntimeError("the figure contains no panels to export")
        out_dir = _os.path.dirname(out_path)
        if out_dir:
            _os.makedirs(out_dir, exist_ok=True)
        scene = capture_scene(panel, movies=fmt == "pptx")
        summary = scene_summary(scene)
        if fmt == "pptx":
            write_pptx(scene, out_path)
        elif fmt == "vectorcraft":
            write_vectorcraft(scene, out_path)
        elif fmt == "deckcraft":
            write_deckcraft(scene, out_path)
        else:
            _, assets = write_jsx(scene, out_path)
            summary["assets"] = assets
    finally:
        _release(gui)
    if not _os.path.isfile(out_path):
        raise RuntimeError("editable export produced no output")
    summary["path"] = out_path
    return _json.dumps(summary)


def fonts_report(out_json: str, resolve=()) -> str:
    """Write the portable-font report (bundled + available families) to *out_json*.
    Needs a QApplication for QFontDatabase, so it runs here off-screen."""
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841
    from pyfigures.gui.portable_fonts import register_portable_fonts, font_report
    register_portable_fonts(app)
    import json as _json
    rep = font_report(resolve)
    with open(out_json, "w", encoding="utf-8") as f:
        _json.dump(rep, f, ensure_ascii=False, indent=2)
    return out_json


def consolidate(pyf_path: str, out_pyf: str, download_remote: bool = False, failed=None) -> str:
    """Copy every referenced image next to *out_pyf* (in a .files folder) and
    save a self-contained figure — the GUI's Save & Consolidate, headless.

    Remote images (http(s), OME-Zarr URLs, OMERO links) stay links, unless
    *download_remote*: then they are saved into the bundle too. Downloads that
    fail keep their link and are appended to *failed* as (url, error)."""
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
        names, consolidated = smartly_consolidate_files_to_reduce_dupes(names, files_dir,
                                                                        download_remote=download_remote)
        not_downloaded = consolidate_files2(files_dir, names, consolidated, download_remote=download_remote)
        if failed is not None:
            failed.extend(not_downloaded or [])
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
        _release(gui)
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
    c.add_argument("--download-remote", action="store_true",
                   help="also save remote images (http(s), OME-Zarr URLs, OMERO links) into the bundle")

    lx = sub.add_parser("latex")
    lx.add_argument("pyf_path")
    lx.add_argument("out_path")
    lx.add_argument("--format", default="pdf", choices=["pdf", "png", "svg"])
    lx.add_argument("--with-caption", action="store_true",
                    help="wrap in a figure float with the .caption.json sidecar caption")

    ed = sub.add_parser("editable")
    ed.add_argument("pyf_path")
    ed.add_argument("out_path")
    ed.add_argument("--format", required=True, choices=["pptx", "jsx", "vectorcraft", "deckcraft"])

    fo = sub.add_parser("fonts")
    fo.add_argument("out_json")
    fo.add_argument("--resolve", nargs="*", default=[],
                    help="font families to report the actually drawn family for")

    sub.add_parser("install-latex",
                   help="download TinyTeX (a small TeX Live) and the packages PyFigures uses")

    args = ap.parse_args(argv)
    try:
        if args.op == "install-latex":
            from batoolset import tex_install
            out = "TinyTeX: " + tex_install.install(
                progress=lambda f, m: sys.stderr.write(f"[{f * 100:3.0f}%] {m}\n"))
        elif args.op == "fonts":
            out = fonts_report(args.out_json, args.resolve)
        elif args.op == "video":
            bg = tuple(int(x) for x in args.bg.split(","))
            out = export_video(args.pyf_path, args.out_path,
                               frame_mode=args.frame_mode, bg_color=bg)
        elif args.op == "latex":
            img, tex = export_latex(args.pyf_path, args.out_path,
                                    image_format=args.format,
                                    with_caption=args.with_caption)
            out = img + "\n" + tex
        elif args.op == "editable":
            out = export_editable(args.pyf_path, args.out_path, args.format)
        else:
            failed = []
            out = consolidate(args.pyf_path, args.out_path, download_remote=args.download_remote,
                              failed=failed)
            # one line per remote image that stayed a link (read by the MCP tool)
            for url, err in failed:
                out += f"\nNOT_DOWNLOADED\t{url}\t{err}"
    except Exception as e:
        sys.stderr.write(f"ERROR: {type(e).__name__}: {e}\n")
        return 1
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    _code = _main()
    # the work is done and reported: skip the interpreter/Qt teardown, which can
    # crash (no message, non-zero exit) after a successful export
    sys.stdout.flush()
    sys.stderr.flush()
    _os._exit(_code)
