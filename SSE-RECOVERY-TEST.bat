@echo off
REM SSE-Recovery + Visual Review Test — full autonomous run
cd /d "%~dp0"

REM Pruefe ob portables .NET SDK vorhanden ist und konfiguriere Umgebung
if exist "%~dp0tools\dotnet\dotnet.exe" (
    set "DOTNET_ROOT=%~dp0tools\dotnet"
    set "PATH=%~dp0tools\dotnet;%PATH%"
    echo [INFO] Nutze portables .NET SDK unter tools\dotnet.
)

echo === SSE-Recovery-Test Start: %date% %time% ===  > sse_test.log

REM Kill any leftover python
taskkill /F /IM python.exe /T  >nul 2>&1
taskkill /F /IM PBStudio.UI.exe /T >nul 2>&1
ping -n 3 127.0.0.1 >nul

REM === Phase 1: Build ===
echo --- Phase 1: dotnet build Release --- >> sse_test.log
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --verbosity minimal >> sse_test.log 2>&1
if errorlevel 1 (
    echo BUILD_FAILED > sse_test_done.flag
    echo *** BUILD FAILED *** >> sse_test.log
    exit /b 1
)
echo Build OK >> sse_test.log

REM === Phase 2: Launch Backend in background ===
echo --- Phase 2: Backend launch --- >> sse_test.log
start "PB-Backend" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && .venv\Scripts\python.exe -m uvicorn backend.main:app --port 8765"
echo Waiting 30s for backend ready... >> sse_test.log
ping -n 31 127.0.0.1 >nul

REM Health-Check
curl -s -m 5 http://127.0.0.1:8765/health >> sse_test.log 2>&1
echo. >> sse_test.log
echo Backend health probed >> sse_test.log

REM === Phase 3: Launch WPF App in background ===
echo --- Phase 3: WPF launch --- >> sse_test.log
start "PB-UI" /MIN "PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe"
echo Waiting 15s for app ready... >> sse_test.log
ping -n 16 127.0.0.1 >nul

REM === Phase 4: Kill backend, wait for overlay (5 attempts × 3-30s) ===
echo --- Phase 4: Kill backend --- >> sse_test.log
echo Killing python.exe at %time% >> sse_test.log
taskkill /F /IM python.exe /T  >>sse_test.log 2>&1
echo Waiting 25s for overlay to trigger (5 attempts at 3s/6s/12s/24s)... >> sse_test.log
ping -n 26 127.0.0.1 >nul

REM === Phase 5: Take screenshot via PowerShell (overlay should be visible) ===
echo --- Phase 5: Screenshot 1 (overlay visible) --- >> sse_test.log
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('sse_screenshot_overlay.png'); $bmp.Dispose(); $g.Dispose(); Write-Output 'Screenshot1 saved'" >> sse_test.log 2>&1

REM === Phase 6: Restart backend, wait, screenshot 2 (overlay gone) ===
echo --- Phase 6: Restart backend --- >> sse_test.log
start "PB-Backend2" /MIN cmd /c "call .venv\Scripts\activate.bat && set PYTHONPATH=src && .venv\Scripts\python.exe -m uvicorn backend.main:app --port 8765"
echo Waiting 30s for backend ready + reconnect... >> sse_test.log
ping -n 31 127.0.0.1 >nul

echo --- Phase 7: Screenshot 2 (overlay should be gone) --- >> sse_test.log
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('sse_screenshot_recovered.png'); $bmp.Dispose(); $g.Dispose(); Write-Output 'Screenshot2 saved'" >> sse_test.log 2>&1

REM === Phase 8: Cleanup ===
echo --- Phase 8: Cleanup --- >> sse_test.log
taskkill /F /IM PBStudio.UI.exe /T >nul 2>&1
taskkill /F /IM python.exe /T >nul 2>&1

echo === DONE at %date% %time% === >> sse_test.log
echo OK > sse_test_done.flag
