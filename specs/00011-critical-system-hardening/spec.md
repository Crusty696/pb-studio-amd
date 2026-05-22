---
feature_branch: "00011-critical-system-hardening"
created: "2026-05-22"
input: "Four Major System Hardening Fixes"
spec_type: "technical"
spec_maturity: "draft"
epic_id: "E011"
epic_sources: "{STATUS:Hardening}"
---

# Technical Specification: Critical System Hardening (Four Major Fixes)

**Feature Branch**: `00011-critical-system-hardening`  
**Created**: 2026-05-22  
**Status**: Draft  
**Spec Type**: technical  
**Spec Maturity**: draft  
**Epic ID**: E011  
**Epic Sources**: {STATUS:Hardening}

## Problem Statement *(mandatory)*

The PB Studio AMD workstation suffers from four critical stability and performance issues:
1. **Circular Deadlock in VRAM Manager / Model Loader**: Circular lock acquisition between `VRAMBudgetManager._registry_lock` and `ModelLoader._session_lock` causing complete UI/Backend freeze during model allocation.
2. **SQLite Thread Contention & FAISS Lock Blocks**: Thread crashes under concurrent read/write due to shared connections in the embedding repository, `SQLITE_BUSY` errors due to standard transaction upgrades, and FAISS index disk writes blocking search operations.
3. **WPF Memory & Event Leaks**: Memory leaks in WPF due to transient ViewModels being tracked indefinitely by the MS Dependency Injection container (due to `IDisposable` implementation) and active subscriptions to singletons (SSEClient) not being unregistered on view unload.
4. **Hanging Subprocesses & OpenCV GOP Seeks**: FFmpeg processes leaking as zombies during transcode exception paths, OpenCV VideoCapture handles leaked in fallback paths, and extremely slow random frame seeking `cap.set(cv2.CAP_PROP_POS_FRAMES)` in video loops.

## Scope *(mandatory)*

### Included

- **VRAM Deadlock & OOM Fix**: Decouple `vram_budget_manager.py` eviction callbacks from `_registry_lock` and make arbiter allocation atomic.
- **SQLite & FAISS Hardening**: Implement thread-local database connections in `embedding_repository.py`, enforce `BEGIN IMMEDIATE` for SQLite write operations in `media_repository.py`, and separate FAISS disk I/O writes from main search-lock.
- **WPF VM Scope & Lifecycle Cleanup**: Update WPF View Code-behinds to utilize `IServiceScope` for ViewModel resolution to allow cleanup, implement clean `Dispose` and `Unloaded` cleanup (de-register SSE events and timers), and restore timeline playhead auto-scroll/composition loops.
- **FFmpeg & OpenCV Process Safe-Guards & Fast Seeks**: Implement robust `try...finally` blocks for FFmpeg subprocess cleanup and OpenCV video capture release, and convert H.264 frame seeking from $O(N)$ random seeking (`cap.set`) to sequential `cap.grab()` / `cap.read()`.

### Excluded

- **Framework migration**: The project remains on Python 3.11.x, WPF, DirectML, and SQLite-vec/FAISS.
- **New Features**: No new functional elements are added. This is strictly system hardening.

## Technical Objectives *(mandatory for technical specs only)*

### OBJ1 - Deadlock-Free VRAM Allocation (Priority: P1)

Ensure model loads and evictions can run concurrently across threads without circular wait conditions.

### OBJ2 - Concurrent Database & Thread-Local Stability (Priority: P1)

Achieve 100% crash-free concurrent DB transactions and ensure FAISS search operations are never blocked by index disk writes.

### OBJ3 - Zero-Leak WPF UI (Priority: P2)

Prevent transient ViewModels from remaining in memory after the associated View is unloaded, and resolve event-handler memory retention.

### OBJ4 - Reliable Subprocesses & Rapid Video Frame Retrieval (Priority: P1)

Ensure 0 zombie FFmpeg processes are left behind on crash/cancellation, and speed up frame retrieval loops by utilizing sequential grabs.

## Requirements *(mandatory)*

### Technical Requirements *(technical specs only)*

- **TR-001**: `vram_budget_manager.py` MUST NOT execute callbacks (such as unloading) while holding `_registry_lock`.
- **TR-002**: `embedding_repository.py` MUST use thread-local database connections to avoid `sqlite3.ProgrammingError`.
- **TR-003**: `media_repository.py` MUST use `BEGIN IMMEDIATE` transactions for all operations that perform database writes.
- **TR-004**: `vector_store.py` MUST clone FAISS indices for disk writes to prevent write I/O from locking concurrent searches.
- **TR-005**: WPF View-behinds MUST resolve ViewModels inside a localized DI Scope that is disposed on View `Unloaded`.
- **TR-006**: Video extraction loops MUST NOT use `cap.set(cv2.CAP_PROP_POS_FRAMES)` inside loops when sequential iteration is possible.
- **TR-007**: Every FFmpeg `subprocess.Popen` call MUST be guarded with `try...finally` to ensure the process is terminated/killed on failure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Stress testing with VRAM evictions completes without deadlock freezes.
- **SC-002**: Bulk imports of 400+ clips run without SQLite transaction crashes or search blockages.
- **SC-003**: Tab switching in WPF does not leak ViewModel instances or active timers, and timeline playback remains smooth after switching.
- **SC-004**: FFmpeg subprocesses terminate immediately if transcoding is cancelled.
