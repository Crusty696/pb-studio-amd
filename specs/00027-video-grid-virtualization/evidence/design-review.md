# Design Review: VirtualizingWrapPanel (Spec 00027)

Datum: 2026-09-12
Klasse: PBStudio.UI.Controls.VirtualizingWrapPanel

## Architektur
1. **Basisklasse & Schnittstellen**:
   - `VirtualizingPanel`, `IScrollInfo`.
2. **Eigenschaften**:
   - `ItemWidth` (DependencyProperty, double, Default: 216.0)
   - `ItemHeight` (DependencyProperty, double, Default: 280.0)
3. **IScrollInfo-Kontrakt**:
   - Berechnet `ExtentWidth` (`columns * ItemWidth`), `ExtentHeight` (`totalRows * ItemHeight`).
   - Berechnet `ViewportWidth`, `ViewportHeight`.
   - `SetVerticalOffset`, `SetHorizontalOffset` mit InvalidateMeasure und `ScrollOwner?.InvalidateScrollInfo()`.
   - `LineUp`, `LineDown`, `PageUp`, `PageDown`, `MouseWheelUp`, `MouseWheelDown`.
   - `BringIndexIntoView(int index)` für präzises Anspringen von Kacheln.
4. **Virtualisierung & Recycling (FR-002)**:
   - Berechnet Spalten aus Viewport-Breite: `cols = Math.Max(1, (int)Math.Floor(availableWidth / ItemWidth))`.
   - Berechnet sichtbare Zeilen: `firstVisibleRow = floor(vOffset / ItemHeight)`, `lastVisibleRow = floor((vOffset + vHeight) / ItemHeight)`.
   - Puffer: maximal 2 Zeilen vor und nach Sichtbereich (`firstRealizedRow = max(0, firstVisibleRow - 2)`, `lastRealizedRow = min(totalRows - 1, lastVisibleRow + 2)`).
   - Verwendet `IRecyclingItemContainerGenerator` zum Recyceln von Containern außerhalb des Zielbereichs.
5. **Robustheit (FR-003, FR-004)**:
   - Schutz vor Division durch 0 / unendlichen Breiten.
   - Schutz vor leeren Listen.
   - Kein Stale-State durch sauberes Rebinding beim Container-Recycling.
