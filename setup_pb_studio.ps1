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
        FFmpeg + LibreHardwareMonitor -> tools\
        Venv + pip install -r requirements.txt (Brain-Stack inkl.)
        Pre-commit Hook (Schema-Drift-Check)
        Optional: CLAP + SigLIP-2 Modelle pre-cachen
        Optional: Woechentliches Brain-Backup Task

    PHASE C - Verify
        Smoke imports
        sqlite-vec KNN
        Optional: CLAP+SigLIP DirectML GPU-Run
        Optional: WPF Build
        Optional: pytest

.PARAMETER SkipBuildTools
    VS Build Tools install ueberspringen (z.B. wenn bereits da).

.PARAMETER SkipBackupPrompt
    Auto-Backup-Task-Frage ueberspringen.

.PARAMETER SkipModelPrecache
    Auto-Download von CLAP+SigLIP Modellen ueberspringen (~1.8 GB).

.PARAMETER SkipGpuVerify
    DirectML-GPU-Verify ueberspringen (CLAP/SigLIP-Inferenz Test).

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
    & winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements *>&1 | Out-String | Add-Content $LogFile
    if ($LASTEXITCODE -eq 0) { OK "$pretty installiert" }
    else { FAIL "$pretty install fehlgeschlagen ($LASTEXITCODE)" }
}

function Install-Tool([string]$url, [string]$name, [string]$destName) {
    $destDir = Join-Path $TOOLS_DIR $destName
    if ((Test-Path $destDir) -and -not $Force) {
        OK "$name bereits in $destDir"
        return $destDir
    }
    Step "Download $name..."
    $zip = Join-Path $env:TEMP "$destName.zip"
    try {
        Invoke-WebRequest -Uri $url -OutFile $zip -UserAgent "PBStudioInstaller/11.0"
        Unblock-File -Path $zip
        $extractTmp = Join-Path $env:TEMP $destName
        if (Test-Path $extractTmp) { Remove-Item $extractTmp -Recurse -Force }
        Expand-Archive -Path $zip -DestinationPath $extractTmp -Force
        $items = Get-ChildItem $extractTmp
        if ($items.Count -eq 1 -and $items[0].PSIsContainer) {
            Move-Item -Path $items[0].FullName -Destination $destDir -Force
        } else {
            Move-Item -Path $extractTmp -Destination $destDir -Force
        }
        Get-ChildItem -Path $destDir -Recurse | Unblock-File
        OK "$name installiert nach $destDir"
        return $destDir
    } catch {
        FAIL "$name install fehlgeschlagen: $_"
        return $null
    } finally {
        if (Test-Path $zip) { Remove-Item $zip -Force }
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
    WARN "Keine AMD GPU erkannt - Brain laeuft auf CPU (langsam)"
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
if (Test-Path (Join-Path $TOOLS_DIR "ffmpeg")) { OK "FFmpeg in tools/ vorhanden" }
else { Step "FFmpeg fehlt - wird in Phase B geladen" }
if (Test-Path (Join-Path $TOOLS_DIR "LibreHardwareMonitor")) { OK "LibreHardwareMonitor in tools/ vorhanden" }
else { Step "LibreHardwareMonitor fehlt - wird in Phase B geladen" }

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
    $vcInstalled = $false
    if (Test-Admin -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Step "Versuche Visual C++ Redistributable via winget..."
        & winget install -e --id Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements *>&1 | Out-String | Add-Content $LogFile
        if (Test-VCRedist) { $vcInstalled = $true }
    }
    if (-not $vcInstalled) {
        Step "Visual C++ Redistributable fehlt. Downloade direkt von Microsoft..."
        $vcRedistPath = Join-Path $env:TEMP "vc_redist.x64.exe"
        try {
            Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $vcRedistPath -UserAgent "PBStudioInstaller/11.0"
            Unblock-File $vcRedistPath
            Step "Installiere Visual C++ Redistributable stillschweigend..."
            $proc = Start-Process -FilePath $vcRedistPath -ArgumentList "/quiet /norestart" -Wait -PassThru
            if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
                OK "Visual C++ Redistributable erfolgreich installiert"
            } else {
                WARN "Visual C++ Redistributable Installer beendet mit ExitCode: $($proc.ExitCode)"
            }
        } catch {
            WARN "Visual C++ Redistributable Download/Install fehlgeschlagen: $_"
        } finally {
            if (Test-Path $vcRedistPath) { Remove-Item $vcRedistPath -Force }
        }
    }
} else {
    OK "Visual C++ Redistributable (x64) bereits installiert"
}

# B.0.3 Git Auto-Check & Installation (sichert pre-commit hooks und checkout ab)
if (-not $global:HasGit) {
    $gitInstalled = $false
    if (Test-Admin -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Step "Versuche Git via winget..."
        Install-WingetPackage "Git.Git" "Git"
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
        if (Get-Command git -ErrorAction SilentlyContinue) { $gitInstalled = $true }
    }
    if (-not $gitInstalled) {
        Step "Git fehlt oder winget fehlgeschlagen. Installiere portables MinGit..."
        $gitDir = Install-Tool "https://github.com/git-for-windows/git/releases/download/v2.45.1.windows.1/MinGit-2.45.1-64-bit.zip" "MinGit" "git"
        if ($gitDir) {
            $cmdDir = Join-Path $gitDir "cmd"
            $env:Path = "$cmdDir;$env:Path"
            $userPath = [Environment]::GetEnvironmentVariable("Path","User")
            if (-not ($userPath -like "*$cmdDir*")) {
                [Environment]::SetEnvironmentVariable("Path","$cmdDir;$userPath","User")
                OK "MinGit in User-PATH ergaenzt"
            }
            $global:HasGit = $true
        }
    }
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
        Step "VS Build Tools install (gross, ~10 min)..."
        try {
            $ie = Join-Path $env:TEMP "vs_buildtools.exe"
            Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_buildtools.exe" -OutFile $ie -UserAgent "PBStudioInstaller/11.0"
            $a = "--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
            Start-Process -FilePath $ie -ArgumentList $a -Wait
            $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
            OK "VS Build Tools installiert"
        } catch { WARN "VS Build Tools install scheitert (nicht kritisch wenn Wheels verfuegbar): $_" }
    }
} else {
    Step "VS Build Tools uebersprungen (--SkipBuildTools)"
}

# B.2 Python 3.11 falls fehlt
if (-not $py -or $py.Minor -ne 11) {
    $pyInstalled = $false
    if (Test-Admin) {
        Step "Versuche Python 3.11 via winget..."
        Install-WingetPackage "Python.Python.3.11" "Python 3.11"
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
        $py = Get-PyExe
        if ($py -and $py.Minor -eq 11) { $pyInstalled = $true }
    }
    
    if (-not $pyInstalled) {
        Step "Python 3.11 fehlt oder winget fehlgeschlagen. Starte autonomen User-Scope Download..."
        $pyInstaller = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
        try {
            Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $pyInstaller -UserAgent "PBStudioInstaller/11.0"
            Unblock-File $pyInstaller
            Step "Installiere Python 3.11.9 stillschweigend im User-Scope (ohne Admin-Rechte)..."
            $installerArgs = "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1"
            $proc = Start-Process -FilePath $pyInstaller -ArgumentList $installerArgs -Wait -PassThru
            if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
                # PATH aktualisieren fuer den aktuellen Prozess
                $localPy = Join-Path $env:USERPROFILE "AppData\Local\Programs\Python\Python311"
                $localPyScripts = Join-Path $localPy "Scripts"
                $env:Path = "$localPy;$localPyScripts;$env:Path"
                
                # Permanente Pfadkopplung in der Registry fuer neue Shells + Batchdateien
                $userPath = [Environment]::GetEnvironmentVariable("Path","User")
                if (-not ($userPath -like "*$localPy*")) {
                    [Environment]::SetEnvironmentVariable("Path","$localPy;$localPyScripts;$userPath","User")
                    OK "Python 3.11 in User-PATH permanent registriert"
                }
                
                OK "Python 3.11.9 autonom im User-Scope installiert"
                $py = Get-PyExe
            } else {
                FAIL "Python 3.11.9 Installer beendet mit ExitCode: $($proc.ExitCode)"
            }
        } catch {
            FAIL "Autonomer Python-Download/Install fehlgeschlagen: $_"
        } finally {
            if (Test-Path $pyInstaller) { Remove-Item $pyInstaller -Force }
        }
    }
    
    if (-not $py -or $py.Minor -ne 11) {
        FAIL "Python 3.11 konnte nicht eingerichtet werden. Abbruch."
        exit 1
    }
}

# B.3 .NET 9 SDK falls fehlt
if (-not $dn -or $dn.Major -lt 9) {
    $dotnetInstalled = $false
    if (Test-Admin) {
        Step "Versuche .NET 9 SDK via winget..."
        Install-WingetPackage "Microsoft.DotNet.SDK.9" ".NET 9 SDK"
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
        $dn = Get-DotnetVer
        if ($dn -and $dn.Major -ge 9) { $dotnetInstalled = $true }
    }
    
    if (-not $dotnetInstalled) {
        Step ".NET 9 SDK fehlt oder winget fehlgeschlagen. Starte portable Installation..."
        $dotnetDest = Join-Path $TOOLS_DIR "dotnet"
        $scriptPath = Join-Path $env:TEMP "dotnet-install.ps1"
        try {
            Step "Downloade offizielles Microsoft dotnet-install.ps1 Skript..."
            Invoke-WebRequest -Uri "https://dot.net/v1/dotnet-install.ps1" -OutFile $scriptPath -UserAgent "PBStudioInstaller/11.0"
            Unblock-File $scriptPath
            
            Step "Installiere .NET 9.0 SDK portabel nach $dotnetDest..."
            $installArgs = @("-Channel", "9.0", "-InstallDir", $dotnetDest, "-Runtime", "dotnet")
            $proc = Start-Process -FilePath powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Channel 9.0 -InstallDir `"$dotnetDest`"" -Wait -PassThru
            if ($proc.ExitCode -eq 0) {
                $env:Path = "$dotnetDest;$env:Path"
                OK ".NET 9.0 SDK erfolgreich portabel installiert unter $dotnetDest"
                $dn = Get-DotnetVer
                
                # Permanente Pfadkopplung fuer WPF /dotnet build in nachfolgenden Shells
                $userPath = [Environment]::GetEnvironmentVariable("Path","User")
                if (-not ($userPath -like "*$dotnetDest*")) {
                    [Environment]::SetEnvironmentVariable("Path","$dotnetDest;$userPath","User")
                    OK ".NET SDK in User-PATH ergaenzt"
                }
            } else {
                FAIL "dotnet-install.ps1 beendet mit ExitCode: $($proc.ExitCode)"
            }
        } catch {
            FAIL "Portable .NET SDK Installation fehlgeschlagen: $_"
        } finally {
            if (Test-Path $scriptPath) { Remove-Item $scriptPath -Force }
        }
    }
    
    if (-not $dn -or $dn.Major -lt 9) {
        WARN ".NET 9.0 SDK fehlt. WPF-Build wird fehlschlagen."
    }
}

# B.4 FFmpeg + LHM
$ffmpegDir = Install-Tool "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" "FFmpeg" "ffmpeg"
$lhmDir = Install-Tool "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.5/LibreHardwareMonitor.zip" "LibreHardwareMonitor" "LibreHardwareMonitor"
if ($ffmpegDir) {
    $bin = Join-Path $ffmpegDir "bin"
    if (-not ($env:Path -like "*$bin*")) {
        $env:Path = "$bin;$env:Path"
        $userPath = [Environment]::GetEnvironmentVariable("Path","User")
        if (-not ($userPath -like "*$bin*")) {
            [Environment]::SetEnvironmentVariable("Path","$bin;$userPath","User")
            OK "FFmpeg in User-PATH ergaenzt"
        }
    }
}

# B.5 Venv
if ((Test-Path $VENV_PATH) -and -not $Force) {
    Step "venv existiert bereits ($VENV_PATH) - wird wiederverwendet (--Force fuer Neuanlage)"
} else {
    if (Test-Path $VENV_PATH) { Remove-Item $VENV_PATH -Recurse -Force }
    Step "Lege venv an mit Python $($py.Full)..."
    & $py.Cmd -m venv $VENV_PATH
    if ($LASTEXITCODE -ne 0) { FAIL "venv-Anlage scheitert"; exit 1 }
    OK "venv unter $VENV_PATH"
}
$venvPython = Join-Path $VENV_PATH "Scripts\python.exe"
$venvPip = Join-Path $VENV_PATH "Scripts\pip.exe"

# B.6 Pip + numpy lock
& $venvPython -m pip install --upgrade pip setuptools wheel *>&1 | Out-String | Add-Content $LogFile
& $venvPip install "numpy==1.26.4" *>&1 | Out-String | Add-Content $LogFile

# B.7 requirements.txt
$reqFile = Join-Path $REPO_ROOT "requirements.txt"
if (-not (Test-Path $reqFile)) { FAIL "requirements.txt nicht gefunden"; exit 1 }
Step "pip install -r requirements.txt (kann mehrere Minuten dauern)..."
& $venvPip install -r $reqFile *>&1 | Out-String | Add-Content $LogFile
if ($LASTEXITCODE -ne 0) { FAIL "pip install scheitert (siehe $LogFile)"; exit 1 }
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

# B.10 Optional: CLAP + SigLIP-2 Modelle pre-cachen
if (-not $SkipModelPrecache) {
    Step "Modelle pre-cachen (CLAP ~1.4 GB + SigLIP-2 ~370 MB) ..."
    $cacheFile = Join-Path $env:TEMP "pb_model_cache.py"
    $cacheBody = @(
        'import sys, os',
        'try:',
        '    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")',
        '    from transformers import ClapModel, ClapProcessor, AutoImageProcessor, AutoModel',
        '    print("Loading CLAP...")',
        '    ClapProcessor.from_pretrained("laion/larger_clap_music")',
        '    ClapModel.from_pretrained("laion/larger_clap_music")',
        '    print("Loading SigLIP-2 vision tower...")',
        '    AutoImageProcessor.from_pretrained("google/siglip2-base-patch16-384")',
        '    AutoModel.from_pretrained("google/siglip2-base-patch16-384", torch_dtype="float16")',
        '    print("OK models cached")',
        'except Exception as e:',
        '    print("Cache fehlgeschlagen: " + str(e), file=sys.stderr)',
        '    sys.exit(1)'
    ) -join "`n"
    [System.IO.File]::WriteAllText($cacheFile, $cacheBody, [System.Text.UTF8Encoding]::new($false))
    & $venvPython $cacheFile *>&1 | Out-String | Add-Content $LogFile
    if ($LASTEXITCODE -eq 0) { OK "Modelle gecached" }
    else { WARN "Modell-Cache scheitert (Brain-Verify in Phase C wird nachladen)" }
} else {
    Step "Model-Precache uebersprungen (--SkipModelPrecache)"
}

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
    'mods = ["numpy","torch","torch_directml","transformers","sqlite_vec",',
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
if ($LASTEXITCODE -eq 0) { OK "Brain-Stack Imports (11/11)" }
else { FAIL "Brain-Stack-Imports unvollstaendig - siehe $LOGS_DIR\smoke.log" }

# C.2 sqlite-vec verify
$env:PYTHONPATH = Join-Path $REPO_ROOT "src"
& $venvPython (Join-Path $REPO_ROOT "scripts\verify_sqlite_vec.py") *>&1 | Tee-Object -FilePath (Join-Path $LOGS_DIR "verify_sqlite_vec.log") | Out-Null
if ($LASTEXITCODE -eq 0) { OK "sqlite-vec KNN" }
else { FAIL "sqlite-vec verify scheitert" }

# C.3 DirectML verify (auf venv-Python, der gerade installiert wurde)
$dml = Test-DirectML $venvPython
if ($dml -eq $true) { OK "ONNX Runtime DirectML Provider" }
elseif ($dml -eq $false) { WARN "DirectML Provider fehlt - Brain laeuft auf CPU" }
else { Step "DirectML Test uebersprungen (onnxruntime nicht ladbar)" }

# C.4 GPU verify (CLAP + SigLIP)
if (-not $SkipGpuVerify) {
    $audio = Join-Path $REPO_ROOT "data\dummy_audio.wav"
    $video = Join-Path $REPO_ROOT "data\smoke_test_video.mp4"
    if (Test-Path $audio) {
        Step "CLAP DirectML run (kann 30-120s dauern)..."
        & $venvPython (Join-Path $REPO_ROOT "scripts\verify_clap_directml.py") $audio *>&1 | Tee-Object -FilePath (Join-Path $LOGS_DIR "verify_clap.log") | Out-Null
        if ($LASTEXITCODE -eq 0) { OK "CLAP DirectML inference" }
        else { WARN "CLAP DirectML inference scheitert (siehe verify_clap.log)" }
    }
    if (Test-Path $video) {
        Step "SigLIP-2 DirectML run..."
        & $venvPython (Join-Path $REPO_ROOT "scripts\verify_siglip_directml.py") $video *>&1 | Tee-Object -FilePath (Join-Path $LOGS_DIR "verify_siglip.log") | Out-Null
        if ($LASTEXITCODE -eq 0) { OK "SigLIP-2 DirectML inference" }
        else { WARN "SigLIP-2 DirectML inference scheitert (siehe verify_siglip.log)" }
    }
} else {
    Step "GPU-Verify uebersprungen (--SkipGpuVerify)"
}

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
Write-Host "    1. Backend:    .\.venv\Scripts\Activate.ps1; `$env:PYTHONPATH='src'; python -m uvicorn backend.main:app --port 8765"
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
