"""Beatgrid-Schaetzung: Tempo, Anker und eine belastbare Guete.

Was hier anders gemacht wird als in `librosa.beat.beat_track`, und warum:

**1. Kein 120-BPM-Prior.** `beat_track` zieht sein Tempo aus einem Prior um
`start_bpm=120` mit `std_bpm=1.0`. Gemessen an 104 Fenstern kommerzieller
Tracks mit BPM-Referenz im Dateinamen (Beatport) lieferte das nur **sechs
verschiedene** Tempowerte; drei davon deckten 99 Fenster ab, obwohl die Stuecke
laut Auszeichnung von 69 bis 145 BPM streuen. In 33,7 % der Fenster stand das
Ergebnis in keinem einfachen Verhaeltnis zur Wahrheit. Die Kandidaten kommen
hier stattdessen aus dem Tempogramm.

**2. Feine Tempo-Nachoptimierung.** Der wirksamste Hebel, gemessen. Anteil der
Segmente, in denen ein starres Raster sitzt (Kontrast > 2,0, 770 Messwerte):

    Spanne    ganzzahlige BPM    Tempo nachoptimiert
      8 s          48 %                73 %
     30 s          38 %                66 %
    120 s          40 %                71 %

Die **Spanne ist fast bedeutungslos**, das Tempo entscheidet. Noetige
Genauigkeit an den tragenden Segmenten: Median-Abweichung 0,00-0,20 %,
90-Perzentil rund 1,45 %.

**3. Phasennormierte Guete statt roher Onset-Staerke.** Ein naheliegendes Mass
- mittlere Onset-Staerke an den Rasterpositionen geteilt durchs Gesamtmittel -
ist unbrauchbar, weil es einen Dichte-Bias hat: duennere Raster sitzen
selektiver auf Peaks. Gemessen an einer Datei, je beste Phase:

    572 BPM -> 1,101    143 BPM -> 1,135    17,9 BPM -> 1,370

Monoton steigend mit sinkendem Tempo. Der hier benutzte Kontrast (beste Phase
gegen den Mittelwert ueber alle Phasen) hat in Zaehler und Nenner dieselbe
Punktzahl; der Bias kuerzt sich weg.

**4. Oktav-Aufloesung ueber Praezision UND Trefferquote.** Die Kick-Gegenprobe
in `_evaluate_beat_grid` misst nur, welcher Anteil der Kicks nahe an einem Beat
liegt. Damit faellt ein zu langsames Raster auf (~0,5), ein zu schnelles aber
nicht: es enthaelt die wahren Beats als Teilmenge und trifft weiter zu ~100 %.
Hier wird deshalb zusaetzlich gemessen, welcher Anteil der **Beats** einen Kick
trifft. Ein doppelt zu schnelles Raster halbiert diesen Wert. Erst beide Werte
zusammen trennen die Oktave in beide Richtungen.

Bewusste Grenze: ein Tempo pro Aufruf. Fuer DJ-Mixe mit wechselndem Tempo ist
das strukturell falsch - dort muss der Aufrufer segmentieren und je Segment
schaetzen. Die Messung, die diesem Modul zugrunde liegt, lief ausschliesslich
auf Originalen mit konstantem Tempo; auf Mixe ist sie nicht uebertragbar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

HOP_LENGTH = 512
PHASE_STEPS = 64

# Suchraum fuer die Tempokandidaten. Unten 50, damit halbe Tempi langsamer
# Stuecke noch im Raster liegen und die Oktavpruefung sie sehen kann.
TEMPO_RANGE = (50.0, 220.0)
TEMPO_CANDIDATES = 6

# Feinsuche um jeden Kandidaten. +-2 % deckt die gemessene Streuung ab
# (90-Perzentil der noetigen Korrektur lag bei rund 1,45 %).
TEMPO_REFINE_REL = 0.02
TEMPO_REFINE_STEPS = 41

# Ab diesem Kontrast gilt ein Raster als sitzend. Der Wert trennt die beiden
# Modi der gemessenen, deutlich bimodalen Verteilung (Kontrast springt
# entweder auf ~3,2 oder bleibt bei ~1,1). Er ist an dieser Verteilung
# abgelesen, nicht gegen eine Nullhypothese kalibriert.
GRID_CONTRAST_MIN = 2.0

# Oktavpruefung: eine Alternative muss deutlich besser sein, um das
# bestbewertete Tempo zu verdraengen. Verhindert Flattern bei knappen Faellen.
OCTAVE_MARGIN = 0.05

# Toleranz beim Abgleich Beat gegen Kick. Die Kick-Zeiten sind auf das
# Hop-Raster quantisiert; unterhalb weniger Frames misst man
# Quantisierungsrauschen statt Treffer.
_KICK_TOLERANCE_FRAMES = 3


@dataclass
class BeatGrid:
    """Ein Raster als Regel: Anker plus Tempo, nicht als Liste von Zeitpunkten."""

    bpm: float
    anchor_s: float
    contrast: float
    method: str
    status: str
    kick_recall: Optional[float] = None
    kick_precision: Optional[float] = None
    octave_checked: bool = False
    candidates: list[dict[str, float]] = field(default_factory=list)

    def beat_times(self, start: float, end: float) -> np.ndarray:
        """Beat-Positionen im Intervall - aus der Regel erzeugt, nicht gespeichert."""
        if self.bpm <= 0:
            return np.zeros(0)
        interval = 60.0 / self.bpm
        first = self.anchor_s + np.ceil((start - self.anchor_s) / interval) * interval
        return np.arange(first, end, interval)

    def as_provenance(self) -> dict[str, Any]:
        """Herkunftsangabe im Stil von `downbeat_provenance`."""
        data = asdict(self)
        data.pop("candidates", None)
        data["synthetic"] = False
        return data


def _phase_scores(
    envelope: np.ndarray, times: np.ndarray, bpm: float, span: float
) -> np.ndarray:
    """Score je Phase. Gleiche Punktzahl fuer alle Phasen -> vergleichbar."""
    interval = 60.0 / bpm
    overall = float(np.mean(envelope))
    if overall <= 0.0 or interval <= 0.0 or span <= interval:
        return np.zeros(0)
    scores = np.empty(PHASE_STEPS, dtype=np.float64)
    for step in range(PHASE_STEPS):
        positions = np.arange(interval * step / PHASE_STEPS, span, interval)
        if positions.size < 8:
            return np.zeros(0)
        scores[step] = float(np.mean(np.interp(positions, times, envelope)) / overall)
    return scores


def _contrast(scores: np.ndarray) -> tuple[float, float]:
    """Kontrast und zugehoerige Phase (als Bruchteil eines Beat-Intervalls)."""
    if scores.size == 0:
        return 0.0, 0.0
    mean = float(np.mean(scores))
    if mean <= 0.0:
        return 0.0, 0.0
    best = int(np.argmax(scores))
    return float(scores[best] / mean), best / PHASE_STEPS


def _tempo_candidates(envelope: np.ndarray, sr: int) -> list[float]:
    """Tempospitzen aus dem Tempogramm - ohne den 120-BPM-Prior."""
    import librosa

    tempogram = librosa.feature.tempogram(
        onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
    )
    frequencies = librosa.tempo_frequencies(
        tempogram.shape[0], hop_length=HOP_LENGTH, sr=sr
    )
    strength = np.mean(tempogram, axis=1)
    usable = (frequencies >= TEMPO_RANGE[0]) & (frequencies <= TEMPO_RANGE[1])
    if not np.any(usable):
        return []
    order = np.argsort(strength[usable])[::-1]
    return [float(frequencies[usable][i]) for i in order[:TEMPO_CANDIDATES]]


def _refine(
    envelope: np.ndarray, times: np.ndarray, bpm: float, span: float
) -> tuple[float, float, float]:
    """Tempo eng nachoptimieren. Liefert (bpm, anchor_s, contrast)."""
    best = (bpm, 0.0, 0.0)
    grid = np.linspace(
        bpm * (1.0 - TEMPO_REFINE_REL),
        bpm * (1.0 + TEMPO_REFINE_REL),
        TEMPO_REFINE_STEPS,
    )
    for candidate in grid:
        contrast, phase = _contrast(_phase_scores(envelope, times, float(candidate), span))
        if contrast > best[2]:
            best = (float(candidate), phase * 60.0 / float(candidate), contrast)
    return best


def _kick_agreement(
    grid_times: np.ndarray, kicks: np.ndarray, tolerance: float
) -> tuple[float, float]:
    """Trefferquote und Praezision gegen die Kick-Zeiten.

    recall    Anteil der Kicks, die auf einem Beat liegen. Faellt bei einem zu
              LANGSAMEN Raster (halbes Tempo trifft nur jeden zweiten Kick).
    precision Anteil der Beats, die einen Kick treffen. Faellt bei einem zu
              SCHNELLEN Raster - genau der Fall, den die reine Trefferquote
              nicht sieht, weil ein doppeltes Raster alle Kicks enthaelt.
    """
    if grid_times.size == 0 or kicks.size == 0:
        return 0.0, 0.0

    def _near(source: np.ndarray, target: np.ndarray) -> float:
        idx = np.searchsorted(target, source)
        left = np.clip(idx - 1, 0, target.size - 1)
        right = np.clip(idx, 0, target.size - 1)
        distance = np.minimum(
            np.abs(source - target[left]), np.abs(source - target[right])
        )
        return float(np.mean(distance <= tolerance))

    return _near(kicks, grid_times), _near(grid_times, kicks)


def estimate_beat_grid(
    y: np.ndarray,
    sr: int,
    *,
    kick_times: Optional[list[float]] = None,
) -> BeatGrid:
    """Schaetzt Tempo und Anker eines Beatgrids.

    Args:
        y: Monosignal.
        sr: Abtastrate.
        kick_times: Unabhaengig gewonnene Kick-Zeitpunkte. Ohne sie wird das
            Tempo nicht auf Oktavfehler geprueft - der haeufigste Fehlerfall.

    Returns:
        Ein `BeatGrid`. `status` ist ``"plausible"``, wenn der Kontrast die
        Schwelle erreicht, sonst ``"suspect"``; bei zu kurzem oder stillem
        Material ``"unavailable"``.
    """
    import librosa

    envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH)
    if envelope.size < 16 or float(np.mean(envelope)) <= 0.0:
        return BeatGrid(0.0, 0.0, 0.0, "onset_envelope_empty", "unavailable")

    times = librosa.times_like(envelope, sr=sr, hop_length=HOP_LENGTH)
    span = float(times[-1])

    scored: list[tuple[float, float, float]] = []
    for candidate in _tempo_candidates(envelope, sr):
        refined = _refine(envelope, times, candidate, span)
        if refined[2] > 0.0:
            scored.append(refined)
    if not scored:
        return BeatGrid(0.0, 0.0, 0.0, "no_tempo_candidate", "unavailable")

    scored.sort(key=lambda item: item[2], reverse=True)
    bpm, anchor, contrast = scored[0]
    method = "tempogram_refined"
    recall = precision = None
    octave_checked = False

    # Die Oktavpruefung ist NICHT optional. Der Kontrast allein waehlt
    # systematisch das halbe Tempo: er beseitigt den Dichte-Bias nur innerhalb
    # eines Tempos, ueber Oktaven hinweg gewinnt weiter das duennere Raster,
    # weil dessen konkurrierende Phasen leerer sind. Gemessen an sauberen
    # Klickspuren, jeweils bester Kontrast:
    #
    #     110 BPM -> 54,98 (9,96) schlaegt 110,1 (8,63)
    #     128 BPM -> 64,02 (8,85) schlaegt 128,0 (8,71)
    #     140 BPM -> 69,98 (8,11) schlaegt 140,7 (2,38)
    #
    # Als Referenz dienen die uebergebenen Kick-Zeiten; fehlen sie, treten die
    # Onset-Spitzen an ihre Stelle. Die sind schwaecher, aber immer vorhanden -
    # ein ungeprueftes Tempo waere schlechter als eine schwaechere Pruefung.
    kicks = np.asarray(sorted(float(k) for k in (kick_times or [])), dtype=np.float64)
    reference_source = "kick"
    if kicks.size < 4:
        import librosa as _librosa

        peak_frames = _librosa.onset.onset_detect(
            onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
        )
        kicks = _librosa.frames_to_time(peak_frames, sr=sr, hop_length=HOP_LENGTH)
        reference_source = "onset"

    if kicks.size >= 4:
        octave_checked = True
        tolerance = _KICK_TOLERANCE_FRAMES * HOP_LENGTH / float(sr)
        # Das gewaehlte Tempo gegen seine Oktavnachbarn stellen. Bewertet wird
        # das harmonische Mittel aus Trefferquote und Praezision: ein zu
        # langsames Raster verliert an Trefferquote, ein zu schnelles an
        # Praezision. Nur beide zusammen trennen die Oktave beidseitig.
        best_score = -1.0
        # Nicht nur Oktaven: das Tempogramm liefert auch Drittel. Gemessen an
        # einer 174-BPM-Klickspur war der staerkste Kandidat 58 BPM = 174/3,
        # den eine reine Halb/Doppel-Pruefung nicht erreicht.
        for factor in (1.0 / 3.0, 0.5, 1.0, 2.0, 3.0):
            trial_bpm = bpm * factor
            if not (TEMPO_RANGE[0] <= trial_bpm <= TEMPO_RANGE[1]):
                continue
            trial = _refine(envelope, times, trial_bpm, span)
            if trial[2] <= 0.0:
                continue
            grid = BeatGrid(trial[0], trial[1], trial[2], "", "").beat_times(0.0, span)
            trial_recall, trial_precision = _kick_agreement(grid, kicks, tolerance)
            if trial_recall + trial_precision <= 0.0:
                continue
            score = 2.0 * trial_recall * trial_precision / (trial_recall + trial_precision)
            # Das ungeaenderte Tempo behaelt den Zuschlag, damit eine
            # Alternative es nur bei deutlichem Vorsprung verdraengt.
            if factor == 1.0:
                score += OCTAVE_MARGIN
            if score > best_score:
                best_score = score
                bpm, anchor, contrast = trial
                recall, precision = trial_recall, trial_precision
                method = (
                    f"tempogram_refined_{reference_source}_verified" if factor == 1.0
                    else f"tempogram_refined_octave_corrected_{factor:g}x_{reference_source}"
                )
        if "octave_corrected" in method:
            logger.info(
                "Beatgrid: Oktave korrigiert auf %.2f BPM "
                "(Trefferquote %.2f, Praezision %.2f)", bpm, recall or 0.0, precision or 0.0
            )

    status = "plausible" if contrast >= GRID_CONTRAST_MIN else "suspect"
    if status == "suspect":
        logger.info(
            "Beatgrid: Kontrast %.2f unter %.2f - Raster als suspect gemeldet",
            contrast, GRID_CONTRAST_MIN,
        )

    return BeatGrid(
        bpm=round(bpm, 4),
        anchor_s=round(anchor, 5),
        contrast=round(contrast, 4),
        method=method,
        status=status,
        kick_recall=None if recall is None else round(recall, 4),
        kick_precision=None if precision is None else round(precision, 4),
        octave_checked=octave_checked,
        candidates=[
            {"bpm": round(b, 3), "contrast": round(c, 4)} for b, _, c in scored[:TEMPO_CANDIDATES]
        ],
    )
