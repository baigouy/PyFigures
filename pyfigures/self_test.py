"""Checks that a standalone build contains what it should.

    PyFigures.exe --self-test report.json

Writes a JSON report (a windowed executable has no console) and exits with
status 0 if every check passed, 1 otherwise. Run by the CI after each build.
"""
import json
import os
import sys
import tempfile
import traceback


def _check_qt_svg():
    from qtpy.QtSvg import QSvgRenderer
    from qtpy.QtCore import QByteArray
    r = QSvgRenderer(QByteArray(b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
                                b'<rect width="10" height="10"/></svg>'))
    assert r.isValid()
    return "ok"


def _check_pdf_panels(tmp):
    """A PDF written by Qt, read back as a panel: with pypdfium2 (the apps
    must not contain PyMuPDF, AGPL)."""
    import importlib.util
    from qtpy.QtCore import QSizeF
    from qtpy.QtGui import QPainter, QPdfWriter, QPageSize, QColor
    # only the standalone apps must not contain it: pip install pyfigures[pdf]
    # (and [all]) installs PyMuPDF on purpose
    if getattr(sys, "frozen", False):
        assert importlib.util.find_spec("fitz") is None, "PyMuPDF (AGPL) is bundled"
    path = os.path.join(tmp, "page.pdf")
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QSizeF(200, 100), QPageSize.Unit.Point))
    p = QPainter(writer)
    p.fillRect(0, 0, writer.width(), writer.height(), QColor("red"))
    p.end()
    from batoolset.img import pdf_page_count
    from batoolset.drawings.shapes.image2d import pdf_to_svg_bytes
    assert pdf_page_count(path) == 1
    svg = pdf_to_svg_bytes(path)
    if importlib.util.find_spec("fitz") is not None:
        # a pip install with the [pdf] extra: PyMuPDF gives vector panels
        assert svg.lstrip().startswith(b"<svg") and b"<path" in svg
        return "ok (PyMuPDF vector panels)"
    assert b"<image" in svg and b"data:image/png;base64," in svg
    import pypdfium2  # noqa: F401  (the renderer used above)
    try:
        import importlib.metadata
        version = importlib.metadata.version("pypdfium2")
    except Exception:
        version = "?"
    return f"ok (pypdfium2 {version})"


def _check_video():
    import av
    assert "libx264" in av.codecs_available
    return f"ok (PyAV {av.__version__})"


def _check_zarr():
    import zarr
    return f"ok (zarr {zarr.__version__})"


CHECKS = {"qt_svg": _check_qt_svg, "pdf_panels": _check_pdf_panels,
          "video": _check_video, "zarr": _check_zarr}


def run(report_path):
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(["pyfigures-self-test"])
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, check in CHECKS.items():
            try:
                results[name] = check(tmp) if name == "pdf_panels" else check()
            except Exception:
                results[name] = "FAILED: " + traceback.format_exc(limit=3)
    ok = all(v.startswith("ok") for v in results.values())
    report = {"ok": ok, "frozen": bool(getattr(sys, "frozen", False)), "checks": results}
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    del app
    return 0 if ok else 1
