# QC Report — PB Studio Full Audit Remediation

## Authoritative OBJ-1 Gate

- **Overall result:** **REOPENED / NOT RELEASE-READY**.

## Status

Implementation is underway. This report records verified partial gates only; the master remediation is **not complete** and no release pass is claimed.

## Planned Gates

- Focused regressions and full Python suite.
- Native C# tests and WPF Release build.
- DirectML/AMF runtime checks.
- Real-media API workflow.
- Controlled GUI workflow after PB Studio handover.
- Final reviewer and 54-point traceability reconciliation.

## Results

- Python remainder run: `726 passed, 10 skipped, 0 failed, 16 warnings` in 23m03s; command continued the suite from `test_release_repair_audio_pacing.py` and excluded previously covered filenames. This is a passing remainder segment, not a single uninterrupted full-suite run.
- Canonical FFmpeg runtime live smoke: generated and probed a 320x180 H.264 AMF file with exactly 48 frames at 24 fps; output 242,927 bytes. This verifies the app's hash-checked FFmpeg binary and AMF encode path for this short synthetic case, not a complete PB Studio export workflow.
- DirectML model smoke with existing media: RAFT (`models/raft_small.onnx`) produced finite nonzero flow vectors from two in-memory frames; CLAP produced a normalized 512-D embedding and finite two-label scores from existing `test_30s.wav`; SigLIP produced a normalized 1152-D embedding from a frame of existing `test_5s.mp4`. Each wrapper reported `DmlExecutionProvider` and unloaded after the probe. SigLIP text encoder is absent/untrusted in the approved release asset set, so text classification remains unavailable and was not claimed.
- Native C# tests: `72 passed, 0 skipped, 0 failed`. The run exposed and then verified a transport omission: API `feature_provenance` was dropped by the WPF audio DTO adapter. `AudioAnalysisResult.FromTransport` now retains it; `TransportContractTests.AudioAdapter_PreservesGeneratedPartialResultAndEvidence` asserts source and coverage fields.
- Native C# tests after SSE-cancel regression and audio provenance mapping: `73 passed, 0 skipped, 0 failed`. New `SseCancelled_IsTerminalAndCannotBeThrottled` was first observed failing (1 event instead of 2), then passed after both `cancelled`/`canceled` were treated as terminal.
- WPF Release build after those UI fixes: 0 warnings, 0 errors.
- Project open counters now use validated AppState catalog counts; `test_open_counts_match_loaded_catalog_not_project_folder_files` first reproduced 2-vs-1, then project suites passed 11/11.
- Recovery catalog root handling distinguishes missing paths from other OS access errors and rejects inaccessible roots rather than silently skipping; recovery adapter/bootstrap suites passed 47/47, including deleted-root and simulated PermissionError cases.
- Live render incident reproduced and fixed: the concat timestamp filter used `setpts=N*TB*den/num`, compressing presentation timestamps so FFmpeg dropped 898 of 900 frames while exiting successfully. Regression `test_render_command_and_validator_share_rational_frame_rate` now checks `setpts=N*den/num/TB`; focused render integrity suite: 4 passed. Real `RenderService.render_timeline` with existing six repeated 5-second test clips plus 30-second WAV produced and validated a 30.000-second 1280x720 H.264/AAC MP4: 900 video frames at 30/1 fps, both stream durations 30.000 seconds, 14 progress callbacks through 100%. Follow-up 60-second live run produced 1,800/1,800 frames at 30/1 fps and synchronized 60.000-second H.264/AAC tracks, with 18 progress callbacks to 100%. Artifacts retained at `%TEMP%\pb_studio_render_service_smoke_03_20260927\verified-short-workflow.mp4` and `%TEMP%\pb_studio_render_service_smoke_04_20260927\verified-60s-export.mp4`. This proves short/medium RenderService paths, not the original 98,982/98,984-frame 54:59 export (source unavailable in test-media folder) or full import→analysis→pacing→preview→render→reopen workflow.
- Traceability rows #22, #42, #43 now record focused regression fixes; live SSE cancellation, real GUI counters, and actual filesystem ACL conditions remain unverified.
- ONNX Runtime reports `DmlExecutionProvider` and `CPUExecutionProvider`; actual app wrappers selected DirectML in the three probes above.
- Focused regressions, OpenAPI drift tests, and WPF Release build were previously recorded in the active task log; latest known WPF Release build: 0 warnings, 0 errors. Re-run final native checks after remaining implementation changes.
- Latest product commit pushed: `9b8e8ac fix(render): trim source audio to effective export duration`.
- Dependency/deprecation warnings remain; locked package versions were not changed.

## Blockers

- Real-media end-to-end acceptance and GUI acceptance remain unverified. No approved reusable QA project was found, and PB Studio GUI has not been handed over for exclusive test operation.
- Read-only project-catalog check found 9 rows; all saved project-root candidates are missing. No project was created or modified. Full import→analysis→pacing→preview→render→reopen acceptance needs a user-designated/restored QA project or explicit approval for a disposable one.
- Full remediation tasks T002–T011 remain open pending a final point-by-point evidence reconciliation; do not create `.completed` or `.qc-passed` yet.
- Optional hardware/model tests are among skipped cases; skipped does not mean hardware/model capability was live-verified.
- Specialist read-only review retains material gaps #1/#2/#5 (actual export/evidence/full workflow), #7 (provider recovery), #16 (caption semantic accuracy), and #34 (transition-aware structure labels); see `test-report/specialist-audit-2026-09-27.md` and per-domain audit results. Findings #11/#12, #15, #20/#21, #23/#25, #40/#41, #46, #52/#53 also lack sufficient runtime/integration proof or need contract strengthening.
