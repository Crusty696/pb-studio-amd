"""
Video-specific UI Widgets for PB Studio AMD.

Provides specialized widgets for video analysis and editing:
- SceneListWidget: Display and interact with detected scenes
- VideoInfoPanel: Show video metadata
- EncoderSettingsWidget: Configure AMD AMF encoder settings
- MotionVisualizationWidget: Visualize motion data as graph
"""

from .scene_list_widget import SceneListWidget, SceneInfo
from .video_info_panel import VideoInfoPanel, VideoMetadata
from .encoder_settings_widget import EncoderSettingsWidget
from .motion_visualization_widget import MotionVisualizationWidget, MotionData

__all__ = [
    "SceneListWidget",
    "SceneInfo",
    "VideoInfoPanel",
    "VideoMetadata",
    "EncoderSettingsWidget",
    "MotionVisualizationWidget",
    "MotionData",
]
