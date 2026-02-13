"""
Audio-related data models for PB Studio AMD.
"""

import bisect
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AudioMetadata:
    """Metadata for an audio file."""

    duration: float  # Duration in seconds
    sample_rate: int  # Sample rate in Hz
    channels: int  # Number of audio channels
    codec: str  # Audio codec (e.g., 'aac', 'mp3', 'flac')

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "codec": self.codec,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioMetadata":
        """Create instance from dictionary."""
        return cls(
            duration=float(data["duration"]),
            sample_rate=int(data["sample_rate"]),
            channels=int(data["channels"]),
            codec=str(data["codec"]),
        )


@dataclass
class BeatInfo:
    """Information about a single beat in the audio."""

    time: float  # Time position in seconds
    beat_index: int  # Index of the beat (0-based)
    is_downbeat: bool  # True if this is a downbeat (first beat of measure)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "time": self.time,
            "beat_index": self.beat_index,
            "is_downbeat": self.is_downbeat,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BeatInfo":
        """Create instance from dictionary."""
        return cls(
            time=float(data["time"]),
            beat_index=int(data["beat_index"]),
            is_downbeat=bool(data["is_downbeat"]),
        )


@dataclass
class AudioAnalysisResult:
    """Result of audio analysis including BPM and beat detection."""

    bpm: float  # Detected beats per minute
    beat_times: list[float]  # Timestamps of all beats in seconds
    downbeat_times: list[float]  # Timestamps of downbeats only
    energy_curve: list[float]  # Energy values over time (normalized 0-1)
    energy_times: list[float] = field(default_factory=list)  # Zeitachse fuer energy_curve
    confidence: float = 0.0  # Confidence score of the analysis (0-1)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "bpm": self.bpm,
            "beat_times": self.beat_times,
            "downbeat_times": self.downbeat_times,
            "energy_curve": self.energy_curve,
            "energy_times": self.energy_times,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioAnalysisResult":
        """Create instance from dictionary."""
        return cls(
            bpm=float(data.get("bpm", 0)),
            beat_times=[float(t) for t in data.get("beat_times", [])],
            downbeat_times=[float(t) for t in data.get("downbeat_times", [])],
            energy_curve=[float(e) for e in data.get("energy_curve", [])],
            energy_times=[float(t) for t in data.get("energy_times", [])],
            confidence=float(data.get("confidence", 0)),
        )

    @classmethod
    def from_analyzer_output(cls, data: dict[str, Any]) -> "AudioAnalysisResult":
        """Create from AudioAnalyzer.analyze_file() output.

        Transformiert das Analyzer-Format {bpm, beat_data, count}
        in das standardisierte AudioAnalysisResult-Format.
        """
        beat_data = data.get("beat_data", [])
        # BeatNet gibt [[time, beat_type], ...] zurueck
        beat_times = [float(b[0]) for b in beat_data] if beat_data else []
        # Downbeats: beat_type == 1
        downbeat_times = [
            float(b[0]) for b in beat_data
            if len(b) > 1 and int(b[1]) == 1
        ] if beat_data else []
        return cls(
            bpm=float(data.get("bpm", 0)),
            beat_times=beat_times,
            downbeat_times=downbeat_times,
            energy_curve=data.get("energy_curve", []),
            energy_times=data.get("energy_times", []),
            confidence=1.0 if data.get("bpm", 0) > 0 else 0.0,
        )

    def get_beats(self) -> list[BeatInfo]:
        """Generate BeatInfo objects for all beats."""
        beats = []
        downbeats_sorted = sorted(self.downbeat_times)
        for i, time in enumerate(self.beat_times):
            # Binaere Suche statt linearer O(n*m) Iteration
            idx = bisect.bisect_left(downbeats_sorted, time - 0.01)
            is_downbeat = (
                idx < len(downbeats_sorted)
                and abs(downbeats_sorted[idx] - time) < 0.01
            )
            beats.append(BeatInfo(time=time, beat_index=i, is_downbeat=is_downbeat))
        return beats


@dataclass
class StemResult:
    """Result of audio stem separation."""

    vocals_path: Optional[str]  # Path to separated vocals
    instrumental_path: Optional[str]  # Path to instrumental track
    drums_path: Optional[str]  # Path to drums track
    bass_path: Optional[str]  # Path to bass track
    other_path: Optional[str] = None  # Path to other stems (if available)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "vocals_path": self.vocals_path,
            "instrumental_path": self.instrumental_path,
            "drums_path": self.drums_path,
            "bass_path": self.bass_path,
            "other_path": self.other_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StemResult":
        """Create instance from dictionary."""
        return cls(
            vocals_path=data.get("vocals_path"),
            instrumental_path=data.get("instrumental_path"),
            drums_path=data.get("drums_path"),
            bass_path=data.get("bass_path"),
            other_path=data.get("other_path"),
        )

    def get_available_stems(self) -> dict[str, str]:
        """Return dictionary of available stems (non-None paths)."""
        stems = {}
        if self.vocals_path:
            stems["vocals"] = self.vocals_path
        if self.instrumental_path:
            stems["instrumental"] = self.instrumental_path
        if self.drums_path:
            stems["drums"] = self.drums_path
        if self.bass_path:
            stems["bass"] = self.bass_path
        if self.other_path:
            stems["other"] = self.other_path
        return stems


@dataclass
class AudioEmbeddingResult:
    """Result of audio embedding extraction for similarity matching."""

    embeddings: list[list[float]]  # 2D array of embedding vectors
    timestamps: list[float]  # Corresponding timestamps for each embedding
    model_name: str = "default"  # Name of the embedding model used
    embedding_dim: int = 0  # Dimension of embedding vectors

    def __post_init__(self):
        """Calculate embedding dimension after initialization."""
        if self.embeddings and len(self.embeddings) > 0:
            self.embedding_dim = len(self.embeddings[0])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "embeddings": self.embeddings,
            "timestamps": self.timestamps,
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioEmbeddingResult":
        """Create instance from dictionary."""
        return cls(
            embeddings=[[float(v) for v in emb] for emb in data["embeddings"]],
            timestamps=[float(t) for t in data["timestamps"]],
            model_name=data.get("model_name", "default"),
            embedding_dim=int(data.get("embedding_dim", 0)),
        )

    def get_embedding_at_time(self, target_time: float) -> Optional[list[float]]:
        """Get the embedding vector closest to the target time."""
        if not self.timestamps or not self.embeddings:
            return None

        # Find closest timestamp
        min_diff = float("inf")
        closest_idx = 0
        for i, t in enumerate(self.timestamps):
            diff = abs(t - target_time)
            if diff < min_diff:
                min_diff = diff
                closest_idx = i

        return self.embeddings[closest_idx]
