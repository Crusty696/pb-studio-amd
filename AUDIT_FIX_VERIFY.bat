@echo off
REM ============================================================
REM AUDIT-FIX VERIFY (AP1-AP5, 2026-06-12)
REM Verifiziert: Python-Syntax, WPF Release-Build, pytest-Suite
REM Output: verify_audit_fix_2026-06-12.log + VERIFY_DONE.flag
REM ============================================================
setlocal
cd /d "%~dp0"
set LOG=verify_audit_fix_2026-06-12.log
set FLAG=VERIFY_DONE.flag
if exist %FLAG% del %FLAG%
echo === AUDIT-FIX VERIFY %DATE% %TIME% === > %LOG%

set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python
set PYTHONPATH=src

echo [1/3] py_compile (backend + src + scripts)... >> %LOG%
%PY% -m compileall -q backend src\pb_studio scripts >> %LOG% 2>&1
if errorlevel 1 ( echo PYCOMPILE: FAIL >> %LOG% & set STEP1=FAIL ) else ( echo PYCOMPILE: OK >> %LOG% & set STEP1=OK )

echo [2/3] dotnet build Release... >> %LOG%
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --nologo >> %LOG% 2>&1
if errorlevel 1 ( echo BUILD: FAIL >> %LOG% & set STEP2=FAIL ) else ( echo BUILD: OK >> %LOG% & set STEP2=OK )

echo [3/3] pytest Tests/ -q ... >> %LOG%
%PY% -m pytest Tests/ -q --no-header >> %LOG% 2>&1
if errorlevel 1 ( echo PYTEST: FAIL >> %LOG% & set STEP3=FAIL ) else ( echo PYTEST: OK >> %LOG% & set STEP3=OK )

echo === RESULT: PYCOMPILE=%STEP1% BUILD=%STEP2% PYTEST=%STEP3% === >> %LOG%
echo %STEP1%/%STEP2%/%STEP3% > %FLAG%
echo === DONE === >> %LOG%
endlocal
