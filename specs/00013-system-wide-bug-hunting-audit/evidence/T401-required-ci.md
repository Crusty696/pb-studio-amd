# T401 Required CI

Date: 2026-07-31
Result: PASS

## Change

- CI runs on every pushed branch, every pull request and manual dispatch.
- Governance selects and validates the active SDD phase.
- Python uses the exact Windows hash lock and the coverage/skip/temp quality gate.
- WPF and native tests restore both NuGet graphs in locked mode.
- WPF Release treats warnings as errors.
- Native tests produce TRX and fail below 28 total/passed tests or on any failure/error/timeout/abort.
- All receipts are uploaded even when a preceding gate fails.

## Verification

- YAML parse: PASS.
- Python helper compilation: PASS.
- All Actions use immutable commit SHAs.
- Trigger, expression, locked-restore and TRX semantics independently reviewed: PASS.
- Actual hosted branch/PR checks remain assigned to T415; no remote success is claimed here.
