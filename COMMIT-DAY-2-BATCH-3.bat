@echo off
REM Cowork Day 2 Batch 3 — alle heutigen Updates committen
cd /d "%~dp0"

if exist .git\index.lock del /F /Q .git\index.lock

echo === COMMIT Batch 3 ===
echo.

REM 1. Test Coverage Gaps (P3.1)
git add Tests/test_encoder_utils.py Tests/test_cache_manager.py Tests/test_model_loader.py
git commit -m "test(coverage): 36 new tests for encoder_utils, cache_manager, model_loader (P3.1)" -m "P3.1 Test-Coverage-Gap-Filler: 3 neue Test-Files mit 12 Tests pro Modul = 36 neue Tests. encoder_utils: Enums + EncoderConfig + build_args + reset_cache + get_encoder_info + preview/export. cache_manager: init+save+load+exists+invalidate+clear_all+TTL-expiry+corrupt-json. model_loader: ModelType+Spec+register+is_loaded+get_stats+unload_all+singleton. Alle 36 PASS in 2.7s. pytest gesamt: 537 passed / 10 skipped / 0 failed in 71s."

REM 2. Dep Cluster 1 + Release Smoke Expansion
git add requirements.txt verify_release_smoke.ps1
git commit -m "feat: Cluster-1 FastAPI-Stack-Update + Spec-00007-T012 Release-Smoke-Expansion" -m "requirements.txt: fastapi 0.110->0.115, uvicorn 0.28->0.32, pydantic 2.5->2.9, pydantic-settings 2.2->2.6, httpx 0.27->0.27.2 (alle >= bumps). pip-install brachte latest: fastapi 0.136.1, uvicorn 0.47.0, pydantic 2.13.4, pydantic-settings 2.14.1, httpx 0.28.1. pytest regression: 537/0/0 PASS. verify_release_smoke.ps1: +3 Steps (Heartbeat-Probe gegen /health/heartbeat T002, VRAM-Telemetry-Probe gegen /health/vram, Brain-DB-Migration-Check via /brain/stats)."

REM 3. CLAUDE.md + CHANGELOG sync
git add CLAUDE.md CHANGELOG.md run_full_test.ps1
git commit -m "docs: CLAUDE.md + CHANGELOG sync for 2026-05-15 (Day 2 Cowork)" -m "CLAUDE.md: Date 2026-05-11 -> 2026-05-15, Phase aktualisiert, Status 537 passed, Next Task = P1.2 + Cluster-2 + 4h-stress. CHANGELOG.md: 2026-05-15 Sektion prepended (Added Code/Tests, Fixed UI/Test-Infra, Updated Deps, Verified Runtime). run_full_test.ps1: Test-Count-Kommentar 239->537."

REM 4. Verify bats (kept for re-use)
git add SSE-RECOVERY-TEST.bat SSE-VISUAL-V2.bat LOW-VRAM-STRESS.bat KILL-ALL.bat FIX-AND-COMMIT-ALL.bat COMMIT-DAY-2-BATCH-3.bat
git commit -m "chore(infra): verification/maintenance .bat scripts" -m "Self-contained .bat scripts fuer Cowork-Workflow: SSE-RECOVERY-TEST + SSE-VISUAL-V2 fuer Backend-Kill-Test (Spec 00010 T003+T004), LOW-VRAM-STRESS fuer 4GB-Resilience (Spec 00010 T006), KILL-ALL fuer Recovery, FIX-AND-COMMIT-ALL fuer Lock-Recovery + Commit-Replay. Alle mit cd /d %%~dp0 location-independent. COWORK_AUTONOMY_LESSONS Anti-Pattern #1+#2+#3 vermieden."

REM 5. AUTONOMY LESSONS update
git add COWORK_AUTONOMY_LESSONS.md
git commit -m "docs(autonomy): Pattern #13 cmd-variable-expansion ohne setlocal" -m "Neuer Anti-Pattern: !VAR! Syntax in .bat ohne setlocal enabledelayedexpansion expandiert nicht. Konkretes Beispiel: LOW-VRAM-STRESS.bat fand kein Test-Video weil 'Using test video: !TESTVID!' als literal-Text durchlief statt zu expandieren."

echo.
echo === DONE — git log ===
git log --oneline -10
echo.
pause
