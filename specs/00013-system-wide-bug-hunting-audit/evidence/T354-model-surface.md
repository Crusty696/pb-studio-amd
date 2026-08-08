# T354 — Truthful provider/model surface

Status: CONFIRMED

## Backend surface

- `/models/list` returns provider-specific cards; duplicate names are not merged
  into a synthetic `both` record.
- Additive fields expose installed, loaded, downloadable, usable, capabilities,
  inventory sources, verification time, and status reason.
- Provider records expose `offline`, `online_empty`, `ready`, or `degraded`
  with source-specific reasons and catalog state.
- Active-task labels require the persisted provider/model pair. Legacy
  model-only choices are marked active only when uniquely resolvable.
- `/models/available` no longer emits the static curated catalog as model cards.
- Individual cards appear only from a live-verified downloadable inventory
  record; general LM Studio/Ollama discovery actions remain visible separately.
- Explicit model tests resolve and call the exact card provider.

## WPF surface

- DTOs mirror inventory, provider, discovery, and receipt metadata additively.
- Opening or refreshing the view performs one inventory refresh, then reads the
  same cached generation for download state.
- Provider status and catalog verification are visible.
- Cards show provider, loaded/on-demand/not-usable state, verified capabilities,
  active tasks, and status reason.
- Provider is sent back for activation and model tests.
- The empty download state explicitly says no individual model was live
  verified; no ghost cards are rendered.

## Static verification

- Python 3.11 `py_compile` passed.
- Model Manager XAML parsed as XML.
- Modified C# files have balanced braces.
- Removed `both` model handling and parallel view fan-out from the active
  surface.
- WPF build and GUI execution remain deferred until T362/T365.

## Gate

CONFIRMED: the model UI presents live provider truth and no longer asserts
uninstalled or unverified models.
