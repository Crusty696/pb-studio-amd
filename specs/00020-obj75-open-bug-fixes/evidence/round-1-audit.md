# OBJ-75 Round 1 Audit Evidence

## Scope

- Branch/worktree: `codex/obj75-open-bug-fixes`, OBJ-74 fast-forward included.
- Layers: WPF, REST/SSE, FastAPI, Audio, Video, Pacing, Brain, Core/DirectML,
  Rendering/AMF, Project/Data/Storage, Chat/Models, Settings, Timeline, Terminal.
- Method: 11 read-only specialist-agent audits plus parent convergence checks.
- Excluded: dependency/schema migration, destructive user-data operations,
  production deployment, locked `src/pb_studio/audio/separator.py` edits.

## Baseline Verification

- Python 3.11.9; NumPy 1.26.4; `DmlExecutionProvider` available.
- Full-tree `compileall`: PASS.
- OBJ-75 SDD open validator: PASS after audit extension.
- Existing resume/preflight/SSE baseline: 16/16 PASS.
- Isolated OBJ-74 lifecycle/long-mix/provenance candidate: 26/26 PASS.
- Specialist targeted clusters: 343 PASS total; no agent source edits.

## Agent Matrix

| Audit | Zone | Findings H/M/L-I | Targeted tests |
|---|---|---:|---:|
| Audio | Z-AUDIO | 3/1/0 | 21 |
| Video | Z-VIDEO | 3/1/0 | 66 |
| Pacing | Z-PACING | 3/2/0 | 40 |
| Timeline | Z-UI-TIMELINE | 4/3/1 | 8 |
| Core/GPU | Z-CORE | 3/0/1 | 60 |
| Render | Z-RENDER | 1/2/1 | 42 |
| Project/Data | Z-DATA/Z-PROJECT | 3/1/0 | 41 |
| Chat/Models | Z-CHAT-MODELS | 1/3/2 | 85 |
| Settings | Z-SETTINGS | 1/2/1 | 42 |
| Brain | Z-BRAIN | 3/1/0 | 89 |
| Terminal | Z-TERMINAL | 0/3/0 | 8 |
| **Total** |  | **25/19/6** | **502** |

The 502 specialist-test total includes independently overlapping clusters and
is not a unique pytest test count.

## High Findings

### Audio

- Long-mix drum-trigger Mel filters collapse narrow bands and emit empty-filter
  warnings in `src/pb_studio/audio/streaming_analyzer.py`.
- Long-mix key analysis reads original-mix chroma after energy overwrite instead
  of the selected instrumental source in `backend/routers/audio_router.py`.
- HTDemucs instrumental synthesis materializes several full-length arrays and
  can OOM after successful separation in `backend/routers/audio_router.py`.

### Video

- Scene decode errors become `completed` plus empty payload and are never retried.
- `force=True` still accepts existing embedding reuse.
- Color/mood metrics average KMeans centers without cluster population weights.

### Pacing and Timeline

- Key matching and UI anchors do not activate the advanced path alone.
- UI-anchor synthetic IDs replace real clip identity.
- Semantic scores only create a shortlist; motion can fully replace ranking.
- Pending timeline autosave is lost on tab unload.
- Recreated Timeline views do not hydrate state or preserve selection.
- Timeline ItemsControl is non-virtualized despite 144,000-entry contract limit.
- Backend duration caps are not returned to UI, causing saved/rendered drift.

### Core, Render, Project, Chat, Settings

- Model eviction releases accounting while wrapper-owned ORT sessions can remain.
- Sensor truth remains deliberately advisory by accepted ADR; tracked as accepted
  operational risk, not an automatic code change.
- `/gpu/cleanup` calls nonexistent `get_model_budget()`.
- FFmpeg normalization can block cancellation on synchronous stderr readline.
- Project close reports success after Brain unbind failure.
- Backup helper is uncalled and excludes embedding/file/FAISS truth sources.
- Corrupt embedding cache lacks recovery and leaks already-open initialization handles.
- Chat stream can write assistant history into a newly opened project.
- Forced VRAM environment precedence contradicts visible settings.

### Brain

- Feedback retry has no client operation ID and double-learns after lost responses.
- Missing analysis features become synthetic numeric evidence and receive credit.
- Projector training repeatedly replays older feedback at every 20-event trigger.

## Cross-Domain Convergence

1. **Project identity captured too late or not at all:** Chat history, anchor writes,
   UI timeline save and some async UI results.
2. **Success published before durable/semantic truth:** Scene empty success, Project
   close, GPU eviction, rendering progress, provider status.
3. **Implemented contract has no effective consumer:** Semantic score, Key/Anchor
   advanced activation, backup API, forced VRAM priority.
4. **Bounded container with unbounded single item or owner:** Terminal entry,
   Timeline visual tree, HTDemucs arrays, external ORT session owners.
5. **Tests inject state instead of proving producer wiring:** repeated historical
   pattern; new regressions must assert production entrypoints.

## Primary Sources Used for Fix Review

- Python subprocess pipe/deadlock and `communicate()` guidance:
  https://docs.python.org/3.11/library/subprocess.html
- Python SQLite online backup API:
  https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
- OpenCV VideoCapture property caveats:
  https://docs.opencv.org/4.9.0/d4/d15/group__videoio__flags__base.html
- FFmpeg `-an` video-only output contract:
  https://ffmpeg.org/ffmpeg.html
- NumPy weighted averages:
  https://numpy.org/doc/stable/reference/generated/numpy.average.html
- librosa Mel-filter construction:
  https://librosa.org/doc/main/filters.html
- ONNX Runtime session/memory guidance:
  https://onnxruntime.ai/docs/performance/tune-performance/memory.html

## Gate

Round 1 audit complete. Product fixes, full convergence, live checks and Round 2
remain open. No release marker is authorized by this evidence.

## Round-1 Remediation Progress

- `T019 / Z-RENDER` complete: cancellation no longer blocks on
  `stderr.readline()`, post-transcode probe cancellation removes its temporary
  artifact, and `include_audio=False` no longer requires or probes audio.
- Laufverifikation ausstehend: OR-344 sperrt Tests und Builds bis zur eigenen
  Nutzerfreigabe.
- `T021 / Z-CORE` complete: `/gpu/cleanup` uses the public `get_model()` API;
  ModelLoader now clears weakly registered SigLIP/CLAP session owners before
  confirming VRAM release. The accepted advisory LibreHardwareMonitor contract
  remains unchanged.
- Laufverifikation ausstehend: OR-344 sperrt Tests und Builds bis zur eigenen
  Nutzerfreigabe.
- `T020 / Z-DATA` remediation statically reviewed: Project close no longer reports
  success after Brain unbind failure; anchor publish is epoch-guarded; corrupt
  embedding-cache initialization recovers and closes partial resources; Brain
  backups now include physical embedding files and are wired to clean close.
- Laufverifikation ausstehend: OR-344 sperrt Tests und Builds bis zur eigenen
  Nutzerfreigabe.
- `T022 / Z-CHAT` complete: request-local project keys prevent cross-project
  history writes; both server and client histories share the token budget;
  fallback events/status use the current provider receipt; WPF transport errors
  and cancellation remain visible.
- Laufverifikation ausstehend: OR-344 sperrt Tests und WPF-Build bis zur
  eigenen Nutzerfreigabe.
- `T024 / Z-TERMINAL+CONFIG` complete: oversized entries are individually
  truncated, UI updates are coalesced and disposal-guarded, reconnect gaps emit
  a visible marker, forced VRAM overrides the normal cap, and LLM provider
  config uses `ConfigManager` instead of a second file reader.
- Laufverifikation ausstehend: OR-344 sperrt Tests und WPF-Build bis zur
  eigenen Nutzerfreigabe.
