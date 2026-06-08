# Tasks: KI-Modus-Sync, Modell-Zuordnungs-Heuristik & LM-Studio Fallbacks

- [ ] T001 [P0] {FR-001} Fix registry model size heuristics in `src/pb_studio/ai/model_registry.py` (sort unknowns to the end)
- [ ] T002 [P0] {FR-002} Implement model-load retry loop in `src/pb_studio/video/lmstudio_vision_wrapper.py` (exclude failed model and retry)
- [ ] T003 [P0] {FR-003} Implement `POST /models/mode` endpoint in `backend/routers/models_router.py` to persist selected mode in `config.json`
- [ ] T004 [P0] {FR-004} Dynamically read default mode in `backend/routers/models_router.py` (active tasks) and `backend/routers/video_router.py` (captioning)
- [ ] T005 [P0] {FR-005} Extend `IApiClient.cs` and `ApiClient.cs` with `UpdateKiModeAsync(string mode)` in `PBStudio.UI`
- [ ] T006 [P0] {FR-006} Integrate `UpdateKiModeAsync` into `SettingsViewModel.cs` (SaveSettings/OnKiModeIndexChanged)
- [ ] T007 [P0] {FR-007} Trigger Model list refresh in frontend after mod change to update task badges
- [ ] T008 [P0] {TR-001} Verify with pytest subset `pytest Tests/test_model_registry.py`
- [ ] T009 [P0] {TR-002} Run full WPF build and execute E2E test sequence
