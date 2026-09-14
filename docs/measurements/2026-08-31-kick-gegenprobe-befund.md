# Kick-Gegenprobe des Beat-Rasters — Messbefund

**Stand:** 2026-08-31
**Werkzeuge:** `scripts/dev/measure_kick_alignment_threshold.py`,
`scripts/dev/evaluate_kick_alignment.py`
**Rohdaten:** `2026-08-31-kick-alignment.json` (127 Fenster, 35 Dateien)
**Material:** `D:\beatport_tracks_2025-08` — gemasterte AIFF-Originale mit BPM
im Dateinamen als Referenz

Gemessen wurde die **echte** `_evaluate_beat_grid` aus
`backend/routers/audio_router.py`, keine Nachbildung.

## Anlass

Die Schwelle `_BEAT_GRID_KICK_ALIGNMENT_MIN = 0.75` war beim Einbau
ausdrücklich nicht kalibriert, sondern als Mittelpunkt zwischen zwei Erwartungen
gesetzt: korrektes Raster trifft ~100 % der Kicks, Halbtempo-Raster ~50 %.

## Ergebnis in einem Satz

Die Schwelle ist unbrauchbar, und keine andere Einstellung rettet sie — die
Gegenprobe misst in dieser Form nichts, was mit der Rastergüte zu tun hat.

## 1. Die Schwelle 0,75 meldet fast alles als verdächtig

```
als suspect gemeldet: 125 von 127 (98 %)
davon zu Recht (Tempo falsch): 80 von 80 (100 % der Falschen gefangen)
Fehlalarm (Tempo korrekt, trotzdem suspect): 45 von 47 (96 %)
```

Ein Alarm, der bei 98 % aller Fenster angeht, trägt keine Information.

## 2. Die tragende Annahme ist falsch

Erwartet war bei korrektem Raster ein Anteil um 1,0. Gemessen:

| | Median | 10-Perzentil | 90-Perzentil |
|---|---|---|---|
| Tempo korrekt (n=47) | **0,433** | 0,218 | 0,621 |
| Tempo falsch (n=80) | 0,336 | 0,230 | 0,492 |

Die Verteilungen überlappen fast vollständig.

## 3. Keine Schwelle trennt brauchbar

| Schwelle | fängt Falsche | verwirft Richtige | Youden |
|---|---|---|---|
| 0,35 | 54 % | 26 % | **+0,282** (bestmöglich) |
| 0,50 | 94 % | 74 % | +0,193 |
| 0,75 | 100 % | 96 % | +0,043 *(Produktion)* |

## 4. Auch die naheliegende Alternative hilft nicht

Geprüfte Gegenidee: dieselbe Trefferquote, normiert gegen phasenverschobene
Raster desselben Tempos — dieselbe Bauart, die bei der Grid-Machbarkeitsmessung
den Dichte-Bias beseitigt hatte.

| Metrik | beste Schwelle | fängt Falsche | verwirft Richtige | Youden |
|---|---|---|---|---|
| `kick_alignment` | 0,35 | 54 % | 26 % | **+0,282** |
| `alignment_contrast` | 1,50 | 75 % | 49 % | +0,261 |

**Der Vorschlag ist damit widerlegt** — er trennt schlechter, nicht besser.

## 5. Auch die Toleranz ist es nicht

Sweep über 1/2/3/4/6 Hop-Frames, mit der Zufallserwartung daneben:

| Toleranz | Zufall | korrekt | falsch | beste Schwelle | fängt | Fehlalarm | Youden |
|---|---|---|---|---|---|---|---|
| 1 F · 23 ms | 0,100 | **0,079** | 0,056 | 0,100 | 74 % | 55 % | +0,184 |
| 2 F · 46 ms | 0,190 | 0,229 | 0,185 | 0,225 | 66 % | 49 % | +0,173 |
| 3 F · 70 ms | 0,274 | 0,433 | 0,336 | 0,375 | 57 % | 26 % | +0,320 |
| 4 F · 93 ms | 0,365 | 0,487 | 0,418 | 0,475 | 69 % | 34 % | +0,347 |
| 6 F · 139 ms | 0,566 | 0,565 | 0,482 | 0,500 | 59 % | 30 % | +0,290 |

Keine Einstellung erreicht brauchbare Trennung. Bei **1 Frame liegt die
Trefferquote bei korrektem Tempo (0,079) unter der Zufallserwartung (0,100)** —
das ist der Hinweis auf die eigentliche Ursache.

## 6. Die Ursache

Zwei unabhängige Messungen an 4388 Kicks aus 10 Tracks:

- **Systematischer Versatz von genau +23,2 ms** — exakt einer Hop-Länge. Die
  Kick-Onsets liegen durchgehend ein Frame nach den Beat-Positionen.
- **Nur 4 % aller Kicks liegen innerhalb von ±23 ms eines Beats.**

Dazu die Geometrie: die Produktionstoleranz von 70 ms deckt bei 143 BPM
(Beat-Intervall 0,42 s) **ein Drittel der Zeitachse** ab. Entsprechend trifft
schon reiner Zufall 27,4 %. Eine Trefferquote, deren Grundrauschen bei einem
Drittel liegt, kann strukturell nicht scharf trennen.

Beat-Detektor und Kick-Onset-Kette liefern schlicht keine vergleichbaren
Zeitpunkte.

## Konsequenz im Code

`kick_alignment` und `kick_cross_check` werden **weiterhin berechnet und
ausgeliefert** — als Beobachtung sind sie richtig. Sie gehen aber seit
2026-08-31 **nicht mehr in `status` ein**; das Urteil stützt sich allein auf
die Gleichmäßigkeit der Beat-Intervalle.

Wächter dagegen: `Tests/test_beat_grid_provenance.py::test_kick_cross_check_does_not_drive_status`.

Der Wert stillschweigend weiter ins Urteil einzurechnen hieße, eine gemessen
wertlose Größe als Wahrheit auszugeben.

## Grenzen dieser Messung

- **Das Wahrheitskriterium ist unvollständig.** `tempo_correct` prüft nur die
  BPM, nicht die Phase. Die Gruppe „Tempo korrekt" enthält damit auch Fenster
  mit richtigem Tempo und falscher Ausrichtung. Das drückt deren Median — am
  Befund ändert es nichts, 96 % Fehlalarm bleiben unbrauchbar.
- **Nur Originale**, keine DJ-Mixe mit wechselndem Tempo.
- **Halbtempo und Doppeltempo kamen im Material nicht vor** (0 Fenster je), der
  Fehlerfall war zu 91 % „unverwandtes Tempo". Die konstruierten Hypothesen
  hinter 0,75 waren also nicht nur falsch kalibriert, sondern zielten auf
  Fälle, die hier gar nicht auftreten.
- **Die Referenz-BPM aus dem Dateinamen ist selbst fehlerbehaftet** (ganzzahlig,
  teils real daneben — siehe `2026-08-30-beatgrid-machbarkeit.md`).

## Reproduzierbarkeit

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe scripts\dev\measure_kick_alignment_threshold.py --dir "D:\beatport_tracks_2025-08" --out ergebnis.json
.\.venv\Scripts\python.exe scripts\dev\evaluate_kick_alignment.py ergebnis.json
.\.venv\Scripts\python.exe scripts\dev\measure_kick_alignment_threshold.py --dir "D:\beatport_tracks_2025-08" --selftest
```

Selbsttest ausgeführt, Ergebnis REPRODUZIERBAR. Das Werkzeug schreibt die
DB-Zählstände vor und nach dem Lauf in die Ausgabedatei (6 Projekte,
711 Medien, `integrity_check: ok` — unverändert), weil der Import des Routers
den Recovery-Bootstrap zieht. Es darf **nicht** parallel zu einem pytest-Lauf
gestartet werden.
