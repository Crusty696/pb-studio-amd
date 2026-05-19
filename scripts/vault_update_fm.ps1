$ErrorActionPreference = 'Stop'
$vault = 'C:\Users\david\Brain\10_Projects\PB_studio'
$f = Join-Path $vault 'INDEX.md'
$c = Get-Content $f -Raw -Encoding UTF8

# Update updated:
$c2 = $c -replace "(?m)^updated:\s*'?\d{4}-\d{2}-\d{2}'?.*$", "updated: '2026-05-17'"
$c2 = $c2 -replace "(?m)^active_session:\s*'?\d{4}-\d{2}-\d{2}'?.*$", "active_session: '2026-05-17'"

if ($c -ne $c2) {
    Set-Content -Path $f -Value $c2 -NoNewline -Encoding UTF8
    Write-Host 'INDEX.md frontmatter UPDATED'
    Write-Host '--- new first 18 lines ---'
    Get-Content $f -TotalCount 18 -Encoding UTF8
} else {
    Write-Host 'NO MATCH - first 18 lines:'
    Get-Content $f -TotalCount 18 -Encoding UTF8
}
