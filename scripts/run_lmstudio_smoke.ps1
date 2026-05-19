# Run the lmstudio_client smoke test via the venv python, capture output.
$ErrorActionPreference = "Continue"
$out = "C:\Users\david\Documents\Pb_studio_AMD_version\.lmstudio_smoke.txt"
$repo = "C:\Users\david\Documents\Pb_studio_AMD_version"

# Find python — prefer venv if exists
$python = "$repo\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

"=== LM Studio Client Smoke ===" | Out-File $out
"python: $python" | Out-File $out -Append
"timestamp: $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')" | Out-File $out -Append
"" | Out-File $out -Append

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = "$repo\scripts\lmstudio_client_smoke.py"
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WorkingDirectory = $repo
$psi.EnvironmentVariables["PYTHONPATH"] = "$repo\src"
$proc = [System.Diagnostics.Process]::Start($psi)
if ($proc.WaitForExit(180000)) {
    "=== STDOUT ===" | Out-File $out -Append
    $proc.StandardOutput.ReadToEnd() | Out-File $out -Append
    "=== STDERR ===" | Out-File $out -Append
    $proc.StandardError.ReadToEnd() | Out-File $out -Append
    "=== ExitCode: $($proc.ExitCode) ===" | Out-File $out -Append
} else {
    $proc.Kill()
    "TIMEOUT after 180s" | Out-File $out -Append
}
