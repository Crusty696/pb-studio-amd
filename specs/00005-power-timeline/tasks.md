---
description: "Task list for Interactive Power-Timeline implementation"
---

# Tasks: Interactive Power-Timeline

**Input**: Design documents from `specs/00005-power-timeline/`
**Prerequisites**: `plan.md`, `spec.md`

## Project Mode

`Mixed`

## Epic / Capability Map

- `[US1]` → Visual Overview (PRD:CAP-004)
- `[US2]` → Manual Cut Adjustment (PRD:CAP-004)

## Brownfield Notes

- Existing flows touched: `TimelineViewModel.cs`, `TimelineView.xaml`
- Regression focus: Ensure existing `ListView` summary remains accurate after drag/trim operations.

## Phase 1: Foundational (Cross-Work-Item Blockers)

- [X] T001 [P] [US1] {FR-001} Create `WaveformBarModel` in `PBStudio.UI/Models/WaveformBarModel.cs`
- [X] T002 [P] [US1] {FR-005} Create `TimeToPixelConverter` in `PBStudio.UI/Converters/TimeToPixelConverter.cs`
- [X] T003 [US1] {FR-002} Implement aggregated waveform loading logic in `PBStudio.UI/ViewModels/TimelineViewModel.cs`

---

## Phase 2: Work Item 1 - Visual Overview (Priority: P1) 🎯 MVP

- [X] T004 [US1] {FR-001, FR-005} Implement `TimelineView.xaml` with Canvas, Ruler, and Zoom slider
- [X] T005 [US1] {FR-002} Bind `WaveformBars` to background `ItemsControl` in `TimelineView.xaml`
- [X] T006 [US1] {FR-006} [COMPLETES FR-006, US1] Implement real-time Playhead sync between Canvas and `MediaElement` in `TimelineView.xaml.cs`

---

## Phase 3: Work Item 2 - Manual Adjustment (Priority: P1)

- [X] T007 [US2] {FR-003} Implement Mouse drag-and-drop logic for `TimelineEntryModel` in `TimelineView.xaml.cs`
- [X] T008 [US2] {FR-004} [COMPLETES FR-004] Implement edge-based trimming logic for `TimelineEntryModel` in `TimelineView.xaml.cs`
- [X] T009 [US2] {FR-003} [COMPLETES FR-003] Implement debounce logic for backend synchronization of timeline changes
- [X] T010 [US2] [COMPLETES US2] Implement `POST /project/timeline` update in `ApiClient.cs` and `TimelineViewModel.cs`

---

## Phase 4: Polish

- [X] T011 Add "Snap to Beat" visual indicators in `TimelineView.xaml`
- [X] T012 Verify 1-hour mix performance via `verify_release_smoke.ps1` expansion

---

## Dependencies

Foundational (Phase 1) → Visual Overview (Phase 2) → Manual Adjustment (Phase 3) → Polish (Phase 4)

- T006 depends on T004.
- T009/T010 depend on T007/T008.
- Tasks marked `[P]` can run in parallel.
