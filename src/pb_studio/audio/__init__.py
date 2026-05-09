"""Audio processing module for PB Studio AMD.

This module provides:
- Beat detection and tempo analysis (BeatNet CPU)
- Stem separation (Demucs with DirectML)
- 3-band waveform analysis (Rekordbox-style)
- Waveform caching for performance
- 8-band spectral analysis
- Anchor feature extraction (20-dim vectors)
- DJ-Mix transition & energy-phase detection
- Song structure segmentation (verse/chorus/bridge...)
- Streaming analysis for long files (1-4h)
"""

try:
    from .analyzer import AudioAnalyzer
except ImportError:
    pass

try:
    from .separator import StemSeparator
except ImportError:
    pass

try:
    from .waveform_analyzer import WaveformAnalyzer
except ImportError:
    pass

try:
    from .waveform_cache import WaveformCache
except ImportError:
    pass

# Neue Module (lazy imports für schnelleren App-Start)
try:
    from .beat_detector import BeatDetector, get_beat_detector, is_beatnet_available
except ImportError:
    pass

try:
    from .spectral_analyzer import SpectralAnalyzer, FREQUENCY_BANDS, BAND_NAMES
except ImportError:
    pass

try:
    from .anchor_features import AnchorFeatureExtractor
except ImportError:
    pass

try:
    from .dj_mix_analyzer import DJMixAnalyzer, ENERGY_PHASES
except ImportError:
    pass

try:
    from .structure_analyzer import StructureAnalyzer, SEGMENT_LABELS
except ImportError:
    pass

try:
    from .streaming_analyzer import StreamingAudioAnalyzer, StreamingAnalysisResult
except ImportError:
    pass

__all__ = [
    'AudioAnalyzer',
    'StemSeparator',
    'WaveformAnalyzer',
    'WaveformCache',
    'BeatDetector',
    'get_beat_detector',
    'is_beatnet_available',
    'SpectralAnalyzer',
    'FREQUENCY_BANDS',
    'BAND_NAMES',
    'AnchorFeatureExtractor',
    'DJMixAnalyzer',
    'ENERGY_PHASES',
    'StructureAnalyzer',
    'SEGMENT_LABELS',
    'StreamingAudioAnalyzer',
    'StreamingAnalysisResult',
]
