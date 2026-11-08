# Specification: PB Studio Full Audit Remediation

## Objective

**OBJ-1:** Repair and verify the audited PB Studio workflows with truthful results and no user-data loss.

Resolve/disposition all 54 findings in `test-report/specialist-audit-2026-09-27.md`; prove import→analysis→music-led pacing→audible preview→export→reopen. Finding 54 (withdrawn semantic bypass) is documented, not changed.

## User Stories

### US1 — Trustworthy analysis and AI (P1)
As an editor, I need truthful model/audio/video status, source, coverage, retry, and partial-failure reporting.

### US2 — Music-led coherent edit (P1)
As an editor, I need music-led cuts and bounded visual-theme continuity without false beat provenance.

### US3 — Audible preview and dependable export (P1)
As an editor, I need safe, audible, synchronized preview and correctly validated, observable, recoverable export.

### US4 — Isolated, durable project state (P1)
As an editor, I need project/chat/recovery/GPU/events scoped and recoverable across retry, cancel, reconnect, and project switch.

## Functional Requirements

- **FR-429:** Map findings 1–54 to fix, test, or explicit conditional/withdrawn disposition; do not omit duplicates.
- **FR-430:** `completed` requires valid evidence/coverage; preserve partials, expose failures/unavailable, retry after recovery.
- **FR-431:** Empty replies, probe failures, tool support, selection/errors stay explicit; no fabricated success/capability.
- **FR-432:** Identify feature sources and valid timebase; expose long-file tails and capped/skipped windows. Long-stream structure shall consume time-aligned mix features (energy plus normalized chroma/spectral change where available), report feature coverage, and use neutral labels when evidence cannot justify musical semantics.
- **FR-433:** Cut times follow validated triggers. Rank: eligibility, music, visual/semantic/motion, bounded theme, diversity. Source-repeat boundaries are not musical triggers.
- **FR-434:** WPF-safe path, synced master audio, measured duration; selection/seeking preserve render state and map timeline offset to source time.
- **FR-435:** Consistent rational-FPS accounting; reject source/output collision; retain render and validation evidence incrementally while work runs; report validation progress/status; fix 2-frame defect without weakening validation.
- **FR-436:** Reconcile SSE gaps/restarts/overflow/cancel/reconnect; wire render-status path. Never release GPU lock while worker runs.
- **FR-437:** Guard UI by project generation; refresh changed-media hash/metadata; align counters; inaccessible roots are not deleted.
- **FR-438:** Failed-stage defaults are not evidence; count valid nonzero pairs; annotations use media time, not timeline time.
- **FR-439:** Keep existing requests compatible; additive response/status/provenance only. No schema migration or new dependency.
- **FR-440:** Final AAC artifacts must satisfy the configured true-peak ceiling after encoding; preserve fail-closed artifact validation and prove the production audio filter on encoded audio.
- **FR-441:** Persist a redacted ordered segment manifest per render and bind its receipt to that exact manifest.

## Technical Requirements

- **TR-391:** Every active finding gets a focused RED→GREEN regression; conditional findings get both paths.
- **TR-395:** Time-aligned streaming-structure evidence survives chunk aggregation and checkpoint resume with matched timestamps, bounded memory, source provenance, and explicit incomplete-feature behavior.
- **TR-396:** FFmpeg machine-progress evidence is flushed to the run-scoped evidence file as blocks arrive, so interruption does not erase already-received progress; final evidence remains complete and compatible.
- **TR-397:** Exercise the production AAC filter and post-encode true-peak meter against deterministic transient-rich audio; no mocked measurement may substitute for this regression.
- **TR-398:** Run-scoped manifest records order, source-path SHA-256, source/timeline ranges; no raw paths or media. Create atomically; add manifest/canonical-timeline SHA-256 to `result.json`; retain across render failure.
- **TR-392:** Run Python, C#, WPF Release, DirectML/AMF gates; record exact results.
- **TR-393:** Reuse existing QA project/media; verify progress, music-timed cuts, narrative, audible preview, full decode, and reopen in one real run.
- **TR-394:** GUI acceptance waits for PB Studio handover. Never delete existing project/media/log/test artifacts.

## Operational Requirements

- **OR-364:** Preserve DirectML/both ONNX flags, Python 3.11/NumPy 1.26.4, AMF, Windows paths, `PYTHONPATH=src`, `Tests/` casing.
- **OR-365:** Do not edit locked separator, add dependencies, migrate DB/FAISS, or change locked versions.
- **OR-366:** Preserve user changes. No commit/push/merge/install or destructive cleanup.
- **OR-367:** Parallelize disjoint zones; serialize shared state and cross-zone integration.

## Success Criteria

- **SC-116:** Traceability matrix covers all 54 entries, duplicates, conditional cases, and withdrawn 54.
- **SC-117:** Regressions fix active defects or rule out conditional risks; mocks alone do not satisfy media acceptance.
- **SC-118:** Automated gates pass with evidence and no unresolved Critical/High active finding.
- **SC-119:** Real-media API passes; GUI passes after handover. Otherwise release acceptance stays pending.
- **SC-120:** No release-ready claim before automated and applicable live acceptance pass.
- **SC-121:** A real or deterministic encoded AAC artifact at/under the true-peak ceiling passes; an over-limit artifact remains rejected.
- **SC-122:** Tests prove path redaction, ordered time mapping, hash binding, pre-encode persistence, and no-overwrite.

**Task range:** T001–T017 (T012 is final implementation marker gate).

## Out of Scope

- Finding 54 product changes (withdrawn; retain a regression/decision record only).
- Cloud inference, CUDA/ROCm, CPU neural fallback, new dependencies, model downloads, database/FAISS migration, broad redesign, and cleanup of pre-existing user data.

## Finding Traceability (54 numbered list entries)

| # | Audit finding | Requirement / disposition |
|---:|---|---|
| 1 | Render 98,982/98,984 frames; staging removed | FR-435 |
| 2 | Long evidence-record timestamp gap | FR-435 |
| 3 | Preview artifact path and missing audio | FR-434 |
| 4 | Model timeout/cooldown and empty batch results | FR-430, FR-431 |
| 5 | Mocked tests do not prove full media workflow | TR-392, TR-393 |
| 6 | Partial frame tags accepted as completed | FR-430 |
| 7 | Cooldown/tag counts do not prove provider recovery | FR-430, FR-431 |
| 8 | Unavailable model stage blocks ordinary retry but reports completed | FR-430 |
| 9 | Probe failure conflated with no audio track | FR-430, FR-432 |
| 10 | Resume skips vector-link/tombstone validation | FR-430 |
| 11 | UI hides successful scenes on aggregate failure | FR-430 |
| 12 | Stale batch errors survive later stage responses | FR-430 |
| 13 | Empty model smoke response fabricated as success | FR-431 |
| 14 | Capability probe failure misstates installed model usability | FR-431 |
| 15 | Tool-use activation lacks tool capability proof | FR-431 |
| 16 | Positive caption counts do not prove content accuracy | TR-393 |
| 17 | Relative preview path rejected by WPF | FR-434 |
| 18 | Preview omits master audio | FR-434 |
| 19 | Preview reports target not artifact duration | FR-434 |
| 20 | Timeline selection interrupts rendered preview | FR-434 |
| 21 | Scrubbing ignores timeline-to-source offset | FR-434 |
| 22 | Cancel SSE may be throttled and lost | FR-436 |
| 23 | Replay-gap announcement does not reconcile state | FR-436 |
| 24 | SSE cursor invalid after backend restart | FR-436 |
| 25 | Queue overflow drops events without a gap marker | FR-436 |
| 26 | FPS normalization and frame validation disagree | FR-435 |
| 27 | Render source/output identity collision possible | FR-435 |
| 28 | Validation has no visible progress | FR-435 |
| 29 | Render status poll API has no UI caller | FR-436 |
| 30 | Drums-derived features may be mistaken for mix features | FR-432 |
| 31 | Key can use incomplete streaming chroma | FR-432 |
| 32 | Beatgrid suspect status can be lost | FR-432 |
| 33 | Long-file segment grid omits tail/capped coverage | FR-432 |
| 34 | Long-mix structure uses coarse fixed-minute heuristic | FR-432 |
| 35 | Motion normalization has a discontinuity | FR-433 |
| 36 | BPM correction fails to remap beat strengths | FR-433 |
| 37 | Theme bonus can dominate music/motion match | FR-433 |
| 38 | Short render uses wrong energy-curve timebase | FR-433 |
| 39 | Repeated short clips inherit false beat provenance | FR-433 |
| 40 | Stale project response can overwrite new project UI | FR-437 |
| 41 | Same-path changed media can reuse stale metadata | FR-437 |
| 42 | Project counters use inconsistent sources | FR-437 |
| 43 | Recovery catalog may skip temporarily inaccessible root | FR-437 |
| 44 | Valid `error:null` chat response appears as error | FR-431 |
| 45 | Chat render blocks video-only request | FR-431 |
| 46 | Stale clear-history response can clear another project view | FR-437 |
| 47 | Failed analysis defaults can be accepted by Brain learning | FR-438 |
| 48 | Invalid training pairs can be acknowledged as applied | FR-438 |
| 49 | Brain annotation confuses timeline time with media time | FR-438 |
| 50 | GPU lock wait escapes some worker deadlines | FR-436 |
| 51 | VRAM reservation may evict before safe lock acquisition | FR-436 |
| 52 | Empty timeline persistence may retain old timeline file; UI path uncertain | FR-437; prove/reproduce or close with explicit non-reachability evidence |
| 53 | String/integer ID inconsistency in preflight | FR-433; normalize or prove normal-path exclusion |
| 54 | Semantic bypass claim withdrawn | Explicit no-product-fix disposition; preserve evidence |
