# Try LM Studio CLI (lms) - typical install path: %USERPROFILE%\.lmstudio\bin\lms.exe
$outFile = 'C:\Users\david\Documents\Pb_studio_AMD_version\.lms_cli_output.txt'

$lmsCandidates = @(
    "$env:USERPROFILE\.lmstudio\bin\lms.exe",
    "$env:USERPROFILE\.lmstudio\bin\lms.cmd",
    "$env:LOCALAPPDATA\Programs\LM Studio\resources\app\.webpack\main\lms.exe"
)

$lms = $null
foreach ($p in $lmsCandidates) {
    if (Test-Path $p) { $lms = $p; break }
}

# also try PATH
if (-not $lms) {
    try { $found = (Get-Command lms -ErrorAction Stop).Source; if ($found) { $lms = $found } } catch {}
}

if (-not $lms) {
    "lms CLI not found in any of: " + ($lmsCandidates -join '; ') | Out-File $outFile -Encoding UTF8
    Write-Host "lms not found"
    exit 1
}

"--- using lms: $lms" | Out-File $outFile -Encoding UTF8

"--- lms ps (currently loaded)" | Out-File $outFile -Append -Encoding UTF8
& $lms ps 2>&1 | Out-File $outFile -Append -Encoding UTF8

"--- lms ls (all)" | Out-File $outFile -Append -Encoding UTF8
& $lms ls 2>&1 | Out-File $outFile -Append -Encoding UTF8

"--- attempting load qwen3.5-9b-uncensored-hauhaucs-aggressive" | Out-File $outFile -Append -Encoding UTF8
& $lms load qwen3.5-9b-uncensored-hauhaucs-aggressive --gpu max --yes 2>&1 | Out-File $outFile -Append -Encoding UTF8

"--- final lms ps" | Out-File $outFile -Append -Encoding UTF8
& $lms ps 2>&1 | Out-File $outFile -Append -Encoding UTF8

Write-Host "DONE -> $outFile"
