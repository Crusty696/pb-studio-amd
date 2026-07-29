#Requires -Version 5.1

function Get-PBStudioRuntimeContract {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [switch]$RequirePython,
        [switch]$RequireFFmpeg,
        [switch]$ApplyEnvironment
    )

    $root = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
    $manifestPath = Join-Path $root 'config\ffmpeg-runtime.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "FFmpeg runtime manifest missing: $manifestPath"
    }

    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -ne 1) {
        throw "Unsupported FFmpeg runtime manifest schema: $($manifest.schema_version)"
    }

    $stableBin = Join-Path $root ([string]$manifest.stable_bin)
    $ffmpeg = Join-Path $stableBin 'ffmpeg.exe'
    $ffprobe = Join-Path $stableBin 'ffprobe.exe'
    $python = Join-Path $root '.venv\Scripts\python.exe'
    $pythonPath = Join-Path $root 'src'

    if ($RequirePython) {
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw "Canonical Python runtime missing: $python"
        }
        $version = (& $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not ([string]$version).StartsWith('3.11.')) {
            throw "Canonical Python runtime must be 3.11.x; got '$version' from $python"
        }
    }

    if ($RequireFFmpeg) {
        foreach ($item in @(
            @{ Path = $ffmpeg; Expected = [string]$manifest.active.ffmpeg_sha256; Name = 'ffmpeg.exe' },
            @{ Path = $ffprobe; Expected = [string]$manifest.active.ffprobe_sha256; Name = 'ffprobe.exe' }
        )) {
            if (-not (Test-Path -LiteralPath $item.Path -PathType Leaf)) {
                throw "Canonical $($item.Name) missing: $($item.Path)"
            }
            $actual = (Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash
            if ($actual -ne $item.Expected) {
                throw "Canonical $($item.Name) hash mismatch: expected $($item.Expected), got $actual"
            }
        }
    }

    foreach ($override in @(
        @{ Name = 'PBSTUDIO_FFMPEG_PATH'; Expected = $ffmpeg },
        @{ Name = 'PBSTUDIO_FFPROBE_PATH'; Expected = $ffprobe },
        @{ Name = 'PBSTUDIO_PYTHON_EXE'; Expected = $python }
    )) {
        $current = [Environment]::GetEnvironmentVariable($override.Name, 'Process')
        if ($current) {
            try {
                $resolved = [System.IO.Path]::GetFullPath($current)
                $expected = [System.IO.Path]::GetFullPath($override.Expected)
            } catch {
                throw "Invalid external runtime override $($override.Name): $current"
            }
            if (-not $resolved.Equals($expected, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "External runtime override $($override.Name) selects a non-canonical runtime: $current"
            }
        }
    }

    if ($ApplyEnvironment) {
        $env:PYTHONPATH = $pythonPath
        $env:PBSTUDIO_PYTHON_EXE = $python
        $env:PBSTUDIO_FFMPEG_PATH = $ffmpeg
        $env:PBSTUDIO_FFPROBE_PATH = $ffprobe
    }

    return [pscustomobject]@{
        ProjectRoot = $root
        PythonExe = $python
        PythonPath = $pythonPath
        FfmpegExe = $ffmpeg
        FfprobeExe = $ffprobe
        FfmpegVersion = [string]$manifest.active.version
        BackendArguments = @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8765')
        Manifest = $manifest
        ManifestPath = $manifestPath
    }
}
