# 54-Point Traceability — OBJ-1

`OPEN` means fix and acceptance evidence are pending. `FIXED + REGRESSION` means a focused automated regression now proves the reported defect is corrected; broader live workflow acceptance remains separate.

| # | Finding | Task / requirement | Status |
|---:|---|---|---|
| 1 | 98,982/98,984-frame export failure; staging removed | T008 / FR-435 | FIXED + REGRESSION + LIVE SHORT/60-s EXPORTS + LIVE RATIONAL-FPS AMF EXPORT (180/180); original 54:59 media unavailable |
| 2 | 437.861-second evidence-record gap | T008 / FR-435 | OPEN |
| 3 | Preview path/audio contract failure | T007 / FR-434 | FIXED + ROUTE REGRESSION + LIVE 3-s H.264/AAC PREVIEW; GUI audition pending |
| 4 | Provider timeout/cooldown produces empty batch results | T005,T002 / FR-430,FR-431 | FIXED + RED/GREEN ROUTER REGRESSION: stop repeated provider probes after exhausted receipt, mark captions unavailable when no fallback exists; live recovery/batch acceptance pending |
| 5 | Mocked render tests are not full-workflow proof | QC,T014 / TR-392,TR-393 | OPEN |
| 6 | Incomplete frame captions can report completed | T002 / FR-430 | FIXED + SEEK/READ + STAGE-MERGE REGRESSIONS; semantic accuracy pending |
| 7 | Cooldown tag counts do not prove provider recovery or caption accuracy | T002,T005,T014 / FR-430,FR-431 | MOCKED RECOVERY + OUTAGE/RECOVERY ROUTER REGRESSIONS; live provider recovery and semantic accuracy pending |
| 8 | Unavailable model stage can report completed and block retry | T002 / FR-430 | FIXED + PERSISTED-RESUME REGRESSION: unavailable remains non-success and ordinary requested retry runs; live model recovery pending |
| 9 | Probe failure conflated with missing audio track | T002 / FR-430 | FIXED + NO-STREAM/PROBE-ERROR/SUCCESS STAGE REGRESSION; real encoded-media probe pending |
| 10 | Resume may skip vector-link/tombstone validation | T002 / FR-430 | FIXED + RED/GREEN RESUME REGRESSION: metadata alone cannot reuse embedding; requires live vector_map link, non-tombstoned in-range nonnegative FAISS ID, exact media path and content hash. Full user-project vector recovery remains pending |
| 11 | UI can hide successful scenes on aggregate failure | T002 / FR-430 | FIXED + NATIVE VIEWMODEL REGRESSION: scene stage remains visible after later motion failure; GUI visual acceptance pending |
| 12 | Old batch error can override later valid stage response | T002 / FR-430 | FIXED + NATIVE MULTI-PASS RECOVERY REGRESSION: lost scene response followed by complete server response clears stale request failure; GUI/network-loss live acceptance pending |
| 13 | Empty model smoke output fabricated as success | T005 / FR-431 | FIXED + ROUTE-LEVEL REGRESSION: empty provider response returns `success=false`, empty response field, and explicit error; no synthetic success text |
| 14 | Capability probe failure misstates model usability | T005 / FR-431 | FIXED + REGRESSION: installed remains true, unverified capability keeps usable=false, and user-facing status reason includes probe failure/cause |
| 15 | Tool-use activation lacks tool-capability proof | T005 / FR-431 | FIXED + ACTIVATION API REGRESSION: chat-only model rejected without config mutation; tool_calls-capable model accepted and persisted only for chat_tool_use |
| 16 | Positive caption counts do not prove semantic correctness | T014 / TR-393 | OPEN |
| 17 | Relative preview path rejected by WPF | T007 / FR-434 | FIXED + ROUTE ARTIFACT REGRESSION: relative renderer result resolves to absolute existing local file path; live WPF playback remains pending |
| 18 | Preview omits master audio | T007 / FR-434 | ROUTER REGRESSION + LIVE AMF ARTIFACT: registered master path reaches preview mux; real 3-s preview contains decodable AAC stereo aligned to 3.000-s H.264 video. GUI listening/playback acceptance pending |
| 19 | Preview reports target, not artifact duration | T007 / FR-434 | FIXED + ROUTE/ARTIFACT REGRESSION: renderer-measured 2.4 s is returned even when request target is 2.75 s; live preview ffprobe reports actual stream durations |
| 20 | Timeline selection can interrupt rendered preview | T007 / FR-434 | FIXED + RANGE REGRESSION: retain rendered preview for selections within its timeline window; selections outside switch to selected source clip; GUI playback acceptance pending |
| 21 | Scrubbing ignores timeline-to-source offset | T007 / FR-434 | FIXED + NATIVE REGRESSION: timeline delta maps to source offset and rendered-preview time; WPF GUI playback/scrub acceptance pending |
| 22 | Render cancel SSE can be throttled/lost | T010 / FR-436 | FIXED + REGRESSION; live SSE pending |
| 23 | Replay-gap message does not reconcile state | T010 / FR-436 | FIXED + NATIVE SSE→VIEWMODEL REGRESSION: lost-event marker fetches authoritative render status, applies completion/output evidence, and ignores late response after task switch; backend replay-gap tests pass |
| 24 | SSE cursor can be stale after backend restart | T010 / FR-436 | VERIFIED EXISTING SEQUENCE BOOTSTRAP + FRESH-PROCESS ROUTER REGRESSION: new backend process emits and replays event with ID greater than previous process cursor |
| 25 | Queue overflow drops event without gap signal | T010 / FR-436 | VERIFIED EXISTING IMPLEMENTATION + LIVE-QUEUE REGRESSION: bounded queue records dropped sequence range and emits `replay_gap` before next accepted progress event |
| 26 | FPS normalization and frame validation differ | T008 / FR-435 | VERIFIED REGRESSION + LIVE 30000/1001 AMF EXPORT: 6-s clip produced/decoded 180/180 frames; ffprobe r_frame_rate=avg_frame_rate=30000/1001 |
| 27 | Render source/output identity collision possible | T008 / FR-435 | FIXED + ROUTER REGRESSION: exact source path and distinct hardlink alias rejected before queue enqueue; canonical path plus inode identity checked |
| 28 | Validation progress is not visible | T008 / FR-435 | FIXED + SERVICE→SSE→VIEWMODEL REGRESSION: named validation phases emitted and bypass 100-ms progress throttle; visible `ValidationText` receives phase/percent; interactive GUI observation pending |
| 29 | Render-status poll has no UI caller | T010 / FR-436 | VERIFIED + NATIVE UI-RECOVERY REGRESSION: ProductionViewModel calls render-status API after replay-gap and applies authoritative progress/completion |
| 30 | Drums-derived features can stand in for mix features | T003 / FR-432 | LIVE ORIGINAL-MIX ANALYSIS: existing 30-s WAV produced 2,584 spectral frames/10 bands and F minor; spectral/key provenance both `original_mix`, 100%/30-s coverage; mocked stem-separation comparison remains pending because no real stem fixture exists |
| 31 | Key may use incomplete streaming chroma | T003 / FR-432 | FIXED + ROUTER REGRESSION; real-media key accuracy pending |
| 32 | Beat-grid suspect status may be dropped | T003 / FR-432 | ROUTER + GENERATED DTO + ANALYSIS-COMMAND VIEWMODEL REGRESSIONS; live GUI presentation pending |
| 33 | Long-file beat-grid may omit tail/capped coverage | T003 / FR-432 | FIXED + REGRESSIONS: full tail, sub-5-second tail and window cap; real long-media coverage pending |
| 34 | Long-mix structure uses coarse fixed-minute heuristic | T003 / FR-432 | FIXED + 35-TEST STREAMING/SUBTRACK REGRESSION SET: boundaries follow observed energy transitions rather than fixed minute marks; confidence derives from measured boundary evidence; no unsupported verse/drop semantics are claimed from energy-only stream. Full semantic sections remain intentionally limited to available evidence. |
| 35 | Motion normalization discontinuity | T006 / FR-433 | FIXED + LINEAR/BOUNDED REGRESSION; real-media ranking pending |
| 36 | BPM correction does not remap beat strengths | T006 / FR-433 | FIXED + FULL VECTOR MAPPING REGRESSION; real pacing acceptance pending |
| 37 | Theme bonus can dominate music/motion ranking | T006 / FR-433 | STRONG-MATCH + NEAR-TIE REGRESSIONS; real-media ranking pending |
| 38 | Short render uses wrong energy-curve timebase | T006 / FR-433 | FIXED + 32s OUTPUT / 64s SOURCE REGRESSION; real pacing acceptance pending |
| 39 | Repeated short clip inherits false beat provenance | T006 / FR-433 | FIXED + 3s SOURCE / 8s INTERVAL REGRESSION; real timeline acceptance pending |
| 40 | Stale project response can overwrite new project UI | T009 / FR-437 | VERIFIED + NATIVE DELAYED-SAVE/PROJECT-SWITCH TEST: late project-A info response rejected after project B opens; current service state stays B |
| 41 | Changed media at same path can reuse stale metadata | T009 / FR-437 | FIXED + RESTARTED-STATE AUDIO/VIDEO REGRESSIONS: fresh hash/probe fields overwrite persisted path row; changed content clears analysis payload/status and in-memory analysis cache; same-hash audio retains stems |
| 42 | Project counters read different sources | T009 / FR-437 | FIXED + REGRESSION: open/info counters match loaded media catalog, not folder files; GUI pending |
| 43 | Recovery discovery may skip temporarily inaccessible root | T009 / FR-437 | FIXED + PERMISSION-ERROR REGRESSION: inaccessible registered root is reported as inaccessible, not deleted; live ACL pending |
| 44 | Valid `error:null` chat response presented as error | T005 / FR-431 | FIXED + CHAT-AGENT REGRESSION: successful tool result retains `error:null` without emitting tool-dispatch error event |
| 45 | Chat render rejects valid video-only request | T005 / FR-431 | FIXED + TOOL-ROUTE REGRESSION: `include_audio=false` with omitted audio path reaches render endpoint with empty audio path and unchanged video-only flag |
| 46 | Stale clear-history response can clear other project view | T005 / FR-437 | FIXED + NATIVE WPF VIEWMODEL RACE TEST: delayed clear response after switching projects preserves newly loaded project history |
| 47 | Failed-stage defaults can be used by Brain learning | T004 / FR-438 | FIXED + STAGE-SPECIFIC RED/GREEN: failed beats/spectral/structure/motion/scenes/colors/captions gate features, curves, segments, and motion-pool scaling; completed stages stay eligible under aggregate `partial` |
| 48 | Invalid training pair can be acknowledged as applied | T004 / FR-438 | FIXED + ZERO/TINY-NORM AND FIT-REJECTION REGRESSIONS: trainer shares fit input validation and refuses publish when actual `n_pairs` differs from accepted events |
| 49 | Brain annotation uses timeline time instead of source time | T004 / FR-438 | VERIFIED + SOURCE-MEDIA-TIME REGRESSION: scene scoring and persisted provenance use `clip_start` (12 s) rather than timeline position (2 s) |
| 50 | GPU-lock wait may exceed job deadline | T010 / FR-436 | VERIFIED + DEADLINE REGRESSION: lock wait and worker execution share one deadline; timeout returns promptly while lock remains owned until physical worker completion; cancellation while queued starts no worker |
| 51 | VRAM reserve can evict before safe lock acquisition | T010 / FR-436 | VERIFIED + ORDERING/ACCOUNTING REGRESSIONS: reservation only follows GPU-lock acquisition; failed eviction preserves resident committed accounting; successful unload callback is accounted only after callback completion |
| 52 | Empty timeline may leave old file; productive UI path uncertain | T009 / FR-437 | VERIFIED SAFE DISPOSITION: close preserves prior timeline on uncertain empty RAM; explicit WPF Save command reaches `/project/save`, whose live API test deletes stale `timeline.json` and writes `has_timeline=false`; interactive click pending GUI handover |
| 53 | Pacing preflight string/integer ID inconsistency | T006 / FR-433 | FIXED + INTEGER REQUEST / STRING CACHE-KEY PREFLIGHT REGRESSION; worker-path acceptance pending |
| 54 | Semantic-bypass report was withdrawn | No product fix; retain disposition/test evidence | WITHDRAWN |

## Baseline and Preservation

- Initial dirty paths recorded in `.superpowers/sdd/plan/progress.md`; all retained.
- No baseline product tests/builds run by the initial audit. This plan will run regression tests per task and full verification after `.completed`.
- GUI is not handed over yet; GUI acceptance remains pending.
