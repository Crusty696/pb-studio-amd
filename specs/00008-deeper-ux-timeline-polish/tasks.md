---
description: "Task list for Deeper UX & Timeline Polish"
---

# Tasks: Deeper UX & Timeline Polish

**Input**: Design documents from `specs/00008-deeper-ux-timeline-polish/`
**Prerequisites**: `plan.md`, `spec.md`

## Project Mode

`Brownfield`

## Epic / Capability Map

- `[US1]` → Precision Editing (PRD:CAP-004)

## Brownfield Notes

- Existing flows touched: `TimelineView.xaml`, `TimelineView.xaml.cs`
- Regression focus: Ensure basic drag/trim functionality remains intact without "fighting" the user.

## Phase 1: Foundational (Refinement)

- [ ] T001 [US1] {FR-001} Update `TimelineViewModel.cs` to fetch Onset markers in addition to Beats
- [ ] T002 [P] [US1] {FR-003} Define `Snapped` VisualState in `TimelineView.xaml` clip template

---

## Phase 2: Work Item 1 - Enhanced Snapping (Priority: P1) 🎯 MVP

- [ ] T003 [US1] {FR-001} [COMPLETES FR-001] Refactor `Clip_MouseMove` in `TimelineView.xaml.cs` to support multi-trigger snapping (Beats + Onsets)
- [ ] T004 [US1] {FR-003} [COMPLETES FR-003] Trigger `VisualStateManager` transitions for "snapped" state during drag operations

---

## Phase 3: Work Item 2 - Smooth Auto-Scroll (Priority: P1)

- [ ] T005 [US1] {FR-002} Implement `CompositionTarget.Rendering` loop for smooth playhead tracking in `TimelineView.xaml.cs`
- [ ] T006 [US1] {FR-002} [COMPLETES FR-002] Implement `RenderTransform` with easing for timeline container auto-scrolling

---

## Phase 4: Polish & Performance

- [ ] T007 [P] Verify 60 FPS scrolling during playback on large timelines
- [ ] T008 [P] [COMPLETES US1] Perform end-to-end visual review of tab transitions and hover effects

---

## Dependencies

Foundational (Phase 1) → Snapping & Scrolling (Phase 2/3) → Polish (Phase 4)

- T003 depends on T001.
- T004 depends on T002 and T003.
- Tasks marked `[P]` can run in parallel.
