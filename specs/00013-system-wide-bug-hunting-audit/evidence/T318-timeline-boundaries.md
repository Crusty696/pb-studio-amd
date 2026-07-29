# T318 — Timeline boundaries

Status: CONFIRMED

## Root cause

- Stored reference timeline: 4,816 cuts, first start
  `1.9272562358276644`, final end `6335.027`.
- The shared finalizer only stretched an under-running last cut. It did not
  normalize the first boundary or clamp overflow.
- Sequencer and rule-engine returns bypassed the finalizer.

## Contract

- All non-empty generated cut lists pass through one finalizer.
- Entries starting at or beyond the target budget are discarded.
- The first cut starts at exactly `0.0`.
- Its source `clip_start` is shifted backward where possible so the existing
  terminal source point is preserved.
- The last cut ends at exactly the requested target (`duration_limit` or full
  audio duration).
- Original and normalized boundary values are retained in cut metadata.
- Sequencer and rule-engine paths now use the same boundary gate.

## Static verification

- `python -m py_compile src/pb_studio/services/pacing_service.py` — PASS
- `git diff --check -- src/pb_studio/services/pacing_service.py` — PASS
- Return-path reference scan — all generated non-empty paths reach
  `_finalize_cut_list`
- Runtime timeline regression remains deferred to T332.
