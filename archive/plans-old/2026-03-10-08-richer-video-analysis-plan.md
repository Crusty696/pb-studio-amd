# Work Plan – Richer Video Analysis Quality Test

Date: 2026-03-10
Status: planned

## Goal
Test video-analysis behavior on a non-trivial clip so scene detection, motion, embeddings, and semantic outputs can be assessed beyond the tiny smoke clip.

## Why this comes next
- Core video backend paths are already green on the minimal smoke clip.
- The remaining uncertainty is quality/value on richer real-world input.

## Preparation
### Files / areas to inspect first
- `backend/routers/video_router.py`
- any existing sample/demo clips in repo or accessible project data

### Tools needed
- `read` for endpoint expectations
- `exec` for live analysis script and result inspection
- `write` / `edit` for result compression

### Research questions
- Which available local clip is best suited to trigger non-zero scenes/motion/tags?
- Are embeddings/colors/tags/scenes exposed directly in current analysis response or via separate endpoints?

## Execution steps
1. Find a richer available local video clip.
2. Run import + analyze + scenes + motion against it.
3. Inspect result shape for non-trivial outputs.
4. Update status/worklog.

## Success criteria
- either confirm richer outputs are working, or isolate why they remain weak/empty

## Stop / ask conditions
- no suitable non-trivial clip available locally
- unexpectedly heavy runtime cost without clear value
