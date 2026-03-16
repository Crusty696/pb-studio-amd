# Work Plan – Render Path / Config Alignment Review

Date: 2026-03-10
Status: planned

## Goal
Determine the cleanest way to resolve the mismatch between the active AMD project workspace and the backend `project_dir` output guard used by render/export.

## Why this comes next
- Core functional flows are broadly green.
- A remaining product/workflow issue is that render output is allowed under `C:\Users\david\Documents\PBStudio`, not directly under the active AMD repo path.
- This is a real usability/config correctness issue.

## Preparation
### Files / areas to inspect first
- `backend/config.py`
- any `.env`, config file, or settings source that sets `project_dir`
- render router path-guard logic
- WPF project/open/create behavior if relevant

### Tools needed
- `read` for config source inspection
- `exec` for current effective config verification
- `edit` only if a safe targeted fix is appropriate
- `write` / `edit` for result compression

### Research questions
- Is `project_dir` intentionally independent from repo root?
- Should render outputs be constrained to the currently opened project rather than a static folder?
- Is this a config bug, default-path issue, or intended product behavior?

## Execution steps
1. Trace where `project_dir` is defined and loaded.
2. Compare intended semantics vs active AMD workflow.
3. Decide whether this should be fixed in config, runtime project state, or path guard logic.
4. If safe and obvious, apply a targeted fix; otherwise document precise recommendation.
5. Update `STATUS_MATRIX.md` and `WORKLOG.md`.

## Success criteria
- mismatch source identified clearly
- next fix/recommendation becomes concrete and low-risk

## Stop / ask conditions
- config changes with broader system impact
- uncertainty about intended project isolation semantics
