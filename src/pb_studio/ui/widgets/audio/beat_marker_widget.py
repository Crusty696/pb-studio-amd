"""
Beat Marker Widget

Transparent overlay widget for displaying beat markers on waveforms.
Shows vertical lines at beat positions with different colors for downbeats.
"""
import logging
from typing import List, Optional

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QMouseEvent

logger = logging.getLogger(__name__)


class BeatMarkerWidget(QWidget):
    """
    Overlay widget for displaying beat markers on a waveform.

    Shows vertical lines at beat positions:
    - Red lines for downbeats (first beat of each bar)
    - Gray lines for regular beats

    Signals:
        beatClicked(float): Emitted when user clicks near a beat marker,
                           provides the beat time in seconds
    """

    # Signal emitted when a beat marker is clicked
    beatClicked = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Beat data
        self._beats: List[float] = []  # All beat times in seconds
        self._downbeats: List[float] = []  # Downbeat times in seconds

        # Display parameters
        self._start_time: float = 0.0  # Visible window start (seconds)
        self._end_time: float = 10.0  # Visible window end (seconds)
        self._click_tolerance: int = 10  # Pixels tolerance for beat click detection

        # Colors
        self._beat_color = QColor("#666666")  # Gray for regular beats
        self._downbeat_color = QColor("#ff4d4d")  # Red for downbeats
        self._hover_color = QColor("#ffffff")  # White for hover highlight

        # Hover state
        self._hover_time: Optional[float] = None

        # Make widget transparent for mouse events passthrough when not clicking on beats
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def set_beats(self, beats: List[float]):
        """
        Set the beat positions.

        Args:
            beats: List of beat times in seconds
        """
        self._beats = sorted(beats) if beats else []
        logger.debug(f"BeatMarkerWidget: Set {len(self._beats)} beats")
        self.update()

    def set_downbeats(self, downbeats: List[float]):
        """
        Set the downbeat positions (first beat of each bar).

        Args:
            downbeats: List of downbeat times in seconds
        """
        self._downbeats = sorted(downbeats) if downbeats else []
        logger.debug(f"BeatMarkerWidget: Set {len(self._downbeats)} downbeats")
        self.update()

    def set_visible_range(self, start_time: float, end_time: float):
        """
        Set the visible time range.

        Args:
            start_time: Start of visible window in seconds
            end_time: End of visible window in seconds
        """
        self._start_time = start_time
        self._end_time = end_time
        self.update()

    def set_colors(self, beat_color: str, downbeat_color: str):
        """
        Set custom colors for beat markers.

        Args:
            beat_color: Color string for regular beats (e.g., "#666666")
            downbeat_color: Color string for downbeats (e.g., "#ff4d4d")
        """
        self._beat_color = QColor(beat_color)
        self._downbeat_color = QColor(downbeat_color)
        self.update()

    def _time_to_x(self, time: float) -> int:
        """Convert time in seconds to X pixel coordinate."""
        if self._end_time <= self._start_time:
            return 0

        duration = self._end_time - self._start_time
        relative_pos = (time - self._start_time) / duration
        return int(relative_pos * self.width())

    def _x_to_time(self, x: int) -> float:
        """Convert X pixel coordinate to time in seconds."""
        if self.width() == 0:
            return self._start_time

        duration = self._end_time - self._start_time
        relative_pos = x / self.width()
        return self._start_time + (relative_pos * duration)

    def _find_nearest_beat(self, time: float) -> Optional[float]:
        """Find the beat nearest to the given time within tolerance."""
        if not self._beats:
            return None

        # Calculate time tolerance based on pixel tolerance
        if self.width() == 0:
            return None

        duration = self._end_time - self._start_time
        time_tolerance = (self._click_tolerance / self.width()) * duration

        # Find nearest beat
        nearest = None
        min_distance = float('inf')

        for beat in self._beats:
            distance = abs(beat - time)
            if distance < min_distance and distance <= time_tolerance:
                min_distance = distance
                nearest = beat

        return nearest

    def paintEvent(self, event):
        """Draw beat markers as vertical lines."""
        if not self._beats and not self._downbeats:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        height = self.height()

        # Draw regular beats (gray, dashed)
        beat_pen = QPen(self._beat_color, 1)
        beat_pen.setStyle(Qt.PenStyle.DashLine)

        for beat_time in self._beats:
            # Skip if outside visible range
            if beat_time < self._start_time or beat_time > self._end_time:
                continue

            # Skip if this is a downbeat (will be drawn separately)
            if beat_time in self._downbeats:
                continue

            x = self._time_to_x(beat_time)

            # Check if this is the hovered beat
            if self._hover_time is not None and abs(beat_time - self._hover_time) < 0.01:
                hover_pen = QPen(self._hover_color, 2)
                painter.setPen(hover_pen)
            else:
                painter.setPen(beat_pen)

            painter.drawLine(x, 0, x, height)

        # Draw downbeats (red, solid)
        downbeat_pen = QPen(self._downbeat_color, 2)
        downbeat_pen.setStyle(Qt.PenStyle.SolidLine)

        for downbeat_time in self._downbeats:
            # Skip if outside visible range
            if downbeat_time < self._start_time or downbeat_time > self._end_time:
                continue

            x = self._time_to_x(downbeat_time)

            # Check if this is the hovered beat
            if self._hover_time is not None and abs(downbeat_time - self._hover_time) < 0.01:
                hover_pen = QPen(self._hover_color, 3)
                painter.setPen(hover_pen)
            else:
                painter.setPen(downbeat_pen)

            painter.drawLine(x, 0, x, height)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse movement for hover highlighting."""
        time = self._x_to_time(int(event.position().x()))
        nearest = self._find_nearest_beat(time)

        if nearest != self._hover_time:
            self._hover_time = nearest
            self.update()

            # Change cursor when hovering over a beat
            if nearest is not None:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse click to emit beat position."""
        if event.button() == Qt.MouseButton.LeftButton:
            time = self._x_to_time(int(event.position().x()))
            nearest = self._find_nearest_beat(time)

            if nearest is not None:
                logger.debug(f"Beat clicked at time: {nearest:.3f}s")
                self.beatClicked.emit(nearest)
                event.accept()
                return

        # Pass through if not clicking on a beat
        event.ignore()

    def leaveEvent(self, event):
        """Clear hover state when mouse leaves widget."""
        self._hover_time = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def clear(self):
        """Clear all beat data."""
        self._beats = []
        self._downbeats = []
        self._hover_time = None
        self.update()
