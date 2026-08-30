# Eigenes Beatgrid — Machbarkeitsmessung

**Stand:** 2026-08-30
**Werkzeuge:** `scripts/dev/measure_rigid_grid_feasibility.py` (erste, widerlegte Fassung),
`scripts/dev/measure_grid_span.py` (tragfähige Fassung)
**Rohdaten:** `2026-08-30-rigid-grid-feasibility.json` (312 Messwerte),
`2026-08-30-grid-span.json` (770 Messwerte, 35 Dateien)
**Material:** `D:\beatport_tracks_2025-08` — gemasterte AIFF-Originale mit BPM im Dateinamen

## Anlass

Die Frage war: soll die App ihr Beatgrid selbst rechnen, so wie DJ-Programme es
tun? Vorher musste die Machbarkeit gemessen werden, nicht angenommen.

## Ergebnis in einem Satz

Ein starres Raster ist tragfähig — der begrenzende Faktor ist die **Genauigkeit
des Tempos**, nicht die Länge der Spanne. Mit ganzzahlig gerundeter BPM sitzt
das Raster in 38–48 % der Segmente, mit fein nachoptimiertem Tempo in 66–73 %.

## Der erste Messversuch war falsch — und wie das auffiel

Die erste Fassung verglich `beat_track` gegen ein starres Raster über das Maß
*mittlere Onset-Stärke an den Rasterpositionen / Gesamtmittel*:

| Methode | Score (Median) | Tempo korrekt |
|---|---|---|
| `beat_track` | 4,249 | 39,4 % |
| `rigid_scan` | 1,250 | 27,9 % |
| `rigid_true` *(wahres Tempo erzwungen)* | 1,154 | 100 % |

`rigid_scan` war in **0 von 104** Fenstern besser. Der naheliegende Schluss —
starres Raster taugt nicht — ist **falsch**.

Aufgefallen an der Zeile, die nicht passt: `rigid_true` fährt das nachweislich
richtige Tempo und bekommt trotzdem den schlechtesten Score. Ein Gütemaß, unter
dem die Wahrheit verliert, misst nicht Güte.

**Ursache: Dichte-Bias.** Das Maß belohnt dünnere Raster, weil weniger Punkte
selektiver auf Peaks sitzen können. An einer Datei, jeweils beste Phase:

| Tempo | 572,0 | 286,0 | 143,0 | 71,5 | 35,8 | 17,9 |
|---|---|---|---|---|---|---|
| Score | 1,101 | 1,122 | 1,135 | 1,163 | 1,160 | 1,370 |

Monoton steigend mit sinkendem Tempo. Deshalb fand `rigid_scan` auch überwiegend
halbe Tempi — 69,8 (36×), 92,3 (28×), 71,8 (16×) waren die häufigsten Werte. Es
optimierte den Bias, nicht die Musik.

## Das tragfähige Maß

    kontrast = score(beste Phase) / mittelwert(score über alle Phasen)

Zähler und Nenner haben dieselbe Punktzahl, der Dichte-Bias kürzt sich weg. Der
Kontrast misst nur, ob sich **eine** Phase abhebt — ob an dieser Stelle
überhaupt ein Raster dieses Tempos sitzt. Schwelle für „sitzt": Kontrast > 2,0,
also beste Phase doppelt so stark wie das Phasenmittel.

## Befund

Anteil der Segmente, in denen das Raster sitzt:

| Spanne | n | Dateinamen-BPM | Tempo optimiert | dazugewonnen |
|---|---|---|---|---|
| 8 s | 210 | 48 % | 73 % | 26 % |
| 16 s | 210 | 41 % | 70 % | 30 % |
| 30 s | 210 | 38 % | 66 % | 28 % |
| 60 s | 105 | 38 % | 66 % | 28 % |
| 120 s | 35 | 40 % | 71 % | 31 % |

**Die Spanne ist fast bedeutungslos** — 73 % bei 8 s gegen 71 % bei 120 s. Was
zählt, ist das Tempo: die Nachoptimierung um maximal ±2 % hebt jede Zeile um
26–31 Prozentpunkte.

Nötige Genauigkeit, gemessen an den Segmenten, die tragen: Median-Abweichung von
der Dateinamen-BPM **0,00–0,20 %**, 90-Perzentil **1,45–1,69 %**. Die
ganzzahlige BPM im Dateinamen ist also nicht nur gerundet, sie ist in einem Teil
der Fälle real daneben.

**Rund 30 % tragen auch mit optimiertem Tempo nicht.** Über alle Spannen
stabil (27–34 %). Plausibelste Erklärung sind Passagen ohne durchgehenden
Anschlag — Breakdowns, Intros, Ambient-Teile. Nicht gemessen, siehe Grenzen.

## Eine eigene Fehllesung, festgehalten

Die Verteilung ist **bimodal**: der Kontrast springt entweder von ~1,1 auf ~3,2
oder bleibt liegen. Median der Differenzen (0,075) und Differenz der Mediane
(1,98) widersprachen sich deshalb scheinbar. Beide Zahlen waren richtig; falsch
war, sie wie unimodale Statistik zu lesen. Anteile über einer Schwelle sind hier
die richtige Kennzahl, Mediane nicht.

## Was das für die App heißt

1. **Ein eigenes Grid ist machbar**, aber der Gewinn liegt in der
   Tempobestimmung, nicht in der Rasterlogik. Ein Verfahren, das das Tempo auf
   ~0,2 % genau trifft, ist die eigentliche Aufgabe.
2. **Eine feine Tempo-Nachoptimierung um den Schätzwert herum ist billig und
   wirksam** — ±2 % abgesucht, hebt den Trefferanteil um rund 28 Punkte.
3. **Segmentierung ist für Originale nicht nötig.** Ein Anker plus ein präzises
   Tempo trägt über 120 s genauso gut wie über 8 s.
4. **Für DJ-Mixe gilt Punkt 3 ausdrücklich nicht** — siehe Grenzen.

## Grenzen dieser Messung

Ausdrücklich, damit niemand mehr hineinliest als drinsteht:

- **Nur Originale mit konstantem Tempo.** Genau deshalb ist die Aussage „Spanne
  egal" **nicht** auf DJ-Mixe übertragbar. Ein Mix wechselt an jedem Übergang
  Tempo und Phase; dort ist Segmentierung zwingend. Diese Messung sagt dazu
  nichts.
- **Die Dateinamen-BPM ist die einzige Referenz** und selbst fehlerbehaftet.
  Ein Vergleich gegen annotierte Beat-Zeiten wäre stärker, liegt aber nicht vor.
- **Der Kontrast misst Phasenlage, nicht musikalische Richtigkeit.** Ein Raster
  auf der Zählzeit 2 hätte denselben Kontrast wie eines auf der 1.
- **Die Schwelle 2,0 ist gesetzt, nicht hergeleitet.** Sie trennt die beiden
  Modi der bimodalen Verteilung sauber; eine Kalibrierung gegen eine Nullhypothese
  fehlt.
- **Tempo-Oktave wird nicht geprüft.** Das Suchgitter liegt eng um die
  Dateinamen-BPM, ein Faktor-2-Fehler kann darin nicht auftreten — in Produktion
  ist er der häufigste Fehler.

## Reproduzierbarkeit

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\python.exe scripts\dev\measure_grid_span.py --dir "D:\beatport_tracks_2025-08" --out ergebnis.json
.\.venv\Scripts\python.exe scripts\dev\measure_grid_span.py --dir "D:\beatport_tracks_2025-08" --selftest
```

Selbsttest misst dieselbe Datei zweimal und verlangt wertgleiche Ergebnisse —
ausgeführt, Ergebnis REPRODUZIERBAR. Jeder Messwert trägt SHA-256 der Quelldatei
sowie die Versionen von Python, NumPy und librosa.
