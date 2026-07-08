# Fix Remaining Audit Risks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve critical remaining stability issues from Block B and C of the Full-Stack Audit (unsafe taskkills, unapplied locks, and undocumented CPU fallbacks).

**Architecture:** Switch process termination in verify scripts from global image name matching to specific PID termination. Apply the defined `_patterns_lock` to SQLite connections in `brain_store.py` and document the PyTorch/CPU reality of the Demucs model to avoid DirectML expectations.

**Tech Stack:** PowerShell 5.1, Python 3.11, SQLite3, PyTorch

---

### Task 1: PID-Based Process Termination in verify_release_smoke.ps1

**Files:**
- Modify: `verify_release_smoke.ps1:420-435`
- Test: `verify_release_smoke.ps1`

- [X] **Step 1: Write a failing integration test scenario**
  Since this is a PowerShell script, create a test step in `verify_release_smoke.ps1` that starts a dummy background Python process, verifies its PID is distinct from the backend, runs the script, and asserts the dummy process is still alive.

- [X] **Step 2: Run test to verify it fails**
  Run: `powershell -File verify_release_smoke.ps1`
  Expected: The dummy Python process is terminated because `taskkill /F /IM python.exe` kills all Python instances.

- [X] **Step 3: Modify verify_release_smoke.ps1 to use targeted PID termination**
  Replace the global `taskkill` calls with PowerShell's native process tracking.
  ```powershell
  finally {
      if ($script:StartedBackend -and $script:BackendProcess) {
          Write-Host "[SMOKE] Terminating backend process PID $PId..."
          try {
              Stop-Process -Id $script:BackendProcess.Id -Force -ErrorAction SilentlyContinue
          } catch {
              # Fallback if Stop-Process fails
              taskkill /F /PID $script:BackendProcess.Id /T
          }
      }
      exit $script:SmokeExitCode
  }
  ```

- [X] **Step 4: Run test to verify it passes**
  Run: `powershell -File verify_release_smoke.ps1`
  Expected: The backend process terminates, but the dummy Python process remains running.

- [X] **Step 5: Commit**
  ```bash
  git add verify_release_smoke.ps1
  git commit -m "fix(infra): use targeted PID-based termination instead of global taskkill"
  ```

---

### Task 2: Apply SQLite Connection Lock in BrainStore

**Files:**
- Modify: `src/pb_studio/storage/brain_store.py`
- Test: `Tests/test_brain_recovery.py`

- [ ] **Step 1: Write a test asserting concurrent access safety**
  Create a test in `Tests/test_brain_recovery.py` that concurrently reads/writes to `patterns_conn` using threads, demonstrating a lock-less write collision.

- [ ] **Step 2: Run test to verify it fails**
  Run: `pytest Tests/test_brain_recovery.py -k test_concurrent_patterns`
  Expected: Fail with database-lock/thread-safety exception.

- [ ] **Step 3: Implement locking for patterns_conn**
  Modify database operations or connection access in `brain_store.py` to serialize operations using `self._patterns_lock`.
  ```python
  # Apply patterns lock around close
  def close(self) -> None:
      with self._patterns_lock:
          if self.patterns_conn is not None:
              try:
                  self.patterns_conn.close()
              except Exception:
                  pass
              self.patterns_conn = None
      # weights_conn close...
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest Tests/test_brain_recovery.py -k test_concurrent_patterns`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add src/pb_studio/storage/brain_store.py
  git commit -m "fix(data): serialize patterns_conn close using patterns lock"
  ```

---

### Task 3: Document PyTorch/CPU Reality for htdemucs

**Files:**
- Modify: `CLAUDE.md:80-95`
- Test: None (Documentation task)

- [X] **Step 1: Update CLAUDE.md to clarify model hardware support**
  Specify in `CLAUDE.md` that while ONNX models (MDX-NET) run accelerated on AMD via DirectML, PyTorch models (Demucs) run on CPU because the pinned environment uses PyTorch CPU.

- [X] **Step 2: Commit**
  ```bash
  git add CLAUDE.md
  git commit -m "docs: document CPU inference reality for htdemucs"
  ```
