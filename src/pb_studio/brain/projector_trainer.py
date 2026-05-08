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
import logging
import sqlite3
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

LABEL_MAP: dict[str, float] = {
    "perfect":   +1.0,
    "fits":      +0.5,
    "not_quite": -0.5,
    "no_match":  -1.0,
}


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
        "ORDER BY fe.timestamp DESC"
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
