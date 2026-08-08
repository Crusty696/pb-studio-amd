# T342 Independent Root-Cause Gate — 2026-07-30

## Status

- Task: T342
- Result: CONFIRMED
- Tests executed: none
- Methods: frozen-log analysis, source/data-flow audit, live read-only inventory, DXGI enumeration, OpenAPI parity audit, and three independent specialist reviews

## GPU adapter mapping

### Reproduction

The official DXGI `EnumAdapters` order was enumerated read-only on the target machine:

| DirectML device ID | DXGI LUID | Vendor | Dedicated VRAM | Flags | Adapter |
|---:|---|---:|---:|---:|---|
| 0 | `0x00000000_0x0000ffbc` | `0x1002` | 485 MB | `0x0` | AMD Radeon(TM) Graphics |
| 1 | `0x00000000_0x0001185b` | `0x1002` | 16,177 MB | `0x0` | AMD Radeon RX 7800 XT |
| 2 | `0x00000000_0x000117f8` | `0x1414` | 0 MB | `0x2` | Microsoft Basic Render Driver |

The frozen runtime log contains 338 exact RAFT selections of DirectML device `0`. The repository has no configured `ai.dml_device_id`, so the independent consumers default to `0`:

- `src/pb_studio/core/model_loader.py:209-210`
- `src/pb_studio/video/raft.py:131-133`
- `src/pb_studio/video/moondream.py:148-150`
- `src/pb_studio/ai/siglip_wrapper.py:70-76`
- `src/pb_studio/ai/clap_wrapper.py:86-92`

`src/pb_studio/audio/separator.py:146-148` supplies only the provider name and cannot bind a DirectML device ID.

### Falsification

- CUDA/ROCm selection is absent and not causal.
- The RX 7800 XT is visible to DXGI and therefore not missing from the OS adapter inventory.
- All inspected explicit ONNX session sites preserve both mandatory flags: `enable_mem_pattern=False` and `enable_cpu_mem_arena=False`.
- Provider availability alone does not select the discrete GPU; DirectML device IDs follow DXGI enumeration order, not maximum VRAM.

### Root cause

**CONFIRMED:** six DirectML consumers do not share a central adapter contract. Five independently use the unset legacy key with default device `0`; audio separation omits the device tuple entirely. Device `0` is the integrated Radeon, while VRAM budgeting describes the RX 7800 XT, producing inference/budget/monitoring incoherence.

`src/pb_studio/core/vram_budget_manager.py:293,317-357` independently uses WMI/name heuristics and a hard-coded 16,384 MB RX 7800 XT capacity. The frozen runtime selected that RX budget 14 times while inference stayed on device `0`. `src/pb_studio/core/system_monitor.py:305-324` uses another name heuristic. No LUID/index contract connects the three sources. The main acquisition path also reaches the budget manager directly through `backend/dependencies.py:36,59-68,93-103`; its sensor comparison path in `src/pb_studio/core/vram_arbiter.py:85-111` is not the source of adapter truth.

Official contract: <https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html>

## LibreHardwareMonitor trust

### Reproduction

- `paths.lhm_lib` points to `tools/LibreHardwareMonitor/LibreHardwareMonitorLib.dll`.
- The bundle exists, but `pb-studio-lhm-manifest.json` is absent.
- The untrusted existing bundle reports version 0.9.5, not the required official 0.9.6.
- `PBSTUDIO_LHM_MANIFEST_SHA256` and `PBSTUDIO_LHM_SHA256` were unset.
- Direct invocation of the current verifier reproduced:
  `ValueError: PBSTUDIO_LHM_MANIFEST_SHA256 fehlt oder ist ungueltig`.
- The frozen runtime log contains the same manifest error 16 times.
- `src/pb_studio/core/system_monitor.py:42-68` requires a schema-v1 manifest whose hash is bound through the environment before assembly load.

### Falsification

- The primary DLL is present, so a missing DLL is not the cause.
- Monitoring is enabled in `config.json`, so the feature flag is not the cause.
- No provenance assertion is made for the pre-T347 bundle merely because the files exist.
- A live `/gpu/status` recheck is **OPEN** because port 8765 was not listening and T342 did not authorize a process start. The frozen run already proves the same failure path and returned `Unknown/0`.

### Root cause

**CONFIRMED:** deployment and runtime trust contracts are incomplete. The runtime correctly fails closed because neither the required manifest nor its expected hash exists. The official, hash-bound 0.9.6 bundle/manifest/launcher chain must be established before monitoring can be enabled.

Official release: <https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6>

## Provider and model inventory

### Historical reproduction

The frozen runtime log records LM Studio as `online_empty`, zero LM Studio provider selections, 1,014 Ollama selections, and a successful Ollama vision request. LM Studio JIT was disabled, so `/v1/models` represented only loaded/served models rather than installed models.

### Live read-only cross-check

State changed while T342 was running and was recorded without mutation:

| Provider | Installed | Loaded/served | Evidence |
|---|---:|---:|---|
| LM Studio | 13 | 1 (`hermes-ha-ornith`) | `/api/v1/models`, `/v1/models`, `lms ls`, `lms ps` |
| Ollama | 15 | 0 | `/api/tags`, `/api/ps`, CLI inventory |

`C:\Users\david\.lmstudio\.internal\http-server-config.json:10` still has `justInTimeModelLoading:false`. The current non-empty LM Studio response is explained by one explicitly loaded text model, not by JIT activation. Who loaded that model or changed the installed inventory is **OPEN** and non-blocking because it does not alter the reproduced inventory-contract defect.

### Data-flow proof

- Vision routing: `backend/routers/video_router.py:1279-1297` → `src/pb_studio/ai/lmstudio_vision_wrapper.py:226-303` → `src/pb_studio/ai/llm_provider.py:122-162` → `src/pb_studio/ai/lmstudio_client.py:552-583` → `src/pb_studio/ai/model_registry.py:329-377`.
- LM Studio has no served vision model; Ollama exposes a compatible vision model, so the observed Ollama fallback is consistent with the existing selection contract.
- `task_overrides` is empty and configured preferences do not match the currently served LM Studio ID.
- `backend/routers/models_router.py:584-659` emits eight static curated vision cards without confirming installed, loaded, or downloadable state.
- `src/pb_studio/ai/lmstudio_client.py:394-456,846-852` and `backend/routers/models_router.py:43-103,461-473` conflate provider reachability, installed inventory, and served inventory.

### Root cause

**CONFIRMED:** provider reachability, installed models, loaded/served models, downloadable catalog entries, capability, and current selection are mixed. Static curated entries create ghost cards, HTTP 200 with an empty served list is reported as broadly available, and selection receipts do not expose the actual tier/source/reason. Ollama use was a real bounded fallback; the misleading status surface was not.

Official LM Studio contracts:

- <https://lmstudio.ai/docs/developer/core/headless>
- <https://lmstudio.ai/docs/developer/core/server/settings>

## SceneInfo nullability

### Contract parity

| Layer | Contract | Evidence |
|---|---|---|
| Backend schema | `Optional[float] = None` | `backend/schemas/video_schemas.py:95-100` |
| Backend producer | intentionally emits `None` when no calibrated score exists | `backend/routers/video_router.py:786-795` |
| OpenAPI | nullable number, not required | `PBStudio.UI/openapi.snapshot.json:4149-4152` |
| Generated DTO | `double?` | `PBStudio.UI/Generated/ApiTypes.g.cs:2261-2284` |
| Active handwritten DTO | `double` | `PBStudio.UI/Services/ApiClient.cs:1216-1221` |

### Failure-path proof

The active WPF client uses the handwritten Services DTO, not the generated type. Both `/video/analyze` and `/video/scenes` deserialize through it. `System.Text.Json` rejects JSON `null` for non-nullable `double`; the client catches the exception and returns `null`. Batch loops then increment completion despite a null result, leaving backend persistence and UI state split. The frozen log contains 171 matching failures: 165 POST analysis responses and 6 GET scene responses.

### Root cause

**CONFIRMED:** the active handwritten C# DTO drifted from the backend, OpenAPI, and generated DTO. The backend `null` is valid data and must not be replaced with a fabricated confidence value.

## Gate decision

- GPU mapping root cause: CONFIRMED
- LHM trust root cause: CONFIRMED
- Provider/inventory root cause: CONFIRMED
- SceneInfo nullability root cause: CONFIRMED
- Implementation may proceed only after T343 freezes the repair contracts.
