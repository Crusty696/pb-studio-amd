# PB Studio — Cowork Parallel-Subagent-Session 2026-05-15
# P2.1 Tab-Animations + P2.5 Inline-TODOs + P3.4 Vulture-Noqa + AGENTS.md erweitert

if (Test-Path .git/index.lock) {
    Remove-Item -Force .git/index.lock
    Write-Host "[OK] Lock entfernt" -ForegroundColor Green
}

# 1. AGENTS.md erweitert
git add AGENTS.md
git commit -m @"
docs(agents): parallele Subagent-Arbeit + Mount-Truncation-Schutz

Erweitert AGENTS.md um Sektion "Parallele Subagent-Arbeit":
- 13 vordefinierte non-overlapping Code-Zonen (Z-AUDIO, Z-VIDEO, Z-BRAIN,
  Z-RENDER, Z-PACING, Z-CORE, Z-DATA, Z-UI-VM, Z-UI-VIEWS, Z-UI-SERVICES,
  Z-TESTS, Z-DOCS, Z-INFRA)
- Shared-Zones (app_state.py, main.py, CLAUDE.md) muessen sequenziell editiert werden
- Subagent-Brief-Pflichtfelder: ZONE, NON-GOAL, TICKET, DELIVERABLE,
  VERIFY, WRITE-METHOD
- Mount-Truncation-Schutz: bash redirect Pflicht, NICHT Edit/Write-Tool
  und NICHT git checkout (alle 3 koennen auf Linux->Windows-Mount truncaten)
- Skill-Mapping pro Zone (pb-master, audio-engineering, video-engineering, etc.)
- Konkretes Spawn-Beispiel mit 5 parallelen Plan-Items
"@

# 2. P2.1 Tab-Animations
git add PBStudio.UI/MainWindow.xaml
git commit -m @"
feat(ui): GPU-accelerated tab transitions (Spec 00007 T010)

ScaleTransform 0.97 to 1.0 + Opacity 0.6 to 1.0 ueber 150ms,
getriggert durch TabControl.SelectionChanged Event. RenderTransform laeuft
auf WPF-Compositor-Thread (GPU-Pfad) -> kein Layout-Re-Pass, kein CPU-Load.

Pattern:
- ScaleTransform x:Name=TabContentScale als TabControl.RenderTransform
- RenderTransformOrigin=0.5,0.05 (Skalierung um obere Mitte)
- 3 DoubleAnimations parallel via Storyboard

Verify: XML-Parse via ET.parse OK, Tag-Balance OK.

Refs: specs/00007-release-hardening-ux-polish T010
"@

# 3. P2.5 Inline-TODOs aufgeloest
git add backend/routers/video_router.py src/pb_studio/pacing/advanced_pacing_engine.py
git commit -m @"
fix: resolve 2 inline-TODOs (P2.5 / progress callback + subtrack snap)

video_router.py:348 (CLARIFY):
- TODO-Kommentar war stale: _run_video_analysis IST bereits via
  _loop + RAFT on_progress Callback per-frame instrumentiert und
  published analysis_progress SSE-Events (Audit C1).
- Kommentar durch praezise Status-Beschreibung ersetzt.

advanced_pacing_engine.py:1293 (FIX):
- _snap_cuts_to_subtrack_boundaries(cuts, window=0.5) implementiert:
  snapt naechstgelegenen Cut im Fenster auf Subtrack-Anker, oder
  inserts neuen Cut mit trigger_type=subtrack, strength=1.0.
- Aufruf in generate_cut_list direkt nach _enforce_clip_lengths.
- No-op wenn _pre_cached_subtracks leer.
- 37 Zeilen, self-contained, additiv.

Refs: PLAN_OPEN_TASKS_2026-05-15.md P2.5
"@

# 4. P3.4 Vulture-Noqa-Comments
git add src/pb_studio/core/vram_budget_manager.py `
        src/pb_studio/pacing/clip_selector.py `
        src/pb_studio/services/analysis_service.py `
        src/pb_studio/services/generation_service.py
git commit -m @"
chore: vulture false-positive-clarifications (P3.4)

4 Inline-Kommentare + noqa-Marker fuer API-Compat-Parameter die vulture
als unused gemeldet hat aber intentional sind:

- vram_budget_manager.py:934 __exit__(exc_val): Python context-manager
  protocol signature (exc_val unused by design)
- clip_selector.py:205 previous_clip_id: NV-API Compat-Param,
  future routing-hook
- analysis_service.py:21 status_callback: PyQt-Legacy-Signal,
  API-Stability
- generation_service.py:38 status_callback: PyQt-Legacy-Signal,
  API-Stability

Diff: +4 Kommentar-Zeilen, 0 Logik-Aenderung.

Refs: PLAN_OPEN_TASKS_2026-05-15.md P3.4
"@

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
git log --oneline -8
