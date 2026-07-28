@echo off
cd /d C:\Users\david\Documents\Pb_studio_AMD_version
del _cowork_run.done 2>nul
echo === pytest Tests/ -x -q (Rerun nach Test-Fix M3) === > _cowork_run.log
set PYTHONPATH=src
.venv\Scripts\python.exe -m pytest Tests/ -x -q >> _cowork_run.log 2>&1
echo PYTEST_EXIT=%ERRORLEVEL% >> _cowork_run.log
echo DONE > _cowork_run.done
exit
