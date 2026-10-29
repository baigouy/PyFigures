# exit codes are recorded from here on, for the Qt-teardown guard that a
# headless tool may arm later (pyfigures/qt_exit.py)
from pyfigures.qt_exit import install_recorder as _install_recorder

_install_recorder()

# extras the user installed into a standalone app (e.g. PyMuPDF) become importable
from pyfigures.extras import enable_extras as _enable_extras

_enable_extras()
