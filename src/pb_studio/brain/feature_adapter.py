"""Canonical real-data adapter shared by Brain scoring entry points."""

from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np

from .bridge_dimensions import CandidateFeatures


class CanonicalFeatureAdapter:
    def __init__(
        self,
        *,
        audio_analysis: Optional[dict] = None,
        video_analysis_by_clip: Optional[dict[str, dict]] = None,
        fallback_duration: float = 0.0,
        fallback_mood_tags: Optional[list[str]] = None,
    ) -> None:
        self.audio = dict(audio_analysis or {})
        self.video_by_clip = {
            str(key): dict(value)
            for key, value in (video_analysis_by_clip or {}).items()
        }
        self.duration_seconds = _nonnegative(
            self.audio.get("duration_seconds"),
            fallback_duration,
        )
        self.energy_curve = _normalize_unit_curve(
            self.audio.get("energy_curve")
        )
        normalized_centroids = self.audio.get("centroid_curve")
        if normalized_centroids is not None:
            self.centroid_curve = _normalize_unit_curve(normalized_centroids)
        else:
            spectral = self.audio.get("spectral_data") or {}
            self.centroid_curve = _normalize_percentile_curve(
                spectral.get("centroids")
            )
        audio_tags = self.audio.get("mood_tags") or fallback_mood_tags or []
        self.audio_mood_tags = _canonical_tags(audio_tags)
        self.audio_confidence = _analysis_confidence(self.audio)
        self.motion_scale = self._motion_scale()

    def candidate_features(
        self,
        *,
        clip_id: str,
        trigger_type: str,
        trigger_strength: float,
        cut_time_sec: float,
        cut_duration_sec: float,
        segment_type: Optional[str] = None,
        audio_embedding: Any = None,
        video_embedding: Any = None,
        semantic_status: Optional[str] = None,
        semantic_reason: Optional[str] = None,
    ) -> CandidateFeatures:
        video = self.video_by_clip.get(str(clip_id), {})
        raw_motion = _motion_value(video)
        normalized_motion = _clip01(raw_motion / self.motion_scale)
        explicit_pace = _optional_float(video.get("pace_class_score"))
        pace = (
            _clip01(explicit_pace)
            if explicit_pace is not None
            else normalized_motion
        )
        resolved_segment = _canonical_segment(
            segment_type or self._segment_at(cut_time_sec)
        )
        video_confidence = _analysis_confidence(video)
        confidence = min(self.audio_confidence, video_confidence)
        resolved_semantic_status, resolved_semantic_reason = (
            _semantic_availability(audio_embedding, video_embedding)
        )
        if semantic_status is not None:
            resolved_semantic_status = _canonical_semantic_status(
                semantic_status
            )
        if semantic_reason is not None:
            resolved_semantic_reason = str(semantic_reason)
        return CandidateFeatures(
            trigger_type=str(trigger_type or ""),
            trigger_strength=_clip01(trigger_strength),
            audio_energy=_value_at_time(
                self.energy_curve,
                cut_time_sec,
                self.duration_seconds,
            ),
            audio_centroid=_value_at_time(
                self.centroid_curve,
                cut_time_sec,
                self.duration_seconds,
            ),
            audio_embedding=audio_embedding,
            motion_score=normalized_motion,
            scene_distance_sec=_nearest_scene_distance(
                cut_time_sec,
                video.get("scenes") or video.get("scene_changes") or [],
            ),
            brightness=_clip01(video.get("avg_brightness", 0.5)),
            saturation=_clip01(video.get("avg_saturation", 0.5)),
            color_temp=max(
                -1.0,
                min(1.0, _finite_float(video.get("avg_color_temp"), 0.0)),
            ),
            pace_class_score=pace,
            video_embedding=video_embedding,
            mood_tags=_canonical_tags(video.get("mood_tags") or []),
            audio_mood_tags=list(self.audio_mood_tags),
            cut_duration_sec=max(_finite_float(cut_duration_sec, 0.01), 0.01),
            segment_type=resolved_segment,
            audio_confidence=self.audio_confidence,
            video_confidence=video_confidence,
            confidence=confidence,
            semantic_status=resolved_semantic_status,
            semantic_reason=resolved_semantic_reason,
            feature_provenance={
                "motion": {
                    "source": "avg_motion",
                    "raw": raw_motion,
                    "scale": self.motion_scale,
                    "unit": "normalized_pool_p95",
                },
                "pace": {
                    "source": (
                        "pace_class_score"
                        if explicit_pace is not None
                        else "normalized_motion"
                    ),
                    "unit": "normalized_0_1",
                },
                "mood": {"source": "analysis_mood_tags"},
                "segment_type": {"source": "structure_segments"},
                "confidence": {
                    "source": "analysis_status",
                    "audio": self.audio_confidence,
                    "video": video_confidence,
                },
                "semantic": {
                    "status": resolved_semantic_status,
                    "reason": resolved_semantic_reason,
                },
            },
        )

    def normalized_motion_curve(self, clip_id: str) -> list[float]:
        video = self.video_by_clip.get(str(clip_id), {})
        nested = video.get("motion") or {}
        values = video.get("motion_curve")
        # Audit 2026-08-05 (H-7/T2.5): Der Fallback prueft auf "is None", der
        # Top-Level-Key ist aber ein Migrations-Default `[]` — also nicht None,
        # sondern leer. Der Fallback auf die verschachtelte, real gefuellte
        # Variante griff dadurch NIE: das Brain sah bei allen 1359 analysierten
        # Clips leere Motion-Kurven, obwohl die Daten direkt danebenlagen.
        # Truthiness statt Identitaetsvergleich (PEP 8: leere Sequenzen sind falsy).
        if not values and isinstance(nested, dict):
            values = nested.get("motion_curve")
        if not values:
            return []
        return [
            _clip01(_finite_float(value, 0.0) / self.motion_scale)
            for value in values
        ]

    def _motion_scale(self) -> float:
        values = [
            _motion_value(video)
            for video in self.video_by_clip.values()
        ]
        positive = np.asarray(
            [value for value in values if value > 0.0],
            dtype=np.float32,
        )
        if positive.size == 0:
            return 1.0
        scale = float(np.percentile(positive, 95))
        return scale if scale > 1e-6 else 1.0

    def _segment_at(self, time_sec: float) -> str:
        segments = (
            self.audio.get("structure_segments")
            or self.audio.get("subtrack_segments")
            or []
        )
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            start = _nonnegative(segment.get("start_time"), 0.0)
            end = _nonnegative(segment.get("end_time"), start)
            if start <= time_sec < end:
                return str(segment.get("label") or segment.get("type") or "")
        return "transition"


def _analysis_confidence(data: dict) -> float:
    explicit = _optional_float(
        data.get("analysis_confidence", data.get("confidence"))
    )
    if explicit is not None:
        return _clip01(explicit)
    status = str(
        data.get("_analysis_status")
        or data.get("analysis_status")
        or ""
    ).lower()
    if status == "completed":
        return 1.0
    if status == "partial":
        return 0.5
    if status in {"failed", "unavailable"}:
        return 0.0
    return 1.0 if data.get("is_analyzed") is True else 0.0


def _motion_value(video: dict) -> float:
    nested = video.get("motion") or {}
    for value in (
        video.get("avg_motion"),
        video.get("motion_score"),
        nested.get("avg_motion") if isinstance(nested, dict) else None,
    ):
        parsed = _optional_float(value)
        if parsed is not None:
            return max(parsed, 0.0)
    return 0.0


def _normalize_unit_curve(values: Any) -> list[float]:
    if values is None:
        return []
    return [_clip01(value) for value in values]


def _normalize_percentile_curve(values: Any) -> list[float]:
    if values is None:
        return []
    arr = np.asarray(list(values), dtype=np.float32)
    if arr.size == 0:
        return []
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    scale = float(np.percentile(arr, 95))
    if scale <= 1e-6:
        return []
    return np.clip(arr / scale, 0.0, 1.0).tolist()


def _value_at_time(curve: list[float], time_sec: float, duration: float) -> float:
    if not curve or duration <= 0.0:
        return 0.0
    position = max(0.0, min(1.0, float(time_sec) / duration))
    index = min(len(curve) - 1, int(position * len(curve)))
    return float(curve[index])


def _nearest_scene_distance(time_sec: float, scenes: list) -> float:
    distances: list[float] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        for key in ("start_time", "end_time", "time"):
            value = _optional_float(scene.get(key))
            if value is not None:
                distances.append(abs(float(time_sec) - value))
    return min(distances) if distances else 1.0


def _canonical_tags(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    return sorted({
        str(value).strip().lower()
        for value in values
        if str(value).strip()
    })


def _canonical_segment(value: Any) -> str:
    raw = str(value or "transition").strip().lower()
    aliases = {
        "buildup": "build",
        "build-up": "build",
        "breakdown": "break",
        "chorus": "drop",
        "verse": "verse",
        "intro": "intro",
        "outro": "outro",
        "bridge": "transition",
    }
    canonical = aliases.get(raw, raw)
    allowed = {"intro", "verse", "build", "drop", "break", "outro", "transition"}
    return canonical if canonical in allowed else "transition"


def _semantic_availability(
    audio_embedding: Any,
    video_embedding: Any,
) -> tuple[str, str]:
    audio = _valid_embedding(audio_embedding)
    video = _valid_embedding(video_embedding)
    if audio is None and video is None:
        return "unavailable", "audio_and_video_embeddings_missing"
    if audio is None:
        return "partial", "audio_embedding_missing_or_invalid"
    if video is None:
        return "partial", "video_embedding_missing_or_invalid"
    if audio.size != video.size:
        return "partial", "projected_embedding_dimensions_mismatch"
    return "available", "projected_embeddings_available"


def _valid_embedding(value: Any) -> Optional[np.ndarray]:
    if value is None:
        return None
    try:
        embedding = np.asarray(value, dtype=np.float32).reshape(-1)
    except (TypeError, ValueError):
        return None
    if (
        embedding.size == 0
        or not np.all(np.isfinite(embedding))
        or float(np.linalg.norm(embedding)) <= 1e-9
    ):
        return None
    return embedding


def _canonical_semantic_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    return status if status in {"available", "partial", "unavailable"} else "unavailable"


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _finite_float(value, 0.0)))


def _nonnegative(value: Any, fallback: float) -> float:
    return max(_finite_float(value, fallback), 0.0)


def _optional_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _finite_float(value: Any, fallback: float) -> float:
    parsed = _optional_float(value)
    return parsed if parsed is not None else float(fallback)
