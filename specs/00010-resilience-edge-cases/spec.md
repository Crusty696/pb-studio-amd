---
feature_branch: "00010-resilience-edge-cases"
created: "2026-04-25"
input: "E010 Resilience & Edge-Cases"
spec_type: "technical"
spec_maturity: "draft"
epic_id: "E010"
epic_sources: "{STATUS:Stability}"
---

# Technical Specification: Resilience & Edge-Cases

**Feature Branch**: `00010-resilience-edge-cases`  
**Created**: 2026-04-25  
**Status**: Draft  
**Spec Type**: technical  
**Spec Maturity**: draft  
**Epic ID**: E010  
**Epic Sources**: {STATUS:Stability}

## Problem Statement *(mandatory)*

Professional workstations must survive unexpected failures. Currently, if the backend restarts or a network glitch occurs, the WPF UI loses its SSE connection and stays "dead." Furthermore, while 16GB VRAM is stable, the system's behavior under extreme pressure (simulated 4GB limit) remains unverified.

## Scope *(mandatory)*

### Included

- **SSE Reconnection Logic**: Implement exponential backoff for SSE stream recovery in `SSEClient.cs`.
- **Backend Heartbeat**: A visual "Connection Lost" overlay in WPF when the backend is unreachable.
- **Low VRAM Stress Test**: A specialized test run using the Arbiter with a forced 4000MB limit.
- **Error Boundary Hardening**: Global exception handling in critical ViewModels to prevent app crashes.

### Excluded

- **Multi-GPU Support**: Only the primary detected AMD GPU is handled.
- **Cloud Failover**: Zero cloud dependencies remain a hard constraint.

## Technical Objectives *(mandatory for technical specs only)*

### OBJ1 - Self-Healing SSE (Priority: P1)

Ensure the UI automatically reconnects to `/events/progress` within 30 seconds of a backend restart.

### OBJ2 - Boundary Verification (Priority: P2)

Verify that the `VRAMArbiter` successfully rejects or evicts models when the budget is artificially capped at 4GB.

## Requirements *(mandatory)*

### Technical Requirements *(technical specs only)*

- **TR-001**: `SSEClient` MUST implement a retry loop with max 5 attempts before notifying the UI.
- **TR-002**: The `VRAMBudgetManager` MUST be testable with a mock/forced limit via environment variables or config.
- **TR-003**: UI MUST show a non-modal warning when the connection to the Python backend is interrupted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Kill backend -> Restart backend -> UI resumes progress updates without user intervention.
- **SC-002**: Stress test with 4GB limit completes with 0 OOM crashes (rejections are allowed).
