using System.ComponentModel;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI;

/// <summary>
/// MainWindow Code-Behind. Minimal — Logik ist im MainViewModel.
/// </summary>
public partial class MainWindow : Window
{
    private readonly ILogger<MainWindow> _logger;
    private bool _shutdownStarted;

    // AP3.1: IApiClient-Parameter entfernt — wurde nur noch für das (entfernte)
    // verfrühte BeginShutdown() in OnClosing gebraucht.
    public MainWindow(MainViewModel viewModel, ILogger<MainWindow> logger)
    {
        _logger = logger;
        InitializeComponent();
        DataContext = viewModel;
        Closing += OnClosing;
        AddHandler(ButtonBase.ClickEvent, new RoutedEventHandler(OnUiButtonClicked), true);
        AddHandler(Selector.SelectionChangedEvent, new SelectionChangedEventHandler(OnUiSelectionChanged), true);
        AddHandler(UIElement.LostKeyboardFocusEvent, new KeyboardFocusChangedEventHandler(OnUiInputCommitted), true);
        _logger.LogInformation("MainWindow initialisiert.");
    }

    private static string ControlLabel(FrameworkElement element)
    {
        var accessibleName = AutomationProperties.GetName(element);
        if (!string.IsNullOrWhiteSpace(accessibleName))
            return accessibleName;
        if (!string.IsNullOrWhiteSpace(element.Name))
            return element.Name;
        if (element is TabItem tabItem && tabItem.Header is string header && !string.IsNullOrWhiteSpace(header))
            return header;
        return "(ohne Namen)";
    }

    private static T? FindActionElement<T>(object? source) where T : DependencyObject
    {
        var current = source as DependencyObject;
        while (current is not null)
        {
            if (current is T match)
                return match;

            current = current is Visual visual
                ? VisualTreeHelper.GetParent(visual)
                : current is FrameworkContentElement content
                    ? content.Parent
                    : null;
        }

        return null;
    }

    private void OnUiButtonClicked(object sender, RoutedEventArgs e)
    {
        if (FindActionElement<ButtonBase>(e.OriginalSource) is FrameworkElement element)
            _logger.LogInformation(
                "UI-Aktion: Klick; Control={Control}; Name={Name}",
                element.GetType().Name,
                ControlLabel(element));
    }

    private void OnUiSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (FindActionElement<Selector>(e.OriginalSource) is Selector selector)
            _logger.LogInformation(
                "UI-Aktion: Auswahl; Control={Control}; Name={Name}; Hinzu={Added}; Entfernt={Removed}",
                selector.GetType().Name,
                ControlLabel(selector),
                e.AddedItems.Count,
                e.RemovedItems.Count);
    }

    private void OnUiInputCommitted(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (e.Source is TextBox textBox)
            _logger.LogInformation(
                "UI-Aktion: Eingabe abgeschlossen; Control=TextBox; Name={Name}",
                ControlLabel(textBox));
    }

    private void OnClosing(object? sender, CancelEventArgs e)
    {
        if (_shutdownStarted)
            return;

        _shutdownStarted = true;
        WeakReferenceMessenger.Default.Send(new AppShutdownMessage());
        // AP3.1/K7-Nachfix (Audit 2026-06-10): BeginShutdown() hier entfernt —
        // OnClosing feuert VOR App.OnExit; der Cancel des Shutdown-Tokens hätte
        // den SaveProjectAsync-Call in OnExit weiterhin sofort abgebrochen
        // (Save-on-Exit wäre trotz K7-Fix tot geblieben). BeginShutdown läuft
        // jetzt ausschließlich in App.OnExit NACH dem Projekt-Save.
    }
}
