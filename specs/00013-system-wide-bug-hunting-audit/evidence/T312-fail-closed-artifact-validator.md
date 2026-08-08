# T312 — Fail-closed Artefaktvalidator

Status: `CONFIRMED`

## Publication gate

`RenderService.render_timeline()` now validates the staging file before
`os.replace()` can publish it.

The gate requires:

- exactly one video stream;
- exactly one AAC audio stream when audio is requested, otherwise none;
- the expected AMF output codec and target resolution;
- positive audio sample rate and channel count;
- container duration within `max(50 ms, one target frame)`;
- a complete video decode ending in `progress=end`;
- decoded frame count equal to `round(expected_duration * target_fps)` with a
  documented tolerance of one frame;
- video end PTS within the duration tolerance;
- when present, a separate complete audio decode and matching audio end PTS.

Both full-stream decodes use FFmpeg `-xerror` and fail closed on nonzero exit,
timeout, missing progress, missing PTS or malformed progress. Any failure leaves
the prior final output untouched because validation occurs on the unique staging
path before atomic replacement.

## Confirmed reference behavior

The frozen defective artifact has only 58,863 video frames versus 190,051
expected frames at 30 fps for 6,335.027 s. The new frame gate therefore rejects
the exact T308 fingerprint even though its container duration is complete and
FFmpeg originally returned zero.

## Static verification

- Python 3.11 compile/AST parse: `PASS`
- Validator methods present: `_validate_render_artifact`,
  `_decode_artifact_stream`, `_required_duration`, `_progress_end_seconds`
- Validator call is before `os.replace`: `PASS`
- File after edit: 48,507 bytes; 1,186 lines
- Forbidden runtime/encoder reference scan: `PASS`
- `git diff --check`: `PASS` except pre-existing SDD markdown EOL notices
- Runtime, regression and full-length execution: deferred to T332–T336
