"""Offer PyMuPDF when a PDF panel would otherwise be a picture.

Without PyMuPDF a PDF page is embedded as a 600-dpi image; with it the page
stays a true vector panel. The offer appears the first time a PDF is added
in a session, and when a figure holding PDF panels is exported to a vector
format (PDF, SVG, PowerPoint, Illustrator, VectorCraft). "Don't ask again"
turns it off (user_prefs); Tools > Vector PDF panels (PyMuPDF)… asks
again any time. PyMuPDF (AGPL v3) is downloaded from PyPI only on the
user's yes — see pyfigures/extras.py and docs/LICENSING.md.
"""
from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QCheckBox, QMessageBox

from pyfigures.extras import PYMUPDF_LICENSE, has_pymupdf, install_pymupdf

_asked_this_session = [False]
# offscreen (headless tests, scripted runs) there is nobody to answer a dialog;
# tests of the offer itself set this
ASK_OFFSCREEN = False


def _nobody_to_ask() -> bool:
    try:
        return QApplication.platformName() == 'offscreen' and not ASK_OFFSCREEN
    except Exception:
        return True


def figure_pdf_panels(shapes) -> list:
    """The Image2D panels of *shapes* (nested groups included) showing a PDF."""
    found = []
    stack = list(shapes or [])
    while stack:
        s = stack.pop()
        content = getattr(s, 'content', None)
        if isinstance(content, list):
            stack.extend(content)
        fn = getattr(s, 'filename', None)
        if isinstance(fn, str) and fn.lower().endswith('.pdf'):
            found.append(s)
    return found


def revectorise(panels) -> int:
    """Convert PDF panels drawn as pictures again, now as vectors; returns
    how many were redone (their size and settings are kept)."""
    n = 0
    for p in panels:
        try:
            p.setFigure(p.filename)
            n += 1
        except Exception:
            pass
    return n


def offer_pymupdf(parent, reason='add', panels=None, force=False) -> bool:
    """Offer to install PyMuPDF; True when PDF panels can now be vectors.
    *reason*: 'add' (a PDF was just added), 'export' (a vector export of a
    figure with PDF panels) or 'menu' (asked from the Tools menu: always
    shown). Asked once per session, never after "Don't ask again"."""
    from pyfigures.gui import user_prefs
    if has_pymupdf():
        if force and not _nobody_to_ask():
            QMessageBox.information(parent, 'Vector PDF panels',
                                    'PyMuPDF is installed: PDF panels are already vectors.')
        return True
    if _nobody_to_ask():
        return False
    if not force and (_asked_this_session[0] or not user_prefs.load_offer_pymupdf()):
        return False
    _asked_this_session[0] = True
    lead = {'add': 'This PDF is shown as a 600-dpi picture.',
            'export': 'The PDF panels of this figure will be exported as 600-dpi pictures.',
            }.get(reason, 'PDF panels are shown as 600-dpi pictures.')
    box = QMessageBox(parent)
    box.setWindowTitle('Keep PDF panels as vectors?')
    box.setIcon(QMessageBox.Question)
    box.setText(f'<b>{lead}</b><br><br>'
                'With <b>PyMuPDF</b> they stay true vectors: sharp at any zoom, light '
                'files, and still vectors in your PDF, SVG, PowerPoint, Illustrator and '
                'VectorCraft exports. One click, about 25 MB.')
    box.setInformativeText(f'PyMuPDF is free, open-source software by Artifex, licensed '
                           f'{PYMUPDF_LICENSE.split(" (")[0]}. It is downloaded from PyPI '
                           f'only if you click Install; PyFigures works without it.')
    install = box.addButton('Install PyMuPDF', QMessageBox.AcceptRole)
    box.addButton('Not now', QMessageBox.RejectRole)
    box.setDefaultButton(install)
    check = None
    if not force:
        check = QCheckBox("Don't ask again", box)
        box.setCheckBox(check)
    box.exec()
    if check is not None and check.isChecked():
        user_prefs.save_offer_pymupdf(False)
    if box.clickedButton() is not install:
        return False
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        ok, msg = install_pymupdf()
    finally:
        QApplication.restoreOverrideCursor()
    if not ok:
        import sys
        if getattr(sys, 'frozen', False):
            # the standalone apps have no pip: a pip command is no help there
            hint = ('\n\nCheck the internet connection (or a proxy or firewall blocking '
                    'pypi.org), then try again from Tools → Vector PDF panels.')
        else:
            hint = None
        if hint is None:
            from pyfigures.gui.command_box import show_command
            show_command(parent, 'Vector PDF panels',
                         'PyMuPDF could not be installed:\n' + msg
                         + '\n\nYou can install it yourself with:  pip install pymupdf',
                         'pip install pymupdf', warning=True)
        else:
            QMessageBox.warning(parent, 'Vector PDF panels',
                                'PyMuPDF could not be installed:\n' + msg + hint)
        return False
    redone = revectorise(panels or [])
    QMessageBox.information(parent, 'Vector PDF panels',
                            'PyMuPDF installed: PDF panels are now vectors'
                            + (f' ({redone} panel(s) converted).' if redone else '.'))
    return True
