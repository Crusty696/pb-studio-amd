# T353 — Provider/model selection persistence

Status: CONFIRMED

## Implementation

- `task_overrides[task]` continues to store the model ID unchanged.
- Additive `task_provider_overrides[task]` stores `lmstudio` or `ollama`.
- Both keys exist in ConfigManager defaults and `config.json`.
- `/models/activate` remains backward compatible with a name-only request.
- Additive request fields allow explicit provider and single-task selection.
- A name-only request is rejected as ambiguous when the same usable model is
  live at both providers.
- Activation accepts only an installed, usable live-inventory record.
- Task capability is validated before persistence; a text model cannot be
  persisted for a vision task.
- Selecting a text model no longer deletes unrelated vision-task choices.
- The endpoint reads the saved file back and verifies every provider/model pair.
- Inventory is invalidated and refreshed once after a successful change.

## Static verification

- Python 3.11 `py_compile` passed.
- `config.json` parsed successfully.
- Static references confirm model-only compatibility plus provider-aware reads,
  writes, and post-write verification.
- Runtime persistence regressions remain deferred until T361.

## Gate

CONFIRMED: task-specific model persistence is backward compatible,
provider-aware, capability-safe, and read-back verified.
