---
description: "Task list for Resilience & Edge-Cases"
---

# Tasks: Resilience & Edge-Cases

**Input**: Design documents from `specs/00010-resilience-edge-cases/`
**Prerequisites**: `plan.md`, `spec.md`

## Project Mode

`Brownfield`

## Epic / Capability Map

- `[OBJ1]` → Self-Healing SSE (STATUS:Stability)
- `[OBJ2]` → Boundary Verification (STATUS:Stability)

## Brownfield Notes

- Existing files to modify: `PBStudio.UI/Services/SSEClient.cs`, `PBStudio.UI/MainWindow.xaml`, `src/pb_studio/core/vram_arbiter.py`

## Phase 1: Foundational (Backend Hardening)

- [ ] T001 [OBJ2] {TR-002} Implement forced VRAM capping logic in `vram_arbiter.py` via `PB_STUDIO_FORCED_VRAM` env var
- [ ] T002 [OBJ1] Add a `/health/heartbeat` dummy endpoint to FastAPI to verify basic reachability (optional but recommended)

---

## Phase 2: Work Item 1 - Self-Healing SSE (Priority: P1)

- [ ] T003 [OBJ1] {TR-001} Refactor `SSEClient.cs` to include exponential backoff (1s, 2s, 4s...) on connection drop
- [ ] T004 [OBJ1] {TR-003} Implement `ConnectionStatus` overlay in `MainWindow.xaml` with auto-hide on reconnect

---

## Phase 3: Work Item 2 - Boundary Testing (Priority: P2)

- [ ] T005 [P] [OBJ2] {TR-002} Implement specialized stress test script `src/tools/verify_low_vram_resilience.py` (Capped at 4GB)
- [ ] T006 [OBJ2] {TR-002} [COMPLETES OBJ2] Run 4GB stress test and verify 0 OOM crashes (rejections are expected/logged)

---

## Phase 4: Final QA

- [ ] T007 [P] [OBJ1] [COMPLETES OBJ1] Kill backend during active SSE progress and verify automatic UI recovery
- [ ] T008 [P] Perform final visual review of the "Connection Lost" overlay UI

---

## Dependencies

Foundational (Phase 1) → SSE Hardening (Phase 2) → Boundary Testing (Phase 3) → QA (Phase 4)

- T003 depends on T002.
- T006 depends on T001 and T005.
- Tasks marked `[P]` can run in parallel.
