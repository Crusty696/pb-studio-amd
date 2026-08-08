# Plan — OBJ-73 Release Gate Remediation

## Clarifications

- The user's merge request authorizes PR publication and merge, but not a
  force-push, deletion, migration or dependency change.
- Existing remote topic branches are evidence sources only. Their historical
  commits are integrated only when current code and tests prove the behavior
  is still missing.
- Confirmed HIGH runtime defects and failing required checks are release
  blockers. Medium/low audit findings are logged for later work.

## Implementation Strategy

1. Correct the in-memory beat key, SSE journal ordering, RAFT reservation,
   preview GPU serialization/truth and structure-option forwarding with focused
   Python regressions.
2. Serialize/project-bind anchor operations, gate ratings per cut and enforce
   learning playback seek/end behavior with native WPF tests.
3. Repair CI mechanics without weakening gates: LF-stable SDD inputs,
   repository-clean pytest execution, successful negative-fixture exit status,
   and an ephemeral vulnerable NuGet fixture.
4. Make unit tests independent of AMD hardware and external media/model assets;
   retain explicitly marked hardware/integration coverage for real gates.
5. Run targeted tests, full Python, native C#, WPF Release, SDD validation and
   three clean quality-gate runs. Record exact receipts.
6. Push the release branch, require green PR checks, configure protected
   `main`, merge PR #22, then verify and synchronize Brain/SDD truth.

## Code Zones

| Zone | Allowed files |
|---|---|
| Z-DATA-SHARED | `backend/app_state.py`, beat-cache regression tests |
| Z-BACKEND | `backend/dependencies.py`, `backend/routers/pacing_router.py`, `src/pb_studio/video/raft.py`, `src/pb_studio/rendering/preview_renderer.py`, `src/pb_studio/services/pacing_service.py`, `src/pb_studio/pacing/advanced_pacing_engine.py`, related tests |
| Z-UI | `PBStudio.UI/ViewModels/AnchorViewModel.cs`, `LearningSessionViewModel.cs`, `BrainViewModel.cs`, `PBStudio.UI/Views/LearningSessionDialog.xaml*`, native tests |
| Z-INFRA | `.gitattributes`, `.github/workflows/*.yml`, `scripts/run_python_quality_gate.ps1`, `config/pytest-skip-allowlist.json`, security fixtures and CI-contract tests |
| Z-DOCS | `specs/00018-release-gate-remediation/**`, Brain project log/index, `CLAUDE.md` |

`backend/app_state.py`, workflow files, Brain files and SDD artifacts remain
sequential parent-owned files. Agents must not touch them outside an explicit
zone assignment.

## Verification Gates

- Python 3.11 and NumPy 1.26.4 identity check.
- Focused regressions for every confirmed HIGH defect.
- Full `pytest Tests/ -q` with `PYTHONPATH=src`.
- Locked native C# tests and WPF Release build with zero errors/warnings.
- Immutable SDD validator for OBJ-72 and structural phase-gate validation for
  the independent OBJ-73 workspace.
- Security workflow syntax and negative-fixture contract tests.
- PR required checks green on one commit; protected `main` points to its merge.

## Rollback

All changes are ordinary Git commits on the release branch. No schema or data
migration is permitted. A failing gate stops publication; no force-push or
direct unverified `main` update is used.
