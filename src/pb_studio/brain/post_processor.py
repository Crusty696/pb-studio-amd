"""Brain post-processor for cut lists (Plan Phase 4 lite).

Reads cached audio analysis + video motion data, derives CutContext,
attaches brain_scores per axis, optionally filters by min confidence.

Persists cuts (id, brain_scores_json, metadata.context_keys) into the
project state.db so /brain/feedback can later look them up.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from .bridge_dimensions import BRIDGE_AXES, BridgeDimensions, CandidateFeatures
from .context_resolver import ContextResolver
from .weight_store import WeightStore

logger = logging.getLogger(__name__)


def annotate_cuts_with_brain(
    cuts: list[dict[str, Any]],
    *,
    weight_store: WeightStore,
    audio_analysis: Optional[dict] = None,
    video_analysis_by_clip: Optional[dict[str, dict]] = None,
    audio_clip_id: Optional[int] = None,
    audio_path: Optional[str] = None,
    persist_to_state_conn: Optional[sqlite3.Connection] = None,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """Returns cuts with `metadata.brain_scores` and `metadata.context_keys`.

    Cuts below `min_confidence` (final mean score) are filtered out.
    """
    if not cuts:
        return cuts

    bridge = BridgeDimensions()
    resolver = ContextResolver()
    audio_analysis = audio_analysis or {}
    video_analysis_by_clip = video_analysis_by_clip or {}

    audio_mood_tags: list[str] = list(audio_analysis.get("mood_tags") or [])
    energy_curve = audio_analysis.get("energy_curve") or []
    subtrack_segments = audio_analysis.get("subtrack_segments") or []

    out: list[dict[str, Any]] = []
    timeline_id = _ensure_timeline(persist_to_state_conn, audio_clip_id)

    for idx, cut in enumerate(cuts):
        start = float(cut.get("start_time", 0.0))
        end = float(cut.get("end_time", start + 1.0))
        clip_id = str(cut.get("clip_id", ""))

        # subtrack-window for this cut time
        sub_start, sub_end = _enclosing_subtrack(start, subtrack_segments)
        # rough audio energy at this time (linear scan over curve)
        a_energy = _value_at_time(energy_curve, start, audio_analysis.get("duration_seconds", 0.0))

        v = video_analysis_by_clip.get(clip_id, {})
        motion = float(v.get("avg_motion") or 0.0)
        v_pace = _video_pace_score(v)

        ctx = resolver.resolve(
            section_type=str(cut.get("metadata", {}).get("segment_type") or "transition"),
            cut_time_sec=start,
            subtrack_start_sec=sub_start,
            subtrack_end_sec=sub_end,
            audio_energy=a_energy,
            audio_mood_tags=audio_mood_tags,
            video_motion_score=motion,
            video_pace_class_value=v_pace,
            energy_curve_full=energy_curve,
            motion_curve_full=v.get("motion_curve") or None,
        )

        feats = CandidateFeatures(
            trigger_type=str(cut.get("metadata", {}).get("trigger_type") or ""),
            trigger_strength=float(cut.get("metadata", {}).get("trigger_strength") or 0.0),
            audio_energy=a_energy,
            audio_centroid=0.5,
            motion_score=motion,
            scene_distance_sec=0.5,  # not modelled in cut metadata yet
            brightness=float(v.get("avg_brightness") or 0.5),
            saturation=float(v.get("avg_saturation") or 0.5),
            color_temp=float(v.get("avg_color_temp") or 0.0),
            pace_class_score=v_pace,
            mood_tags=list(v.get("mood_tags") or []),
            audio_mood_tags=audio_mood_tags,
            cut_duration_sec=max(end - start, 0.01),
        )

        bridge_values = bridge.compute_all(feats)
        scores: dict[str, float] = {}
        for axis in BRIDGE_AXES:
            bv = float(bridge_values.get(axis, 0.0))
            w = float(weight_store.get_posterior_mean(axis, ctx.context_keys))
            scores[axis] = round(bv * w, 6)

        final_score = sum(scores.values()) / len(scores) if scores else 0.0

        if final_score < min_confidence:
            continue

        new_cut = dict(cut)
        meta = dict(new_cut.get("metadata") or {})
        meta["brain_scores"] = scores
        meta["context_keys"] = ctx.context_keys
        meta["brain_final_score"] = round(final_score, 6)
        new_cut["metadata"] = meta
        out.append(new_cut)

        if persist_to_state_conn is not None and timeline_id is not None:
            cut_db_id = _persist_cut(
                persist_to_state_conn, timeline_id, idx, new_cut, scores, ctx,
            )
            if cut_db_id is not None:
                meta["cut_id"] = cut_db_id

    return out


# ---------- helpers ----------

def _enclosing_subtrack(t: float, segs: list) -> tuple[float, float]:
    if not segs:
        return 0.0, max(t * 2.0, 1.0)
    for s in segs:
        if isinstance(s, dict):
            a = float(s.get("start_time", 0.0))
            b = float(s.get("end_time", a + 1.0))
        else:
            a = float(getattr(s, "start_time", 0.0))
            b = float(getattr(s, "end_time", a + 1.0))
        if a <= t < b:
            return a, b
    s = segs[0]
    if isinstance(s, dict):
        return float(s.get("start_time", 0.0)), float(s.get("end_time", 1.0))
    return float(getattr(s, "start_time", 0.0)), float(getattr(s, "end_time", 1.0))


def _value_at_time(curve, t: float, total_dur: float) -> float:
    if curve is None or len(curve) == 0 or total_dur <= 0:
        return 0.5
    arr = np.asarray(list(curve), dtype=np.float32)
    idx = int(min(arr.size - 1, max(0, t / total_dur * arr.size)))
    return float(max(0.0, min(1.0, arr[idx])))


def _video_pace_score(v: dict) -> float:
    cat = (v.get("motion_category") or "medium").lower()
    return {"low": 0.2, "medium": 0.5, "high": 0.8, "extreme": 1.0}.get(cat, 0.5)


def _ensure_timeline(
    conn: Optional[sqlite3.Connection], audio_clip_id: Optional[int]
) -> Optional[int]:
    if conn is None:
        return None
    now = datetime.now(timezone.utc).isoformat()
    aud = int(audio_clip_id) if audio_clip_id is not None else 0
    # Mark all existing as not current, insert new.
    conn.execute("UPDATE timelines SET is_current = 0")
    cur = conn.execute(
        "INSERT INTO timelines (audio_clip_id, created_at, is_current) "
        "VALUES (?, ?, 1)",
        (aud, now),
    )
    return int(cur.lastrowid) if cur.lastrowid else None


def _persist_cut(
    conn: sqlite3.Connection,
    timeline_id: int,
    idx: int,
    cut: dict,
    scores: dict[str, float],
    ctx,
) -> Optional[int]:
    md = dict(cut.get("metadata") or {})
    md.setdefault("context_keys", ctx.context_keys)
    cur = conn.execute(
        "INSERT INTO timeline_cuts (timeline_id, position_idx, clip_id, "
        "start_time, end_time, clip_start, trigger_type, trigger_strength, "
        "segment_type, brain_scores_json, metadata_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            int(timeline_id),
            int(idx),
            str(cut.get("clip_id", "")),
            float(cut.get("start_time", 0.0)),
            float(cut.get("end_time", 0.0)),
            float(md.get("clip_start", 0.0)),
            str(md.get("trigger_type", "")),
            float(md.get("trigger_strength", 0.0)),
            str(md.get("segment_type", "")),
            json.dumps(scores),
            json.dumps(md),
        ),
    )
    return int(cur.lastrowid) if cur.lastrowid else None
