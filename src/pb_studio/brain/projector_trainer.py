"""R-Brain-05: Sammelt Audio-Video-Embedding-Paare aus Brain-Feedback und
trainiert die CrossModalProjector-Matrizen via fit_pairs().

Datenfluss:
1. state.db.feedback_events     -> rating (perfect/fits/not_quite/no_match)
2. state.db.timeline_cuts        -> clip_id (e.g. "clip_5") fuer den bewerteten Cut
3. brain_store.cache (EmbeddingCache) -> die zugehoerigen rohen Embeddings

Mapping Rating -> Label:
    perfect    = +1.0
    fits       = +0.5
    not_quite  = -0.5
    no_match   = -1.0

Pairs werden ueber media_hash aufgeloest:
- audio_hash kommt aus dem Projekt (siehe `audio_clip_id` und entsprechender
  hash in der app_state oder durch ergaenzendes lookup-arg).
- video_hash kommt aus state.db.video_metadata.video_hash (oder analog).

Da wir hier moeglichst entkoppelt vom Backend bleiben wollen, nimmt
`collect_training_pairs` Hash-Auflöser-Callbacks (audio_hash_for_clip_id,
video_hash_for_clip_id), damit Tests einfach mockbar sind.

IRON RULES: NumPy-only, keine Torch/CUDA-Imports, pathlib.
"""

from __future__ import annotations

import json
import hashlib
import logging
import sqlite3
import threading
import uuid
from pb_studio.storage.recovery_barrier import recovery_write_operation
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

LABEL_MAP: dict[str, float] = {
    "perfect":   +1.0,
    "fits":      +0.5,
    "not_quite": -0.5,
    "no_match":  -1.0,
}

_V2_TRAIN_LOCK = threading.Lock()


@dataclass(frozen=True)
class ProjectTrainingSource:
    project_uuid: str
    state_conn: Optional[sqlite3.Connection]
    audio_hash_for_clip_id: Callable[[int], Optional[str]]
    video_hash_for_clip_id: Callable[[str], Optional[str]]
    status: str = "ready"


def collect_training_pairs(
    *,
    state_conn: sqlite3.Connection,
    embedding_cache,
    audio_hash_for_clip_id: Callable[[int], Optional[str]],
    video_hash_for_clip_id: Callable[[str], Optional[str]],
    audio_load_fn: Optional[Callable[[str], Optional[np.ndarray]]] = None,
    video_load_fn: Optional[Callable[[str], Optional[np.ndarray]]] = None,
    limit: Optional[int] = None,
) -> list[tuple[np.ndarray, np.ndarray, float]]:
    """Joins feedback_events + timeline_cuts + timelines and resolves embeddings.

    Args:
        state_conn: project state.db connection.
        embedding_cache: BrainStore.cache (EmbeddingCache).
        audio_hash_for_clip_id: callable int audio_clip_id -> hash str (or None).
            Audio-clip-id steckt in `timelines.audio_clip_id`.
        video_hash_for_clip_id: callable clip_id-string ("clip_5") -> hash str.
            Video clip_id steckt direkt in timeline_cuts.clip_id (incl. "clip_" prefix).
        audio_load_fn / video_load_fn: optional lookups (default: post_processor's
            _load_audio_embedding / _load_video_embedding). Inject for tests.
        limit: max number of pairs (most-recent feedback first).

    Returns:
        list of (audio_emb_raw, video_emb_raw, label) ready for fit_pairs().
    """
    if audio_load_fn is None or video_load_fn is None:
        from .post_processor import _load_audio_embedding, _load_video_embedding
        if audio_load_fn is None:
            audio_load_fn = lambda h: _load_audio_embedding(embedding_cache, h)
        if video_load_fn is None:
            video_load_fn = lambda h: _load_video_embedding(embedding_cache, h)

    sql = (
        "SELECT fe.rating, tc.clip_id, t.audio_clip_id, fe.timestamp "
        "FROM feedback_events fe "
        "JOIN timeline_cuts tc ON tc.id = fe.cut_id "
        "JOIN timelines t ON t.id = tc.timeline_id "
        "ORDER BY fe.timestamp DESC, fe.id DESC"
    )
    if limit is not None and int(limit) > 0:
        sql += f" LIMIT {int(limit)}"

    rows = state_conn.execute(sql).fetchall()

    pairs: list[tuple[np.ndarray, np.ndarray, float]] = []
    for rating, video_clip_id, audio_clip_id, _ts in rows:
        label = LABEL_MAP.get(str(rating))
        if label is None:
            continue
        try:
            ah = audio_hash_for_clip_id(int(audio_clip_id))
            vh = video_hash_for_clip_id(str(video_clip_id))
        except Exception as e:
            logger.debug("hash resolver failed: %s", e)
            continue
        if not ah or not vh:
            continue
        a_emb = audio_load_fn(ah)
        v_emb = video_load_fn(vh)
        if a_emb is None or v_emb is None:
            continue
        pairs.append((a_emb, v_emb, label))

    return pairs


@recovery_write_operation("brain-projector")
def run_fit_step(
    projector,
    *,
    state_conn: sqlite3.Connection,
    embedding_cache,
    audio_hash_for_clip_id: Callable[[int], Optional[str]],
    video_hash_for_clip_id: Callable[[str], Optional[str]],
    lr: float = 0.01,
    steps: int = 1,
    limit: Optional[int] = None,
    save: bool = True,
) -> dict:
    """End-to-end: collect pairs from DB and fit the projector.

    Returns the dict from fit_pairs() augmented with `saved: bool`.
    """
    pairs = collect_training_pairs(
        state_conn=state_conn,
        embedding_cache=embedding_cache,
        audio_hash_for_clip_id=audio_hash_for_clip_id,
        video_hash_for_clip_id=video_hash_for_clip_id,
        limit=limit,
    )
    result = projector.fit_pairs(pairs, lr=lr, steps=steps)
    saved = False
    if save and result.get("n_pairs", 0) > 0:
        saved = bool(projector.save())
    result["saved"] = saved
    return result


def run_v2_fit_step(
    projector,
    *,
    sources: list[ProjectTrainingSource],
    embedding_cache,
    lr: float = 0.01,
    steps: int = 1,
    publish_fn=None,
) -> dict:
    """Train unseen event UUIDs on a private snapshot and atomically publish."""
    from .cross_modal_projector import publish_default_projector
    from .post_processor import _load_audio_embedding, _load_video_embedding

    publish = publish_fn or publish_default_projector
    with _V2_TRAIN_LOCK:
        active_applied = set(projector.applied_event_uuids)
        seen_event_uuids: set[str] = set()
        ready: list[tuple[str, str, np.ndarray, np.ndarray, float]] = []
        pending: dict[str, dict] = {}
        checkpoints: dict[str, dict] = {}

        for source in sorted(sources, key=lambda item: item.project_uuid):
            project_uuid = str(uuid.UUID(str(source.project_uuid)))
            if source.state_conn is None:
                checkpoints[project_uuid] = {
                    "events": 0,
                    "status": source.status,
                }
                continue
            rows = source.state_conn.execute(
                "SELECT fe.event_uuid, fe.project_uuid, fe.rating, tc.clip_id, "
                "t.audio_clip_id FROM feedback_events fe "
                "JOIN timeline_cuts tc ON tc.id=fe.cut_id "
                "JOIN timelines t ON t.id=tc.timeline_id "
                "ORDER BY fe.event_uuid"
            ).fetchall()
            checkpoints[project_uuid] = {
                "events": len(rows),
                "status": source.status,
            }
            for event_uuid_raw, row_project_uuid, rating, video_id, audio_id in rows:
                if not event_uuid_raw or not row_project_uuid:
                    raise RuntimeError("Projector V2 encountered unmigrated feedback")
                event_uuid = str(uuid.UUID(str(event_uuid_raw)))
                if str(uuid.UUID(str(row_project_uuid))) != project_uuid:
                    raise RuntimeError("Feedback project_uuid conflicts with inventory")
                if event_uuid in seen_event_uuids:
                    raise RuntimeError(f"Duplicate feedback event_uuid: {event_uuid}")
                seen_event_uuids.add(event_uuid)
                if event_uuid in active_applied:
                    continue
                label = LABEL_MAP.get(str(rating))
                if label is None:
                    pending[event_uuid] = {
                        "project_uuid": project_uuid,
                        "reason": "unknown_rating",
                    }
                    continue
                audio_hash = source.audio_hash_for_clip_id(int(audio_id))
                video_hash = source.video_hash_for_clip_id(str(video_id))
                reason = None
                if not audio_hash:
                    reason = "missing_audio_hash"
                elif not video_hash:
                    reason = "missing_video_hash"
                audio_embedding = (
                    _load_audio_embedding(embedding_cache, audio_hash)
                    if audio_hash else None
                )
                video_embedding = (
                    _load_video_embedding(embedding_cache, video_hash)
                    if video_hash else None
                )
                if reason is None and audio_embedding is None:
                    reason = "missing_audio_embedding"
                if reason is None and video_embedding is None:
                    reason = "missing_video_embedding"
                if reason is not None:
                    pending[event_uuid] = {
                        "project_uuid": project_uuid,
                        "reason": reason,
                    }
                    continue
                ready.append((
                    project_uuid,
                    event_uuid,
                    audio_embedding,
                    video_embedding,
                    float(label),
                ))

        ready.sort(key=lambda item: (item[0], item[1]))
        candidate = projector.clone()
        fit_result = candidate.fit_pairs(
            [(item[2], item[3], item[4]) for item in ready],
            lr=lr,
            steps=steps,
        )
        candidate.parent_generation_uuid = projector.generation_uuid
        candidate.generation_uuid = str(uuid.uuid4())
        candidate.applied_event_uuids = tuple(sorted(
            active_applied | {item[1] for item in ready}
        ))
        candidate.pending_events = pending
        candidate.project_checkpoints = checkpoints
        digest_payload = json.dumps(
            {
                "applied": list(candidate.applied_event_uuids),
                "checkpoints": checkpoints,
                "pending": pending,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        candidate.inventory_digest = hashlib.sha256(digest_payload).hexdigest()
        publish(candidate)
        return {
            **fit_result,
            "applied_events": len(candidate.applied_event_uuids),
            "new_events": len(ready),
            "pending_events": len(pending),
            "generation_uuid": candidate.generation_uuid,
            "saved": True,
        }
