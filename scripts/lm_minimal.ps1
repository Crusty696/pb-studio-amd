"PING $(Get-Date)" | Out-File "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_minimal.txt"
"PowerShell version: $($PSVersionTable.PSVersion)" | Out-File "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_minimal.txt" -Append
"User: $env:USERNAME" | Out-File "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_minimal.txt" -Append
$procs = Get-Process -Name lms,powershell,"LM Studio" -ErrorAction SilentlyContinue
"Processes:" | Out-File "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_minimal.txt" -Append
$procs | ForEach-Object { "  $($_.Name) PID=$($_.Id)" } | Out-File "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_minimal.txt" -Append
"DONE" | Out-File "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_minimal.txt" -Append
