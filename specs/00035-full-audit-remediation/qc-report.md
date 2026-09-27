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
- ONNX Runtime reports `DmlExecutionProvider` and `CPUExecutionProvider`. Provider availability was observed; a real approved model session/inference was not run, so DirectML inference remains unverified.
- Focused regressions, OpenAPI drift tests, and WPF Release build were previously recorded in the active task log; latest known WPF Release build: 0 warnings, 0 errors. Re-run final native checks after remaining implementation changes.
- Latest product commit pushed: `9b8e8ac fix(render): trim source audio to effective export duration`.
- Dependency/deprecation warnings remain; locked package versions were not changed.

## Blockers

- Real-media end-to-end acceptance and GUI acceptance remain unverified. No approved reusable QA project was found, and PB Studio GUI has not been handed over for exclusive test operation.
- Full remediation tasks T002–T011 remain open pending a final point-by-point evidence reconciliation; do not create `.completed` or `.qc-passed` yet.
- Optional hardware/model tests are among skipped cases; skipped does not mean hardware/model capability was live-verified.
