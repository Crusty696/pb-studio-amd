# Clarifications: Audio Functional Completion

- The user ordered fixes first and prohibited every test until explicit authorization.
- “Audio” includes `src/pb_studio/audio/**`, audio backend routes/schemas/services, productive persistence boundaries, and Audio Library WPF/API contracts.
- The long-file threshold is greater than ten minutes; older contradictory comments are not authoritative.
- BeatNet unavailable on the pinned environment and librosa DSP fallback is expected, not a defect.
- `separator.py` is locked by `audio-expertise`; only its callers, contracts, lifecycle, and state handling may be changed.
- Source-complete does not mean runtime-complete. Test/QC tasks remain open.
