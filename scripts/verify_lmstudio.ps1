# LM Studio Live-Verify Script - PB Studio AMD - 2026-05-17
# Output: repository root, .lm_studio_check.json
$ErrorActionPreference = 'Continue'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outFile = Join-Path $repoRoot '.lm_studio_check.json'

$result = [ordered]@{
    timestamp     = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    api_base      = 'http://localhost:1234/v1'
    server_up     = $false
    models        = @()
    raw_models    = $null
    tool_use_test = $null
    error         = $null
}

# 1. Check /v1/models
try {
    $resp = Invoke-RestMethod -Uri 'http://localhost:1234/v1/models' -TimeoutSec 6 -ErrorAction Stop
    $result.server_up  = $true
    $result.raw_models = $resp
    if ($resp.data) {
        $result.models = @($resp.data | ForEach-Object { $_.id })
    }
} catch {
    $result.error = "MODELS_ENDPOINT_FAIL: " + $_.Exception.Message
}

# 2. Tool-Use Test (only if at least one model loaded)
if ($result.server_up -and $result.models.Count -gt 0) {
    $testModel = $result.models[0]
    $body = @{
        model      = $testModel
        messages   = @(@{ role = 'user'; content = 'What is 7+5? Use the calculator tool.' })
        stream     = $false
        max_tokens = 80
        tools      = @(@{
            type = 'function'
            function = @{
                name = 'calculator'
                description = 'Add two numbers'
                parameters = @{
                    type = 'object'
                    properties = @{
                        a = @{ type = 'number' }
                        b = @{ type = 'number' }
                    }
                    required = @('a','b')
                }
            }
        })
    } | ConvertTo-Json -Depth 10 -Compress

    try {
        $tu = Invoke-RestMethod -Uri 'http://localhost:1234/v1/chat/completions' `
            -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 25 -ErrorAction Stop
        $result.tool_use_test = [ordered]@{
            model       = $testModel
            had_tool_call = $false
            response    = $tu
        }
        if ($tu.choices -and $tu.choices[0].message.tool_calls) {
            $result.tool_use_test.had_tool_call = $true
        }
    } catch {
        $result.tool_use_test = [ordered]@{
            model = $testModel
            error = $_.Exception.Message
        }
    }
}

$result | ConvertTo-Json -Depth 10 | Out-File -FilePath $outFile -Encoding UTF8
Write-Host "DONE -> $outFile"
