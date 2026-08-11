# Gate 0 Baseline — 2026-08-10

## Source identity

- HEAD: `958353b25575b650c85f052f2a6a2149790f9577`
- Branch: `codex/obj75-open-bug-fixes`
- Porcelain before runtime start:
  - `M config.json` — pre-existing local runtime/user configuration; excluded from OBJ-76 edits.
  - `?? specs/00021-live-runtime-truth-and-observability/` — new OBJ-76 SDD workspace.
- `config.json` SHA-256: `f903b666d3032fee7497b879e385a8ed4206569fa6e0b6278f0261b3178d5a88`
- Python: `3.11.9`
- NumPy: `1.26.4`

## T052/T053 ancestry

- T052 implementation commits `aaf39a6`, `0f5a8a5` and `8a0d924` are ancestors of HEAD.
- T053/QC anchor `bb6916f` is an ancestor of HEAD.
- Existing focused evidence records 73 Python video/runtime contracts, three C# video contracts and a clean WPF Release build.
- This evidence is implementation/QC evidence only; it is not substituted for the OBJ-76 live gate.

## Unchanged Release build

- Command: `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release --nologo`
- Result: PASS, 0 warnings, 0 errors.

## Unchanged canonical start attempt

- `launch.ps1 -NoPause` resolved the canonical Python 3.11 runtime and FFmpeg 6.1.1 contract.
- Result: FAIL. The launcher stopped its owned backend after the fixed 30-second health deadline.
- A foreground start with the same runtime and owner-capability contract became healthy after approximately 45 seconds.
- Current root cause: valid recovery/bootstrap work exceeds the launcher's fixed 30-second deadline; no import exception was emitted.
- The controlled diagnostic interruption left `RUNTIME_DIRTY`; the next startup must prove recovery before the live video checks continue.

## Gate decision

- T001: PASS.
- T002: PASS after the bounded launcher deadline accepted the observed recovery startup duration.
- T003: PARTIAL FAIL; the current shutdown probe persisted terminal interrupted
  stages but reproduced an ASGI traceback. See `gate0-live-shutdown.md`.
- No video, UI or configuration fix was applied before this result.
