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

**5. Kein 3:2-Faktor in der Oktavpruefung - gemessen, nicht vergessen.** Der
Anlass war ein 3:2-Fehler an echtem Material: 94,67 statt 143 BPM. Die
Kandidatenliste enthaelt das wahre Tempo (142,00, Kontrast 4,35) direkt hinter
dem gewaehlten (94,67, Kontrast 4,44), und 94,67 x 1,5 = 142,00 - der Faktor
1,5 wuerde also genau dorthin fuehren. Er ist trotzdem nicht eingebaut, weil
die Gegenprobe ihn nicht traegt. An derselben Datei, harmonisches Mittel aus
Trefferquote und Praezision, Toleranz 69,7 ms:

    x1     ->  94,67 BPM   0,3098   (+0,05 Zuschlag = 0,3598)
    x1,5   -> 142,00 BPM   0,2606
    x2     -> 189,34 BPM   0,4053

Das wahre Tempo schneidet am schlechtesten ab. Ein zusaetzlicher Faktor 1,5
wuerde die Auswahl also nicht auf 143 bringen, und an derselben Datei mit
sr=22050 zoege er sie von 81,14 auf 126,22 - auch falsch. Der Grund liegt
tiefer und ist in
docs/measurements/2026-08-31-kick-gegenprobe-befund.md belegt: die
Kick-Kette dieses Tracks traegt tatsaechlich einen Puls bei 0,634 s
(= 1,5 Beats), die Gegenprobe stuetzt das falsche Tempo. Wer 1,5 ergaenzen
will, braucht vorher eine Referenz, die das wahre Tempo auch belohnt.

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

# Suchraum fuer die Tempokandidaten.
#
# Frueher (50, 220) mit der Begruendung, halbe Tempi langsamer Stuecke muessten
# noch im Raster liegen. Das war zu weit gefasst und hat mehr geschadet als
# genutzt: an 20 gemasterten Tracks gemessen, je ein 120-s-Fenster,
# oktavnormiert mit 2 % Toleranz:
#
#     50-220 BPM   ->  7/20 = 35,0 %
#     70-145 BPM   -> 10/20 = 50,0 %
#    100-150 BPM   -> 11/20 = 55,0 %
#
# Ein weiter Suchraum liefert mehr Kandidaten, und der Kontrast bevorzugt unter
# ihnen systematisch das duennere (langsamere) Raster - die zusaetzlichen
# Kandidaten sind also ueberwiegend Fehlerquellen, keine Chancen.
#
# ACHTUNG, das ist genrespezifisch: der Bereich stammt aus der Angabe des
# Projektinhabers ("meine Mixe sind nie schneller als 145 BPM") und ist an
# dessen Material (Psy-/Progressive-Trance, 136-145 BPM) gemessen. Fuer
# Drum'n'Bass (~174), Footwork (~160) oder langsamen HipHop (~85) ist er
# falsch. Deshalb Konstante und kein Literal - wer anderes Material hat, muss
# ihn anpassen und die Messung wiederholen.
#
# Die Untergrenze 100 statt 70 kostet nichts, solange oktavnormiert verglichen
# wird: ein 69-BPM-Track wird als 138 gefunden. Sie schuetzt aber davor, dass
# das halbe Tempo ueberhaupt erst als Kandidat antritt.
TEMPO_RANGE = (100.0, 150.0)
TEMPO_CANDIDATES = 6

# Feinsuche um jeden Kandidaten.
#
# Die urspruengliche Begruendung fuer +-2 % ("90-Perzentil der noetigen
# Korrektur lag bei rund 1,45 %") war an der falschen Groesse gemessen: sie
# betraf die Abweichung von einer bereits richtigen BPM, nicht die Luecke
# zwischen zwei Kandidaten.
#
# Die Kandidaten kommen aus dem Tempogramm und liegen deshalb auf einem
# diskreten Raster: 60*sr/hop / k, bei sr=22050 und hop=512 also 2583,98 / k.
# Der Abstand zweier Nachbarn betraegt dort 3,3 % bis 6,7 %:
#
#     k=14 -> 184,57 BPM   Luecke 6,7 %
#     k=18 -> 143,55 BPM   Luecke 5,3 %
#     k=28 ->  92,29 BPM   Luecke 3,4 %
#
# Mit +-2 % konnte die Suche zwischen zwei Kandidaten gar nicht landen. An
# 127 Fenstern gemessen war die Folge ein eigener Attraktor: 32 Fenster
# lieferten 141,98 BPM (= 143,55 x 0,989, also den unteren Rand des
# Suchbereichs um k=18) fuer wahre Tempi zwischen 69 und 144.
#
# Genau derselbe Mechanismus erklaert die Attraktoren des heutigen
# Produktionspfads: dessen drei haeufigste Werte - 143,55 / 136,00 / 92,29 -
# sind exakt die Tempogramm-Frequenzen fuer k = 18, 19 und 28.
#
# Der Suchbereich richtet sich daher nach der tatsaechlichen Luecke des
# jeweiligen Kandidaten (siehe `_refine_span`). Ueberlappende Bereiche
# benachbarter Kandidaten schaden nicht - es gewinnt ohnehin der beste
# Kontrast.
TEMPO_REFINE_STEPS = 81
# Untere Schranke, falls die Luecke sehr klein wird (hohe k, langsame Tempi).
TEMPO_REFINE_REL_MIN = 0.02
# Konstante des Tempogramm-Rasters: 60 * sr / hop_length.
_TEMPOGRAM_CONST = 60.0 * 22050.0 / HOP_LENGTH

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

# Bezugsrate der Toleranz - NICHT die tatsaechliche `sr`.
#
# Der Router laedt mit `analysis_sr`, und das ist 44100, wenn
# `spectral_analysis` gesetzt ist, sonst 22050 (audio_router.py:2136). Wurde
# die Toleranz mit der tatsaechlichen Rate gerechnet, hing sie an einem Flag,
# das mit Beats nichts zu tun hat: 3*512/22050 = 69,7 ms gegen
# 3*512/44100 = 34,8 ms.
#
# An der echten Datei gemessen (Antinomy - Imagination (Kalki remix), 544 s,
# 143 BPM laut Auszeichnung), identisches Signal, identische Kick-Kette,
# identisches 94,67-BPM-Raster:
#
#     34,8 ms -> Trefferquote 0,0339   Praezision 0,0349
#     69,7 ms -> Trefferquote 0,3054   Praezision 0,3143
#
# Faktor 9 allein aus der Abtastrate. Genau das ist der Grund, aus dem die
# Schwester-Pruefung im Router ihre Toleranz fest an 22050 bindet
# (`_BEAT_GRID_KICK_TOLERANCE_FLOOR`, audio_router.py:897): "damit dieselbe
# Datei nicht je nach `spectral_analysis`-Flag anders bewertet wird". Hier galt
# diese Regel nicht - das war der Fehler.
_KICK_TOLERANCE_REFERENCE_SR = 22050


def _kick_tolerance(sr: int) -> float:
    """Vergleichstoleranz in Sekunden, unabhaengig von der geladenen Rate.

    Untergrenze ist die Hop-Dauer bei 22050 Hz. Wird noch groeber geladen
    (sr < 22050), zaehlt die tatsaechliche, groebere Hop-Dauer - darunter
    misst man wieder Quantisierungsrauschen.
    """
    if sr <= 0:
        return _KICK_TOLERANCE_FRAMES * HOP_LENGTH / float(_KICK_TOLERANCE_REFERENCE_SR)
    return max(
        _KICK_TOLERANCE_FRAMES * HOP_LENGTH / float(sr),
        _KICK_TOLERANCE_FRAMES * HOP_LENGTH / float(_KICK_TOLERANCE_REFERENCE_SR),
    )


def _chance_rates(
    bpm: float, kick_count: int, span: float, tolerance: float
) -> tuple[float, float]:
    """Zufallserwartung fuer Trefferquote und Praezision.

    Keine abgelesene Schwelle, sondern die Nullhypothese selbst: liegt ein
    Zeitpunkt gleichverteilt auf der Achse, faellt er mit Wahrscheinlichkeit
    `2*Toleranz/Abstand` in das Fenster um eine der Marken der Gegenseite.

        Trefferquote  Marken sind die Beats      -> Abstand 60/bpm
        Praezision    Marken sind die Kicks      -> Abstand span/(n-1)

    Beispiel aus der Messung oben: 94,67 BPM (Intervall 0,634 s), Toleranz
    34,8 ms -> Zufall 0,110. Gemessen wurden 0,0339 - ein Drittel des
    Zufallsniveaus. Solche Werte sind kein "schlechtes Material", sie zeigen
    an, dass die beiden Ketten nicht dasselbe messen. Ein Raster, dessen
    Gegenprobe das Zufallsniveau nicht erreicht, darf sich nicht `plausible`
    nennen (siehe `estimate_beat_grid`).
    """
    if bpm <= 0.0 or span <= 0.0 or kick_count < 2:
        return 0.0, 0.0
    beat_interval = 60.0 / bpm
    kick_interval = span / float(kick_count - 1)
    if beat_interval <= 0.0 or kick_interval <= 0.0:
        return 0.0, 0.0
    return (
        min(1.0, 2.0 * tolerance / beat_interval),
        min(1.0, 2.0 * tolerance / kick_interval),
    )


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
    # Zufallserwartung zu genau diesen beiden Werten. Ohne sie ist eine
    # Trefferquote nicht lesbar: 0,30 ist bei 95 BPM gut und bei 190 BPM
    # nichts. Wird mitgeliefert, damit das Urteil nachrechenbar bleibt.
    kick_recall_chance: Optional[float] = None
    kick_precision_chance: Optional[float] = None
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


def _tempo_candidates(
    envelope: np.ndarray, sr: int,
    tempo_range: tuple[float, float] | None = None,
) -> list[float]:
    """Tempospitzen aus dem Tempogramm - ohne den 120-BPM-Prior."""
    import librosa

    tempogram = librosa.feature.tempogram(
        onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
    )
    frequencies = librosa.tempo_frequencies(
        tempogram.shape[0], hop_length=HOP_LENGTH, sr=sr
    )
    strength = np.mean(tempogram, axis=1)
    low, high = tempo_range or TEMPO_RANGE
    usable = (frequencies >= low) & (frequencies <= high)
    if not np.any(usable):
        return []
    order = np.argsort(strength[usable])[::-1]
    return [float(frequencies[usable][i]) for i in order[:TEMPO_CANDIDATES]]


def _refine_span(bpm: float, sr: int) -> float:
    """Relativer Suchbereich, der bis zum Nachbarkandidaten reicht.

    Die Tempogramm-Kandidaten liegen bei `60*sr/hop / k`. Der Abstand zum
    Nachbarn betraegt relativ rund `1/(k-1)`. Deckt die Feinsuche weniger ab,
    entstehen Tempi, die der Schaetzer strukturell nie erreichen kann - siehe
    die Herleitung bei TEMPO_REFINE_STEPS.
    """
    if bpm <= 0.0:
        return TEMPO_REFINE_REL_MIN
    const = 60.0 * float(sr) / HOP_LENGTH
    k = const / bpm
    if k <= 2.0:
        return max(TEMPO_REFINE_REL_MIN, 0.5)
    return max(TEMPO_REFINE_REL_MIN, 1.0 / (k - 1.0))


def _refine(
    envelope: np.ndarray, times: np.ndarray, bpm: float, span: float,
    sr: int = 22050,
) -> tuple[float, float, float]:
    """Tempo eng nachoptimieren. Liefert (bpm, anchor_s, contrast)."""
    best = (bpm, 0.0, 0.0)
    rel = _refine_span(bpm, sr)
    grid = np.linspace(
        bpm * (1.0 - rel),
        bpm * (1.0 + rel),
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
    tempo_range: Optional[tuple[float, float]] = None,
) -> BeatGrid:
    """Schaetzt Tempo und Anker eines Beatgrids.

    Args:
        y: Monosignal.
        sr: Abtastrate.
        kick_times: Unabhaengig gewonnene Kick-Zeitpunkte. Ohne sie wird das
            Tempo nicht auf Oktavfehler geprueft - der haeufigste Fehlerfall.
        tempo_range: Suchbereich in BPM. Ohne Angabe gilt `TEMPO_RANGE`, das
            auf das Material dieses Projekts eingestellt ist (Psy-/Progressive
            -Trance, 136-145 BPM). Wer anderes Material analysiert - DnB,
            Footwork, langsamen HipHop - muss ihn hier setzen; ein zu weiter
            Bereich kostet nachweislich Genauigkeit (35 % gegen 55 %).

    Returns:
        Ein `BeatGrid`. `status` ist ``"plausible"``, wenn der Kontrast die
        Schwelle erreicht UND die Kick-Gegenprobe (sofern gelaufen) das
        Zufallsniveau uebersteigt; sonst ``"suspect"``, bei zu kurzem oder
        stillem Material ``"unavailable"``. Ein wegen der Gegenprobe
        abgestuftes Raster traegt das Suffix ``_below_chance`` im `method`-Feld.
    """
    import librosa

    _low, _high = tempo_range or TEMPO_RANGE
    envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH)
    if envelope.size < 16 or float(np.mean(envelope)) <= 0.0:
        return BeatGrid(0.0, 0.0, 0.0, "onset_envelope_empty", "unavailable")

    times = librosa.times_like(envelope, sr=sr, hop_length=HOP_LENGTH)
    span = float(times[-1])

    scored: list[tuple[float, float, float]] = []
    for candidate in _tempo_candidates(envelope, sr, tempo_range):
        refined = _refine(envelope, times, candidate, span, sr)
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
        tolerance = _kick_tolerance(sr)
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
            if not (_low <= trial_bpm <= _high):
                continue
            trial = _refine(envelope, times, trial_bpm, span, sr)
            if trial[2] <= 0.0:
                continue
            grid = BeatGrid(trial[0], trial[1], trial[2], "", "").beat_times(0.0, span)
            trial_recall, trial_precision = _kick_agreement(grid, kicks, tolerance)
            # Ein Nullergebnis wurde vorher UEBERSPRUNGEN. Traf keine Oktave
            # auch nur einen Kick, blieb `recall`/`precision` deshalb `None`,
            # und das Raster ging ungeprueft als `plausible` durch - der
            # ungueenstigste Fall wurde als der beste ausgegeben. Ein
            # Nullergebnis ist ein Messwert und wird als solcher gefuehrt.
            denominator = trial_recall + trial_precision
            score = (
                0.0 if denominator <= 0.0
                else 2.0 * trial_recall * trial_precision / denominator
            )
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

    # Status: Kontrast ALLEIN reicht nicht.
    #
    # Vorher entschied nur der Kontrast. An der echten Datei (544 s, 143 BPM
    # laut Auszeichnung) lieferte das: 94,67 BPM, Kontrast 4,44, Trefferquote
    # 0,0339, Praezision 0,0349 - und Status `plausible`. Der Kontrast misst
    # nur, ob EIN Puls im Onset-Verlauf steht; ob es derselbe Puls ist wie der
    # der Kicks, sagt er nicht. Ein Raster, dessen unabhaengige Gegenprobe
    # unter der Zufallserwartung liegt, behauptet mit `plausible` etwas, das
    # seine eigenen Messwerte widerlegen.
    #
    # Die Schwelle ist nicht abgelesen, sie IST die Nullhypothese: bei
    # gleichverteilter Phase trifft schon der Zufall `2*Toleranz/Abstand`
    # (siehe `_chance_rates`). Bewusst nicht mehr: eine hoehere, an Material
    # kalibrierte Schwelle waere hier nicht zu rechtfertigen - die Messung in
    # docs/measurements/2026-08-31-kick-gegenprobe-befund.md hat an 127
    # Fenstern gezeigt, dass die Kick-Gegenprobe korrekte von falschen Tempi
    # NICHT trennt (Median 0,433 gegen 0,336). Unterhalb des Zufallsniveaus
    # ist die Aussage dagegen eindeutig: dort liegt kein schwaches Signal,
    # dort liegt ein systematischer Widerspruch.
    chance_recall = chance_precision = None
    status = "plausible" if contrast >= GRID_CONTRAST_MIN else "suspect"
    if status == "suspect":
        logger.info(
            "Beatgrid: Kontrast %.2f unter %.2f - Raster als suspect gemeldet",
            contrast, GRID_CONTRAST_MIN,
        )
    elif recall is not None and precision is not None:
        chance_recall, chance_precision = _chance_rates(
            bpm, int(kicks.size), span, _kick_tolerance(sr)
        )
        if recall <= chance_recall or precision <= chance_precision:
            status = "suspect"
            method = f"{method}_below_chance"
            logger.info(
                "Beatgrid: Gegenprobe unter Zufallsniveau - Trefferquote %.4f "
                "(Zufall %.4f), Praezision %.4f (Zufall %.4f) bei Kontrast "
                "%.2f. Raster als suspect gemeldet.",
                recall, chance_recall, precision, chance_precision, contrast,
            )

    return BeatGrid(
        bpm=round(bpm, 4),
        anchor_s=round(anchor, 5),
        contrast=round(contrast, 4),
        method=method,
        status=status,
        kick_recall=None if recall is None else round(recall, 4),
        kick_precision=None if precision is None else round(precision, 4),
        kick_recall_chance=(
            None if chance_recall is None else round(chance_recall, 4)
        ),
        kick_precision_chance=(
            None if chance_precision is None else round(chance_precision, 4)
        ),
        octave_checked=octave_checked,
        candidates=[
            {"bpm": round(b, 3), "contrast": round(c, 4)} for b, _, c in scored[:TEMPO_CANDIDATES]
        ],
    )
