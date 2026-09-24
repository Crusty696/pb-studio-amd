# Spec 00032 — Verification Evidence (2026-09-20)

## Scope

Full automated and live verification of productive Brain/HIRN paths after explicit user authorization ("mach das").

## 1. Automated Verification (T008)

### Python Backend & DSP Testsuite
- 20 Testdateien für Brain, Pacing, Binding, Verträge und Recovery ausgeführt:
  - `Tests/test_brain_backup.py`
  - `Tests/test_brain_caching.py`
  - `Tests/test_brain_caching_layers.py`
  - `Tests/test_brain_core.py`
  - `Tests/test_brain_cross_modal.py`
  - `Tests/test_brain_embeddings.py`
  - `Tests/test_brain_explain.py`
  - `Tests/test_brain_helpers_new.py`
  - `Tests/test_brain_learned_projector.py`
  - `Tests/test_brain_post_processor.py`
  - `Tests/test_brain_projector_v2.py`
  - `Tests/test_brain_recovery.py`
  - `Tests/test_brain_router.py`
  - `Tests/test_brain_router_narrative.py`
  - `Tests/test_brain_smart_sampler.py`
  - `Tests/test_conftest_brain_reset_is_decoupled.py`
  - `Tests/test_pacing_brain_w5.py`
  - `Tests/test_project_brain_binding.py`
  - `Tests/test_release_repair_brain_runtime_contracts.py`
  - `Tests/test_wpf_brain_load_lifecycle_contract.py`
- **Ergebnis:** `183 passed, 2 warnings in 210.44s (0:03:30)` (0 Failures).

### C# WPF & Transport Testsuite
- Testprojekt: `PBStudio.UI.Tests/PBStudio.UI.Tests.csproj`
- **Ergebnis:** `70 passed, 0 failed, 0 skipped` (net9.0).
- **WPF Release-Build:** `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
  - `0 Warnung(en), 0 Fehler`.

## 2. Live Runtime Verification (T009)

- Ausgeführt via `.agents\skills\run-pb-studio\driver.ps1 -Command smoke`
- **Hardware:** AMD Radeon RX 7800 XT (DirectML Adapter Index 1, LUID 0x00000000_0x00012722, 16177 MB VRAM).
- **Backend-Endpoints:**
  - `GET /health` -> 200 OK (`gpu_available: true`)
  - `GET /gpu/status` -> 200 OK (`directml_active: true`, `monitoring_status: "ready"`)
  - `GET /brain/stats` -> 200 OK (`total_clicks, cold_start_axes, learned_axes, ...`)
  - `POST /shutdown` -> 200 OK (Clean Shutdown, Port 8765 freigegeben).
- **Ergebnis:** `smoke PASS`.
