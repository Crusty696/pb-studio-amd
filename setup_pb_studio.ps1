<#
.SYNOPSIS
    PB Studio AMD One-Shot Installer (v11) - Pre-Flight + Install + Verify
    Macht alles was die App braucht: System-Check, Download, Install, Verify.

.DESCRIPTION
    PHASE A - Pre-Flight
        Windows-Version, Admin, Python 3.11, .NET 9.0 SDK, AMD GPU,
        Adrenalin Treiber, DirectML, Disk, RAM, Internet, Antivirus

    PHASE B - Install
        VS Build Tools (optional via -SkipBuildTools)
        Python 3.11 (winget falls fehlt)
        .NET 9.0 SDK (winget falls fehlt)
        Hashverifiziertes FFmpeg -> tools\
        LibreHardwareMonitor nur aus freigegebenem lokalem Bundle-Manifest
        Venv + pip install -r requirements.txt (Brain-Stack inkl.)
        Pre-commit Hook (Schema-Drift-Check)
        ONNX-Modellassets ausschließlich über freigegebene Manifeste
        Optional: Woechentliches Brain-Backup Task

    PHASE C - Verify
        Smoke imports
        sqlite-vec KNN
        ONNX Runtime DirectML Provider-Vertrag
        Optional: WPF Build
        Optional: pytest

.PARAMETER SkipBuildTools
    VS Build Tools install ueberspringen (z.B. wenn bereits da).

.PARAMETER SkipBackupPrompt
    Auto-Backup-Task-Frage ueberspringen.

.PARAMETER SkipModelPrecache
    Veralteter Kompatibilitaetsschalter ohne Skip-Wirkung. Pflichtassets werden
    weiterhin manifest- und hashverifiziert.

.PARAMETER SkipGpuVerify
    Veralteter Kompatibilitaetsschalter ohne Skip-Wirkung. ONNX Runtime
    DirectML wird weiterhin verpflichtend verifiziert.

.PARAMETER SkipPytest
    Final pytest-Run ueberspringen.

.PARAMETER NoPause
    Kein "Press Enter" am Ende.

.PARAMETER Force
    Idempotenz-Check umgehen - alles neu installieren.

.PARAMETER LogFile
    Pfad zum Log-File (default: setup_log_<ts>.txt)

.NOTES
    REQUIRES ADMIN fuer Build-Tools / winget-Installs.
    Skript ist idempotent: kann mehrfach gelaufen werden.
#>

param (
    [switch]$SkipBuildTools = $false,
    [switch]$SkipBackupPrompt = $false,
    [switch]$SkipModelPrecache = $false,
    [switch]$SkipGpuVerify = $false,
    [switch]$SkipPytest = $false,
    [switch]$NoPause = $false,
    [switch]$Force = $false,
    [string]$LogFile = ""
)

# Setup script: native exe stderr (pip WARNINGs etc.) MUST NOT abort.
# Critical errors are caught via explicit $LASTEXITCODE checks.
$ErrorActionPreference = "Continue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# =============================================================================
# Constants
# =============================================================================
$REPO_ROOT = $PSScriptRoot
$VENV_PATH = Join-Path $REPO_ROOT ".venv"
$TOOLS_DIR = Join-Path $REPO_ROOT "tools"
$LOGS_DIR = Join-Path $REPO_ROOT "logs"
. (Join-Path $REPO_ROOT 'scripts\runtime_contract.ps1')
$RuntimeContract = Get-PBStudioRuntimeContract -ProjectRoot $REPO_ROOT

$REQUIRED_PYTHON = "3.11"          # exact major.minor; 3.12 bricht BeatNet
$REQUIRED_DOTNET = "9.0"
$MIN_DISK_GB = 20
$MIN_RAM_GB = 8

if (-not (Test-Path $LOGS_DIR)) { New-Item -ItemType Directory -Path $LOGS_DIR | Out-Null }
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $LogFile) {
    $LogFile = Join-Path $LOGS_DIR "setup_log_$ts.txt"
}
$TranscriptFile = Join-Path $LOGS_DIR "setup_transcript_$ts.txt"

# Transcript faengt ALLES ab - auch unhandled Exceptions, Native exe stderr,
# Stack-Traces. Ueberlebt Window-Close (File-Flush ist sync).
try { Stop-Transcript | Out-Null } catch {}
try {
    Start-Transcript -Path $TranscriptFile -Append -Force | Out-Null
} catch {
    Write-Host "WARN: Transcript konnte nicht gestartet werden ($_)" -ForegroundColor Yellow
}

# Globaler Trap fuer unbehandelte Exceptions - schreibt Stack-Trace ins Log.
trap {
    $err = $_
    $msg = "UNHANDLED: $($err.Exception.Message)`n$($err.ScriptStackTrace)`n$($err.InvocationInfo.PositionMessage)"
    Add-Content -Path $LogFile -Value "[$(Get-Date -Format HH:mm:ss)] [CRASH] $msg" -Encoding utf8
    Write-Host ""
    Write-Host "  [CRASH] Unbehandelter Fehler - Stack-Trace siehe $LogFile" -ForegroundColor Red
    Write-Host "  $($err.Exception.Message)" -ForegroundColor Red
    try { Stop-Transcript | Out-Null } catch {}
    if (-not $NoPause) {
        Read-Host "Press Enter to exit"
    }
    exit 99
}

# =============================================================================
# Helpers
# =============================================================================
$global:Issues = @()
$global:Warnings = @()
$global:Successes = @()

function Log-Out([string]$msg, [string]$lvl = "INFO") {
    $line = "[$(Get-Date -Format HH:mm:ss)] [$lvl] $msg"
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Hdr([string]$txt) {
    Write-Host ""
    Write-Host "==============================================================" -ForegroundColor Cyan
    Write-Host "  $txt" -ForegroundColor Cyan
    Write-Host "==============================================================" -ForegroundColor Cyan
    Log-Out "==== $txt ===="
}

function OK([string]$msg) {
    Write-Host "  [OK]   $msg" -ForegroundColor Green
    Log-Out "OK $msg"
    $global:Successes += $msg
}

function WARN([string]$msg) {
    Write-Host "  [WARN] $msg" -ForegroundColor Yellow
    Log-Out "WARN $msg" "WARN"
    $global:Warnings += $msg
}

function FAIL([string]$msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    Log-Out "FAIL $msg" "FAIL"
    $global:Issues += $msg
}

function Step([string]$msg) {
    Write-Host "  > $msg" -ForegroundColor Gray
    Log-Out $msg
}

function Test-VCRedist {
    try {
        $reg = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -Name "Installed" -ErrorAction SilentlyContinue
        return ($reg -and $reg.Installed -eq 1)
    } catch { return $false }
}

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $prin = New-Object Security.Principal.WindowsPrincipal($id)
    return $prin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-OsName {
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
        return @{ Caption = $os.Caption; Version = $os.Version; Build = $os.BuildNumber }
    } catch { return $null }
}

function _PyProbe([string]$cmd) {
    try {
        $v = & cmd /c "$cmd --version 2>&1"
        if ($v -match "Python\s+(\d+)\.(\d+)\.(\d+)") {
            return @{ Cmd = $cmd; Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Patch = [int]$Matches[3]; Full = "$($Matches[1]).$($Matches[2]).$($Matches[3])" }
        }
    } catch {}
    return $null
}

function Get-PyExe {
    # Prefer 3.11 strict; collect all candidates, return 3.11 if any.
    $found = @()

    # py launcher with explicit 3.11
    $r = _PyProbe "py -3.11"
    if ($r) { $found += $r }

    foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python311\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )) {
        if (Test-Path $p) {
            $r = _PyProbe "`"$p`""
            if ($r) { $found += $r }
        }
    }

    # Generic fallback
    foreach ($cmd in @("python","python3","py")) {
        $r = _PyProbe $cmd
        if ($r) { $found += $r }
    }

    foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python310\python.exe"
    )) {
        if (Test-Path $p) {
            $r = _PyProbe "`"$p`""
            if ($r) { $found += $r }
        }
    }

    if (-not $found.Count) { return $null }

    $py311 = $found | Where-Object { $_.Major -eq 3 -and $_.Minor -eq 11 } | Select-Object -First 1
    if ($py311) { return $py311 }
    return $found[0]
}

function Get-DotnetVer {
    # Pruefe zuerst lokales portables dotnet in tools\dotnet
    $localDotnet = Join-Path $PSScriptRoot "tools\dotnet\dotnet.exe"
    $cmd = "dotnet"
    if (Test-Path $localDotnet) {
        $cmd = "`"$localDotnet`""
    }
    try {
        $out = & cmd /c "$cmd --version 2>&1"
        if ($out -match "(\d+)\.(\d+)\.(\d+)") {
            return @{ Cmd = $cmd; Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Patch = [int]$Matches[3]; Full = "$($Matches[1]).$($Matches[2]).$($Matches[3])" }
        }
    } catch {}
    return $null
}

function Get-AmdGpu {
    try {
        $g = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -match "AMD|Radeon|RX " } |
             Select-Object -First 1
        if ($g) {
            return @{ Name = $g.Name; Driver = $g.DriverVersion; Vram = [math]::Round($g.AdapterRAM / 1MB) }
        }
    } catch {}
    return $null
}

function Test-DirectML($pythonExe) {
    if (-not $pythonExe -or -not (Test-Path $pythonExe)) { return $null }
    $code = "import sys; sys.exit(0 if 'DmlExecutionProvider' in __import__('onnxruntime').get_available_providers() else 1)"
    try {
        & $pythonExe -c "import onnxruntime" *>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { return $null }
        & $pythonExe -c $code *>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch { return $null }
}

function Get-DiskFreeGB([string]$drv = "C:") {
    try {
        $d = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -eq $drv.Substring(0,1) } | Select-Object -First 1
        if ($d) { return [math]::Round($d.Free / 1GB, 1) }
    } catch {}
    return 0
}

function Get-RamGB {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        return [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    } catch { return 0 }
}

function Test-Internet {
    try {
        $r = Test-NetConnection -ComputerName "pypi.org" -Port 443 -WarningAction SilentlyContinue
        return $r.TcpTestSucceeded
    } catch { return $false }
}

function Install-WingetPackage([string]$id, [string]$pretty) {
    Step "winget install $id ..."
    & winget install -e --id $id --source winget --silent --disable-interactivity --accept-package-agreements --accept-source-agreements *>&1 | Out-String | Add-Content $LogFile
    if ($LASTEXITCODE -eq 0) { OK "$pretty installiert" }
    else { FAIL "$pretty install fehlgeschlagen ($LASTEXITCODE)" }
}

function Install-VerifiedFFmpeg {
    $active = $RuntimeContract.Manifest.active
    $destDir = Join-Path $TOOLS_DIR "ffmpeg"
    $ffmpegExe = Join-Path $destDir "bin\ffmpeg.exe"
    $ffprobeExe = Join-Path $destDir "bin\ffprobe.exe"

    if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
        $ffmpegHash = (Get-FileHash -LiteralPath $ffmpegExe -Algorithm SHA256).Hash
        $ffprobeHash = (Get-FileHash -LiteralPath $ffprobeExe -Algorithm SHA256).Hash
        if ($ffmpegHash -eq $active.ffmpeg_sha256 -and
            $ffprobeHash -eq $active.ffprobe_sha256) {
            OK "FFmpeg $($active.version) verifiziert in $destDir"
            return $destDir
        }
        if (-not $Force) {
            FAIL "FFmpeg-Hash weicht vom freigegebenen Runtime-Manifest ab. --Force nur nach gesichertem Rollback verwenden."
            return $null
        }
    } elseif ((Test-Path $destDir) -and -not $Force) {
        FAIL "FFmpeg-Bundle ist unvollständig. --Force nur nach gesichertem Rollback verwenden."
        return $null
    }

    $workDir = Join-Path $env:TEMP ("PBStudio-FFmpeg-Setup-" + [guid]::NewGuid().ToString("N"))
    $zip = Join-Path $workDir "ffmpeg.zip"
    $extractDir = Join-Path $workDir "extract"
    New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
    try {
        Step "Download verifiziertes FFmpeg $($active.version)..."
        Invoke-WebRequest -Uri $active.asset_url -OutFile $zip -UserAgent "PBStudioInstaller/11.0"
        $assetHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
        if ($assetHash -ne $active.asset_sha256) {
            throw "FFmpeg-Asset-Hash falsch: erwartet $($active.asset_sha256), erhalten $assetHash"
        }

        Expand-Archive -LiteralPath $zip -DestinationPath $extractDir -Force
        $candidateFfmpeg = Get-ChildItem -LiteralPath $extractDir -Filter ffmpeg.exe -Recurse |
            Select-Object -First 1
        if (-not $candidateFfmpeg) {
            throw "ffmpeg.exe fehlt im verifizierten Asset"
        }
        $candidateRoot = $candidateFfmpeg.Directory.Parent.FullName
        $candidateFfprobe = Join-Path $candidateRoot "bin\ffprobe.exe"
        if (-not (Test-Path -LiteralPath $candidateFfprobe)) {
            throw "ffprobe.exe fehlt im verifizierten Asset"
        }
        if ((Get-FileHash -LiteralPath $candidateFfmpeg.FullName -Algorithm SHA256).Hash -ne $active.ffmpeg_sha256 -or
            (Get-FileHash -LiteralPath $candidateFfprobe -Algorithm SHA256).Hash -ne $active.ffprobe_sha256) {
            throw "FFmpeg/FFprobe stimmen nicht mit dem aktiven Runtime-Manifest überein"
        }

        if (Test-Path -LiteralPath $destDir) {
            $backupRoot = Join-Path $TOOLS_DIR "runtime-backups"
            New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
            $backupDir = Join-Path $backupRoot ("ffmpeg_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
            Move-Item -LiteralPath $destDir -Destination $backupDir
            WARN "Vorheriges FFmpeg-Bundle gesichert: $backupDir"
        }
        Move-Item -LiteralPath $candidateRoot -Destination $destDir
        OK "FFmpeg $($active.version) installiert und hashverifiziert"
        return $destDir
    } catch {
        FAIL "FFmpeg-Installation fehlgeschlagen: $_"
        return $null
    } finally {
        if (Test-Path -LiteralPath $workDir) {
            Remove-Item -LiteralPath $workDir -Recurse -Force
        }
    }
}

function Test-VerifiedLhmBundle {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BundleDirectory,
        [Parameter(Mandatory = $true)]
        [string]$MainAssemblyPath
    )

    try {
        $manifestPath = Join-Path $BundleDirectory "pb-studio-lhm-manifest.json"
        $manifestExpectedHash = [string]$env:PBSTUDIO_LHM_MANIFEST_SHA256
        $mainExpectedHash = [string]$env:PBSTUDIO_LHM_SHA256
        if ($manifestExpectedHash -notmatch '^[A-Fa-f0-9]{64}$') {
            throw "PBSTUDIO_LHM_MANIFEST_SHA256 fehlt oder ist ungueltig"
        }
        if ($mainExpectedHash -notmatch '^[A-Fa-f0-9]{64}$') {
            throw "PBSTUDIO_LHM_SHA256 fehlt oder ist ungueltig"
        }
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
            throw "pb-studio-lhm-manifest.json fehlt"
        }

        $manifestItem = Get-Item -LiteralPath $manifestPath
        if (($manifestItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "LHM-Manifest darf kein Reparse-Point sein"
        }
        $manifestActualHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
        if ($manifestActualHash -ne $manifestExpectedHash) {
            throw "LHM-Manifest-Hash stimmt nicht"
        }

        $manifest = Get-Content -Raw -LiteralPath $manifestPath |
            ConvertFrom-Json
        if ($manifest.schema_version -ne 1) {
            throw "LHM-Manifest schema_version muss 1 sein"
        }
        $entries = @($manifest.assemblies)
        if ($entries.Count -eq 0) {
            throw "LHM-Manifest enthaelt keine Assemblies"
        }

        $bundleRoot = [IO.Path]::GetFullPath($BundleDirectory)
        $mainFullPath = [IO.Path]::GetFullPath($MainAssemblyPath)
        $seenNames = @{}
        $seenFiles = @{}
        $mainVerified = $false
        foreach ($entry in $entries) {
            $assemblyName = [string]$entry.name
            $fileName = [string]$entry.file
            $expectedHash = [string]$entry.sha256
            if ($assemblyName -notmatch '^[A-Za-z0-9_.-]+$') {
                throw "Ungueltiger Assembly-Name im LHM-Manifest"
            }
            if ($seenNames.ContainsKey($assemblyName.ToLowerInvariant())) {
                throw "Doppelter Assembly-Name im LHM-Manifest: $assemblyName"
            }
            $seenNames[$assemblyName.ToLowerInvariant()] = $true
            if ([IO.Path]::GetFileName($fileName) -ne $fileName -or
                [IO.Path]::GetExtension($fileName) -ne ".dll") {
                throw "Ungueltiger DLL-Dateiname im LHM-Manifest: $fileName"
            }
            if ($seenFiles.ContainsKey($fileName.ToLowerInvariant())) {
                throw "Doppelter DLL-Dateiname im LHM-Manifest: $fileName"
            }
            $seenFiles[$fileName.ToLowerInvariant()] = $true
            if ($expectedHash -notmatch '^[A-Fa-f0-9]{64}$') {
                throw "Ungueltiger SHA-256 fuer $assemblyName"
            }

            $assemblyPath = [IO.Path]::GetFullPath(
                (Join-Path $bundleRoot $fileName)
            )
            if ([IO.Path]::GetDirectoryName($assemblyPath) -ne $bundleRoot) {
                throw "LHM-Assembly verlaesst Bundle-Verzeichnis: $fileName"
            }
            if (-not (Test-Path -LiteralPath $assemblyPath -PathType Leaf)) {
                throw "LHM-Assembly fehlt: $fileName"
            }
            $assemblyItem = Get-Item -LiteralPath $assemblyPath
            if (($assemblyItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "LHM-Assembly darf kein Reparse-Point sein: $fileName"
            }
            $actualHash = (Get-FileHash -LiteralPath $assemblyPath -Algorithm SHA256).Hash
            if ($actualHash -ne $expectedHash) {
                throw "LHM-Assembly-Hash stimmt nicht: $fileName"
            }
            if ($assemblyPath -eq $mainFullPath) {
                if ($actualHash -ne $mainExpectedHash) {
                    throw "LibreHardwareMonitorLib.dll stimmt nicht mit PBSTUDIO_LHM_SHA256 ueberein"
                }
                $mainVerified = $true
            }
        }
        if (-not $mainVerified) {
            throw "LHM-Hauptassembly fehlt im freigegebenen Manifest"
        }
        return [PSCustomObject]@{ Valid = $true; Reason = "OK" }
    } catch {
        return [PSCustomObject]@{
            Valid = $false
            Reason = $_.Exception.Message
        }
    }
}

# =============================================================================
# PHASE A - Pre-Flight
# =============================================================================
Hdr "PB STUDIO ONE-SHOT INSTALLER v11 - PHASE A: Pre-Flight Check"

# A.1 Admin
if (Test-Admin) { OK "Admin-Rechte" }
else { WARN "Keine Admin-Rechte (winget/VS Build Tools werden ggf. fehlschlagen)" }

# A.2 OS
$os = Get-OsName
if ($os) {
    $isWin10Or11 = ($os.Caption -match "Windows (10|11)")
    if ($isWin10Or11) { OK "OS: $($os.Caption) (Build $($os.Build))" }
    else { FAIL "OS nicht unterstuetzt: $($os.Caption)" }
} else {
    FAIL "OS nicht erkennbar"
}

# A.3 Python
$py = Get-PyExe
if ($py) {
    if ($py.Major -eq 3 -and $py.Minor -eq 11) {
        OK "Python $($py.Full) ($($py.Cmd))"
    } elseif ($py.Major -eq 3 -and $py.Minor -lt 11) {
        WARN "Python $($py.Full) zu alt - 3.11 erforderlich"
    } elseif ($py.Major -eq 3 -and $py.Minor -gt 11) {
        WARN "Python $($py.Full) zu neu - 3.11 erforderlich (BeatNet-Constraint)"
    }
} else {
    WARN "Python nicht gefunden - wird via winget installiert"
}

# A.4 .NET 9
$dn = Get-DotnetVer
if ($dn) {
    if ($dn.Major -ge 9) { OK ".NET SDK $($dn.Full)" }
    else { WARN ".NET SDK $($dn.Full) zu alt - 9.0 erforderlich" }
} else {
    WARN ".NET SDK nicht gefunden - wird via winget installiert"
}

# A.5 AMD GPU
$gpu = Get-AmdGpu
if ($gpu) {
    OK "AMD GPU: $($gpu.Name) (Driver $($gpu.Driver))"
    if ($gpu.Vram -gt 0) { Step "VRAM: $($gpu.Vram) MB" }
} else {
    WARN "Keine AMD GPU erkannt - DirectML-ML-Funktionen bleiben deaktiviert; kein CPU-Fallback"
}

# A.6 DirectML (provisorisch; richtiger Test in Phase C)
Step "DirectML Provider Check folgt in Phase C nach pip install"

# A.7 Disk
$diskFree = Get-DiskFreeGB
if ($diskFree -ge $MIN_DISK_GB) { OK "Disk free: $diskFree GB" }
else { WARN "Disk free: $diskFree GB (<$MIN_DISK_GB GB empfohlen fuer models + venv)" }

# A.8 RAM
$ram = Get-RamGB
if ($ram -ge $MIN_RAM_GB) { OK "RAM: $ram GB" }
else { WARN "RAM: $ram GB (<$MIN_RAM_GB GB; Embedding-Pipeline kann limitiert sein)" }

# A.9 Internet
if (Test-Internet) { OK "Internet (PyPI erreichbar)" }
else { FAIL "Kein Internet - pip install nicht moeglich" }

# A.10 FFmpeg+LHM check (existing)
$preflightFfmpeg = $RuntimeContract.FfmpegExe
$preflightFfprobe = $RuntimeContract.FfprobeExe
if ((Test-Path $preflightFfmpeg) -and (Test-Path $preflightFfprobe) -and
    (Get-FileHash -LiteralPath $preflightFfmpeg -Algorithm SHA256).Hash -eq $RuntimeContract.Manifest.active.ffmpeg_sha256 -and
    (Get-FileHash -LiteralPath $preflightFfprobe -Algorithm SHA256).Hash -eq $RuntimeContract.Manifest.active.ffprobe_sha256) {
    OK "FFmpeg/FFprobe entsprechen dem aktiven Runtime-Manifest"
} else {
    Step "FFmpeg/FFprobe fehlen oder weichen vom aktiven Runtime-Manifest ab"
}
$lhmDir = Join-Path $TOOLS_DIR "LibreHardwareMonitor"
$lhmLib = Join-Path $lhmDir "LibreHardwareMonitorLib.dll"
$lhmContract = Test-VerifiedLhmBundle `
    -BundleDirectory $lhmDir `
    -MainAssemblyPath $lhmLib
if ($lhmContract.Valid) {
    OK "LibreHardwareMonitor-Bundle und Abhaengigkeiten sind manifestgebunden"
} else {
    WARN "LibreHardwareMonitor deaktiviert: $($lhmContract.Reason). Setup installiert kein LHM-Bundle."
}

# A.11 MSVC C++ Runtime
if (Test-VCRedist) { OK "Visual C++ Redistributable (x64) vorhanden" }
else { WARN "Visual C++ Redistributable (x64) fehlt - wird in Phase B installiert" }

# A.12 Git
$global:HasGit = $false
if (Get-Command git -ErrorAction SilentlyContinue) {
    OK "Git installiert"
    $global:HasGit = $true
} else {
    WARN "Git nicht gefunden - wird in Phase B portabel/systemweit eingerichtet"
}

# A.X Summary
Write-Host ""
Write-Host "  ----- Pre-Flight Summary -----" -ForegroundColor Cyan
Write-Host "  OK:   $($global:Successes.Count)"
Write-Host "  WARN: $($global:Warnings.Count)"
Write-Host "  FAIL: $($global:Issues.Count)"
if ($global:Issues.Count -gt 0) {
    Write-Host ""
    Write-Host "  Pre-Flight gescheitert. Behebe FAIL-Punkte und versuche erneut." -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Press Enter to exit" }
    exit 1
}

# =============================================================================
# PHASE B - Install
# =============================================================================
Hdr "PHASE B: Install"

if (-not (Test-Path $TOOLS_DIR)) { New-Item -ItemType Directory -Path $TOOLS_DIR | Out-Null }

# B.0.1 Winget Source Reset (sichert frische Systeme ab)
if (Get-Command winget -ErrorAction SilentlyContinue) {
    Step "Initialisiere winget Quellen (Source Reset)..."
    & winget source reset --force *>&1 | Out-String | Add-Content $LogFile
}

# B.0.2 Visual C++ Redistributable 2015-2022 x64 (kritisch fuer onnxruntime/cv2 DLLs)
if (-not (Test-VCRedist)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Step "Versuche Visual C++ Redistributable via winget..."
        Install-WingetPackage "Microsoft.VCRedist.2015+.x64" "Visual C++ Redistributable"
    }
    if (-not (Test-VCRedist)) {
        FAIL "Visual C++ Redistributable fehlt. Verifizierte winget-Installation erforderlich; direkter Installer-Fallback ist gesperrt."
        exit 1
    }
} else {
    OK "Visual C++ Redistributable (x64) bereits installiert"
}

# B.0.3 Git Auto-Check & Installation (sichert pre-commit hooks und checkout ab)
if (-not $global:HasGit) {
    $gitInstalled = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Step "Versuche Git via winget..."
        Install-WingetPackage "Git.Git" "Git"
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
        if (Get-Command git -ErrorAction SilentlyContinue) { $gitInstalled = $true }
    }
    if (-not $gitInstalled) {
        FAIL "Git fehlt. Verifizierte winget-Installation erforderlich; portabler Download-Fallback ist gesperrt."
        exit 1
    }
    $global:HasGit = $true
}

# B.1 VS Build Tools
if (-not $SkipBuildTools) {
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    $hasBT = $false
    if (Test-Path $vsWhere) {
        $check = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
        if ($check) { $hasBT = $true }
    }
    if ($hasBT) {
        OK "VS Build Tools installiert"
    } else {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            FAIL "VS Build Tools fehlen. Verifizierte winget-Installation erforderlich; direkter Installer-Fallback ist gesperrt. Alternativ -SkipBuildTools verwenden."
            exit 1
        }
        Step "VS Build Tools via winget installieren (gross, ~10 min)..."
        $vsInstallArgs = "--wait --quiet --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
        & winget install -e --id Microsoft.VisualStudio.2022.BuildTools --source winget --silent --disable-interactivity --accept-package-agreements --accept-source-agreements --override $vsInstallArgs *>&1 |
            Out-String | Add-Content $LogFile
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
        if (Test-Path $vsWhere) {
            $check = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
        }
        if ($LASTEXITCODE -eq 0 -and $check) {
            OK "VS Build Tools installiert"
        } else {
            FAIL "VS Build Tools konnten nicht ueber winget installiert und verifiziert werden. Alternativ -SkipBuildTools verwenden."
            exit 1
        }
    }
} else {
    Step "VS Build Tools uebersprungen (--SkipBuildTools)"
}

# B.2 Python 3.11 falls fehlt
if (-not $py -or $py.Minor -ne 11) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Step "Versuche Python 3.11 via winget..."
        Install-WingetPackage "Python.Python.3.11" "Python 3.11"
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
        $py = Get-PyExe
    }
    if (-not $py -or $py.Minor -ne 11) {
        FAIL "Python 3.11 fehlt. Verifizierte winget-Installation erforderlich; direkter Installer-Fallback ist gesperrt."
        exit 1
    }
}

# B.3 .NET 9 SDK falls fehlt
if (-not $dn -or $dn.Major -lt 9) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Step "Versuche .NET 9 SDK via winget..."
        Install-WingetPackage "Microsoft.DotNet.SDK.9" ".NET 9 SDK"
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
        $dn = Get-DotnetVer
    }
    if (-not $dn -or $dn.Major -lt 9) {
        FAIL ".NET 9 SDK fehlt. Verifizierte winget-Installation erforderlich; dotnet-install.ps1-Fallback ist gesperrt."
        exit 1
    }
}

# B.4 FFmpeg + optionales, lokal freigegebenes LHM-Bundle
$ffmpegDir = Install-VerifiedFFmpeg
if ($lhmContract.Valid) {
    OK "Freigegebenes lokales LibreHardwareMonitor-Bundle wird verwendet"
} else {
    WARN "Hardware-Monitoring bleibt deaktiviert; freigegebenes lokales LHM-Bundle plus beide SHA-256-Umgebungswerte erforderlich"
}
if ($ffmpegDir) {
    $RuntimeContract = Get-PBStudioRuntimeContract -ProjectRoot $REPO_ROOT -RequireFFmpeg -ApplyEnvironment
    OK "FFmpeg/FFprobe auf kanonischen Projektpfad gebunden"
}

# B.5 Venv
if ((Test-Path $VENV_PATH) -and -not $Force) {
    $existingVenvPython = Join-Path $VENV_PATH "Scripts\python.exe"
    $existingVenvVersion = if (Test-Path $existingVenvPython) {
        & $existingVenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    } else {
        ""
    }
    if ($existingVenvVersion -ne $REQUIRED_PYTHON) {
        FAIL "Vorhandene venv ist nicht Python $REQUIRED_PYTHON.x; sichere Neuerstellung mit --Force erforderlich."
        exit 1
    }
    Step "venv Python $existingVenvVersion verifiziert ($VENV_PATH)"
} else {
    if (Test-Path $VENV_PATH) { Remove-Item $VENV_PATH -Recurse -Force }
    Step "Lege venv an mit Python $($py.Full)..."
    & $py.Cmd -m venv $VENV_PATH
    if ($LASTEXITCODE -ne 0) { FAIL "venv-Anlage scheitert"; exit 1 }
    OK "venv unter $VENV_PATH"
}
$venvPython = Join-Path $VENV_PATH "Scripts\python.exe"
$venvPip = Join-Path $VENV_PATH "Scripts\pip.exe"
$RuntimeContract = Get-PBStudioRuntimeContract -ProjectRoot $REPO_ROOT -RequirePython -RequireFFmpeg -ApplyEnvironment

# B.6/B.7 hash-locked Python graph + approved local wheel overrides
$reqFile = Join-Path $REPO_ROOT "requirements.txt"
if (-not (Test-Path $reqFile)) { FAIL "requirements.txt nicht gefunden"; exit 1 }
$wheelManifestPath = Join-Path $REPO_ROOT "config\python-wheel-overrides.json"
if (-not (Test-Path -LiteralPath $wheelManifestPath -PathType Leaf)) {
    FAIL "Python-Wheelmanifest fehlt: $wheelManifestPath"
    exit 1
}
try {
    $wheelManifest = Get-Content -LiteralPath $wheelManifestPath -Raw | ConvertFrom-Json
    if ($wheelManifest.schema_version -ne 1 -or -not $wheelManifest.packages) {
        throw "ungueltiges Schema"
    }
    $vendorRoot = [IO.Path]::GetFullPath((Join-Path $REPO_ROOT "vendor\wheels"))
    $requirementsText = Get-Content -LiteralPath $reqFile -Raw
    $declaredWheels = @{}
    foreach ($package in $wheelManifest.packages) {
        $relativeWheel = [string]$package.wheel_path
        if (-not $relativeWheel.StartsWith("vendor/wheels/", [StringComparison]::Ordinal) -or
            $relativeWheel.Contains("..")) {
            throw "unsicherer Wheelpfad: $relativeWheel"
        }
        $wheelPath = [IO.Path]::GetFullPath((Join-Path $REPO_ROOT $relativeWheel))
        if (-not $wheelPath.StartsWith($vendorRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $wheelPath -PathType Leaf)) {
            throw "Wheel fehlt oder liegt ausserhalb vendor/wheels: $relativeWheel"
        }
        $expectedWheelHash = ([string]$package.wheel_sha256).ToLowerInvariant()
        $actualWheelHash = (Get-FileHash -LiteralPath $wheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($expectedWheelHash -notmatch '^[0-9a-f]{64}$' -or $actualWheelHash -ne $expectedWheelHash) {
            throw "Wheel-Hash ungueltig: $relativeWheel"
        }
        if ($requirementsText.IndexOf("--hash=sha256:$expectedWheelHash", [StringComparison]::Ordinal) -lt 0) {
            throw "Wheel-Hash fehlt im Python-Lock: $relativeWheel"
        }
        $declaredWheels[$wheelPath.ToLowerInvariant()] = $true
    }
    foreach ($localWheel in Get-ChildItem -LiteralPath $vendorRoot -Filter "*.whl" -File) {
        if (-not $declaredWheels.ContainsKey($localWheel.FullName.ToLowerInvariant())) {
            throw "Nicht allowlistetes Wheel in vendor/wheels: $($localWheel.Name)"
        }
    }
} catch {
    FAIL "Python-Wheelmanifest nicht vertrauenswuerdig: $($_.Exception.Message)"
    exit 1
}
Step "pip install --require-hashes -r requirements.txt (kann mehrere Minuten dauern)..."
Push-Location $REPO_ROOT
& $venvPython -m pip install --require-hashes -r $reqFile *>&1 | Out-String | Add-Content $LogFile
$pipInstallExitCode = $LASTEXITCODE
Pop-Location
if ($pipInstallExitCode -ne 0) { FAIL "pip install scheitert (siehe $LogFile)"; exit 1 }
OK "Brain-Stack + Backend-Deps installiert"

# B.8 Pre-commit Hook
$preCommit = Join-Path $REPO_ROOT "scripts\install_pre_commit.ps1"
if (Test-Path $preCommit) {
    & $preCommit *>&1 | Out-String | Add-Content $LogFile
    if ($LASTEXITCODE -eq 0) {
        OK "Pre-commit Schema-Drift-Hook installiert"
    } else {
        WARN "Pre-commit Hook-Installation fehlgeschlagen (siehe $LogFile)"
    }
}

# B.9 WPF dotnet restore + build (falls .NET vorhanden)
$dn = Get-DotnetVer
if ($dn -and $dn.Major -ge 9) {
    $csproj = Join-Path $REPO_ROOT "PBStudio.UI\PBStudio.UI.csproj"
    if (Test-Path $csproj) {
        Step "dotnet restore + build ..."
        & dotnet restore $csproj --nologo -v q *>&1 | Out-String | Add-Content $LogFile
        & dotnet build $csproj -c Release --nologo -v q *>&1 | Out-String | Add-Content $LogFile
        if ($LASTEXITCODE -eq 0) { OK "WPF Build OK" }
        else { WARN "WPF Build scheitert (siehe $LogFile)" }
    }
}

# B.10 DirectML assets: approved manifest + exact hashes + safe atomic promotion.
$directMlProvisioner = Join-Path $REPO_ROOT "scripts\provision_directml_assets.ps1"
$directMlBundleManifest = Join-Path $REPO_ROOT "config\directml-asset-bundle.json"
if ($SkipModelPrecache) {
    WARN "--SkipModelPrecache ist veraltet und wird ignoriert; Pflichtassets bleiben verpflichtend."
}
if (-not (Test-Path -LiteralPath $directMlProvisioner -PathType Leaf)) {
    FAIL "DirectML-Asset-Provisioner fehlt: $directMlProvisioner"
    exit 1
}
$directMlProvisionArgs = @{
    ManifestPath = $directMlBundleManifest
    InstallRoot = $REPO_ROOT
}
if (-not [string]::IsNullOrWhiteSpace($env:PBSTUDIO_DIRECTML_ASSET_BUNDLE)) {
    $directMlProvisionArgs.BundlePath = $env:PBSTUDIO_DIRECTML_ASSET_BUNDLE
}
Step "DirectML-Pflichtassets aus freigegebenem Release-Bundle pruefen..."
$directMlProvisionOutput = & $directMlProvisioner @directMlProvisionArgs 2>&1
$directMlProvisionExitCode = $LASTEXITCODE
$directMlProvisionOutput | Out-String | Add-Content $LogFile
if ($directMlProvisionExitCode -ne 0) {
    FAIL "DirectML-Pflichtassets fehlen oder sind nicht freigegeben (siehe $LogFile)"
    exit 1
}
OK "DirectML-Pflichtassets manifest- und hashverifiziert"

# B.11 Auto-Backup Task
# SkipBackupPrompt = true  -> skip
# NoPause = true           -> nicht-interaktiver Modus (Doppelklick via .bat) -> skip
# sonst: Read-Host
$backupInst = Join-Path $REPO_ROOT "scripts\install_brain_backup_task.ps1"
if (Test-Path $backupInst) {
    if ($SkipBackupPrompt -or $NoPause) {
        Step "Brain-Backup-Task uebersprungen (nicht-interaktiver Modus oder --SkipBackupPrompt)"
    } else {
        $resp = Read-Host "Woechentliches Brain-Backup als Windows Task einrichten? (y/N)"
        if ($resp -match "^[Yy]") {
            & $backupInst *>&1 | Out-String | Add-Content $LogFile
            OK "Auto-Backup-Task installiert"
        } else {
            Step "Skipped - install later mit: scripts\install_brain_backup_task.ps1"
        }
    }
}

# =============================================================================
# PHASE C - Verify
# =============================================================================
Hdr "PHASE C: Verify"

# C.1 Smoke imports
$smokeFile = Join-Path $env:TEMP "pb_smoke_imports.py"
$smokeBody = @(
    'import sys',
    'errors = []',
    'mods = ["numpy","torch","transformers","sqlite_vec",',
    '        "librosa","onnxruntime","cv2","fastapi","uvicorn","demucs"]',
    'for m in mods:',
    '    try:',
    '        __import__(m)',
    '        print("OK " + m)',
    '    except Exception as e:',
    '        errors.append(m + ": " + str(e))',
    '        print("FAIL " + m + ": " + str(e), file=sys.stderr)',
    'sys.exit(1 if errors else 0)'
) -join "`n"
[System.IO.File]::WriteAllText($smokeFile, $smokeBody, [System.Text.UTF8Encoding]::new($false))
& $venvPython $smokeFile *>&1 | Tee-Object -FilePath (Join-Path $LOGS_DIR "smoke.log") | Out-Null
if ($LASTEXITCODE -eq 0) { OK "Brain-Stack Imports (10/10)" }
else { FAIL "Brain-Stack-Imports unvollstaendig - siehe $LOGS_DIR\smoke.log" }

# C.2 sqlite-vec verify
$env:PYTHONPATH = Join-Path $REPO_ROOT "src"
& $venvPython (Join-Path $REPO_ROOT "scripts\verify_sqlite_vec.py") *>&1 | Tee-Object -FilePath (Join-Path $LOGS_DIR "verify_sqlite_vec.log") | Out-Null
if ($LASTEXITCODE -eq 0) { OK "sqlite-vec KNN" }
else { FAIL "sqlite-vec verify scheitert" }

# C.3 DirectML verify (auf venv-Python, der gerade installiert wurde)
if ($SkipGpuVerify) {
    WARN "--SkipGpuVerify ist veraltet und wird ignoriert; DirectML-Verifikation bleibt verpflichtend."
}
$dml = Test-DirectML $venvPython
if ($dml -eq $true) { OK "ONNX Runtime DirectML Provider" }
elseif ($dml -eq $false) { FAIL "DirectML Provider fehlt - ML-Funktionen deaktiviert; kein CPU-Fallback" }
else { FAIL "DirectML-Vertrag nicht pruefbar (onnxruntime nicht ladbar)" }

# C.4 Legacy Nicht-ONNX-Verifier sind nach ADR0002/IRON R1 gesperrt.
Step "GPU-Vertrag wird ausschliesslich ueber ONNX Runtime DirectML geprueft"

# C.5 Pytest
if (-not $SkipPytest) {
    Step "pytest Tests/ (kann 60-90s dauern)..."
    & $venvPython -m pytest (Join-Path $REPO_ROOT "Tests") -q --tb=line *>&1 | Tee-Object -FilePath (Join-Path $LOGS_DIR "pytest.log") | Out-Null
    if ($LASTEXITCODE -eq 0) { OK "pytest gruen (siehe pytest.log)" }
    else { FAIL "pytest scheitert (siehe $LOGS_DIR\pytest.log)" }
} else {
    Step "Pytest uebersprungen (--SkipPytest)"
}

# =============================================================================
# Final Summary
# =============================================================================
Hdr "ERGEBNIS"
Write-Host "  OK:   $($global:Successes.Count)" -ForegroundColor Green
Write-Host "  WARN: $($global:Warnings.Count)" -ForegroundColor Yellow
Write-Host "  FAIL: $($global:Issues.Count)" -ForegroundColor $(if ($global:Issues.Count -gt 0) { "Red" } else { "Green" })

if ($global:Warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "  Warnungen:" -ForegroundColor Yellow
    $global:Warnings | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
}
if ($global:Issues.Count -gt 0) {
    Write-Host ""
    Write-Host "  Probleme:" -ForegroundColor Red
    $global:Issues | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
}

Write-Host ""
Write-Host "  Log: $LogFile" -ForegroundColor Gray
Write-Host ""
Write-Host "  Naechste Schritte:" -ForegroundColor Cyan
Write-Host "    1. Backend:    .\.venv\Scripts\Activate.ps1; `$env:PYTHONPATH='src'; python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765"
Write-Host "    2. WPF App:    dotnet run --project PBStudio.UI"
Write-Host "    3. Brain Verify Guide: docs\HARDWARE_VERIFY_GUIDE.md"
Write-Host "    4. Brain User Guide:   docs\BRAIN_USER_GUIDE.md"
Write-Host ""

Write-Host "  Transcript: $TranscriptFile" -ForegroundColor Gray
Write-Host ""

if ($global:Issues.Count -gt 0) {
    try { Stop-Transcript | Out-Null } catch {}
    if (-not $NoPause) { Read-Host "Press Enter to exit (mit Fehlern)" }
    exit 1
}

Write-Host "  Setup erfolgreich abgeschlossen." -ForegroundColor Green
try { Stop-Transcript | Out-Null } catch {}
if (-not $NoPause) { Read-Host "Press Enter" }
