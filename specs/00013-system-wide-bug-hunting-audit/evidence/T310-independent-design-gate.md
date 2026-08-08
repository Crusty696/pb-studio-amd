# T310 — Unabhängiges Design-Gate

Status: `DECIDED`

Reviewer: independent read-only agent
Gate result: `CONFIRMED`

## Independent falsification

- The reviewer independently confirmed the 4,816-entry freeze, the exact
  58,863-frame signature and the byte-identical T308 reproduction.
- Demux reached 6,338.71 s with 701,461 packets.
- Decode without `concatdec_select` produced 701,461 frames.
- Decode with the production filter but without AMF or MP4 mux reproduced
  58,863 frames / 1,962.10 s.
- GOP=1 counterevidence produced 189,948 full-manifest frames and changed prefix
  20 from 390 to exactly 985 frames.

AMF final encoding, MP4 muxing and an early demux/decode EOF are falsified as
root causes. Missing frame addressability in normalization is confirmed.

## Caller and contract

`ProductionViewModel → POST /render/start → persisted timeline_snapshot →
_execute_render → _normalize_clips → _transcode_clip → concat manifest →
concatdec_select → AMF/Mux`

`render_router._execute_render()` converts every `clip_start + duration` into a
random-access range. The renderer must therefore guarantee that every distinct
intermediate source is frame-addressable before it writes the concat manifest.
Public request/response DTOs do not change in T311.

## Frozen T311 design

1. Introduce frame addressability as an explicit normalization postcondition.
2. Preserve the one-transcode-per-distinct-source cache.
3. Prevent the existing format-compatible bypass for sources that do not meet
   the frame-addressability contract.
4. Normalize nonconforming sources with the active AMD AMF encoder and the
   independently proven all-intra setting `-g 1`.
5. Statically post-validate the normalized intermediate before manifest
   creation; fail closed when the contract is not met.
6. Keep the existing production concat/filter/final AMF graph otherwise
   unchanged.

Rejected alternatives:

- `tpad` or freeze-frame concealment masks missing content.
- Removing `concatdec_select` admits keyframe pre-roll.
- A final artifact validator detects but does not repair the loss.
- Adding `-g 1` only to transcoding leaves already format-compatible Long-GOP
  sources on the defective bypass.

## Side effects and acceptance

- Expected side effects: larger temporary intermediates, longer normalization,
  generation loss. Bound them through the existing unique-source cache and
  cleanup; T313 further isolates job temp state.
- T311 static acceptance: no format-compatible Long-GOP bypass; AMF-only
  contract preserved; postcondition is fail-closed; manifest graph unchanged.
- Deferred runtime acceptance: frozen 4,816 manifest reaches the GOP=1
  frame-quantized target without the 58,863 fingerprint; full H.264 and HEVC
  validation remains T335/T336.
- Fresh T311 ETA: 4–6 h, confidence `MEDIUM`.

## Review findings

- `src/pb_studio/rendering/render_service.py:345`: format equality permits a
  Long-GOP bypass; include frame addressability in the decision.
- `src/pb_studio/rendering/render_service.py:442`: normalization has no GOP
  contract; create and post-validate all-intra AMF intermediates.
- `src/pb_studio/rendering/render_service.py:542`: random ranges assume
  seek-safe intermediates; enforce the contract before manifest creation.
- `src/pb_studio/rendering/render_service.py:263`: exit zero plus nonempty size
  accepts incomplete streams; T312 must validate before `os.replace`.
