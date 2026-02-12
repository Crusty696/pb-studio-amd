"""
Waveform Widget for Audio Visualization

Renders audio waveform using PyQt6's QPainter.
Supports pan and zoom interactions.
"""
import logging
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen

logger = logging.getLogger(__name__)

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = None  # Audio samples (mono, normalized)
        self.sample_rate = 44100
        self.zoom_level = 1.0
        self.scroll_offset = 0
        self.beat_markers = []  # Beat-Marker Zeitstempel
        
        self.setMinimumHeight(100)
        self.setStyleSheet("background-color: #1e1e1e;")

    def load_audio(self, file_path: str):
        """Loads audio and extracts waveform data."""
        try:
            import librosa
            logger.info(f"Loading waveform for: {file_path}")
            
            # Load as mono, downsample for performance
            y, sr = librosa.load(file_path, sr=22050, mono=True)
            
            # Normalize to -1, 1 range
            if np.max(np.abs(y)) > 0:
                y = y / np.max(np.abs(y))
            
            self.samples = y
            self.sample_rate = sr
            self.scroll_offset = 0
            self.zoom_level = 1.0
            
            logger.info(f"Waveform loaded: {len(y)} samples, {sr}Hz")
            self.update()
            
        except Exception as e:
            logger.error(f"Failed to load waveform: {e}")
            self.samples = None
            
    def set_beat_markers(self, beats: list):
        """Sets beat markers (list of timestamps in seconds)."""
        self.beat_markers = beats
        self.update()

    def paintEvent(self, event):
        if self.samples is None or len(self.samples) == 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        mid_y = h // 2
        
        # Calculate visible range based on zoom
        total_samples = len(self.samples)
        visible_samples = int(total_samples / self.zoom_level)
        start_idx = max(0, self.scroll_offset)
        end_idx = min(total_samples, start_idx + visible_samples)
        
        if end_idx <= start_idx:
            return
        
        # Subsample for performance
        step = max(1, (end_idx - start_idx) // (w * 2))
        visible = self.samples[start_idx:end_idx:step]
        
        if len(visible) == 0:
            return
        
        # Draw waveform
        pen = QPen(QColor("#007acc"), 1)
        painter.setPen(pen)
        
        x_scale = w / len(visible)
        
        for i in range(len(visible) - 1):
            x1 = int(i * x_scale)
            x2 = int((i + 1) * x_scale)
            y1 = int(mid_y - visible[i] * (mid_y - 5))
            y2 = int(mid_y - visible[i + 1] * (mid_y - 5))
            painter.drawLine(x1, y1, x2, y2)
        
        # Draw center line
        pen = QPen(QColor("#3e3e42"), 1)
        painter.setPen(pen)
        painter.drawLine(0, mid_y, w, mid_y)
        
        # Draw Beat Markers (if any)
        if hasattr(self, 'beat_markers') and self.beat_markers:
            pen_beat = QPen(QColor("#ff4d4d"), 1)  # Red for beats
            pen_beat.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen_beat)
            
            # Start/End time of visible window
            start_time = start_idx / self.sample_rate
            end_time = end_idx / self.sample_rate
            
            # Map time to X
            duration = end_time - start_time
            if duration > 0:
                for beat_time in self.beat_markers:
                    # Check if beat is in visible range
                    if start_time <= beat_time <= end_time:
                        x = int((beat_time - start_time) / duration * w)
                        painter.drawLine(x, 0, x, h)

    def wheelEvent(self, event):
        """Zoom with mouse wheel."""
        delta = event.angleDelta().y()
        
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl + Wheel = Zoom
            if delta > 0:
                self.zoom_level = min(100.0, self.zoom_level * 1.2)
            else:
                self.zoom_level = max(1.0, self.zoom_level / 1.2)
        else:
            # Wheel = Scroll
            scroll_amount = int(len(self.samples) / 100) if self.samples is not None else 0
            if delta < 0:
                self.scroll_offset = min(len(self.samples) if self.samples is not None else 0, 
                                        self.scroll_offset + scroll_amount)
            else:
                self.scroll_offset = max(0, self.scroll_offset - scroll_amount)
        
        self.update()
        event.accept()

    def get_duration(self) -> float:
        """Returns duration in seconds."""
        if self.samples is not None and self.sample_rate > 0:
            return len(self.samples) / self.sample_rate
        return 0.0
