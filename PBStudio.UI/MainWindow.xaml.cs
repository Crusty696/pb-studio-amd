using System.ComponentModel;
using System.Windows;
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
        _logger.LogInformation("MainWindow initialisiert.");
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
