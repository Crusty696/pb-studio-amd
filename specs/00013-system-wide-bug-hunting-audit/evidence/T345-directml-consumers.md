# T345 DirectML Consumer Binding — 2026-07-30

## Status

- Task: T345
- Result: CONFIRMED
- Tests executed: none
- Execution: parent Z-CORE plus disjoint Z-VIDEO, Z-AI, and Z-AUDIO specialists

## Bound consumers

| Consumer | Central binding | Session flags |
|---|---|---|
| ModelLoader | `get_directml_provider()` | both false |
| RAFT | `get_directml_adapter()` identity + `get_directml_provider()` | both false |
| Moondream | `get_directml_adapter()` identity + `get_directml_provider()` | both false |
| SigLIP | `get_directml_provider()` | both false |
| CLAP | `get_directml_provider()` through ModelLoader | both false |
| audio-separator MDX/MDXC | exact provider tuple assigned to `onnx_execution_provider` | scoped patch sets both false |

All six resolve the process-wide descriptor:

- index `1`
- LUID `0x00000000_0x0001185b`
- AMD Radeon RX 7800 XT

The legacy per-consumer `ai.dml_device_id` reads are absent. DirectML availability checks remain fail-closed and no CPU/CUDA/ROCm provider was added.

## Audio package compatibility

Installed `audio-separator` 0.30.2 passes its `onnx_execution_provider` value unchanged to:

`ort.InferenceSession(..., providers=self.onnx_execution_provider, sess_options=ort_session_options)`

Therefore `[("DmlExecutionProvider", {"device_id": 1})]` reaches ONNX Runtime without package modification. If central adapter resolution fails, `_has_directml` remains false and ONNX stem models stay disabled. The intentionally separate Demucs CPU path is unchanged.

## Verification

- Full files read after convergence: CONFIRMED
- `py_compile` for resolver and all six consumers: CONFIRMED
- Legacy device reads across the six consumers: `0`
- Central provider references across the six consumers: `6/6`
- `git diff --check`: CONFIRMED
- Truncation check: CONFIRMED
- Runtime/model loading tests remain deferred to T361/T363.
