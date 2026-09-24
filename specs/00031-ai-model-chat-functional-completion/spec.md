# Specification: AI Models and Chat Functional Completion

## Objective

Audit and repair every productively reachable function in the MODELLE and CHAT tabs, including provider discovery, model inventory, task selection, overrides, download/load/delete lifecycle, chat streaming, history, cancellation, tool dispatch, provider fallback, status SSE, and project isolation. The HIRN/Brain tab is a separate later area.

## User Stories

### US1 — Truthful model management (P1)

As an editor, I can see the actual installed, loaded, usable, and downloadable local models and perform supported model actions without stale cards or invented capability states.

### US2 — Reliable model selection (P1)

As an editor, each AI task uses the configured compatible provider/model pair, honors valid overrides, rejects stale or incompatible overrides visibly, and performs only bounded compatible fallback.

### US3 — Reliable AI chat (P1)

As an editor, I can send, stream, cancel, retry, and clear project-scoped chat turns while model, tool, error, and completion events remain ordered and visible.

### US4 — Safe tool execution (P1)

As an editor, chat tools execute only registered local operations with validated arguments, bounded timeouts, truthful results, and no cross-project state leakage.

## Requirements

### FR-402 Productive-path inventory

Catalog every reachable MODELLE/CHAT control, command, DTO, endpoint, provider operation, selection tier, stream event, history mutation, tool call, and status update. Mark unreachable legacy paths explicitly.

### FR-403 Runtime/provider truth

Installed, loaded, usable, compatible, and downloadable states must remain distinct and come from supported live provider APIs or pinned local manifests. Stale configuration must never be presented as live runtime truth.

### FR-404 Selection integrity

Task overrides, preferences, capability filters, failed-model exclusion, bounded refresh, and provider fallback must select exactly one compatible candidate or return one truthful failure reason. Vision and tool-use capability gates must not silently select incompatible models.

### FR-405 Chat lifecycle

Chat streaming must preserve ordered model/text/tool/error/done events, terminate cancellation and failures cleanly, avoid stuck busy/status state, bound retained history, and reject stale project results.

### FR-406 Tool lifecycle

Tool schemas, dispatch names, arguments, loopback requests, long-running timeouts, results, and errors must agree across UI, router, agent, and backend endpoints. Unknown or failed tools must be visible and must not masquerade as successful assistant output.

### FR-407 Mutation safety

Model downloads, loads, deletions, task overrides, chat history clears, and provider changes must be scoped, recoverable where possible, and reject conflicting/stale operations without corrupting config or UI state.

### TR-380 Deferred verification

Regression tests, builds, provider probes, and GUI/live runs are prohibited until the user explicitly authorizes them. The implementation phase may add/update regression definitions but must not execute them.

### OR-357 Compatibility

No dependency, migration, cloud fallback, CUDA/ROCm path, CPU neural-inference fallback, public API break, destructive model deletion outside an explicit UI action, or unrelated refactor is permitted.

## Success Criteria

- SC-112: Every productive MODELLE/CHAT function has a mapped active path and source-audit status.
- SC-113: Every proven defect and open implementation task in the area is repaired before reporting back.
- SC-114: No silent provider/model/tool fallback or stale project publication remains in audited paths.
- SC-115: Verification remains explicitly pending; no PASS/release claim or QC marker exists before user authorization.

## Out of Scope

- HIRN/Brain tab and learning algorithms.
- Pacing/Director behavior already covered by Spec 00030.
- New providers, new dependencies, remote/cloud inference, model training, or UI redesign.
