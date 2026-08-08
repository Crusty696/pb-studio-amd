"""Brain post-processor for cut lists (Plan Phase 4 + R-Brain-01..09).

R-Brain-01: spectral centroid (95th-percentile-normalized) statt 0.5-Default.
R-Brain-02: nearest-scene-distance aus video_analysis statt 0.5-Default.
R-Brain-03: real CLAP/SigLIP embedding lookup via EmbeddingCache.
R-Brain-04: optional CrossModalProjector (CLAP-512 / SigLIP-1152 -> 256).
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

from .bridge_dimensions import BridgeDimensions
from .context_resolver import ContextResolver
from .feature_adapter import CanonicalFeatureAdapter
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

    subtrack_segments = audio_analysis.get("subtrack_segments") or []
    adapter = CanonicalFeatureAdapter(
        audio_analysis=audio_analysis,
        video_analysis_by_clip=video_analysis_by_clip,
    )

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
            logger.warning("Cross-modal projector unavailable: %s", e)
            projector = None

    audio_embedding_raw = _load_audio_embedding(embedding_cache, audio_hash)
    audio_embedding = None
    if projector is not None and audio_embedding_raw is not None:
        audio_embedding = projector.project_audio_for_hash(
            audio_hash, audio_embedding_raw
        )

    video_embedding_by_clip: dict[str, np.ndarray] = {}
    if (
        projector is not None
        and embedding_cache is not None
        and video_hashes_by_clip
    ):
        for cid, vh in video_hashes_by_clip.items():
            emb = _load_video_embedding(embedding_cache, vh)
            if emb is None:
                continue
            emb = projector.project_video_for_hash(vh, emb)
            if emb is None:
                continue
            video_embedding_by_clip[cid] = emb

    out: list[dict[str, Any]] = []

    if persist_to_state_conn is not None:
        try:
            # Expliziter Transaktions-Kontext für maximale I/O-Performance (reduziert N+2 Writes auf 1 Write)
            persist_to_state_conn.execute("BEGIN IMMEDIATE")
            timeline_id = _ensure_timeline(persist_to_state_conn, audio_clip_id)
            for idx, cut in enumerate(cuts):
                new_cut = _annotate_and_maybe_persist_cut(
                    idx, cut, bridge, resolver, adapter, subtrack_segments,
                    audio_embedding, video_embedding_by_clip,
                    weight_store, min_confidence, persist_to_state_conn, timeline_id
                )
                if new_cut is not None:
                    out.append(new_cut)
            persist_to_state_conn.execute("COMMIT")
        except Exception as e:
            if persist_to_state_conn.in_transaction:
                persist_to_state_conn.execute("ROLLBACK")
            logger.error(f"Failed to persist annotated cuts to state db: {e}", exc_info=True)
            # Robustheits-Fallback: RAM-only im Fehlerfall, damit die Generierung nie fehlschlägt
            out = []
            for idx, cut in enumerate(cuts):
                new_cut = _annotate_and_maybe_persist_cut(
                    idx, cut, bridge, resolver, adapter, subtrack_segments,
                    audio_embedding, video_embedding_by_clip,
                    weight_store, min_confidence, None, None
                )
                if new_cut is not None:
                    out.append(new_cut)
    else:
        # RAM-only Modus
        for idx, cut in enumerate(cuts):
            new_cut = _annotate_and_maybe_persist_cut(
                idx, cut, bridge, resolver, adapter, subtrack_segments,
                audio_embedding, video_embedding_by_clip,
                weight_store, min_confidence, None, None
            )
            if new_cut is not None:
                out.append(new_cut)

    return out


def _annotate_and_maybe_persist_cut(
    idx: int,
    cut: dict[str, Any],
    bridge: BridgeDimensions,
    resolver: ContextResolver,
    adapter: CanonicalFeatureAdapter,
    subtrack_segments: list,
    audio_embedding: Optional[np.ndarray],
    video_embedding_by_clip: dict[str, np.ndarray],
    weight_store: WeightStore,
    min_confidence: float,
    conn: Optional[sqlite3.Connection],
    timeline_id: Optional[int],
) -> Optional[dict[str, Any]]:
    """Helper method: processes a single cut list entry and optionally persists it (R-2 / G-2)."""
    start = float(cut.get("start_time", 0.0))
    end = float(cut.get("end_time", start + 1.0))
    clip_id = str(cut.get("clip_id", ""))

    sub_start, sub_end = _enclosing_subtrack(start, subtrack_segments)
    cut_meta = dict(cut.get("metadata") or {})
    feats = adapter.candidate_features(
        clip_id=clip_id,
        trigger_type=str(cut_meta.get("trigger_type") or ""),
        trigger_strength=float(cut_meta.get("trigger_strength") or 0.0),
        cut_time_sec=start,
        cut_duration_sec=max(end - start, 0.01),
        segment_type=cut_meta.get("segment_type"),
        audio_embedding=audio_embedding,
        video_embedding=video_embedding_by_clip.get(clip_id),
    )

    ctx = resolver.resolve(
        section_type=feats.segment_type,
        cut_time_sec=start,
        subtrack_start_sec=sub_start,
        subtrack_end_sec=sub_end,
        audio_energy=feats.audio_energy,
        audio_mood_tags=feats.audio_mood_tags,
        video_motion_score=feats.motion_score,
        video_pace_class_value=feats.pace_class_score,
        energy_curve_full=adapter.energy_curve,
        motion_curve_full=adapter.normalized_motion_curve(clip_id) or None,
    )

    bridge_values = bridge.compute_all(feats)
    scores: dict[str, float] = {}
    for axis, bridge_value in bridge_values.items():
        bv = float(bridge_value)
        w = float(weight_store.get_posterior_mean(axis, ctx.context_keys))
        scores[axis] = round(bv * w, 6)

    final_score = sum(scores.values()) / len(scores) if scores else 0.0

    if feats.confidence < min_confidence:
        return None

    new_cut = dict(cut)
    meta = dict(new_cut.get("metadata") or {})
    meta["brain_scores"] = scores
    meta["context_keys"] = ctx.context_keys
    meta["brain_final_score"] = round(final_score, 6)
    meta["bridge_values"] = bridge_values
    meta["feature_confidence"] = round(feats.confidence, 6)
    meta["feature_provenance"] = feats.feature_provenance
    meta["segment_type"] = feats.segment_type
    meta["semantic_status"] = feats.semantic_status
    meta["semantic_reason"] = feats.semantic_reason
    meta["brain_axis_status"] = {
        "semantic_match_weight": {
            "status": feats.semantic_status,
            "reason": feats.semantic_reason,
        }
    }
    new_cut["metadata"] = meta

    if conn is not None and timeline_id is not None:
        cut_db_id = _persist_cut(
            conn, timeline_id, idx, new_cut, scores, ctx,
        )
        if cut_db_id is not None:
            meta["cut_id"] = cut_db_id

    return new_cut


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
            CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION, EMBED_DIM,
        )
    except Exception as exc:
        logger.warning("Audio embedding identity unavailable: %s", exc)
        return None
    return _cached_lookup(
        cache, media_hash, CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION,
        media_type="audio", expected_dim=EMBED_DIM,
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
            CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION, EMBED_DIM,
        )
    except Exception as exc:
        logger.warning("Video embedding identity unavailable: %s", exc)
        return None
    return _cached_lookup(
        cache, media_hash, CURRENT_MODEL_NAME, CURRENT_MODEL_VERSION,
        media_type="video", expected_dim=EMBED_DIM,
    )


def _cached_lookup(
    cache: Any,
    media_hash: str,
    model_name: str,
    model_version: str,
    *,
    media_type: str,
    expected_dim: int,
) -> Optional[np.ndarray]:
    """Load only the exact model/version and reject dimension drift."""
    from .loader_cache import get_default_loader_cache
    lc = get_default_loader_cache()
    cached = lc.get(media_hash, model_name, model_version)
    if cached is not None:
        return _validate_embedding_dimension(
            cached, expected_dim, media_hash=media_hash, media_type=media_type,
        )
    try:
        entry = cache.lookup(media_hash, model_name, model_version)
        if entry is None:
            logger.warning(
                "No exact %s embedding for hash %s and model %s@%s",
                media_type, media_hash, model_name, model_version,
            )
            return None
        arr = cache.load_array(entry)
        arr = _validate_embedding_dimension(
            arr, expected_dim, media_hash=media_hash, media_type=media_type,
        )
        if arr is None:
            return None
        lc.put(media_hash, model_name, model_version, arr)
        return arr
    except Exception as e:
        logger.warning("Embedding lookup failed for %s: %s", media_hash, e)
        return None


def _validate_embedding_dimension(
    embedding: Any,
    expected_dim: int,
    *,
    media_hash: str,
    media_type: str,
) -> Optional[np.ndarray]:
    if embedding is None:
        return None
    arr = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if arr.size != int(expected_dim):
        logger.warning(
            "Rejected %s embedding for hash %s: dimension %d, expected %d",
            media_type, media_hash, arr.size, expected_dim,
        )
        return None
    if not np.all(np.isfinite(arr)):
        logger.warning(
            "Rejected non-finite %s embedding for hash %s",
            media_type, media_hash,
        )
        return None
    return arr


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
