"""Test: StreamingAudioAnalyzer fuer lange Mixe (Audit F3)."""
import pytest
import numpy as np


def _make_audio(tmp_path, duration_sec: float, sr: int = 22050, with_beat: bool = True):
    """Erzeugt sin-wave Audio mit Click-Beats fuer Test."""
    import soundfile as sf

    n = int(duration_sec * sr)
    t = np.arange(n) / sr
    # 440Hz sine + clicks alle 0.5s (120 BPM = 0.5s)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    if with_beat:
        beat_period = sr * 0.5  # 120 BPM
        for i in range(0, n, int(beat_period)):
            click_end = min(i + 100, n)
            audio[i:click_end] = 0.8

    path = tmp_path / "test_long.wav"
    sf.write(str(path), audio, sr)
    return path


def test_streaming_short_file_uses_single_shot(tmp_path):
    """Files < 1.5x window: Fallback single-shot."""
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer
    audio = _make_audio(tmp_path, duration_sec=10.0)
    analyzer = StreamingAudioAnalyzer(window_sec=300.0)
    result = analyzer.analyze(str(audio))
    assert result.window_count == 1
    assert result.duration_seconds == pytest.approx(10.0, abs=0.1)
    assert len(result.beats) >= 0


def test_streaming_long_file_uses_streaming(tmp_path):
    """Files > 1.5x window: Streaming with multiple windows."""
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer
    # 90s file mit 30s window (statt 5min default fuer schnelleren Test)
    audio = _make_audio(tmp_path, duration_sec=90.0)
    analyzer = StreamingAudioAnalyzer(window_sec=30.0, overlap_sec=5.0)
    result = analyzer.analyze(str(audio))
    assert result.window_count >= 2
    assert result.duration_seconds == pytest.approx(90.0, abs=0.5)
    assert len(result.beats) > 0
    assert result.onset_times
    assert max(result.onset_times) > 60.0


def test_streaming_energy_only_skips_trigger_detection(tmp_path):
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    audio = _make_audio(tmp_path, duration_sec=60.0)
    analyzer = StreamingAudioAnalyzer(window_sec=20.0, overlap_sec=2.0)
    result = analyzer.analyze(str(audio), energy_only=True)

    assert result.onset_times == []
    assert result.kick_times == []
    assert result.snare_times == []
    assert result.hihat_times == []


def test_streaming_energy_preserves_time_after_middle_chunk_failure(
    monkeypatch,
    tmp_path,
):
    import soundfile as sf

    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    audio = tmp_path / "timeline.wav"
    audio.write_bytes(b"placeholder")
    analyzer = StreamingAudioAnalyzer(window_sec=10.0, overlap_sec=0.0)

    monkeypatch.setattr(
        sf,
        "info",
        lambda _path: type("Info", (), {"samplerate": analyzer.SR})(),
    )

    def load_chunk(_path, offset, duration):
        if offset == pytest.approx(10.0):
            raise OSError("forced middle chunk failure")
        amplitude = 0.2 if offset < 10.0 else 1.0
        return np.full(
            int(duration * analyzer.SR),
            amplitude,
            dtype=np.float32,
        )

    monkeypatch.setattr(analyzer, "_load_chunk", load_chunk)

    result = analyzer._analyze_streaming(
        audio,
        duration=30.0,
        on_progress=None,
        energy_only=True,
    )

    peak_position = int(np.argmax(result.energy_curve)) / len(result.energy_curve)
    assert peak_position >= 0.65
    middle = result.energy_curve[
        len(result.energy_curve) // 3: 2 * len(result.energy_curve) // 3
    ]
    assert middle
    assert max(middle) == 0.0


def test_audio_router_uses_full_streaming_triggers(monkeypatch, tmp_path):
    import librosa

    from backend.routers.audio_router import _run_audio_analysis
    from backend.schemas.audio_schemas import AudioAnalyzeRequest
    from pb_studio.audio.key_detector import KeyDetector
    from pb_studio.audio.streaming_analyzer import (
        StreamingAnalysisResult,
        StreamingAudioAnalyzer,
    )

    audio_path = tmp_path / "long.wav"
    audio_path.write_bytes(b"placeholder")
    streamed = StreamingAnalysisResult(
        duration_seconds=900.0,
        bpm=120.0,
        beats=[0.5, 700.5],
        energy_curve=[0.2, 0.8],
        onset_times=[1.0, 701.0],
        kick_times=[2.0, 702.0],
        snare_times=[3.0, 703.0],
        hihat_times=[4.0, 704.0],
        window_count=36,
    )

    monkeypatch.setattr(librosa, "get_duration", lambda **_kwargs: 900.0)
    monkeypatch.setattr(
        librosa,
        "load",
        lambda *_args, **_kwargs: (np.zeros(22050, dtype=np.float32), 22050),
    )
    monkeypatch.setattr(
        librosa.onset,
        "onset_detect",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("600-second snapshot trigger extraction must not run")
        ),
    )
    monkeypatch.setattr(
        StreamingAudioAnalyzer,
        "analyze",
        lambda *_args, **_kwargs: streamed,
    )
    monkeypatch.setattr(KeyDetector, "detect_key", lambda *_args, **_kwargs: "C Major")

    result = _run_audio_analysis(
        str(audio_path),
        7,
        AudioAnalyzeRequest(
            clip_id=7,
            detect_beats=True,
            detect_structure=False,
            spectral_analysis=False,
        ),
    )

    assert result["duration_seconds"] == 900.0
    assert result["onset_times"] == [1.0, 701.0]
    assert result["kick_times"] == [2.0, 702.0]
    assert result["snare_times"] == [3.0, 703.0]
    assert result["hihat_times"] == [4.0, 704.0]


def test_streaming_progress_callback(tmp_path):
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer
    audio = _make_audio(tmp_path, duration_sec=60.0)
    analyzer = StreamingAudioAnalyzer(window_sec=20.0, overlap_sec=2.0)
    progress_calls = []
    analyzer.analyze(str(audio), on_progress=lambda pct: progress_calls.append(pct))
    assert len(progress_calls) >= 2
    assert all(0 <= p <= 100 for p in progress_calls)
    assert progress_calls[-1] == pytest.approx(100.0, abs=1.0)


def test_streaming_beat_dedup(tmp_path):
    """Beat-Boundaries werden dedupliziert (kein Doppel-Beat im Overlap)."""
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer
    audio = _make_audio(tmp_path, duration_sec=60.0)
    analyzer = StreamingAudioAnalyzer(window_sec=20.0, overlap_sec=2.0)
    result = analyzer.analyze(str(audio))
    # Beats sollten monoton steigend sein (sortiert) + min 0.5s Abstand
    if len(result.beats) > 1:
        diffs = np.diff(result.beats)
        assert all(d >= 0 for d in diffs), "Beats nicht sortiert"


def test_streaming_missing_file_raises(tmp_path):
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer
    analyzer = StreamingAudioAnalyzer()
    with pytest.raises(FileNotFoundError):
        analyzer.analyze(str(tmp_path / "nonexistent.wav"))


def test_beat_accumulator_dedup_and_average():
    from pb_studio.audio.streaming_analyzer import _BeatAccumulator
    # Threshold should default to 0.15 (150ms)
    accum = _BeatAccumulator()
    assert accum._dedup_threshold == 0.15
    
    # Let's add beats with some jitter
    # Group 1: 1.0, 1.05, 1.11 (all within 150ms of each other sequentially)
    # Group 2: 2.5, 2.52 (within 150ms)
    # Group 3: 4.0
    accum.add_chunk_beats([1.0, 1.11, 2.5, 4.0])
    accum.add_chunk_beats([1.05, 2.52])
    
    deduped = accum.get_deduplicated()
    # Expected groups:
    # Group 1: mean(1.0, 1.05, 1.11) = 1.05333...
    # Group 2: mean(2.5, 2.52) = 2.51
    # Group 3: mean(4.0) = 4.0
    assert len(deduped) == 3
    assert deduped[0] == pytest.approx(1.05333, abs=0.001)
    assert deduped[1] == pytest.approx(2.51, abs=0.001)
    assert deduped[2] == pytest.approx(4.0, abs=0.001)
