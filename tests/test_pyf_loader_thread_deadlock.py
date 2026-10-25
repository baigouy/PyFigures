"""The .pyf loader's worker is deleted on the GUI thread (2026-10-25).

Deleted on its own thread (thread.finished → deleteLater), ~QObject held
Qt's connection lock while PyQt waited for the GIL to drop the wrapper; the
GUI thread, holding the GIL and creating an object (a layout animation),
waited for that lock — the whole app froze. Seen as random 5-min hangs in
the suite (py-spy: main in QBasicMutex::lockInternal from QObjectPrivate,
worker in PyGILState_Ensure from QObject::~QObject)."""
from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def test_worker_returns_to_the_gui_thread_before_it_is_deleted(qapp, tmp_path):
    from qtpy.QtCore import QThread, Qt
    from pyfigures.gui.pfgui import _PyfLoaderWorker
    from pyfigures.mcp_server import create_figure
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    thread = QThread()
    worker = _PyfLoaderWorker([pyf])
    worker.moveToThread(thread)
    seen = {}
    worker.file_ready.connect(lambda *a: seen.setdefault("ready", True), Qt.QueuedConnection)
    worker.finished.connect(lambda: seen.setdefault("owner", worker.thread()), Qt.DirectConnection)
    worker.finished.connect(thread.quit, Qt.DirectConnection)
    thread.started.connect(worker.run)
    thread.start()
    t0 = time.time()
    while not thread.isFinished() and time.time() - t0 < 30:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()
    assert thread.wait(5000)
    assert seen.get("ready") and seen["owner"] is qapp.thread()
