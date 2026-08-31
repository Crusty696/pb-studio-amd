"""Segmentiertes Beatgrid fuer DJ-Mixe: mehrere Grid-Abschnitte statt eines Tempos.

## Warum

Ein einzelnes Tempo ueber eine ganze Datei ist bei einem Mix nicht ungenau,
sondern strukturell falsch: an jedem Uebergang wechseln Tempo UND Phase, und
einzelne Tracks laufen hoch- oder heruntergepitcht.

Gemessen an 800 Segmenten aus 20 echten DJ-Mixen
(`docs/measurements/2026-08-31-mix-tempo-drift.json`), Guetemass ist der
phasennormierte Kontrast:

    ein Tempo pro Mix       Median 1,248   sitzt in 19 % der Segmente
    Tempo je 30-s-Segment   Median 3,530   sitzt in 95 % der Segmente

Segmentierung gewinnt in 90 % der Segmente, Median-Gewinn +2,04. Die
Tempo-Streuung innerhalb eines Mixes betraegt im Median 33 % (90-Perzentil
gegen 10-Perzentil), bei 12 von 20 Mixen ueber 5 %.

Ein Kontrast von 1,248 bedeutet: das globale Raster hebt sich kaum von einer
zufaellig gewaehlten Phase ab. Es traegt also praktisch keine Information.

## Wie

Drei Schritte:

1. **Fenstern** - die Datei wird in Abschnitte von `SEGMENT_SECONDS` zerlegt,
   fuer jeden wird eigenstaendig ein Grid geschaetzt (`estimate_beat_grid`),
   ohne Wissen ueber die Nachbarn.
2. **Verketten** - benachbarte Fenster werden zusammengefasst, wenn ihr Tempo
   uebereinstimmt UND die Phase durchgehend ist. Der zweite Teil ist der
   schwierigere: zwei Fenster koennen dasselbe Tempo tragen und trotzdem
   gegeneinander verschoben sein. Geprueft wird deshalb, ob das Raster des
   laufenden Abschnitts am Beginn des naechsten Fensters noch auf dessen
   eigenem Anker sitzt (siehe `_phase_continues`).
3. **Ausgeben** - eine Liste von `GridSegment` statt eines einzelnen Wertes.

## Warum nicht die vorhandenen Subtrack-Grenzen

`subtrack_detector.py` liefert bereits Mix-Grenzen. Sie werden hier bewusst
NICHT als Grundlage genommen: 20 % ihres Fusionsgewichts stammt aus
`_tempo_drift`, das `librosa.beat_track` auf 8-Sekunden-Fenstern aufruft. Ein
Oktav-Flip zwischen zwei solchen Fenstern (143,6 gegen 71,8) erzeugt eine
Drift-Spitze, die als Trackgrenze gewertet wird - die Grenzen haengen also am
selben Schaetzer, dessen Schwaeche dieses Modul umgehen soll.

Die Grenzen ergeben sich hier stattdessen aus dem Tempo selbst. Das macht sie
zu einer *unabhaengigen* Gegenprobe fuer die Subtrack-Erkennung, statt zu
deren Abhaengigkeit.

## Grenzen dieses Moduls

- Die Segmentgrenzen liegen auf dem Fensterraster, nicht auf dem exakten
  Uebergang. Ein Trackwechsel mitten in einem Fenster verunreinigt dieses eine
  Fenster; er wird nicht auf die Millisekunde datiert.
- Ein Uebergang, in dem zwei Tracks gleichzeitig laufen (das uebliche
  Beatmatching), hat kein eindeutiges Tempo. Solche Fenster bekommen einen
  niedrigen Kontrast und werden als eigener, kurzer Abschnitt sichtbar - sie
  werden nicht kuenstlich einem der beiden Nachbarn zugeschlagen.
- Das Modul sagt nichts darueber, WELCHER Track spielt. Es misst Tempo und
  Phase, nicht Identitaet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Optional

import numpy as np

from pb_studio.audio.beat_grid import BeatGrid, estimate_beat_grid

logger = logging.getLogger(__name__)

# Fensterlaenge fuer die Einzelschaetzung.
#
# Gemessen: bei 8 s sitzen 73 % der Raster, bei 30 s 66 %, bei 120 s 71 % -
# die Spanne ist fuer die Guete fast bedeutungslos (siehe
# docs/measurements/2026-08-30-beatgrid-machbarkeit.md). Entscheidend ist hier
# etwas anderes: das Fenster muss kurz genug sein, dass ein Trackwechsel
# hoechstens EIN Fenster verunreinigt, und lang genug, dass die Tempo-Schaetzung
# stabil bleibt. 30 s entspricht bei 140 BPM rund 70 Beats bzw. 17 Takten.
SEGMENT_SECONDS = 30.0

# Zulaessiger Phasenversatz beim Verketten, als Bruchteil eines Beat-Intervalls.
# Ein Achtel Beat ist bei 140 BPM rund 54 ms - unterhalb dessen, was als
# Versatz hoerbar waere, und oberhalb der Frame-Quantisierung von 23 ms.
PHASE_MATCH_BEATS = 0.125


def _tempo_match_rel(bpm: float, segment_seconds: float) -> float:
    """Tempotoleranz, die zur Phasentoleranz passt.

    Die beiden Bedingungen der Verkettung - gleiches Tempo und durchgehende
    Phase - duerfen sich nicht widersprechen. Eine Tempoabweichung laeuft
    ueber ein Fenster linear als Phasendrift auf:

        Drift [Beats] = Fensterlaenge / Beat-Intervall x Tempoabweichung

    Erste Fassung setzte beide Werte unabhaengig (0,5 % und 0,125 Beats). Bei
    138 BPM und 30-s-Fenstern sind das 69 Beats: die erlaubte Tempoabweichung
    erzeugt dann 0,345 Beats Drift, also fast das Dreifache dessen, was die
    Phasenpruefung zulaesst. Fast jedes Fensterpaar, das die Tempopruefung
    bestand, fiel danach zwangslaeufig an der Phasenpruefung durch - die
    Verkettung brach nicht an Trackwechseln, sondern an der Parametrierung.
    Gemessen an sechs Mixen blieb die Abschnittszahl deshalb bei 26 bis 86,
    obwohl dort 15 bis 25 Tracks laufen.

    Die Tempotoleranz wird daher aus der Phasentoleranz abgeleitet. Damit ist
    die Phasenpruefung die eigentliche Pruefung, und die Tempopruefung nur
    eine billige Vorfilterung, die ihr nicht widerspricht.
    """
    if bpm <= 0 or segment_seconds <= 0:
        return 0.002
    beats_per_window = segment_seconds / (60.0 / bpm)
    if beats_per_window <= 0:
        return 0.002
    return PHASE_MATCH_BEATS / beats_per_window

# Ein Abschnitt unter dieser Laenge wird nicht eigenstaendig ausgewiesen,
# sondern dem besser passenden Nachbarn zugeschlagen. Kuerzere Abschnitte
# entstehen fast nur an Uebergaengen und beschreiben keine eigene Passage.
MIN_SEGMENT_SECONDS = 45.0

# Unterhalb dieses Kontrasts gilt ein Fenster als nicht tragend. Derselbe
# Wert wie `GRID_CONTRAST_MIN` im Einzelschaetzer.
SEGMENT_CONTRAST_MIN = 2.0


@dataclass
class GridSegment:
    """Ein Grid-Abschnitt: Gueltigkeitsbereich plus die Regel, die dort gilt."""

    start_s: float
    end_s: float
    bpm: float
    anchor_s: float
    contrast: float
    status: str
    window_count: int

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def beat_times(self) -> np.ndarray:
        """Beat-Positionen dieses Abschnitts - aus der Regel erzeugt."""
        if self.bpm <= 0:
            return np.zeros(0)
        interval = 60.0 / self.bpm
        first = self.anchor_s + np.ceil(
            (self.start_s - self.anchor_s) / interval
        ) * interval
        return np.arange(first, self.end_s, interval)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration_s"] = round(self.duration_s, 3)
        return data


# Vielfache, in denen ein Schaetzfehler typischerweise auftritt. An 800
# Segmenten aus 20 Mixen gemessen liegen 97,2 % aller Segmenttempi auf einem
# dieser Verhaeltnisse zum Median der Datei:
#
#     1     77,9 %      2/3   10,0 %      3/2    5,5 %
#     2      1,9 %      4/3    1,4 %      3/4    0,6 %
#     kein Vielfaches   2,8 %
#
# Faltet man sie heraus, faellt die Tempo-Spannweite je Mix von 33,3 % auf
# 0,1 %. Die Mixe sind also tempostabil - es ist der Schaetzer, der zwischen
# Vielfachen springt. Ohne diese Faltung zerreisst die Verkettung eine
# durchgehende Passage an jedem solchen Sprung: ein 92-Minuten-Mix bekam
# 43 Abschnitte, wo 15 bis 20 Tracks laufen.
CONSENSUS_FACTORS = (1.0, 2.0, 0.5, 1.5, 2.0 / 3.0, 3.0, 1.0 / 3.0, 4.0 / 3.0, 0.75)

# Ein Fenstertempo gilt als Vielfaches des Konsenses, wenn es nach Division
# durch den Faktor so nah am Konsens liegt. Grosszuegiger als
# der Verkettungstoleranz (`_tempo_match_rel`), weil hier ueber die ganze
# Datei gemittelt wird und die
# Einzelschaetzung streut.
CONSENSUS_MATCH_REL = 0.02


def _consensus_tempo(windows: list[tuple[float, float, "BeatGrid"]]) -> float:
    """Das dominante Tempo der Datei, gewichtet nach Kontrast.

    Nicht der schlichte Median: ein Fenster mit hohem Kontrast traegt mehr
    Information als eines aus einer Breakdown-Passage. Gewichtet wird mit dem
    Kontrast oberhalb der Tragfaehigkeitsschwelle, damit nicht tragende
    Fenster den Konsens nicht verschieben.
    """
    tempi, weights = [], []
    for _, _, grid in windows:
        if grid.bpm <= 0:
            continue
        tempi.append(grid.bpm)
        weights.append(max(0.0, grid.contrast - SEGMENT_CONTRAST_MIN) + 0.1)
    if not tempi:
        return 0.0

    # Erst grob auf ein gemeinsames Oktavband falten, sonst mittelt man
    # 69 und 138 zu einem Wert, den keines der Fenster traegt.
    folded = []
    reference = float(np.median(tempi))
    for value in tempi:
        best = min(
            CONSENSUS_FACTORS,
            key=lambda factor: abs(value / factor - reference) / reference,
        )
        folded.append(value / best)
    order = np.argsort(folded)
    values = np.asarray(folded)[order]
    cumulative = np.cumsum(np.asarray(weights)[order])
    # Gewichteter Median: robuster gegen einzelne Ausreisser als der
    # gewichtete Mittelwert.
    return float(values[np.searchsorted(cumulative, cumulative[-1] / 2.0)])


def _fold_to_consensus(bpm: float, consensus: float) -> tuple[float, float]:
    """Zieht ein Fenstertempo auf das naechste Vielfache des Konsenses.

    Returns:
        ``(gefaltetes_bpm, angewandter_faktor)``. Passt kein Faktor innerhalb
        von CONSENSUS_MATCH_REL, bleibt das Tempo unveraendert - dann ist es
        kein Vielfachfehler, sondern eine echte Abweichung, und die darf nicht
        wegdefiniert werden.
    """
    if bpm <= 0 or consensus <= 0:
        return bpm, 1.0
    best_factor, best_error = 1.0, float("inf")
    for factor in CONSENSUS_FACTORS:
        candidate = bpm / factor
        error = abs(candidate - consensus) / consensus
        if error < best_error:
            best_error, best_factor = error, factor
    if best_error > CONSENSUS_MATCH_REL:
        return bpm, 1.0
    return bpm / best_factor, best_factor


def _best_phase(
    envelope: np.ndarray,
    times: np.ndarray,
    bpm: float,
    start_s: float,
    end_s: float,
    steps: int = 48,
) -> tuple[float, float]:
    """Beste Phase eines gegebenen Tempos im Zeitfenster.

    Gebraucht nach dem Falten auf ein Vielfaches: das neue Tempo braucht eine
    eigene Phase, der Anker des alten Rasters passt nur zufaellig.

    Returns:
        ``(anchor_s, contrast)`` - der Kontrast ist phasennormiert (bester
        Phasenscore geteilt durch den Mittelwert ueber alle Phasen), also
        unabhaengig von der Rasterdichte.
    """
    if bpm <= 0 or end_s <= start_s:
        return 0.0, 0.0
    interval = 60.0 / bpm
    overall = float(np.mean(envelope))
    if overall <= 0:
        return 0.0, 0.0

    scores = np.empty(steps, dtype=np.float64)
    for step in range(steps):
        offset = interval * step / steps
        positions = np.arange(start_s + offset, end_s, interval)
        if positions.size < 8:
            return 0.0, 0.0
        scores[step] = float(np.mean(np.interp(positions, times, envelope)) / overall)

    mean = float(np.mean(scores))
    if mean <= 0:
        return 0.0, 0.0
    best = int(np.argmax(scores))
    return start_s + interval * best / steps, float(scores[best] / mean)


def _phase_continues(
    current_bpm: float, current_anchor: float, next_anchor: float
) -> bool:
    """Setzt sich das laufende Raster im naechsten Fenster fort?

    Gleiches Tempo allein genuegt nicht: zwei Fenster koennen dasselbe Tempo
    tragen und trotzdem gegeneinander verschoben sein - dann sind es zwei
    Raster, kein durchgehendes. Geprueft wird der Abstand der beiden Anker
    modulo Beat-Intervall.
    """
    if current_bpm <= 0:
        return False
    interval = 60.0 / current_bpm
    offset = abs(next_anchor - current_anchor) % interval
    # Der Versatz kann auch knapp UNTER einem vollen Intervall liegen.
    offset = min(offset, interval - offset)
    return offset <= PHASE_MATCH_BEATS * interval


def _tempo_matches(a: float, b: float, segment_seconds: float) -> bool:
    """Vorfilterung: liegen zwei Fenstertempi nah genug beieinander?

    Die Schranke haengt an der Fensterlaenge - siehe `_tempo_match_rel`.
    """
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= _tempo_match_rel(max(a, b), segment_seconds)


def _merge_short_segments(segments: list[GridSegment]) -> list[GridSegment]:
    """Zu kurze Abschnitte dem passenderen Nachbarn zuschlagen.

    Kurze Abschnitte entstehen fast nur an Uebergaengen, wo zwei Tracks
    gleichzeitig laufen. Sie als eigene Passage auszuweisen taeuscht eine
    Genauigkeit vor, die die Messung nicht hergibt.
    """
    if len(segments) <= 1:
        return segments

    result = list(segments)
    changed = True
    while changed and len(result) > 1:
        changed = False
        for index, segment in enumerate(result):
            if segment.duration_s >= MIN_SEGMENT_SECONDS:
                continue
            previous = result[index - 1] if index > 0 else None
            following = result[index + 1] if index + 1 < len(result) else None
            # An den besseren Nachbarn anhaengen: hoeherer Kontrast gewinnt,
            # bei Gleichstand der laengere.
            target_index: Optional[int] = None
            if previous is not None and following is not None:
                target_index = (
                    index - 1
                    if (previous.contrast, previous.duration_s)
                    >= (following.contrast, following.duration_s)
                    else index + 1
                )
            elif previous is not None:
                target_index = index - 1
            elif following is not None:
                target_index = index + 1
            if target_index is None:
                continue

            target = result[target_index]
            merged = GridSegment(
                start_s=min(target.start_s, segment.start_s),
                end_s=max(target.end_s, segment.end_s),
                bpm=target.bpm,
                anchor_s=target.anchor_s,
                contrast=target.contrast,
                status=target.status,
                window_count=target.window_count + segment.window_count,
            )
            low, high = sorted((index, target_index))
            result = result[:low] + [merged] + result[high + 1:]
            changed = True
            break
    return result


def _chain_windows(
    windows: list[tuple[float, float, BeatGrid]], segment_seconds: float
) -> list[GridSegment]:
    """Fasst benachbarte Fenster zusammen, deren Raster durchgeht.

    Zwei Bedingungen, die zusammenpassen muessen: gleiches Tempo (billige
    Vorfilterung) und durchgehende Phase (die eigentliche Pruefung). Siehe
    `_tempo_match_rel` - werden beide Toleranzen unabhaengig gesetzt,
    widersprechen sie sich und die Verkettung bricht ueberall.
    """
    if not windows:
        return []

    segments: list[GridSegment] = []
    start_s, end_s, current = windows[0]
    count = 1
    contrasts = [current.contrast]

    def flush() -> None:
        mean_contrast = float(np.mean(contrasts))
        segments.append(
            GridSegment(
                start_s=round(start_s, 3), end_s=round(end_s, 3),
                bpm=round(current.bpm, 4), anchor_s=round(current.anchor_s, 5),
                contrast=round(mean_contrast, 4),
                status=("plausible" if mean_contrast >= SEGMENT_CONTRAST_MIN
                        else "suspect"),
                window_count=count,
            )
        )

    # Geprueft wird gegen den ANFANG des laufenden Abschnitts, nicht gegen das
    # zuletzt angehaengte Fenster.
    #
    # Der Unterschied ist gemessen, nicht theoretisch. Die Variante
    # "Fenster gegen Fenster" wurde an sechs Mixen ausprobiert: sie liefert
    # weniger Abschnitte (50->47, 88->79, 35->31), aber durchgehend
    # schlechtere Passung (Kontrast 2,58->2,34, 2,08->1,81, 2,85->2,50).
    #
    # Grund: ein Abschnitt hat EIN Grid, und das muss ueber seine ganze Laenge
    # gelten. Prueft man nur den jeweils naechsten Uebergang, akkumuliert die
    # Drift, der Abschnitt waechst - und sein einziges Tempo passt am Ende
    # nicht mehr auf die Musik. Dass die Toleranz ueber viele Fenster
    # "aufgebraucht" wird, ist deshalb kein Fehler der Pruefung, sondern ihre
    # Aufgabe: passt das Grid am Ende nicht mehr, beginnt ein neuer Abschnitt.
    for window_start, window_end, grid in windows[1:]:
        same_tempo = _tempo_matches(current.bpm, grid.bpm, segment_seconds)
        same_phase = _phase_continues(current.bpm, current.anchor_s, grid.anchor_s)
        if same_tempo and same_phase:
            end_s = window_end
            count += 1
            contrasts.append(grid.contrast)
            continue
        flush()
        start_s, end_s, current = window_start, window_end, grid
        count = 1
        contrasts = [grid.contrast]

    flush()
    return segments


def segment_beat_grids(
    y: np.ndarray,
    sr: int,
    *,
    kick_times: Optional[list[float]] = None,
    segment_seconds: float = SEGMENT_SECONDS,
) -> list[GridSegment]:
    """Schaetzt ein Beatgrid je Abschnitt und fasst gleiche Abschnitte zusammen.

    Args:
        y: Monosignal der gesamten Datei.
        sr: Abtastrate.
        kick_times: Unabhaengig gewonnene Kick-Zeitpunkte ueber die GESAMTE
            Datei. Sie werden je Fenster zugeschnitten und relativ zum
            Fensteranfang uebergeben, damit die Oktavpruefung im
            Einzelschaetzer greift.
        segment_seconds: Fensterlaenge.

    Returns:
        Abschnitte in zeitlicher Reihenfolge. Bei zu kurzem Material eine
        Liste mit genau einem Abschnitt ueber die volle Laenge; bei leerem
        Signal eine leere Liste.
    """
    if y.size == 0 or sr <= 0:
        return []

    duration = float(y.size) / float(sr)
    window_samples = int(segment_seconds * sr)
    if window_samples <= 0 or duration <= segment_seconds * 1.5:
        # Zu kurz zum Segmentieren: ein Abschnitt ueber alles. Ehrlicher als
        # eine Segmentierung, die auf einem einzigen Fenster beruht.
        grid = estimate_beat_grid(y, sr, kick_times=kick_times)
        return [
            GridSegment(
                start_s=0.0, end_s=round(duration, 3), bpm=grid.bpm,
                anchor_s=grid.anchor_s, contrast=grid.contrast,
                status=grid.status, window_count=1,
            )
        ]

    all_kicks = np.asarray(sorted(float(k) for k in (kick_times or [])), dtype=np.float64)

    windows: list[tuple[float, float, BeatGrid]] = []
    offset = 0.0
    while offset + segment_seconds <= duration + 1e-9:
        start = int(offset * sr)
        end = min(start + window_samples, y.size)
        chunk = y[start:end]
        if chunk.size < sr * 5:
            break
        window_end = offset + float(chunk.size) / sr

        # Kicks auf das Fenster zuschneiden und auf dessen Nullpunkt beziehen -
        # der Einzelschaetzer rechnet relativ zum uebergebenen Signal.
        local_kicks: Optional[list[float]] = None
        if all_kicks.size:
            selected = all_kicks[(all_kicks >= offset) & (all_kicks < window_end)]
            local_kicks = (selected - offset).tolist()

        try:
            grid = estimate_beat_grid(chunk, sr, kick_times=local_kicks)
        except Exception as exc:  # noqa: BLE001 - ein Fenster darf den Lauf nicht stoppen
            logger.warning("Beatgrid-Schaetzung fuer Fenster bei %.1f s fehlgeschlagen: %s",
                           offset, exc)
            offset += segment_seconds
            continue

        # Anker zurueck in absolute Zeit.
        absolute = BeatGrid(
            bpm=grid.bpm, anchor_s=offset + grid.anchor_s, contrast=grid.contrast,
            method=grid.method, status=grid.status, kick_recall=grid.kick_recall,
            kick_precision=grid.kick_precision, octave_checked=grid.octave_checked,
        )
        windows.append((offset, window_end, absolute))
        offset += segment_seconds

    if not windows:
        return []

    # Vielfachfehler ueber die ganze Datei ausgleichen, BEVOR verkettet wird.
    #
    # Ohne diesen Schritt zerreisst jeder Sprung zwischen 69 und 138 BPM eine
    # durchgehende Passage. An sechs echten Mixen gemessen entstanden so
    # 29 bis 86 Abschnitte je Datei, obwohl dort 15 bis 20 Tracks laufen; die
    # erkannten Tempi zeigten das Muster offen (69, 138, 138, 138 / 68, 205,
    # 137, 137 / 136, 204, 136, 68).
    #
    # Der Konsens ist ein gewichteter Median ueber alle Fenster. Er wird nur
    # angewandt, wo ein Fenster tatsaechlich auf einem Vielfachen liegt -
    # eine echte Tempoabweichung bleibt unangetastet und wird weiterhin als
    # eigener Abschnitt sichtbar.
    consensus = _consensus_tempo(windows)
    folded_count = 0
    if consensus > 0:
        # Huellkurve der ganzen Datei - gebraucht, um nach dem Falten die
        # Phase neu zu bestimmen. Ein gefaltetes Tempo mit altem Anker sitzt
        # falsch: bei einer Halbierung faellt das nicht auf (jeder Beat des
        # langsameren Rasters ist auch einer des schnelleren), bei Faktor 1,5
        # dagegen verrutscht das Raster. Erste Fassung dieser Faltung hat den
        # Anker unveraendert uebernommen; an sechs Mixen gemessen sank der
        # Kontrast dadurch von 2,24 auf 1,96 bzw. von 2,18 auf 1,97.
        import librosa

        envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
        times = librosa.times_like(envelope, sr=sr, hop_length=512)

        adjusted: list[tuple[float, float, BeatGrid]] = []
        for window_start, window_end, grid in windows:
            new_bpm, factor = _fold_to_consensus(grid.bpm, consensus)
            if factor != 1.0 and new_bpm > 0:
                folded_count += 1
                anchor, contrast = _best_phase(
                    envelope, times, new_bpm, window_start, window_end
                )
                grid = BeatGrid(
                    bpm=new_bpm,
                    anchor_s=anchor if contrast > 0 else grid.anchor_s,
                    contrast=contrast if contrast > 0 else grid.contrast,
                    method=f"{grid.method}_folded", status=grid.status,
                    kick_recall=grid.kick_recall, kick_precision=grid.kick_precision,
                    octave_checked=grid.octave_checked,
                )
            adjusted.append((window_start, window_end, grid))
        windows = adjusted
        if folded_count:
            logger.info(
                "Vielfach-Konsens %.2f BPM: %d von %d Fenstern gefaltet",
                consensus, folded_count, len(windows),
            )

    segments = _chain_windows(windows, segment_seconds)
    merged = _merge_short_segments(segments)
    logger.info(
        "Segmentiertes Beatgrid: %d Fenster -> %d Abschnitte (nach Zusammenfassen %d), "
        "Tempi %s",
        len(windows), len(segments), len(merged),
        ", ".join(f"{s.bpm:.1f}" for s in merged[:8]),
    )
    return merged


def segment_beat_grids_from_file(
    audio_path: str,
    *,
    sr: int = 22050,
    kick_times: Optional[list[float]] = None,
    segment_seconds: float = SEGMENT_SECONDS,
    max_windows: int = 400,
) -> list[GridSegment]:
    """Wie `segment_beat_grids`, laedt aber fensterweise statt am Stueck.

    Genau fuer den Fall gebaut, fuer den die Segmentierung ueberhaupt
    gebraucht wird: lange DJ-Mixe. `segment_beat_grids` verlangt das gesamte
    Signal im Speicher, und das ist bei genau diesen Dateien das Problem -

        60 min bei 22050 Hz   =  318 MB float32
        90 min                =  476 MB
       188 min                =  995 MB

    Das ist dasselbe OOM-Szenario, gegen das der `StreamingAudioAnalyzer`
    gebaut wurde (Audit-Befund H-5). Diese Fassung haelt nur ein Fenster
    (30 s = 2,6 MB) plus die Huellkurven aller Fenster im Speicher; eine
    30-s-Huellkurve ist bei hop=512 rund 1300 Werte, also 5 KB - selbst
    400 Fenster kosten damit nur 2 MB.

    Args:
        audio_path: Pfad zur Audiodatei.
        sr: Zielabtastrate.
        kick_times: Kick-Zeitpunkte ueber die gesamte Datei, absolut.
        segment_seconds: Fensterlaenge.
        max_windows: Obergrenze, damit eine unerwartet lange Datei nicht
            unbemerkt in eine sehr lange Laufzeit laeuft.

    Returns:
        Abschnitte in zeitlicher Reihenfolge, leer bei unlesbarer Datei.
    """
    import librosa

    try:
        duration = float(librosa.get_duration(path=str(audio_path)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Dauer von %s nicht bestimmbar: %s", audio_path, exc)
        return []
    if duration <= 0:
        return []

    all_kicks = np.asarray(
        sorted(float(k) for k in (kick_times or [])), dtype=np.float64
    )

    windows: list[tuple[float, float, BeatGrid]] = []
    # Huellkurven je Fenster aufheben - gebraucht, falls nach dem
    # Vielfach-Konsens die Phase neu bestimmt werden muss. Billig genug,
    # um ein zweites Laden der Datei zu ersparen.
    envelopes: list[tuple[np.ndarray, np.ndarray]] = []

    offset = 0.0
    while offset + segment_seconds <= duration + 1e-9 and len(windows) < max_windows:
        try:
            chunk, actual_sr = librosa.load(
                str(audio_path), sr=sr, mono=True,
                offset=offset, duration=segment_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - ein Fenster darf den Lauf nicht stoppen
            logger.warning("Fenster bei %.1f s nicht ladbar: %s", offset, exc)
            offset += segment_seconds
            continue
        if chunk.size < actual_sr * 5:
            break
        window_end = offset + float(chunk.size) / actual_sr

        local_kicks: Optional[list[float]] = None
        if all_kicks.size:
            selected = all_kicks[(all_kicks >= offset) & (all_kicks < window_end)]
            local_kicks = (selected - offset).tolist()

        try:
            grid = estimate_beat_grid(chunk, actual_sr, kick_times=local_kicks)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Beatgrid fuer Fenster bei %.1f s fehlgeschlagen: %s",
                           offset, exc)
            offset += segment_seconds
            continue

        envelope = librosa.onset.onset_strength(
            y=chunk, sr=actual_sr, hop_length=512
        )
        times = librosa.times_like(envelope, sr=actual_sr, hop_length=512) + offset
        envelopes.append((envelope, times))

        windows.append((
            offset, window_end,
            BeatGrid(
                bpm=grid.bpm, anchor_s=offset + grid.anchor_s,
                contrast=grid.contrast, method=grid.method, status=grid.status,
                kick_recall=grid.kick_recall, kick_precision=grid.kick_precision,
                octave_checked=grid.octave_checked,
            ),
        ))
        del chunk
        offset += segment_seconds

    if not windows:
        return []

    consensus = _consensus_tempo(windows)
    folded = 0
    if consensus > 0:
        adjusted: list[tuple[float, float, BeatGrid]] = []
        for index, (window_start, window_end, grid) in enumerate(windows):
            new_bpm, factor = _fold_to_consensus(grid.bpm, consensus)
            if factor != 1.0 and new_bpm > 0:
                folded += 1
                envelope, times = envelopes[index]
                anchor, contrast = _best_phase(
                    envelope, times, new_bpm, window_start, window_end
                )
                grid = BeatGrid(
                    bpm=new_bpm,
                    anchor_s=anchor if contrast > 0 else grid.anchor_s,
                    contrast=contrast if contrast > 0 else grid.contrast,
                    method=f"{grid.method}_folded", status=grid.status,
                    kick_recall=grid.kick_recall,
                    kick_precision=grid.kick_precision,
                    octave_checked=grid.octave_checked,
                )
            adjusted.append((window_start, window_end, grid))
        windows = adjusted
        if folded:
            logger.info(
                "Vielfach-Konsens %.2f BPM: %d von %d Fenstern gefaltet",
                consensus, folded, len(windows),
            )

    segments = _chain_windows(windows, segment_seconds)
    merged = _merge_short_segments(segments)
    logger.info(
        "Segmentiertes Beatgrid (%s): %d Fenster -> %d Abschnitte, Tempi %s",
        audio_path, len(windows), len(merged),
        ", ".join(f"{s.bpm:.1f}" for s in merged[:8]),
    )
    return merged


def segments_as_payload(segments: list[GridSegment]) -> dict[str, Any]:
    """Antwortstruktur fuer die API - mit ehrlicher Zusammenfassung.

    `dominant_bpm` ist das Tempo des laengsten Abschnitts, nicht ein
    Mittelwert. Ein Mittelwert ueber mehrere Tracks waere eine Zahl, die in
    keinem Moment des Mixes gilt.
    """
    if not segments:
        return {"status": "unavailable", "method": "no_segments", "segments": []}

    longest = max(segments, key=lambda s: s.duration_s)
    tempi = sorted({round(s.bpm, 1) for s in segments})
    plausible = sum(1 for s in segments if s.status == "plausible")
    return {
        "status": "plausible" if plausible else "suspect",
        "method": "segmented_beat_grid",
        "segment_count": len(segments),
        "plausible_count": plausible,
        "dominant_bpm": round(longest.bpm, 4),
        "dominant_span_s": round(longest.duration_s, 3),
        "distinct_tempi": tempi,
        "segments": [s.as_dict() for s in segments],
    }
