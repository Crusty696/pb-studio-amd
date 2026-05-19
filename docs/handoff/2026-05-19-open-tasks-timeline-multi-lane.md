# Open Tasks — nach Timeline-Multi-Lane Merge (2026-05-19)

> Aufgenommen nach erfolgreichem PR-Merge `worktree-timeline-multi-lane @ 8ed0111` in `main`. Diese Liste fortlaufend abarbeiten in folgenden Sessions.

## Quick-Recall
- **Wiederfinden:** `cat docs/handoff/2026-05-19-open-tasks-timeline-multi-lane.md`
- **Memory-Pointer:** `project_open_tasks_post_timeline_merge` in `~/.claude/projects/.../memory/`
- **Vault-Pointer:** `10_Projects/PB_studio/open-tasks/2026-05-19-post-timeline-merge.md`
- **CLAUDE.md:** Sektion "Next Task" zeigt auf dieses Dokument

## Hart-Pending (echte Loose-Ends)

### 1. Live-Verify Timeline-UI
- **Was:** Visuelle Bestaetigung V1+A1 Lanes, Thumbnail-Strips, Per-Clip-Mini-Waveform, A1-Big-Waveform, Drag-Collision-Prevent, Auto-Gap-Close
- **Wie:** Backend starten, App launchen, Projekt oeffnen, Audio+Video importieren, Cut-Liste generieren, Timeline-Tab oeffnen, oben genannte Features pruefen
- **Status:** App geoeffnet 2026-05-19 nur fuer Projekt-Creation, kein Cut-List-Test

### 2. Parent's `bin/Release` stale
- **Was:** Nach Merge nicht rebuilt. Falls Launcher (`start.bat`, `launch.ps1`) genutzt: laedt alte DLL ohne V1+A1
- **Wie:** `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` in parent dir
- **Blocker:** Parent's working dir hat 47+ uncommitted MM-Files (Chat-Track-Rollback) — Build greift trotzdem auf working tree

### 3. Pre-staged Chat-Track-Rollback in parent main
- **Was:** 47+ uncommitted files seit Wochen pending (siehe `git status` in parent)
- **Inhalt:** Loescht LM-Studio + Chat-Track + Tool-Registry, MM diverse UI-Files
- **Optionen:**
  - Mergen (= LM-Studio raus) → User-Direktive noetig
  - Verwerfen (`git checkout -- .` in parent) → LM-Studio bleibt halb-broken
  - Eigener Branch + Commit + spaeter mergen
- **Status:** unangetastet, blockiert Branch-Switching in parent

### 4. Worktree-Branch loeschen
- **Was:** `worktree-timeline-multi-lane` auf remote nach Merge nicht mehr noetig
- **Wie:** `git push origin --delete worktree-timeline-multi-lane`
- **Risiko:** keiner (history erhalten via main FF)

### 5. Worktree-Dir entfernen
- **Was:** `.claude/worktrees/timeline-multi-lane/` (Disk-Space, post-Merge nutzlos)
- **Wie:** `git worktree remove --force .claude/worktrees/timeline-multi-lane`
- **Vorsicht:** dieses Handoff-Doc wurde IN diesem Worktree erstellt — vorher committen + nach parent kopieren

## LM-Studio-Korruption (Tech-Debt)

### 6. Vram-Stubs unvollstaendig
- **Was:** `/health/vram` Connection-Reset im UI-Log
- **Wo:** `PBStudio.UI/Models/VramTelemetry.cs` (Stubs in T6-Prereq, commit `53abecd`)
- **Wie:** Fix entweder Backend-Side `/health/vram`-Endpoint (warum reset?) oder Stub-Records an echte Backend-Response anpassen

### 7. LM-Studio-Refactor 8c46676 halb-broken
- **Was:** Surgical-Restore-Hack in `53abecd` deckt nur Build, nicht Funktion
- **Empfehlung:** Eigener Cleanup-Task — entweder full revert von 8c46676 ODER vollwertige Re-Implementation der LM-Studio-Bindings
- **Refs:** Memory `project_lm_studio_refactor_broken`

### 8. Chat-Track Files Konflikt
- **Was:** `BrainExplainResponse.cs`, `ChatViewModel.cs`, `ChatView.xaml`, `ChatEvent.cs`, `ChatMessage.cs` wurden in T6-Prereq RESTORED (waren in main als deleted geplant)
- **Konflikt:** User's Chat-Track-Rollback-Intent vs Timeline-Merge
- **Aktion:** User-Direktive — soll Chat-Track raus oder bleiben?

## Doku-Pending (per Iron Rules)

### 9. CHANGELOG.md
- **Was:** Timeline-Multi-Lane Eintrag (Commits c9dd4b7..8ed0111) fehlt
- **Format:** wie bisherige Eintraege (Bug-Liste / Feature-Liste pro Datum)

### 10. COWORK_AUTONOMY_LESSONS.md
- **Was:** Heutige Lessons fehlen
- **Patterns zum Eintragen:**
  - Pre-existing-HEAD-corruption Recovery (`brain_schemas.py`, `chat_router.py` Surgical Edit)
  - Partial-Rollback aus Parent Working-Dir + Stubs (commit `53abecd` Pattern)
  - Worktree-FF via `update-ref` ohne Branch-Switch in Parent (bypass uncommitted)

### 11. CLAUDE.md Status-Update
- **Was:** Sektion 3 (PROJECT BRAIN & CURRENT STATUS) zeigt noch "LM Studio Refactor Phase A LIVE-VERIFIED + Phase B Foundation"
- **Soll:** "Timeline-Multi-Lane gemerged 2026-05-19, Live-Verify pending"

## Original-Plan Drops (intentional, re-add optional)

### 12. DepthRenderer SpectralPoints Overlay
- **Was:** Cyan Spectral-Centroid-Line in V1-Lane war im alten Design
- **Status:** Aus T9-XAML entfernt, `SpectralPoints` ObservableCollection in VM erhalten
- **Re-Add:** `<controls:DepthRenderer Points="{Binding SpectralPoints}" ...>` zurueck in V1-Lane Border

### 13. SnapMarkers Onset-Rendering
- **Was:** Cyan vertikale Onset-Lines (separater Layer von BeatMarkers)
- **Status:** Aus T9-XAML entfernt, `SnapMarkers` ObservableCollection populiert
- **Re-Add:** ItemsControl-Block analog zu BeatMarkers

### 14. Song-Segment Label-TextBlock
- **Was:** "intro" / "verse" / "chorus" Text im Segment-Background
- **Status:** Nur farbiger Background bleibt
- **Re-Add:** TextBlock im SongSegment-Border-Template

### 15. VisualStateManager Animationen V1-Clips
- **Was:** MouseOver Opacity, Selected Yellow-Border, Snapped White-Border (Drag-Feedback)
- **Status:** Drag/Snap-Logic in Code-Behind intakt, nur Visual-Feedback weg
- **Re-Add:** VSM-Block in Border-Template

## Empfohlene Reihenfolge
1. **#1 Live-Verify** zuerst — UI-Probleme aufdecken bevor wir weiterbauen
2. **#9-#11 Doku** parallel — billig + verhindert Drift
3. **#3 Chat-Track-Rollback** User-Direktive einholen — blockiert sonst alles in parent
4. **#2 Parent rebuild** sobald #3 geklaert
5. **#4 #5 Cleanup** wenn #1 erfolgreich
6. **#12-#15** nur falls #1 zeigt dass User die Features vermisst
7. **#6 #7 #8 LM-Studio-Cleanup** separater Plan, eigene Brainstorm-Session
