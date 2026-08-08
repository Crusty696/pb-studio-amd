@echo off
REM PB Studio Test-Coverage-Run v3 — excluded hardware tests + dedicated config
cd /d "%~dp0"
call "%~dp0scripts\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
"%PBSTUDIO_PYTHON_EXE%" -c "import coverage, pytest_timeout" 2>nul
if errorlevel 1 (
    echo ABORT: coverage oder pytest-timeout fehlt. setup.bat verwenden; dieser Lauf veraendert die Umgebung nicht.
    exit /b 1
)

echo === Coverage Run v3 with pytest-coverage.ini === > coverage_v2_output.log
"%PBSTUDIO_PYTHON_EXE%" -m coverage erase
"%PBSTUDIO_PYTHON_EXE%" -m coverage run -c .coveragerc -m pytest -c pytest-coverage.ini Tests/ -q --tb=no >> coverage_v2_output.log 2>&1
echo. >> coverage_v2_output.log
echo === Top 30 Coverage Report === >> coverage_v2_output.log
"%PBSTUDIO_PYTHON_EXE%" -m coverage report --skip-empty --sort=-cover --fail-under=0 | powershell -NoProfile -Command "$input | Select-Object -First 40" >> coverage_v2_output.log 2>&1
echo. >> coverage_v2_output.log
echo === TOTAL === >> coverage_v2_output.log
"%PBSTUDIO_PYTHON_EXE%" -m coverage report --skip-empty --fail-under=0 | findstr "TOTAL" >> coverage_v2_output.log 2>&1
echo. >> coverage_v2_output.log
echo === Worst 20 Coverage === >> coverage_v2_output.log
"%PBSTUDIO_PYTHON_EXE%" -m coverage report --skip-empty --sort=cover --fail-under=0 | powershell -NoProfile -Command "$input | Select-Object -First 25" >> coverage_v2_output.log 2>&1
echo DONE > coverage_v2_done.flag
