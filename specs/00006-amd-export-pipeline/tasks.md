---
description: "Task list for AMD Export Pipeline implementation"
---

# Tasks: AMD Export Pipeline

**Input**: Design documents from `specs/00006-amd-export-pipeline/`
**Prerequisites**: `plan.md`, `spec.md`

## Project Mode

`Brownfield`

## Epic / Capability Map

- `[US1]` → High-Speed Export (PRD:CAP-005)
- `[US2]` → Accurate Cut Export (PRD:CAP-005)

## Phase 1: Foundational (Refinement)

- [X] T001 [US1] {FR-001} Finalize AMD AMF encoder detection in `RenderService._detect_best_encoder`
- [X] T002 [US1, US2] {FR-002} Implement robust FFmpeg concat list generation in `RenderService._generate_concat_file`
- [X] T003 [US1] {FR-003} Implement high-precision stderr queue draining for telemetry in `RenderService._parse_ffmpeg_progress`

---

## Phase 2: Work Item 1 - High-Speed Export (Priority: P1)

- [X] T004 [US1] {FR-001} Configure `RenderService` to use `-quality balanced` and `-b:v bitrate` for AMF encoders
- [X] T005 [US1] {FR-003} Integrate live FPS/ETA telemetry emission in `RenderService.render_timeline`
- [X] T006 [US1] [COMPLETES US1] Verify AMF encoding speed gains using `verify_release_smoke.ps1` with real hardware

---

## Phase 3: Work Item 2 - Accurate Cut Export (Priority: P1)

- [X] T007 [US2] {FR-002} Implement mixed-source FPS normalization before concatenation in `RenderService._normalize_clips`
- [X] T008 [US2] {FR-002} Implement `-segment_time_metadata 1` support in FFmpeg command for precise cut alignment
- [X] T009 [US2] [COMPLETES US2] Perform visual sync verification of final exported video against audio triggers

---

## Phase 4: Reliability & Polish

- [X] T010 {FR-004} Finalize `/render/cancel` state handling to ensure clean process termination
- [X] T011 Implement FFmpeg stderr tail logging on failure for better remote debugging
- [X] T012 Verify memory management during long exports (> 1 hour)

---

## Dependencies

Phase 1 (Foundational) → Phase 2/3 (Work Items) → Phase 4 (Polish)

- T006 depends on T004/T005.
- T009 depends on T007/T008.
- Tasks marked `[X]` are already verified as part of today's `RenderService` overhaul.
