# OBJ-75 Round 2 Audit Evidence

## Method

- Independent read-only re-audit by Brain/Data, Chat/Project, and
  Terminal/Config/Timeline specialists.
- Parent re-audit of Audio, Video, Pacing, Render, Core/GPU, SDD and WPF.
- All round-1 fixes were evaluated against the current post-fix worktree.

## Resolved and reverified

- Audio full-duration key evidence and model-bound stem cache contract.
- Video duration bounds, forced recomputation, weighted colors and cold-start paths.
- Pacing gates, semantic ranking, snapping and independent degradation fallback.
- Render cancellation, video-only export and temporary-file cleanup.
- GPU cleanup endpoint and wrapper-owned ORT-session eviction.
- Project close/anchor epoch, Chat history/provider/error truth, Terminal bounds,
  Config precedence, Timeline autosave/selection/viewport behavior.
- Brain legacy axis-status compatibility while strict versioned metadata continues
  to exclude unavailable synthetic evidence.
- Filter-aware SSE replay gaps, project-info atomic snapshots and backup retention.

## Round-2 findings fixed during convergence

- Legacy Brain cuts with semantic-only axis status produced empty credit and HTTP 409.
- Long-mix key detection regressed from full-duration chroma to a short load window.
- SSE log reconnect warned about gaps caused only by evicted progress events.
- Timeline viewport capped visible clips at 512 and scanned all entries per scroll.
- `/project/info` could combine project metadata and counts from different epochs.
- Automatic Brain backups did not invoke their existing retention policy.
- The SDD validator spawned hundreds of duplicate Git subprocesses and could exceed
  per-test timeouts; immutable lookups are now cached and bounded.

## Post-audit closure of the three High risks

1. **Chat:** a server-verifiable project capability now covers the full streamed
   turn, confirmation wait, loopback tool dispatch and final commit.
2. **Projector:** stable project/event UUIDs, pending events, durable checkpoints,
   copy-on-write publish and V1 rebuild/rollback provide exactly-once behavior.
3. **Recovery:** immutable generations now couple DB, embeddings, FAISS and the
   registered Config/Project/Chat/Brain/Stem/Render owners behind a startup gate.

These remediations happened after the read-only Round-2 snapshot and are covered
by the dedicated Chat, Projector and Recovery evidence files. Render retention,
Chat token deltas and external Config hot reload remain accepted post-OBJ-75
scope items, not release blockers.

## Verification

- Audio: 44/44 passed.
- Video: 60/60 passed.
- Pacing: 63/63 passed.
- Render/Core/GPU: 68/68 passed.
- WPF timeline/terminal/replay contracts: 17/17 passed.
- Native WPF tests: 54/54 passed.
- WPF Release build: 0 warnings, 0 errors.
- Python compileall: passed.
- OBJ-75 SDD open gate: valid, zero findings.
- A later broad Python run collected the current suite and produced 1450 passed,
  13 skipped and one T412 harness timeout. After root-cause correction the full
  T412 contract passed 3/3 and ten stress repetitions passed 10/10; see
  `final-qc.md`. The long suite was not repeated.
