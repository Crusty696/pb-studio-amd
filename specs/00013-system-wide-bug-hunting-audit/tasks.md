---
feature_branch: "00013-system-wide-bug-hunting-audit"
created: "2026-05-29"
spec_path: "specs/00013-system-wide-bug-hunting-audit/spec.md"
plan_path: "specs/00013-system-wide-bug-hunting-audit/plan.md"
---

# Tasks: System-wide Bug Hunting & Codebase Audit

## Work Item Checklist

- [x] T001 [P] [OBJ-1] Perform static audit of Z-CORE & Z-DATA (VRAM & SQLite safety)
- [x] T002 [P] [OBJ-2] Perform static audit of Z-AUDIO & Z-VIDEO (Pipeline & Fallback safety)
- [x] T003 [P] [OBJ-3] Perform static audit of Z-UI-VM & Z-UI-SERVICES (Memory leaks & thread safety)
- [x] T004 [P] [OBJ-4] Perform static audit of Shared-Zones & Z-INFRA (API Routes & traversal safety)
- [x] T005 [P] [OBJ-5] Execute E2E automated smoke runs and Visual screenshot audits
- [x] T006 [P] [OBJ-3] {(FR-101)} Fix SmartDirector VRAM-Thrashing in `src/pb_studio/ai/smart_director.py`
- [x] T007 [P] [OBJ-2] {(FR-102)} Implement true ONNX Batch Inference in `src/pb_studio/ai/siglip_wrapper.py`
- [x] T008 [P] [OBJ-4] {(FR-103)} Add physical Index Re-Indexing `clean_tombstones()` in `src/pb_studio/data/vector_store.py`
- [x] T009 [P] [OBJ-5] {(TR-104)} Execute test verification for AI optimizations


