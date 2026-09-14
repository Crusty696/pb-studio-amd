"""Beat This contracts through persistence, API and actual pacing triggers.

Model inference is injected. These tests never open a GPU session or real media.
"""

from __future__ import annotations

import copy
import importlib
import json
import wave

import numpy as np
import pytest

from backend.app_state import AppState
from backend.schemas.audio_schemas import AudioAnalysisResult, AudioAnalyzeRequest
from pb_studio.audio.downbeat_alignment import align_downbeats
from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.pacing_models import TriggerSettings
from pb_studio.services.pacing_service import PacingService


REVISION = "fixture-immutable-model-revision"
GRID = [index * 0.5 for index in range(16)]


def _engine_for(analysis):
    engine = AdvancedPacingEngine(
        trigger_settings=TriggerSettings(beat_trigger_mode="downbeat_only")
    )
    PacingService.__new__(PacingService)._inject_cached_into_engine(
        engine, "fixture.wav", analysis
    )
    return engine


def test_aligned_downbeats_survive_persistence_reload_api_and_real_triggers(
    monkeypatch, tmp_path
):
    audio = tmp_path / "persist.wav"
    audio.write_bytes(b"RIFF")
    beats = [
        {"time": time, "strength": 0.2 + index / 20, "beat_type": "beat"}
        for index, time in enumerate(GRID)
    ]
    original = copy.deepcopy(beats)
    neural = [time + 0.02 for time in GRID]
    mapped, provenance = align_downbeats(beats, neural, neural[::4])
    assert beats == original, "Alignment must not mutate the product grid"
    assert mapped == GRID[::4]
    provenance["model_revision"] = REVISION
    for beat in beats:
        if beat["time"] in mapped:
            beat["beat_type"] = "downbeat"

    row = {
        "id": 101, "file_path": str(audio), "duration_sec": 8.0,
        "metadata_json": json.dumps(
            {"clip_type": "audio", "clip_id": 7, "name": "persist"}
        ),
        "ai_data_json": "{}",
    }
    payloads = []

    class FakeRepo:
        def find_by_project_and_path(self, **kwargs):
            return row

        def update_status(self, media_id, status, *, ai_data):
            assert media_id == 101 and status == "analyzed"
            payloads.append(copy.deepcopy(ai_data))
            row["ai_data_json"] = json.dumps(ai_data)

        def get_by_project(self, project_id):
            return [row]

        def delete_media(self, media_id):
            raise AssertionError("Persistence proof must never delete media")

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository", FakeRepo
    )
    state = AppState()
    state.audio_clips[7] = {
        "id": 7, "path": str(audio), "duration_seconds": 8.0,
    }
    state.update_audio_analysis(
        clip_id=7, bpm=120.0, beat_count=len(beats),
        beats_json=json.dumps(beats), downbeats=mapped,
        downbeat_provenance=provenance, is_analyzed=True,
    )
    assert payloads[0]["downbeat_provenance"] == provenance
    assert payloads[0]["downbeats"] == mapped
    assert state.get_audio_analysis(7)["downbeat_provenance"] == provenance

    reloaded = AppState()
    assert reloaded.load_from_db() is True
    cache = reloaded.get_audio_analysis(7)
    assert cache["bpm"] == 120.0
    assert cache["beats"] == beats
    dto = AudioAnalysisResult.model_validate(cache).model_dump()
    assert dto["downbeat_provenance"] == provenance
    assert dto["downbeats"] == mapped
    assert dto["bpm"] == 120.0
    engine = _engine_for(dto)
    assert engine._pre_cached_beats == GRID
    assert engine._pre_cached_beat_strengths == [b["strength"] for b in original]
    triggers = engine._build_beat_triggers(
        engine._pre_cached_beats, engine._pre_cached_downbeats
    )
    assert [trigger.time for trigger in triggers] == mapped
    assert len(mapped) == len(set(mapped))
    assert set(mapped).issubset(GRID)


@pytest.mark.parametrize("status", ["unavailable", "derived", "failed"])
def test_untrusted_provenance_does_not_inject_downbeat_markers(status):
    engine = _engine_for({
        "beats": [{"time": t, "beat_type": "downbeat"} for t in GRID],
        "downbeats": GRID[::4],
        "downbeat_provenance": {"status": status},
    })
    assert not getattr(engine, "_pre_cached_downbeats", [])


@pytest.fixture
def router_fixture(monkeypatch, tmp_path):
    router = importlib.import_module("backend.routers.audio_router")
    path = tmp_path / "clicks.wav"
    sr = 22050
    samples = np.zeros(sr * 8, dtype="<i2")
    for time in GRID:
        start = int(time * sr)
        samples[start:start + 100] = 16000
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sr)
        output.writeframes(samples.tobytes())

    class Detector:
        def detect_beats_with_downbeats(self, path, on_progress=None):
            return GRID.copy(), []

    monkeypatch.setattr(router, "_get_beat_detector", Detector)
    request = AudioAnalyzeRequest(
        clip_id=7, detect_beats=True, detect_structure=False,
        spectral_analysis=False, detect_key=False,
    )
    return router, str(path), request


def test_router_enrichment_precedes_completed_beat_checkpoint(router_fixture):
    router, path, request = router_fixture
    events = []
    neural = [time + 0.02 for time in GRID]

    def runner(source, duration):
        assert source == path and duration == 8.0
        events.append("neural")
        return neural, neural[::4], REVISION

    def checkpoint(stage, payload):
        if stage == "beats":
            events.append("checkpoint")
            assert payload["downbeats"] == neural[::4]
            assert payload["downbeat_provenance"]["model_revision"] == REVISION
            assert payload["_stage_status"]["beats"] == "completed"

    result = router._run_audio_analysis(
        path, 7, request, on_stage_checkpoint=checkpoint,
        neural_downbeat_runner=runner,
    )
    assert events == ["neural", "checkpoint"]
    assert result["bpm"] == pytest.approx(120.0)
    assert [beat["time"] for beat in result["beats"]] == neural
    assert [b["time"] for b in result["beats"] if b["beat_type"] == "downbeat"] == neural[::4]
    assert result["downbeat_provenance"]["method"] == "beat_this_onnx_native"


@pytest.mark.parametrize("kind", ["missing_asset", "inference_error", "empty", "single"])
def test_router_failure_retains_beats_and_honest_provenance(router_fixture, kind):
    from pb_studio.audio.beat_this_tracker import BeatThisUnavailable

    router, path, request = router_fixture

    def runner(source, duration):
        if kind == "missing_asset":
            raise BeatThisUnavailable("fixture model missing")
        if kind == "inference_error":
            raise RuntimeError("fixture inference failed")
        neural = [] if kind == "empty" else [0.5]
        return neural, [], REVISION

    result = router._run_audio_analysis(
        path, 7, request, neural_downbeat_runner=runner
    )
    assert result["bpm"] == pytest.approx(120.0)
    assert [beat["time"] for beat in result["beats"]] == GRID
    assert result["downbeats"] == []
    assert all(beat["beat_type"] == "beat" for beat in result["beats"])
    assert result["downbeat_provenance"]["status"] == (
        "failed" if kind == "inference_error" else "unavailable"
    )
    assert result["downbeat_provenance"]["synthetic"] is False


@pytest.mark.parametrize("interval", [0.5, 0.4])
def test_native_grid_replaces_conflicting_legacy_phase_and_tempo(
    router_fixture, interval
):
    router, path, request = router_fixture
    neural = [0.25 + index * interval for index in range(16)]
    result = router._run_audio_analysis(
        path, 7, request,
        neural_downbeat_runner=lambda *_: (neural, neural[::4], REVISION),
    )
    assert [beat["time"] for beat in result["beats"]] == neural
    assert result["beat_count"] == len(neural)
    assert result["bpm"] == pytest.approx(60.0 / interval)
    assert result["downbeats"] == neural[::4]
    provenance = result["downbeat_provenance"]
    assert provenance["method"] == "beat_this_onnx_native"
    assert provenance["status"] == "measured"
    assert provenance["model_revision"] == REVISION
    assert provenance["legacy_bpm"] == pytest.approx(120.0)
    assert provenance["legacy_beat_count"] == len(GRID)
    dto = AudioAnalysisResult.model_validate(result).model_dump()
    engine = _engine_for(dto)
    triggers = engine._build_beat_triggers(
        engine._pre_cached_beats, engine._pre_cached_downbeats
    )
    assert [trigger.time for trigger in triggers] == neural[::4]


@pytest.mark.parametrize(
    ("neural", "downbeats"),
    [
        ([0.0, float("nan"), 1.0], [0.0]),
        ([0.0, 0.5, 0.5, 1.0], [0.0]),
        ([0.0, 1.0, 0.5], [0.0]),
        ([-0.1, 0.5, 1.0], [0.5]),
        ([0.0, 0.5, 8.1], [0.0]),
        ([0.0, 0.5, 1.0], [0.25]),
        ([0.0, 0.5, 1.0], [0.0, 0.0]),
    ],
)
def test_invalid_native_output_never_replaces_valid_legacy_grid(
    router_fixture, neural, downbeats
):
    router, path, request = router_fixture
    result = router._run_audio_analysis(
        path, 7, request,
        neural_downbeat_runner=lambda *_: (neural, downbeats, REVISION),
    )
    assert [beat["time"] for beat in result["beats"]] == GRID
    assert result["bpm"] == pytest.approx(120.0)
    assert result["downbeats"] == []
    assert all(beat["beat_type"] == "beat" for beat in result["beats"])
    assert result["downbeat_provenance"]["status"] == "failed"
    assert result["downbeat_provenance"]["synthetic"] is False


def test_router_cancellation_never_commits_completed_neural_stage(router_fixture):
    router, path, request = router_fixture
    checkpoints = []

    def runner(source, duration):
        raise router._AudioAnalysisInterrupted("fixture cancellation")

    with pytest.raises(router._AudioAnalysisInterrupted):
        router._run_audio_analysis(
            path, 7, request, neural_downbeat_runner=runner,
            on_stage_checkpoint=lambda stage, data: checkpoints.append(stage),
        )
    assert "beats" not in checkpoints
