# Work Plan – SSE GPU Parser Fix

Date: 2026-03-11
Status: in-progress

## Goal
Fix a live WPF/runtime bug where GPU SSE payloads are parsed too strictly and generate format exceptions.

## Trigger
`wpf_app.log` showed:
- `SSE Event Parsing fehlgeschlagen (Gpu)`
- backend emits numeric GPU values as floating-point JSON numbers
- WPF parser used `GetInt32()` and crashed parsing for those fields

## Success criteria
- build passes
- live WPF run no longer logs GPU SSE format exceptions
