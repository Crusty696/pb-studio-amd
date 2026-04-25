<#
.SYNOPSIS
    PB Studio One-Click Installer (AMD Premium Edition) - FINAL EXPERT v9 (No-Compile)
    Automates Setup: VS Build Tools (Safety), Python, FFmpeg, LibreHardwareMonitor, AMD-ML Stack.
    Now uses Moondream ONNX (DirectML) to guarantee 100% installation success without Vulkan SDK.

.DESCRIPTION
    1. Enforces TLS 1.2 & User-Agent for secure downloads.
    2. Downloads/Installs VS Build Tools (Silent Fallback).
    3. Downloads FFmpeg (Gyan.dev Static) -> ./tools/ffmpeg.
    4. Downloads LibreHardwareMonitor (GitHub) -> ./tools/LibreHardwareMonitor.
    5. UNBLOCKS downloaded DLLs (Zone.Identifier security fix).
    6. Sets up Python 3.11 Venv.
    7. Installs PyTorch CPU (No Nvidia Bloat).
    8. Installs Unified DirectML Stack (ONNX Runtime).
    9. Forces Strict Dependency Order (Numpy<2.0, OpenCV-GUI).

    RUN AS ADMINISTRATOR REQUIRED!
#>

param (
    [switch]$SkipBuildTools = $false
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

Write-Host ">>> Installing Dependencies (AMD Optimized v9 - STRICT)..." -ForegroundColor Cyan

# A. Upgrade Pip (Crucial for proper dependency resolution)
& $pip install --upgrade pip setuptools wheel

# EXPERT FIX: Install Numpy 1.26.4 FIRST to lock version before Numba/Librosa
Write-Host "    Locking Numpy 1.26.4..." -ForegroundColor Gray
& $pip install "numpy==1.26.4"

# B. PyTorch CPU (No Nvidia Bloat)
Write-Host "    Installing PyTorch (CPU)..." -ForegroundColor Gray
& $pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# C. Transformers & PythonNet
& $pip install transformers huggingface_hub pythonnet

# D. Core AMD ML (Unified DirectML Stack)
& $pip install faiss-cpu==1.7.4
& $pip install onnxruntime-directml==1.19.2
# Note: Moondream ONNX runs on this stack. No extra pip package needed besides transformers/ort.

# EXPERT FIX: Install OpenCV-Python BEFORE Scenedetect to avoid headless
& $pip install opencv-python

# E. Audio, Video & Backend
& $pip install "audio-separator[dml]>=0.17.0" librosa soundfile pydub ffmpeg-python
& $pip install scenedetect fastapi uvicorn[standard] pydantic pydantic-settings httpx colorlog python-dotenv

Write-Host ">>> SETUP COMPLETE <<<" -ForegroundColor Green
Write-Host "Unified AMD Stack (DirectML) Ready."
Write-Host "FFmpeg & LHM are in ./tools"
Read-Host "Done. Press Enter."
