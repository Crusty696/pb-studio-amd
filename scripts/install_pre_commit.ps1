# Plan Phase 0 #4: install pre-commit hook for schema drift check.
# Run once after clone or worktree setup. Hook scope: shared via main .git dir.

$ErrorActionPreference = "Stop"

$RepoRoot = git rev-parse --show-toplevel
$HookFile = Join-Path $RepoRoot ".git\hooks\pre-commit"

$Body = @(
    '#!/bin/sh',
    '# Plan Phase 0 #4: schema drift check before every commit.',
    '# Resolves .venv from the common-dir when running inside a worktree.',
    'REPO_ROOT="$(git rev-parse --show-toplevel)"',
    'COMMON_GITDIR="$(git rev-parse --git-common-dir)"',
    'MAIN_REPO_ROOT="$(cd "$COMMON_GITDIR/.." && pwd)"',
    'PYTHON_EXE="$REPO_ROOT/.venv/Scripts/python.exe"',
    '[ -x "$PYTHON_EXE" ] || PYTHON_EXE="$MAIN_REPO_ROOT/.venv/Scripts/python.exe"',
    '[ -x "$PYTHON_EXE" ] || PYTHON_EXE="python"',
    '"$PYTHON_EXE" "$REPO_ROOT/scripts/check_trigger_settings_drift.py"',
    'RC=$?',
    'if [ $RC -ne 0 ]; then',
    '    echo "[pre-commit] Schema-Drift detected. Commit blocked."',
    '    exit 1',
    'fi',
    'exit 0'
)

# UTF-8 without BOM, LF line endings — required by Git for Windows hook execution.
$Text = ($Body -join "`n") + "`n"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($HookFile, $Text, $Utf8NoBom)
Write-Host "Installed pre-commit hook at $HookFile"
