"""Pacing must reject missing analysis stages before starting its worker."""

import asyncio
import contextlib
import importlib

import pytest
from fastapi import HTTPException

from backend.schemas.pacing_schemas import PacingConfigSchema

pacing_router = importlib.import_module("backend.routers.pacing_router")


def _valid_audio(*, structure: bool = False, key: bool = False) -> dict:
    analysis = {
        "bpm": 120.0,
        "beat_count": 1,
        "beats": [{"time": 0.5, "strength": 1.0}],
        "energy_curve": [0.5],
        "downbeats": [0.5],
        "downbeat_provenance": {"status": "measured"},
        "onset_times": [],
        "kick_times": [],
        "snare_times": [],
        "hihat_times": [],
        "_stage_status": {"beats": "completed"},
    }
    if structure:
        analysis["structure_segments"] = [
            {"start_time": 0.0, "end_time": 1.0, "label": "intro"}
        ]
        analysis["_stage_status"]["structure"] = "completed"
    if key:
        analysis["key"] = "C Major"
        analysis["_stage_status"]["key"] = "completed"
    return analysis


def _valid_video() -> dict:
    return {
        "avg_motion": 0.5,
        "motion": {"motion_curve": [0.2, 0.5]},
        "has_embedding": True,
        "embedding_dim": 1152,
        "embedding_samples": 2,
        "audio_key": "G Major",
        "stage_status": {
            "motion": "completed",
            "embedding": "completed",
            "audio_key": "completed",
        },
    }


def test_preflight_reports_mode_specific_missing_stages_and_clip_ids():
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10, 11],
        use_structure_awareness=True,
        use_motion_matching=True,
        use_semantic_matching=True,
        use_key_matching=True,
    )

    with pytest.raises(HTTPException) as caught:
        pacing_router._validate_pacing_analysis_preflight(
            config,
            _valid_audio(),
            {10: _valid_video(), 11: {}},
        )

    assert caught.value.status_code == 422
    detail = caught.value.detail
    assert detail["code"] == "pacing_analysis_incomplete"
    assert detail["missing"]["audio"] == [
        {
            "clip_id": 1,
            "stages": [
                {"stage": "structure", "status": "missing", "payload_valid": False},
                {"stage": "key", "status": "missing", "payload_valid": False},
            ],
        }
    ]
    assert detail["missing"]["video"] == [
        {
            "clip_id": 11,
            "stages": [
                {"stage": "motion", "status": "missing", "payload_valid": False},
                {"stage": "embedding", "status": "missing", "payload_valid": False},
                {"stage": "audio_key", "status": "missing", "payload_valid": False},
            ],
        }
    ]


def test_preflight_accepts_audio_key_that_the_source_cannot_provide():
    """A video without an audio track can never carry a key — that is not a defect.

    video_router marks this case "unavailable" and records no stage error. The
    gate must let it pass and report the clip as unscored instead of blocking a
    run that the selector handles natively (clip_selector.py, neutral factor).
    """
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10],
        use_key_matching=True,
    )
    silent_clip = _valid_video()
    silent_clip["audio_key"] = None
    silent_clip["stage_status"]["audio_key"] = "unavailable"
    silent_clip["stage_errors"] = {}

    report = pacing_router._validate_pacing_analysis_preflight(
        config,
        _valid_audio(key=True),
        {10: silent_clip},
    )

    assert report["key_scored_clips"] == 0
    assert report["key_unscored_clips"] == [10]


def test_preflight_still_blocks_a_real_audio_key_failure():
    """"unavailable" plus a recorded stage error is a defect, not a capability."""
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10],
        use_key_matching=True,
    )
    broken_clip = _valid_video()
    broken_clip["audio_key"] = None
    broken_clip["stage_status"]["audio_key"] = "unavailable"
    broken_clip["stage_errors"] = {"audio_key": "ffmpeg timeout"}

    with pytest.raises(HTTPException) as caught:
        pacing_router._validate_pacing_analysis_preflight(
            config,
            _valid_audio(key=True),
            {10: broken_clip},
        )

    assert caught.value.detail["missing"]["video"] == [
        {
            "clip_id": 10,
            "stages": [
                {"stage": "audio_key", "status": "unavailable", "payload_valid": False}
            ],
        }
    ]


def test_preflight_reports_partially_scored_key_pools():
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10, 11],
        use_key_matching=True,
    )
    silent_clip = _valid_video()
    silent_clip["audio_key"] = None
    silent_clip["stage_status"]["audio_key"] = "unavailable"
    silent_clip["stage_errors"] = {}

    report = pacing_router._validate_pacing_analysis_preflight(
        config,
        _valid_audio(key=True),
        {10: _valid_video(), 11: silent_clip},
    )

    assert report["key_scored_clips"] == 1
    assert report["key_unscored_clips"] == [11]


@pytest.mark.parametrize("stage", ["motion", "embedding"])
def test_preflight_never_waives_stages_that_are_always_producible(stage):
    """Only audio_key may be absent by capability. Motion/embedding must not."""
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10],
        use_motion_matching=True,
        use_semantic_matching=True,
    )
    clip = _valid_video()
    clip["stage_status"][stage] = "unavailable"
    clip["stage_errors"] = {}

    with pytest.raises(HTTPException) as caught:
        pacing_router._validate_pacing_analysis_preflight(
            config,
            _valid_audio(),
            {10: clip},
        )

    reported = [entry["stage"] for entry in caught.value.detail["missing"]["video"][0]["stages"]]
    assert reported == [stage]


def test_preflight_requires_truthful_status_and_valid_payload():
    config = PacingConfigSchema(audio_clip_id=1, video_clip_ids=[10])
    audio = _valid_audio()
    audio["_stage_status"]["beats"] = "partial"

    with pytest.raises(HTTPException) as caught:
        pacing_router._validate_pacing_analysis_preflight(config, audio, {})

    assert caught.value.detail["missing"]["audio"][0]["stages"] == [
        {"stage": "beats", "status": "partial", "payload_valid": True}
    ]

    audio["_stage_status"]["beats"] = "completed"
    audio["beats"] = None
    with pytest.raises(HTTPException) as caught:
        pacing_router._validate_pacing_analysis_preflight(config, audio, {})
    assert caught.value.detail["missing"]["audio"][0]["stages"] == [
        {"stage": "beats", "status": "completed", "payload_valid": False}
    ]


def test_brain_only_degrades_optional_video_axes():
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10],
        use_brain=True,
    )

    pacing_router._validate_pacing_analysis_preflight(
        config,
        _valid_audio(),
        {},
    )


@pytest.mark.parametrize(
    "field",
    ["use_motion_matching", "use_semantic_matching", "use_key_matching", "use_brain"],
)
def test_video_analysis_snapshot_is_loaded_for_all_consumers(field):
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[10],
        **{field: True},
    )
    assert pacing_router._requires_video_analysis(config) is True


def _state_with_one_silent_clip():
    silent_clip = _valid_video()
    silent_clip["audio_key"] = None
    silent_clip["stage_status"]["audio_key"] = "unavailable"
    silent_clip["stage_errors"] = {}

    class _State:
        current_audio_path = None

        def get_audio_clips_snapshot(self):
            return {1: {"id": 1, "path": "audio.wav", "duration_seconds": 10.0}}

        def get_video_clips_snapshot(self):
            return {10: {"id": 10, "name": "v", "path": "v.mp4", "duration_seconds": 10.0}}

        def get_audio_analysis(self, _clip_id):
            return _valid_audio(key=True)

        def get_video_analysis_snapshot(self):
            return {10: silent_clip}

        def require_project_context_current(self, _context):
            return None

        @contextlib.contextmanager
        def project_commit(self, _context):
            yield

        def set_timeline(self, _cuts):
            return None

    return _State()


def test_unscorable_key_matching_is_switched_off_and_reported(monkeypatch):
    """The run proceeds, and the response admits the mode did not apply."""
    seen_config = {}

    async def _publish(*_args, **_kwargs):
        return None

    def _fake_worker(config, *_args, **_kwargs):
        seen_config["use_key_matching"] = config.use_key_matching
        return [{"clip_id": "10", "start_time": 0.0, "end_time": 1.0, "metadata": {}}]

    async def _to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(pacing_router, "publish_log", _publish)
    monkeypatch.setattr(pacing_router, "publish_event", _publish)
    monkeypatch.setattr(pacing_router, "_run_pacing_generation", _fake_worker)
    monkeypatch.setattr(pacing_router, "_load_ui_anchors", lambda _s: [])
    monkeypatch.setattr(pacing_router.asyncio, "to_thread", _to_thread)

    response = asyncio.run(
        pacing_router._generate_cut_list_for_project(
            PacingConfigSchema(
                audio_clip_id=1,
                video_clip_ids=[10],
                use_key_matching=True,
            ),
            _state_with_one_silent_clip(),
            object(),
        )
    )

    assert response.cut_count == 1
    assert seen_config["use_key_matching"] is False, "no-op mode must not reach the engine"
    assert [d.mode for d in response.degradations] == ["key_matching"]
    assert response.degradations[0].scored_clips == 0
    assert response.degradations[0].total_clips == 1


def test_missing_beats_blocks_before_worker(monkeypatch):
    class _State:
        def get_audio_clips_snapshot(self):
            return {1: {"id": 1, "path": "audio.wav", "duration_seconds": 1.0}}

        def get_video_clips_snapshot(self):
            return {10: {"id": 10, "path": "video.mp4", "duration_seconds": 1.0}}

        def get_audio_analysis(self, _clip_id):
            return {}

    async def _publish_log(*_args, **_kwargs):
        return None

    async def _worker_must_not_start(*_args, **_kwargs):
        raise AssertionError("pacing worker started before preflight")

    monkeypatch.setattr(pacing_router, "publish_log", _publish_log)
    monkeypatch.setattr(pacing_router.asyncio, "to_thread", _worker_must_not_start)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(
            pacing_router._generate_cut_list_for_project(
                PacingConfigSchema(audio_clip_id=1, video_clip_ids=[10]),
                _State(),
                object(),
            )
        )

    assert caught.value.status_code == 422
    assert caught.value.detail["missing"]["audio"][0]["clip_id"] == 1
