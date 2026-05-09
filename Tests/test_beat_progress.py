"""Test: BeatDetector.detect_beats ruft on_progress (Audit C3)."""
from pathlib import Path

import pytest


def _find_audio_fixture() -> str | None:
    """Sucht ein Audio-Fixture im Repo (Tests/fixtures/* oder src/.../assets)."""
    candidates = [
        Path("Tests/fixtures/test_audio.wav"),
        Path("Tests/fixtures/test_audio.mp3"),
        Path("Tests/fixtures/sample.wav"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Generisch: irgendeine .wav unter Tests/fixtures
    fixtures_dir = Path("Tests/fixtures")
    if fixtures_dir.exists():
        for ext in ("*.wav", "*.mp3", "*.flac"):
            for p in fixtures_dir.glob(ext):
                return str(p)
    return None


def _make_synthetic_wav(tmp_path: Path) -> str:
    """Erzeugt eine kurze synthetische WAV-Datei (ohne externe Deps)."""
    import wave
    import struct
    import math

    path = tmp_path / "synthetic_120bpm.wav"
    sr = 22050
    duration_s = 4.0  # kurz halten für CI-Speed
    n_frames = int(sr * duration_s)
    # 120 BPM -> 2 Hz Beat-Klick. Sinus-Trägerfrequenz 440 Hz, AM mit 2 Hz.
    samples = []
    for i in range(n_frames):
        t = i / sr
        carrier = math.sin(2 * math.pi * 440.0 * t)
        envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 2.0 * t)
        s = int(0.4 * 32767 * carrier * envelope)
        samples.append(struct.pack("<h", s))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        wf.writeframes(b"".join(samples))
    return str(path)


def test_beat_detector_calls_on_progress(tmp_path):
    """detect_beats ruft on_progress mind. mit 0 + 100 auf, alles in [0..100]."""
    from pb_studio.audio.beat_detector import BeatDetector

    audio_path = _find_audio_fixture() or _make_synthetic_wav(tmp_path)

    progress_calls: list[float] = []
    detector = BeatDetector(mode="offline", inference_model="DBN")

    try:
        detector.detect_beats(
            audio_path,
            on_progress=lambda pct: progress_calls.append(pct),
        )
    except Exception:
        # Downstream-Errors (z.B. fehlendes Modell) OK — solange on_progress
        # vorher schon mind. 0% emittiert hat.
        pass

    assert len(progress_calls) >= 2, (
        f"Erwartet >=2 Progress-Calls, bekam {len(progress_calls)}: {progress_calls}"
    )
    assert all(0.0 <= p <= 100.0 for p in progress_calls), (
        f"Progress-Werte ausserhalb [0..100]: {progress_calls}"
    )
    # Sanity: erster Call sollte 0.0 sein, letzter sollte 100.0 sein
    assert progress_calls[0] == 0.0, f"Erster Call sollte 0.0 sein, war {progress_calls[0]}"
    assert progress_calls[-1] == 100.0, f"Letzter Call sollte 100.0 sein, war {progress_calls[-1]}"


def test_beat_detector_works_without_callback(tmp_path):
    """Default on_progress=None — kein TypeError, alter API-Vertrag bleibt."""
    from pb_studio.audio.beat_detector import BeatDetector

    audio_path = _find_audio_fixture() or _make_synthetic_wav(tmp_path)

    detector = BeatDetector(mode="offline", inference_model="DBN")
    try:
        detector.detect_beats(audio_path)  # KEIN on_progress
    except Exception as e:
        # Downstream-Errors OK — wichtig: kein TypeError "on_progress not callable"
        assert "on_progress" not in str(e), (
            f"Aufrufer ohne on_progress sollte keinen on_progress-Error werfen: {e}"
        )


def test_beat_detector_swallows_callback_exceptions(tmp_path):
    """Wenn on_progress wirft, soll detect_beats trotzdem durchlaufen."""
    from pb_studio.audio.beat_detector import BeatDetector

    audio_path = _find_audio_fixture() or _make_synthetic_wav(tmp_path)

    def raising(_pct: float) -> None:
        raise RuntimeError("simulated callback failure")

    detector = BeatDetector(mode="offline", inference_model="DBN")
    # Darf KEIN RuntimeError aus dem Callback nach aussen lassen.
    try:
        detector.detect_beats(audio_path, on_progress=raising)
    except RuntimeError as e:
        if "simulated callback failure" in str(e):
            pytest.fail(f"detect_beats hat Callback-Exception nicht geschluckt: {e}")
        # Andere RuntimeErrors (z.B. fehlendes Modell) sind OK.
