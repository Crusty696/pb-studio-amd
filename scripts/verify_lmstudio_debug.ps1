# LM Studio debug - capture raw response body on errors
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outFile = Join-Path $repoRoot '.lm_studio_debug.json'

# Use a known-loaded model from /v1/models output
$model = 'qwen/qwen3-vl-8b'

$body = @{
    model = $model
    messages = @(@{ role = 'user'; content = 'Reply PING' })
    max_tokens = 12
    stream = $false
} | ConvertTo-Json -Depth 6 -Compress

$result = [ordered]@{
    model = $model
    body_sent = $body
    status_code = $null
    response_body = $null
    error = $null
}

try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:1234/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 60 -ErrorAction Stop
    $result.status_code = [int]$resp.StatusCode
    $result.response_body = $resp.Content
} catch {
    $result.error = $_.Exception.Message
    try {
        $errResp = $_.Exception.Response
        if ($errResp) {
            $result.status_code = [int]$errResp.StatusCode
            $stream = $errResp.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $result.response_body = $reader.ReadToEnd()
            $reader.Close()
        }
    } catch { $result.error += ' [no body: ' + $_.Exception.Message + ']' }
}

$result | ConvertTo-Json -Depth 10 | Out-File -FilePath $outFile -Encoding UTF8
Write-Host "DONE -> $outFile"
