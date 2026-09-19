# Tasks: Pacing Functional Completion

- [X] T001 [OBJ1] {FR-396,FR-397} Build the productive-path function catalog in `test-report/function-catalog.md` from current WPF, API, service, engine, persistence, preview, and timeline code.
- [X] T002 [OBJ1] {TR-379} Run and record the existing focused Python and C# Pacing baseline in `specs/00030-pacing-functional-completion/evidence/baseline.md`.
- [X] T003 [US1] {FR-398,TR-379} Verify cut-list ordering, continuity, interval, source-bound, finite-value, and active-project invariants; add regressions in `Tests/` for uncovered defects.
- [X] T004 [US2] {FR-397,FR-399,TR-379} Verify every visible Director parameter reaches and affects the active runtime path; add Python/C# contract regressions for uncovered defects.
- [X] T005 [US3] {FR-400,TR-379} Verify progress correlation, cancellation, concurrent requests, retry, stale-result rejection, project transitions, and truthful error/degradation presentation.
- [X] T006 [US4] {FR-397,FR-398,FR-400,TR-379} Verify generated timeline reload/update, preview creation, and timeline/render-boundary handoff without stale or invalid state.
- [X] T007 [US1] {FR-398} Implement minimal active-path fixes in `src/pb_studio/pacing/`, `src/pb_studio/services/pacing_service.py`, or `backend/` for proven engine/service defects.
- [X] T008 [US2] {FR-397,FR-399} Implement minimal DTO/ViewModel/View fixes in `PBStudio.UI/` for proven Director contract defects.
- [X] T009 [US3] {FR-400} Implement minimal lifecycle, correlation, cancellation, persistence, or degradation fixes for proven runtime defects.
- [ ] T010 [OBJ1] {TR-379,OR-356} Run Python compile sweep, focused and relevant Pacing regression cluster, C# tests, Release build, and IRON-rule scan; record results in `specs/00030-pacing-functional-completion/evidence/automated-verification.md`.
- [ ] T011 [US1] {FR-401} Run real-media API validation with approved audio/video inputs and record exact receipts in `test-report/pacing/test-report.md`.
- [ ] T012 [US2] {FR-399,FR-401} Run GUI validation of every visible KI-Regie function and record screenshots/UI evidence in `specs/00030-pacing-functional-completion/evidence/gui/`.
- [ ] T013 [OBJ1] {FR-401,OR-356} Shut down cleanly, remove only run-owned test artifacts, verify recovery/cleanup, and write `test-report/pacing/cleanup-report.md`.
- [ ] T014 [OBJ1] {FR-396,FR-397,FR-398,FR-399,FR-400,FR-401,TR-379,OR-356} Write final function/status report, update Brain log and any new learning, then create `.completed`, `qc-report.md`, and `.qc-passed` only after every P1 gate passes.
