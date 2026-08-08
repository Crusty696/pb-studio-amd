# PB Studio — remove the dead pb_studio.workers package (2026-07-24 audit).
# Nothing in backend/ or src/ outside workers/ imports it (verified). This script
# is REVERSIBLE: it MOVES the tree into _to_delete_workers_backup/ instead of
# hard-deleting, so you can restore or run `git rm` yourself after confirming.
#
# Run from the repo root:  powershell -ExecutionPolicy Bypass -File .\delete_dead_workers.ps1
$ErrorActionPreference = "Stop"
$src = "src\pb_studio\workers"
if (-not (Test-Path $src)) { Write-Host "workers/ not found — nothing to do."; exit 0 }

# Safety: refuse if anything outside workers/ imports it.
$refs = Get-ChildItem -Recurse -Include *.py -Path "src","backend" |
  Where-Object { $_.FullName -notmatch "\\workers\\" } |
  Select-String -Pattern "pb_studio\.workers|from\s+\.\.?\.?workers|import\s+workers" -List
if ($refs) {
  Write-Host "ABORT: found external references to workers/ — review before deleting:"
  $refs | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber)" }
  exit 1
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$dest = "_to_delete_workers_backup_$ts"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Move-Item -Path $src -Destination (Join-Path $dest "workers")
Write-Host "Moved $src -> $dest\workers  (reversible)."
Write-Host "Verify the app + tests still pass, then delete $dest and commit:"
Write-Host "    git rm -r src/pb_studio/workers && git commit -m 'chore: remove dead workers package'"
