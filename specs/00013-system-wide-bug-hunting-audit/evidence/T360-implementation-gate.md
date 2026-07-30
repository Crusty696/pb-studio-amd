# T360 — Implementation gate

Status: CONFIRMED

## Preconditions

- T340–T359 are checked complete in `tasks.md`.
- Evidence exists for every task T340–T359.
- No incomplete feature checklist item exists.
- All three T359 independent read-only audits returned.
- `.completed` and `.qc-passed` were absent during gate evaluation.

## Static gate results

- Python 3.11 and NumPy 1.26.4: PASS.
- Global `compileall` over `src`, `backend`, `Tests`, and `scripts`: PASS.
- Independent syntax compile: 348 Python files PASS.
- XML parse: 19 XAML files and all active project XML PASS.
- JSON parse: 58 active/tracked JSON files PASS, including the preserved
  UTF-16-BOM historical evidence file.
- OpenAPI snapshot equals `app.openapi()`: PASS.
- Generated NSwag C# exists, is non-empty, and is not older than OpenAPI:
  PASS.
- Five model mutation owner headers are present in OpenAPI: PASS.
- DirectML memory flags, CPU-EP fallback disablement, run fallback
  disablement, and exact provider post-check: PASS.
- ModelLoader, RAFT, Moondream, SigLIP, CLAP, and audio separator coverage:
  PASS.
- Cross-adapter aggregate monitor fallback removal: PASS.
- Python/NumPy, AMF, LHM, Windows test-path, and forbidden runtime import
  contracts: PASS.
- LibreHardwareMonitor manifest, library, and assembly hashes: PASS.
- Every changed file is non-empty: PASS.
- `git diff --check`: PASS.

Gate summary:
`T360_GATE_STATIC_PASS checks=169 python=348 json=58 xaml=19 changed=87`

## Contract hashes

- OpenAPI SHA-256:
  `2AFEB279BDB05CB543CE6D62CF467F4CF206175376E1FA00B8CB982220FD8962`
- Generated C# SHA-256:
  `CD5C28E35757B9B5E5C704FBD69C23B94659F0A9215BD7D21B155A264CC90358`

## Execution boundary

No pytest, WPF build, GUI, provider E2E, hardware load, or render was run.
Those remain gated to T361–T367.

CONFIRMED: implementation and review evidence are complete. Recreating
`.completed` is authorized; `.qc-passed` remains forbidden until T368.

## Revalidation after T363 remediation

Date: 2026-07-30T07:32+02:00
Receipt: `evidence/T360-revalidation-20260730.log`

T363 found that ONNX Runtime can implicitly report `CPUExecutionProvider`
even when only the central DML provider was requested. The central enforcer
was corrected to verify the effective session contract:

- `session.disable_cpu_ep_fallback=1`
- both required memory flags are false
- `disable_fallback()` is callable and applied
- `DmlExecutionProvider` has first priority
- no unexpected provider is registered

Fresh static result:

- Python compile: 348 PASS
- active JSON parse: 6 PASS
- XAML/project XML parse: 20 PASS
- changed non-empty files: 106 PASS
- OpenAPI/runtime equality: PASS
- generated client freshness: PASS
- LHM manifest/library hashes: PASS
- DirectML consumers and explicit CPU-provider search: PASS
- `git diff --check`: PASS

Hashes remain unchanged:

- OpenAPI SHA-256:
  `2AFEB279BDB05CB543CE6D62CF467F4CF206175376E1FA00B8CB982220FD8962`
- generated C# SHA-256:
  `CD5C28E35757B9B5E5C704FBD69C23B94659F0A9215BD7D21B155A264CC90358`

Revalidation PASS. `.completed` may be recreated. T361 and T362 still
require fresh executable verification.

## Revalidation after T365 production-launcher fix

Date: 2026-07-30T08:26+02:00
Receipt: `evidence/T360-post-T365-revalidation.json`

The production GUI run proved that the externally managed backend did not
inherit the LHM trust anchors from `PythonBridgeService`. The narrowly scoped
fix moved equivalent validation and environment provisioning into the
already authoritative `scripts/runtime_contract.ps1`, which `launch.ps1`
applies before starting the backend.

Fresh result:

- Python syntax: 348 PASS
- active/tracked JSON parse: 63 PASS
- XAML/project XML parse: 22 PASS
- changed non-empty files: 132 PASS
- OpenAPI/runtime equality and generated client freshness: PASS
- complete LHM manifest/library/assembly hash chain: PASS
- launcher PowerShell syntax and live trust-environment application: PASS
- all six DirectML consumers retain central enforcement: PASS
- `git diff --check`: PASS
- focused GPU/WPF/nullability contracts: 19 passed, 1 expected hardware skip
- WPF Release `--warnaserror`: 0 warnings, 0 errors

Hashes remain unchanged:

- OpenAPI SHA-256:
  `2AFEB279BDB05CB543CE6D62CF467F4CF206175376E1FA00B8CB982220FD8962`
- generated C# SHA-256:
  `CD5C28E35757B9B5E5C704FBD69C23B94659F0A9215BD7D21B155A264CC90358`

LHM trust anchors:

- manifest:
  `AF9C9CF981F92A0BD6EA5CC80FDDF0822DAAE76E60F42636AA5B65757CC5B001`
- library:
  `6EBC194316536BA61AF5BE24508AD9FCBB2ECC685E716C12E787C79530F66BF0`

Revalidation PASS. `.completed` may be recreated. `.qc-passed` remains
forbidden because T363 is BLOCKED and T366–T369 are not complete.
