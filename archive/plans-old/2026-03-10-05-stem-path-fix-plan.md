# Work Plan – Stem Path Normalization Fix

Date: 2026-03-10
Status: planned

## Goal
Fix the stem-separation contract so returned stem paths are actually usable and point to the generated files.

## Root cause
`StemSeparator.separate()` returns relative output filenames (e.g. `808kick120bpm_(Vocals)...wav`).
The real files are written under the configured temp directory (`./temp`).
The current backend mapping does not normalize those filenames into real paths, so API results appear empty/unusable.

## Preparation
### Files / areas to inspect first
- `src/pb_studio/audio/separator.py`
- `backend/routers/audio_router.py`
- any temp/output-dir path helpers in config manager

### Tools needed
- `read` for implementation review
- `edit` for precise fix
- `exec` for live re-test
- `write` / `edit` for compression into status docs

## Execution steps
1. Identify the cleanest normalization point:
   - inside `StemSeparator.separate()` or
   - inside `_run_stem_separation()` in `audio_router.py`
2. Convert returned relative filenames into resolved paths under the configured output/temp directory.
3. Ensure mapping still detects vocals/instrumental/etc correctly.
4. Re-run live stem smoke test.
5. Confirm returned paths exist.
6. Update status/worklog.

## Success criteria
- API returns non-null usable paths
- returned files exist on disk
- no regression in schema shape

## Stop / ask conditions
- risky refactor beyond targeted normalization
- unexpected contract conflicts elsewhere
