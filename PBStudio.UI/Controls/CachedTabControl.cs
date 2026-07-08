using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Automation.Peers;

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

        // Suche den PART_SelectedContentHost (Standard-WPF + MaterialDesign).
        // Statt den ContentHost zu verstecken und ein Geschwister-Grid
        // einzufügen (scheitert wenn der Parent kein Grid ist — MaterialDesign
        // wrappt den ContentPresenter in einer Border), ersetzen wir den
        // ContentHost template-agnostisch an exakt seiner Stelle im Visual Tree.
        var contentHost = GetTemplateChild("PART_SelectedContentHost") as FrameworkElement;
        if (contentHost != null && ReplaceInVisualParent(contentHost, _itemsHolderPanel))
        {
            // erfolgreich an Stelle des ContentHost eingehängt
        }
        else if (GetTemplateChild("ContentPanel") is Panel panel)
        {
            // Fallback: bekanntes Content-Panel im Template
            panel.Children.Add(_itemsHolderPanel);
        }

        // Initialisiere vorhandene Tabs
        EnsureAllTabsCached();
        UpdateVisibility();
    }

    /// <summary>
    /// Ersetzt <paramref name="oldElement"/> durch <paramref name="newElement"/>
    /// im Visual-Parent, unabhängig vom Parent-Typ (Panel, Decorator/Border,
    /// ContentControl, Border). Gibt false zurück wenn kein bekannter Parent-Typ.
    /// </summary>
    private static bool ReplaceInVisualParent(FrameworkElement oldElement, FrameworkElement newElement)
    {
        var parent = VisualTreeHelper.GetParent(oldElement) as DependencyObject;

        switch (parent)
        {
            case Panel panel:
            {
                int idx = panel.Children.IndexOf(oldElement);
                if (idx < 0) return false;
                // Layout-Attached-Properties (Grid/DockPanel) vom Original übernehmen
                Grid.SetRow(newElement, Grid.GetRow(oldElement));
                Grid.SetColumn(newElement, Grid.GetColumn(oldElement));
                Grid.SetRowSpan(newElement, Grid.GetRowSpan(oldElement));
                Grid.SetColumnSpan(newElement, Grid.GetColumnSpan(oldElement));
                panel.Children.RemoveAt(idx);
                panel.Children.Insert(idx, newElement);
                return true;
            }
            case Border border:
                border.Child = newElement;
                return true;
            case Decorator decorator:
                decorator.Child = newElement;
                return true;
            case ContentControl contentControl:
                contentControl.Content = newElement;
                return true;
            case ContentPresenter contentPresenter:
                contentPresenter.Content = newElement;
                return true;
            default:
                return false;
        }
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

    /// <summary>
    /// Gibt den aktuell aktiven ContentPresenter zurück (für UI-Automation).
    /// </summary>
    public ContentPresenter? GetActiveContentPresenter()
    {
        var selectedTab = GetTabItem(SelectedIndex);
        if (selectedTab != null && _cachedPresenters.TryGetValue(selectedTab, out var presenter))
        {
            return presenter;
        }
        return null;
    }

    protected override AutomationPeer OnCreateAutomationPeer()
    {
        return new CachedTabControlAutomationPeer(this);
    }
}

/// <summary>
/// AutomationPeer für CachedTabControl, der den geladenen Content-Tree für UI-Automation (UIA) freigibt.
/// </summary>
public class CachedTabControlAutomationPeer : TabControlAutomationPeer
{
    private readonly CachedTabControl _control;

    public CachedTabControlAutomationPeer(CachedTabControl control) : base(control)
    {
        _control = control;
    }

    protected override List<AutomationPeer> GetChildrenCore()
    {
        var children = base.GetChildrenCore() ?? new List<AutomationPeer>();

        var activePresenter = _control.GetActiveContentPresenter();
        if (activePresenter != null)
        {
            var peer = CreatePeerForElement(activePresenter);
            if (peer != null)
            {
                children.Add(peer);
            }
        }

        return children;
    }
}
