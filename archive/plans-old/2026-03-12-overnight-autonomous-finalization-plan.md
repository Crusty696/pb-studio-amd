# PB Studio AMD – Overnight Autonomous Finalization Plan

Date: 2026-03-12
Window: ~8 hours
Mode: autonomous
Owner: Sputim + parallel specialist team

## Mission
Drive PB Studio from the current ~85–90% technical product-readiness level toward a genuinely finishable, repeatedly verified state.

## Non-negotiable success rule
A capability/workstream only counts as "successfully finished" when it completes **3 bug-free verification passes** after the latest relevant fix.

## Work principles
- Fix only what is real and evidenced.
- Prefer minimal targeted fixes over broad rewrites.
- Keep product shell, backend bridge, Python core, and persistence aligned.
- Every fix must be followed by verification.
- If a verification fails, re-enter fix/test loop until green or until the blocker is proven external.

## Streams

### Stream 1 — Integration lead
Goal:
- integrate current uncommitted improvements into one technically coherent tree
- remove compile blockers and cross-file drift
- decide what is commit-worthy vs. local/tmp noise

### Stream 2 — GUI user testing / WPF foreground
Goal:
- test the real visible app like a user
- verify startup, project open/save/close/reopen, timeline, anchors, production
- prove what is actually clickable/usable vs. only buildable

### Stream 3 — Backend/API/contracts/data
Goal:
- finish remaining backend correctness issues
- close state leaks / persistence inconsistencies / invalid success paths
- harden render/timeline/project route semantics

### Stream 4 — Release / verification gate
Goal:
- keep Debug/Release build green
- keep publish path green
- keep release smoke green
- improve determinism of verifier scripts

### Stream 5 — Runtime / polish / startup-noise
Goal:
- reduce duplicate loads, shutdown noise, reconnect churn, thumbnail storms
- preserve responsiveness while avoiding destabilizing refactors

## Phases

### Phase A — Stabilize the working tree
1. Eliminate compile/syntax blockers.
2. Re-run Debug and Release builds.
3. Re-run targeted backend compile checks.
4. Re-run project persistence tests.

### Phase B — Deep fix/test loop per feature area
For each area:
1. Verify current behavior.
2. Identify defect / weakness.
3. Apply minimal fix.
4. Re-test immediately.
5. Repeat until 3 clean passes or proven external blocker.

Areas:
- project workflow
- audio import/library/analysis/waveform/beats/stems
- video import/library/thumbnails/analyze/scenes/motion
- pacing/director/timeline
- production/render/start/progress/cancel
- startup/shutdown/reconnect/runtime noise
- publish/launch/release smoke

### Phase C — Full acceptance pass
Required gate set:
- Debug build
- Release build
- publish
- release smoke
- key pytest suites
- persistence regression tests
- GUI user-path proof where technically possible

### Phase D — Commit hygiene and final integration
- exclude local/tmp artifacts
- keep technical changes grouped logically
- only commit when the tree is technically green and verification evidence is explicit

## Success definition
The overnight run is considered successful if:
- the tree is technically integrated and buildable
- release smoke passes reliably
- major user workflows are verified
- remaining blockers are reduced to explicitly named non-trivial architecture/polish items
- at least the most critical paths have achieved 3 bug-free verification passes after their last fix

## Known likely hard blockers
- multi-project media persistence semantics
- final GUI automation depth on custom WPF controls
- residual thumbnail/noise polish
- final packaging mode decision (framework/selfcontained/singlefile)
