param(
    [Parameter(Mandatory = $true)]
    [string]$RunRoot,
    [Parameter(Mandatory = $true)]
    [string]$FfmpegBin,
    [Parameter(Mandatory = $true)]
    [int]$DeviceId,
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^0x[0-9A-Fa-f]{8}_0x[0-9A-Fa-f]{8}$")]
    [string]$AdapterLuid,
    [int]$DurationSeconds = 12
)

$ErrorActionPreference = "Stop"
$RunRoot = [IO.Path]::GetFullPath($RunRoot)
$FfmpegBin = [IO.Path]::GetFullPath($FfmpegBin)
$ffmpeg = Join-Path $FfmpegBin "ffmpeg.exe"
$ffprobe = Join-Path $FfmpegBin "ffprobe.exe"
$results = @()

foreach ($encoder in @("h264_amf", "hevc_amf")) {
    $captureRoot = Join-Path $RunRoot (
        "captures\{0}-{1}" -f $encoder, [guid]::NewGuid().ToString("N")
    )
    [IO.Directory]::CreateDirectory($captureRoot) | Out-Null
    $output = Join-Path $captureRoot "output.mp4"
    $progress = Join-Path $captureRoot "progress.log"
    $stdout = Join-Path $captureRoot "stdout.log"
    $stderr = Join-Path $captureRoot "stderr.log"
    $arguments = @(
        "-y", "-hide_banner", "-loglevel", "verbose",
        "-init_hw_device", "d3d11va=pb_amf:$DeviceId",
        "-re",
        "-f", "lavfi", "-i",
        "testsrc2=size=1920x1080:rate=60:duration=$DurationSeconds",
        "-pix_fmt", "yuv420p", "-c:v", $encoder,
        "-quality", "balanced", "-rc", "cbr", "-b:v", "12M",
        "-an", "-progress", $progress, $output
    )
    $process = Start-Process $ffmpeg `
        -ArgumentList $arguments `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr
    $samples = @()
    $samplingErrors = @()
    $deadline = (Get-Date).AddSeconds($DurationSeconds + 30)
    while (-not $process.HasExited -and (Get-Date) -lt $deadline) {
        try {
            $counter = Get-Counter "\GPU Engine(*)\Utilization Percentage"
            $samples += @(
                $counter.CounterSamples |
                    Where-Object {
                        $value = [double]$_.CookedValue
                        $_.InstanceName -match "pid_$($process.Id)_" -and
                        $_.Status -eq 0 -and
                        -not [double]::IsNaN($value) -and
                        -not [double]::IsInfinity($value) -and
                        $value -ge 0 -and
                        $value -le 110
                    } |
                    Select-Object Timestamp, InstanceName, CookedValue, Status
            )
        } catch {
            $samplingErrors += $_.Exception.Message
        }
        Start-Sleep -Milliseconds 100
        $process.Refresh()
    }
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        throw "$encoder exceeded the bounded runtime"
    }

    ConvertTo-Json -InputObject $samples -Depth 4 |
        Set-Content (Join-Path $captureRoot "gpu-pid.json") -Encoding utf8
    if (-not (Test-Path $output) -or (Get-Item $output).Length -eq 0) {
        throw "$encoder produced no output: $(Get-Content $stderr -Raw)"
    }
    if ((Get-Content $progress -Raw) -notmatch "progress=end") {
        throw "$encoder did not report terminal progress"
    }
    & $ffmpeg -v error -i $output -map 0:v:0 -f null NUL
    if ($LASTEXITCODE -ne 0) {
        throw "$encoder output does not fully decode"
    }
    $probeJson = & $ffprobe `
        -v error -count_frames -select_streams v:0 `
        -show_entries "stream=codec_name,width,height,avg_frame_rate,nb_read_frames:format=duration,size" `
        -of json $output
    if ($LASTEXITCODE -ne 0) {
        throw "$encoder ffprobe failed"
    }
    $probe = $probeJson | ConvertFrom-Json
    $expectedCodec = if ($encoder -eq "h264_amf") { "h264" } else { "hevc" }
    $stream = $probe.streams[0]
    if (
        $stream.codec_name -ne $expectedCodec -or
        $stream.width -ne 1920 -or
        $stream.height -ne 1080 -or
        $stream.avg_frame_rate -ne "60/1" -or
        [int]$stream.nb_read_frames -ne ($DurationSeconds * 60)
    ) {
        throw "$encoder output contract mismatch: $probeJson"
    }
    $rxSamples = @(
        $samples |
            Where-Object {
                $_.InstanceName -match ("luid_" + [regex]::Escape($AdapterLuid))
            }
    )
    $otherSamples = @(
        $samples |
            Where-Object {
                $_.InstanceName -match "luid_" -and
                $_.InstanceName -notmatch ("luid_" + [regex]::Escape($AdapterLuid))
            }
    )
    $rxMaximum = ($rxSamples | Measure-Object CookedValue -Maximum).Maximum
    if ([double]$rxMaximum -le 0) {
        throw "$encoder has no positive RX 7800 XT engine sample"
    }
    $result = [ordered]@{
        encoder = $encoder
        device_id = $DeviceId
        adapter_luid = $AdapterLuid
        ffmpeg_sha256 = (Get-FileHash $ffmpeg -Algorithm SHA256).Hash
        ffprobe_sha256 = (Get-FileHash $ffprobe -Algorithm SHA256).Hash
        capture_root = $captureRoot
        pid = $process.Id
        output_bytes = (Get-Item $output).Length
        output_sha256 = (Get-FileHash $output -Algorithm SHA256).Hash
        codec = $stream.codec_name
        width = $stream.width
        height = $stream.height
        frame_rate = $stream.avg_frame_rate
        readable_frames = [int]$stream.nb_read_frames
        duration = $probe.format.duration
        pid_engine_samples = $samples.Count
        sampling_errors = $samplingErrors
        rx_engine_max = $rxMaximum
        other_engine_max = (
            $otherSamples | Measure-Object CookedValue -Maximum
        ).Maximum
    }
    $result | ConvertTo-Json -Depth 6 |
        Set-Content (Join-Path $captureRoot "summary.json") -Encoding utf8
    $results += [pscustomobject]$result
}

$results | ConvertTo-Json -Depth 6
