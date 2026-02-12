"""
Timeline Widget

Horizontal timeline with playhead, markers, zoom and pan support.
Used for video/audio timeline navigation.
"""
import logging
from typing import List, Optional, NamedTuple
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QMouseEvent, QWheelEvent, QPaintEvent
)

logger = logging.getLogger(__name__)


class TimelineMarker(NamedTuple):
    """Represents a marker on the timeline."""
    time: float  # Time in seconds
    label: str = ""
    color: str = "#ff4d4d"


class TimelineWidget(QWidget):
    """
    A horizontal timeline widget with playhead and markers.

    Features:
    - Playhead position indicator
    - Markers (beats, scenes, etc.)
    - Zoom (Ctrl + wheel)
    - Pan (wheel or drag)
    - Click to seek

    Signals:
        seekRequested(float): Emitted when user clicks to seek (time in seconds)
        markerClicked(int): Emitted when user clicks a marker (marker index)
    """

    # Signals
    seekRequested = pyqtSignal(float)  # Time in seconds
    markerClicked = pyqtSignal(int)     # Marker index

    # Colors - Dark theme
    COLOR_BACKGROUND = "#1e1e1e"
    COLOR_TRACK = "#2d2d30"
    COLOR_RULER = "#3e3e42"
    COLOR_PLAYHEAD = "#007acc"
    COLOR_TEXT = "#9d9d9d"
    COLOR_MARKER_DEFAULT = "#ff4d4d"

    def __init__(self, parent=None):
        super().__init__(parent)

        # Timeline state
        self._duration = 60.0  # Total duration in seconds
        self._playhead = 0.0   # Current playhead position
        self._markers: List[TimelineMarker] = []

        # View state
        self._zoom_level = 1.0  # 1.0 = fit all, higher = zoomed in
        self._scroll_offset = 0.0  # Pan offset in seconds

        # Interaction state
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_offset = 0.0

        # Configuration
        self._ruler_height = 24
        self._track_height = 40
        self._marker_radius = 6

        self._setup_ui()

    def _setup_ui(self):
        """Initialize UI settings."""
        self.setMinimumHeight(self._ruler_height + self._track_height + 10)
        self.setMaximumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_duration(self, seconds: float):
        """
        Set total timeline duration.

        Args:
            seconds: Duration in seconds
        """
        self._duration = max(0.1, seconds)
        self._playhead = min(self._playhead, self._duration)
        self.update()

    def get_duration(self) -> float:
        """Get total duration in seconds."""
        return self._duration

    def set_playhead(self, seconds: float):
        """
        Set playhead position.

        Args:
            seconds: Position in seconds
        """
        self._playhead = max(0.0, min(self._duration, seconds))
        self.update()

    def get_playhead(self) -> float:
        """Get current playhead position in seconds."""
        return self._playhead

    def set_markers(self, markers: List):
        """
        Set timeline markers.

        Args:
            markers: List of TimelineMarker or dicts with 'time', optional 'label', 'color'
        """
        self._markers = []
        for m in markers:
            if isinstance(m, TimelineMarker):
                self._markers.append(m)
            elif isinstance(m, dict):
                self._markers.append(TimelineMarker(
                    time=m.get('time', 0),
                    label=m.get('label', ''),
                    color=m.get('color', self.COLOR_MARKER_DEFAULT)
                ))
            elif isinstance(m, (int, float)):
                # Simple time value
                self._markers.append(TimelineMarker(time=float(m)))
        self.update()

    def add_marker(self, time: float, label: str = "", color: str = None):
        """
        Add a single marker.

        Args:
            time: Time in seconds
            label: Optional label
            color: Optional color (hex)
        """
        marker = TimelineMarker(
            time=time,
            label=label,
            color=color or self.COLOR_MARKER_DEFAULT
        )
        self._markers.append(marker)
        self.update()

    def clear_markers(self):
        """Remove all markers."""
        self._markers.clear()
        self.update()

    def set_zoom(self, level: float):
        """
        Set zoom level.

        Args:
            level: Zoom level (1.0 = fit all, >1.0 = zoomed in)
        """
        self._zoom_level = max(1.0, min(100.0, level))
        self._clamp_scroll()
        self.update()

    def reset_view(self):
        """Reset zoom and pan to default."""
        self._zoom_level = 1.0
        self._scroll_offset = 0.0
        self.update()

    def _time_to_x(self, time: float) -> float:
        """Convert time (seconds) to x pixel coordinate."""
        visible_duration = self._duration / self._zoom_level
        time_offset = time - self._scroll_offset
        return (time_offset / visible_duration) * self.width()

    def _x_to_time(self, x: float) -> float:
        """Convert x pixel coordinate to time (seconds)."""
        visible_duration = self._duration / self._zoom_level
        time_offset = (x / self.width()) * visible_duration
        return self._scroll_offset + time_offset

    def _clamp_scroll(self):
        """Clamp scroll offset to valid range."""
        max_offset = max(0.0, self._duration - (self._duration / self._zoom_level))
        self._scroll_offset = max(0.0, min(max_offset, self._scroll_offset))

    def _format_time(self, seconds: float) -> str:
        """Format time as MM:SS or HH:MM:SS."""
        if seconds < 0:
            return "00:00"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def paintEvent(self, event: QPaintEvent):
        """Paint the timeline."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(self.COLOR_BACKGROUND))

        # Track area
        track_y = self._ruler_height
        painter.fillRect(0, track_y, w, self._track_height, QColor(self.COLOR_TRACK))

        # Ruler
        self._draw_ruler(painter, w)

        # Markers
        self._draw_markers(painter, track_y)

        # Playhead
        self._draw_playhead(painter, h)

    def _draw_ruler(self, painter: QPainter, width: int):
        """Draw the time ruler with ticks."""
        visible_duration = self._duration / self._zoom_level
        start_time = self._scroll_offset
        end_time = start_time + visible_duration

        # Calculate tick interval based on zoom
        if visible_duration <= 10:
            major_interval = 1.0
            minor_interval = 0.25
        elif visible_duration <= 60:
            major_interval = 5.0
            minor_interval = 1.0
        elif visible_duration <= 300:
            major_interval = 30.0
            minor_interval = 5.0
        else:
            major_interval = 60.0
            minor_interval = 10.0

        # Draw ruler background
        painter.fillRect(0, 0, width, self._ruler_height, QColor(self.COLOR_BACKGROUND))

        # Bottom line
        painter.setPen(QPen(QColor(self.COLOR_RULER), 1))
        painter.drawLine(0, self._ruler_height - 1, width, self._ruler_height - 1)

        # Font for labels
        font = QFont("Segoe UI", 9)
        painter.setFont(font)

        # Draw ticks
        t = start_time - (start_time % minor_interval)
        while t <= end_time:
            x = self._time_to_x(t)

            if 0 <= x <= width:
                is_major = abs(t % major_interval) < 0.01

                if is_major:
                    # Major tick
                    painter.setPen(QPen(QColor(self.COLOR_TEXT), 1))
                    painter.drawLine(int(x), self._ruler_height - 8, int(x), self._ruler_height - 1)

                    # Label
                    label = self._format_time(t)
                    painter.drawText(int(x) - 20, 2, 40, 14,
                                   Qt.AlignmentFlag.AlignCenter, label)
                else:
                    # Minor tick
                    painter.setPen(QPen(QColor(self.COLOR_RULER), 1))
                    painter.drawLine(int(x), self._ruler_height - 4, int(x), self._ruler_height - 1)

            t += minor_interval

    def _draw_markers(self, painter: QPainter, track_y: int):
        """Draw timeline markers."""
        marker_y = track_y + self._track_height // 2

        for i, marker in enumerate(self._markers):
            x = self._time_to_x(marker.time)

            if 0 <= x <= self.width():
                # Marker line
                painter.setPen(QPen(QColor(marker.color), 1))
                painter.drawLine(int(x), track_y, int(x), track_y + self._track_height)

                # Marker circle
                painter.setBrush(QBrush(QColor(marker.color)))
                painter.drawEllipse(
                    QPointF(x, marker_y),
                    self._marker_radius,
                    self._marker_radius
                )

    def _draw_playhead(self, painter: QPainter, height: int):
        """Draw the playhead indicator."""
        x = self._time_to_x(self._playhead)

        if 0 <= x <= self.width():
            # Playhead line
            pen = QPen(QColor(self.COLOR_PLAYHEAD), 2)
            painter.setPen(pen)
            painter.drawLine(int(x), 0, int(x), height)

            # Playhead triangle at top
            painter.setBrush(QBrush(QColor(self.COLOR_PLAYHEAD)))
            painter.drawPolygon([
                QPointF(x - 6, 0),
                QPointF(x + 6, 0),
                QPointF(x, 8)
            ])

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for seek and drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on a marker
            for i, marker in enumerate(self._markers):
                marker_x = self._time_to_x(marker.time)
                if abs(event.position().x() - marker_x) <= self._marker_radius + 2:
                    self.markerClicked.emit(i)
                    return

            # Start drag or seek
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                # Shift+click = pan
                self._dragging = True
                self._drag_start_x = event.position().x()
                self._drag_start_offset = self._scroll_offset
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                # Normal click = seek
                time = self._x_to_time(event.position().x())
                time = max(0.0, min(self._duration, time))
                self.seekRequested.emit(time)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for drag."""
        if self._dragging:
            delta_x = event.position().x() - self._drag_start_x
            visible_duration = self._duration / self._zoom_level
            delta_time = (delta_x / self.width()) * visible_duration
            self._scroll_offset = self._drag_start_offset - delta_time
            self._clamp_scroll()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zoom and pan."""
        delta = event.angleDelta().y()

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl + wheel = zoom
            mouse_time = self._x_to_time(event.position().x())

            if delta > 0:
                self._zoom_level = min(100.0, self._zoom_level * 1.2)
            else:
                self._zoom_level = max(1.0, self._zoom_level / 1.2)

            # Keep mouse position stable after zoom
            new_time = self._x_to_time(event.position().x())
            self._scroll_offset += mouse_time - new_time
            self._clamp_scroll()
        else:
            # Wheel = pan
            visible_duration = self._duration / self._zoom_level
            scroll_amount = visible_duration * 0.1

            if delta < 0:
                self._scroll_offset += scroll_amount
            else:
                self._scroll_offset -= scroll_amount
            self._clamp_scroll()

        self.update()
        event.accept()
