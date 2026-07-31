# T398 Native C# Test Implementation

Date: 2026-07-31
Result: PASS

## Change

- Added `PBStudio.UI.Tests` targeting `net9.0-windows` with WPF and locked restore.
- Pinned `Microsoft.NET.Test.Sdk` 18.8.1 and MSTest 4.3.3 with a complete independent NuGet lock.
- Added 28 tests with 135 concrete assertions across transport adapters, Settings, ApiClient, ViewModels, ProjectService, Timeline and CachedTabControl.
- Stateful WPF tests use bounded STA/Dispatcher execution and non-parallel fixtures.
- `bin/` and `obj/` are ignored and are not deliverables.

## Verification

- XML, exact package pins, lock graph, project reference and product signatures: PASS.
- 28/28 test attributes and inventory mapping: PASS.
- Independent read-only review found no mock/reflection illusion and confirmed real public product paths.
- Independent review: PASS.
- Runtime test execution and Release build remain intentionally assigned to T406.
