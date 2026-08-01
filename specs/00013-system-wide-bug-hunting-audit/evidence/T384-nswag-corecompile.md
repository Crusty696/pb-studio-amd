# T384 NSwag Clean-Build Integration

Date: 2026-07-31
Result: PASS

## Change

- NSwag generation now runs `BeforeTargets="CoreCompile"`.
- `obj/Generated/ApiTypes.g.cs` is an unconditional Compile item, so MSBuild
  evaluation no longer omits it merely because a clean checkout has not
  generated the file yet.
- Inputs/Outputs remain incremental and generation no longer depends on an
  ignored source-tree file.

## Verification

- XML contract check: NSwag target is `CoreCompile` and Compile item has no
  `Condition`: PASS.
- `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore`:
  PASS, 0 warnings, 0 errors.
- `git diff --check`: PASS.
- `PBStudio.UI/PBStudio.UI.csproj` SHA-256:
  `da891f2c76c98a615cbf164bc03736da13cc84ed0ccc101df07b098b70e2e9c7`.
- `PBStudio.UI/nswag.json` SHA-256:
  `ec39d10f07d68816c3a2d5af1f2c14c49163d29d95812fdf5e6ce59ebb8846c0`.

The external no-generated-file clean-checkout proof remains T407.
