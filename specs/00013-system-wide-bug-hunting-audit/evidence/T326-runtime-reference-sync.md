# T326 – Runtime Reference Synchronization

Status: CONFIRMED

## Root cause and data flow

- `PBSTUDIO_FFMPEG_PATH`, WPF settings, `ConfigManager`, backend settings,
  PATH fallback, and the unpinned setup download could resolve different
  FFmpeg binaries.
- FFprobe was derived or configured independently, so the probe/encode pair
  was not an atomic runtime contract.
- Several launch and test wrappers accepted non-3.11 Python or omitted
  `--host 127.0.0.1`.
- Call flow checked:
  `setup/start/test/release scripts or WPF -> uvicorn -> ServerConfig /
  ConfigManager / encoder_utils -> FFmpeg and FFprobe subprocesses`.

## Contract implemented

- `config/ffmpeg-runtime.json` is the shared version/hash manifest.
- The active runtime remains the T325-approved 8.0.1 bundle at
  `tools\ffmpeg\bin`; the 6.1.1 candidate remains
  `pending_t332_hardware_qc`.
- `scripts/runtime_contract.ps1` and `.bat` enforce project-local Python
  3.11, absolute `PYTHONPATH`, the stable FFmpeg/FFprobe pair, hashes, and
  canonical uvicorn host/port arguments.
- Setup uses a pinned asset and verifies asset, FFmpeg, and FFprobe hashes.
  It no longer adds FFmpeg to the user PATH.
- Python backend/config/encoder consumers reject alternate binaries and use
  the verified pair.
- WPF startup and settings force and persist the canonical project runtime;
  FFmpeg and FFprobe are passed together to the backend.
- Direct start, build, test, release-smoke, OpenAPI, stress, SSE, Brain, and
  LM Studio wrappers were synchronized. Public API DTOs were not changed.

## Side effects and boundaries

- External runtime overrides now fail closed when they select another path.
- Setup `--Force` preserves an existing bundle under
  `tools\runtime-backups` before replacement.
- No binary was replaced, no dependency or lockfile changed, and no
  functional, hardware, GUI, regression, or E2E test ran.
- The unrelated existing parser errors in
  `scripts/lm_kill_runtime_test.ps1` remain outside T326.

## Static evidence

- PowerShell parser: PASS for every changed `.ps1`.
- Python `py_compile`: PASS for `runtime_contract.py`, `encoder_utils.py`,
  `config_manager.py`, and `backend/config.py`.
- JSON parse: PASS for `config/ffmpeg-runtime.json` and `config.json`.
- Runtime diagnostic: PASS; Python resolves to `.venv` 3.11.9 and the
  project-local FFmpeg/FFprobe hashes match active 8.0.1.
- Reference scan: no unpinned FFmpeg setup URL or FFmpeg PATH fallback
  remains in active consumers; every direct uvicorn wrapper uses explicit
  host and port.
- Independent read-only audit: CONFIRMED the original divergence and the
  synchronized caller set; no subagent file changes.
