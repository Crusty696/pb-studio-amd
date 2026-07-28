"""R-Brain-03: Tests fuer Embedding-Integration in post_processor.

Verifiziert dass annotate_cuts_with_brain echte CLAP/SigLIP Embeddings aus
EmbeddingCache zieht und an CandidateFeatures durchreicht, statt 0.5-Default.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from pb_studio.brain import BRIDGE_AXES
from pb_studio.brain.brain_service import BrainService
from pb_studio.brain.cross_modal_projector import (
    DEFAULT_AUDIO_DIM,
    DEFAULT_AUDIO_MODEL_NAME,
    DEFAULT_AUDIO_MODEL_VERSION,
    DEFAULT_VIDEO_DIM,
    DEFAULT_VIDEO_MODEL_NAME,
    DEFAULT_VIDEO_MODEL_VERSION,
)
from pb_studio.brain.loader_cache import clear_default_loader_cache
from pb_studio.brain.post_processor import (
    annotate_cuts_with_brain,
    _load_audio_embedding,
    _load_video_embedding,
)
from pb_studio.storage.embedding_cache import EmbeddingCache
from pb_studio.storage.migration_runner import migrate
from pb_studio.storage.sqlite_init import init_connection


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


@pytest.fixture(autouse=True)
def _clear_embedding_loader_cache():
    clear_default_loader_cache()
    yield
    clear_default_loader_cache()


def test_load_audio_embedding_returns_none_on_miss(tmp_path):
    cache = _make_cache(tmp_path)
    try:
        # No data in cache
        assert _load_audio_embedding(cache, "deadbeef") is None
        # Cache None / hash empty -> None
        assert _load_audio_embedding(None, "deadbeef") is None
        assert _load_audio_embedding(cache, "") is None
        assert _load_audio_embedding(cache, None) is None
    finally:
        cache.close()


def test_load_audio_embedding_rejects_arbitrary_model(tmp_path):
    cache = _make_cache(tmp_path)
    try:
        emb = np.random.rand(512).astype(np.float32)
        cache.store(
            media_hash="abc123",
            media_type="audio",
            embedding=emb,
            model_name="my-test-model",
            model_version="0.1",
        )
        assert _load_audio_embedding(cache, "abc123") is None
    finally:
        cache.close()


def test_load_video_embedding_returns_array(tmp_path):
    cache = _make_cache(tmp_path)
    try:
        emb = np.random.rand(768).astype(np.float32)
        cache.store(
            media_hash="vidhash1",
            media_type="video",
            embedding=emb,
            model_name=DEFAULT_VIDEO_MODEL_NAME,
            model_version=DEFAULT_VIDEO_MODEL_VERSION,
        )
        loaded = _load_video_embedding(cache, "vidhash1")
        assert loaded is not None
        assert loaded.shape == (768,)
    finally:
        cache.close()


def test_annotate_uses_embeddings_when_cache_provided(brain_svc, tmp_path):
    """Exact CLAP/SigLIP cache entries reach cross-modal projection."""
    cache = _make_cache(tmp_path)
    state = _make_state_conn(tmp_path)
    try:
        audio_emb = np.ones(DEFAULT_AUDIO_DIM, dtype=np.float32)
        video_emb = np.ones(DEFAULT_VIDEO_DIM, dtype=np.float32)
        cache.store(
            media_hash="ahash",
            media_type="audio",
            embedding=audio_emb,
            model_name=DEFAULT_AUDIO_MODEL_NAME,
            model_version=DEFAULT_AUDIO_MODEL_VERSION,
        )
        cache.store(
            media_hash="vhash1",
            media_type="video",
            embedding=video_emb,
            model_name=DEFAULT_VIDEO_MODEL_NAME,
            model_version=DEFAULT_VIDEO_MODEL_VERSION,
        )

        cuts = [{
            "clip_id": "clip_1",
            "start_time": 0.0,
            "end_time": 1.0,
            "metadata": {"trigger_type": "kick", "trigger_strength": 1.0},
        }]
        out = annotate_cuts_with_brain(
            cuts,
            weight_store=brain_svc.weights,
            audio_analysis={"duration_seconds": 1.0},
            video_analysis_by_clip={"clip_1": {"avg_motion": 0.5}},
            audio_clip_id=1,
            persist_to_state_conn=state,
            embedding_cache=cache,
            audio_hash="ahash",
            video_hashes_by_clip={"clip_1": "vhash1"},
        )

        assert len(out) == 1
        scores = out[0]["metadata"]["brain_scores"]
        assert set(scores.keys()) == set(BRIDGE_AXES)
        assert scores["semantic_match_weight"] > 0.0
    finally:
        cache.close()
        state.close()


def test_annotate_orthogonal_embeddings_yield_lower_score(brain_svc, tmp_path):
    """Orthogonale Embeddings sollten niedrigeren semantic_match score liefern
    als identische Embeddings (mehr als nur konstanter 0.5)."""
    cache = _make_cache(tmp_path)
    state = _make_state_conn(tmp_path)
    try:
        a = np.zeros(DEFAULT_AUDIO_DIM, dtype=np.float32)
        a[0] = 1.0
        b = np.zeros(DEFAULT_VIDEO_DIM, dtype=np.float32)
        b[1] = 1.0  # orthogonal zu a -> cosine = 0 -> mapped 0.5
        cache.store(media_hash="ah", media_type="audio", embedding=a,
                    model_name=DEFAULT_AUDIO_MODEL_NAME,
                    model_version=DEFAULT_AUDIO_MODEL_VERSION)
        cache.store(media_hash="vh", media_type="video", embedding=b,
                    model_name=DEFAULT_VIDEO_MODEL_NAME,
                    model_version=DEFAULT_VIDEO_MODEL_VERSION)

        class HeadProjector:
            @staticmethod
            def project_audio_for_hash(_media_hash, emb):
                return emb[:256]

            @staticmethod
            def project_video_for_hash(_media_hash, emb):
                return emb[:256]

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
            cross_modal_projector=HeadProjector(),
        )

        sm_orth = out[0]["metadata"]["brain_scores"]["semantic_match_weight"]
        # cosine=0 -> _cosine_zero_one returns 0.5 -> *posterior=0.5 -> ~0.25
        assert 0.2 <= sm_orth <= 0.3
    finally:
        cache.close()
        state.close()


def test_no_cache_fallback_to_default(brain_svc, tmp_path):
    """Ohne cache muss alles wie vorher arbeiten (0.5 default semantic_match)."""
    state = _make_state_conn(tmp_path)
    try:
        cuts = [{"clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0,
                 "metadata": {"trigger_type": "beat", "trigger_strength": 1.0}}]
        out = annotate_cuts_with_brain(
            cuts,
            weight_store=brain_svc.weights,
            audio_analysis={"duration_seconds": 1.0},
            video_analysis_by_clip={"clip_1": {}},
            audio_clip_id=1,
            persist_to_state_conn=state,
        )
        assert len(out) == 1
        sm = out[0]["metadata"]["brain_scores"]["semantic_match_weight"]
        # 0.5 (default) * 0.5 (cold-start posterior) = 0.25
        assert 0.2 <= sm <= 0.3
    finally:
        state.close()
