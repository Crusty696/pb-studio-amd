---
feature_branch: "00006-amd-export-pipeline"
created: "2026-04-24"
input: "E006 AMD Export Pipeline"
spec_type: "product"
spec_maturity: "draft"
epic_id: "E006"
epic_sources: "{PRD:CAP-005}"
---

# Feature Specification: AMD Export Pipeline

**Feature Branch**: `00006-amd-export-pipeline`  
**Created**: 2026-04-24  
**Status**: Draft  
**Spec Type**: product  
**Spec Maturity**: draft  
**Epic ID**: E006  
**Epic Sources**: {PRD:CAP-005}  
**Product Document**: specs/prd.md

## Problem Statement *(mandatory)*

Users need a reliable, high-performance way to export their finalized timelines into a shareable video format. The export must leverage AMD hardware acceleration (AMF) to handle long DJ mixes efficiently and must accurately reflect all manual adjustments made on the Power-Timeline.

## Scope *(mandatory)*

### Included

- **AMD AMF Hardware Encoding**: Full support for H.264 and HEVC via AMD AMF.
- **Timeline-to-Video Translation**: Accurate conversion of the `TimelineEntry` list (including manual edits) into a final FFmpeg command.
- **Robust Telemetry**: Real-time updates for FPS, ETA, and progress percentage during the entire export process.
- **Error Handling**: Graceful recovery and logging for GPU driver timeouts (TDR) or FFmpeg crashes.
- **Audio/Video Muxing**: High-quality AAC audio muxing with the generated video track.

### Excluded

- **Multi-pass Encoding**: Initial release focuses on high-quality single-pass encoding for speed.
- **Cloud Rendering**: Out of scope per "Offline First" principle.
- **VFX Overlays**: Complex watermarks or text overlays are deferred.

## User Scenarios & Testing *(mandatory for product specs only)*

### User Story 1 - High-Speed Export (Priority: P1)

As a DJ, I want to export my 2-hour mix using my AMD GPU so that I don't have to wait all night for the video to render.

**Why this priority**: Essential for the "AMD Version" value proposition.

**Acceptance Scenarios**:

1. **Given** a finalized timeline, **When** I start the export with "H.264 AMF", **Then** the GPU utilization increases and the render completes significantly faster than CPU-only encoding.

### User Story 2 - Accurate Cut Export (Priority: P1)

As a creator, I want the final exported video to exactly match the cuts and timing I set on the interactive timeline.

**Why this priority**: Correctness is the primary success metric.

**Acceptance Scenarios**:

1. **Given** a timeline with manually shifted cuts, **When** the video is exported, **Then** the visual cuts land exactly on the timestamps defined in the EDL.

## Requirements *(mandatory)*

### Functional Requirements *(product specs only)*

- **FR-001**: The system MUST detect and use AMD AMF encoders (`h264_amf`, `hevc_amf`) when available.
- **FR-002**: The system MUST generate a valid FFmpeg concat list from the current project state.
- **FR-003**: The system MUST provide live telemetry via SSE during the render.
- **FR-004**: The system MUST support cancellation of the export process at any time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Export speed on supported AMD hardware is at least 3x faster than `libx264` (CPU).
- **SC-002**: Sync drift between audio beats and video cuts in the final file is < 33ms (1 frame at 30fps).

## Compliance Check

- **AMD DirectML First**: ✅ PASS. Pipeline is built around AMF.
- **Offline First**: ✅ PASS. Zero cloud dependencies.
- **Agent Output Style**: ✅ PASS.
