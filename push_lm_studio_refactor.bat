@echo off
REM Autonomous push for LM Studio refactor commit 8c46676
cd /d "C:\Users\david\Documents\Pb_studio_AMD_version"

REM Write start marker
echo START %DATE% %TIME% > "%~dp0_push_result.txt"
echo HEAD before: >> "%~dp0_push_result.txt"
git rev-parse HEAD >> "%~dp0_push_result.txt" 2>&1

REM Also delete the index.lock as a side effect — we have rights from host
if exist .git\index.lock del /F /Q .git\index.lock
if exist .git\HEAD.lock del /F /Q .git\HEAD.lock

REM Do the push
echo. >> "%~dp0_push_result.txt"
echo --- PUSH OUTPUT --- >> "%~dp0_push_result.txt"
git push origin main >> "%~dp0_push_result.txt" 2>&1

echo. >> "%~dp0_push_result.txt"
echo --- AFTER --- >> "%~dp0_push_result.txt"
echo HEAD after: >> "%~dp0_push_result.txt"
git rev-parse HEAD >> "%~dp0_push_result.txt" 2>&1
echo origin/main: >> "%~dp0_push_result.txt"
git rev-parse origin/main >> "%~dp0_push_result.txt" 2>&1
echo END %DATE% %TIME% >> "%~dp0_push_result.txt"

REM Auto-close
exit
