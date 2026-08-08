$ErrorActionPreference = 'Stop'

$repoDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$pythonExe = Join-Path $repoDir '.venv\Scripts\python.exe'
$exitPath = Join-Path $PSScriptRoot 'T338-final-full-suite.exit.txt'

$env:PYTHONPATH = 'src;.'
& $pythonExe -m pytest Tests/ -q
$testExit = $LASTEXITCODE
[System.IO.File]::WriteAllText(
    $exitPath,
    "$testExit`n",
    [System.Text.Encoding]::ASCII
)
exit $testExit
