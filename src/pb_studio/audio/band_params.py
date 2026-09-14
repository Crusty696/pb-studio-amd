"""Gemeinsame Bandgrenzen und STFT-Parameter fuer die Drum-Trigger.

Befund H-3 (Audit 2026-08-30): Kick-, Snare- und HiHat-Zeiten werden an drei
Stellen unabhaengig voneinander berechnet, mit drei verschiedenen
Parametersaetzen:

    backend/routers/audio_router.py          `_band_stft_params`, adaptiv
    src/pb_studio/audio/streaming_analyzer.py `_band_times`, adaptiv
    src/pb_studio/pacing/advanced_pacing_engine.py  n_mels=64, n_fft=Default

Der Audit 2026-08-05 hatte die degenerierte Mel-Filterbank in Router und
Streaming repariert; die Pacing-Engine hat denselben Fix nie bekommen und stand
weiter auf `n_mels=64` mit `n_fft=2048`. Bei sr=22050 liegen im Kick-Band
(20-150 Hz) dann rund 14 Bins - fuer 64 Filter. Das ist genau die Konfiguration
mit "Empty filters detected", die der Audit verworfen hatte.

Zweite, unabhaengige Divergenz: das HiHat-Band war ohne `fmax` definiert und
reichte damit bis zur halben Abtastrate. Router (44100 Hz) mass 5000-22050 Hz,
die Engine (22050 Hz) mass 5000-11025 Hz - **verschiedene Frequenzbaender**
fuer dieselbe Aufgabe. Deshalb ist die Obergrenze hier fest verdrahtet und
nicht mehr von der Abtastrate abhaengig.

Dieselbe Datei lieferte je nach Codepfad andere Trigger-Zeitpunkte. Dieses
Modul ist die eine Quelle fuer alle drei Pfade.
"""

from __future__ import annotations

# Bandgrenzen in Hz. Die HiHat-Obergrenze ist bewusst fest und liegt knapp
# unter der Nyquist-Frequenz der niedrigsten hier verwendeten Abtastrate
# (22050 Hz -> 11025 Hz), damit alle Pfade dasselbe Band messen.
KICK_BAND: tuple[float, float] = (20.0, 150.0)
SNARE_BAND: tuple[float, float] = (200.0, 400.0)
HIHAT_BAND: tuple[float, float] = (5000.0, 11000.0)

_MIN_BINS_IN_BAND = 24.0
_MAX_N_FFT = 8192
_MIN_N_MELS = 4


def band_stft_params(
    sr: int,
    fmin: float,
    fmax: float | None,
    max_mels: int = 64,
) -> tuple[int, int]:
    """Waehlt ``n_fft`` und ``n_mels`` passend zur Bandbreite.

    Audit 2026-08-05 (M-2): Eine feste Filterzahl ueber ein schmales Band
    erzeugt leere Mel-Filter - das Band liefert dann keine oder eine
    unbrauchbare Onset-Envelope. Regel: erst die FFT-Aufloesung so waehlen,
    dass genug Bins im Band liegen, dann hoechstens halb so viele Filter wie
    Bins vergeben.

    Returns:
        ``(n_fft, n_mels)`` - ``n_fft`` als Zweierpotenz, ``n_mels`` mindestens 4.
    """
    upper = float(fmax) if fmax else float(sr) / 2.0
    span = max(1.0, upper - float(fmin))

    n_fft = 2048
    while n_fft < _MAX_N_FFT and (span / (sr / n_fft)) < _MIN_BINS_IN_BAND:
        n_fft *= 2

    bins_in_band = max(1, int(span / (sr / n_fft)))
    n_mels = max(_MIN_N_MELS, min(max_mels, bins_in_band // 2))
    return n_fft, n_mels
