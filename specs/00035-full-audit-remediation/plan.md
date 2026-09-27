# Plan: PB Studio Full Audit Remediation

## Instructions Check

- Preserve `project-instructions.md`, CLAUDE.md/AGENTS.md AMD, DirectML, locked-version, path, MVVM, and testing rules; repository ADRs 0001–0004 remain binding.
- Work on `codex/full-audit-remediation`; do not commit/push/merge. Preserve pre-existing dirty work, especially recovery/bootstrap and WPF observability changes.
- Do not edit `src/pb_studio/audio/separator.py`; no dependency/version changes, schema/FAISS migration, user-data deletion, or repeated QA project creation.
- Automated tests/builds/API checks are authorized by the implementation request. GUI manipulation remains gated on explicit handover of PB Studio.

## Implementation Sequence

1. Verify clean feature-spec structure, capture baseline dirty paths, validate all 54 traceability rows, and record shared interfaces/ownership before dispatch.
2. In parallel, implement disjoint Audio, Video/vision, Brain, and Model/Chat tasks. Each task writes failing regression first, observes the intended failure, makes minimal correction, and runs its focused tests.
3. Implement music-first Pacing after the domain contracts stabilize. Preserve beat timestamps; bound narrative-theme scoring; repair timebase, source-repeat provenance, motion scale, BPM strength alignment, and ID normalization.
4. Implement Preview and Export on separate files after Pacing. Preview covers safe path/audio/duration/player seeking. Export covers exact failure reproduction, rational FPS, collision rejection, evidence retention, and validation progress.
5. Implement SSE/GPU recovery after render terminal semantics are fixed. Reconcile event gaps/restarts/overflow/cancel through existing status APIs; bound lock wait without unlocking a live worker; correct reservation order.
6. Handle project persistence and project-switch races sequentially in shared-state files. Preserve existing recovery changes; distinguish absent/unavailable roots without deleting catalog entries or media. Prove duplicate path/name behavior and counter consistency.
7. Integrate with focused cross-domain regressions, full Python suite, native C# tests, WPF Release build, DirectML/AMF checks, then one reusable real-media API workflow.
8. After user hands over PB Studio, run the controlled GUI acceptance pass on the same QA project. Keep release/QC markers absent until every applicable gate passes; record unresolved gates rather than claim success.

## Parallel Code-Zone Ownership

| Workstream | Exclusive write zone |
|---|---|
| Video/vision + caption cooldown | `backend/routers/video_router.py`, `src/pb_studio/video/**`, unique video regression files |
| Audio provenance/coverage | `backend/routers/audio_router.py`, `src/pb_studio/audio/**` except locked separator, unique audio regression files |
| Brain learning/annotation | `src/pb_studio/brain/**`, unique Brain regression files |
| Models/chat | `backend/routers/models_router.py`, `src/pb_studio/ai/model_inventory.py`, `src/pb_studio/ai/chat_agent.py`, `src/pb_studio/ai/tool_registry.py`, `PBStudio.UI/ViewModels/ChatViewModel.cs`, unique tests |
| Pacing | `src/pb_studio/pacing/**`, `src/pb_studio/services/pacing_service.py`, `backend/routers/pacing_router.py`, unique tests |
| Preview | `src/pb_studio/rendering/preview_renderer.py`, preview-only router/schema files, `PBStudio.UI/ViewModels/TimelineViewModel.cs`, `PBStudio.UI/Views/TimelineView*`, unique tests |
| Export | `src/pb_studio/rendering/render_service.py`, `backend/routers/render_router.py`, render DTOs, Production ViewModel/API files only where assigned, unique tests |
| Project shared state | Parent-owned `backend/app_state.py`, `backend/routers/project_router.py`, `src/pb_studio/storage/recovery_adapters.py`; unique recovery regression files |
| Events/GPU | `backend/dependencies.py`, `backend/routers/events_router.py`, `PBStudio.UI/Services/SSEClient.cs`; do not edit render-router terminal payload or project shared state |
| Project UI | `PBStudio.UI/Services/ProjectService.cs`, unique project tests |

Tests are owned by unique test files per task; no concurrent edits to the same file. Any cross-zone conflict pauses that pair and is integrated sequentially by the parent.

## Verification Gates

- Every finding is checked against current code; tests assert observable behavior, not implementation details alone.
- Per task: RED for the intended pre-fix defect, GREEN after fix, adjacent regressions and syntax/compile check.
- Integration: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/ -x -q`; relevant native C# test projects; `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release`; DirectML provider/session-flag and FFmpeg AMF checks.
- API/E2E uses approved existing fixtures and one existing QA project; verify output path, streams, rational FPS, complete decode, source identities, project reload, and musical/narrative receipts.
- No GUI action before handover. No `.completed` until implementation is done; no `.qc-passed` until all automated and live acceptance gates pass.

## Rollback and Evidence

- No destructive rollback, database/FAISS migration, or cleanup of existing data. Revert only task-owned changes after preserving a copy/diff; never reset or checkout over the user's dirty work.
- Keep exact commands/results in `evidence/`; update Brain project log after completed milestones. Do not publish or merge.
