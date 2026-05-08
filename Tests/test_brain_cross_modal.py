"""R-Brain-04: Tests fuer CrossModalProjector.

Verifiziert:
- Output-Dimension korrekt (common_dim)
- Determinismus bei gleichem seed
- Save/Load-Roundtrip ueber pathlib
- Wrong-size + NaN/Inf Inputs werden gracefully behandelt
- L2-normalized Output (cosine == dot product)
- Integration in post_processor: projizierte Embeddings landen
  in semantic_match_weight bridge
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from pb_studio.brain import (
    BRIDGE_AXES,
    CrossModalProjector,
    get_default_projector,
    reset_default_projector,
)
from pb_studio.brain.brain_service import BrainService
from pb_studio.brain.cross_modal_projector import (
    DEFAULT_AUDIO_DIM,
    DEFAULT_COMMON_DIM,
    DEFAULT_VIDEO_DIM,
)
from pb_studio.brain.post_processor import annotate_cuts_with_brain
from pb_studio.storage.embedding_cache import EmbeddingCache
from pb_studio.storage.migration_runner import migrate
from pb_studio.storage.sqlite_init import init_connection


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_default_projector()
    yield
    reset_default_projector()


def test_projector_output_dim():
    p = CrossModalProjector()
    a = p.project_audio(np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32))
    v = p.project_video(np.random.rand(DEFAULT_VIDEO_DIM).astype(np.float32))
    assert a is not None and a.shape == (DEFAULT_COMMON_DIM,)
    assert v is not None and v.shape == (DEFAULT_COMMON_DIM,)


def test_projector_l2_normalized_output():
    p = CrossModalProjector()
    a = p.project_audio(np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32))
    v = p.project_video(np.random.rand(DEFAULT_VIDEO_DIM).astype(np.float32))
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-5
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-5


def test_projector_deterministic_same_seed():
    p1 = CrossModalProjector(seed=123)
    p2 = CrossModalProjector(seed=123)
    np.testing.assert_array_equal(p1.W_audio, p2.W_audio)
    np.testing.assert_array_equal(p1.W_video, p2.W_video)


def test_projector_different_seeds_differ():
    p1 = CrossModalProjector(seed=1)
    p2 = CrossModalProjector(seed=2)
    assert not np.array_equal(p1.W_audio, p2.W_audio)
    assert not np.array_equal(p1.W_video, p2.W_video)


def test_projector_handles_wrong_size_inputs():
    p = CrossModalProjector()
    # Too short -> zero-padded
    short = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    out = p.project_audio(short)
    assert out is not None and out.shape == (DEFAULT_COMMON_DIM,)
    # Too long -> truncated
    long = np.random.rand(DEFAULT_AUDIO_DIM + 100).astype(np.float32)
    out = p.project_audio(long)
    assert out is not None and out.shape == (DEFAULT_COMMON_DIM,)


def test_projector_handles_nan_inf():
    p = CrossModalProjector()
    bad = np.array([float("nan"), float("inf")] + [1.0] * (DEFAULT_AUDIO_DIM - 2),
                   dtype=np.float32)
    out = p.project_audio(bad)
    assert out is not None
    # No NaN in output
    assert np.all(np.isfinite(out))


def test_projector_returns_none_on_empty_or_zero():
    p = CrossModalProjector()
    assert p.project_audio(None) is None
    assert p.project_audio(np.array([], dtype=np.float32)) is None
    # All-zero input -> norm < eps -> None (cannot normalize)
    assert p.project_audio(np.zeros(DEFAULT_AUDIO_DIM, dtype=np.float32)) is None


def test_save_load_roundtrip(tmp_path: Path):
    weights = tmp_path / "cm.npz"
    p1 = CrossModalProjector(seed=7, weights_path=weights)
    saved = p1.save()
    assert saved is True
    assert weights.is_file()

    # Re-load with different seed -> file overrides random init
    p2 = CrossModalProjector(seed=999, weights_path=weights)
    np.testing.assert_array_equal(p1.W_audio, p2.W_audio)
    np.testing.assert_array_equal(p1.W_video, p2.W_video)


def test_load_dim_mismatch_keeps_random(tmp_path: Path):
    weights = tmp_path / "cm.npz"
    p1 = CrossModalProjector(common_dim=128, weights_path=weights)
    p1.save()

    # Try loading with different common_dim -> should NOT load, keeps fresh init
    p2 = CrossModalProjector(common_dim=256, weights_path=weights)
    assert p2.W_audio.shape == (DEFAULT_AUDIO_DIM, 256)
    assert p2.W_video.shape == (DEFAULT_VIDEO_DIM, 256)


def test_get_default_projector_singleton(tmp_path: Path):
    p1 = get_default_projector()
    p2 = get_default_projector()
    assert p1 is p2


def test_cosine_helper_bounds():
    p = CrossModalProjector()
    a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    c = p.cosine(a, b)
    assert 0.99 <= c <= 1.01  # identical -> ~1.0

    b2 = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
    c2 = p.cosine(a, b2)
    assert -0.01 <= c2 <= 0.01  # opposite -> 0.0


def test_random_projection_preserves_relative_distances():
    """Johnson-Lindenstrauss Eigenschaft: zwei aehnliche embeddings sollten
    nach projektion immernoch aehnlicher sein als zwei unaehnliche."""
    p = CrossModalProjector(seed=42)

    base = np.random.RandomState(0).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    similar = base + 0.01 * np.random.RandomState(1).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    different = np.random.RandomState(99).rand(DEFAULT_AUDIO_DIM).astype(np.float32)

    pb = p.project_audio(base)
    ps = p.project_audio(similar)
    pd = p.project_audio(different)

    cos_similar = float(np.dot(pb, ps))
    cos_different = float(np.dot(pb, pd))
    assert cos_similar > cos_different


# ---------- Integration with annotate_cuts_with_brain ----------

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
    db = tmp_path / "cache" / "embedding_cache.db"
    emb_dir = tmp_path / "cache" / "embeddings"
    return EmbeddingCache(db, emb_dir)


@pytest.fixture
def brain_svc(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    BrainService.reset_singleton()
    yield BrainService.get()
    BrainService.reset_singleton()


def test_post_processor_uses_projector_for_clap_siglip_dim_mismatch(
    brain_svc, tmp_path: Path,
):
    """Realistischer Fall: 512-dim audio + 768-dim video. Ohne projector
    truncated cosine auf 512. MIT projector werden beide auf 256 projiziert."""
    cache = _make_cache(tmp_path)
    state = _make_state_conn(tmp_path)
    try:
        # Realistische dimensionen
        a_emb = np.random.RandomState(1).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
        v_emb = np.random.RandomState(2).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
        cache.store(media_hash="ah", media_type="audio", embedding=a_emb,
                    model_name="clap-fake", model_version="1.0")
        cache.store(media_hash="vh", media_type="video", embedding=v_emb,
                    model_name="siglip-fake", model_version="1.0")

        projector = CrossModalProjector(seed=42)
        cuts = [{"clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0,
                 "metadata": {"trigger_type": "kick", "trigger_strength": 1.0}}]
        out = annotate_cuts_with_brain(
            cuts,
            weight_store=brain_svc.weights,
            audio_analysis={"duration_seconds": 1.0},
            video_analysis_by_clip={"clip_1": {}},
            audio_clip_id=1,
            persist_to_state_conn=state,
            embedding_cache=cache,
            audio_hash="ah",
            video_hashes_by_clip={"clip_1": "vh"},
            cross_modal_projector=projector,
        )
        assert len(out) == 1
        scores = out[0]["metadata"]["brain_scores"]
        assert set(scores.keys()) == set(BRIDGE_AXES)
        sm = scores["semantic_match_weight"]
        assert 0.0 < sm <= 1.0
    finally:
        cache.close()
        state.close()


def test_auto_projector_resolved_when_cache_provided(
    brain_svc, tmp_path: Path,
):
    """Wenn cross_modal_projector=None und cache gegeben, soll der
    post_processor get_default_projector(weights_path=cache.parent/...) nutzen."""
    cache = _make_cache(tmp_path)
    state = _make_state_conn(tmp_path)
    try:
        a_emb = np.random.RandomState(1).rand(DEFAULT_AUDIO_DIM).astype(np.float32)
        v_emb = np.random.RandomState(2).rand(DEFAULT_VIDEO_DIM).astype(np.float32)
        cache.store(media_hash="ah", media_type="audio", embedding=a_emb,
                    model_name="t", model_version="1")
        cache.store(media_hash="vh", media_type="video", embedding=v_emb,
                    model_name="t", model_version="1")

        cuts = [{"clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0,
                 "metadata": {"trigger_type": "beat", "trigger_strength": 1.0}}]
        out = annotate_cuts_with_brain(
            cuts,
            weight_store=brain_svc.weights,
            audio_analysis={"duration_seconds": 1.0},
            video_analysis_by_clip={"clip_1": {}},
            audio_clip_id=1,
            persist_to_state_conn=state,
            embedding_cache=cache,
            audio_hash="ah",
            video_hashes_by_clip={"clip_1": "vh"},
            # cross_modal_projector NICHT gesetzt -> auto-resolve
        )
        assert len(out) == 1
        sm = out[0]["metadata"]["brain_scores"]["semantic_match_weight"]
        assert 0.0 < sm <= 1.0
    finally:
        cache.close()
        state.close()
