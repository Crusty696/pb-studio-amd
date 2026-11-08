# Clarifications: Pacing Functional Completion

## Resolved Scope

- "Every function" means every control and behavior reachable through the current KI-Regie, Pacing API, preview, and timeline handoff. Uncalled legacy `SyncMode` methods are documented, not revived.
- Optional AI modes count as functional when they either execute on approved local DirectML assets or return a visible, structured unavailable/degraded state. CPU or cloud fallback is not acceptable.
- Existing real media under `C:\Users\david\Videos\test_data` is authoritative for live validation. Tests may create a disposable project, but cleanup may remove only artifacts recorded as created by this run.
- Existing public API fields remain compatible. A visible UI control with no effect is a defect; it must be wired minimally or disabled with a truthful explanation.
- Pacing completion stops at the validated timeline/render boundary. Encoder quality and unrelated Audio/Video analysis quality remain separate areas unless they block Pacing input contracts.
