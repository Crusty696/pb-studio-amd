# Tasks: OBJ-76 Live-Runtime-Wahrheit und Observability

**Status:** OPEN
**Spec:** `specs/00021-live-runtime-truth-and-observability/spec.md`
**Plan:** `specs/00021-live-runtime-truth-and-observability/plan.md`

## Gate 0 — aktueller Build

- [X] T001 [OBJ-76] {(OR-355)} Erfasse HEAD, Porcelain-Status, `config.json`-Fingerprint und vorhandene T052/T053-Evidence unter `specs/00021-live-runtime-truth-and-observability/evidence/`
- [X] T002 [OBJ-76] {(TR-378)} Baue `PBStudio.UI/PBStudio.UI.csproj` unverändert als WPF-Release und starte Backend/WPF über den kanonischen Runtime- und Owner-Capability-Vertrag
- [ ] T003 [OBJ-76] {(FR-392)} {(FR-394)} {(FR-395)} Führe getrennte Live-Proben für Tagging, Provider-Degradation, Shutdown und Restart/Resume aus und speichere PASS, NO-CHANGE oder reproduzierten Restfehler unter `specs/00021-live-runtime-truth-and-observability/evidence/`

## Gate 1 — Launcher und Telemetrie

- [X] T004 [P] [OBJ-76] {(FR-397)} Verdrahte `.agents/skills/run-pb-studio/driver.ps1` mit `Get-PBStudioRuntimeContract -ApplyEnvironment` und dem bestehenden Owner-Capability-Skript, ohne Capability-Wert zu loggen; der kanonische Launcher muss einen validen Recovery-Start innerhalb einer begrenzten 90-Sekunden-Deadline akzeptieren [Z-INFRA]
- [X] T005 [P] [OBJ-76] {(TR-380)} Ergänze in `Tests/test_runtime_contract.py` fokussierte Launcher-Verträge für Python 3.11, NumPy 1.26.4, FFmpeg-AMF, DirectML-Provider, LHM-Hashes und Adapteridentität [Z-TESTS]

## Gate 2 — Diagnosemitschnitt

- [X] T006 [P] [OBJ-76] {(FR-400)} Registriere den Capture-Monitor unter `scripts/diagnostics/` mit echten Startoffsets, PIDs, Exitcodes, monotoner Sequenz, Drop-Zähler und terminalem Stop-Receipt [Z-INFRA]
- [X] T007 [P] [OBJ-76] {(FR-401)} Ergänze unter `scripts/diagnostics/` einen fail-closed sanitisierten Export für Credentials, Owner-Capability, Health-Proof-Nonces und private absolute Pfade; das Raw-Log bleibt lokal [Z-INFRA]
- [X] T008 [OBJ-76] {(TR-382)} Prüfe in `Tests/test_capture_monitor_contract.py` Start, Rotation, reguläres Ende und abruptes Ende mit genau einer Sitzung und null privaten Treffern im Export [Z-TESTS]

## Gate 3 — LM Studio und Analysewahrheit

- [X] T009 [OBJ-76] {(FR-396)} Erfasse mit `scripts/diagnostics/verify_lmstudio_vlm.py`, `lms ps` und `lms log stream --source server --json` einen kalten sowie zwei warme Engine-/SSE-Receipts des aktuell konfigurierten Captioning-Modells; prüfe qwen2.5-VL anschließend als dokumentierte Kontrolle, unterscheide Transporterfolg von nutzbarem finalen Tag-Inhalt und stelle zuvor geladene fremde Modell-Identitäten danach exakt wieder her
- [X] T010 [OBJ-76] {(FR-392)} {(FR-393)} Bestätige per NO-CHANGE-Prüfung in `backend/routers/video_router.py` und `src/pb_studio/ai/model_registry.py` terminale angeforderte Stage-Zustände, Receipt-gebundene maximal drei Versuche, einen Refresh und die ablaufende bounded Quarantäne; keine reservierte Produktdatei ändern [Z-VIDEO/Z-AI]
- [X] T011 [OBJ-76] {(FR-393)} {(FR-394)} Bestätige per NO-CHANGE-Prüfung in `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs`, dass der UI-Batch-Retry nur angeforderte Stages sendet und ausschließlich nicht-null abgeschlossene Analysen als Erfolg zählt; keine reservierte Produktdatei ändern [Z-UI-VM/Z-UI-SERVICES]
- [X] T012 [OBJ-76] {(TR-379)} Verifiziere die geänderten Deadline-, Cancellation- und stage-aware Retry-Verträge fokussiert in `Tests/test_video_pipeline_truth.py` und `Tests/test_video_analysis_resume.py`; nicht geänderte Modellwahlverträge werden nicht breit wiederholt [Z-TESTS]

## Gate 4 — Shutdown und Resume

- [X] T013 [OBJ-76] {(FR-395)} Reproduziere einen realen Shutdown während Captioning und decke die gemeinsame Cancellation-/Interrupted-Logik für andere aktive Stages mit fokussierter Injection ab; speichere den Live-Receipt unter `specs/00021-live-runtime-truth-and-observability/evidence/`
- [X] T014 [OBJ-76] {(FR-395)} Implementiere bei rotem Repro in `backend/main.py` und `backend/app_state.py` Intake-Stop, bounded Drain, atomaren `interrupted`-Commit und normalisierte Cancellation ohne ASGI-Fehler [Z-CORE/Z-VIDEO/BACKEND]
- [X] T015 [OBJ-76] {(TR-378)} Verifiziere den realen Captioning-Shutdown sowie fokussierte Cancellation- und stage-aware Resume-Verträge in `Tests/test_video_analysis_resume.py` ohne Traceback, Datenverlust oder späten Completed-Overwrite [Z-TESTS]

## Gate 5 — Assets und Szenen

- [X] T016 [P] [OBJ-76] {(FR-398)} Prüfe `config/directml-model-assets.json` auf ein SigLIP-Text-ONNX-Artefakt; aktiviere ausschließlich validiertes DirectML oder dedupliziere den Unavailable-Status [Z-AI/Z-CORE]
- [X] T017 [P] [OBJ-76] {(FR-399)} {(TR-381)} Erfasse in `specs/00021-live-runtime-truth-and-observability/evidence/scene-ground-truth.md` drei deterministische kontinuierliche und drei deterministische Multi-Cut-Fixtures und ändere Thresholds nur bei reproduzierten False-Negatives [Z-TESTS/Z-VIDEO]

## Gate 6 — kontrollierte Bestandsreparatur

- [X] T018 [OBJ-76] {(OR-357)} Validiere die aktuelle Recovery-Generation read-only und beweise Restore isoliert gegen eine temporäre Kopie; dokumentiere Dry-Run-Inventar und geplante Stage-Wiederholungen ohne Live-Mutation in `specs/00021-live-runtime-truth-and-observability/evidence/reanalysis-dry-run.md`
- [ ] T019 [OBJ-76] {(OR-358)} {(TR-383)} Führe erst nach separatem Go zehn repräsentative Clips als Canary aus und vergleiche Stage-Hashes sowie Receipts in `specs/00021-live-runtime-truth-and-observability/evidence/reanalysis-canary.md`
- [X] T020 [OBJ-76] {(OR-358)} Dokumentiere das gesperrte Bulk-Go/No-Go in `specs/00021-live-runtime-truth-and-observability/evidence/bulk-decision.md`; ohne Canary 10/10 bleibt eine Massen-Nachanalyse verboten
