from __future__ import annotations

import asyncio
from unittest.mock import MagicMock


def test_onsets_endpoint_returns_persisted_candidates() -> None:
    from backend.routers.audio_router import get_onsets

    state = MagicMock()
    state.get_audio_analysis.return_value = {
        "onset_times": [0.125, 4.5, 99.75],
        "energy_curve": [0.0, 1.0, 0.0],
    }

    result = asyncio.run(get_onsets(7, state))

    assert result == [0.125, 4.5, 99.75]


def test_streaming_spectral_path_uses_44k1() -> None:
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    assert StreamingAudioAnalyzer.SR == 44100


def test_router_selects_44k1_when_spectral_analysis_is_requested() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "routers"
        / "audio_router.py"
    ).read_text(encoding="utf-8")

    assert "analysis_sr = 44100 if request.spectral_analysis else 22050" in source
    assert "analysis.get(\"onset_times\", [])" in source

