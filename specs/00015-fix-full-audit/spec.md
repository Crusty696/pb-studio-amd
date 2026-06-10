---
feature_branch: "00013-system-wide-bug-hunting-audit"
created: "2026-06-10"
input: "Full-Stack Audit Phase 2 (High, Medium, Low findings) 2026-06-10"
spec_type: "technical"
spec_maturity: "draft"
epic_id: "E015"
epic_sources: "{STATUS:AuditFixes}"
---

# Technical Specification: Full-Stack Audit Fixes Phase 2 (2026-06-10)

**Feature Branch**: `00013-system-wide-bug-hunting-audit`  
**Created**: 2026-06-10  
**Status**: Draft  
**Spec Type**: technical  
**Spec Maturity**: draft  
**Epic ID**: E015  
**Epic Sources**: {STATUS:AuditFixes}

## Problem Statement

Following the completion of the critical findings (K1-K11), PB Studio must address the remaining high, medium, and low findings from the `FULL_AUDIT_2026-06-10.md` report. These issues span multiple layers and prevent reliable long-running performance, data persistence integrity, accurate feature engineering, and robust WPF UI interaction.

## Scope

### Included
- **Z-CORE & Z-DATA**:
  - `with_gpu_task` VRAM leak on cancel/timeout and Zombie GPU thread preventions.
  - Eviction accounting rollback upon unload callback failures.
  - SQLite transaction atomicity: Rewrite migration runner to split SQL and run statements individually instead of `executescript()`.
  - LibreHardwareMonitor `Hardware.Update()` thread-safety lock.
- **Z-AUDIO**:
  - Handle corrupt/0-byte drum stem gracefully with mix-fallback.
  - Correct `/audio/analyze` endpoint accepting JSON string for `stems_paths`.
  - Resolve htdemucs CPU EP fallback and structural gaps.
- **Z-VIDEO & Z-RENDER**:
  - Fix double-quote output in FFmpeg concat generator (`export_for_ffmpeg`).
  - Resolve bare `"ffmpeg"` calls to absolute paths.
  - Stop storyboard hardcoded path fallback.
  - Concat select with `concatdec_select` to avoid GOP misalignment.
- **Z-UI & SSE**:
  - Chat history: Correct `.Take(40)` to send the *latest* 40 messages chronologically.
  - WPF re-entry gates for analysis tasks.
  - SSE progress piping: ensure client views update on progress.
- **Scripts**:
  - Fix PS error masks, elevation parameter leaks, and wrong doc folders.

## Technical Objectives

### OBJ4 - Core Execution Safety (Priority: P1)
Prevent VRAM overcommits, race conditions during hardware queries, and database corruption during migrations.

### OBJ5 - Hardened Audio Pipelines (Priority: P1)
Deliver fail-safe stem extraction, drum-beat analysis, and schema consistency.

### OBJ6 - Robust Timeline Compositing (Priority: P1)
Produce GOP-aligned, AMF-accelerated, error-free videos.

### OBJ7 - Correct User Interface Lifecycle (Priority: P1)
Deliver responsive UI states, thread-safe updates, and accurate chat histories.

## Success Criteria

- **SC-004**: Pytest backend suite completes with 100% green.
- **SC-005**: WPF UI builds successfully in Release.
- **SC-006**: Multiple migration failures do not leave database in corrupted partial states.
