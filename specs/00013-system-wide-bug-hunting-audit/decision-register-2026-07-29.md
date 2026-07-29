# Decision Register — Release-Video Repair

Date: 2026-07-29
Status vocabulary: CONFIRMED, OPEN, DECIDED, BLOCKED

## Architecture and security context

Protected assets:

- Existing successful render targets and the 6,335.027-s reference media.
- Project SQLite, timeline, FAISS mappings, Brain weights, and event history.
- Release evidence, SDD markers, PB Studio Git history, and PB-Studio-scoped Brain history.

Trust boundaries:

- WPF/user input → localhost FastAPI → project/data/render services.
- Chat-model output → server-enforced tool dispatcher → mutating operations.
- Python render service → FFmpeg child process → temporary and final artifacts.
- Project repository → Git origin; Brain vault → separate Git origin.

Security invariants:

- Untrusted paths or model arguments never select arbitrary overwrite targets or shell syntax.
- Existing successful artifacts survive failed, cancelled, or resumed jobs.
- Production data changes require a verified backup and restore path.
- Release markers and PASS statements require stored evidence.
- No secret, unrelated Brain path, forced update, or unreviewed remote divergence is published.

## D01 — Diagnose before implementation

- Status: DECIDED
- Decision: T308–T310 are a mandatory gate. No render fix is permitted before production-identical reproduction, stage isolation, and independent falsification.
- Impact: Prevents symptom patches and preserves one causal baseline.
- Reversibility: Two-way door; diagnostic artifacts are additive.
- Abort/reopen criterion: BLOCKED if the concrete failure cannot be reproduced, stage signatures diverge, or two attempts provide no new evidence under the anti-loop rules.

## D02 — Preserve 58.2-second source end silence

- Status: DECIDED
- Decision: Source end silence remains part of the export.
- Impact: Timeline and audio validators must distinguish intended silence from missing media.
- Reversibility: Two-way door before release; changing it would alter creative output.
- Abort/reopen criterion: Reopen only with source evidence that the 58.2 seconds are not part of the intended asset.

## D03 — Audio target

- Status: DECIDED
- Decision: AAC export must measure `≤ -1.0 dBTP` and zero overs. Filter design follows measurement evidence.
- Impact: Audio filter selection cannot be hardcoded before measured encode behavior is known.
- Reversibility: Two-way door; filter parameters can be replaced and revalidated.
- Abort/reopen criterion: BLOCKED if the target cannot be achieved without changing source duration/silence or introducing audible damage; save measurement artifacts first.

## D04 — Existing Brain weights

- Status: DECIDED
- Decision: No blanket reset. Replay requires a complete event log; otherwise archive the old version and start the new schema neutrally.
- Impact: T324 is a production-data gate with backup, hash, copy rehearsal, replay check, and restore probe.
- Reversibility: One-way door after live migration; backup and versioned archive make rollback possible.
- Abort/reopen criterion: BLOCKED before live mutation if backup hash, copy rehearsal, event completeness, or restore probe fails.

## D05 — FFmpeg 8.0.1 versus 6.x

- Status: DECIDED
- Decision: Switch to 6.x only after source verification, hash, AMF function proof, compatibility comparison, and rollback package.
- Impact: T325 decides runtime; T326 synchronizes every wrapper only after that decision.
- Reversibility: Two-way door when both bundles and config rollback remain available.
- Abort/reopen criterion: Keep 8.0.1 and mark 6.x BLOCKED if provenance, hash, AMF behavior, or rollback is missing.

## D06 — Codec QC

- Status: DECIDED
- Decision: H.264 and HEVC each require an independent full 6,335.027-s pass.
- Impact: Any output-affecting fix after T335/T336 invalidates both affected full-length results.
- Reversibility: Two-way door, but computationally expensive.
- Abort/reopen criterion: BLOCKED on decode, End-PTS, frame/audio completeness, drift, terminal image, True Peak, or end-silence failure.

## D07 — Remote divergence

- Status: DECIDED
- Decision: No automatic rebase and no force-push. Fetch, compare, and stop on divergence.
- Impact: Preserves remote history and prevents silent integration of unrelated changes.
- Reversibility: Two-way operational decision; remote mutation is withheld.
- Abort/reopen criterion: BLOCKED if upstream is not an ancestor of the local push candidate. Store the remote diff and request a new integration decision.

## D08 — Brain repository scope

- Status: DECIDED
- Decision: Commit and push only PB Studio paths; preserve every unrelated dirty entry.
- Impact: Brain updates require path-limited staging and a pre-push path audit.
- Reversibility: Two-way before push; after push normal follow-up commits only.
- Abort/reopen criterion: BLOCKED if staged Brain changes contain any path outside `10_Projects/PB_studio/` or if the target remote/branch cannot be verified.

## Threat review outcome

- CONFIRMED: D04, D07, and D08 are the main irreversible/security-sensitive gates.
- CONFIRMED: Direct output publication, production-data mutation, and Git push cross distinct trust boundaries and remain sequential.
- OPEN: Concrete render EOF cause, FFmpeg version decision, and Brain migration applicability.
- BLOCKED: none at T307.
