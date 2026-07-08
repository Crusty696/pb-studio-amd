# Implementation Plan - Block C (AP6) Production Hardening

This plan resolves the remaining 12 stability, concurrency, and security issues from Block C (AP6) of the Full-Stack Audit.

## Proposed Changes

### 1. Reset Token TTL (AP6.1)
- **Files:** [brain_router.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/routers/brain_router.py)
- **Change:** Store confirmation tokens in a dictionary mapping token to expiry timestamp (5-minute TTL). Clean expired tokens on check.

### 2. Remove Dead tiktoken Logic (AP6.2)
- **Files:** [chat_router.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/routers/chat_router.py), [requirements.txt](file:///C:/Users/david/Documents/Pb_studio_AMD_version/requirements.txt)
- **Change:** Remove the unused `tiktoken` dependency (which fails download in offline environments) and establish the robust character-length heuristic tokenizer as the primary implementation.

### 3. Persist Stems Path on Re-Import (AP6.3)
- **Files:** [app_state.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/app_state.py)
- **Change:** Include `stems_paths` when reusing an existing database audio clip to avoid redundant stem separation runs.

### 4. CORS security Hardening (AP6.4)
- **Files:** [main.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/main.py)
- **Change:** Remove the insecure `"null"` origin from CORS middleware and add missing HTTP methods (`DELETE`, `PUT`) to `allow_methods`.

### 5. Render Completion Race Condition (AP6.5)
- **Files:** [render_router.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/routers/render_router.py)
- **Change:** Remove the final cancel-flag check after `_execute_render` successfully runs to prevent deleting completed output videos.

### 6. VRAMBudgetManager Init Race (AP6.6)
- **Files:** [vram_budget_manager.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/core/vram_budget_manager.py)
- **Change:** Protect instance initialization blocks in `__init__` using an initialization lock to secure multithreaded Singleton accesses.

### 7. SQLite Connection Leaks in Dead Threads (AP6.7)
- **Files:** [embedding_repository.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/embedding_repository.py)
- **Change:** Re-initialize the `self._local` thread-local connection cache when `close()` is called to prevent subsequent accesses from using closed connections.

### 8. Robust File-based SQL Migrations (AP6.8)
- **Files:** [migration_runner.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/migration_runner.py), [embedding_repository.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/embedding_repository.py)
- **Change:** Parse versions from script file prefixes (e.g. `001_initial.sql` -> `1`) instead of utilizing unsafe glob order list-indexes.

### 9. SQL Syntax Errors on Empty Bulk Updates (AP6.9)
- **Files:** [media_repository.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/data/repositories/media_repository.py)
- **Change:** Add an early exit check inside `bulk_update_status()` if the `media_ids` list is empty, preventing SQLite syntax errors inside the `IN ()` clause.

### 10. Beat Detection Dedup & Jitter Mitigation (AP6.11)
- **Files:** [streaming_analyzer.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/audio/streaming_analyzer.py)
- **Change:** Increase the chunk boundary beat dedup threshold to 150ms and merge close boundaries with timestamp averaging.

### 11. Video Analysis Timeout Positional Bug (AP6.13)
- **Files:** [video_router.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/routers/video_router.py)
- **Change:** Pass the mode argument to `extract_tags_and_model_via_lmstudio` using keyword arguments (`mode=current_mode`) to prevent positional argument TypeErrors.

### 12. Atomic File Writes in AnchorManager (AP6.14)
- **Files:** [anchor_manager.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/pacing/anchor_manager.py)
- **Change:** Use a temporary file write followed by `replace()` to ensure atomic JSON writes, preventing file corruption on process crash.

---

## Verification Plan

### Automated Tests
- Run `AUDIT_FIX_VERIFY.bat` to assert correct compilation, release builds, and run all 733 tests.
