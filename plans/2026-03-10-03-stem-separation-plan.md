# Work Plan – Stem Separation Smoke Test

Date: 2026-03-10
Status: planned

## Goal
Verify whether PB Studio can execute a real stem-separation job successfully on a minimal audio clip.

## Why this comes next
- Audio import/analyze/waveform is already green.
- Stem separation is still a major unverified GPU/media workflow.
- It is one of the most meaningful remaining functional checks.

## Preparation
### Files / areas to inspect first
- `backend/routers/audio_router.py`
- any stem/model config references
- optional related tests

### Tools needed
- `read` for route/config inspection
- `exec` for live smoke script
- `write` / `edit` for result compression

### Research questions
- Which model names are accepted in practice?
- Where are output stem files expected to land?
- How does success/failure present in the response payload?

## Execution steps
1. Inspect current stem endpoint expectations and result format.
2. Use known-good imported audio clip.
3. Trigger minimal real stem separation.
4. Wait safely for result.
5. Validate returned paths / file existence if successful.
6. Update `STATUS_MATRIX.md` and `WORKLOG.md`.

## Success criteria
- endpoint returns success payload
- result paths exist or are otherwise verifiably valid
- no backend crash / no invalid response shape

## Stop / ask conditions
- suspiciously large model/runtime cost
- destructive overwrite risk
- signs of unstable GPU/runtime behavior
