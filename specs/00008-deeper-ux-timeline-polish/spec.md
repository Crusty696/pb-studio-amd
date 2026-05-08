---
feature_branch: "00008-deeper-ux-timeline-polish"
created: "2026-05-07"
input: "E008 Deeper UX & Timeline Polish"
spec_type: "product"
spec_maturity: "clarified"
epic_id: "E008"
epic_sources: "{STATUS:UX}"
---

# Product Specification: Deeper UX & Timeline Polish

**Feature Branch**: `00008-deeper-ux-timeline-polish`  
**Created**: 2026-05-07  
**Status**: Draft  
**Spec Type**: product  
**Spec Maturity**: clarified
  
**Epic ID**: E008  
**Epic Sources**: {STATUS:UX}  
**Product Context**: specs/prd.md  
**Technical Context**: specs/sad.md

## Problem Statement

While the core interactive timeline is functional, the editing experience lacks the fluidity and precision expected of a professional media workstation. Scrolling in long mixes (1h+) is not sufficiently smooth, magnetic snapping is too simplistic and provides no visual confirmation, and UI feedback for selection and hover states is basic. These friction points hinder the "AI Director" workflow by making manual adjustments feel clunky rather than intuitive.

## Scope

### Included

- **Fluid Timeline Scrolling**: Implement pixel-based scrolling with UI virtualization and recycling for the main timeline area.
- **Enhanced Magnetic Snapping**: Upgrade the snapping engine to handle Playhead, Clip Edges, and Onset Markers with configurable thresholds (default 8px).
- **Visual Snap Feedback**: Implement vertical "Snap Lines" that appear when an element docks to a target.
- **Refined Interaction States**: Implement consistent Hover, Selection, and Dragging states using WPF `VisualStateManager` with subtle animations (glow, scaling).
- **Ruler Optimization**: Refactor the timeline ruler to minimize redraw overhead during zoom and scroll operations.

### Excluded

- **Multi-Track Editing**: This epic focuses on the primary interactive track, not adding additional layers.
- **Waveform Generation**: Improvements to the waveform generation itself are out of scope (handled by E002/E003).

### Edge Cases & Boundaries

- **Extreme Zoom Levels**: Maintaining performance when zoomed in to 1ms or out to 4 hours.
- **Overlapping Markers**: Handling situations where multiple snap points (e.g., beat + onset) are within the same pixel radius.
- **Keyboard Overrides**: Temporary disabling of snapping via modifier keys.

## User Scenarios & Testing

### US1 - Fluid Navigation in Long Mixes (Priority: P1)
As a creator working on a 2-hour mix, I want the timeline to scroll smoothly without "jumping" between clips, so that I can maintain my visual orientation during editing.

**Why this priority**: Core UX requirement for long-form content.

**Independent Test**: Scroll horizontally through a 2-hour project; verify scrolling is pixel-precise and maintains 60fps.

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Smooth Scroll | A project with >500 clips | I use the horizontal scrollbar | The timeline moves smoothly with no frame drops and no jumping between elements |

### US2 - Precision Snapping with Visual Feedback (Priority: P1)
As an editor, I want my clips to "snap" to onsets and beats with a clear visual line, so that I can be confident my cuts are perfectly synced to the music.

**Why this priority**: Fulfills the "Rhythmic Perfection" product principle.

**Independent Test**: Drag a clip edge near an onset marker; verify it snaps and a vertical line appears.

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Clip Snapping | A clip is being dragged | It comes within 8 pixels of an onset | The clip start/end jumps to the onset and a vertical cyan line appears |

### US3 - High-Fidelity Interaction States (Priority: P2)
As a user, I want clips to react subtley when I hover over them or select them, so that I have immediate confirmation of my interaction target.

**Why this priority**: Enhances professional feel and reduces cognitive load.

**Independent Test**: Hover over multiple clips rapidly; verify glow effect follows smoothly.

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Selection Feedback | A clip is clicked | Selection occurs | The clip border glows and its Z-index increases above surrounding clips |

## Requirements

### Functional Requirements

- **FR-001**: The `TimelineView` MUST use `VirtualizingPanel.ScrollUnit="Pixel"` for all horizontal scrolling.
- **FR-002**: UI container recycling MUST be enabled for all `ItemsControl` elements in the timeline to maintain performance with >1000 items.
- **FR-003**: The snapping engine MUST support a configurable threshold (default 8px) for Playhead, Clip Edges, and Onset Markers.
- **FR-004**: A vertical "Snap Line" MUST be rendered dynamically when a snap occurs.
- **FR-005**: Holding the `SHIFT` key MUST temporarily disable all magnetic snapping.
- **FR-006**: The `TimelineRuler` MUST use a cached drawing strategy to prevent UI freezes during high-frequency zoom operations.
- FR-007: Every clip MUST implement `VisualStateManager` states for `Normal`, `MouseOver`, and `Selected`.
- FR-008: The `TimelineView` MUST provide high-contrast visual indicators for selection and snapping to support accessibility.


## Key Entities

- **SnapPoint**: A time-based coordinate (Seconds) with a type (Beat, Onset, Playhead, Edge).
- **TimelineState**: Shared state managing Zoom (PPS), ScrollOffset, and SnapSettings.

## Assumptions & Risks

### Assumptions

- The hardware (AMD GPU) handles basic WPF rendering without issues.
- .NET 9 features like `ScrollUnit="Pixel"` are available.

### Risks

- **Virtualization Complexity**: Custom `VirtualizingCanvas` may be needed if standard panels cannot handle absolute positioning with recycling.
- **Binding Overhead**: High-frequency MultiBindings for time-to-pixel conversion may impact FPS during fast scrolling.

## Implementation Signals

- `NEW-UI` — Snap Line overlay and VSM-driven clip styles.
- `NEW-ENTITY` — Client-side `SnapEngine` logic.
- `MIGRATION` — Refactor `TimelineView` to advanced virtualization patterns.

## Success Criteria

- **SC-001** [US1]: Timeline scrolling maintains 60fps during a 2-hour project scroll.
- **SC-002** [US2]: Users can reliably snap clips to onset markers within a 10ms precision window.
- **SC-003** [US3]: UI feedback (hover/select) is delivered within 100ms of the user action.

## Clarifications

### Session 2026-05-07
- Q: What happens if multiple snap points are within the threshold? -> A: The system will snap to the closest point. If equidistant, priority is Playhead > Beat > Onset > Clip Edge.

## Stress-Test Findings

### Session 2026-05-07
- STF-001: Ambiguity in snap priority for overlapping markers. Resolved by defining explicit priority order.
- STF-002: Potential performance hit from MultiBindings in high-density timelines. Resolved by prioritizing UI virtualization and cached drawing.
