# Specification: Manual acceptance and live session log

## Objective

**OBJ-1:** Let David execute PB Studio acceptance manually and retain emitted app diagnostics in one live file.

## User Stories

### US1 — Manual acceptance (P1)
David follows an ordered checklist for the approved existing project, records PASS/FAIL/NOT RUN and returns one session log.

### US2 — Live evidence (P1)
David starts a recorder before the test or attaches to an already running app. Existing logs and project data remain intact.

## Functional Requirements

- **FR-001:** Provide a German checklist for project identity, missing media, tabs, analysis, preview selection/scrub, AMF export/cancel, save/reopen and honest manual quality judgments.
- **FR-002:** Combine new WPF, backend, stdout/stderr, native crash and launcher lines in a unique append-only UTF-8 session file while the app runs; identify sources and recording times.
- **FR-003:** Track file recreation, truncation and rotation; retain partial UTF-8 lines, flush final fragments, report recording gaps and source read failures explicitly.
- **FR-004:** Never launch, close, control or modify PB Studio or its project through the recorder. Stop independently with Ctrl+C or a finite-duration CLI option.
- **FR-005:** Redact common credentials; bound read chunks and partial lines. State that emitted diagnostics do not prove every internal event, audio perception or semantic quality.

## Technical Requirements

- **TR-001:** Python 3.11 standard library only; Windows paths, PYTHONPATH=src, Tests/; no dependency, schema, API or provider changes.
- **TR-002:** Regression tests and actual recorder CLI run must verify incremental persistence, restart/rotation, redaction and finalization without controlling the app.

## Out of Scope

Automatic GUI acceptance, source-media relinking, screenshots, keyboard contents, raw request/response bodies, exhaustive internal tracing, release acceptance of Spec 00035.

## Acceptance

Checklist and double-click recorder entry point exist. Tests and finite live recording pass. Unavailable inputs or logging gaps remain visible. Spec 00035 evidence and completion markers remain unchanged.

## Task Mapping

Implementation and verification: T001–T004 in `tasks.md`.
