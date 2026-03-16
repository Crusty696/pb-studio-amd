from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class BeatMarkerWidget(QWidget):
    """Minimal transparent overlay for beat/downbeat markers."""

    beatClicked = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._beats = []
        self._downbeats = []
        self._visible_start = 0.0
        self._visible_end = 1.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_beats(self, beats):
        self._beats = [float(b) for b in beats or []]
        self.update()

    def set_downbeats(self, downbeats):
        self._downbeats = [float(b) for b in downbeats or []]
        self.update()

    def set_visible_range(self, start_time: float, end_time: float):
        self._visible_start = float(start_time)
        self._visible_end = max(float(end_time), self._visible_start + 1e-6)
        self.update()

    def clear(self):
        self._beats = []
        self._downbeats = []
        self.update()

    def _draw_markers(self, painter: QPainter, markers, color: str, width: int):
        if not markers:
            return

        pen = QPen(QColor(color))
        pen.setWidth(width)
        painter.setPen(pen)
        duration = max(self._visible_end - self._visible_start, 1e-6)

        for marker in markers:
            if self._visible_start <= marker <= self._visible_end:
                rel = (marker - self._visible_start) / duration
                x = int(rel * max(1, self.width() - 1))
                painter.drawLine(x, 0, x, self.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self._draw_markers(painter, self._beats, "#f59e0b", 1)
        self._draw_markers(painter, self._downbeats, "#ef4444", 2)
        painter.end()
