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
