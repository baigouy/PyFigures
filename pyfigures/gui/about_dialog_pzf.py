from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton
from qtpy.QtCore import Qt
import sys

class AboutDialog(QDialog):
    def __init__(self, parent=None, title="About My Software", name="My Software", version="Version 1.0.0", description="""
        This is a brief description of My Software.
        You can provide more information about its features and functionality here.
        """, copyright="© 2023 Your Name", email='benoit.aigouy@gmail.com', ok_or_close="Ok"):
        super().__init__(parent)

        # Set dialog properties
        self.setWindowTitle(title)
        self.setMinimumWidth(400)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # Add application icon (optional)
        # icon_label = QLabel(self)
        # icon_label.setPixmap(QPixmap("path/to/your/icon.png")))
        # layout.addWidget(icon_label)

        # Add application name and version
        name_label = QLabel(name, self)
        name_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(name_label)

        version_label = QLabel(version, self)
        layout.addWidget(version_label)

        # Add description
        description_label = QLabel(description, self)
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        # Add email label
        email_label = QLabel(email, self)
        email_label.setStyleSheet("font-weight: bold; color: blue;")
        email_label.setOpenExternalLinks(True)
        email_link = f'<a href="mailto:{email}">{email}</a>'
        email_label.setText(email_link)
        layout.addWidget(email_label)


        # Add copyright and attribution
        copyright_label = QLabel(copyright, self)
        layout.addWidget(copyright_label)

        # Add close button
        close_button = QPushButton(ok_or_close, self)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        self.adjustSize()

def main():
    app = QApplication([])

    # Show the About dialog
    about_dialog = AboutDialog()
    about_dialog.exec_()

if __name__ == '__main__':
    main()