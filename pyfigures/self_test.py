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


def _check_video(tmp):
    """An H.264 MP4 is really written: with x264 when PyAV has it, else the
    system's encoder (VideoToolbox on macOS, Media Foundation on Windows), the
    order the video export uses. (Asking for libx264 by name failed every macOS
    app when OpenCV 5.1's FFmpeg libraries took the place of PyAV's.)"""
    import av
    import numpy as np
    from batoolset.img import _av_codec_for, _write_video_av
    path = os.path.join(tmp, "self_test.mp4")
    codec = _av_codec_for(path)
    assert codec, f"no H.264 encoder in PyAV {av.__version__}"
    frames = np.zeros((6, 64, 96, 3), np.uint8)
    frames[:, :, :, 1] = np.arange(6, dtype=np.uint8)[:, None, None] * 40
    _write_video_av(frames, path, 10, codec, 23)
    with av.open(path) as container:
        stream = container.streams.video[0]
        assert stream.codec_context.name == "h264", stream.codec_context.name
        assert sum(1 for _ in container.decode(stream)) == 6
    return f"ok (PyAV {av.__version__}, {codec})"


def _check_zarr():
    import zarr
    if getattr(sys, "frozen", False):
        # zarr 2 (all a Python 3.10 build gets) cannot read newer OME-Zarr files
        assert int(zarr.__version__.split(".")[0]) >= 3, f"zarr {zarr.__version__} < 3"
    return f"ok (zarr {zarr.__version__})"


def _check_chat(tmp):
    """The chat sidebar is a core part of the apps: its package, a real key
    store for API keys, and the live MCP server it starts (PyFigures
    --live-mcp in the apps), which must answer with its tools. The no-AI
    app must not contain it."""
    from pyfigures.assistant import ai_features_enabled
    if not ai_features_enabled():
        try:
            import qtpy_ai_sidecar  # noqa: F401
        except ImportError:
            return "ok (no AI: chat sidebar not included)"
        assert not getattr(sys, "frozen", False), "the no-AI app contains qtpy_ai_sidecar"
        return "ok (no AI: chat sidebar hidden)"
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
    try:
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
    finally:
        # the page must be gone before Qt releases the WebEngine profile at exit,
        # or the app crashes on quitting ("WebEnginePage still not deleted"):
        # after a failed check too, which must end with status 1 and its report
        from qtpy.QtCore import QCoreApplication, QEvent
        view.close()
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
    return "ok (Qt WebEngine loads a page)"


def _check_fiji():
    """Fiji / Bio-Formats is in every app (user 2026-11-27): its Python side is bundled
    and the Java bridge starts frozen. Java 21 is fetched (about 50 MB, or a Java 21 found
    on the machine); Fiji itself (650 MB) is not downloaded here: jgo is pure Python and
    the same as in the pip install, checked on a fresh install.

    Only the built apps are held to it: a pip install may have no [fiji] extra, and the
    test suite never starts a JVM in its own process."""
    frozen = bool(getattr(sys, "frozen", False))
    if not frozen and os.environ.get("PYFIGURES_SELF_TEST_FIJI_OPEN") != "1":
        try:
            import imagej
        except ImportError:
            return "ok (pip install without the [fiji] extra)"
        return f"ok (pyimagej {imagej.__version__}; the JVM start is checked in the built apps)"
    import cjdk  # noqa: F401
    import imagej
    import jgo  # noqa: F401
    import jpype
    import scyjava
    from batoolset.IJ import ij_reader
    jar = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(jpype.__file__))),
                       "org.jpype.jar")
    if not os.path.isfile(jar):
        return f"FAILED: JPype support library missing ({jar})"
    if ij_reader._FIJI_ENDPOINT != "sc.fiji:fiji:" + ij_reader._FIJI_VERSION:
        return "FAILED: Fiji not pinned"
    if os.environ.get("PYFIGURES_SELF_TEST_FIJI_OPEN") == "1":
        # the whole first run, for a release check by hand (not in CI: ~650 MB): start
        # Fiji, downloading it if needed, and open a Bio-Formats-only file with it
        import tempfile
        import time
        from batoolset.img import Img
        fake = os.path.join(tempfile.mkdtemp(),
                            "t&sizeX=64&sizeY=32&sizeZ=2&sizeC=3&pixelType=uint16.fake")
        open(fake, "w").close()
        t0 = time.time()
        img = Img(fake)
        if tuple(img.shape) != (2, 32, 64, 3):
            return f"FAILED: the Bio-Formats test file opened as {img.shape}"
        return (f"ok: pyimagej {imagej.__version__}, Fiji {ij_reader._FIJI_VERSION} started and "
                f"a Bio-Formats file opened in {time.time() - t0:.0f} s")
    ij_reader._use_conda_java()          # Java 21: a system one, else fetched by cjdk
    scyjava.start_jvm()
    version = str(scyjava.jimport("java.lang.System").getProperty("java.version"))
    if int(version.split(".")[0]) < ij_reader._FIJI_JAVA:
        return f"FAILED: Java {version} started, Fiji needs {ij_reader._FIJI_JAVA}"
    return f"ok: pyimagej {imagej.__version__}, Java {version} started"


CHECKS = {"qt_svg": _check_qt_svg, "pdf_panels": _check_pdf_panels,
          "video": _check_video, "zarr": _check_zarr, "chat": _check_chat,
          "web_engine": _check_web_engine,
          "fiji": _check_fiji}     # last: it starts a JVM


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
                results[name] = check(tmp) if name in ("pdf_panels", "video", "chat") else check()
            except Exception:
                results[name] = "FAILED: " + traceback.format_exc(limit=3)
    ok = all(v.startswith("ok") for v in results.values())
    report = {"ok": ok, "frozen": bool(getattr(sys, "frozen", False)), "checks": results}
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    # destroyed here, not left to os._exit: with Qt WebEngine loaded, quitting
    # with a live QApplication crashes on Windows (fatal 0x80000003)
    del app
    return 0 if ok else 1
