# T398 Native C# Test Inventory

Status: implementation complete; execution and Release build deferred to T406.

## Locked test project

- Target: `net9.0-windows`, WPF enabled, nullable enabled.
- `Microsoft.NET.Test.Sdk` exactly `18.8.1`.
- `MSTest.TestAdapter` exactly `4.3.3`.
- `MSTest.TestFramework` exactly `4.3.3`.
- `packages.lock.json` contains exact ranges and NuGet content hashes.
- Product reference: `PBStudio.UI/PBStudio.UI.csproj`.

## Contract tests

| File | Count | Contracts |
|---|---:|---|
| `TransportContractTests.cs` | 4 | Generated audio adapter, complete spectral adapter, single→multi VRAM adapter, negative result DTO JSON |
| `SettingsServiceTests.cs` | 4 | Missing-file defaults, malformed JSON truth, atomic verified roundtrip, deterministic write failure |
| `ApiClientContractTests.cs` | 4 | Chat clear HTTP truth, GPU cleanup DTO, timeline-preview cancellation propagation |
| `ViewModelAndProjectServiceTests.cs` | 9 | Chat clear preserve/reset, Settings load/save failures, GPU failure, mode/project recommendation ordering, failed save/close, A→B context invalidation |
| `TimelineViewModelTests.cs` | 5 | First/last selection, scrub clamp, nudge collision, trim bounds, unsafe delete rejection, stable sort/selection |
| `CachedTabControlTests.cs` | 2 | Presenter reparenting exactly once, repeated template reapply with content identity |
| **Total** | **28** | FR-350 native DTO/service/ViewModel/cancellation/control coverage |

## T406 execution gate

Run only in T406 with locked restore:

```powershell
dotnet restore PBStudio.UI.Tests\PBStudio.UI.Tests.csproj --locked-mode
dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release --no-restore
dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --no-restore
```

T398 does not claim test or build PASS. T406 owns execution logs, binlog and
zero-warning/zero-error evidence.
