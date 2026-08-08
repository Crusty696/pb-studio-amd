# T340 Evidence Freeze — 2026-07-30

## Status

- Task: T340
- Result: CONFIRMED
- Captured: 2026-07-30T04:12:42.8836386+02:00
- Release state: REOPENED / NOT RELEASE-READY
- Tests executed: none

## Manual runtime log

| Artifact | Bytes | SHA-256 | Git state |
|---|---:|---|---|
| `logs/manual_app_test_20260730_020333.log` | 7,214,505 | `086DCC6F3F7B03872AD72B90148B260E9584FACF3556E01AF2797DC193181D52` | ignored source |
| `evidence/T340-evidence-freeze-2026-07-30/manual_app_test_20260730_020333.log.txt` | 7,214,505 | `086DCC6F3F7B03872AD72B90148B260E9584FACF3556E01AF2797DC193181D52` | versionable copy |

Original and copy match the approved expected hash.

## Git inventory before T340 mutation

- Branch: `00013-system-wide-bug-hunting-audit`
- HEAD: `81dc9fcbb9b72124dc600ca8f2ba398297b3b3d9`
- Upstream: `origin/00013-system-wide-bug-hunting-audit`
- Upstream tracking SHA: `81dc9fcbb9b72124dc600ca8f2ba398297b3b3d9`
- Ahead/behind: `0/0`
- Existing untracked files preserved:
  - `approved-repair-plan-2026-07-30.md`
  - `new-chat-execution-prompt-2026-07-30.md`
- No pre-existing tracked modification was present.

## Runtime inventory

| Component | Observed value |
|---|---|
| Python | `3.11.9` |
| NumPy | `1.26.4` |
| ONNX Runtime | `1.19.2` |
| Available ORT providers | `DmlExecutionProvider`, `CPUExecutionProvider` |
| .NET SDK | `10.0.301` |
| FFmpeg | `8.0.1-essentials_build-www.gyan.dev` |
| LM Studio CLI | commit `efce996` |
| LM Studio daemon | `llmster.exe`, PID `28180` |
| Ollama | `0.32.5`, running |
| PB Studio process | not running |

Provider availability is inventory only. Runtime ML inference remains constrained to `DmlExecutionProvider`; `CPUExecutionProvider` is not an allowed fallback.

## Repository configuration inventory

- `config.json` bytes: `3,610`
- `config.json` SHA-256: `52120D72E2CAE3FB78ABFA01763FA67422B0D775DA5BE5C5C36C4C8C9264037E`
- `hardware.gpu_backend`: `directml`
- `hardware.vram_limit_mb`: `0`
- `hardware.enable_monitoring`: `true`
- `ai.dml_device_id`: unset
- `ai.lmstudio_base_url`: `http://127.0.0.1:1234/v1`
- `ai.ollama_base_url`: `http://localhost:11434/v1`
- `ai.task_overrides`: empty
- `ai.task_preferences`: five task groups
- `paths.lhm_lib`: `./tools/LibreHardwareMonitor/LibreHardwareMonitorLib.dll`
- `PYTHONPATH`, `PBSTUDIO_PYTHON_EXE`, `PBSTUDIO_LHM_MANIFEST_SHA256`, and `PBSTUDIO_LHM_SHA256` were unset in the capture shell.

## LibreHardwareMonitor inventory

- Runtime directory: `tools/LibreHardwareMonitor`
- Trust manifest `pb-studio-lhm-manifest.json`: absent
- `LibreHardwareMonitor.exe`: `B88137B050E7F75276097F27A9BE1AB572B0259841372FCB02B78FA592E81BCF`
- `LibreHardwareMonitor.exe.config`: `B1AC14207C3B84AEEB2DDDD37D27D62AC5BAA1EDD963818AB194C05C364ED7A3`
- `LibreHardwareMonitorLib.dll`: `21673A431323CD350F31F7598D3E1A161BF9D0A4C030B76EF475441FBD30AC33`
- `LibreHardwareMonitorLib.pdb`: `281FF0D05EF896648590E20D0E6BC8566ACA7DF4CAA68F9C264819DE78BD2924`
- `LibreHardwareMonitorLib.xml`: `3163E8A9C070ED86E547FECA6B1E92B88A4277370049DC677B0DDD4EEEC440D6`

No trust or origin claim is made for this pre-T347 bundle.

## Governance artifacts

- Approved plan SHA-256: `D3F1F7630C907322294B71549B403C1CD77C9B432A257AFE8BBB232244195AAF`
- Execution prompt SHA-256: `060A7A655701DD0271F59ED9AD51D9F9472BE35805F08F6B118E421EF971F97E`
- `spec.md`, `plan.md`, `tasks.md`, and `repair-progress.md`: present
- `checklists/`: absent

## Invalidated release markers

| Marker | Pre-delete SHA-256 | Pre-delete content |
|---|---|---|
| `.completed` | `2FD82D35F3105D4B22E8A77E6ABB56CF08B74137193DEE08FC5212116ACF7549` | `Implementation gate passed 2026-07-29: T305-T330 complete; T329 has 0 open High/Critical findings.` |
| `.qc-passed` | `0224A4FA4FB873F6D4A3E01427BA535529B462C5706D438B722EBA3C2D65336C` | `QC passed 2026-07-29: T332-T338 End-QC 100% PASS; final suite 1036 passed, 11 justified skips, 0 failures; WPF Release 0 warnings/0 errors; full-length postfix H.264 and HEVC PASS over 6335.027 seconds. Publication gate T339 remains open.` |

Both markers are absent after T340. They may only be recreated at T360 and T368 respectively.
