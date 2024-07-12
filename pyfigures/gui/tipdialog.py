from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QDialog, QPushButton, QHBoxLayout,QTextEdit,QCheckBox
import random

class TipDialog(QDialog):
    def __init__(self, parent=None, tips=[]):
        super().__init__(parent)
        self.tips = tips
        if not tips:
            self.close()
            return
        self.current_tip_index = 0
        self.setWindowTitle("Tips")
        # Create layout
        layout = QVBoxLayout(self)
        # Add tip text edit
        self.tip_text_edit = QTextEdit(self)
        self.tip_text_edit.setReadOnly(True)
        self.tip_text_edit.setHtml(self.tips[self.current_tip_index])
        layout.addWidget(self.tip_text_edit)
        # Add navigation and close buttons
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)
        self.previous_button = QPushButton("Previous Tip", self)
        self.previous_button.clicked.connect(self.show_previous_tip)
        button_layout.addWidget(self.previous_button)
        self.next_button = QPushButton("Next Tip", self)
        self.next_button.clicked.connect(self.show_next_tip)
        button_layout.addWidget(self.next_button)
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        # Add auto-show checkbox
        self.auto_show_checkbox = QCheckBox("Auto-show tips", self)
        self.auto_show_checkbox.setChecked(True)
        self.auto_show_checkbox.stateChanged.connect(self.toggle_auto_show)
        layout.addWidget(self.auto_show_checkbox)
        # Set up auto-show timer
        self.auto_show_timer = QTimer(self)
        self.auto_show_timer.timeout.connect(self.show_random_tip)
        self.auto_show_timer.start(16000)  # Show a random tip every 10 seconds

        self.setMinimumSize(700, 520)

    def show_next_tip(self):
        self.current_tip_index = (self.current_tip_index + 1) % len(self.tips)
        self.tip_text_edit.setHtml(self.tips[self.current_tip_index])
        self.auto_show_checkbox.setChecked(False)

    def show_previous_tip(self):
        self.current_tip_index = (self.current_tip_index - 1) % len(self.tips)
        self.tip_text_edit.setHtml(self.tips[self.current_tip_index])
        self.auto_show_checkbox.setChecked(False)

    def show_random_tip(self):
        random_index = random.randint(1, len(self.tips) - 1)  # Exclude the first tip
        self.current_tip_index = random_index
        self.tip_text_edit.setHtml(self.tips[self.current_tip_index])
    # def show_random_tip(self):
    #     remaining_tips = [tip for i, tip in enumerate(self.tips) if i != self.current_tip_index]
    #     if remaining_tips:
    #         random_tip = random.choice(remaining_tips)
    #         self.current_tip_index = self.tips.index(random_tip)
    #         self.tip_text_edit.setHtml(random_tip)

    def toggle_auto_show(self):
        if self.auto_show_checkbox.isChecked():
            self.auto_show_timer.start(8000)
        else:
            self.auto_show_timer.stop()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Your MainWindow setup code here

        # List of tips
        tips = [
            "Tip 1: Use the shortcut Ctrl+S to save your work.",
            "Tip 2: Press F1 to access the help menu.",
            "Tip 3: Use the 'About' menu to learn more about this software.",
            # Add more tips as needed
        ]

        # Show the TipDialog at launch (using a QTimer to avoid recursion)
        QTimer.singleShot(0, lambda: self.show_tip_dialog(tips))

    def show_tip_dialog(self, tips):
        tip_dialog = TipDialog(self, tips)
        tip_dialog.exec_()

if __name__ == "__main__":
    app = QApplication([])
    main_window = MainWindow()
    main_window.show()
    app.exec_()