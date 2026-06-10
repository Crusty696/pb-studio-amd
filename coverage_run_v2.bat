@echo off
REM PB Studio Test-Coverage-Run v3 — excluded hardware tests + dedicated config
cd /d "%~dp0"
taskkill /F /IM python.exe /T >nul 2>&1
timeout /T 2 /NOBREAK >nul

call .venv\Scripts\activate.bat
set PYTHONPATH=src
pip install coverage pytest-timeout --quiet 2>nul

echo === Coverage Run v3 with pytest-coverage.ini === > coverage_v2_output.log
python -m coverage erase
python -m coverage run -c .coveragerc -m pytest -c pytest-coverage.ini Tests/ -q --tb=no >> coverage_v2_output.log 2>&1
echo. >> coverage_v2_output.log
echo === Top 30 Coverage Report === >> coverage_v2_output.log
python -m coverage report --skip-empty --sort=-cover --fail-under=0 | powershell -NoProfile -Command "$input | Select-Object -First 40" >> coverage_v2_output.log 2>&1
echo. >> coverage_v2_output.log
echo === TOTAL === >> coverage_v2_output.log
python -m coverage report --skip-empty --fail-under=0 | findstr "TOTAL" >> coverage_v2_output.log 2>&1
echo. >> coverage_v2_output.log
echo === Worst 20 Coverage === >> coverage_v2_output.log
python -m coverage report --skip-empty --sort=cover --fail-under=0 | powershell -NoProfile -Command "$input | Select-Object -First 25" >> coverage_v2_output.log 2>&1
echo DONE > coverage_v2_done.flag
