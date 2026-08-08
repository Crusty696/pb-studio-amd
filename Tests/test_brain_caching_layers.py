"""R-Brain-08 erweitert: Tests fuer loader_cache (process-LRU fuer raw embeddings)
und CrossModalProjector hash-keyed projection cache.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pb_studio.brain.loader_cache import (
    LoaderCache,
    clear_default_loader_cache,
    get_default_loader_cache,
)
from pb_studio.brain.cross_modal_projector import (
    CrossModalProjector,
    DEFAULT_AUDIO_DIM,
    DEFAULT_AUDIO_MODEL_NAME,
    DEFAULT_AUDIO_MODEL_VERSION,
    DEFAULT_VIDEO_DIM,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    clear_default_loader_cache()
    yield
    clear_default_loader_cache()


# ---------- LoaderCache ----------

def test_loader_cache_miss_then_hit():
    lc = LoaderCache()
    assert lc.get("h", "m", "1") is None
    s = lc.stats()
    assert s["hits"] == 0 and s["misses"] == 1

    arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    lc.put("h", "m", "1", arr)
    out = lc.get("h", "m", "1")
    assert out is not None
    np.testing.assert_array_equal(out, arr)
    assert lc.stats()["hits"] == 1


def test_loader_cache_separate_keys_separate_entries():
    lc = LoaderCache()
    a = np.zeros(10, dtype=np.float32)
    b = np.ones(10, dtype=np.float32)
    lc.put("h1", "m", "1", a)
    lc.put("h2", "m", "1", b)
    lc.put("h1", "m", "2", a)
    assert lc.stats()["size"] == 3


def test_loader_cache_lru_eviction():
    lc = LoaderCache(max_items=8)
    for i in range(20):
        lc.put(f"h{i}", "m", "1", np.zeros(2, dtype=np.float32))
    s = lc.stats()
    assert s["size"] <= 8
    # Aelteste sollten weg sein, neueste noch da
    assert lc.get("h0", "m", "1") is None
    assert lc.get("h19", "m", "1") is not None


def test_loader_cache_lru_promotes_on_access():
    """LRU: access bewegt entry ans Ende -> wird nicht zuerst evicted."""
    lc = LoaderCache(max_items=4)
    for i in range(4):
        lc.put(f"h{i}", "m", "1", np.zeros(2, dtype=np.float32))
    # touch h0 -> bewegt es ans Ende
    _ = lc.get("h0", "m", "1")
    # neuer eintrag drueckt h1 (jetzt aelteste) raus
    lc.put("h_new", "m", "1", np.zeros(2, dtype=np.float32))
    assert lc.get("h0", "m", "1") is not None
    assert lc.get("h1", "m", "1") is None


def test_loader_cache_clear():
    lc = LoaderCache()
    lc.put("h", "m", "1", np.zeros(2, dtype=np.float32))
    assert lc.stats()["size"] == 1
    lc.clear()
    assert lc.stats()["size"] == 0


def test_loader_cache_singleton_idempotent():
    a = get_default_loader_cache()
    b = get_default_loader_cache()
    assert a is b


def test_loader_cache_singleton_reset():
    a = get_default_loader_cache()
    a.put("h", "m", "1", np.zeros(2, dtype=np.float32))
    clear_default_loader_cache()
    b = get_default_loader_cache()
    assert b.stats()["size"] == 0


def test_loader_cache_empty_hash_returns_none():
    lc = LoaderCache()
    assert lc.get("", "m", "1") is None


# ---------- Integration via post_processor ----------

def test_post_processor_uses_loader_cache(tmp_path: Path, monkeypatch):
    """Wenn _load_audio_embedding zweimal aufgerufen wird, kommt der zweite
    Aufruf aus dem process-LRU (kein zweiter np.load)."""
    from pb_studio.brain.post_processor import _load_audio_embedding
    from pb_studio.storage.embedding_cache import EmbeddingCache

    cache = EmbeddingCache(
        tmp_path / "ec.db",
        tmp_path / "embs",
    )
    try:
        emb = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
        cache.store(
            media_hash="abc",
            media_type="audio",
            embedding=emb,
            model_name=DEFAULT_AUDIO_MODEL_NAME,
            model_version=DEFAULT_AUDIO_MODEL_VERSION,
        )

        clear_default_loader_cache()
        out1 = _load_audio_embedding(cache, "abc")
        assert out1 is not None
        out2 = _load_audio_embedding(cache, "abc")
        assert out2 is not None
        # process-LRU sollte hits gezaehlt haben
        s = get_default_loader_cache().stats()
        assert s["hits"] >= 1
    finally:
        cache.close()


# ---------- CrossModalProjector hash-keyed cache ----------

def test_projector_hash_cache_first_miss_then_hit():
    p = CrossModalProjector()
    a = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    out1 = p.project_audio_for_hash("h1", a)
    out2 = p.project_audio_for_hash("h1", a)
    np.testing.assert_array_equal(out1, out2)
    s = p.projection_cache_stats()
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["size"] == 1


def test_projector_hash_cache_audio_video_separate():
    p = CrossModalProjector()
    a = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    v = np.random.rand(DEFAULT_VIDEO_DIM).astype(np.float32)
    p.project_audio_for_hash("h", a)
    p.project_video_for_hash("h", v)
    assert p.projection_cache_stats()["size"] == 2


def test_projector_hash_cache_no_hash_passes_through():
    p = CrossModalProjector()
    a = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    out1 = p.project_audio_for_hash("", a)
    out2 = p.project_audio_for_hash(None, a)
    assert out1 is not None
    assert out2 is not None
    # Cache wurde nie befuellt (keine Hash-Keys)
    assert p.projection_cache_stats()["size"] == 0


def test_projector_clear_cache():
    p = CrossModalProjector()
    a = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    p.project_audio_for_hash("h", a)
    assert p.projection_cache_stats()["size"] == 1
    p.clear_projection_cache()
    assert p.projection_cache_stats()["size"] == 0
    assert p.projection_cache_stats()["hits"] == 0


def test_projector_load_weights_invalidates_cache(tmp_path: Path):
    """Nach _load_weights() muss der projection cache geleert sein."""
    weights = tmp_path / "cm.npz"
    p1 = CrossModalProjector(seed=1, weights_path=weights)
    p1.save()

    a = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    p1.project_audio_for_hash("h", a)
    assert p1.projection_cache_stats()["size"] == 1

    # Frische Instanz mit anderen Matrizen, dann load -> sollte cache leeren
    p2 = CrossModalProjector(seed=999, weights_path=weights)
    a2 = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    p2.project_audio_for_hash("h", a2)
    assert p2.projection_cache_stats()["size"] == 1

    # _load_weights call: simuliere reload (in echten szenarien nach learning step)
    p2._load_weights()
    assert p2.projection_cache_stats()["size"] == 0


def test_projector_hash_cache_returns_same_array_object():
    """Cache-Hit gibt das gespeicherte Array zurueck (evtl. shared reference)."""
    p = CrossModalProjector()
    a = np.random.rand(DEFAULT_AUDIO_DIM).astype(np.float32)
    out1 = p.project_audio_for_hash("h", a)
    out2 = p.project_audio_for_hash("h", a)
    # Die ndarrays muessen value-gleich sein
    np.testing.assert_array_equal(out1, out2)
