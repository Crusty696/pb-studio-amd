# Live GUI Provider Verification — 2026-09-20

- Project opened through WPF folder dialog: `C:\Users\david\Documents\PBStudio\12345`.
- Project truth visible: 1 audio clip, 395 video clips, 3299.5 seconds.
- WPF Release build: 0 warnings, 0 errors.
- Provider sequence through MODELLE UI: LM Studio → Ollama → LM Studio.
- Every switch returned HTTP 200 and displayed the selected provider with the other provider in standby.
- Direct runtime truth after the sequence: LM Studio loaded instances = 0; Ollama running models = 0.
- GUI release gate: 14/14 tabs rendered, 14 screenshots, no failures.
- Backend and WPF terminated; port 8765 free.
- Complete run log: `logs/gui_live_12345_20260920_040830/complete_run.log`.
- Gate result: `logs/gui_live_12345_20260920_040830/release_gate/gui-release-gate.json`.

Known non-failures: BeatNet/madmom unavailable on Python 3.11 uses the intended librosa fallback. The project has no generated timeline, so a real trim interaction was not available in this run.

## Full functional continuation

- Audio analysis through WPF: 139.7 BPM, E minor, 6205 beats, 54:59 duration.
- Imported fresh uncached clip `functional_video_qwen36_input.mp4`; no existing project clip was removed.
- Video pipeline through WPF: 1 scene, RAFT average 80.1/peak 339.5, SigLIP embedding dimension 1152.
- Vision model: `lmstudio/qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive`; three image calls returned HTTP 200; result persisted with 5 colors and 10 tags.
- Chat through WPF returned exact marker `PB-STUDIO-QWEN36-LIVE-OK` through the same Qwen 3.6 model.
- Post-run standby: LM Studio loaded models = 0; Ollama loaded models = 0; WPF and backend stopped; port 8765 free.
- Evidence: `logs/gui_functional_12345_20260920_041747/complete_functional_run.log`, `qwen36_vision_pass.png`, and `qwen36_chat_pass.png`.
