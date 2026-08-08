# T406 Native .NET and WPF Release Gate

**Status:** PASS

**Run:** 2026-08-01T21:26:25+02:00

**Baseline commit:** `72e721b`

## Environment and commands

- SDK `9.0.316`, exactly pinned by `global.json` with roll-forward disabled.
- `dotnet restore PBStudio.UI.Tests/PBStudio.UI.Tests.csproj --locked-mode --force-evaluate`
- `dotnet test PBStudio.UI.Tests/PBStudio.UI.Tests.csproj -c Release --no-restore -p:TreatWarningsAsErrors=true -p:ContinuousIntegrationBuild=true`
- `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release --no-restore -p:TreatWarningsAsErrors=true -p:ContinuousIntegrationBuild=true`

## Results

- Locked restore: PASS for `PBStudio.UI` and `PBStudio.UI.Tests`; lock files unchanged.
- Native tests: **28 passed, 0 failed, 0 skipped**.
- WPF Release build: **0 warnings, 0 errors**.
- NSwag generation: PASS; `obj/Generated/ApiTypes.g.cs` generated at 170,703 bytes and compiled.
- TRX, text logs and MSBuild binary logs are stored in `evidence/T406-dotnet-quality/`.

## Evidence hashes

| Artifact | SHA-256 |
|---|---|
| `restore-tests.log` | `a49b6a4aeb4d53b8d922daa8b2ae914775d4b6d2c8b85eb819103845ea73a91a` |
| `native-tests.log` | `e8cb350dc8c9fda0e0c1ac89777b81f19e6eefdf0a088b16e405036b7d839f4a` |
| `T406-native-tests.trx` | `796bd0264902f4cbe70c425c7d15eae1804af63d959f51302dd757f4b750a444` |
| `native-tests.binlog` | `4d348e5084426c5107ab5c73c64724c083020946cd4df92581934ab408d76096` |
| `wpf-release.log` | `f5ae642d61760d114c9106eb54c3d8726f95f88de3c5b1827e928d35d5493564` |
| `wpf-release.binlog` | `616f59add4a9f23807e01325f0a835195d14b77a2d223a788204989b9efc89b5` |
