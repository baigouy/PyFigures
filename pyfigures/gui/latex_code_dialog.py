"""Dialog to write a LaTeX code panel (pyfigures.latex_document.latex_code_pdf):
TikZ / pgfplots pictures, tables, maths or a whole document, with a preview
compiled on request."""
from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtGui import QFont, QImage, QPixmap
from qtpy.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
                            QLabel, QPlainTextEdit, QPushButton, QVBoxLayout)

EXAMPLES = {
    "TikZ picture": "\\begin{tikzpicture}\n"
                    "  \\draw[->] (0,0) -- (3,0) node[right] {$t$};\n"
                    "  \\draw[->] (0,0) -- (0,2) node[above] {$F$};\n"
                    "  \\draw[blue, thick, domain=0:2.8] plot (\\x, {1.5*exp(-\\x)});\n"
                    "\\end{tikzpicture}",
    "pgfplots plot": "\\begin{tikzpicture}\n"
                     "\\begin{axis}[width=6cm, xlabel={$t$ (s)}, ylabel={$\\Delta F/F_0$}]\n"
                     "  \\addplot[blue, thick, domain=0:5] {exp(-x)};\n"
                     "\\end{axis}\n"
                     "\\end{tikzpicture}",
    "Table": "\\begin{tabular}{lrr}\n"
             "  \\toprule\n"
             "  Strain & $n$ & Speed (\\si{\\micro\\metre\\per\\second}) \\\\\n"
             "  \\midrule\n"
             "  WT & 12 & $0.42 \\pm 0.05$ \\\\\n"
             "  mutant & 9 & $0.21 \\pm 0.04$ \\\\\n"
             "  \\bottomrule\n"
             "\\end{tabular}",
    "Whole document": "\\documentclass{article}\n"
                      "\\usepackage{tikz}\n"
                      "\\begin{document}\n"
                      "\\begin{tikzpicture}\\draw[red, thick] (0,0) circle (1);\\end{tikzpicture}\n"
                      "\\end{document}",
}


class LatexCodeDialog(QDialog):
    """Write or edit the LaTeX code of a panel. A snippet gets amsmath,
    siunitx, booktabs, tikz and pgfplots; a whole document keeps its own
    preamble."""

    def __init__(self, parent=None, code=""):
        super().__init__(parent)
        self.setWindowTitle("LaTeX code panel")
        self.setMinimumSize(640, 480)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Start from:"))
        self.example_combo = QComboBox()
        self.example_combo.addItem("—")
        self.example_combo.addItems(list(EXAMPLES))
        self.example_combo.activated.connect(self._use_example)
        top.addWidget(self.example_combo)
        top.addStretch(1)
        self.preview_button = QPushButton("Preview")
        self.preview_button.setToolTip("Compile the code with LaTeX and show the result")
        self.preview_button.clicked.connect(self.update_preview)
        top.addWidget(self.preview_button)
        from batoolset.latex_tools import latex_available
        self.install_button = None
        if not latex_available():
            self.install_button = QPushButton("Install LaTeX…")
            self.install_button.clicked.connect(self._install_latex)
            top.addWidget(self.install_button)
        layout.addLayout(top)
        self.code_edit = QPlainTextEdit(code or EXAMPLES["TikZ picture"])
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_edit.setFont(font)
        self.code_edit.setToolTip("LaTeX code: a tikzpicture, a tabular, maths… (packages: amsmath, "
                                  "siunitx, booktabs, tikz, pgfplots), or a whole document "
                                  "(\\documentclass…) with its own preamble.")
        layout.addWidget(self.code_edit, 3)
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        self.preview = QLabel("Press Preview to compile")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(140)
        frame_layout.addWidget(self.preview)
        layout.addWidget(frame, 2)
        self.error = QLabel()
        self.error.setStyleSheet("color: #b00020;")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                        | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _use_example(self, index):
        name = self.example_combo.itemText(index)
        if name in EXAMPLES:
            self.code_edit.setPlainText(EXAMPLES[name])

    def _install_latex(self, *_):
        from pyfigures.gui.latex_support import offer_latex_install
        if offer_latex_install(self, "A LaTeX code panel is compiled by LaTeX"):
            self.install_button.hide()

    def code(self):
        return self.code_edit.toPlainText().strip()

    def update_preview(self, *_):
        """Compile the code and show it (errors below)."""
        from pyfigures.latex_document import latex_code_pdf
        self.error.setText("")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            pdf = latex_code_pdf(self.code())
        except ValueError as e:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("")
            self.error.setText(str(e))
            return False
        finally:
            QApplication.restoreOverrideCursor()
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(pdf)
            try:
                page = doc[0]
                w = page.get_width()
                scale = min(4.0, max(0.5, 560.0 / max(w, 1.0)))
                pil = page.render(scale=scale).to_pil().convert("RGBA")
            finally:
                doc.close()
            data = pil.tobytes("raw", "RGBA")
            img = QImage(data, pil.width, pil.height, QImage.Format.Format_RGBA8888).copy()
            self.preview.setPixmap(QPixmap.fromImage(img))
        except Exception as e:
            self.preview.setText(f"(compiled; no preview: {e})")
        return True
