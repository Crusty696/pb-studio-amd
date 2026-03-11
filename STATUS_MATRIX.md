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
| App startup | present | live-tested | WPF app starts and stays running in smoke test | UI interaction check |
| Main/backend status integration | present | code-inspected + build-start-verified | MainViewModel waits for backend, updates status | UI path verification |
| Audio library UI wiring | present | code-inspected + live-tested (backend flow) | Import refresh bug fixed via messenger | WPF click-path verify |
| Video library UI wiring | partial | code-inspected + live-tested (backend flow) | Import/list flow works, thumbnail API verified; WPF visual path still unverified | Thumbnail/UI verify |
| Director UI wiring | partial | code-inspected + live-tested (backend pacing) | Generate path works through API | Multi-clip + UI verify |
| Timeline UI | present | live-tested contract + glue-fixed + build-verified | timeline contract verified live; WPF auto-refresh wiring exists and selected-cut inspection UI now makes review materially more useful | WPF click-path verify / future true timeline control |
| Production/Render UI | present | live-tested contract + glue-fixed + build-verified | render contract verified live; WPF now syncs audio path, handles render terminal states properly, and exposes a real bound render log instead of placeholder text | live click-path verify |
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
| Project routes | present | live-tested + fixed | `open/save/close/info` now practically verified; save/load was previously stub-like, now persists `project.json` + `timeline.json` and restores timeline/audio path on reopen | WPF save/open UI path verify |
| Schema / DTO alignment | partial | code-inspected + live-tested subset | key routes align | broaden verification |

## 3. Events / SSE / Runtime Bridge

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| GPU SSE | present | live-tested | `/events/gpu` returns `gpu_status` | long-run observe |
| Progress SSE | present | code-inspected + build-verified + live-tested backend path | WPF SSE client now actively listens to progress stream and understands backend status fields; backend render progress path already live-tested | WPF click-path observe during long job |
| Log SSE | partial | code-inspected + build-verified | WPF client now actively listens to `/events/log`; backend/UI wiring no longer dead code, but practical live log-stream proof is still pending | practical test |
| Reconnect behavior | partial | code-inspected + build-verified | reconnect/backoff logic now applies across progress/log/gpu listeners, but forced-disconnect behavior is still not practically exercised | forced reconnect test |

## 4. Audio

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Audio import | present | live-tested | passed | none |
| Audio library data flow | present | live-tested | clip list available | WPF UI path verify |
| Audio analysis | present | live-tested | BPM/key/beat count returned | longer file test |
| Waveform | present | live-tested + build-verified | backend 3-band waveform already verified; Anchor WPF view now renders a real waveform inspection surface instead of placeholder-only UI | live click-path verify |
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
| Timeline persistence / retrieval | partial | code-inspected | not tested live | timeline route test |
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
| Project persistence | present | live-tested + fixed | save/load now durably persists `project.json` + `timeline.json`; close→reopen restored timeline/audio path and project counts in live test | WPF save/open path verify |
| Vector store / embeddings | partial | code-inspected | not practically tested | vector path review |

## 10. QA / Delivery Confidence

| Area | Status | Verification | Notes | Next step |
|---|---|---|---|---|
| Build confidence | present | live-tested | WPF build clean | keep verifying after changes |
| Backend smoke confidence | present | live-tested | core import/analyze/video/render paths green | broaden coverage |
| Full E2E confidence | partial | live-tested subset | focused end-to-end smoke coverage now exists, but not full user-path coverage | expand focused E2E list |
| Release readiness | partial | assessed | major core flows work; config-alignment risk reduced and removed-PyQt area classified, but interactive WPF parity + cancel/stress/persistence coverage remain open | close red/yellow items |

---

## Current Priority Order
1. Optional real-world video-analysis validation with richer external/local clip
2. Optional multi-model / richer-audio stem validation
3. SSE progress/log/reconnect practical verification
4. WPF click-path verification for Timeline / Production / Anchor
5. True timeline/player control rebuild planning

## Working Rules
- Before each work item: create a plan with needed tools.
- If necessary: research first, execute second.
- After each completed item: compress results into this file + WORKLOG.
- Preserve cross-session continuity through files, not chat memory.
