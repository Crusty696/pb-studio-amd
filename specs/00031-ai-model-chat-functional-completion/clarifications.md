# Clarifications: AI Models and Chat Functional Completion

## Resolved Scope

- “KI-Bereich” maps to the product tabs `MODELLE` and `CHAT`; `HIRN` remains the next separate area.
- Local providers currently wired by the product are in scope. A configured provider counts as usable only when its supported runtime API confirms the state.
- MODELLE includes inventory, refresh, provider state, model download/load/delete, active-task assignment, task overrides, progress/cancellation, and project/app lifecycle.
- CHAT includes mode selection, input/send, streamed output, cancellation, history/clear, model/provider status, tool calls/results, errors, retry/fallback, and project isolation.
- Tests may be edited as regression definitions but are not executed. No build, provider probe, backend start, GUI run, download, load, or deletion occurs without explicit user authorization.
- Existing external provider/model state is read-only during the fix phase.
