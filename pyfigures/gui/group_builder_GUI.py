import sys
from qtpy import QtWidgets, QtCore
from batoolset.drawings.shapes.group import Group

def _orientation_icon(orientation):
    """Three boxes side by side (row) or one above the other (column)."""
    from qtpy.QtGui import QIcon
    from pyfigures.gui.drag_sketch import _OTHER, sketch_canvas
    from qtpy.QtGui import QPen
    pm, p = sketch_canvas()
    p.setPen(QPen(_OTHER.darker(140), 1))
    p.setBrush(_OTHER)
    for i in range(3):
        if orientation == 'X':
            p.drawRect(QtCore.QRectF(6 + i * 21, 16, 18, 16))
        else:
            p.drawRect(QtCore.QRectF(26, 3 + i * 14.5, 20, 12.5))
    p.end()
    return QIcon(pm)


class PanelOrRow(QtWidgets.QWidget):
    def __init__(self, group=None, hide_size=False):
        super().__init__()
        self.hide_size = hide_size
        self.group = group if isinstance(group, Group) else None
        self.init_ui()
        if isinstance(group, Group):
            # get the parameters and set them to the GUI
            space = group.space
            orientation = group.orientation
            self.space_spinbox.setValue(space)
            if orientation=='Y':
                self.orientation_combo.setCurrentIndex(1)
        self.show_preview()

    def init_ui(self):
        orientation_label = QtWidgets.QLabel("Orientation:")
        self.orientation_combo = QtWidgets.QComboBox()
        self.orientation_combo.setIconSize(QtCore.QSize(36, 24))
        for text, value in (("Row (side by side)", "X"), ("Column (one above the other)", "Y")):
            try:
                self.orientation_combo.addItem(_orientation_icon(value), text, value)
            except Exception:
                self.orientation_combo.addItem(text, value)
        self.orientation_combo.setCurrentIndex(0)  # Set default to 'X'

        # if not self.hide_size:
        size_label = QtWidgets.QLabel("Size:")
        self.size_spinbox = QtWidgets.QSpinBox()
        self.size_spinbox.setRange(1, 20000)  # Set the range of the spin box
        # self.size_spinbox.setMinimum(1)
        self.size_spinbox.setValue(512)  # Set default value

        space_label = QtWidgets.QLabel("Space:")
        self.space_spinbox = QtWidgets.QSpinBox()
        self.space_spinbox.setRange(0, 256)  # Set the range of the spin box
        self.space_spinbox.setValue(3)  # Set default value

        layout = QtWidgets.QGridLayout()
        layout.addWidget(orientation_label, 0, 0)
        layout.addWidget(self.orientation_combo, 0, 1)
        if not self.hide_size:
            layout.addWidget(size_label, 1, 0)
            layout.addWidget(self.size_spinbox, 1, 1)
        layout.addWidget(space_label, 2, 0)
        layout.addWidget(self.space_spinbox, 2, 1)

        # the group as it will look (only when editing a group of the figure)
        self.preview = QtWidgets.QLabel()
        self.preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview.setVisible(False)
        layout.addWidget(self.preview, 3, 0, 1, 2)
        self.orientation_combo.currentIndexChanged.connect(self.show_preview)
        self.space_spinbox.valueChanged.connect(self.show_preview)

        self.setLayout(layout)

    def show_preview(self, *args):
        """Sketch of the group with the orientation and space chosen."""
        if self.group is None:
            return
        try:
            from pyfigures.gui.drag_sketch import _clone, preview_pixmap, sketch
            from batoolset.drawings.shapes.group import set_to_width
            clone = _clone(self.group, {})
            if clone is None:
                return
            orientation, _size, space = self.get_parameters()
            clone.orientation = orientation
            clone.space = space
            clone.update()
            set_to_width(clone, self.group.width() or 512)
            icon = sketch([clone], set(), set())
            if icon is not None:
                self.preview.setPixmap(preview_pixmap(icon))
                self.preview.setVisible(True)
        except Exception:
            import traceback
            traceback.print_exc()       # the preview never blocks the dialog

    def get_parameters(self):
        orientation = self.orientation_combo.currentData() or self.orientation_combo.currentText()
        size = self.size_spinbox.value()
        space = self.space_spinbox.value()

        return orientation, size, space


def main():
    app = QtWidgets.QApplication(sys.argv)

    window = PanelOrRow()
    window.setWindowTitle("QtPy Example")
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
