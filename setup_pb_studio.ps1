<#
.SYNOPSIS
    PB Studio One-Click Installer (AMD Premium Edition) - v10 (Brain-Modul integriert)

.DESCRIPTION
    1. Enforces TLS 1.2 & User-Agent for secure downloads.
    2. Downloads/Installs VS Build Tools (Silent Fallback).
    3. Downloads FFmpeg (Gyan.dev Static) -> ./tools/ffmpeg.
    4. Downloads LibreHardwareMonitor (GitHub) -> ./tools/LibreHardwareMonitor.
    5. UNBLOCKS downloaded DLLs (Zone.Identifier security fix).
    6. Sets up Python 3.11 Venv.
    7. Installs full requirements.txt (AMD-ML Stack + Brain-Modul):
       torch 2.4.1 + torch-directml 0.2.5 (CLAP/SigLIP-2 GPU)
       transformers PIN 4.49.0 (CVE + SigLIP2-Tokenizer Constraint)
       sqlite-vec >=0.1.6 (KNN-Search im Embeddings-Store)
       librosa >=0.11 (Foote-SSM Sub-Track-Detector)
    8. Installs Brain pre-commit hook (Schema-Drift-Check).
    9. Optional: wöchentliches Brain-Backup als Windows Task einrichten.

    RUN AS ADMINISTRATOR REQUIRED!
#>

param (
    [switch]$SkipBuildTools = $false,
    [switch]$SkipBackupPrompt = $false,
    [switch]$NoPause = $false
)

$ErrorActionPreference = "Stop"
# EXPERT FIX: Force TLS 1.2
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$toolsDir = Join-Path $PSScriptRoot "tools"
if (-not (Test-Path $toolsDir)) { New-Item -ItemType Directory -Path $toolsDir | Out-Null }

Write-Host ">>> PB Studio Master Installer (AMD Expert v9 - No-Compile) <<<" -ForegroundColor Cyan

# 1. ADMIN CHECK
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "ERROR: Admin rights required for VS Build Tools & Symlinks."
    exit 1
}

# 2. VISUAL STUDIO BUILD TOOLS (Kept as Safety Net for PIP builds)
if (-not $SkipBuildTools) {
    # Check vswhere
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    $hasBuildTools = $false
    if (Test-Path $vsWhere) {
        $check = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($check) { $hasBuildTools = $true }
    }

    if ($hasBuildTools) {
        Write-Host "[+] VS Build Tools installed." -ForegroundColor Green
    }
    else {
        Write-Host "[!] Installing VS Build Tools (C++ Safety Net)..." -ForegroundColor Yellow
        # EXPERT FIX: UserAgent to prevent 403 Forbidden
        Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_buildtools.exe" -OutFile "$env:TEMP\vs_buildtools.exe" -UserAgent "PBStudioInstaller/1.0"
        $argsList = "--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
        Start-Process -FilePath "$env:TEMP\vs_buildtools.exe" -ArgumentList $argsList -Wait
        
        # EXPERT FIX: Refresh Environment Variables (VS modifies System Path)
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        Write-Host "[!] Refreshed Environment Variables." -ForegroundColor Cyan
    }
}

# 3. HELPER: Download & Extract Function
function Install-Tool ($url, $name, $destName) {
    $destDir = Join-Path $toolsDir $destName
    if (-not (Test-Path $destDir)) {
        Write-Host "[!] Downloading $name..." -ForegroundColor Yellow
        $zipPath = "$env:TEMP\$destName.zip"
        try {
            # EXPERT FIX: UserAgent
            Invoke-WebRequest -Uri $url -OutFile $zipPath -UserAgent "PBStudioInstaller/1.0"
            
            # RED TEAM FIX: Unblock File (Zone.Identifier)
            Unblock-File -Path $zipPath
            
            Write-Host "[!] Extracting $name..." -ForegroundColor Yellow
            Expand-Archive -Path $zipPath -DestinationPath "$env:TEMP\$destName" -Force
            
            # Handle nested folders
            $items = Get-ChildItem "$env:TEMP\$destName"
            if ($items.Count -eq 1 -and $items[0].PSIsContainer) {
                Move-Item -Path $items[0].FullName -Destination $destDir -Force
            }
            else {
                Move-Item -Path "$env:TEMP\$destName" -Destination $destDir -Force
            }
            
            # EXPERT FIX: Recursive Unblock on Destination
            Get-ChildItem -Path $destDir -Recurse | Unblock-File

        }
        catch {
            Write-Error "Failed to install $name. $_"
            exit 1
        }
        finally {
            if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
            if (Test-Path "$env:TEMP\$destName") { Remove-Item "$env:TEMP\$destName" -Recurse -Force -ErrorAction SilentlyContinue }
        }
        Write-Host "[+] $name Installed." -ForegroundColor Green
    }
    else {
        Write-Host "[+] $name already present." -ForegroundColor Green
    }
    return $destDir
}

# 4. INSTALL TOOLS (FFmpeg & LibreHardwareMonitor)
$ffmpegDir = Install-Tool "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" "FFmpeg" "ffmpeg"
$lhmDir = Install-Tool "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.5/LibreHardwareMonitor.zip" "LibreHardwareMonitor" "LibreHardwareMonitor"

if (-not (Test-Path "$lhmDir\LibreHardwareMonitorLib.dll")) {
    Write-Error "CRITICAL: LibreHardwareMonitorLib.dll not found."
    exit 1
}

# Add FFmpeg to Session Path & Persistent User Path
$ffmpegBin = "$ffmpegDir\bin"
if (-not ($env:Path -like "*$ffmpegBin*")) {
    $env:Path = "$ffmpegBin;" + $env:Path
    # Persist for future sessions
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not ($userPath -like "*$ffmpegBin*")) {
        [Environment]::SetEnvironmentVariable("Path", "$ffmpegBin;$userPath", "User")
        Write-Host "[+] Added FFmpeg to PERMANENT User Path." -ForegroundColor Green
    }
}

# 5. PYTHON 3.11 CHECK
try {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not ($py -and (& $py --version) -match "3.11")) {
        Write-Host "[!] Installing Python 3.11..." -ForegroundColor Yellow
        winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        $env:Path += ";$env:LocalAppData\Programs\Python\Python311"
    }
}
catch {
    Write-Warning "Python 3.11 check warning. Verify manually."
}

# 6. VENV & DEPS
$venvPath = "$PSScriptRoot\.venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating VENV..."
    python -m venv $venvPath
}
$pip = "$venvPath\Scripts\pip.exe"

Write-Host ">>> Installing Dependencies (AMD + Brain - STRICT)..." -ForegroundColor Cyan

# A. Upgrade Pip (Crucial for proper dependency resolution)
& $pip install --upgrade pip setuptools wheel

# EXPERT FIX: Install Numpy 1.26.4 FIRST to lock version before Numba/Librosa
Write-Host "    Locking Numpy 1.26.4..." -ForegroundColor Gray
& $pip install "numpy==1.26.4"

# B. Master requirements (single source of truth - incl. Brain stack)
$reqFile = Join-Path $PSScriptRoot "requirements.txt"
if (Test-Path $reqFile) {
    Write-Host "    Installing requirements.txt (AMD + Brain)..." -ForegroundColor Gray
    & $pip install -r $reqFile
} else {
    Write-Warning "requirements.txt missing - installing core only"
    & $pip install torch==2.4.1 torchvision==0.19.1 "torch-directml>=0.2.5"
    & $pip install transformers==4.49.0 huggingface_hub pythonnet
    & $pip install faiss-cpu==1.7.4 onnxruntime-directml==1.19.2
    & $pip install sqlite-vec
    & $pip install opencv-python
    & $pip install "audio-separator[dml]>=0.17.0" "librosa>=0.11.0" soundfile pydub ffmpeg-python
    & $pip install scenedetect fastapi uvicorn[standard] pydantic pydantic-settings httpx colorlog python-dotenv
}

# C. Brain post-install hooks (idempotent)
$venvPython = "$venvPath\Scripts\python.exe"
$preCommitScript = Join-Path $PSScriptRoot "scripts\install_pre_commit.ps1"
if (Test-Path $preCommitScript) {
    Write-Host "    Installing brain pre-commit hook..." -ForegroundColor Gray
    & $preCommitScript
}

# D. Optional: weekly brain backup scheduled task
$backupInstaller = Join-Path $PSScriptRoot "scripts\install_brain_backup_task.ps1"
if (Test-Path $backupInstaller) {
    if ($SkipBackupPrompt) {
        Write-Host "    Skipped (--SkipBackupPrompt) - run scripts\install_brain_backup_task.ps1 to install later" -ForegroundColor Gray
    } else {
        $resp = Read-Host "Wöchentliches Brain-Backup einrichten? (y/N)"
        if ($resp -match "^[Yy]") {
            & $backupInstaller
        } else {
            Write-Host "    Skipped - install later with: scripts\install_brain_backup_task.ps1" -ForegroundColor Gray
        }
    }
}

# E. Smoke verification (no GPU runs - just imports)
Write-Host ">>> Smoke verifying imports..." -ForegroundColor Cyan
$smoke = @'
import sys
errors = []
def check(mod):
    try:
        __import__(mod)
        print(f"  OK  {mod}")
    except Exception as e:
        errors.append((mod, str(e)))
        print(f"  FAIL {mod}: {e}")
for m in ["numpy","torch","torch_directml","transformers","sqlite_vec",
         "librosa","onnxruntime","cv2","fastapi","uvicorn"]:
    check(m)
sys.exit(1 if errors else 0)
'@
& $venvPython -c $smoke
if ($LASTEXITCODE -ne 0) { Write-Warning "Some imports failed - check above." }

Write-Host ">>> SETUP COMPLETE <<<" -ForegroundColor Green
Write-Host "Unified AMD Stack (DirectML) + Brain-Modul ready." -ForegroundColor Green
Write-Host "FFmpeg & LHM unter ./tools"
Write-Host ""
Write-Host "Nächste Schritte:" -ForegroundColor Yellow
Write-Host "  1. Backend:  .venv\Scripts\activate; `$env:PYTHONPATH='src'; python -m uvicorn backend.main:app --port 8765"
Write-Host "  2. WPF UI:   dotnet run --project PBStudio.UI"
Write-Host "  3. Tests:    .\run_full_test.ps1"
Write-Host "  4. Brain Verify: docs\HARDWARE_VERIFY_GUIDE.md"
if (-not $NoPause) { Read-Host "Done. Press Enter." }
