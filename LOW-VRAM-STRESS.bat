@echo off
REM P1.2 + P3.3: 4GB-VRAM-Stress + VRAMArbiter-Eviction-Verify
setlocal enabledelayedexpansion
cd /d "%~dp0"
call "%~dp0scripts\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
for /f "delims=" %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\owner_capability.ps1"') do set "PBSTUDIO_OWNER_CAPABILITY=%%I"
if not defined PBSTUDIO_OWNER_CAPABILITY exit /b 1
echo === Low-VRAM-Stress Start: %date% %time% === > stress_low.log

ping -n 3 127.0.0.1 >nul

call .venv\Scripts\activate.bat

REM Start backend mit Forced 4GB VRAM Limit
echo --- Backend launch mit PB_STUDIO_FORCED_VRAM=4000 --- >> stress_low.log
set PB_STUDIO_FORCED_VRAM=4000
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\owned_runtime_process.ps1" -Operation Start -Kind Backend -StateName low_vram_backend -WindowStyle Minimized -LogName backend_low >> stress_low.log 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%
ping -n 36 127.0.0.1 >nul

REM Probe health + VRAM telemetry
echo --- /health probe --- >> stress_low.log
curl -s -m 5 http://127.0.0.1:8765/health >> stress_low.log 2>&1
echo. >> stress_low.log
echo --- /health/vram initial --- >> stress_low.log
curl -s -m 5 http://127.0.0.1:8765/health/vram >> stress_low.log 2>&1
echo. >> stress_low.log

REM Pressure: 2 video imports + analyze (SigLIP + RAFT each take ~1-2 GB)
echo --- Pressure phase: 2 video imports --- >> stress_low.log

REM Find a real video file
set "TESTVID="
for /f "delims=" %%I in ('dir /b /s "%~dp0Tests\test_assets\sample.mp4" 2^>nul') do set "TESTVID=%%I"
if "!TESTVID!"=="" (
    for /f "delims=" %%I in ('dir /b /s "%~dp0data\smoke_test_video.mp4" 2^>nul') do set "TESTVID=%%I"
)
if "!TESTVID!"=="" (
    for /f "delims=" %%I in ('dir /b /s "%~dp0data\test_clip.mp4" 2^>nul') do set "TESTVID=%%I"
)
if "!TESTVID!"=="" (
    for /f "delims=" %%I in ('dir /b /s "%~dp0test-report\*.mp4" 2^>nul ^| findstr /v output') do set "TESTVID=%%I"
)
if "!TESTVID!"=="" (
    echo NO TEST VIDEO FOUND — checking common project paths >> stress_low.log
    for /f "delims=" %%I in ('dir /b "%~dp0..\*.mp4" 2^>nul') do set "TESTVID=%%~fI"
)
echo Using test video: !TESTVID! >> stress_low.log

if not "!TESTVID!"=="" (
    powershell -Command "$body = @{paths=@('!TESTVID!')} | ConvertTo-Json; try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/video/import' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 60; Write-Output ($r | ConvertTo-Json -Compress -Depth 3) } catch { Write-Output 'Import failed: $_' }" >> stress_low.log 2>&1
    echo. >> stress_low.log

    REM Trigger analysis (multi-stage GPU load)
    powershell -Command "try { $clips = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/video/clips?page=1&limit=10' -Method Get -TimeoutSec 30; foreach ($c in $clips) { Write-Output ('Analyzing clip ' + $c.id + '...'); try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/video/analyze' -Method Post -ContentType 'application/json' -Body (@{clip_id=$c.id} | ConvertTo-Json) -TimeoutSec 120; Write-Output ('Analysis OK: ' + $r.status) } catch { Write-Output ('Analysis failed: ' + $_) } } } catch { Write-Output ('List failed: ' + $_) }" >> stress_low.log 2>&1
)

echo. >> stress_low.log
echo --- /health/vram after pressure --- >> stress_low.log
curl -s -m 5 http://127.0.0.1:8765/health/vram >> stress_low.log 2>&1
echo. >> stress_low.log

echo --- /health final --- >> stress_low.log
curl -s -m 5 http://127.0.0.1:8765/health >> stress_low.log 2>&1
echo. >> stress_low.log

REM Cleanup
echo --- Cleanup --- >> stress_low.log
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\owned_runtime_process.ps1" -Operation Stop -Kind Backend -StateName low_vram_backend -StopMode Graceful >> stress_low.log 2>&1

echo === DONE %time% === >> stress_low.log
echo OK > stress_low_done.flag
