import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QSlider, QLabel, QStyle)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)

class PlayerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Video Display Area
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(300)
        self.media_player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget, 1)

        # Controls Bar
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 5, 10, 10)

        # Play/Pause Button
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self._toggle_playback)
        controls_layout.addWidget(self.play_btn)

        # Position Label (Current)
        self.pos_label = QLabel("00:00")
        self.pos_label.setStyleSheet("color: #cccccc; min-width: 50px;")
        controls_layout.addWidget(self.pos_label)

        # Seek Slider
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderMoved.connect(self._seek)
        controls_layout.addWidget(self.seek_slider, 1)

        # Duration Label
        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("color: #cccccc; min-width: 50px;")
        controls_layout.addWidget(self.duration_label)

        # Volume Slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._set_volume)
        controls_layout.addWidget(self.volume_slider)

        layout.addLayout(controls_layout)

    def _connect_signals(self):
        self.media_player.positionChanged.connect(self._update_position)
        self.media_player.durationChanged.connect(self._update_duration)
        self.media_player.playbackStateChanged.connect(self._update_play_button)

    def load_media(self, file_path: str):
        """Loads a media file for playback."""
        logger.info(f"Loading media: {file_path}")
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self._set_volume(self.volume_slider.value())

    def _toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _seek(self, position):
        self.media_player.setPosition(position)

    def _set_volume(self, value):
        self.audio_output.setVolume(value / 100.0)

    def _update_position(self, position):
        self.seek_slider.setValue(position)
        self.pos_label.setText(self._format_time(position))

    def _update_duration(self, duration):
        self.seek_slider.setRange(0, duration)
        self.duration_label.setText(self._format_time(duration))

    def _update_play_button(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def _format_time(self, ms):
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m:02d}:{s:02d}"
