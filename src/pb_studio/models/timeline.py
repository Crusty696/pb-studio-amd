"""
Timeline-related data models for PB Studio AMD.

Contains dataclasses for cut planning, render segments, and timeline operations.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class TransitionType(Enum):
    """Video transition types between clips."""
    HARD_CUT = "cut"
    FADE = "fade"
    CROSSFADE = "crossfade"
    ZOOM = "zoom"
    SLIDE = "slide"


@dataclass
class CutPoint:
    """
    Represents a single cut decision in the video timeline.

    Contains timing information, energy levels, beat alignment data,
    and transition type for video editing decisions.
    """

    time: float  # Cut timestamp in seconds
    duration: float  # Clip duration in seconds
    energy: float = 0.5  # Local energy level (0.0 to 1.0)
    beat_aligned: bool = False  # Whether cut was aligned to a beat
    beat_strength: float = 0.0  # Strength of nearest beat (0.0 to 1.0)
    transition: TransitionType = TransitionType.HARD_CUT
    confidence: float = 1.0  # Algorithm confidence score (0.0 to 1.0)
    source_video_index: int = 0  # Index of source video to use
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def end_time(self) -> float:
        """Calculate end timestamp."""
        return self.time + self.duration

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "time": self.time,
            "duration": self.duration,
            "energy": self.energy,
            "beat_aligned": self.beat_aligned,
            "beat_strength": self.beat_strength,
            "transition": self.transition.value,
            "confidence": self.confidence,
            "source_video_index": self.source_video_index,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CutPoint":
        """Create instance from dictionary."""
        transition_value = data.get("transition", "cut")
        transition = TransitionType(transition_value) if isinstance(
            transition_value, str
        ) else TransitionType.HARD_CUT

        return cls(
            time=float(data["time"]),
            duration=float(data["duration"]),
            energy=float(data.get("energy", 0.5)),
            beat_aligned=bool(data.get("beat_aligned", False)),
            beat_strength=float(data.get("beat_strength", 0.0)),
            transition=transition,
            confidence=float(data.get("confidence", 1.0)),
            source_video_index=int(data.get("source_video_index", 0)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CutPlan:
    """
    Complete cut plan for a video generation session.

    Contains a list of cut points and metadata about the plan.
    """

    cuts: list[CutPoint]  # Ordered list of cut points
    total_duration: float  # Total timeline duration in seconds
    bpm: float = 120.0  # Detected BPM from audio analysis
    sync_mode: str = "hybrid"  # Synchronization mode used
    statistics: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Return number of cuts in the plan."""
        return len(self.cuts)

    def __iter__(self):
        """Iterate over cuts."""
        return iter(self.cuts)

    def __getitem__(self, index: int) -> CutPoint:
        """Get cut by index."""
        return self.cuts[index]

    @property
    def total_cuts(self) -> int:
        """Get total number of cuts."""
        return len(self.cuts)

    @property
    def avg_cut_duration(self) -> float:
        """Calculate average cut duration."""
        if not self.cuts:
            return 0.0
        return sum(c.duration for c in self.cuts) / len(self.cuts)

    @property
    def beat_aligned_ratio(self) -> float:
        """Calculate ratio of beat-aligned cuts."""
        if not self.cuts:
            return 0.0
        aligned = sum(1 for c in self.cuts if c.beat_aligned)
        return aligned / len(self.cuts)

    def get_cut_at_time(self, time: float) -> Optional[CutPoint]:
        """Find the cut point that contains a specific time."""
        for cut in self.cuts:
            if cut.time <= time < cut.end_time:
                return cut
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "cuts": [c.to_dict() for c in self.cuts],
            "total_duration": self.total_duration,
            "bpm": self.bpm,
            "sync_mode": self.sync_mode,
            "statistics": self.statistics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CutPlan":
        """Create instance from dictionary."""
        return cls(
            cuts=[CutPoint.from_dict(c) for c in data.get("cuts", [])],
            total_duration=float(data.get("total_duration", 0.0)),
            bpm=float(data.get("bpm", 120.0)),
            sync_mode=str(data.get("sync_mode", "hybrid")),
            statistics=data.get("statistics", {}),
        )


@dataclass
class RenderSegment:
    """
    Represents a single rendered video segment.

    Used to track individual segment rendering progress and output files.
    """

    segment_index: int  # Index of segment in the cut plan
    source_video: str  # Path to source video file
    start_time: float  # Start time in source video (seconds)
    duration: float  # Duration of segment (seconds)
    output_path: str  # Path to rendered segment file
    transition: TransitionType = TransitionType.HARD_CUT
    render_status: str = "pending"  # pending, rendering, completed, failed
    error_message: Optional[str] = None

    @property
    def end_time(self) -> float:
        """Calculate end time in source video."""
        return self.start_time + self.duration

    @property
    def is_completed(self) -> bool:
        """Check if segment rendering is complete."""
        return self.render_status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if segment rendering failed."""
        return self.render_status == "failed"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "segment_index": self.segment_index,
            "source_video": self.source_video,
            "start_time": self.start_time,
            "duration": self.duration,
            "output_path": self.output_path,
            "transition": self.transition.value,
            "render_status": self.render_status,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderSegment":
        """Create instance from dictionary."""
        transition_value = data.get("transition", "cut")
        transition = TransitionType(transition_value) if isinstance(
            transition_value, str
        ) else TransitionType.HARD_CUT

        return cls(
            segment_index=int(data["segment_index"]),
            source_video=str(data["source_video"]),
            start_time=float(data["start_time"]),
            duration=float(data["duration"]),
            output_path=str(data["output_path"]),
            transition=transition,
            render_status=str(data.get("render_status", "pending")),
            error_message=data.get("error_message"),
        )


@dataclass
class RenderResult:
    """
    Result of a complete video render operation.

    Contains all rendered segments and final output information.
    """

    segments: list[RenderSegment]  # All rendered segments
    final_output_path: Optional[str] = None  # Path to final concatenated video
    total_duration: float = 0.0  # Total duration of rendered video
    render_time_seconds: float = 0.0  # Time taken to render
    encoder_used: str = ""  # Encoder used (e.g., "h264_amf")
    is_hardware_accelerated: bool = False

    @property
    def total_segments(self) -> int:
        """Get total number of segments."""
        return len(self.segments)

    @property
    def completed_segments(self) -> int:
        """Get number of completed segments."""
        return sum(1 for s in self.segments if s.is_completed)

    @property
    def failed_segments(self) -> int:
        """Get number of failed segments."""
        return sum(1 for s in self.segments if s.is_failed)

    @property
    def is_complete(self) -> bool:
        """Check if all segments completed successfully."""
        return all(s.is_completed for s in self.segments)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "segments": [s.to_dict() for s in self.segments],
            "final_output_path": self.final_output_path,
            "total_duration": self.total_duration,
            "render_time_seconds": self.render_time_seconds,
            "encoder_used": self.encoder_used,
            "is_hardware_accelerated": self.is_hardware_accelerated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderResult":
        """Create instance from dictionary."""
        return cls(
            segments=[RenderSegment.from_dict(s) for s in data.get("segments", [])],
            final_output_path=data.get("final_output_path"),
            total_duration=float(data.get("total_duration", 0.0)),
            render_time_seconds=float(data.get("render_time_seconds", 0.0)),
            encoder_used=str(data.get("encoder_used", "")),
            is_hardware_accelerated=bool(data.get("is_hardware_accelerated", False)),
        )
