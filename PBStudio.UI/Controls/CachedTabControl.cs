using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;

namespace PBStudio.UI.Controls;

/// <summary>
/// Ein TabControl-Ersatz der seine Tab-Inhalte im Visual Tree cached,
/// statt sie bei jedem Tab-Wechsel zu entladen und neu zu erstellen.
/// 
/// PROBLEM: Standardmäßig zerstört WPF TabControl den Content eines Tabs
/// wenn man wegwechselt und erstellt ihn neu wenn man zurückwechselt.
/// Das führt zu:
///   - Verlust von Fortschrittsbalken während laufender Analysen
///   - Verlust von Scroll-Positionen und UI-State
///   - Unnötiges Neurendern komplexer Views
///
/// LÖSUNG: Dieser CachedTabControl hält alle Tab-Contents parallel
/// in einem Grid. Nur der aktive Tab ist Visibility.Visible, alle
/// anderen sind Visibility.Collapsed. So bleibt der gesamte UI-State
/// (Fortschritt, Daten, Scroll, Analyse-Progress) beim Tab-Wechsel erhalten.
///
/// VERWENDUNG: Einfach <controls:CachedTabControl> statt <TabControl> in XAML.
/// Alle Properties (SelectedIndex, Styles, Triggers) funktionieren identisch.
/// </summary>
public class CachedTabControl : TabControl
{
    // Speichert die gecachten ContentPresenter pro TabItem
    private readonly Dictionary<TabItem, ContentPresenter> _cachedPresenters = new();
    private Grid? _itemsHolderPanel;

    public CachedTabControl()
    {
        // ItemContainerGenerator ist erst verfügbar nach Template-Apply
    }

    public override void OnApplyTemplate()
    {
        base.OnApplyTemplate();

        // Erstelle unser internes Grid das alle Contents hält
        _itemsHolderPanel = new Grid();

        // Suche den PART_SelectedContentHost (Standard-WPF-TabControl)
        // und ersetze ihn mit unserem Grid
        // Falls nicht gefunden: füge das Grid als Overlay hinzu
        if (GetTemplateChild("PART_SelectedContentHost") is ContentPresenter contentHost)
        {
            // Verstecke den Standard-ContentPresenter
            contentHost.Visibility = Visibility.Collapsed;

            // Füge unser Grid als Geschwister ein
            if (contentHost.Parent is Grid parentGrid)
            {
                // Gleiche Grid.Row/Column wie der ContentPresenter
                Grid.SetRow(_itemsHolderPanel, Grid.GetRow(contentHost));
                Grid.SetColumn(_itemsHolderPanel, Grid.GetColumn(contentHost));
                Grid.SetRowSpan(_itemsHolderPanel, Grid.GetRowSpan(contentHost));
                Grid.SetColumnSpan(_itemsHolderPanel, Grid.GetColumnSpan(contentHost));
                parentGrid.Children.Add(_itemsHolderPanel);
            }
        }
        else
        {
            // Fallback: Suche das Content-Panel im Template
            // MaterialDesign nutzt ggf. andere Namen
            if (GetTemplateChild("ContentPanel") is Panel panel)
            {
                panel.Children.Add(_itemsHolderPanel);
            }
        }

        // Initialisiere vorhandene Tabs
        EnsureAllTabsCached();
        UpdateVisibility();
    }

    protected override void OnSelectionChanged(SelectionChangedEventArgs e)
    {
        base.OnSelectionChanged(e);

        if (_itemsHolderPanel != null)
        {
            EnsureAllTabsCached();
            UpdateVisibility();
        }
    }

    /// <summary>
    /// Stellt sicher dass jeder TabItem einen gecachten ContentPresenter hat.
    /// </summary>
    private void EnsureAllTabsCached()
    {
        if (_itemsHolderPanel == null) return;

        for (int i = 0; i < Items.Count; i++)
        {
            var tabItem = GetTabItem(i);
            if (tabItem == null) continue;

            if (!_cachedPresenters.ContainsKey(tabItem))
            {
                // Erstelle ContentPresenter und cache ihn
                var cp = new ContentPresenter
                {
                    Visibility = Visibility.Collapsed,
                };

                // Content vom TabItem übernehmen
                if (tabItem.Content is UIElement uiContent)
                {
                    cp.Content = uiContent;
                    tabItem.Content = null; // Aus TabItem entfernen (nur 1 Parent erlaubt)
                }
                else if (tabItem.Content != null)
                {
                    cp.Content = tabItem.Content;
                    cp.ContentTemplate = tabItem.ContentTemplate;
                    tabItem.Content = null;
                }

                _cachedPresenters[tabItem] = cp;
                _itemsHolderPanel.Children.Add(cp);
            }
        }
    }

    /// <summary>
    /// Setzt nur den aktiven Tab-Content auf Visible, alle anderen auf Collapsed.
    /// </summary>
    private void UpdateVisibility()
    {
        if (_itemsHolderPanel == null) return;

        var selectedTab = GetTabItem(SelectedIndex);

        foreach (var kvp in _cachedPresenters)
        {
            kvp.Value.Visibility = (kvp.Key == selectedTab)
                ? Visibility.Visible
                : Visibility.Collapsed;
        }
    }

    /// <summary>
    /// Holt ein TabItem per Index (unterstützt sowohl direkte TabItems als auch generierte Container).
    /// </summary>
    private TabItem? GetTabItem(int index)
    {
        if (index < 0 || index >= Items.Count) return null;

        if (Items[index] is TabItem directItem)
            return directItem;

        return ItemContainerGenerator.ContainerFromIndex(index) as TabItem;
    }
}
