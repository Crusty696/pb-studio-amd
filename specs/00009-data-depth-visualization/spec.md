---
feature_branch: "00009-data-depth-visualization"
created: "2026-05-07"
input: "E009 Audio/Video Data Depth"
spec_type: "technical"
spec_maturity: "clarified"
epic_id: "E009"
epic_sources: "{STATUS:Refinement}"
---

# Technical Specification: Audio/Video Data Depth

**Feature Branch**: `00009-data-depth-visualization`  
**Created**: 2026-05-07  
**Status**: Draft  
**Spec Type**: technical  
**Spec Maturity**: clarified
  
**Epic ID**: E009  
**Epic Sources**: {STATUS:Refinement}  
**Product Context**: specs/prd.md  
**Technical Context**: specs/sad.md

## Problem Statement

The current "AI Director" loop provides basic beat and content tagging, but lacks "depth" in its understanding of media. The system cannot distinguish between a high-energy chorus and a quiet verse, nor can it visualize the spectral character of audio or subtle motion patterns in video. This limits the creative variety of automated cuts and prevents professional users from making informed manual adjustments based on visual data overlays.

## Scope

### Included

- **Song Section Detection**: Implement backend logic to detect song sections (Intro, Verse, Chorus, Outro, Drop) based on self-similarity and energy patterns.
- **Spectral Data Extraction**: Extract Spectral Centroid and RMS Energy curves from audio files for high-resolution visualization.
- **Refined Scene Detection**: Upgrade video analysis to use adaptive content detection to minimize false positives in high-motion clips.
- **Data-Depth Overlays**: Implement WPF timeline overlays for song sections (colored regions) and spectral curves (synchronized with waveform).
- **Metadata Persistence**: Extend the `project.json` and FAISS metadata to store and retrieve these deep data attributes.

### Excluded

- **Real-time Spectral Visualization**: Visualization is performed post-analysis, not during live playback (deferred).
- **Vocal/Instrumental Separation**: Handled by separate stems (E002), not part of this depth visualization.

### Edge Cases & Boundaries

- **Non-Standard Song Structures**: Handling ambient or avant-garde tracks with no clear verse/chorus.
- **Extremely Short/Long Clips**: Maintaining detection accuracy for <1s or >1h media files.
- **VRAM Constraints**: Ensuring deep analysis models fit within the DirectML budget alongside existing models.

## User Scenarios & Testing

### US1 - Visualizing Song Structure (Priority: P1)
As an editor, I want to see colored regions on the timeline for Intro, Chorus, and Verse, so that I can quickly navigate to the most energetic parts of the track.

**Why this priority**: Essential for rapid navigation in long mixes.

**Independent Test**: Analyze a 3-minute pop track; verify that at least 3 distinct sections are labeled and visualized on the timeline.

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Section Detection | A project with a standard pop song | I run "Deep Analysis" | The timeline shows labeled colored blocks for Intro, Verse, and Chorus |

### US2 - Spectral Insight for Cuts (Priority: P2)
As a creator, I want to see a spectral energy curve overlaid on the waveform, so that I can align my video cuts precisely with the most impactful frequency changes.

**Why this priority**: Enhances the "Rhythmic Perfection" principle.

**Independent Test**: Zoom into a transition; verify the energy curve peaks align with the perceived audio impact.

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Spectral Overlay | A waveform is rendered | I toggle "Spectral Depth" | A high-resolution energy curve is rendered on top of the waveform |

## Requirements

### Functional Requirements

- **FR-001**: The backend MUST extract Mel-spectrogram data and Spectral Centroids for every audio file during analysis.
- **FR-002**: The system MUST detect at least 3 functional song sections (e.g., Intro, Body, Outro) using Librosa-based SSM or energy clustering.
- **FR-003**: The `TimelineView` MUST support rendering colored background regions for song sections.
- **FR-004**: The `VideoLibrary` MUST use an adaptive threshold for scene detection to account for camera movement.
- **FR-005**: All "Depth" metadata MUST be saved in the `media_cache` and accessible via the `REST API`.

### Technical Requirements

- **TR-001**: Spectral visualization in WPF MUST use `DrawingVisual` or `WriteableBitmap` to maintain >30fps during scrolling.
- **TR-002**: Backend analysis MUST be performed in chunks to avoid OOM on large audio files.
- **TR-003**: Scene detection MUST utilize DirectML-accelerated frame comparison if available.

## Key Entities

- **SongSegment**: { StartTime, EndTime, Label, EnergyScore }
- **SpectralCurve**: { Timestamps[], CentroidValues[], EnergyValues[] }
- **VideoSceneRefined**: { StartFrame, EndTime, MotionIntensity, ContentChangeScore }

## Assumptions & Risks

### Assumptions

- `Librosa` and `NumPy` are available in the Python environment.
- The UI can handle additional canvas layers without significant performance degradation.

### Risks

- **Analysis Latency**: Deep data extraction increases the total analysis time per project.
- **Label Inaccuracy**: Automated labeling of song sections is non-deterministic and may require user overrides.

## Implementation Signals

- `NEW-ENTITY` — `SongSegment` and `SpectralData` schemas.
- `NEW-UI` — Timeline overlays for segments and energy curves.
- `BACKEND-REFactor` — Enhancing the analysis worker loop.

## Success Criteria

- **SC-001** [US1]: Song section detection achieves >80% alignment with manual ground-truth labels for pop/EDM tracks.
- **SC-002** [US2]: Timeline scrolling remains fluid (<50ms frame time) with all depth overlays active.
- **SC-003**: All depth metadata is persistent across application restarts.

## Clarifications

### Session 2026-05-07
- Q: Which song sections are supported? -> A: Default set: `Intro`, `Verse`, `Chorus`, `Bridge`, `Outro`, `Drop`. If detection is uncertain, generic `Section A`, `Section B` etc. will be used.
- Q: How is spectral data handled for 2h+ tracks? -> A: The UI will perform dynamic downsampling based on the current zoom level to ensure rendering efficiency.
- Q: What is the fallback for failed analysis? -> A: The UI will display a placeholder "No Depth Data" and allow the user to trigger a re-analysis.

## Stress-Test Findings

### Session 2026-05-07
- STF-001: Potential UI lag when rendering thousands of spectral points. Resolved by TR-001 (DrawingVisual) and dynamic downsampling.
- STF-002: Metadata bloat in `project.json`. Resolved by storing spectral data in binary sidecar files or compressed JSON arrays in `media_cache`.
- STF-003: Over-segmentation in ambient music. Resolved by merging segments shorter than 8 bars or 15 seconds.
