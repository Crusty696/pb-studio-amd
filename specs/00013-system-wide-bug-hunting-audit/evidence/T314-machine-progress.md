# T314 — Maschinenlesbarer Renderfortschritt

Status: `CONFIRMED`

## FFmpeg protocol

The final render command now uses:

`-progress pipe:1 -stats_period 0.5 -nostats`

Progress is parsed as key/value blocks. `progress=end` is mandatory even when
FFmpeg returns exit code zero. Runtime telemetry is derived from `frame`, `fps`
and `out_time_us`, not human-formatted stderr.

## Persistent evidence

Each isolated run writes:

`.render_evidence/<job-token>/<run-id>/`

- `ffmpeg.progress.log`: complete raw machine progress;
- `ffmpeg.stderr.log`: complete FFmpeg diagnostic log;
- `result.json`: schema version, status, exit code, `progress=end`, frame count,
  FPS, `out_time_us`, end PTS, total size, speed, expected duration/frame count,
  log hashes and failure fingerprint;
- `validation.json`: full-decode validation metrics or a typed validation
  failure/cancel fingerprint.

Writes are atomic. Failure fingerprints normalize volatile hexadecimal
addresses before SHA-256. Logs are persisted outside the temporary render
workspace and survive cleanup.

## Failure semantics

- nonzero exit: `failed`;
- exit zero without `progress=end`: `failed`;
- task cancellation: `cancelled`;
- validator failure: typed `failed` record;
- only `progress=end` plus T312 validation can publish the output.

No command line, environment variables or secrets are written into the
machine-readable record or Terminal SSE.

## Static verification

- Python 3.11 compile/AST parse: `PASS`
- Source after edit: 58,528 bytes; 1,484 lines
- Required evidence methods present: `PASS`
- Final command contains machine progress and suppresses human stats: `PASS`
- `progress=end`, exit code, end PTS and fingerprint fields: `CONFIRMED`
- `git diff --check`: `PASS` except pre-existing SDD markdown EOL notices
- Runtime evidence generation is deferred to T332+
