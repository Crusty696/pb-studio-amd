---
feature_branch: "00012-timeline-high-fidelity-playback-beatgrid"
created: "2026-05-22"
spec_path: "specs/00012-timeline-high-fidelity-playback-beatgrid/spec.md"
plan_path: "specs/00012-timeline-high-fidelity-playback-beatgrid/plan.md"
---

# Tasks: Timeline High-Fidelity Playback & DJ-Beatgrid

## Work Item Checklist

### Setup & Foundation
- [ ] T001 [P] [OBJ-1] {FR-001} Create `WaveformRenderer.cs` GPU-accelerated custom control in `PBStudio.UI/Controls/`
- [ ] T002 [P] [OBJ-2] {FR-002} Implement playback seamless transition at clip borders in `TimelineView.xaml.cs`
- [ ] T003 [P] [OBJ-3] {FR-003} Incorporate `WaveformRenderer` and high-contrast DJ-Beatgrid in `TimelineView.xaml`
- [ ] T004 [P] [OBJ-4] {FR-004} Refine song phrase coloring & watermarks in `TimelineView.xaml`
- [ ] T005 [P] [OBJ-5] {TR-005} [COMPLETES TR-005] Build and verify the application in Release mode and run backend tests

## Task Details

### T001 — Create WaveformRenderer Custom Control
- **Priority**: P1
- **Status**: todo
- **Requirement**: {FR-001}
- **Description**: Create `PBStudio.UI/Controls/WaveformRenderer.cs`. Inherit from `FrameworkElement`. Declare `WaveformBars` (IEnumerable<WaveformBarModel>), `PixelsPerSecond` (double) and `FillBrush` (Brush) dependency properties. Implement a fast `StreamGeometry` drawing loop in `OnRender` that symmetric-mirrors the amplitudes around the vertical center.

### T002 — Seamless Playback Transition
- **Priority**: P1
- **Status**: todo
- **Requirement**: {FR-002}
- **Description**: Modify `TimelineView.xaml.cs`. Introduce `_wasPlayingBeforeReload` flag. In `PlaybackTimer_OnTick`, if position is near clip end, look up the next chronological entry. Set the selected entry in the ViewModel to load the next clip. Do not stop the playback timer. In `PreviewPlayer_OnMediaOpened`, if `_wasPlayingBeforeReload` is true, immediately trigger play on the MediaElement.

### T003 — UI Integration & DJ-Beatgrid
- **Priority**: P1
- **Status**: todo
- **Requirement**: {FR-003}
- **Description**: Update `TimelineView.xaml`. Replace old `ItemsControl` for `WaveformBars` with the new `<controls:WaveformRenderer>` control. Rewrite the `<DataTemplate DataType="{x:Type models:BeatMarkerViewModel}">` in A1 lane to style Downbeats with bold red vertical lines, standard beats with faint ice-blue lines, and bar number badges inside dark, rounded contrast borders for premium readability.

### T004 — Song Phrase Coloring & Watermarks
- **Priority**: P1
- **Status**: todo
- **Requirement**: {FR-004}
- **Description**: Revamp A1 lane's `SongSegments` `ItemsControl` to display refined background colors (Intro, Verse, Chorus, Outro, Break, Bridge) with low opacity (8%-12%) and semi-transparent label watermarks for perfect visual orientation.

### T005 — Build & Verification
- **Priority**: P1
- **Status**: todo
- **Requirement**: {TR-005}
- **Description**: Run `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` and make sure it builds without errors or warnings. Run backend tests using `pytest Tests/ -x -q` to make sure there are no regressions.
