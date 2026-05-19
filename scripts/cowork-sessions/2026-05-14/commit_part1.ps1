# PB Studio AMD — Commit-Skript fuer heutige Cowork-Session 2026-05-14
# Erstellt von Claude Cowork. Lokal pruefen, dann ausfuehren.
# REIHENFOLGE: 1. Lock entfernen, 2. Commits 1-4 nacheinander.

# 0. Lock loswerden (falls noch stuck)
if (Test-Path .git/index.lock) {
    Remove-Item -Force .git/index.lock
    Write-Host "[OK] .git/index.lock entfernt" -ForegroundColor Green
}

# 1. Spec-Status Updates (T-Marker fuer abgeschlossene Tasks)
git add specs/00007-release-hardening-ux-polish/tasks.md `
        specs/00009-data-depth-visualization/tasks.md `
        specs/00010-resilience-edge-cases/tasks.md
git commit -m @"
docs(specs): mark verified-done tasks from cowork audit 2026-05-14

Spec 00007 Release Hardening:
- T001/T002: IDialogService.cs + DialogService.cs exist + registered
- T003-T006: 4 ViewModels migrated to IDialogService
- T007: AI Wrapper Iron-Rule-2 audit (5/5 wrappers OK)

Spec 00009 Data Depth:
- T001: StructureSegment + SpectralData schemas vorhanden (HEAD)

Spec 00010 Resilience:
- T001: PB_STUDIO_FORCED_VRAM bug fixed (constructor-AttributeError)
- T002: /health/heartbeat endpoint vorhanden
- T005: verify_low_vram_resilience.py script vorhanden
"@

# 2. VRAM Arbiter Bug-Fix (Spec 00010 T001)
git add src/pb_studio/core/vram_arbiter.py
git commit -m @"
fix(vram): VRAMArbiter constructor crash when PB_STUDIO_FORCED_VRAM is set

Move \``self._budget_manager = None\` initialization BEFORE the
\`if self.forced_limit > 0:\` block. Previously the if-block accessed
\`self.budget_manager\` (property) which dereferences \`self._budget_manager\`
— but that attr was only set 3 lines later, causing AttributeError on
constructor when env var was set.

Verified:
- with PB_STUDIO_FORCED_VRAM=4096 -> constructor OK, max_vram=4096
- without env var -> constructor OK, max_vram=8192 (fallback)

Refs: specs/00010-resilience-edge-cases T001 (TR-002)
"@

# 3. Cleanup: dev-scratch + dead-test placeholders
# (User-Pruefung: src/pb_studio/core/compression.py war pre-existing korrupt
#  und ist nicht in HEAD. Tests/test_*.py: pytest.skip-Placeholder weil
#  zugehoerige Backend-Fixes verloren sind und re-implementiert werden muessen.)
git add src/pb_studio/core/compression.py `
        Tests/test_motion_schema_forwarding.py `
        Tests/test_video_hash_persist.py
git commit -m @"
chore: placeholders for corrupted dev-scratch + lost-work tests

- src/pb_studio/core/compression.py: empty placeholder (pre-existing
  dev-scratch corruption; original content never landed in HEAD)
- Tests/test_motion_schema_forwarding.py: pytest.skip until X1/L-VIDEO-2
  fix (peak_motion) is re-implemented
- Tests/test_video_hash_persist.py: pytest.skip until X4/L-VIDEO-3 fix
  (video_hash persist) is re-implemented

Context: Linux->Windows-mount truncating-write bug in cowork sandbox
destroyed the original auto-qa-loop-2026-05-14 work (21 audit fixes
across 22 files). Original test files reference work that no longer
exists. See test-report/auto-qa-loop-2026-05-14-CRITICAL-CORRUPTION.md
for full incident postmortem.
"@

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
git log --oneline -5
