@echo off
setlocal EnableDelayedExpansion
title PB Studio - Git Recovery + Final Docs Commit
cd /d "C:\Users\david\Documents\Pb_studio_AMD_version"

echo ====================================================
echo  Git Recovery (HEAD truncated, rebase mid-progress)
echo ====================================================
echo.

echo --- Pre-state ---
echo HEAD file content:
type .git\HEAD 2>nul
echo.
echo main ref content:
type .git\refs\heads\main 2>nul
echo.
echo rebase-merge exists?
if exist ".git\rebase-merge" (echo YES - cleaning) else (echo NO)
echo.

echo --- Step 1: Abort any in-progress rebase ---
git rebase --abort 2>nul
echo Rebase aborted (or was already not active)

if exist ".git\rebase-merge" (
    rmdir /s /q ".git\rebase-merge" 2>nul
    echo Forcibly removed .git\rebase-merge
)
if exist ".git\AUTO_MERGE" del /f ".git\AUTO_MERGE" 2>nul
if exist ".git\REBASE_HEAD" del /f ".git\REBASE_HEAD" 2>nul
if exist ".git\MERGE_MSG" del /f ".git\MERGE_MSG" 2>nul
if exist ".git\index.lock" del /f ".git\index.lock" 2>nul
echo.

echo --- Step 2: Fix HEAD pointer (re-attach to main branch) ---
git symbolic-ref HEAD refs/heads/main
echo HEAD now points to refs/heads/main

echo --- Step 3: Reset working tree to main HEAD ---
git reset --hard HEAD
echo.

echo --- Verify log ---
git log --oneline -6
echo.

echo --- Step 4: Stage + commit final docs ---
git add CLAUDE.md CHANGELOG.md sync-brain-vault.bat final-docs-commit.bat git-recovery-and-commit.bat test-report/2026-05-14-AMD-DRIVER-UPDATE-required.md test-report/brain_log_entry_2026-05-14.md test-report/brain_learning_2026-05-14.md test-report/auto-qa-loop-2026-05-14-FINAL.md
git status --short

git commit -m "docs(audit-2026-05-14): CLAUDE.md + CHANGELOG.md + brain-sync + AMF-TODO" -m "Final docs after Audit-Phase X+Y+Z+IRC autonomer run. CLAUDE.md Section 3 auf 2026-05-14 511 pytest pass. CHANGELOG vollstaendiger Audit-Eintrag. sync-brain-vault.bat fuer Obsidian Vault sync. 2026-05-14-AMD-DRIVER-UPDATE-required.md fuer User-Action h264_amf. git-recovery-and-commit.bat zur Wiederherstellung nach mid-rebase HEAD-Truncation."
set RC=%ERRORLEVEL%
echo Commit exit: %RC%

echo.
echo --- Final log ---
git log --oneline -6

echo.
echo --- Push ---
git push origin main
set RCP=%ERRORLEVEL%

echo.
echo ====================================================
echo  Commit: %RC%  Push: %RCP%
echo  HEAD now at:
git rev-parse HEAD
echo ====================================================
echo Press any key to close...
pause
