"""Brain post-processor for cut lists (Plan Phase 4 + R-Brain-01..09).

R-Brain-01: spectral centroid (95th-percentile-normalized) statt 0.5-Default.
R-Brain-02: nearest-scene-distance aus video_analysis statt 0.5-Default.
R-Brain-03: real CLAP/SigLIP embedding lookup via EmbeddingCache.
R-Brain-04: optional CrossModalProjector (CLAP-512 / SigLIP-768 -> 256).
R-Brain-08: process-level loader cache (LoaderCache singleton) +
            CrossModalProjector hash-keyed projection cache.
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
    embedding_cache: Any = None,
    audio_hash: Optional[str] = None,
    video_hashes_by_clip: Optional[dict[str, str]] = None,
    cross_modal_projector: Any = None,
) -> list[dict[str, Any]]:
    """Annotate cuts with brain_scores + context_keys.

    Cuts unter `min_confidence` werden gefiltert.

    Args:
        embedding_cache: optional EmbeddingCache (BrainStore.cache).
        audio_hash: sha256 des Audio-Files fuer cache.lookup.
        video_hashes_by_clip: dict clip_id ("clip_5") -> sha256.
        cross_modal_projector: optional CrossModalProjector. Bei None und
            embedding_cache gegeben -> get_default_projector() lazy.
    """
    if not cuts:
        return cuts

    bridge = BridgeDimensions()
    resolver = ContextResolver()
    audio_analysis = audio_analysis or {}
    video_analysis_by_clip = video_analysis_by_clip or {}
    video_hashes_by_clip = video_hashes_by_clip or {}

    audio_mood_tags: list[str] = list(audio_analysis.get("mood_tags") or [])
    energy_curve = audio_analysis.get("energy_curve") or []
    subtrack_segments = audio_analysis.get("subtrack_segments") or []
    spectral_data = audio_analysis.get("spectral_data") or {}
    centroid_curve = spectral_data.get("centroids") or []
    centroid_curve_norm = _normalize_centroid_curve(centroid_curve)
    audio_duration = float(audio_analysis.get("duration_seconds", 0.0) or 0.0)

    # R-Brain-04: resolve cross-modal projector
    projector = cross_modal_projector
    if projector is None and embedding_cache is not None:
        try:
            from .cross_modal_projector import get_default_projector
            from pathlib import Path as _Path
            wp = None
            cache_dir = getattr(embedding_cache, "embeddings_dir", None)
            if cache_dir is not None:
                wp = _Path(cache_dir).parent / "cross_modal_projector.npz"
            projector = get_default_projector(weights_path=wp)
        except Exception as e:
            logger.debug("auto-resolve cross_modal_projector failed: %s", e)
            projector = None

    audio_embedding_raw = _load_audio_embedding(embedding_cache, audio_hash)
    if projector is not None and audio_embedding_raw is not None:
        audio_embedding = projector.project_audio_for_hash(
            audio_hash, audio_embedding_raw
        )
    else:
        audio_embedding = audio_embedding_raw

    video_embedding_by_clip: dict[str, np.ndarray] = {}
    if embedding_cache is not None and video_hashes_by_clip:
        for cid, vh in video_hashes_by_clip.items():
            emb = _load_video_embedding(embedding_cache, vh)
            if emb is None:
                continue
            if projector is not None:
                emb = projector.project_video_for_hash(vh, emb)
                if emb is None:
                    continue
            video_embedding_by_clip[cid] = emb

    out: list[dict[str, Any]] = []
    timeline_id = _ensure_timeline(persist_to_state_conn, audio_clip_id)

    for idx, cut in enumerate(cuts):
        start = float(cut.get("start_time", 0.0))
        end = float(cut.get("end_time", start + 1.0))
        clip_id = str(cut.get("clip_id", ""))

        sub_start, sub_end = _enclosing_subtrack(start, subtrack_segments)
        a_energy = _value_at_time(energy_curve, start, audio_duration)

        v = video_analysis_by_clip.get(clip_id, {})
        motion = float(v.get("avg_motion") or 0.0)
        v_pace = _video_pace_score(v)
        scene_dist = _nearest_scene_distance(start, v.get("scenes") or [])
        a_centroid = _value_at_time(centroid_curve_norm, start, audio_duration)

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
            audio_centroid=a_centroid,
            audio_embedding=audio_embedding,
            motion_score=motion,
            scene_distance_sec=scene_dist,
            brightness=float(v.get("avg_brightness") or 0.5),
            saturation=float(v.get("avg_saturation") or 0.5),
            color_temp=float(v.get("avg_color_temp") or 0.0),
            pace_class_score=v_pace,
            video_embedding=video_embedding_by_clip.get(clip_id),
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


def _normalize_centroid_curve(curve) -> list[float]:
    """R-Brain-01: normalize spectral centroid curve to 0..1 (95th-percentile)."""
    if curve is None or len(curve) == 0:
        return []
    arr = np.asarray(list(curve), dtype=np.float32)
    if arr.size == 0:
        return []
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    max_val = float(np.percentile(arr, 95)) if arr.size > 1 else float(arr[0])
    if max_val < 1e-6:
        return []
    arr = arr / max_val
    return [float(max(0.0, min(1.0, x))) for x in arr]


def _nearest_scene_distance(t: float, scenes: list) -> float:
    """R-Brain-02: Min |t - scene_boundary| in seconds. Empty list -> 1.0."""
    if not scenes:
        return 1.0
    min_dist = float("inf")
    for s in scenes:
        if isinstance(s, dict):
            for key in ("start_time", "end_time", "time"):
                if key in s:
                    try:
                        d = abs(float(s[key]) - float(t))
                        if d < min_dist:
                            min_dist = d
                    except (TypeError, ValueError):
                        continue
        elif isinstance(s, (list, tuple)) and len(s) >= 1:
            try:
                d = abs(float(s[0]) - float(t))
                if d < min_dist:
                    min_dist = d
            except (TypeError, ValueError):
                continue
    if min_dist == float("inf"):
        return 1.0
    return min(min_dist, 10.0)


# ---------- embedding lookup with R-Brain-08 LRU ----------

def _load_audio_embedding(
    cache: Any, media_hash: Optional[str]
) -> Optional[np.ndarray]:
    """R-Brain-03: load CLAP audio embedding from cache by sha256 hash.
    R-Brain-08: process-level LRU before SQLite + np.load.
    """
    if cache is None or not media_hash:
        return None
    try:
        from pb_studio.audio.audio_embedder import (
            CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION,
        )
    except Exception:
        return _load_first_match(cache, media_hash, media_type="audio")
    return _cached_lookup(
        cache, media_hash, CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION,
        media_type="audio",
    )


def _load_video_embedding(
    cache: Any, media_hash: Optional[str]
) -> Optional[np.ndarray]:
    """R-Brain-03: load SigLIP video embedding from cache by sha256 hash.
    R-Brain-08: process-level LRU before SQLite + np.load.
    """
    if cache is None or not media_hash:
        return None
    try:
        from pb_studio.video.video_embedder import (
            CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION,
        )
    except Exception:
        return _load_first_match(cache, media_hash, media_type="video")
    return _cached_lookup(
        cache, media_hash, CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION,
        media_type="video",
    )


def _cached_lookup(
    cache: Any,
    media_hash: str,
    model_name: str,
    model_version: str,
    *,
    media_type: str,
) -> Optional[np.ndarray]:
    """R-Brain-08: LRU-checked + DB-fallback lookup."""
    from .loader_cache import get_default_loader_cache
    lc = get_default_loader_cache()
    cached = lc.get(media_hash, model_name, model_version)
    if cached is not None:
        return cached
    try:
        entry = cache.lookup(media_hash, model_name, model_version)
        if entry is None:
            return _load_first_match(cache, media_hash, media_type=media_type)
        arr = cache.load_array(entry)
        if arr is not None:
            lc.put(media_hash, model_name, model_version, arr)
        return arr
    except Exception as e:
        logger.debug("embedding lookup failed for %s: %s", media_hash, e)
        return None


def _load_first_match(
    cache: Any, media_hash: str, *, media_type: str
) -> Optional[np.ndarray]:
    """Probe cache for any model_name/version with the given hash + type.
    R-Brain-08: process-level LRU on the resolved (model_name, model_version).
    """
    try:
        row = cache.conn.execute(
            "SELECT model_name, model_version FROM media_embedding_index "
            "WHERE media_hash = ? AND media_type = ? LIMIT 1",
            (media_hash, media_type),
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    model_name, model_version = str(row[0]), str(row[1])
    from .loader_cache import get_default_loader_cache
    lc = get_default_loader_cache()
    cached = lc.get(media_hash, model_name, model_version)
    if cached is not None:
        return cached
    try:
        entry = cache.lookup(media_hash, model_name, model_version)
        if entry is None:
            return None
        arr = cache.load_array(entry)
        if arr is not None:
            lc.put(media_hash, model_name, model_version, arr)
        return arr
    except Exception:
        return None


# ---------- DB persistence ----------

def _ensure_timeline(
    conn: Optional[sqlite3.Connection], audio_clip_id: Optional[int]
) -> Optional[int]:
    if conn is None:
        return None
    now = datetime.now(timezone.utc).isoformat()
    aud = int(audio_clip_id) if audio_clip_id is not None else 0
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
