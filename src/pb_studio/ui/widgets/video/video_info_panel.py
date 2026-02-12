"""
Video Info Panel for PB Studio AMD.

Displays video metadata in a clean, organized panel.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Data class for video metadata."""
    duration: float = 0.0           # Seconds
    width: int = 0                  # Pixels
    height: int = 0                 # Pixels
    fps: float = 0.0                # Frames per second
    codec: str = ""                 # Video codec (e.g., "h264", "hevc")
    has_audio: bool = False         # Audio track present
    audio_codec: str = ""           # Audio codec (e.g., "aac")
    audio_channels: int = 0         # Audio channels
    audio_sample_rate: int = 0      # Hz
    bitrate: int = 0                # Total bitrate in bits/s
    file_size: int = 0              # Bytes
    container: str = ""             # Container format (e.g., "mp4")

    @property
    def resolution_str(self) -> str:
        """Format resolution as string."""
        if self.width and self.height:
            # Common resolution names
            if self.width == 1920 and self.height == 1080:
                return "1920x1080 (1080p)"
            elif self.width == 3840 and self.height == 2160:
                return "3840x2160 (4K)"
            elif self.width == 1280 and self.height == 720:
                return "1280x720 (720p)"
            elif self.width == 2560 and self.height == 1440:
                return "2560x1440 (1440p)"
            return f"{self.width}x{self.height}"
        return "Unknown"

    @property
    def duration_str(self) -> str:
        """Format duration as HH:MM:SS."""
        if self.duration <= 0:
            return "00:00:00"
        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        seconds = int(self.duration % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @property
    def file_size_str(self) -> str:
        """Format file size with appropriate unit."""
        if self.file_size <= 0:
            return "Unknown"
        elif self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.2f} GB"

    @property
    def bitrate_str(self) -> str:
        """Format bitrate as Mbps or kbps."""
        if self.bitrate <= 0:
            return "Unknown"
        elif self.bitrate >= 1_000_000:
            return f"{self.bitrate / 1_000_000:.1f} Mbps"
        else:
            return f"{self.bitrate / 1_000:.0f} kbps"


class ResultCard(QFrame):
    """
    A styled card for displaying a label-value pair.
    Consistent with VS Code dark theme styling.
    """

    def __init__(self, label: str, value: str = "", parent=None):
        super().__init__(parent)
        self._setup_ui(label, value)

    def _setup_ui(self, label: str, value: str):
        """Set up the card UI."""
        self.setStyleSheet("""
            ResultCard {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Label (smaller, gray)
        self._label = QLabel(label)
        self._label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self._label)

        # Value (larger, white)
        self._value = QLabel(value)
        self._value.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        layout.addWidget(self._value)

    def set_value(self, value: str):
        """Update the displayed value."""
        self._value.setText(value)

    def set_label(self, label: str):
        """Update the label text."""
        self._label.setText(label)


class VideoInfoPanel(QFrame):
    """
    Panel displaying comprehensive video metadata.

    Layout: Vertical list of ResultCard widgets showing:
    - Duration
    - Resolution
    - Frame Rate
    - Video Codec
    - Audio Status
    - File Size
    - Bitrate
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metadata: Optional[VideoMetadata] = None
        self._setup_ui()

    def _setup_ui(self):
        """Configure panel appearance."""
        self.setStyleSheet("""
            VideoInfoPanel {
                background-color: #1e1e1e;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Video Information")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #ffffff;
            padding: 4px 0;
        """)
        layout.addWidget(title)

        # Info cards
        self._duration_card = ResultCard("Duration", "--:--:--")
        layout.addWidget(self._duration_card)

        self._resolution_card = ResultCard("Resolution", "Unknown")
        layout.addWidget(self._resolution_card)

        self._fps_card = ResultCard("Frame Rate", "-- fps")
        layout.addWidget(self._fps_card)

        self._codec_card = ResultCard("Video Codec", "Unknown")
        layout.addWidget(self._codec_card)

        self._audio_card = ResultCard("Audio", "No Audio")
        layout.addWidget(self._audio_card)

        self._size_card = ResultCard("File Size", "Unknown")
        layout.addWidget(self._size_card)

        self._bitrate_card = ResultCard("Bitrate", "Unknown")
        layout.addWidget(self._bitrate_card)

        # Stretch at bottom
        layout.addStretch()

    def set_info(self, metadata: VideoMetadata):
        """
        Update panel with video metadata.

        Args:
            metadata: VideoMetadata object with video information
        """
        self._metadata = metadata

        # Update all cards
        self._duration_card.set_value(metadata.duration_str)
        self._resolution_card.set_value(metadata.resolution_str)
        self._fps_card.set_value(f"{metadata.fps:.2f} fps" if metadata.fps > 0 else "Unknown")
        self._codec_card.set_value(metadata.codec.upper() if metadata.codec else "Unknown")

        # Audio info
        if metadata.has_audio:
            audio_info = metadata.audio_codec.upper() if metadata.audio_codec else "Audio"
            if metadata.audio_channels > 0:
                ch_str = "Stereo" if metadata.audio_channels == 2 else f"{metadata.audio_channels}ch"
                audio_info += f" ({ch_str})"
            if metadata.audio_sample_rate > 0:
                audio_info += f" @ {metadata.audio_sample_rate // 1000}kHz"
            self._audio_card.set_value(audio_info)
        else:
            self._audio_card.set_value("No Audio Track")

        self._size_card.set_value(metadata.file_size_str)
        self._bitrate_card.set_value(metadata.bitrate_str)

        logger.debug(f"Video info panel updated: {metadata.resolution_str}, {metadata.duration_str}")

    def clear_info(self):
        """Clear all displayed information."""
        self._metadata = None
        self._duration_card.set_value("--:--:--")
        self._resolution_card.set_value("Unknown")
        self._fps_card.set_value("-- fps")
        self._codec_card.set_value("Unknown")
        self._audio_card.set_value("No Audio")
        self._size_card.set_value("Unknown")
        self._bitrate_card.set_value("Unknown")

    def get_metadata(self) -> Optional[VideoMetadata]:
        """Get the currently displayed metadata."""
        return self._metadata


class CompactVideoInfoPanel(QFrame):
    """
    Compact horizontal layout for video info display.
    Shows key metrics in a single row.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Configure compact panel."""
        self.setStyleSheet("""
            CompactVideoInfoPanel {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(20)

        # Duration
        self._duration_label = QLabel("--:--:--")
        self._duration_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(self._create_info_item("Duration", self._duration_label))

        # Resolution
        self._resolution_label = QLabel("--")
        self._resolution_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(self._create_info_item("Resolution", self._resolution_label))

        # FPS
        self._fps_label = QLabel("-- fps")
        self._fps_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(self._create_info_item("FPS", self._fps_label))

        # Audio indicator
        self._audio_label = QLabel("No Audio")
        self._audio_label.setStyleSheet("color: #888888;")
        layout.addWidget(self._create_info_item("Audio", self._audio_label))

        layout.addStretch()

    def _create_info_item(self, label_text: str, value_label: QLabel) -> QFrame:
        """Create a label-value pair widget."""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label = QLabel(label_text)
        label.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(label)
        layout.addWidget(value_label)

        return frame

    def set_info(self, metadata: VideoMetadata):
        """Update compact panel with metadata."""
        self._duration_label.setText(metadata.duration_str)
        self._resolution_label.setText(f"{metadata.width}x{metadata.height}" if metadata.width else "--")
        self._fps_label.setText(f"{metadata.fps:.0f} fps" if metadata.fps > 0 else "-- fps")

        if metadata.has_audio:
            self._audio_label.setText("Audio OK")
            self._audio_label.setStyleSheet("color: #4ec9b0;")  # Green
        else:
            self._audio_label.setText("No Audio")
            self._audio_label.setStyleSheet("color: #888888;")
