from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtWidgets import QApplication, QWidget, QPushButton, QFontDialog, QVBoxLayout,QCheckBox
from qtpy.QtGui import QFont
import sys

class FontSelector(QWidget):
    def __init__(self):
        super().__init__()

        self.font_button = QPushButton('Select Font', self)
        self.font_button.clicked.connect(self.choose_font)

        self.font = QFont('Arial', 12, QFont.Normal)

        self.keep_original_size = QCheckBox('Keep original text size', self)
        self.keep_original_size.setChecked(True)

        self.keep_original_weight = QCheckBox('Keep original font weight', self)
        self.keep_original_weight.setChecked(True)

        self.keep_original_style = QCheckBox('Keep original font style', self)
        self.keep_original_style.setChecked(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.font_button)
        layout.addWidget(self.keep_original_size)
        layout.addWidget(self.keep_original_weight)
        layout.addWidget(self.keep_original_style)

    def choose_font(self):
        font_dialog = QFontDialog(self)
        font_dialog.setCurrentFont(self.font)
        if font_dialog.exec_():
            self.font = font_dialog.selectedFont()
            # print(f'Selected font: {self.font.family()}, {self.font.pointSize()}, {self.font.weight()}, {self.font.italic()}')

    def get_font(self):
        # by default we ignore bold/italic from font-−> keep default
        clean_font = QFont()  # we will only keep size and font name and ignore the bold and italic and alike stuff
        clean_font.setFamily(self.font.family())  #

        if not self.keep_original_size.isChecked():
            clean_font.setPointSize(self.font.pointSize()) # ignore size

        if not self.keep_original_weight.isChecked():
            clean_font.setWeight(self.font.weight())  # Set the font weight if not keeping original weight

        if not self.keep_original_style.isChecked():
            clean_font.setItalic(self.font.italic())  # Set the font italic if not keeping original style
            clean_font.setUnderline(self.font.underline())  # Set underline style if needed

        return clean_font

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = FontSelector()
    window.show()
    sys.exit(app.exec_())
