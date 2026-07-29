@echo off
REM P1.1 4h-Stress-Test — launches background test
setlocal
cd /d "%~dp0\..\.."
call "%~dp0..\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
for /f "delims=" %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owner_capability.ps1"') do set "PBSTUDIO_OWNER_CAPABILITY=%%I"
if not defined PBSTUDIO_OWNER_CAPABILITY exit /b 1

echo === 4h-Stress-Test Start: %date% %time% === > scripts\qa\stress_4h.log
echo Hinweis: laeuft ~4h, prueft logs\stress_main.stdout.log periodisch >> scripts\qa\stress_4h.log


ping -n 3 127.0.0.1 >nul

REM Start backend
echo --- Backend launch --- >> scripts\qa\stress_4h.log
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Start -Kind Backend -StateName stress_4h_backend -WindowStyle Minimized -LogName backend_4h >> scripts\qa\stress_4h.log 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%
ping -n 36 127.0.0.1 >nul
curl -s -m 5 http://127.0.0.1:8765/health >> scripts\qa\stress_4h.log 2>&1
echo. >> scripts\qa\stress_4h.log

REM Start stress test in background (will run ~4h)
echo --- Stress-Test launch (background) --- >> scripts\qa\stress_4h.log
echo Started at %time% >> scripts\qa\stress_4h.log
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Start -Kind Stress -StateName stress_4h_worker -WindowStyle Minimized -LogName stress_main >> scripts\qa\stress_4h.log 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%

echo === BACKGROUND-RUN GESTARTET === >> scripts\qa\stress_4h.log
echo Pruefen via: type logs\stress_main.stdout.log >> scripts\qa\stress_4h.log
echo Stop worker: powershell -File scripts\owned_runtime_process.ps1 -Operation Stop -Kind Stress -StateName stress_4h_worker -StopMode Crash >> scripts\qa\stress_4h.log
echo Stop backend: powershell -File scripts\owned_runtime_process.ps1 -Operation Stop -Kind Backend -StateName stress_4h_backend -StopMode Crash >> scripts\qa\stress_4h.log
echo OK > scripts\qa\stress_4h_started.flag
