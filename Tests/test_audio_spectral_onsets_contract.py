from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest


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
    source = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "routers"
        / "audio_router.py"
    ).read_text(encoding="utf-8")

    assert "analysis_sr = 44100 if request.spectral_analysis else 22050" in source
    assert "analysis.get(\"onset_times\", [])" in source


def test_streaming_temp_transcode_is_removed_on_processing_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import soundfile

    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    source = tmp_path / "source.mp3"
    source.write_bytes(b"source")
    temp_wav = tmp_path / "streaming.wav"
    temp_wav.write_bytes(b"temporary")
    analyzer = StreamingAudioAnalyzer()

    def fake_info(path: str):
        if Path(path) == source:
            raise RuntimeError("unsupported")
        return MagicMock(samplerate=44100)

    monkeypatch.setattr(soundfile, "info", fake_info)
    monkeypatch.setattr(analyzer, "_transcode_to_wav", lambda _path: str(temp_wav))
    monkeypatch.setattr(
        analyzer,
        "_analyze_streaming_prepared",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("processing failed")
        ),
    )

    with pytest.raises(RuntimeError, match="processing failed"):
        analyzer._analyze_streaming(source, 900.0, None)

    assert not temp_wav.exists()


def test_streaming_transcode_failure_does_not_use_offset_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import soundfile

    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    source = tmp_path / "source.mp3"
    source.write_bytes(b"source")
    analyzer = StreamingAudioAnalyzer()
    monkeypatch.setattr(
        soundfile,
        "info",
        lambda _path: (_ for _ in ()).throw(RuntimeError("unsupported")),
    )
    monkeypatch.setattr(analyzer, "_transcode_to_wav", lambda _path: None)
    load_chunk = MagicMock()
    monkeypatch.setattr(analyzer, "_load_chunk", load_chunk)

    with pytest.raises(RuntimeError, match="Offset-Decoding"):
        analyzer._analyze_streaming(source, 900.0, None)

    load_chunk.assert_not_called()
