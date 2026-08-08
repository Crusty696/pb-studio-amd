# Plan: OBJ-74 Tiefenaudit, Analyse-Resume und Pacing-Wahrheit

**Status:** PLANNED
**Spec:** `specs/00019-deep-app-audit-resume-pacing/spec.md`

## Geklärte Entscheidungen

- Resume ist standardmäßig stage-/chunk-selektiv; Vollanalyse nur mit
  explizitem Force-Vertrag.
- Bestehende Analysefelder werden merge-only behandelt. Nicht angeforderte
  Stages sind kein Löschsignal.
- Kein neues Paket und keine DB-Migration. Checkpoints nutzen versionierte
  bestehende JSON-Persistenz, sofern die Implementierungsanalyse dies bestätigt.
- Pacing-Anforderungen hängen von aktiven Matching-/Trigger-Optionen ab.
  Unvollständige Medien werden nicht still als vollständig behandelt.
- Audit und Reproduktion gehen jeder Produktänderung voraus.

## Architektur

```text
WPF Command
  -> ApiClient DTO
  -> FastAPI Analyze/Pacing Request
  -> Stage Planner (requested - valid completed)
  -> Stage/Chunk Worker
  -> DB-first checkpoint/merge
  -> RAM + FAISS/Brain publication
  -> correlated terminal SSE
  -> WPF stage status / retry action

Pacing Request
  -> Requirement Preflight
  -> eligible/excluded/missing clip set
  -> Trigger + ClipSelector scoring
  -> selection provenance
  -> timeline commit
```

## Arbeitspakete

1. Funktionskatalog und frische Baseline über alle Produktzonen erstellen.
2. Verlust-/Unterbrechungsreproduktionen für Audio, Video und WPF-Batchpfade
   schreiben und rot beweisen.
3. Kanonischen Stage-Planer, merge-only Persistenz und Interrupt-Checkpoints
   sequenziell in Shared-/Analysezonen implementieren.
4. WPF-DTOs, Modelle, Batchsteuerung und gezielte Retry-Anzeige verdrahten.
5. Pacing-Preflight, Clip-Eignung und Auswahlprovenienz implementieren und
   mit deterministischen sowie echten Medien prüfen.
6. Alle Claude-Branches gegen Main prüfen, gültige Änderungen auf aktuelle
   Architektur portieren und die geprüften Branch-Tips ohne Tree-Rückschritt
   als verarbeitet in der Integrationshistorie erfassen.

## Zonen und Reihenfolge

| Reihenfolge | Zone | Verantwortung |
|---|---|---|
| 1 | Z-DOCS/Z-TESTS | Katalog, Reproducer, Evidence |
| 2 | SHARED (`backend/app_state.py`) | kanonische Persistenz-/Checkpoint-Verträge |
| 3 | Z-AUDIO | Audio Stage-/Chunk-Resume |
| 4 | Z-VIDEO | Video Stage-Resume und merge-only Outcome |
| 5 | Z-UI-SERVICES/Z-UI-VM/Z-UI-VIEWS | DTO, Status, Batch, Retry |
| 6 | Z-PACING | Preflight, Auswahl, Provenienz |
| 7 | QC sequenziell | Gesamt-, Native-, Build-, API-, GUI-, Hardwaretests |

Shared-State und Cross-Module-Resume werden nicht parallel editiert. Read-only
Audits und disjunkte Tests dürfen parallel laufen.

## Geplante Produktpfade

- `backend/app_state.py`
- `backend/routers/audio_router.py`
- `backend/routers/video_router.py`
- `backend/routers/pacing_router.py`
- `backend/schemas/audio_schemas.py`
- `backend/schemas/video_schemas.py`
- `backend/schemas/pacing_schemas.py`
- `src/pb_studio/pacing/`
- `src/pb_studio/services/pacing_service.py`
- `PBStudio.UI/Services/ApiClient.cs`
- `PBStudio.UI/Models/AudioClip.cs`
- `PBStudio.UI/Models/VideoClip.cs`
- `PBStudio.UI/ViewModels/AudioLibraryViewModel.cs`
- `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs`
- `PBStudio.UI/ViewModels/DirectorViewModel.cs`
- `PBStudio.UI/Views/`
- `Tests/`, `PBStudio.UI.Tests/`, `test-report/`

## Verifikation

- Python: `PYTHONPATH=src .venv\Scripts\python.exe -m pytest Tests/ -q`
- Native UI: `dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release`
- WPF: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
- SDD: `scripts/validate_sdd.py` für Phase open/implementation/QC
- echte Medien: ausschließlich `C:\Users\david\Videos\test_data\audio` und
  `C:\Users\david\Videos\test_data\video`
- Live-App: Launcher `start.bat`, REST/SSE, alle 14 Tabs, Backend-Kill/Restart
- Pacing: gleiche Inputs/Settings ergeben nachvollziehbare Scores; aktivierte
  Optionen verändern erwartete Rangfolge; fehlende Stages erscheinen im Preflight.

## Risiken

- Stage-Fingerprint-Drift kann veraltete Ergebnisse fälschlich wiederverwenden.
- FAISS/Brain-Dualwrite benötigt Kompensation bei Persistenzfehlern.
- `asyncio.to_thread` ist nicht hart abbrechbar; Commit-Guards und cooperative
  Checkpoints müssen stale Resultate abweisen.
- Long-Mix-Checkpointing darf Speicher/OOM-Verhalten nicht verschlechtern.
- Director darf Basispacing nicht unnötig blockieren, wenn deaktivierte Modi
  deren Analysedaten nicht benötigen.
- `separator.py` bleibt LOCKED; Stem-Resume wird nur außerhalb dieser Datei
  geändert oder als offener Blocker dokumentiert.

## Evidence

- `test-report/function-catalog.md`
- `test-report/state.json`
- `test-report/<bereich>/test-report.md`
- `specs/00019-deep-app-audit-resume-pacing/evidence/`
- `FULLSTACK_AUDIT_PB_STUDIO_2026-08-08.md`
- `specs/00019-deep-app-audit-resume-pacing/evidence/claude-branch-integration.md`
- `qc-report.md`, `.completed`, `.qc-passed` erst nach ihren Gates
