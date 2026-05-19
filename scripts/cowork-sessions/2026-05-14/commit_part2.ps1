# PB Studio AMD — Commit-Skript Part 2 fuer Cowork-Session 2026-05-14
# Audit-Phase + Spec 00010 T003/T004 + Spec 00007 T011 + Spec 00009 progress markers

# 0. Lock entfernen falls noch da
if (Test-Path .git/index.lock) {
    Remove-Item -Force .git/index.lock
    Write-Host "[OK] .git/index.lock entfernt" -ForegroundColor Green
}

# 1. Spec-Marker-Update (T-Tasks die existierende Funktionalitaet abdecken)
git add specs/00007-release-hardening-ux-polish/tasks.md `
        specs/00009-data-depth-visualization/tasks.md `
        specs/00010-resilience-edge-cases/tasks.md
git commit -m @"
docs(specs): mark verified-done tasks from cowork audit part 2

Spec 00007 Release Hardening (T011 + T013):
- T011: VirtualizingStackPanel audit completed — VideoClipList +
  WaveformBars already use IsVirtualizing=True + Recycling-Mode.
  AudioClipList fix in separate commit.
- T013: MVVM consistency verified — 13/13 ViewModels use identical
  pattern: partial class, ObservableObject base, [ObservableProperty],
  [RelayCommand], no manual INotifyPropertyChanged, no SetProperty().

Spec 00009 Data Depth (T002/T003/T004/T005/T007/T009/T010):
- T002 Section-Detection: StructureAnalyzer (Novelty + Clustering)
- T003 Spectral extraction: SpectralAnalyzer (8-Band + Centroid + RMS)
- T004 Adaptive scene threshold: scene_detect.py uses AdaptiveDetector
- T005 Depth endpoints: /audio/spectral + /audio/structure exist
- T007 TimelineVM SongSegments + SpectralData properties
- T009 DepthRenderer.cs in PBStudio.UI/Controls/
- T010 DepthLayer + SongSegments overlay in TimelineView.xaml

Spec 00010 Resilience (T003 + T004):
- T003: SSEClient 5-attempt UI-Notify implemented (separate commit)
- T004: ConnectionStatus overlay implemented (separate commit)
"@

# 2. AudioClipList VirtualizingStackPanel (Spec 00007 T011)
git add PBStudio.UI/Views/AudioLibraryView.xaml
git commit -m @"
perf(ui): AudioClipList virtualization mode = Recycling (T011)

Spec 00007 T011: Add VirtualizingPanel.IsVirtualizing=True and
VirtualizationMode=Recycling to AudioClipList ListBox for consistency
with VideoClipList (which already had these). Default WPF behavior is
IsVirtualizing=True but VirtualizationMode=Standard (not recycling) —
explicit Recycling reuses item containers and reduces allocations for
long audio clip lists.

Verified:
- VideoClipList already uses Recycling
- WaveformBars (TimelineView) already uses Recycling
- Other ItemsControls without virtualization are either small fixed
  lists (BrainView segments, VramTelemetry stats) or Canvas-based
  (TimelineItemsControl — absolute positioning, not virtualizable)
"@

# 3. SSEClient 5-attempt UI-Notify (Spec 00010 T003)
git add PBStudio.UI/Services/SSEClient.cs
git commit -m @"
feat(sse): UI-notify after 5 failed reconnects (Spec 00010 T003)

Implements TR-001: SSEClient MUST implement a retry loop with max 5
attempts before notifying the UI.

Changes (purely additive — no breaking changes):
- New constant NotifyUiAfterAttempts = 5
- New event BackendReachabilityChanged (EventHandler<bool>)
- New property IsBackendReachable (latched, default true)
- On successful connect: IsBackendReachable = true (fires event)
- On reconnectAttempts >= 5: IsBackendReachable = false (fires event)

Existing ConnectionStateChanged event unchanged (still fires on every
connect/disconnect). New event is meant for UI overlay binding to
avoid flicker on brief drops (backend restart, transient network).

Refs: specs/00010-resilience-edge-cases TR-001
"@

# 4. ConnectionStatus Overlay (Spec 00010 T004)
git add PBStudio.UI/ViewModels/MainViewModel.cs `
        PBStudio.UI/MainWindow.xaml
git commit -m @"
feat(ui): ConnectionStatus overlay banner (Spec 00010 T004)

Implements TR-003: UI MUST show a non-modal warning when the connection
to the Python backend is interrupted.

MainViewModel.cs:
- New ObservableProperty IsBackendUnreachable (default false)
- Subscribes to SSEClient.BackendReachabilityChanged in ctor
- Handler dispatches !reachable to UI thread, sets IsBackendUnreachable
- Unsubscribes in Dispose

MainWindow.xaml:
- New Border element at Grid.Row=1 VerticalAlignment=Top,
  Panel.ZIndex=1000 — sits on top of tabs without shifting layout
- Visibility binds to IsBackendUnreachable via BooleanToVisibilityConverter
- Content: WifiOff icon + "Verbindung zum Backend verloren — versuche
  erneut..." in red banner (#FF8B1A1A)
- Auto-hide on successful reconnect (IsBackendReachable → true →
  IsBackendUnreachable → false → Visibility = Collapsed)

Refs: specs/00010-resilience-edge-cases TR-003 + SC-001
"@

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
git log --oneline -8
