@echo off
cd /d "%~dp0"
call "%~dp0scripts\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
del _cowork_run.done 2>nul
echo === pytest Tests/ -x -q (Rerun nach Test-Fix M3) === > _cowork_run.log
"%PBSTUDIO_PYTHON_EXE%" -m pytest Tests/ -x -q >> _cowork_run.log 2>&1
echo PYTEST_EXIT=%ERRORLEVEL% >> _cowork_run.log
echo DONE > _cowork_run.done
exit
