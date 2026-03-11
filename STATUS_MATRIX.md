# PB Studio – Status Matrix

_Last updated: 2026-03-11 Europe/Zurich_

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
| App startup | present | live-tested + crash-fixed + publish-launch-verified | real WPF startup path verified via `dotnet run`; startup crash from read-only timeline bindings was fixed, and published frontend launch now also boots the backend correctly | broader click-path verify |
| Main/backend status integration | present | code-inspected + build-start-verified | MainViewModel waits for backend, updates status | UI path verification |
| Audio library UI wiring | present | code-inspected + live-tested (backend flow) | Import refresh bug fixed via messenger | WPF click-path verify |
| Video library UI wiring | present | build-start-verified + live-tested (backend flow) | import/list flow works; startup/load behavior hardened against overlapping refreshes and thumbnail churn via gating + cache | broader click-path verify |
| Director UI wiring | partial | code-inspected + live-tested (backend pacing) | Generate path works through API | Multi-clip + UI verify |
| Timeline UI | present | build-start-verified + live-tested contract + glue-fixed | timeline contract verified live; WPF now has selected-cut inspection plus scrubber and previous/next cut navigation for materially better review | broader click-path verify / future true timeline control |
| Production/Render UI | present | build-start-verified + live-tested contract + glue-fixed | render contract verified live; WPF now syncs audio path, handles render terminal states properly, exposes a real bound render log, and surfaces richer runtime/GPU feedback | live click-path verify |
| Settings UI | partial | code-inspected | Present, not validated | Settings smoke test |
| WPF parity vs old PyQt product UI | partial | code-inspected + build-verified | Removed PyQt area is explicitly classified in `PYQT_MIGRATION_CLASSIFICATION.md`; shell screens are largely replaced and Anchor now has real waveform + beat-marker inspection, but true timeline/player/scene-motion inspection still remain rebuild targets | prioritize next interactive timeline/player block |

## 2. Backend / API Bridge

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Health endpoint | present | live-tested | `/health` ok, GPU available true | none |
| Audio routes core | present | live-tested | import/list/analyze/waveform all passed | stems/structure/spectral deeper test |
| Video routes core | present | live-tested | import/list/analyze/thumbnail/scenes/motion all exercised live | broader quality / heavier-input test |
| Pacing generate | present | live-tested | generated 3 cuts in live smoke test | multi-input test |
| Render routes | partial | code-inspected | API exists, not yet live-tested | render smoke test |
| Project routes | present | live-tested + fixed + build-verified | `open/save/close/info` now practically verified; WPF shell now exposes real project lifecycle actions instead of backend-only capability | WPF click-path verify |
| Schema / DTO alignment | partial | code-inspected + live-tested subset | key routes align | broaden verification |

## 3. Events / SSE / Runtime Bridge

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| GPU SSE | present | live-tested | `/events/gpu` returns `gpu_status` | long-run observe |
| Progress SSE | present | code-inspected + build-verified + live-tested backend path | WPF SSE client now actively listens to progress stream and understands backend status fields; backend render progress path already live-tested | WPF click-path observe during long job |
| Log SSE | present | live-tested + build-verified | `/events/log` live endpoint verified; client/backend fanout logic hardened and keepalive path observed | WPF render-log click-path verify |
| Reconnect behavior | partial | code-inspected + live-tested keepalive + build-verified | reconnect/backoff logic applies across progress/log/gpu listeners; live keepalive behavior verified, but forced-disconnect recovery is still not practically exercised | forced reconnect test |

## 4. Audio

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Audio import | present | live-tested | passed | none |
| Audio library data flow | present | live-tested | clip list available | WPF UI path verify |
| Audio analysis | present | live-tested | BPM/key/beat count returned | longer file test |
| Waveform | present | build-start-verified + live-tested | backend 3-band waveform verified; Anchor WPF view renders a real waveform inspection surface and runtime loading was hardened against duplicate refresh races | broader click-path verify |
| Structure data | partial | code-inspected | endpoint exists, not tested live | structure test |
| Spectral data | partial | code-inspected | endpoint exists, not tested live | spectral test |
| Stem separation | present | live-tested + fixed | API now returns normalized usable stem paths; real vocal/instrumental files verified in `temp/` | optional multi-model / richer-audio test |

## 5. Video

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Video import | present | live-tested | passed | none |
| Video library data flow | present | live-tested | clip list available | WPF UI path verify |
| Thumbnail generation | present | live-tested | thumbnail endpoint returned valid JPEG (`ffd8`, 6203 bytes) | WPF display-path verify |
| Video analyze | present | live-tested | analysis completed successfully on smoke clip and richer render clip | optional real-world clip test |
| Scene data | partial | live-tested | endpoint works, but both tested local clips produced empty scene sets | test with stronger scene-cut source clip |
| Motion data | present | live-tested | motion data now non-zero on richer render clip (`avg_motion≈3.65`, `low`) | richer/high-motion clip test |
| Vision/tagging | partial | live-tested subset | embeddings work (`has_embedding=true`, dim 1152), but tested local clips still produced empty tags/colors | test with semantically richer clip |

## 6. Director / Timeline / Generation

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Basic pacing generate | present | live-tested | generated cuts successfully | quality/multi-input test |
| Timeline persistence / retrieval | present | live-tested + fixed | timeline state now persists and reloads via project save/open flow; active timeline retrieval route already exercised live | WPF click-path verify |
| Multi-clip selection logic | partial | code-inspected | UI supports it | multi-clip pacing test |
| Cut quality / semantic quality | partial | not-yet-verified | functional only, not judged | manual output review |

## 7. Render / Export

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Render start | present | live-tested | accepted real render task and returned task id; now also verified against active project root after `project/open` | cancel path test |
| Render progress | present | live-tested | status moved pending → running → completed | SSE render progress observe |
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
| Project persistence | present | live-tested + fixed + build-verified | save/load now durably persists `project.json` + `timeline.json`; WPF shell has save/open/close actions wired, but full click-path proof is still pending | WPF click-path verify |
| Vector store / embeddings | partial | code-inspected | not practically tested | vector path review |

## 10. QA / Delivery Confidence

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Build confidence | present | live-tested + publish-verified | WPF build clean and framework-dependent publish path now verified via `publish.ps1` | keep verifying after changes |
| Backend smoke confidence | present | live-tested | core import/analyze/video/render paths green | broaden coverage |
| Full E2E confidence | partial | live-tested subset + scripted smoke | focused end-to-end smoke coverage now exists and `verify_release_smoke.ps1` encodes a repeatable project/analyze/timeline/save/render-cancel flow | expand focused WPF/UI path coverage |
| Release readiness | partial | assessed + build-start-verified + publish-smoke-verified + publish-launch-fixed | major core flows work; project shell, startup, SSE, timeline and anchor runtime are materially stronger, publish + scripted release smoke exist, and published frontend launch now boots the backend correctly, but full WPF click-path proof and final packaging choice are still open | close remaining click-path/publish gaps |

---

## Current Priority Order
1. Practical WPF project workflow verification (open/save/close/reopen) + click-path smoke
2. WPF click-path verification for Timeline / Production / Anchor
3. Render-progress / cancel UI proof from integrated WPF shell
4. Final packaging/deployment choice for release artifact
5. True timeline/player control rebuild planning

## Working Rules
- Before each work item: create a plan with needed tools.
- If necessary: research first, execute second.
- After each completed item: compress results into this file + WORKLOG.
- Preserve cross-session continuity through files, not chat memory.
