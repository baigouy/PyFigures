# in fact there will just be two possibilities --> either default/acquisition or a chosen LUT
from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from batoolset.luts.lut_minimal_test import list_available_luts, PaletteCreator, invert_lut_name, is_inverted_lut
from batoolset.pyqts.tools import get_items_of_combo
import numpy as np
from qtpy.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox, QLabel, QCheckBox
from qtpy.QtGui import QPixmap, QImage, QIcon
from qtpy.QtCore import Qt, QSize

ACQUISITION = 'Default/Acquisition'
_RAMPS = {}                     # LUT name -> its 256 x 3 colours, made once per session


def lut_colours(name, lutcreator=None, available=None):
    """The 256 RGB colours of a LUT key (cached), or None for the acquisition colour."""
    if not name or 'cquisi' in name:
        return None
    if name not in _RAMPS:
        lutcreator = lutcreator or PaletteCreator()
        available = available if available is not None else lutcreator.list
        _RAMPS[name] = np.asarray(lutcreator.create3(available[name]), dtype=np.uint8)[:256, :3]
    return _RAMPS[name]


def ramp_pixmap(colours, width=256, height=16):
    """A horizontal colour ramp of a LUT, as a pixmap."""
    row = np.ascontiguousarray(colours[np.linspace(0, 255, width).astype(int)])
    strip = np.ascontiguousarray(np.repeat(row[np.newaxis], height, axis=0))
    image = QImage(strip.data, width, height, 3 * width, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class LutWidget(QWidget):
    """One LUT per channel. Each list entry shows its colour ramp; under it, the
    chosen LUT's ramp and an Invert box (Fiji's Invert LUT: GRAY <-> GRAY_INVERTED,
    a matplotlib map <-> its _r twin). The inversion is part of the stored LUT name."""

    def __init__(self, nb_channels, parent=None, user_specified_luts=None):
        super().__init__(parent)

        self.all_LUTs = []
        self.invert_boxes = []
        self.previews = []
        self.nb_channels=nb_channels

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.available_luts = list_available_luts()
        self.lutcreator = PaletteCreator()

        for ch in range(nb_channels):
            channel_box = QGroupBox(f"Channel {ch}")
            channel_layout = QVBoxLayout()

            lut_combo = QComboBox()
            lut_combo.setIconSize(QSize(64, 12))
            lut_combo.addItem(ACQUISITION)
            for lll, lut in enumerate(self.available_luts):  # Skip the first LUT as it's 'Default/Acquisition'
                if lll == 0:
                    continue
                lut_combo.addItem(self._icon(lut), lut)

            # we try to reload previous LUT if it exists
            if user_specified_luts and len(user_specified_luts) == self.nb_channels and user_specified_luts[ch]:
                for iii, pos in enumerate(get_items_of_combo(lut_combo)):
                    if pos.lower().strip() == user_specified_luts[ch].lower().strip():
                        lut_combo.setCurrentIndex(iii)
                        break

            invert = QCheckBox('Invert')
            invert.setToolTip('Invert this LUT (dark signal on a light background for GRAY)')
            preview = QLabel()
            preview.setFixedSize(256, 16)

            lut_combo.currentIndexChanged.connect(lambda idx, combo=lut_combo: self.updateLabel(combo))
            invert.toggled.connect(lambda on, combo=lut_combo: self.set_inverted(combo, on))

            self.all_LUTs.append(lut_combo)
            self.invert_boxes.append(invert)
            self.previews.append(preview)
            row = QHBoxLayout()
            row.addWidget(lut_combo, 1)
            row.addWidget(invert)
            channel_layout.addLayout(row)
            channel_layout.addWidget(preview)
            channel_box.setLayout(channel_layout)
            layout.addWidget(channel_box)
            self.sync_channel(ch)

        preview_box = QGroupBox(f"Preview")
        preview_box_layout = QVBoxLayout()
        self.label = QLabel()
        self.label.setFixedSize(256,32)
        preview_box_layout.addWidget(self.label)
        preview_box.setLayout(preview_box_layout)
        layout.addWidget(preview_box)
        if self.all_LUTs:
            self.updateLabel(self.all_LUTs[-1])

    def _icon(self, lut):
        try:
            return QIcon(ramp_pixmap(lut_colours(lut, self.lutcreator, self.lutcreator.list), 64, 12))
        except Exception:
            return QIcon()                       # a LUT that cannot be drawn is still listed

    def sync_channel(self, ch):
        """The channel's ramp and Invert box follow its chosen LUT."""
        combo, invert, preview = self.all_LUTs[ch], self.invert_boxes[ch], self.previews[ch]
        lut = combo.currentText()
        invert.blockSignals(True)
        invert.setChecked(is_inverted_lut(lut))
        invert.setEnabled(invert_lut_name(lut, self.available_luts) is not None)
        invert.blockSignals(False)
        colours = lut_colours(lut, self.lutcreator, self.lutcreator.list)
        preview.setPixmap(ramp_pixmap(colours, 256, 16) if colours is not None else QPixmap())
        preview.setToolTip(lut)

    def set_inverted(self, combo, on):
        lut = combo.currentText()
        if is_inverted_lut(lut) != on:
            twin = invert_lut_name(lut, self.available_luts)
            if twin:
                combo.setCurrentText(twin)

    def updateLabel(self, combo):
        if combo in self.all_LUTs:
            self.sync_channel(self.all_LUTs.index(combo))
        colours = lut_colours(combo.currentText(), self.lutcreator, self.lutcreator.list)
        self.label.setPixmap(ramp_pixmap(colours, 256, 32) if colours is not None else QPixmap())

    def getAllLuts(self):
        all_luts = [lut.currentText() if not 'cquisi' in lut.currentText() else None for lut in self.all_LUTs ]
        return all_luts

if __name__ == '__main__':
    from qtpy.QtWidgets import QApplication

    # Create a sample image with shape (512, 512, 3)
    image = np.random.randint(0, 256, size=(512, 512, 3), dtype=np.uint8)

    # Create a QApplication instance
    app = QApplication([])

    specified_luts = [None, None, 'DNA'] # simulate existing channels
    # Create a LutWidget instance
    lut_widget = LutWidget(nb_channels=image.shape[-1], user_specified_luts=specified_luts)

    # Show the LutWidget instance
    lut_widget.show()

    print(lut_widget.getAllLuts())

    # Run the QApplication event loop
    app.exec_()
