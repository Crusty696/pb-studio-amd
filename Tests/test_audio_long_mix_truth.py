from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def stem_model_dir(monkeypatch, tmp_path):
    from pb_studio.config_manager import ConfigManager

    model_path = tmp_path / "UVR-MDX-NET-Inst_HQ_3.onnx"
    model_path.write_bytes(b"model")
    monkeypatch.setattr(ConfigManager, "resolve_path", lambda self, _path: tmp_path)
    return tmp_path


def test_long_mix_stem_timeout_scales_beyond_fixed_floor():
    from backend.routers.audio_router import _stem_timeout_for_duration

    assert _stem_timeout_for_duration(600.0, 900.0) == 900.0
    assert _stem_timeout_for_duration(6335.0, 900.0) == pytest.approx(4751.25)


def test_reusable_stems_require_complete_matching_outputs(tmp_path, stem_model_dir):
    import soundfile as sf

    from backend.routers.audio_router import (
        _find_reusable_stem_files,
        _write_stem_cache_marker,
    )

    source = tmp_path / "long_mix.wav"
    samples = np.zeros(44100, dtype=np.float32)
    sf.write(source, samples, 44100)
    vocals = tmp_path / "long_mix_(Vocals)_UVR-MDX-NET-Inst_HQ_3.wav"
    instrumental = tmp_path / "long_mix_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav"
    sf.write(vocals, samples, 44100)

    assert _find_reusable_stem_files(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
    ) == []

    sf.write(instrumental, samples, 44100)
    assert _find_reusable_stem_files(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
    ) == []
    _write_stem_cache_marker(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
        [str(vocals), str(instrumental)],
    )
    reusable = _find_reusable_stem_files(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
    )
    assert reusable == sorted([str(instrumental.resolve()), str(vocals.resolve())])


def test_reusable_stems_are_bound_to_exact_source_identity(tmp_path, stem_model_dir):
    import soundfile as sf

    from backend.routers.audio_router import (
        _find_reusable_stem_files,
        _write_stem_cache_marker,
    )

    source_a = tmp_path / "a" / "same.wav"
    source_b = tmp_path / "b" / "same.wav"
    source_a.parent.mkdir()
    source_b.parent.mkdir()
    samples = np.zeros(44100, dtype=np.float32)
    sf.write(source_a, samples, 44100)
    sf.write(source_b, samples, 44100)
    vocals = tmp_path / "same_(Vocals)_UVR-MDX-NET-Inst_HQ_3.wav"
    instrumental = tmp_path / "same_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav"
    sf.write(vocals, samples, 44100)
    sf.write(instrumental, samples, 44100)
    _write_stem_cache_marker(
        str(source_a),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
        [str(vocals), str(instrumental)],
    )

    assert _find_reusable_stem_files(
        str(source_b),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
    ) == []


def test_reusable_stem_role_parsing_rejects_multi_role_filename(tmp_path):
    import soundfile as sf

    from backend.routers.audio_router import _write_stem_cache_marker

    source = tmp_path / "mix.wav"
    model_path = tmp_path / "UVR-MDX-NET-Inst_HQ_3.onnx"
    model_path.write_bytes(b"model")
    samples = np.zeros(44100, dtype=np.float32)
    sf.write(source, samples, 44100)
    ambiguous = tmp_path / "mix_(Vocals)_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav"
    sf.write(ambiguous, samples, 44100)

    with pytest.raises(ValueError, match="Rolle"):
        _write_stem_cache_marker(
            str(source),
            "UVR-MDX-NET-Inst_HQ_3.onnx",
            tmp_path,
            [str(ambiguous)],
        )


def test_reusable_stems_reject_output_truncated_after_success(tmp_path, stem_model_dir):
    import soundfile as sf

    from backend.routers.audio_router import (
        _find_reusable_stem_files,
        _write_stem_cache_marker,
    )

    source = tmp_path / "mix.wav"
    samples = np.zeros(44100, dtype=np.float32)
    sf.write(source, samples, 44100)
    vocals = tmp_path / "mix_(Vocals)_UVR-MDX-NET-Inst_HQ_3.wav"
    instrumental = tmp_path / "mix_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav"
    sf.write(vocals, samples, 44100)
    sf.write(instrumental, samples, 44100)
    _write_stem_cache_marker(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
        [str(vocals), str(instrumental)],
    )

    sf.write(instrumental, samples[:22050], 44100)

    assert _find_reusable_stem_files(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        tmp_path,
    ) == []


def test_stem_cache_marker_rejects_truncated_success_output(tmp_path):
    import soundfile as sf

    from backend.routers.audio_router import _write_stem_cache_marker

    source = tmp_path / "mix.wav"
    full_samples = np.zeros(44100 * 2, dtype=np.float32)
    short_samples = full_samples[: int(44100 * 1.5)]
    sf.write(source, full_samples, 44100)
    vocals = tmp_path / "mix_(Vocals)_UVR-MDX-NET-Inst_HQ_3.wav"
    instrumental = tmp_path / "mix_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav"
    sf.write(vocals, full_samples, 44100)
    sf.write(instrumental, short_samples, 44100)

    with pytest.raises(ValueError, match="unvollstaendig"):
        _write_stem_cache_marker(
            str(source),
            "UVR-MDX-NET-Inst_HQ_3.onnx",
            tmp_path,
            [str(vocals), str(instrumental)],
        )


def test_successful_stem_run_publishes_marker_and_reuses_outputs(
    monkeypatch,
    tmp_path,
):
    from pathlib import Path

    import soundfile as sf

    import pb_studio.audio.separator as separator_module
    import pb_studio.config_manager as config_module
    from backend.routers.audio_router import _run_stem_separation

    source = tmp_path / "mix.wav"
    model_path = tmp_path / "UVR-MDX-NET-Inst_HQ_3.onnx"
    model_path.write_bytes(b"model")
    samples = np.zeros(44100, dtype=np.float32)
    sf.write(source, samples, 44100)
    separator_calls = []

    class FakeConfigManager:
        def get(self, *_args):
            return {"temp_dir": str(tmp_path), "models_dir": str(tmp_path)}

        def resolve_path(self, _path):
            return tmp_path

    class FakeSeparator:
        def separate(self, *_args, **_kwargs):
            separator_calls.append(True)
            output_dir = Path(_kwargs["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            vocals = output_dir / "mix_(Vocals)_UVR-MDX-NET-Inst_HQ_3.wav"
            instrumental = output_dir / "mix_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav"
            sf.write(vocals, samples, 44100)
            sf.write(instrumental, samples, 44100)
            return {"stems": [str(vocals), str(instrumental)]}

    monkeypatch.setattr(config_module, "ConfigManager", FakeConfigManager)
    monkeypatch.setattr(separator_module, "StemSeparator", FakeSeparator)

    first = _run_stem_separation(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
    )
    second = _run_stem_separation(
        str(source),
        "UVR-MDX-NET-Inst_HQ_3.onnx",
    )

    assert separator_calls == [True]
    assert first["vocals_path"] == second["vocals_path"]
    assert first["instrumental_path"] == second["instrumental_path"]
    assert Path(first["vocals_path"]).parent.parent == tmp_path / "stem-runs"


def test_long_mix_subtrack_detection_never_full_loads(monkeypatch, tmp_path):
    import librosa

    from pb_studio.audio.subtrack_detector import SubtrackDetector

    audio = tmp_path / "long.wav"
    audio.write_bytes(b"placeholder")
    load_durations: list[float | None] = []

    monkeypatch.setattr(librosa, "get_duration", lambda **_kwargs: 1200.0)

    def bounded_load(*_args, **kwargs):
        load_durations.append(kwargs.get("duration"))
        duration = float(kwargs["duration"])
        return np.zeros(int(duration * 100), dtype=np.float32), 100

    monkeypatch.setattr(librosa, "load", bounded_load)
    detector = SubtrackDetector(sr=100)
    def bounded_features(_path, duration, _stems):
        offset = 0.0
        while offset < duration:
            chunk_duration = min(detector.LONG_MIX_CHUNK_SEC, duration - offset)
            librosa.load(
                str(audio),
                sr=detector.sr,
                mono=True,
                offset=offset,
                duration=chunk_duration,
            )
            offset += chunk_duration
        return (
            np.ones((12, 8), dtype=np.float32),
            np.zeros(8, dtype=np.float32),
            np.zeros(8, dtype=np.float32),
            np.full(8, 120.0, dtype=np.float32),
        )

    monkeypatch.setattr(detector, "_bounded_chunk_features", bounded_features)

    result = detector.detect(audio)

    assert result.segments[-1][1] == pytest.approx(1200.0)
    assert load_durations
    assert all(value is not None for value in load_durations)
    assert max(load_durations) <= detector.LONG_MIX_CHUNK_SEC


def test_duration_probe_failure_does_not_full_load(monkeypatch, tmp_path):
    import librosa

    from backend.routers.audio_router import _run_audio_analysis
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio = tmp_path / "unknown-duration.wav"
    audio.write_bytes(b"placeholder")
    monkeypatch.setattr(
        librosa,
        "get_duration",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("probe failed")),
    )
    monkeypatch.setattr(
        librosa,
        "load",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("full-load fallback must not run")
        ),
    )

    with pytest.raises(RuntimeError, match="Dauer"):
        _run_audio_analysis(
            str(audio),
            1,
            AudioAnalyzeRequest(clip_id=1),
        )


def test_long_mix_uses_full_duration_streaming_representations(
    monkeypatch,
    tmp_path,
):
    import librosa

    from backend.routers.audio_router import _run_audio_analysis
    from backend.schemas.audio_schemas import AudioAnalyzeRequest
    from pb_studio.audio.streaming_analyzer import (
        StreamingAnalysisResult,
        StreamingAudioAnalyzer,
    )

    audio = tmp_path / "long.wav"
    audio.write_bytes(b"placeholder")
    streamed = StreamingAnalysisResult(
        duration_seconds=1200.0,
        bpm=120.0,
        beats=[1.0, 1190.0],
        energy_curve=[0.1, 0.2, 0.8],
        chroma_mean=[1.0] + [0.0] * 11,
        spectral_times=[0.0, 600.0, 1199.0],
        spectral_bands={"bass": [0.1, 0.5, 0.9]},
        spectral_centroids=[100.0, 500.0, 900.0],
        window_count=48,
    )

    monkeypatch.setattr(librosa, "get_duration", lambda **_kwargs: 1200.0)
    monkeypatch.setattr(
        librosa,
        "load",
        lambda *_args, **_kwargs: (np.zeros(22050, dtype=np.float32), 22050),
    )
    monkeypatch.setattr(
        StreamingAudioAnalyzer,
        "analyze",
        lambda *_args, **_kwargs: streamed,
    )

    result = _run_audio_analysis(
        str(audio),
        3,
        AudioAnalyzeRequest(
            clip_id=3,
            detect_beats=False,
            detect_structure=True,
            spectral_analysis=True,
        ),
    )

    assert result["structure_segments"][-1]["end_time"] == pytest.approx(1200.0)
    assert result["spectral_data"]["times"][-1] == pytest.approx(1199.0)
    assert result["key"] == "C major"


def test_stage_failure_marks_analysis_partial(monkeypatch, tmp_path):
    import librosa

    from backend.routers.audio_router import _run_audio_analysis
    from backend.schemas.audio_schemas import AudioAnalyzeRequest
    from pb_studio.audio.key_detector import KeyDetector
    from pb_studio.audio.structure_analyzer import StructureAnalyzer

    audio = tmp_path / "short.wav"
    audio.write_bytes(b"placeholder")
    monkeypatch.setattr(librosa, "get_duration", lambda **_kwargs: 30.0)
    monkeypatch.setattr(
        librosa,
        "load",
        lambda *_args, **_kwargs: (np.ones(22050, dtype=np.float32), 22050),
    )
    monkeypatch.setattr(
        StructureAnalyzer,
        "analyze_song_structure",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("structure broke")
        ),
    )
    monkeypatch.setattr(KeyDetector, "detect_key", lambda *_args: "C major")

    result = _run_audio_analysis(
        str(audio),
        4,
        AudioAnalyzeRequest(
            clip_id=4,
            detect_beats=False,
            detect_structure=True,
            spectral_analysis=False,
        ),
    )

    assert result["_analysis_status"] == "partial"
    assert result["_stage_status"]["structure"] == "failed"
    assert "structure broke" in result["_stage_errors"]["structure"]


def test_partial_result_never_publishes_completed(monkeypatch, tmp_path):
    import asyncio

    import importlib

    from backend.app_state import AppState
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio_router = importlib.import_module("backend.routers.audio_router")

    audio = tmp_path / "partial.wav"
    audio.write_bytes(b"audio")
    state = AppState()
    state.current_project = {"db_project_id": 1, "path": str(tmp_path)}
    clip = state.register_audio_clip(
        {
            "name": "partial",
            "path": str(audio),
            "duration_seconds": 30.0,
            "sample_rate": 22050,
            "channels": 1,
            "format": "wav",
            "is_analyzed": False,
        }
    )
    events = []

    async def capture_event(name, payload):
        events.append((name, payload))

    result = {
        "clip_id": clip["id"],
        "duration_seconds": 30.0,
        "bpm": 120.0,
        "beat_count": 1,
        "beats": [{"time": 1.0, "strength": 1.0, "beat_type": "beat"}],
        "key": None,
        "energy_curve": [0.5],
        "structure_segments": [],
        "spectral_data": None,
        "_analysis_status": "partial",
        "_stage_status": {"beats": "completed", "key": "failed"},
        "_stage_errors": {"key": "forced key failure"},
    }
    monkeypatch.setattr(
        audio_router,
        "_run_audio_analysis",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(audio_router, "publish_event", capture_event)
    monkeypatch.setattr(
        audio_router,
        "publish_log",
        lambda *_args, **_kwargs: asyncio.sleep(0),
    )

    response = asyncio.run(
        audio_router.analyze_audio(
            AudioAnalyzeRequest(clip_id=clip["id"]),
            state,
        )
    )

    assert response.bpm == 120.0
    final_event = [
        payload
        for name, payload in events
        if name == "analysis_progress" and payload.get("percent") == 100
    ][-1]
    assert final_event["status"] == "partial"
    assert final_event["stage_status"]["key"] == "failed"
    assert state.get_audio_clip(clip["id"])["is_analyzed"] is False
