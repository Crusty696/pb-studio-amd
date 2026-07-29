$ErrorActionPreference = 'Stop'

$evidenceDir = $PSScriptRoot
$repoDir = (Resolve-Path (Join-Path $evidenceDir '..\..\..\..')).Path
$wpfExe = Join-Path $repoDir 'PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe'
$wpfWorkDir = Split-Path -Parent $wpfExe
$wpfLog = Join-Path $repoDir 'logs\wpf_app.log'
$screenshotDir = Join-Path $evidenceDir 'screenshots-cycle-5-xaml'
$reportPath = Join-Path $evidenceDir 'xaml-regression-cycle-5.json'

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class T337WindowApi
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int command);

    [DllImport("user32.dll")]
    public static extern bool PrintWindow(
        IntPtr hWnd,
        IntPtr deviceContext,
        uint flags
    );
}
'@

function Get-TabElement {
    param(
        [System.Windows.Automation.AutomationElement]$Root,
        [string]$Name
    )

    $condition = [System.Windows.Automation.AndCondition]::new(
        [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::NameProperty,
            $Name
        ),
        [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::TabItem
        )
    )
    $element = $Root.FindFirst(
        [System.Windows.Automation.TreeScope]::Descendants,
        $condition
    )
    if ($null -eq $element) {
        throw "Missing tab: $Name"
    }
    return $element
}

function Select-Tab {
    param(
        [System.Windows.Automation.AutomationElement]$Root,
        [string]$Name
    )

    $element = Get-TabElement -Root $Root -Name $Name
    $pattern = $element.GetCurrentPattern(
        [System.Windows.Automation.SelectionItemPattern]::Pattern
    )
    $pattern.Select()
    Start-Sleep -Milliseconds 750
    if (-not $pattern.Current.IsSelected) {
        throw "Tab did not become selected: $Name"
    }
}

function Get-VisibleNames {
    param([System.Windows.Automation.AutomationElement]$Root)

    $names = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::Ordinal
    )
    $elements = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    foreach ($element in $elements) {
        try {
            $current = $element.Current
            if ($current.IsOffscreen) {
                continue
            }
            if (
                $current.ControlType -ne
                    [System.Windows.Automation.ControlType]::Text -and
                $current.ControlType -ne
                    [System.Windows.Automation.ControlType]::Edit -and
                $current.ControlType -ne
                    [System.Windows.Automation.ControlType]::Button
            ) {
                continue
            }
            $name = $current.Name.Trim()
            if ($name) {
                [void]$names.Add($name)
            }
        }
        catch {
            continue
        }
    }
    return @($names | Sort-Object)
}

function Get-VisibleEditCount {
    param([System.Windows.Automation.AutomationElement]$Root)

    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Edit
    )
    $elements = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        $condition
    )
    $count = 0
    foreach ($element in $elements) {
        try {
            if (-not $element.Current.IsOffscreen) {
                $count++
            }
        }
        catch {
            continue
        }
    }
    return $count
}

function Save-WindowScreenshot {
    param(
        [IntPtr]$Handle,
        [string]$Path
    )

    $rect = [T337WindowApi+RECT]::new()
    if (-not [T337WindowApi]::GetWindowRect($Handle, [ref]$rect)) {
        throw "GetWindowRect failed for $Handle"
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -lt 1000 -or $height -lt 600) {
        throw "Window too small: ${width}x${height}"
    }
    $bitmap = [System.Drawing.Bitmap]::new($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $deviceContext = $graphics.GetHdc()
        try {
            $captured = [T337WindowApi]::PrintWindow(
                $Handle,
                $deviceContext,
                2
            )
        }
        finally {
            $graphics.ReleaseHdc($deviceContext)
        }
        if (-not $captured) {
            throw "PrintWindow failed for $Handle"
        }
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

$health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 5
if ($health.status -ne 'ok') {
    throw "Backend unhealthy: $($health | ConvertTo-Json -Compress)"
}
if (Get-Process -Name 'PBStudio.UI' -ErrorAction SilentlyContinue) {
    throw 'Unexpected PBStudio.UI process already running'
}

New-Item -ItemType Directory -Path $screenshotDir -Force | Out-Null
$env:PBSTUDIO_PYTHON_EXE = (Resolve-Path (
    Join-Path $repoDir '.venv\Scripts\python.exe'
)).Path
$ui = Start-Process `
    -FilePath $wpfExe `
    -WorkingDirectory $wpfWorkDir `
    -PassThru

try {
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        $ui.Refresh()
        if ($ui.HasExited -or $ui.MainWindowHandle -ne 0) {
            break
        }
    }
    if ($ui.HasExited -or $ui.MainWindowHandle -eq 0) {
        throw "Release UI failed: PID=$($ui.Id)"
    }

    $handle = [IntPtr]$ui.MainWindowHandle
    [void][T337WindowApi]::ShowWindow($handle, 9)
    [void][T337WindowApi]::ShowWindow($handle, 3)
    [void][T337WindowApi]::SetForegroundWindow($handle)
    Start-Sleep -Seconds 1

    $root = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
    if ($null -eq $root) {
        throw "AutomationElement unavailable: $handle"
    }

    Select-Tab -Root $root -Name 'MODELLE'
    $modelApi = Invoke-RestMethod `
        -Uri 'http://127.0.0.1:8765/models/list' `
        -TimeoutSec 15
    $installedCount = @($modelApi.models).Count
    $installedPrefix = "$installedCount installiert"
    $modelNames = @()
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        $modelNames = Get-VisibleNames -Root $root
        if (
            $modelNames |
                Where-Object { $_.StartsWith($installedPrefix) }
        ) {
            break
        }
    }
    $installedState = $modelNames |
        Where-Object { $_.StartsWith($installedPrefix) } |
        Select-Object -First 1
    if (-not $installedState) {
        throw "Models UI/API mismatch: expected prefix '$installedPrefix'"
    }
    $modelsScreenshot = Join-Path $screenshotDir 'modelle-after-refresh.png'
    Save-WindowScreenshot -Handle $handle -Path $modelsScreenshot

    Select-Tab -Root $root -Name 'EXPORT'
    Start-Sleep -Seconds 3
    $exportNames = Get-VisibleNames -Root $root
    $exportEditCount = Get-VisibleEditCount -Root $root
    if ($exportNames -notcontains 'RENDER LOG') {
        throw 'EXPORT render-log surface missing'
    }
    if ($exportEditCount -lt 5) {
        throw "EXPORT copyable/read-only surfaces missing: $exportEditCount"
    }
    $exportScreenshot = Join-Path $screenshotDir 'export-render-log.png'
    Save-WindowScreenshot -Handle $handle -Path $exportScreenshot

    Select-Tab -Root $root -Name 'TERMINAL'
    Start-Sleep -Seconds 3
    $terminalNames = Get-VisibleNames -Root $root
    if ($terminalNames -notcontains 'LIVE BACKEND TERMINAL') {
        throw 'TERMINAL surface missing'
    }
    $terminalScreenshot = Join-Path $screenshotDir 'terminal-after-model-refresh.png'
    Save-WindowScreenshot -Handle $handle -Path $terminalScreenshot

    Start-Sleep -Seconds 5
    $logText = Get-Content -LiteralPath $wpfLog -Raw
    $errorCounts = [ordered]@{
        xaml_parse_exception = (
            [regex]::Matches($logText, 'XamlParseException')
        ).Count
        path_xpath_failure = (
            [regex]::Matches(
                $logText,
                'Die bidirektionale Bindung erfordert "Path" oder "XPath"\.'
            )
        ).Count
        unhandled_ui_exception = (
            [regex]::Matches($logText, 'Unbehandelte UI-Exception')
        ).Count
        unobserved_task_exception = (
            [regex]::Matches($logText, 'Unbeobachtete Task-Exception')
        ).Count
    }
    if (($errorCounts.Values | Measure-Object -Sum).Sum -ne 0) {
        throw "WPF regression log gate failed: $(
            $errorCounts | ConvertTo-Json -Compress
        )"
    }

    $report = [ordered]@{
        status = 'pass'
        completed_at = [DateTimeOffset]::Now.ToString('o')
        process_id = $ui.Id
        window_handle = $handle.ToInt64()
        models = [ordered]@{
            api_installed_count = $installedCount
            ui_installed_state = $installedState
            base_url = $modelApi.base_url
            screenshot = $modelsScreenshot
        }
        export = [ordered]@{
            copyable_edit_count = $exportEditCount
            render_log_visible = $true
            screenshot = $exportScreenshot
        }
        terminal = [ordered]@{
            visible = $true
            screenshot = $terminalScreenshot
        }
        wpf_log = [ordered]@{
            path = $wpfLog
            bytes = (Get-Item -LiteralPath $wpfLog).Length
            error_counts = $errorCounts
        }
    }
    $report |
        ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $reportPath -Encoding utf8
    $report | ConvertTo-Json -Depth 8
}
finally {
    if ($null -ne $ui -and -not $ui.HasExited) {
        [void]$ui.CloseMainWindow()
        if (-not $ui.WaitForExit(5000)) {
            Stop-Process -Id $ui.Id
        }
    }
}
