# T003 – Referenzmessung gegen rekordbox und eine konstruierte Mix-Referenz (2026-09-30)

Parallel-Session-Notiz: stammt aus der zweiten Claude-Sitzung. Nur lesend
gegen Nutzerdaten; alle Ausgaben liegen in
`%TEMP%\pb00035-t003-rekordbox-20260930_084402\`.

## Gefundene unabhängige Referenz

`F:\pioneer_xml\rekordbox.xml` (SHA-256 `2068CF35…EEF396`): rekordbox-Export der
Bibliothek des Nutzers, 2.476 Titel, **alle** mit Tonart (`Tonality`, Camelot),
Tempo und Beatgrid-Anker (`TEMPO Inizio/Bpm`), 2.467 mit Cue-Punkten, dazu
Wiedergabelisten (u. a. `18.12.2025`, `Ritual`, `Nov. 2024`). Pfade zeigen auf
`D:/…`; die Dateien liegen heute unter `F:/…` (Remap `D:/=F:/`).

rekordbox ist ein vom PB-Studio-Code unabhängiger Analysator. Die Werte sind
**keine** menschlich geprüften Labels, aber zeitcodierte, unabhängige Referenzen.
CUE-Dateien, Tracklisten mit Zeitmarken oder NML/Traktor-Daten wurden auf C:, D:,
E:, F: nicht gefunden (Scan von C:/D: vollständig, E:/F: per `dir /s`).

## A. Einzeltitel: Tonart, Tempo, Beat-Phase (40 Titel)

Werkzeug `scripts/dev/t003_rekordbox_reference_eval.py`; Stichprobe jeder
n-te vorhandene Titel; Produktionscode `KeyDetector.detect_key` (ganzer Titel,
22,05 kHz mono) und `estimate_beat_grid` (Ausschnitt 60–180 s).
`results.json` SHA-256 `B4A4B4A8…E370D4`.

| Messgröße | Ergebnis |
|---|---|
| Tonart exakt | **25/40 (62,5 %)** |
| Tonart MIREX-Mittel | 0,67 |
| Fehlerarten | 9 × Dur/Moll vertauscht (parallel), 6 × andere, 0 × Quinte/relativ |
| Tempo innerhalb 2 % | **38/40** |
| Tempofehler | 2 × 110,36 statt 138 (Faktor 0,8 – kein Oktavfehler) |
| Beat-Phase (Anteil Beats ≤ 70 ms am rekordbox-Raster) | Median 0,37; **bimodal: 19 Titel ≥ 0,9, 19 Titel ≤ 0,1** |

Deutung: Tempo stimmt fast immer, die Phase liegt aber bei rund der Hälfte der
Titel genau eine halbe Schlagperiode daneben (Raster auf dem Off-Beat –
typisch für Psytrance-Rollbass). Die Tonart verwechselt vor allem Dur und Moll.

## B. Mix-Grenzen: konstruierte Referenz mit bekannten Zeitmarken

Werkzeug `scripts/dev/t003_build_reference_mix.py`. Die ersten 10 vorhandenen
Titel der rekordbox-Liste `18.12.2025` (Melodic House & Techno / Progressive,
124–143 BPM laut Label) mit 16-s-Equal-Power-Crossfades verbunden.
Grenzen = Crossfade-Mitten, **exakt durch Konstruktion**:
354,880 · 637,699 · 932,949 · 1205,336 · 1528,216 · 1931,002 · 2437,242 · 2831,565 · 3278,285 s.
Mix 3.546,0 s (ffprobe 3.545,97 s), FLAC SHA-256 `307E0ACD…70D4`.

Produktionsprüfer `scripts/verify_subtrack_detection.py` (Toleranz 15 s, Ziel F1 ≥ 0,65):

- erkannt 23 Grenzen in 24,0 s; Referenz 9
- TP 6 · FP 17 · FN 3 → Precision 0,261 · Recall 0,667 · **F1 0,375 → FAIL**

## Bewertung für T003

Die bisher fehlende reale Genauigkeitsmessung ist jetzt möglich und
durchgeführt. Ergebnis: **nicht bestanden** – Übersegmentierung der Mix-Grenzen,
Dur/Moll-Verwechslung, halbe-Periode-Phasenfehler. T003 bleibt offen, aber nicht
mehr wegen fehlender Labels, sondern wegen gemessener Defekte.

Grenzen der Aussage: konstruierte Crossfades sind einfacher als echte DJ-Übergänge
(keine EQ-/Filterfahrten, keine Loops); rekordbox-Werte können selbst irren.
Ein echter DJ-Mitschnitt liegt vor (`F:\BD@LoRa 05.09.25 JJ & Crusty\`, 6 × 1 h),
aber ohne Tracklist mit Zeiten.
