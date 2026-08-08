# T337 — Release GUI, Modelle und Projektwechsel

Status: CONFIRMED PASS

## Release-GUI

- Release-Build: 0 Fehler, 0 Warnungen.
- 14/14 sichtbare Bereiche geprüft:
  PROJEKT, AUDIO, VIDEO, KI-REGIE, TIMELINE, EXPORT, HIRN, SETTINGS,
  PERFORMANCE, MODELLE, CHAT, TERMINAL, INGEST und ANCHOR.
- Die zwölf Kernbereiche sowie die zwei erweiterten Bereiche renderten
  nichtleer und ohne unbehandelte UI-/Task-Exception.
- Postfix-XAML-Gate:
  `xaml-regression-cycle-8.json`, Status `pass`.
- Export- und Terminal-Logs sind sichtbar und kopierbar.
- WPF-Endlog: 763 Bytes; 0 XamlParse-, Path/XPath-, UI- und
  UnobservedTask-Exceptions.

## XAML-Root-Cause

Der Export-Log verwendete für String-Items implizites bidirektionales
TextBox-Binding ohne `Path`. Dies erzeugte einen 28,24-GB-Exception-Sturm.
`ProductionView.xaml` bindet Logzeilen jetzt explizit mit
`Text="{Binding Path=., Mode=OneWay}"`.

Der komprimierte Originalbeleg liegt in
`evidence/T337-gui/wpf-cycle-4-exception-storm.tar.zst`.

## Modelle

- Cycle 4: LM Studio live, ein aktives installiertes Modell, UI/API-Parität.
- Cycle 8: `1 installiert · 8 verfügbar`, LM-Studio-URL sichtbar,
  Export-/Terminal-Regression PASS.
- Cycle 12 live:
  LM Studio und Ollama erreichbar, 13 zusammengeführte Modelle;
  Recommendation für `video_captioning/balance` wählte
  `moondream:latest`.
- Die falsche Aussage „kein Provider erreichbar“ bei live erreichbarem
  Textprovider ohne Vision-Eignung wurde auf den bestehenden
  capability-genauen No-suitable-Vertrag korrigiert.
- Öffentliche DTOs und OpenAPI blieben unverändert.
- Regression:
  `Tests/test_models_capability_routing.py`.

Root-Cause-Beleg:
`evidence/T337-gui/models-recommendation-root-cause.md`.

## Projektwechsel während eines Jobs

Cycle 12, Release-Binary:

- reales H.264-AMF-Rendering sichtbar gestartet;
- Task `e19882c8`, Queue-Job
  `d087637c-b6dc-46b9-93f2-883c8ee272bd`;
- Partial-Zustand sichtbar: 140/190.051 Frames, 60 %, out_time 4,666667 s;
- Quellprojekt während des Jobs über das GUI geschlossen;
- Render nach 9,4 s kooperativ abgebrochen;
- Queue terminal `failed`, Fehler `cancelled`;
- FFmpeg-Prozesse nach Abbruch: 0;
- natives `#32770`-Projektfenster erkannt, Button
  `Ordner auswählen` bestätigt;
- Zielprojekt
  `ReleaseSmoke_20260727_083320` über den GUI-Dialog geöffnet;
- Export anschließend sichtbar `Bereit für Rendering`;
- kein stale Abbrechen-Control;
- kein Ziel- oder Stagingartefakt für Cycle 12;
- Quell- und Zielprojektdateihashes vor/nach dem Lauf identisch;
- keine PB-Studio-, Backend- oder FFmpeg-Testprozesse verblieben.

Kanonischer Bericht:
`evidence/T337-gui/project-switch-cycle-12.json`.

Screenshots:

- `screenshots-cycle-12-project-switch/export-visible-failure.png`
- `screenshots-cycle-12-project-switch/export-running-partial-progress.png`
- `screenshots-cycle-12-project-switch/project-closed-during-running-job.png`
- `screenshots-cycle-12-project-switch/project-after-running-job-switch.png`
- `screenshots-cycle-12-project-switch/export-after-project-switch.png`

Cycle 10 und 11 bleiben als falsifizierte UIA-Dialogerkennungsversuche
gespeichert. Die bestätigte Win32-Probe und Cycle 12 verwendeten die
unabhängig bewiesene native Fenster-/Buttonerkennung.

## Postfix-Codec-Gates

Der Cycle-9-Reproducer bewies, dass der produktive Router den kanonischen
Pacing-Abschluss übersprang. Nach dem outputrelevanten Fix wurden beide
Codecs vollständig neu ausgeführt.

### H.264 AMF

- Router-Finalizer: aktiv
- Timeline: 0–6.335,027 s
- 190.051/190.051 Frames, `progress=end`
- Container/Video: 6.335,033333 s; Audio: 6.335,040000 s
- True Peak: −1,06 dBTP
- Endstille: 58,215083 s
- Vollscan: 106/106 Segmente
- 1.962-s-Fenster: 25/25 unterschiedliche Frames
- Terminalfenster: 60 Samples, 56 unterschiedliche Frames
- Schwarz-/Freezeintervalle: 0/0
- SHA-256:
  `4bf4c2c83dd6db9a047d1e1541b237cbbfe955f7303b445dfb6fe9b3d33cc366`

### HEVC AMF

- Router-Finalizer: aktiv
- Timeline: 0–6.335,027 s
- 190.051/190.051 Frames, `progress=end`
- Container/Video: 6.335,033333 s; Audio: 6.335,040000 s
- True Peak: −1,06 dBTP
- Endstille: 58,215083 s
- Vollscan: 106/106 Segmente
- 1.962-s-Fenster: 25/25 unterschiedliche Frames
- Terminalfenster: 60 Samples, 54 unterschiedliche Frames
- Schwarz-/Freezeintervalle: 0/0
- SHA-256:
  `9ad896ef336b3a0da72fc936efa19dcadd9931423ba40d6146316b508eb913e7`

Die Postfix-Artefakte sind jeweils byteidentisch zu den bereits
vollständig geprüften T335-/T336-Artefakten.

Kanonische Belege:

- `evidence/T337-gui/postfix-full-h264-export/completed.json`
- `evidence/T337-gui/postfix-full-h264-visual-qc/qc-result.json`
- `evidence/T337-gui/postfix-full-hevc-export/completed.json`
- `evidence/T337-gui/postfix-full-hevc-visual-qc/qc-result.json`
- `evidence/T337-gui/cycle-9-root-cause.md`
- `evidence/T337-gui/cycle-9-failed-render/`

## Regression

Gezielter Abschlusscluster:
15/15 PASS in 5,21 s.
