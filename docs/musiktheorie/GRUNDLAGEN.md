# Musiktheoretische Grundlagen für die Audioanalyse in PB Studio

Stand: 2026-08-31 · Recherchebericht, keine Codeänderung

**Lesehinweis zur Kennzeichnung.** Jede Aussage ist einer von drei Klassen zugeordnet:

- **[BELEG]** — durch eine zitierte Quelle gedeckt. Quelle steht dabei.
- **[MESSUNG]** — in dieser Sitzung auf dieser Maschine reproduziert. Der Befehl
  steht dabei, das Ergebnis ist nachvollziehbar.
- **[EINSCHÄTZUNG]** — meine eigene Schlussfolgerung. Nicht belegt. Kann falsch sein.

Wo die Literatur den eigenen Messungen des Projekts **widerspricht**, ist das mit
**⚠ WIDERSPRUCH** markiert. Das sind die wertvollsten Stellen dieses Berichts.

---

## 1. Kurzfassung — die fünf wichtigsten anwendbaren Erkenntnisse

### 1.1 Die drei „librosa-Lieblingstempi" sind kein Zufall, sondern das Gitter selbst

Der gemessene Befund des Projekts (häufigste Werte = Tempogramm-Frequenzen für
k = 18, 19, 28) ist auf dieser Maschine exakt reproduzierbar. `librosa.feature.tempo`
aggregiert ein **Autokorrelations**-Tempogramm; dessen Achse ist
`60 · sr / (hop_length · k)` mit ganzzahligem Lag `k`. Bei den Standardwerten
`sr=22050, hop_length=512` ergibt das eine Bildrate von 43,066 Hz und damit ein
Tempogitter, das im relevanten EDM-Bereich **6,8 bis 7,6 BPM grob** ist. [MESSUNG]

```
k = 18  ->  143,555 BPM
k = 19  ->  135,999 BPM
k = 28  ->   92,285 BPM
```

Ein Track mit echten 126 BPM kann von diesem Verfahren **prinzipiell nicht**
richtig geschätzt werden — der nächstgelegene Gitterwert ist 123,05 BPM
(−2,34 %). Über vier Minuten läuft ein daraus gebautes Beatgrid um **5,7 Sekunden**
aus dem Takt. [MESSUNG] Die 37-%-Trefferquote ist damit keine Eigenart der Musik,
sondern eine Obergrenze des Messverfahrens.

**Gegenmaßnahme, ohne Modell umsetzbar:** ein **Fourier-Tempogramm auf einer frei
gewählten, dichten Tempoachse**. Müller (FMP, Kapitel 6.2.2) berechnet die
Fourier-Koeffizienten nicht per FFT, sondern **einzeln für jeden gewünschten
Tempowert** aus einer Menge Θ, gerade um diese Diskretisierung zu umgehen; die
Aufwandsbetrachtung dort nennt das ausdrücklich „reasonable", weil nur wenige
Koeffizienten gebraucht werden. [BELEG: FMP C6S2]

### 1.2 Downbeats aus Anschlagstärke abzuleiten ist nicht „schwierig", sondern der falsche Merkmalsraum

Der beste veröffentlichte merkmalsbasierte Downbeat-Tracker (Durand et al. 2016)
nutzt vier getrennte Merkmalsfamilien. Das **stärkste Einzelmerkmal ist die
Harmonie (Chroma) mit 61,0 % F-Measure**; das rhythmische Onset-Merkmal ist so
schwach, dass es nur als Ergänzung geführt wird. Erst das Ensemble aus Harmonie,
Rhythmus, Bass und Melodie erreicht 72,6 %. [BELEG: Durand et al. 2016, Tab. III]

Das heißt: Selbst mit vier Merkmalsfamilien, beat-synchroner Rasterung und einem
CNN-Ensemble erreicht der Stand der Technik von 2016 knapp drei Viertel. Der
verworfene Ansatz des Projekts benutzte **genau die schwächste der vier Familien,
allein**. Der Fehlschlag ist damit von der Literatur vorhergesagt.

### 1.3 „Beat This!" ist als ONNX-Modell verfügbar — MIT-lizenziert, ohne madmom, ohne PyTorch

Der aktuelle Stand der Technik (Foscarin, Schlüter, Widmer, ISMIR 2024) verzichtet
**bewusst auf die DBN-Nachverarbeitung** und übertrifft trotzdem die bisherige
Bestleistung im F-Measure. [BELEG: arXiv 2407.21658] Es existiert eine öffentliche
ONNX-Konvertierung mit vorgefertigtem Modell (`onnx/beat_this.onnx`, ~97 MB,
Opset 14, Eingang `[1, T, 128]`, zwei Ausgänge `beat` und `downbeat`), MIT-Lizenz.
[BELEG: mosynthkey/beat_this_cpp]

Damit ist das der **einzige Pfad in diesem Bericht, der belastbare Downbeats
liefern kann und gleichzeitig alle IRON RULES einhält**: kein CUDA, kein ROCm, kein
madmom, kein PyTorch zur Laufzeit — `onnxruntime` 1.19.2 mit
`DmlExecutionProvider` ist auf dieser Maschine bereits installiert. [MESSUNG]

### 1.4 ⚠ Die DJ-Mixe schwanken nicht im Tempo — das Schätzverfahren wechselt die metrische Ebene

Das ist der wichtigste Einzelbefund dieses Berichts, weil er eine Projektannahme
umkehrt. An den vorliegenden Messdaten (19 Mixe, 800 Segmente) nachgerechnet:
**97,2 % aller Segmenttempi liegen innerhalb ±3 % auf einem einfachen
musikalischen Vielfachen des Datei-Medians** (1: 77,9 %, 2/3: 10,0 %, 3/2: 5,5 %).
Faltet man nur diese Faktoren heraus, sinkt die mediane Tempo-Spannweite **von
33,8 % auf 1,5 %**. [MESSUNG, Herleitung in 3.5]

Das deckt sich mit der Literatur zu realen DJ-Mixen: „86.1 % of the tempo are
adjusted less than 5 %". [BELEG: Kim et al., ISMIR 2020] Ein Tempo pro Mix ist für
diese Dateien **nicht** strukturell falsch. Falsch ist die Schätzung in 22 % der
Segmente.

Das Marker-basierte Beatgrid-Modell aus Mixxx — BeatGrid (Anker + BPM, O(1)) vs.
BeatMap (alle Positionen), mit mehreren Gitterregionen bei Tempowechsel und der
Annahme „every bar has a constant tempo" [BELEG: Mixxx Wiki] — bleibt fachlich
richtig und ist der Weg für *echte* Tempowechsel. Für die hier vermessenen Mixe
löst es aber nichts, weil es Marker mit falschen Tempi tragen würde. **Zuerst die
Oktave, dann das Datenmodell.**

### 1.5 Konsonante Tonartwechsel sind operational definiert — es gibt eine offizielle Gewichtung

Das Camelot Wheel ist eine DJ-taugliche Umbenennung des Quintenzirkels
[BELEG: DJ.Studio], seine wissenschaftliche Grundlage ist die Torus-Repräsentation
von Krumhansl & Kessler (1982), in der Quintverwandtschaft sowie Parallel- und
Varianttonart als Nachbarschaften auftreten. [BELEG: Krumhansl & Kessler 1982]

Praktisch nutzbar ist die **MIREX-Gewichtung für Tonarterkennung**: korrekt = 1,0;
Quinte auf/ab = 0,5; Paralleltonart (relative major/minor) = 0,3; Varianttonart
(parallel major/minor) = 0,2; sonst 0,0. [BELEG: MIREX Audio Key Detection]
Das ist eine fertige, zitierbare Konsonanz-Distanzmatrix für 24 Tonarten.

---

## 2. Beat, Takt, Downbeat

### 2.1 Begriffe

Die MIR-Literatur ordnet die metrische Hierarchie in drei Ebenen, die sich als
Teilmengenbeziehung schachteln — „pulses on higher levels are subsets of the lower
level pulses": [BELEG: Seppänen, Tatum Grid Analysis; übereinstimmend in der
Carnatic-Meter-Literatur]

| Ebene | Begriff | Bedeutung |
|---|---|---|
| schnellste | **Tatum** | kleinste regelmäßige Unterteilung, in der Onsets liegen |
| mittlere | **Tactus** (= Beat) | die Ebene, zu der man mitklopft; „most salient level" |
| langsamste | **Measure** / Takt | Gruppierung der Beats; ihr erster Beat ist der Downbeat |

Aus der Musiktheorie ergänzend: der **Downbeat** ist „the first beat of the
measure — taken to be the strongest beat of the measure"; der **Backbeat** ist
„an accent on beats 2 and 4 of a quadruple meter". [BELEG: Open Music Theory]
Oberhalb des Taktes liegt der **Hypermeter**: „a hypermeasure is typically four
measures long", mit dem Muster stark–schwach–stark–schwach über vier Takte.
[BELEG: Open Music Theory, Hypermeter]

**Metrum** ist dabei nicht dasselbe wie Tempo: Metrum ist die *Struktur* der
Betonungshierarchie, Tempo ist die *Rate* der Tactus-Ebene. Ein Tempo-Oktavfehler
ist ein Fehler in der Ebenenwahl, kein Messfehler an der Rate. [EINSCHÄTZUNG,
aber unmittelbar aus der Hierarchiedefinition folgend]

### 2.2 Welche Merkmale tragen die Taktinformation nachweislich

Durand et al. (2016) verwenden vier komplementäre, auf ein **Tatum-Raster**
synchronisierte Merkmalsfamilien: [BELEG: arXiv 1605.08396]

| Familie | Repräsentation | Begründung im Paper |
|---|---|---|
| **Harmonie** | 12-Bin-Chromagramm aus Constant-Q | „the harmonic content is more likely to change around the downbeat positions" |
| **Rhythmus** | Spektralfluss-ODF in drei Bändern | Onsets korrelieren mit Taktstruktur, „though isolated onsets don't always align with downbeats" |
| **Bass** | Tiefpass-Spektrogramm unter 150 Hz | Kick und Bass „tend to emphasize the downbeat" |
| **Melodie** | CQT 392–3520 Hz | „pitch contour and note duration play an important role in our interpretation of meter" |

Ergebnisse (F-Measure, neun Datensätze, 1511 Tracks): Harmonie allein **61,0 %**,
Harmonie + Rhythmus **69,9 %**, volles Ensemble **72,6 %** gegenüber 55,8 % für
das nächstbeste Verfahren. [BELEG: ebd., Tab. III]

Böck et al. (2016) ergänzen die zweite tragende Säule: ein **metrisches Modell**.
Ihr Verfahren koppelt ein RNN an ein Bar-Pointer-Modell in einem dynamischen
Bayes-Netz, das die Vorhersagen „to valid rhythmic structures" zwingt, statt Beats
unabhängig zu behandeln. Die Arbeit betont, dass rein akustische Merkmale ohne
metrisches Modell Downbeats nicht zuverlässig von anderen starken Beats trennen
können. [BELEG: ISMIR 2016, „Joint Beat and Downbeat Tracking with RNNs"]

### 2.3 Warum reine Anschlagstärke unzureichend ist

Drei unabhängige Gründe, alle belegt:

1. **Falsche Merkmalsfamilie.** Der Onset-/Akzent-Kanal ist bei Durand die
   schwächste der vier Familien; die Taktinformation sitzt überwiegend im
   Harmoniewechsel. [BELEG]
2. **Fehlendes metrisches Modell.** Ohne Bar-Pointer-Constraint ist der stärkste
   Akzent nicht vom Downbeat unterscheidbar. [BELEG: Böck et al. 2016]
3. **Backbeat-Kollision.** In Pop, House und Techno liegt die *lauteste*
   wiederkehrende Betonung typischerweise auf 2 und 4 (Snare/Clap), nicht auf 1.
   [BELEG: Open Music Theory, Definition Backbeat]

**Zum eigenen Befund des Projekts.** Die Beobachtung, dass das Kontrastmaß
`max(4 Phasen)/mean(übrige)` Periode 2 nicht von Periode 4 trennen kann, ist
mathematisch zwingend und deckt sich mit Punkt 3: ein Backbeat-Muster erzeugt in
einem 4-Phasen-Test genau denselben Kontrast wie ein Taktmuster, weil Periode 2
ein Teiler von Periode 4 ist. **Die Literatur bestätigt diesen Fehlschluss als
strukturell, nicht als Implementierungsfehler.** Ein Vier-Phasen-Kontrast ohne
vorherigen Periodizitätstest kann diese Frage prinzipiell nicht beantworten.
[EINSCHÄTZUNG, gestützt auf die zitierte Backbeat-Definition]

Dass 9 von 520 Messwerten ein Gatter bestanden, wo Zufall 26 erwarten ließe,
ist zusätzlich ein Hinweis, dass die Ableitung **schlechter als Raten** war —
also nicht nur schwach, sondern systematisch in die falsche Richtung gezogen.
[EINSCHÄTZUNG]

### 2.4 Stand der Technik im Downbeat-Tracking

| System | Jahr | Ansatz | Für dieses Projekt |
|---|---|---|---|
| madmom `DBNDownBeatTracking` | 2016 | RNN + Bar-Pointer-DBN | **nicht verfügbar** |
| Beat Transformer | 2022 | Demixed, dilated self-attention | PyTorch, keine offizielle ONNX-Version gefunden |
| BEAST | 2024 | Streaming Transformer, online | PyTorch |
| **Beat This!** | **2024** | **Conv + Transformer, ohne DBN** | **ONNX vorhanden, MIT** |
| BeatNet+ | TISMIR | CRNN + Partikelfilter, echtzeitfähig | baut auf madmom-Ökosystem |

**Zur Nichtverfügbarkeit von madmom.** Die Beobachtung des Projekts ist upstream
dokumentiert: madmom-Issue #517 meldet genau die `VisibleDeprecationWarning` beim
Erzeugen eines ndarray aus „ragged nested sequences" in `downbeats.py`; die
NumPy-1.24-Release-Notes machen daraus einen harten `ValueError`, sofern nicht
`dtype=object` übergeben wird. [BELEG: madmom #517, NumPy 1.24 Release Notes]
Zusätzlich ist `np.float` seit NumPy 1.24 entfernt und in madmom noch in Gebrauch
(PR #542 offen/nicht releaset). [BELEG: madmom #542]

**Die Diagnose des Projekts ist damit fremdbestätigt und nicht durch Konfiguration
umgehbar.** Ein NumPy-Downgrade unter 1.24 verletzt die eigene IRON RULE 3 nicht
(die fordert < 2.0), würde aber die gepinnte 1.26.4 aufgeben — und BeatNet ist
laut CLAUDE.md ohnehin nur über madmom nutzbar.

**Beat This! ist der Ausweg.** Konkrete Spezifikation für eine spätere
Implementierung: [BELEG: CPJKU/beat_this `preprocessing.py`]

```
sr        = 22050        n_fft = 1024      hop_length = 441   ->  50 fps
n_mels    = 128          f_min = 30        f_max      = 11000
mel_scale = "slaney"     power = 1 (Magnitude, nicht Leistung)
normalized = "frame_length"
Skalierung: log1p(1000 * S)
ONNX:  input_spectrogram [1, T, 128]  ->  beat [1, T], downbeat [1, T]  (Logits)
Chunking: 1500 Frames, 6 Frames Rand
```

⚠ **Nicht verifiziert.** Ich habe das Modell **nicht** heruntergeladen und **nicht**
unter DirectML ausgeführt. Ob `DmlExecutionProvider` alle Operatoren dieses
Transformers unterstützt, ist **unbekannt**. Ebenso ungeprüft: ob sich
`normalized="frame_length"` und `power=1` aus torchaudio in librosa bitgenau
nachbilden lassen — eine Abweichung im Frontend kann ein sonst korrektes Modell
wertlos machen. Beides gehört in einen Machbarkeits-Spike **vor** jeder
Architekturentscheidung.

---

## 3. Tempo, Tempo-Oktaven, Beatgrid

### 3.1 Das Oktavproblem

Tempo-Oktavfehler sind Verwechslungen der metrischen Ebene: Statt des Tactus wird
eine Tempo-Harmonische (doppelt) oder -Subharmonische (halb) gewählt. Müllers
Tempogramm-Kapitel führt „tempo harmonic" und „tempo subharmonic" als eigene
Begriffe. [BELEG: FMP C6] Schreiber & Müller (2017) korrigieren Oktavfehler mit
50 globalen Merkmalen — Energie an 10 Beat-Periodizitäten × 5 Spektralbändern.
[BELEG: Schreiber & Müller, „Exploiting global features for tempo octave correction"]

Genau diese Idee ist in librosa 0.11 fertig eingebaut: **`librosa.feature.tempogram_ratio`**
misst die relative Energie an 13 metrisch bedeutsamen Vielfachen des geschätzten
Tempos — 4, 8/3, 3, 2, 4/3, **3/2**, 1, **2/3**, 3/4, 1/2, 1/3, 3/8, 1/4.
[MESSUNG: Docstring der installierten Version; BELEG: Peeters 2005, Prockup et al. 2015]

Die Faktoren 3/2 und 2/3 sind exakt die von der Aufgabenstellung genannten
3:2-Fehler (Quartolen-/Triolenverwechslung), 4/3 der punktierte Fall.

### 3.2 Warum 3:2- und 4:3-Fehler auftreten

Zwei getrennte Ursachen, die in den Projektmessungen vermutlich vermischt sind:

**Ursache A — musikalisch.** Bei Halftime-Feel (typisch Drum & Bass, Trap) ist die
wahrgenommene Tactus-Ebene doppeldeutig; bei Shuffle/Triolenfeel liegt eine echte
3er-Unterteilung vor, die die Autokorrelation als konkurrierende Periodizität
sieht. Das ist der Fall, den `tempogram_ratio` adressiert. [BELEG: Prockup et al.,
Faktorentabelle]

**Ursache B — Diskretisierung.** ⚠ **Diese Ursache ist in der Literatur zum
Oktavproblem nicht beschrieben, folgt aber zwingend aus dem Gitter.** [MESSUNG +
EINSCHÄTZUNG]

Das Autokorrelationsgitter enthält 143,555 und 92,285 BPM. Deren Verhältnis ist
1,5556 — praktisch genau 3:2. Ein Track bei echten 138 BPM hat auf dem Gitter die
Nachbarn 136,0 (−1,45 %) und 143,55 (+4,0 %); sein 2/3-Relativ bei 92 BPM trifft
mit 92,285 (+0,3 %) **deutlich besser auf das Gitter als das wahre Tempo**. Wenn
das Gitter die falsche Ebene genauer darstellen kann als die richtige, wird die
Aggregation systematisch zur falschen Ebene gezogen.

**Welche Ursache in welcher Messreihe wirkt — auseinanderhalten.** Die
Mix-Messreihe des Projekts verfeinert bereits um ±2 % (`refine_rel = 0.02`), liegt
also nicht mehr auf dem rohen Gitter; dort dominiert **Ursache A**, wie die
Faktorentabelle in 3.5 zeigt. Die 37-%-Trefferquote der 35 Beatport-Tracks
stammt dagegen aus dem ungefeinerten `librosa.beat_track` und ist **Ursache B**.
Es sind zwei verschiedene Defekte, und sie brauchen zwei verschiedene Mittel
(U-2 bzw. U-1). [MESSUNG + EINSCHÄTZUNG]

**Konsequenz für die Reihenfolge der Arbeit:** Wo auf dem rohen Gitter geschätzt
wird, ist jede Oktavkorrektur auf verfälschte Eingaben gestützt — dort erst die
Tempoachse verfeinern. Wo bereits verfeinert wird, wirkt die Oktavkorrektur
sofort und allein. [EINSCHÄTZUNG]

### 3.3 Wie DJ-Programme ein Beatgrid halten

Mixxx unterscheidet zwei Datenmodelle: [BELEG: Mixxx Wiki, Beat and Bar Edit Workflow]

- **BeatGrid** — „an offset measured in frames and tempo measured in BPM. With this,
  we can unequivocally determine every beat position." Kompakt, O(1)-Abfrage,
  jede Beatposition per Interpolation.
- **BeatMap** — „the series of all detected beats positions in frames". Bildet
  Tempoänderungen und Livemitschnitte ab, aber: „We can not unequivocally determine
  any beat position or assign a frame to an arbitrary beat."

Die adaptive Weiterentwicklung führt **mehrere Gitterregionen** ein: „we allow our
grid to be described by a different set of coordinates at any arbitrary places" —
bei einem Tempowechsel „we simply reset the metronome, ie -the grid, on any
arbitrary offset with a new BPM". Grundannahme: „every bar has a constant tempo".
[BELEG: ebd.]

In den Voreinstellungen bildet sich das ab als „Assume Constant Tempo": „If enabled,
Mixxx assumes that the distances between the beats are constant"; ist es
abgeschaltet, wird das rohe Analyseraster gezeigt — „appropriate for tracks with
variable tempo". [BELEG: Mixxx-Handbuch 13.4]

Bemerkenswert und für PB Studio direkt relevant: Mixxx' „Enable Fast Analysis"
analysiert nur die **erste Minute**, mit der ausdrücklichen Begründung, „most of
today's dance music is written in a 4/4 signature with a fixed tempo". [BELEG: ebd.]
Für gemasterte Beatport-Tracks ist ein konstantes Grid also branchenüblich
gerechtfertigt — für DJ-Mixe ausdrücklich nicht.

### 3.4 Genauigkeitsanforderungen

Der De-facto-Standard aus MIREX/`mir_eval`: ein Beat gilt als korrekt, wenn er in
einem **±70-ms-Fenster** um die Referenzposition liegt (F-Measure). Die
Kontinuitätsmaße sind strenger — ein Beat zählt nur, wenn auch der vorherige
korrekt war; **CMLt** misst auf der korrekten metrischen Ebene, **AMLt** erlaubt
zusätzlich doppeltes/halbes Tempo und Offbeat-Verschiebung. Konvention: die ersten
5 Sekunden werden verworfen. [BELEG: mir_eval / MIREX Beat Tracking]

⚠ **Für PB Studio ist ±70 ms zu locker.** Ein Videoschnitt bei 25 fps hat 40 ms
Rasterweite; ein Versatz von 70 ms ist knapp zwei Frames und als Fehlschnitt
sichtbar. Für Schnittzwecke ist außerdem **CMLt das relevante Maß, nicht F-Measure** —
ein Grid, das die Hälfte der Beats trifft, aber ständig die Phase verliert, ist für
Schnitt unbrauchbar, obwohl es einen guten F-Wert haben kann. Genau davor warnt
das Beat-This-Paper selbst: es „performs worse on continuity metrics" trotz
besserem F1. [BELEG: arXiv 2407.21658] [EINSCHÄTZUNG für den 25-fps-Bezug]

### 3.5 ⚠ WIDERLEGT: „In DJ-Mixen schwankt das Tempo im Median um 33 %"

Die Literatur zu realen DJ-Mixen misst das Gegenteil: **„86.1 % of the tempo are
adjusted less than 5 %, 94.5 % are less than 10 %, and 98.6 % are less than 20 %."**
[BELEG: Kim et al., ISMIR 2020, Mix-To-Track Subsequence Alignment]

Ein Median von 33 % Schwankung ist damit **nicht vereinbar**, wenn es sich um
echte Tempoänderungen handelte. Ich habe die Frage an den vorliegenden Messdaten
des Projekts entschieden (`docs/measurements/2026-08-31-mix-tempo-drift.json`,
19 Mixe, 800 Segmente à 30 s). [MESSUNG]

**Erstens ist die Zahl reproduzierbar** — und sie ist eine *Spannweite*, keine
mittlere Abweichung:

```
Median über 19 Mixe von (max - min) / median  =  33,8 %
```

**Zweitens ist die Streuung fast vollständig Ebenenverwechslung.** Bildet man für
jedes Segmenttempo das Verhältnis zum Median seiner Datei, liegen die Werte auf
den Faktoren der `tempogram_ratio`-Tabelle:

| Verhältnis zum Datei-Median | Anteil (±3 %) |
|---|---|
| 1 (korrekt) | **77,9 %** |
| 2/3 | 10,0 % |
| 3/2 | 5,5 % |
| 2 | 1,9 % |
| 4/3 | 1,4 % |
| 3/4 | 0,6 % |
| **Summe auf musikalischen Faktoren** | **97,2 %** |

**Drittens verschwindet die Schwankung, wenn man nur die Oktave faltet** — ohne
jede Neuschätzung, allein durch Division jedes Wertes durch den nächstgelegenen
dieser Faktoren:

```
Median der Spannweite   vorher: 33,8 %   ->   nachher:  1,5 %
Mittelwert              vorher: 45,5 %   ->   nachher:  5,0 %
```

Bei 14 der 19 Mixe ist die *mediane* relative Abweichung ohnehin exakt 0,0 % —
das Tempo ist bereits stabil, die Spannweite entsteht durch einzelne
Ausreißersegmente.

**Schlussfolgerung, und sie kehrt eine Projektannahme um:**

> Die 20 DJ-Mixe sind tempostabil. Sie sind mit **einem** Tempo pro Datei
> beschreibbar — genau wie es die ISMIR-2020-Statistik erwarten lässt. Die
> Aussage „ein Tempo pro Datei ist dort strukturell falsch" ist **durch die
> eigenen Daten des Projekts widerlegt**. Was strukturell falsch ist, ist das
> **Schätzverfahren**, das in 22 % der Segmente die metrische Ebene wechselt.

Das verschiebt die Priorität deutlich: Ein Marker-basiertes Beatgrid (U-4) löst
für diese Mixe **nichts**, weil es Marker mit falschen Tempi tragen würde. Der
wirksame Eingriff ist die Oktavkorrektur (U-2) — hier mit gemessenem Effekt
33,8 % → 1,5 %.

⚠ **Grenze dieses Belegs.** Gezeigt ist, dass die *Schätzungen* auf musikalische
Vielfache eines stabilen Wertes fallen. **Nicht** gezeigt ist, dass dieser
stabile Wert der *richtige* ist — die Faltung macht die Reihe konsistent, nicht
notwendig korrekt. Dafür braucht es Referenzannotationen (U-14). Ebenso wenig
gezeigt: dass das für andere Mixe als diese 19 gilt; alle stammen aus einem engen
Genrebereich (Median-Tempi 72–138 BPM).

---

## 4. Phrasenstruktur in elektronischer Tanzmusik

### 4.1 Warum 4/8/16/32 Takte so stabil sind

Musiktheoretische Grundlage ist der **Hypermeter**: „Hypermeter refers to groupings
of measures into different patterns of accentuation akin to meter"; der Hyperbeat
entspricht in der Regel einem Takt, die Hypermeasure typischerweise vier Takten
im Muster stark–schwach–stark–schwach. [BELEG: Open Music Theory] Vier Takte à
vier Beats ergeben die 16er-Einheit, deren Verdopplungen die 8-, 16- und
32-Takt-Phrasen bilden.

Empirisch für EDM belegt der Raveform-Datensatz (TISMIR): 4902 DJ-Mixe, 56 873
Tracks, davon **1423 Tracks von drei Fachleuten annotiert** mit „tempo, beat and
downbeat positions, and functional segment boundaries with labels". Genres
schwerpunktmäßig Techno (~550), Trance, Drum & Bass, Tech House, Deep House.
Strukturänderungen treten „at multiples of four or eight measures" auf; die
häufigste Segmentlänge ist **„30 seconds or 16 measures"** bei 128 BPM; die meisten
Tracks haben 8 bis 13 Segmente. [BELEG: Raveform, TISMIR]

### 4.2 Wo Schnitte musikalisch sitzen

Aus den Definitionen in 2.1 und dem Hypermeter ergibt sich eine Hierarchie von
Schnittpunkten mit absteigender „Gewichtigkeit":

| Position | Musikalische Bedeutung | Wirkung im Schnitt |
|---|---|---|
| Phrasengrenze (16/32 Takte) | Formteilwechsel | stärkster Schnitt, Szenenwechsel |
| Hypermeasure-Grenze (4/8 Takte) | Untergliederung | Abschnittswechsel |
| Downbeat (Takt 1) | stärkster Beat des Taktes | Standardschnitt |
| Backbeat (2 und 4) | Akzent in Pop/Rock/House | Betonungsschnitt, Kontrast |
| Offbeat (Achtel dazwischen) | Synkopierung | schnelle Folgen, Energie |

[BELEG für die musikalischen Definitionen: Open Music Theory; die Zuordnung zur
Schnittwirkung ist EINSCHÄTZUNG.]

Empirische Stütze aus der DJ-Praxis: Schwerkolt et al. leiten „switch points"
aus Interviews mit Berufs-DJs ab und setzen sie über Merkmalsextraktion und
Novelty-Analyse um; 96 % der so erzeugten Punkte wurden als für einen DJ-Mix
brauchbar bewertet. [BELEG: arXiv 2007.08411]

### 4.3 Build-up, Drop, Breakdown — belastbare akustische Merkmale?

**Teilweise, mit klaren Grenzen.**

Die Raveform-Taxonomie umfasst neun funktionale Labels: Intro, Buildup, Drop,
Breakdown, Cooldown, Outro, Bridge, Ambient-Intro, Ambient-Outro; die
Begriffsbildung ist ausdrücklich **energiezentriert** — „focusing on perceived
changes in musical intensity and function". [BELEG: Raveform]

Beschreibend gilt: der Drop ist der lauteste Abschnitt und der Punkt, an dem
Rhythmus oder Basslinie sich plötzlich ändern, unmittelbar nach Break und
Build-up. [BELEG: Wikipedia „Drop (music)"; Sekundärquelle, schwächer als die
übrigen]

Methodisch verfährt Yadati et al. (ISMIR 2014) zweistufig: **zuerst
Strukturgrenzen segmentieren** (Annahme: ein Drop ist immer eine
Strukturgrenze), dann jede Grenze mit einem binären SVM klassifizieren — Merkmale
MFCC, Spektrogramm und rhythmische Merkmale, gestützt auf die Annahme, dass ein
Drop durch eine plötzliche Änderung gekennzeichnet ist. [BELEG: Yadati et al. 2014,
über Sekundärzusammenfassung — die Primär-PDF war maschinell nicht auslesbar,
konkrete Genauigkeitswerte konnte ich **nicht** belegen]

Ergänzend charakterisieren neuere Arbeiten EDM-Dynamik über
Harmonic-to-Percussive-Energieverhältnis, Crest-Faktor und RMS-Kurtosis.
[BELEG: arXiv 2509.11474]

**Ehrliche Bewertung.** Ein Build-up ist als *monotoner Anstieg* von RMS,
spektralem Zentroid und Hochfrequenzanteil über 8–16 Takte gut greifbar. Ein Drop
ist als *Sprung* an einer Phrasengrenze nach einem energiearmen Abschnitt
greifbar. Was **nicht** ohne trainiertes Modell geht, ist die Unterscheidung
Drop / zweiter Drop / Cooldown — die ist funktional, nicht akustisch definiert.
[EINSCHÄTZUNG]

---

## 5. Harmonik für Track-Übergänge

### 5.1 Theoretische Grundlage

Das Camelot Wheel ist „an adaptation of the traditional circle of fifths", entwickelt
von Mark Davis (Mixed In Key). 24 Positionen: 1A–12A innen (Moll), 1B–12B außen
(Dur). C-Dur = 8B, sein Parallelmoll a-Moll = 8A. [BELEG: DJ.Studio]

Open Key Notation nummeriert denselben Kreis mit Versatz: Dur bekommt „d", Moll
„m"; **Open-Key-Zahl = Camelot-Zahl + 5** (−12 bei Überlauf). [BELEG: openkeyscan.com]
⚠ Diese Umrechnungsregel stammt aus einer kommerziellen Sekundärquelle und ist
**nicht** aus einer akademischen Quelle bestätigt. Vor Implementierung an einer
Handvoll bekannter Tonarten gegenprüfen.

Die wissenschaftliche Fundierung liefert **Krumhansl & Kessler (1982)**: Aus
interkorrelierten Tonprofilen wird per Multidimensionaler Skalierung eine
vierdimensionale Karte der Tonartabstände gewonnen. Die Tonarten liegen auf der
Oberfläche eines **Torus**, „in which the circle of fifths and the parallel and
relative relations between major and minor keys are represented" — zwei Dimensionen
entsprechen dem Quintenzirkel, zwei einem Kreis alternierender Terzen.
[BELEG: Krumhansl & Kessler 1982]

Das Camelot Wheel ist damit eine **zweidimensionale Projektion einer
vierdimensionalen Struktur**. [EINSCHÄTZUNG] Praktische Folge: Es gibt konsonante
Beziehungen, die auf dem Rad nicht als Nachbarschaft sichtbar sind.

### 5.2 Welche Wechsel gelten als konsonant

DJ-Praxis (Camelot): gleiche Tonart, ±1 Position im selben Ring, oder Wechsel
zwischen Ringen bei gleicher Zahl (Parallel-Dur/Moll). [BELEG: DJ.Studio]

Wissenschaftlich operationalisiert, und für PB Studio direkt als Distanzmatrix
verwendbar, ist die MIREX-Gewichtung: [BELEG: MIREX Audio Key Detection]

```
w = 1,0 · r_korrekt + 0,5 · r_quinte + 0,3 · r_parallel + 0,2 · r_variante
```

| Beziehung | MIREX-Gewicht | Camelot |
|---|---|---|
| identische Tonart | 1,0 | gleiche Position |
| Quinte auf/ab | 0,5 | ±1 im selben Ring |
| Paralleltonart (C-Dur ↔ a-Moll) | 0,3 | gleiche Zahl, anderer Ring |
| Varianttonart (C-Dur ↔ c-Moll) | 0,2 | nicht benachbart |
| sonst | 0,0 | — |

⚠ Diese Gewichte sind **Fehlertoleranzen einer Evaluation**, keine
Konsonanzurteile. Sie messen „wie verzeihlich ist diese Verwechslung", was mit
„wie gut klingt dieser Übergang" korreliert, aber nicht identisch ist. Als
Rangordnung sind sie brauchbar, als absolute Konsonanzskala nicht.
[EINSCHÄTZUNG]

Auffällig ist, dass MIREX die Varianttonart (0,2) *niedriger* wertet als die
Paralleltonart (0,3), während das Camelot Wheel die Varianttonart gar nicht als
Nachbarschaft führt — beide Systeme sind sich hier einig, die Camelot-Regel ist
nur gröber. [EINSCHÄTZUNG]

### 5.3 Grenzen automatischer Tonarterkennung

Die dokumentierten Schwächen von Krumhansl-Schmuckler:

- **Kontextabhängigkeit.** Das Verfahren ist „strongly dependent on one set context
  for a key, and does not cope well with pretention to other keys or modes" —
  ein bei manchen Stilen häufiger Fall. [BELEG: Suchergebnis-Zusammenfassung
  akademischer Quellen; ⚠ ich konnte die Primärquelle nicht direkt einsehen]
- **Zeitliche Reihenfolge wird ignoriert.** Das Verfahren arbeitet auf einer
  Tonklassenverteilung; die Reihenfolge der Tonhöhen beeinflusst aber die
  wahrgenommene tonale Struktur. [BELEG: ebd.]
- **Genauigkeit.** In einer Korpusauswertung 75 % gegenüber 93 % für neuere
  Verfahren. [BELEG: ebd.; ⚠ Korpus und Metrik sind mir unbekannt, die Zahl ist
  **nicht** auf EDM übertragbar]

Für EDM speziell existiert ein Referenzdatensatz: **GiantSteps Key** (604 bzw. im
GiantSteps+-Set 600 zweiminütige Beatport-Ausschnitte mit Einzeltonart-Labels,
Kommentaren und Konfidenzangaben) und **GiantSteps Tempo** (661 Ausschnitte).
[BELEG: Knees et al., ISMIR 2015; Zenodo]

Das ist **direkt für dieses Projekt verwertbar**: die 35 eigenen Beatport-Tracks
mit BPM im Dateinamen sind eine sinnvolle, aber kleine Stichprobe. GiantSteps
liefert eine 20-fach größere, veröffentlichte Referenz mit derselben Herkunft
(Beatport) — damit werden eigene Messungen mit publizierten Werten vergleichbar.
[EINSCHÄTZUNG]

Eigene Anmerkung zur bestehenden Implementierung: PB Studio nutzt laut CLAUDE.md
Krumhansl-Kessler über librosa in `key_detector.py`. Der wesentliche Hebel ist
dort **nicht** ein anderes Verfahren, sondern die **Segmentierung**: eine
Tonartaussage pro DJ-Mix ist aus demselben Grund falsch wie ein Tempo pro Mix.
[EINSCHÄTZUNG]

---

## 6. Tabelle: umsetzbar mit vorhandenen Mitteln

Randbedingung durchgehend: Python 3.11, NumPy 1.26.4, librosa 0.11.0,
onnxruntime 1.19.2 mit `DmlExecutionProvider` — alles auf dieser Maschine
verifiziert vorhanden. [MESSUNG]

| # | Erkenntnis / Maßnahme | Benötigte Daten | Mittel | Aufwand | Erwarteter Nutzen |
|---|---|---|---|---|---|
| **U-1** | **Fourier-Tempogramm auf dichter Tempoachse** statt Autokorrelationsgitter (FMP C6S2: Koeffizienten einzeln für gewählte Θ berechnen) | Onset-Novelty-Kurve | librosa + numpy | **mittel** (1 Funktion, ~50 Z.) | **hoch** — hebt die harte 6,8-BPM-Grenze auf, ohne die 37 % kann kein Grid stimmen |
| **U-2** | **Tempo-Oktavkorrektur** über `librosa.feature.tempogram_ratio` (13 metrische Faktoren inkl. 3/2, 2/3, 4/3) | Onset-Envelope + Tempokandidat | librosa (eingebaut) | **niedrig** | **sehr hoch, gemessen** — allein die Faltung auf musikalische Faktoren senkt die Tempo-Spannweite der 19 Mixe von 33,8 % auf 1,5 % (3.5) |
| **U-3** | ~~Diagnose: stehen die Segment-Tempi in Verhältnissen 1, 4/3, 3/2, 2?~~ **In diesem Bericht bereits erledigt: ja, 97,2 %.** Siehe 3.5 | — | — | **erledigt** | — |
| **U-4** | **Beatgrid als Anker + BPM + Markerliste** statt Skalar (Mixxx-Modell, „every bar has a constant tempo") | Beatpositionen | eigenes Datenmodell | **mittel** (Schema + Persistenz + UI) | ⚠ **heruntergestuft.** Die 19 vermessenen Mixe sind tempostabil (3.5); das Marker-Modell löst dort nichts. Erst sinnvoll, wenn ein Mix mit *belegtem* echtem Tempowechsel vorliegt |
| **U-5** | **Segmentweise Tonart** statt eine pro Datei | Chroma pro Segment | vorhandener `key_detector` + Segmentierung | **niedrig** | **mittel** |
| **U-6** | **Konsonanzmatrix 24×24** nach MIREX-Gewichten für Übergangsbewertung | erkannte Tonarten | reine Tabelle | **sehr niedrig** | **mittel** — direkt für Track-Übergänge nutzbar |
| **U-7** | **Harmonic Change Detection Function** als Downbeat-*Hinweis*: `librosa.feature.tonnetz` ist exakt Hartes 6-D-Tonzentroid | Chroma | librosa (eingebaut) | **niedrig** | **mittel** — Harmonie ist laut Durand das stärkste Einzelmerkmal (61,0 %) |
| **U-8** | **Bass-Onset-Kanal** (< 150 Hz Spektralfluss) als zweiter Downbeat-Hinweis | Spektrogramm | librosa | **niedrig** | **mittel** |
| **U-9** | **Phrasenraster 4/8/16/32 Takte** ab bekanntem Downbeat als Schnitt-Priorität | Downbeats + Taktart | reine Arithmetik | **sehr niedrig** | **hoch** — aber vollständig abhängig von korrekten Downbeats |
| **U-10** | **Build-up-Erkennung** über monotonen Anstieg von RMS + spektralem Zentroid über 8–16 Takte | RMS, Zentroid, Downbeats | librosa | **niedrig** | **mittel** |
| **U-11** | **Drop-Kandidaten**: Energiesprung an einer Phrasengrenze nach energiearmem Abschnitt | wie U-10 | librosa | **niedrig** | **mittel**, mit Fehlalarmen |
| **U-12** | **Selbstähnlichkeits-Segmentierung** (beat-synchrone Merkmale + Novelty) für Strukturgrenzen | Chroma/MFCC beat-synchron | `librosa.segment` | **mittel** | **mittel–hoch** — Vorstufe für U-10/U-11 und für Mix-Segmentierung |
| **U-13** | **Bewertung nach CMLt/AMLt statt F-Measure**, Toleranz auf Framedauer statt 70 ms | Referenz-Beatgrids | `mir_eval` (Zusatzpaket) | **niedrig** | **hoch** — ohne das richtige Maß ist jeder Fortschritt ungeprüft |
| **U-14** | **GiantSteps Tempo/Key als externe Referenz** (661 bzw. 604 Beatport-Ausschnitte) | Download der Annotationen | — | **niedrig** | **hoch** — 20× größere Stichprobe als die eigenen 35 Tracks |
| **U-15** | **Beat This! ONNX unter DirectML** für echte Beats **und** Downbeats | Modell (97 MB) + Mel-Frontend | onnxruntime-directml | **hoch** (Frontend bitgenau nachbauen, Operator-Support prüfen) | **sehr hoch, falls es läuft** — der einzige belegte Weg zu brauchbaren Downbeats |

**Reihenfolge-Empfehlung.** [EINSCHÄTZUNG]

1. **U-2** — die Oktavkorrektur hat als einzige Maßnahme in diesem Bericht einen
   *gemessenen* Effekt (33,8 % → 1,5 %) und ist zugleich die billigste.
2. **U-13 und U-14** — ohne CMLt/AMLt als Maß und GiantSteps als Referenz bleibt
   jeder weitere Fortschritt unbewertbar. Insbesondere zeigt die Faltung in 3.5
   nur *Konsistenz*, nicht *Korrektheit*; das kann erst eine Referenz klären.
3. **U-1** — die feine Tempoachse. Sie hebt die 6,8-BPM-Schranke auf, die derzeit
   jedes Beatgrid begrenzt.
4. **U-15** als eigenständiger Machbarkeits-Spike, parallel und **ohne**
   Produktcode anzufassen: Modell laden, unter `DmlExecutionProvider` starten,
   Frontend gegen die Referenzimplementierung vergleichen.
5. **U-6, U-7, U-8** — billig, unabhängig, jeweils für sich nützlich.
6. **U-9 bis U-12** erst, wenn belastbare Downbeats vorliegen. Vorher bauen sie
   auf Sand.
7. **U-4** zurückgestellt, bis ein Mix mit belegtem echtem Tempowechsel vorliegt.

---

## 7. Was ausdrücklich NICHT umsetzbar ist

| Vorhaben | Warum nicht |
|---|---|
| **madmom / BeatNet** | `downbeats.py` erzeugt ein ndarray aus ungleichförmigen Sequenzen; NumPy ≥ 1.24 macht daraus einen `ValueError` statt einer Warnung. Zusätzlich `np.float` entfernt. Beides upstream offen. [BELEG: madmom #517, #542, NumPy-1.24-Notes] Keine Konfiguration umgeht das — die Messung des Projekts ist fremdbestätigt. |
| **DBN-Nachverarbeitung à la madmom** | Selbst der C++-Port von Beat This! implementiert sie als „madmom-compatible HMM" nach — sie wäre neu zu schreiben. [BELEG: beat_this_cpp] Laut ISMIR-2024-Paper aber **nicht nötig**: „surpasses the current state of the art in F1 score despite using no DBN". |
| **Beat Transformer, BEAST, BeatNet+** | PyTorch-Modelle ohne mir auffindbare ONNX-Konvertierung. Ohne CUDA/ROCm auf CPU lauffähig, aber das verletzt die Leistungserwartung und den Sinn der GPU-Regel. |
| **Zuverlässige Downbeats allein aus librosa** | Der Stand der Technik erreicht mit vier Merkmalsfamilien und CNN-Ensemble 72,6 %. Ein handgeschriebenes Heuristikverfahren auf einer davon liegt darunter — das ist die bereits gemessene Realität. [BELEG: Durand et al. 2016] **Kein Aufwand an dieser Stelle wird das ändern.** |
| **Funktionale Sektionslabels (Drop vs. zweiter Drop vs. Cooldown)** | Die Raveform-Taxonomie ist ausdrücklich funktional und energiezentriert definiert, von drei Fachleuten annotiert. Akustische Merkmale liefern Grenzen und Energie, nicht die Funktion. Braucht ein trainiertes Modell. [BELEG: Raveform] |
| **Tonarterkennung auf Mix-Ebene** | Strukturell dasselbe Problem wie ein Tempo pro Mix. Keine Verfahrensfrage. |
| **Camelot-Regeln als Konsonanz*wahrheit*** | Das Rad ist eine 2-D-Projektion der 4-D-Torus-Struktur von Krumhansl & Kessler. Es ist eine brauchbare Heuristik, kein Modell tonaler Nähe. [BELEG: Krumhansl & Kessler 1982] [EINSCHÄTZUNG zur Projektionsaussage] |
| **`librosa.beat_track` als Beatgrid-Lieferant für Schnitt** | Das Tempogitter erlaubt bei 126 BPM bestenfalls 123,05 BPM (−2,34 %) → 5,7 s Drift über 4 Minuten. Für Schnitt auf 40-ms-Framerastern unbrauchbar. [MESSUNG] Für grobe Klassifikation weiterhin geeignet. |

### Offen geblieben — konnte ich nicht belegen

- **Genauigkeitswerte von Yadati et al. (2014)** zur Drop-Erkennung. Die
  ISMIR-PDF ließ sich maschinell nicht auslesen; ich habe nur Sekundärangaben.
- **Ob `DmlExecutionProvider` den Beat-This-Transformer trägt.** Ungetestet.
- **Ob sich das torchaudio-Mel-Frontend (`normalized="frame_length"`, `power=1`)
  bitgenau in librosa nachbilden lässt.** Ungetestet, aber entscheidend.
- **Die Primärquelle zu den KS-Schwächen** (75 % vs. 93 %). Nur über
  Suchzusammenfassung; Korpus und Metrik unbekannt.
- **Die Open-Key-↔-Camelot-Umrechnung (+5)** stammt nur aus einer kommerziellen
  Quelle.

---

## 8. Quellenverzeichnis

**Universitär / Lehrmaterial**

- Meinard Müller, *Fundamentals of Music Processing*, FMP Notebooks, AudioLabs
  Erlangen — Kapitel 6 (Tempo and Beat Tracking):
  https://www.audiolabs-erlangen.de/resources/MIR/FMP/C6/C6.html
- FMP C6S2, Fourier-Tempogramm (Definition, Tempomenge Θ = [30:600] BPM,
  Fenster 4–12 s, Einzelberechnung der Koeffizienten):
  https://www.audiolabs-erlangen.de/resources/MIR/FMP/C6/C6S2_TempogramFourier.html
- Müller, *Tempo and Beat Tracking* (Springer-Kapitel):
  https://link.springer.com/content/pdf/10.1007/978-3-319-21945-5_6.pdf
- Open Music Theory (VIVA Pressbooks) — Hypermeter, Downbeat, Backbeat:
  https://viva.pressbooks.pub/openmusictheory/chapter/hypermeter2/
  https://viva.pressbooks.pub/openmusictheory/back-matter/glossary/
- Krumhansl & Kessler (1982), Torus-Repräsentation der Tonartabstände:
  https://www.researchgate.net/publication/16065411_Tracing_the_dynamic_changes_in_perceived_tonal_organization_in_a_spatial_representation_of_musical_keys
- Jarno Seppänen, *Tatum Grid Analysis of Musical Signals* (TU Tampere):
  https://citeseerx.ist.psu.edu/document?doi=23bc0cadb746ebdeb2a75aafde48d0f51ac2bce4&repid=rep1&type=pdf

**ISMIR / MIR-Fachliteratur**

- Durand, Bello, David, Richard (2016), *Robust Downbeat Tracking Using an Ensemble
  of Convolutional Networks*: https://arxiv.org/abs/1605.08396
- Böck, Krebs, Widmer (2016), *Joint Beat and Downbeat Tracking with Recurrent
  Neural Networks*, ISMIR: https://archives.ismir.net/ismir2016/paper/000186.pdf
- Durand & Essid (2016), *Downbeat Detection with Conditional Random Fields and
  Deep Learned Features*: https://archives.ismir.net/ismir2016/paper/000213.pdf
- Krebs et al. (2016), *Downbeat Tracking Using Beat-Synchronous Features and RNNs*:
  https://archives.ismir.net/ismir2016/paper/000249.pdf
- Foscarin, Schlüter, Widmer (2024), *Beat this! Accurate beat tracking without DBN
  postprocessing*, ISMIR 2024: https://arxiv.org/abs/2407.21658
- Heydari et al., *BeatNet: CRNN and Particle Filtering for Online Joint Beat,
  Downbeat and Meter Tracking*, ISMIR 2021:
  https://archives.ismir.net/ismir2021/paper/000033.pdf
- Chang et al. (2024), *BEAST: Online Joint Beat and Downbeat Tracking Based on
  Streaming Transformer*: https://arxiv.org/pdf/2312.17156
- Schreiber & Müller, *Exploiting Global Features for Tempo Octave Correction*:
  https://www.researchgate.net/publication/269294941_Exploiting_global_features_for_tempo_octave_correction
- Harte, Sandler, Gasser (2006), *Detecting Harmonic Change in Musical Audio*:
  https://ofai.at/papers/oefai-tr-2006-13.pdf
- Yadati et al. (2014), *Detecting Drops in Electronic Dance Music*, ISMIR:
  https://archives.ismir.net/ismir2014/paper/000297.pdf
- *Raveform: A Dataset of Metrical and Functional Structure Annotations*, TISMIR:
  https://transactions.ismir.net/articles/10.5334/tismir.288
- Schwarz et al. (2020), *Automatic Detection of Cue Points for DJ Mixing*:
  https://arxiv.org/abs/2007.08411
- Kim et al. (2020), *A Computational Analysis of Real-World DJ Mixes using
  Mix-To-Track Subsequence Alignment*, ISMIR:
  https://archives.ismir.net/ismir2020/paper/000352.pdf
- Knees et al. (2015), *Two Data Sets for Tempo Estimation and Key Detection in
  Electronic Dance Music Annotated from User Corrections*, ISMIR:
  https://archives.ismir.net/ismir2015/paper/000246.pdf ·
  Daten: https://github.com/GiantSteps/giantsteps-tempo-dataset ·
  https://github.com/GiantSteps/giantsteps-key-dataset
- Raffel et al. (2014), *mir_eval: A Transparent Implementation of Common MIR
  Metrics*: https://archives.ismir.net/ismir2014/paper/000320.pdf
- MIREX Audio Key Detection, Ergebnis- und Metrikseite:
  https://nema.lis.illinois.edu/nema_out/mirex2016/results/akd/gsteps/summary.html
- Peeters (2005), *Rhythm Classification Using Spectral Rhythm Patterns*, ISMIR;
  Prockup et al. (2015), *Modeling Musical Rhythm at Scale with the Music Genome
  Project*, WASPAA — beide zitiert im Docstring von `librosa.feature.tempogram_ratio`

**Werkzeugdokumentation**

- librosa 0.11.0, installierte Fassung (`librosa.feature.tempo`,
  `librosa.beat.beat_track`, `librosa.feature.tempogram_ratio`,
  `librosa.feature.tonnetz`, `librosa.tempo_frequencies`) — auf dieser Maschine
  ausgelesen: https://librosa.org/doc/latest/
- Mixxx-Handbuch 13.4, Beat Detection:
  https://manual.mixxx.org/2.5/en/chapters/preferences/beat_detection
- Mixxx Wiki, *Beat and Bar Edit Workflow* (BeatGrid vs. BeatMap,
  adaptive Gitterregionen):
  https://github.com/mixxxdj/mixxx/wiki/Beat-and-Bar-Edit-Workflow
- CPJKU/beat_this — Referenzimplementierung, MIT, `preprocessing.py`:
  https://github.com/CPJKU/beat_this
- mosynthkey/beat_this_cpp — ONNX-Export (`onnx/beat_this.onnx`, Opset 14),
  MIT: https://github.com/mosynthkey/beat_this_cpp
- madmom Issue #517 (ragged sequences in `downbeats.py`):
  https://github.com/CPJKU/madmom/issues/517
- madmom PR #542 (`np.float`/`np.int` entfernen):
  https://github.com/CPJKU/madmom/pull/542
- NumPy 1.24 Release Notes (ragged → `ValueError`, `np.float` entfernt):
  https://numpy.org/devdocs/release/1.24.0-notes.html

**DJ-Praxis (Sekundärquellen, entsprechend gekennzeichnet)**

- DJ.Studio, *The DJ's Guide to the Camelot Wheel and Harmonic Mixing*:
  https://dj.studio/blog/camelot-wheel
- openkeyscan.com, *Open Key vs Camelot Notation*:
  https://www.openkeyscan.com/open-key-vs-camelot
- Wikipedia, *Drop (music)*: https://en.wikipedia.org/wiki/Drop_(music)

---

## Anhang: Reproduktion der Gittermessung

Auf dieser Maschine ausgeführt, `.venv` mit librosa 0.11.0 / NumPy 1.26.4:

```python
import numpy as np, librosa
tf = librosa.tempo_frequencies(384, hop_length=512, sr=22050)
# tf[18] = 143.555, tf[19] = 135.999, tf[28] = 92.285
grid = tf[1:60]
for t in [126, 128, 138, 174]:
    i = int(np.argmin(np.abs(grid - t)))
    print(t, grid[i], f"{100*(grid[i]-t)/t:+.2f} %")
# 126 -> 123.05  (-2.34 %)
# 128 -> 129.20  (+0.94 %)
# 138 -> 136.00  (-1.45 %)
# 174 -> 172.27  (-1.00 %)
```

Gitterabstand im Bereich 129–172 BPM: 6,15 bis 10,77 BPM.

## Anhang B: Reproduktion der Oktav-Analyse aus 3.5

Datenquelle: `docs/measurements/2026-08-31-mix-tempo-drift.json` (Schema 1,
19 Dateien, 800 Segmente à 30 s, `hop_length=512`, `refine_rel=0.02`) — nicht von
mir erzeugt, unverändert gelesen.

```python
import json, collections, numpy as np
d  = json.load(open('docs/measurements/2026-08-31-mix-tempo-drift.json', encoding='utf-8'))
by = collections.defaultdict(list)
for r in d['measurements']:
    by[r['sha256_16']].append(r['local_bpm'])

fac = np.array([0.5, 2/3, 0.75, 1, 4/3, 1.5, 2])
vor, nach = [], []
for b in by.values():
    b = np.array(b); med = np.median(b)
    vor.append((b.max() - b.min()) / med)
    j = np.argmin(np.abs(b[:, None] / med - fac), axis=1)   # Oktave falten
    c = b / fac[j]
    nach.append((c.max() - c.min()) / np.median(c))

print(np.median(vor), np.median(nach))   # 0.338 -> 0.015
```

Anteil aller 800 Verhältnisse `local_bpm / median` innerhalb ±3 % eines Faktors
aus `fac`: **97,2 %**.

