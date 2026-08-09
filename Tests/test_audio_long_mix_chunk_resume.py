from __future__ import annotations

import copy
import importlib
from pathlib import Path

import numpy as np
import pytest

from pb_studio.audio.streaming_analyzer import (
    StreamingAnalysisResult,
    StreamingAudioAnalyzer,
)


class _StopStreaming(RuntimeError):
    pass


def _configure_fast_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    analyzer: StreamingAudioAnalyzer,
    load_calls: list[float],
) -> None:
    def load_chunk(_path: Path, start: float, _duration: float) -> np.ndarray:
        load_calls.append(float(start))
        return np.full(32, 0.5 + start / 100.0, dtype=np.float32)

    def process_beats(_chunk, start, bpm_est, beat_acc):
        bpm_est.add(120.0 + start)
        beat_acc.add_chunk_beats([start + 1.0])
        return None

    def process_triggers(
        _chunk,
        start,
        onset_acc,
        kick_acc,
        snare_acc,
        hihat_acc,
    ):
        onset_acc.add_chunk_beats([start + 1.1])
        kick_acc.add_chunk_beats([start + 1.2])
        snare_acc.add_chunk_beats([start + 1.3])
        hihat_acc.add_chunk_beats([start + 1.4])
        return None

    def representative(_chunk, start, **_kwargs):
        from pb_studio.audio.spectral_analyzer import FREQUENCY_BANDS

        value = 1.0 + start / 10.0
        band_names = set(FREQUENCY_BANDS) | {"low", "mid", "high"}
        return {
            "times": [start + 0.5],
            "bands": {name: [value] for name in band_names},
            "centroids": [100.0 + start],
            "chroma_mean": [value] * 12,
            "chroma_weight": 2,
        }

    def process_energy(_chunk, is_first, overlap_frames, energy_agg):
        energy_agg.add_chunk_rms(
            np.arange(1.0, 9.0, dtype=np.float64),
            is_first_chunk=is_first,
            overlap_frames=overlap_frames,
        )
        return None

    monkeypatch.setattr(analyzer, "_load_chunk", load_chunk)
    monkeypatch.setattr(analyzer, "_process_beats", process_beats)
    monkeypatch.setattr(analyzer, "_process_triggers", process_triggers)
    monkeypatch.setattr(analyzer, "_extract_representative_features", representative)
    monkeypatch.setattr(analyzer, "_process_energy", process_energy)


def _run_stream(
    analyzer: StreamingAudioAnalyzer,
    source: Path,
    *,
    resume_checkpoint: dict | None = None,
    on_chunk_checkpoint=None,
    checkpoint_guard=None,
):
    return analyzer._analyze_streaming_prepared(
        source,
        duration=30.0,
        on_progress=None,
        energy_only=False,
        native_sr=44100,
        resume_checkpoint=resume_checkpoint,
        on_chunk_checkpoint=on_chunk_checkpoint,
        checkpoint_guard=checkpoint_guard,
        source_identity=analyzer._source_identity(source),
    )


def _interrupted_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[StreamingAudioAnalyzer, Path, dict]:
    source = tmp_path / "long-mix.wav"
    source.write_bytes(b"stable-source-identity")
    analyzer = StreamingAudioAnalyzer(window_sec=10.0, overlap_sec=0.0)
    _configure_fast_pipeline(monkeypatch, analyzer, [])
    snapshots: list[dict] = []

    def checkpoint(snapshot: dict) -> None:
        snapshots.append(copy.deepcopy(snapshot))
        if len(snapshot["chunks"]) == 2:
            raise _StopStreaming("forced interruption")

    with pytest.raises(_StopStreaming, match="forced interruption"):
        _run_stream(analyzer, source, on_chunk_checkpoint=checkpoint)
    return analyzer, source, snapshots[-1]


def test_resume_rehydrates_valid_chunks_and_processes_only_missing_chunk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analyzer, source, checkpoint = _interrupted_checkpoint(monkeypatch, tmp_path)
    resumed_loads: list[float] = []
    _configure_fast_pipeline(monkeypatch, analyzer, resumed_loads)
    persisted: list[dict] = []

    result = _run_stream(
        analyzer,
        source,
        resume_checkpoint=checkpoint,
        on_chunk_checkpoint=lambda value: persisted.append(copy.deepcopy(value)),
    )

    assert resumed_loads == [20.0]
    assert [row.get("reused_from_checkpoint", False) for row in result.chunk_evidence] == [
        True,
        True,
        False,
    ]
    assert result.beats == [1.0, 11.0, 21.0]
    assert result.onset_times == [1.1, 11.1, 21.1]
    assert result.spectral_times == [0.5, 10.5, 20.5]
    assert len(result.energy_curve) == 6
    assert len(result.resume_checkpoint["chunks"]) == 3
    assert len(persisted) == 1
    assert len(persisted[0]["chunks"]) == 3


def test_invalid_checkpoint_payload_recomputes_only_that_and_missing_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analyzer, source, checkpoint = _interrupted_checkpoint(monkeypatch, tmp_path)
    checkpoint["chunks"][0]["payload"]["energy_frames"] = []
    resumed_loads: list[float] = []
    _configure_fast_pipeline(monkeypatch, analyzer, resumed_loads)

    result = _run_stream(analyzer, source, resume_checkpoint=checkpoint)

    assert resumed_loads == [0.0, 20.0]
    assert result.chunk_evidence[0].get("reused_from_checkpoint") is None
    assert result.chunk_evidence[1]["reused_from_checkpoint"] is True


@pytest.mark.parametrize(
    "corruption",
    ["energy_max", "feature_time", "band_schema"],
)
def test_semantically_invalid_checkpoint_payload_is_recomputed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    corruption: str,
) -> None:
    analyzer, source, checkpoint = _interrupted_checkpoint(monkeypatch, tmp_path)
    payload = checkpoint["chunks"][0]["payload"]
    if corruption == "energy_max":
        payload["energy_max"] = max(payload["energy_frames"]) - 0.5
    elif corruption == "feature_time":
        payload["features"]["times"] = [20.0]
    else:
        payload["features"]["bands"].pop(
            next(iter(payload["features"]["bands"]))
        )
    resumed_loads: list[float] = []
    _configure_fast_pipeline(monkeypatch, analyzer, resumed_loads)

    result = _run_stream(analyzer, source, resume_checkpoint=checkpoint)

    assert resumed_loads == [0.0, 20.0]
    assert result.chunk_evidence[0].get("reused_from_checkpoint") is None
    assert result.chunk_evidence[1]["reused_from_checkpoint"] is True


def test_changed_source_identity_invalidates_all_cached_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    analyzer, source, checkpoint = _interrupted_checkpoint(monkeypatch, tmp_path)
    source.write_bytes(b"changed-source-identity")
    resumed_loads: list[float] = []
    _configure_fast_pipeline(monkeypatch, analyzer, resumed_loads)

    result = _run_stream(analyzer, source, resume_checkpoint=checkpoint)

    assert resumed_loads == [0.0, 10.0, 20.0]
    assert not any(
        row.get("reused_from_checkpoint", False)
        for row in result.chunk_evidence
    )


def test_checkpoint_guard_stops_before_late_chunk_and_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "guarded-mix.wav"
    source.write_bytes(b"guarded-source")
    analyzer = StreamingAudioAnalyzer(window_sec=10.0, overlap_sec=0.0)
    load_calls: list[float] = []
    _configure_fast_pipeline(monkeypatch, analyzer, load_calls)
    committed: list[dict] = []

    def guard() -> None:
        if committed:
            raise _StopStreaming("context changed")

    with pytest.raises(_StopStreaming, match="context changed"):
        _run_stream(
            analyzer,
            source,
            checkpoint_guard=guard,
            on_chunk_checkpoint=lambda value: committed.append(value),
        )

    assert load_calls == [0.0]
    assert len(committed) == 1
    assert len(committed[0]["chunks"]) == 1


def test_router_checkpoint_merge_preserves_sibling_pass_and_private_payload() -> None:
    from backend.routers.audio_router import (
        _audio_stream_resume_checkpoints,
        _merge_audio_chunk_checkpoint_evidence,
    )

    primary = {
        "schema_version": 2,
        "window_count": 1,
        "chunks": [{"chunk_index": 0, "payload": {"energy_frames": [0.5]}}],
    }
    existing = {
        "schema_version": 2,
        "audit_marker": "keep",
        "mix_energy": {
            "source_role": "original_mix_energy",
            "checkpoint": {"schema_version": 2, "chunks": []},
        },
    }

    merged = _merge_audio_chunk_checkpoint_evidence(
        cached=existing,
        pass_name="primary",
        source_role="beat_source",
        checkpoint=primary,
    )

    assert merged["audit_marker"] == "keep"
    assert merged["mix_energy"] == existing["mix_energy"]
    assert "payload" not in merged["primary"]["chunks"][0]
    assert merged["primary"]["checkpoint"]["chunks"][0]["payload"] == {
        "energy_frames": [0.5]
    }
    assert _audio_stream_resume_checkpoints(
        {"_chunk_evidence": merged}
    )["primary"] == primary


def test_mix_energy_failure_preserves_checkpoint_and_marks_beats_partial(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio_router = importlib.import_module("backend.routers.audio_router")
    source = tmp_path / "long-mix.wav"
    drums = tmp_path / "drums.wav"
    source.write_bytes(b"source")
    drums.write_bytes(b"drums")
    mix_checkpoint = {
        "schema_version": 2,
        "source": {"path": str(source), "size": 6, "mtime_ns": 1},
        "config": {},
        "duration_seconds": 601.0,
        "window_count": 1,
        "chunks": [
            {
                "chunk_index": 0,
                "status": "completed",
                "payload": {"energy_frames": [0.5]},
            }
        ],
    }
    primary = StreamingAnalysisResult(
        duration_seconds=601.0,
        bpm=128.0,
        beats=[1.0],
        energy_curve=[0.4],
        onset_times=[1.1],
        kick_times=[1.2],
        snare_times=[1.3],
        hihat_times=[1.4],
        chunk_evidence=[],
        resume_checkpoint={
            "schema_version": 2,
            "window_count": 0,
            "chunks": [],
        },
        window_count=0,
    )
    calls = 0

    def analyze(_self, _path, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return primary
        kwargs["on_chunk_checkpoint"](copy.deepcopy(mix_checkpoint))
        raise RuntimeError("mix energy interrupted")

    monkeypatch.setattr("librosa.get_duration", lambda **_kwargs: 601.0)
    monkeypatch.setattr(
        "librosa.load",
        lambda *_args, **_kwargs: (np.ones(32, dtype=np.float32), 22050),
    )
    monkeypatch.setattr(StreamingAudioAnalyzer, "analyze", analyze)
    monkeypatch.setattr(
        "pb_studio.audio.beat_detector.BeatDetector.compute_beat_strengths",
        lambda *_args, **_kwargs: [1.0],
    )

    result = audio_router._run_audio_analysis(
        str(source),
        7,
        AudioAnalyzeRequest(
            clip_id=7,
            detect_beats=True,
            detect_structure=False,
            spectral_analysis=False,
            detect_key=False,
        ),
        {"drums": str(drums)},
        on_stage_checkpoint=lambda *_args: None,
    )

    assert result["_analysis_status"] == "partial"
    assert result["_stage_status"]["beats"] == "partial"
    assert "mix energy interrupted" in result["_stage_errors"]["beats"]
    assert result["_chunk_evidence"]["mix_energy"]["checkpoint"] == mix_checkpoint
    assert audio_router._audio_stream_resume_checkpoints(result)["mix_energy"] == mix_checkpoint
