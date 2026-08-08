"""Pacing must reject missing analysis stages before starting its worker."""

import asyncio
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
