---
description: "Task list for Audio/Video Data Depth Visualization"
---

# Tasks: Audio/Video Data Depth Visualization

**Input**: Design documents from `specs/00009-data-depth-visualization/`
**Prerequisites**: `plan.md`, `spec.md`

## Project Mode

`Brownfield`

## Epic / Capability Map

- `[OBJ1]` → Structure Visualization (STATUS:DataDepth)
- `[OBJ2]` → Scene Inspector (STATUS:DataDepth)

## Brownfield Notes

- Existing ViewModels to expand: `TimelineViewModel.cs`, `VideoLibraryViewModel.cs`
- Existing Views to modify: `TimelineView.xaml.cs`, `VideoLibraryView.xaml`

## Phase 1: Foundational (Data Loading)

- [ ] T001 [OBJ1] {TR-001} Update `TimelineViewModel.cs` to fetch song structure from `/audio/structure/{id}`
- [ ] T002 [OBJ2] {TR-002} Update `VideoLibraryViewModel.cs` to fetch scene analysis from `/video/scenes/{id}`

---

## Phase 2: Work Item 1 - Song Structure Ruler (Priority: P1)

- [ ] T003 [OBJ1] {TR-001} Implement `DrawStructure` method in `TimelineView.xaml.cs` using `DrawingContext`
- [ ] T004 [OBJ1] {TR-003} [COMPLETES TR-001, TR-003] Add ToolTip support for segment labels in the ruler area

---

## Phase 3: Work Item 2 - Scene Detail Inspector (Priority: P2)

- [ ] T005 [P] [OBJ2] {TR-002} Define `SceneInspector` UI layout in `VideoLibraryView.xaml` (Details Panel)
- [ ] T006 [OBJ2] {TR-002} [COMPLETES TR-002] Implement `SceneListView` with motion intensity bar markers

---

## Phase 4: Final Polishing

- [ ] T007 [P] Verify structure colors match the "Ableton" professional palette
- [ ] T008 [P] Perform manual verification of scene list updates on video selection

---

## Dependencies

Foundational (Phase 1) → Work Items (Phase 2/3) → Polishing (Phase 4)

- T003 depends on T001.
- T006 depends on T002 and T005.
- Tasks marked `[P]` can run in parallel.
