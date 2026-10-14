"""Offer to install LaTeX (TinyTeX, batoolset.tex_install) when a LaTeX feature
is used on a computer without it: full-LaTeX equations, .tex documents,
LaTeX data plots. Also Help → Install LaTeX for PyFigures…

The download (~55-75 MB, then the packages) runs in a thread; the dialog only
polls its progress, so no Qt object is touched from the thread.
"""
from __future__ import annotations

import threading

from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtWidgets import QMessageBox, QProgressDialog

_declined = set()          # don't ask twice in one session for the same need


def latex_ready() -> bool:
    from batoolset.latex_tools import latex_available
    return latex_available()


def run_install(parent, installer=None) -> bool:
    """Install TinyTeX with a progress dialog; True when LaTeX is usable after."""
    from batoolset import tex_install
    installer = installer or tex_install.install
    state = {"fraction": 0.0, "message": "Starting…", "done": False, "error": None,
             "cancel": False}

    def progress(fraction, message):
        state["fraction"] = fraction
        state["message"] = message

    def work():
        try:
            installer(progress=progress, cancelled=lambda: state["cancel"])
        except Exception as e:                       # reported in the GUI thread
            state["error"] = e
        finally:
            state["done"] = True

    dlg = QProgressDialog("Installing LaTeX…", "Cancel", 0, 1000, parent)
    dlg.setWindowTitle("Install LaTeX for PyFigures")
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.setValue(0)
    loop = QEventLoop()
    timer = QTimer()

    def poll():
        if dlg.wasCanceled():
            state["cancel"] = True
        dlg.setLabelText(state["message"])
        dlg.setValue(int(state["fraction"] * 1000))
        if state["done"]:
            timer.stop()
            loop.quit()
    timer.timeout.connect(poll)
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    timer.start(150)
    loop.exec()
    dlg.close()
    if state["error"] is not None:
        if not isinstance(state["error"], InterruptedError):
            QMessageBox.warning(parent, "Install LaTeX",
                                "LaTeX could not be installed:\n" + str(state["error"])
                                + "\n\nYou can also install TeX Live, MiKTeX or MacTeX yourself.")
        return False
    from batoolset import latex_tools
    latex_tools.ensure_on_path()
    return latex_ready()


def offer_latex_install(parent, why="This needs LaTeX") -> bool:
    """True when LaTeX can be used, after offering to install it if needed."""
    if latex_ready():
        return True
    if why in _declined:
        return False
    answer = QMessageBox.question(
        parent, "LaTeX",
        f"{why}, and no LaTeX installation was found.\n\n"
        "PyFigures can install TinyTeX for you: a small TeX Live (about 75 MB to "
        "download, ~400 MB on disk) in your user folder, no administrator rights needed. "
        "Figures made with it open on any computer, LaTeX or not.\n\nInstall it now?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes)
    if answer != QMessageBox.StandardButton.Yes:
        _declined.add(why)
        return False
    return run_install(parent)


def install_latex_action(parent):
    """Help → Install LaTeX for PyFigures…"""
    from batoolset import tex_install
    if latex_ready() and tex_install.is_installed():
        QMessageBox.information(parent, "Install LaTeX",
                                "TinyTeX is installed in\n" + tex_install.install_dir())
        return True
    if latex_ready():
        answer = QMessageBox.question(
            parent, "Install LaTeX",
            "A LaTeX installation was found and PyFigures uses it. Install TinyTeX anyway "
            "(about 75 MB)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return True
        return run_install(parent)
    why = "Typesetting equations and .tex documents with LaTeX"
    _declined.discard(why)                       # asked from the menu: always ask
    return offer_latex_install(parent, why)
