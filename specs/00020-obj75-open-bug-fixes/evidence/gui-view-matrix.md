# OBJ-75 Named Main-View QC Matrix

Source of truth: `PBStudio.UI/MainWindow.xaml`. Dialogs are excluded.

| # | Main view | Launch | Data load | Interaction | Switch away/back | Receipt |
|---:|---|---|---|---|---|---|
| 1 | ProjectOverviewView | [X] | [X] | [X] | [X] | `tab_projekt.png`, R1+R2 |
| 2 | AudioLibraryView | [X] | [X] | [X] | [X] | `tab_audio.png`, R1+R2 |
| 3 | VideoLibraryView | [X] | [X] | [X] | [X] | `tab_video.png`, R1+R2 |
| 4 | DirectorView | [X] | [X] | [X] | [X] | `tab_ki-regie.png`, R1+R2 |
| 5 | TimelineView | [X] | [X] | [X] | [X] | `tab_timeline.png`, R1+R2 |
| 6 | ProductionView | [X] | [X] | [X] | [X] | `tab_export.png`, R1+R2 |
| 7 | BrainView | [X] | [X] | [X] | [X] | `tab_hirn.png`, R1+R2 |
| 8 | SettingsView | [X] | [X] | [X] | [X] | `tab_settings.png`, R1+R2 |
| 9 | VramTelemetryView | [X] | [X] | [X] | [X] | `tab_performance.png`, R1+R2 |
| 10 | ModelManagerView | [X] | [X] | [X] | [X] | `tab_modelle.png`, R1+R2 |
| 11 | ChatView | [X] | [X] | [X] | [X] | `tab_chat.png`, R1+R2 |
| 12 | TerminalView | [X] | [X] | [X] | [X] | `tab_terminal.png`, R1+R2 |
| 13 | MediaIngestView | [X] | [X] | [X] | [X] | `tab_ingest.png`, R1+R2 |
| 14 | AnchorView | [X] | [X] | [X] | [X] | `tab_anchor.png`, R1+R2 |

## Screenshot receipts

- Runde 1: `gui_screenshots/obj75_round1`, 14 PNGs, 09:22:58–09:24:37
  CEST; sortierter Name/SHA-256-Manifestdigest
  `50315cee922fb9c76d95bc25923265b18399f1dfcf5e9fc40253caa33683831b`.
- Runde 2: `gui_screenshots/obj75_round2`, 14 PNGs, 09:25:01–09:26:41
  CEST; sortierter Name/SHA-256-Manifestdigest
  `4a3cf1375538e5d27da6ed0a4cab03940a897dfb7040abb2a4a2aa21fa2a06fc`.
- Automation: `Tests/gui_screenshot_v4.py`; Win32 `PrintWindow` erfasste nur
  das WPF-Fenster. Beide Runden aktivierten jede View und warteten auf sichtbaren
  Inhalt. Die zweite Runde belegt den erneuten Rückwechsel.
- Visuelle Kontrolle der zweiten Runde: 14/14 kohärent, Backend verbunden, keine
  Crash- oder leere Hauptview.

Der einmalige A→B-Auswahlsonderfall bleibt getrennt unter T049; die 28
Hauptview-Screenshots müssen dafür nicht wiederholt werden.
