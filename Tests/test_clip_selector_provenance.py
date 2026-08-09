"""OBJ-74/T019 deterministic ClipSelector provenance regressions."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from pb_studio.pacing.clip_selector import ClipSelector


def _clips(count: int = 6) -> list[dict]:
    return [
        {
            "id": str(index),
            "file_path": f"clip-{index}.mp4",
            "motion_score": index / 10.0,
        }
        for index in range(1, count + 1)
    ]


def _provenance(selected) -> dict:
    return selected.metadata["selection_provenance"]


@pytest.mark.parametrize(
    ("strategy", "expected_path"),
    [
        ("random", "random"),
        ("round_robin", "round_robin"),
        ("motion", "motion"),
    ],
)
def test_base_paths_emit_deterministic_provenance(
    monkeypatch,
    strategy: str,
    expected_path: str,
) -> None:
    monkeypatch.setattr(
        "pb_studio.pacing.clip_selector.random.choice",
        lambda clips: clips[0],
    )
    first = ClipSelector(strategy=strategy).select_clip(
        _clips(3),
        trigger_strength=0.6,
        trigger_type="beat",
    )
    second = ClipSelector(strategy=strategy).select_clip(
        _clips(3),
        trigger_strength=0.6,
        trigger_type="beat",
    )

    assert _provenance(first) == _provenance(second)
    assert _provenance(first)["selection_path"] == expected_path
    assert _provenance(first)["candidate_ids"] == ["1", "2", "3"]
    assert _provenance(first)["selected_clip_id"] == first.clip_id
    assert _provenance(first)["selected_score"] == first.score


def test_empty_pool_emits_terminal_provenance() -> None:
    selected = ClipSelector().select_clip([])

    provenance = _provenance(selected)
    assert selected.clip_id == "none"
    assert provenance["selection_path"] == "no_candidates"
    assert provenance["fallback_reason"] == "empty_candidate_pool"
    assert provenance["eligible_candidate_ids"] == []


def test_adaptive_diversity_records_unique_lru_and_eligible_pool() -> None:
    selector = ClipSelector(
        strategy="round_robin",
        blacklist_percentage=0.8,
    )
    clips = _clips(6)

    selected_ids = []
    provenances = []
    for _ in range(8):
        selected = selector.select_clip(clips)
        selected_ids.append(selected.clip_id)
        provenances.append(_provenance(selected))

    assert all(left != right for left, right in zip(selected_ids, selected_ids[1:]))
    assert all(item["blacklist_size"] == 3 for item in provenances)
    assert all(item["diversity_policy"] == "adaptive_unique_lru" for item in provenances)
    assert all(len(item["eligible_candidate_ids"]) >= 3 for item in provenances)
    assert all(
        len(item["recent_clip_ids"]) == len(set(item["recent_clip_ids"]))
        for item in provenances
    )
    assert provenances[1]["excluded_recent_clip_ids"] == [selected_ids[0]]


class _VectorStore:
    def __init__(self, results) -> None:
        self.index = SimpleNamespace(ntotal=len(results))
        self.results = results

    def search(self, _embedding, *, k):
        return self.results[:k]


def test_semantic_faiss_path_records_semantic_and_motion_scores() -> None:
    store = _VectorStore([({"file_path": "target.mp4"}, 0.91)])
    selector = ClipSelector(strategy="semantic", vector_store=store)
    selector._get_text_embedding = lambda _prompt: np.array(
        [1.0, 0.0], dtype=np.float32
    )

    selected = selector.select_clip(
        [
            {"id": "other", "file_path": "other.mp4", "motion_score": 0.6},
            {"id": "target", "file_path": "target.mp4", "motion_score": 0.2},
        ],
        prompt="calm scene",
        trigger_strength=0.2,
    )

    provenance = _provenance(selected)
    assert selected.clip_id == "target"
    assert provenance["selection_path"] == "semantic_faiss"
    assert provenance["score_components"]["semantic"] == {
        "status": "matched",
        "source": "faiss",
        "prompt": "calm scene",
        "score": pytest.approx(0.91),
    }
    assert provenance["score_components"]["ranking"]["selection_path"] == "motion"


def test_semantic_direct_path_records_similarity_without_changing_ranking() -> None:
    selector = ClipSelector(strategy="semantic")
    selector._get_text_embedding = lambda _prompt: np.array(
        [1.0, 0.0], dtype=np.float32
    )
    clips = [
        {
            "id": "semantic",
            "file_path": "semantic.mp4",
            "motion_score": 0.5,
            "video_embedding": [1.0, 0.0],
        }
    ]
    clips.extend(
        {
            "id": f"middle-{index}",
            "file_path": f"middle-{index}.mp4",
            "motion_score": 0.0,
            "video_embedding": [0.8, 0.6],
        }
        for index in range(9)
    )
    clips.append(
        {
            "id": "motion-only",
            "file_path": "motion-only.mp4",
            "motion_score": 0.5,
            "video_embedding": [-1.0, 0.0],
        }
    )

    selected = selector.select_clip(clips, trigger_strength=0.5)

    provenance = _provenance(selected)
    assert selected.clip_id == "semantic"
    assert provenance["selection_path"] == "semantic_direct_embedding"
    assert provenance["score_components"]["semantic"]["score"] == pytest.approx(1.0)
    assert provenance["score_components"]["semantic"]["faiss_status"] == "unavailable"


def test_semantic_unavailable_records_motion_fallback_reason() -> None:
    selector = ClipSelector(strategy="semantic")
    selector._get_text_embedding = lambda _prompt: None

    selected = selector.select_clip(_clips(3), trigger_strength=0.3)

    provenance = _provenance(selected)
    assert provenance["selection_path"] == "semantic_fallback_motion"
    assert provenance["fallback_reason"] == "semantic_query_embedding_unavailable"
    assert provenance["score_components"]["fallback"]["selection_path"] == "motion"


class _FeatureAdapter:
    def candidate_features(self, **_kwargs):
        return SimpleNamespace(
            motion_score=0.7,
            confidence=0.8,
            feature_provenance={"motion": {"source": "test"}},
            segment_type="normal",
            semantic_status="measured",
            semantic_reason=None,
        )


class _BrainReranker:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def rerank(self, candidates, **_kwargs):
        if self.fail:
            raise RuntimeError("reranker unavailable")
        candidate = candidates[-1]
        return [
            SimpleNamespace(
                candidate=candidate.candidate,
                features=candidate.features,
                final_score=0.84,
                brain_scores={"motion_match_weight": 0.84},
            )
        ]


def test_brain_deep_hook_records_success_and_preserves_brain_metadata() -> None:
    selector = ClipSelector(strategy="motion")
    selector.brain_reranker = _BrainReranker()
    selector.brain_context_keys = ["project:test"]
    selector.brain_feature_adapter = _FeatureAdapter()

    selected = selector.select_clip(_clips(2))

    provenance = _provenance(selected)
    assert selected.clip_id == "2"
    assert provenance["selection_path"] == "brain"
    assert provenance["score_components"]["brain_final_score"] == pytest.approx(0.84)
    assert selected.metadata["brain_final_score"] == pytest.approx(0.84)


def test_brain_error_records_deterministic_strategy_fallback() -> None:
    selector = ClipSelector(strategy="round_robin")
    selector.brain_reranker = _BrainReranker(fail=True)
    selector.brain_context_keys = ["project:test"]
    selector.brain_feature_adapter = _FeatureAdapter()

    selected = selector.select_clip(_clips(2))

    provenance = _provenance(selected)
    assert selected.clip_id == "1"
    assert provenance["selection_path"] == "brain_fallback_round_robin"
    assert provenance["fallback_reason"] == "brain_error:RuntimeError"
    assert provenance["score_components"]["fallback"]["selection_path"] == "round_robin"


def test_motion_provenance_exposes_key_and_anchor_contributions(monkeypatch) -> None:
    from pb_studio.pacing import advanced_pacing_engine

    selector = ClipSelector(strategy="motion")
    selector.use_key_matching = True
    selector.audio_key = "C"
    selector.video_keys = {"anchor": "G"}
    selector.bridging_in_to = {"file_path": "manual-anchor.mp4"}
    selector._get_clip_neighbors = lambda _path: ["anchor.mp4"]
    monkeypatch.setattr(
        advanced_pacing_engine,
        "_key_compatibility_score",
        lambda _audio_key, _video_key: 0.75,
    )

    selected = selector.select_clip(
        [{"id": "anchor", "file_path": "anchor.mp4", "motion_score": 0.5}],
        trigger_strength=0.5,
    )

    components = _provenance(selected)["score_components"]
    assert components["anchor_in_bonus"] == 400.0
    assert components["anchor_out_bonus"] == 0.0
    assert components["key_compatibility_multiplier"] == pytest.approx(0.75)
    assert components["total_score"] == pytest.approx(
        components["pre_key_score"] * 0.75
    )
