---
description: "Task list for Release Hardening & UX Polish"
---

# Tasks: Release Hardening & UX Polish

**Input**: Design documents from `specs/00007-release-hardening-ux-polish/`
**Prerequisites**: `plan.md`, `spec.md`

## Project Mode

`Brownfield`

## Epic / Capability Map

- `[OBJ1]` → Native Dialog Abstraction (STATUS:ReleaseReadiness)
- `[OBJ2]` → 4H Stability Verification (STATUS:ReleaseReadiness)

## Phase 1: Setup & Foundational

- [ ] T001 [P] [OBJ1] {TR-001} Create `IDialogService.cs` and `DialogService.cs` in `PBStudio.UI/Services/`
- [ ] T002 [P] [OBJ1] {TR-001} Register `IDialogService` as a Singleton in `App.xaml.cs`

---

## Phase 2: Work Item 1 - Native Dialog Migration (Priority: P1)

- [ ] T003 [OBJ1] {TR-001} Migrate `VideoLibraryViewModel.cs` to use `IDialogService` (folder and file pickers)
- [ ] T004 [OBJ1] {TR-001} Migrate `AudioLibraryViewModel.cs` to use `IDialogService` (file picker)
- [ ] T005 [OBJ1] {TR-001} Migrate `MediaIngestViewModel.cs` to use `IDialogService` (folder picker)
- [ ] T006 [OBJ1] {TR-001} [COMPLETES OBJ1] Migrate `ProductionViewModel.cs` to use `IDialogService` (save file picker)

---

## Phase 3: Work Item 2 - Stability & Performance (Priority: P1)

- [ ] T007 [P] [OBJ2] {TR-004} Audit all AI wrappers in `src/pb_studio/ai/` to ensure `enable_mem_pattern=False`
- [ ] T008 [OBJ2] {TR-002} Implement `src/tools/execute_4h_stress_test.py` with `amdsmi` telemetry and batch loop
- [ ] T009 [OBJ2] {TR-002} [COMPLETES OBJ2] Verify `VRAMArbiter` eviction logic triggers when buffer < 500MB via stress test

---
## Phase 4: Work Item 3 - UI Polish (Priority: P2)

- [ ] T010 [P] {TR-005} Implement GPU-accelerated `RenderTransform` tab animations in `MainWindow.xaml`
- [ ] T011 [P] {TR-006} Verify `VirtualizingStackPanel` is enabled and recycling for all clip list controls
- [ ] T013 [P] {TR-003} [COMPLETES TR-003] Audit all WPF ViewModels for consistent `ObservableObject` and `[ObservableProperty]` usage

---

## Phase 5: Final QA


- [ ] T012 Run full `verify_release_smoke.ps1` expansion to confirm release readiness verdict

---

## Dependencies

Foundational (Phase 1) → Dialog Migration (Phase 2) → Stability (Phase 3) → Polish (Phase 4) → QA (Phase 5)

- T003-T006 depend on T002.
- T009 depends on T008.
- Tasks marked `[P]` can run in parallel.
