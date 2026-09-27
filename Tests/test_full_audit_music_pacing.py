"""Regressions for full-audit music-led pacing findings 35-39 and 53."""

from __future__ import annotations

import importlib

import numpy as np
import pytest

from backend.schemas.pacing_schemas import PacingConfigSchema
from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.clip_selector import ClipSelector
from pb_studio.pacing.pacing_models import CutListEntry
from pb_studio.services.pacing_service import PacingService

pacing_router = importlib.import_module("backend.routers.pacing_router")


def test_raft_motion_normalization_is_linear_bounded_and_continuous():
    raw_scores = [0.0, 0.5, 1.0, 1.01, 15.0, 30.0, 45.0]
    normalized = [ClipSelector._normalize_motion_score(value) for value in raw_scores]

    assert normalized == pytest.approx([0.0, 0.5 / 30, 1 / 30, 1.01 / 30, 0.5, 1.0, 1.0])
    assert normalized == sorted(normalized)
    assert all(0.0 <= value <= 1.0 for value in normalized)


def test_expected_bpm_grid_remaps_strength_to_nearest_measured_beat():
    engine = AdvancedPacingEngine.__new__(AdvancedPacingEngine)
    engine._pre_cached_beat_strengths = [0.1, 0.9, 0.2]
    corrected, _ = engine._apply_expected_bpm_grid(
        [0.0, 0.5, 1.0], [], expected_bpm=120.0,
        detected_bpm=100.0, duration=1.1,
    )
    assert len(engine._pre_cached_beat_strengths) == len(corrected)
    assert corrected == pytest.approx([0.0, 0.5, 1.0])
    assert engine._pre_cached_beat_strengths == pytest.approx([0.1, 0.9, 0.2])


def test_theme_bonus_cannot_overwhelm_music_and_motion_score():
    selector = ClipSelector.__new__(ClipSelector)
    selector.motion_tolerance = 0.35
    selector.use_key_matching = False
    selector.audio_key = None
    selector._last_clip_path = None
    selector._last_clip_motion_score = 0.5
    selector._continuity_weight = 0.0
    selector.use_motion_matching = True
    selector.active_theme = "neon_cyber_rave"
    selector.bridging_in_to = None
    selector.bridging_out_of = None
    selector._selection_details = {}
    selector._record_selection_details = ClipSelector._record_selection_details.__get__(selector)
    selector._update_continuity = lambda *args, **kwargs: None
    selector._update_recently_used = lambda *args, **kwargs: None
    selected = selector._select_by_motion(
        [
            {"id": "theme", "file_path": "theme.mp4", "motion_score": 0.0,
             "tags": ["neon"]},
            {"id": "music", "file_path": "music.mp4", "motion_score": 1.0,
             "tags": []},
        ],
        1.0, "beat", semantic_scores={
            ClipSelector._normalized_path_key("theme.mp4"): 0.0,
            ClipSelector._normalized_path_key("music.mp4"): 1.0,
        },
    )
    assert selected.clip_id == "music"
    assert selector._selection_details["score_components"]["semantic_similarity_score"] == 1.0
    assert selector._selection_details["score_components"]["theme_bonus"] == 0.0


def test_theme_bonus_only_breaks_a_near_tie_for_narrative_continuity():
    selector = ClipSelector.__new__(ClipSelector)
    selector.motion_tolerance = 0.35
    selector.use_key_matching = False
    selector.audio_key = None
    selector._last_clip_path = None
    selector._last_clip_motion_score = 0.5
    selector._continuity_weight = 0.0
    selector.use_motion_matching = True
    selector.active_theme = "neon_cyber_rave"
    selector.bridging_in_to = None
    selector.bridging_out_of = None
    selector._selection_details = {}
    selector._record_selection_details = ClipSelector._record_selection_details.__get__(selector)
    selector._update_continuity = lambda *args, **kwargs: None
    selector._update_recently_used = lambda *args, **kwargs: None

    selected = selector._select_by_motion(
        [
            {"id": "theme", "file_path": "theme.mp4", "motion_score": 30.0,
             "tags": ["neon"]},
            {"id": "music", "file_path": "music.mp4", "motion_score": 30.0,
             "tags": []},
        ],
        1.0, "beat", semantic_scores={
            ClipSelector._normalized_path_key("theme.mp4"): 0.48,
            ClipSelector._normalized_path_key("music.mp4"): 0.50,
        },
    )

    assert selected.clip_id == "theme"
    components = selector._selection_details["score_components"]
    assert components["semantic_similarity_score"] == pytest.approx(0.48)
    assert components["theme_bonus"] == pytest.approx(0.05)


def test_semantic_request_keeps_music_fit_primary_and_uses_theme_only_for_near_tie(monkeypatch):
    selector = ClipSelector(strategy="semantic")
    selector.active_theme = "neon_cyber_rave"
    selector._get_text_embedding = lambda _prompt: np.asarray([1.0, 0.0], dtype=np.float32)
    selector._vector_store_has_embeddings = lambda: False
    clips = [
        {"id": "theme", "file_path": "theme.mp4", "motion_score": 0.0,
         "tags": ["neon"], "video_embedding": [0.999, 0.045]},
        {"id": "music", "file_path": "music.mp4", "motion_score": 30.0,
         "tags": [], "video_embedding": [1.0, 0.0]},
    ]
    music_wins = selector.select_clip(clips, 1.0, "beat")
    assert music_wins.clip_id == "music"

    clips[0]["video_embedding"] = [0.9998, 0.02]
    clips[1]["video_embedding"] = [1.0, 0.0]
    themed_near_tie = selector.select_clip(clips, 0.01, "beat")
    assert themed_near_tie.clip_id == "theme"


def test_worker_normalizes_string_analysis_ids_before_motion_clip_build(monkeypatch):
    captured = {}

    class FakeService:
        def generate_cut_list(self, **kwargs):
            captured.update(kwargs)
            return [CutListEntry(clip_id="clip_10", start_time=0.0, end_time=1.0)]

    monkeypatch.setattr(PacingService, "__new__", lambda cls: FakeService())
    config = PacingConfigSchema(
        audio_clip_id=1, video_clip_ids=[10], use_motion_matching=True
    )
    result = pacing_router._run_pacing_generation(
        config,
        {1: {"path": "audio.wav", "duration_seconds": 5.0}},
        {10: {"id": 10, "name": "clip", "path": "clip.mp4", "duration_seconds": 3.0}},
        cached_analysis={"beats": [0.0, 0.5], "bpm": 120.0},
        video_analysis_cache={"10": {"avg_motion": 12.0}},
    )
    assert result
    assert captured["clips"][0]["motion_score"] == 12.0


def test_short_export_chapter_energy_uses_full_track_timebase(monkeypatch):
    service = PacingService.__new__(PacingService)
    beats = [float(i) / 2.0 for i in range(64)]
    # Output uses first 32 s of a 64-s analyzed track. Energy transition
    # occurs at source time 8 s (first 16 of 128 curve bins).
    curve = np.concatenate((np.zeros(16), np.ones(112)))
    service._chapter_energy_duration = 64.0
    monkeypatch.setattr(
        "pb_studio.services.pacing_service.select_theme_for_chapter",
        lambda energy, _previous: "low" if energy <= 0.58 else "high",
    )
    chapters = service.segment_timeline_into_chapters(curve, beats, 120.0, 32.0)
    assert len(chapters) == 2
    assert chapters[0]["start"] == 0.0
    assert chapters[1]["start"] == pytest.approx(16.0)
    assert chapters[-1]["end"] == 32.0
    assert chapters[0]["theme"] == "low"
    assert chapters[1]["theme"] == "high"


def test_repeated_source_reset_is_not_reported_as_music_trigger(monkeypatch):
    service = PacingService.__new__(PacingService)
    monkeypatch.setattr(service, "_get_clip_duration", lambda _path: 3.0)
    entries = [CutListEntry(
        clip_id="clip_1", start_time=0.0, end_time=8.0,
        metadata={"file_path": "short.mp4", "source_duration": 3.0,
                 "clip_start": 0.0, "trigger_type": "beat",
                 "trigger_strength": 0.8, "trigger_provenance": {"measured": True}},
    )]
    service._finalize_cut_list(entries, 8.0)
    assert [entry.start_time for entry in entries] == [0.0, 3.0, 6.0]
    for entry in entries[1:]:
        assert entry.metadata["trigger_type"] == "source_repeat"
        assert "trigger_provenance" not in entry.metadata


def test_preflight_resolves_string_cache_key_for_integer_clip_id():
    config = PacingConfigSchema(audio_clip_id=1, video_clip_ids=[10], use_motion_matching=True)
    video = {"10": {"motion": {"motion_curve": [0.2]}, "stage_status": {"motion": "completed"}}}
    report = pacing_router._validate_pacing_analysis_preflight(
        config,
        {
            "beats": [0.0, 0.5], "bpm": 120.0, "beat_count": 2,
            "energy_curve": [], "downbeats": [], "onset_times": [],
            "kick_times": [], "snare_times": [], "hihat_times": [],
            "downbeat_provenance": {},
            "_stage_status": {"beats": "completed"},
        },
        video,
    )
    assert report["key_scored_clips"] == 0
    assert report["key_unscored_clips"] == []


def test_normal_path_video_analysis_lookup_accepts_normalized_ids():
    """Preflight and worker lookup share numeric ID normalization contract."""
    assert pacing_router._normalize_video_analysis_ids({"10": {"ok": True}}) == {
        10: {"ok": True}
    }
