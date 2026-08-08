# T380 Video Analysis Truth

Date: 2026-07-31
Result: PASS

## Change

- Video analysis persists `completed`, `partial` and `failed` outcomes with
  stage status and stage errors before publishing RAM state.
- `is_analyzed` is true only for a completed result; list and detail endpoints
  reload partial and failed truth from durable state.
- The UI captures clip ID/path and project generation before awaiting, permits
  only one analysis scope and rejects stale or mismatched responses.

## Verification

- Python compile and `git diff --check`: PASS.
- WPF Release build: PASS, 0 warnings, 0 errors.
- `video_router.py`: `c16f29f432a39e225918e260bb56cd62772390c58825863702b6c431da4f3411`.
- `video_schemas.py`: `73cedb28f89a4934b3a24b98aa1e573c71a718f3f6af4fcb163ddd741c1de424`.
- `VideoLibraryViewModel.cs`: `396e6dba451751d6d606bf16d07428474e5eacf2a458a6dbb799bf9cfee38224`.

Fault-injection and A→B runtime proof remain bundled in T404 and T410.
