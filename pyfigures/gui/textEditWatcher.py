from batoolset.settings.global_settings import set_UI  # set the UI to qtpy
set_UI()
from pyfigures.gui.simple_text_editor import TextEditor
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from qtpy.QtCore import QObject, Signal, QEvent

class TextEditWatcher(QObject):
    # focusChanged = Signal(bool)
    textChanged = Signal()
    formatChanged = Signal()
    # textChangedByUser = Signal(bool)

    def __init__(self, text_edits, callback=None):
        super().__init__()
        if not text_edits:
            text_edits = []
        if not isinstance(text_edits, list):
            text_edits = [text_edits]
        self.text_edits = text_edits
        self.active_text_edit = None
        self.callback = callback
        for text_edit in self.text_edits:
            text_edit.installEventFilter(self)
            text_edit.formatChanged.connect(self.onFormatChanged)  # Connect to the formatChanged signal
            text_edit.textEdit.textChanged.connect(self.on_text_changed)  # Connect to the formatChanged signal
            # text_edit.focusChanged.connect(self.on_focus_changed)

    def get_associated_texts(self):
        return self.text_edits

    def eventFilter(self, obj, event):
        try:
            if obj in self.text_edits:
                if event.type() == QEvent.FocusIn:
                    self.active_text_edit = obj
                    self.focusChanged.emit(True)  # Emit True when a QTextEdit gains focus
                elif event.type() == QEvent.FocusOut:
                    self.active_text_edit = None
                    self.focusChanged.emit(False)  # Emit False when a QTextEdit loses focus
                # el
                elif event.type() in [QEvent.KeyPress, QEvent.KeyRelease]:
                    self.active_text_edit = obj
                    self.textChanged.emit()
                # print(event.type())
        except:
            pass
        return False

    def get_active_editor(self):
        return self.active_text_edit

    def on_focus_changed(self, has_focus):
        if has_focus:
            print(f"{self.active_text_edit} has focus")
        else:
            print("No QTextEdit has focus")

    def on_text_changed(self):
        if self.callback is not None:
            self.callback(self.active_text_edit)
        else:
            print(f"Text has changed in {self.active_text_edit}")

    def onFormatChanged(self):
        if self.callback is not None:
            self.callback(self.active_text_edit)
        else:
            print(f"Text format has changed in {self.active_text_edit}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.text_edit = TextEditor()
        self.text_edit2 = TextEditor()

        container = QWidget()  # Create a container widget
        layout = QVBoxLayout(container)  # Set layout on the container widget

        layout.addWidget(self.text_edit)
        layout.addWidget(self.text_edit2)



        self.setCentralWidget(container)  # Set the contdqsainer widget as central widget

        self.text_edit_watcher = TextEditWatcher([self.text_edit, self.text_edit2], self.on_text_changed)
        # self.text_edit_watcher.focusChanged.connect(self.on_focus_changed)
        # self.text_edit_watcher.textChanged.connect(self.on_text_changed)df sd
        # self.text_edit_watcher.formatChanged.connect(self.onFormatChanged)
        # self.text_edit_watcher.



    def on_text_changed(self, text_edit=None):
        print(f"Text has changed in {text_edit}")
        print('bob')
        # Do something else


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
