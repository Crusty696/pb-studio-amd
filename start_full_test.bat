@echo off
TITLE PB Studio - Full Autonomous Test
cd /d "%~dp0"
echo Starte PB Studio Test Suite...
powershell -ExecutionPolicy Bypass -File .\run_full_test.ps1
echo.
echo Test beendet. Beliebige Taste zum Schliessen des Fensters...
pause > nul
