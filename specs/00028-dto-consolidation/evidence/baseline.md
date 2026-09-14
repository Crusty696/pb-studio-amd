# Baseline: C#-Transporttypen auf NSwag konsolidieren (Spec 00028)

Datum: 2026-09-12

## Befund & Ausgangslage
- NSwag generiert `PBStudio.UI/obj/Generated/ApiTypes.g.cs` im Namespace `PBStudio.UI.Generated` deterministisch aus `PBStudio.UI/openapi.snapshot.json`.
- `Tests/test_openapi_snapshot_drift.py` prüft 4/4 Tests grün: Snapshot ist 100% konsistent mit dem FastAPI-Backend.
- Bisherige Teilmigrationen:
  - `ThumbstripResponse.cs` -> `global using ThumbstripResponse = PBStudio.UI.Generated.ThumbstripResponse;`
  - `ClipwaveResponse.cs` -> `global using ClipwaveResponse = PBStudio.UI.Generated.ClipwaveResponse;`
  - `BrainExplainResponse.cs` -> `global using BrainAxisContribution = PBStudio.UI.Generated.BrainAxisContribution;`
  - `SpectralDataModel.cs` -> UI-Adapter `SpectralDataModel.FromTransport(Generated.SpectralData)`
  - `AudioClip.cs` -> UI-Adapter `AudioAnalysisResult.FromTransport(Generated.AudioAnalysisResult)`
  - `VramTelemetry.cs` -> UI-Adapter `VramHealthSingleResponse.ToMultiModelSnapshot()`
- Unterscheidung nach FR-001:
  - **Reine DTOs / Transport**: Werden über NSwag-Generierung abgebildet.
  - **Reine UI-/Observable-Modelle**: `VideoClipModel`, `AudioClipModel`, `TimelineEntryModel`, `BeatMarkerViewModel`, `SongSegmentModel`, `WaveformBarModel` bleiben eigenständige UI-Modelle mit `ObservableObject`-Logik.
