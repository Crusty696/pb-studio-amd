"""
Video-related data models for PB Studio AMD.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VideoMetadata:
    """Metadata for a video file."""

    duration: float  # Duration in seconds
    fps: float  # Frames per second
    width: int  # Width in pixels
    height: int  # Height in pixels
    codec: str  # Video codec (e.g., 'h264', 'hevc')
    has_audio: bool  # Whether video contains audio track
    bitrate: Optional[int] = None  # Bitrate in bits per second

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "duration": self.duration,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "codec": self.codec,
            "has_audio": self.has_audio,
            "bitrate": self.bitrate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoMetadata":
        """Create instance from dictionary."""
        return cls(
            duration=float(data["duration"]),
            fps=float(data["fps"]),
            width=int(data["width"]),
            height=int(data["height"]),
            codec=str(data["codec"]),
            has_audio=bool(data["has_audio"]),
            bitrate=int(data["bitrate"]) if data.get("bitrate") else None,
        )

    @property
    def resolution(self) -> str:
        """Return resolution as string (e.g., '1920x1080')."""
        return f"{self.width}x{self.height}"

    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio."""
        return self.width / self.height if self.height > 0 else 0.0

    @property
    def total_frames(self) -> int:
        """Calculate total number of frames."""
        return int(self.duration * self.fps)


@dataclass
class SceneInfo:
    """Information about a detected scene in the video."""

    start: float  # Start time in seconds
    end: float  # End time in seconds
    duration: float  # Duration in seconds
    thumbnail_path: Optional[str] = None  # Path to scene thumbnail
    scene_index: int = 0  # Index of the scene (0-based)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "thumbnail_path": self.thumbnail_path,
            "scene_index": self.scene_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneInfo":
        """Create instance from dictionary."""
        return cls(
            start=float(data["start"]),
            end=float(data["end"]),
            duration=float(data["duration"]),
            thumbnail_path=data.get("thumbnail_path"),
            scene_index=int(data.get("scene_index", 0)),
        )

    def contains_time(self, time: float) -> bool:
        """Check if a time point falls within this scene."""
        return self.start <= time < self.end

    @property
    def midpoint(self) -> float:
        """Get the midpoint time of the scene."""
        return (self.start + self.end) / 2


@dataclass
class MotionData:
    """Motion analysis data for a scene or video segment."""

    scene_index: int  # Index of the corresponding scene
    avg_motion: float  # Average motion intensity (0-1)
    max_motion: float  # Maximum motion intensity (0-1)
    motion_curve: list[float]  # Motion values over time
    timestamps: list[float] = field(default_factory=list)  # Timestamps for motion_curve

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scene_index": self.scene_index,
            "avg_motion": self.avg_motion,
            "max_motion": self.max_motion,
            "motion_curve": self.motion_curve,
            "timestamps": self.timestamps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotionData":
        """Create instance from dictionary."""
        return cls(
            scene_index=int(data["scene_index"]),
            avg_motion=float(data["avg_motion"]),
            max_motion=float(data["max_motion"]),
            motion_curve=[float(m) for m in data["motion_curve"]],
            timestamps=[float(t) for t in data.get("timestamps", [])],
        )

    @property
    def is_high_motion(self) -> bool:
        """Check if this is a high-motion scene (threshold: 0.5)."""
        return self.avg_motion > 0.5

    def get_motion_at_time(self, target_time: float) -> Optional[float]:
        """Get motion value at a specific time."""
        if not self.timestamps or not self.motion_curve:
            return None

        for i, t in enumerate(self.timestamps):
            if t >= target_time:
                return self.motion_curve[i]

        return self.motion_curve[-1] if self.motion_curve else None


@dataclass
class VideoAnalysisResult:
    """Complete video analysis result."""

    scenes: list[SceneInfo]  # Detected scenes
    motion_data: list[MotionData]  # Motion analysis per scene
    captions: list[dict[str, Any]] = field(default_factory=list)  # Auto-generated captions
    tags: list[str] = field(default_factory=list)  # Content tags
    dominant_colors: list[str] = field(default_factory=list)  # Dominant colors (hex)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scenes": [s.to_dict() for s in self.scenes],
            "motion_data": [m.to_dict() for m in self.motion_data],
            "captions": self.captions,
            "tags": self.tags,
            "dominant_colors": self.dominant_colors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoAnalysisResult":
        """Create instance from dictionary."""
        return cls(
            scenes=[SceneInfo.from_dict(s) for s in data["scenes"]],
            motion_data=[MotionData.from_dict(m) for m in data["motion_data"]],
            captions=data.get("captions", []),
            tags=data.get("tags", []),
            dominant_colors=data.get("dominant_colors", []),
        )

    @property
    def total_scenes(self) -> int:
        """Get total number of scenes."""
        return len(self.scenes)

    @property
    def total_duration(self) -> float:
        """Calculate total duration from scenes."""
        if not self.scenes:
            return 0.0
        return self.scenes[-1].end

    def get_scene_at_time(self, time: float) -> Optional[SceneInfo]:
        """Find the scene that contains a specific time point."""
        for scene in self.scenes:
            if scene.contains_time(time):
                return scene
        return None

    def get_high_motion_scenes(self) -> list[SceneInfo]:
        """Get all scenes with high motion."""
        high_motion_indices = {
            m.scene_index for m in self.motion_data if m.is_high_motion
        }
        return [s for s in self.scenes if s.scene_index in high_motion_indices]

    def get_motion_for_scene(self, scene_index: int) -> Optional[MotionData]:
        """Get motion data for a specific scene."""
        for m in self.motion_data:
            if m.scene_index == scene_index:
                return m
        return None
