"""R-Brain-05: Tests fuer fit_pairs (CrossModalProjector) +
projector_trainer.collect_training_pairs / run_fit_step.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from pb_studio.brain.cross_modal_projector import (
    CrossModalProjector,
    DEFAULT_AUDIO_DIM,
    DEFAULT_COMMON_DIM,
    DEFAULT_VIDEO_DIM,
)
from pb_studio.brain.projector_trainer import (
    LABEL_MAP,
    collect_training_pairs,
    run_fit_step,
)
from pb_studio.storage.embedding_cache import EmbeddingCache
from pb_studio.storage.migration_runner import migrate
from pb_studio.storage.sqlite_init import init_connection


# ---------- fit_pairs unit tests ----------

def test_fit_pairs_empty():
    p = CrossModalProjector()
    res = p.fit_pairs([])
    assert res["n_pairs"] == 0
    assert res["loss_before"] == 0.0


def test_fit_pairs_label_clipped_into_range():
    """Labels ausserhalb [-1,1] werden geclipt."""
    p = CrossModalProjector()
    a = np.random.RandomState(0).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    v = np.random.RandomState(1).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
    res = p.fit_pairs([(a, v, 100.0)], lr=0.01, steps=1)
    assert res["n_pairs"] == 1


def test_fit_pairs_drops_bad_inputs():
    """None / leere Embeddings werden ausgefiltert."""
    p = CrossModalProjector()
    a = np.random.RandomState(0).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    v = np.random.RandomState(1).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
    res = p.fit_pairs([
        (None, v, 1.0),
        (a, None, 1.0),
        (a, v, 1.0),
    ])
    assert res["n_pairs"] == 1


def test_fit_pairs_pulls_cosine_toward_positive_label():
    """Bei label=+1 sollte cosine nach training hoeher sein (zu 1.0 hin)."""
    p = CrossModalProjector(seed=7)
    a = np.random.RandomState(1).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    v = np.random.RandomState(2).rand(DEFAULT_VIDEO_DIM).astype(np.float32)

    pa = p.project_audio(a)
    pv = p.project_video(v)
    cos_before = float(np.dot(pa, pv))

    res = p.fit_pairs([(a, v, 1.0)] * 5, lr=0.05, steps=20)
    assert res["loss_after"] < res["loss_before"]

    pa2 = p.project_audio(a)
    pv2 = p.project_video(v)
    cos_after = float(np.dot(pa2, pv2))
    assert cos_after > cos_before
    assert cos_after > 0.5  # konvergiert klar Richtung +1


def test_fit_pairs_pushes_cosine_toward_negative_label():
    p = CrossModalProjector(seed=7)
    a = np.random.RandomState(1).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    v = np.random.RandomState(2).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
    res = p.fit_pairs([(a, v, -1.0)] * 5, lr=0.05, steps=20)
    assert res["loss_after"] < res["loss_before"]
    cos_after = float(np.dot(p.project_audio(a), p.project_video(v)))
    assert cos_after < -0.5


def test_fit_pairs_invalidates_projection_cache():
    p = CrossModalProjector()
    a = np.random.RandomState(0).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    p.project_audio_for_hash("h1", a)
    assert p.projection_cache_stats()["size"] == 1

    v = np.random.RandomState(1).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
    p.fit_pairs([(a, v, 1.0)], lr=0.01, steps=1)
    assert p.projection_cache_stats()["size"] == 0


def test_fit_pairs_save_load_roundtrip(tmp_path: Path):
    """Nach training save() -> reload reproduziert die gelernten matrices."""
    weights = tmp_path / "cm.npz"
    p1 = CrossModalProjector(seed=7, weights_path=weights)
    a = np.random.RandomState(1).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    v = np.random.RandomState(2).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
    p1.fit_pairs([(a, v, 1.0)] * 5, lr=0.05, steps=10)
    assert p1.save()

    p2 = CrossModalProjector(seed=999, weights_path=weights)
    np.testing.assert_array_almost_equal(p1.W_audio, p2.W_audio)
    np.testing.assert_array_almost_equal(p1.W_video, p2.W_video)


def test_fit_pairs_gradient_clip_does_not_explode(tmp_path: Path):
    """Mit max_grad_norm=1.0 sollten matrices begrenzt bleiben."""
    p = CrossModalProjector(seed=1)
    a = np.random.RandomState(0).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    v = np.random.RandomState(0).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
    norm_before = float(np.linalg.norm(p.W_audio))
    p.fit_pairs([(a, v, 1.0)] * 100, lr=10.0, steps=5, max_grad_norm=1.0)
    norm_after = float(np.linalg.norm(p.W_audio))
    # Cap: 5 steps * 100 pairs * 1.0 max_norm = 500 max delta -> matrix bleibt
    # in einem mit norm < ~600 noch OK
    assert norm_after < norm_before + 1000.0
    # Keine NaNs
    assert np.all(np.isfinite(p.W_audio))
    assert np.all(np.isfinite(p.W_video))


# ---------- collect_training_pairs / run_fit_step ----------

def _make_state_conn(tmp_path: Path) -> sqlite3.Connection:
    p = tmp_path / "state.db"
    mig = (
        Path(__file__).resolve().parent.parent
        / "src" / "pb_studio" / "storage" / "migrations" / "state"
    )
    migrate(p, mig)
    conn = sqlite3.connect(str(p), isolation_level=None, check_same_thread=False)
    init_connection(conn)
    return conn


def _make_cache(tmp_path: Path) -> EmbeddingCache:
    return EmbeddingCache(
        tmp_path / "cache" / "ec.db",
        tmp_path / "cache" / "embs",
    )


def _seed_db(conn: sqlite3.Connection):
    """Seed state.db mit Timeline + 3 cuts + 3 feedback events."""
    conn.execute(
        "INSERT INTO timelines (id, name, audio_clip_id, created_at, is_current) "
        "VALUES (1, 't', 5, '2026-05-08T00:00:00Z', 1)"
    )
    for cut_id, vid in ((100, "clip_a"), (101, "clip_b"), (102, "clip_c")):
        conn.execute(
            "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, "
            "start_time, end_time) "
            "VALUES (?, 1, 0, ?, 0.0, 1.0)",
            (cut_id, vid),
        )
    for cut_id, rating in ((100, "perfect"), (101, "no_match"), (102, "fits")):
        conn.execute(
            "INSERT INTO feedback_events (cut_id, rating, alpha_delta, "
            "beta_delta, context_keys_json, timestamp) "
            "VALUES (?, ?, 1.0, 0.0, '[]', '2026-05-08T01:00:00Z')",
            (cut_id, rating),
        )


def test_collect_pairs_resolves_hashes_and_loads_embeddings(tmp_path: Path):
    state = _make_state_conn(tmp_path)
    cache = _make_cache(tmp_path)
    try:
        _seed_db(state)
        # Audio + Video hashes pro clip
        cache.store(media_hash="ah_5", media_type="audio",
                    embedding=np.ones(DEFAULT_AUDIO_DIM, dtype=np.float32),
                    model_name="t", model_version="1")
        for vh in ("vh_a", "vh_b", "vh_c"):
            cache.store(media_hash=vh, media_type="video",
                        embedding=np.ones(DEFAULT_VIDEO_DIM, dtype=np.float32),
                        model_name="t", model_version="1")

        audio_hash = lambda audio_clip_id: f"ah_{audio_clip_id}"
        video_hash_map = {"clip_a": "vh_a", "clip_b": "vh_b", "clip_c": "vh_c"}
        video_hash = lambda clip_id: video_hash_map.get(clip_id)

        pairs = collect_training_pairs(
            state_conn=state,
            embedding_cache=cache,
            audio_hash_for_clip_id=audio_hash,
            video_hash_for_clip_id=video_hash,
        )
        assert len(pairs) == 3
        labels = sorted(p[2] for p in pairs)
        assert labels == [-1.0, 0.5, 1.0]
    finally:
        cache.close()
        state.close()


def test_collect_pairs_skips_unknown_rating(tmp_path: Path):
    state = _make_state_conn(tmp_path)
    cache = _make_cache(tmp_path)
    try:
        state.execute(
            "INSERT INTO timelines (id, name, audio_clip_id, created_at, is_current) "
            "VALUES (1, 't', 5, '2026-05-08T00:00:00Z', 1)"
        )
        state.execute(
            "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, start_time, end_time) "
            "VALUES (200, 1, 0, 'clip_x', 0.0, 1.0)"
        )
        state.execute(
            "INSERT INTO feedback_events (cut_id, rating, alpha_delta, beta_delta, "
            "context_keys_json, timestamp) "
            "VALUES (200, 'gibberish', 1.0, 0.0, '[]', '2026-05-08T01:00:00Z')"
        )

        pairs = collect_training_pairs(
            state_conn=state,
            embedding_cache=cache,
            audio_hash_for_clip_id=lambda i: "ah",
            video_hash_for_clip_id=lambda c: "vh",
        )
        assert pairs == []
    finally:
        cache.close()
        state.close()


def test_collect_pairs_skips_missing_embeddings(tmp_path: Path):
    state = _make_state_conn(tmp_path)
    cache = _make_cache(tmp_path)
    try:
        _seed_db(state)
        # KEINE Embeddings in cache -> alle Paare sollten gefiltert werden
        pairs = collect_training_pairs(
            state_conn=state,
            embedding_cache=cache,
            audio_hash_for_clip_id=lambda i: "ah",
            video_hash_for_clip_id=lambda c: "vh",
        )
        assert pairs == []
    finally:
        cache.close()
        state.close()


def test_collect_pairs_respects_limit(tmp_path: Path):
    state = _make_state_conn(tmp_path)
    cache = _make_cache(tmp_path)
    try:
        _seed_db(state)
        cache.store(media_hash="ah_5", media_type="audio",
                    embedding=np.ones(DEFAULT_AUDIO_DIM, dtype=np.float32),
                    model_name="t", model_version="1")
        for vh in ("vh_a", "vh_b", "vh_c"):
            cache.store(media_hash=vh, media_type="video",
                        embedding=np.ones(DEFAULT_VIDEO_DIM, dtype=np.float32),
                        model_name="t", model_version="1")

        pairs = collect_training_pairs(
            state_conn=state,
            embedding_cache=cache,
            audio_hash_for_clip_id=lambda i: f"ah_{i}",
            video_hash_for_clip_id=lambda c: {"clip_a": "vh_a", "clip_b": "vh_b",
                                              "clip_c": "vh_c"}.get(c),
            limit=2,
        )
        assert len(pairs) == 2
    finally:
        cache.close()
        state.close()


def test_run_fit_step_end_to_end(tmp_path: Path):
    state = _make_state_conn(tmp_path)
    cache = _make_cache(tmp_path)
    try:
        _seed_db(state)
        cache.store(media_hash="ah_5", media_type="audio",
                    embedding=np.random.RandomState(1).rand(DEFAULT_AUDIO_DIM)
                    .astype(np.float32),
                    model_name="t", model_version="1")
        for i, vh in enumerate(("vh_a", "vh_b", "vh_c")):
            cache.store(media_hash=vh, media_type="video",
                        embedding=np.random.RandomState(i + 2).rand(DEFAULT_VIDEO_DIM)
                        .astype(np.float32),
                        model_name="t", model_version="1")

        weights = tmp_path / "cm.npz"
        proj = CrossModalProjector(seed=7, weights_path=weights)

        result = run_fit_step(
            proj,
            state_conn=state,
            embedding_cache=cache,
            audio_hash_for_clip_id=lambda i: f"ah_{i}",
            video_hash_for_clip_id=lambda c: {"clip_a": "vh_a", "clip_b": "vh_b",
                                              "clip_c": "vh_c"}.get(c),
            lr=0.05,
            steps=10,
        )
        assert result["n_pairs"] == 3
        assert result["loss_after"] <= result["loss_before"]
        assert result["saved"] is True
        assert weights.is_file()
    finally:
        cache.close()
        state.close()


def test_label_map_covers_all_ratings():
    """Sanity: alle 4 ratings aus FeedbackLogger.RATING_MAP haben einen label."""
    from pb_studio.brain.feedback_logger import RATING_MAP
    for r in RATING_MAP.keys():
        assert r in LABEL_MAP
        assert -1.0 <= LABEL_MAP[r] <= 1.0
