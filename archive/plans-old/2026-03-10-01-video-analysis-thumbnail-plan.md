# Work Plan – Video Analysis + Thumbnail Verification

Date: 2026-03-10
Status: planned

## Goal
Verify the next highest-priority unconfirmed video capabilities:
1. thumbnail availability / retrieval
2. video analysis route
3. scene / motion related backend outputs if exposed

## Why this comes next
- Video is currently only partially verified.
- Thumbnail status looked suspicious in the first smoke test (`thumbnail_available=false`).
- Video analysis is a major functional gap between "core works" and "user-ready".

## Preparation
### Files / areas to inspect first
- `backend/routers/video_router.py`
- `PBStudio.UI/Services/ApiClient.cs`
- relevant tests in `Tests/test_backend_routers.py`

### Tools needed
- `read` for route/client inspection
- `exec` for live smoke scripts / API calls
- `write` for log/status updates

### Research questions
- Does video import generate thumbnails immediately, lazily, or not at all?
- Which exact endpoints exist for thumbnail / analysis / scenes / motion?
- What minimal input is sufficient for a deterministic smoke test?

## Execution steps
1. Inspect video router and confirm exact endpoints + expected payloads.
2. Run live thumbnail test on imported smoke clip.
3. Run live video analysis on smoke clip.
4. If analysis passes, query scene and motion endpoints where available.
5. Record result in `STATUS_MATRIX.md` and `WORKLOG.md`.
6. Compress findings into next-step priority.

## Success criteria
- We know whether thumbnail generation is working, deferred, or broken.
- We know whether video analysis works on a real clip.
- We know which remaining video gaps are real vs only untested.

## Stop / ask conditions
- destructive cleanup needed
- long-running or suspiciously heavy job with system risk
- unclear evidence of data corruption or cross-project side effects
