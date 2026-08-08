# Release Gate Remediation

## Context

The OBJ-72 pre-merge audit on 2026-08-08 found runtime defects and four
failing required CI gates on PR #22. Merging remains blocked until each defect
has a regression test and the same commit passes the local and remote gates.

## Objective

**OBJ-73:** Make the current release candidate truthful under live operation,
clean Windows CI and protected-`main` publication without weakening AMD,
security or quality contracts.

**Task range:** T001-T009.

## Functional Requirements

- **FR-354:** Fresh audio-analysis results expose beats immediately from RAM;
  SSE completion events remain replayable after a client disconnect.
- **FR-355:** RAFT reserves and commits VRAM before reporting a loaded session;
  preview rendering shares the central GPU lock and reports failures truthfully.
- **FR-356:** Anchor loads and writes are project-generation-bound and ordered;
  rating actions accept at most one write per displayed cut.
- **FR-357:** Learning playback seeks audio and video to the displayed cut and
  stops at its end.
- **FR-358:** Security negative fixtures prove rejection without appearing as
  vulnerable production dependencies.
- **FR-359:** Structure-aware stem generation reaches the pacing engine with
  the requested option unchanged.

## Test Requirements

- **TR-356:** Targeted Python tests reproduce and close the beat-cache, SSE
  replay, RAFT reservation, preview-lock and structure-awareness defects.
- **TR-357:** Native WPF tests reproduce and close anchor ordering/switch,
  single-rating and cut-range playback defects.
- **TR-358:** The Python quality gate is hardware-independent for unit tests,
  leaves no repository cache, and passes from a clean checkout.
- **TR-359:** SDD, Python quality, Python SCA and dependency review pass on the
  same PR commit without allowlisting a known vulnerable dependency.
- **TR-360:** Full Python, native C#, WPF Release and immutable SDD validation
  pass before merge.

## Operational Requirements

- **OR-338:** No CUDA, ROCm, NVENC, software encoder, unlocked dependency or
  production-data migration is introduced.
- **OR-339:** Only semantically current work is integrated; stale remote branch
  commits are not merged wholesale.
- **OR-340:** `main` becomes the default protected branch with the required
  successful checks before the release PR is merged.

## Out of Scope

- Medium and low audit findings without demonstrated release-blocking impact.
- Performance tuning, schema migration, new dependencies and UI redesign.
- Deleting or renaming historical scratch evidence.

## Success Criteria

- **SC-084:** All targeted regressions pass and no HIGH finding remains open.
- **SC-085:** Full local release verification passes with zero failures.
- **SC-086:** PR #22 required checks are green and the protected `main` SHA is
  the verified merge result.
