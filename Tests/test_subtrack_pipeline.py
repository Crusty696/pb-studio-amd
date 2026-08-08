"""Test: Subtracks landen im audio_analysis_cache nach Import + reach Pacing (L-K1)."""
import asyncio

import numpy as np
import pytest


def _make_long_audio(tmp_path, duration_sec=120):
    import soundfile as sf
    audio = tmp_path / "long.wav"
    sf.write(str(audio), np.zeros(22050 * duration_sec, dtype=np.float32), 22050)
    return audio


def test_import_audio_persists_subtracks_to_cache(tmp_path, monkeypatch):
    """Nach import_audio (>60s) MUSS state.audio_analysis_cache subtrack_segments enthalten."""
    from backend.app_state import AppState
    from backend.routers.audio_router import import_audio
    from backend.schemas.audio_schemas import AudioImportRequest

    class FakeResult:
        segments = [(0.0, 60.0, 0.9), (60.0, 120.0, 0.85)]
        tempo_curve = [120.0, 121.0, 119.0]

    class FakeDetector:
        def detect(self, path):
            return FakeResult()

    # Patch the SubtrackDetector at the import-site (audio_router pulls it
    # lazily out of pb_studio.audio.subtrack_detector at call-time).
    monkeypatch.setattr(
        "pb_studio.audio.subtrack_detector.SubtrackDetector",
        lambda: FakeDetector(),
    )

    audio = _make_long_audio(tmp_path, 120)
    state = AppState()
    state.current_project = {
        "db_project_id": 1,
        "path": str(tmp_path),
    }
    request = AudioImportRequest(path=str(audio.absolute()))

    asyncio.run(import_audio(request, state))

    clip_id = list(state.audio_clips.keys())[0]
    cached = state.get_audio_analysis(clip_id)

    assert cached is not None, "audio_analysis_cache NICHT befuellt"
    assert "subtrack_segments" in cached, "subtrack_segments fehlt im Cache"
    assert len(cached["subtrack_segments"]) == 2
    assert "tempo_curve" in cached
    assert cached["tempo_curve"] == [120.0, 121.0, 119.0]
