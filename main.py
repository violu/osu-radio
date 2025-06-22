import os
import sys
import json
import ctypes
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
import qtawesome as qta

from ui.main_window import OsuPlayerApp
from utils.config import get_songs_directory
from utils.scanner import scan_songs

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    app = QApplication(sys.argv)
    
    # --- Windows-specific taskbar icon fix ---
    if sys.platform == 'win32':
        myappid = 'mycompany.osuradio.1.0.0' # Arbitrary unique string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    qta.set_defaults(color_disabled='#555555')

    # --- Create Icons ---
    icons = {
        'prev': QIcon(resource_path("icons/previous.svg")),
        'play': QIcon(resource_path("icons/play.svg")),
        'pause': QIcon(resource_path("icons/pause.svg")),
        'next': QIcon(resource_path("icons/next.svg")),
        'dt_off': QIcon(resource_path("icons/dt_off.svg")),
        'dt_on': QIcon(resource_path("icons/dt_on.svg")),
        'volume': {
            'mute': QIcon(resource_path("icons/volume_mute.svg")),
            'low': QIcon(resource_path("icons/volume_low.svg")),
            'med': QIcon(resource_path("icons/volume_medium.svg")),
            'high': QIcon(resource_path("icons/volume_high.svg")),
        },
        'shuffle_off': QIcon(resource_path("icons/shuffle_off.svg")),
        'shuffle_on': QIcon(resource_path("icons/shuffle_on.svg")),
        'repeat_off': QIcon(resource_path("icons/repeat_off.svg")),
        'repeat_one': QIcon(resource_path("icons/repeat_one.svg")),
    }

    songs_dir = get_songs_directory()
    if not songs_dir:
        sys.exit(0)
        
    song_library = scan_songs(songs_dir)
    if not song_library:
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText("No songs found in the selected directory.")
        msg_box.setWindowTitle("Empty Library")
        msg_box.exec()

    main_win = OsuPlayerApp(song_library, icons)
    
    # --- Установка иконки приложения ---
    app_icon_path = resource_path("icons/app_icon.ico")
    if os.path.exists(app_icon_path):
        main_win.setWindowIcon(QIcon(app_icon_path))

    main_win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()