from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from pyfigures.gui.panelcreationwidget import PanelCreator
from qtpy.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QApplication,QLabel

class AsSingleOrPanel(QWidget):
    def __init__(self, parent=None, num_widgets=0):
        super().__init__(parent)



        self.panel_creator = PanelCreator(self,num_widgets)
        self.check_box = QCheckBox('As single images')

        self.check_box.stateChanged.connect(self.toggle_panel_creator)

        self.warning_label = QLabel("<font color=#FF0000>Warning: This can be slow. Please be patient.</font>")
        self.warning_label.setWordWrap(True)  # enable word wrapping

        layout = QVBoxLayout()
        layout.addWidget(self.check_box)
        layout.addWidget(self.panel_creator)
        layout.addWidget(self.warning_label)

        self.setLayout(layout)

    def toggle_panel_creator(self):
        self.panel_creator.setEnabled(not self.check_box.isChecked())

    def is_checkbox_selected(self):
        return self.check_box.isChecked()

if __name__ == '__main__':
    app = QApplication([])

    window = AsSingleOrPanel()
    window.show()

    app.exec_()