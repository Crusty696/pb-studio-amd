"""
PB Studio UI Widgets

Contains all UI widget components for the application.

Widget Categories:
- Main widgets: Dashboard, Player, Waveform, Analysis, Generation, Settings, Editor
- Common widgets: ProgressCard, ResultCard, TimelineWidget, FileDropMixin
- Audio widgets: AudioInfoPanel, BeatMarkerWidget, StemSeparatorWidget, WaveformContainer
- Video widgets: SceneListWidget, VideoInfoPanel, EncoderSettingsWidget, MotionVisualizationWidget
- Generation widgets: PacingConfigWidget, ClipSelectorWidget, RenderProgressWidget, GenerationContainer
"""

# Main widgets
from .dashboard import DashboardWidget
from .player_widget import PlayerWidget
from .waveform_widget import WaveformWidget
from .analysis_widget import AnalysisWidget
from .generation_widget import GenerationWidget
from .settings_widget import SettingsWidget
from .editor_widget import EditorWidget
from .library_browser import LibraryBrowserWidget as LibraryBrowser

# Common reusable widgets
from .common import (
    ProgressCard,
    ResultCard,
    TimelineWidget,
    FileDropMixin,
)

# Audio-specific widgets
from .audio import (
    AudioInfoPanel,
    BeatMarkerWidget,
    StemSeparatorWidget,
    WaveformContainer,
)

# Video-specific widgets
from .video import (
    SceneListWidget,
    SceneInfo,
    VideoInfoPanel,
    VideoMetadata,
    EncoderSettingsWidget,
    MotionVisualizationWidget,
    MotionData,
)

# Generation step widgets
from .generation import (
    PacingConfigWidget,
    ClipSelectorWidget,
    RenderProgressWidget,
    GenerationContainer,
)

__all__ = [
    # Main widgets
    'DashboardWidget',
    'PlayerWidget',
    'WaveformWidget',
    'AnalysisWidget',
    'GenerationWidget',
    'SettingsWidget',
    'EditorWidget',
    'LibraryBrowser',

    # Common widgets
    'ProgressCard',
    'ResultCard',
    'TimelineWidget',
    'FileDropMixin',

    # Audio widgets
    'AudioInfoPanel',
    'BeatMarkerWidget',
    'StemSeparatorWidget',
    'WaveformContainer',

    # Video widgets
    'SceneListWidget',
    'SceneInfo',
    'VideoInfoPanel',
    'VideoMetadata',
    'EncoderSettingsWidget',
    'MotionVisualizationWidget',
    'MotionData',

    # Generation widgets
    'PacingConfigWidget',
    'ClipSelectorWidget',
    'RenderProgressWidget',
    'GenerationContainer',
]
