# Downbeat-Ableitung — Messbefund

**Stand:** 2026-08-30 · **Werkzeug:** `scripts/dev/measure_downbeat_phase_contrast.py`
**Rohdaten:** `2026-08-30-downbeat-phase-contrast.json` (750 Messwerte, 68 Dateien, 106 Fenster)
**Material:** `C:\Users\david\Music`, 140 Dateien angeboten, 68 mit ≥ 32 Beats je Fenster

## Ergebnis in einem Satz

`derive_downbeats_from_strengths` kann in diesem Material keine Taktanfänge
finden — nicht mit den Anschlagstärken, und auch mit keinem der vier geprüften
Alternativmerkmale. Der Ansatz ist nicht durch ein anderes Merkmal oder eine
andere Schwelle zu retten.

## Die drei Belege

### 1. Das Gatter besteht praktisch niemand

Korrektes Gatter = paritätsrestringierter p-Wert < 0,05 **und**
Periode-4-Anteil > Periode-2-Anteil **und** Phase in beiden Fensterhälften gleich.

| Merkmal | besteht | von |
|---|---|---|
| `onset_strength` *(Produktion)* | 2 | 150 |
| `lowmid_120_500` | 4 | 150 |
| `high_2k_8k` | 2 | 150 |
| `bass_20_120` | 0 | 150 |
| `rms` | 0 | 150 |

**8 von 750.** Allein durch Vielfachtesten wären auf dem 5-%-Niveau rund
**38** zu erwarten. Der beobachtete Wert liegt fünffach darunter.

### 2. Die Phase ist nicht einmal innerhalb eines Fensters stabil

In nur **18,5 %** der Fenster stimmt die in der ersten Hälfte gefundene Phase
mit der der zweiten Hälfte überein. Bei vier Phasen wäre reiner Zufall 25 %.
Ein Schätzer, der seinen eigenen Hälften widerspricht, trägt nichts.

### 3. Der scheinbar beste Befund war ein Periode-2-Artefakt

Mit freier Permutation als Nullhypothese erschien `high_2k_8k` in **48,7 %**
der Fenster als signifikant. Mit der richtigen Null — Permutation *innerhalb*
der geraden und ungeraden Beat-Positionen, die die Periode-2-Struktur erhält —
sind es **6,7 %**, also Zufallsniveau.

Grund: der Kontrast `max(4 Phasen) / mean(übrige)` kann Periode 2 und Periode 4
nicht unterscheiden. In Technomusik dominiert die Periode 2 (Off-Beat-HiHat,
Backbeat), und die trägt **keine** Taktinformation.

Nachgestellt an einer Kontrollreihe, die per Konstruktion keinen Takt hat
(Wert 1,0 auf ungeraden, 0,3 auf geraden Beats plus Rauschen):

| | Kontrast | p (frei) | p (paritätsrestringiert) |
|---|---|---|---|
| Kontrollreihe Periode 2 | 1,886 | **0,0005** | 0,886 |
| `high_2k_8k`, echtes Audio | 1,223 | **0,0010** | 0,739 |

Die „beste Phase" der Kontrollreihe ist über 200 Rauschziehungen ein Münzwurf:
`[0, 101, 0, 99]`. Am echten Audio zeigt die Fourierzerlegung dasselbe —
Periode-4-Anteil 0,0047 gegen Periode-2-Anteil 0,1528, Faktor 32.

## Zusätzlicher Befund am Produktionscode

`derive_downbeats_from_strengths` lässt Ableitungen ab `beats_per_bar * 2` = **8
Beats** zu und vergleicht gegen die feste Schwelle `DOWNBEAT_PHASE_CONTRAST = 1,25`.

Das Maß `max/rest` ist ein Selektionsschätzer und liegt schon ohne jedes Signal
über 1. Falsch-Alarm-Rate unter reinem Rauschen, simuliert:

| Beats | symmetrisch | schief |
|---|---|---|
| **8** | **61 %** | 98 % |
| 32 | 12 % | 87 % |
| 128 | 0 % | 48 % |
| 512 | 0 % | 5 % |

Die im Docstring zugesicherte Eigenschaft „verweigert die Auskunft, wenn sich
keine Taktposition abhebt" hält bei kurzen Beat-Listen nicht.

## Methodische Irrwege auf dem Weg dorthin

Drei Zwischenstände waren falsch und sind hier festgehalten, damit sie nicht
wiederholt werden:

1. **„Bassenergie trägt die Taktinformation."** Beruhte auf einem einzigen
   Track und einem unkalibrierten Vergleich. Über 68 Dateien: 6 % signifikant
   bei freier, 2 % bei korrekter Null — Zufallsniveau.
2. **„48,7 % der Fenster zeigen Taktstruktur."** Periode-2-Artefakt.
3. **„Zyklische Verschiebung ist die bessere Null."** Falsch — der Kontrast ist
   unter Rotation invariant, sobald die Beat-Zahl durch 4 teilbar ist; gemessen
   liefert er dann genau *einen* distinkten Wert.

## Reproduzierbarkeit

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\python.exe scripts\dev\measure_downbeat_phase_contrast.py --dir "C:\Users\david\Music" --out ergebnis.json
.\.venv\Scripts\python.exe scripts\dev\measure_downbeat_phase_contrast.py --files "<eine Datei>" --selftest
```

Das Werkzeug schreibt je Messwert SHA-256 und Größe der Quelldatei sowie die
Versionen von Python, NumPy und librosa. `--selftest` misst dieselbe Datei
zweimal und verlangt wertgleiche Ergebnisse.

**Grenzen, die der Selbsttest nicht abdeckt** (aus der Gegenprüfung):
er läuft im selben Prozess, mit demselben MP3-Dekoder und derselben
librosa-Version. Ein anderer Dekoder liefert einen anderen Startversatz und
damit ein verschobenes Beat-Raster. Verglichen werden gerundete Werte, Drift
unter 1e-4 fällt nicht auf.

## Bekannte Schwächen des Werkzeugs

Aus der unabhängigen Methodikprüfung, nicht behoben und beim Weiterlesen zu
berücksichtigen:

- **Fenster überlappen** bei Einzeltracks von 3–5 Minuten zu 37–75 %. „Drei
  Fenster einig" ist dort fast tautologisch und kein dreifacher Beleg.
- **Abtastregime uneinheitlich:** `onset_strength` ist ein Maximum über ±70 ms
  (so rechnet `compute_beat_strengths`), die Bandmerkmale sind
  Punktinterpolationen. Gegenprobe am Bassband: Kontrast 1,0492 → 1,0051 und
  Phasenwechsel allein durch das Abtastregime.
- **Rasterdrift** wird erfasst (`grid_outliers`), aber nicht ausgeschlossen. Ein
  einziger ausgelassener Beat rotiert alle Folgephasen.
- **Tempo-Oktave** wird nicht geprüft. Bei doppeltem Tempo sind die Phasen 0 und
  2 beide Taktanfang — genau die Periode-2-Falle.
- **Keine Multiplizitätskorrektur** in der Rohausgabe; 5 Merkmale × 3 Fenster
  je Datei.


---

## Nachtrag: Gegenprobe an kommerziellem Material (2026-08-30)

Einwand des Projektinhabers: die erste Messung lief überwiegend über eigene
DJ-Mixe. Wiederholt an `D:\beatport_tracks_2025-08` — 35 einzelne, gemasterte
AIFF-Tracks mit **BPM und Tonart im Dateinamen**, also mit Referenzwert.
Rohdaten: `2026-08-30-downbeat-phase-contrast-beatport.json` (520 Messwerte,
104 nicht überlappende Fenster).

Zwei Verbesserungen am Werkzeug für diesen Lauf: Fenster überlappen nicht mehr
(vorher bei 3–5-Minuten-Tracks 37–75 % Überlappung), und das Tempo wird gegen
die Dateinamen-BPM geprüft.

### Der Befund zur Ableitung hält

| Merkmal | besteht Gatter | von |
|---|---|---|
| `onset_strength` | 2 | 104 |
| `high_2k_8k` | 5 | 104 |
| `lowmid_120_500` | 2 | 104 |
| `bass_20_120` | 0 | 104 |
| `rms` | 0 | 104 |

**9 von 520.** Allein durch Vielfachtesten wären rund **26** zu erwarten.
Phasenstabilität 16–22 % bei 25 % Zufall. Und `high_2k_8k` fällt wieder von
44,2 % (freie Permutation) auf 11,5 % (korrekte Null) — dasselbe
Periode-2-Artefakt wie zuvor.

**Auf sauberem kommerziellem Material gilt derselbe Schluss.**

### Der eigentliche Fund: die Temposchätzung trägt nicht

Der Referenzwert im Dateinamen erlaubt erstmals einen Abgleich des
Beat-Rasters — und der fällt schlecht aus:

| Verhältnis erkannt / Dateiname | Fenster |
|---|---|
| 1× (korrekt) | 60 (57,7 %) |
| **unverwandt** | **35 (33,7 %)** |
| 3/2× | 4 |
| 2× · 2/3× · 1/2× | 5 |

Oktavnormierte Korrelation zwischen Dateiname und Erkennung: **r = +0,254**,
mittlere Abweichung **14,8 BPM**.

Noch deutlicher: über 104 Fenster gibt es nur **sechs verschiedene erkannte
BPM-Werte**, und drei davon decken 99 Fenster ab — 143,6 (54×), 136,0 (27×),
92,3 (18×). Bei Tracks, die laut Auszeichnung von 69 bis 145 BPM streuen.

Ein Tempo-Prior repariert die meisten Fälle:

| Datei-BPM | ohne Prior | mit `start_bpm` |
|---|---|---|
| 140 | 69,8 | 143,6 |
| 71 | 92,3 | 143,6 |
| 122 | 136,0 | 136,0 *(bleibt falsch)* |

**Warum das schwerer wiegt als die Downbeat-Frage:** jeder beat-synchrone
Schnitt sitzt auf diesem Raster, und PB Studio leitet die angezeigte BPM
ihrerseits aus den erkannten Beats ab (`60 / median(diff)`) — ein falsches
Raster erzeugt also auch eine falsche BPM-Anzeige, ohne Widerspruch.

Das ist ein **eigener, noch nicht abgeschlossener Vorgang**. Hier ist nur der
Messbefund festgehalten; am Beat-Pfad wurde nichts geändert.
