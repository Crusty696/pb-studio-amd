# PB Studio – Worklog

## 2026-03-10

### Baseline established
- Confirmed project is in active hybrid migration: WPF/C# frontend + FastAPI bridge + Python core.
- Verified repo has active uncommitted changes and significant removal of legacy PyQt UI files.
- Verified WPF build succeeds cleanly (`0 warnings`, `0 errors`).
- Verified backend import works (`from backend.main import app`).
- Verified running backend health endpoint works and GPU is available.
- Verified GPU SSE endpoint responds.
- Verified WPF app executable starts successfully in smoke test.

### Live smoke test completed
- Audio import: passed.
- Video import: passed.
- Audio clip listing: passed.
- Video clip listing: passed.
- Audio analysis: passed.
- Waveform retrieval: passed.
- Pacing generation: passed.

### Live smoke test result details
- Audio analysis result: ~117.45 BPM, 18 beats, key = G minor.
- Pacing generation result: 3 cuts, total duration ~3.53s.

### Process decision
- Project work will proceed in controlled autonomous mode.
- Before each work block: explicit plan + tools + research if needed.
- After each block: update status + compress context into files.

### Video analysis + thumbnail verification
- Confirmed thumbnail generation is lazy on request, not done during import.
- Live thumbnail test passed on `smoke_test_video.mp4`.
  - HTTP 200
  - `content-type: image/jpeg`
  - JPEG magic bytes `ffd8`
  - size: 6203 bytes
- Live video analysis test passed on `smoke_test_video.mp4`.
  - HTTP 200
  - `has_embedding: true`
  - `embedding_dim: 1152`
  - `scene_count: 0`
  - `avg_motion: 0.0`
- Scene endpoint returned valid empty result set.
- Motion endpoint returned valid response object (zero / empty values on trivial clip).

### Interpretation
- The earlier `thumbnail_available=false` signal was not proof of a bug; thumbnails are generated lazily by request.
- Video backend core is more complete than initially assumed.
- Remaining uncertainty is now more about quality/richer media and render/export than basic video backend functionality.

### Render / export end-to-end smoke test
- First render attempt failed before execution because of output-path guard.
- Root cause identified: backend `config.project_dir` currently resolves to `C:\Users\david\Documents\PBStudio`, not the active AMD repo path.
- Render smoke test re-run with allowed output path inside `C:\Users\david\Documents\PBStudio\render-tests\`.
- Real render passed end-to-end:
  - render start accepted
  - task status progressed `pending -> running -> completed`
  - output file created successfully
  - output size: `416151` bytes
  - ffprobe duration: `10.0s`
  - render elapsed time: `3.2s`

### Interpretation
- Render/export core is functionally working.
- There is a configuration/path-alignment issue between backend guardrails and the active project workspace.
- This is not a render-engine failure, but it is a real product/workflow issue that should be reviewed.

### Stem separation smoke test
- Live endpoint test executed on short known-good audio clip (`808kick120bpm.mp3`).
- Endpoint returned HTTP 200 with valid `StemResult` schema.
- However, all returned stem paths were `null`.

### Stem separation root-cause review
- Direct local reproduction of `StemSeparator` succeeded.
- Model file exists and loads correctly: `models/UVR-MDX-NET-Inst_HQ_3.onnx`.
- Separator actually generated two stems:
  - `808kick120bpm_(Vocals)_UVR-MDX-NET-Inst_HQ_3.wav`
  - `808kick120bpm_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav`
- Real output files were confirmed in:
  - `C:\Users\david\Dokumente\Pb_studio_AMD_version\temp\...`
- Root cause identified:
  - separator returns relative filenames
  - backend mapping/API flow did not normalize them into usable absolute/project paths

### Stem path normalization fix
- Implemented targeted fix in `backend/routers/audio_router.py`.
- Relative stem outputs are now normalized against the configured temp/output directory before response mapping.
- Also cleaned backend runtime state by removing duplicate competing `uvicorn` processes and restarting a single clean backend instance from the project venv.

### Stem separation re-test
- Live API re-test passed after fix.
- Endpoint returned HTTP 200 with usable absolute paths.
- Verified returned files exist:
  - vocals stem: exists, 1,764,078 bytes
  - instrumental stem: exists, 1,764,078 bytes

### Interpretation
- Stem separation is now functionally working end-to-end for the tested model/clip.
- The defect was contract/path normalization, and it is resolved for the verified case.

### Timeline / production UI workflow verification
- Verified live that backend timeline state is correct after cut generation:
  - `/pacing/timeline` returns entries, duration, and real existing `audio_path`
- Verified live that render start succeeds using exactly the timeline-provided `audio_path`
- Conclusion: backend / contract side is green; remaining gap was WPF workflow glue.

### WPF workflow glue fix
- Implemented targeted messenger-based glue fix.
- `DirectorViewModel` now sends `timeline-refresh` after successful cut generation.
- `TimelineViewModel` now listens for `backend-ready` and `timeline-refresh`, then auto-refreshes timeline data.
- `ProductionViewModel` now listens for `backend-ready` and `timeline-refresh`, and proactively syncs `AudioPath` from timeline.
- `StartRenderAsync()` now reuses the shared sync helper instead of doing ad-hoc inline timeline loading.
- WPF build re-verified clean: `0 warnings`, `0 errors`.

### Interpretation
- The previously suspected gap was real and is now addressed in a minimal, architecture-consistent way.
- Backend correctness was already proven; this fix improves UI coherence and reduces manual refresh friction.

### Render path / config alignment review
- Confirmed static default root source: `backend/config.py` sets `project_dir = ~/Documents/PBStudio`.
- Confirmed `.env` override is currently absent.
- Confirmed both `project_router.py` and `render_router.py` previously relied on that static root.
- Identified correct long-term direction: active project path should be the runtime source of truth; config root should remain fallback/default only.

### Durable project-root fix
- Added shared resolver in `backend/app_state.py`: `resolve_active_project_root(state, fallback_root)`.
- Updated `project_router.py` to use active project root when available, else fallback to configured base.
- Updated `render_router.py` to use the same resolver for output-path guard checks.
- Backend restarted cleanly.
- WPF build re-verified clean: `0 warnings`, `0 errors`.

### Live verification
- Opened active AMD project via `/project/open` with path:
  - `C:\Users\david\Dokumente\Pb_studio_AMD_version`
- Generated pacing data successfully.
- Started render successfully with output path inside the active AMD project path:
  - `C:\Users\david\Dokumente\Pb_studio_AMD_version\data\render_after_project_open.mp4`
- Result: render start accepted (`HTTP 200`) with task id returned.

### Interpretation
- The project-path mismatch is now resolved in the correct direction.
- Active project path is now honored at runtime for guarded project/render operations.
- `config.project_dir` remains useful as fallback/default instead of being the hard runtime truth.

### Richer video-analysis quality test
- No substantially richer local source clip was available beyond generated artifacts.
- Chosen test input: `data/render_after_project_open.mp4` (larger/more realistic than `smoke_test_video.mp4`).
- Live analysis passed:
  - `has_embedding: true`
  - `embedding_dim: 1152`
  - `avg_motion: 3.6472`
  - `motion_category: low`
- Scene endpoint and embedded scenes remained empty on this local clip.
- Semantic outputs (`tags`, `dominant_colors`) also remained empty on this local clip.

### Interpretation
- Video analysis pipeline is functionally working beyond the trivial smoke clip.
- Motion path is now positively verified with non-zero output.
- Remaining uncertainty is more about quality/content richness of available test media than basic backend correctness.
- Scene/tag/color quality should be validated later with a clip containing clearer cuts and richer semantic content.

### PyQt removal classification completed
- Reviewed deleted legacy PyQt area under `src/pb_studio/ui/...` against current WPF views/viewmodels.
- Added durable classification document: `PYQT_MIGRATION_CLASSIFICATION.md`.
- Conclusion:
  - safely replaced: styling shell, generic cards, audio/video analysis triggers, pacing controls, monolithic generation shell
  - explicit rebuild targets: real waveform/beat overlay, true interactive timeline, media preview/player, scene/motion inspection UI, richer audio/video info panels, queued analysis UX, drag-drop ingest, richer render progress/log UI
- Key migration judgment:
  - architecture direction is correct
  - parity risk now comes from missing rich interactive controls, not from the already-replaced shell screens

### Render cancel-path live verification
- Backend was brought up locally via Uvicorn against the repo environment.
- Re-opened active project root:
  - `C:\Users\david\Dokumente\Pb_studio_AMD_version`
- Re-generated a longer short timeline using known-good local assets:
  - audio clip `2` (`808kick120bpm.mp3`)
  - video clips `110..119`
  - generated cut list: `5` cuts, total duration `~10.52s`
- Started live render task:
  - task id: `3219ea4e`
  - output: `data/cancel_test_render.mp4`
- Cancel request sent while status was already `running`.
- Terminal result:
  - status transitioned to `cancelled`
  - elapsed `1.4s`
  - partial output file was removed successfully (`FILE_EXISTS = false`)

### Interpretation
- Render cancel path is now positively verified end-to-end, not just code-inspected.
- Cancel propagation from API -> task flag -> worker -> terminal status works.
- Cleanup after cancel also works for the output target used in the live test.

### Project persistence verification + fix
- Verified the suspicion: `/project/save` previously returned success without durably persisting meaningful runtime state.
- Observed broken pre-fix behavior:
  - save returned success
  - close cleared state
  - reopen did not restore timeline/audio path
  - project info still showed `audio_count=0`, `video_count=0`, `has_timeline=false`
- Implemented minimal durable persistence in `backend/routers/project_router.py`:
  - writes `project.json` with project metadata (`name`, counts, timestamps, `has_timeline`)
  - writes `timeline.json` with `audio_path` + current timeline snapshot
  - `open` now resets state, reloads DB clip catalog, restores timeline/audio path if present
  - `create` now initializes project metadata file
- Live re-verification after backend restart:
  - generated fresh timeline
  - saved project successfully
  - confirmed `timeline.json` written to project root
  - closed project
  - reopened project
  - timeline + audio path restored successfully
  - project info now returns `audio_count=2`, `video_count=119`, `has_timeline=true`

### Interpretation
- Project persistence is no longer a hollow status endpoint.
- The project open/save path now restores a meaningful working session state.
- This removes one of the larger hidden release blockers in the backend workflow.

### WPF Production/SSE workflow fix
- Inspected `TimelineViewModel`, `ProductionViewModel`, `MainViewModel`, `SSEClient`, and backend SSE router contract.
- Found a real UI/runtime bug:
  - `SSEClient` effectively listened only to `/events/progress`
  - `LogReceived` and `GpuStatusReceived` existed as events but were not backed by active listeners
  - result: render log / GPU live updates in WPF were effectively incomplete
- Fixed `PBStudio.UI/Services/SSEClient.cs`:
  - now starts dedicated listeners for `/events/progress`, `/events/log`, and `/events/gpu`
  - keeps per-stream reconnect behavior
  - extended progress event args with backend `status`
- Improved `PBStudio.UI/ViewModels/ProductionViewModel.cs`:
  - handles render terminal states properly (`completed`, `cancelled`, `failed`)
  - no longer marks cancel as instantly finished before backend confirms terminal state
  - now records live render/log messages into a bounded in-memory render log
  - added clear-log command
- Upgraded `PBStudio.UI/Views/ProductionView.xaml`:
  - replaced placeholder render log with real bound `ListBox`
  - added log-clear action and entry count
- Verification:
  - `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Debug`
  - result: `0 warnings`, `0 errors`

### Interpretation
- Production tab is now materially more real, not just visually present.
- SSE-backed runtime feedback is closer to product-grade behavior.
- This also improves confidence that global GPU/live status can actually update as intended.

### Anchor waveform / beat-marker UI upgrade
- Replaced the old placeholder-only Anchor waveform screen with a real backend-driven inspection surface.
- Updated `PBStudio.UI/ViewModels/AnchorViewModel.cs`:
  - loads available audio clips on backend/media refresh
  - allows selecting an audio source for anchor work
  - loads waveform data via `/audio/waveform/{clipId}`
  - loads beat markers via `/audio/beats/{clipId}`
  - builds lightweight UI-ready waveform bars and beat markers
  - keeps current-position marker synced against audio duration
- Updated `PBStudio.UI/Views/AnchorView.xaml`:
  - added audio-source selector
  - added reload action
  - replaced fake waveform placeholder with bound waveform bars + beat markers + current-position line
  - kept the anchor list workflow intact
- Verification:
  - `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Debug`
  - result: `0 warnings`, `0 errors`

### Interpretation
- Anchor view is no longer a decorative stub.
- The app now has a practical sync-inspection surface for audio-driven editing decisions.
- This meaningfully reduces one of the biggest visible WPF parity gaps without dragging domain logic into the UI layer.

### Timeline inspection UI upgrade
- Improved `PBStudio.UI/ViewModels/TimelineViewModel.cs`:
  - added selected-entry state
  - auto-selects first timeline entry after refresh
  - exposes selected cut details (clip, trigger, clip-in, source path)
- Updated `PBStudio.UI/Views/TimelineView.xaml`:
  - binds selected timeline entry
  - adds a real detail/inspection card for the selected cut
  - keeps the existing list/table view while making the screen more useful for review
- Verification:
  - `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Debug`
  - result: `0 warnings`, `0 errors`

### Interpretation
- Timeline is still not a full interactive editor, but it is no longer just a dumb dump table.
- This is a sensible intermediate step before a true timeline-control rebuild.

### WPF project workflow implementation
- Closed the largest remaining product-shell gap by wiring real project lifecycle actions into the WPF main shell.
- Updated `PBStudio.UI/Services/IApiClient.cs` + `ApiClient.cs`:
  - added typed `/project/create|open|save|close|info` client methods
  - added `ProjectInfo` + `StatusResponse` response models
- Replaced stubbed `PBStudio.UI/Services/ProjectService.cs` behavior with real backend-backed project state management.
- Updated `PBStudio.UI/ViewModels/MainViewModel.cs`:
  - added project state (`CurrentProjectName`, `CurrentProjectPath`, `HasProject`)
  - added `CreateProject`, `OpenProject`, `SaveProject`, `CloseProject` commands
  - refreshes project info after backend startup
- Updated `PBStudio.UI/MainWindow.xaml`:
  - added minimal top-level project actions (Neu / Öffnen / Speichern / Schließen)
  - shows current project name/path in the shell header
- Added lightweight `PromptDialog` helper for project naming.
- Verification:
  - `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Debug`
  - result: `0 warnings`, `0 errors`

### Interpretation
- PB Studio now exposes a real project lifecycle in the actual WPF product shell instead of hiding it in backend-only capability.
- This meaningfully improves launchability and reduces the biggest “not finished” product gap.

### WPF startup smoke + crash fix
- Ran the real WPF startup path via `dotnet run --project PBStudio.UI/PBStudio.UI.csproj -c Debug` instead of relying only on compile success.
- Found and fixed a real startup blocker:
  - `TimelineView.xaml` bound computed read-only properties (`SelectedClipName`, `SelectedTimeRange`, `SelectedClipStart`, `SelectedTrigger`, `SelectedFilePath`) without explicit `Mode=OneWay`
  - WPF attempted default editable binding semantics and crashed the app during window creation
- Fixed all affected bindings to `Mode=OneWay`.
- Re-verified:
  - `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Debug` -> `0 warnings`, `0 errors`
  - `dotnet run --project PBStudio.UI/PBStudio.UI.csproj -c Debug` -> app reached running state and actively loaded backend/media data instead of crashing on startup

### Interpretation
- PB Studio now has a real WPF startup smoke proof, not just a build proof.
- This closed an actual launch-blocking regression introduced by the earlier timeline inspection upgrade.

### Release surface cleanup
- Rewrote `README.md` onto the real product architecture and launch path:
  - WPF frontend + FastAPI backend + Python core
  - real startup commands
  - smoke checklist
  - known limits
- This removes the old mixed PyQt/WPF ambiguity from the project surface.

### Integrated runtime + workflow hardening pass
- Implemented a real WPF project workflow in the main shell:
  - New / Open / Save / Close actions
  - current project name/path shown in the shell
  - `ProjectService` now uses real backend project endpoints instead of stub behavior
- Performed a real WPF startup smoke against the app, not just a build check.
- Found and fixed a launch blocker in `TimelineView.xaml`:
  - read-only computed bindings now use `Mode=OneWay`
  - app now reaches running state instead of crashing during window creation
- Hardened `VideoLibraryViewModel` against overlapping refreshes:
  - load gate added
  - thumbnail cache added
  - duplicate thumbnail churn reduced
  - project-close now clears library state cleanly
- Hardened `SSEClient` against runtime payload issues:
  - numeric parsing now tolerates float/string variants
  - fixed live GPU SSE format errors

### Parallel team integration results
- Timeline usability improved:
  - scrubber/transport card added
  - previous/next cut navigation added
  - nearest-cut auto-selection during scrub
  - selected cut index/status surfaced in UI
- Anchor runtime hardened:
  - duplicate waveform/beat loads serialized
  - audio selection preserved across refreshes
  - beat loading skips non-analyzed clips
  - beat recovery retries through analyze once
  - repeated 404 churn suppressed after failed recovery
  - waveform remains usable even if beats are unavailable
- SSE / Production runtime hardened further:
  - SSE frame parsing now respects proper blank-line event dispatch
  - multi-line payloads and keepalives handled more correctly
  - progress payload support widened (frames, elapsed, ETA, output, error)
  - backend SSE router fanout made more robust per connection
  - Production tab now gives richer runtime/GPU/render feedback and cleaner state transitions

### Integrated verification
- `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Debug -p:OutDir=.build_verify\integrated\` passed cleanly.
- `python -m py_compile backend/routers/events_router.py backend/routers/project_router.py` passed.
- Real WPF launch from verified output directory succeeded.
- Backend smoke during integrated run succeeded:
  - `/health` ok
  - audio clips reachable
  - video clips reachable
- Live SSE verification completed earlier for:
  - `/events/progress`
  - `/events/log`
  - `/events/gpu`

### Current known remaining gaps
- Full click-confirmed WPF project open/save/close/reopen path is still not fully exercised end-to-end from the desktop UI.
- Anchor visual click-smoke is still lighter than build/runtime verification.
- A full safe render-progress UI proof from the integrated WPF shell still remains desirable.

### Next work block
- Commit integrated product/runtime hardening block, then continue with practical WPF click-path verification and release/publish readiness
