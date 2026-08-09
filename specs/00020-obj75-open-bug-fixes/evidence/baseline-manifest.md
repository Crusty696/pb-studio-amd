# OBJ-75 Baseline-Manifest

**Captured:** 2026-08-09T07:24:02+02:00

**Purpose:** Historical pre-implementation receipt after Consulting-Team
correction. These digests describe the state at 07:24 CEST and are not claimed
as final post-implementation digests.

## Git state

- HEAD: `f8e1ad67750f3f2490e6ca5a09f5eff54093b847`
- `git status --porcelain=v2 --untracked-files=all` SHA-256:
  `ACFD43BD28C4AA99BE0F57DD7FE5BA5F2F10DEBD8BBE655D1A1CB8DD30E59BF9`
- `git diff --binary --no-ext-diff` text SHA-256:
  `606386E63B0F643F135246702367AB694833B93000988CDE60D75773AFF75E45`
- Status entries: 88
- Tracked changed files: 72
- Worktree is dirty; no existing user or agent change may be discarded.

## Canonical artifact hashes

| Artifact | SHA-256 |
|---|---|
| `spec.md` | `575572725955F05A71DDD52F8F8276185C5DC3779566650C25A50BB28599C999` |
| `plan.md` | `F30528F2B2326563AC07CC50E9FDB5A88A5DB9BABD5D270F72CABE626EF1B83B` |
| `tasks.md` | `6F02735E597BBE5F28C6EC178B927BCC87CE2020D8D0346CC61B3EE61EA870F6` |
| `residual-remediation-plan.md` | `2CD85A95E60C9EB800FF503887777F2779A018F06FA75EA5E16A2D26682B018E` |
| `FULLSTACK_DOUBLE_AUDIT_PB_STUDIO_2026-08-09.md` | `30325374AF786FFAC2EEC9D42E3781DF68D976E7AD04EDEA9CE279A7DFB18F70` |

## Post-audit drift requiring T049

These files changed after the corrected plan was first written. Previous Round-2
PASS statements do not cover their current content.

| File | Last write (local) |
|---|---|
| `backend/routers/video_router.py` | 2026-08-09 06:43:36 |
| `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs` | 2026-08-09 06:43:43 |
| `src/pb_studio/video/lmstudio_vision_wrapper.py` | 2026-08-09 06:43:50 |
| `PBStudio.UI/Views/VideoLibraryView.xaml` | 2026-08-09 06:44:19 |
| `PBStudio.UI/Views/VideoLibraryView.xaml.cs` | 2026-08-09 06:44:39 |

## Historical gate result

This preflight receipt authorized attribution before product writes. The
subsequent implementation deliberately changed the worktree. Final attribution
uses the separate convergence digest below and must be refreshed only if the
remaining T049 live smoke changes files.

## Final post-implementation convergence digest

**Captured:** 2026-08-09 after product/test convergence and green T049 live run.

- HEAD: `f8e1ad67750f3f2490e6ca5a09f5eff54093b847`
- Scoped Porcelain-v2 entries: **111**; SHA-256
  `c5b4fde69fe707b5a50146be18b660d7f5b3753cfe6d842a6a07615fdeab40f1`.
- Scoped binary diff SHA-256:
  `4f5b02caf248946b952c31e10f0265071e81fe58011a5c12ed4a494aa39464e7`.
- File-manifest entries: **111**; aggregate SHA-256
  `93f82b300f5ef72995cf8f44195f99df8f6e381619dc72e68b7c9b1e207a2ff2`.
- Manifest line format: `<porcelain-status>|<repo-path>|<file-sha256>`, sorted
  by path and joined with LF before hashing.
- Scope: `PBStudio.UI/**`, `PBStudio.UI.Tests/**`, `Tests/**`, `backend/**`,
  `scripts/**`, `src/**` and `config.json`.
- Excluded as mutable/generated evidence: `specs/**`, root reports,
  screenshots, logs, `__pycache__`, `.pyc` and pytest-temp directories.

Der T049-Live-Lauf änderte keine Datei im Digest-Scope. Die historischen
Preflight-Werte bleiben unverändert und werden nicht rückwirkend umgedeutet.
