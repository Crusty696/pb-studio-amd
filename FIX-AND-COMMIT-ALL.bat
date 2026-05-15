@echo off
REM PB Studio — Recovery + Alle 8 Commits in einem Klick
REM Behebt: korruptes git-index + stuck lock
REM Faehrt: 8 Commits aus den Cowork-Sessions 2026-05-14/15

cd /d "%~dp0"

echo ============================================================
echo  PB Studio — Recovery + 8 Commits
echo ============================================================
echo Working dir: %CD%
echo.

REM === Phase 1: Recovery (corrupted index) ===
echo --- Phase 1: Git-Index Recovery ---
if exist .git\index.lock (
    del /F /Q .git\index.lock
    echo [1.1] index.lock entfernt
) else (
    echo [1.1] kein index.lock vorhanden
)
if exist .git\index (
    del /F /Q .git\index
    echo [1.2] korruptes index entfernt
)
git read-tree HEAD
if errorlevel 1 (
    echo FATAL: git read-tree fehlgeschlagen
    pause
    exit /b 1
)
echo [1.3] Index aus HEAD wiederhergestellt
git status --short > nul
echo [1.4] git status OK
echo.

REM === Phase 2: 8 Commits ===
echo --- Phase 2: 8 Commits ---

echo [1/8] docs(specs) markers v2
git add specs/00007-release-hardening-ux-polish/tasks.md specs/00009-data-depth-visualization/tasks.md specs/00010-resilience-edge-cases/tasks.md
git commit -m "docs(specs): mark verified-done tasks from cowork audit part 2" -m "Spec 00007 T011 + T013; Spec 00009 T002-T010 (alle in HEAD verifiziert); Spec 00010 T003+T004 implementiert."

echo [2/8] perf(ui) AudioClipList virtualization
git add PBStudio.UI/Views/AudioLibraryView.xaml
git commit -m "perf(ui): AudioClipList virtualization mode = Recycling (T011)" -m "Spec 00007 T011: VirtualizingPanel.IsVirtualizing=True + VirtualizationMode=Recycling fuer AudioClipList (Konsistenz mit VideoClipList)."

echo [3/8] feat(sse) 5-attempt UI-Notify
git add PBStudio.UI/Services/SSEClient.cs
git commit -m "feat(sse): UI-notify after 5 failed reconnects (Spec 00010 T003)" -m "TR-001 implementiert. NotifyUiAfterAttempts=5, IsBackendReachable property, BackendReachabilityChanged event. Rein additiv."

echo [4/8] feat(ui) ConnectionStatus overlay
git add PBStudio.UI/ViewModels/MainViewModel.cs PBStudio.UI/MainWindow.xaml
git commit -m "feat(ui): ConnectionStatus overlay banner (Spec 00010 T004)" -m "MainViewModel IsBackendUnreachable + Subscriber. MainWindow rotes Banner Grid.Row=1 Top, Panel.ZIndex=1000, WifiOff-Icon."

echo [5/8] docs(agents) parallel-subagent rules
git add AGENTS.md
git commit -m "docs(agents): parallele Subagent-Arbeit + Mount-Truncation-Schutz" -m "13 Code-Zonen, Subagent-Brief-Pflichtfelder, bash-redirect Pflicht, Convergence-Protokoll, Skill-Mapping, Spawn-Beispiel."

echo [6/8] feat tab-anim + fix TODOs + chore vulture
git add PBStudio.UI/MainWindow.xaml backend/routers/video_router.py src/pb_studio/pacing/advanced_pacing_engine.py src/pb_studio/core/vram_budget_manager.py src/pb_studio/pacing/clip_selector.py src/pb_studio/services/analysis_service.py src/pb_studio/services/generation_service.py
git commit -m "feat: Spec-00007-T010 tab animations + 2 inline-TODOs + P3.4 vulture-noqa" -m "Tab-Animations: ScaleTransform+Opacity 150ms. video_router.py:348 stale TODO geklaert. advanced_pacing_engine.py:1293 _snap_cuts_to_subtrack_boundaries impl. 4 Vulture-noqa Compat-Param-Kommentare."

echo [7/8] feat+docs+test batch 2
git add src/pb_studio/data/repositories/media_repository.py PBStudio.UI/ViewModels/TimelineViewModel.cs pytest-coverage.ini .coveragerc coverage_run_v2.bat
git commit -m "feat+docs+test: gzip-meta + downsampling marker + coverage hang fix" -m "Spec 00009 T006: _serialize_meta gzip-Wrap >10KB (96.8 percent saving). T008: XML-Doc-Comment ueber UpdateSpectralPoints. P1.5: pytest-coverage.ini + .coveragerc + coverage_run_v2.bat (Hardware-Tests excluded wegen CLR-Deadlock)."

echo [8/8] docs(autonomy) Cowork lessons + IRON RULE 12
git add COWORK_AUTONOMY_LESSONS.md CLAUDE.md
git commit -m "docs(autonomy): COWORK_AUTONOMY_LESSONS.md + CLAUDE.md IRON RULE 12" -m "User-Direktive: 11 Anti-Patterns dokumentiert wo Claude nicht autonom gehandelt hat. Iron Rule 12 verweist auf die Datei."

echo.
echo ============================================================
echo  DONE — git log
echo ============================================================
git log --oneline -12
echo.
echo Press ENTER to close...
pause
