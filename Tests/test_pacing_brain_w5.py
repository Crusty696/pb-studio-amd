from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.routers.pacing_router import _requires_video_analysis
from backend.schemas.pacing_schemas import PacingConfigSchema
from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.clip_selector import ClipSelector
from pb_studio.pacing.pacing_models import TriggerSettings
from pb_studio.services.pacing_service import PacingService, _uses_advanced_pacing


class _CapturingReranker:
    def __init__(self) -> None:
        self.inputs = []
        self.context_keys = []
        self.min_confidence = None

    def rerank(self, candidates, *, context_keys, min_confidence=0.0):
        self.inputs = list(candidates)
        self.context_keys = list(context_keys)
        self.min_confidence = min_confidence
        return [
            SimpleNamespace(
                candidate=self.inputs[0].candidate,
                features=self.inputs[0].features,
                final_score=0.8,
                brain_scores={"motion_match_weight": 0.8},
            )
        ]


def test_use_brain_activates_advanced_pacing_and_video_analysis():
    assert _uses_advanced_pacing({"use_brain": True}, semantic_enabled=False)
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[7],
        use_brain=True,
        use_motion_matching=False,
    )
    assert _requires_video_analysis(config)


def test_pacing_service_forwards_cached_brain_features(monkeypatch):
    reranker = _CapturingReranker()
    from pb_studio.brain.brain_service import BrainService

    monkeypatch.setattr(
        BrainService,
        "get",
        classmethod(lambda cls: SimpleNamespace(reranker=reranker)),
    )
    selector = ClipSelector()
    engine = SimpleNamespace(clip_selector=selector)
    service = PacingService()

    service._configure_brain_selector(
        engine,
        {"use_brain": True, "brain_min_confidence": 0.72},
        {
            "duration_seconds": 10.0,
            "energy_curve": [0.2, 0.8],
            "spectral_data": {"centroids": [100.0, 400.0]},
            "mood_tags": ["dark"],
        },
        [{"id": 7, "avg_motion": 0.6, "avg_brightness": 0.4}],
        10.0,
        None,
    )

    assert selector.brain_reranker is reranker
    assert selector.brain_min_confidence == pytest.approx(0.72)
    assert selector.brain_audio_features["energy_curve"] == [0.2, 0.8]
    assert selector.brain_audio_features["centroid_curve"][1] == pytest.approx(
        1.0, abs=0.02
    )
    assert selector.brain_video_features_by_clip["7"]["avg_motion"] == 0.6


def test_brain_selector_receives_real_features_and_threshold():
    selector = ClipSelector()
    reranker = _CapturingReranker()
    selector.brain_reranker = reranker
    selector.brain_context_keys = [""]
    selector.brain_min_confidence = 0.63
    selector.brain_audio_features = {
        "energy_curve": [0.1, 0.9],
        "centroid_curve": [0.2, 0.8],
        "duration_seconds": 10.0,
        "mood_tags": ["energetic"],
    }
    selector.brain_video_features_by_clip = {
        "7": {
            "avg_motion": 0.75,
            "scenes": [{"start_time": 4.5, "end_time": 6.0}],
            "avg_brightness": 0.7,
            "avg_saturation": 0.6,
            "avg_color_temp": 0.4,
            "motion_category": "high",
            "mood_tags": ["energetic"],
        }
    }

    selected = selector.select_clip(
        [{"id": 7, "file_path": "clip.mp4"}],
        trigger_strength=0.8,
        trigger_type="beat",
        current_time=5.0,
        cut_duration_sec=2.5,
    )

    features = reranker.inputs[0].features
    assert selected.clip_id == "7"
    assert reranker.min_confidence == pytest.approx(0.63)
    assert features.audio_energy == pytest.approx(0.9)
    assert features.audio_centroid == pytest.approx(0.8)
    assert features.motion_score == pytest.approx(1.0)
    assert features.scene_distance_sec == pytest.approx(0.5)
    assert features.trigger_strength == pytest.approx(0.8)
    assert features.pace_class_score == pytest.approx(1.0)
    assert features.cut_duration_sec == pytest.approx(2.5)
    assert features.mood_tags == ["energetic"]
    assert features.audio_mood_tags == ["energetic"]


@pytest.mark.parametrize(
    ("mode", "expected_times"),
    [
        ("all", [0.0, 1.0, 2.0, 3.0]),
        ("downbeat_only", [0.0, 2.0]),
        ("strong_only", [1.0, 3.0]),
    ],
)
def test_beat_trigger_mode_filters_live_beat_triggers(mode, expected_times):
    engine = AdvancedPacingEngine(
        trigger_settings=TriggerSettings(beat_trigger_mode=mode)
    )
    engine._pre_cached_beat_strengths = [0.2, 0.8, 0.5, 1.0]

    triggers = engine._build_beat_triggers(
        beats=[0.0, 1.0, 2.0, 3.0],
        downbeats=[0.0, 2.0],
    )

    assert [trigger.time for trigger in triggers] == expected_times
