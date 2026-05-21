# nswag OpenAPI → C# Code-Gen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual C# DTO records (`PBStudio.UI/Models/*.cs`) with generated code from FastAPI's `openapi.json`, eliminating silent schema-drift between backend and frontend (Audit V2 finding S-H1b).

**Architecture:** NSwag.MSBuild package adds a `BeforeBuild` MSBuild target that reads a checked-in `openapi.snapshot.json` (cached from the running backend) and generates `PBStudio.UI/Generated/ApiTypes.g.cs`. Migration is incremental: new generated types live in the `PBStudio.UI.Generated` namespace next to existing manual records; consumers switch one DTO at a time; a refresh script regenerates the snapshot from a live backend on demand.

**Tech Stack:** NSwag 14.x (`NSwag.MSBuild`), FastAPI's built-in `/openapi.json`, C# `partial`-class workaround for property additions.

**Scope check:** Single subsystem (build-pipeline + DTO generation). Out of scope: generating the `ApiClient.cs` HTTP-call methods themselves (that would be a follow-up plan — too risky for one cycle since `ApiClient.cs` has hand-rolled SSE, cancellation, and error-handling logic the generator would clobber).

---

## File Structure

**New files:**
- `PBStudio.UI/openapi.snapshot.json` — checked-in cached OpenAPI spec
- `PBStudio.UI/nswag.json` — NSwag generator config (DTO-only)
- `PBStudio.UI/Generated/.gitkeep` — placeholder so empty dir survives
- `PBStudio.UI/Generated/ApiTypes.g.cs` — generated, gitignored
- `scripts/dev/refresh-openapi-snapshot.ps1` — fetches `/openapi.json` from running backend, overwrites snapshot
- `Tests/test_openapi_snapshot_drift.py` — pytest that runs `/openapi.json` against checked-in snapshot, fails on drift
- `docs/openapi-codegen.md` — short developer-facing README

**Modified files:**
- `PBStudio.UI/PBStudio.UI.csproj` — add NSwag.MSBuild PackageReference + `BeforeBuild` Target
- `.gitignore` — add `PBStudio.UI/Generated/*.g.cs`
- `PBStudio.UI/Models/VramTelemetryResponse.cs` — migrate to use generated type via type-alias or deletion
- `PBStudio.UI/Models/ThumbstripResponse.cs` — same
- `PBStudio.UI/Models/ClipwaveResponse.cs` — same
- `PBStudio.UI/Models/BrainExplainResponse.cs` — same
- `PBStudio.UI/build.ps1` — call `dotnet restore` before build so NSwag tool resolves
- `scripts/start.bat` (or `launch.ps1`) — no change needed (snapshot is checked-in; generation runs at build time, not start)

**Files NOT touched:**
- `backend/*` — already exposes `/openapi.json` (FastAPI default)
- `PBStudio.UI/Services/ApiClient.cs` — out of scope (manual HTTP code stays)
- `PBStudio.UI/Models/TimelineEntry.cs`, `VideoClip.cs`, `AudioClip.cs` — these contain ObservableObject UI logic, NOT pure DTOs; leave manual

---

## Task 1: Verify NSwag.MSBuild supports .NET 9 + create initial snapshot

**Files:**
- Create: `PBStudio.UI/openapi.snapshot.json`
- Read-only check: `PBStudio.UI/PBStudio.UI.csproj`

- [ ] **Step 1: Confirm NSwag 14.x supports .NET 9**

Run:
```powershell
dotnet add PBStudio.UI/PBStudio.UI.csproj package NSwag.MSBuild --version 14.2.0 --no-restore
```
Expected: `info : Paket "NSwag.MSBuild" wurde mit Version "14.2.0" hinzugefügt.`
If error: try `14.4.0`, then `14.0.8` (older). Document which version worked.

- [ ] **Step 2: Roll back the package add (we add it properly in Task 2)**

Run:
```powershell
dotnet remove PBStudio.UI/PBStudio.UI.csproj package NSwag.MSBuild
```

- [ ] **Step 3: Start backend in background**

Run:
```powershell
$env:PYTHONPATH = "src"
Start-Process -NoNewWindow -RedirectStandardOutput "$env:TEMP\uvicorn.out" `
  -FilePath ".venv\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","backend.main:app","--port","8765","--log-level","warning"
Start-Sleep -Seconds 5
```

- [ ] **Step 4: Fetch openapi.json and save as snapshot**

Run:
```powershell
Invoke-RestMethod -Uri "http://localhost:8765/openapi.json" -OutFile "PBStudio.UI/openapi.snapshot.json"
```
Expected: file size 50–200 KB, JSON valid.

- [ ] **Step 5: Verify snapshot contains the audit-referenced endpoints**

Run:
```powershell
$snap = Get-Content PBStudio.UI/openapi.snapshot.json -Raw | ConvertFrom-Json
$paths = $snap.paths.PSObject.Properties.Name
"thumbstrip", "clipwave", "vram", "brain/explain" | ForEach-Object {
    $hit = $paths -match $_
    Write-Host "$_ : $($hit -join ', ')"
}
```
Expected (all four lines non-empty):
```
thumbstrip : /video/thumbstrip/{clip_id}
clipwave : /video/clipwave/{clip_id}
vram : /health/vram
brain/explain : /brain/explain/{cut_id}
```

If `vram` line is empty, **STOP** — this is the underlying S-H1b root cause (endpoint missing). Report back: nswag plan needs `/health/vram` endpoint added to backend first.

- [ ] **Step 6: Kill backend**

Run:
```powershell
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*uvicorn*" -or $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force
```
(Fallback if MainWindowTitle is empty: `Stop-Process -Name python -Force` — only if no other python work is in flight.)

- [ ] **Step 7: Commit the snapshot**

```powershell
git add PBStudio.UI/openapi.snapshot.json
git commit -m "chore(ui): checked-in openapi.snapshot.json baseline (S-H1b prereq)"
```

---

## Task 2: Add NSwag.MSBuild package + nswag.json config

**Files:**
- Modify: `PBStudio.UI/PBStudio.UI.csproj`
- Create: `PBStudio.UI/nswag.json`
- Modify: `.gitignore`

- [ ] **Step 1: Add NSwag.MSBuild package**

```powershell
dotnet add PBStudio.UI/PBStudio.UI.csproj package NSwag.MSBuild --version 14.2.0
```
Use the version confirmed working in Task 1 Step 1.

- [ ] **Step 2: Create nswag.json with DTO-only config**

Create `PBStudio.UI/nswag.json`:

```json
{
  "runtime": "Net90",
  "defaultVariables": null,
  "documentGenerator": {
    "fromDocument": {
      "json": "openapi.snapshot.json",
      "url": "",
      "output": null
    }
  },
  "codeGenerators": {
    "openApiToCSharpClient": null,
    "openApiToCSharpController": null,
    "openApiToTypeScriptClient": null
  },
  "codeGenerator": {
    "openApiToCSharp": {
      "namespace": "PBStudio.UI.Generated",
      "className": "ApiTypes",
      "generateClientClasses": false,
      "generateClientInterfaces": false,
      "generateDtoTypes": true,
      "dateType": "System.DateTimeOffset",
      "dateTimeType": "System.DateTimeOffset",
      "arrayType": "System.Collections.Generic.IList",
      "arrayInstanceType": "System.Collections.Generic.List",
      "dictionaryType": "System.Collections.Generic.IDictionary",
      "dictionaryInstanceType": "System.Collections.Generic.Dictionary",
      "classStyle": "Record",
      "jsonLibrary": "SystemTextJson",
      "generateOptionalPropertiesAsNullable": true,
      "generateNullableReferenceTypes": true,
      "output": "Generated/ApiTypes.g.cs"
    }
  }
}
```

- [ ] **Step 3: Add BeforeBuild Target to csproj**

Modify `PBStudio.UI/PBStudio.UI.csproj`. Insert this block before the closing `</Project>`:

```xml
  <Target Name="NSwag" BeforeTargets="BeforeBuild" Inputs="openapi.snapshot.json;nswag.json" Outputs="Generated/ApiTypes.g.cs">
    <Message Text="NSwag: generating Generated/ApiTypes.g.cs from openapi.snapshot.json" Importance="high" />
    <Exec Command="dotnet &quot;$(NSwagExe_Net90)&quot; run nswag.json /variables:Configuration=$(Configuration)" WorkingDirectory="$(MSBuildProjectDirectory)" />
  </Target>

  <ItemGroup>
    <Compile Remove="Generated/**" />
    <None Remove="Generated/**" />
  </ItemGroup>
  <ItemGroup>
    <Compile Include="Generated/ApiTypes.g.cs" Condition="Exists('Generated/ApiTypes.g.cs')" />
  </ItemGroup>
```

The Inputs/Outputs make MSBuild incremental: re-runs nswag only if snapshot or config changed.

- [ ] **Step 4: Add Generated/*.g.cs to .gitignore**

In `.gitignore`, append:

```
# NSwag generated DTOs — regenerated from openapi.snapshot.json on each build
PBStudio.UI/Generated/*.g.cs
```

- [ ] **Step 5: Create placeholder so Generated/ dir exists**

```powershell
New-Item -ItemType Directory -Path PBStudio.UI/Generated -Force | Out-Null
Set-Content -Path PBStudio.UI/Generated/.gitkeep -Value "" -Encoding utf8
git add PBStudio.UI/Generated/.gitkeep
```

- [ ] **Step 6: Test the build runs nswag**

```powershell
dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release -v minimal 2>&1 | Select-String -Pattern "NSwag|error|Erstellen erfolgreich|Erstellungsvorgang"
```
Expected: line containing `NSwag: generating Generated/ApiTypes.g.cs` AND `Erstellen erfolgreich` AND no `error CS`.

- [ ] **Step 7: Verify generated file content**

```powershell
Test-Path PBStudio.UI/Generated/ApiTypes.g.cs
(Get-Content PBStudio.UI/Generated/ApiTypes.g.cs | Measure-Object -Line).Lines
Select-String -Path PBStudio.UI/Generated/ApiTypes.g.cs -Pattern "VramTelemetryResponse|ThumbstripResponse|ClipwaveResponse|BrainExplainResponse" | Select-Object -First 10
```
Expected: file exists, > 200 lines, all four type-names present.

- [ ] **Step 8: Commit config and csproj changes**

```powershell
git add PBStudio.UI/PBStudio.UI.csproj PBStudio.UI/nswag.json .gitignore PBStudio.UI/Generated/.gitkeep
git commit -m "feat(ui): NSwag.MSBuild generator for OpenAPI -> C# DTOs (S-H1b infra)"
```

---

## Task 3: Snapshot-drift pytest

**Files:**
- Create: `Tests/test_openapi_snapshot_drift.py`

- [ ] **Step 1: Write the failing test**

Create `Tests/test_openapi_snapshot_drift.py`:

```python
"""S-H1b (Audit V2): fails when backend openapi.json drifts from
checked-in PBStudio.UI/openapi.snapshot.json. Forces dev to refresh
the snapshot before WPF build (else generated DTOs go stale)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


SNAPSHOT_PATH = Path(__file__).parent.parent / "PBStudio.UI" / "openapi.snapshot.json"


def _normalize(spec: dict) -> dict:
    """Strip non-deterministic fields (version stamps, server URLs)
    so the diff focuses on schema-relevant differences."""
    out = dict(spec)
    out.pop("servers", None)
    info = dict(out.get("info", {}))
    info.pop("version", None)
    out["info"] = info
    return out


def test_snapshot_exists():
    assert SNAPSHOT_PATH.exists(), (
        f"Snapshot missing: {SNAPSHOT_PATH}. "
        "Run scripts/dev/refresh-openapi-snapshot.ps1 to create it."
    )


def test_snapshot_matches_live_backend():
    client = TestClient(app)
    live = client.get("/openapi.json").json()

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    live_paths = sorted(_normalize(live).get("paths", {}).keys())
    snap_paths = sorted(_normalize(snapshot).get("paths", {}).keys())

    missing_in_snapshot = set(live_paths) - set(snap_paths)
    missing_in_live = set(snap_paths) - set(live_paths)

    assert not missing_in_snapshot, (
        f"Backend has paths NOT in snapshot (run refresh script): "
        f"{sorted(missing_in_snapshot)}"
    )
    assert not missing_in_live, (
        f"Snapshot has paths NOT in live backend (delete from snapshot): "
        f"{sorted(missing_in_live)}"
    )


def test_snapshot_schemas_consistent():
    """Per-component schemas must match key-set. Catches added/removed fields
    without requiring full deep-diff (tests aren't a regression suite for
    OpenAPI itself — they're a drift-alarm)."""
    client = TestClient(app)
    live = client.get("/openapi.json").json()
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    live_schemas = (live.get("components") or {}).get("schemas") or {}
    snap_schemas = (snapshot.get("components") or {}).get("schemas") or {}

    diffs = []
    for name in set(live_schemas) | set(snap_schemas):
        if name not in live_schemas:
            diffs.append(f"snapshot has schema '{name}' not in live")
            continue
        if name not in snap_schemas:
            diffs.append(f"live has schema '{name}' not in snapshot")
            continue
        live_props = set((live_schemas[name].get("properties") or {}).keys())
        snap_props = set((snap_schemas[name].get("properties") or {}).keys())
        if live_props != snap_props:
            diffs.append(
                f"{name}: properties diverge "
                f"live={sorted(live_props)} snap={sorted(snap_props)}"
            )

    assert not diffs, "Schema drift:\n  " + "\n  ".join(diffs)
```

- [ ] **Step 2: Run the test**

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest Tests/test_openapi_snapshot_drift.py -v
```
Expected: 3 passed (snapshot matches because Task 1 just generated it from the same backend).

- [ ] **Step 3: Commit**

```powershell
git add Tests/test_openapi_snapshot_drift.py
git commit -m "test(openapi): snapshot-drift detection vs live backend"
```

---

## Task 4: Refresh script

**Files:**
- Create: `scripts/dev/refresh-openapi-snapshot.ps1`

- [ ] **Step 1: Create the refresh script**

Create `scripts/dev/refresh-openapi-snapshot.ps1`:

```powershell
#requires -version 5
<#
.SYNOPSIS
  Refreshes PBStudio.UI/openapi.snapshot.json from a live backend.
.DESCRIPTION
  S-H1b (Audit V2): the snapshot is the source for NSwag DTO generation.
  Run this after any backend route/schema change, then rebuild WPF.

  The script starts a uvicorn backend if none is running on port 8765.
.EXAMPLE
  pwsh scripts/dev/refresh-openapi-snapshot.ps1
#>
param(
    [int]$Port = 8765,
    [int]$StartupWaitSec = 8
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$snapshotPath = Join-Path $repoRoot "PBStudio.UI/openapi.snapshot.json"
$uri = "http://localhost:$Port/openapi.json"

function Test-BackendAlive {
    try {
        $null = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

$ownedBackend = $false
if (-not (Test-BackendAlive)) {
    Write-Host "Backend not running on port $Port — starting uvicorn"
    $env:PYTHONPATH = "src"
    $proc = Start-Process -PassThru -NoNewWindow `
        -RedirectStandardOutput "$env:TEMP\refresh-openapi.uvicorn.out" `
        -RedirectStandardError  "$env:TEMP\refresh-openapi.uvicorn.err" `
        -FilePath ".venv\Scripts\python.exe" `
        -ArgumentList "-m","uvicorn","backend.main:app","--port","$Port","--log-level","warning"
    $ownedBackend = $true
    Start-Sleep -Seconds $StartupWaitSec
    if (-not (Test-BackendAlive)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        throw "Backend didn't come up within $StartupWaitSec s. See $env:TEMP\refresh-openapi.uvicorn.err"
    }
} else {
    Write-Host "Backend already running on port $Port — using existing"
}

try {
    Write-Host "Fetching $uri"
    $spec = Invoke-RestMethod -Uri $uri
    $json = $spec | ConvertTo-Json -Depth 100 -Compress:$false
    Set-Content -Path $snapshotPath -Value $json -Encoding utf8
    $size = (Get-Item $snapshotPath).Length
    Write-Host "Wrote $snapshotPath ($size bytes)"
} finally {
    if ($ownedBackend) {
        Write-Host "Stopping owned backend (PID $($proc.Id))"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. git diff PBStudio.UI/openapi.snapshot.json   # review changes"
Write-Host "  2. dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release"
Write-Host "  3. pytest Tests/test_openapi_snapshot_drift.py"
Write-Host "  4. git add + commit"
```

- [ ] **Step 2: Verify it runs**

```powershell
pwsh scripts/dev/refresh-openapi-snapshot.ps1
```
Expected: `Wrote .../openapi.snapshot.json (<bytes>)`. The snapshot will be re-written but if no backend changes happened since Task 1 the git diff is empty.

- [ ] **Step 3: Check no diff was introduced**

```powershell
git diff --stat PBStudio.UI/openapi.snapshot.json
```
Expected: empty output. If non-empty, that's the actual drift — investigate, then re-baseline.

- [ ] **Step 4: Commit**

```powershell
git add scripts/dev/refresh-openapi-snapshot.ps1
git commit -m "chore(scripts): refresh-openapi-snapshot.ps1 helper"
```

---

## Task 5: Migrate VramTelemetryResponse to generated type

**Files:**
- Modify: `PBStudio.UI/Models/VramTelemetryResponse.cs`
- Modify: `PBStudio.UI/Services/ApiClient.cs` (using-statement only)
- Modify: `PBStudio.UI/ViewModels/VramTelemetryViewModel.cs` (using-statement only)

- [ ] **Step 1: Inspect what NSwag generated**

```powershell
Select-String -Path PBStudio.UI/Generated/ApiTypes.g.cs -Pattern "class VramTelemetryResponse|record VramTelemetryResponse" -Context 0,10
```
Note the property names + types NSwag chose. They may use PascalCase already (System.Text.Json with case-insensitive matching), but verify before deleting the hand-rolled record.

- [ ] **Step 2: Replace manual record with type-alias**

Replace the entire content of `PBStudio.UI/Models/VramTelemetryResponse.cs` with:

```csharp
// S-H1b (Audit V2): manual record replaced by NSwag-generated type in
// PBStudio.UI.Generated namespace. This file kept as a using-alias shim
// to avoid touching every caller in one go. Delete once all callers
// import PBStudio.UI.Generated directly.
global using VramTelemetryResponse = PBStudio.UI.Generated.VramTelemetryResponse;
global using VramTelemetryEntry = PBStudio.UI.Generated.VramTelemetryEntry;
global using VramTelemetrySummary = PBStudio.UI.Generated.VramTelemetrySummary;
global using VramDurationStats = PBStudio.UI.Generated.VramDurationStats;
global using VramPeakStats = PBStudio.UI.Generated.VramPeakStats;
global using VramHistogramBar = PBStudio.UI.Generated.VramHistogramBar;
```

The `global using` directive makes the alias visible project-wide so no other file needs editing.

- [ ] **Step 3: Build to check for property-name divergence**

```powershell
dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release 2>&1 | Select-String -Pattern "error CS"
```
Expected: no CS errors. If any error like `'VramTelemetryEntry' does not contain a definition for 'XXX'`, the NSwag-generated property names differ. Two options:
- Rename in the generated file via `nswag.json` (use the `propertyNameGenerator` setting), OR
- Update the ViewModel to use the generated name.

Pick the cheapest option per error. Document choice in step-summary commit.

- [ ] **Step 4: Run tests**

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest Tests/ -q -k "not slow"
```
Expected: same passing count as before (688), no new failures.

- [ ] **Step 5: Commit**

```powershell
git add PBStudio.UI/Models/VramTelemetryResponse.cs
git commit -m "refactor(ui): migrate VramTelemetryResponse to NSwag-generated type"
```

---

## Task 6: Migrate ThumbstripResponse + ClipwaveResponse

**Files:**
- Modify: `PBStudio.UI/Models/ThumbstripResponse.cs`
- Modify: `PBStudio.UI/Models/ClipwaveResponse.cs`

- [ ] **Step 1: Replace ThumbstripResponse with type-alias**

Replace entire content of `PBStudio.UI/Models/ThumbstripResponse.cs`:

```csharp
// S-H1b (Audit V2): NSwag-generated. Manual shim for backwards compat.
global using ThumbstripResponse = PBStudio.UI.Generated.ThumbstripResponse;
```

- [ ] **Step 2: Replace ClipwaveResponse with type-alias**

Replace entire content of `PBStudio.UI/Models/ClipwaveResponse.cs`:

```csharp
// S-H1b (Audit V2): NSwag-generated. Manual shim for backwards compat.
global using ClipwaveResponse = PBStudio.UI.Generated.ClipwaveResponse;
```

- [ ] **Step 3: Build + run pytest**

```powershell
dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release 2>&1 | Select-String -Pattern "error CS|Erstellen erfolgreich"
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest Tests/test_video_thumbstrip_endpoint.py Tests/test_video_clipwave_endpoint.py -q
```
Expected: 0 CS errors, "Erstellen erfolgreich". 6 pytest passed.

- [ ] **Step 4: Commit**

```powershell
git add PBStudio.UI/Models/ThumbstripResponse.cs PBStudio.UI/Models/ClipwaveResponse.cs
git commit -m "refactor(ui): migrate Thumbstrip/Clipwave DTOs to NSwag-generated"
```

---

## Task 7: Migrate BrainExplainResponse

**Files:**
- Modify: `PBStudio.UI/Models/BrainExplainResponse.cs`

- [ ] **Step 1: Inspect what NSwag generated for BrainExplain types**

```powershell
Select-String -Path PBStudio.UI/Generated/ApiTypes.g.cs -Pattern "class BrainExplainResponse|class BrainAxisContribution|record BrainExplain|record BrainAxis" -Context 0,8
```
Confirm both `BrainExplainResponse` and `BrainAxisContribution` were emitted (the audit calls out both as part of the same response).

- [ ] **Step 2: Replace manual records with type-aliases**

Replace entire content of `PBStudio.UI/Models/BrainExplainResponse.cs`:

```csharp
// S-H1b (Audit V2): NSwag-generated. Manual shim for backwards compat.
global using BrainExplainResponse = PBStudio.UI.Generated.BrainExplainResponse;
global using BrainAxisContribution = PBStudio.UI.Generated.BrainAxisContribution;
```

- [ ] **Step 3: Build + check Timeline view still compiles**

`TimelineView.xaml.cs` uses `BrainExplainResponse` for the confidence-tooltip. Build will surface any property-rename issues.

```powershell
dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release 2>&1 | Select-String -Pattern "error CS|Erstellen erfolgreich"
```
Expected: no CS errors.

If the build complains about property mismatches (e.g. `final_score` → `FinalScore` mapping issue), fix the consuming code (`TimelineViewModel.cs` or `TimelineView.xaml.cs`) to use the new property names. Do not patch the generated file — edit the call site.

- [ ] **Step 4: Run pytest**

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest Tests/ -q -k "brain"
```
Expected: all brain-related tests still passing.

- [ ] **Step 5: Commit**

```powershell
git add PBStudio.UI/Models/BrainExplainResponse.cs
# If call-site fixes were needed:
git add PBStudio.UI/ViewModels/TimelineViewModel.cs PBStudio.UI/Views/TimelineView.xaml.cs
git commit -m "refactor(ui): migrate BrainExplainResponse to NSwag-generated"
```

---

## Task 8: Doc + final integration test

**Files:**
- Create: `docs/openapi-codegen.md`
- Modify: `Tests/test_openapi_snapshot_drift.py` (extend with a generated-build sanity check)

- [ ] **Step 1: Write the developer docs**

Create `docs/openapi-codegen.md`:

```markdown
# OpenAPI → C# Code Generation

Backend Pydantic schemas are the single source of truth for HTTP DTOs.
WPF C# DTOs in `PBStudio.UI/Generated/` are auto-generated from
`PBStudio.UI/openapi.snapshot.json` at build time via NSwag.MSBuild.

## Workflow

When you change a backend Pydantic schema:

1. Start backend: `python -m uvicorn backend.main:app --port 8765`
2. Refresh snapshot:
   ```
   pwsh scripts/dev/refresh-openapi-snapshot.ps1
   ```
3. Review the diff: `git diff PBStudio.UI/openapi.snapshot.json`
4. Rebuild WPF: `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release`
5. Run tests: `pytest Tests/test_openapi_snapshot_drift.py`
6. Commit snapshot + any call-site fixes.

## Files

| Path | Purpose | Tracked? |
|---|---|---|
| `PBStudio.UI/openapi.snapshot.json` | Cached spec, source for generation | yes |
| `PBStudio.UI/nswag.json` | Generator config | yes |
| `PBStudio.UI/Generated/ApiTypes.g.cs` | Generated DTOs | NO (.gitignore) |
| `PBStudio.UI/Models/<X>Response.cs` | `global using` shims for backwards compat | yes |

## Adding a new DTO

1. Add Pydantic model + endpoint in `backend/schemas/` + `backend/routers/`.
2. Refresh snapshot (see Workflow above).
3. Build — NSwag will emit the type into `PBStudio.UI.Generated`.
4. Reference it directly: `using PBStudio.UI.Generated;` or via a
   `global using X = PBStudio.UI.Generated.X;` shim in `Models/`.

## Why a snapshot file?

- CI builds without a live backend.
- Cold-start dev machines don't need uvicorn running for the WPF
  project to compile.
- The snapshot-drift pytest forces an explicit `git diff` review of
  schema changes (you can't accidentally regenerate-and-forget).

## Audit reference

Audit V2 finding S-H1b in `AUDIT_FULL_STACK_2026-05-19_v2.md`.
```

- [ ] **Step 2: Extend the drift-test with a "generated file is fresh" check**

Append to `Tests/test_openapi_snapshot_drift.py`:

```python
def test_generated_dtos_not_stale_relative_to_snapshot():
    """If Generated/ApiTypes.g.cs is older than the snapshot, NSwag
    didn't run since the last snapshot refresh. Caller should rebuild."""
    snapshot = Path(__file__).parent.parent / "PBStudio.UI" / "openapi.snapshot.json"
    generated = (
        Path(__file__).parent.parent
        / "PBStudio.UI" / "Generated" / "ApiTypes.g.cs"
    )
    if not generated.exists():
        pytest.skip(
            "Generated/ApiTypes.g.cs not built yet — "
            "run `dotnet build PBStudio.UI/PBStudio.UI.csproj` first"
        )
    assert generated.stat().st_mtime >= snapshot.stat().st_mtime - 1.0, (
        f"Generated DTOs older than snapshot. "
        f"Rebuild WPF: dotnet build PBStudio.UI/PBStudio.UI.csproj"
    )
```

- [ ] **Step 3: Run the extended test**

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest Tests/test_openapi_snapshot_drift.py -v
```
Expected: 4 passed (3 from Task 3 + 1 new).

- [ ] **Step 4: Run full pytest one more time**

```powershell
.venv\Scripts\python.exe -m pytest Tests/ -q --ignore=Tests/test_app_state.py
```
Expected: 689 passed (688 previous + 1 new test, the other 3 from Task 3 are already in the previous count if `test_openapi_snapshot_drift.py` was committed before this point).

- [ ] **Step 5: Commit docs + extended test**

```powershell
git add docs/openapi-codegen.md Tests/test_openapi_snapshot_drift.py
git commit -m "docs(ui): openapi-codegen workflow + freshness drift test"
```

- [ ] **Step 6: Push**

```powershell
git push origin main
```

---

## Task 9: Update Audit findings + Vault sync

**Files:**
- Modify: `AUDIT_FULL_STACK_2026-05-19_v2.md`
- Vault: `C:\Users\david\Brain\10_Projects\PB_studio\open-tasks\2026-05-19-post-timeline-merge.md`

- [ ] **Step 1: Mark S-H1b resolved in the audit doc**

Find the line `#### S-H1 [HIGH] Frontend VramTelemetry.cs Records sind Stubs ohne Backend-Endpoint` in `AUDIT_FULL_STACK_2026-05-19_v2.md` and replace it with:

```markdown
#### S-H1b [HIGH] DTO-Mismatch /health/vram Response vs WPF VramTelemetryResponse.cs ✅ RESOLVED 2026-05-19
- **Evidence:** war Stubs in 53abecd, Vram-Endpoint Schema unbekannt.
- **Resolution:** NSwag.MSBuild generiert `PBStudio.UI/Generated/ApiTypes.g.cs`
  aus `PBStudio.UI/openapi.snapshot.json` (FastAPI). Manuelle DTOs in
  `PBStudio.UI/Models/*Response.cs` durch `global using`-Shims ersetzt.
  Plan: `docs/superpowers/plans/2026-05-19-nswag-openapi-codegen.md`.
- **Status:** DONE — schema drift jetzt build-time-detected.
```

- [ ] **Step 2: Update open-tasks Vault doc**

Edit `C:\Users\david\Brain\10_Projects\PB_studio\open-tasks\2026-05-19-post-timeline-merge.md`. Find the row:

```
| #6 VRAM-Stubs | ⚠️ DEFERRED | ... |
```

Replace with:

```
| #6 VRAM-Stubs | ✅ DONE 2026-05-20 | nswag-generated DTOs, schema-drift pytest, refresh-script |
```

- [ ] **Step 3: Update CLAUDE.md Section 3**

Edit `CLAUDE.md`. In Section 3 (PROJECT BRAIN), find:

```
- **#16 E010 abschliessen: ...
```

Right before that line, add:

```
- **S-H1b/#6 nswag**: ✅ DONE — NSwag.MSBuild OpenAPI→C# Generator. Schema-Drift pytest grün. `docs/openapi-codegen.md`.
```

- [ ] **Step 4: Commit + push docs**

```powershell
git add AUDIT_FULL_STACK_2026-05-19_v2.md CLAUDE.md
git commit -m "docs: S-H1b resolved via NSwag codegen; vault sync"
git push origin main
```

---

## Self-Review

**1. Spec coverage:**
- Audit S-H1b says: "OpenAPI-Spec Snapshot ... als pre-commit-hook gegen WPF `VramTelemetryResponse.cs` diffen. Build-Pipeline: nswag json2csharp" → Task 2 (BeforeBuild target) + Task 3 (drift pytest, functionally the same as pre-commit-hook, executed via CI/dev). ✅
- "Sources: NSwag docs, FastAPI OpenAPI integration" → referenced in Task 1 / Task 2 / docs (Task 8). ✅
- "Rationale: Eliminiert manuelle Drift" → Task 5/6/7 migrate the 4 specific DTOs the audit named. ✅
- "Estimated effort M, Risk Mittel" → Schritt-Risiko mitigiert durch (a) `global using` Shims (kein call-site Big-Bang), (b) `BeforeBuild Inputs/Outputs` incremental, (c) snapshot in git = no live-backend requirement. ✅
- "Schrittweise erstmal nur generierter Code in PBStudio.UI/Generated/" → genau das ist die `global using`-Migration in T5/T6/T7. ✅

No gaps.

**2. Placeholder scan:**
- No "TBD" / "TODO" / "implement later" anywhere.
- All XML/JSON snippets are complete.
- Task 1 Step 1 has a fallback chain for NSwag version — that's deliberate verification, not a placeholder.
- Task 5 Step 3 says "If any error like ... two options" — both options spelled out (regenerate vs call-site update), not a placeholder.

**3. Type consistency:**
- `PBStudio.UI.Generated` namespace used identically in Tasks 2, 5, 6, 7. ✅
- `ApiTypes.g.cs` filename used identically in Tasks 2, 3, 7, 8. ✅
- `openapi.snapshot.json` path used identically across all tasks. ✅
- `NSwag.MSBuild` package name + version (`14.2.0` baseline with documented fallback) consistent in Tasks 1 + 2. ✅
- `BeforeBuild` Target name used in Task 2 only — no later task references it. ✅
- `refresh-openapi-snapshot.ps1` filename consistent in Tasks 3 + 4 + 8. ✅
- Vram-type names (`VramTelemetryResponse`, `VramTelemetryEntry`, `VramTelemetrySummary`, `VramDurationStats`, `VramPeakStats`, `VramHistogramBar`) — Task 5 declares all six aliases. Task 9 only references `VramTelemetryResponse` indirectly (audit doc edit). ✅
- Test names (`test_snapshot_exists`, `test_snapshot_matches_live_backend`, `test_snapshot_schemas_consistent`, `test_generated_dtos_not_stale_relative_to_snapshot`) — Task 3 defines first three, Task 8 adds fourth. ✅

No drift.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-19-nswag-openapi-codegen.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task + two-stage review (spec-compliance + code-quality) between tasks

**2. Inline Execution** — executing-plans skill, batch with checkpoints

**Which approach?**
