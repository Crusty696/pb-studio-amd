"""Waechter gegen divergierende Drum-Trigger-Parameter (Befund H-3).

Kick-, Snare- und HiHat-Zeiten entstehen an drei Stellen unabhaengig
voneinander:

    backend/routers/audio_router.py                  Nicht-Streaming-Analyse
    src/pb_studio/audio/streaming_analyzer.py        lange Mixe
    src/pb_studio/pacing/advanced_pacing_engine.py   Live-Trigger-Pfad

Bis 2026-08-30 hatte jede Stelle ihren eigenen Parametersatz. Der Audit
2026-08-05 reparierte die degenerierte Mel-Filterbank in Router und Streaming;
die Pacing-Engine bekam denselben Fix nie und stand weiter auf `n_mels=64` mit
dem n_fft-Default 2048 - im Kick-Band bei sr=22050 rund 14 Bins fuer 64 Filter.

Dieselbe Datei lieferte damit je nach Codepfad andere Trigger-Zeitpunkte. Diese
Tests halten fest, dass es genau eine Quelle gibt und niemand sie umgeht.
"""

import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from pb_studio.audio.band_params import (  # noqa: E402
    HIHAT_BAND,
    KICK_BAND,
    SNARE_BAND,
    band_stft_params,
)

CONSUMERS = (
    REPO_ROOT / "backend" / "routers" / "audio_router.py",
    REPO_ROOT / "src" / "pb_studio" / "audio" / "streaming_analyzer.py",
    REPO_ROOT / "src" / "pb_studio" / "pacing" / "advanced_pacing_engine.py",
)


@pytest.mark.parametrize("path", CONSUMERS, ids=lambda p: p.name)
def test_consumer_imports_the_shared_source(path: Path) -> None:
    """Jeder der drei Pfade bezieht die Parameter aus `band_params`."""
    source = path.read_text(encoding="utf-8")
    assert "band_params import" in source, (
        f"{path.name} importiert die gemeinsamen Bandparameter nicht"
    )


def _code_lines(path: Path) -> str:
    """Quelltext ohne reine Kommentarzeilen.

    Die Befunde werden in Kommentaren zitiert ("stand vorher auf n_mels=64").
    Ohne diese Trennung wuerde der Waechter seine eigene Begruendung als
    Verstoss melden - ein Falschalarm, der ihn wertlos machte.
    """
    return "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


@pytest.mark.parametrize("path", CONSUMERS, ids=lambda p: p.name)
def test_consumer_has_no_hardcoded_filter_count(path: Path) -> None:
    """`n_mels=64` fest verdrahtet war genau der Defekt - darf nicht zurueck."""
    assert "n_mels=64" not in _code_lines(path), (
        f"{path.name} verdrahtet die Filterzahl wieder fest; sie muss aus "
        f"band_stft_params kommen"
    )


@pytest.mark.parametrize("path", CONSUMERS, ids=lambda p: p.name)
def test_consumer_has_no_literal_band_edges(path: Path) -> None:
    """Bandgrenzen nur noch als Konstante, nicht als Zahl im Aufruf."""
    code = _code_lines(path)
    for literal in ("fmin=200, fmax=400", "fmin=5000", "fmax=150,"):
        assert literal not in code, (
            f"{path.name} setzt die Bandgrenze literal ({literal!r}) statt "
            f"ueber KICK_BAND / SNARE_BAND / HIHAT_BAND"
        )


def test_hihat_band_is_independent_of_sample_rate() -> None:
    """Das HiHat-Band darf nicht an der Abtastrate haengen.

    Ohne feste Obergrenze mass der Router (44100 Hz) 5000-22050 Hz und die
    Pacing-Engine (22050 Hz) 5000-11025 Hz - verschiedene Baender fuer
    dieselbe Aufgabe.
    """
    assert HIHAT_BAND[1] is not None
    # Muss unter der Nyquist-Frequenz der niedrigsten benutzten Rate liegen.
    assert HIHAT_BAND[1] < 22050 / 2


@pytest.mark.parametrize("sr", [22050, 44100])
@pytest.mark.parametrize("band", [KICK_BAND, SNARE_BAND, HIHAT_BAND])
def test_filter_bank_never_degenerates(sr: int, band: tuple[float, float]) -> None:
    """Kernzusage: hoechstens halb so viele Filter wie Bins im Band."""
    n_fft, n_mels = band_stft_params(sr, *band)
    bins_in_band = (band[1] - band[0]) / (sr / n_fft)
    assert n_mels <= max(4, bins_in_band // 2) or n_mels == 4
    assert n_mels >= 4
    assert n_fft & (n_fft - 1) == 0, "n_fft muss eine Zweierpotenz sein"


def test_engine_would_have_degenerated_before_the_fix() -> None:
    """Belegt, dass der alte Engine-Parametersatz tatsaechlich entartet war.

    Kein Verhaltenstest, sondern die Rechnung, die den Befund traegt: bei
    sr=22050 und n_fft=2048 liegen im Kick-Band rund 14 Bins - fuer die
    vorher fest verdrahteten 64 Filter.
    """
    sr, old_n_fft, old_n_mels = 22050, 2048, 64
    bins_in_kick_band = (KICK_BAND[1] - KICK_BAND[0]) / (sr / old_n_fft)
    assert bins_in_kick_band < old_n_mels / 2, (
        "Ausgangsbefund nicht mehr reproduzierbar - Bandgrenzen geaendert?"
    )

    _, new_n_mels = band_stft_params(sr, *KICK_BAND)
    assert new_n_mels < old_n_mels


def test_shared_helper_signature_is_stable() -> None:
    """Der Router haelt einen Alias auf diese Funktion; Signatur festhalten."""
    parameters = list(inspect.signature(band_stft_params).parameters)
    assert parameters == ["sr", "fmin", "fmax", "max_mels"]
