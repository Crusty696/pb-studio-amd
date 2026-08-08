# T361 — Targeted regressions

Status: CONFIRMED
Date: 2026-07-30

## Scope

- Central DirectML adapter selection, configured override precedence, and deprecated `ai.dml_device_id` compatibility.
- All six DirectML consumer contracts and both required ORT memory flags.
- Provider/model inventory truth, refresh coalescing, downloadable verification, capability filtering, receipts, bounded failover, and provider-bound requests.
- Owner-authorized model mutations and atomic provider/model persistence.
- GPU API/WPF truth, LHM trust anchors, OpenAPI/generated/handwritten `SceneInfo` nullability, and video batch accounting.
- Copy-only restoration of all 43 backed-up LibreHardwareMonitor files with exact path and SHA-256 parity.

## First run and correction

Initial result: `42 passed, 1 skipped, 1 failed`.

The failure was test drift: one static assertion expected the removed inline expression
`model.provider == requested_provider`. Runtime code now binds provider identity through
the central `_resolve_inventory_matches(..., provider=...)` helper, and behavior tests
already proved ambiguous-provider rejection and exact-provider forwarding. The assertion
was updated to the central resolver contract. No product code changed.

Two missing executable contract checks were then added:

- `hardware.directml_device_id` precedence plus readable deprecated `ai.dml_device_id`.
- LHM backup restoration into pytest `tmp_path` with exact 43-file/hash comparison.

## Final command

```powershell
$env:PYTHONPATH='src'
Remove-Item Env:PBSTUDIO_RUN_T357_HARDWARE -ErrorAction SilentlyContinue
.venv\Scripts\python.exe -m pytest `
  Tests\test_t357_gpu_wpf_nullability_contracts.py `
  Tests\test_t357_model_inventory_receipts.py `
  Tests\test_t357_models_router_persistence.py `
  -q --tb=short `
  --junitxml=specs\00013-system-wide-bug-hunting-audit\evidence\T361-targeted-regressions.xml
```

## Result

- Collected: 47
- Passed: 46
- Failed/errors: 0
- Skipped: 1
- Duration: 10.309 s
- JUnit SHA-256: `12320F8417FE3E4C651B03772A3C1E85B7ABB6A1C1D8164C5C9056495ED2075D`
- `git diff --check`: PASS; line-ending conversion notices only.

The only skip is
`test_physical_directml_and_lhm_identity_is_rx7800xt`, gated by
`PBSTUDIO_RUN_T357_HARDWARE=1` for T363.

## Revalidation after T363 remediation

Date: 2026-07-30T07:33+02:00

The targeted scope was expanded with `test_model_loader.py` and
`test_clap_wrapper.py` because T363 corrected the effective ONNX Runtime
session contract and removed CLAP's duplicate exact-provider-list check.

Fresh result:

- collected: 88
- passed: 85
- failed/errors: 0
- skipped: 3
- duration: 14.73 seconds
- JUnit SHA-256:
  `1063D6336F8296DBBB54670311333A779D076C8FE0C1048524D4A1B14E8A9392`

The skips are the T363 physical multi-model probe and the two existing
CLAP real-asset integration cases. T363 executed the physical adapter probe
and separately proved the available Audio DirectML load; missing CLAP assets
remain recorded as its blocker.

Revalidation PASS.
