# T311 — Deterministischen EOF-Fehler beheben

Status: `CONFIRMED`

## Implemented cause-specific contract

File: `src/pb_studio/rendering/render_service.py`

- Format-compatible sources no longer bypass normalization when they are
  Long-GOP encoded.
- Frame addressability is checked from video-packet keyframe flags.
- All AMF normalization intermediates use the T309-proven all-intra setting
  `-g 1`.
- Every generated intermediate is post-validated before it can enter the concat
  manifest.
- Probe or postcondition failure is fail-closed.
- The one-normalization-per-distinct-source cache remains unchanged.
- The concat filter, final AMF encoder, mux graph and public DTOs are unchanged.

## Caller and side effects

The fix is limited to the normalization boundary called by
`RenderService.render_timeline()`. It covers both mismatched inputs and
previously bypassed format-compatible Long-GOP inputs.

Expected side effects are larger temporary all-intra files and longer
normalization. Existing per-source caching and cleanup bound duplicate work;
job-level isolation is handled separately by T313.

## Static verification

- Python 3.11 compile/AST parse: `PASS`
- File size after edit: 39,607 bytes
- File line count after edit: 956
- Required methods present: `_normalize_clips`, `_is_frame_addressable`,
  `_encoder_args`, `_transcode_clip`, `_generate_concat_file`
- Forbidden encoder/runtime reference scan: no CUDA, ROCm, pynvml, libx264,
  libx265 or Media Foundation reference added
- `git diff --check`: `PASS` except pre-existing line-ending notices in SDD
  markdown files
- Functional, regression, hardware and E2E execution: intentionally deferred
  to T332–T336 by the approved gate

The runtime counterexample supporting the exact `-g 1` contract is preserved in
`evidence/T309-stage-isolation/evidence.md`.
