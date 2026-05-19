# LM Studio Load-Model via native REST API
$outFile = 'C:\Users\david\Documents\Pb_studio_AMD_version\.lm_studio_load.json'

# Try loading via /api/v1/models/load (LM Studio native, NOT OpenAI)
# Try multiple candidate IDs as the API may accept different ID schemes
$candidates = @(
    'qwen3.5-9b-uncensored-hauhaucs-aggressive',
    'google/gemma-4-e4b',
    'gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf'
)

$result = [ordered]@{
    timestamp = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    attempts  = @()
    final_loaded = $null
}

foreach ($model_key in $candidates) {
    $entry = [ordered]@{
        model_key = $model_key
        status = $null
        response = $null
        error = $null
    }
    $body = @{ model_key = $model_key } | ConvertTo-Json -Compress
    try {
        $resp = Invoke-WebRequest -Uri 'http://localhost:1234/api/v1/models/load' `
            -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 60 -ErrorAction Stop
        $entry.status = [int]$resp.StatusCode
        $entry.response = $resp.Content
        $result.final_loaded = $model_key
        $result.attempts += $entry
        break
    } catch {
        $entry.error = $_.Exception.Message
        try {
            $errResp = $_.Exception.Response
            if ($errResp) {
                $entry.status = [int]$errResp.StatusCode
                $stream = $errResp.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $entry.response = $reader.ReadToEnd()
                $reader.Close()
            }
        } catch {}
        $result.attempts += $entry
    }
}

$result | ConvertTo-Json -Depth 10 | Out-File -FilePath $outFile -Encoding UTF8
Write-Host "DONE -> $outFile"
