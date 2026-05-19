# Test load with various model paths (now that Vulkan runtime is selected)
$ErrorActionPreference = "Continue"
$out = "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_load_test.json"
$result = [ordered]@{ timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"); steps = [ordered]@{} }

function Add-Step($name, $data) {
    $result.steps[$name] = $data
    $result | ConvertTo-Json -Depth 10 | Out-File -FilePath $out -Encoding UTF8
}

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

# Step 1: Get exact model paths
Add-Step "ls_full" (RunWithTimeout $lms "ls" 15000)

# Step 2: Try loading 1B Gemma WITHOUT --exact (substring match)
Add-Step "load_gemma_1b_no_exact" (RunWithTimeout $lms "load gemma-3-1b --gpu max --identifier vk-test --context-length 2048" 120000)

# Step 3: ps
Add-Step "ps1" (RunWithTimeout $lms "ps" 10000)

# Step 4: try via API (load via REST might be different)
$body = '{"model":"vk-test","messages":[{"role":"user","content":"Sag hi"}],"max_tokens":16,"temperature":0.2}'
try {
    $resp = Invoke-RestMethod -Uri http://localhost:1234/v1/chat/completions -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 60 -ErrorAction Stop
    Add-Step "chat_test" @{ ok = $true; response = ($resp | ConvertTo-Json -Depth 6) }
} catch {
    $reader = $null
    try {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $errBody = $reader.ReadToEnd()
    } catch { $errBody = "" }
    Add-Step "chat_test" @{ ok = $false; error = "$_"; body = $errBody; statusCode = $_.Exception.Response.StatusCode.value__ }
}

Add-Step "_done" @{ time = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ") }
