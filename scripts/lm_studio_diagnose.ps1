# LM Studio Diagnostic Script — 2026-05-17
# Captures runtime/backend state, attempts model load with each backend,
# and outputs detailed JSON for Claude to analyze.

$ErrorActionPreference = "Continue"
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$out = Join-Path $repoRoot '.lm_studio_diagnose.json'
$result = [ordered]@{
    timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    sections = [ordered]@{}
}

$lms = "$env:USERPROFILE\.lmstudio\bin\lms.exe"

function Run-Cmd($name, $cmd) {
    Write-Host "=== $name ==="
    try {
        $out = & cmd /c "$cmd 2>&1"
        $result.sections[$name] = @{
            cmd = $cmd
            output = ($out -join "`n")
            exit = $LASTEXITCODE
        }
        Write-Host ($out -join "`n")
    } catch {
        $result.sections[$name] = @{ cmd = $cmd; error = "$_"; exit = -1 }
    }
}

# 1. Basics
Run-Cmd "lms_version" "`"$lms`" version"
Run-Cmd "lms_help" "`"$lms`" --help"
Run-Cmd "lms_runtime_help" "`"$lms`" runtime --help"
Run-Cmd "lms_ps" "`"$lms`" ps"
Run-Cmd "lms_status" "`"$lms`" status"
Run-Cmd "lms_server_status" "`"$lms`" server status"

# 2. Runtime listing — try multiple subcommand variants since LM Studio versions differ
Run-Cmd "lms_runtime_list" "`"$lms`" runtime list"
Run-Cmd "lms_runtime_ls" "`"$lms`" runtime ls"
Run-Cmd "lms_runtime_status" "`"$lms`" runtime status"

# 3. Check LM Studio install structure
$lmStudioPath1 = "C:\Program Files\AMD\ai_bundle\lmstudio"
$lmStudioPath2 = "$env:LOCALAPPDATA\Programs\LM Studio"
$result.sections["install_paths"] = @{
    amd_bundle_exists = (Test-Path $lmStudioPath1)
    local_lmstudio_exists = (Test-Path $lmStudioPath2)
    amd_bundle_files = if (Test-Path $lmStudioPath1) { @(Get-ChildItem $lmStudioPath1 -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 50 | ForEach-Object { $_.FullName }) } else { @() }
}

# 4. Runtime/Engine internal dir
$runtimeDir = "$env:USERPROFILE\.lmstudio\extensions\backends"
$result.sections["runtime_backends"] = @{
    path = $runtimeDir
    exists = (Test-Path $runtimeDir)
    contents = if (Test-Path $runtimeDir) { @(Get-ChildItem $runtimeDir -ErrorAction SilentlyContinue | ForEach-Object { @{name=$_.Name; type=if($_.PSIsContainer){"dir"}else{"file"}; size=$_.Length} }) } else { @() }
}

# 5. Internal storage
$internalDir = "$env:USERPROFILE\.lmstudio\internal"
$result.sections["internal_dir"] = @{
    path = $internalDir
    exists = (Test-Path $internalDir)
    contents = if (Test-Path $internalDir) { @(Get-ChildItem $internalDir -ErrorAction SilentlyContinue | ForEach-Object { @{name=$_.Name; type=if($_.PSIsContainer){"dir"}else{"file"}} }) } else { @() }
}

# 6. Find recent LM Studio log files
$logPaths = @(
    "$env:USERPROFILE\.lmstudio\logs",
    "$env:USERPROFILE\.cache\lm-studio\logs",
    "$env:LOCALAPPDATA\LM-Studio\logs",
    "$env:APPDATA\LM Studio\logs"
)
$result.sections["log_search"] = @()
foreach ($p in $logPaths) {
    if (Test-Path $p) {
        $logs = Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5
        foreach ($f in $logs) {
            $result.sections["log_search"] += @{
                path = $f.FullName
                size = $f.Length
                modified = $f.LastWriteTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
            }
        }
    }
}

# 7. AMD/GPU info
Run-Cmd "wmic_gpu" "wmic path Win32_VideoController get Name,DriverVersion,VideoProcessor /format:list"
Run-Cmd "dxdiag_check" "powershell -Command `"Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM | Format-List`""

# Save
$result | ConvertTo-Json -Depth 10 | Out-File -FilePath $out -Encoding UTF8
Write-Host "=== DONE ==="
Write-Host "Output: $out"
