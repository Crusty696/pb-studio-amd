# T365 — Release GUI and nullable analysis E2E

Status: CONFIRMED  
Executed: 2026-07-30T08:08+02:00–2026-07-30T08:26+02:00

## Production launcher and GPU truth

The first production-launch run exposed a real launcher gap: `launch.ps1`
starts the backend before WPF and sets `PBSTUDIO_BACKEND_MANAGED_EXTERNALLY`,
but only `PythonBridgeService` provisioned the two LHM trust hashes. The
externally managed backend therefore reported:

`PBSTUDIO_LHM_MANIFEST_SHA256 fehlt oder ist ungueltig`

`scripts/runtime_contract.ps1` now validates the canonical
`config/lhm-runtime.json`, bundle boundary, schema/version, reparse-point
status, manifest/library hashes, and conflicting process overrides before it
exports:

- `PBSTUDIO_LHM_MANIFEST_SHA256`
- `PBSTUDIO_LHM_SHA256`

The production launcher already calls this contract with
`-ApplyEnvironment`. A fresh `launch.ps1` run then reported:

- adapter: `AMD Radeon RX 7800 XT`
- DirectML index: `1`
- LUID: `0x00000000_0x0001185b`
- selection policy: `highest_vram_amd`
- physical VRAM ceiling: `16177 MB`
- monitoring: `ready`
- monitoring error: `null`

PowerShell syntax, live environment application, and both trust hashes passed.
The focused regression receipt is
`evidence/T365-lhm-launcher-regression.xml`.

## Release GUI

`evidence/T365-gui-e2e.py` connected to the real Release WPF process through
UI Automation, queried the live backend, navigated the affected views, and
captured 1400×900 screenshots. Every image passed the non-blank color-range
check and was visually inspected.

| View | Verified truth | Screenshot SHA-256 |
|---|---|---|
| Settings | RX 7800 XT, index 1, exact LUID, DirectML active, monitoring ready, 16177 MB | `6AA63FF75F6A1D91CAD299026D9F4B0605FC9906D764C61BC9CCE759BF57F426` |
| Performance | 15872 MB maximum, 15372 MB usable, zero phantom committed/load state | `62A56E17D316A340C0E87E93B2B939776127A2B7739D93ABF56F192CFF0B922F` |
| Modelle | 29 installed live cards, LM Studio and Ollama ready, loaded/on-demand labels | `579433EE158660B0482BCAFCF45FD002436AAB4B1378A14C179C17F91820DBCD` |
| Video | analysis controls and scene-analysis surface render without exception text | `056745D8AA61BF30C57A61327A99C528C24E571C7151BA72487339536DE61D64` |

Machine-readable receipt:
`evidence/T365-gui-runtime.json`
(`41A55BBFF9BAC2BEA9CDAEE52BCF786327A4CA538F72E91E94BF571592E2082D`).

## Nullable runtime analysis

The isolated .NET 9 runtime harness references the production
`PBStudio.UI.csproj`, instantiates the real `ApiClient`, and returns the exact
backend-shaped `/video/analyze` payload with one scene whose
`confidence` is `null`.

Result:

- Release compilation: PASS, zero warnings
- request: exactly one `POST /video/analyze`
- request `clip_id`: `42`
- response `clip_id`: `42`
- scenes: `1`
- `SceneInfo.Confidence is null`: PASS
- retry storm: absent

Receipt:
`evidence/T365-nullable-runtime.json`
(`D36D8DFE7E9E2BD0D36947E2CC6432F99896C66F52C7B1E8E9D14906CC07A43D`).

## Regression and lifecycle checks

- `Tests/test_t357_gpu_wpf_nullability_contracts.py`:
  **19 passed, 1 expected T363 hardware skip, 0 failed**.
- WPF Release `--warnaserror`: **0 warnings, 0 errors**.
- WPF log after the production run: no `JsonException`, unhandled exception,
  fatal error, or repeated video-analysis request.
- Closing WPF stopped the UI, production launcher, backend parent, backend
  worker, and listener on port 8765.
- One non-repeating `POST /project/save` HTTP 400 was logged during shutdown
  because no project was open. It caused no crash or retry and is unrelated
  to nullable video analysis.

CONFIRMED: T365 GUI, adapter/model truth, nullable response deserialization,
and no-retry acceptance criteria pass. T363 remains independently BLOCKED;
T366 and T367 remain open.
