# OBJ-77 AMD-First Blocker Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete every non-external repair and prove the full local product chain on the existing RX 7800 XT first. Only after that local AMD completion may the Intel/NVIDIA DirectML matrix, LM-Studio maintenance window and real four-hour stress run execute as final release gates. OR-363 remains unchanged and must be fulfilled before release.

**Architecture:** Wave 0 records the truthful current external-resource status and registered, hash-bound pending-or-verified real-media manifests without changing product code, then merges into the integration branch even while the reservation validator truthfully exits 1. Waves 1-6 complete all non-external implementation and local RX 7800 XT verification. Tasks 5-7 also implement and commit the matrix runner, LM harness and stress worker, prove the local AMD matrix, and pass stress Canary/Soak before the candidate SHA is frozen. A fresh four-resource receipt with reservation-validator exit 0 then opens the final external phase. Tasks 9-12 make no code changes and execute exactly the frozen `tested_candidate_sha`; the later evidence commit references that unchanged SHA. Production PB Studio remains AMD-only; Intel and NVIDIA prove the ONNX-DirectML contract, not a new product-support promise.

**Tech Stack:** Python 3.11.9, NumPy 1.26.4, ONNX Runtime DirectML 1.19.2, PowerShell 5.1, Windows batch, pytest, FastAPI, DXGI, LibreHardwareMonitor, LM Studio HTTP API, JSON/SHA-256 evidence.

## Global Constraints

- Execute only in `C:\Users\david\Documents\Pb_studio_AMD_version-remediation`. Use `codex/obj77-wave0-foundation` through Task 3, then create later wave branches only from the latest green integration SHA.
- Do not modify the dirty source worktree `C:\Users\david\Documents\Pb_studio_AMD_version`.
- Runtime neural inference remains `DmlExecutionProvider` only; CUDA, ROCm, CPU EP and PyTorch inference fallbacks remain forbidden.
- Every ORT session sets `enable_mem_pattern=False`, `enable_cpu_mem_arena=False`, `execution_mode=ORT_SEQUENTIAL`, disables CPU fallback and serializes `Run` through the shared GPU lock.
- Production adapter selection remains `highest_vram_amd`; Intel/NVIDIA testing is isolated in the matrix runner.
- Python remains 3.11.x, NumPy remains exactly 1.26.4, and every Python command uses `PYTHONPATH=src`.
- Real gate media may come only from `C:\Users\david\Videos\test_data\audio` and `C:\Users\david\Videos\test_data\video`; synthetic media and mocks cannot close a live gate.
- No database migration, dependency change, `IApiClient.cs` change, file deletion, model load/unload, watchdog stop or paid cloud resource without its existing explicit approval gate.
- Historical evidence files are immutable. New observations go into new timestamped receipts.
- T003 must pass before requesting T019; no bulk analysis before the ten-clip Canary receives separate approval.
- Wave 0 and Waves 1-6 local-AMD work are not blocked by missing Intel/NVIDIA access, an unauthorized LM-Studio maintenance window or an unreserved four-hour stress window. Those four states remain truthfully failed and deferred until final external release acceptance.
- Tasks 5, 6 and 7 are local AMD preparation and must finish before Candidate-Freeze. Tasks 9-12 are the deferred external executions. Task 13 remains the final release-convergence gate.

## Authoritative Task-2 Scope Correction

Task 2 registers every currently present file in the two approved media roots in
Wave 0, including its path, size, media SHA-256, stream, duration, annotation
version and `verification_status`. `pending` is an honest, valid registration
state; it is rejected only by the later strict KPI validator. Wave 0 has no
five-mix or ten-clip count gate. Those quantities remain A-14 (Wave 2) and
V-11/T019 (Wave 3) gates. The authoritative ruling is
`.superpowers/sdd/2026-08-12-obj77-blocker-remediation/task-2-scope-correction.md`.

---

## File Map

### New files

- `specs/00022-complete-requirements-remediation/contracts/external-reservation.schema.json` — machine-readable authorization and reservation contract.
- `specs/00022-complete-requirements-remediation/contracts/ground-truth-corpus.schema.json` — corpus metadata contract.
- `specs/00022-complete-requirements-remediation/contracts/ground-truth-annotation.schema.json` — per-medium annotation contract.
- `scripts/requirements/validate_obj77_reservations.py` — fail-closed reservation validator.
- `scripts/validate_obj77_ground_truth.py` — real-media, hash and annotation validator.
- `scripts/directml_matrix/probe.py` — vendor-neutral DirectML hardware and inference probe.
- `scripts/directml_matrix/run.ps1` — portable AMD/Intel/NVIDIA matrix entry point.
- `scripts/directml_matrix/evidence.schema.json` — matrix receipt contract.
- `scripts/diagnostics/obj77_lmstudio_window.ps1` — snapshot, exact-process pause, product verification and restore orchestration.
- `scripts/qa/stress_receipt.py` — stress receipt writer and validator.
- `scripts/qa/execute_4h_stress_test.py` — real-media stress worker.
- `scripts/qa/run_4h_stress.ps1` — synchronous owner-scoped backend/worker orchestration.
- `Tests/test_obj77_external_reservations.py` — reservation contract tests.
- `Tests/test_obj77_ground_truth_contract.py` — Ground-Truth validator tests.
- `Tests/test_obj77_directml_matrix.py` — vendor and receipt tests.
- `Tests/test_obj77_lmstudio_window_contract.py` — maintenance safety tests.
- `Tests/test_obj77_stress_worker.py` — duration, VRAM, media, telemetry and receipt tests.

### Modified files

- `src/pb_studio/core/directml_adapter.py` — complete the existing central DirectML session contract.
- `Tests/test_obj77_directml_contract.py` — retain the three existing red contract tests and add exact-provider regression.
- `scripts/owned_runtime_process.ps1` — point `Kind=Stress` to the tracked worker under `scripts/qa`.
- `scripts/qa/stress_4h.bat` — delegate to the synchronous PowerShell orchestrator and propagate its exit code.
- `scripts/qa/check_stress.bat` — validate the final receipt instead of process presence.
- `specs/00022-complete-requirements-remediation/tasks.md` — mark only evidence-backed tasks complete.
- `specs/00022-complete-requirements-remediation/evidence/` — add immutable reservation, Ground-Truth, hardware, live and stress receipts.
- `C:\Users\david\Brain\10_Projects\PB_studio\log.md` — append final implementation/evidence status after completion.

---

### Task 1: External authorization and reservation status inventory

**Files:**
- Create: `specs/00022-complete-requirements-remediation/contracts/external-reservation.schema.json`
- Create: `scripts/requirements/validate_obj77_reservations.py`
- Create: `Tests/test_obj77_external_reservations.py`
- Evidence: `specs/00022-complete-requirements-remediation/evidence/external-resource-reservations.json`

**Interfaces:**
- Consumes: OBJ-77 `OR-363` and the currently verifiable external-resource state.
- Produces: `validate_reservations(path: Path) -> list[str]`; an empty list is required only for final external release acceptance, while Wave 0 records the truthful nonzero result.

- [ ] **Step 1: Write the failing reservation tests**

```python
from pathlib import Path

from scripts.requirements.validate_obj77_reservations import validate_reservations


def test_missing_authorization_is_blocking(tmp_path: Path) -> None:
    receipt = tmp_path / "reservations.json"
    receipt.write_text(
        '{"schema_version":1,"intel":{"status":"missing"},"nvidia":{"status":"missing"},'
        '"lm_window":{"status":"not_authorized"},'
        '"stress_window":{"status":"not_reserved"}}',
        encoding="utf-8",
    )
    errors = validate_reservations(receipt)
    assert errors == [
        "intel.status must be reserved",
        "nvidia.status must be reserved",
        "lm_window.status must be authorized",
        "stress_window.status must be reserved",
    ]
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run:

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_external_reservations.py -q
```

Expected: collection fails because `validate_obj77_reservations` does not exist.

- [ ] **Step 3: Implement the fail-closed reservation validator**

```python
REQUIRED_STATUS = {
    "intel": "reserved",
    "nvidia": "reserved",
    "lm_window": "authorized",
    "stress_window": "reserved",
}


def validate_reservations(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for key, expected in REQUIRED_STATUS.items():
        actual = payload.get(key, {}).get("status")
        if actual != expected:
            errors.append(f"{key}.status must be {expected}")
    return errors
```

The JSON schema must additionally require owner, start/end UTC, machine or provider identity, approval identity and scope for every reservation. Temporary sentinel values and empty strings are invalid.

- [ ] **Step 4: Record the current deferred state without fabricating approvals**

Create the receipt with real known data and explicit deferred values. The validator must exit nonzero until Intel access, NVIDIA/Azure authorization, an LM maintenance window and a 4.5-hour stress window are supplied. That nonzero result blocks only final external release acceptance; it does not block Wave 0 or local AMD remediation.

- [ ] **Step 5: Run unit and live validation**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_external_reservations.py -q
.\.venv\Scripts\python.exe scripts\requirements\validate_obj77_reservations.py specs\00022-complete-requirements-remediation\evidence\external-resource-reservations.json
```

Expected: unit tests pass; live validation remains nonzero until all four external reservations are genuine. Preserve that exit code as Wave-0 evidence and continue with AMD-first local work.

- [ ] **Step 6: Commit validator and honest deferred receipt**

```powershell
git add specs/00022-complete-requirements-remediation/contracts/external-reservation.schema.json scripts/requirements/validate_obj77_reservations.py Tests/test_obj77_external_reservations.py specs/00022-complete-requirements-remediation/evidence/external-resource-reservations.json
git commit -m "test(infra): enforce obj77 external reservation gates"
```

---

### Task 2: Wave-0 real-media Ground-Truth registration

**Files:**
- Create: `specs/00022-complete-requirements-remediation/contracts/ground-truth-corpus.schema.json`
- Create: `specs/00022-complete-requirements-remediation/contracts/ground-truth-annotation.schema.json`
- Create: `scripts/validate_obj77_ground_truth.py`
- Create: `Tests/test_obj77_ground_truth_contract.py`
- Evidence: `specs/00022-complete-requirements-remediation/evidence/ground-truth-registration.json`

**Interfaces:**
- Consumes: the current files under the two approved audio/video roots.
- Produces: a hash-bound registration receipt and registration/strict validation.

**Scope:** This task follows the authoritative Task-2 Scope Correction above.
Registration records every currently present file from exactly the two approved
roots. Pending entries are valid Wave-0 facts and carry no invented annotation
or external approval data. A later strict KPI check requires a
hash-bound, verified annotation document.

- [ ] **Step 1: Write focused registration contract tests**

Cover the approved-root-only builder, current-file inventory equality, file
drift, pending acceptance, and strict annotation binding.

- [ ] **Step 2: Implement and run Wave-0 registration**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe scripts\validate_obj77_ground_truth.py --receipt specs\00022-complete-requirements-remediation\evidence\ground-truth-registration.json --register
.\.venv\Scripts\python.exe scripts\validate_obj77_ground_truth.py --receipt specs\00022-complete-requirements-remediation\evidence\ground-truth-registration.json
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_ground_truth_contract.py -q
```

Expected: registration validation and tests exit 0; `--strict` remains
nonzero until a later KPI supplies verified, hash-bound annotations.

- [ ] **Step 3: Record T083 after hash-bound registration**

Commit the schemas, validator, tests and receipt; update only T083 after the
registration receipt validates. Five annotated mixes are A-14 Wave 2 work; ten
clips are V-11/T019 Wave 3 work, not Wave-0 requirements.

---

### Task 3: Close documentation-only Wave 0 and merge it

**Files:**
- Create: `specs/00022-complete-requirements-remediation/evidence/wave-0-unblock-receipt.json`

**Interfaces:**
- Consumes: the truthful Task-1 reservation-status receipt, approved Task-2 Ground-Truth registration and the immutable saved baseline.
- Produces: one Wave-0 gate decision and the integration merge SHA; no product-code change.

- [ ] **Step 1: Verify the Wave-0 branch contains no product-code diff**

```powershell
$base = git merge-base codex/obj77-wave0-foundation 8328d492f8b128b02ae1ce92a0e6e14d999b2af2
git diff --name-only "$base..HEAD" | rg "^(src|backend|PBStudio.UI)/"
```

Expected: no output. Changes under `specs/`, `docs/`, `scripts/requirements/` and contract tests are infrastructure/documentation, not product behavior.

- [ ] **Step 2: Record deferred reservations and validate Ground Truth**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe scripts\requirements\validate_obj77_reservations.py specs\00022-complete-requirements-remediation\evidence\external-resource-reservations.json
.\.venv\Scripts\python.exe scripts\validate_obj77_ground_truth.py --receipt specs\00022-complete-requirements-remediation\evidence\ground-truth-registration.json
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_external_reservations.py Tests\test_obj77_ground_truth_contract.py -q
```

Expected: the reservation validator exits 1 for the four truthfully deferred
external gates; record that exact exit code. Ground-Truth registration and both
contract-test files exit 0. The Wave-0 registration receipt is sufficient here;
strict KPI validation remains a later annotation gate. Reservation status does
not count as final K-16, T003 or D-08 evidence and does not block the AMD-first
Wave-0 merge.

- [ ] **Step 3: Revalidate the saved Wave-0 baseline and SDD state**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe scripts\validate_sdd.py --feature specs\00022-complete-requirements-remediation --phase open
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_requirement_registry.py -q
git diff --check
```

Expected: SDD open-valid, requirement registry green and no whitespace errors. Previously captured baseline failures remain baseline evidence; Wave 0 does not rewrite product code to close them.

- [ ] **Step 4: Create the immutable Wave-0 unblock receipt**

The receipt must contain the current Git SHA, source receipt paths and hashes, exact commands and exit codes, start/end UTC and exactly these decision fields: `resources_reserved: false`, `external_release_gates_deferred: true`, `deferred_external_release_gates: ["intel_directml_system", "nvidia_directml_system", "lm_studio_maintenance_window", "four_hour_stress_window"]`, `reservation_validator_exit_code: 1`, `ground_truth_registered: true`, `product_code_changed: false` and `overall_status: pass_for_wave_0_amd_first`.

- [ ] **Step 5: Commit Wave-0 evidence without changing completed T083**

T083 was already completed by Task 2 and must not be edited again in this step.

```powershell
git add specs/00022-complete-requirements-remediation/evidence/wave-0-unblock-receipt.json
git commit -m "docs(sdd): close obj77 wave0 amd-first foundation"
```

- [ ] **Step 6: Verify the protected source worktree and merge Wave 0**

```powershell
git -C C:\Users\david\Documents\Pb_studio_AMD_version status --short
git switch codex/complete-requirements-remediation
git merge --no-ff codex/obj77-wave0-foundation -m "merge: complete obj77 wave0 foundation"
git rev-parse HEAD
```

Expected: the protected worktree contains only its pre-existing changes; the merge succeeds. Record the integration SHA without marking later live gates complete.

---

### Task 4: Complete the central DirectML contract at the start of Wave 1

**Files:**
- Modify: `src/pb_studio/core/directml_adapter.py:425-488`
- Modify: `Tests/test_obj77_directml_contract.py`

**Interfaces:**
- Consumes: `onnxruntime.SessionOptions` and an instantiated ORT session.
- Produces: `configure_directml_session_options(options) -> options`; `enforce_directml_session(session) -> session` or `DirectMLAdapterError`.

Start this task only after Task 3 merged. Create `codex/obj77-wave1-shared-contracts` from the resulting `codex/complete-requirements-remediation` SHA; do not commit product code on the Wave-0 branch.

- [ ] **Step 1: Run the existing red tests**

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_directml_contract.py -q
```

Expected: three failures for missing `ORT_SEQUENTIAL`, accepted parallel mode and accepted registered CPU provider.

- [ ] **Step 2: Add the exact-provider regression**

```python
def test_enforcer_accepts_exact_directml_provider() -> None:
    session = _Session(["DmlExecutionProvider"], _SessionOptions())
    assert enforce_directml_session(session) is session
    assert session.fallback_disabled is True
```

- [ ] **Step 3: Implement the minimal central fix**

```python
import onnxruntime as ort


def configure_directml_session_options(session_options: Any) -> Any:
    session_options.enable_mem_pattern = False
    session_options.enable_cpu_mem_arena = False
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session_options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    return session_options
```

In `enforce_directml_session`, reject any execution mode other than `ORT_SEQUENTIAL` and require `session.get_providers() == ["DmlExecutionProvider"]` exactly.

- [ ] **Step 4: Run focused tests and compile**

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_directml_contract.py Tests\test_directml_motion_contract.py Tests\test_c01_semantic_audio_directml.py -q
.\.venv\Scripts\python.exe -m py_compile src\pb_studio\core\directml_adapter.py
```

Expected: all focused tests pass and compilation exits 0.

- [ ] **Step 5: Run the Iron-Rule scan and commit**

```powershell
rg -n "CUDAExecutionProvider|ROCMExecutionProvider|torch\.cuda|pynvml" src backend
git diff --check
git add src/pb_studio/core/directml_adapter.py Tests/test_obj77_directml_contract.py
git commit -m "fix(core): enforce sequential directml-only sessions"
```

Expected scan: no new prohibited runtime inference path.

---

### Task 5: Implement and unit-test the matrix runner before Candidate-Freeze

**Files:**
- Create: `scripts/directml_matrix/probe.py`
- Create: `scripts/directml_matrix/run.ps1`
- Create: `scripts/directml_matrix/evidence.schema.json`
- Create: `Tests/test_obj77_directml_matrix.py`
- Evidence: `specs/00022-complete-requirements-remediation/evidence/directml-matrix/`

**Interfaces:**
- Consumes: `enumerate_dxgi_adapters()`, expected vendor, expected Git SHA, model manifest and real media manifest.
- Produces: `select_expected_adapter(adapters, expected_vendor) -> DirectMLAdapter` and one hash-bound evidence bundle per vendor.

Execute this task in the local AMD preparation wave. Commit its code and unit tests before any matrix execution. The local RX 7800 XT execution occurs in Task 7 only after all three live-gate toolsets are committed; Intel/NVIDIA execution is Task 9. A Wave-0 reservation status is never hardware evidence.

- [ ] **Step 1: Write failing vendor-selection tests**

```python
from pb_studio.core.directml_adapter import DirectMLAdapter


def make_adapter(*, vendor_id: int, is_software: bool) -> DirectMLAdapter:
    return DirectMLAdapter(
        device_id=0,
        luid="0x00000000_0x00000001",
        name="contract-adapter",
        vendor_id=vendor_id,
        device_id_pci=1,
        dedicated_vram_bytes=4 * 1024**3,
        shared_system_memory_bytes=0,
        is_software=is_software,
        is_discrete=not is_software,
        high_performance_preferred=not is_software,
        selection_policy="matrix",
        selection_reason="contract-test",
    )


@pytest.mark.parametrize(
    ("vendor", "vendor_id"),
    [("AMD", 0x1002), ("Intel", 0x8086), ("NVIDIA", 0x10DE)],
)
def test_select_expected_real_adapter(vendor: str, vendor_id: int) -> None:
    adapter = make_adapter(vendor_id=vendor_id, is_software=False)
    assert select_expected_adapter([adapter], vendor).vendor_id == vendor_id


def test_rejects_software_adapter() -> None:
    adapter = make_adapter(vendor_id=0x1414, is_software=True)
    with pytest.raises(MatrixContractError, match="real hardware"):
        select_expected_adapter([adapter], "Intel")
```

- [ ] **Step 2: Run tests and verify failure**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_directml_matrix.py -q
```

- [ ] **Step 3: Implement isolated vendor selection and receipt generation**

```python
VENDOR_IDS = {"AMD": 0x1002, "Intel": 0x8086, "NVIDIA": 0x10DE}


def select_expected_adapter(adapters: Sequence[DirectMLAdapter], vendor: str) -> DirectMLAdapter:
    expected_id = VENDOR_IDS[vendor]
    candidates = [
        item for item in adapters
        if item.vendor_id == expected_id and not item.is_software
    ]
    if not candidates:
        raise MatrixContractError(f"no real hardware adapter for {vendor}")
    return max(candidates, key=lambda item: item.dedicated_vram_bytes)
```

The runner must create RAFT, SigLIP, Moondream and MDX sessions with the shared session options, run five cold/warm repetitions on real manifest-bound media, verify the provider list after session creation, and write `machine.json`, `runtime.json`, `assets.json`, `session-contract.json`, `runs.jsonl`, `errors.jsonl` and a SHA-256 `manifest.json`.

- [ ] **Step 4: Validate and commit the runner**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_directml_matrix.py Tests\test_obj77_directml_contract.py -q
git add scripts/directml_matrix Tests/test_obj77_directml_matrix.py
git commit -m "test(core): add portable directml hardware matrix"
```

The commit must contain every runner file used by later local and external
execution. No matrix code may change after this commit without invalidating
the later local receipt and repeating Task 7.

---

### Task 6: Implement and dry-verify the LM-Studio/Hermes harness before Candidate-Freeze

**Files:**
- Create: `scripts/diagnostics/obj77_lmstudio_window.ps1`
- Create: `Tests/test_obj77_lmstudio_window_contract.py`
- Modify: `scripts/diagnostics/verify_video_resume_live.ps1`
- Evidence: `specs/00022-complete-requirements-remediation/evidence/lmstudio-live/`

**Interfaces:**
- Consumes: exact watchdog PID/start time/path and the existing live-resume contract.
- Produces: committed, statically tested `Snapshot/Pause/Verify/Restore` tooling; no live maintenance evidence yet.

Execute this task in the local AMD preparation wave. Implement and commit every harness and verifier change before Candidate-Freeze. `Snapshot` is the only allowed runtime operation here; the authorized `Pause/Verify/Restore` sequence is Task 10.

- [ ] **Step 1: Write static safety tests before process-control code**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/diagnostics/obj77_lmstudio_window.ps1"


def test_maintenance_script_forbids_wildcard_process_stop() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Stop-Process -Name" not in source
    assert "taskkill /IM" not in source
    assert "lms server status" not in source
    assert "StartTime.ToUniversalTime().Ticks" in source
    assert "-ApprovalReceipt" in source
```

- [ ] **Step 2: Run and verify failure because the script is absent**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_lmstudio_window_contract.py -q
```

- [ ] **Step 3: Implement four explicit operations**

```powershell
[ValidateSet('Snapshot','Pause','Verify','Restore')]
[string]$Operation,
[string]$ApprovalReceipt,
[string]$ProjectPath,
[int]$ClipId
```

`Snapshot` records the exact watchdog process and HTTP model state. `Pause` requires an authorized receipt and stops only the PID whose executable, script path and start ticks match the snapshot. `Verify` invokes `verify_video_resume_live.ps1`, then Chat and Brain-Explain product calls, and requires terminal SSE plus provider/model receipts. `Restore` runs the recorded Hermes service script, restores context `65536` and parallelism `1`, checks SearXNG, restarts one hidden watchdog process, waits two polling intervals and verifies the final state.

- [ ] **Step 4: Extend the live resume verifier fail-closed**

Require nonempty tags, caption stage `completed`, the expected `tag_source`, identical persisted tags and truth hash after backend restart, and no second caption attempt during the resume run. Any mismatch exits nonzero.

- [ ] **Step 5: Run dry safety verification**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_lmstudio_window_contract.py -q
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostics\obj77_lmstudio_window.ps1 -Operation Snapshot
```

Snapshot must not stop, load or unload anything.

- [ ] **Step 6: Commit the dry-verified harness before Candidate-Freeze**

```powershell
git add scripts/diagnostics/obj77_lmstudio_window.ps1 scripts/diagnostics/verify_video_resume_live.ps1 Tests/test_obj77_lmstudio_window_contract.py
git commit -m "test(video): add reversible lm studio live harness"
```

No LM process may be stopped and no live receipt may be claimed in this local
task. No harness code may change after Candidate-Freeze.

---

### Task 7: Implement the stress worker and pass local Canary/Soak before Candidate-Freeze

**Files:**
- Create: `scripts/qa/stress_receipt.py`
- Create: `scripts/qa/execute_4h_stress_test.py`
- Create: `scripts/qa/run_4h_stress.ps1`
- Create: `Tests/test_obj77_stress_worker.py`
- Modify: `scripts/owned_runtime_process.ps1:105-109`
- Modify: `scripts/qa/stress_4h.bat`
- Modify: `scripts/qa/check_stress.bat`
- Evidence: `specs/00022-complete-requirements-remediation/evidence/stress-4h/`

**Interfaces:**
- Consumes: duration, expected Git SHA, real-media manifest, receipt path, backend URL and the enforced VRAM environment.
- Produces: atomic version-1 stress receipt; process exit 0 only when all release invariants pass.

Execute this task in the local AMD preparation wave. First implement, test and commit the worker and launchers; then execute the 15-minute Canary, 60-minute Soak and local AMD matrix against that unchanged committed HEAD before Candidate-Freeze. The real 14,400-second run is Task 12 and cannot start here.

- [ ] **Step 1: Write guard tests**

```python
def test_release_config_requires_exact_4096_mb() -> None:
    config = StressConfig(
        duration_seconds=14400,
        forced_vram_mb=4000,
        expected_git_sha="a" * 40,
        media_manifest=Path("media.json"),
        receipt_path=Path("receipt.json"),
    )
    with pytest.raises(StressContractError, match="exactly 4096"):
        validate_release_config(config)


def test_release_config_requires_four_hours() -> None:
    config = StressConfig(
        duration_seconds=14399,
        forced_vram_mb=4096,
        expected_git_sha="a" * 40,
        media_manifest=Path("media.json"),
        receipt_path=Path("receipt.json"),
    )
    with pytest.raises(StressContractError, match="at least 14400"):
        validate_release_config(config)
```

Add tests for unmanifested media, early exit, missing LHM telemetry, timeout, OOM, forbidden provider, database/FAISS/sidecar hash drift and atomic receipt replacement.

- [ ] **Step 2: Run tests and verify failure**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_stress_worker.py -q
```

- [ ] **Step 3: Implement immutable configuration and hard guards**

```python
@dataclass(frozen=True)
class StressConfig:
    duration_seconds: int
    forced_vram_mb: int
    expected_git_sha: str
    media_manifest: Path
    receipt_path: Path
    backend_url: str = "http://127.0.0.1:8765"


def validate_release_config(config: StressConfig) -> None:
    if config.duration_seconds < 14400:
        raise StressContractError("release duration must be at least 14400 seconds")
    if config.forced_vram_mb != 4096:
        raise StressContractError("forced VRAM must be exactly 4096 MB")
```

The worker must verify `/health/vram` reports 4096 before work, use a monotonic deadline, emit a heartbeat at least every 60 seconds, run only productive APIs on manifest-bound real media, capture provider/stage/artifact receipts and LHM/RSS/VRAM samples, perform periodic controlled backend restart/resume, and fail immediately on every guarded condition.
`run_4h_stress.ps1` must require `-ExpectedGitSha` and fail before work if the
current Git SHA or any tracked code/config path differs from it.

- [ ] **Step 4: Implement atomic receipt validation**

Write to `receipt_path.with_suffix(receipt_path.suffix + ".tmp")`, flush and `os.fsync`, then `os.replace`. Receipt validation requires Git/config/asset/media hashes, GPU/LUID/driver, runtime versions, start/end timestamps, raw samples, error journal, minimum/median/P95/maximum and elapsed monotonic seconds `>=14400` in release mode.

- [ ] **Step 5: Replace the ignored worker path and false-success launchers**

Change `scripts/owned_runtime_process.ps1` from `src\tools\execute_4h_stress_test.py` to `scripts\qa\execute_4h_stress_test.py`. `stress_4h.bat` must require the expected Git SHA as `%1`, set `PB_STUDIO_FORCED_VRAM=4096`, pass that SHA to `run_4h_stress.ps1` synchronously and propagate its exit code. `check_stress.bat` must validate the final receipt against the same expected SHA; process presence and a started flag are not PASS conditions.

- [ ] **Step 6: Run the worker unit tests**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_stress_worker.py -q
```

Expected: unit tests pass before the worker is committed.

- [ ] **Step 7: Commit worker, launchers and tests**

```powershell
git add scripts/qa/stress_receipt.py scripts/qa/execute_4h_stress_test.py scripts/qa/run_4h_stress.ps1 scripts/qa/stress_4h.bat scripts/qa/check_stress.bat scripts/owned_runtime_process.ps1 Tests/test_obj77_stress_worker.py
git commit -m "test(infra): prepare four-hour 4096mb stress gate"
```

No stress code may change after this commit without repeating the following
local executions.

- [ ] **Step 8: Run all pre-freeze local live gates on the committed HEAD**

```powershell
$localCandidateSha = git rev-parse HEAD
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\directml_matrix\run.ps1 -ExpectedVendor AMD -ExpectedGitSha $localCandidateSha
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\qa\run_4h_stress.ps1 -DurationSeconds 900 -Mode Canary -ExpectedGitSha $localCandidateSha
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\qa\run_4h_stress.ps1 -DurationSeconds 3600 -Mode Soak -ExpectedGitSha $localCandidateSha
```

Expected: RX 7800 XT matrix, 15-minute Canary and 60-minute Soak pass with
receipts referencing `$localCandidateSha`. Keep those receipts uncommitted for
Task 13. Any code/config change requires repeating this step.

---

### Task 8: Freeze the tested AMD candidate and open external acceptance

**Files:**
- Create: `specs/00022-complete-requirements-remediation/evidence/external-acceptance-reservations.json`
- Create: `specs/00022-complete-requirements-remediation/evidence/external-acceptance-preflight.json`

**Interfaces:**
- Consumes: every green master-plan non-external/local-AMD gate, committed tooling from Tasks 5-7 and green uncommitted AMD/Canary/Soak receipts from Task 7.
- Produces: immutable `tested_candidate_sha` and a fresh OR-363 preflight whose reservation validator exits 0 for exactly Intel, NVIDIA, LM window and stress window.

- [ ] **Step 1: Prove the local AMD candidate is complete and clean**

Run the complete local Python, C#, WPF, OpenAPI, GUI, KPI, store, SDD and RX
7800 XT gates required by the master plan. Verify that all matrix, LM-harness
and stress-worker files are committed and that every remaining diff is limited
to immutable Task-7 evidence paths.

- [ ] **Step 2: Freeze the exact tested candidate SHA**

```powershell
$testedCandidateSha = git rev-parse HEAD
git diff --name-only
git show --format=fuller --no-patch $testedCandidateSha
```

Expected: `$testedCandidateSha` equals the SHA in all Task-7 AMD/Canary/Soak
receipts, and diff output contains evidence paths only. Record that SHA plus
config, asset and media-manifest hashes. From this point through Task 12,
product, runner, harness, worker, tests and configuration are immutable.

- [ ] **Step 3: Create a fresh external-acceptance reservation receipt**

The new receipt must contain current, concrete owner, machine/provider,
approval scope and UTC window data for all four resources. It does not rewrite
the Wave-0 deferred receipt.

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe scripts\requirements\validate_obj77_reservations.py specs\00022-complete-requirements-remediation\evidence\external-acceptance-reservations.json
```

Expected: exit 0 before the external phase starts. Any other exit code blocks
Tasks 9-12 only; it never invalidates Wave 0 or completed local AMD work.

- [ ] **Step 4: Create and validate the external-acceptance preflight**

Record `tested_candidate_sha`, the fresh receipt path/hash, validator exit 0,
all local gate receipt hashes, start/end UTC and
`overall_status: ready_for_external_acceptance`. Keep these new evidence files
uncommitted until Task 13 so `HEAD` remains exactly `tested_candidate_sha`.

---

### Task 9: Execute Intel and NVIDIA DirectML on the frozen candidate

**Files:**
- Evidence only: `specs/00022-complete-requirements-remediation/evidence/directml-matrix/intel/`
- Evidence only: `specs/00022-complete-requirements-remediation/evidence/directml-matrix/nvidia/`

**Interfaces:**
- Consumes: Task-8 preflight and the committed runner from Task 5.
- Produces: real Intel and NVIDIA receipts bound to `tested_candidate_sha`; no code change.

- [ ] **Step 1: Export and verify the frozen source tree**

Transport an archive produced from `tested_candidate_sha` to a physical Intel
Windows system and either a physical NVIDIA Windows system or an approved
Azure `NVadsA10_v5` Windows VM. Each machine must independently verify the Git
SHA, PCI vendor ID, LUID, driver and non-software adapter status.

- [ ] **Step 2: Run the unchanged matrix runner**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\directml_matrix\run.ps1 -ExpectedVendor Intel -ExpectedGitSha $testedCandidateSha
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\directml_matrix\run.ps1 -ExpectedVendor NVIDIA -ExpectedGitSha $testedCandidateSha
```

Expected: exact DML provider, five cold/warm runs and zero errors per vendor.
Copy receipts back without committing or changing code.

---

### Task 10: Execute T003 in the authorized LM-Studio window

**Files:**
- Evidence only: `specs/00022-complete-requirements-remediation/evidence/lmstudio-live/t003/`

**Interfaces:**
- Consumes: Task-8 preflight, committed Task-6 harness, approved QC project and real clip.
- Produces: T003 product, restart/resume and Hermes-restore receipts bound to `tested_candidate_sha`; no code change.

- [ ] **Step 1: Reconfirm the frozen candidate and approved window**

Require `git rev-parse HEAD == tested_candidate_sha`, no diff under `src/`,
`backend/`, `PBStudio.UI/`, `scripts/` or `Tests/`, and a still-current LM
window in the Task-8 receipt.

- [ ] **Step 2: Execute Pause, Verify and Restore**

```powershell
$reservation = Get-Content -Raw specs\00022-complete-requirements-remediation\evidence\external-acceptance-reservations.json | ConvertFrom-Json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostics\obj77_lmstudio_window.ps1 -Operation Pause -ApprovalReceipt specs\00022-complete-requirements-remediation\evidence\external-acceptance-reservations.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostics\obj77_lmstudio_window.ps1 -Operation Verify -ApprovalReceipt specs\00022-complete-requirements-remediation\evidence\external-acceptance-reservations.json -ProjectPath $reservation.lm_window.qc_project_path -ClipId $reservation.lm_window.real_clip_id
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\diagnostics\obj77_lmstudio_window.ps1 -Operation Restore -ApprovalReceipt specs\00022-complete-requirements-remediation\evidence\external-acceptance-reservations.json
```

Expected: T003 passes, persisted tags and truth hash survive restart without a
second caption attempt, and Hermes/SearXNG/watchdog state is fully restored.
Keep receipts uncommitted for Task 13.

---

### Task 11: Execute the separately approved T019 ten-clip Canary

**Files:**
- Evidence only: `specs/00022-complete-requirements-remediation/evidence/lmstudio-live/t019/`

**Interfaces:**
- Consumes: validated T003 PASS from Task 10 and a separate explicit T019 Go.
- Produces: ten of ten clip receipts with stable stage hashes bound to `tested_candidate_sha`; no code change.

- [ ] **Step 1: Validate T003 and obtain the separate Go**

Do not infer approval from the LM maintenance receipt. Without both a valid
T003 receipt and separate T019 Go, stop only this task and final convergence;
completed local AMD work remains valid.

- [ ] **Step 2: Run exactly the ten-clip Canary**

Use only the ten manifest-bound real clips approved for T019. Require 10/10
complete receipts, stable stage hashes, correct provider/model IDs, restart
parity and zero silent fallback. No bulk reanalysis may begin before this PASS.

---

### Task 12: Execute the real 14,400-second 4096-MB stress gate

**Files:**
- Evidence only: `specs/00022-complete-requirements-remediation/evidence/stress-4h/release/`

**Interfaces:**
- Consumes: Task-8 preflight, committed Task-7 worker and its green Canary/Soak receipts.
- Produces: real D-08 release receipt bound to `tested_candidate_sha`; no code change.

- [ ] **Step 1: Reconfirm the frozen candidate and stress window**

Require the exact candidate SHA, no code/config drift, valid Canary/Soak
receipts and a still-current stress reservation from Task 8.

- [ ] **Step 2: Run and validate the real release gate**

```powershell
scripts\qa\stress_4h.bat $testedCandidateSha
scripts\qa\check_stress.bat $testedCandidateSha
```

Expected: measured duration at least 14,400 seconds, forced VRAM exactly 4096
MB, no OOM/deadlock/data loss/silent fallback, integrity hashes unchanged or
transactionally advanced, and a valid receipt referencing
`tested_candidate_sha`. Keep it uncommitted for Task 13.

---

### Task 13: Final blocker-evidence convergence

**Files:**
- Modify: `specs/00022-complete-requirements-remediation/tasks.md`
- Create: `specs/00022-complete-requirements-remediation/evidence/blocker-closure-manifest.json`
- Modify: `C:\Users\david\Brain\10_Projects\PB_studio\log.md`

**Interfaces:**
- Consumes: the Wave-0 receipt, Task-8 preflight and green live receipts from Tasks 9-12.
- Produces: a later evidence commit and one hash manifest that close only the blocker-related tasks whose full acceptance criteria passed while preserving `tested_candidate_sha` as the executed code identity.

Start Task 13 only after Tasks 9-12 pass. It is the final release-convergence gate and cannot bypass any unchanged OR-363 acceptance criterion.

- [ ] **Step 1: Verify every external receipt against `tested_candidate_sha`**

All Ground-Truth, DirectML, LM-Studio, T019 and stress evidence must reference the exact `tested_candidate_sha`, config hash and asset manifest hash recorded by Task 8. The later evidence-commit SHA is allowed to differ, but a receipt referencing any other tested code SHA cannot close the gate. Verify that no product, runner, harness, worker, test or config path differs from `tested_candidate_sha`.

- [ ] **Step 2: Run focused contract tests**

```powershell
$env:PYTHONPATH = "src;."
.\.venv\Scripts\python.exe -m pytest Tests\test_obj77_external_reservations.py Tests\test_obj77_ground_truth_contract.py Tests\test_obj77_directml_contract.py Tests\test_obj77_directml_matrix.py Tests\test_obj77_lmstudio_window_contract.py Tests\test_obj77_stress_worker.py -q
```

- [ ] **Step 3: Run the complete post-blocker verification matrix**

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest Tests -q
dotnet test
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release
.\.venv\Scripts\python.exe scripts\validate_sdd.py --feature specs\00022-complete-requirements-remediation --phase open
git diff --check
git status --short --branch
```

Expected: Python and C# suites green, WPF Release 0 errors/0 warnings, SDD open-valid, no diff errors, and only uncommitted Task-7-to-Task-12 evidence plus the intended task/manifest updates changed. No executed code or configuration differs from `tested_candidate_sha`.

- [ ] **Step 4: Create the blocker-closure manifest**

The manifest lists every source receipt path and SHA-256, exact command, exit code, start/end UTC, `tested_candidate_sha`, later evidence-commit parent, relevant wave merge SHA and an individual status for Ground Truth, external preflight, AMD/Intel/NVIDIA DirectML, T003 live resume, Hermes restore, T019 10/10 and D-08 stress. It must not rewrite `wave-0-prerequisites.json` or hide an open item behind an aggregate PASS.

- [ ] **Step 5: Update only genuinely completed task checkboxes**

T062 changes to `[X]` only after all three real hardware receipts pass. T003 and T019 change only after their separate receipts pass in order. T073 changes to `[X]` only after the real 14,400-second receipt passes. T094 remains open until every GUI, KPI, LM-Studio, DirectML and four-hour live gate from the master remediation plan passes; this blocker plan alone cannot close it.

- [ ] **Step 6: Append the Brain log after implementation**

Record the relevant wave SHAs, receipt paths, test totals, remaining master-plan gates and the fact that production remains AMD-only while K-16 is a vendor-neutral ONNX-DirectML contract.

- [ ] **Step 7: Commit the blocker-closure evidence on the final external-acceptance branch**

```powershell
git add specs/00022-complete-requirements-remediation/tasks.md specs/00022-complete-requirements-remediation/evidence/external-acceptance-reservations.json specs/00022-complete-requirements-remediation/evidence/external-acceptance-preflight.json specs/00022-complete-requirements-remediation/evidence/directml-matrix/amd specs/00022-complete-requirements-remediation/evidence/directml-matrix/intel specs/00022-complete-requirements-remediation/evidence/directml-matrix/nvidia specs/00022-complete-requirements-remediation/evidence/lmstudio-live/t003 specs/00022-complete-requirements-remediation/evidence/lmstudio-live/t019 specs/00022-complete-requirements-remediation/evidence/stress-4h specs/00022-complete-requirements-remediation/evidence/blocker-closure-manifest.json
git commit -m "docs(sdd): register obj77 blocker closure evidence"
```

The new commit is an evidence commit, not a new tested candidate. Its manifest
must continue to identify the unchanged `tested_candidate_sha` executed by
Tasks 9-12.

- [ ] **Step 8: Verify the protected source worktree is unchanged**

```powershell
git -C C:\Users\david\Documents\Pb_studio_AMD_version status --short
```

Expected: exactly the pre-existing modified/untracked files; no remediation edit appears there.

- [ ] **Step 9: Return control to the master Wave-6 gate**

Do not merge this branch independently. The master remediation plan merges the final external-acceptance candidate only after its complete Python, C#, WPF, OpenAPI, GUI, KPI, store, SDD and release checks pass.

---

## Required References

- `C:\Users\david\Brain\10_Projects\PB_studio\_wiki\decisions\2026-07-28-onnx-directml-only-inference.md` — accepted DirectML-only inference decision.
- `C:\Users\david\Brain\10_Projects\PB_studio\_wiki\decisions\2026-07-30-runtime-hardware-provider-truth.md` — accepted hardware/provider receipt decision.
- [ONNX Runtime DirectML Execution Provider](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html) — sequential execution and disabled memory-pattern requirements.
- [Microsoft DirectML](https://learn.microsoft.com/en-us/windows/win32/direct3d12/dml-redirect) — DirectX-12 hardware support across AMD, Intel and NVIDIA.
- [Azure NVadsA10 v5](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nvadsa10v5-series) — optional approved NVIDIA A10 Windows capacity.
- [LM Studio CLI](https://lmstudio.ai/docs/cli) — explicit load/unload/server operations; the maintenance harness still uses HTTP for health.
- [GitHub self-hosted runners](https://docs.github.com/en/actions/reference/runners/self-hosted-runners) — optional transport for real external Windows hardware; labels never replace the local PCI-vendor check.

---

## Consulting Gates Applied

1. **Ground Truth:** T083 requires the hash-bound Wave-0 registration receipt;
   later strict KPI use requires hash-bound verified annotations.
2. **K-16 scope:** Vendor-neutral ONNX-DirectML contract on AMD/Intel/NVIDIA; full PB Studio remains AMD-only.
3. **LM Studio:** Exact-process maintenance window with complete Hermes restoration; no wildcard process termination and no `lms server status` healthcheck.
4. **Stress:** Tracked worker under `scripts/qa`, exact 4096 MB, 14,400 measured seconds and fail-closed receipt; no started flag as evidence.
5. **AMD-first ordering:** The truthful reservation validator exit 1 is recorded in Wave 0 but does not block its merge or subsequent local RX 7800 XT remediation. Tasks 5-7 commit all live-gate tooling, then complete SHA-bound local AMD proofs before Candidate-Freeze.
6. **External preflight:** Task 8 creates a fresh receipt and requires reservation-validator exit 0 for all four OR-363 resources before any external execution starts.
7. **Frozen execution:** Tasks 9-12 change no code and execute exactly `tested_candidate_sha`; a later evidence commit may differ only because it records the receipts.
8. **T019 ordering:** Task 11 requires T003 PASS and a separate Go, and it must pass before Task 13.
9. **Final release:** Intel/NVIDIA DirectML, the authorized LM-Studio maintenance window and the real four-hour stress receipt remain mandatory final release evidence. OR-363 is unchanged.

## Execution Stop Conditions

- Stop before Task 2 registration if either approved media root is unavailable;
  do not invent annotations. Strict KPI validation stops until verified,
  hash-bound annotation documents exist.
- Do not stop Wave 0 or local RX 7800 XT remediation because the reservation
  validator exits 1; record the four deferred gates exactly and continue.
- Stop before Candidate-Freeze until Task-5-to-Task-7 tooling is committed, the local AMD matrix and stress Canary/Soak have passed against that exact HEAD, and every master-plan non-external/local RX 7800 XT gate is green.
- Stop before Task 9 unless Task 8 produced a fresh receipt and reservation-validator exit 0 for all four external resources.
- Stop before Task 9 if Intel hardware or NVIDIA budget/quota is not approved; this blocks final release only.
- Stop before Task 10 `Pause` if the Hermes maintenance receipt is not authorized; this blocks final release only.
- Stop before Task 11 if T003 has not passed or the separate T019 approval is missing.
- Stop before Task 12 if the 15-minute Canary or 60-minute Soak failed or the four-hour window is no longer current.
- Stop before Task 13 convergence on any nonzero test, invalid receipt, `tested_candidate_sha` mismatch, code/config drift or protected-worktree drift.
