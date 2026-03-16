import logging
from pathlib import Path

import librosa
import numpy as np
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class WaveformWidget(QWidget):
    """Lightweight compatibility waveform widget for PyQt verification/debug flows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = None
        self.sample_rate = 44100
        self.duration = 0.0
        self.zoom_level = 1.0
        self.scroll_offset = 0
        self._beat_markers = []
        self._cached_pixmap = None
        self.setMinimumHeight(60)

    def load_audio(self, file_path: str):
        file_path = str(Path(file_path))
        logger.info("Loading waveform audio: %s", file_path)
        samples, sample_rate = librosa.load(file_path, sr=None, mono=True)
        self.samples = np.asarray(samples, dtype=np.float32)
        self.sample_rate = int(sample_rate)
        self.duration = float(len(self.samples) / self.sample_rate) if self.sample_rate else 0.0
        self.scroll_offset = 0
        self._cached_pixmap = None
        self.update()

    def get_duration(self) -> float:
        return self.duration

    def set_beat_markers(self, beats):
        self._beat_markers = [float(b) for b in beats or []]
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.zoom_level = max(1.0, min(100.0, self.zoom_level * factor))
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.zoom_level = 1.0
        self.scroll_offset = 0
        self.update()
        event.accept()

    def _build_waveform_pixmap(self) -> QPixmap | None:
        if self.samples is None or len(self.samples) == 0 or self.width() <= 0 or self.height() <= 0:
            return None

        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("#1e1e1e"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor("#34d399"))
        pen.setWidth(1)
        painter.setPen(pen)

        total_samples = len(self.samples)
        visible_samples = max(1, int(total_samples / self.zoom_level))
        start_idx = max(0, min(self.scroll_offset, max(0, total_samples - 1)))
        end_idx = min(total_samples, start_idx + visible_samples)
        visible = self.samples[start_idx:end_idx]
        if len(visible) == 0:
            painter.end()
            return pixmap

        width = max(1, self.width())
        step = max(1, len(visible) // width)
        center_y = self.height() / 2
        amplitude = max(float(np.max(np.abs(visible))), 1e-6)
        x = 0
        for idx in range(0, len(visible), step):
            chunk = visible[idx:idx + step]
            if len(chunk) == 0:
                continue
            peak = float(np.max(np.abs(chunk))) / amplitude
            half_height = peak * (self.height() * 0.42)
            painter.drawLine(x, int(center_y - half_height), x, int(center_y + half_height))
            x += 1
            if x >= width:
                break

        if self._beat_markers and self.duration > 0:
            beat_pen = QPen(QColor("#f59e0b"))
            beat_pen.setWidth(1)
            painter.setPen(beat_pen)
            visible_start = start_idx / self.sample_rate
            visible_end = end_idx / self.sample_rate
            visible_duration = max(visible_end - visible_start, 1e-6)
            for beat in self._beat_markers:
                if visible_start <= beat <= visible_end:
                    rel = (beat - visible_start) / visible_duration
                    beat_x = int(rel * max(1, self.width() - 1))
                    painter.drawLine(beat_x, 0, beat_x, self.height())

        painter.end()
        return pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        if self.samples is None or len(self.samples) == 0:
            painter.setPen(QColor("#666666"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No waveform loaded")
            painter.end()
            return

        pixmap = self._build_waveform_pixmap()
        if pixmap is not None:
            painter.drawPixmap(0, 0, pixmap)
        painter.end()
