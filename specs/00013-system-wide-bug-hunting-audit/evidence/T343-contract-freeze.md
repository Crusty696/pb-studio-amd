# T343 Contract Freeze — 2026-07-30

## Status

- Task: T343
- Result: DECIDED
- Authority: approved repair plan 2026-07-30, OBJ-71, FR-326–FR-336, TR-337
- Preconditions: all four T342 root causes CONFIRMED
- Tests executed: none

## Adapter contract

### Resolution

1. Enumerate normal DXGI adapters in the same index space used by ONNX Runtime DirectML.
2. Exclude software adapters.
3. Configuration precedence:
   1. `hardware.directml_device_id`
   2. deprecated `ai.dml_device_id`, with a warning
   3. `hardware.directml_adapter_policy`, default `highest_vram_amd`
4. `highest_vram_amd` selects the hardware AMD adapter with the largest dedicated VRAM.
5. An AMD integrated adapter is eligible only when no AMD discrete adapter exists.
6. If no AMD hardware adapter is resolvable, fail closed. Do not use CPU, CUDA, ROCm, NVIDIA, Microsoft Basic Render Driver, or an unrelated adapter.
7. A configured index must resolve to an AMD hardware adapter; invalid, software, or non-AMD overrides fail closed.

Expected target-machine result:

| Field | Required value |
|---|---|
| `device_id` | `1` |
| `luid` | `0x00000000_0x0001185b` |
| `name` | `AMD Radeon RX 7800 XT` |
| `dedicated_vram_mb` | physical DXGI value, approximately 16,177–16,384 MB depending on unit/reporting source |

### Central representation

The resolver returns one immutable adapter descriptor containing at least:

- normal DXGI/DirectML index
- normalized LUID
- adapter name
- vendor ID
- software flag
- discrete/integrated classification
- physical dedicated VRAM bytes/MB
- selection policy and reason

All inference, budget, monitoring, and API status code consumes this descriptor. No consumer may independently default, enumerate, or infer an adapter by name.

### ONNX provider and session

- The only inference provider contract is:
  `("DmlExecutionProvider", {"device_id": selected_adapter.device_id})`.
- Every DirectML session sets:
  `enable_mem_pattern=False` and `enable_cpu_mem_arena=False`.
- Existing GPU locks and fail-closed provider checks remain.
- Audio separation must receive the same provider tuple; provider-name-only binding is invalid.
- No silent provider fallback.

Official reference: <https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html>

## VRAM and monitoring coherence

- Effective budget is `min(configured_limit, physical_selected_adapter_vram)` when a positive configured limit exists; otherwise it is the selected adapter's physical ceiling.
- WMI/name-based capacity tables may be diagnostic fallback metadata only; they cannot override a resolved physical ceiling.
- LHM sensor values are accepted only when the monitored adapter can be matched unambiguously to the selected DirectML adapter, preferably by LUID and otherwise by a documented exact identity mapping.
- A mismatch or ambiguous match produces `monitoring_status="degraded"`, records `monitoring_error`, and exposes no temperature/VRAM values from another GPU.
- Budget and status must identify the same index/LUID/name as DirectML.

## Additive GPU status contract

Existing `/gpu/status` fields remain compatible. Add:

- `adapter_index`
- `adapter_luid`
- `adapter_name`
- `selection_policy`
- `dedicated_vram_total_mb`
- `directml_active`
- `monitoring_status`
- `monitoring_error`

States:

- `ready`: selected adapter and matching trusted monitoring data available.
- `degraded`: DirectML adapter is resolved, but matching monitoring data is absent/ambiguous/unavailable.
- `error`: DirectML adapter resolution or required provider contract failed.

The WPF surface displays these states and never presents another GPU's values as the selected adapter.

## LibreHardwareMonitor trust and restore contract

- Required upstream version: official LibreHardwareMonitor 0.9.6.
- Before activation, back up the existing directory to a timestamped path and store SHA-256 for every file.
- Record official release URL, release asset URL, archive SHA-256, extracted file hashes, schema version, and activation time in a versioned runtime manifest.
- The runtime manifest itself is bound by `PBSTUDIO_LHM_MANIFEST_SHA256`; the primary DLL is additionally bound by `PBSTUDIO_LHM_SHA256`.
- The WPF launcher supplies both hashes to the backend environment.
- Activate only after an exact Python 3.11/pythonnet load probe succeeds.
- Missing/mismatched manifest, missing/mismatched assembly, unsupported schema/version, reparse/non-regular files, load failure, or adapter mismatch fails closed.
- The existing untrusted 0.9.5 bundle is never an automatic fallback.
- Restore rehearsal works on copies first. A restore must reproduce the backed-up file set and hashes exactly; production-path activation/restore uses atomic replacement where possible.
- Incompatibility after the bounded activation attempt is `BLOCKED`, with the original backup retained.
- No Python, NuGet, or lockfile dependency is added.

Official release: <https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6>

## Provider and model inventory contract

### Provider state

Exactly one of:

- `offline`: endpoint is unreachable or protocol-invalid.
- `online_empty`: provider is reachable but has no usable installed/served model for the queried scope.
- `ready`: provider is reachable and at least one usable model is verified.
- `degraded`: provider is reachable but one or more required inventory sources failed or disagree.

Reachability alone never implies model availability.

### Model record

Every returned model contains at least:

- `provider`
- `model_id`
- `installed`
- `loaded`
- `downloadable`
- `usable`
- `capabilities`
- `verified_at`
- `status_reason`
- inventory source(s)

`usable` is derived from live provider state, capabilities, and load/JIT semantics; it is not copied from a static card.

### Sources

- LM Studio installed: `/v1/models` only with demonstrably active JIT.
- LM Studio loaded: `lms ps --json`.
- Ollama installed: `/api/tags`.
- Ollama loaded: `/api/ps`.
- Private LM Studio index files and hanging `lms ls --detailed` are not runtime dependencies.
- A downloadable card requires a successful live provider catalog/manifest check.
- Without a supported LM Studio per-model availability check, expose a generic Discover action rather than individual claimed-downloadable models.
- A stale configured ID is a warning, never an installed card.
- Failed catalog verification hides downloadable cards and exposes catalog state as unverified.

Inventory refresh occurs once at backend startup, on model-view open/refresh, after override change, and once after a provider failure. Concurrent callers share a bounded refresh; they do not fan out into request storms.

Official LM Studio references:

- <https://lmstudio.ai/docs/developer/core/headless>
- <https://lmstudio.ai/docs/developer/core/server/settings>

## Selection Receipt contract

Every selection creates a `ModelSelectionReceipt` with:

- provider
- model ID
- task
- execution mode
- required and verified capabilities
- selection source/tier
- reason
- timestamp

The next HTTP request uses exactly the provider URL and model ID from that receipt.

Priority:

1. usable explicit override
2. usable persisted task preference
3. capability-based recommendation
4. another suitable live model

Tie-break:

1. already loaded
2. configured provider preference
3. stable provider/model-name ordering

Failover:

- capability mismatch is never a candidate;
- after a provider error, perform exactly one shared inventory refresh;
- attempt at most three distinct candidates;
- each attempt produces/updates traceable receipt evidence;
- exhaustion returns a clear error rather than silently switching to an unreported provider.

Persistence remains backward compatible:

- `task_overrides[task]` retains the model ID;
- optional `task_provider_overrides[task]` retains the provider;
- old model-only entries resolve only when a unique usable provider match exists; ambiguity is surfaced.

## SceneInfo DTO contract

- Backend remains `confidence: Optional[float]`.
- OpenAPI remains nullable.
- Generated C# DTO remains `double?`.
- Active handwritten C# DTO becomes `double? Confidence`.
- No synthetic default is introduced.
- Both `/video/analyze` and `/video/scenes` must deserialize `null`.
- Batch completion counts a clip only when the client receives a valid successful result; a deserialization/service failure remains visible and is not reported as success.
- A static parity check covers backend schema, OpenAPI snapshot, generated DTO, handwritten DTO, and affected bindings.

## Error and rollback contract

| Condition | Required behavior |
|---|---|
| No valid AMD adapter | fail closed; `error`; no inference fallback |
| Configured adapter invalid/non-AMD/software | fail closed with actionable configuration error |
| DirectML unavailable | fail closed; no CPU provider |
| Consumer adapter differs from central descriptor | fail before session/work execution |
| VRAM configured above physical | clamp to physical ceiling and report effective value |
| Monitoring missing/mismatched | inference may remain available; monitoring `degraded`; foreign values suppressed |
| LHM trust/load failure | monitoring disabled/degraded; do not load untrusted fallback |
| Provider offline/empty | truthful provider state; no ghost model |
| Selected model lacks capability | reject candidate before request |
| Provider request fails | one refresh, at most three distinct candidates, then explicit failure |
| LM Studio JIT activation fails | restore exact hashed backup; mark `BLOCKED` if supported activation cannot be proven |
| DTO confidence is null | preserve null and complete successful deserialization |

## Implementation gate

- Adapter contract: DECIDED
- Provider/inventory contract: DECIDED
- Selection/persistence contract: DECIDED
- DTO contract: DECIDED
- Error/restore contract: DECIDED
- Phase 2 implementation may start at T344.
