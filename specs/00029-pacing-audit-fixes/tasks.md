# Tasks: Pacing Audit Fixes

- [X] T001 [OBJ1] {TR-378} Reproduce and trace all four defects across active UI, router, service, engine, and render paths.
- [X] T002 [US1] {FR-392,TR-378} Add failing source-bound and render split-preservation tests in `Tests/`.
- [X] T003 [US2] {FR-393,TR-378} Add failing expected-BPM active-grid tests in `Tests/`.
- [X] T004 [US3] {FR-394,TR-378} Add failing interval validation and enforcement tests in `Tests/`.
- [X] T005 [US4] {FR-395,TR-378} Add failing degradation aggregation and UI-format contract tests in `Tests/`.
- [X] T006 [US1] {FR-392} Implement source-aware finalization in `src/pb_studio/services/pacing_service.py` and preserve segments in `backend/routers/render_router.py`.
- [X] T007 [US2] {FR-393} Apply expected BPM to the active grid in `src/pb_studio/pacing/advanced_pacing_engine.py`.
- [X] T008 [US3] {FR-394} Add schema validation and defensive interval enforcement in `backend/schemas/pacing_schemas.py` and the pacing engine.
- [X] T009 [US4] {FR-395} Aggregate runtime degradations in selector/router code and format them in `PBStudio.UI/ViewModels/DirectorViewModel.cs`.
- [X] T010 [OBJ1] {TR-378,OR-355} Run focused tests, compile sweep, relevant regression suite, and WPF Release build.
- [X] T011 [OBJ1] {OR-355} Write QA report, update Brain log, and create `.completed` and `.qc-passed` after verified success.
