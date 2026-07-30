# Repair Progress — T305–T339

Updated: 2026-07-30T07:52:00+02:00

| Task | Status | Sachstand | ETA | Ist-Zeit | Owner | Evidenz | Commit |
|---|---|---|---:|---:|---|---|---|
| T305 | PASS | CONFIRMED | 0,5–1 h | 0,04 h | Parent | `evidence/T305-evidence-freeze-2026-07-29.md` | – |
| T306 | PASS | CONFIRMED | 1–2 h | 0,03 h | Parent | `evidence/T306-requirement-dedup-2026-07-29.md` | – |
| T307 | PASS | CONFIRMED | 1–2 h | 0,08 h | Parent | `evidence/T307-decision-architecture-security-review-2026-07-29.md` | – |
| T308 | PASS | CONFIRMED | 1–3 h | 0,32 h | Parent | `evidence/T308-production-reproducer/evidence.md` | – |
| T309 | PASS | CONFIRMED | 2–6 h | 0,27 h | Parent | `evidence/T309-stage-isolation/evidence.md` | – |
| T310 | PASS | DECIDED | 0,5–1,5 h | 0,18 h | Independent reviewer | `evidence/T310-independent-design-gate.md` | – |
| T311 | PASS | CONFIRMED | 4–6 h | 0,10 h | Z-RENDER | `evidence/T311-frame-addressability-fix.md` | – |
| T312 | PASS | CONFIRMED | 1–3 h | 0,17 h | Z-RENDER | `evidence/T312-fail-closed-artifact-validator.md` | – |
| T313 | PASS | CONFIRMED | 2–4 h | 0,20 h | Z-RENDER | `evidence/T313-job-isolation.md` | – |
| T314 | PASS | CONFIRMED | 1–2 h | 0,22 h | Z-RENDER | `evidence/T314-machine-progress.md` | – |
| T315 | PASS | CONFIRMED | 1–3 h | 0,22 h | Z-AUDIO/Z-RENDER | `evidence/T315-audio-contract.md` | – |
| T316 | PASS | CONFIRMED | 1–3 h | 0,25 h | Z-AUDIO/Shared sequential | `evidence/T316-chunk-beat-evidence.md` | – |
| T317 | PASS | CONFIRMED | 1–3 h | 0,23 h | Z-AUDIO/Z-PACING/Shared sequential | `evidence/T317-downbeat-provenance.md` | – |
| T318 | PASS | CONFIRMED | 0,5–1,5 h | 0,13 h | Z-PACING | `evidence/T318-timeline-boundaries.md` | – |
| T319 | PASS | CONFIRMED | 0,5–2 h | 0,13 h | Z-PACING | `evidence/T319-snap-provenance.md` | – |
| T320 | PASS | CONFIRMED | 1–3 h | 0,18 h | Z-PACING | `evidence/T320-adaptive-diversity.md` | – |
| T321 | PASS | CONFIRMED | 2–4 h | 0,55 h | Z-BRAIN/Z-PACING | `evidence/T321-canonical-feature-adapter.md` | – |
| T322 | PASS | CONFIRMED | 2–5 h | 0,25 h | Parent/Z-BRAIN/Model Registry | `evidence/T322-semantic-availability.md` | – |
| T323 | PASS | CONFIRMED | 2–5 h | 0,32 h | Parent/Z-BRAIN | `evidence/T323-context-credit-assignment.md` | – |
| T324 | PASS | CONFIRMED | 2–5 h | 0,22 h | Parent/Z-BRAIN | `evidence/T324-brain-weight-migration.md` | – |
| T325 | PASS | DECIDED | 1–3 h | 0,38 h | Parent/Z-INFRA | `evidence/T325-ffmpeg-runtime-decision.md` | – |
| T326 | PASS | CONFIRMED | 2–4 h | 0,47 h | Parent/Z-INFRA + independent read-only audit | `evidence/T326-runtime-reference-sync.md` | – |
| T327 | PASS | CONFIRMED | 1–3 h | 0,42 h | Parent/Shared contracts, sequential | `evidence/T327-public-contract-ui-status.md` | – |
| T328 | PASS | CONFIRMED | 3–6 h | 0,55 h | Parent + 3 disjoint Z-TESTS shards | `evidence/T328-test-implementation.md` | – |
| T329 | PASS | CONFIRMED | 1–3 h | 1,13 h | Parent + Codex Security + 2 independent reviewers | `evidence/T329-cross-zone-security-review.md` | – |
| T330 | PASS | CONFIRMED | 1–2 h | 1,88 h | Parent + Z-DOCS/Z-INFRA reviews | `evidence/T330-reference-completeness-scan.md` | – |
| T331 | PASS | CONFIRMED | 0,25–0,5 h | 0,03 h | Parent | `evidence/T331-implementation-gate.md` | – |
| T332 | PASS | CONFIRMED | 1–3 h | 0,27 h | Parent + static/security reviewer | `evidence/T332-static-targeted-regressions.md` | – |
| T333 | PASS | CONFIRMED | 1–4 h | 0,63 h | Parent + independent root-cause reviewers | `evidence/T333-full-suite-release-build.md` | – |
| T334 | PASS | CONFIRMED | 2–5 h | 0,12 h | Parent | `evidence/T334-security-data-fault-qc.md` | – |
| T335 | PASS | CONFIRMED | 3–7 h | 0,45 h | Parent | `evidence/T335-h264-full-length-qc.md` | – |
| T336 | PASS | CONFIRMED | 3–8 h | 0,37 h | Parent | `evidence/T336-hevc-control-qc.md` | – |
| T337 | PASS | CONFIRMED | 1–4 h | 7,6 h aktiv (9,2 h Wandzeit inkl. Pause/Neustart) | Parent | `evidence/T337-gui-models-qc.md` | – |
| T338 | PASS | CONFIRMED | 1–3 h | 0,7 h | Parent | `evidence/T338-final-truth-gate.md` | – |
| T339 | PASS | CONFIRMED | 1–3 h | 1,1 h aktiv | Parent | `evidence/T339-commit-push-verification.md` | `c3267ef` |

## Fortsetzung T340–T369

| Task | Status | Start | ETA | Ist-Zeit | Owner | Zone | Root Cause / Datenfluss | Änderungen | Evidenz | Commit / Remote-SHA |
|---|---|---|---:|---:|---|---|---|---|---|---|
| T340 | CONFIRMED | 2026-07-30T04:12+02:00 | 0,5–1 h | 0,25 h | Parent | Z-DOCS/Z-INFRA | Ausgangslog, Git, Runtime, Config und Marker direkt inventarisiert | Logkopie; `.completed`/`.qc-passed` invalidiert | `evidence/T340-evidence-freeze-2026-07-30/evidence.md` | – |
| T341 | CONFIRMED | 2026-07-30T04:26+02:00 | 0,5–1 h | 0,2 h | Parent | Z-DOCS | OBJ-71 und freigegebener Plan gegen Spec-/Task-IDs abgeglichen | `spec.md`, `tasks.md`, `repair-progress.md` | `evidence/T341-governance-registration.md` | – |
| T342 | CONFIRMED | 2026-07-30T04:31+02:00 | 1,5–3 h | 0,6 h | Parent + 3 unabhängige Read-only-Prüfungen | Z-CORE/Z-AI/Z-UI-SERVICES | Getrennte Ursachen für GPU-Index, LHM-Trust, Provider-Inventar und DTO-Drift reproduziert und falsifiziert | Root-Cause-Gate dokumentiert; keine Implementierung | `evidence/T342-independent-root-cause-gate.md` | – |
| T343 | DECIDED | 2026-07-30T04:30+02:00 | 1–2 h | 0,3 h | Parent | Z-DOCS | Adapter-, Provider-, Auswahl-, DTO-, Fehler- und Restore-Verträge aus bestätigten Ursachen eingefroren | Vertrags-Freeze dokumentiert; keine Implementierung | `evidence/T343-contract-freeze.md` | – |
| T344 | CONFIRMED | 2026-07-30T04:35+02:00 | 2–4 h | 0,5 h | Parent | Z-CORE/Config sequenziell | DXGI-Normalindex, LUID, AMD-/Softwarefilter und Config-Präzedenz zentralisiert | `directml_adapter.py`, Config-Default und `config.json` | `evidence/T344-adapter-resolver.md` | – |
| T345 | CONFIRMED | 2026-07-30T04:47+02:00 | 3–6 h | 0,7 h | Parent + disjunkte Fachzonen | Z-CORE/Z-VIDEO/Z-AUDIO/Z-AI | Sechs DirectML-Konsumenten auf einen Prozessvertrag gebunden | ModelLoader, RAFT, Moondream, SigLIP, CLAP und Separator aktualisiert | `evidence/T345-directml-consumers.md` | – |
| T346 | CONFIRMED | 2026-07-30T05:00+02:00 | 2–4 h | 0,7 h | Parent | Z-CORE | Budget, Arbiter und Monitor an zentralen LUID gebunden; physische Obergrenze erzwungen | `vram_budget_manager.py`, `vram_arbiter.py`, `system_monitor.py` | `evidence/T346-vram-coherence.md` | – |
| T347 | CONFIRMED | 2026-07-30T05:12+02:00 | 2–4 h | 0,9 h | Parent | Z-CORE/Z-INFRA/Z-UI-SERVICES sequenziell | Offizielles 0.9.6-Asset publisher-gehasht; Trust-Anchor, Launcher und Restore-Probe geschlossen | LHM-Bundle, Manifest, `config/lhm-runtime.json`, `PythonBridgeService.cs` | `evidence/T347-lhm-trust-chain.md`; `evidence/T347-lhm-backup-sha256.json` | – |
| T348 | CONFIRMED | 2026-07-30T05:28+02:00 | 2–4 h | 0,6 h | Parent | Shared API/Z-UI sequenziell | Additiver Status trennt DirectML-Identität von ready/degraded Monitoring und unterdrückt Fremdwerte | `backend/main.py`, GPU-DTO, Settings-VM und XAML | `evidence/T348-gpu-status-truth.md` | – |
| T349 | CONFIRMED | 2026-07-30T05:38+02:00 | 1–2 h | 0,4 h | Parent | lokale Config/Z-DOCS | JIT nach bytegenauem Backup aktiviert; Server neu gestartet; 14 verfügbare bei 1 geladenem Modell; Restore-Kopie hashgleich | LM-Studio-HTTP-Server-Config | `evidence/T349-lmstudio-jit.md` | – |
| T350 | CONFIRMED | 2026-07-30T05:51+02:00 | 3–5 h | 0,6 h | Parent | Z-AI/Model Registry sequenziell | Providergetrenntes Inventar aus unterstützten Livequellen; installierte, geladene, nutzbare und verifiziert herunterladbare Zustände atomar modelliert | `src/pb_studio/ai/model_inventory.py` | `evidence/T350-model-inventory.md` | – |
| T351 | CONFIRMED | 2026-07-30T06:06+02:00 | 1–3 h | 0,5 h | Parent | Shared startup/Z-AI sequenziell | Ein Startup-Refresh; TTL, Invalidierung, Lock und atomare Generation koaleszieren parallele Modellansicht-Abfragen | `backend/main.py`, `model_inventory.py`, `models_router.py` | `evidence/T351-startup-refresh.md` | – |
| T352 | CONFIRMED | 2026-07-30T06:18+02:00 | 3–5 h | 1,0 h | Parent | Z-AI/Model Registry sequenziell | Receipt enthält Provider/Modell/Task/Mode/Capabilities/Quelle/Grund/Zeit; Request bindet exakt; ein Refresh und höchstens drei Kandidaten | Registry, Chat, Vision, Brain und Recommendation API | `evidence/T352-selection-receipt.md` | – |
| T353 | CONFIRMED | 2026-07-30T06:53+02:00 | 1–3 h | 0,5 h | Parent | Config/Model Registry sequenziell | Modell-ID bleibt in `task_overrides`; Provider additiv je Task; Live-/Capability-Prüfung, Ambiguitätsfehler und Read-back-Verifikation | Config, Registry und Activate API | `evidence/T353-model-selection-persistence.md` | – |
| T354 | CONFIRMED | 2026-07-30T07:08+02:00 | 2–4 h | 0,8 h | Parent | Z-UI-VM/Z-UI-VIEWS | Providergetrennte Livekarten mit loaded/on-demand/usable/capabilities/reason; statische Downloadkarten entfernt; Discover-Zustand separat | Models API/DTO, ModelManager VM/XAML, ApiClient | `evidence/T354-model-surface.md` | – |
| T355 | CONFIRMED | 2026-07-30T07:34+02:00 | 0,5–1,5 h | 0,3 h | Parent | Z-UI-SERVICES | Handgeschriebenes DTO nullable; Batch zählt nur gültige Responses, weist Fehler/Skipped getrennt aus und setzt Fehlclips nicht auf analysiert | ApiClient DTO, VideoLibraryViewModel | `evidence/T355-sceneinfo-nullability.md` | – |
| T356 | CONFIRMED | 2026-07-30T07:44+02:00 | 1–2 h | 0,5 h | Parent | Shared contracts sequenziell | Config, API-Schemas, OpenAPI-Snapshot, NSwag-Client und handgeschriebene DTOs synchron; SceneInfo überall nullable | Config/OpenAPI/Generated/Handwritten DTOs | `evidence/T356-contract-sync.md` | – |
| T357 | CONFIRMED | 2026-07-30T07:58+02:00 | 3–5 h | 0,9 h | Z-TESTS | Z-TESTS | 33 Testfunktionen für Inventar/Receipts, Owner/Persistenz, DirectML/LHM, WPF-Verträge und Nullability implementiert; Hardwareprobe bis T363 gesperrt; keine Tests ausgeführt | 3 neue T357-Testdateien | `evidence/T357-test-implementation.md` | – |
| T358 | CONFIRMED | 2026-07-30 | 1–2 h | 1,3 h | Parent + lokaler Security Review | alle geänderten Zonen | 3 HIGH + 2 MEDIUM geschlossen: Owner-Schutz, Receipt-Providerbindung, kanonische IDs, kein CLI-Exec, atomare Config und bereinigte Fehler | Backend/AI/Core/WPF/Tests | `evidence/T358-security-review.md` | – |
| T359 | CONFIRMED | 2026-07-30 | 1–2 h | 1,2 h | Parent + 3 Read-only-Audits | gesamter Workspace, sequenzieller Fix | ORT-Run-/CPU-EP-Fallback, Ollama-Quellenwechsel, mehrdeutige Aktivkarten sowie DTO-/UI-Drift gefunden und geschlossen | zentraler DirectML-Sessionvertrag; Provider-/Receipt-Fixes; OpenAPI/NSwag/WPF synchronisiert | `evidence/T359-completeness-scan.md` | – |
| T360 | CONFIRMED | 2026-07-30T06:28+02:00 | 0,5–1 h | 0,35 h | Parent | Z-DOCS | Nach T363-Enforcer- und T365-Launcher-Fix jeweils frisch validiert; zuletzt 348 Python, 63 JSON, 22 XML/XAML und 132 geänderte Dateien PASS | OpenAPI/NSwag, LHM-Gesamthashkette, DirectML-Vertrag, PowerShell-Syntax und Diff PASS; `.qc-passed` bleibt absent | `evidence/T360-implementation-gate.md`; `evidence/T360-revalidation-20260730.log`; `evidence/T360-post-T365-revalidation.json` | – |
| T361 | CONFIRMED | 2026-07-30T06:38+02:00 | 1–3 h | 0,12 h | Parent | QC/Z-TESTS | Enforcer-/CLAP-Vertrag nach T363 mit ModelLoader- und CLAP-Tests erweitert | 85 passed/3 skips/0 failed; Skips auf T363-Hardware und fehlende CLAP-Assets begrenzt | `evidence/T361-targeted-regressions.md`; `evidence/T361-targeted-regressions.xml` | – |
| T362 | CONFIRMED | 2026-07-30T06:42+02:00 | 1–4 h | 0,90 h | Parent + 3 Read-only-Audits | QC/Z-TESTS | T363-Enforcer-Fix frisch über Vollsuite; ein veralteter Fehlermeldungs-Assert isoliert und korrigiert | Vollsuite 1.086 passed/12 skipped/0 failed; WPF Release 0 Warnungen/0 Fehler | `evidence/T362-full-suite-release-build.md`; `evidence/T362-full-suite.xml`; `evidence/T362-wpf-release.binlog`; `evidence/T362-c01-cluster.xml` | – |
| T363 | BLOCKED | 2026-07-30T07:16+02:00 | 2–4 h | 0,25 h | Parent | Hardware-QC | Audio PASS auf RX 7800 XT; RAFT/SigLIP-Exporte benötigen verbotene CPU-Knoten; Moondream/CLAP-ONNX-Assets fehlen lokal | zentralen Enforcer für implizite ORT-CPU-Registrierung korrigiert; alle fünf Pfade isoliert; sichere Alternativen ausgeschöpft | `evidence/T363-rx7800xt-hardware-proof.md`; `evidence/T363-hardware-identity.xml`; `evidence/T363-enforcer-regressions.xml` | BLOCKED: kompatible/fehlende ONNX-Assets bzw. Dependency-Freigabe erforderlich |
| T364 | CONFIRMED | 2026-07-30T07:52+02:00 | 2–4 h | 0,20 h | Parent | Provider-E2E | 29 Live-Karten, Startrefresh und Capability-Routing; Modellwechsel über API blieb nach Backend-Neustart providergebunden | Offline/Online-Empty korrekt; echter LM-Studio→Ollama-Chat-Failover mit 2 Receipts, 1 Invalidation und exaktem HTTP-Modell; alle Prozess-/Config-Zustände restauriert | `evidence/T364-model-e2e.md`; `evidence/T364-provider-baseline.json`; `evidence/T364-failover-e2e.json` | – |
| T365 | CONFIRMED | 2026-07-30T08:08+02:00 | 1–3 h | 0,30 h | Parent | GUI-/Analyse-E2E/Z-INFRA | Produktionslauf entdeckte fehlende LHM-Trust-Weitergabe im extern gestarteten Backend; Runtime-Vertrag geschlossen und live mit RX 7800 XT/Monitoring ready bestätigt | Vier visuell geprüfte UIA-Screenshots; 29 Live-Modelle; echte ApiClient-Deserialisierung von `confidence=null` mit exakt einem Request; 19 passed/1 Hardware-Skip; WPF 0/0; sauberer Prozess-Cleanup | `evidence/T365-gui-analysis-e2e.md`; `evidence/T365-gui-runtime.json`; `evidence/T365-nullable-runtime.json`; `evidence/T365-contract-regressions.xml` | – |
| T366 | CONFIRMED | 2026-07-30T08:30+02:00 | 3–8 h | 0,22 h | Parent | Full-Length Render-QC | Frischer H.264-AMF-Lauf über eingefrorene 4.816-Einträge-Timeline; Cycle 1 stoppte vor FFmpeg wegen Child-Importpfad, Cycle 2 nutzte echten Router-Finalizer | 3.688.013.674 Bytes; 190.051 Frames; Video/Audio komplett; 106/106 Segmente; 0 Black/Freeze; atomar publiziert | `evidence/T366-h264-full-length-qc.md`; `evidence/T366-h264/full-export-cycle-2/completed.json`; `evidence/T366-h264/full-visual-qc/qc-result.json` | – |
| T367 | CONFIRMED | 2026-07-30T08:44+02:00 | 3–8 h | 0,38 h | Parent | Full-Length Render-QC | Frischer HEVC-AMF-Lauf mit identischer eingefrorener 4.816-Einträge-Timeline, Audioquelle, Router-Finalisierung und eigenem Ziel | 3.687.203.928 Bytes; 190.051 Frames; Video/Audio komplett; 106/106 Segmente; 0 Black/Freeze; atomar publiziert; keine Restprozesse | `evidence/T367-hevc-full-length-qc.md`; `evidence/T367-hevc/full-export/completed.json`; `evidence/T367-hevc/full-visual-qc/qc-result.json` | – |
| T368 | CONFIRMED | 2026-07-30T09:13+02:00 | 2–4 h | 0,25 h | Parent | Z-DOCS/Brain | Gesamt-QC bleibt wegen T363 BLOCKED; T368 schließt die Wahrheitsdrift und erfüllt die Marker-Invariante ohne falsche Freigabe | QC, CHANGELOG, ADR-0003, CLAUDE, Tasks, Ledger und PB-Brain abgeglichen; alte CPU-SigLIP-Entscheidung superseded; `.qc-passed` absent | `evidence/T368-final-truth-gate.md` | – |
| T369 | OPEN | – | 1–3 h | – | Parent | Git/Remote | OPEN | – | geplant: `evidence/T369-publication.md` | – |

## Classification

- CONFIRMED: backed by stored evidence.
- OPEN: evidence or execution pending.
- DECIDED: governed by approved D01–D08.
- BLOCKED: only after a plan-defined blocker is recorded.
