# Plan: Manual acceptance and live session log

## Constraints

No GUI control or restart requested. Preserve active user app, existing logs, approved project and Spec 00035 receipts. Python standard library only; no dependency/API/schema change. Vault `_wiki/decisions` is absent; no architecture decision required.

## Design

An independent polling recorder tails emitted WPF/backend/stdout/stderr/native/launcher diagnostics from byte offsets into one unique UTF-8 log. Start before manual app launch or attach from current file ends. Stable file identity and a prefix fingerprint detect recreation/truncation, with explicit gap markers. Read bounded chunks; buffer incomplete lines; redact common credential formats; flush every output record. Existing source files are read-only. A double-click batch wrapper starts recording; Ctrl+C ends recording and flushes final fragments. No SSE client is created, so the recorder cannot keep the backend alive.

Capture WPF-delivered SSE events before UI progress throttling using the existing ILogger/file path and redactor; this covers task progress/errors/state changes received by WPF. Existing UI routed action logging remains in place. Document logging limitations, including historical messages, file rotation between polls, unlogged states and manual audio/quality judgments.

## Verification

Meaningful recorder regressions cover existing-content exclusion, incremental flush, split Unicode, source recreation/rotation, partial-line handling, credential redaction and bounded overlong lines. Existing/native SSE tests plus Release build verify additive event logging. A finite recorder run against the active app verifies actual file persistence without app control. Validate script entry point three finite runs.

## Delivery

German manual checklist with approved project paths, missing-media preflight and PASS/FAIL/NOT RUN fields; recorder and batch entry point; test/QC report. No Spec 00035 release marker.
