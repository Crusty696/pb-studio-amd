# Full LM Studio verify with loaded model - 2026-05-17
$outFile = 'C:\Users\david\Documents\Pb_studio_AMD_version\.lm_studio_verify_full.json'
$model = 'qwen3.5-9b-uncensored-hauhaucs-aggressive'

$result = [ordered]@{
    timestamp = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    model     = $model
    server_ok  = $false
    basic_ok   = $false
    basic_text = $null
    basic_err  = $null
    tool_ok    = $false
    tool_call  = $null
    tool_err   = $null
    stream_ok  = $false
    stream_chunks = 0
    embed_ok   = $false
    embed_dim  = $null
    embed_err  = $null
}

# Server check
try {
    $m = Invoke-RestMethod -Uri 'http://localhost:1234/v1/models' -TimeoutSec 6 -ErrorAction Stop
    if ($m.data) { $result.server_ok = $true }
} catch { }

# Basic non-streaming chat
$bodyBasic = @{
    model = $model
    messages = @(@{ role = 'user'; content = 'Reply with the single word PING and nothing else.' })
    max_tokens = 12
    stream = $false
    temperature = 0.1
} | ConvertTo-Json -Depth 6 -Compress
try {
    $r = Invoke-RestMethod -Uri 'http://localhost:1234/v1/chat/completions' -Method Post -Body $bodyBasic -ContentType 'application/json' -TimeoutSec 120 -ErrorAction Stop
    $result.basic_ok = $true
    $result.basic_text = $r.choices[0].message.content
} catch {
    $result.basic_err = $_.Exception.Message
    try {
        $errResp = $_.Exception.Response
        if ($errResp) {
            $stream = $errResp.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $result.basic_err += ' | body: ' + $reader.ReadToEnd()
        }
    } catch {}
}

# Tool call test
if ($result.basic_ok) {
    $bodyTool = @{
        model = $model
        messages = @(@{ role = 'user'; content = 'Use the get_time tool to get the current time. Call it.' })
        max_tokens = 200
        stream = $false
        temperature = 0.1
        tools = @(@{
            type = 'function'
            function = @{
                name = 'get_time'
                description = 'Returns current time as ISO string.'
                parameters = @{ type = 'object'; properties = @{}; required = @() }
            }
        })
        tool_choice = 'auto'
    } | ConvertTo-Json -Depth 10 -Compress
    try {
        $r = Invoke-RestMethod -Uri 'http://localhost:1234/v1/chat/completions' -Method Post -Body $bodyTool -ContentType 'application/json' -TimeoutSec 120 -ErrorAction Stop
        if ($r.choices[0].message.tool_calls) {
            $result.tool_ok = $true
            $result.tool_call = $r.choices[0].message.tool_calls[0]
        } else {
            $result.tool_err = 'No tool_calls. Content: ' + ($r.choices[0].message.content -replace '\s+', ' ')
        }
    } catch { $result.tool_err = $_.Exception.Message }
}

# Streaming test (just count chunks until done)
if ($result.basic_ok) {
    $bodyStream = @{
        model = $model
        messages = @(@{ role = 'user'; content = 'Count from 1 to 5.' })
        max_tokens = 50
        stream = $true
        temperature = 0.1
    } | ConvertTo-Json -Depth 6 -Compress
    try {
        Add-Type -AssemblyName System.Net.Http
        $client = New-Object System.Net.Http.HttpClient
        $client.Timeout = [TimeSpan]::FromSeconds(60)
        $req = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, 'http://localhost:1234/v1/chat/completions')
        $req.Content = New-Object System.Net.Http.StringContent($bodyStream, [System.Text.Encoding]::UTF8, 'application/json')
        $resp = $client.SendAsync($req, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).Result
        if ($resp.IsSuccessStatusCode) {
            $reader = New-Object System.IO.StreamReader($resp.Content.ReadAsStream())
            while (-not $reader.EndOfStream) {
                $line = $reader.ReadLine()
                if ($line -and $line.StartsWith('data:')) {
                    $payload = $line.Substring(5).Trim()
                    if ($payload -eq '[DONE]') { break }
                    $result.stream_chunks++
                }
            }
            $reader.Close()
            $result.stream_ok = ($result.stream_chunks -gt 0)
        }
        $client.Dispose()
    } catch { }
}

# Embeddings test
try {
    $bodyEmbed = @{
        model = 'text-embedding-nomic-embed-text-v1.5'
        input = 'Hello world'
    } | ConvertTo-Json -Depth 6 -Compress
    $r = Invoke-RestMethod -Uri 'http://localhost:1234/v1/embeddings' -Method Post -Body $bodyEmbed -ContentType 'application/json' -TimeoutSec 60 -ErrorAction Stop
    if ($r.data -and $r.data[0].embedding) {
        $result.embed_ok = $true
        $result.embed_dim = $r.data[0].embedding.Count
    }
} catch { $result.embed_err = $_.Exception.Message }

$result | ConvertTo-Json -Depth 10 | Out-File -FilePath $outFile -Encoding UTF8
Write-Host "DONE -> $outFile"
