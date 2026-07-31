# T389 .NET and NuGet Lock

Date: 2026-07-31
Result: PASS

## Change

- `global.json` pins SDK `9.0.316`, disables roll-forward and prerelease SDKs.
- `packages.lock.json` records the complete direct and transitive graph.
- MSBuild enables lock-file generation and fail-closed locked restore.
- Existing T384 NSwag `CoreCompile` integration remains intact.

## Verification

- Locked restore: PASS.
- Release build with `--no-restore`: PASS, 0 warnings, 0 errors.
- JSON/XML parsing and `git diff --check`: PASS.
- `global.json`: `9c69ebf15e08f944921f34b4cadf50e879d3467bb847d609b6ae079fc120d192`.
- `packages.lock.json`: `fd2581cd9160f49243ce6feae30a05006bcb90c4556491f07da436213e8df0c2`.
- `PBStudio.UI.csproj`: `37394a5778df6cbbc0065a70e4e0d0f3a6135a43e92509b85c92131b02ab01a1`.

The external clean-checkout proof remains T407.
