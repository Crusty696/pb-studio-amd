"""Regressionstests fuer sechs verifizierte Defekte in
``src/pb_studio/pacing/advanced_pacing_engine.py`` (Audit 2026-08-30).

Jeder Test ist ohne den jeweiligen Fix rot — Gegenprobe im Bericht dokumentiert.

  C-1  Energy-Trigger aus gecachter Kurve landeten bei doppelter Zeit
  C-2  Bass-Stem-Trigger indizierten die (fremde) Mix-Energiekurve
  H-1  toter ``bpm``-Parameter in den beiden Trigger-Buildern
  H-5  Default-Gewichte erzwangen Voll-Load des Audios bei langen Mixen
  H-6  ``downbeat_only``/``strong_only`` lieferten still leere Listen
  M-3  ``_tempo_at_time`` hat keinen produktiven Konsumenten (dokumentiert)
"""
import inspect
import logging
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_FILE = REPO_ROOT / "src" / "pb_studio" / "pacing" / "advanced_pacing_engine.py"

SR = 22050


def _engine(**weights) -> AdvancedPacingEngine:
    ts = {
        "beat_weight": 0.0,
        "onset_weight": 0.0,
        "kick_weight": 0.0,
        "snare_weight": 0.0,
        "hihat_weight": 0.0,
        "energy_weight": 0.0,
        "energy_threshold": 0.6,
    }
    ts.update(weights)
    return AdvancedPacingEngine(trigger_settings=ts)


def _warnings(caplog) -> str:
    return "\n".join(
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    )


# ---------------------------------------------------------------- C-1
def test_c1_cached_energy_trigger_stays_inside_audio_duration():
    """Gecachte Energiekurve -> Zeit relativ zur echten Dauer, nicht via
    frames_to_time(sr=22050, hop=512).

    Die Kurve wird hier mit ~86,13 Werten/s erzeugt (so rechnet
    ``audio_router.py`` bei ``analysis_sr=44100``). Der alte Code las sie mit
    43,07 Frames/s zurueck und lieferte exakt die doppelte Zeit.
    """
    duration = 10.0
    y = np.zeros(int(duration * SR), dtype=np.float32)

    n = 862                      # ~86,13 Werte/s bei 10 s
    curve = np.full(n, 0.05, dtype=float)
    peak_idx = 431               # relative Position 0.5 -> wahre Zeit 5,0 s
    curve[peak_idx - 1: peak_idx + 2] = 0.4
    curve[peak_idx] = 1.0

    eng = _engine(energy_weight=1.0)
    eng._pre_cached_energy = curve

    triggers = [t for t in eng._extract_other_triggers(y, SR) if t.trigger_type == "energy"]
    assert triggers, "kein Energy-Trigger erzeugt — Testaufbau pruefen"

    for trig in triggers:
        assert 0.0 <= trig.time <= duration, (
            f"Energy-Trigger bei {trig.time:.3f}s liegt ausserhalb der "
            f"Audiodauer {duration:.1f}s (C-1: doppelte Zeit)"
        )

    best = max(triggers, key=lambda t: t.strength)
    expected = duration * peak_idx / n
    assert abs(best.time - expected) < 0.1, (
        f"Peak bei {best.time:.3f}s statt {expected:.3f}s"
    )


def test_c1_locally_computed_energy_still_uses_frames_to_time():
    """Gegenprobe: ohne Cache bleibt die frame-basierte Umrechnung richtig."""
    duration = 4.0
    t = np.linspace(0, duration, int(duration * SR), endpoint=False)
    y = (0.02 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    burst = slice(int(2.0 * SR), int(2.2 * SR))
    y[burst] = np.sin(2 * np.pi * 220 * t[burst]).astype(np.float32)

    eng = _engine(energy_weight=1.0)
    assert getattr(eng, "_pre_cached_energy", None) is None

    triggers = [x for x in eng._extract_other_triggers(y, SR) if x.trigger_type == "energy"]
    assert triggers
    best = max(triggers, key=lambda x: x.strength)
    assert 1.8 <= best.time <= 2.4, f"lokal berechneter Peak bei {best.time:.3f}s"
    assert best.time <= duration


# ---------------------------------------------------------------- C-2
def test_c2_bass_stem_uses_own_rms_not_cached_mix_energy(tmp_path, monkeypatch):
    """Bass-Stem-Staerken muessen aus dem Stem selbst kommen.

    Frueher wurde bei vorhandenem ``_pre_cached_energy`` die MIX-Kurve
    indiziert (andere Framerate, andere Laenge) und der Ueberlauf mit
    ``min()`` still geklemmt.
    """
    import librosa
    import soundfile as sf

    duration = 2.0
    t = np.linspace(0, duration, int(duration * SR), endpoint=False)
    y = np.sin(2 * np.pi * 60 * t).astype(np.float32)
    y[int(1.0 * SR):] *= 0.05          # zweite Haelfte deutlich leiser
    stem = tmp_path / "bass.wav"
    sf.write(str(stem), y, SR)

    # feste Onset-Frames: einer in der lauten, einer in der leisen Haelfte
    frames = np.array([10, 60])        # 0.23 s und 1.39 s bei hop=512
    monkeypatch.setattr(librosa.onset, "onset_detect", lambda *a, **k: frames)

    eng = _engine()
    # Konstante Mix-Kurve: alter Code haette daraus fuer JEDEN Onset
    # rms_norm == 1.0 gelesen -> alle Staerken exakt gleich 0.7.
    eng._pre_cached_energy = np.ones(200, dtype=float)

    triggers = eng._extract_bass_triggers_from_stem(str(stem))
    assert len(triggers) == 2, f"erwartet 2 Bass-Trigger, bekam {len(triggers)}"

    loud, quiet = triggers[0].strength, triggers[1].strength
    assert not (abs(loud - 0.7) < 1e-6 and abs(quiet - 0.7) < 1e-6), (
        "beide Staerken exakt 0.7 — die gecachte Mix-Kurve wurde indiziert (C-2)"
    )
    assert loud > quiet * 2, (
        f"Staerke im lauten Abschnitt ({loud:.4f}) muss die im leisen "
        f"({quiet:.4f}) klar uebersteigen"
    )


# ---------------------------------------------------------------- H-1
@pytest.mark.parametrize(
    "method_name", ["_extract_other_triggers", "_build_triggers_from_cache"]
)
def test_h1_no_dead_bpm_parameter(method_name):
    """``bpm`` wurde in beiden Rumpfen nie gelesen und ist entfernt."""
    sig = inspect.signature(getattr(AdvancedPacingEngine, method_name))
    assert "bpm" not in sig.parameters, (
        f"{method_name} fuehrt weiterhin den ungenutzten Parameter 'bpm' "
        f"(Signatur: {sig})"
    )


def test_h1_public_signature_unchanged():
    """``expected_bpm`` bleibt oeffentlich — pacing_service.py haengt daran."""
    sig = inspect.signature(AdvancedPacingEngine.generate_cut_list)
    assert "expected_bpm" in sig.parameters


# ---------------------------------------------------------------- H-5
def test_h5_long_mix_does_not_full_load_audio(monkeypatch, caplog):
    """> 600 s: fehlender Kick-Cache darf keinen Voll-Load ausloesen."""
    import librosa

    load_mock = Mock(side_effect=AssertionError("librosa.load darf hier nicht laufen"))
    monkeypatch.setattr(librosa, "load", load_mock)

    eng = _engine(beat_weight=1.0, onset_weight=0.5, kick_weight=1.2, energy_weight=0.8)
    eng._pre_cached_beats = [float(i) * 2.0 for i in range(300)]
    eng._pre_cached_duration = 700.0
    eng._pre_cached_onset_times = [1.0, 3.5, 7.25]
    eng._pre_cached_energy = np.linspace(0.1, 1.0, 500)
    # kick_times fehlt bewusst -> _missing_for_active_weights == True

    with caplog.at_level(logging.WARNING):
        cuts = eng._generate_cut_list_from_audio(
            r"C:\pacing-test\longmix.wav", expected_bpm=120.0,
        )

    load_mock.assert_not_called()
    assert cuts, "trotz uebersprungenem Voll-Load muessen Cuts entstehen"
    text = _warnings(caplog)
    assert "kick_weight" in text, (
        "die Warnung muss die betroffenen Gewichte benennen; gesehen:\n" + text
    )


def test_h5_short_mix_still_full_loads(monkeypatch):
    """Unter der Grenze bleibt das bisherige Verhalten erhalten."""
    import librosa

    loaded = np.zeros(SR * 5, dtype=np.float32)
    load_mock = Mock(return_value=(loaded, SR))
    monkeypatch.setattr(librosa, "load", load_mock)

    eng = _engine(beat_weight=1.0, onset_weight=0.5, kick_weight=1.2, energy_weight=0.8)
    eng._pre_cached_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    eng._pre_cached_duration = 5.0
    eng._pre_cached_onset_times = [1.0]
    eng._pre_cached_energy = np.linspace(0.1, 1.0, 50)

    eng._generate_cut_list_from_audio(r"C:\pacing-test\short.wav", expected_bpm=120.0)
    load_mock.assert_called_once_with(r"C:\pacing-test\short.wav", sr=22050)


# ---------------------------------------------------------------- H-6
def test_h6_downbeat_only_without_downbeats_falls_back_loudly(caplog):
    eng = _engine(beat_weight=1.0)
    eng.trigger_settings.beat_trigger_mode = "downbeat_only"
    beats = [0.0, 0.5, 1.0, 1.5]

    with caplog.at_level(logging.WARNING):
        out = eng._build_beat_triggers(beats, [])

    assert len(out) == len(beats), (
        "downbeat_only ohne Downbeats muss auf mode='all' zurueckfallen "
        f"(bekam {len(out)} Trigger)"
    )
    text = _warnings(caplog)
    assert "downbeat_only" in text and "Downbeats" in text
    assert "all" in text


def test_h6_strong_only_without_strengths_falls_back_loudly(caplog):
    eng = _engine(beat_weight=1.0)
    eng.trigger_settings.beat_trigger_mode = "strong_only"
    beats = [0.0, 0.5, 1.0, 1.5]

    with caplog.at_level(logging.WARNING):
        out = eng._build_beat_triggers(beats, [])

    assert len(out) == len(beats), (
        "strong_only ohne Beat-Staerken muss auf mode='all' zurueckfallen "
        f"(bekam {len(out)} Trigger)"
    )
    text = _warnings(caplog)
    assert "strong_only" in text and "Staerken" in text


def test_h6_modes_still_filter_when_data_is_available():
    """Kein pauschaler Rueckfall: sind Downbeats da, filtert der Modus weiter."""
    eng = _engine(beat_weight=1.0)
    eng.trigger_settings.beat_trigger_mode = "downbeat_only"
    out = eng._build_beat_triggers([0.0, 0.5, 1.0, 1.5], [0.0, 1.0])
    assert [c.time for c in out] == [0.0, 1.0]


# ---------------------------------------------------------------- M-3
def test_m3_tempo_at_time_missing_consumer_is_documented():
    """Solange es keinen Konsumenten gibt, muss der Docstring das belegen."""
    doc = inspect.getdoc(AdvancedPacingEngine._tempo_at_time) or ""
    assert "M-3" in doc, "_tempo_at_time-Docstring dokumentiert den Befund nicht"
    assert "KEIN PRODUKTIVER KONSUMENT" in doc
    assert "_plan_emotional_sync" in doc, "der gepruefte Kandidat muss benannt sein"


def test_m3_tempo_at_time_has_no_production_caller():
    """Waechter: taucht ein produktiver Aufrufer auf, ist der Docstring stale."""
    hits = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if "_tempo_at_time(" not in line:
                continue
            stripped = line.strip()
            if stripped.startswith("def _tempo_at_time") or stripped.startswith("#"):
                continue
            if path == ENGINE_FILE and "_tempo_at_time(t)" in stripped:
                continue  # Prosa im Docstring von pacing_service-Hinweisen
            hits.append(f"{path}:{lineno}: {stripped}")
    assert not hits, (
        "_tempo_at_time hat jetzt einen Aufrufer — Docstring-Begruendung "
        "aktualisieren:\n" + "\n".join(hits)
    )
