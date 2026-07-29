@echo off
REM Visual review: backend up, app visible, then kill backend, capture overlay
setlocal
cd /d "%~dp0"
call "%~dp0..\runtime_contract.bat"
if errorlevel 1 exit /b %ERRORLEVEL%
for /f "delims=" %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owner_capability.ps1"') do set "PBSTUDIO_OWNER_CAPABILITY=%%I"
if not defined PBSTUDIO_OWNER_CAPABILITY exit /b 1
echo === Visual Review Start: %date% %time% === > vr_test.log

timeout /T 2 /NOBREAK >nul

REM Backend in minimized window
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Start -Kind Backend -StateName sse_visual_backend -WindowStyle Minimized -LogName sse_visual_backend >> vr_test.log 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%
timeout /T 25 /NOBREAK >nul

REM WPF App in NORMAL window (no /MIN)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Start -Kind Ui -StateName sse_visual_ui -WindowStyle Normal >> vr_test.log 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%
timeout /T 12 /NOBREAK >nul

REM Initial screenshot - app visible, no overlay
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr_1_app_normal.png'); $bmp.Dispose(); $g.Dispose();" >> vr_test.log 2>&1

REM Kill backend
echo Killing backend at %time% >> vr_test.log
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Stop -Kind Backend -StateName sse_visual_backend -StopMode Crash >> vr_test.log 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%
echo Waiting 22s for 5-attempt threshold... >> vr_test.log
timeout /T 22 /NOBREAK >nul

REM Screenshot 2: should show overlay
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr_2_overlay_visible.png'); $bmp.Dispose(); $g.Dispose();" >> vr_test.log 2>&1

REM Restart backend
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Start -Kind Backend -StateName sse_visual_backend -WindowStyle Minimized -LogName sse_visual_backend_restart >> vr_test.log 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%
timeout /T 25 /NOBREAK >nul

REM Screenshot 3: overlay should be gone
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bmp.Size); $bmp.Save('vr_3_recovered.png'); $bmp.Dispose(); $g.Dispose();" >> vr_test.log 2>&1

REM Cleanup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Stop -Kind Ui -StateName sse_visual_ui -StopMode Crash >> vr_test.log 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PBSTUDIO_PROJECT_ROOT%\scripts\owned_runtime_process.ps1" -Operation Stop -Kind Backend -StateName sse_visual_backend -StopMode Graceful >> vr_test.log 2>&1

echo === DONE %time% === >> vr_test.log
echo OK > vr_test_done.flag
