"""
Audio Info Panel Widget

Displays audio metadata and analysis results in a structured vertical layout.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


@dataclass
class AudioMetadata:
    """Audio file metadata container."""
    duration: float = 0.0  # seconds
    sample_rate: int = 44100
    channels: int = 2
    format: str = "Unknown"
    bit_depth: Optional[int] = None
    file_size: Optional[int] = None  # bytes


@dataclass
class AudioAnalysisResult:
    """Audio analysis result container."""
    bpm: float = 0.0
    key: Optional[str] = None
    time_signature: Optional[str] = None
    beat_count: int = 0
    downbeat_count: int = 0


class ResultCard(QFrame):
    """
    A single result card displaying a label-value pair.
    """

    def __init__(self, label: str, value: str = "-", parent=None):
        super().__init__(parent)
        self._setup_ui(label, value)

    def _setup_ui(self, label: str, value: str):
        self.setStyleSheet("""
            ResultCard {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Label
        self.label_widget = QLabel(label)
        self.label_widget.setStyleSheet("""
            color: #888888;
            font-size: 12px;
        """)
        layout.addWidget(self.label_widget)

        layout.addStretch()

        # Value
        self.value_widget = QLabel(value)
        self.value_widget.setStyleSheet("""
            color: #ffffff;
            font-size: 12px;
            font-weight: bold;
        """)
        layout.addWidget(self.value_widget)

    def set_value(self, value: str):
        """Update the displayed value."""
        self.value_widget.setText(value)

    def set_highlight(self, highlight: bool):
        """Highlight the card (e.g., for important values)."""
        if highlight:
            self.value_widget.setStyleSheet("""
                color: #007acc;
                font-size: 12px;
                font-weight: bold;
            """)
        else:
            self.value_widget.setStyleSheet("""
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
            """)


class AudioInfoPanel(QFrame):
    """
    Panel displaying audio metadata and analysis results.

    Shows information like BPM, duration, sample rate, channels, and key.
    Uses ResultCard widgets for a clean, structured layout.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            AudioInfoPanel {
                background-color: #252526;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Title
        title = QLabel("Audio Info")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #ffffff;
        """)
        layout.addWidget(title)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3e3e42;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Info Cards Container
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 5, 0, 0)
        self.cards_layout.setSpacing(6)

        # Create result cards
        self.bpm_card = ResultCard("BPM", "-")
        self.duration_card = ResultCard("Duration", "-")
        self.sample_rate_card = ResultCard("Sample Rate", "-")
        self.channels_card = ResultCard("Channels", "-")
        self.key_card = ResultCard("Key", "-")
        self.format_card = ResultCard("Format", "-")

        # Add cards to layout
        self.cards_layout.addWidget(self.bpm_card)
        self.cards_layout.addWidget(self.duration_card)
        self.cards_layout.addWidget(self.sample_rate_card)
        self.cards_layout.addWidget(self.channels_card)
        self.cards_layout.addWidget(self.key_card)
        self.cards_layout.addWidget(self.format_card)

        layout.addWidget(self.cards_container)

        # Analysis section header (hidden by default)
        self.analysis_header = QLabel("Analysis Results")
        self.analysis_header.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: #007acc;
            margin-top: 10px;
        """)
        self.analysis_header.setVisible(False)
        layout.addWidget(self.analysis_header)

        # Analysis cards container
        self.analysis_container = QWidget()
        self.analysis_layout = QVBoxLayout(self.analysis_container)
        self.analysis_layout.setContentsMargins(0, 5, 0, 0)
        self.analysis_layout.setSpacing(6)

        self.beat_count_card = ResultCard("Beat Count", "-")
        self.downbeat_count_card = ResultCard("Downbeats", "-")
        self.time_sig_card = ResultCard("Time Signature", "-")

        self.analysis_layout.addWidget(self.beat_count_card)
        self.analysis_layout.addWidget(self.downbeat_count_card)
        self.analysis_layout.addWidget(self.time_sig_card)

        self.analysis_container.setVisible(False)
        layout.addWidget(self.analysis_container)

        layout.addStretch()

    def set_info(self, metadata: AudioMetadata):
        """
        Update the panel with audio metadata.

        Args:
            metadata: AudioMetadata object with file information
        """
        # Duration formatting
        mins = int(metadata.duration // 60)
        secs = int(metadata.duration % 60)
        ms = int((metadata.duration % 1) * 1000)
        self.duration_card.set_value(f"{mins:02d}:{secs:02d}.{ms:03d}")

        # Sample rate
        sr_khz = metadata.sample_rate / 1000
        self.sample_rate_card.set_value(f"{sr_khz:.1f} kHz")

        # Channels
        channel_str = "Mono" if metadata.channels == 1 else "Stereo" if metadata.channels == 2 else f"{metadata.channels} ch"
        self.channels_card.set_value(channel_str)

        # Format
        format_str = metadata.format
        if metadata.bit_depth:
            format_str += f" ({metadata.bit_depth}-bit)"
        self.format_card.set_value(format_str)

        logger.debug(f"AudioInfoPanel updated: {metadata}")

    def set_analysis(self, analysis: AudioAnalysisResult):
        """
        Update the panel with audio analysis results.

        Args:
            analysis: AudioAnalysisResult object with analysis data
        """
        # BPM
        if analysis.bpm > 0:
            self.bpm_card.set_value(f"{analysis.bpm:.1f}")
            self.bpm_card.set_highlight(True)
        else:
            self.bpm_card.set_value("-")
            self.bpm_card.set_highlight(False)

        # Key
        if analysis.key:
            self.key_card.set_value(analysis.key)
            self.key_card.set_highlight(True)
        else:
            self.key_card.set_value("-")
            self.key_card.set_highlight(False)

        # Show analysis section if we have data
        has_analysis = analysis.beat_count > 0 or analysis.downbeat_count > 0 or analysis.time_signature
        self.analysis_header.setVisible(has_analysis)
        self.analysis_container.setVisible(has_analysis)

        if has_analysis:
            self.beat_count_card.set_value(str(analysis.beat_count))
            self.downbeat_count_card.set_value(str(analysis.downbeat_count))
            self.time_sig_card.set_value(analysis.time_signature or "-")

        logger.debug(f"AudioInfoPanel analysis updated: {analysis}")

    def clear(self):
        """Reset all values to default."""
        self.bpm_card.set_value("-")
        self.bpm_card.set_highlight(False)
        self.duration_card.set_value("-")
        self.sample_rate_card.set_value("-")
        self.channels_card.set_value("-")
        self.key_card.set_value("-")
        self.key_card.set_highlight(False)
        self.format_card.set_value("-")

        self.analysis_header.setVisible(False)
        self.analysis_container.setVisible(False)
