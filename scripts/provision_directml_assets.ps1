<#
.SYNOPSIS
    Verifies and installs the approved PB Studio DirectML asset bundle.

.DESCRIPTION
    Fails closed unless the checked-in bundle manifest is approved and complete.
    ZIP entries are allowlisted before extraction, verified by size and SHA-256,
    staged on the target volume, then promoted with atomic file replacement and
    rollback.
#>

[CmdletBinding()]
param(
    [string]$ManifestPath = "",
    [string]$BundlePath = "",
    [string]$InstallRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:StagingRoot = $null
$script:BackupRoot = $null
$script:PreserveBackup = $false
$script:Promoted = New-Object System.Collections.Generic.List[object]

function Get-RequiredProperty {
    param(
        [Parameter(Mandatory)] [object]$Object,
        [Parameter(Mandatory)] [string]$Name
    )

    if (-not ($Object.PSObject.Properties.Name -contains $Name)) {
        throw "Manifestfeld fehlt: $Name"
    }
    $value = $Object.$Name
    if ($null -eq $value) {
        throw "Manifestfeld ist null: $Name"
    }
    return $value
}

function Assert-Text {
    param(
        [Parameter(Mandatory)] [object]$Value,
        [Parameter(Mandatory)] [string]$Field
    )

    if ($Value -isnot [string] -or [string]::IsNullOrWhiteSpace($Value)) {
        throw "Manifestfeld muss nicht-leerer Text sein: $Field"
    }
    return [string]$Value
}

function Assert-Sha256 {
    param(
        [Parameter(Mandatory)] [object]$Value,
        [Parameter(Mandatory)] [string]$Field
    )

    $hash = Assert-Text -Value $Value -Field $Field
    if ($hash -cnotmatch "^[0-9a-f]{64}$") {
        throw "Ungueltiger SHA-256 in $Field"
    }
    return $hash
}

function Assert-ImmutableRevision {
    param(
        [Parameter(Mandatory)] [object]$Value,
        [Parameter(Mandatory)] [string]$Field
    )

    $revision = Assert-Text -Value $Value -Field $Field
    if ($revision -cnotmatch "^[0-9a-f]{40,64}$") {
        throw "Revision in $Field ist kein unveraenderlicher Commit-Hash"
    }
    return $revision
}

function Assert-SafeRelativePath {
    param(
        [Parameter(Mandatory)] [object]$Value,
        [Parameter(Mandatory)] [string]$Field
    )

    $path = Assert-Text -Value $Value -Field $Field
    if ($path.Contains("\")) {
        throw "Backslashes sind in Bundlepfaden nicht erlaubt: $Field"
    }
    if ($path.StartsWith("/") -or $path.StartsWith("//") -or $path -match "^[A-Za-z]:") {
        throw "Absoluter Bundlepfad ist nicht erlaubt: $Field"
    }
    $segments = $path.Split("/")
    if ($segments.Count -eq 0) {
        throw "Leerer Bundlepfad: $Field"
    }
    foreach ($segment in $segments) {
        if ([string]::IsNullOrWhiteSpace($segment) -or $segment -eq "." -or $segment -eq "..") {
            throw "Unsicheres Pfadsegment in $Field"
        }
        if ($segment.EndsWith(".") -or $segment.EndsWith(" ")) {
            throw "Windows-ambiges Pfadsegment in $Field"
        }
        if ($segment.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0) {
            throw "Ungueltiges Windows-Pfadzeichen in $Field"
        }
        if ($segment -match "^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$") {
            throw "Reservierter Windows-Dateiname in $Field"
        }
    }
    return ($segments -join "/")
}

function Resolve-SafeInstallTarget {
    param(
        [Parameter(Mandatory)] [string]$RelativePath,
        [Parameter(Mandatory)] [string]$Root
    )

    if (-not $RelativePath.StartsWith("models/", [System.StringComparison]::Ordinal)) {
        throw "Installationsziel liegt nicht unter models/: $RelativePath"
    }
    $modelRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "models"))
    $modelPrefix = $modelRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $nativeRelative = $RelativePath.Replace("/", [System.IO.Path]::DirectorySeparatorChar)
    $target = [System.IO.Path]::GetFullPath((Join-Path $Root $nativeRelative))
    if (-not $target.StartsWith($modelPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Installationsziel verlaesst models/: $RelativePath"
    }
    return $target
}

function Read-ApprovedManifest {
    param([Parameter(Mandatory)] [string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "DirectML-Bundlemanifest fehlt: $Path"
    }
    try {
        $manifest = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    } catch {
        throw "DirectML-Bundlemanifest ist kein gueltiges JSON: $($_.Exception.Message)"
    }

    if ([int](Get-RequiredProperty -Object $manifest -Name "schema_version") -ne 1) {
        throw "Nicht unterstuetzte DirectML-Bundlemanifest-Version"
    }
    [void](Assert-Text -Value (Get-RequiredProperty -Object $manifest -Name "bundle_id") -Field "bundle_id")
    [void](Assert-Text -Value (Get-RequiredProperty -Object $manifest -Name "bundle_version") -Field "bundle_version")

    $approvalStatus = Assert-Text `
        -Value (Get-RequiredProperty -Object $manifest -Name "approval_status") `
        -Field "approval_status"
    if ($approvalStatus -cne "approved") {
        $blockerText = "keine Begruendung hinterlegt"
        if ($manifest.PSObject.Properties.Name -contains "approval_blockers") {
            $blockers = @($manifest.approval_blockers | ForEach-Object { [string]$_ })
            if ($blockers.Count -gt 0) {
                $blockerText = $blockers -join "; "
            }
        }
        throw "DirectML-Release-Bundle ist nicht freigegeben: $blockerText"
    }

    $archive = Get-RequiredProperty -Object $manifest -Name "archive"
    $archiveName = Assert-SafeRelativePath `
        -Value (Get-RequiredProperty -Object $archive -Name "file_name") `
        -Field "archive.file_name"
    if ($archiveName.Contains("/")) {
        throw "archive.file_name darf kein Verzeichnis enthalten"
    }
    [void](Assert-Sha256 `
        -Value (Get-RequiredProperty -Object $archive -Name "sha256") `
        -Field "archive.sha256")

    $files = @(Get-RequiredProperty -Object $manifest -Name "files")
    if ($files.Count -eq 0) {
        throw "Freigegebenes DirectML-Bundle enthaelt keine Dateien"
    }

    $archivePaths = New-Object "System.Collections.Generic.HashSet[string]" `
        ([System.StringComparer]::OrdinalIgnoreCase)
    $targets = New-Object "System.Collections.Generic.HashSet[string]" `
        ([System.StringComparer]::OrdinalIgnoreCase)
    $licensePaths = New-Object "System.Collections.Generic.HashSet[string]" `
        ([System.StringComparer]::Ordinal)
    $licenseReferences = New-Object System.Collections.Generic.List[string]

    foreach ($file in $files) {
        $archivePath = Assert-SafeRelativePath `
            -Value (Get-RequiredProperty -Object $file -Name "archive_path") `
            -Field "files.archive_path"
        $target = Assert-SafeRelativePath `
            -Value (Get-RequiredProperty -Object $file -Name "target") `
            -Field "files.target"
        [void](Resolve-SafeInstallTarget -RelativePath $target -Root $InstallRoot)
        if (-not $archivePaths.Add($archivePath)) {
            throw "Doppelter Bundlepfad: $archivePath"
        }
        if (-not $targets.Add($target)) {
            throw "Doppeltes Installationsziel: $target"
        }

        $size = [int64](Get-RequiredProperty -Object $file -Name "size")
        if ($size -lt 0) {
            throw "Negative Dateigroesse fuer $archivePath"
        }
        [void](Assert-Sha256 `
            -Value (Get-RequiredProperty -Object $file -Name "sha256") `
            -Field "files[$archivePath].sha256")

        $kind = Assert-Text `
            -Value (Get-RequiredProperty -Object $file -Name "kind") `
            -Field "files[$archivePath].kind"
        if (@("model", "runtime", "license", "metadata") -cnotcontains $kind) {
            throw "Unbekannter Dateityp fuer $archivePath"
        }
        if ($kind -eq "license") {
            [void]$licensePaths.Add($archivePath)
            continue
        }
        if ($kind -eq "model" -or $kind -eq "runtime") {
            $source = Get-RequiredProperty -Object $file -Name "source"
            [void](Assert-Text `
                -Value (Get-RequiredProperty -Object $source -Name "repository") `
                -Field "files[$archivePath].source.repository")
            [void](Assert-ImmutableRevision `
                -Value (Get-RequiredProperty -Object $source -Name "revision") `
                -Field "files[$archivePath].source.revision")
            [void](Assert-SafeRelativePath `
                -Value (Get-RequiredProperty -Object $source -Name "file") `
                -Field "files[$archivePath].source.file")
            [void](Assert-Sha256 `
                -Value (Get-RequiredProperty -Object $source -Name "sha256") `
                -Field "files[$archivePath].source.sha256")

            $license = Get-RequiredProperty -Object $file -Name "license"
            [void](Assert-Text `
                -Value (Get-RequiredProperty -Object $license -Name "spdx") `
                -Field "files[$archivePath].license.spdx")
            $licensePath = Assert-SafeRelativePath `
                -Value (Get-RequiredProperty -Object $license -Name "archive_path") `
                -Field "files[$archivePath].license.archive_path"
            $licenseReferences.Add($licensePath)
        }
    }

    foreach ($licensePath in $licenseReferences) {
        if (-not $licensePaths.Contains($licensePath)) {
            throw "Referenzierter Lizenztext fehlt in der Allowlist: $licensePath"
        }
    }
    return $manifest
}

function Test-InstalledBundle {
    param(
        [Parameter(Mandatory)] [object]$Manifest,
        [Parameter(Mandatory)] [string]$Root
    )

    foreach ($file in @($Manifest.files)) {
        $target = Resolve-SafeInstallTarget -RelativePath ([string]$file.target) -Root $Root
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            return $false
        }
        $item = Get-Item -LiteralPath $target
        if ($item.Length -ne [int64]$file.size) {
            return $false
        }
        $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -cne [string]$file.sha256) {
            return $false
        }
    }
    return $true
}

function Expand-VerifiedBundle {
    param(
        [Parameter(Mandatory)] [object]$Manifest,
        [Parameter(Mandatory)] [string]$ArchivePath,
        [Parameter(Mandatory)] [string]$Destination
    )

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $expected = @{}
    foreach ($file in @($Manifest.files)) {
        $expected[[string]$file.archive_path] = $file
    }

    $stream = [System.IO.File]::OpenRead($ArchivePath)
    try {
        $zip = New-Object System.IO.Compression.ZipArchive(
            $stream,
            [System.IO.Compression.ZipArchiveMode]::Read,
            $false
        )
        try {
            $seen = New-Object "System.Collections.Generic.HashSet[string]" `
                ([System.StringComparer]::OrdinalIgnoreCase)
            foreach ($entry in $zip.Entries) {
                $entryPath = Assert-SafeRelativePath -Value $entry.FullName -Field "zip.entry"
                if (-not $expected.ContainsKey($entryPath)) {
                    throw "Nicht allowlisteter ZIP-Eintrag: $entryPath"
                }
                if (-not $seen.Add($entryPath)) {
                    throw "Doppelter ZIP-Eintrag: $entryPath"
                }
                $unixType = (($entry.ExternalAttributes -shr 16) -band 0xF000)
                if ($unixType -eq 0xA000) {
                    throw "Symbolischer Link ist im Asset-Bundle verboten: $entryPath"
                }
                $declared = $expected[$entryPath]
                if ([int64]$entry.Length -ne [int64]$declared.size) {
                    throw "ZIP-Groesse stimmt nicht fuer $entryPath"
                }

                $relativeNative = $entryPath.Replace(
                    "/",
                    [System.IO.Path]::DirectorySeparatorChar
                )
                $destinationPath = [System.IO.Path]::GetFullPath(
                    (Join-Path $Destination $relativeNative)
                )
                $destinationPrefix = [System.IO.Path]::GetFullPath($Destination).TrimEnd(
                    [System.IO.Path]::DirectorySeparatorChar,
                    [System.IO.Path]::AltDirectorySeparatorChar
                ) + [System.IO.Path]::DirectorySeparatorChar
                if (-not $destinationPath.StartsWith(
                    $destinationPrefix,
                    [System.StringComparison]::OrdinalIgnoreCase
                )) {
                    throw "ZIP-Eintrag verlaesst das Staging: $entryPath"
                }
                [System.IO.Directory]::CreateDirectory(
                    [System.IO.Path]::GetDirectoryName($destinationPath)
                ) | Out-Null
                $inputStream = $entry.Open()
                try {
                    $outputStream = New-Object System.IO.FileStream(
                        $destinationPath,
                        [System.IO.FileMode]::CreateNew,
                        [System.IO.FileAccess]::Write,
                        [System.IO.FileShare]::None
                    )
                    try {
                        $inputStream.CopyTo($outputStream)
                    } finally {
                        $outputStream.Dispose()
                    }
                } finally {
                    $inputStream.Dispose()
                }
                $actual = (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actual -cne [string]$declared.sha256) {
                    throw "Einzelhash stimmt nicht fuer $entryPath"
                }
            }
            if ($seen.Count -ne $expected.Count) {
                $missing = @($expected.Keys | Where-Object { -not $seen.Contains($_) })
                throw "ZIP-Eintraege fehlen: $($missing -join ', ')"
            }
        } finally {
            $zip.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

function Restore-PromotedFiles {
    $restored = $true
    foreach ($operation in @($script:Promoted | Sort-Object Sequence -Descending)) {
        try {
            if ($operation.HadExisting) {
                if (Test-Path -LiteralPath $operation.Backup -PathType Leaf) {
                    if (Test-Path -LiteralPath $operation.Target -PathType Leaf) {
                        [System.IO.File]::Replace(
                            $operation.Backup,
                            $operation.Target,
                            $null,
                            $true
                        )
                    } else {
                        [System.IO.File]::Move($operation.Backup, $operation.Target)
                    }
                }
            } elseif (Test-Path -LiteralPath $operation.Target -PathType Leaf) {
                [System.IO.File]::Delete($operation.Target)
            }
        } catch {
            $restored = $false
            Write-Warning "Rollback fehlgeschlagen fuer $($operation.Target): $($_.Exception.Message)"
        }
    }
    return $restored
}

function Install-StagedBundle {
    param(
        [Parameter(Mandatory)] [object]$Manifest,
        [Parameter(Mandatory)] [string]$Stage,
        [Parameter(Mandatory)] [string]$Root
    )

    $sequence = 0
    foreach ($file in @($Manifest.files)) {
        $sequence += 1
        $archiveNative = ([string]$file.archive_path).Replace(
            "/",
            [System.IO.Path]::DirectorySeparatorChar
        )
        $staged = [System.IO.Path]::GetFullPath((Join-Path $Stage $archiveNative))
        $target = Resolve-SafeInstallTarget -RelativePath ([string]$file.target) -Root $Root
        [System.IO.Directory]::CreateDirectory(
            [System.IO.Path]::GetDirectoryName($target)
        ) | Out-Null

        if (Test-Path -LiteralPath $target -PathType Leaf) {
            $existingHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($existingHash -ceq [string]$file.sha256) {
                continue
            }
        }

        $backup = Join-Path $script:BackupRoot ("{0:D4}.bak" -f $sequence)
        $hadExisting = Test-Path -LiteralPath $target -PathType Leaf
        if ($hadExisting) {
            [System.IO.File]::Replace($staged, $target, $backup, $true)
        } else {
            [System.IO.File]::Move($staged, $target)
        }
        $script:Promoted.Add([pscustomobject]@{
            Sequence = $sequence
            Target = $target
            Backup = $backup
            HadExisting = $hadExisting
        })
    }
}

$exitCode = 0
try {
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
        $InstallRoot = Split-Path -Parent $PSScriptRoot
    }
    $InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
    if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
        $ManifestPath = Join-Path $InstallRoot "config\directml-asset-bundle.json"
    }
    $ManifestPath = [System.IO.Path]::GetFullPath($ManifestPath)
    $manifest = Read-ApprovedManifest -Path $ManifestPath

    if (Test-InstalledBundle -Manifest $manifest -Root $InstallRoot) {
        Write-Output "DirectML assets already match approved bundle $($manifest.bundle_id) $($manifest.bundle_version)."
    } else {
        if ([string]::IsNullOrWhiteSpace($BundlePath)) {
            $BundlePath = Join-Path $InstallRoot (
                "release-assets\" + [string]$manifest.archive.file_name
            )
        }
        $BundlePath = [System.IO.Path]::GetFullPath($BundlePath)
        if (-not (Test-Path -LiteralPath $BundlePath -PathType Leaf)) {
            throw "Freigegebenes DirectML-Asset-Bundle fehlt: $BundlePath"
        }
        if ([System.IO.Path]::GetFileName($BundlePath) -cne [string]$manifest.archive.file_name) {
            throw "Bundle-Dateiname stimmt nicht mit dem Manifest ueberein"
        }
        $archiveHash = (Get-FileHash -LiteralPath $BundlePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($archiveHash -cne [string]$manifest.archive.sha256) {
            throw "DirectML-Bundlehash stimmt nicht mit dem Manifest ueberein"
        }

        $modelsRoot = Join-Path $InstallRoot "models"
        [System.IO.Directory]::CreateDirectory($modelsRoot) | Out-Null
        $script:StagingRoot = Join-Path $modelsRoot (
            ".pb-directml-staging-" + [guid]::NewGuid().ToString("N")
        )
        $script:BackupRoot = Join-Path $modelsRoot (
            ".pb-directml-backup-" + [guid]::NewGuid().ToString("N")
        )
        [System.IO.Directory]::CreateDirectory($script:StagingRoot) | Out-Null
        [System.IO.Directory]::CreateDirectory($script:BackupRoot) | Out-Null

        Expand-VerifiedBundle `
            -Manifest $manifest `
            -ArchivePath $BundlePath `
            -Destination $script:StagingRoot
        try {
            Install-StagedBundle `
                -Manifest $manifest `
                -Stage $script:StagingRoot `
                -Root $InstallRoot
        } catch {
            if (-not (Restore-PromotedFiles)) {
                $script:PreserveBackup = $true
                throw "Asset-Promotion und Rollback fehlgeschlagen; Recovery-Backups bleiben erhalten: $script:BackupRoot"
            }
            throw
        }
        if (-not (Test-InstalledBundle -Manifest $manifest -Root $InstallRoot)) {
            if (-not (Restore-PromotedFiles)) {
                $script:PreserveBackup = $true
                throw "Abschlusspruefung und Rollback fehlgeschlagen; Recovery-Backups bleiben erhalten: $script:BackupRoot"
            }
            throw "Installierte DirectML-Assets bestehen die Abschlusspruefung nicht"
        }
        Write-Output "DirectML asset bundle $($manifest.bundle_id) $($manifest.bundle_version) installed and verified."
    }
} catch {
    Write-Error `
        "DirectML-Asset-Provisioning abgebrochen: $($_.Exception.Message)" `
        -ErrorAction Continue
    $exitCode = 1
} finally {
    foreach ($temporaryPath in @($script:StagingRoot)) {
        if (-not [string]::IsNullOrWhiteSpace($temporaryPath) -and
            (Test-Path -LiteralPath $temporaryPath)) {
            Remove-Item -LiteralPath $temporaryPath -Recurse -Force
        }
    }
    if (-not $script:PreserveBackup -and
        -not [string]::IsNullOrWhiteSpace($script:BackupRoot) -and
        (Test-Path -LiteralPath $script:BackupRoot)) {
        Remove-Item -LiteralPath $script:BackupRoot -Recurse -Force
    }
}

exit $exitCode
