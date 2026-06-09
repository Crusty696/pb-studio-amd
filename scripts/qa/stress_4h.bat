@echo off
REM P1.1 4h-Stress-Test — launches background test
cd /d "%~dp0\..\.."

echo === 4h-Stress-Test Start: %date% %time% === > scripts\qa\stress_4h.log
echo Hinweis: laeuft ~4h, prueft stress_4h.log periodisch >> scripts\qa\stress_4h.log


taskkill /F /IM python.exe /T  >nul 2>&1
ping -n 3 127.0.0.1 >nul

REM Start backend
echo --- Backend launch --- >> scripts\qa\stress_4h.log
start "PB-Backend" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python -m uvicorn backend.main:app --port 8765 > scripts\qa\backend_4h.log 2>&1"
ping -n 36 127.0.0.1 >nul
curl -s -m 5 http://127.0.0.1:8765/health >> scripts\qa\stress_4h.log 2>&1
echo. >> scripts\qa\stress_4h.log

REM Start stress test in background (will run ~4h)
echo --- Stress-Test launch (background) --- >> scripts\qa\stress_4h.log
echo Started at %time% >> scripts\qa\stress_4h.log
start "PB-Stress-4h" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && python src\tools\execute_4h_stress_test.py > scripts\qa\stress_main.log 2>&1"

echo === BACKGROUND-RUN GESTARTET === >> scripts\qa\stress_4h.log
echo Pruefen via: type scripts\qa\stress_main.log >> scripts\qa\stress_4h.log
echo Stop via: KILL-ALL.bat >> scripts\qa\stress_4h.log
echo OK > scripts\qa\stress_4h_started.flag
