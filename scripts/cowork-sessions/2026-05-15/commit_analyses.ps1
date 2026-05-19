# PB Studio — Cowork Audit-Analysen 2026-05-15
# Dead-Code (vulture), Dependency-Staleness, Static-Test-Coverage

if (Test-Path .git/index.lock) {
    Remove-Item -Force .git/index.lock
    Write-Host "[OK] Lock entfernt" -ForegroundColor Green
}

# Cleanup: temp run-artifacts nicht committen
Remove-Item -Force -ErrorAction SilentlyContinue `
    coverage_run.bat, coverage_static.bat, coverage_static.py, `
    coverage_output.log, coverage_static_output.log, `
    coverage_done.flag, coverage_static_done.flag, `
    kill_hung.bat, kill_done.flag, .coverage

git status --short
