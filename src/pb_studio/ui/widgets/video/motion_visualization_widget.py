"""
Motion Visualization Widget for PB Studio AMD.

Displays motion intensity data as a graph, similar to audio waveform visualization.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QLinearGradient,
    QPainterPath,
    QFont,
)

logger = logging.getLogger(__name__)


@dataclass
class MotionData:
    """Data class for motion information at a specific time."""
    timestamp: float        # Time in seconds
    magnitude: float        # Motion magnitude (0.0 - 1.0 normalized)
    direction: float = 0.0  # Dominant direction in degrees (optional)

    @property
    def is_high_motion(self) -> bool:
        """Check if this is a high-motion frame (>0.7)."""
        return self.magnitude > 0.7


class MotionVisualizationWidget(QWidget):
    """
    Widget for visualizing motion data as a curve/graph.

    Features:
    - Displays motion magnitude over time
    - Color-codes high-motion regions (red)
    - Supports pan and zoom
    - Click to seek functionality

    Signals:
        positionClicked(float): Emitted when clicking on the graph (time in seconds)
        regionSelected(float, float): Emitted when selecting a region (start, end)
    """

    positionClicked = pyqtSignal(float)
    regionSelected = pyqtSignal(float, float)

    # Colors
    COLOR_BACKGROUND = QColor("#1e1e1e")
    COLOR_GRID = QColor("#2d2d30")
    COLOR_AXIS = QColor("#3e3e42")
    COLOR_LINE_LOW = QColor("#007acc")      # Blue for low motion
    COLOR_LINE_HIGH = QColor("#f14c4c")     # Red for high motion
    COLOR_FILL_LOW = QColor(0, 122, 204, 40)   # Semi-transparent blue
    COLOR_FILL_HIGH = QColor(241, 76, 76, 60)   # Semi-transparent red
    COLOR_PLAYHEAD = QColor("#ffffff")
    COLOR_TEXT = QColor("#888888")

    # Thresholds
    HIGH_MOTION_THRESHOLD = 0.6

    def __init__(self, parent=None):
        super().__init__(parent)

        self._motion_data: List[MotionData] = []
        self._duration: float = 0.0
        self._playhead_position: float = -1.0

        # View state
        self._zoom_level: float = 1.0
        self._scroll_offset: float = 0.0
        self._selection_start: float = -1.0
        self._selection_end: float = -1.0
        self._is_selecting: bool = False

        # Appearance
        self.setMinimumHeight(100)
        self.setStyleSheet("background-color: #1e1e1e;")

        # Enable mouse tracking
        self.setMouseTracking(True)

    def set_motion_data(self, data: List[MotionData], duration: float = 0.0):
        """
        Set the motion data to visualize.

        Args:
            data: List of MotionData objects
            duration: Total video duration in seconds (auto-detected if 0)
        """
        self._motion_data = sorted(data, key=lambda x: x.timestamp)

        if duration > 0:
            self._duration = duration
        elif self._motion_data:
            self._duration = self._motion_data[-1].timestamp
        else:
            self._duration = 0.0

        # Reset view
        self._zoom_level = 1.0
        self._scroll_offset = 0.0
        self._playhead_position = -1.0

        logger.info(f"Motion data loaded: {len(data)} points, {self._duration:.1f}s duration")
        self.update()

    def set_playhead_position(self, time_sec: float):
        """
        Set the playhead position indicator.

        Args:
            time_sec: Current playback time in seconds (-1 to hide)
        """
        self._playhead_position = time_sec
        self.update()

    def clear(self):
        """Clear all motion data."""
        self._motion_data = []
        self._duration = 0.0
        self._playhead_position = -1.0
        self.update()

    def paintEvent(self, event):
        """Paint the motion visualization."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, self.COLOR_BACKGROUND)

        if not self._motion_data or self._duration <= 0:
            self._draw_empty_state(painter, w, h)
            return

        # Calculate visible range
        visible_duration = self._duration / self._zoom_level
        start_time = self._scroll_offset
        end_time = start_time + visible_duration

        # Draw components
        self._draw_grid(painter, w, h, start_time, end_time)
        self._draw_high_motion_regions(painter, w, h, start_time, end_time)
        self._draw_motion_curve(painter, w, h, start_time, end_time)
        self._draw_axis_labels(painter, w, h, start_time, end_time)
        self._draw_selection(painter, w, h, start_time, end_time)
        self._draw_playhead(painter, w, h, start_time, end_time)

    def _draw_empty_state(self, painter: QPainter, w: int, h: int):
        """Draw placeholder when no data is loaded."""
        painter.setPen(self.COLOR_TEXT)
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(
            QRectF(0, 0, w, h),
            Qt.AlignmentFlag.AlignCenter,
            "No motion data loaded"
        )

    def _draw_grid(self, painter: QPainter, w: int, h: int, start_time: float, end_time: float):
        """Draw background grid lines."""
        pen = QPen(self.COLOR_GRID, 1)
        painter.setPen(pen)

        # Horizontal lines (motion levels: 0.25, 0.5, 0.75)
        for level in [0.25, 0.5, 0.75]:
            y = int(h - (level * h))
            painter.drawLine(0, y, w, y)

        # Vertical lines (time markers)
        visible_duration = end_time - start_time

        # Determine grid interval based on visible duration
        if visible_duration <= 10:
            interval = 1.0
        elif visible_duration <= 60:
            interval = 5.0
        elif visible_duration <= 300:
            interval = 30.0
        else:
            interval = 60.0

        # Find first grid line
        first_mark = (int(start_time / interval) + 1) * interval

        for t in np.arange(first_mark, end_time, interval):
            x = self._time_to_x(t, w, start_time, end_time)
            painter.drawLine(x, 0, x, h)

    def _draw_high_motion_regions(self, painter: QPainter, w: int, h: int,
                                   start_time: float, end_time: float):
        """Highlight regions with high motion."""
        if not self._motion_data:
            return

        in_high_region = False
        region_start_x = 0

        # Get visible data points
        visible_data = [
            d for d in self._motion_data
            if start_time <= d.timestamp <= end_time
        ]

        for i, data in enumerate(visible_data):
            x = self._time_to_x(data.timestamp, w, start_time, end_time)

            if data.magnitude > self.HIGH_MOTION_THRESHOLD:
                if not in_high_region:
                    region_start_x = x
                    in_high_region = True
            else:
                if in_high_region:
                    # Draw high motion region
                    painter.fillRect(
                        region_start_x, 0,
                        x - region_start_x, h,
                        self.COLOR_FILL_HIGH
                    )
                    in_high_region = False

        # Close any open region
        if in_high_region:
            painter.fillRect(
                region_start_x, 0,
                w - region_start_x, h,
                self.COLOR_FILL_HIGH
            )

    def _draw_motion_curve(self, painter: QPainter, w: int, h: int,
                           start_time: float, end_time: float):
        """Draw the motion magnitude curve."""
        if len(self._motion_data) < 2:
            return

        # Create path for filled area
        fill_path = QPainterPath()
        line_path = QPainterPath()

        # Get visible data with some padding
        padding = (end_time - start_time) * 0.05
        visible_data = [
            d for d in self._motion_data
            if (start_time - padding) <= d.timestamp <= (end_time + padding)
        ]

        if not visible_data:
            return

        # Start paths
        first_x = self._time_to_x(visible_data[0].timestamp, w, start_time, end_time)
        first_y = h - int(visible_data[0].magnitude * h)

        fill_path.moveTo(first_x, h)  # Start at bottom
        fill_path.lineTo(first_x, first_y)
        line_path.moveTo(first_x, first_y)

        # Draw curve segments
        prev_high = visible_data[0].magnitude > self.HIGH_MOTION_THRESHOLD

        for i in range(1, len(visible_data)):
            data = visible_data[i]
            x = self._time_to_x(data.timestamp, w, start_time, end_time)
            y = h - int(data.magnitude * h)

            fill_path.lineTo(x, y)
            line_path.lineTo(x, y)

        # Close fill path
        last_x = self._time_to_x(visible_data[-1].timestamp, w, start_time, end_time)
        fill_path.lineTo(last_x, h)
        fill_path.closeSubpath()

        # Draw filled area
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.COLOR_FILL_LOW)
        painter.drawPath(fill_path)

        # Draw line
        pen = QPen(self.COLOR_LINE_LOW, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line_path)

        # Draw high motion segments with different color
        for i in range(1, len(visible_data)):
            prev_data = visible_data[i - 1]
            data = visible_data[i]

            # Check if this segment crosses high motion threshold
            if prev_data.magnitude > self.HIGH_MOTION_THRESHOLD or data.magnitude > self.HIGH_MOTION_THRESHOLD:
                x1 = self._time_to_x(prev_data.timestamp, w, start_time, end_time)
                y1 = h - int(prev_data.magnitude * h)
                x2 = self._time_to_x(data.timestamp, w, start_time, end_time)
                y2 = h - int(data.magnitude * h)

                pen = QPen(self.COLOR_LINE_HIGH, 2)
                painter.setPen(pen)
                painter.drawLine(x1, y1, x2, y2)

    def _draw_axis_labels(self, painter: QPainter, w: int, h: int,
                          start_time: float, end_time: float):
        """Draw time axis labels."""
        painter.setPen(self.COLOR_TEXT)
        painter.setFont(QFont("Segoe UI", 9))

        visible_duration = end_time - start_time

        # Determine label interval
        if visible_duration <= 10:
            interval = 2.0
        elif visible_duration <= 60:
            interval = 10.0
        elif visible_duration <= 300:
            interval = 60.0
        else:
            interval = 120.0

        # Draw labels
        first_mark = (int(start_time / interval) + 1) * interval

        for t in np.arange(first_mark, end_time, interval):
            x = self._time_to_x(t, w, start_time, end_time)
            label = self._format_time(t)

            # Draw label centered on position
            painter.drawText(
                int(x - 25), h - 5,
                50, 20,
                Qt.AlignmentFlag.AlignCenter,
                label
            )

    def _draw_selection(self, painter: QPainter, w: int, h: int,
                        start_time: float, end_time: float):
        """Draw selection highlight."""
        if self._selection_start < 0 or self._selection_end < 0:
            return

        x1 = self._time_to_x(self._selection_start, w, start_time, end_time)
        x2 = self._time_to_x(self._selection_end, w, start_time, end_time)

        if x1 > x2:
            x1, x2 = x2, x1

        painter.fillRect(
            int(x1), 0,
            int(x2 - x1), h,
            QColor(255, 255, 255, 30)
        )

    def _draw_playhead(self, painter: QPainter, w: int, h: int,
                       start_time: float, end_time: float):
        """Draw playhead position indicator."""
        if self._playhead_position < 0:
            return

        if not (start_time <= self._playhead_position <= end_time):
            return

        x = self._time_to_x(self._playhead_position, w, start_time, end_time)

        pen = QPen(self.COLOR_PLAYHEAD, 2)
        painter.setPen(pen)
        painter.drawLine(int(x), 0, int(x), h)

    def _time_to_x(self, time: float, w: int, start_time: float, end_time: float) -> int:
        """Convert time to x coordinate."""
        if end_time <= start_time:
            return 0
        return int((time - start_time) / (end_time - start_time) * w)

    def _x_to_time(self, x: int, w: int, start_time: float, end_time: float) -> float:
        """Convert x coordinate to time."""
        if w <= 0:
            return start_time
        return start_time + (x / w) * (end_time - start_time)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton and self._duration > 0:
            visible_duration = self._duration / self._zoom_level
            start_time = self._scroll_offset
            end_time = start_time + visible_duration

            time = self._x_to_time(event.pos().x(), self.width(), start_time, end_time)

            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                # Start selection
                self._is_selecting = True
                self._selection_start = time
                self._selection_end = time
            else:
                # Clear selection and emit click
                self._selection_start = -1
                self._selection_end = -1
                self.positionClicked.emit(time)

            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move."""
        if self._is_selecting and self._duration > 0:
            visible_duration = self._duration / self._zoom_level
            start_time = self._scroll_offset
            end_time = start_time + visible_duration

            self._selection_end = self._x_to_time(
                event.pos().x(), self.width(), start_time, end_time
            )
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if self._is_selecting:
            self._is_selecting = False

            if abs(self._selection_end - self._selection_start) > 0.1:
                start = min(self._selection_start, self._selection_end)
                end = max(self._selection_start, self._selection_end)
                self.regionSelected.emit(start, end)
            else:
                self._selection_start = -1
                self._selection_end = -1

            self.update()

    def wheelEvent(self, event):
        """Handle mouse wheel for zoom/scroll."""
        if self._duration <= 0:
            return

        delta = event.angleDelta().y()

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Zoom
            if delta > 0:
                self._zoom_level = min(50.0, self._zoom_level * 1.2)
            else:
                self._zoom_level = max(1.0, self._zoom_level / 1.2)
        else:
            # Scroll
            visible_duration = self._duration / self._zoom_level
            scroll_amount = visible_duration * 0.1

            if delta < 0:
                self._scroll_offset = min(
                    self._duration - visible_duration,
                    self._scroll_offset + scroll_amount
                )
            else:
                self._scroll_offset = max(0, self._scroll_offset - scroll_amount)

        self.update()
        event.accept()

    def get_motion_at_time(self, time: float) -> Optional[MotionData]:
        """
        Get motion data nearest to specified time.

        Args:
            time: Time in seconds

        Returns:
            MotionData if found, None otherwise
        """
        if not self._motion_data:
            return None

        # Binary search for nearest point
        nearest = min(self._motion_data, key=lambda d: abs(d.timestamp - time))
        return nearest

    def get_high_motion_regions(self) -> List[Tuple[float, float]]:
        """
        Get list of high-motion time regions.

        Returns:
            List of (start_time, end_time) tuples
        """
        if not self._motion_data:
            return []

        regions = []
        in_region = False
        region_start = 0.0

        for data in self._motion_data:
            if data.magnitude > self.HIGH_MOTION_THRESHOLD:
                if not in_region:
                    region_start = data.timestamp
                    in_region = True
            else:
                if in_region:
                    regions.append((region_start, data.timestamp))
                    in_region = False

        # Close any open region
        if in_region:
            regions.append((region_start, self._motion_data[-1].timestamp))

        return regions
