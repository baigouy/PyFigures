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
    if getattr(sys, "frozen", False):
        # zarr 2 (all a Python 3.10 build gets) cannot read newer OME-Zarr files
        assert int(zarr.__version__.split(".")[0]) >= 3, f"zarr {zarr.__version__} < 3"
    return f"ok (zarr {zarr.__version__})"


def _check_chat(tmp):
    """The chat sidebar is a core part of the apps: its package, a real key
    store for API keys, and the live MCP server it starts (PyFigures
    --live-mcp in the apps), which must answer with its tools."""
    import qtpy_ai_sidecar  # noqa: F401
    from qtpy_ai_sidecar import widgets  # noqa: F401  (the dock)
    from qtpy_ai_sidecar.adapters import pyfigures as adapter  # noqa: F401
    import keyring
    backend = keyring.get_keyring()
    name = type(backend).__module__ + "." + type(backend).__name__
    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        # Linux apps: the Secret Service backend must be bundled; whether a key
        # store answers depends on the desktop (none on a headless build machine)
        from keyring.backends import SecretService  # noqa: F401
        import secretstorage  # noqa: F401
        import jeepney  # noqa: F401
    elif getattr(sys, "frozen", False):
        # the apps must bundle the OS key store backends (Windows Credential
        # Manager, macOS Keychain); a pip install on a headless Linux server has
        # none, which only means API keys cannot be saved there
        assert "fail" not in name.lower() and "null" not in name.lower(), f"no key store: {name}"
    from pyfigures.assistant.launch import mcp_server_command
    command, args = mcp_server_command()
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ, PYFIGURES_MCP_SURFACE="categories", PYFIGURES_LIVE_RUNTIME=tmp,
               QT_QPA_PLATFORM="offscreen")

    async def tools():
        params = StdioServerParameters(command=command, args=args, env=env)
        with anyio.fail_after(240):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return (await session.list_tools()).tools

    listed = anyio.run(tools)
    assert len(listed) >= 5, f"MCP server listed {len(listed)} tools"
    import importlib.metadata
    store = name.rsplit('.', 2)[-2]
    if store == "fail" and sys.platform.startswith("linux"):
        store = "Secret Service bundled, no key store running"
    return f"ok (qtpy-ai-sidecar {importlib.metadata.version('qtpy-ai-sidecar')}, {store}, {len(listed)} MCP tools)"


def _check_web_engine():
    """The 'PyFigures Web Chat' app must bundle Qt WebEngine and its helper
    process: a page is loaded and its text read back. The other apps leave it
    out (the web chat then works through the clipboard)."""
    from pyfigures.assistant.web_chat import is_web_chat_app
    required = getattr(sys, "frozen", False) and is_web_chat_app(sys.executable)
    try:
        from qtpy.QtWebEngineWidgets import QWebEngineView
    except Exception as e:
        assert not required, f"Qt WebEngine missing: {e}"
        return "ok (not bundled: web chat in clipboard mode)"
    from qtpy.QtCore import QEventLoop, QTimer
    view = QWebEngineView()
    loop = QEventLoop()
    state = {}
    view.loadFinished.connect(lambda ok: (state.update(loaded=ok), loop.quit()))
    QTimer.singleShot(120000, loop.quit)
    view.setHtml("<html><body>pyfigures web engine</body></html>")
    loop.exec()
    assert state.get("loaded"), "the page did not load (helper process?)"
    view.page().runJavaScript("document.body.innerText", 0,
                              lambda text: (state.update(text=text), loop.quit()))
    QTimer.singleShot(60000, loop.quit)
    loop.exec()
    assert state.get("text") == "pyfigures web engine", f"page text {state.get('text')!r}"
    view.deleteLater()
    return "ok (Qt WebEngine loads a page)"


CHECKS = {"qt_svg": _check_qt_svg, "pdf_panels": _check_pdf_panels,
          "video": _check_video, "zarr": _check_zarr, "chat": _check_chat,
          "web_engine": _check_web_engine}


def run(report_path):
    from qtpy.QtCore import QCoreApplication, Qt
    from qtpy.QtWidgets import QApplication
    if QApplication.instance() is None:
        # Qt WebEngine (web_engine check) is imported after the QApplication
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(["pyfigures-self-test"])
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, check in CHECKS.items():
            try:
                results[name] = check(tmp) if name in ("pdf_panels", "chat") else check()
            except Exception:
                results[name] = "FAILED: " + traceback.format_exc(limit=3)
    ok = all(v.startswith("ok") for v in results.values())
    report = {"ok": ok, "frozen": bool(getattr(sys, "frozen", False)), "checks": results}
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    del app
    return 0 if ok else 1
