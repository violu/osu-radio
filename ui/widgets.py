from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QSize, pyqtSignal

class VolumePopupWidget(QWidget):
    volume_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal()

    def __init__(self, icons_dict, parent=None):
        super().__init__(parent)

        self.volume_icon_high = icons_dict['high']
        self.volume_icon_med = icons_dict['med']
        self.volume_icon_low = icons_dict['low']
        self.volume_icon_mute = icons_dict['mute']

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)
        
        self.volume_button = QPushButton()
        self.volume_button.setObjectName("volumeButton")
        self.volume_button.setIcon(self.volume_icon_high)
        self.volume_button.setIconSize(QSize(24,24))

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(100)
        
        layout.addWidget(self.volume_button)
        layout.addWidget(self.volume_slider)
        
        self.volume_button.clicked.connect(self.mute_toggled.emit)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
    
    def set_icon(self, icon: QIcon):
        self.volume_button.setIcon(icon)

    def set_slider_position(self, value):
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(value)
        self.volume_slider.blockSignals(False)
