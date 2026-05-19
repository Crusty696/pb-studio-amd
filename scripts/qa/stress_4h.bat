@echo off
REM P1.1 4h-Stress-Test — launches background test
cd /d "%~dp0"

echo === 4h-Stress-Test Start: %date% %time% === > stress_4h.log
echo Hinweis: laeuft ~4h, prueft stress_4h.log periodisch >> stress_4h.log

taskkill /F /IM python.exe /T  >nul 2>&1
timeout /T 2 /NOBREAK >nul

REM Start backend
echo --- Backend launch --- >> stress_4h.log
start "PB-Backend" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python -m uvicorn backend.main:app --port 8765 > backend_4h.log 2>&1"
timeout /T 35 /NOBREAK >nul
curl -s -m 5 http://127.0.0.1:8765/health >> stress_4h.log 2>&1
echo. >> stress_4h.log

REM Start stress test in background (will run ~4h)
echo --- Stress-Test launch (background) --- >> stress_4h.log
echo Started at %time% >> stress_4h.log
start "PB-Stress-4h" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python src\tools\execute_4h_stress_test.py > stress_main.log 2>&1"

echo === BACKGROUND-RUN GESTARTET === >> stress_4h.log
echo Pruefen via: type stress_main.log >> stress_4h.log
echo Stop via: KILL-ALL.bat >> stress_4h.log
echo OK > stress_4h_started.flag
