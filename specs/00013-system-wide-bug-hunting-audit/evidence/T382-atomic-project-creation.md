# T382 Atomic Project Creation

Date: 2026-07-31
Result: PASS

## Change

- Creation uses a unique same-parent staging directory carrying a random owner
  marker; audio, video, output, cache, metadata and migrated `state.db` are
  prepared before publication.
- A fresh global project row is written transactionally with the same owner
  token and its generated project ID.
- `os.replace()` publishes the fully prepared directory atomically on the same
  volume; concurrent target creation cannot merge directory contents.
- Every failure or cancellation compensates only the freshly returned DB row
  after token verification and only the marker-matching staging/final
  directory below the configured project base.
- Existing targets, foreign rows and directories without the exact marker are
  rejected and never removed.

## Critical Review

- Filesystem and SQLite cannot share one transaction. The implementation uses
  atomic filesystem publication plus explicit, ownership-checked compensation.
- Brain migration is completed against staging before rename. A later bind
  failure leaves the previous runtime project intact and enters the same
  compensation path.
- Cleanup failure is not hidden: the API returns HTTP 500 with the incomplete
  compensation detail and logs it at critical severity.

## Verification

- `.venv\Scripts\python.exe -m py_compile backend\routers\project_router.py
  src\pb_studio\data\repositories\project_repository.py`: PASS.
- `git diff --check` for both files: PASS.
- Active SDD validator: `valid=true`, phase `open`, no findings.
- `backend/routers/project_router.py` SHA-256:
  `0da8d11bdbc2d084f71a0cfeec14a66b2a0186c316a66bbd8f60d1d1cb7857bf`.
- `src/pb_studio/data/repositories/project_repository.py` SHA-256:
  `5ac9008ee6e3452f0af27cbd21b0d0ba4d822b7e9b2dc447cb7b9de899be1fa6`.

Stage-by-stage fault injection and retry proof remain deferred to T404/T410.
