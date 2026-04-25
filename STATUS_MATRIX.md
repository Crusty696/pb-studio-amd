# PB Studio – Status Matrix

_Last updated: 2026-03-13 Europe/Zurich_

## Purpose
This file is the operational source of truth for current PB Studio project status.
It tracks:
- current implementation state by area
- verified vs assumed capabilities
- risks / blockers
- next validation or implementation step

Status values:
- `present` = exists and was verified sufficiently
- `partial` = exists but incomplete / only partially verified
- `missing` = not implemented or not reachable
- `regressed` = broken or likely broken

Verification levels:
- `live-tested`
- `build-start-verified`
- `code-inspected`
- `not-yet-verified`

---

## 1. WPF Frontend

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| App startup | present | live-tested + crash-fixed + publish-launch-verified + live-click-path-verified | real WPF startup path verified via `dotnet run`; app now also re-proved in a live UIAutomation session with stable main window and working tab selection | continue deeper workflow checks |
| Main/backend status integration | present | code-inspected + build-start-verified + live-click-path-verified | Header shows `Backend: Online` plus live GPU text in the real WPF window | Settings / reconnect proof |
| Audio library UI wiring | present | code-inspected + live-tested (backend flow) + live-click-path-verified | Audio tab practically loads project asset `test_120bpm` in the real window | none |
| Video library UI wiring | present | build-start-verified + live-tested (backend flow) + live-click-path-verified | Video tab practically loads project asset `test_bars`, and `Alle analysieren` now also runs to completion in the real window | only native import-dialog edge remains |
| Director UI wiring | present | code-inspected + live-tested (backend pacing) + live-click-path-verified + bug-fixed | real WPF Director path now exercised in Release build; found and fixed `JsonElement`→`double` crash in `DirectorViewModel.GenerateCutListAsync`, then re-verified successful 8-cut generation in UI | none |
| Timeline UI | partial | build-start-verified + live-tested contract + glue-fixed + live-click-path-verified + ux-bug-fixed | timeline contract verified live; real WPF tab surfaces project clip content and scrub-position text bug was fixed, but the surface is still scrubber/list-based and not a true interactive edit timeline | decide scope of true timeline/player rebuild |
| Production/Render UI | present | build-start-verified + live-tested contract + glue-fixed + live-click-path-verified + bug-fixed | real WPF render path now verified end-to-end; found and fixed initial-project-state bug in `ProductionViewModel` (pre-opened project incorrectly showed `Kein Projekt geöffnet`) | longer progress/ETA observe |
| Settings UI | present | code-inspected + live-click-path-verified + bug-fixed | real Settings tab now practically verified; found and fixed missed-initial-refresh bug in `SettingsViewModel`, and cleanup path shows `VRAM aufgeräumt` in the real app | none |
| WPF parity vs old PyQt product UI | partial | code-inspected + build-verified | Removed PyQt area is explicitly classified in `PYQT_MIGRATION_CLASSIFICATION.md`; shell screens are largely replaced and Anchor now has real waveform + beat-marker inspection, but true timeline/player/scene-motion inspection still remain rebuild targets | prioritize next interactive timeline/player block |

## 2. Backend / API Bridge

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Health endpoint | present | live-tested | `/health` ok, GPU available true | none |
| Audio routes core | present | live-tested | import/list/analyze/waveform all passed | stems/structure/spectral deeper test |
| Video routes core | present | live-tested | import/list/analyze/thumbnail/scenes/motion all exercised live | broader quality / heavier-input test |
| Pacing generate | present | live-tested | generated 3 cuts in live smoke test | multi-input test |
| Render routes | present | live-tested + cancel-tested + heavy-runtime-tested | start/status/cancel now exercised in both short smoke and longer mixed-material runs; hard gap remains in active ETA/frame/fps telemetry (`/render/status` stays at zeros until terminal state) | patch runtime telemetry path |
| Project routes | present | live-tested + fixed + build-verified + WPF-click-path-verified | backend CRUD already passed; WPF shell path for create/open/save/close/reopen is now also practically verified via UI automation | none |
| Schema / DTO alignment | partial | code-inspected + live-tested subset | key routes align | broaden verification |

## 3. Events / SSE / Runtime Bridge

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| GPU SSE | present | live-tested | `/events/gpu` returns `gpu_status` | long-run observe |
| Progress SSE | present | code-inspected + build-verified + live-tested backend path + live-click-path-verified (short render) | WPF render run visibly transitioned through active state (`Abbrechen` surfaced during run) and completion; a longer job is still needed for richer ETA/progress sampling | longer WPF observe |
| Log SSE | present | live-tested + build-verified + fixed + live-click-path-verified | `/events/log` war zunächst effektiv unverdrahtet; after backend fix the WPF render log now visibly fills in the real app (`8 Einträge` on live render) | longer mixed-workload observe |
| Reconnect behavior | partial | code-inspected + live-tested keepalive + build-verified | reconnect/backoff logic applies across progress/log/gpu listeners; live keepalive behavior verified, but forced-disconnect recovery is still not practically exercised | forced reconnect test |

## 4. Audio

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Audio import | present | live-tested | passed | none |
| Audio library data flow | present | live-tested + live-click-path-verified | clip list available and real WPF tab shows expected project asset | import-dialog path verify |
| Audio analysis | present | live-tested | BPM/key/beat count returned | longer file test |
| Waveform | present | build-start-verified + live-tested | backend 3-band waveform verified; Anchor WPF view renders a real waveform inspection surface and runtime loading was hardened against duplicate refresh races | broader click-path verify |
| Structure data | partial | code-inspected | endpoint exists, not tested live | structure test |
| Spectral data | partial | code-inspected | endpoint exists, not tested live | spectral test |
| Stem separation | present | live-tested + fixed | API now returns normalized usable stem paths; real vocal/instrumental files verified in `temp/` | optional multi-model / richer-audio test |

## 5. Video

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Video import | present | live-tested | passed | none |
| Video library data flow | present | live-tested + live-click-path-verified | clip list available and real WPF tab shows expected project asset | import-dialog path verify |
| Thumbnail generation | present | live-tested | thumbnail endpoint returned valid JPEG (`ffd8`, 6203 bytes); früherer Fehler erwies sich als PowerShell-/Client-Artefakt, nicht als Backend-Defekt | WPF display-path verify |
| Video analyze | present | live-tested | analysis completed successfully on smoke clip and richer render clip | optional real-world clip test |
| Scene data | partial | live-tested | endpoint works, but both tested local clips produced empty scene sets | test with stronger scene-cut source clip |
| Motion data | present | live-tested | motion data now non-zero on richer render clip (`avg_motion≈3.65`, `low`) | richer/high-motion clip test |
| Vision/tagging | partial | live-tested subset | embeddings work (`has_embedding=true`, dim 1152), but tested local clips still produced empty tags/colors | test with semantically richer clip |

## 6. Director / Timeline / Generation

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Basic pacing generate | present | live-tested | generated cuts successfully | quality/multi-input test |
| Timeline persistence / retrieval | present | live-tested + fixed + live-click-path-verified | timeline state now persists and reloads via project save/open flow; real WPF tab also surfaces timeline project content after reopen | deeper timeline interaction |
| Multi-clip selection logic | partial | code-inspected | UI supports it | multi-clip pacing test |
| Cut quality / semantic quality | partial | not-yet-verified | functional only, not judged | manual output review |

## 7. Render / Export

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Render start | present | live-tested + live-click-path-verified | accepted real render task and returned task id; real WPF `Render starten` path now also produced `uia_render_verify.mp4` | longer render / cancel path |
| Render progress | present | live-tested + live-click-path-verified + heavy-runtime-tested + patch-verified (2026-04-24) | progress/status transitions are real and stable; runtime telemetry gap (ETA/frame/fps) was patched and verified with real queue-draining loop | longer render / cancel path |
| Render cancel | present | live-tested | started real render task `3219ea4e`, cancel request accepted during `running`, final status became `cancelled`, partial output cleaned up successfully | SSE cancel/progress observe in UI |
| Output validation | present | live-tested | real output file produced and ffprobe-validated | manual playback / richer clip test |

## 8. GPU / DirectML / Models

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| GPU availability | present | live-tested | backend reports GPU available | none |
| GPU runtime stats | present | live-tested | SSE gpu status works | observe during jobs |
| VRAM management under load | partial | code-inspected | not stress-tested | stem/render stress test |
| Model loading robustness | partial | not-yet-verified | depends on task-specific models | test stems/video analyze |

## 9. Persistence / Data

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| DB startup load | present | live-tested | backend restored audio/video clips | none |
| Clip metadata persistence | partial | live-tested subset | import/analyze metadata visible | restart-consistency test |
| Project persistence | present | live-tested + fixed + build-verified + WPF-click-path-verified | save/load now durably persists `project.json` + `timeline.json`; create/open/save/close/reopen were all exercised from the real WPF shell | none |
| Vector store / embeddings | partial | code-inspected | not practically tested | vector path review |

## 10. QA / Delivery Confidence

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Build confidence | present | live-tested + publish-verified | WPF build clean and framework-dependent publish path now verified via `publish.ps1` | keep verifying after changes |
| Backend smoke confidence | present | live-tested | core import/analyze/video/render paths green | broaden coverage |
| Full E2E confidence | present | live-tested subset + scripted smoke + live-WPF-click-path-verified + post-fix settings verify + release-path-import/anchor-remove verify + 9-view-E2E-verified | focused end-to-end smoke coverage now exists and the real WPF shell now also proves startup, project workflow, asset loading, render completion, settings refresh, release-build Director, video path import, and anchor add/remove; environment was restored (dotnet 9, python 3.11) and all 9 views were verified interactive via automated UI test | expand remaining WPF edges |
| Release readiness | present | assessed + publish-verified + publish-smoke-verified + release-director-crash-fixed + release-reverify + packaging-hardened + telemetry-patched + dialog-hardening-verified + stress-test-verified (2026-04-25) | core create/import/analyze/director/render/settings flows now survive real published-artifact checks and framework publish is script-verified; native dialogs implemented; VRAM stability verified under load | release MVP |

---

## Current Priority Order
1. Decide and freeze MVP release scope versus future true player/timeline-edit scope
2. Optional native video-dialog hardening (non-blocking now that direct path import exists)
3. Optional broader UX polish after core verification

## Working Rules
- Before each work item: create a plan with needed tools.
- If necessary: research first, execute second.
- After each completed item: compress results into this file + WORKLOG.
- Preserve cross-session continuity through files, not chat memory.
