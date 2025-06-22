import sys
import threading
import time

import sounddevice as sd
import soundfile as sf

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QSlider,
    QMessageBox, QStackedWidget, QLineEdit, QSpacerItem, QSizePolicy, QScrollBar, QSplitter
)
from PyQt6.QtGui import QPixmap, QFont, QIcon
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal

from ui.widgets import VolumePopupWidget
from utils.scanner import format_time


class OsuPlayerApp(QMainWindow):
    playback_finished = pyqtSignal()

    def __init__(self, song_library, icons):
        super().__init__()
        self.song_library = song_library
        
        # --- Player State ---
        self.current_song_index = -1
        self.is_paused = False
        self.is_muted = False
        self.volume = 0.75 # 0.0 to 1.0
        self.user_is_seeking = False
        self.is_dt_enabled = False
        self.shuffle_enabled = False
        self.repeat_mode = 0  # 0: No Repeat, 2: Repeat One
        self.shuffled_indices = []
        self.history = []

        self.playback_thread = None
        self.stop_playback_event = threading.Event()
        self.playback_lock = threading.Lock()

        # --- Audio Stream State ---
        self.stream = None
        self.audio_file = None
        self.samplerate = 0  # Native sample rate of the file
        self.current_playback_rate = 0 # Effective sample rate for playback
        self.current_frame = 0
        self.total_frames = 0
        self.last_volume = self.volume
        
        self.setWindowTitle("osu!radio")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(600, 500)
        
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.update_progress_bar)
        self.playback_finished.connect(self.handle_playback_finished)
        
        # --- Icons ---
        self.prev_icon = icons['prev']
        self.play_icon = icons['play']
        self.pause_icon = icons['pause']
        self.next_icon = icons['next']
        self.dt_icon = icons['dt_off']
        self.dt_icon_on = icons['dt_on']
        self.volume_icons = icons['volume']
        self.shuffle_icon = icons['shuffle_off']
        self.shuffle_icon_on = icons['shuffle_on']
        self.repeat_icon = icons['repeat_off']
        self.repeat_icon_one = icons['repeat_one']

        self.init_ui()
        self.apply_stylesheet()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # --- Новый основной вертикальный layout ---
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left Panel Stack ---
        self.left_panel_stack = QStackedWidget()

        # --- Welcome Widget (Cat) ---
        welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(welcome_widget)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ascii_cat = "  /\\_/\\  \n" \
                    " ( o.o ) \n" \
                    "  > ^ <  "
        self.cat_label = QLabel(ascii_cat)
        self.cat_label.setObjectName("catLabel")
        font = QFont("Courier New", 14)
        self.cat_label.setFont(font)
        self.cat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(self.cat_label)
        # --- Player Widget ---
        self.player_widget = QWidget()
        player_layout = QVBoxLayout(self.player_widget)
        player_layout.setContentsMargins(0, 12, 0, 12)
        player_layout.setSpacing(12)

        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(280, 280)
        self.cover_label.setObjectName("coverLabel")
        self.cover_label.setStyleSheet("background: #222;")
        
        # Контейнер для идеального центрирования обложки
        cover_container = QWidget()
        cover_h_layout = QHBoxLayout(cover_container)
        cover_h_layout.setContentsMargins(0,0,0,0)
        cover_h_layout.addStretch()
        cover_h_layout.addWidget(self.cover_label)
        cover_h_layout.addStretch()

        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.artist_label = QLabel()
        self.artist_label.setObjectName("artistLabel")
        self.artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bpm_label = QLabel()
        self.bpm_label.setObjectName("bpmLabel")
        self.bpm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # --- Controls Layout ---
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(20)
        controls_widget = QWidget()
        controls_widget.setLayout(controls_layout)
        self.shuffle_button = QPushButton()
        self.shuffle_button.setIcon(self.shuffle_icon)
        self.shuffle_button.setCheckable(True)
        self.shuffle_button.setObjectName("shuffleButton")
        self.prev_button = QPushButton()
        self.prev_button.setIcon(self.prev_icon)
        self.prev_button.setIconSize(QSize(32, 32))
        self.play_pause_button = QPushButton()
        self.play_pause_button.setIcon(self.play_icon)
        self.play_pause_button.setIconSize(QSize(36, 36))
        self.next_button = QPushButton()
        self.next_button.setIcon(self.next_icon)
        self.next_button.setIconSize(QSize(32, 32))
        self.repeat_button = QPushButton()
        self.repeat_button.setIcon(self.repeat_icon)
        self.repeat_button.setObjectName("repeatButton")
        self.prev_button.setObjectName("prevButton")
        self.play_pause_button.setObjectName("playPauseButton")
        self.next_button.setObjectName("nextButton")
        self.volume_popup = VolumePopupWidget(self.volume_icons)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.shuffle_button)
        controls_layout.addWidget(self.prev_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(self.repeat_button)
        controls_layout.addStretch(1)
        
        player_layout.addWidget(cover_container)
        player_layout.addWidget(self.title_label)
        player_layout.addWidget(self.artist_label)
        player_layout.addWidget(self.bpm_label)
        player_layout.addWidget(controls_widget)
        player_layout.addStretch(1)
        # --- Добавляем виджеты в левый стек ---
        self.left_panel_stack.addWidget(welcome_widget)
        self.left_panel_stack.addWidget(self.player_widget)
        
        # --- Right Panel (Song List and Search) ---
        right_panel_widget = QWidget()
        right_panel_widget.setObjectName("rightPanelWidget")
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(12, 12, 12, 12)
        right_panel_layout.setSpacing(10)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search songs...")
        self.search_bar.setObjectName("searchBar")
        self.song_list_widget = QListWidget()
        self.song_list_widget.setObjectName("songListWidget")
        self.song_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.song_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for song in self.song_library:
            self.song_list_widget.addItem(song['display_text'])
        # --- Внешний вертикальный скроллбар ---
        self.song_list_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.song_list_scrollbar.setObjectName("externalSongScrollBar")
        # Разделитель между списком и скроллбаром
        self.song_list_separator = QWidget()
        self.song_list_separator.setFixedWidth(4)
        self.song_list_separator.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #222, stop:0.25 #222, stop:0.25 transparent, stop:1 transparent);")
        # Контейнер для списка и скроллбара
        self.song_list_container = QWidget()
        self.song_list_container.setObjectName("songListContainer")
        song_list_hlayout = QHBoxLayout(self.song_list_container)
        song_list_hlayout.setContentsMargins(0, 0, 0, 0)
        song_list_hlayout.setSpacing(0)
        song_list_hlayout.addWidget(self.song_list_widget, 1)
        song_list_hlayout.addWidget(self.song_list_separator, 0)
        song_list_hlayout.addWidget(self.song_list_scrollbar, 0)
        # Синхронизация скроллбаров
        sbar = self.song_list_widget.verticalScrollBar()
        if sbar is not None:
            self.song_list_scrollbar.setMinimum(sbar.minimum())
            self.song_list_scrollbar.setMaximum(sbar.maximum())
            self.song_list_scrollbar.setPageStep(sbar.pageStep())
            self.song_list_scrollbar.setSingleStep(sbar.singleStep())
            sbar.valueChanged.connect(self.song_list_scrollbar.setValue)
            self.song_list_scrollbar.valueChanged.connect(sbar.setValue)
            sbar.rangeChanged.connect(lambda minv, maxv: self.song_list_scrollbar.setRange(minv, maxv))
        right_panel_layout.addWidget(self.search_bar)
        right_panel_layout.addWidget(self.song_list_container)
        
        # --- Splitter, который разделяет левую и правую панели ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setObjectName("mainSplitter")
        main_splitter.addWidget(self.left_panel_stack)
        main_splitter.addWidget(right_panel_widget)
        main_splitter.setStretchFactor(0, 0) # Левая панель не растягивается
        main_splitter.setStretchFactor(1, 1) # Правая панель растягивается
        main_splitter.setSizes([320, 480]) # Начальные размеры

        # --- Нижняя панель ---
        bottom_bar_widget = QWidget()
        bottom_bar_widget.setStyleSheet("background-color: #0a0a0c;")
        bottom_bar_layout = QHBoxLayout(bottom_bar_widget)
        bottom_bar_layout.setContentsMargins(0, 10, 0, 10)
        
        side_margin = 30
        bottom_bar_layout.addSpacerItem(QSpacerItem(side_margin, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))
        
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setMinimumWidth(48)
        self.current_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bottom_bar_layout.addWidget(self.current_time_label)
        bottom_bar_layout.addSpacing(12)
        
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setMinimumHeight(18)
        bottom_bar_layout.addWidget(self.progress_slider, 1)
        bottom_bar_layout.addSpacing(12)

        self.total_time_label = QLabel("00:00")
        self.total_time_label.setMinimumWidth(48)
        self.total_time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom_bar_layout.addWidget(self.total_time_label)
        
        # Правая группа контролов (громкость и DT)
        right_controls_layout = QHBoxLayout()
        right_controls_layout.setContentsMargins(0, 0, 0, 0)
        right_controls_layout.setSpacing(15)

        self.dt_button = QPushButton()
        self.dt_button.setIcon(self.dt_icon)
        self.dt_button.setIconSize(QSize(24, 24))
        self.dt_button.setCheckable(True)
        self.dt_button.setObjectName("dtButton")
        
        right_controls_layout.addWidget(self.volume_popup)
        right_controls_layout.addWidget(self.dt_button)

        bottom_bar_layout.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        bottom_bar_layout.addLayout(right_controls_layout)
        bottom_bar_layout.addSpacerItem(QSpacerItem(side_margin, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

        # --- Добавляем разделитель и нижнюю панель в основной layout ---
        main_layout.addWidget(main_splitter, 1)
        main_layout.addWidget(bottom_bar_widget)
        # --- Подключения сигналов ---
        self.search_bar.textChanged.connect(self.filter_song_list)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.next_button.clicked.connect(self.next_song)
        self.prev_button.clicked.connect(self.previous_song)
        self.shuffle_button.clicked.connect(self.toggle_shuffle)
        self.repeat_button.clicked.connect(self.toggle_repeat)
        self.song_list_widget.itemDoubleClicked.connect(self.play_selected_song_from_item)
        self.dt_button.clicked.connect(self.toggle_dt)
        self.progress_slider.sliderPressed.connect(self.slider_pressed)
        self.progress_slider.sliderReleased.connect(self.slider_released)
        self.progress_slider.sliderMoved.connect(self.update_time_label_on_drag)
        self.volume_popup.mute_toggled.connect(self.toggle_mute)
        self.volume_popup.volume_changed.connect(self.set_volume)
        # --- Initial State ---
        self.set_volume(int(self.volume * 100))
        self.set_controls_enabled(False)

    def set_controls_enabled(self, enabled):
        self.prev_button.setEnabled(enabled)
        self.play_pause_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)
        self.dt_button.setEnabled(enabled)
        self.progress_slider.setEnabled(enabled)
        self.volume_popup.setEnabled(enabled)
        self.shuffle_button.setEnabled(enabled)
        self.repeat_button.setEnabled(enabled)

        if not enabled:
            # Сброс состояния, когда нет активного трека
            self.shuffle_button.setChecked(False)
            self.shuffle_button.setIcon(self.shuffle_icon)
            self.repeat_mode = 0
            self.repeat_button.setIcon(self.repeat_icon)
            self.repeat_button.setProperty("class", "")
            style = self.repeat_button.style()
            if style:
                style.polish(self.repeat_button)

    def filter_song_list(self, text):
        for i in range(self.song_list_widget.count()):
            item = self.song_list_widget.item(i)
            if item:
                item.setHidden(text.lower() not in item.text().lower())

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
                font-family: 'Segoe UI', 'Arial';
            }
            QMainWindow {
                background-color: #222222;
            }
            QListWidget {
                background-color: #2c2c2c;
                border: 1px solid #444444;
                font-size: 14px;
                padding: 5px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QListWidget::item:selected {
                background-color: #ff66aa;
                color: #ffffff;
            }
            #coverLabel {
                border: 2px solid #444;
                background-color: #2c2c2c;
                margin-bottom: 5px; /* Отступ под обложкой */
            }
            #titleLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 0 10px;
                margin-top: 5px; /* Отступ над заголовком */
            }
            #artistLabel {
                font-size: 14px;
                color: #bbbbbb;
                padding: 0 10px;
            }
            #bpmLabel {
                font-size: 12px;
                color: #999999;
                padding: 0 10px;
                margin-bottom: 10px; /* Отступ под BPM перед кнопками */
            }
            #catLabel {
                color: #bbbbbb;
            }
            #searchBar {
                background-color: #2c2c2c;
                border: 1px solid #444444;
                border-radius: 0;
                font-size: 14px;
                padding: 8px;
            }
            #songListWidget {
                margin: 0;
                padding: 0;
            }
            QWidget#rightPanelWidget {
                padding: 0;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 5px;
            }
            QPushButton:hover:!disabled {
                color: #ff66aa;
            }
            #shuffleButton, #repeatButton {
                padding: 5px;
            }
            #shuffleButton:checked {
                background-color: #332b33;
            }
            #repeatButton.repeat-one {
                 background-color: #332b33;
            }
            #volumeButton {
                font-size: 20px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height:4px;
                background: #333333;
                margin: 1px 0;
            }
            QSlider::handle:horizontal {
                background: #ff66aa;
                border: 0px solid #ff66aa;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #ff66aa;
                border: 1px solid #444;
                height: 4px;
            }
            QSlider::groove:vertical {
                background: #ff66aa;
                width: 5px;
            }
            QSlider::handle:vertical {
                background: #ff66aa;
		        height: 14px;
		        width: 14px;
                min-height: 20px;
		        margin: 0 -5px ;
                border-radius: 7px;
            }
            QSlider::sub-page:vertical {
                background: #333333;
                width: 4px;
            }
            QSlider::add-page:vertical {
                background: #ff66aa;
                width: 4px;
            }
            
            QScrollBar:vertical {
                border: 1px solid #444;
                background: #2c2c2c;
                width: 14px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #ff66aa;
                min-height: 20px;
                border-radius: 0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }

            QScrollBar:horizontal {
                border: 1px solid #444;
                background: #2c2c2c;
                height: 14px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #ff66aa;
                min-width: 20px;
                border-radius: 0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            #dtButton {
                margin: 0 0 0 0;
                padding: 6px;
                background: none;
                background-color: transparent;
            }
            #dtButton:hover:!disabled {
                background-color: #232336;
                color: #ff66aa;
            }
            #progressBarWidget {
                background-color: #0a0a0c;
            }
            #progressBarWidget QLabel, #progressBarWidget QSlider {
                background-color: transparent;
            }
            #dtButtonContainer {
                background: none;
                background-color: transparent;
            }
            #songListWidget QScrollBar:horizontal {
                height: 0px;
            }
            #externalSongScrollBar {
                background-color: #18181b !important;
                border: none;
                width: 12px;
                min-width: 12px;
                max-width: 12px;
                margin: 0;
            }
            #externalSongScrollBar::handle {
                background: #ff66aa;
                min-height: 32px;
                margin: 2px;
                border-radius: 0;
            }
            #externalSongScrollBar::add-line, #externalSongScrollBar::sub-line {
                height: 0px;
                background: none;
                border: none;
            }
            #songListContainer {
                background: none;
            }
            QSplitter::handle:horizontal {
                background-color: #444;
                width: 1px;
                margin: 0px;
            }
        """)
        
    def slider_pressed(self):
        self.user_is_seeking = True

    def slider_released(self):
        if self.user_is_seeking:
            position_ms = self.progress_slider.value()
            self.set_music_position(position_ms)
            self.user_is_seeking = False

    def update_time_label_on_drag(self, position):
        self.current_time_label.setText(format_time(position))

    def set_volume(self, value): # value is 0-100 from slider
        self.volume = value / 100.0
        if not self.is_muted:
            self.last_volume = self.volume
            icon = self.volume_popup.volume_icon_high if value > 50 else self.volume_popup.volume_icon_med if value > 0 else self.volume_popup.volume_icon_low
            self.volume_popup.set_icon(icon)
        self.volume_popup.set_slider_position(value)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.volume_popup.set_icon(self.volume_popup.volume_icon_mute)
        else:
            current_volume_percent = int(self.last_volume * 100)
            icon = self.volume_popup.volume_icon_high if current_volume_percent > 50 else self.volume_popup.volume_icon_med if current_volume_percent > 0 else self.volume_popup.volume_icon_low
            self.volume_popup.set_icon(icon)
            self.volume = self.last_volume

    def toggle_dt(self):
        self.is_dt_enabled = self.dt_button.isChecked()
        self.dt_button.setIcon(self.dt_icon_on if self.is_dt_enabled else self.dt_icon)
        
        if self.stream and (self.stream.active or self.is_paused):
            # Calculate position in ms based on the rate that *was* being used for playback
            current_pos_ms = (self.current_frame / self.current_playback_rate) * 1000 if self.current_playback_rate > 0 else 0
            self.play_song(self.current_song_index, start_pos_ms=current_pos_ms)

    def update_duration_display(self, duration_ms):
        self.total_time_label.setText(format_time(duration_ms))
        self.progress_slider.setMaximum(int(duration_ms))

    def update_progress_bar(self):
        if self.stream and not self.user_is_seeking and self.current_playback_rate > 0:
            with self.playback_lock:
                position_ms = (self.current_frame / self.current_playback_rate) * 1000
                self.progress_slider.setValue(int(position_ms))
                self.current_time_label.setText(format_time(position_ms))

    def handle_playback_finished(self):
        if not self.is_paused and not self.user_is_seeking:
            # Если включен повтор одного трека, он будет обработан в play_song
            if self.repeat_mode == 2:
                self.play_song(self.current_song_index)
            else:
                self.next_song()

    def set_music_position(self, position_ms):
        if self.audio_file and self.current_playback_rate > 0:
            with self.playback_lock:
                self.current_frame = int((position_ms / 1000.0) * self.current_playback_rate)
                self.audio_file.seek(self.current_frame)

    def update_info_on_selection(self, index):
        if not (0 <= index < len(self.song_library)):
            return
            
        song_info = self.song_library[index]
        self.title_label.setText(song_info['title'])
        self.artist_label.setText(song_info['artist'])

        bpm_text = f"BPM: {song_info['bpm']}" if song_info.get('bpm') else ""
        if self.is_dt_enabled and song_info.get('bpm'):
             bpm_text += f" -> {round(song_info['bpm'] * 1.5)}"
        self.bpm_label.setText(bpm_text)

        if song_info['background_path']:
            pixmap = QPixmap(song_info['background_path'])
            self.cover_label.setPixmap(pixmap.scaled(
                280, 280,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            self.cover_label.clear()
            self.cover_label.setText("No Cover")
        
        self.song_list_widget.setCurrentRow(index)
    
    def _stop_current_playback(self):
        self.stop_playback_event.set()
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join()
        self.stop_playback_event.clear()

    def _audio_callback(self, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        with self.playback_lock:
            if self.is_paused or not self.audio_file:
                outdata.fill(0)
                return

            chunk = self.audio_file.read(frames, dtype='float32', always_2d=True)
            
            if len(chunk) == 0:
                outdata.fill(0)
                raise sd.CallbackStop # End of song

            # Apply volume
            volume = self.volume if not self.is_muted else 0.0
            chunk *= volume
            
            if chunk.shape[0] < frames:
                outdata[:len(chunk)] = chunk
                outdata[len(chunk):].fill(0)
            else:
                outdata[:] = chunk
            
            self.current_frame += len(chunk)

    def _playback_manager(self, start_pos_ms):
        try:
            if not self.audio_file:
                return

            with self.playback_lock:
                self.audio_file.seek(self.current_frame)

            self.stream = sd.OutputStream(
                samplerate=self.current_playback_rate, # Use the effective rate for playback
                channels=self.audio_file.channels,
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_paused = False
            self.play_pause_button.setIcon(self.pause_icon)

            # Keep the thread alive while the stream is active
            while not self.stop_playback_event.is_set() and self.stream.active:
                 time.sleep(0.1)

        except Exception as e:
            print(f"Error in playback thread: {e}")
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close(ignore_errors=True)
                self.stream = None
            if self.audio_file:
                self.audio_file.close()
                self.audio_file = None

            if not self.stop_playback_event.is_set():
                self.playback_finished.emit()

    def play_song(self, song_index: int, start_pos_ms: float = 0.0):
        if song_index == -1: # Сигнал остановки
            self._stop_current_playback()
            self.play_pause_button.setIcon(self.play_icon)
            self.set_controls_enabled(False)
            self.progress_slider.setValue(0)
            self.current_time_label.setText("00:00")
            return
        
        if not (0 <= song_index < len(self.song_library)):
            return

        # Обновление истории для shuffle
        if self.shuffle_enabled:
            # Удаляем из "будущего" (shuffled_indices), если трек там есть
            if song_index in self.shuffled_indices:
                self.shuffled_indices.remove(song_index)
            # Добавляем в историю, избегая дубликатов в конце
            if not self.history or self.history[-1] != song_index:
                 self.history.append(song_index)

        self._stop_current_playback()
        
        self.left_panel_stack.setCurrentWidget(self.player_widget)
        self.current_song_index = song_index
        song_info = self.song_library[song_index]
        
        try:
            self.audio_file = sf.SoundFile(song_info['audio_path'])
            self.samplerate = self.audio_file.samplerate
            self.total_frames = len(self.audio_file)
            
            # Setup playback rate for DT
            if self.is_dt_enabled:
                self.current_playback_rate = self.samplerate * 1.5
            else:
                self.current_playback_rate = self.samplerate

        except Exception as e:
            print(f"Error processing audio file: {e}")
            self._stop_current_playback()
            return
        
        duration_ms = (self.total_frames / self.current_playback_rate) * 1000 if self.current_playback_rate > 0 else 0
        self.update_info_on_selection(song_index)
        self.set_music_position(start_pos_ms)
        self.update_duration_display(duration_ms)
        
        self.set_controls_enabled(True)
        
        # Start playback manager in a new thread
        self.playback_thread = threading.Thread(target=self._playback_manager, args=(start_pos_ms,))
        self.playback_thread.daemon = True
        self.playback_thread.start()

        self.playback_timer.start(100)
    
    def toggle_play_pause(self):
        if not self.stream: # Not playing anything
            current_row = self.song_list_widget.currentRow()
            if current_row < 0 and self.song_library:
                current_row = 0
            if current_row >= 0:
                self.play_song(current_row)
            return

        if self.stream:
            if self.is_paused:
                self.is_paused = False
                self.play_pause_button.setIcon(self.pause_icon)
            else:
                self.is_paused = True
                self.play_pause_button.setIcon(self.play_icon)

    def play_selected_song_from_item(self, item):
        selected_index = self.song_list_widget.row(item)
        if self.shuffle_enabled:
            # При ручном выборе, перегенерируем плейлист,
            # чтобы он начинался с выбранного трека
            self.current_song_index = selected_index
            self.generate_shuffled_list()

        self.play_song(selected_index)

    def next_song(self):
        if self.current_song_index < 0: return
        next_index = self.get_next_song_index()
        self.play_song(next_index)

    def previous_song(self):
        if self.current_song_index < 0: return
        
        # Если трек играет больше 3 секунд, "назад" просто перезапускает его
        position_ms = (self.current_frame / self.current_playback_rate) * 1000 if self.current_playback_rate > 0 else 0
        if position_ms > 3000:
            self.play_song(self.current_song_index)
            return

        prev_index = self.get_previous_song_index()
        self.play_song(prev_index)

    def closeEvent(self, event):
        self._stop_current_playback()
        event.accept()

    def toggle_shuffle(self):
        self.shuffle_enabled = self.shuffle_button.isChecked()
        self.shuffle_button.setIcon(self.shuffle_icon_on if self.shuffle_enabled else self.shuffle_icon)
        if self.shuffle_enabled:
            self.generate_shuffled_list()
        else:
            # При отключении шаффла, сбрасываем историю и перемешанный плейлист
            self.shuffled_indices = []
            self.history = []

    def toggle_repeat(self):
        # 0: No Repeat, 2: Repeat One
        if self.repeat_mode == 0:
            self.repeat_mode = 2 # Turn on Repeat One
            self.repeat_button.setIcon(self.repeat_icon_one)
            self.repeat_button.setProperty("class", "repeat-one")
        else:
            self.repeat_mode = 0 # Turn off
            self.repeat_button.setIcon(self.repeat_icon)
            self.repeat_button.setProperty("class", "")
        
        # Обновление стиля
        style = self.repeat_button.style()
        if style:
            style.polish(self.repeat_button)

    def generate_shuffled_list(self):
        import random
        # Создаем список индексов, кроме текущей песни
        indices = list(range(len(self.song_library)))
        if self.current_song_index != -1:
            indices.pop(self.current_song_index)
        
        random.shuffle(indices)
        self.shuffled_indices = indices
        # Очищаем историю, но добавляем текущий трек как точку отсчета
        self.history = [self.current_song_index] if self.current_song_index != -1 else []

    def get_next_song_index(self):
        if not self.song_library:
            return -1

        if self.shuffle_enabled:
            if not self.shuffled_indices:
                # Если перемешанный список закончился, останавливаем воспроизведение
                return -1 
            
            if not self.shuffled_indices:
                 return -1

            next_index = self.shuffled_indices.pop(0)
            self.history.append(next_index)
            return next_index

        # Стандартная логика без shuffle
        if self.current_song_index == -1:
            return 0
        
        next_index = self.current_song_index + 1
        
        if next_index >= len(self.song_library):
            return -1 # Конец плейлиста
        return next_index

    def get_previous_song_index(self):
        if not self.song_library:
            return -1

        # В режиме shuffle "назад" возвращает к предыдущему треку в истории
        if self.shuffle_enabled:
            if len(self.history) > 1:
                current_song = self.history.pop()
                prev_song = self.history[-1]
                # Добавляем текущую песню в начало перемешанного списка, чтобы к ней можно было вернуться
                self.shuffled_indices.insert(0, current_song)
                return prev_song
            else:
                 # Если истории нет (например, первый трек в шаффл-сессии), то ничего не делаем
                return self.current_song_index
        
        # Стандартная логика
        prev_index = self.current_song_index - 1
        if prev_index < 0:
            return self.current_song_index # Остаемся на месте
        return prev_index
