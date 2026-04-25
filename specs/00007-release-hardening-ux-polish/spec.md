---
feature_branch: "00007-release-hardening-ux-polish"
created: "2026-04-25"
input: "E007 Release Hardening & UX Polish"
spec_type: "technical"
spec_maturity: "draft"
epic_id: "E007"
epic_sources: "{STATUS:ReleaseReadiness}"
---

# Technical Specification: Release Hardening & UX Polish

**Feature Branch**: `00007-release-hardening-ux-polish`  
**Created**: 2026-04-25  
**Status**: Draft  
**Spec Type**: technical  
**Spec Maturity**: draft  
**Epic ID**: E007  
**Epic Sources**: {STATUS:ReleaseReadiness}  
**Technical Context**: specs/sad.md

## Problem Statement *(mandatory)*

As PB Studio approaches its MVP release, several technical gaps remain that impact professional usability and stability. Legacy WinForms dialogs cause app bloat and inconsistent UX, while VRAM management hasn't been stress-tested under extreme long-mix conditions. Addressing these "last-mile" issues is critical to fulfill the "AMD Premium Edition" promise and ensure a crash-free experience for creators.

## Scope *(mandatory)*

### Included

- **Native Dialog Service**: Implement a modern WPF-native folder and file picker using `Microsoft.Win32.OpenFolderDialog` (.NET 9).
- **VRAM Stress Test Suite**: Create an automated Python utility to simulate 4-hour processing loads and verify the `VRAMArbiter`'s eviction logic.
- **UI Transition Polish**: Implement GPU-accelerated `RenderTransform` animations for tab switching and clip selection.
- **DirectML Performance Tuning**: Global audit of ONNX SessionOptions to ensure `enable_mem_pattern` is disabled for all DML sessions.
- **Consistency Audit**: Standardize status reporting and error message formatting across all ViewModels.

### Excluded

- **New AI Models**: This epic focuses on hardening existing models (SigLIP, RAFT, BeatNet), not adding new ones.
- **Linux Support**: Deployment remains strictly Windows 10/11 for the MVP.

### Edge Cases & Boundaries

- **Low VRAM Hardware**: Handling 4GB VRAM cards during a 4-hour render.
- **Path Characters**: Ensuring native dialogs correctly handle non-ASCII characters in folder paths (Umlaute, etc.).

## Technical Objectives *(mandatory for technical specs only)*

### OBJ1 - Native Dialog Abstraction (Priority: P1)

Replace all instances of manual dialog instantiation with a centralized `IDialogService`.

**Why this priority**: Required for clean MVVM and consistent native look-and-feel.

**Validation**: Verify that clicking "Import" opens the modern Windows 11 style folder picker.

### OBJ2 - 4H Stability Verification (Priority: P1)

Execute a simulated 4-hour analysis/render loop without reaching OOM or driver reset.

**Why this priority**: Proves the "Workstation" reliability for professional use.

**Validation**: `execute_stress_test.py` completes with 100% success and stable VRAM baseline.

## Requirements *(mandatory)*

### Technical Requirements *(technical specs only)*

- **TR-001**: The system MUST use `Microsoft.Win32.OpenFolderDialog` for all folder selection tasks.
- **TR-002**: The `VRAMArbiter` MUST be verified to trigger model eviction when free VRAM drops below 500MB.
- **TR-003**: All WPF ViewModels MUST inherit from `ObservableObject` and use `[ObservableProperty]` for consistent data binding.
- **TR-004**: ONNX sessions MUST have `enable_mem_pattern = False` when using `DmlExecutionProvider`.
- **TR-005**: All UI transitions MUST use `RenderTransform` instead of layout property animations.
- **TR-006**: Long media lists MUST use recycled `VirtualizingStackPanel` for performance.

## Assumptions & Risks *(mandatory)*

### Assumptions

- The environment continues to use .NET 9 and Python 3.11 as restored on 2026-04-24.
- Hardware testing is performed on the user's AMD Radeon RX 7800 XT.

### Risks

- **Driver Resets** *(likelihood: low, impact: high)*: DirectML may still trigger a TDR (Timeout Detection and Recovery) under extreme sustained load. Mitigation: Incremental batch sizing.

## Implementation Signals *(mandatory)*

- `NEW-UI` — Modern native dialog service.
- `MIGRATION` — Transition from legacy dialog patterns to centralized service.
- `NEW-WORKER` — Automated stability testing utility.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** [OBJ1]: 100% of import paths use the modern native Windows 11 dialog style.
- **SC-002** [OBJ2]: Zero unhandled exceptions or memory leaks during a sustained 2-hour stress test.

## Compliance Check

- **AMD DirectML First**: ✅ PASS. Focuses on DML-specific stability and performance tuning.
- **Offline First**: ✅ PASS. No cloud components introduced.
- **Agent Output Style**: ✅ PASS.
