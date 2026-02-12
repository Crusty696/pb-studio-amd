"""
Audio-specific UI Widgets for PB Studio AMD

This module provides specialized widgets for audio visualization and processing:
- AudioInfoPanel: Display audio metadata (BPM, duration, sample rate, etc.)
- BeatMarkerWidget: Overlay widget for beat visualization on waveforms
- StemSeparatorWidget: UI for stem separation with progress tracking
- WaveformContainer: Combined waveform + beat marker container
"""

from .audio_info_panel import AudioInfoPanel
from .beat_marker_widget import BeatMarkerWidget
from .stem_separator_widget import StemSeparatorWidget
from .waveform_container import WaveformContainer

__all__ = [
    "AudioInfoPanel",
    "BeatMarkerWidget",
    "StemSeparatorWidget",
    "WaveformContainer",
]
