"""Audio processing module for PB Studio AMD.

This module provides:
- Beat detection and tempo analysis (BeatNet)
- Stem separation (Demucs with DirectML)
- 3-band waveform analysis (Rekordbox-style)
- Waveform caching for performance
"""

from .analyzer import AudioAnalyzer
from .separator import StemSeparator
from .waveform_analyzer import WaveformAnalyzer
from .waveform_cache import WaveformCache

__all__ = [
    'AudioAnalyzer',
    'StemSeparator',
    'WaveformAnalyzer',
    'WaveformCache',
]
