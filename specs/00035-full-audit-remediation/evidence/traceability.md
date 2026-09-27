# 54-Point Traceability — OBJ-1

`OPEN` means fix and acceptance evidence are pending. `FIXED + REGRESSION` means a focused automated regression now proves the reported defect is corrected; broader live workflow acceptance remains separate.

| # | Finding | Task / requirement | Status |
|---:|---|---|---|
| 1 | 98,982/98,984-frame export failure; staging removed | T008 / FR-435 | FIXED + REGRESSION + LIVE SHORT EXPORT; original long-media incident pending |
| 2 | 437.861-second evidence-record gap | T008 / FR-435 | OPEN |
| 3 | Preview path/audio contract failure | T007 / FR-434 | OPEN |
| 4 | Provider timeout/cooldown produces empty batch results | T005,T002 / FR-430,FR-431 | OPEN |
| 5 | Mocked render tests are not full-workflow proof | QC,T014 / TR-392,TR-393 | OPEN |
| 6 | Incomplete frame captions can report completed | T002 / FR-430 | OPEN |
| 7 | Cooldown tag counts do not prove provider recovery or caption accuracy | T002,T005,T014 / FR-430,FR-431 | OPEN |
| 8 | Unavailable model stage can report completed and block retry | T002 / FR-430 | OPEN |
| 9 | Probe failure conflated with missing audio track | T002 / FR-430 | OPEN |
| 10 | Resume may skip vector-link/tombstone validation | T002 / FR-430 | OPEN |
| 11 | UI can hide successful scenes on aggregate failure | T002 / FR-430 | OPEN |
| 12 | Old batch error can override later valid stage response | T002 / FR-430 | OPEN |
| 13 | Empty model smoke output fabricated as success | T005 / FR-431 | OPEN |
| 14 | Capability probe failure misstates model usability | T005 / FR-431 | OPEN |
| 15 | Tool-use activation lacks tool-capability proof | T005 / FR-431 | OPEN |
| 16 | Positive caption counts do not prove semantic correctness | T014 / TR-393 | OPEN |
| 17 | Relative preview path rejected by WPF | T007 / FR-434 | OPEN |
| 18 | Preview omits master audio | T007 / FR-434 | OPEN |
| 19 | Preview reports target, not artifact duration | T007 / FR-434 | OPEN |
| 20 | Timeline selection can interrupt rendered preview | T007 / FR-434 | OPEN |
| 21 | Scrubbing ignores timeline-to-source offset | T007 / FR-434 | OPEN |
| 22 | Render cancel SSE can be throttled/lost | T010 / FR-436 | FIXED + REGRESSION; live SSE pending |
| 23 | Replay-gap message does not reconcile state | T010 / FR-436 | OPEN |
| 24 | SSE cursor can be stale after backend restart | T010 / FR-436 | OPEN |
| 25 | Queue overflow drops event without gap signal | T010 / FR-436 | OPEN |
| 26 | FPS normalization and frame validation differ | T008 / FR-435 | OPEN |
| 27 | Render source/output identity collision possible | T008 / FR-435 | OPEN |
| 28 | Validation progress is not visible | T008 / FR-435 | OPEN |
| 29 | Render-status poll has no UI caller | T010 / FR-436 | OPEN |
| 30 | Drums-derived features can stand in for mix features | T003 / FR-432 | OPEN |
| 31 | Key may use incomplete streaming chroma | T003 / FR-432 | OPEN |
| 32 | Beat-grid suspect status may be dropped | T003 / FR-432 | OPEN |
| 33 | Long-file beat-grid may omit tail/capped coverage | T003 / FR-432 | OPEN |
| 34 | Long-mix structure uses coarse fixed-minute heuristic | T003 / FR-432 | OPEN |
| 35 | Motion normalization discontinuity | T006 / FR-433 | OPEN |
| 36 | BPM correction does not remap beat strengths | T006 / FR-433 | OPEN |
| 37 | Theme bonus can dominate music/motion ranking | T006 / FR-433 | OPEN |
| 38 | Short render uses wrong energy-curve timebase | T006 / FR-433 | OPEN |
| 39 | Repeated short clip inherits false beat provenance | T006 / FR-433 | OPEN |
| 40 | Stale project response can overwrite new project UI | T009 / FR-437 | OPEN |
| 41 | Changed media at same path can reuse stale metadata | T009 / FR-437 | OPEN |
| 42 | Project counters read different sources | T009 / FR-437 | FIXED + REGRESSION; GUI pending |
| 43 | Recovery discovery may skip temporarily inaccessible root | T009 / FR-437 | FIXED + REGRESSION; live ACL pending |
| 44 | Valid `error:null` chat response presented as error | T005 / FR-431 | OPEN |
| 45 | Chat render rejects valid video-only request | T005 / FR-431 | OPEN |
| 46 | Stale clear-history response can clear other project view | T005 / FR-437 | OPEN |
| 47 | Failed-stage defaults can be used by Brain learning | T004 / FR-438 | OPEN |
| 48 | Invalid training pair can be acknowledged as applied | T004 / FR-438 | OPEN |
| 49 | Brain annotation uses timeline time instead of source time | T004 / FR-438 | OPEN |
| 50 | GPU-lock wait may exceed job deadline | T010 / FR-436 | OPEN |
| 51 | VRAM reserve can evict before safe lock acquisition | T010 / FR-436 | OPEN |
| 52 | Empty timeline may leave old file; productive UI path uncertain | T009 / FR-437 | OPEN |
| 53 | Pacing preflight string/integer ID inconsistency | T006 / FR-433 | OPEN |
| 54 | Semantic-bypass report was withdrawn | No product fix; retain disposition/test evidence | WITHDRAWN |

## Baseline and Preservation

- Initial dirty paths recorded in `.superpowers/sdd/plan/progress.md`; all retained.
- No baseline product tests/builds run by the initial audit. This plan will run regression tests per task and full verification after `.completed`.
- GUI is not handed over yet; GUI acceptance remains pending.
