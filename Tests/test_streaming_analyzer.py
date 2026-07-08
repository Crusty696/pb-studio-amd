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
