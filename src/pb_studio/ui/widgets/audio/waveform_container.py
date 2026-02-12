"""
Waveform Container Widget

Combines WaveformWidget with BeatMarkerWidget as an overlay.
Synchronizes zoom and scroll between both widgets.
"""
import logging
from typing import List, Optional

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QStackedLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from src.pb_studio.ui.widgets.waveform_widget import WaveformWidget
from src.pb_studio.ui.widgets.audio.beat_marker_widget import BeatMarkerWidget

logger = logging.getLogger(__name__)


class WaveformContainer(QFrame):
    """
    Container widget combining waveform display with beat markers.

    Provides:
    - Waveform visualization (WaveformWidget)
    - Beat marker overlay (BeatMarkerWidget)
    - Synchronized zoom/scroll between both
    - Unified interface for loading and controlling both

    Signals:
        beatClicked(float): Forwarded from BeatMarkerWidget
        positionChanged(float): Emitted when playhead position changes
    """

    # Signals
    beatClicked = pyqtSignal(float)
    positionChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._duration: float = 0.0
        self._current_position: float = 0.0

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setStyleSheet("""
            WaveformContainer {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header label
        self.header_label = QLabel("Waveform")
        self.header_label.setStyleSheet("""
            color: #888888;
            font-size: 11px;
            padding: 5px;
            background-color: transparent;
        """)
        main_layout.addWidget(self.header_label)

        # Stacked widget container for overlay
        self.stack_container = QWidget()
        stack_layout = QStackedLayout(self.stack_container)
        stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        # Waveform widget (bottom layer)
        self.waveform = WaveformWidget()
        self.waveform.setMinimumHeight(80)

        # Beat marker widget (top layer, transparent)
        self.beat_markers = BeatMarkerWidget()
        self.beat_markers.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Add widgets to stack (order matters: first added = bottom)
        stack_layout.addWidget(self.waveform)
        stack_layout.addWidget(self.beat_markers)

        main_layout.addWidget(self.stack_container, 1)  # Stretch factor

        self.setMinimumHeight(100)

    def _connect_signals(self):
        """Connect internal signals."""
        # Forward beat clicked signal
        self.beat_markers.beatClicked.connect(self.beatClicked.emit)

    def load_audio(self, file_path: str):
        """
        Load audio file for waveform display.

        Args:
            file_path: Path to the audio file
        """
        logger.info(f"WaveformContainer loading: {file_path}")

        # Load waveform
        self.waveform.load_audio(file_path)

        # Update duration
        self._duration = self.waveform.get_duration()

        # Clear existing beat markers
        self.beat_markers.clear()

        # Sync visible range
        self._sync_visible_range()

    def set_beats(self, beats: List[float]):
        """
        Set beat positions.

        Args:
            beats: List of beat times in seconds
        """
        self.beat_markers.set_beats(beats)

        # Also set on waveform for its internal rendering
        if hasattr(self.waveform, 'set_beat_markers'):
            self.waveform.set_beat_markers(beats)

    def set_downbeats(self, downbeats: List[float]):
        """
        Set downbeat positions.

        Args:
            downbeats: List of downbeat times in seconds
        """
        self.beat_markers.set_downbeats(downbeats)

    def set_beat_data(self, beat_data: List):
        """
        Set beat data from BeatNet format.

        BeatNet returns [[time, beat_index], ...] where beat_index 1 = downbeat.

        Args:
            beat_data: BeatNet format beat data
        """
        if not beat_data:
            self.beat_markers.clear()
            return

        try:
            # Parse BeatNet format
            all_beats = []
            downbeats = []

            for item in beat_data:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    time = float(item[0])
                    beat_idx = int(item[1])

                    all_beats.append(time)

                    # Beat index 1 typically means downbeat
                    if beat_idx == 1:
                        downbeats.append(time)
                else:
                    # Simple list of times
                    all_beats.append(float(item))

            self.set_beats(all_beats)
            self.set_downbeats(downbeats)

            logger.debug(f"Set {len(all_beats)} beats, {len(downbeats)} downbeats")

        except Exception as e:
            logger.error(f"Error parsing beat data: {e}")

    def set_position(self, position: float):
        """
        Set current playhead position.

        Args:
            position: Position in seconds
        """
        self._current_position = position
        # TODO: Add playhead indicator to waveform/beat markers
        self.positionChanged.emit(position)

    def set_zoom(self, zoom_level: float):
        """
        Set zoom level.

        Args:
            zoom_level: Zoom factor (1.0 = no zoom)
        """
        self.waveform.zoom_level = max(1.0, min(100.0, zoom_level))
        self._sync_visible_range()
        self.waveform.update()

    def set_scroll(self, scroll_offset: int):
        """
        Set scroll offset.

        Args:
            scroll_offset: Offset in samples
        """
        if self.waveform.samples is not None:
            max_offset = len(self.waveform.samples)
            self.waveform.scroll_offset = max(0, min(max_offset, scroll_offset))
            self._sync_visible_range()
            self.waveform.update()

    def _sync_visible_range(self):
        """Synchronize visible range between waveform and beat markers."""
        if self.waveform.samples is None or len(self.waveform.samples) == 0:
            return

        # Calculate visible time range based on waveform state
        total_samples = len(self.waveform.samples)
        sample_rate = self.waveform.sample_rate

        visible_samples = int(total_samples / self.waveform.zoom_level)
        start_idx = self.waveform.scroll_offset
        end_idx = min(total_samples, start_idx + visible_samples)

        start_time = start_idx / sample_rate
        end_time = end_idx / sample_rate

        self.beat_markers.set_visible_range(start_time, end_time)

    def resizeEvent(self, event):
        """Handle resize to sync overlay size."""
        super().resizeEvent(event)

        # Ensure beat marker widget matches waveform size
        waveform_geometry = self.waveform.geometry()
        self.beat_markers.setGeometry(waveform_geometry)

        self._sync_visible_range()

    def wheelEvent(self, event):
        """Handle wheel events for zoom/scroll."""
        # Forward to waveform
        self.waveform.wheelEvent(event)

        # Sync beat markers
        self._sync_visible_range()

    def get_duration(self) -> float:
        """Get audio duration in seconds."""
        return self._duration

    def get_zoom_level(self) -> float:
        """Get current zoom level."""
        return self.waveform.zoom_level

    def get_scroll_offset(self) -> int:
        """Get current scroll offset in samples."""
        return self.waveform.scroll_offset

    def clear(self):
        """Clear all content."""
        self.waveform.samples = None
        self.beat_markers.clear()
        self._duration = 0.0
        self._current_position = 0.0
        self.waveform.update()
