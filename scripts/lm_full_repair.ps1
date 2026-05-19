# Full repair: kill stuck PS, switch runtime to Vulkan, test load, output JSON
$ErrorActionPreference = "Continue"
$out = "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_full_repair.json"
$result = [ordered]@{ timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"); steps = [ordered]@{} }
$myPid = $PID

function Add-Step($name, $data) {
    $result.steps[$name] = $data
    $result | ConvertTo-Json -Depth 10 | Out-File -FilePath $out -Encoding UTF8
}

# Step 1: Kill stuck PowerShell processes (not this one)
$killed = @()
Get-Process -Name powershell -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $myPid } | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force; $killed += $_.Id } catch {}
}
# Also kill stuck lms.exe
Get-Process -Name lms -ErrorAction SilentlyContinue | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force } catch {}
}
Add-Step "killed_pids" @{ killed = $killed; myPid = $myPid }
Start-Sleep -Seconds 2

# Helper function: run external command with timeout, capture output
function RunWithTimeout($exe, $argstr, $timeoutMs) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = $argstr
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    if ($proc.WaitForExit($timeoutMs)) {
        return @{
            exitCode = $proc.ExitCode
            stdout = $proc.StandardOutput.ReadToEnd()
            stderr = $proc.StandardError.ReadToEnd()
            timeout = $false
        }
    } else {
        $proc.Kill()
        return @{ exitCode = -999; stdout = ""; stderr = "TIMEOUT after $timeoutMs ms"; timeout = $true }
    }
}

$lms = "$env:USERPROFILE\.lmstudio\bin\lms.exe"

# Step 2: lms runtime select --help (to see syntax)
Add-Step "runtime_select_help" (RunWithTimeout $lms "runtime select --help" 10000)

# Step 3: select Vulkan 2.14.0
Add-Step "select_vulkan" (RunWithTimeout $lms "runtime select llama.cpp-win-x86_64-vulkan-avx2@2.14.0" 30000)

# Step 4: verify
Add-Step "verify_runtime_ls" (RunWithTimeout $lms "runtime ls" 10000)

# Step 5: Test load smallest model with Vulkan
Add-Step "load_gemma_1b_vulkan" (RunWithTimeout $lms "load gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf --gpu max --identifier vk-test --context-length 2048 --exact" 90000)

# Step 6: ps after load
Add-Step "ps_after_load" (RunWithTimeout $lms "ps" 10000)

# Step 7: try chat completion
$body = '{"model":"vk-test","messages":[{"role":"user","content":"Sag hi auf Deutsch."}],"max_tokens":32,"temperature":0.2}'
try {
    $resp = Invoke-RestMethod -Uri http://localhost:1234/v1/chat/completions -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 60 -ErrorAction Stop
    Add-Step "chat_completion" @{ ok = $true; response = ($resp | ConvertTo-Json -Depth 6) }
} catch {
    Add-Step "chat_completion" @{ ok = $false; error = "$_"; statusCode = $_.Exception.Response.StatusCode.value__ }
}

# Step 8: alternative — try CPU AVX2 if Vulkan loaded 0 bytes
# Save final
Add-Step "_done" @{ time = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ") }
