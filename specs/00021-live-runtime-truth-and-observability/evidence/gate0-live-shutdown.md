# Gate 0 Live Shutdown Reproduction — 2026-08-10

## Runtime receipt

- Source: HEAD `958353b25575b650c85f052f2a6a2149790f9577` plus only the bounded launcher deadline adjustment.
- WPF Release build: PASS, 0 warnings, 0 errors.
- Recovery start: healthy after approximately 42 seconds; WPF Release process responsive.
- LHM: manifest/hash validation active; physical sensors reported for the same live-selected RX 7800 XT LUID.
- DirectML selection: discrete RX 7800 XT with highest dedicated VRAM. Historical index/LUID fields in the asset-release manifest were not used as boot-stable identity.

## Reproduction

1. An existing three-clip QC project was opened through the real WPF project picker.
2. A pending clip was selected.
3. Only the requested Tags/Colors path was enabled; scene, RAFT and SigLIP work were disabled for this probe.
4. WPF issued `POST /video/analyze`; LM Studio selected the configured live vision override and began a cold call.
5. The application was closed while that call was active.

## Actual result

- Backend logged `RuntimeError: No response returned` through `OwnerCapabilityMiddleware`.
- The GPU middleware logged the same request as an error.
- The correct analyzed media row reached a durable terminal receipt:
  `captions=interrupted`, `colors=interrupted`, all unrequested stages `skipped`,
  and explicit interruption errors.
- Der persistierte Abschlussdatensatz enthielt `tags=[]`, `tag_source=none` und
  Gesamtstatus `failed`; ein valider früherer Caption-Commit war in diesem
  Datensatz nicht belegt und wurde deshalb nicht als erhaltene Wahrheit
  behauptet.
- Backend shutdown completed; no process remained listening on port 8765.

## Gate decision

- SC-103: FAIL — current build still emits the ASGI traceback.
- FR-395 persistence: PASS — requested active stages reached a terminal
  `interrupted` receipt before shutdown.
- FR-395 transport: FAIL — cancellation still escaped through
  `BaseHTTPMiddleware` as an ASGI traceback.
- Keine Originalmediendatei wurde geändert.
- T014/T015 require a focused current fix and proof before normal/degradation live checks resume.
