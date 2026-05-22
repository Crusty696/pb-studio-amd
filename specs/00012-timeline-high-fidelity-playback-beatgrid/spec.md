# Spezifikation: Timeline High-Fidelity Playback & DJ-Beatgrid

## Problem Statement

### Playback-Ruckeln & Zurückspringen
* **Schmerzpunkt:** Der Playhead in der Timeline stottert beim Abspielen, springt unkontrolliert zurück oder bricht an Clipgrenzen (den Grenzen der einzelnen Cuts) abrupt ab. Der Grund dafür liegt darin, dass der Code-Behind (`TimelineView.xaml.cs`) in `PlaybackTimer_OnTick` bei Erreichen des Clip-Endes hart stoppt (`_playbackTimer.Stop(); SeekToClipStart();`) anstatt das Abspielen nahtlos im nächsten Clip fortzusetzen. Wenn die Position über die Kante läuft, versucht das ViewModel den nächsten Clip zu selektieren, was ein erneutes Laden über den Player triggert. Weil der Timer gestoppt wurde, pausiert das Abspielen auf Frame 1 des neuen Clips.
* **Ziel:** Ein kontinuierlicher, unterbrechungsfreier Playback-Lauf über alle Clipgrenzen hinweg. Der Playhead wandert flüssig. Erreicht ein Clip sein Ende, wird der nächste Clip in chronologischer Reihenfolge automatisch geladen und direkt unterbrechungsfrei weitergespielt.

### Visuelle Qualität der Waveform
* **Schmerzpunkt:** Das Zeichnen von 1000 einzelnen Rechtecken über ein WPF `ItemsControl` für die Haupt-Waveform auf der A1-Spur erzeugt massiven UI-Layout-Overhead. Jeder Zoom- und Scroll-Pass verlangsamt den WPF-Rendering-Thread, was zu Mikrorucklern führt. Zudem erzeugen Rundungsfehler unschöne vertikale Spalten zwischen den Amplitudenbalken, wodurch die Wellenform lückenhaft und unprofessionell aussieht.
* **Ziel:** Eine hochperformante, GPU-beschleunigte Wellenformdarstellung. Wir implementieren ein Custom Control `WaveformRenderer`, das alle Wellenform-Daten in einer einzigen, zusammenhängenden und eingefrorenen `StreamGeometry` zeichnet. Dies reduziert die Rendering-Last um 99% und liefert eine lückenlose, flüssige Darstellung wie in professionellen DAWs oder DJ-Tools.

### DJ-Style Beatgrid & Phrasen-Wasserzeichen
* **Schmerzpunkt:** Das aktuelle Beatgrid auf der A1-Spur ist visuell flach und schwer lesbar. Downbeats werden unzureichend hervorgehoben, Standard-Beats haben zu geringen Kontrast zur Waveform, und es fehlen lesbare Taktnummern. Song-Sektionen (Phrasen) sind kaum erkennbar.
* **Ziel:** Ein optisch herausragendes Traktor-/Rekordbox-artiges Beatgrid:
  1. **Downbeats (Beginn eines Taktes):** Kräftige rote Vertikallinien (`#FFFF3B30`, `StrokeThickness="1.4"`, `Opacity="0.85"`).
  2. **Standard-Beats:** Feine, eisblaue Linien (`#FF00D2FF`, `StrokeThickness="0.6"`, `Opacity="0.35"`).
  3. **Taktnummer-Badges:** Oberhalb jedes Downbeats platzieren wir ein kontrastreiches, abgerundetes Badge mit dunkelgrauem, halbtransparentem Hintergrund (`#CC111111`), feiner roter Umrandung und weiße Taktnummer (z. B. `BAR 12`). Dies sichert 100%ige Lesbarkeit bei jeder Wellenform-Helligkeit.
  4. **Zarte Phrasen-Hintergründe & Wasserzeichen:** Mapping aller typischen Sektionen im Hintergrund der A1-Lane mit feiner Opazität (12%) und dezenten, halbdurchsichtigen Wasserzeichen-Texten (z. B. "INTRO" = Deep Purple, "VERSE" = AbletonBlue, "CHORUS" = AbletonAccent, "BREAK" = Yellow, "OUTRO" = DarkGrey).

---

## Scope

### Included
* Implementierung des `WaveformRenderer` Custom Controls in WPF C#.
* Anpassung von `TimelineView.xaml.cs` an nahtlose Playback-Übergänge.
* XAML-Erweiterungen in `TimelineView.xaml` für rote Downbeats, eisblaue Standard-Beats, Taktnummern und Phrasensegmente.
* Build- und Regressionstests.

### Excluded
* Änderungen am Audio-Dekodierungsprozess im Python-Backend.
* Multi-Kanal Audio-Analyse oder Sound-Treiber-Anpassungen (z. B. ASIO).

### Edge Cases & Boundaries
* **Sehr kurze Timeline-Einträge:** Clips unter 0.5 Sekunden Dauer müssen stabil geladen werden.
* **Herauszoomen auf maximale Timeline-Breite:** Die Wellenform muss sich performant komprimieren lassen, ohne abzustürzen.

---

## Technical Objectives

* **OBJ-1:** Rendering-Overhead der Waveform durch `StreamGeometry` um mindestens 95% verringern.
* **OBJ-2:** Nahtloses Abspielen über Clip-Grenzen hinweg ohne Wiedergabe-Stopps oder Frame-Freezes.
* **OBJ-3:** Perfekte visuelle DJ-Beatgrid-Lesbarkeit bei jeder Wellenform-Helligkeit durch kontraststarke Badges sichern.
* **OBJ-4:** Musikalische Struktur durch Phrasen-Wasserzeichen auf der A1-Spur visuell hervorheben.

---

## Integration Points

* **WPF-Interface:** `TimelineView` (XAML / Code-Behind) bindet an das existierende ViewModel `TimelineViewModel`.
* **Backend-API:** Datenaustausch über das JSON-Format der `TimelineEntries` bleibt unverändert.

---

## Requirements

* **FR-001:** Erstellung des `WaveformRenderer` Custom Controls (erbt von `FrameworkElement`).
* **FR-002:** Playback-Zustandsmaschine in `TimelineView.xaml.cs` verwaltet das transiente Flag `_wasPlayingBeforeReload` zur Absicherung nahtloser Wiedergabe.
* **FR-003:** Einbettung des `WaveformRenderer` und Definition des DJ-Beatgrids in `TimelineView.xaml` (rote Downbeats, eisblaue Beats, kontrastreiche Badges).
* **FR-004:** Integration von Song-Phrasen-Hintergründen mit 8%-12% Opazität und dezenten Text-Wasserzeichen in der A1-Lane.
* **TR-005:** Durchführung des WPF Release-Builds und Ausführung der Backend-Testsuite zur Vermeidung von Regressionen.

---

## Assumptions & Risks

* **Annahme:** Die Grafikkarte unterstützt Standard DirectX-WPF-Hardwarebeschleunigung für die StreamGeometry-Darstellung.
* **Risiko:** Schnelle Clipwechsel könnten den Media-Player blockieren. *Lösung:* Wiedergabe-Resume erfolgt asynchron nach `MediaOpened`.

---

## Implementation Signals

* **`[SIGNAL:WPF-BUILD-OK]`**: Erfolgreicher WPF-Release-Compiler-Run.
* **`[SIGNAL:TEST-SUITE-GREEN]`**: Python-Backend Tests laufen fehlerfrei durch.

---

## Success Criteria

* **SC-001 [OBJ-2]:** Beim Erreichen des Clip-Endes springt das Playback nahtlos zum nächsten Clip, lädt ihn und spielt ihn direkt ab.
* **SC-002 [OBJ-1]:** Flüssiges Zoomen und Scrollen der Wellenform ohne FPS-Einbrüche im Rendering-Thread.
* **SC-003 [OBJ-3]:** Kontrastreiche Taktnummer-Badges (`BAR 1`, `BAR 2` ...) sind unabhängig von der Waveform-Helligkeit perfekt ablesbar.
* **SC-004 [OBJ-4]:** Phrasen im Hintergrund (z. B. VERSE, CHORUS) bieten eine sanfte, farblich codierte Orientierungshilfe mit gut lesbaren Bezeichnungen.

---

## Glossary

* **Playhead:** Der vertikale rote Strich in der Timeline, der die aktuelle Wiedergabeposition anzeigt.
* **Waveform:** Die visuelle Darstellung der Audio-Amplitude über die Zeitachse.
* **Downbeat:** Der erste Schlag eines Taktes, meist farblich und strukturell im Beatgrid hervorgehoben.
* **StreamGeometry:** Ein hocheffizientes WPF-Geometrieobjekt zum Zeichnen komplexer Pfade mit direkter GPU-Unterstützung.
