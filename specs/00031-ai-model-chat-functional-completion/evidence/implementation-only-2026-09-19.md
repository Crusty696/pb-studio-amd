# Spec 00031 — Implementation-only Evidence (2026-09-19)

## Scope

- Productive MODELLE and CHAT paths were source-audited and repaired.
- User explicitly prohibited tests, builds, GUI checks, and live provider probes.
- Runtime, compilation, and GUI behavior remain `[unknown: verification deferred]`.
- No `.completed` or `.qc-passed` marker was created.

## Root cause and implemented behavior

- Video batch analysis was clip-centric and repeatedly traversed scene, RAFT, SigLIP, and VLM stages per clip. It is now stage-centric across the selected clip set: one stage processes all clips before the next stage begins.
- Vision selection previously ran for every sampled frame and treated empty tag content like a provider failure. The successful provider/model is now pinned per task/mode; empty content falls back for that frame without switching the VLM. Real provider failures retain bounded failover and replace the pin only after success.
- Chat now uses the same stable model policy unless an explicit/configured override or real failure requires a change.

## Implemented fixes

### Video and model runtime

- `src/pb_studio/video/lmstudio_vision_wrapper.py`: exact provider/model pinning, override precedence, bounded failover, content-error separation.
- `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs`: stage-centric multi-clip batch execution with existing cancellation/project guards.
- `src/pb_studio/ai/model_inventory.py`: invalidation revision prevents a concurrent provider refresh from publishing an already stale snapshot.
- `backend/routers/models_router.py`: truthful pull completion, exact delete errors, unloadable-state reset, real chat-or-vision inference test.
- `PBStudio.UI/ViewModels/ModelManagerViewModel.cs`: single active mutation, cancellation on tab unload/disposal, backend error publication.
- `PBStudio.UI/Services/ApiClient.cs`: model mutation methods preserve backend error detail.
- `PBStudio.UI/Views/ModelManagerView.xaml`: truthful provider-bound “Inferenz-Test” wording.

### Chat and tools

- `src/pb_studio/ai/chat_agent.py`: stable chat model pin, bounded replacement after real failure, visible same-model no-tools retry.
- `src/pb_studio/ai/tool_registry.py`: audio, video, and pacing jobs use the existing long-running timeout class.
- `PBStudio.UI/Models/ChatEvent.cs`, `PBStudio.UI/Models/ChatMessage.cs`, `PBStudio.UI/Services/ApiClient.cs`: stable tool-call IDs survive SSE parsing and correlate repeated tool names correctly.
- `PBStudio.UI/ViewModels/ChatViewModel.cs`: persisted project history loading, stale-project suppression, clear/send lifecycle guards, recovery notices without false terminal errors.
- `PBStudio.UI/Views/ChatView.xaml`: keyboard help matches Enter/Shift+Enter behavior.

## Deferred verification

- T010: automated focused/full verification — blocked until explicit user authorization.
- T011: live provider/API/GUI verification — blocked until explicit user authorization.
- T012: completion and QC markers — blocked until T010 and T011 pass.
