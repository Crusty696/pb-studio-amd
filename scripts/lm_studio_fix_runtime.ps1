# LM Studio Runtime Fix — 2026-05-17
# Diagnose ergab: ROCm 2.14.0 selected. Test Vulkan → CPU als Fallback.

$ErrorActionPreference = "Continue"
$out = "C:\Users\david\Documents\Pb_studio_AMD_version\.lm_studio_fix.json"
$result = [ordered]@{
    timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    sections = [ordered]@{}
}

$lms = "$env:USERPROFILE\.lmstudio\bin\lms.exe"

function Run-Cmd($name, $cmd) {
    Write-Host "=== $name ==="
    try {
        $output = & cmd /c "$cmd 2>&1"
        $result.sections[$name] = @{
            cmd = $cmd
            output = ($output -join "`n")
            exit = $LASTEXITCODE
        }
        Write-Host ($output -join "`n")
    } catch {
        $result.sections[$name] = @{ cmd = $cmd; error = "$_"; exit = -1 }
    }
}

# 1. Get help on runtime commands
Run-Cmd "select_help" "`"$lms`" runtime select --help"

# 2. Try switching to Vulkan 2.14.0
Run-Cmd "select_vulkan_2.14" "`"$lms`" runtime select llama.cpp-win-x86_64-vulkan-avx2@2.14.0"

# 3. Verify selection
Run-Cmd "verify_after_vulkan" "`"$lms`" runtime ls"

# 4. Try loading the smallest model (1B Gemma)
Run-Cmd "load_smallest_vulkan" "`"$lms`" load gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf --gpu max --identifier vk-test --context-length 4096 --exact"

# 5. Verify load
Run-Cmd "ps_after_vulkan_load" "`"$lms`" ps"

# 6. Try chat completion
$body = '{"model":"vk-test","messages":[{"role":"user","content":"Sag hi auf Deutsch."}],"max_tokens":32,"temperature":0.2}'
$bodyEscaped = $body.Replace('"', '\"')
Run-Cmd "chat_vulkan" "curl -s -X POST http://localhost:1234/v1/chat/completions -H `"Content-Type: application/json`" -d `"$bodyEscaped`""

# 7. Unload
Run-Cmd "unload_vulkan" "`"$lms`" unload vk-test"

# Save
$result | ConvertTo-Json -Depth 10 | Out-File -FilePath $out -Encoding UTF8
Write-Host "=== DONE ==="
