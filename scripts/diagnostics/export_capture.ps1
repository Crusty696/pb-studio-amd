#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [string[]]$PrivateRoots = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$utf8 = New-Object Text.UTF8Encoding($false)
$input = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $InputPath -ErrorAction Stop).Path)
$output = [IO.Path]::GetFullPath($OutputPath)
$outputParent = Split-Path -Parent $output
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    throw "Export directory missing: $outputParent"
}
if ($input.Equals($output, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Sanitized export must not overwrite the private raw capture'
}
if (Test-Path -LiteralPath $output) {
    throw "Export already exists; refusing to overwrite: $output"
}

$credentialAssignment = '(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|owner[_-]?capability)\s*[:=]\s*[^\s,;]+'
$bearerToken = '(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+'
$nonceAssignment = '(?i)\b(nonce|health[_-]?proof)\s*[:=]\s*[^\s,;&]+'
$windowsPath = '(?i)(?:[A-Z]:\\[^\s"''<>|]+|\\\\[^\s"''<>|]+)'
$posixPrivatePath = '(?i)/(?:Users|home)/[^\s"''<>|]+'
$ownerCapability = [string]$env:PBSTUDIO_OWNER_CAPABILITY

function Protect-String {
    param([AllowEmptyString()][string]$Value)

    $sanitized = $Value
    if (-not [string]::IsNullOrEmpty($ownerCapability)) {
        $sanitized = $sanitized.Replace($ownerCapability, '<REDACTED>')
    }
    foreach ($privateRoot in $PrivateRoots) {
        if (-not [string]::IsNullOrWhiteSpace($privateRoot)) {
            $sanitized = $sanitized.Replace([IO.Path]::GetFullPath($privateRoot), '<PRIVATE_PATH>')
        }
    }
    $sanitized = [regex]::Replace($sanitized, $bearerToken, 'Bearer <REDACTED>')
    $sanitized = [regex]::Replace($sanitized, $credentialAssignment, '$1=<REDACTED>')
    $sanitized = [regex]::Replace($sanitized, $nonceAssignment, '$1=<REDACTED>')
    $sanitized = [regex]::Replace($sanitized, $windowsPath, '<PRIVATE_PATH>')
    $sanitized = [regex]::Replace($sanitized, $posixPrivatePath, '<PRIVATE_PATH>')
    return $sanitized
}

function Protect-Value {
    param(
        [AllowNull()]$Value,
        [string]$PropertyName = ''
    )

    if ($PropertyName -match '(?i)(authorization|api[_-]?key|token|secret|password|owner[_-]?capability|nonce|health[_-]?proof)') {
        return '<REDACTED>'
    }
    if ($null -eq $Value) {
        return $null
    }
    if ($Value -is [string]) {
        return Protect-String -Value $Value
    }
    if ($Value -is [Collections.IDictionary]) {
        $result = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $result[[string]$key] = Protect-Value -Value $Value[$key] -PropertyName ([string]$key)
        }
        return $result
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $result = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $result[$property.Name] = Protect-Value -Value $property.Value -PropertyName $property.Name
        }
        return $result
    }
    if ($Value -is [Collections.IEnumerable] -and -not ($Value -is [string])) {
        return @($Value | ForEach-Object { Protect-Value -Value $_ })
    }
    return $Value
}

function Assert-SafeValue {
    param([AllowNull()]$Value)

    if ($null -eq $Value) {
        return
    }
    if ($Value -is [string]) {
        if ($Value -match $windowsPath -or $Value -match $posixPrivatePath) {
            throw 'Sanitized value still contains an absolute private path'
        }
        if (-not [string]::IsNullOrEmpty($ownerCapability) -and $Value.Contains($ownerCapability)) {
            throw 'Sanitized value still contains the owner capability'
        }
        if ($Value -match $bearerToken -and $Value -notmatch 'Bearer\s+<REDACTED>') {
            throw 'Sanitized value still contains a bearer credential'
        }
        if (($Value -match $credentialAssignment -or $Value -match $nonceAssignment) -and $Value -notmatch '<REDACTED>') {
            throw 'Sanitized value still contains a credential or health-proof nonce'
        }
        return
    }
    if ($Value -is [Collections.IDictionary]) {
        foreach ($item in $Value.Values) { Assert-SafeValue -Value $item }
        return
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        foreach ($property in $Value.PSObject.Properties) { Assert-SafeValue -Value $property.Value }
        return
    }
    if ($Value -is [Collections.IEnumerable]) {
        foreach ($item in $Value) { Assert-SafeValue -Value $item }
    }
}

$sanitizedLines = New-Object Collections.Generic.List[string]
$lineNumber = 0
$sessionId = ''
$expectedSequence = 1L
$stopCount = 0
$lastEvent = ''
foreach ($line in [IO.File]::ReadLines($input, $utf8)) {
    $lineNumber++
    if ([string]::IsNullOrWhiteSpace($line)) {
        continue
    }
    try {
        $record = $line | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Raw capture is not valid JSONL at line ${lineNumber}: $($_.Exception.Message)"
    }
    if ([int]$record.schema_version -ne 1) {
        throw "Raw capture has an unsupported schema at line ${lineNumber}"
    }
    $recordSessionId = [string]$record.session_id
    if ([string]::IsNullOrWhiteSpace($recordSessionId)) {
        throw "Raw capture has no session id at line ${lineNumber}"
    }
    if ([string]::IsNullOrWhiteSpace($sessionId)) {
        $sessionId = $recordSessionId
    } elseif ($recordSessionId -ne $sessionId) {
        throw "Raw capture mixes sessions at line ${lineNumber}"
    }
    if ([long]$record.sequence -ne $expectedSequence) {
        throw "Raw capture sequence is not contiguous at line ${lineNumber}"
    }
    $expectedSequence++
    if ($stopCount -gt 0) {
        throw "Raw capture contains data after monitor_stopped at line ${lineNumber}"
    }
    $lastEvent = [string]$record.event
    if ($lastEvent -eq 'monitor_stopped') {
        $stopCount++
    }
    $sanitized = Protect-Value -Value $record
    Assert-SafeValue -Value $sanitized
    $sanitizedLines.Add(($sanitized | ConvertTo-Json -Compress -Depth 12))
}
if ($sanitizedLines.Count -eq 0) {
    throw 'Raw capture contains no records'
}
if ($stopCount -ne 1 -or $lastEvent -ne 'monitor_stopped') {
    throw 'Raw capture must contain exactly one terminal monitor_stopped receipt'
}

$temporary = Join-Path $outputParent ('.capture-export-' + [Guid]::NewGuid().ToString('N') + '.tmp')
try {
    [IO.File]::WriteAllText(
        $temporary,
        (($sanitizedLines -join [Environment]::NewLine) + [Environment]::NewLine),
        $utf8
    )
    Move-Item -LiteralPath $temporary -Destination $output
} finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Force
    }
}

Write-Output $output
