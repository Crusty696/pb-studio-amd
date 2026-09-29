# T013 live music-to-preview-to-AMF integration — 2026-09-29

## Scope

Ran opt-in pytest node `Tests/test_full_audit_render_integrity.py::test_live_music_selected_cutlist_renders_all_fractional_rate_frames` with `PBSTUDIO_LIVE_AMF_RENDER_TEST=1`, Python 3.11, `PYTHONPATH=src`, unique `APPDATA`/`LOCALAPPDATA`, and unique pytest basetemp. It used the approved existing fixture catalog read-only (`data/pb_studio.db`, SQLite `mode=ro` + `PRAGMA query_only=ON`) and existing files `test_30s.wav`, `test_20s.mp4`, `test_12s.mp4`. No saved project/database/media was modified. All preview/export outputs and evidence remain in `%TEMP%\pb00035-amf-integration-7ebb3e4eec5c4103afa9339dd0c3c1e4\pytest\test_live_music_selected_cutli0\`.

## Observed and proven

- The test checked cached audio/video-analysis fields and motion curves, generated a 30.0-s pacing cutlist, asserted both video source IDs were selected and at least one cut was tied to a measured music trigger, then generated an actual 10-s preview. The preview was present, measured 10 s, and FFprobe found both video and audio streams with the audio stream also 10 s.
- `RenderService` exported the selected timeline through the AMD AMF path at 1280×720 and 30000/1001 fps. Run `job_id=11549d2777dd45168e09aa2c64465a00`, `run_id=b2f007eef8664a20a401d42fc758eb04`; `result.json` says FFmpeg exit 0, progress=end, 899/899 expected frames and includes segment-manifest, canonical-timeline, and exact concat-input SHA-256 receipts. `validation.json` status is `passed`, decoded/expected frames 899/899, video end 29.963267 s, container 29.996633 s, true peak −11.72 dBTP.
- Independent FFprobe: HEVC 1280×720 at 30000/1001 plus AAC stereo 44.1 kHz; container/video duration 29.996633 s. Independent full FFmpeg decode exited 0 with empty stderr. Output SHA-256 `2be2fea5afcdcee6a52e701b48d49aa30659164172160a8a4e9776da46b166e5`, 20,449,659 bytes. Preview and render evidence are retained under the run-scoped temp path above.
- Targeted physical hardware probe separately passed `Tests/test_t357_gpu_wpf_nullability_contracts.py::test_physical_directml_and_lhm_identity_is_rx7800xt` (1 passed); it verified RX 7800 XT DXGI/DirectML selection and ready LHM identity without model inference.

## Limits

This is real media and real AMF through service classes, not UI Automation or visible GUI interaction. It did not import into or reopen the PB Studio project, verify user-visible progress, or assess a human-reviewed narrative/caption answer key. Therefore T013 remains open for GUI/project/reopen acceptance; T003/T014 quality gates also remain open.
