# T363 — RX 7800 XT Hardware Proof

Status: BLOCKED
Date: 2026-07-30
Scope: TR-344, SC-073

## Adapter and monitoring identity

The physical gated regression passed:

```powershell
$env:PYTHONPATH='src'
$env:PBSTUDIO_RUN_T357_HARDWARE='1'
.venv\Scripts\python.exe -m pytest Tests\test_t357_gpu_wpf_nullability_contracts.py::test_physical_directml_and_lhm_identity_is_rx7800xt -q
```

Receipt: `evidence/T363-hardware-identity.xml`

Verified:

- adapter index: `1`
- adapter LUID: `0x00000000_0x0001185b`
- adapter: `AMD Radeon RX 7800 XT`
- dedicated VRAM: `16,963,137,536` bytes
- central provider tuple: `("DmlExecutionProvider", {"device_id": 1})`
- LibreHardwareMonitor state: `ready`

## Active audio DirectML load

The MDX ONNX audio model completed a dedicated 20-second load probe:

- runtime PID: `35936`
- iterations: `422`
- input tensor: `[1, 4, 3072, 256]`
- selected LUID: `0x00000000_0x0001185b`
- peak GPU engine utilization: `94.891771 %`
- peak dedicated process VRAM: `1,875,615,744` bytes
- peak shared process GPU memory: `31,948,800` bytes
- iGPU LUID `0x00000000_0x0000ffbc`: no counter instance for PID `35936`

Receipts:

- `evidence/T363-audio-active-20260730-072701.out.log`
- `evidence/T363-audio-active-20260730-072701.err.log`
- `evidence/T363-audio-active-20260730-072701.counters.log`

The ONNX Runtime session reports DML first and its implicitly registered CPU
provider second. The session itself proves:

- `session.disable_cpu_ep_fallback=1`
- `enable_mem_pattern=False`
- `enable_cpu_mem_arena=False`
- `disable_fallback()` applied

ONNX Runtime documents that the CPU provider can be implicitly registered and
that `session.disable_cpu_ep_fallback=1` rejects session initialization when
nodes require CPU placement. Provider registration is therefore not evidence
of CPU node execution. The central enforcer was corrected to validate the
session options and DML priority instead of rejecting the implicit provider
name. Regression receipt: `evidence/T363-enforcer-regressions.xml` with
58 passed and 3 bounded skips.

Official reference:
<https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html>

## Workload matrix

| Workload | Asset state | Runtime result | PID/LUID/engine/VRAM proof |
|---|---|---|---|
| Audio MDX | present, 66,759,214 bytes | PASS, 422 iterations | PASS |
| RAFT | present, 4,318,909 bytes | FAIL: graph nodes assigned to default CPU EP while fallback is disabled | unavailable |
| SigLIP Vision | present, 1,713,419,274 bytes | FAIL: graph nodes assigned to default CPU EP while fallback is disabled | unavailable |
| Moondream | required ONNX files absent | FAIL: capability unavailable; no CPU/PyTorch fallback | unavailable |
| CLAP | combined and split ONNX files absent | FAIL: semantic capability unavailable | unavailable |

Per-workload receipts:

- `evidence/T363-inventory.log`
- `evidence/T363-raft.log`
- `evidence/T363-siglip.log`
- `evidence/T363-moondream.log`
- `evidence/T363-clap.log`
- `evidence/T363-audio.log`

## Exhausted safe alternatives

1. Default strict session options: RAFT and SigLIP fail closed.
2. Strict session with graph optimization disabled: both still fail.
3. ONNX static shape inference on temporary copies: both still fail.
4. Local model search across Documents, Hugging Face caches, and Temp:
   no alternative RAFT, SigLIP, Moondream, or CLAP ONNX assets found.
5. CPU EP, PyTorch CPU, torch-directml, CUDA, ROCm, and contract relaxation
   were not used.

Diagnostic receipts:

- `evidence/T363-strict-no-opt-probe.log`
- `evidence/T363-raft-siglip-strict-verbose.log`
- `evidence/T363-shape-inference-probe.log`
- reproducible driver: `evidence/T363-hardware-probe.py`

## Blocker

TR-344 requires all five active workloads. Only Audio can currently produce
the required PID/LUID/engine/VRAM receipt. Completion requires:

- DirectML-only-compatible RAFT and SigLIP ONNX exports for pinned ONNX Runtime
  1.19.2, or an explicitly approved runtime/dependency change; and
- DirectML ONNX assets for Moondream and CLAP from approved, hashed sources.

Those assets are not present locally. Downloading or re-exporting them is not
part of the approved model-asset actions, and changing ONNX Runtime would
violate the no-dependency-change constraint. T363 remains BLOCKED. No
`.qc-passed` marker may be created.

The T363 enforcer correction changed production code after the initial T360.
The implementation marker was invalidated and then recreated only after fresh
T360–T362 validation. The post-T365 launcher correction was likewise followed
by a complete static T360 revalidation. `.completed` is therefore current;
`.qc-passed` remains forbidden by this blocker.
