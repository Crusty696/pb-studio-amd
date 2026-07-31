# T384 NSwag Clean-Build Integration

Date: 2026-07-31
Result: PASS

## Change

- NSwag generation now runs `BeforeTargets="CoreCompile"`.
- `Generated/ApiTypes.g.cs` is an unconditional Compile item, so MSBuild
  evaluation no longer omits it merely because a clean checkout has not
  generated the file yet.
- Inputs/Outputs remain incremental and the generated file remains ignored.

## Verification

- XML contract check: NSwag target is `CoreCompile` and Compile item has no
  `Condition`: PASS.
- `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore`:
  PASS, 0 warnings, 0 errors.
- `git diff --check`: PASS.
- `PBStudio.UI/PBStudio.UI.csproj` SHA-256:
  `bfb6764b41d8dceab7d5fd36a32d24ac2d700ddbbe8690be5a74c3ccee067dd0`.

The external no-generated-file clean-checkout proof remains T407.
