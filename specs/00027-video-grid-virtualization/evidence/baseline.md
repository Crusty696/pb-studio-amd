# Baseline: Video-Kachelraster Virtualisierung (Spec 00027)

Datum: 2026-09-12
Komponente: PBStudio.UI/Views/VideoLibraryView.xaml

## Befund
- `VideoLibraryView.xaml` verwendet aktuell:
  ```xml
  <ListBox x:Name="VideoClipList" ... VirtualizingPanel.IsVirtualizing="True" VirtualizingPanel.VirtualizationMode="Recycling">
      <ListBox.ItemsPanel>
          <ItemsPanelTemplate>
              <WrapPanel/>
          </ItemsPanelTemplate>
      </ListBox.ItemsPanel>
  ```
- WPF-Problem: Standard-`WrapPanel` erbt von `Panel`, nicht von `VirtualizingPanel`. Dadurch schlägt die Virtualisierung trotz `VirtualizingPanel.IsVirtualizing="True"` stillschweigend fehl; alle Items (z.B. 1.000 bis 10.000) werden gleichzeitig instantiiert und gerendert.
- UI-Element-Maße:
  - `VideoThumbCard` Style in `App.xaml`: `Width="200"`, `Margin="4"`
  - `ListBoxItem` Style in `VideoLibraryView.xaml`: `Margin="2"`, `BorderThickness="2"`
  - Gesamtbreite pro Kachel: 200 + 2*4 + 2*2 + 2*2 = 216 px.
  - Gesamthöhe pro Kachel: Thumbnail (112) + Status-Strip (20) + Title/Details/Tags (~120-140) = ~280 px.
- Vorgeschlagene Lösung (TR-001):
  - Eigener `VirtualizingWrapPanel : VirtualizingPanel, IScrollInfo` in `PBStudio.UI.Controls`.
  - Keine neuen externen NuGet-Abhängigkeiten.
