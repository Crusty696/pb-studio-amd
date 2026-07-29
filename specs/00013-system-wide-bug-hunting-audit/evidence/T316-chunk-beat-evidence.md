# T316 — Chunk and beat evidence

Status: CONFIRMED

## Root cause

- `StreamingAudioAnalyzer` retained only aggregate output and grouped error
  strings. Successful per-chunk results disappeared at return.
- `audio_router` did not forward chunk provenance to persistence.
- `AppState.update_audio_analysis()` preserved a previous
  `is_analyzed=true` when a later analysis was partial, so a partial rerun
  could remain durably labelled successful.
- Read-only SQLite inspection of live media row `1910` confirmed
  `status=analyzed`, `beat_count=12646`, and no `chunk_evidence` field.
  `PRAGMA quick_check` returned `ok`.

## Contract

- Every scheduled window has one durable record with index, absolute start,
  duration, overall status, and per-stage status.
- Successful stages record beat, trigger, representative-feature, and energy
  counts; failed stages retain their concrete error.
- Load failures block dependent stages and reserve the missing energy interval.
- Partial/failed chunk stages propagate to `_analysis_status=partial`.
- SQLite `ai_data_json`, in-memory cache, and reload restore carry
  `chunk_evidence`, analysis status, stage status, and stage errors.
- Explicit `is_analyzed=false` now clears stale success truth; omitted values
  still preserve existing state for unrelated partial updates.

## 6,335.027-second cardinality

With `window=30 s`, `overlap=5 s`, and `step=25 s`:

`ceil((6335.027 - 5) / 25) = 254`

The evidence schema therefore records all 254 primary analysis chunks. If the
beat source is a stem, the separate original-mix energy pass is retained under
`mix_energy` rather than overwriting primary provenance.

## Static verification

- `python -m compileall -q src/pb_studio/audio backend/routers/audio_router.py backend/app_state.py` — PASS
- `git diff --check` for all three changed files — PASS
- Static caller/persistence/reload reference scan — PASS
- Functional and fault-injection execution remains deferred to T332.
