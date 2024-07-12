from batoolset.settings.global_settings import set_UI
set_UI()
from qtpy.QtWidgets import QApplication
from batoolset.img import start_JVM
import sys
from pyfigures.gui.pfgui import EZFIG_GUI





def run_pyfigures():
    """
    Runs the PyFigures GUI.

    This function sets the UI and initializes the QApplication.
    The EPySeg PyFigures window is created and shown.
    The application event loop is started and the program exits
    when the GUI window is closed.

    # Examples:
    #     >>> run_pyfigures()
    """

    # start JVM to enable the bioformat image reader
    start_JVM()

    # Initialize the QApplication
    app = QApplication(sys.argv)

    if False:
        # just a trick to override the default cursor...
        from qtpy.QtGui import QCursor, QPixmap
        # Load a custom cursor image
        cursor_image = QPixmap("/home/aigouy/Téléchargements/cursor-mini.png")

        # Create a custom cursor object with the cursor image
        custom_cursor = QCursor(cursor_image)

        # Set the custom cursor globally for the application
        QApplication.setOverrideCursor(custom_cursor)

    # Create and show the PyFigures GUI window
    w = EZFIG_GUI()
    w.show()

    # Start the application event loop and exit when the GUI window is closed
    sys.exit(app.exec_())


if __name__ == '__main__':
    # Run the PyFigures GUI
    run_pyfigures()
