# T359 — Static completeness enumeration

Status: CONFIRMED

## DirectML sessions

| Consumer | Creation path | Provider and fallback contract |
|---|---|---|
| ModelLoader | `src/pb_studio/core/model_loader.py` | Central provider tuple; both memory flags false; CPU node fallback disabled; run fallback disabled; exact DirectML-only post-check |
| RAFT | `src/pb_studio/video/raft.py` | Same central options and exact post-check |
| Moondream | `src/pb_studio/video/moondream.py` | Encoder, decoder, encoder-only, and combined sessions use the same central options and exact post-check |
| SigLIP | `src/pb_studio/ai/siglip_wrapper.py` | Loader and direct creation paths are post-checked and run fallback is disabled |
| CLAP | `src/pb_studio/ai/clap_wrapper.py` | Sessions originate in the hardened ModelLoader; redundant unused options factory removed |
| Audio MDX | `src/pb_studio/audio/separator.py` | Scoped external constructor interception applies the central options and exact post-check; absence of a real ORT session rejects the external ONNX-to-PyTorch CPU conversion path |

`src/pb_studio/core/directml_adapter.py` is the single options/session
contract. It sets `enable_mem_pattern=False`,
`enable_cpu_mem_arena=False`,
`session.disable_cpu_ep_fallback=1`, calls `disable_fallback()`, and rejects
any provider list other than `DmlExecutionProvider`.

The three unreferenced aggregate multi-adapter fallbacks were removed from
`system_monitor.py`: process-wide VRAM aggregation, foreign-GPU/system
temperature proxying, and all-engine load aggregation.

## Provider and model paths

Production paths were enumerated across startup inventory, model inventory,
registry receipts, Chat, Vision, Brain narration, Model Manager endpoints,
and the provider client factory.

Closed gaps:

- Ollama inventory now fails closed on `/api/tags`; it cannot relabel
  `/v1/models` results as native Ollama inventory.
- Active UI cards resolve exact identity first and only one unambiguous
  legacy alias second; an ambiguous model-only override marks no card active.
- `/models/test` emits an explicit provider/model Selection Receipt before
  inference.
- Provider refresh classification now excludes model-specific HTTP 4xx;
  connection failures, timeouts, HTTP 429, and HTTP 5xx remain provider
  failures.
- The unused synchronous `ModelRegistry._resolve_client()` and the fake
  registry constructed only for model-card enrichment were removed.

Security decision: the approved plan named `lms ps --json` for LM Studio
loaded state. Executing a user-writable CLI was rejected in T358. The
equivalent native HTTP state from `/api/v0/models` (`state=loaded`) is retained
as the process-free, bounded source. This is an explicit security-preserving
technical equivalent, not an omitted check.

The injected-client Brain path and asynchronous legacy Registry refresh remain
documented compatibility/test hooks. Production Chat, Vision, Brain, and
recommendation paths are receipt-bound.

## DTO and UI parity

- `/gpu/status` now has an explicit `GpuStatusResponse` OpenAPI schema and a
  generated C# type.
- Owner-capability headers are present in OpenAPI for Pull, Delete, Activate,
  Mode, and Test.
- `VideoAnalysisResult.status`, `stage_status`, and `stage_errors` exist in
  backend, OpenAPI, generated C#, and handwritten C#.
- Selected and batch video analysis accept only `status=completed` as success;
  partial results remain unanalysed and expose stage errors.
- Available model cards bind provider, provider-specific action text, and
  provider-specific tooltip. Ollama Pull/Delete and LM Studio desktop
  management are no longer presented as the same action.
- Settings displays receipt provider, selection source, and verified
  capabilities.
- `SceneInfo.confidence` remains nullable through every contract copy and UI
  binding.

## Regenerated artifacts

- OpenAPI SHA-256:
  `2AFEB279BDB05CB543CE6D62CF467F4CF206175376E1FA00B8CB982220FD8962`
- Generated C# SHA-256:
  `CD5C28E35757B9B5E5C704FBD69C23B94659F0A9215BD7D21B155A264CC90358`
- Generated C# timestamp is not older than the OpenAPI snapshot.

## Static verification

- Parsed 329 Python files as syntax trees.
- Parsed 19 XAML files as XML.
- Parsed the OpenAPI JSON and verified all five owner headers.
- Enumerated every repository `InferenceSession` and `SessionOptions`
  construction.
- Verified DirectML-only fallback tokens and removal of aggregate monitor
  fallbacks.
- Verified provider-specific UI bindings and video partial-status DTO fields.
- `git diff --check` passed.
- No pytest, WPF build, GUI, provider E2E, hardware load, or render was run.

CONFIRMED: DirectML session creation, provider calls, DTO copies, and affected
UI bindings are fully enumerated and the discovered gaps are closed.
