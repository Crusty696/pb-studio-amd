@echo off
setlocal EnableDelayedExpansion
title PB Studio - Auto-QA Loop pytest+commit
cd /d "C:\Users\david\Documents\Pb_studio_AMD_version"

echo ====================================================
echo  PB Studio Auto-QA Loop - Iteration Final
echo ====================================================
echo.

call .venv\Scripts\activate.bat
set PYTHONPATH=src

echo --- Step 1: pytest -x -q ---
pytest Tests/ -x -q
set PYTEST_EXIT=%ERRORLEVEL%

echo.
echo Pytest exit code: %PYTEST_EXIT%
echo.

if not "%PYTEST_EXIT%"=="0" (
    echo ###############################################
    echo # PYTEST FAILED - NO COMMIT, NO PUSH
    echo # Output above shows which test failed.
    echo ###############################################
    echo Press any key to close...
    pause
    exit /b %PYTEST_EXIT%
)

echo ====================================================
echo  Step 2: git add + commit (3 phases)
echo ====================================================
echo.

echo --- Phase X CRITICAL ---
git add backend/app_state.py backend/routers/audio_router.py backend/schemas/audio_schemas.py backend/schemas/video_schemas.py src/pb_studio/data/vector_store.py src/pb_studio/pacing/semantic_matcher.py PBStudio.UI/Services/ApiClient.cs PBStudio.UI/ViewModels/DirectorViewModel.cs Tests/test_motion_schema_forwarding.py Tests/test_video_hash_persist.py Tests/test_clap_wrapper.py
git commit -m "feat(audit-X): 6 CRITICAL fixes (X1..X6: L-VIDEO-2/3, CD-1/2/4, L-FE-13)" -m "Auto-QA-Loop 2026-05-14. X1 peak_motion schema. X2 stems_paths persist. X3 FAISS index unify + atexit leak. X4 video_hash persist. X5 subtrack reload decoupled from is_analyzed. X6 DirectorVM StemsPaths. Plus 3 regression tests (motion_schema, video_hash, clap_wrapper aligned to IRC-1)."
set RC_X=%ERRORLEVEL%
echo Phase X commit exit: %RC_X%
echo.

echo --- Phase Y HIGH UX + Y6 vector_map ---
git add backend/routers/video_router.py backend/routers/project_router.py backend/_brain_singleton.py src/pb_studio/brain/brain_service.py PBStudio.UI/ViewModels/BrainViewModel.cs PBStudio.UI/ViewModels/LearningSessionViewModel.cs PBStudio.UI/Views/TimelineView.xaml.cs PBStudio.UI/Views/LearningSessionDialog.xaml.cs
git commit -m "feat(audit-Y): 7 HIGH UX fixes (Y1..Y7) inkl vector_map" -m "Y1 L-FE-15 TimelineView CompositionTarget unsubscribe. Y2 L-FE-7 BrainVM/LearningSessionVM IDisposable + Dialog OnClosed. Y3 GPU-F2 audio_key out of with_gpu_task. Y4 L-AUDIO-1 StreamingAudioAnalyzer wired for >10min mixes. Y5 L-VIDEO-5 range-bug fix. Y6 L-STATE-2 vector_map populate + tombstone-on-delete. Y7 L-STATE-4 Brain state.db connection reset on project close."
set RC_Y=%ERRORLEVEL%
echo Phase Y commit exit: %RC_Y%
echo.

echo --- Phase Z + IRC ---
git add backend/routers/brain_router.py src/pb_studio/core/model_loader.py src/pb_studio/core/vram_budget_manager.py src/pb_studio/ai/siglip_wrapper.py src/pb_studio/ai/clap_wrapper.py src/pb_studio/video/video_embedder.py src/pb_studio/audio/audio_embedder.py
git commit -m "feat(audit-Z+IRC): 6 backend + 2 iron-rule fixes" -m "Z1 GPU-F3 Brain-Embedder VRAM registered (brain_clap 600MB, brain_siglip2 1100MB). Z2 GPU-F4 brain_router asyncio.to_thread. Z3 M-1 ModelLoader Lock to RLock. Z4 L-AUDIO-4 Spectral band_means/variances/events forwarded. Z5 L-AUDIO-5 subtrack/tempo merge in analyze_audio. Z6 L-VIDEO-4 6 dead schema fields removed. IRC-1 siglip+clap DML-strict. IRC-2 video/audio_embedder torch-directml strict."
set RC_Z=%ERRORLEVEL%
echo Phase Z commit exit: %RC_Z%
echo.

echo ====================================================
echo  Step 3: Final-Report + git push
echo ====================================================
echo.
git add test-report/auto-qa-loop-2026-05-14-FINAL.md test-report/auto-qa-loop-2026-05-14-report.md test-report/auto-qa-loop-2026-05-14-CRITICAL-CORRUPTION.md
git commit -m "docs(audit-2026-05-14): final report + session notes"

echo.
echo --- git log preview (last 5) ---
git log --oneline -5

echo.
echo --- git push ---
git push
set RC_PUSH=%ERRORLEVEL%
echo Push exit: %RC_PUSH%
echo.

echo ====================================================
echo  DONE. Summary:
echo    pytest:    %PYTEST_EXIT%
echo    commit X:  %RC_X%
echo    commit Y:  %RC_Y%
echo    commit Z:  %RC_Z%
echo    push:      %RC_PUSH%
echo ====================================================
echo Press any key to close...
pause
