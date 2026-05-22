# Implementierungsplan: Timeline Playback & DJ-Beatgrid

## Technical Context
* **Target Project:** `PBStudio.UI` (WPF C# .NET) & `src/pb_studio` (Python)
* **WPF Version:** .NET SDK-basiert WPF Core
* **Python Runtime:** Python 3.11.x, NumPy 1.26.4
* **Hardware Profile:** AMD Radeon GPU mit DirectML & AMF Hardware Encoding
* **FFmpeg Profile:** Gyan.dev 6.x mit `h264_amf` / `hevc_amf` Codecs

---

## Proposed Changes

### 1. [NEW] Custom Control: [WaveformRenderer.cs](file:///C:/Users/david/Documents/Pb_studio_AMD_version/PBStudio.UI/Controls/WaveformRenderer.cs)
Wir erstellen ein GPU-optimiertes Custom Control, das von `FrameworkElement` erbt. Es rendert die gesamte Audio-Wellenform über eine hocheffiziente `StreamGeometry` und zeichnet sie in den `DrawingContext`.
* **Vorteil:** Reduziert die Rendering-Last von 1000 separaten WPF-Rechtecken auf einen einzigen Drawing-Call, was Ruckler beim Zoomen/Scrollen eliminiert.
* **Darstellungsstil:** Gefüllte Wellenform um die Mittelachse (symmetrisch nach oben und unten), gezeichnet mit einer harmonischen Akzentfarbe (`AbletonBlue` oder per Property anpassbar).

### 2. [MODIFY] Playback- & Transition-Logik: [TimelineView.xaml.cs](file:///C:/Users/david/Documents/Pb_studio_AMD_version/PBStudio.UI/Views/TimelineView.xaml.cs)
Wir überarbeiten die Playback-Logik, damit der Übergang an Clipgrenzen nahtlos funktioniert:
* **Zustandssicherung:** Einführung eines transienten Flags `_wasPlayingBeforeReload` zur Kennzeichnung aktiver Wiedergabe während des Clipwechsels.
* **Automatischer Übergang:** In `PlaybackTimer_OnTick` ermitteln wir bei Erreichen des Clip-Endes (`PreviewPlayer.Position.TotalSeconds >= _loadedClipEnd - 0.05`), ob in der sortierten Liste `_viewModel.TimelineEntries` ein nächster Clip existiert.
  - Wenn ja: Wir setzen `_wasPlayingBeforeReload = true`, selektieren den nächsten Clip (`_viewModel.SelectedEntry = nextEntry`) und überlassen dem UI den Ladevorgang. Der Playback-Timer wird *nicht* gestoppt.
  - Wenn nein: Wir stoppen die Wiedergabe normal am Ende der Timeline.
* **Auto-Resume:** In `PreviewPlayer_OnMediaOpened` fangen wir das Flag ab: Wenn `_wasPlayingBeforeReload` wahr ist, rufen wir sofort `PreviewPlayer.Play(); _playbackTimer.Start();` auf, setzen das Flag auf `false` zurück und führen ein nahtloses Seek auf den Clipstart des neuen Clips aus.

### 3. [MODIFY] XAML-Styling & DJ-Beatgrid: [TimelineView.xaml](file:///C:/Users/david/Documents/Pb_studio_AMD_version/PBStudio.UI/Views/TimelineView.xaml)
* **Wellenform-Einbindung:** Ersetzung der `ItemsControl` für die Haupt-Waveform der A1-Spur durch unser neues `<controls:WaveformRenderer>`-Control.
* **High-Contrast DJ-Beatgrid:** Überarbeitung der `ItemsControl` für `UIBeatMarkers`:
  - Rote, deutliche Downbeat-Linien (`#FFFF3B30`, `StrokeThickness="1.4"`, `Opacity="0.85"`).
  - Eisblaue Standard-Beats (`#FF00D2FF`, `StrokeThickness="0.6"`, `Opacity="0.35"`).
  - Taktnummer-Badges: Ein kleiner, abgerundeter Badge direkt am Downbeat-Kopf mit dunkelgrauem, halbtransparentem Hintergrund (`#CC111111`), feinem rotem Rand und weißem Takt-Text (`BAR 1`, `BAR 2` ...). Dies garantiert 100%ige Lesbarkeit bei jedem Helligkeitswert der dahinterliegenden Wellenform.
* **Phrasen-Wasserzeichen:** Die zarte Hintergrund-Farbcodierung der Phrasensegmente (Intro, Verse, Chorus, Outro, Break, Bridge) in der A1-Lane wird verfeinert und erhält gut lesbare, leicht transparente Bezeichnungen direkt in den jeweiligen Sektionen.

---

## Requirement Coverage Map

| Anforderungs-ID | Beschreibung | Ziel-Dateien | Implementierungs-Ansatz |
|-----------------|--------------|--------------|-------------------------|
| **FR-001** | WaveformRenderer Custom Control | `PBStudio.UI/Controls/WaveformRenderer.cs` | FrameworkElement + StreamGeometry Drawing |
| **FR-002** | Playback-Transition Logik | `PBStudio.UI/Views/TimelineView.xaml.cs` | Transientes Flag `_wasPlayingBeforeReload` + Auto-Resume |
| **FR-003** | UI-Integration Waveform & Beatgrid | `PBStudio.UI/Views/TimelineView.xaml` | Einbettung Renderer + DataTemplates für Downbeats & Badges |
| **FR-004** | Phrasen-Wasserzeichen | `PBStudio.UI/Views/TimelineView.xaml` | Segment ItemsControl Opacity & TextBlock Labels |
| **TR-005** | Build- & Verifikations-Pipeline | `PBStudio.UI/PBStudio.UI.csproj` & Tests | dotnet build Release + pytest regression run |

---

## Instructions Check

Wir prüfen die geplante Implementierung gegen die non-negotiable **IRON RULES** aus [CLAUDE.md](file:///C:/Users/david/Documents/Pb_studio_AMD_version/CLAUDE.md):

| Regel-Kategorie | Status | Evidenz & Validierung |
|-----------------|--------|-----------------------|
| **AMD DirectML Only** | **PASS** | Keine unkompilierten NVIDIA-Bibliotheken verwendet. Reine WPF C# und Standard-Python-Tests. |
| **Windows Pathing** | **PASS** | Pfadformate nutzen Standard WPF-Ressourcen-URIs und `pathlib.Path` im Backend. |
| **Build & Deployment** | **PASS** | Der WPF-Release-Build wird asynchron nach dem Code-Edit autonom ausgeführt (`dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`). |
| **Honesty Pledge** | **PASS** | Jede Implementierungsstufe wird real per Build-Output und Testsuite-Lauf verifiziert. |

---

## Verifikationsplan

### Automatisierte Verifikation & Build
* **Kompilierung:** Ausführung des WPF-Release-Builds zur Prüfung auf Syntaxfehler und Compiler-Warnungen:
  ```powershell
  dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
  ```
* **Backend-Tests:** Lauf der Python-Testsuite zur Absicherung gegen Regressionen im Pacing-/Timeline-Datenaustausch:
  ```powershell
  pytest Tests/ -x -q
  ```

### Manuelle Verifikation
* **Timeline-Wiedergabe:** Abspielen der Timeline über mehrere Clipgrenzen hinweg. Der Playhead muss kontinuierlich über die Clip-Grenzen laufen, und der Player muss das nächste Video nahtlos ohne Ruckler oder Zurückspringen laden und direkt abspielen.
* **Visuelle Qualitätskontrolle:** 
  - Die Wellenform auf der A1-Lane muss geschlossen, lückenlos und flüssig gerendert sein.
  - Beim Scrollen/Zoomen darf die Timeline nicht mehr hängen oder ruckeln.
  - Das Beatgrid muss mit leuchtend roten Downbeats, eisblauen Standardbeats und perfekt lesbaren Taktnummer-Badges (z. B. `BAR 32`) aufwarten.
  - Die Phrasen im Hintergrund müssen eine harmonische, dezente farbliche Trennung mit dezenten Labels aufweisen.
