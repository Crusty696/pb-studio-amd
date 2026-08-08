# T317 — Downbeat provenance

Status: CONFIRMED

## Root cause and callers

- Long-mix streaming measures beat times with librosa but does not measure bar
  positions/downbeats.
- `AdvancedPacingEngine._identify_downbeats()` converted missing evidence into
  the claim that every fourth beat was a downbeat.
- Cached Pacing then boosted, filtered, and labelled these synthetic points as
  measured downbeats.
- Live SQLite audio row `1910` had neither `downbeats` nor
  `downbeat_provenance`.

## Contract

- Downbeats are either `status=measured` with a named measurement method or
  `status=unavailable`.
- `synthetic` is always `false`; no every-fourth fallback remains.
- BeatNet bar-position output remains accepted as measured provenance.
- Streaming/librosa and beat-time-only detector paths persist
  `unavailable` with zero measured count.
- SQLite, in-memory cache, and reload restore retain `downbeats` and
  `downbeat_provenance`.
- Pacing trusts cached downbeat labels/times only when top-level provenance is
  `measured`; unavailable data yields ordinary beat triggers only.

## Static verification

- Python syntax and `git diff --check` — PASS
- Production scan for `range(0, len(beats), 4)`, “every fourth”, and equivalent
  Python synthesis — no matches
- Caller/persistence/reload scan — PASS
- Public DTO and WPF projection are intentionally synchronized in T327.
- Runtime regression execution remains deferred to T332.
