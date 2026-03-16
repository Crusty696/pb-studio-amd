# PB Studio AMD – QA/Doku Integrationsnotizen (Agent 5)

Datum: 2026-03-13
Zweck: Konsolidierungsvorbereitung für Abschlussreport, Status-Matrix und Release-Einordnung.

## 1. Was bereits wirklich live belegt ist

Die folgenden Claims sind nicht nur code-inspected, sondern durch echte Läufe / UI / Publish / HTTP / SSE belegt:

### Core Runtime / Backend
- `/health` PASS
- `/gpu/status` PASS
- Projekt-CRUD (`create/open/save/close/info`) PASS innerhalb erlaubtem Root `C:\Users\david\Documents\PBStudio`
- Audio-Import PASS
- Video-Import Backend/API PASS
- Audio-Analyse PASS
- Beats PASS
- Waveform PASS
- Structure PASS
- Spectral PASS
- Video-Analyse PASS
- `/video/scenes/{id}` funktional PASS, aber in getesteten Clips teils leer
- `/video/motion/{id}` PASS
- `/video/thumbnails/{id}` PASS mit validen JPEG-Bytes
- `/pacing/generate` PASS
- `/pacing/timeline` PASS
- `/pacing/preview` PASS
- `/render/start` PASS
- `/render/status/{task_id}` Statuswechsel PASS
- `/render/cancel/{task_id}` PASS
- `/events/gpu` PASS
- `/events/progress` PASS
- `/events/log` PASS nach Fix

### WPF / echter Click-Path
- App-Start PASS
- Header `Backend: Online` / GPU-Status PASS
- Tab-Surfaces AUDIO / VIDEO / ANCHORS / TIMELINE / PRODUKTION PASS
- Projekt öffnen/speichern/schließen/wieder öffnen/erstellen PASS
- Audio-Library zeigt echte Assets PASS
- Video-Library zeigt echte Assets PASS
- Timeline zeigt echte Assets PASS
- Production-Tab Render-Workflow PASS
- Render-Log-Liste im echten UI PASS
- Settings-Tab Initialdaten + Cleanup PASS nach Fix
- VIDEO `Alle analysieren` PASS
- Anchor Add PASS
- Anchor Remove PASS nach Selektionsfix
- Director Generate im Release-Build PASS nach JsonElement-Fix
- Video-Import via neuem In-App-Pfadfeld PASS

### Packaging / Release
- `publish.ps1` framework-dependent Publish PASS
- `launch.ps1` latest-pointer-basierter Launchpfad dokumentiert/gehärtet
- `verify_release_smoke.ps1` PASS
- Publish-Artefakt `artifacts\publish\framework\Release\win-x64\hardening-20260313\PBStudio.UI.exe` praktisch belegt
- `artifacts\publish\framework\latest.txt` als aktueller Pointer belegt

### Heavy Runtime
- Heavy-Lauf mit echter 60s-Audioquelle + 6 Video-Clips PASS
- Render cancel PASS
- Render complete PASS
- gültige 60s-Outputdatei PASS
- SSE `progress`/`log`/`gpu` unter Last PASS

## 2. Was weiterhin nur partial / eingeschränkt belegt ist

Diese Punkte dürfen in Abschlussstatus nicht als voll gelöst verkauft werden:

- **Aktive Render-ETA-/Frame-/FPS-/Elapsed-Telemetrie**: FAIL/PARTIAL
  - `/render/status/{task_id}` liefert während aktiver Läufe praktisch nur Prozent + Message; Telemetriedetails bleiben 0.
- **Nativer Windows-Video-Dateidialog**: PARTIAL
  - Dialog öffnet grundsätzlich, aber Automation war flaky / nicht deterministisch.
  - Produktpfad ist durch In-App-Video-Path-Import entschärft, der native Dialog selbst ist aber nicht sauber „grün“.
- **Scene quality / Vision richness**: PARTIAL
  - Endpoints laufen, aber auf getesteten Clips oft leere oder wenig aussagekräftige semantische Resultate.
- **GPU-/VRAM-Stress unter Renderlast**: PARTIAL
  - GPU-SSE funktioniert, aber der Heavy-Lauf zeigte kaum Lastsignal / keine klare Belastungsspitze.
- **True player / echte Edit-Timeline**: weiterhin funktionale Produktlücke
  - aktueller Scope ist Inspector/List/Scrubber, kein echter Playback-/Editing-Workflow.

## 3. Dokument-Drift / was im Abschluss unbedingt konsistent sein muss

### A. `STATUS_MATRIX.md`
Bereits weitgehend aktuell, aber diese Aussagen müssen besonders konsistent bleiben:
- Release readiness = **partial**, nicht present
- Grund: kein echter Player / keine echte Edit-Timeline und aktive ETA-Telemetrie weiter schwach
- Native Video-Dialog-Härtung nur als optional/non-blocking formulieren, weil In-App-Path-Import existiert
- Render progress nicht zu positiv formulieren: Status/Percent ja, echte Runtime-Telemetrie nein

### B. `VERIFICATION_REPORT_2026-03-12.md`
Dieses File ist inzwischen historisch gewachsen und enthält die meiste Detailtiefe. Für finalen Konsum muss klar sein:
- es ist faktisch das **detaillierte Beweisprotokoll**
- ältere `NOT_STARTED/BLOCKED`-Abschnitte am Anfang sind historisch und dürfen nicht isoliert zitiert werden
- falls das File als Abschlussbeleg weiterverwendet wird, braucht es idealerweise einen kurzen Top-Hinweis wie:
  - „frühe Abschnitte dokumentieren den damaligen Zwischenstand; maßgeblich ist der ergänzte Live-Verifikationsblock ab 6.x“

### C. `HARDENING_FINAL_REPORT_2026-03-13.md`
Gute Executive Summary. Muss inhaltlich synchron bleiben mit:
- `STATUS_MATRIX.md`
- Heavy-Runtime-Report
- Release-Empfehlung framework-dependent
- Scope-Entscheid MVP vs echter Editor

### D. `VERIFICATION_HEAVY_RUNTIME_2026-03-13_AGENT_D.md`
Muss als Primärbeleg für die verbleibende ETA-/Telemetry-Lücke behandelt werden.
Wichtig:
- nicht verwässern
- die dortige FAIL-Aussage zu aktiver ETA-/Frame-/FPS-Telemetrie ist belastbar und sollte im finalen Gesamtfazit sichtbar bleiben

## 4. Dateien, die am Ende zwingend aktualisiert / gegeneinander geprüft werden müssen

### Zwingend
1. `C:\Users\david\Dokumente\Pb_studio_AMD_version\STATUS_MATRIX.md`
2. `C:\Users\david\Dokumente\Pb_studio_AMD_version\VERIFICATION_REPORT_2026-03-12.md`
3. `C:\Users\david\Dokumente\Pb_studio_AMD_version\HARDENING_FINAL_REPORT_2026-03-13.md`
4. finales Master-/Abschlussdokument des Hauptagenten (falls neuer Finalreport entsteht)

### Sekundär, aber referenzwichtig
5. `C:\Users\david\Dokumente\Pb_studio_AMD_version\VERIFICATION_HEAVY_RUNTIME_2026-03-13_AGENT_D.md`
6. `C:\Users\david\Dokumente\Pb_studio_AMD_version\verify_release_smoke.ps1`
7. `C:\Users\david\Dokumente\Pb_studio_AMD_version\publish.ps1`
8. `C:\Users\david\Dokumente\Pb_studio_AMD_version\launch.ps1`

## 5. Empfohlene Abschlussformulierungen

### Sicher formulierbar
- PB Studio ist **release-nah für einen framework-dependent Windows-Beta-Release im aktuellen Batch-/Pacing-/Render-MVP-Scope**.
- Die Kernpfade create/import/analyze/director/render/settings sind praktisch belegt.
- Der frühere `/events/log`-Blindspot ist behoben und live verifiziert.
- Der frühere Release-Crash im Director-Pfad ist behoben und im Publish-Build re-verifiziert.
- Für den flakigen nativen Video-Dialog existiert ein praktisch verifizierter In-App-Workaround.

### Nicht überziehen
- Nicht behaupten, dass Render-ETA zuverlässig funktioniert.
- Nicht behaupten, dass es bereits einen echten Player oder eine echte Edit-Timeline gibt.
- Nicht behaupten, dass GPU-Stressverhalten unter hoher Last ausreichend charakterisiert ist.
- Nicht behaupten, dass der native Windows-Video-Dateidialog robust verifiziert ist.

## 6. Fazit für den Hauptagenten

Die Doku-Lage ist insgesamt brauchbar, aber der Abschluss muss auf **Claim-Hygiene** achten: 
- Kernworkflow = grün und live belegt
- Release-Scope = MVP, nicht „voller Editor“
- verbleibende harte Lücke = aktive Render-Telemetrie
- verbleibende weiche Lücken = echter Player/Edit-Timeline, nativer Video-Dialog, reichere Qualitätsverifikation bei Vision/Scenes/GPU-Stress
