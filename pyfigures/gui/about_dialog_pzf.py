from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import os
import sys

from qtpy.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton
from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices

# The standalone app bundles GPL/LGPL code (PyQt6, Qt, FFmpeg + x264/x265), so
# as a whole it is distributed under the GPLv3; installed with pip, PyFigures
# itself is BSD-2-Clause and only uses those libraries.
LICENSE_FROZEN = ("This application is distributed under the GNU General Public License v3, "
                  "because it includes PyQt6, Qt and FFmpeg; PyFigures' own source code is "
                  "BSD-2-Clause. It comes with ABSOLUTELY NO WARRANTY.")
LICENSE_PIP = ("PyFigures is BSD-2-Clause licensed. It uses PyQt6 (GPL v3) and Qt (LGPL v3). "
               "It comes with ABSOLUTELY NO WARRANTY.")


def third_party_licenses_path():
    """THIRD_PARTY_LICENSES.txt inside a standalone app (packaging/collect_licenses.py), else None."""
    if not getattr(sys, 'frozen', False):
        return None
    base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    path = os.path.join(base, 'third_party', 'THIRD_PARTY_LICENSES.txt')
    return path if os.path.isfile(path) else None


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

        # Licence, and in a standalone app the third-party licence texts
        licenses_path = third_party_licenses_path()
        license_label = QLabel(LICENSE_FROZEN if getattr(sys, 'frozen', False) else LICENSE_PIP, self)
        license_label.setWordWrap(True)
        layout.addWidget(license_label)
        if licenses_path:
            licenses_button = QPushButton("Third-party licences…", self)
            licenses_button.clicked.connect(
                lambda *_: QDesktopServices.openUrl(QUrl.fromLocalFile(licenses_path)))
            layout.addWidget(licenses_button)
        self.licenses_path = licenses_path

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
    import sys
    main()
    sys.exit(0)