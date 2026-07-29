$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outFile = Join-Path $repoRoot '.lm_minimal.txt'
"PING $(Get-Date)" | Out-File $outFile
"PowerShell version: $($PSVersionTable.PSVersion)" | Out-File $outFile -Append
"User: $env:USERNAME" | Out-File $outFile -Append
$procs = Get-Process -Name lms,powershell,"LM Studio" -ErrorAction SilentlyContinue
"Processes:" | Out-File $outFile -Append
$procs | ForEach-Object { "  $($_.Name) PID=$($_.Id)" } | Out-File $outFile -Append
"DONE" | Out-File $outFile -Append
