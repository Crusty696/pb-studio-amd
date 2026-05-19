# Kill any hanging lms.exe processes from earlier scripts, then test runtime select
$ErrorActionPreference = "Continue"
$out = "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_kill_test.txt"

"=== Kill hanging lms.exe processes ===" | Out-File $out
Get-Process -Name lms -ErrorAction SilentlyContinue | ForEach-Object {
    "Killing PID $($_.Id) cmdline: $($_.Path)" | Out-File $out -Append
    Stop-Process -Id $_.Id -Force
}
"--- Done ---" | Out-File $out -Append

# Now test runtime select with timeout (separate process, 30s timeout)
$lms = "$env:USERPROFILE\.lmstudio\bin\lms.exe"
"" | Out-File $out -Append
"=== Test: lms runtime select --help (with 15s timeout) ===" | Out-File $out -Append
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $lms
$psi.Arguments = "runtime select --help"
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$proc = [System.Diagnostics.Process]::Start($psi)
if ($proc.WaitForExit(15000)) {
    "ExitCode: $($proc.ExitCode)" | Out-File $out -Append
    "stdout:" | Out-File $out -Append
    $proc.StandardOutput.ReadToEnd() | Out-File $out -Append
    "stderr:" | Out-File $out -Append
    $proc.StandardError.ReadToEnd() | Out-File $out -Append
} else {
    "TIMEOUT after 15s" | Out-File $out -Append
    $proc.Kill()
}

"" | Out-File $out -Append
"=== Test: lms runtime select VULKAN (with 30s timeout) ===" | Out-File $out -Append
$psi2 = New-Object System.Diagnostics.ProcessStartInfo
$psi2.FileName = $lms
$psi2.Arguments = "runtime select llama.cpp-win-x86_64-vulkan-avx2@2.14.0"
$psi2.RedirectStandardOutput = $true
$psi2.RedirectStandardError = $true
$psi2.UseShellExecute = $false
$psi2.CreateNoWindow = $true
$proc2 = [System.Diagnostics.Process]::Start($psi2)
if ($proc2.WaitForExit(30000)) {
    "ExitCode: $($proc2.ExitCode)" | Out-File $out -Append
    "stdout:" | Out-File $out -Append
    $proc2.StandardOutput.ReadToEnd() | Out-File $out -Append
    "stderr:" | Out-File $out -Append
    $proc2.StandardError.ReadToEnd() | Out-File $out -Append
} else {
    "TIMEOUT after 30s — KILLED" | Out-File $out -Append
    $proc2.Kill()
}

"" | Out-File $out -Append
"=== Verify after switch: lms runtime ls (with 15s timeout) ===" | Out-File $out -Append
$psi3 = New-Object System.Diagnostics.ProcessStartInfo
$psi3.FileName = $lms
$psi3.Arguments = "runtime ls"
$psi3.RedirectStandardOutput = $true
$psi3.RedirectStandardError = $true
$psi3.UseShellExecute = $false
$psi3.CreateNoWindow = $true
$proc3 = [System.Diagnostics.Process]::Start($psi3)
if ($proc3.WaitForExit(15000)) {
    "ExitCode: $($proc3.ExitCode)" | Out-File $out -Append
    "stdout:" | Out-File $out -Append
    $proc3.StandardOutput.ReadToEnd() | Out-File $out -Append
} else {
    "TIMEOUT" | Out-File $out -Append
    $proc3.Kill()
}

"=== DONE ===" | Out-File $out -Append
