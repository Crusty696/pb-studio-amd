@echo off
setlocal EnableDelayedExpansion
set "VAULT=C:\Users\david\Brain\10_Projects\PB_studio"
set "LOG=C:\Users\david\Documents\Pb_studio_AMD_version\vault_fm_fix.log"
cd /d "%VAULT%"
powershell -NoProfile -Command "$f='INDEX.md'; $c=Get-Content $f -Raw; $c2 = $c -replace ""(?m)^updated:\s*'?\d{4}-\d{2}-\d{2}'?.*$"", ""updated: '2026-05-17'""; $c2 = $c2 -replace ""(?m)^active_session:\s*'?\d{4}-\d{2}-\d{2}'?.*$"", ""active_session: '2026-05-17'""; if ($c -ne $c2) { Set-Content -Path $f -Value $c2 -NoNewline; Write-Host 'INDEX.md frontmatter UPDATED' } else { Write-Host 'NO MATCH - dumping first 20 lines:'; Get-Content $f -TotalCount 20 }" > "%LOG%" 2>&1
echo === END === >> "%LOG%"
exit /b 0
