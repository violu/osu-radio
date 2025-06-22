import os
import json
from PyQt6.QtWidgets import QFileDialog, QMessageBox

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_songs_directory(parent=None):
    config = load_config()
    songs_dir = config.get('songs_directory')

    if not songs_dir or not os.path.exists(songs_dir):
        songs_dir = QFileDialog.getExistingDirectory(
            parent,
            "Select your osu! 'Songs' folder",
            os.path.expanduser("~") 
        )
        if songs_dir:
            config['songs_directory'] = songs_dir
            save_config(config)
        else:
            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setText("No folder selected. The application will now close.")
            msg_box.setWindowTitle("Error")
            msg_box.exec()
            return None
    return songs_dir
