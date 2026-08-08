# T328 – Test Implementation

Status: CONFIRMED

## Root cause and data flow

- T311–T327 introduced new fail-closed media, evidence, provenance, sparse
  learning, runtime identity, and public status contracts without one focused
  regression set spanning their caller boundaries.
- Verified flows before authoring:
  `render router -> job-bound RenderService -> AMF/decode validator -> atomic
  publication/evidence`;
  `audio streaming -> cache/persistence -> pacing -> timeline provenance`;
  `canonical features -> Brain scorer/feedback -> weight/outbox persistence`;
  `runtime manifest -> launchers/backend/WPF`;
  `Pydantic/OpenAPI -> ApiClient/SSE -> visible WPF state`.

## Tests implemented

- `Tests/test_release_repair_render_full_length.py`: 10 test functions for
  all-intra frame addressability, fail-closed packet probes, complete H.264 and
  HEVC 6335.027-second validation, machine progress, audio headroom/end
  silence, target preservation, run evidence isolation, resume, and owned
  process shutdown.
- `Tests/test_release_repair_audio_pacing.py`: 9 test functions / 16 cases for
  source audio, complete chunk evidence and faults, partial DTO truth,
  authoritative downbeats, exact timeline boundaries, snap provenance, and
  adaptive unique-LRU diversity.
- `Tests/test_release_repair_brain_runtime_contracts.py`: 15 test functions /
  20 cases for canonical features, semantic availability, sparse credit,
  unknown-cut rejection, v2 migration rehearsal/restore, runtime hashes and
  launchers, DTO/OpenAPI/UI visibility, containment, and secret-field absence.
- Existing Brain and snap tests were updated to the T319/T323 contracts.

## Security validation rubric

- [x] Attacker/operator-controlled output and project paths reach resolved
  containment guards before filesystem effects.
- [x] Non-canonical runtime overrides fail before process launch.
- [x] Unknown feedback IDs fail before weight mutation; unavailable semantic
  axes receive no credit.
- [x] Render publication requires complete decode and validated terminal
  evidence while preserving an existing target on failure.
- [x] Public render status exposes only the explicit evidence allowlist and no
  secret-bearing fields.

Dynamic security validation is deliberately deferred to T332/T334.

## Follow-up drift closed

- T320 available-history pruning retained duplicate legacy IDs. The selector
  now keeps only the newest occurrence before adaptive limiting.
- Old tests still expected synthesized snap type, Cartesian Brain credit, and
  semantic similarity without explicit availability. Those expectations now
  match the approved contracts.
- OpenAPI selected-schema property parity was rechecked against Pydantic after
  correcting the RenderProgress component placement.

## Static evidence

- Python `py_compile`: PASS for all three new files and all updated tests/source.
- AST parse: PASS; 34 new test functions authored.
- Pydantic/OpenAPI selected property-set comparison: PASS.
- `git diff --check`: PASS for the T328 file set.
- Pytest collection/execution, build, FFmpeg, hardware, GUI, regression, and
  E2E execution: not run; gated until T332.
