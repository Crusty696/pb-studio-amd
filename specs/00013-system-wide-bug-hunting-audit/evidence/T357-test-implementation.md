# T357 Test Implementation

Status: CONFIRMED
Date: 2026-07-30

## Implemented coverage

- `Tests/test_t357_model_inventory_receipts.py`: 11 groups for provider inventory, model states, downloadable verification, capability guards, deterministic receipts, canonical-identity ambiguity handling, three-candidate bounds, and the single-refresh rule.
- `Tests/test_t357_models_router_persistence.py`: 11 groups for router validation, owner authorization, atomic configuration persistence, provider identity, activation persistence/read-back, recommendation error mapping, and isolated configuration behavior.
- `Tests/test_t357_gpu_wpf_nullability_contracts.py`: 11 groups for adapter index/LUID, all six DirectML consumers, both ORT memory flags, GPU API/UI truth, LHM trust hashes, model-card truth, provider forwarding, SceneInfo nullability parity, and truthful video-batch counts.
- The physical DirectML/LHM probe is gated by `PBSTUDIO_RUN_T357_HARDWARE=1` and remains disabled until T363.

## Static verification

```text
.venv\Scripts\python.exe -m py_compile Tests\test_t357_*.py
PASS

git diff --check
PASS (line-ending conversion notices only)
```

All three files were read completely and checked for non-zero byte/line counts. They contain 33 test functions before parametrized expansion. No pytest, dotnet build, GUI run, or hardware probe was executed before T361.
