"""Dialog to type a LaTeX equation, with a preview (see pyfigures.equations)."""
from __future__ import annotations

import os
import tempfile

from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QPixmap, QPainter, QColor
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                            QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
                            QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout)

from pyfigures import equations as E

_LATEX_DEFAULT_FONT = "Latin Modern (LaTeX default)"
_FONTSET_LABELS = {"cm": "Computer Modern (LaTeX)", "stix": "STIX (Times-like)",
                   "stixsans": "STIX sans", "dejavusans": "DejaVu Sans",
                   "dejavuserif": "DejaVu Serif"}


class EquationDialog(QDialog):
    """Returns its settings via values() after exec(): latex, font_size, color,
    fontset, engine, preamble."""

    def __init__(self, parent=None, latex="", font_size=12.0, color="black", fontset="cm",
                 engine=None, preamble=None, font=None):
        super().__init__(parent)
        self.setWindowTitle("Equation (LaTeX)")
        self.setMinimumWidth(560)
        self._latex_ok = E.latex_available()
        if engine is None:
            engine = "mathtext"
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.latex_edit = QPlainTextEdit(latex)
        self.latex_edit.setPlaceholderText(r"e.g. \Delta F/F_0 = \frac{F - F_0}{F_0}")
        self.latex_edit.setToolTip("LaTeX mathematics. Without $…$ the whole text is a formula; "
                                   "with $…$, text outside the dollars is plain text. With "
                                   "“Full LaTeX”, environments (align*, cases…) and packages work.")
        self.latex_edit.setFixedHeight(80)
        row = QHBoxLayout()
        row.addWidget(self.latex_edit)
        self.load_button = QPushButton("Load .tex…")
        self.load_button.setToolTip("Take the equation from a .tex file (its document body)")
        self.load_button.clicked.connect(self._load_tex)
        row.addWidget(self.load_button, 0, Qt.AlignmentFlag.AlignTop)
        form.addRow("Equation:", row)
        self.engine_check = QCheckBox("Full LaTeX (uses the LaTeX installation)")
        self.engine_check.setChecked(engine == "latex" and self._latex_ok)
        self.engine_check.setEnabled(self._latex_ok)
        self.engine_check.setToolTip(
            "Typeset with LaTeX itself (any environment, any package): needs TeX Live, MiKTeX or "
            "MacTeX. The result is saved as an SVG, so the figure opens anywhere."
            if self._latex_ok else
            "No LaTeX installation found (latex and dvisvgm from TeX Live, MiKTeX or MacTeX). "
            "Matplotlib's built-in LaTeX maths is used.")
        if self._latex_ok:
            form.addRow("", self.engine_check)
        else:
            engine_row = QHBoxLayout()
            engine_row.addWidget(self.engine_check)
            self.install_latex_button = QPushButton("Install LaTeX…")
            self.install_latex_button.setToolTip("Download TinyTeX (a small TeX Live, about 75 MB) "
                                                 "into your user folder")
            self.install_latex_button.clicked.connect(self._install_latex)
            engine_row.addWidget(self.install_latex_button)
            engine_row.addStretch(1)
            form.addRow("", engine_row)
        self.preamble_edit = QLineEdit(E.DEFAULT_PREAMBLE if preamble is None else preamble)
        self.preamble_edit.setToolTip(r"LaTeX packages and definitions, e.g. \usepackage{physics}")
        form.addRow("Preamble:", self.preamble_edit)
        self.latex_font_combo = QComboBox()
        self.latex_font_combo.setEditable(True)
        self.latex_font_combo.addItem(_LATEX_DEFAULT_FONT)
        for fam in ("Arial", "Helvetica", "Times New Roman", "Calibri", "Cambria"):
            self.latex_font_combo.addItem(fam)
        self.latex_font_combo.setCurrentText(font or _LATEX_DEFAULT_FONT)
        self.latex_font_combo.setToolTip(
            "Full LaTeX: an installed font for the text and for the letters, digits and Greek of "
            "the maths (XeLaTeX), e.g. the font of the figure's labels. Symbols and fraction bars "
            "stay Latin Modern.")
        form.addRow("LaTeX font:", self.latex_font_combo)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(4.0, 200.0)
        self.size_spin.setDecimals(1)
        self.size_spin.setSuffix(" pt")
        self.size_spin.setValue(float(font_size))
        form.addRow("Font size:", self.size_spin)
        self.fontset_combo = QComboBox()
        for key in E.FONTSETS:
            self.fontset_combo.addItem(_FONTSET_LABELS.get(key, key), key)
        self.fontset_combo.setCurrentIndex(max(0, list(E.FONTSETS).index(fontset)
                                               if fontset in E.FONTSETS else 0))
        form.addRow("Font:", self.fontset_combo)
        self.color_edit = QLineEdit(color)
        self.color_edit.setToolTip("A colour name (black, navy…) or #rrggbb")
        form.addRow("Colour:", self.color_edit)
        layout.addLayout(form)
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(90)
        frame_layout.addWidget(self.preview)
        layout.addWidget(frame)
        self.error = QLabel()
        self.error.setStyleSheet("color: #b00020;")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                        | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.update_preview)
        self.latex_edit.textChanged.connect(self._schedule)
        self.color_edit.textChanged.connect(self._schedule)
        self.preamble_edit.textChanged.connect(self._schedule)
        self.latex_font_combo.currentTextChanged.connect(self._schedule)
        self.size_spin.valueChanged.connect(self._schedule)
        self.fontset_combo.currentIndexChanged.connect(self._schedule)
        self.engine_check.toggled.connect(self._engine_changed)
        self._engine_changed()
        self.update_preview()

    def _engine_changed(self, *_):
        full = self.engine_check.isChecked()
        self.preamble_edit.setEnabled(full)
        self.latex_font_combo.setEnabled(full)
        self.fontset_combo.setEnabled(not full)        # LaTeX uses its own fonts
        self._schedule()

    def _install_latex(self, *_):
        from pyfigures.gui.latex_support import offer_latex_install
        if offer_latex_install(self, "Full LaTeX needs a LaTeX installation"):
            self._latex_ok = True
            self.engine_check.setEnabled(True)
            self.engine_check.setToolTip("Typeset with LaTeX itself (any environment, any package).")
            self.engine_check.setChecked(True)
            self.install_latex_button.hide()

    def _schedule(self, *_):
        # LaTeX takes about a second per run: wait until typing pauses
        self._timer.start(900 if self.engine_check.isChecked() else 250)

    def _load_tex(self):
        path, _ = QFileDialog.getOpenFileName(self, "Equation from a .tex file", "",
                                              "LaTeX (*.tex);;All files (*)")
        if path:
            self.load_tex(path)

    def load_tex(self, path):
        """Put the equation of the .tex file *path* in the editor."""
        try:
            text = E.read_tex_file(path)
        except (OSError, ValueError) as e:
            self.error.setText(str(e))
            return
        if not self.engine_check.isChecked():
            text = E.mathtext_formula(text)
        self.latex_edit.setPlainText(text)

    def values(self):
        return {"latex": self.latex_edit.toPlainText().strip(), "font_size": self.size_spin.value(),
                "color": self.color_edit.text().strip() or "black",
                "fontset": self.fontset_combo.currentData(),
                "engine": "latex" if self.engine_check.isChecked() else "mathtext",
                "preamble": self.preamble_edit.text(),
                "font": self._latex_font()}

    def _latex_font(self):
        text = self.latex_font_combo.currentText().strip()
        return None if not text or text == _LATEX_DEFAULT_FONT else text

    def update_preview(self):
        """Typeset the equation; show it, or the error and disable OK."""
        v = self.values()
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if not v["latex"]:
            self.preview.clear()
            self.error.setText("")
            ok_button.setEnabled(False)
            return False
        fd, tmp = tempfile.mkstemp(suffix=".svg")
        os.close(fd)
        if v["engine"] == "latex":
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            E.render_svg(v["latex"], tmp, v["font_size"], v["color"], v["fontset"],
                         v["engine"], v["preamble"], v["font"] if v["engine"] == "latex" else None)
            renderer = QSvgRenderer(tmp)
            size = renderer.defaultSize()
            # preview at twice the size, within the dialog
            scale = min(2.0, 500.0 / max(1, size.width()), 160.0 / max(1, size.height()))
            pm = QPixmap(max(1, int(size.width() * scale)), max(1, int(size.height() * scale)))
            pm.fill(QColor("white"))
            p = QPainter(pm)
            renderer.render(p)
            p.end()
            self.preview.setPixmap(pm)
            self.error.setText("")
            ok_button.setEnabled(True)
            return True
        except Exception as e:
            self.preview.clear()
            self.error.setText(str(e))
            ok_button.setEnabled(False)
            return False
        finally:
            if v["engine"] == "latex":
                QApplication.restoreOverrideCursor()
            if os.path.isfile(tmp):
                os.remove(tmp)
