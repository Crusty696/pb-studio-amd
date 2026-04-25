# =============================================================================
# PB Studio AMD Edition - One-Click Installer
# =============================================================================
# Requires: Windows 10/11, AMD GPU (RX 5000+), Admin Rights recommended
# Usage: Right-click -> Run with PowerShell
#        Or: powershell -ExecutionPolicy Bypass -File .\install.ps1
# =============================================================================

param(
    [switch]$SkipPythonCheck,
    [switch]$SkipVenvCreate,
    [switch]$Verbose,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# =============================================================================
# CONSTANTS
# =============================================================================
$SCRIPT_VERSION = "1.0.0"
$PROJECT_NAME = "PB Studio AMD Premium Edition"
$VENV_NAME = ".venv"
$REQUIRED_PYTHON_MAJOR = 3
$REQUIRED_PYTHON_MINOR_MIN = 10
$REQUIRED_PYTHON_MINOR_MAX = 11

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([int]$Number, [string]$Text)
    Write-Host "[$Number] $Text" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Text)
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Text)
    Write-Host "[WARN] $Text" -ForegroundColor DarkYellow
}

function Write-Fail {
    param([string]$Text)
    Write-Host "[FAIL] $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "     $Text" -ForegroundColor Gray
}

function Test-AdminRights {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Find-PythonExecutable {
    # 1. Standard-Befehle probieren
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $out = & $cmd --version 2>&1
            if ($out -match "Python \d+\.\d+") {
                return $cmd
            }
        } catch { }
    }

    # 2. Windows Python Launcher mit Version probieren
    foreach ($ver in @("3.11", "3.10", "3.12", "3.9")) {
        try {
            $out = & py -$ver --version 2>&1
            if ($out -match "Python \d+\.\d+") {
                return "py -$ver"
            }
        } catch { }
    }

    # 3. Bekannte Installationspfade durchsuchen
    $searchPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe",
        "$env:ProgramFiles\Python312\python.exe"
    )
    foreach ($path in $searchPaths) {
        if (Test-Path $path) {
            return "`"$path`""
        }
    }

    return $null
}

$script:PythonExe = $null

function Get-PythonVersion {
    $candidates = @("python", "python3", "py")
    foreach ($ver in @("3.11", "3.10", "3.12", "3.9")) {
        $candidates += "py -$ver"
    }
    $searchPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe",
        "$env:ProgramFiles\Python312\python.exe"
    )
    foreach ($path in $searchPaths) {
        if (Test-Path $path) { $candidates += "`"$path`"" }
    }

    foreach ($cmd in $candidates) {
        try {
            $out = Invoke-Expression "$cmd --version 2>&1"
            if ($out -match "Python (\d+)\.(\d+)\.(\d+)") {
                $script:PythonExe = $cmd
                return @{
                    Major = [int]$Matches[1]
                    Minor = [int]$Matches[2]
                    Patch = [int]$Matches[3]
                    Full  = "$($Matches[1]).$($Matches[2]).$($Matches[3])"
                }
            }
        } catch { }
    }
    return $null
}

function Test-FFmpegAMF {
    try {
        $output = & ffmpeg -encoders 2>&1
        $hasH264 = $output -match "h264_amf"
        $hasHEVC = $output -match "hevc_amf"
        $hasAV1 = $output -match "av1_amf"
        return @{
            Available = ($hasH264 -or $hasHEVC)
            H264 = $hasH264
            HEVC = $hasHEVC
            AV1 = $hasAV1
        }
    } catch {
        return @{ Available = $false; H264 = $false; HEVC = $false; AV1 = $false }
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "$PROJECT_NAME - Installer v$SCRIPT_VERSION" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\install.ps1 [options]"
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  -SkipPythonCheck   Skip Python version validation"
    Write-Host "  -SkipVenvCreate    Skip virtual environment creation"
    Write-Host "  -Verbose           Show detailed output"
    Write-Host "  -Help              Show this help message"
    Write-Host ""
    Write-Host "Requirements:" -ForegroundColor Yellow
    Write-Host "  - Windows 10 (1903+) or Windows 11"
    Write-Host "  - AMD Radeon GPU (RX 5000 series or newer)"
    Write-Host "  - Python 3.10 or 3.11 (NOT 3.12!)"
    Write-Host "  - AMD Adrenalin Driver 24.x+"
    Write-Host ""
    exit 0
}

# =============================================================================
# MAIN INSTALLATION
# =============================================================================

if ($Help) { Show-Help }

Clear-Host
Write-Header "$PROJECT_NAME"
Write-Host "Installer Version: $SCRIPT_VERSION" -ForegroundColor Gray
Write-Host "Working Directory: $(Get-Location)" -ForegroundColor Gray
Write-Host ""

if (-not (Test-AdminRights)) {
    Write-Warn "Running without Administrator rights."
    Write-Info "Some features may require elevated privileges."
    Write-Host ""
}

$currentStep = 0

# =============================================================================
# STEP 1: Python Version Check
# =============================================================================
$currentStep++
Write-Step $currentStep "Checking Python Version..."

if ($SkipPythonCheck) {
    Write-Warn "Python check skipped by user request."
    # Trotzdem Python-Pfad ermitteln für spätere Schritte
    Get-PythonVersion | Out-Null
} else {
    $pythonInfo = Get-PythonVersion

    if ($null -eq $pythonInfo) {
        Write-Fail "Python not found!"
        Write-Info "Please install Python 3.10 or 3.11 from https://python.org"
        Write-Info "Tipp: Haken bei 'Add Python to PATH' im Installer setzen."
        exit 1
    }

    Write-Info "Found Python $($pythonInfo.Full) (via: $script:PythonExe)"

    $isValidVersion = ($pythonInfo.Major -eq $REQUIRED_PYTHON_MAJOR) -and
                      ($pythonInfo.Minor -ge $REQUIRED_PYTHON_MINOR_MIN) -and
                      ($pythonInfo.Minor -le $REQUIRED_PYTHON_MINOR_MAX)

    if (-not $isValidVersion) {
        Write-Fail "Python version $($pythonInfo.Full) is not supported!"
        Write-Info "Required: Python 3.10 or 3.11 (NOT 3.12+)"
        Write-Info "BeatNet has compatibility issues with Python 3.12+"
        exit 1
    }

    Write-Success "Python $($pythonInfo.Full) is compatible"
}

# =============================================================================
# STEP 2: Create Virtual Environment
# =============================================================================
$currentStep++
Write-Step $currentStep "Setting up Virtual Environment..."

$venvPath = Join-Path (Get-Location) $VENV_NAME
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

if ($SkipVenvCreate) {
    Write-Warn "Venv creation skipped by user request."
} else {
    if (Test-Path $venvPath) {
        Write-Info "Virtual environment already exists at $VENV_NAME"
    } else {
        Write-Info "Creating virtual environment..."
        Invoke-Expression "$script:PythonExe -m venv `"$VENV_NAME`""

        if (-not (Test-Path $venvPython)) {
            Write-Fail "Failed to create virtual environment!"
            exit 1
        }
        Write-Success "Virtual environment created at $VENV_NAME"
    }
}

if (-not (Test-Path $venvPython)) {
    Write-Fail "Virtual environment not found at $venvPath"
    exit 1
}

Write-Success "Virtual environment ready"

# =============================================================================
# STEP 3: Upgrade pip
# =============================================================================
$currentStep++
Write-Step $currentStep "Upgrading pip..."

try {
    & $venvPython -m pip install --upgrade pip --quiet
    Write-Success "pip upgraded successfully"
} catch {
    Write-Warn "pip upgrade failed, continuing..."
}

# =============================================================================
# STEP 4: Install Dependencies
# =============================================================================
$currentStep++
Write-Step $currentStep "Installing Dependencies (this may take several minutes)..."

Write-Info "Removing conflicting ONNX packages..."
& $venvPip uninstall onnxruntime onnxruntime-gpu -y 2>$null

$requirementsPath = Join-Path (Get-Location) "requirements.txt"
if (Test-Path $requirementsPath) {
    Write-Info "Installing from requirements.txt..."
    & $venvPip install -r $requirementsPath
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Dependencies installed from requirements.txt"
    } else {
        Write-Warn "Some packages failed - check output above"
    }
} else {
    Write-Warn "requirements.txt not found - installing core packages..."
    $corePackages = @(
        "numpy==1.26.4",
        "PyQt6>=6.8.0",
        "onnxruntime-directml>=1.16.0"
    )
    foreach ($pkg in $corePackages) {
        & $venvPip install $pkg
    }
}

Write-Success "Dependencies installation completed"

# =============================================================================
# STEP 5: Check FFmpeg with AMF
# =============================================================================
$currentStep++
Write-Step $currentStep "Checking FFmpeg AMF Support..."

$ffmpegInfo = Test-FFmpegAMF

if ($ffmpegInfo.Available) {
    Write-Success "FFmpeg with AMF encoder found"
    if ($ffmpegInfo.H264) { Write-Info "  - H.264 AMF: Available" }
    if ($ffmpegInfo.HEVC) { Write-Info "  - HEVC AMF: Available" }
    if ($ffmpegInfo.AV1) { Write-Info "  - AV1 AMF: Available" }
} else {
    Write-Warn "FFmpeg not found or missing AMF support"
    Write-Info "Download from: https://github.com/BtbN/FFmpeg-Builds/releases"
}

# =============================================================================
# STEP 6: Validate Installation
# =============================================================================
$currentStep++
Write-Step $currentStep "Validating Installation..."

$verifyScript = Join-Path (Get-Location) "verify_env_v2.py"
if (Test-Path $verifyScript) {
    & $venvPython $verifyScript
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Environment verification passed"
    } else {
        Write-Warn "Environment verification reported issues"
    }
} else {
    $validationCode = @'
import sys
print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
try:
    import onnxruntime as ort
    providers = ort.get_available_providers()
    dml = 'DmlExecutionProvider' in providers
    print(f"ONNX Runtime: {ort.__version__}")
    print(f"DirectML: {'OK' if dml else 'NOT Available'}")
except Exception as e:
    print(f"ONNX Runtime: Error - {e}")
'@
    & $venvPython -c $validationCode
}

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host ""
Write-Header "Installation Complete"

Write-Host "  Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. Activate the virtual environment:" -ForegroundColor White
Write-Host "     .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Start PB Studio:" -ForegroundColor White
Write-Host "     python run_ui.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Documentation: README.md" -ForegroundColor Gray
Write-Host ""
