"""Dialog to type a LaTeX equation, with a live preview (see pyfigures.equations)."""
from __future__ import annotations

import os
import tempfile

from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QPixmap, QPainter, QColor
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                            QFrame, QLabel, QLineEdit, QVBoxLayout)

from pyfigures import equations as E

_FONTSET_LABELS = {"cm": "Computer Modern (LaTeX)", "stix": "STIX (Times-like)",
                   "stixsans": "STIX sans", "dejavusans": "DejaVu Sans",
                   "dejavuserif": "DejaVu Serif"}


class EquationDialog(QDialog):
    """Returns its settings via values() after exec(): latex, font_size, color, fontset."""

    def __init__(self, parent=None, latex="", font_size=12.0, color="black", fontset="cm"):
        super().__init__(parent)
        self.setWindowTitle("Equation (LaTeX)")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.latex_edit = QLineEdit(latex)
        self.latex_edit.setPlaceholderText(r"e.g. \Delta F/F_0 = \frac{F - F_0}{F_0}")
        self.latex_edit.setToolTip("LaTeX mathematics (a LaTeX subset typeset by Matplotlib — no TeX "
                                   "installation needed). Without $…$ the whole text is a formula; "
                                   "with $…$, text outside the dollars is plain text.")
        form.addRow("Equation:", self.latex_edit)
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
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.update_preview)
        for sig in (self.latex_edit.textChanged, self.color_edit.textChanged):
            sig.connect(lambda *_: self._timer.start())
        self.size_spin.valueChanged.connect(lambda *_: self._timer.start())
        self.fontset_combo.currentIndexChanged.connect(lambda *_: self._timer.start())
        self.update_preview()

    def values(self):
        return {"latex": self.latex_edit.text().strip(), "font_size": self.size_spin.value(),
                "color": self.color_edit.text().strip() or "black",
                "fontset": self.fontset_combo.currentData()}

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
        try:
            E.render_svg(v["latex"], tmp, v["font_size"], v["color"], v["fontset"])
            renderer = QSvgRenderer(tmp)
            size = renderer.defaultSize()
            # preview at twice the size, within the dialog
            scale = min(2.0, 480.0 / max(1, size.width()), 160.0 / max(1, size.height()))
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
            if os.path.isfile(tmp):
                os.remove(tmp)
