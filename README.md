# osu!radio

A lightweight and modern music player designed specifically for your collection of osu! songs.



## Features

- **Automatic Song Scanning:** Automatically finds and processes songs from your osu! "Songs" directory.
- **Blazing-Fast Caching:** Subsequent launches are instant thanks to an intelligent caching system that detects changes to your songs folder.
- **Full Playback Control:** Standard controls including play, pause, next, and previous song.
- **Playback Modes:**
    - **Shuffle:** Play your songs in a random order.
    - **Repeat:** Loop your favorite track endlessly.
    - **Double Time (DT):** Listen to any track at 1.5x speed.
- **Search:** Quickly find any song in your library with a real-time search filter.
- **Modern Interface:** A clean, sleek, and intuitive UI built with Python and Qt6.

## Getting Started

To run the player from the source code, follow these steps.

### Prerequisites

- Python 3.8+
- An osu! installation with some beatmaps

### Installation

1.  **Clone the repository:**
    *(Replace `YOUR_USERNAME` with your actual GitHub username)*
    ```bash
    git clone https://github.com/YOUR_USERNAME/osu-radio.git
    cd osu-radio
    ```

2.  **Install dependencies:**
    It's highly recommended to use a virtual environment.
    ```bash
    # Create and activate a virtual environment (optional)
    python -m venv venv
    .\venv\Scripts\activate  # On Windows

    # Install the required packages
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    python main.py
    ```
    On the first launch, the player will ask you to locate your osu! "Songs" directory. This path is then saved in `config.json`.

## Building from Source

You can build a standalone `.exe` file for Windows using PyInstaller.

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller pyinstaller-hooks-contrib
    ```

2.  **Run the build command:**
    Execute the following command from the project root. It will create a single executable file in the `dist` folder.
    ```bash
    pyinstaller --name "osu!radio" --onefile --windowed --icon="icons/app_icon.ico" --add-data "icons;icons" main.py
    ```

---
*This project was developed with the assistance of an AI pair programmer.* 
