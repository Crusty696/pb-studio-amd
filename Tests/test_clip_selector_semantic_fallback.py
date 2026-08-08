"""Regression tests for ClipSelector's direct semantic fallback."""

from types import SimpleNamespace

import numpy as np
import pytest

from pb_studio.pacing.clip_selector import ClipSelector


class _VectorStore:
    def __init__(self, *, ntotal: int, results=None, error: Exception | None = None):
        self.index = SimpleNamespace(ntotal=ntotal)
        self.results = results or []
        self.error = error
        self.search_calls = 0

    def search(self, _embedding, *, k):
        self.search_calls += 1
        if self.error is not None:
            raise self.error
        return self.results[:k]


def _direct_embedding_clips(embedding_key: str) -> list[dict]:
    clips = [
        {
            "id": "semantic",
            "file_path": "semantic.mp4",
            "motion_score": 0.5,
            embedding_key: [1.0, 0.0],
        }
    ]
    clips.extend(
        {
            "id": f"middle-{index}",
            "file_path": f"middle-{index}.mp4",
            "motion_score": 0.0,
            embedding_key: [0.8, 0.6],
        }
        for index in range(9)
    )
    clips.append(
        {
            "id": "motion-only",
            "file_path": "motion-only.mp4",
            "motion_score": 0.5,
            embedding_key: [-1.0, 0.0],
        }
    )
    return clips


@pytest.mark.parametrize(
    "vector_store",
    [None, _VectorStore(ntotal=0)],
    ids=["unavailable", "empty"],
)
def test_direct_video_embeddings_are_used_without_populated_faiss(vector_store):
    selector = ClipSelector(strategy="semantic", vector_store=vector_store)
    prompts = []
    selector._get_text_embedding = lambda prompt: (
        prompts.append(prompt) or np.array([1.0, 0.0], dtype=np.float32)
    )

    selected = selector.select_clip(
        _direct_embedding_clips("video_embedding"),
        trigger_strength=0.5,
        trigger_type="beat",
        prompt="custom semantic prompt",
        current_time=3.0,
    )

    assert selected.clip_id == "semantic"
    assert prompts == ["custom semantic prompt"]
    if vector_store is not None:
        assert vector_store.search_calls == 0


def test_direct_embeddings_are_used_when_faiss_search_fails():
    vector_store = _VectorStore(ntotal=1, error=RuntimeError("index unavailable"))
    selector = ClipSelector(strategy="semantic", vector_store=vector_store)
    selector._get_text_embedding = lambda _prompt: np.array(
        [1.0, 0.0], dtype=np.float32
    )

    selected = selector.select_clip(
        _direct_embedding_clips("embedding"),
        trigger_strength=0.5,
        trigger_type="beat",
    )

    assert vector_store.search_calls == 1
    assert selected.clip_id == "semantic"


def test_faiss_metadata_paths_are_normalized_across_supported_keys(tmp_path):
    canonical = tmp_path / "target.mp4"
    equivalent = tmp_path / "folder" / ".." / "target.mp4"
    vector_store = _VectorStore(
        ntotal=1,
        results=[({"file_path": canonical}, 0.99)],
    )
    selector = ClipSelector(strategy="semantic", vector_store=vector_store)
    selector._get_text_embedding = lambda _prompt: np.array(
        [1.0, 0.0], dtype=np.float32
    )

    selected = selector.select_clip(
        [
            {"id": "other", "path": str(tmp_path / "other.mp4"), "motion_score": 0.5},
            {"id": "target", "path": equivalent, "motion_score": 0.0},
        ],
        trigger_strength=0.5,
        trigger_type="beat",
    )

    assert selected.clip_id == "target"
    assert selected.clip_path == equivalent


def test_missing_query_embedding_keeps_audio_aware_motion_fallback():
    selector = ClipSelector(strategy="semantic")
    selector._get_text_embedding = lambda _prompt: None
    selector.bass_curve = np.zeros(10, dtype=np.float32)
    selector.duration_seconds = 10.0

    selected = selector.select_clip(
        [
            {"id": "intense", "file_path": "intense.mp4", "motion_score": 0.9},
            {"id": "calm", "file_path": "calm.mp4", "motion_score": 0.1},
        ],
        trigger_strength=0.6,
        trigger_type="beat",
        current_time=5.0,
    )

    assert selected.clip_id == "calm"
