@echo off
REM Auto-push fuer die drei Brain-LLM-Narrator Commits.
REM Erzeugt 2026-05-16, Phase E von "Pilot Brain LLM-Narrator".
cd /d C:\Users\david\Documents\Pb_studio_AMD_version
echo === Local commits ===
git log --oneline HEAD~3..HEAD
echo.
echo === Pushing to origin/main ===
git push origin main
if errorlevel 1 (
    echo PUSH FAILED
    exit /b 1
)
echo.
echo === Remote HEAD ===
git ls-remote origin main
pause
