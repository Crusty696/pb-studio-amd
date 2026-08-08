# T362 — Full Suite, Release Build, Security, Failure, Restart

Status: PASS
Date: 2026-07-30
Scope: TR-343

## Python full-suite result

Command:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m pytest Tests -q --tb=short --junitxml=specs\00013-system-wide-bug-hunting-audit\evidence\T362-full-suite.xml
```

Final result:

- 1,083 passed
- 12 skipped
- 0 failed
- 45 warnings
- 479.52 seconds wall time
- JUnit: `evidence/T362-full-suite.xml`
- JUnit SHA-256: `807408179D4FFFFD36B225EECB8F60F08CCB59FA3247DAD8A6433E2BD0882ACC`

The first full run reported 22 failures. Isolation assigned all failures to stale test expectations after the approved T344–T359 adapter, inventory, provider, and separator contract changes. No production-code correction was required by this run. The affected tests were aligned with the central DirectML resolver, frozen model inventory, receipt, and separator session contracts.

Isolation receipts:

- AI/provider cluster: 70 passed — `evidence/T362-ai-provider-cluster.xml`
- DirectML cluster: 52 passed, 2 skipped — `evidence/T362-directml-cluster.xml`
- Separator cluster: 16 passed — `evidence/T362-separator-cluster.xml`

## Required regression clusters

The final JUnit receipt contains the following passing clusters:

- security regressions: `Tests/test_t329_security_regressions.py` — 11 passed
- render persistence: `Tests/test_render_persistence.py` — 10 passed
- project/Brain binding: `Tests/test_project_brain_binding.py` — 6 passed
- Brain recovery: `Tests/test_brain_recovery.py` — 6 passed
- model persistence/restart: `Tests/test_t357_models_router_persistence.py` — 16 passed
- GPU failure/release readiness: `Tests/test_gpu_core_release_readiness.py` — 8 passed

These receipts cover the T362 security, failure, persistence, recovery, and restart checks. `git diff --check` also completed without an error; its output contained line-ending notices only.

## Skip audit

All 12 skips are identified and bounded:

1. deprecated Ollama vision wrapper collection; replacement coverage is in `test_lmstudio_vision_wrapper.py`
2. CLAP integration model asset absent
3. CLAP integration audio asset absent
4. SigLIP text encoder asset absent
5. SigLIP text encoder asset absent
6. SigLIP text encoder asset absent
7. SigLIP model assets absent
8. manually annotated subtrack data set absent
9. physical RX 7800 XT test intentionally reserved for T363
10. waveform integration audio asset absent
11. waveform integration audio asset absent
12. waveform integration audio asset absent

The physical hardware skip is not accepted as final hardware evidence; it must execute under T363. Asset-dependent integration skips do not hide a failing unit or contract test.

## WPF Release build

Command:

```powershell
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore -v:minimal -bl:specs\00013-system-wide-bug-hunting-audit\evidence\T362-wpf-release.binlog
```

Result:

- 0 warnings
- 0 errors
- binary log: `evidence/T362-wpf-release.binlog`
- binary log SHA-256: `D4DB5FE26466E7E923BE3CA81416DBD4C1A0FA15CFCD275CEAA71AF0C4B2FF88`
- `PBStudio.UI.dll` SHA-256: `0F1183A45008573FF645E43730E139E36A1C2A290B92A7C09EDE3223F4C7779B`
- generated `ApiTypes.g.cs` SHA-256: `CD5C28E35757B9B5E5C704FBD69C23B94659F0A9215BD7D21B155A264CC90358`

## Gate result

T362 PASS. T363–T368 remain required. `.qc-passed` remains absent.

## Revalidation after T363 remediation

Date: 2026-07-30

T363 corrected the effective ONNX Runtime session validation and CLAP's
duplicate provider-list check. The first fresh full-suite run produced:

- 1,085 passed
- 12 skipped
- 1 failed

The single failure was stale test-message drift in
`test_c01_semantic_audio_directml.py`: the unsafe mock session was still
rejected, now by the stronger `CPU EP fallback is not disabled` check rather
than the removed exact-list error. The assertion was aligned with the actual
guard. Isolated receipt: `evidence/T362-c01-cluster.xml`, 7 passed.

Final fresh full-suite result:

- 1,086 passed
- 12 skipped
- 0 failed/errors
- 45 warnings
- 497.70 seconds
- JUnit logical total: 1,098, including collection skip
- JUnit SHA-256:
  `718A40FDCAD3CDDDCB7BEC543E5C2C0E26A674FDDFB737A6BD6C08347E534D9A`

Fresh WPF Release build:

- 0 warnings
- 0 errors
- binlog SHA-256:
  `BAB566BF6AC87D07E03D9F86928225433DD55C0E902506E5C3943AF45CC307BA`
- `PBStudio.UI.dll` SHA-256:
  `0F1183A45008573FF645E43730E139E36A1C2A290B92A7C09EDE3223F4C7779B`
- generated client SHA-256:
  `CD5C28E35757B9B5E5C704FBD69C23B94659F0A9215BD7D21B155A264CC90358`

The 12 skips remain the same bounded asset/data/hardware cases listed above.
T363 separately executed the physical adapter test and recorded the current
model-asset blockers.

Revalidation PASS. `.completed` exists; `.qc-passed` remains absent.
