# Segmentiertes Beatgrid für Mixe — Messbefund

**Stand:** 2026-08-31
**Modul:** `src/pb_studio/audio/beat_grid_segments.py`
**Werkzeug:** `scripts/dev/measure_mix_tempo_drift.py`
**Rohdaten:** `2026-08-31-mix-tempo-drift.json` (800 Segmente, 20 Mixe)
**Material:** `C:\Users\david\Music` — echte DJ-Mixe, 55 bis 188 Minuten

## Ergebnis in einem Satz

Die Segmentierung verdoppelt die Passung des Rasters bei allen geprüften Mixen
(Kontrast 1,12–1,75 → 2,15–2,85); die Zahl der Abschnitte lässt sich mangels
annotierten Materials **nicht** bewerten.

## Der Ausgangsbefund

| | Median-Kontrast | sitzt (> 2,0) |
|---|---|---|
| ein Tempo pro Mix | 1,248 | 19 % |
| Tempo je 30-s-Segment | 3,530 | 95 % |

Ein Kontrast um 1,2 bedeutet, dass sich das Raster kaum von einer zufällig
gewählten Phase abhebt — es trägt praktisch keine Information.

## Eine widerlegte Zwischenbehauptung

Zunächst hieß es hier: *„in DJ-Mixen schwankt das Tempo im Median um 33 %, ein
Tempo pro Datei ist strukturell falsch."* Die 33 % sind reproduzierbar, die
Deutung war **falsch**.

Nachgerechnet an denselben Daten: **97,2 %** aller Segmenttempi liegen auf einem
einfachen Vielfachen des Datei-Medians.

| Faktor | 1 | 2/3 | 3/2 | 2 | 4/3 | 3/4 | keins |
|---|---|---|---|---|---|---|---|
| Anteil | 77,9 % | 10,0 % | 5,5 % | 1,9 % | 1,4 % | 0,6 % | 2,8 % |

Faltet man die Faktoren heraus, fällt die Spannweite je Mix **von 33,3 % auf
0,1 %**. Die Mixe sind tempostabil — es ist der Schätzer, der zwischen
Vielfachen springt. Das deckt sich mit ISMIR 2020: 86 % aller
DJ-Tempoanpassungen liegen unter 5 %.

Damit verschiebt sich die Begründung: Segmentierung ist nötig für **Phase und
Vielfachfehler**, nicht wegen echter Tempowechsel.

## Ergebnis an sechs Mixen

| Mix | Dauer | Abschnitte | Kontrast global | segmentiert |
|---|---|---|---|---|
| 02 Mai Podcast 19 | 92 min | 50 | 1,29 | **2,58** |
| Klangkraft 2022 | 106 min | 47 | 1,75 | **2,08** |
| Progressive-Psy-Set2 | 62 min | 32 | 1,12 | **2,18** |
| Podcast-04 | 188 min | 88 | 1,47 | **2,58** |
| Summer Dream | 55 min | 27 | 1,21 | **2,33** |
| Progressive Psy trance 2 | 66 min | 35 | 1,66 | **2,85** |

## Drei eigene Fehler, alle durch Messung gefunden

### 1. Kommentar ohne Deckung

Beim Falten auf ein Vielfaches stand im Code:

```python
# Der Anker muss mitwandern: ...
grid = BeatGrid(bpm=new_bpm, anchor_s=grid.anchor_s, ...)   # tut es nicht
```

Bei Faktor 2 fällt das nicht auf, weil jeder Beat des langsameren Rasters auch
einer des schnelleren ist; erst bei Faktor 1,5 verrutscht das Raster. Ein Test
mit Halb- und Doppeltempo wäre grün geblieben. Kontrast fiel dadurch von 2,24
auf 1,96. Behoben durch `_best_phase`.

### 2. Widersprüchliche Toleranzen

Tempo- und Phasentoleranz waren unabhängig gesetzt (0,5 % und 0,125 Beats). Eine
Tempoabweichung läuft aber über das Fenster linear als Phasendrift auf:

```
138 BPM, 30-s-Fenster = 69 Beats
  0,5 % Tempotoleranz -> 0,345 Beats Drift
  Phasentoleranz       ->  0,125 Beats
```

Fast jedes Fensterpaar, das die eine Prüfung bestand, fiel zwangsläufig an der
anderen durch. Die Tempotoleranz wird jetzt aus der Phasentoleranz abgeleitet
(`_tempo_match_rel`), damit beide zusammenpassen.

### 3. Eine Korrektur, die es verschlechtert hat — zurückgenommen

Anschließend wurde die Phasenprüfung von „gegen den Abschnittsbeginn" auf
„gegen das zuletzt angehängte Fenster" umgestellt. Gemessen:

| | Abschnitte | Kontrast |
|---|---|---|
| gegen Abschnittsbeginn | 50 · 47 · 88 · 35 | 2,58 · 2,08 · 2,58 · 2,85 |
| gegen letztes Fenster | 47 · 39 · 79 · 31 | **2,34 · 1,81 · 2,44 · 2,50** |

Weniger Abschnitte, aber durchgehend schlechtere Passung. **Zurückgenommen.**

Der Denkfehler: die Drift-Akkumulation über einen langen Abschnitt ist kein
Fehler der Prüfung, sondern ihre Aufgabe. Ein Abschnitt hat **ein** Grid, das
über seine ganze Länge gelten muss; passt es am Ende nicht mehr, beginnt
richtigerweise ein neuer Abschnitt.

## Was diese Messung NICHT sagt

**Die Abschnittszahl ist nicht bewertbar.** Zwischenzeitlich wurde behauptet,
50 Abschnitte seien zu viele — hergeleitet aus geschätzten „15–25 Tracks pro
Mix". Diese Zahl war **erfunden**: es liegt keine Annotation vor, wie viele
Tracks die Mixe enthalten, und ebenso wenig, wie oft die Phase innerhalb eines
Tracks legitim bricht (jeder Breakdown kann das). Zweimal wurde gegen diese
Zahl gemessen und „Erwartung nicht eingetreten" gemeldet — die Erwartung war
das Problem.

Belastbar ist allein der Kontrast: er ist gegen eine Nullhypothese normiert
(beste Phase gegen den Mittelwert über alle Phasen) und braucht keine Annahme
über Trackzahlen.

Weitere Grenzen:

- **Kein annotiertes Referenzmaterial.** Weder Tracklisten noch echte
  Beat-Zeiten. Alle Aussagen sind relativ (besser/schlechter), keine ist absolut.
- **Nur sechs Mixe** im Detailvergleich, alle aus demselben Genre-Umfeld
  (Psy-/Progressive-Trance). Die Tempi liegen fast alle um 136–140 BPM.
- **Übergänge mit zwei laufenden Tracks** haben kein eindeutiges Tempo. Sie
  werden als eigener Abschnitt sichtbar, aber nicht als Übergang erkannt.
- **Die Segmentgrenzen liegen auf dem 30-s-Fensterraster**, nicht auf dem
  exakten Übergang.

## Reproduzierbarkeit

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\python.exe scripts\dev\measure_mix_tempo_drift.py --dir "C:\Users\david\Music" --out ergebnis.json
.\.venv\Scripts\python.exe scripts\dev\measure_mix_tempo_drift.py --dir "C:\Users\david\Music" --selftest
```

Selbsttest ausgeführt, Ergebnis REPRODUZIERBAR.
