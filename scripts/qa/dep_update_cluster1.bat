@echo off
REM Cluster 1: FastAPI-Stack pip-upgrade + pytest-regression
cd /d "%~dp0"
echo === DEP-UPDATE-CLUSTER1 Start: %date% %time% === > dep1.log

taskkill /F /IM python.exe /T  >nul 2>&1
timeout /T 2 /NOBREAK >nul

call .venv\Scripts\activate.bat

echo --- pip upgrade FastAPI-stack --- >> dep1.log
pip install --upgrade "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "pydantic>=2.9.0" "pydantic-settings>=2.6.0" "httpx>=0.27.2" --quiet >> dep1.log 2>&1

echo --- installed versions --- >> dep1.log
pip show fastapi | findstr "Version" >> dep1.log
pip show uvicorn | findstr "Version" >> dep1.log
pip show pydantic | findstr "Version" >> dep1.log
pip show pydantic-settings | findstr "Version" >> dep1.log
pip show httpx | findstr "Version" >> dep1.log
echo. >> dep1.log

echo --- pytest regression --- >> dep1.log
set PYTHONPATH=src
python -m pytest Tests/ -x -q --tb=line --no-header --ignore=Tests/test_gpu_load_fallback.py --ignore=Tests/test_gpu_temperature_fallback.py 2>&1 >> dep1.log
set RC=%errorlevel%

echo === Exit: %RC% === >> dep1.log
if %RC% NEQ 0 (
    echo PYTEST_FAILED > dep1_done.flag
) else (
    echo PYTEST_OK > dep1_done.flag
)
