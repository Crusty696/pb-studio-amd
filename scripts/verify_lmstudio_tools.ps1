# LM Studio Tool-Use Test - test multiple text models - 2026-05-17
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outFile = Join-Path $repoRoot '.lm_studio_tools_check.json'

# Candidates (skip vision model + embedding model)
$candidates = @(
    'qwen3.5-9b-uncensored-hauhaucs-aggressive',
    'gemma-4-31b-it-uncensored',
    'raw-uncensored-qwen3-14b-heretic-recovered',
    'google/gemma-4-e4b'
)

$results = @()
foreach ($m in $candidates) {
    $entry = [ordered]@{ model = $m; ok_basic = $false; ok_tool = $false; tool_call = $null; basic_text = $null; basic_err = $null; tool_err = $null }

    # Basic chat test
    $bodyBasic = @{
        model = $m
        messages = @(@{ role = 'user'; content = 'Reply with the single word PING' })
        max_tokens = 12
        stream = $false
    } | ConvertTo-Json -Depth 6 -Compress
    try {
        $r = Invoke-RestMethod -Uri 'http://localhost:1234/v1/chat/completions' -Method Post -Body $bodyBasic -ContentType 'application/json' -TimeoutSec 60 -ErrorAction Stop
        $entry.ok_basic = $true
        $entry.basic_text = $r.choices[0].message.content
    } catch {
        $entry.basic_err = $_.Exception.Message
    }

    if ($entry.ok_basic) {
        # Tool test
        $bodyTool = @{
            model = $m
            messages = @(@{ role = 'user'; content = 'Call get_time to get the current time.' })
            max_tokens = 100
            stream = $false
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
            $r = Invoke-RestMethod -Uri 'http://localhost:1234/v1/chat/completions' -Method Post -Body $bodyTool -ContentType 'application/json' -TimeoutSec 60 -ErrorAction Stop
            if ($r.choices[0].message.tool_calls) {
                $entry.ok_tool = $true
                $entry.tool_call = $r.choices[0].message.tool_calls[0]
            } else {
                $entry.tool_err = 'No tool_calls in response. Content: ' + $r.choices[0].message.content
            }
        } catch {
            $entry.tool_err = $_.Exception.Message
        }
    }
    $results += $entry
}

@{ tested_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'); results = $results } |
    ConvertTo-Json -Depth 10 | Out-File -FilePath $outFile -Encoding UTF8
Write-Host "DONE -> $outFile"
