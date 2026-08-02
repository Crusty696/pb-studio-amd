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
| T360 | CONFIRMED | 2026-07-30T06:28+02:00 | 0,5–1 h | 0,55 h | Parent | Z-DOCS | Nach T363-Modell- und CLAP-Lock-Fix frisch validiert; zuletzt 348 Python, 74 JSON, 22 XML/XAML und 16 geänderte Dateien PASS | OpenAPI/NSwag, LHM-Gesamthashkette, DirectML-Vertrag und Diff PASS; `.completed` aktuell | `evidence/T360-implementation-gate.md`; `evidence/T360-post-T365-revalidation.json` | – |
| T361 | CONFIRMED | 2026-07-30T06:38+02:00 | 1–3 h | 0,12 h | Parent | QC/Z-TESTS | Enforcer-/CLAP-Vertrag nach T363 mit ModelLoader- und CLAP-Tests erweitert | 85 passed/3 skips/0 failed; Skips auf T363-Hardware und fehlende CLAP-Assets begrenzt | `evidence/T361-targeted-regressions.md`; `evidence/T361-targeted-regressions.xml` | – |
| T362 | CONFIRMED | 2026-07-30T06:42+02:00 | 1–4 h | 1,30 h | Parent + 3 Read-only-Audits | QC/Z-TESTS | Nach T363-Modellintegration und CLAP-Deadlock-Fix vollständig neu ausgeführt | Vollsuite 1.090 passed/11 skipped/0 failed; WPF Release 0 Warnungen/0 Fehler | `evidence/T363-final-full-suite.xml`; `evidence/T363-final-wpf-release.binlog` | – |
| T363 | CONFIRMED | 2026-07-30T07:16+02:00 | 2–4 h | 3,8 h | Parent | Hardware-QC/Z-AI/Z-VIDEO | Statische RAFT-/SigLIP-Formen, gepinnte CLAP-Assets und Moondream-Vision schließen den strict-DML-Assetblocker; real aktiv auf LUID `0x00000000_0x0001185b` | fünf PID/LUID/Engine/VRAM-Receipts; iGPU 0%; CLAP-Semantik funktional; doppelten GPU-Lock entfernt; Caption-Decoder ehrlich unavailable | `evidence/T363-rx7800xt-hardware-proof.md`; `evidence/T363-active-summary-20260730-105514.json`; `evidence/T363-final-full-suite.xml` | – |
| T364 | CONFIRMED | 2026-07-30T07:52+02:00 | 2–4 h | 0,20 h | Parent | Provider-E2E | 29 Live-Karten, Startrefresh und Capability-Routing; Modellwechsel über API blieb nach Backend-Neustart providergebunden | Offline/Online-Empty korrekt; echter LM-Studio→Ollama-Chat-Failover mit 2 Receipts, 1 Invalidation und exaktem HTTP-Modell; alle Prozess-/Config-Zustände restauriert | `evidence/T364-model-e2e.md`; `evidence/T364-provider-baseline.json`; `evidence/T364-failover-e2e.json` | – |
| T365 | CONFIRMED | 2026-07-30T08:08+02:00 | 1–3 h | 0,30 h | Parent | GUI-/Analyse-E2E/Z-INFRA | Produktionslauf entdeckte fehlende LHM-Trust-Weitergabe im extern gestarteten Backend; Runtime-Vertrag geschlossen und live mit RX 7800 XT/Monitoring ready bestätigt | Vier visuell geprüfte UIA-Screenshots; 29 Live-Modelle; echte ApiClient-Deserialisierung von `confidence=null` mit exakt einem Request; 19 passed/1 Hardware-Skip; WPF 0/0; sauberer Prozess-Cleanup | `evidence/T365-gui-analysis-e2e.md`; `evidence/T365-gui-runtime.json`; `evidence/T365-nullable-runtime.json`; `evidence/T365-contract-regressions.xml` | – |
| T366 | CONFIRMED | 2026-07-30T08:30+02:00 | 3–8 h | 0,22 h | Parent | Full-Length Render-QC | Frischer H.264-AMF-Lauf über eingefrorene 4.816-Einträge-Timeline; Cycle 1 stoppte vor FFmpeg wegen Child-Importpfad, Cycle 2 nutzte echten Router-Finalizer | 3.688.013.674 Bytes; 190.051 Frames; Video/Audio komplett; 106/106 Segmente; 0 Black/Freeze; atomar publiziert | `evidence/T366-h264-full-length-qc.md`; `evidence/T366-h264/full-export-cycle-2/completed.json`; `evidence/T366-h264/full-visual-qc/qc-result.json` | – |
| T367 | CONFIRMED | 2026-07-30T08:44+02:00 | 3–8 h | 0,38 h | Parent | Full-Length Render-QC | Frischer HEVC-AMF-Lauf mit identischer eingefrorener 4.816-Einträge-Timeline, Audioquelle, Router-Finalisierung und eigenem Ziel | 3.687.203.928 Bytes; 190.051 Frames; Video/Audio komplett; 106/106 Segmente; 0 Black/Freeze; atomar publiziert; keine Restprozesse | `evidence/T367-hevc-full-length-qc.md`; `evidence/T367-hevc/full-export/completed.json`; `evidence/T367-hevc/full-visual-qc/qc-result.json` | – |
| T368 | CONFIRMED | 2026-07-30T09:13+02:00 | 2–4 h | 0,7 h | Parent | Z-DOCS/Brain | T363-Blocker durch gehashte strict-DML-Assets geschlossen; alle End-QC-Gates PASS | QC, CHANGELOG, ADR-0003, CLAUDE, Tasks, Ledger und PB-Brain abgeglichen; `.completed` und `.qc-passed` gültig | `evidence/T368-final-truth-gate.md` | – |
| T369 | CONFIRMED | 2026-07-30T09:14+02:00 | 1–3 h | 0,45 h | Parent | Git/Remote | D07 auch beim T363-Follow-up: PB 0 remote-only/2 local-only, Brain 0/1; Fast-Forward zulässig | ursprüngliche 7 PB-Zonencommits plus DirectML- und QC-Follow-up; neuer 31-Datei-Secret-Scan 0 Treffer; PB und ausschließlich `10_Projects/PB_studio/**` gepusht; Remote-SHAs verifiziert | `evidence/T369-publication.md` | PB payload `669d9d320774261d6881437760431f7d86ab2b85`; Brain payload `aa2585979ed625f1ae51decff08b20c40155ff11` |

## Classification

- CONFIRMED: backed by stored evidence.
- OPEN: evidence or execution pending.
- DECIDED: governed by approved D01–D08.
- BLOCKED: only after a plan-defined blocker is recorded.

## Team-Infrastruktur für OBJ-72

| Setup | Status | Datum | Owner | Ergebnis | Evidenz |
|---|---|---|---|---|---|
| Claude-Code-Zusatzagent | READ_ONLY_SMOKE_VERIFIED | 2026-07-31 | Teamleiter | CLI 2.1.212 gesund und angemeldet; isolierter Controller- und ticketgebundener Repo-Read-Smoke verifiziert; kein OBJ-72-Task-PASS; CSD/tmux-Pfad begrenzt und durch `claude -p` mit Tool-, Zeit- und Kostenlimits ersetzt | `evidence/claude-controller-setup-2026-07-31.md` |
| SDD-Governance-Bootstrap | PASS | 2026-07-31 | Teamleiter + 3 Read-only-Agenten | OBJ-71 byte-/Git-gebunden archiviert; OBJ-72 Spec/Plan/Tasks aktiv; Fail-Closed-Validator 27/27 PASS; unabhängiger Finalreview PASS; Releasemarker entfernt und QC neu geöffnet | `evidence/T370-T373-governance-gate.md` |

## OBJ-72 Release-Fähigkeit T370–T415

Updated: 2026-08-02
Gesamt: **44/46 PASS (95,7 %)**
Aktuell: **T414/T415 OPEN; Abschlusswahrheit erst nach geschütztem Main-Release-SHA**

| Task | Status | ETA | Owner | Zone | Ist | Evidenz / nächster Schritt |
|---|---|---:|---|---|---:|---|
| T370 Evidenz und Archivmanifest bestätigen | PASS | 0,5–1 h | Teamleiter | Z-DOCS/Z-INFRA | 0,5 h | Git-/Hash-gebundenes Archiv PASS (`evidence/T370-T373-governance-gate.md`) |
| T371 Spec/Requirement-Registry validieren | PASS | 2–4 h | Teamleiter + Docs-Agent | Z-DOCS | 0,8 h | 8.523-Byte-Spec aktiv; deterministische Registry PASS (`evidence/T370-T373-governance-gate.md`) |
| T372 SDD-Gate reparieren | PASS | 3–6 h | SDD-Agent + Reviewer | Z-DOCS/Z-TESTS | 1,4 h | 27/27 Tests, aktiver Validator und Finalreview PASS (`evidence/T370-T373-governance-gate.md`) |
| T373 Release-Gates neu öffnen / Marker invalidieren | PASS | 0,5–1 h | Teamleiter | Z-DOCS | 0,2 h | Marker fehlen; QC `REOPENED / NOT RELEASE-READY` (`evidence/T370-T373-governance-gate.md`) |
| T374 ProjectOperationContext | PASS | 6–10 h | Teamleiter/Core-Agent | SHARED/Z-CORE | 0,8 h | Frozen Kontext, Epoch, Lifecycle-Lock, Registry und atomarer Swap (`evidence/T374-project-operation-context.md`) |
| T375 Audio-Kontext | PASS | 4–8 h | Audio-Agent + Teamleiter-Review | Z-AUDIO | 0,9 h | Frozen Kontext und atomare Import/Analyse/Stem-Commits (`evidence/T375-audio-project-context.md`) |
| T376 Video-Kontext | PASS | 5–10 h | Video-Agent + Teamleiter-Review | Z-VIDEO | 0,9 h | Frozen ID, atomare Import/Analyse/Vector-Commits (`evidence/T376-video-project-context.md`) |
| T377 Pacing-Kontext | PASS | 4–8 h | Pacing-Agent + Teamleiter-Integration | Z-PACING | 1,2 h | Exakte Brain-Lease, Generate/Timeline kontextgebunden (`evidence/T377-pacing-project-context.md`) |
| T378 Timeline-Lifecycle | PASS | 4–8 h | Teamleiter/Timeline-Agent | Z-UI-VM/Z-UI-SERVICES | 1,1 h | Snapshot/CTS/Generation/Projektpfad; WPF Release 0/0 (`evidence/T378-timeline-project-lifecycle.md`) |
| T379 Persistenzfehler | PASS | 6–10 h | Teamleiter/Data-Agent + unabhängiger Reviewer | SHARED/Z-DATA | 3,2 h | DB-first, typisierte Fehler, Rowcount-Guard, exakte Vector-Kompensation (`evidence/T379-persistence-truth.md`) |
| T380 Analysewahrheit | PASS | 6–10 h | Video-/UI-Agent + Teamleiter-Review | Z-VIDEO/Z-UI-VM | 1,4 h | DB-first complete/partial/failed; Clip-/Projekt-/Generation-Guard (`evidence/T380-video-analysis-truth.md`) |
| T381 Connection-Leases | PASS | 5–8 h | Brain-Agent + Teamleiter-Review | Z-BRAIN | 1,3 h | Pfad-/ID-/epochgebundene Leases, deferred close, stale Write-Guard (`evidence/T381-brain-project-leases.md`) |
| T382 Atomare Erstellung | PASS | 4–6 h | Teamleiter | Z-PROJEKT/Z-DATA | 0,8 h | Same-parent Staging, atomarer Rename, tokengeprüfte DB-/FS-Kompensation (`evidence/T382-atomic-project-creation.md`) |
| T383 Bounded Fanout | PASS | 1–2 h | Terminal-Agent + Teamleiter-Review | Z-SSE | 0,4 h | Zentraler bounded Drop-Oldest-Fanout und Drop-Metrik (`evidence/T383-bounded-sse-fanout.md`) |
| T384 NSwag-Clean-Build | PASS | 1–2 h | Teamleiter | Z-UI-SERVICES/Z-INFRA | 0,3 h | `CoreCompile`, unbedingtes Compile-Item, Build 0/0 (`evidence/T384-nswag-corecompile.md`) |
| T385 DTO-Konvergenz | PASS | 3–5 h | WPF/API-Agent + Teamleiter-Integration | Z-UI-SERVICES | 0,9 h | generierte Transporttypen + explizite UI-Adapter; WPF 0/0 (`evidence/T385-generated-dto-convergence.md`) |
| T386 Render-Retry-Identität | PASS | 6–10 h | Render-/Data-Agent + Teamleiter-Review | Z-RENDER/Z-DATA | 1,1 h | aktive Dedupe, terminale Attempts, Content-/Projektidentität (`evidence/T386-render-retry-identity.md`) |
| T387 DirectML-Provisioning | PASS | 8–16 h | GPU/Infra-Agent + Teamleiter | Z-INFRA | 2,8 h | Freigegebenes 3,2-GB-Bundle, immutable Quellen/Lizenzen, Allowlist, SHA-256, atomare Installation (`evidence/T387-directml-provisioning.md`) |
| T388 Python-Lock | PASS | 6–12 h | Infra-Agent + Teamleiter-Review | Z-INFRA | 1,4 h | 41 direkte Pins/124 Wheel-Hashes, 4 reproduzierbare Vendor-Wheels, Setup fail-closed (`evidence/T388-python-windows-lock.md`) |
| T389 .NET-Lock | PASS | 3–6 h | Infra/WPF-Agent + Teamleiter-Review | Z-INFRA/Z-UI | 0,7 h | SDK 9.0.316 + vollständiger NuGet-Graph + Locked Restore/WPF 0/0 (`evidence/T389-dotnet-nuget-lock.md`) |
| T390 Provenienz | PASS | 4–8 h | Teamleiter/Infra | Z-INFRA | 1,0 h | CycloneDX-SBOM + Commit/Dirty/SDK/Lock/Artefakt-Receipt; Dirty-Gate fail-closed (`evidence/T390-release-provenance.md`) |
| T391 Löschbestätigung | PASS | 2–3 h | UI-Agent + Teamleiter-Review | Z-UI-SERVICES/Z-UI-VM | 0,6 h | Default-No vor 4 Löschpfaden, exakte Ziele, Fehler lokal sichtbar; WPF 0/0 (`evidence/T391-delete-confirmation.md`) |
| T392 FFmpeg-/Settings-Wahrheit | PASS | 5–8 h | Settings-Agent + Teamleiter-Integration | Z-UI-VIEWS/Z-UI-VM | 1,3 h | kanonische Runtime, atomarer Save, sichtbare Load-/Save-Fehler (`evidence/T392-settings-runtime-truth.md`) |
| T393 UI-Ergebniswahrheit | PASS | 4–6 h | Chat/UI-Agent + Teamleiter-Integration | Z-UI-VM/Z-UI-SERVICES/SHARED | 1,2 h | Chat-, GPU- und Empfehlungswahrheit; WPF 0/0 (`evidence/T393-ui-result-truth.md`) |
| T394 Exception-Policy | PASS | 2–4 h | Teamleiter | Z-UI | 0,5 h | redigiertes Crashlog, einmaliger Fatalpfad, kein Save aus inkonsistentem State (`evidence/T394-fatal-exception-policy.md`) |
| T395 Responsive Video-Toolbar | PASS | 2–3 h | Views-Agent + Teamleiter-Review | Z-UI-VIEWS | 0,4 h | Aktionen und Statusbereiche umbrechend; WPF 0/0 (`evidence/T395-responsive-video-toolbar.md`) |
| T396 Accessibility | PASS | 16–32 h | 2 UI-Agenten + unabhängiger Reviewer | Z-UI-VIEWS/Z-UI-VM | 3,4 h | 16 Views, UIA/Fokus/Shortcuts, Timeline Nudge/Trim/Scrub; 5 Review-Findings geschlossen (`evidence/T396-accessibility-keyboard.md`) |
| T397 CachedTab-Reapply | PASS | 2–4 h | Controls-Agent + Teamleiter-Review | Z-UI-CONTROLS | 0,3 h | Presenter-Reparenting; WPF Release 0/0 (`evidence/T397-cached-tab-template-reapply.md`) |
| T398 Native C#-Tests | PASS | 12–20 h | Test-Agent + unabhängiger Reviewer | Z-TESTS | 2,1 h | 28 MSTest-Vertragstests/135 Assertions, exakte Pins und eigener Lock (`evidence/T398-native-test-implementation.md`) |
| T399 Python-Coverage/Skips/Temp | PASS | 4–8 h | Teamleiter + unabhängiger Reviewer | Z-TESTS/Z-INFRA | 1,6 h | Coverage ≥53, expiring owned skips, owned temp cleanup, T362 tree-digest preservation (`evidence/T399-python-quality-gates.md`) |
| T400 Security-Workflow | PASS | 6–12 h | Security-Agent + unabhängiger Reviewer | Z-INFRA | nicht separat gemessen | Secret/History, Python-/NuGet-SCA, Dependency Review, SBOM, Negativkontrollen und SHA-Receipts; 3 Review-Runden PASS (`evidence/T400-security-workflow.md`) |
| T401 PR-/Branch-CI | PASS | 4–8 h | Infra-Agent + unabhängiger Reviewer | Z-INFRA | nicht separat gemessen | alle Branches/PRs, SHA-gepinnte Actions, Locked Gates, ≥28 native Tests (`evidence/T401-required-ci.md`) |
| T402 Dokumentationswahrheit | PASS | 3–5 h | Docs-Agent + Teamleiter | Z-DOCS | 1,0 h | DoD-Vertrag, autoritative Skillquelle, Manifest-/Lizenzwahrheit, 55 Links PASS (`evidence/T402-documentation-truth.md`) |
| T403 Implementierungswahrheit | PASS | 2–4 h | Teamleiter + 3 unabhängige Reviewer | SHARED/Z-REVIEW | 2,3 h | 19 Findings geschlossen; statischer Integritäts-Sweep PASS (`evidence/T403-complete-diff-review.md`); `.completed` commitgebunden im nächsten Gate |
| T404 Gezielte Fault-Injection | PASS | 3–6 h | Test-Team | QC | 1,2 h | 48/48 Python + 9/9 native PASS; 5 Build-/Betriebslücken geschlossen (`evidence/T404-targeted-fault-injection.md`) |
| T405 Python-Gesamtsuite | PASS | 1–3 h | Teamleiter/Test-Team | QC | 3,0 h | 1.127 Tests, 0 Fehler, 11 freigegebene Skips, 0 ungeprüfte Skips, Coverage 61,4 % (`evidence/T405-python-release-gate.md`) |
| T406 Native C#-Tests und WPF Release | PASS | 1–3 h | Teamleiter/WPF-Test | QC | 0,2 h | Locked Restore PASS; 28/28 Tests; WPF Release 0 Warnungen/0 Fehler (`evidence/T406-dotnet-release-gate.md`) |
| T407 Clean-Checkout-Windows-Gate | PASS | 2–5 h | Infra/Test-Team | QC | 0,3 h | Externer Checkout, isolierte NuGet/Pip-Restores, NSwag, WPF 0/0, 28/28 Tests und 3,2-GB-Assetprüfung PASS (`evidence/T407-clean-checkout-gate.md`) |
| T408 GUI-Wahrheit | PASS | 3–6 h | GUI-Agent + Teamleiter | QC | 1,4 h | 14 Views, Fehler-/Löschzustand, 70/70 autoritative Auflösungs-/DPI-Renderings PASS (`evidence/T408-gui-release-gate.md`) |
| T409 Accessibility-QC | PASS | 3–6 h | GUI-Agent | QC | 0,8 h | Keyboard, Fokus, UIA und 14/14 High-Contrast-Renderings PASS (`evidence/T409-accessibility-release-gate.md`) |
| T410 Projektwechsel-E2E | PASS | 4–8 h | Teamleiter/Test-Team + unabhängiger Reviewer | QC | 2,0 h | 5/5 Backend mit realem Brain-Rebind/Lease-Retirement und 5/5 echte UI-A→B-Wechsel PASS (`evidence/T410-project-switch-e2e.md`) |
| T411 DirectML-/AMF-Fresh-Install | PASS | 4–8 h | Teamleiter/GPU-/Render-Agent + unabhängiger Reviewer | QC | 1,2 h | 5/5 DirectML, H.264/HEVC-AMF, exakte RX-LUID, 18/18 Assets und 103/103 Vertragsprüfungen PASS (`evidence/T411-directml-amf-fresh-install.md`) |
| T412 Render-Retry/Restart | PASS | 3–6 h | Teamleiter/Render-Agent + unabhängiger Reviewer | QC | 0,5 h | echte Cross-Process-Dedupe, terminale Retries, `interrupted → running → completed` und Contentwechsel; 68/68 PASS (`evidence/T412-render-retry-restart.md`) |
| T413 Security/Provenienz | PASS | 16–37 h | Security-Team + Reviewer | QC | 8,5 h | S1–S7 PASS; Clean-SHA `7fece74`, `release_eligible=true`, 182 SBOM-Komponenten (`evidence/T413-s7-final-gates.md`) |
| T414 Abschlusswahrheit | OPEN | 2–4 h | Teamleiter | Z-DOCS/QC | – | QC/Brain/Marker-Digests; `.qc-passed` nur 100 % |
| T415 Veröffentlichung | OPEN | 1–3 h | Teamleiter | Git/Remote | – | PR, Required Checks, Main, Release |

### T413 laufende Reparaturpakete

| Paket | Status | ETA | Owner | Nächster Beleg |
|---|---|---:|---|---|
| T413-S1 Backend-Identität/Autorisierung | PASS | 4–8 h | Backend-/WPF-Agent + Reviewer | Backend 6/6, WPF 9/9, Harness 10/10; drei Review-Fixzyklen; finaler Review PASS |
| T413-S2 Chat-Logminimierung | PASS | 1–2 h | Chat-Agent + Reviewer | Tool-/Prompt-/Antwort-/Exception-Inhalte fehlen im Live-Log; 2/2 PASS |
| T413-S3 Timeline-Limits | PASS | 1–2 h | Pacing-Agent + Reviewer | 144.000 Einträge/128 MiB vor Parse; 4/4 PASS; unabhängiger Review PASS |
| T413-S4 sichere Legacy-Migration | PASS | 2–4 h | Data-Agent + Reviewer | Restricted Unpickler/Strict JSON/atomarer Publish; 22/22 und Re-Review PASS |
| T413-S5 Python-SCA/Lock | PASS | 4–12 h | Infra-Agent + Reviewer | 130-Wheel-Produktlock und isolierter 29-Wheel-Scannerlock; zwei exakte Ausnahmen bis 2026-09-01; Live-OSV 130/130 ohne unaufgelöste Treffer; 26/26 PASS; Re-Review PASS |
| T413-S6 MCP-Pin/Integrität | PASS | 1–3 h | Infra-Agent + Reviewer | Exakte Pins 3.2.5/0.1.0, 110 SRI-Knoten, Full-Lock-SHA/Tree/Node-Gate, offline; 9/9 PASS; Re-Review PASS |
| T413-S7 finaler Security-/Provenienzlauf | PASS | 3–6 h | Teamleiter + Reviewer | Gesamtsuite 1.207/0, Coverage 62,116 %, C# 42/42, WPF Publish, Secret/History, Python-/NuGet-SCA, MCP und Clean-SHA-Provenienz PASS |

### Laufende Regeln

- Teamleiter aktualisiert Tabelle automatisch bei Start, Review, PASS, Blocker
  und ETA-Änderung.
- Agent meldet nur Evidenz; ausschließlich Teamleiter setzt `PASS`.
- Funktionale Tests beginnen gesammelt bei T404. Vorher nur Syntax-, XML-,
  Truncation-, statische Vertrags- und zwingende Build-Integritätschecks.
- Gleiche Fehlersignatur höchstens drei Fixzyklen; danach unabhängige
  Root-Cause-Prüfung oder `BLOCKED`.
- Gleicher Befehl mit gleichen Argumenten höchstens zweimal ohne neue Evidenz.
- Höchstens drei offene, falsifizierbare Ursachenhypothesen pro Task.
- 45 Minuten ohne neue Evidenz oder zweimalige ETA-Überschreitung aktiviert
  `LOOP_GUARD`; Teamleiter unterbricht Ansatz/Agent.
- Agenten melden spätestens alle 30 Minuten Evidenz oder Blocker; Ausgaben
  bleiben Caveman-komprimiert und auf Zone/Ticket begrenzt.
- Standardbudgets: Investigator 800, Builder 500, Reviewer 700 Output-Tokens;
  Überschreitung nur mit Ledger-Begründung.
- Gesamtsuite, Clean-Checkout, GUI, Hardware und Full-Length-Render nur in
  T404–T413 oder nach belegter Gate-relevanter Änderung.
- Keine doppelte Suche ohne ausgewiesenen unabhängigen Reviewzweck.
- Erreichte Abnahmekriterien beenden Task; kein ungefragtes Nachpolieren.
- Claude Code läuft nur ticket-/zonengebunden mit expliziter Tool-Allowlist,
  `--no-session-persistence`, JSON-Ausgabe und vorab gesetztem Kostenlimit.
- Claude-Budgetfehler werden nicht blind mit höherem Limit wiederholt; zuerst
  Kontext und Tools reduzieren, danach höchstens ein belegter Folgelauf.
- Claude-Limits: Investigator 10 min/0,15 USD/max. 2 Starts, Reviewer
  15 min/0,25 USD/1 Start, Builder 30 min/0,75 USD/1 Start; OBJ-72 insgesamt
  höchstens 10,00 USD gemeldete Kostenäquivalenz ohne neue Nutzerfreigabe.
- Claude-Builder arbeiten nur im temporären Worktree. Fremd- oder
  Shared-Zonenpfade verwerfen den gesamten Diff vor jeder Übernahme.
