"""Regressionstests fuer H-4, M-1 und C-3 im Audio-Router.

H-4: Eine Beat-Erkennung, die nichts geliefert hat, darf nicht als
     abgeschlossene Stufe persistiert werden.
M-1: Der ausgelieferte `bpm` hat EINE Definition und benennt sie.
C-3: Das Beat-Raster wird auf Plausibilitaet geprueft — gemeldet, nicht
     erzwungen.

Gegenprobe-Protokoll siehe Modul-Ende.
"""

from __future__ import annotations

import importlib
import math
import wave
from pathlib import Path

import numpy as np
import pytest

from backend.routers.audio_router import (
    _audio_stage_result_is_valid,
    _evaluate_beat_grid,
    _plan_audio_analysis,
    _run_audio_analysis,
)
from backend.schemas.audio_schemas import AudioAnalyzeRequest

# backend/routers/__init__.py bindet den NAMEN `audio_router` an den APIRouter,
# nicht an das Modul — `import backend.routers.audio_router as x` liefert daher
# den Router. Deshalb ueber importlib.
router_module = importlib.import_module("backend.routers.audio_router")

SR = 22050
CLICK_PERIOD = 0.5  # Sekunden -> 120 BPM
DURATION = 8.0


@pytest.fixture(scope="module")
def click_track(tmp_path_factory) -> str:
    """Kurzer synthetischer Klick-Track, 120 BPM, echtes WAV auf Platte."""
    path = tmp_path_factory.mktemp("beatgrid") / "clicks.wav"
    n = int(SR * DURATION)
    y = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(1234)
    burst = int(SR * 0.01)
    for k in range(int(DURATION / CLICK_PERIOD)):
        start = int(k * CLICK_PERIOD * SR)
        env = np.exp(-np.linspace(0.0, 6.0, burst))
        y[start:start + burst] += env * rng.uniform(-1.0, 1.0, burst)
    y = np.clip(y, -1.0, 1.0)
    pcm = (y * 32000).astype("<i2")
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(pcm.tobytes())
    return str(path)


class _StubDetector:
    """Ersetzt BeatDetector; liefert genau das Raster, das der Test vorgibt."""

    def __init__(self, beats: list[float], downbeats: list[float] | None = None):
        self._beats = beats
        self._downbeats = downbeats or []

    def detect_beats_with_downbeats(self, path, on_progress=None):
        return list(self._beats), list(self._downbeats)


class _StubStreamResult:
    def __init__(self, beats: list[float], bpm: float, duration: float):
        self.beats = beats
        self.bpm = bpm
        self.duration_seconds = duration
        self.energy_curve = [0.5, 0.6]
        self.onset_times = list(beats)
        self.kick_times = list(beats)
        self.snare_times = []
        self.hihat_times = []
        self.stage_errors = {}
        self.window_count = 2
        self.chunk_evidence = []
        self.resume_checkpoint = {}


def _beats_only_request(clip_id: int = 1) -> AudioAnalyzeRequest:
    return AudioAnalyzeRequest(
        clip_id=clip_id,
        detect_beats=True,
        detect_structure=False,
        spectral_analysis=False,
        detect_key=False,
    )


# --------------------------------------------------------------------------
# H-4 (a): leeres Raster darf nicht "completed" werden
# --------------------------------------------------------------------------


def test_empty_beat_result_marks_stage_failed(monkeypatch, click_track):
    """librosa-Fallback liefert [] ohne zu werfen -> Stufe muss failed sein."""
    monkeypatch.setattr(
        router_module, "_get_beat_detector", lambda: _StubDetector([], [])
    )

    checkpoints: list[tuple[str, dict]] = []

    with pytest.raises(RuntimeError):
        # Nur die Beats-Stufe angefordert: schlaegt sie fehl, schlaegt die
        # gesamte Analyse fehl. Ohne den Fix kaeme hier ein Ergebnis mit
        # bpm=0.0, beat_count=0 und stage_status beats="completed" zurueck.
        _run_audio_analysis(
            click_track,
            clip_id=1,
            request=_beats_only_request(),
            on_stage_checkpoint=lambda stage, fresh: checkpoints.append(
                (stage, fresh)
            ),
        )

    beat_checkpoints = [fresh for stage, fresh in checkpoints if stage == "beats"]
    assert beat_checkpoints, "Beats-Checkpoint wurde nie geschrieben"
    fresh = beat_checkpoints[-1]
    assert fresh["_stage_status"]["beats"] == "failed"
    assert fresh["_stage_errors"]["beats"]
    assert fresh["beat_count"] == 0
    assert fresh["bpm"] == 0.0


# --------------------------------------------------------------------------
# H-4 (b): Typpruefung allein macht eine leere Beats-Stufe nicht gueltig
# --------------------------------------------------------------------------


def _valid_beats_cache() -> dict:
    return {
        "bpm": 120.0,
        "beat_count": 2,
        "beats": [
            {"time": 0.5, "strength": 0.8, "beat_type": "beat"},
            {"time": 1.0, "strength": 0.9, "beat_type": "beat"},
        ],
        "energy_curve": [0.2, 0.8],
        "downbeats": [],
        "downbeat_provenance": {"status": "unavailable"},
        "onset_times": [0.5],
        "kick_times": [0.5],
        "snare_times": [],
        "hihat_times": [],
    }


def _empty_beats_cache() -> dict:
    cache = _valid_beats_cache()
    cache.update(
        {
            "bpm": 0.0,
            "beat_count": 0,
            "beats": [],
            "energy_curve": [],
            "onset_times": [],
            "kick_times": [],
        }
    )
    return cache


def test_valid_beats_cache_stays_reusable():
    """Gegenprobe zur Verschaerfung: echte Analysen bleiben wiederverwendbar."""
    assert _audio_stage_result_is_valid("beats", _valid_beats_cache()) is True


def test_empty_beats_cache_is_not_valid():
    # Ohne den Fix True: alle Typen stimmen, nur Inhalt fehlt.
    assert _audio_stage_result_is_valid("beats", _empty_beats_cache()) is False


def test_empty_beats_cache_is_replanned():
    """Der Clip muss erneut versucht werden statt dauerhaft als analysiert zu gelten."""
    cached = _empty_beats_cache()
    cached["_stage_status"] = {"beats": "completed"}
    planned = _plan_audio_analysis(_beats_only_request(), cached)
    assert planned.detect_beats is True

    reusable = _valid_beats_cache()
    reusable["_stage_status"] = {"beats": "completed"}
    assert _plan_audio_analysis(_beats_only_request(), reusable).detect_beats is False


# --------------------------------------------------------------------------
# M-1: eine Definition von BPM, und sie wird benannt
# --------------------------------------------------------------------------


def test_streaming_bpm_uses_beat_grid_not_window_median(monkeypatch, click_track):
    """Streaming lieferte den Fenster-Median; das Raster sagte etwas anderes."""
    import librosa

    import pb_studio.audio.streaming_analyzer as streaming_module

    monkeypatch.setattr(librosa, "get_duration", lambda *a, **kw: 1200.0)

    grid = [round(i * CLICK_PERIOD, 6) for i in range(16)]  # 120 BPM

    class _StubAnalyzer:
        def analyze(self, path, **kwargs):
            # bpm bewusst widerspruechlich zum gelieferten Raster
            return _StubStreamResult(grid, bpm=200.0, duration=1200.0)

    monkeypatch.setattr(streaming_module, "StreamingAudioAnalyzer", _StubAnalyzer)

    result = _run_audio_analysis(
        click_track, clip_id=2, request=_beats_only_request(clip_id=2)
    )

    # Ohne den Fix: 200.0 (Fenster-Median), im Widerspruch zu result["beats"].
    assert result["bpm"] == pytest.approx(60.0 / CLICK_PERIOD, abs=0.01)
    provenance = result["beat_grid_provenance"]
    assert provenance["method"] == "beat_interval_median"
    assert provenance["window_median_bpm"] == pytest.approx(200.0)


def test_bpm_matches_grid_and_method_is_recorded(monkeypatch, click_track):
    """Nicht-Streaming: BPM und Raster muessen dieselbe Aussage machen."""
    grid = [round(i * CLICK_PERIOD, 6) for i in range(16)]
    monkeypatch.setattr(
        router_module, "_get_beat_detector", lambda: _StubDetector(grid, [])
    )

    result = _run_audio_analysis(
        click_track, clip_id=3, request=_beats_only_request(clip_id=3)
    )

    times = [b["time"] for b in result["beats"]]
    recomputed = 60.0 / float(np.median(np.diff(sorted(times))))
    assert result["bpm"] == pytest.approx(recomputed, abs=0.01)
    # Ohne den Fix existiert der Schluessel nicht.
    assert result["beat_grid_provenance"]["method"] == "beat_interval_median"
    assert result["beat_grid_provenance"]["beat_count"] == len(times)
    assert result["beat_grid_provenance"]["kick_cross_check"] in {
        "passed",
        "failed",
        "not_possible",
    }


# --------------------------------------------------------------------------
# C-3: Plausibilitaetspruefung des Rasters
# --------------------------------------------------------------------------


def test_uniform_grid_with_matching_kicks_is_plausible():
    beats = [i * 0.5 for i in range(32)]
    kicks = [t + 0.005 for t in beats]  # leichter Versatz, weit unter Toleranz
    provenance = _evaluate_beat_grid(
        beats, kicks, bpm=120.0, method="beat_interval_median"
    )
    assert provenance["status"] == "plausible"
    assert provenance["regular"] is True
    assert provenance["kick_cross_check"] == "passed"
    assert provenance["kick_alignment"] == pytest.approx(1.0)


def test_half_tempo_grid_fails_the_kick_cross_check():
    """Dieselben Kicks, Raster um Faktor 2 zu langsam -> nur jeder zweite Treffer.

    Die Gegenprobe meldet den Fall weiterhin als `failed`. Sie entscheidet aber
    seit 2026-08-31 NICHT mehr ueber `status` — an echtem Material trennt sie
    nicht (siehe `test_kick_cross_check_does_not_drive_status`).
    """
    kicks = [i * 0.5 for i in range(32)]
    half_tempo_grid = [i * 1.0 for i in range(16)]
    provenance = _evaluate_beat_grid(
        half_tempo_grid, kicks, bpm=60.0, method="beat_interval_median"
    )
    # Das Raster selbst ist perfekt gleichmaessig — nur die Gegenprobe faellt.
    assert provenance["regular"] is True
    assert provenance["kick_alignment"] == pytest.approx(0.5)
    assert provenance["kick_cross_check"] == "failed"
    assert provenance["status"] == "plausible"


def test_kick_cross_check_does_not_drive_status():
    """Der Status haengt allein an der Gleichmaessigkeit.

    Begruendung aus der Messung an 127 Fenstern / 35 gemasterten Tracks
    (docs/measurements/2026-08-31-kick-gegenprobe-befund.md): bei der Schwelle
    0,75 wurden 125 von 127 Fenstern als `suspect` gemeldet, darunter 96 % der
    Fenster mit korrekt erkanntem Tempo. Ursache ist ein systematischer Versatz
    von einer Hop-Laenge zwischen den beiden Detektionsketten; nur 4 % aller
    Kicks liegen ueberhaupt innerhalb von +-23 ms eines Beats.

    Faellt dieser Test, hat jemand die Gegenprobe wieder ins Urteil
    aufgenommen - dann braucht es zuerst eine Metrik, die an echtem Material
    nachweislich trennt.
    """
    # Gleichmaessiges Raster, Kicks vollstaendig daneben: Gegenprobe faellt,
    # der Status bleibt trotzdem `plausible`.
    beats = [i * 0.5 for i in range(32)]
    kicks = [t + 0.25 for t in beats]
    provenance = _evaluate_beat_grid(
        beats, kicks, bpm=120.0, method="beat_interval_median"
    )
    assert provenance["kick_cross_check"] == "failed"
    assert provenance["kick_alignment"] == pytest.approx(0.0)
    assert provenance["regular"] is True
    assert provenance["status"] == "plausible"


def test_irregular_grid_is_suspect_even_without_kicks():
    rng = np.random.default_rng(7)
    beats = list(np.cumsum(rng.uniform(0.2, 1.4, 40)))
    provenance = _evaluate_beat_grid(
        beats, [], bpm=90.0, method="beat_interval_median"
    )
    assert provenance["regular"] is False
    assert provenance["kick_cross_check"] == "not_possible"
    assert provenance["status"] == "suspect"


def test_grid_without_beats_is_unavailable():
    provenance = _evaluate_beat_grid([], [], bpm=0.0, method="no_beats")
    assert provenance["status"] == "unavailable"
    assert provenance["interval_regularity"] is None


def test_tolerance_never_exceeds_a_quarter_beat():
    """Sonst koennte ein Halbtempo-Raster die Gegenprobe bestehen."""
    fast_beats = [i * 0.2 for i in range(40)]  # 300 BPM
    provenance = _evaluate_beat_grid(
        fast_beats, fast_beats, bpm=300.0, method="beat_interval_median"
    )
    assert provenance["tolerance_seconds"] <= 0.25 * 0.2 + 1e-9
    assert not math.isnan(provenance["tolerance_seconds"])


def test_schema_carries_beat_grid_provenance():
    from backend.schemas.audio_schemas import AudioAnalysisResult

    model = AudioAnalysisResult(
        clip_id=1,
        duration_seconds=1.0,
        beat_grid_provenance={"status": "plausible"},
    )
    assert model.beat_grid_provenance == {"status": "plausible"}
