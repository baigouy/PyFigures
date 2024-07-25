from qtpy import QtWidgets, QtCore
from qtpy.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, QApplication, QWidget,QFrame)
from qtpy.QtCore import Qt,Signal

from batoolset.pyqts.tools import disable_wheel_for_combo_and_spin


# from batoolset.pyqts.tools import disable_wheel_for_widget_and_children


class CustomDialog(QDialog):
    option_selected = Signal(str)
    accepting_keywords = ["yes", "ok", "done", "validate", "y"]
    rejecting_keywords = ["no", "cancel", "quit", "abandon", "reject", "stop", "n", "q"]

    def __init__(self, title="Custom Dialog", message="Do you want to proceed?", main_widget=None, parent=None, options=None, add_separator=True, auto_adjust=False, reset_style_sheet=True):
        super().__init__(parent)

        if reset_style_sheet:
            # self.setStyleSheet("") # make sure to reset style sheet # this doesn't work
            self.setStyleSheet("background-color: none;") # make sure to reset style sheet
            # main_widget.setStyleSheet("")
            main_widget.setStyleSheet("background-color: none;")

        # self.setStyleSheet("background-color: lightblue;")

        # Set the object name for the widget
        # self.setObjectName("VectorialDrawPane2")

        # Set the background color
        # if background is not None:
        # self.setStyleSheet("") # prevent it from getting the style sheet of the parent

        # Set the window flags to stay on top
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.setWindowTitle(title)

        self.main_widget = main_widget

        layout = QVBoxLayout()
        if main_widget:
            # main_widget.setStyleSheet("") # also reset style sheet of content
            layout.addWidget(main_widget)

        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        if message:
            label = QLabel(message)
            layout.addWidget(label)

        if options is None:
            options = ["Yes", "No"]

        if isinstance(options, str):
            options=[options]

        for option in options:
            button = QPushButton(option)
            button.setFocusPolicy(Qt.NoFocus)# prevent auto selection from buttons
            layout.addWidget(button)
            button.clicked.connect(lambda _, opt=option: self.handle_option_clicked(opt))

        self.setLayout(layout)

        # disable_wheel_for_widget_and_children(self)

        # disable_wheel_for_combo_and_spin(self.main_widget)
        # disable_wheel_for_combo_and_spin(self.main_widget)

        if not auto_adjust:
            try:
                try:
                    # Get the screen where the application is currently displayed
                    screen = self.screen()
                    if screen is not None:
                        screen_geometry = screen.geometry()
                    else:
                        # If the application is not displayed on any screen, use the primary screen
                        screen_geometry = QtWidgets.QApplication.primaryScreen().geometry()
                except:
                    try:
                        from qtpy.QtGui import QGuiApplication
                        screen_geometry = QGuiApplication.primaryScreen().geometry()
                    except:
                        pass  # no big deal if all fails...
                # Set width and height to 75% of the screen size
                width = int(screen_geometry.width() * 0.85)
                height = int(screen_geometry.height() * 0.85)
                self.resize(width, height)
            except:
                pass  # no big deal if it fails...
        else:
            # force the window to assume the smallest minimum size can be very useful when min size is set
            self.adjustSize()

    def handle_option_clicked(self, option):
        self.selected_option = option
        if option.lower() in CustomDialog.accepting_keywords:
            self.accept()  # Close the dialog with QDialog.Accepted status
        elif option.lower() in CustomDialog.rejecting_keywords:
            self.reject()  # Close the dialog with QDialog.Rejected status
        else:
            self.accept()  # Close the dialog with QDialog.Accepted status

    # def exec_(self):
    #     result = super().exec_()
    #     if result == QDialog.Accepted:
    #         return self.selected_option
    #     else:
    #         return None

    def get_selected_answer(self):
        return self.selected_option

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    options = ["Option 1", "Option 2", "Option 3", "No"] # None
    options = "Done"
    message = "Do you want to proceed?" # "Do you want to proceed?" # None
    auto_adjust = True # force the window to take minimal size if used (calls adjustsize)
    custom_dialog = CustomDialog(title="Custom Dialog", message=message , main_widget=QWidget(), options=options, auto_adjust=auto_adjust)
    custom_dialog.option_selected.connect(lambda option: print(f"Selected option: {option}"))
    selected_option = custom_dialog.exec_()
    print(selected_option)
    if selected_option:
        print(f"Selected option: {selected_option}")
        print(custom_dialog.selected_option)
    else:
        print("Dialog was closed without selecting an option.")
