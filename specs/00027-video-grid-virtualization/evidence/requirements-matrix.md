# Requirements Matrix: Video Grid Virtualization (Spec 00027)

Datum: 2026-09-12

| Anforderungs-ID | Anforderung | Implementierung | Verifikation | Status |
|---|---|---|---|---|
| FR-001 | 2D mehrspaltiges umbrechendes Kachelraster erhalten | `VirtualizingWrapPanel.cs` mit dyn. Spaltenberechnung basierend auf `ItemWidth` | `VirtualizingWrapPanelTests.CalculateColumns_ReturnsExpectedColumnsAndHandlesNarrowWidth` | VERIFIZIERT |
| FR-002 | Nur sichtbare Zeilen plus max. 2 Pufferzeilen realisieren Container; Recycling aktiv | `MeasureOverride` berechnet `firstRealizedRow` & `lastRealizedRow`, recycelt Container außerhalb via `IRecyclingItemContainerGenerator.Recycle` | `VirtualizingWrapPanelTests.LargeCollection_RealizesOnlyVisibleRowsPlusBuffers`, `TenThousandItems_ContainerCountRemainsBounded` (10.000 Items: <= 28 Container realisiert) | VERIFIZIERT |
| FR-003 | Resize, DPI, leeres Grid, schmale Breite, Start/Ende ohne Endlosschleife oder Crash | `CalculateColumns` klammert Spalten auf >= 1; NaN/Infinity/<=0 abgefangen; Viewport/Offset-Klammerung | `VirtualizingWrapPanelTests.EmptyCollection_DoesNotThrowAndHasZeroContainers`, `CalculateColumns_ReturnsExpectedColumnsAndHandlesNarrowWidth` | VERIFIZIERT |
| FR-004 | Selection, Scroll, MakeVisible, Collection-Reset ohne alte Thumbnails/Zustände | `CleanupAllContainers` bei Reset/Remove/Replace; `BringIndexIntoView`, `MakeVisible` implementiert | `VirtualizingWrapPanelTests.ScrollAndCollectionReset_RecyclesContainersProperly`, `test_viewmodel_binding_wiring.py` | VERIFIZIERT |
| TR-001 | Eigener `VirtualizingPanel` mit `IScrollInfo` und `IRecyclingItemContainerGenerator`, keine NuGet-Deps | `PBStudio.UI/Controls/VirtualizingWrapPanel.cs` implementiert `VirtualizingPanel, IScrollInfo` | `dotnet build -c Release PBStudio.UI` (0 Fehler, 0 Warnungen); keine neuen Packages | VERIFIZIERT |
