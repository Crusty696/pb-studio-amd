# T306 Requirement Deduplication — 2026-07-29

## Result

- Status: CONFIRMED
- Existing finding ledger: 60 unique IDs, C-01–C-02, H-01–H-26, M-01–M-25, L-01–L-07.
- Existing requirement mapping: FR-251–FR-310.
- New work: T305–T339 registered once in `tasks.md`.
- Progress source: `repair-progress.md`.

## Deduplication decision

The 60 audit findings remain registered under OBJ-69 and are not duplicated. OBJ-70 adds only release-video repair, evidence, provenance, runtime, final-QC, and publication obligations discovered after the false 2026-07-28 release gate.

Overlap is retained as requirement linkage, not as a duplicate finding:

- T313 extends existing atomic-output FR-275 with per-job temp/resume/process isolation.
- T322 consumes existing DirectML and truthful-stage contracts while adding explicit semantic availability.
- T324 follows D04 and adds the approved backup/rehearsal/restore gate without changing production data in T306.
- T327 synchronizes public contracts after implementation; it does not redefine the domain requirements.

## Gate

- `spec.md` exists.
- `plan.md` exists.
- `tasks.md` now contains T305–T339.
- No checklist directory exists.
- `.completed` absent.
- `.qc-passed` absent.
- No function, regression, hardware, GUI, or E2E tests executed.
