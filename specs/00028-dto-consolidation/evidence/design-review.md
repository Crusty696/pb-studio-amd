# Design Review: DTO-Konsolidierung (Spec 00028)

Datum: 2026-09-12

## Architektur & Mapping-Prinzip
1. **Keine Breaking Changes an `IApiClient.cs`**:
   - `IApiClient.cs` Kontrakte bleiben stabil, damit ViewModels und bestehende Bindings ohne Regressionen weiterarbeiten.
2. **DTO-Inventar & Kategorisierung (FR-001)**:
   - **Kategorie A: Direkt via NSwag generiert & aliasiert (`global using`)**:
     - `ThumbstripResponse` -> `Generated.ThumbstripResponse`
     - `ClipwaveResponse` -> `Generated.ClipwaveResponse`
     - `BrainAxisContribution` -> `Generated.BrainAxisContribution`
   - **Kategorie B: UI-Adapter über NSwag-Transporttypen (FR-003)**:
     - `AudioAnalysisResult.FromTransport(Generated.AudioAnalysisResult)`
     - `SpectralDataModel.FromTransport(Generated.SpectralData)`
     - `VramHealthSingleResponse.ToMultiModelSnapshot()`
     - `VideoClipInfo`: Deserialisierung mit SnakeCaseJson & Stage-Mapping
   - **Kategorie C: UI-spezifische / Nicht-OpenAPI-Typen (Begründung nach FR-003)**:
     - `TimelineEntryModel`: WPF-Observable-Model für Drag-and-Drop, Lane-Rendering, Selektion
     - `VideoClipModel` / `AudioClipModel`: Enthält WPF-Bitmaps (`BitmapImage`), UI-Zustände, Formatierung
     - `SongSegmentModel`, `WaveformBarModel`, `BeatMarkerViewModel`: Reine Canvas-/Rendering-Modelle
     - `PullProgressEvent`, `ChatEvent`: Streaming SSE-Events, keine synchronen REST-Schemas
     - `BrainExplainResponse`: NSwag 14 generiert leere Klassen für Pydantic `anyOf: [string, null]` (`narrative`, `segment_type`); daher manuell behalten mit generiertem `BrainAxisContribution`.
