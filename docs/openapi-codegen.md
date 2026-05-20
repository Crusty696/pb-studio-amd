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
