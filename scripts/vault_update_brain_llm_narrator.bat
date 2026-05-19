@echo off
REM ============================================================
REM Iron Rule 11: Obsidian-Vault Update fuer Brain-LLM-Narrator
REM ============================================================
setlocal EnableDelayedExpansion
set "VAULT=C:\Users\david\Brain\10_Projects\PB_studio"
set "REPO=C:\Users\david\Documents\Pb_studio_AMD_version"
set "LOG=%REPO%\vault_update.log"

if not exist "%VAULT%" (
    echo VAULT NOT FOUND at %VAULT% > "%LOG%"
    exit /b 1
)

cd /d "%VAULT%"
call :Main > "%LOG%" 2>&1
echo. >> "%LOG%"
echo === END (exit code %ERRORLEVEL%) === >> "%LOG%"
exit /b %ERRORLEVEL%

:Main
echo === Vault Update: Brain-LLM-Narrator-Track 2026-05-17 ===
echo VAULT=%VAULT%
echo.
dir /b "%VAULT%"
echo.
echo === Updating INDEX.md frontmatter ===
powershell -NoProfile -Command "$f='%VAULT%\INDEX.md'; if (Test-Path $f) { $c=Get-Content $f -Raw; $c2=$c -replace '(?m)^updated:\s*\d{4}-\d{2}-\d{2}.*$','updated: 2026-05-17'; if ($c -ne $c2) { Set-Content -Path $f -Value $c2 -NoNewline; Write-Host 'INDEX.md frontmatter updated' } else { Write-Host 'INDEX.md frontmatter NOT matched - skipped' } } else { Write-Host 'INDEX.md not found' }"
echo.
echo === Appending to log.md ===
powershell -NoProfile -Command "$f='%VAULT%\log.md'; $entry = \"`n## 2026-05-17 - Brain-LLM-Narrator Pilot abgeschlossen`n`n- 3 Commits gepusht: 3436f1d (llm_narrator), 309facd (model_registry), 8458d4c (UI-Tooltip)`n- Spaeterer Follow-up Fix: 5b8b5d3 (CS1503 named-arg)`n- pytest 76/76 gruen (13 neue llm_narrator + 7 neue brain_router_narrative + 56 Regression)`n- WPF Release-Build verifiziert: 0 Warnungen, 0 Fehler (chat_track_wpf_build.log)`n- /brain/explain/{cut_id}?narrative=true liefert jetzt 1-3 Saetze DE-Erklaerung via Ollama (gemma4:latest, fallback minicpm-v:8b-2.6-q4_0)`n- Bei Ollama-Fehler/Timeout: narrative=null, strukturierte Anzeige als Fallback (Iron Rule 10)`n- Beta-Bernoulli-Logik unberuehrt (augmented, not replaced)`n\"; if (Test-Path $f) { Add-Content -Path $f -Value $entry; Write-Host 'log.md appended' } else { Write-Host 'log.md not found' }"
echo.
echo === Vault dir listing nach Update ===
dir /b "%VAULT%"
exit /b 0
