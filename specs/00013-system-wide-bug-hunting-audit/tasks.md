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
- [x] T010 [P] [OBJ-6] {(FR-105)} Fix htdemucs model filename in `backend/schemas/audio_schemas.py`
- [x] T011 [P] [OBJ-7] {(FR-106)} Integrate stems into audio analysis pipeline in `backend/routers/audio_router.py`
- [x] T012 [P] [OBJ-7] {(TR-107)} Run verification tests for stem separation and integrated audio analysis
- [x] T013 [P] [OBJ-1] {(FR-108)} Fix VRAM-Eviction ABBA deadlock in `vram_budget_manager.py` / `model_loader.py`
- [x] T014 [P] [OBJ-1] {(FR-109)} Resolve SQLite project repository deferred transaction contention
- [x] T015 [P] [OBJ-1] {(FR-110)} Secure atexit shutdown saving logic in `vector_store.py`
- [x] T016 [P] [OBJ-2] {(FR-111)} Downscale frames in `video_router.py` to prevent RAM OOM
- [x] T017 [P] [OBJ-2] {(FR-112)} Implement Moondream model caching loop in `video_router.py`
- [x] T018 [P] [OBJ-2] {(FR-113)} Limit RAM-usage in `subtrack_detector.py` stems activity calculation
- [x] T019 [P] [OBJ-3] {(FR-114)} Resolve WPF IDisposable ViewModels root container leak
- [x] T020 [P] [OBJ-3] {(FR-115)} Dispose HttpResponseMessage socket resources in `ApiClient.cs`
- [x] T021 [P] [OBJ-3] {(FR-116)} Add SSEClient EOF delay to avoid connection hot loops
- [x] T022 [P] [OBJ-3] {(FR-117)} Implement active tab polling timer check for `VramTelemetryView`
- [x] T023 [P] [OBJ-3] {(FR-118)} Integrate `WaveformCache` back into `/audio/waveform` route





